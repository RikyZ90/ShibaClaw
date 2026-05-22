"""Automation module – unified scheduled + heartbeat jobs."""

from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import (
    AutomationJob,
    AutomationJobState,
    AutomationPayload,
    AutomationRunRecord,
    AutomationSchedule,
    AutomationStore,
)

__all__ = [
    "AutomationService",
    "AutomationJob",
    "AutomationJobState",
    "AutomationPayload",
    "AutomationRunRecord",
    "AutomationSchedule",
    "AutomationStore",
]
