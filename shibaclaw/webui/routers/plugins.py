import sys
import asyncio
from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

from shibaclaw.integrations.registry import discover_plugins
from shibaclaw.tts.registry import discover_tts_plugins
from shibaclaw.config.loader import load_config

async def api_list_plugins(request: Request) -> JSONResponse:
    cfg = load_config()
    installed_channels = discover_plugins()
    from shibaclaw.agent.knowledge_manager import RAG_AVAILABLE

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


async def api_install_plugin(request: Request) -> JSONResponse:

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    
    package = body.get("package")
    if not package:
        return JSONResponse({"error": "package is required"}, status_code=400)

    import re
    if not re.match(r"^shibaclaw-[a-zA-Z0-9_\-]+$", package):
        return JSONResponse({"error": "Only shibaclaw official plugins can be installed"}, status_code=400)

    from shibaclaw.helpers.system import is_running_as_exe
    is_exe = is_running_as_exe()
    if is_exe and package == "shibaclaw-rag":
        return JSONResponse({
            "ok": False,
            "error": "The Local RAG plugin requires complex external ML dependencies (langchain, faiss, etc.) which cannot be dynamically installed in the frozen .exe version. Please run ShibaClaw from source to use this feature."
        }, status_code=400)

    from shibaclaw.webui.routers.system import (
        _restart_callback,
        _schedule_restart_outside_loop,
        _graceful_shutdown_server,
        _shutdown_callback
    )

    async def _do_restart():
        await asyncio.sleep(1.5)
        if _shutdown_callback is not None:
            try:
                _shutdown_callback()
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
        if _restart_callback is not None:
            _restart_callback()
        else:
            _schedule_restart_outside_loop(delay=2.0)
            _graceful_shutdown_server()

    if is_exe:
        import httpx
        import tempfile
        import zipfile
        import shutil
        from pathlib import Path
        from shibaclaw.config.paths import get_plugins_dir
        from shibaclaw import __version__
        
        plugins_dir = get_plugins_dir()
        plugins_dir.mkdir(parents=True, exist_ok=True)
        
        tag = f"v{__version__}" if __version__ != "dev" else "main"
        zip_url = f"https://github.com/RikyZ90/ShibaClaw/archive/refs/{'tags/' + tag if tag != 'main' else 'heads/main'}.zip"
        
        try:
            logger.info("Downloading plugin {} from {}", package, zip_url)
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(zip_url)
                resp.raise_for_status()
                
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp.write(resp.content)
                    tmp_path = tmp.name
                    
            logger.info("Extracting plugin {}", package)
            with zipfile.ZipFile(tmp_path, 'r') as z:
                root_folder = z.namelist()[0].split('/')[0]
                target_prefix = f"{root_folder}/plugins/{package}/"
                
                plugin_files = [f for f in z.namelist() if f.startswith(target_prefix)]
                if not plugin_files:
                    return JSONResponse({"ok": False, "error": f"Plugin {package} not found in release archive."}, status_code=404)
                
                short_name = package.replace("shibaclaw-channel-", "").replace("shibaclaw-tts-", "").replace("shibaclaw_", "")
                target_dir = plugins_dir / short_name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True)
                
                for f in plugin_files:
                    if f.endswith('/'):
                        continue
                    rel_path = f[len(target_prefix):]
                    if not rel_path:
                        continue
                    
                    # Se c'è una cartella col nome del pacchetto (es. shibaclaw_channel_whatsapp),
                    # estraiamo direttamente il suo contenuto, ignorando il resto
                    # (questo adatta la struttura di pip a una struttura locale)
                    pkg_snake_case = package.replace("-", "_")
                    if rel_path.startswith(f"{pkg_snake_case}/"):
                        rel_path = rel_path[len(f"{pkg_snake_case}/"):]
                    elif rel_path == "pyproject.toml" or rel_path == "README.md":
                        # Ignoriamo i file root del pacchetto pip, ci serve solo il codice sorgente
                        continue
                    
                    if not rel_path:
                        continue
                        
                    dest_path = target_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(f) as zf, open(dest_path, "wb") as out:
                        shutil.copyfileobj(zf, out)
            
            Path(tmp_path).unlink(missing_ok=True)
            
            import importlib
            importlib.invalidate_caches()

            asyncio.create_task(_do_restart())
            return JSONResponse({
                "ok": True,
                "stdout": f"Plugin {package} downloaded and extracted locally.",
                "restarting": True
            })
            
        except Exception as e:
            logger.exception("Plugin installation failed")
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    from pathlib import Path
    workspace_root = Path(__file__).resolve().parent.parent.parent.parent
    local_path = workspace_root / "plugins" / package
    
    import subprocess
    extra_kwargs = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    if package == "shibaclaw-rag":
        is_source = (workspace_root / "pyproject.toml").exists()
        if is_source:
            cmd = [sys.executable, "-m", "pip", "install", "-e", ".[rag]"]
            extra_kwargs["cwd"] = str(workspace_root)
        else:
            from shibaclaw import __version__
            target = f"shibaclaw[rag]=={__version__}" if __version__ != "dev" else "shibaclaw[rag]"
            cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", target]
    elif local_path.is_dir():
        install_target = str(local_path)
        cmd = [sys.executable, "-m", "pip", "install", install_target]
    else:
        from shibaclaw import __version__
        tag = f"v{__version__}" if __version__ != "dev" else "main"
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
            return JSONResponse({
                "ok": False,
                "error": stderr.decode().strip(),
                "stdout": stdout.decode()
            }, status_code=500)
            
        import importlib
        importlib.invalidate_caches()

        asyncio.create_task(_do_restart())
        return JSONResponse({
            "ok": True,
            "stdout": stdout.decode().strip(),
            "restarting": True
        })
    except Exception as e:
        logger.exception("Plugin installation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

async def api_uninstall_plugin(request: Request) -> JSONResponse:

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    
    package = body.get("package")
    if not package:
        return JSONResponse({"error": "package is required"}, status_code=400)

    import re
    if not re.match(r"^shibaclaw-[a-zA-Z0-9_\-]+$", package):
        return JSONResponse({"error": "Only shibaclaw official plugins can be uninstalled"}, status_code=400)

    from shibaclaw.helpers.system import is_running_as_exe
    is_exe = is_running_as_exe()
    
    from shibaclaw.webui.routers.system import (
        _restart_callback,
        _schedule_restart_outside_loop,
        _graceful_shutdown_server,
        _shutdown_callback
    )

    async def _do_restart():
        await asyncio.sleep(1.5)
        if _shutdown_callback is not None:
            try:
                _shutdown_callback()
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
        if _restart_callback is not None:
            _restart_callback()
        else:
            _schedule_restart_outside_loop(delay=2.0)
            _graceful_shutdown_server()

    if is_exe:
        if package == "shibaclaw-rag":
            return JSONResponse({"ok": False, "error": "RAG is not supported in the .exe version."}, status_code=400)
            
        import shutil
        from shibaclaw.config.paths import get_plugins_dir
        
        short_name = package.replace("shibaclaw-channel-", "").replace("shibaclaw-tts-", "").replace("shibaclaw_", "")
        target_dir = get_plugins_dir() / short_name
        
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        import importlib
        importlib.invalidate_caches()

        asyncio.create_task(_do_restart())
        return JSONResponse({
            "ok": True,
            "stdout": f"Plugin {package} folder deleted locally.",
            "restarting": True
        })

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
    
    import subprocess
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
            
        import importlib
        importlib.invalidate_caches()

        asyncio.create_task(_do_restart())
        return JSONResponse({
            "ok": True,
            "stdout": stdout.decode().strip(),
            "restarting": True
        })
    except Exception as e:
        logger.exception("Plugin uninstallation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
