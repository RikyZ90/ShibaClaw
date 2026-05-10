"""Heartbeat service - periodic agent wake-up to check for tasks."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import yaml
from loguru import logger

from shibaclaw.config.schema import HeartbeatConfig

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
        provider: Thinker | None,
        model: str,
        on_execute: Callable[..., Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[..., Coroutine[Any, Any, None]] | None = None,
        interval_min: int = 30,
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
        self.interval_min = interval_min
        self.enabled = enabled
        self.session_key = session_key
        self.targets = targets or {}
        self.profile_id = profile_id
        self._running = False
        self._task: asyncio.Task | None = None
        self._provider_warning_logged = False
        self._content_notice_logged = False
        self._config_warning_logged = False
        self._last_check_ms: int | None = None
        self._last_action: str | None = None
        self._last_run_ms: int | None = None
        self._last_error: str | None = None

    @property
    def interval_s(self) -> int:
        """Interval in seconds for backward compatibility."""
        return self.interval_min * 60

    @interval_s.setter
    def interval_s(self, value: int) -> None:
        """Set interval in seconds, updating interval_min for backward compatibility."""
        self.interval_min = value // 60

    async def reconfigure(self, hb_cfg: Any, new_provider: Any, model: str) -> None:
        """Hot-reload heartbeat configuration without restarting the gateway process."""
        self.provider = new_provider
        self.model = model
        self.session_key = hb_cfg.session_key
        self.targets = hb_cfg.targets or {}
        self.profile_id = hb_cfg.profile_id

        schedule_changed = (
            hb_cfg.interval_min != self.interval_min or hb_cfg.enabled != self.enabled
        )
        if schedule_changed:
            self.stop()
            self.interval_min = hb_cfg.interval_min
            self.enabled = hb_cfg.enabled
            if self.enabled:
                await self.start()
            else:
                logger.info("Heartbeat disabled via reconfigure")
        logger.info("HeartbeatService reconfigured (enabled={}, interval={}s)", self.enabled, self.interval_s)

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

    def _default_settings(self) -> HeartbeatConfig:
        return HeartbeatConfig(
            enabled=self.enabled,
            interval_min=self.interval_min,
            session_key=self.session_key,
            targets=dict(self.targets),
            profile_id=self.profile_id,
        )

    def _parse_document(self, content: str | None) -> tuple[HeartbeatConfig, str]:
        settings = self._default_settings()
        if not content:
            return settings, ""

        if not content.startswith("---"):
            self._config_warning_logged = False
            return settings, content

        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            self._config_warning_logged = False
            return settings, content

        end_idx: int | None = None
        for idx, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = idx
                break

        if end_idx is None:
            self._config_warning_logged = False
            return settings, content

        raw_frontmatter = "\n".join(lines[1:end_idx]).strip()
        body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
        if not raw_frontmatter:
            self._config_warning_logged = False
            return settings, body

        try:
            parsed = yaml.safe_load(raw_frontmatter) or {}
            if not isinstance(parsed, dict):
                raise ValueError("frontmatter must be a mapping")
            if isinstance(parsed.get("heartbeat"), dict):
                parsed = parsed["heartbeat"]
            if not isinstance(parsed, dict):
                raise ValueError("heartbeat config must be a mapping")
            parsed = {
                key: value
                for key, value in parsed.items()
                if key in {"session_key", "targets", "profile_id"}
            }
            settings = HeartbeatConfig.model_validate(
                {
                    **settings.model_dump(),
                    **parsed,
                }
            )
            self._config_warning_logged = False
        except Exception as exc:
            if not self._config_warning_logged:
                logger.warning(
                    "Heartbeat: invalid HEARTBEAT.md frontmatter, using config defaults: {}", exc
                )
                self._config_warning_logged = True

        return settings, body

    def _extract_active_tasks(self, content: str) -> str:
        cleaned = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        active_match = re.search(r"(?im)^##\s+Active Tasks\s*$", cleaned)

        if active_match:
            relevant = cleaned[active_match.end() :]
            next_section = re.search(r"(?im)^##\s+", relevant)
            if next_section:
                relevant = relevant[: next_section.start()]
        else:
            relevant = cleaned

        lines: list[str] = []
        for raw_line in relevant.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped == "---":
                continue
            lines.append(raw_line.rstrip())

        return "\n".join(lines).strip()

    def _load_runtime_state(self, content: str | None = None) -> tuple[HeartbeatConfig, str]:
        raw_content = content if content is not None else self._read_heartbeat_file()
        settings, task_content = self._parse_document(raw_content)
        return settings, self._extract_active_tasks(task_content)

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: ask LLM to decide skip/run via virtual tool call.

        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        from shibaclaw.helpers.helpers import current_time_str

        if not self.provider:
            logger.warning("Heartbeat: no AI provider is configured")
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
                        "Review the following HEARTBEAT.md and decide whether there are active tasks.\n\n"
                        f"{content}"
                    ),
                },
            ],
            tools=_HEARTBEAT_TOOL,
            model=self.model,
            log_transient_errors=False,
        )

        if response.finish_reason == "error":
            if self.provider._is_transient_error(response.content):
                logger.warning(
                    "Heartbeat: provider rate limited while checking tasks, skipping this cycle"
                )
            else:
                logger.warning(
                    "Heartbeat: decision request failed: {}", (response.content or "")[:200]
                )

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

        settings, active_tasks = self._load_runtime_state()
        if not active_tasks:
            if not self._content_notice_logged:
                logger.info("Heartbeat: HEARTBEAT.md has no active tasks, skipping")
                self._content_notice_logged = True
            return
        self._content_notice_logged = False

        logger.info("Heartbeat: checking for tasks...")

        try:
            action, tasks = await self._decide(active_tasks)
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
                    session_key=settings.session_key,
                    profile_id=settings.profile_id,
                    targets=settings.targets,
                )

                if response:
                    should_notify = await evaluate_response(
                        response,
                        tasks,
                        self.provider,
                        self.model,
                    )
                    if should_notify and self.on_notify:
                        logger.info("Heartbeat: completed, delivering response")
                        await self.on_notify(response, targets=settings.targets)
                    else:
                        logger.info("Heartbeat: silenced by post-run evaluation")
            self._last_error = None
        except Exception:
            self._last_error = "execution failed"
            logger.exception("Heartbeat execution failed")

    def status(self) -> dict:
        """Return serializable telemetry for the sidebar UI."""
        hb_file = self.heartbeat_file
        settings, _ = self._load_runtime_state()
        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_s": self.interval_s,
            "heartbeat_file_exists": hb_file.exists(),
            "last_check_ms": self._last_check_ms,
            "last_action": self._last_action,
            "last_run_ms": self._last_run_ms,
            "last_error": self._last_error,
            "session_key": settings.session_key,
            "targets": settings.targets,
            "profile_id": settings.profile_id,
        }

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        settings, active_tasks = self._load_runtime_state()
        if not self.enabled:
            return None
        if not active_tasks:
            return None
        action, tasks = await self._decide(active_tasks)
        self._last_check_ms = int(time.time() * 1000)
        self._last_action = action
        if action != "run" or not self.on_execute:
            return None
        self._last_run_ms = int(time.time() * 1000)
        try:
            result = await self.on_execute(
                tasks,
                session_key=settings.session_key,
                profile_id=settings.profile_id,
                targets=settings.targets,
            )
            self._last_error = None
            return result
        except Exception as e:
            self._last_error = str(e)
            raise
