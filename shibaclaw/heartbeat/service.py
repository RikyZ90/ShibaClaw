"""Heartbeat service - periodic agent wake-up to check for tasks."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

if TYPE_CHECKING:
    from shibaclaw.thinkers.base import Thinker

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


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.

    Phase 1 (decision): reads HEARTBEAT.md and asks the LLM — via a virtual
    tool call — whether there are active tasks.  This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.

    Phase 2 (execution): only triggered when Phase 1 returns ``run``.  The
    ``on_execute`` callback runs the task through the full agent loop and
    returns the result to deliver.
    """

    def __init__(
        self,
        workspace: Path,
        provider: Thinker,
        model: str,
        on_execute: Callable[..., Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[..., Coroutine[Any, Any, None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
        session_key: str = "heartbeat:default",
        targets: dict[str, str] | None = None,
        profile_id: str | None = None,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self.session_key = session_key
        self.targets = targets or {}
        self.profile_id = profile_id
        self._running = False
        self._task: asyncio.Task | None = None
        self._provider_warning_logged = False
        self._content_notice_logged = False
        self._last_check_ms: int | None = None
        self._last_action: str | None = None
        self._last_run_ms: int | None = None
        self._last_error: str | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: ask LLM to decide skip/run via virtual tool call.

        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        from shibaclaw.helpers.helpers import current_time_str

        response = await self.provider.chat_with_retry(
            messages=[
                {"role": "system", "content": "You are a heartbeat agent. Call the heartbeat tool to report your decision."},
                {"role": "user", "content": (
                    f"Current Time: {current_time_str()}\n\n"
                    "Review the following HEARTBEAT.md and decide whether there are active tasks.\n\n"
                    f"{content}"
                )},
            ],
            tools=_HEARTBEAT_TOOL,
            model=self.model,
            log_transient_errors=False,
        )

        if response.finish_reason == "error":
            if self.provider._is_transient_error(response.content):
                logger.warning("Heartbeat: provider rate limited while checking tasks, skipping this cycle")
            else:
                logger.warning("Heartbeat: decision request failed: {}", (response.content or "")[:200])

        if not response.has_tool_calls:
            logger.warning("Heartbeat: decision request returned no tool call, skipping")
            return "skip", ""

        args = response.tool_calls[0].arguments
        return args.get("action", "skip"), args.get("tasks", "")

    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return
        if self._running:
            logger.warning("Heartbeat already running")
            return
        if not self.provider:
            logger.warning("Heartbeat enabled but no AI provider is configured")

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat started (every {}s, first check immediately)", self.interval_s)

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        first_tick = True
        while self._running:
            try:
                if first_tick:
                    first_tick = False
                else:
                    await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        if not self.provider:
            if not self._provider_warning_logged:
                logger.warning("Heartbeat skipped: no AI provider is configured")
                self._provider_warning_logged = True
            return
        self._provider_warning_logged = False
        from shibaclaw.helpers.evaluator import evaluate_response

        content = self._read_heartbeat_file()
        if not content or not content.strip():
            if not self._content_notice_logged:
                logger.info("Heartbeat: HEARTBEAT.md missing or empty, skipping")
                self._content_notice_logged = True
            return
        self._content_notice_logged = False

        logger.info("Heartbeat: checking for tasks...")

        try:
            action, tasks = await self._decide(content)
            self._last_check_ms = int(time.time() * 1000)
            self._last_action = action

            if action != "run":
                logger.info("Heartbeat: OK (nothing to report)")
                return

            logger.info("Heartbeat: tasks found, executing...")
            if self.on_execute:
                self._last_run_ms = int(time.time() * 1000)
                response = await self.on_execute(
                    tasks,
                    session_key=self.session_key,
                    profile_id=self.profile_id,
                    targets=self.targets,
                )

                if response:
                    should_notify = await evaluate_response(
                        response, tasks, self.provider, self.model,
                    )
                    if should_notify and self.on_notify:
                        logger.info("Heartbeat: completed, delivering response")
                        await self.on_notify(response, targets=self.targets)
                    else:
                        logger.info("Heartbeat: silenced by post-run evaluation")
            self._last_error = None
        except Exception:
            self._last_error = "execution failed"
            logger.exception("Heartbeat execution failed")

    def status(self) -> dict:
        """Return serializable telemetry for the sidebar UI."""
        hb_file = self.heartbeat_file
        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_s": self.interval_s,
            "heartbeat_file_exists": hb_file.exists(),
            "last_check_ms": self._last_check_ms,
            "last_action": self._last_action,
            "last_run_ms": self._last_run_ms,
            "last_error": self._last_error,
            "session_key": self.session_key,
            "targets": self.targets,
            "profile_id": self.profile_id,
        }

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        content = self._read_heartbeat_file()
        if not content:
            return None
        action, tasks = await self._decide(content)
        self._last_check_ms = int(time.time() * 1000)
        self._last_action = action
        if action != "run" or not self.on_execute:
            return None
        self._last_run_ms = int(time.time() * 1000)
        try:
            result = await self.on_execute(
                tasks,
                session_key=self.session_key,
                profile_id=self.profile_id,
                targets=self.targets,
            )
            self._last_error = None
            return result
        except Exception as e:
            self._last_error = str(e)
            raise
