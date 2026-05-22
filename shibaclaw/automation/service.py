"""AutomationService – unified cron + heartbeat scheduling.

Replaces the separate CronService and HeartbeatService with a single
event-driven scheduler.  Every job is an AutomationJob with either
kind='scheduled' (former cron) or kind='heartbeat' (former heartbeat).

The timer loop is purely event-driven (asyncio.sleep until the next
scheduled job) so it is efficient even with hundreds of jobs.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import yaml
from loguru import logger

from shibaclaw.automation.types import (
    AutomationJob,
    AutomationJobState,
    AutomationPayload,
    AutomationRunRecord,
    AutomationSchedule,
    AutomationStore,
)

if TYPE_CHECKING:
    from shibaclaw.thinkers.base import Thinker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: AutomationSchedule, now_ms: int) -> int | None:
    """Return the next trigger time in epoch-ms, or None if never."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr:
        try:
            from zoneinfo import ZoneInfo
            from croniter import croniter

            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(now_ms / 1000, tz=tz)
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None

    return None


def _validate_schedule(schedule: AutomationSchedule) -> None:
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")
    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


# ---------------------------------------------------------------------------
# Heartbeat decision tool definition (same contract as old HeartbeatService)
# ---------------------------------------------------------------------------

_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _job_to_dict(j: AutomationJob) -> dict:
    return {
        "id": j.id,
        "name": j.name,
        "enabled": j.enabled,
        "schedule": {
            "kind": j.schedule.kind,
            "atMs": j.schedule.at_ms,
            "everyMs": j.schedule.every_ms,
            "expr": j.schedule.expr,
            "tz": j.schedule.tz,
        },
        "payload": {
            "kind": j.payload.kind,
            "message": j.payload.message,
            "heartbeatFile": j.payload.heartbeat_file,
            "deliver": j.payload.deliver,
            "channel": j.payload.channel,
            "to": j.payload.to,
            "sessionKey": j.payload.session_key,
            "profileId": j.payload.profile_id,
            "targets": j.payload.targets,
        },
        "state": {
            "nextRunAtMs": j.state.next_run_at_ms,
            "lastRunAtMs": j.state.last_run_at_ms,
            "lastStatus": j.state.last_status,
            "lastError": j.state.last_error,
            "runHistory": [
                {
                    "runAtMs": r.run_at_ms,
                    "status": r.status,
                    "durationMs": r.duration_ms,
                    "error": r.error,
                }
                for r in j.state.run_history
            ],
        },
        "createdAtMs": j.created_at_ms,
        "updatedAtMs": j.updated_at_ms,
        "deleteAfterRun": j.delete_after_run,
    }


def _job_from_dict(d: dict) -> AutomationJob:
    payload_kind = d["payload"].get("kind", "scheduled")
    # Backward-compat: old cron jobs used kind="agent_turn"
    if payload_kind == "agent_turn":
        payload_kind = "scheduled"

    return AutomationJob(
        id=d["id"],
        name=d["name"],
        enabled=d.get("enabled", True),
        schedule=AutomationSchedule(
            kind=d["schedule"]["kind"],
            at_ms=d["schedule"].get("atMs"),
            every_ms=d["schedule"].get("everyMs"),
            expr=d["schedule"].get("expr"),
            tz=d["schedule"].get("tz"),
        ),
        payload=AutomationPayload(
            kind=payload_kind,
            message=d["payload"].get("message", ""),
            heartbeat_file=d["payload"].get("heartbeatFile"),
            deliver=d["payload"].get("deliver", False),
            channel=d["payload"].get("channel"),
            to=d["payload"].get("to"),
            session_key=d["payload"].get("sessionKey"),
            profile_id=d["payload"].get("profileId"),
            targets=d["payload"].get("targets") or {},
        ),
        state=AutomationJobState(
            next_run_at_ms=d.get("state", {}).get("nextRunAtMs"),
            last_run_at_ms=d.get("state", {}).get("lastRunAtMs"),
            last_status=d.get("state", {}).get("lastStatus"),
            last_error=d.get("state", {}).get("lastError"),
            run_history=[
                AutomationRunRecord(
                    run_at_ms=r["runAtMs"],
                    status=r["status"],
                    duration_ms=r.get("durationMs", 0),
                    error=r.get("error"),
                )
                for r in d.get("state", {}).get("runHistory", [])
            ],
        ),
        created_at_ms=d.get("createdAtMs", 0),
        updated_at_ms=d.get("updatedAtMs", 0),
        delete_after_run=d.get("deleteAfterRun", False),
    )


# ---------------------------------------------------------------------------
# Migration helper: cron jobs.json -> automation.json
# ---------------------------------------------------------------------------

def migrate_from_cron_store(cron_store_path: Path) -> list[dict]:
    """Read an old cron jobs.json and return a list of job dicts ready for
    automation.json.  payload.kind is set to 'scheduled'."""
    if not cron_store_path.exists():
        return []
    try:
        data = json.loads(cron_store_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    migrated = []
    for j in data.get("jobs", []):
        j.setdefault("payload", {})["kind"] = "scheduled"
        # rename agent_turn -> scheduled silently
        if j["payload"].get("kind") == "agent_turn":
            j["payload"]["kind"] = "scheduled"
        migrated.append(j)
    return migrated


# ---------------------------------------------------------------------------
# AutomationService
# ---------------------------------------------------------------------------

class AutomationService:
    """Single service that manages both scheduled and heartbeat automation jobs.

    Parameters
    ----------
    store_path:
        Path to ``automation.json`` where jobs are persisted.
    workspace:
        Root workspace directory; heartbeat .md files are resolved here.
    on_scheduled:
        Async callback called with the ``AutomationJob`` for kind='scheduled'.
        Receives ``job`` and should run the agent turn.
    on_heartbeat:
        Async callback for kind='heartbeat' *execution phase* (only invoked
        when the LLM returns action='run').  Receives ``(tasks, **delivery_kwargs)``
        and should return the response string.
    on_notify:
        Async callback called after a successful heartbeat execution when
        ``payload.deliver`` is True.  Receives ``(response, targets=…)``.
    provider:
        Thinker instance used for the heartbeat *decision* phase.
    model:
        Model name for heartbeat decisions.
    """

    _MAX_RUN_HISTORY = 20

    def __init__(
        self,
        store_path: Path,
        workspace: Path | None = None,
        on_scheduled: Callable[[AutomationJob], Coroutine[Any, Any, str | None]] | None = None,
        on_heartbeat: Callable[..., Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[..., Coroutine[Any, Any, None]] | None = None,
        provider: "Thinker | None" = None,
        model: str = "",
    ):
        self.store_path = store_path
        self.workspace = workspace or store_path.parent
        self.on_scheduled = on_scheduled
        self.on_heartbeat = on_heartbeat
        self.on_notify = on_notify
        self.provider = provider
        self.model = model

        self._store: AutomationStore | None = None
        self._last_mtime: float = 0.0
        self._timer_task: asyncio.Task | None = None
        self._running = False
        self._save_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Store I/O
    # ------------------------------------------------------------------

    def _load_store(self) -> AutomationStore:
        """Load jobs from disk.  Auto-reloads if the file was modified externally."""
        if self._store and self.store_path.exists():
            mtime = self.store_path.stat().st_mtime
            if mtime != self._last_mtime:
                logger.debug("Automation: automation.json changed externally, reloading")
                self._store = None

        if self._store:
            return self._store

        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                self._store = AutomationStore(
                    version=data.get("version", 1),
                    jobs=[_job_from_dict(j) for j in data.get("jobs", [])],
                )
                self._last_mtime = self.store_path.stat().st_mtime
            except Exception as exc:
                logger.warning("Automation: failed to load store: {}", exc)
                self._store = AutomationStore()
        else:
            self._store = AutomationStore()

        return self._store

    def _save_store(self) -> None:
        if not self._store:
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self._store.version,
            "jobs": [_job_to_dict(j) for j in self._store.jobs],
        }
        self.store_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._last_mtime = self.store_path.stat().st_mtime

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the automation service."""
        self._running = True
        self._load_store()
        await self._fire_overdue_at_jobs()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        total = len(self._store.jobs) if self._store else 0
        logger.info("AutomationService started with {} jobs", total)

    def stop(self) -> None:
        """Stop the automation service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    # ------------------------------------------------------------------
    # Timer loop (event-driven)
    # ------------------------------------------------------------------

    def _recompute_next_runs(self) -> None:
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

    def _get_next_wake_ms(self) -> int | None:
        if not self._store:
            return None
        times = [
            j.state.next_run_at_ms
            for j in self._store.jobs
            if j.enabled and j.state.next_run_at_ms
        ]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        if self._timer_task:
            self._timer_task.cancel()

        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return

        delay_s = max(0, (next_wake - _now_ms()) / 1000)

        async def _tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(_tick())

    async def _on_timer(self) -> None:
        self._load_store()
        if not self._store:
            return

        now = _now_ms()
        due_jobs = [
            j
            for j in self._store.jobs
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]

        if not due_jobs:
            self._arm_timer()
            return

        # Advance next_run_at_ms before dispatching so the timer can re-arm
        for job in due_jobs:
            if job.schedule.kind == "at":
                job.state.next_run_at_ms = None
            else:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

        self._save_store()
        self._arm_timer()

        for job in due_jobs:
            asyncio.create_task(self._run_job_bg(job))

    async def _run_job_bg(self, job: AutomationJob) -> None:
        await self._execute_job(job)
        async with self._save_lock:
            self._save_store()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_job(self, job: AutomationJob) -> None:
        start_ms = _now_ms()
        logger.info(
            "Automation[{}]: executing job '{}' ({})",
            job.payload.kind, job.name, job.id,
        )

        if job.payload.kind == "scheduled":
            await self._execute_scheduled(job)
        else:
            await self._execute_heartbeat(job)

        end_ms = _now_ms()
        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = end_ms
        job.state.run_history.append(
            AutomationRunRecord(
                run_at_ms=start_ms,
                status=job.state.last_status or "ok",
                duration_ms=end_ms - start_ms,
                error=job.state.last_error,
            )
        )
        job.state.run_history = job.state.run_history[-self._MAX_RUN_HISTORY:]

        # Handle one-shot jobs
        if job.schedule.kind == "at":
            if job.delete_after_run and self._store:
                self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

    async def _execute_scheduled(self, job: AutomationJob) -> None:
        """Run a scheduled (former cron) job."""
        if not (job.payload.message or "").strip():
            job.state.last_status = "skipped"
            job.state.last_error = None
            logger.info("Automation: job '{}' skipped – no message payload", job.name)
            return
        try:
            if self.on_scheduled:
                await self.on_scheduled(job)
            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info("Automation: job '{}' completed", job.name)
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)
            logger.error("Automation: job '{}' failed: {}", job.name, exc)

    async def _execute_heartbeat(self, job: AutomationJob) -> None:
        """Run a heartbeat (former heartbeat) job."""
        if not self.provider:
            job.state.last_status = "skipped"
            job.state.last_error = "no AI provider configured"
            logger.warning("Automation: heartbeat job '{}' skipped – no provider", job.name)
            return

        hb_file = self.workspace / (job.payload.heartbeat_file or "HEARTBEAT.md")
        active_tasks = self._read_active_tasks(hb_file)

        if not active_tasks:
            job.state.last_status = "skipped"
            job.state.last_error = None
            logger.info("Automation: heartbeat '{}' – no active tasks in '{}'", job.name, hb_file.name)
            return

        try:
            action, tasks = await self._heartbeat_decide(active_tasks)

            if action != "run":
                job.state.last_status = "skipped"
                job.state.last_error = None
                logger.info("Automation: heartbeat '{}' – LLM returned skip", job.name)
                return

            logger.info("Automation: heartbeat '{}' – executing tasks", job.name)
            if self.on_heartbeat:
                response = await self.on_heartbeat(
                    tasks,
                    session_key=job.payload.session_key,
                    profile_id=job.payload.profile_id,
                    targets=job.payload.targets,
                )
                if response and job.payload.deliver and self.on_notify:
                    from shibaclaw.helpers.evaluator import evaluate_response
                    should_notify = await evaluate_response(
                        response, tasks, self.provider, self.model
                    )
                    if should_notify:
                        logger.info("Automation: heartbeat '{}' – delivering response", job.name)
                        await self.on_notify(response, targets=job.payload.targets)
                    else:
                        logger.info("Automation: heartbeat '{}' – silenced by evaluator", job.name)

            job.state.last_status = "ok"
            job.state.last_error = None
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)
            logger.exception("Automation: heartbeat '{}' failed", job.name)

    # ------------------------------------------------------------------
    # Heartbeat helpers
    # ------------------------------------------------------------------

    def _read_active_tasks(self, hb_file: Path) -> str:
        """Read and extract the active-tasks block from a heartbeat .md file."""
        if not hb_file.exists():
            return ""
        try:
            raw = hb_file.read_text(encoding="utf-8")
        except Exception:
            return ""

        # Strip YAML frontmatter if present
        body = raw
        if raw.startswith("---"):
            lines = raw.splitlines()
            end_idx = next(
                (i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None
            )
            if end_idx is not None:
                body = "\n".join(lines[end_idx + 1:]).lstrip("\n")

        cleaned = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        active_match = re.search(r"(?im)^##\s+Active Tasks\s*$", cleaned)
        if active_match:
            relevant = cleaned[active_match.end():]
            next_section = re.search(r"(?im)^##\s+", relevant)
            if next_section:
                relevant = relevant[: next_section.start()]
        else:
            relevant = cleaned

        lines_out: list[str] = []
        for ln in relevant.splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or s == "---":
                continue
            lines_out.append(ln.rstrip())

        return "\n".join(lines_out).strip()

    async def _heartbeat_decide(self, content: str) -> tuple[str, str]:
        """Ask the LLM to decide skip/run."""
        from shibaclaw.helpers.helpers import current_time_str

        if not self.provider:
            return "skip", ""

        response = await self.provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": "You are a heartbeat agent. Call the heartbeat tool to report your decision.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Current Time: {current_time_str()}\n\n"
                        "Review the following tasks and decide whether there are active tasks.\n\n"
                        f"{content}"
                    ),
                },
            ],
            tools=_HEARTBEAT_TOOL,
            model=self.model,
            log_transient_errors=False,
        )

        if not response.has_tool_calls:
            logger.warning("Automation: heartbeat decision returned no tool call, skipping")
            return "skip", ""

        args = response.tool_calls[0].arguments
        return args.get("action", "skip"), args.get("tasks", "")

    # ------------------------------------------------------------------
    # Overdue one-shot jobs
    # ------------------------------------------------------------------

    async def _fire_overdue_at_jobs(self) -> None:
        """On startup, immediately execute any 'at' jobs that are past due."""
        if not self._store:
            return
        now = _now_ms()
        overdue = [
            j
            for j in self._store.jobs
            if j.enabled
            and j.schedule.kind == "at"
            and j.schedule.at_ms
            and j.schedule.at_ms <= now
            and not j.state.last_run_at_ms
        ]
        for job in overdue:
            logger.info("Automation: firing overdue job '{}'", job.name)
            await self._execute_job(job)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_job(
        self,
        name: str,
        schedule: AutomationSchedule,
        payload: AutomationPayload,
        delete_after_run: bool = False,
    ) -> AutomationJob:
        """Add a new automation job.

        Both scheduled and heartbeat jobs are added with the same call::

            # Scheduled job
            svc.add_job(
                name="Morning briefing",
                schedule=AutomationSchedule(kind="cron", expr="0 9 * * *", tz="Europe/Rome"),
                payload=AutomationPayload(kind="scheduled", message="Give me a daily summary"),
            )

            # Heartbeat job
            svc.add_job(
                name="Task watcher",
                schedule=AutomationSchedule(kind="every", every_ms=30 * 60 * 1000),
                payload=AutomationPayload(kind="heartbeat", heartbeat_file="HEARTBEAT.md"),
            )
        """
        store = self._load_store()
        _validate_schedule(schedule)
        now = _now_ms()

        job = AutomationJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=payload,
            state=AutomationJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )

        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        logger.info("Automation: added job '{}' ({}) kind={}", name, job.id, payload.kind)
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before
        if removed:
            self._save_store()
            self._arm_timer()
            logger.info("Automation: removed job {}", job_id)
        return removed

    def enable_job(self, job_id: str, enabled: bool = True) -> AutomationJob | None:
        """Enable or disable a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                self._save_store()
                self._arm_timer()
                return job
        return None

    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually trigger a job by ID."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if not force and not job.enabled:
                    return False
                await self._execute_job(job)
                self._save_store()
                self._arm_timer()
                return True
        return False

    def get_job(self, job_id: str) -> AutomationJob | None:
        """Get a job by ID."""
        store = self._load_store()
        return next((j for j in store.jobs if j.id == job_id), None)

    def list_jobs(
        self,
        include_disabled: bool = False,
        kind: str | None = None,
    ) -> list[AutomationJob]:
        """List all jobs, optionally filtered by kind ('scheduled' or 'heartbeat')."""
        store = self._load_store()
        jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
        if kind:
            jobs = [j for j in jobs if j.payload.kind == kind]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float("inf"))

    def status(self) -> dict:
        """Return serializable status for the sidebar / API."""
        store = self._load_store()
        all_jobs = store.jobs
        return {
            "running": self._running,
            "total_jobs": len(all_jobs),
            "enabled_jobs": sum(1 for j in all_jobs if j.enabled),
            "scheduled_jobs": sum(1 for j in all_jobs if j.payload.kind == "scheduled"),
            "heartbeat_jobs": sum(1 for j in all_jobs if j.payload.kind == "heartbeat"),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }
