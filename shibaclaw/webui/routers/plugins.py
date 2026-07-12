import sys
import asyncio
import re
import httpx
import tempfile
import zipfile
import shutil
import importlib
import subprocess
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

from shibaclaw.integrations.registry import discover_plugins, discover_local_plugins
from shibaclaw.tts.registry import discover_tts_plugins
from shibaclaw.config.loader import load_config
from shibaclaw.config.paths import get_plugins_dir
from shibaclaw.helpers.system import is_running_as_exe
from shibaclaw import __version__
from shibaclaw.agent.knowledge_manager import RAG_AVAILABLE

_plugin_lock = asyncio.Lock()

def with_plugin_lock(func):
    import functools
    @functools.wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if _plugin_lock.locked():
            return JSONResponse({"ok": False, "error": "Another plugin operation is in progress. Please wait."}, status_code=409)
        async with _plugin_lock:
            return await func(request, *args, **kwargs)
    return wrapper

async def api_list_plugins(request: Request) -> JSONResponse:
    cfg = load_config()
    installed_channels = {**discover_plugins(), **discover_local_plugins()}

    integrations = []
    for name, cls in installed_channels.items():
        enabled = False
        section = getattr(cfg.channels, name, None)
        if isinstance(section, dict):
            enabled = section.get("enabled", False)
        elif section:
            enabled = getattr(section, "enabled", False)
        integrations.append({
            "name": name,
            "display_name": getattr(cls, "display_name", name),
            "type": "channel",
            "enabled": enabled,
            "installed": True
        })

    tts = []
    installed_tts = discover_tts_plugins()
    for name, cls in installed_tts.items():
        enabled = (cfg.audio.tts_provider == name) if hasattr(cfg.audio, "tts_provider") else False
        tts.append({
            "name": name,
            "display_name": getattr(cls, "display_name", name),
            "type": "tts",
            "enabled": enabled,
            "installed": True
        })

    rag = []
    if RAG_AVAILABLE:
        rag.append({
            "name": "shibaclaw-rag",
            "display_name": "Local RAG & Knowledge Base",
            "type": "rag",
            "enabled": True,
            "installed": True
        })

    available = []

    if not RAG_AVAILABLE:
        available.append({
            "name": "shibaclaw-rag",
            "display_name": "Local RAG & Knowledge Base",
            "type": "rag",
            "description": "Enables local semantic search and document uploading (PDF, CSV, HTML, TXT) using FAISS and HuggingFace sentence-transformers.",
            "installed": False
        })

    if "supertonic" not in installed_tts:
        available.append({
            "name": "shibaclaw-tts-supertonic",
            "display_name": "Supertonic TTS",
            "type": "tts",
            "description": "Local offline Text-to-Speech using Supertonic ONNX engine.",
            "installed": False
        })

    if "whatsapp" not in installed_channels:
        available.append({
            "name": "shibaclaw-channel-whatsapp",
            "display_name": "WhatsApp",
            "type": "channel",
            "description": "WhatsApp channel integration using a Node.js bridge (Baileys).",
            "installed": False
        })

    return JSONResponse({
        "plugins": integrations + tts + rag,
        "available": available
    })


async def _hot_reload_plugins(pre_start_hook=None):
    """Reload plugin modules and restart only the gateway subprocess.

    Unlike the old ``_do_restart()`` this function does **not** kill the
    WebUI server process or call ``os._exit()``.  This is critical for
    frozen ``.exe`` builds (PyInstaller) where ``CTRL_C_EVENT`` +
    ``os._exit(0)`` causes the application to hang with no way to recover.

    Flow:
    1. Wait briefly so the HTTP response reaches the client.
    2. Purge cached ``shibaclaw_*`` modules from ``sys.modules``.
    3. Invalidate importlib caches for local plugin discovery.
    4. Restart **only** the gateway subprocess via :func:`restart_gateway_only`.
    """
    await asyncio.sleep(1.5)

    # Purge any cached plugin modules so re-discovery works
    stale = [k for k in sys.modules if k.startswith("shibaclaw_")]
    for k in stale:
        del sys.modules[k]

    importlib.invalidate_caches()

    # Restart only the gateway subprocess — the WebUI stays alive
    from shibaclaw.webui.routers.system import restart_gateway_only
    restart_gateway_only(pre_start_hook=pre_start_hook)


async def _install_plugin_exe(package: str) -> JSONResponse:
    plugins_dir = get_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    
    tag = f"v{__version__}" if __version__ != "dev" else "main"
    zip_url = f"https://github.com/RikyZ90/ShibaClaw/archive/refs/{'tags/' + tag if tag != 'main' else 'heads/main'}.zip"
    
    try:
        logger.info("Downloading plugin {} from {}", package, zip_url)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "repo.zip"
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                resp = await client.get(zip_url)
                if resp.status_code == 404 and tag != "main":
                    logger.warning("Plugin archive for {} not found, falling back to main branch", tag)
                    zip_url = "https://github.com/RikyZ90/ShibaClaw/archive/refs/heads/main.zip"
                    resp = await client.get(zip_url)
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
            
            logger.info("Extracting plugin {}", package)
            with zipfile.ZipFile(tmp_path, 'r') as z:
                root_folder = z.namelist()[0].split('/')[0]
                target_prefix = f"{root_folder}/plugins/{package}/"
                
                plugin_files = [f for f in z.namelist() if f.startswith(target_prefix)]
                if not plugin_files:
                    return JSONResponse({"ok": False, "error": f"Plugin {package} not found in release archive."}, status_code=404)
                
                pkg_snake_case = package.replace("-", "_")
                target_dir = plugins_dir / pkg_snake_case
                update_dir = plugins_dir / f".update_{pkg_snake_case}"
                
                if update_dir.exists():
                    shutil.rmtree(update_dir, ignore_errors=True)
                
                for f in plugin_files:
                    if f.endswith('/'):
                        continue
                    rel_path = f[len(target_prefix):]
                    if not rel_path:
                        continue
                    
                    if rel_path in ("pyproject.toml", "README.md"):
                        continue
                        
                    if rel_path.startswith(f"{pkg_snake_case}/"):
                        dest_path = update_dir / rel_path[len(f"{pkg_snake_case}/"):]
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(f) as zf, open(dest_path, "wb") as out:
                            shutil.copyfileobj(zf, out)
        
        importlib.invalidate_caches()

        def _apply_install():
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            if update_dir.exists():
                shutil.move(str(update_dir), str(target_dir))

        asyncio.create_task(_hot_reload_plugins(pre_start_hook=_apply_install))
        return JSONResponse({
            "ok": True,
            "stdout": f"Plugin {package} downloaded and extracted locally.",
            "restarting": True
        })
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return JSONResponse({"ok": False, "error": f"Plugin archive not found for version {tag}. Please update ShibaClaw first."}, status_code=404)
        logger.exception("Plugin installation failed (HTTP Error)")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    except Exception as e:
        logger.exception("Plugin installation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def _install_plugin_source(package: str) -> JSONResponse:
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent
    local_path = workspace_root / "plugins" / package
    tag = f"v{__version__}" if __version__ != "dev" else "main"
    
    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    if package == "shibaclaw-rag":
        is_source = (workspace_root / "pyproject.toml").exists()
        if is_source:
            cmd = [sys.executable, "-m", "pip", "install", "-e", ".[rag]"]
            extra_kwargs["cwd"] = str(workspace_root)
        else:
            target = f"shibaclaw[rag]=={__version__}" if __version__ != "dev" else "shibaclaw[rag]"
            cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", target]
    elif local_path.is_dir():
        install_target = str(local_path)
        cmd = [sys.executable, "-m", "pip", "install", install_target]
    else:
        # tag already computed at function top
        install_target = f"git+https://github.com/RikyZ90/ShibaClaw.git@{tag}#subdirectory=plugins/{package}"
        cmd = [sys.executable, "-m", "pip", "install", install_target]

    logger.info("Installing plugin: {}", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **extra_kwargs
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            if tag != "main":
                logger.warning("Pip install for tag {} failed, retrying with main branch...", tag)
                install_target = f"git+https://github.com/RikyZ90/ShibaClaw.git@main#subdirectory=plugins/{package}"
                cmd[-1] = install_target
                logger.info("Retrying pip install: {}", " ".join(cmd))
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **extra_kwargs
                )
                stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return JSONResponse({
                    "ok": False,
                    "error": stderr.decode().strip(),
                    "stdout": stdout.decode()
                }, status_code=500)
            
        importlib.invalidate_caches()


        asyncio.create_task(_hot_reload_plugins())
        return JSONResponse({
            "ok": True,
            "stdout": stdout.decode().strip(),
            "restarting": True
        })
    except Exception as e:
        logger.exception("Plugin installation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@with_plugin_lock
async def api_install_plugin(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    
    package = body.get("package")
    if not package:
        return JSONResponse({"error": "package is required"}, status_code=400)

    if not re.match(r"^shibaclaw-[a-zA-Z0-9_\-]+$", package):
        return JSONResponse({"error": "Only shibaclaw official plugins can be installed"}, status_code=400)

    is_exe = is_running_as_exe()
    if is_exe and package == "shibaclaw-rag":
        return JSONResponse({
            "ok": False,
            "error": "The Local RAG plugin requires complex external ML dependencies (langchain, faiss, etc.) which cannot be dynamically installed in the frozen .exe version. Please run ShibaClaw from source to use this feature."
        }, status_code=400)

    if is_exe:
        return await _install_plugin_exe(package)
    else:
        return await _install_plugin_source(package)


@with_plugin_lock
async def api_uninstall_plugin(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    
    package = body.get("package")
    if not package:
        return JSONResponse({"error": "package is required"}, status_code=400)

    if not re.match(r"^shibaclaw-[a-zA-Z0-9_\-]+$", package):
        return JSONResponse({"error": "Only shibaclaw official plugins can be uninstalled"}, status_code=400)

    is_exe = is_running_as_exe()
    if is_exe:
        if package == "shibaclaw-rag":
            return JSONResponse({
                "ok": False, 
                "info": "The Local RAG plugin cannot be uninstalled in the .exe version. Its dependencies are not dynamically managed."
            }, status_code=400)
            
        pkg_snake_case = package.replace("-", "_")
        target_dir = get_plugins_dir() / pkg_snake_case
        
        try:
            if not target_dir.exists():
                return JSONResponse({"ok": False, "error": f"Plugin {package} is not installed locally."}, status_code=404)

            def _apply_uninstall():
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)

            importlib.invalidate_caches()

            asyncio.create_task(_hot_reload_plugins(pre_start_hook=_apply_uninstall))
            return JSONResponse({
                "ok": True,
                "stdout": f"Plugin {package} folder scheduled for deletion.",
                "restarting": True
            })
        except Exception as e:
            logger.exception("Plugin uninstallation failed in local dir")
            return JSONResponse({"ok": False, "error": f"Failed to delete plugin folder: {str(e)}"}, status_code=500)

    if package == "shibaclaw-rag":
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "uninstall",
            "-y",
            "langchain",
            "langchain-community",
            "langchain-huggingface",
            "faiss-cpu",
            "sentence-transformers",
            "pypdf",
            "beautifulsoup4",
        ]
    else:
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y", package]
    
    logger.info("Uninstalling plugin: {}", " ".join(cmd))
    
    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **extra_kwargs
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return JSONResponse({
                "ok": False,
                "error": stderr.decode().strip(),
                "stdout": stdout.decode()
            }, status_code=500)
            
        importlib.invalidate_caches()

        asyncio.create_task(_hot_reload_plugins())
        return JSONResponse({
            "ok": True,
            "stdout": stdout.decode().strip(),
            "restarting": True
        })
    except Exception as e:
        logger.exception("Plugin uninstallation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
