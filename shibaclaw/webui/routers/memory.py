from __future__ import annotations

import aiofiles
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.agent.memory import ScentKeeper
from shibaclaw.webui.agent_manager import agent_manager
import shibaclaw.webui.auth as webui_auth


def _check_auth(request: Request) -> bool:
    if not webui_auth._auth_enabled():
        return True
    token = request.query_params.get("token") or ""
    if not token:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.startswith("Bearer "):
            token = auth_hdr[7:].strip()
    return bool(token and webui_auth._verify_session_token(token))


def _get_keeper() -> ScentKeeper:
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        raise RuntimeError("No configuration loaded")
    return ScentKeeper(agent_manager.config.workspace_path)


async def api_memory_get(request: Request) -> JSONResponse:
    """Return all memory files, token estimation, and quarantine stats."""
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        sk = _get_keeper()
        long_term = sk.read_long_term()
        user_profile = sk.read_user_profile()

        history = ""
        if sk.history_file.exists():
            history = sk.history_file.read_text(encoding="utf-8")

        diary_file = sk.memory_dir / "DREAM_DIARY.md"
        diary = ""
        if diary_file.exists():
            diary = diary_file.read_text(encoding="utf-8")

        qdir = sk.memory_dir / "quarantine"
        quarantined = []
        if qdir.exists():
            for f in sorted(qdir.glob("*.md"), reverse=True)[:20]:
                quarantined.append({
                    "name": f.name,
                    "mtime": f.stat().st_mtime,
                    "size": f.stat().st_size,
                    "preview": f.read_text(encoding="utf-8")[:500]
                })

        tokens = sk.estimate_memory_tokens()

        return JSONResponse({
            "memory": long_term,
            "user": user_profile,
            "history": history,
            "diary": diary,
            "tokens": tokens,
            "max_tokens": 1500,
            "quarantined": quarantined,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_memory_save(request: Request) -> JSONResponse:
    """Save changes to MEMORY.md or USER.md."""
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        data = await request.json()
        target = data.get("file")
        content = data.get("content", "")

        sk = _get_keeper()
        if target == "MEMORY.md":
            await sk.write_long_term(content)
        elif target == "USER.md":
            await sk.write_user_profile(content)
        elif target == "DREAM_DIARY.md":
            diary_file = sk.memory_dir / "DREAM_DIARY.md"
            async with aiofiles.open(diary_file, "w", encoding="utf-8") as f:
                await f.write(content)
        elif target == "HISTORY.md":
            async with aiofiles.open(sk.history_file, "w", encoding="utf-8") as f:
                await f.write(content)
        else:
            return JSONResponse({"error": f"Invalid target file: {target}"}, status_code=400)

        tokens = sk.estimate_memory_tokens()
        return JSONResponse({"status": "saved", "file": target, "tokens": tokens})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_memory_forget(request: Request) -> JSONResponse:
    """Preview or execute memory forget lines (quarantine and redact)."""
    if not _check_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        data = await request.json()
        needle = data.get("needle", "").strip()
        confirm = bool(data.get("confirm", False))

        if not needle:
            return JSONResponse({"error": "Needle string is required"}, status_code=400)

        sk = _get_keeper()
        res = await sk.forget_memory_lines(needle, confirm=confirm)
        if res.get("error"):
            return JSONResponse({"error": res["error"]}, status_code=400)

        tokens = sk.estimate_memory_tokens()
        return JSONResponse({**res, "tokens": tokens})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
