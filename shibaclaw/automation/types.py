"""Automation types – shared by scheduled and heartbeat jobs."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AutomationSchedule:
    """When to run the job.

    kind:
        ``at``    – run once at the given epoch-ms timestamp (``at_ms``)
        ``every`` – repeat every N milliseconds (``every_ms``)
        ``cron``  – repeat on a cron expression (``expr``), optionally with ``tz``
    """

    kind: Literal["at", "every", "cron"]
    at_ms: int | None = None
    every_ms: int | None = None
    expr: str | None = None
    tz: str | None = None


@dataclass
class AutomationPayload:
    """What to do when the job fires.

    kind:
        ``scheduled``  – run a free-text agent turn (``message`` field)
        ``heartbeat``  – read a Markdown file, let the LLM decide whether
                         there is work to do, then call ``on_heartbeat``
    """

    kind: Literal["scheduled", "heartbeat"] = "scheduled"

    # --- scheduled payload ---
    message: str = ""

    # --- heartbeat payload ---
    # Path to the .md file, relative to workspace (defaults to HEARTBEAT.md)
    heartbeat_file: str | None = None

    # --- delivery (both kinds) ---
    deliver: bool = False
    channel: str | None = None          # e.g. "whatsapp"
    to: str | None = None               # e.g. phone number
    session_key: str | None = None      # stable session key
    profile_id: str | None = None       # profile to use
    targets: dict[str, str] = field(default_factory=dict)


@dataclass
class AutomationRunRecord:
    """Single execution record."""

    run_at_ms: int
    status: Literal["ok", "error", "skipped"]
    duration_ms: int = 0
    error: str | None = None


@dataclass
class AutomationJobState:
    """Mutable runtime state of a job."""

    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    run_history: list[AutomationRunRecord] = field(default_factory=list)


@dataclass
class AutomationJob:
    """A single automation job (scheduled or heartbeat)."""

    id: str
    name: str
    enabled: bool = True
    schedule: AutomationSchedule = field(
        default_factory=lambda: AutomationSchedule(kind="every", every_ms=1_800_000)
    )
    payload: AutomationPayload = field(default_factory=AutomationPayload)
    state: AutomationJobState = field(default_factory=AutomationJobState)
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False


@dataclass
class AutomationStore:
    """Persistent store for all automation jobs."""

    version: int = 1
    jobs: list[AutomationJob] = field(default_factory=list)
