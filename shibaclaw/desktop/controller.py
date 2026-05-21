"""Desktop controller — in-process action surface for the native launcher.

All actions that the future system-tray menu (or any native UI) needs to
trigger are collected here.  Calling these methods directly avoids the
overhead of round-tripping through the HTTP API for operations that live in
the same process.

Usage::

    from shibaclaw.desktop.controller import DesktopController
    ctrl = DesktopController(runtime)
    ctrl.open_in_browser()
    ctrl.restart_service()
"""

from __future__ import annotations

import threading
import time
import webbrowser
from typing import TYPE_CHECKING, Callable

from loguru import logger

from shibaclaw.config.paths import get_app_root, get_logs_dir, get_workspace_path
from shibaclaw.desktop.runtime import DesktopRuntime

if TYPE_CHECKING:
    from shibaclaw.desktop.tray import TrayIcon


class DesktopController:
    """Exposes high-level actions over a running :class:`DesktopRuntime`.

    The *window_show* and *window_hide* callables are injected by the
    launcher so this class stays decoupled from any specific GUI toolkit.
    """

    _NATIVE_NOTIFY_COOLDOWN = 10.0

    def __init__(
        self,
        runtime: DesktopRuntime,
        window_show: Callable[[], None] | None = None,
        window_hide: Callable[[], None] | None = None,
        quit_callback: Callable[[], None] | None = None,
    ) -> None:
        self._runtime = runtime
        self._window_show = window_show
        self._window_hide = window_hide
        self._quit_callback = quit_callback
        self._quitting = False
        self._tray: TrayIcon | None = None
        self._window_visible = True
        self._last_native_notify = 0.0

    # ------------------------------------------------------------------
    # Compatibility Aliases (for code using snake_case)
    # ------------------------------------------------------------------

    def window_show(self) -> None:
        self.show_window()

    def window_hide(self) -> None:
        self.hide_window()

    def quit(self) -> None:
        self.quit_app()

    def open_website(self) -> None:
        """Open the official website in the browser."""
        webbrowser.open("https://github.com/RikyZ90/ShibaClaw")

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def show_window(self) -> None:
        """Bring the embedded window to the foreground."""
        self._window_visible = True
        if self._window_show:
            self._window_show()

    def hide_window(self) -> None:
        """Hide the embedded window (minimise to tray)."""
        self._window_visible = False
        if self._window_hide:
            self._window_hide()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def open_in_browser(self) -> None:
        """Open the WebUI in the system default browser."""
        url = self._runtime.authed_url
        logger.debug("Opening browser: {}", url)
        webbrowser.open(url)

    def open_workspace(self) -> None:
        """Open the agent workspace folder in the system file manager."""
        workspace = (
            self._runtime.config.workspace_path
            if self._runtime.config
            else get_workspace_path()
        )
        _open_path(workspace)

    def open_logs(self) -> None:
        """Open the logs folder in the system file manager."""
        _open_path(get_logs_dir())

    def open_data_dir(self) -> None:
        """Open the ~/.shibaclaw data directory in the system file manager."""
        _open_path(get_app_root())

    # ------------------------------------------------------------------
    # Service management
    # ------------------------------------------------------------------

    def restart_service(self) -> None:
        """Restart the WebUI server in a background thread (non-blocking)."""
        def _do_restart() -> None:
            logger.info("Restarting WebUI service…")
            ok = self._runtime.restart_server()
            if ok:
                logger.info("WebUI service restarted successfully")
            else:
                logger.warning("WebUI service did not come back in time after restart")

        threading.Thread(target=_do_restart, name="shibaclaw-restart", daemon=True).start()

    # ------------------------------------------------------------------
    # Application lifecycle
    # ------------------------------------------------------------------

    def quit_app(self) -> None:
        """Perform a clean shutdown: stop server, gateway, then exit."""
        if self._quitting:
            return
        self._quitting = True

        def _do_quit() -> None:
            logger.info("Desktop quit requested — shutting down…")
            if self._quit_callback:
                self._quit_callback()
            self._runtime.stop()

        threading.Thread(target=_do_quit, name="shibaclaw-quit", daemon=True).start()

    # ------------------------------------------------------------------
    # Native OS notifications
    # ------------------------------------------------------------------

    def set_tray(self, tray: TrayIcon) -> None:
        self._tray = tray

    @property
    def window_visible(self) -> bool:
        return self._window_visible

    @window_visible.setter
    def window_visible(self, value: bool) -> None:
        self._window_visible = value

    def send_native_notification(self, title: str, message: str) -> None:
        """Send a native Windows toast notification if the window is not visible."""
        if self._window_visible:
            return
        if not self._tray:
            return
        now = time.monotonic()
        if now - self._last_native_notify < self._NATIVE_NOTIFY_COOLDOWN:
            return
        self._last_native_notify = now
        self._tray.notify(title, message)


# ------------------------------------------------------------------
# Internal utility
# ------------------------------------------------------------------

def _open_path(path) -> None:
    """Open *path* in the platform file manager, best-effort."""
    import os
    from pathlib import Path

    from shibaclaw.helpers.system import get_os_type

    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    target_str = str(target)
    os_type = get_os_type()
    try:
        if os_type == "windows":
            os.startfile(target_str)  # type: ignore[attr-defined]
        elif os_type == "darwin":
            import subprocess
            subprocess.Popen(["open", target_str])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", target_str])
    except Exception as exc:
        logger.debug("Could not open path {}: {}", target_str, exc)
