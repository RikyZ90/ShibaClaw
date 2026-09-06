"""Per-turn FS/exec permission mode via contextvars (concurrent-safe)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path

_mode: ContextVar[str | None] = ContextVar("shibaclaw_permission_mode", default=None)
_workspace: ContextVar[Path | None] = ContextVar("shibaclaw_permission_ws", default=None)


def bind_permission_mode(mode: str, workspace: Path | None) -> tuple[Token, Token]:
    """Bind mode for the current asyncio Task / call stack."""
    return _mode.set(mode), _workspace.set(workspace)


def reset_permission_mode(tokens: tuple[Token, Token] | None) -> None:
    if not tokens:
        return
    _mode.reset(tokens[0])
    _workspace.reset(tokens[1])


def turn_permission_mode() -> str | None:
    return _mode.get()


def turn_permission_workspace() -> Path | None:
    return _workspace.get()


def resolve_turn_sandbox(
    *,
    default_allowed_dir: Path | None,
    default_readonly: bool = False,
) -> tuple[Path | None, bool, bool]:
    """Return (allowed_dir, readonly, restrict_exec) for the current turn.

    When no turn mode is bound, falls back to tool defaults.
    """
    mode = _mode.get()
    if mode is None:
        return default_allowed_dir, default_readonly, default_allowed_dir is not None

    ws = _workspace.get()
    if mode == "full":
        return None, False, False
    if mode == "readonly":
        return ws, True, True
    # workspace
    return ws, False, True
