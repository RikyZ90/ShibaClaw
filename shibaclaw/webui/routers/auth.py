from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.auth import _auth_enabled, verify_token_value


async def api_auth_verify(request: Request):
    """Verify an auth token."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()
    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})
    if verify_token_value(token):
        return JSONResponse({"valid": True, "auth_required": True})
    return JSONResponse({"valid": False, "auth_required": True})


async def api_auth_status(request: Request):
    """Check if auth is enabled."""
    return JSONResponse({"auth_required": _auth_enabled()})
