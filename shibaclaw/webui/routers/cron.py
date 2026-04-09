from __future__ import annotations
import os
import uuid
import json
import asyncio
from typing import Any, Dict, List, Set, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.auth import get_auth_token, _auth_enabled


async def api_cron_list(request: Request):
    """List all scheduled jobs from the local CronService."""
    await agent_manager.ensure_agent()
    cron = getattr(agent_manager.agent, "cron_service", None) if agent_manager.agent else None
    if not cron:
        return JSONResponse({"jobs": []})

    jobs = cron.list_jobs(include_disabled=True)
    return JSONResponse({"jobs": [
        {
            "id": j.id,
            "name": j.name,
            "enabled": j.enabled,
            "schedule": {"kind": j.schedule.kind, "atMs": j.schedule.at_ms, "everyMs": j.schedule.every_ms, "expr": j.schedule.expr, "tz": j.schedule.tz},
            "payload": {"message": j.payload.message, "deliver": j.payload.deliver, "channel": j.payload.channel, "to": j.payload.to},
            "state": {
                "nextRunAtMs": j.state.next_run_at_ms,
                "lastRunAtMs": j.state.last_run_at_ms,
                "lastStatus": j.state.last_status,
                "lastError": j.state.last_error,
            },
            "deleteAfterRun": j.delete_after_run,
        }
        for j in jobs
    ]})


async def api_cron_trigger(request: Request):
    """Manually trigger a cron job by ID."""
    await agent_manager.ensure_agent()
    cron = getattr(agent_manager.agent, "cron_service", None) if agent_manager.agent else None
    if not cron:
        return JSONResponse({"error": "Cron not available"}, status_code=400)

    job_id = request.path_params["job_id"]
    ran = await cron.run_job(job_id, force=True)
    return JSONResponse({"triggered": ran})
