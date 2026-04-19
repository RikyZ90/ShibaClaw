from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.utils import _gateway_request


async def api_heartbeat_status(request: Request):
    """Proxy heartbeat status from the gateway."""
    result = await _gateway_request("GET", "/heartbeat/status")
    if result is not None:
        return JSONResponse({"reachable": True, **result})
    return JSONResponse({"reachable": False, "reason": "gateway_unreachable"})


async def api_heartbeat_trigger(request: Request):
    """Proxy heartbeat trigger to the gateway."""
    result = await _gateway_request("POST", "/heartbeat/trigger")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "Gateway unreachable"}, status_code=503)
