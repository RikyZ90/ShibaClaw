"""Backward-compat shim: /api/heartbeat/* → /api/automation/*.

Kept so that any external tool or older NanoBot-UI version that still calls
the legacy heartbeat endpoints doesn't break immediately.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.utils import _gateway_post, _gateway_request


async def api_heartbeat_status(request: Request) -> JSONResponse:
    """[DEPRECATED] Use GET /api/automation/status instead."""
    result = await _gateway_request("GET", "/api/automation/status")
    if result is not None:
        return JSONResponse({"reachable": True, **result})
    return JSONResponse({"reachable": False, "reason": "gateway_unreachable"})


async def api_heartbeat_trigger(request: Request) -> JSONResponse:
    """[DEPRECATED] Use POST /api/automation/jobs/{id}/trigger instead.

    Without a job_id we trigger all enabled heartbeat jobs.
    """
    result = await _gateway_post("/api/automation/trigger-heartbeats", {})
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)
