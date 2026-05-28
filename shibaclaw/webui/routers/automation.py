"""Unified Automation REST router.

Endpoints
---------
GET    /api/automation/status
GET    /api/automation/jobs
POST   /api/automation/jobs
GET    /api/automation/jobs/{job_id}
PATCH  /api/automation/jobs/{job_id}
DELETE /api/automation/jobs/{job_id}
POST   /api/automation/jobs/{job_id}/trigger

All requests are proxied to the gateway via the WS client (with HTTP fallback).
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.utils import _gateway_post, _gateway_request


# ── Status ────────────────────────────────────────────────────────────

async def api_automation_status(request: Request) -> JSONResponse:
    """Return automation service status from the gateway."""
    result = await _gateway_request("GET", "/api/automation/status")
    if result is not None:
        return JSONResponse({"reachable": True, **result})
    return JSONResponse({"reachable": False, "reason": "gateway_unreachable"})


# ── Job collection ────────────────────────────────────────────────────

async def api_automation_jobs_list(request: Request) -> JSONResponse:
    """List all automation jobs."""
    result = await _gateway_request("GET", "/api/automation/jobs")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"jobs": [], "error": "gateway_unreachable"}, status_code=503)


async def api_automation_jobs_create(request: Request) -> JSONResponse:
    """Create a new automation job."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    result = await _gateway_post("/api/automation/jobs", body)
    if result is not None:
        return JSONResponse(result, status_code=201)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)


# ── Single job ────────────────────────────────────────────────────────

async def api_automation_job_get(request: Request) -> JSONResponse:
    """Get a single automation job by id."""
    job_id = request.path_params["job_id"]
    result = await _gateway_request("GET", f"/api/automation/jobs/{job_id}")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)


async def api_automation_job_update(request: Request) -> JSONResponse:
    """Partially update an automation job (name, enabled, schedule, payload, delete_after_run)."""
    job_id = request.path_params["job_id"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    result = await _gateway_post(f"/api/automation/jobs/{job_id}/update", body)
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)


async def api_automation_job_delete(request: Request) -> JSONResponse:
    """Delete an automation job."""
    job_id = request.path_params["job_id"]
    result = await _gateway_request("DELETE", f"/api/automation/jobs/{job_id}")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)


async def api_automation_job_trigger(request: Request) -> JSONResponse:
    """Manually trigger an automation job."""
    job_id = request.path_params["job_id"]
    result = await _gateway_post(f"/api/automation/jobs/{job_id}/trigger", {})
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "gateway_unreachable"}, status_code=503)
