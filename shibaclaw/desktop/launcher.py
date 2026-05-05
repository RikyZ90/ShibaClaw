"""Native Windows launcher for ShibaClaw using pywebview.

Starts the full :class:`~shibaclaw.desktop.runtime.DesktopRuntime`, opens an
embedded WebView window that is auto-authenticated, and wires the window close
button to hide-to-tray behaviour (ready for future pystray integration).

Entry point::

    python -m shibaclaw desktop      # via CLI command added in commands.py
    ShibaClaw.exe                    # frozen PyInstaller build
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Any

from loguru import logger

from shibaclaw.config.paths import get_assets_dir
from shibaclaw.desktop.controller import DesktopController
from shibaclaw.desktop.runtime import DesktopRuntime
from shibaclaw.desktop.tray import TrayIcon
from shibaclaw.helpers.system import get_os_type, is_running_as_exe

WINDOWS_APP_USER_MODEL_ID = "RikyZ90.ShibaClaw.Desktop"

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(
    port: int = 3000,
    host: str = "127.0.0.1",
    config_path: str | None = None,
    workspace: str | None = None,
    with_gateway: bool = True,
    close_policy: str | None = None,
    disable_auth: bool = False,
) -> None:
    """Bootstrap the runtime and open the native window.

    *close_policy* controls what happens when the user clicks the window's
    close button:

    * ``'hide'``  — hides the window (future tray will keep app alive).
    * ``'quit'``  — performs a full clean shutdown immediately.

    For local Windows source runs, WebUI auth is disabled by default unless
    ``SHIBACLAW_AUTH`` is already set or ``disable_auth`` is passed explicitly.
    """
    if get_os_type() != "windows":
        logger.warning(
            "Native launcher is intended for Windows; running anyway on {}", sys.platform
        )
    else:
        _set_windows_app_user_model_id()

    _configure_desktop_auth(disable_auth=disable_auth)

    try:
        import webview  # type: ignore[import]
    except ImportError:
        print(
            "[ShibaClaw] pywebview is not installed.\n"
            "Install it with:  pip install pywebview\n"
            "or (inside the project):  pip install -e '.[windows-native]'",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Boot the runtime
    # ------------------------------------------------------------------
    runtime = DesktopRuntime(
        config_path=config_path,
        workspace=workspace,
        port=port,
        host=host,
        with_gateway=with_gateway,
    )

    logger.info("Starting ShibaClaw desktop runtime…")
    runtime.start()

    if not runtime.wait_ready(timeout=20.0):
        logger.error("WebUI did not become ready in time — aborting")
        runtime.stop()
        sys.exit(1)

    logger.info("WebUI ready at {}", runtime.base_url)

    # ------------------------------------------------------------------
    # Create the webview window
    # ------------------------------------------------------------------
    window_config = _resolve_window_config(runtime, close_policy)

    window: Any = webview.create_window(
        title="ShibaClaw",
        url=runtime.authed_url,
        width=window_config["width"],
        height=window_config["height"],
        resizable=True,
        hidden=True,
        # Frameless title bar is disabled for now; keep native chrome so the
        # window can be moved and resized without extra JS drag handling.
        frameless=False,
        # Suppress the default text-selection context menu inside the WebView.
        easy_drag=False,
    )

    # ------------------------------------------------------------------
    # Controller: inject window callbacks
    # ------------------------------------------------------------------
    quit_event = threading.Event()
    force_exit_armed = threading.Event()
    shutdown_complete = threading.Event()
    initial_show_complete = threading.Event()

    def _arm_force_exit(timeout: float = 3.0) -> None:
        if force_exit_armed.is_set():
            return
        force_exit_armed.set()

        def _force_exit_if_needed() -> None:
            if shutdown_complete.wait(timeout=timeout):
                return
            logger.warning(
                "Desktop shutdown did not finish within {} seconds; forcing process exit",
                timeout,
            )
            os._exit(0)

        threading.Thread(
            target=_force_exit_if_needed,
            name="shibaclaw-force-exit",
            daemon=True,
        ).start()

    def _quit_callback() -> None:
        quit_event.set()
        _arm_force_exit()
        try:
            window.destroy()
        except Exception:
            logger.debug("window.destroy() failed during quit", exc_info=True)

    def _on_loaded(*_args: Any) -> None:
        if window_config["start_hidden"] or initial_show_complete.is_set():
            return
        initial_show_complete.set()
        _window_show(window)

    def _on_before_show(*_args: Any) -> None:
        if get_os_type() != "windows":
            return
        icon_path = _get_windows_icon_path()
        if icon_path:
            _apply_windows_window_icon(window, icon_path)

    controller = DesktopController(
        runtime=runtime,
        window_show=lambda: _window_show(window),
        window_hide=lambda: _window_hide(window),
        quit_callback=_quit_callback,
    )

    # ------------------------------------------------------------------
    # Start System Tray
    # ------------------------------------------------------------------
    tray = TrayIcon(controller)
    tray.start()

    # ------------------------------------------------------------------
    # Close-button policy
    # ------------------------------------------------------------------
    def _on_closing() -> bool:
        """Return False to intercept (cancel) close, True to allow it."""
        if quit_event.is_set():
            return True

        if window_config["close_policy"] == "hide":
            _window_hide(window)
            return False  # intercept (cancel) — do not destroy the window

        controller.quit_app()
        return False

    window.events.closing += _on_closing
    window.events.loaded += _on_loaded
    if get_os_type() == "windows":
        window.events.before_show += _on_before_show

    # ------------------------------------------------------------------
    # Start the webview event loop (blocks until quit_event or window.destroy)
    # ------------------------------------------------------------------
    logger.info("Opening ShibaClaw window")
    try:
        webview.start(
            debug=_desktop_debug_enabled(),
            icon=_get_icon_path(),
            # gui='edgechromium'  # optionally force Edge WebView2 on Windows
        )
    finally:
        try:
            tray.stop()
        finally:
            runtime.stop()
            shutdown_complete.set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _window_show(window: Any) -> None:
    try:
        window.show()
    except Exception as exc:
        logger.debug("window.show() failed: {}", exc)


def _window_hide(window: Any) -> None:
    try:
        window.hide()
    except Exception as exc:
        logger.debug("window.hide() failed: {}", exc)


def _desktop_debug_enabled() -> bool:
    """Return True only when desktop debug is explicitly enabled."""
    value = os.environ.get("SHIBACLAW_DESKTOP_DEBUG", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _resolve_window_config(runtime: DesktopRuntime, close_policy: str | None) -> dict[str, Any]:
    """Resolve window geometry and behavior from config with launcher overrides."""
    desktop_cfg = runtime.config.desktop if runtime.config is not None else None
    return {
        "width": desktop_cfg.window_width if desktop_cfg is not None else 820,
        "height": desktop_cfg.window_height if desktop_cfg is not None else 980,
        "start_hidden": desktop_cfg.start_hidden if desktop_cfg is not None else False,
        "close_policy": close_policy or runtime.close_policy,
    }


def _get_icon_path() -> str | None:
    """Return the absolute path to the application icon if found."""
    assets_dir = get_assets_dir()
    candidates = [
        assets_dir / "shibaclaw.ico",
        assets_dir / "shibaclaw_256.png",
        assets_dir / "shibaclaw_128.png",
        assets_dir / "shibaclaw_64.png",
        assets_dir / "shibaclaw_32.png",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _get_windows_icon_path() -> str | None:
    """Return the .ico asset used for the native Windows window icon."""
    icon_path = get_assets_dir() / "shibaclaw.ico"
    if icon_path.exists():
        return str(icon_path)
    return None


def _set_windows_app_user_model_id() -> None:
    """Set a stable Windows AppUserModelID for taskbar grouping and icon lookup."""
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            WINDOWS_APP_USER_MODEL_ID
        )
    except Exception as exc:
        logger.debug("Could not set Windows AppUserModelID: {}", exc)


def _apply_windows_window_icon(window: Any, icon_path: str) -> None:
    """Apply small and large icons to the native Windows window handle."""
    import ctypes

    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    SM_CXSMICON = 49
    SM_CYSMICON = 50

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    hwnd = _resolve_windows_window_handle(window)
    if not hwnd:
        logger.debug("Could not resolve a native window handle for the taskbar icon")
        return

    big_icon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
    small_icon = user32.LoadImageW(
        None,
        icon_path,
        IMAGE_ICON,
        user32.GetSystemMetrics(SM_CXSMICON),
        user32.GetSystemMetrics(SM_CYSMICON),
        LR_LOADFROMFILE,
    )

    if big_icon:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_icon)
    if small_icon:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_icon)


def _resolve_windows_window_handle(window: Any) -> int | None:
    """Best-effort extraction of the native HWND for a pywebview window."""
    native = getattr(window, "native", None)
    if native is not None:
        for attr_name in ("Handle", "handle"):
            handle = getattr(native, attr_name, None)
            if handle is None:
                continue
            try:
                to_int64 = getattr(handle, "ToInt64", None)
                if callable(to_int64):
                    value = to_int64()
                    return value if isinstance(value, int) else int(str(value))
                return int(handle)
            except (TypeError, ValueError):
                continue

    title = getattr(window, "title", None)
    if title:
        import ctypes

        hwnd = ctypes.windll.user32.FindWindowW(None, title)  # type: ignore[attr-defined]
        if hwnd:
            return int(hwnd)

    return None


def _configure_desktop_auth(*, disable_auth: bool = False) -> None:
    """Configure WebUI auth mode for desktop launches.

    Rules:

    * explicit environment wins;
    * ``disable_auth=True`` forces ``SHIBACLAW_AUTH=false``;
    * local Windows source runs default to auth disabled;
    * frozen/packaged builds keep auth enabled unless explicitly overridden.
    """
    if os.environ.get("SHIBACLAW_AUTH", "").strip():
        logger.debug("Desktop auth mode overridden via SHIBACLAW_AUTH={}", os.environ["SHIBACLAW_AUTH"])
        return

    if disable_auth:
        os.environ["SHIBACLAW_AUTH"] = "false"
        logger.info("Desktop auth disabled explicitly via launcher flag")
        return

    if get_os_type() == "windows" and not is_running_as_exe():
        os.environ["SHIBACLAW_AUTH"] = "false"
        logger.info("Desktop source mode on Windows: SHIBACLAW_AUTH=false")


# ---------------------------------------------------------------------------
# CLI shim: ``python -m shibaclaw desktop``
# (the actual typer command is registered in shibaclaw/cli/commands.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()
