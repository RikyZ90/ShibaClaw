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
    from shibaclaw.helpers.system import is_running_as_exe
    if is_running_as_exe():
        return JSONResponse({
            "ok": False,
            "error": "Plugin installation is not supported in the packaged .exe version. Please run ShibaClaw from a Python environment (pip/source) to install plugins."
        }, status_code=400)

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
            cmd = [sys.executable, "-m", "pip", "install", "shibaclaw[rag]"]
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
            
        from shibaclaw.webui.routers.system import (
            _restart_callback,
            _schedule_restart_outside_loop,
            _graceful_shutdown_server
        )
        
        async def _do_restart():
            await asyncio.sleep(1.5)
            if _restart_callback is not None:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _restart_callback)
            else:
                _schedule_restart_outside_loop(delay=2.0)
                _graceful_shutdown_server()
                
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
    from shibaclaw.helpers.system import is_running_as_exe
    if is_running_as_exe():
        return JSONResponse({
            "ok": False,
            "error": "Plugin uninstallation is not supported in the packaged .exe version. Please run ShibaClaw from a Python environment (pip/source) to uninstall plugins."
        }, status_code=400)

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
            
        from shibaclaw.webui.routers.system import (
            _restart_callback,
            _schedule_restart_outside_loop,
            _graceful_shutdown_server
        )
        
        async def _do_restart():
            await asyncio.sleep(1.5)
            if _restart_callback is not None:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _restart_callback)
            else:
                _schedule_restart_outside_loop(delay=2.0)
                _graceful_shutdown_server()
                
        asyncio.create_task(_do_restart())
        
        return JSONResponse({
            "ok": True,
            "stdout": stdout.decode().strip(),
            "restarting": True
        })
    except Exception as e:
        logger.exception("Plugin uninstallation failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
