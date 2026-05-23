"""AutomationService — unified cron + heartbeat scheduler.

Replaces both CronService (shibaclaw/cron/) and HeartbeatService
(shibaclaw/heartbeat/).  A single asyncio event-driven timer loop manages
jobs of two kinds:

  - ``scheduled``  fire an agent turn with a fixed message (ex-cron)
  - ``heartbeat``  read a .md file; let the LLM decide whether to act
                   (ex-heartbeat, including tool-call decision phase and
                   evaluate_response post-run silencing)

Persistence
-----------
Jobs are stored in ``automation.json`` (same directory as the old
``jobs.json``).  On first start, if ``automation.json`` is missing but
``jobs.json`` exists, a one-shot migration copies all legacy cron jobs
over as *scheduled* jobs and writes ``automation.json``.

The heartbeat configuration previously embedded in ``HEARTBEAT.md``
frontmatter (session_key, targets, profile_id) is now part of each job's
``AutomationPayload``.  The ``HEARTBEAT.md`` body (Active Tasks section)
is still read at runtime — it is **not** stored in the job definition.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from .types import AutomationJob, AutomationJobState, AutomationPayload, AutomationSchedule

# ---------------------------------------------------------------------------
# Virtual tool descriptor used in the heartbeat decision phase
# (identical to the one in the old HeartbeatService)
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
# Callback type aliases
# ---------------------------------------------------------------------------

OnScheduledCallback = Callable[["AutomationJob"], Awaitable[Optional[str]]]
OnHeartbeatCallback = Callable[..., Awaitable[str]]
OnNotifyCallback = Callable[..., Awaitable[None]]


# ---------------------------------------------------------------------------
# Schedule helpers (ported verbatim from cron/service.py)
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: AutomationSchedule, now_ms: int) -> int | None:
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
# Heartbeat file helpers (ported from heartbeat/service.py)
# ---------------------------------------------------------------------------

def _extract_active_tasks(content: str) -> str:
    """Extract the Active Tasks section from a HEARTBEAT.md body."""
    cleaned = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    active_match = re.search(r"(?im)^##\s+Active Tasks\s*$", cleaned)
    if active_match:
        relevant = cleaned[active_match.end():]
        next_section = re.search(r"(?im)^##\s+", relevant)
        if next_section:
            relevant = relevant[:next_section.start()]
    else:
        relevant = cleaned
    lines = []
    for raw_line in relevant.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        lines.append(raw_line.rstrip())
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# AutomationService
# ---------------------------------------------------------------------------


class AutomationService:
    """Unified automation scheduler.

    Parameters
    ----------
    store_path:
        Path to ``automation.json`` (persists all jobs).
    workspace:
        Agent workspace root (used to locate heartbeat .md files).
    on_scheduled:
        Async callback invoked for *scheduled* jobs.  Receives the
        :class:`AutomationJob`; should return the agent response string
        (or ``None``).
    on_heartbeat:
        Async callback invoked for *heartbeat* jobs after the LLM decides
        to ``run``.  Signature matches the old ``on_execute`` of
        ``HeartbeatService``.
    on_notify:
        Async callback for delivering a heartbeat response to the user.
        Signature matches the old ``on_notify`` of ``HeartbeatService``.
    provider:
        LLM thinker instance used for the heartbeat decision phase.
    model:
        Model name forwarded to the provider for heartbeat decisions.
    """

    _MAX_RUN_HISTORY = 20

    def __init__(
        self,
        store_path: Path,
        workspace: Path,
        on_scheduled: OnScheduledCallback | None = None,
        on_heartbeat: OnHeartbeatCallback | None = None,
        on_notify: OnNotifyCallback | None = None,
        provider: Any = None,
        model: str | None = None,
    ) -> None:
        self._store_path = store_path
        self._workspace = workspace
        self._on_scheduled = on_scheduled
        self._on_heartbeat = on_heartbeat
        self._on_notify = on_notify
        self._provider = provider
        self._model = model

        self._jobs: dict[str, AutomationJob] = {}
        self._save_lock = asyncio.Lock()
        self._timer_task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._running = False

        # Suppress repeated warnings
        self._provider_warning_logged = False
        self._last_mtime: float = 0.0

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load jobs from automation.json; fall back to migrating jobs.json."""
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                for d in data.get("jobs", []):
                    job = self._job_from_dict(d)
                    self._jobs[job.id] = job
                self._last_mtime = self._store_path.stat().st_mtime
                logger.debug("AutomationService: loaded {} jobs", len(self._jobs))
                return
            except Exception as exc:
                logger.warning("AutomationService: failed to load store: {}", exc)
        self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        """One-shot migration from the old CronService jobs.json format."""
        legacy = self._store_path.parent / "jobs.json"
        if not legacy.exists():
            return
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            migrated = 0
            for d in data.get("jobs", []):
                s = d.get("schedule", {})
                p = d.get("payload", {})
                st = d.get("state", {})
                now = _now_ms()
                job = AutomationJob(
                    id=d.get("id", str(uuid.uuid4())[:8]),
                    name=d.get("name", "Migrated job"),
                    enabled=d.get("enabled", True),
                    delete_after_run=d.get("deleteAfterRun", False),
                    created_at_ms=d.get("createdAtMs", now),
                    updated_at_ms=d.get("updatedAtMs", now),
                    schedule=AutomationSchedule(
                        kind=s.get("kind", "every"),
                        at_ms=s.get("atMs"),
                        every_ms=s.get("everyMs"),
                        expr=s.get("expr"),
                        tz=s.get("tz"),
                    ),
                    payload=AutomationPayload(
                        kind="scheduled",
                        message=p.get("message", ""),
                        deliver=p.get("deliver", False),
                        channel=p.get("channel"),
                        to=p.get("to"),
                        session_key=p.get("sessionKey"),
                    ),
                    state=AutomationJobState(
                        next_run_at_ms=st.get("nextRunAtMs") or 0,
                        last_run_at_ms=st.get("lastRunAtMs") or 0,
                        last_status=st.get("lastStatus") or "pending",
                        last_error=st.get("lastError") or "",
                        run_count=len(st.get("runHistory", [])),
                    ),
                )
                self._jobs[job.id] = job
                migrated += 1
            self._save_unlocked()
            logger.info(
                "AutomationService: migrated {} jobs from legacy jobs.json → automation.json",
                migrated,
            )
        except Exception as exc:
            logger.warning("AutomationService: legacy migration failed: {}", exc)

    def _save_unlocked(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"jobs": [self._job_to_dict(j) for j in self._jobs.values()]}
            self._store_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            self._last_mtime = self._store_path.stat().st_mtime
        except Exception as exc:
            logger.warning("AutomationService: failed to save store: {}", exc)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _job_to_dict(j: AutomationJob) -> dict:
        return {
            "id": j.id,
            "name": j.name,
            "enabled": j.enabled,
            "deleteAfterRun": j.delete_after_run,
            "createdAtMs": j.created_at_ms,
            "updatedAtMs": j.updated_at_ms,
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
                "runCount": j.state.run_count,
            },
        }

    @staticmethod
    def _job_from_dict(d: dict) -> AutomationJob:
        s = d.get("schedule", {})
        p = d.get("payload", {})
        st = d.get("state", {})
        return AutomationJob(
            id=d["id"],
            name=d.get("name", ""),
            enabled=d.get("enabled", True),
            delete_after_run=d.get("deleteAfterRun", False),
            created_at_ms=d.get("createdAtMs", 0),
            updated_at_ms=d.get("updatedAtMs", 0),
            schedule=AutomationSchedule(
                kind=s.get("kind", "every"),
                at_ms=s.get("atMs"),
                every_ms=s.get("everyMs"),
                expr=s.get("expr"),
                tz=s.get("tz"),
            ),
            payload=AutomationPayload(
                kind=p.get("kind", "scheduled"),
                message=p.get("message", ""),
                heartbeat_file=p.get("heartbeatFile"),
                deliver=p.get("deliver", False),
                channel=p.get("channel"),
                to=p.get("to"),
                session_key=p.get("sessionKey"),
                profile_id=p.get("profileId"),
                targets=p.get("targets") or {},
            ),
            state=AutomationJobState(
                next_run_at_ms=st.get("nextRunAtMs") or 0,
                last_run_at_ms=st.get("lastRunAtMs") or 0,
                last_status=st.get("lastStatus") or "pending",
                last_error=st.get("lastError") or "",
                run_count=st.get("runCount") or 0,
            ),
        )

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
        """Add (and persist) a new job. Returns the created job."""
        _validate_schedule(schedule)
        now = _now_ms()
        job = AutomationJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            delete_after_run=delete_after_run,
            created_at_ms=now,
            updated_at_ms=now,
            schedule=schedule,
            payload=payload,
            state=AutomationJobState(
                next_run_at_ms=_compute_next_run(schedule, now) or 0
            ),
        )
        self._jobs[job.id] = job
        self._save_unlocked()
        self._rearm()
        logger.info("AutomationService: added job '{}' ({}) [{}]", name, job.id, payload.kind)
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID. Returns True if found and removed."""
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._save_unlocked()
        self._rearm()
        logger.info("AutomationService: removed job {}", job_id)
        return True

    def enable_job(self, job_id: str, enabled: bool = True) -> AutomationJob | None:
        """Enable or disable a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        job.enabled = enabled
        job.updated_at_ms = _now_ms()
        if enabled:
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms()) or 0
        else:
            job.state.next_run_at_ms = 0
        self._save_unlocked()
        self._rearm()
        return job

    def update_job(self, job_id: str, patch: dict) -> AutomationJob | None:
        """Update a job partially by id."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        if "name" in patch:
            job.name = patch["name"]
        if "enabled" in patch:
            job.enabled = patch["enabled"]
        if "deleteAfterRun" in patch or "delete_after_run" in patch:
            job.delete_after_run = patch.get("deleteAfterRun", patch.get("delete_after_run"))
        if "schedule" in patch:
            s = patch["schedule"]
            if isinstance(s, dict):
                kind = s.get("kind", job.schedule.kind)
                at_ms = s.get("atMs", s.get("at_ms", job.schedule.at_ms))
                every_ms = s.get("everyMs", s.get("every_ms", job.schedule.every_ms))
                expr = s.get("expr", job.schedule.expr)
                tz = s.get("tz", job.schedule.tz)
                new_sched = AutomationSchedule(
                    kind=kind,
                    at_ms=at_ms,
                    every_ms=every_ms,
                    expr=expr,
                    tz=tz,
                )
                _validate_schedule(new_sched)
                job.schedule = new_sched
        if "payload" in patch:
            p = patch["payload"]
            if isinstance(p, dict):
                kind = p.get("kind", job.payload.kind)
                message = p.get("message", job.payload.message)
                heartbeat_file = p.get("heartbeatFile", p.get("heartbeat_file", job.payload.heartbeat_file))
                deliver = p.get("deliver", job.payload.deliver)
                channel = p.get("channel", job.payload.channel)
                to = p.get("to", job.payload.to)
                session_key = p.get("sessionKey", p.get("session_key", job.payload.session_key))
                profile_id = p.get("profileId", p.get("profile_id", job.payload.profile_id))
                targets = p.get("targets", job.payload.targets)
                job.payload = AutomationPayload(
                    kind=kind,
                    message=message,
                    heartbeat_file=heartbeat_file,
                    deliver=deliver,
                    channel=channel,
                    to=to,
                    session_key=session_key,
                    profile_id=profile_id,
                    targets=targets or {},
                )
        job.updated_at_ms = _now_ms()
        if job.enabled:
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms()) or 0
        else:
            job.state.next_run_at_ms = 0
        self._save_unlocked()
        self._rearm()
        return job

    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually trigger a job (regardless of its schedule)."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if not force and not job.enabled:
            return False
        asyncio.create_task(self._execute(job, force=True))
        return True

    def list_jobs(self, include_disabled: bool = True) -> list[AutomationJob]:
        jobs = list(self._jobs.values())
        if not include_disabled:
            jobs = [j for j in jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float("inf"))

    def get_job(self, job_id: str) -> AutomationJob | None:
        return self._jobs.get(job_id)

    def status(self) -> dict:
        jobs = list(self._jobs.values())
        scheduled = [j for j in jobs if j.payload.kind == "scheduled"]
        heartbeats = [j for j in jobs if j.payload.kind == "heartbeat"]
        return {
            "running": self._running,
            "jobs": len(jobs),
            "enabled": sum(1 for j in jobs if j.enabled),
            "scheduled": len(scheduled),
            "heartbeats": len(heartbeats),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }

    async def reconfigure(self, provider: Any, model: str | None) -> None:
        """Hot-reload provider/model without restarting."""
        self._provider = provider
        self._model = model
        logger.info("AutomationService: reconfigured")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._fire_overdue_at_jobs()
        self._rearm()
        logger.info(
            "AutomationService: started ({} jobs)",
            len(self._jobs),
        )

    def stop(self) -> None:
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        logger.info("AutomationService: stopped")

    # ------------------------------------------------------------------
    # Internal timer
    # ------------------------------------------------------------------

    def _get_next_wake_ms(self) -> int | None:
        candidates = [
            j.state.next_run_at_ms
            for j in self._jobs.values()
            if j.enabled and j.state.next_run_at_ms
        ]
        return min(candidates) if candidates else None

    def _rearm(self) -> None:
        """Cancel the current timer and schedule the next one."""
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        if not self._running:
            return
        next_wake = self._get_next_wake_ms()
        if not next_wake:
            return
        delay_s = max(0.0, (next_wake - _now_ms()) / 1000)

        async def _tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(_tick(), name="automation-timer")

    async def _fire_overdue_at_jobs(self) -> None:
        """On startup, immediately fire one-shot 'at' jobs that are already due."""
        now = _now_ms()
        overdue = [
            j
            for j in self._jobs.values()
            if j.enabled
            and j.schedule.kind == "at"
            and j.schedule.at_ms
            and j.schedule.at_ms <= now
            and not j.state.last_run_at_ms
        ]
        for job in overdue:
            logger.info(
                "AutomationService: firing overdue job '{}' (was scheduled at {})",
                job.name, job.schedule.at_ms,
            )
            await self._execute(job, force=True)

    async def _on_timer(self) -> None:
        now = _now_ms()
        due = [
            j for j in self._jobs.values()
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]
        # Advance next_run before dispatching so we don't double-fire
        for job in due:
            if job.schedule.kind == "at":
                job.state.next_run_at_ms = 0
            else:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now) or 0
        self._save_unlocked()
        self._rearm()
        for job in due:
            asyncio.create_task(self._run_job_bg(job))

    async def _run_job_bg(self, job: AutomationJob) -> None:
        await self._execute(job)
        async with self._save_lock:
            self._save_unlocked()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute(self, job: AutomationJob, force: bool = False) -> None:
        start_ms = _now_ms()
        logger.info(
            "AutomationService: executing '{}' [{}] ({})",
            job.name, job.payload.kind, job.id,
        )
        try:
            if job.payload.kind == "scheduled":
                await self._execute_scheduled(job)
            else:
                await self._execute_heartbeat(job)
            job.state.last_status = "ok"
            job.state.last_error = ""
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)
            logger.error("AutomationService: job '{}' failed: {}", job.name, exc)
        finally:
            job.state.run_count += 1
            job.state.last_run_at_ms = start_ms
            job.updated_at_ms = _now_ms()
            if job.schedule.kind == "at":
                if job.delete_after_run:
                    self._jobs.pop(job.id, None)
                    logger.info("AutomationService: removed one-shot job '{}'", job.name)
                else:
                    job.enabled = False
                    job.state.next_run_at_ms = 0
            elif force:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms()) or 0

    async def _execute_scheduled(self, job: AutomationJob) -> None:
        """Run a scheduled job: send a fixed message through the agent."""
        if not self._on_scheduled:
            logger.debug(
                "AutomationService: no on_scheduled callback, skipping '{}'", job.name
            )
            return
        if not job.payload.message.strip():
            logger.info(
                "AutomationService: job '{}' skipped — empty message", job.name
            )
            job.state.last_status = "skipped"
            return
        await self._on_scheduled(job)

    async def _execute_heartbeat(self, job: AutomationJob) -> None:
        """Run a heartbeat job: LLM decides whether to act."""
        if not self._provider:
            if not self._provider_warning_logged:
                logger.warning(
                    "AutomationService: heartbeat '{}' skipped — no AI provider", job.name
                )
                self._provider_warning_logged = True
            job.state.last_status = "skipped"
            return
        self._provider_warning_logged = False

        hb_path = self._workspace / (job.payload.heartbeat_file or "HEARTBEAT.md")
        if not hb_path.exists():
            logger.debug(
                "AutomationService: heartbeat file '{}' not found, skipping", hb_path
            )
            job.state.last_status = "skipped"
            return

        try:
            raw_content = hb_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(
                "AutomationService: cannot read '{}': {}", hb_path, exc
            )
            return

        active_tasks = _extract_active_tasks(raw_content)
        if not active_tasks:
            logger.debug(
                "AutomationService: heartbeat '{}' — no active tasks in '{}'",
                job.name, hb_path.name,
            )
            job.state.last_status = "skipped"
            return

        # --- Phase 1: decide (via virtual tool call) ---
        action, tasks = await self._heartbeat_decide(active_tasks)
        if action != "run":
            logger.info(
                "AutomationService: heartbeat '{}' → skip (LLM decision)", job.name
            )
            job.state.last_status = "skipped"
            return

        logger.info(
            "AutomationService: heartbeat '{}' → run: {}", job.name, tasks[:80]
        )

        # --- Phase 2: execute ---
        if not self._on_heartbeat:
            return

        session_key = job.payload.session_key or f"automation:{job.id}"
        response = await self._on_heartbeat(
            tasks,
            session_key=session_key,
            profile_id=job.payload.profile_id,
            targets=job.payload.targets or None,
        )

        # --- Phase 3: evaluate & notify ---
        if response and self._on_notify:
            should_notify = True
            try:
                from shibaclaw.helpers.evaluator import evaluate_response
                should_notify = await evaluate_response(
                    response, tasks, self._provider, self._model
                )
            except Exception as exc:
                logger.debug(
                    "AutomationService: evaluate_response failed for '{}': {}", job.name, exc
                )
            if should_notify:
                logger.info(
                    "AutomationService: heartbeat '{}' — delivering response", job.name
                )
                await self._on_notify(
                    response,
                    targets=job.payload.targets or None,
                    source="automation",
                    persist=True,
                    msg_type="response",
                )
            else:
                logger.info(
                    "AutomationService: heartbeat '{}' — silenced by post-run evaluation",
                    job.name,
                )

    async def _heartbeat_decide(self, active_tasks: str) -> tuple[str, str]:
        """Phase 1 of heartbeat: ask LLM via tool call → (action, tasks)."""
        try:
            from shibaclaw.helpers.helpers import current_time_str
            response = await self._provider.chat_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a heartbeat agent. "
                            "Call the heartbeat tool to report your decision."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Current Time: {current_time_str()}\n\n"
                            "Review the following HEARTBEAT.md and decide whether there are "
                            "active tasks.\n\n"
                            f"{active_tasks}"
                        ),
                    },
                ],
                tools=_HEARTBEAT_TOOL,
                model=self._model,
                log_transient_errors=False,
            )
            if response.finish_reason == "error":
                logger.warning(
                    "AutomationService: heartbeat decide failed: {}",
                    (response.content or "")[:200],
                )
                return "skip", ""
            if not response.has_tool_calls:
                logger.warning(
                    "AutomationService: heartbeat decide returned no tool call, skipping"
                )
                return "skip", ""
            args = response.tool_calls[0].arguments
            return args.get("action", "skip"), args.get("tasks", "")
        except Exception as exc:
            logger.warning("AutomationService: heartbeat decide exception: {}", exc)
            return "skip", ""
