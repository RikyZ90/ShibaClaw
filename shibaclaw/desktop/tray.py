"""Tray icon management for ShibaClaw."""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING

try:
    import pystray
    from PIL import Image
    HAS_TRAY_DEPS = True
except ImportError:
    HAS_TRAY_DEPS = False
    pystray = None  # type: ignore
    Image = None  # type: ignore

from loguru import logger

from shibaclaw.config.paths import get_assets_dir

if TYPE_CHECKING:
    from shibaclaw.desktop.controller import DesktopController


class TrayIcon:
    """Manages the system tray icon and its menu."""

    def __init__(self, controller: DesktopController) -> None:
        self._controller = controller
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu structure."""
        menu_items = [
            pystray.MenuItem("Open ShibaClaw", self._on_open, default=True),
            pystray.MenuItem("Workspace Folder", self._on_open_workspace),
            pystray.MenuItem("Open Logs", self._on_open_logs),
            pystray.Menu.SEPARATOR,
        ]

        if sys.platform == "win32":
            menu_items.extend([
                pystray.MenuItem(
                    "Run on Startup",
                    self._on_toggle_autostart,
                    checked=lambda item: self._is_autostart_enabled()
                ),
                pystray.Menu.SEPARATOR,
            ])

        menu_items.extend([
            pystray.MenuItem("GitHub", self._on_open_website),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        ])

        return pystray.Menu(*menu_items)

    def _load_icon_image(self) -> Image.Image:
        """Load the icon image from assets."""
        assets_dir = get_assets_dir()
        icon_candidates = [
            assets_dir / "shibaclaw_32.png",
            assets_dir / "shibaclaw_16.png",
        ]

        for icon_path in icon_candidates:
            if icon_path.exists():
                try:
                    return Image.open(icon_path)
                except Exception:
                    continue

        logger.warning("Nessuna icona PNG trovata negli assets, uso fallback generico")
        return Image.new("RGB", (32, 32), (255, 165, 0))  # Orange square fallback

    def _on_open(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._controller.window_show()

    def _on_open_workspace(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._controller.open_workspace()

    def _on_open_logs(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._controller.open_logs()

    def _on_open_website(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._controller.open_website()

    def _is_autostart_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "ShibaClaw")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _on_toggle_autostart(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if sys.platform != "win32":
            return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            if self._is_autostart_enabled():
                winreg.DeleteValue(key, "ShibaClaw")
                logger.info("Autostart disabled")
            else:
                exe_path = sys.executable
                if getattr(sys, 'frozen', False):
                    cmd = f'"{exe_path}"'
                else:
                    cmd = f'"{exe_path}" -m shibaclaw'
                winreg.SetValueEx(key, "ShibaClaw", 0, winreg.REG_SZ, cmd)
                logger.info(f"Autostart enabled: {cmd}")
            winreg.CloseKey(key)
            if self._icon:
                self._icon.update_menu()
        except Exception as e:
            logger.error(f"Failed to toggle autostart: {e}")

    def _on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Chiusura richiesta tramite menu tray")
        self._controller.quit()
        if self._icon:
            self._icon.stop()

    def _run_icon(self) -> None:
        """Run the icon loop."""
        try:
            image = self._load_icon_image()
            self._icon = pystray.Icon(
                "shibaclaw",
                image,
                "ShibaClaw",
                menu=self._create_menu()
            )
            self._icon.run()
        except Exception as e:
            logger.exception(f"Errore fatale nel thread della Tray Icon: {e}")

    def start(self) -> None:
        """Start the tray icon in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_icon, daemon=True, name="TrayIconThread")
        self._thread.start()
        logger.info("Process started")

    def notify(self, title: str, message: str) -> None:
        """Send a native OS toast/balloon notification via the tray icon."""
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title=title)
        except Exception as e:
            logger.debug("Tray notify failed: {}", e)

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon:
            try:
                self._icon.remove_notification()
            except Exception:
                pass
            self._icon.stop()
            self._icon = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Stopped")
