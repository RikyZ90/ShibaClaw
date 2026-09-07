"""Automation operation fingerprint + approve-once helpers."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule


def operation_fingerprint(
    schedule: AutomationSchedule,
    payload: AutomationPayload,
) -> str:
    """Stable hash of the exact operation a job will run."""
    blob = {
        "schedule": {
            "kind": schedule.kind,
            "at_ms": schedule.at_ms,
            "every_ms": schedule.every_ms,
            "expr": schedule.expr,
            "tz": schedule.tz,
        },
        "payload": {
            "kind": payload.kind,
            "message": payload.message,
            "heartbeat_file": payload.heartbeat_file,
            "deliver": payload.deliver,
            "channel": payload.channel,
            "to": payload.to,
            "session_key": payload.session_key,
            "profile_id": payload.profile_id,
            "targets": payload.targets,
        },
    }
    raw = json.dumps(blob, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def job_is_approved(job: AutomationJob) -> bool:
    if not getattr(job, "require_approval", False):
        return True
    fp = operation_fingerprint(job.schedule, job.payload)
    return bool(job.approved_fingerprint) and job.approved_fingerprint == fp
