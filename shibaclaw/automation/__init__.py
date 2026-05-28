"""Automation module — unified scheduler replacing CronService + HeartbeatService."""

from .service import AutomationService
from .types import AutomationJob, AutomationJobState, AutomationPayload, AutomationSchedule

__all__ = [
    "AutomationService",
    "AutomationJob",
    "AutomationJobState",
    "AutomationPayload",
    "AutomationSchedule",
]
