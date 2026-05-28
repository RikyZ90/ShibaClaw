"""Backward-compat shim: /api/cron/* → /api/automation/*.

Kept so that any external tool or older NanoBot-UI version that still calls
the legacy cron endpoints doesn't break immediately.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.utils import _gateway_post, _gateway_request


async def api_cron_list(request: Request) -> JSONResponse:
    """[DEPRECATED] Use GET /api/automation/jobs instead."""
    result = await _gateway_request("GET", "/api/automation/jobs")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"jobs": [], "error": "gateway_unreachable"}, status_code=503)


async def api_cron_trigger(request: Request) -> JSONResponse:
    """[DEPRECATED] Use POST /api/automation/jobs/{id}/trigger instead."""
    job_id = request.path_params["job_id"]
    result = await _gateway_post(f"/api/automation/jobs/{job_id}/trigger", {})
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)
