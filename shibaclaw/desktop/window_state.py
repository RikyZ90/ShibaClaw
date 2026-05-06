"""Persistent window geometry helpers for the native desktop launcher."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from shibaclaw.config.paths import get_runtime_subdir
from shibaclaw.helpers.system import get_os_type

_WINDOW_STATE_VERSION = 1
_MIN_WINDOW_WIDTH = 320
_MIN_WINDOW_HEIGHT = 240
_MIN_VISIBLE_EDGE = 80


@dataclass(frozen=True, slots=True)
class WindowState:
    width: int
    height: int
    x: int | None = None
    y: int | None = None
    maximized: bool = False


def get_window_state_path() -> Path:
    """Return the per-instance desktop window state file path."""
    return get_runtime_subdir("desktop") / "window-state.json"


def load_window_state(default_width: int, default_height: int) -> WindowState:
    """Load persisted window state or return a sanitized default geometry."""
    fallback = sanitize_window_state(
        WindowState(width=default_width, height=default_height),
        default_width=default_width,
        default_height=default_height,
    )
    path = get_window_state_path()
    if not path.exists():
        return fallback

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read desktop window state from {}: {}", path, exc)
        return fallback

    version = payload.get("version")
    if version not in (None, _WINDOW_STATE_VERSION):
        logger.debug("Ignoring unsupported desktop window state version {} from {}", version, path)
        return fallback

    return sanitize_window_state(
        WindowState(
            width=payload.get("width", default_width),
            height=payload.get("height", default_height),
            x=payload.get("x"),
            y=payload.get("y"),
            maximized=_coerce_bool(payload.get("maximized", False)),
        ),
        default_width=default_width,
        default_height=default_height,
    )


def save_window_state(state: WindowState) -> None:
    """Persist window geometry atomically."""
    path = get_window_state_path()
    sanitized = sanitize_window_state(state)
    payload = {
        "version": _WINDOW_STATE_VERSION,
        "width": sanitized.width,
        "height": sanitized.height,
        "x": sanitized.x,
        "y": sanitized.y,
        "maximized": sanitized.maximized,
    }

    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(path)
    except OSError as exc:
        logger.warning("Could not persist desktop window state to {}: {}", path, exc)


def sanitize_window_state(
    state: WindowState,
    *,
    default_width: int | None = None,
    default_height: int | None = None,
) -> WindowState:
    """Normalize dimensions and keep the window at least partially visible."""
    width_fallback = default_width if default_width is not None else _MIN_WINDOW_WIDTH
    height_fallback = default_height if default_height is not None else _MIN_WINDOW_HEIGHT
    sanitized = WindowState(
        width=max(_MIN_WINDOW_WIDTH, _coerce_int(state.width, width_fallback)),
        height=max(_MIN_WINDOW_HEIGHT, _coerce_int(state.height, height_fallback)),
        x=_coerce_optional_int(state.x),
        y=_coerce_optional_int(state.y),
        maximized=_coerce_bool(state.maximized),
    )
    return _clamp_to_visible_area(sanitized)


def _coerce_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clamp_to_visible_area(state: WindowState) -> WindowState:
    bounds = _get_virtual_screen_bounds()
    if not bounds:
        return state

    left, top, screen_width, screen_height = bounds
    width = min(state.width, screen_width) if screen_width > 0 else state.width
    height = min(state.height, screen_height) if screen_height > 0 else state.height

    if state.x is None or state.y is None:
        return WindowState(width=width, height=height, x=None, y=None, maximized=state.maximized)

    max_x = left + screen_width - min(_MIN_VISIBLE_EDGE, width)
    max_y = top + screen_height - min(_MIN_VISIBLE_EDGE, height)
    x = min(max(state.x, left), max_x)
    y = min(max(state.y, top), max_y)

    return WindowState(width=width, height=height, x=x, y=y, maximized=state.maximized)


def _get_virtual_screen_bounds() -> tuple[int, int, int, int] | None:
    if get_os_type() != "windows":
        return None

    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        left = user32.GetSystemMetrics(76)
        top = user32.GetSystemMetrics(77)
        width = user32.GetSystemMetrics(78)
        height = user32.GetSystemMetrics(79)
    except Exception as exc:
        logger.debug("Could not determine virtual screen bounds: {}", exc)
        return None

    if width <= 0 or height <= 0:
        return None
    return int(left), int(top), int(width), int(height)