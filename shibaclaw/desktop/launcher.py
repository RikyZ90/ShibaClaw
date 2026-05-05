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
from pathlib import Path
from typing import Any

from loguru import logger

from shibaclaw.config.paths import get_assets_dir
from shibaclaw.desktop.controller import DesktopController
from shibaclaw.desktop.runtime import DesktopRuntime
from shibaclaw.desktop.tray import TrayIcon
from shibaclaw.helpers.system import get_os_type, is_running_as_exe

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
        hidden=window_config["hidden"],
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

    def _quit_callback() -> None:
        quit_event.set()
        try:
            window.destroy()
        except Exception:
            pass

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
        if window_config["close_policy"] == "hide":
            _window_hide(window)
            return False  # intercept (cancel) — do not destroy the window
        else:
            controller.quit_app()
            return True  # allow webview to destroy the window naturally

    window.events.closing += _on_closing

    # ------------------------------------------------------------------
    # Start the webview event loop (blocks until quit_event or window.destroy)
    # ------------------------------------------------------------------
    logger.info("Opening ShibaClaw window")
    try:
        webview.start(
            debug=_is_debug_mode(),
            icon=_get_icon_path(),
            # gui='edgechromium'  # optionally force Edge WebView2 on Windows
        )
    finally:
        # Assicuriamoci che la tray icon venga fermata quando l'app chiude
        tray.stop()

    # ------------------------------------------------------------------
    # Cleanup after the window loop exits
    # ------------------------------------------------------------------
    if not quit_event.is_set():
        # Window was destroyed without going through the controller (e.g.
        # Alt-F4 with close_policy='quit').
        runtime.stop()


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


def _is_debug_mode() -> bool:
    """Return True when running from source (not a frozen .exe build)."""
    return not is_running_as_exe()


def _resolve_window_config(runtime: DesktopRuntime, close_policy: str | None) -> dict[str, Any]:
    """Resolve window geometry and behavior from config with launcher overrides."""
    desktop_cfg = runtime.config.desktop if runtime.config is not None else None
    return {
        "width": desktop_cfg.window_width if desktop_cfg is not None else 960,
        "height": desktop_cfg.window_height if desktop_cfg is not None else 1050,
        "hidden": desktop_cfg.start_hidden if desktop_cfg is not None else False,
        "close_policy": close_policy or runtime.close_policy,
    }


def _get_icon_path() -> str | None:
    """Return the absolute path to the application icon if found."""
    assets_dir = get_assets_dir()
    candidates = [
        assets_dir / "shibaclaw.ico",
        assets_dir / "shibaclaw_32.png",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
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
