"""Runtime path helpers derived from the active config context."""

from __future__ import annotations

import sys
from pathlib import Path

from shibaclaw.config.loader import get_config_path
from shibaclaw.helpers.helpers import ensure_dir


def get_app_root() -> Path:
    """Return the stable application root directory (~/.shibaclaw).

    This is the canonical base for all user-level data that must not move
    when ``--config`` points to a custom location: auth tokens, update cache,
    bridge install, and CLI history all live here.
    """
    return ensure_dir(Path.home() / ".shibaclaw")


def get_runtime_root() -> Path:
    """Return the root directory that contains bundled runtime resources.

    Handles PyInstaller frozen environments (both --onefile and --onedir)
    as well as direct source execution.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        # In newer PyInstaller versions, resources might be in an '_internal' subdir
        internal = meipass / "_internal"
        return internal if internal.exists() else meipass
    return Path(__file__).resolve().parents[2]


def get_assets_dir() -> Path:
    """Return the assets directory for source or frozen execution."""
    bundled_assets = get_runtime_root() / "assets"
    if bundled_assets.exists():
        return bundled_assets
    return get_app_root() / "assets"


def get_data_dir() -> Path:
    """Return the instance-level runtime data directory.

    Follows any active config override (``--config``).  Use :func:`get_app_root`
    when you need the stable ``~/.shibaclaw`` base regardless of overrides.
    """
    return ensure_dir(get_config_path().parent)


def get_runtime_subdir(name: str) -> Path:
    """Return a named runtime subdirectory under the instance data dir."""
    return ensure_dir(get_data_dir() / name)


def get_media_dir(channel: str | None = None) -> Path:
    """Return the media directory, optionally namespaced per channel."""
    base = get_runtime_subdir("media")
    return ensure_dir(base / channel) if channel else base


def get_cron_dir() -> Path:
    """Return the cron storage directory."""
    return get_runtime_subdir("cron")


def get_logs_dir() -> Path:
    """Return the logs directory."""
    return get_runtime_subdir("logs")


def get_workspace_path(workspace: str | None = None) -> Path:
    """Resolve and ensure the agent workspace path."""
    path = Path(workspace).expanduser() if workspace else Path.home() / ".shibaclaw" / "workspace"
    return ensure_dir(path)


def get_cli_history_path() -> Path:
    """Return the shared CLI history file path."""
    return Path.home() / ".shibaclaw" / "history" / "cli_history"


def get_bridge_install_dir() -> Path:
    """Return the shared WhatsApp bridge installation directory."""
    return Path.home() / ".shibaclaw" / "bridge"


def get_legacy_sessions_dir() -> Path:
    """Return the legacy global session directory used for migration fallback."""
    return Path.home() / ".shibaclaw" / "sessions"
