"""Types for the unified Automation module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AutomationSchedule:
    """When to run a job.

    kind:
      - "at"    — one-shot at a specific epoch-ms timestamp
      - "every" — repeat every N milliseconds
      - "cron"  — standard 5-field cron expression (requires croniter)
    """

    kind: Literal["at", "every", "cron"]
    at_ms: int | None = None
    every_ms: int | None = None
    expr: str | None = None
    tz: str | None = None


@dataclass
class AutomationPayload:
    """What a job does when it fires.

    kind:
      - "scheduled"  — sends a fixed *message* to the agent (ex-cron behaviour)
      - "heartbeat"  — reads a .md file; an LLM decides whether to act
                       (ex-heartbeat behaviour)
    """

    kind: Literal["scheduled", "heartbeat"] = "scheduled"

    # --- scheduled ---
    message: str = ""

    # --- heartbeat ---
    # Path relative to workspace; defaults to "TASK.md"
    heartbeat_file: str | None = None

    # --- delivery (both kinds) ---
    deliver: bool = False
    channel: str | None = None
    to: str | None = None
    session_key: str | None = None
    profile_id: str | None = None
    targets: dict[str, str] = field(default_factory=dict)


@dataclass
class AutomationJobState:
    next_run_at_ms: int = 0
    last_run_at_ms: int = 0
    # "pending" | "ok" | "error" | "skipped"
    last_status: str = "pending"
    last_error: str = ""
    run_count: int = 0


@dataclass
class AutomationJob:
    id: str
    name: str
    schedule: AutomationSchedule
    payload: AutomationPayload
    state: AutomationJobState = field(default_factory=AutomationJobState)
    enabled: bool = True
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False
