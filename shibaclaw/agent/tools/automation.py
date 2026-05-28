"""Automation tool for scheduling reminders and tasks."""

from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from shibaclaw.agent.tools.base import Tool
from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationJobState, AutomationSchedule, AutomationPayload


class AutomationTool(Tool):
    """Tool to schedule reminders and recurring tasks."""

    def __init__(self, automation_service: AutomationService):
        self._automation = automation_service
        self._channel = ""
        self._chat_id = ""
        self._session_key = "cli:direct"
        self._in_automation_context: ContextVar[bool] = ContextVar("automation_in_context", default=False)

    def set_context(self, channel: str, chat_id: str, session_key: str | None = None) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
        self._session_key = session_key or f"{channel}:{chat_id}"

    def set_automation_context(self, active: bool):
        """Mark whether the tool is executing inside an automation job callback."""
        return self._in_automation_context.set(active)

    def reset_automation_context(self, token) -> None:
        """Restore previous automation context."""
        self._in_automation_context.reset(token)

    @property
    def name(self) -> str:
        return "automation"

    @property
    def description(self) -> str:
        return "Schedule reminders and recurring tasks. Actions: add, list, remove."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform",
                },
                "message": {"type": "string", "description": "Reminder message (for add)"},
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)",
                },
                "tz": {
                    "type": "string",
                    "description": "IANA timezone for cron expressions (e.g. 'America/Vancouver')",
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')",
                },
                "delete_after_run": {
                    "type": "boolean",
                    "description": "Whether the job should be deleted after its first successful or failed execution",
                },
                "job_id": {"type": "string", "description": "Job ID (for remove)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at: str | None = None,
        delete_after_run: bool | None = None,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "add":
            if self._in_automation_context.get():
                return "Error: cannot schedule new jobs from within an automation job execution"
            return self._add_job(message, every_seconds, cron_expr, tz, at, delete_after_run)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"

    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        cron_expr: str | None,
        tz: str | None,
        at: str | None,
        delete_after_run: bool | None = None,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if tz and not cron_expr:
            return "Error: tz can only be used with cron_expr"
        if tz:
            from zoneinfo import ZoneInfo

            try:
                ZoneInfo(tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{tz}'"

        # Build schedule
        if every_seconds:
            schedule = AutomationSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = AutomationSchedule(kind="cron", expr=cron_expr, tz=tz)
        elif at:
            from datetime import datetime

            try:
                dt = datetime.fromisoformat(at)
            except ValueError:
                return f"Error: invalid ISO datetime format '{at}'. Expected format: YYYY-MM-DDTHH:MM:SS"
            at_ms = int(dt.timestamp() * 1000)
            schedule = AutomationSchedule(kind="at", at_ms=at_ms)
        else:
            return "Error: either every_seconds, cron_expr, or at is required"

        # Determine if it should be deleted after run
        if delete_after_run is not None:
            delete_after = delete_after_run
        else:
            # Default: one-shot jobs are deleted, recurring ones are kept
            delete_after = (schedule.kind == "at")

        payload = AutomationPayload(
            kind="scheduled",
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            session_key=self._session_key,
        )

        job = self._automation.add_job(
            name=message[:30],
            schedule=schedule,
            payload=payload,
            delete_after_run=delete_after,
        )
        return f"Created job '{job.name}' (id: {job.id})"

    @staticmethod
    def _format_timing(schedule: AutomationSchedule) -> str:
        """Format schedule as a human-readable timing string."""
        if schedule.kind == "cron":
            tz = f" ({schedule.tz})" if schedule.tz else ""
            return f"automation: {schedule.expr}{tz}"
        if schedule.kind == "every" and schedule.every_ms:
            ms = schedule.every_ms
            if ms % 3_600_000 == 0:
                return f"every {ms // 3_600_000}h"
            if ms % 60_000 == 0:
                return f"every {ms // 60_000}m"
            if ms % 1000 == 0:
                return f"every {ms // 1000}s"
            return f"every {ms}ms"
        if schedule.kind == "at" and schedule.at_ms:
            dt = datetime.fromtimestamp(schedule.at_ms / 1000, tz=timezone.utc)
            return f"at {dt.isoformat()}"
        return schedule.kind

    @staticmethod
    def _format_state(state: AutomationJobState) -> list[str]:
        """Format job run state as display lines."""
        lines: list[str] = []
        if state.last_run_at_ms:
            last_dt = datetime.fromtimestamp(state.last_run_at_ms / 1000, tz=timezone.utc)
            info = f"  Last run: {last_dt.isoformat()} — {state.last_status or 'unknown'}"
            if state.last_error:
                info += f" ({state.last_error})"
            lines.append(info)
        if state.next_run_at_ms:
            next_dt = datetime.fromtimestamp(state.next_run_at_ms / 1000, tz=timezone.utc)
            lines.append(f"  Next run: {next_dt.isoformat()}")
        return lines

    def _list_jobs(self) -> str:
        jobs = self._automation.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = []
        for j in jobs:
            timing = self._format_timing(j.schedule)
            parts = [f"- {j.name} (id: {j.id}, {timing})"]
            parts.extend(self._format_state(j.state))
            lines.append("\n".join(parts))
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._automation.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
