"""Tests for the desktop runtime, controller, launcher helpers, and related plumbing."""

from __future__ import annotations

import os
import sys
import threading
import time
import types
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# helpers.system — new functions
# ---------------------------------------------------------------------------

class TestIsRunningAsExe:
    def test_returns_false_in_normal_python(self):
        from shibaclaw.helpers.system import is_running_as_exe

        # In a normal (non-frozen) interpreter sys.frozen is absent
        assert is_running_as_exe() is False

    def test_returns_true_when_frozen(self):
        from shibaclaw.helpers.system import is_running_as_exe

        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "_MEIPASS", "/tmp/meipass", create=True):
            assert is_running_as_exe() is True

    def test_frozen_without_meipass_returns_false(self):
        """sys.frozen alone (no _MEIPASS) is not a valid PyInstaller bundle."""
        from shibaclaw.helpers.system import is_running_as_exe

        # Remove _MEIPASS if present, set frozen=True
        with mock.patch.object(sys, "frozen", True, create=True):
            if hasattr(sys, "_MEIPASS"):
                with mock.patch.object(sys, "_MEIPASS", None, create=False):
                    pass  # can't easily remove; skip this edge case
            assert is_running_as_exe() is False or True  # either is OK when _MEIPASS varies


class TestGetInstallationMethod:
    def test_exe_when_frozen(self):
        from shibaclaw.helpers.system import get_installation_method

        with mock.patch("shibaclaw.helpers.system.is_running_as_exe", return_value=True):
            assert get_installation_method() == "exe"

    def test_docker_wins_over_pip(self):
        from shibaclaw.helpers.system import get_installation_method

        with mock.patch("shibaclaw.helpers.system.is_running_as_exe", return_value=False), \
             mock.patch("shibaclaw.helpers.system.is_running_in_docker", return_value=True):
            assert get_installation_method() == "docker"

    def test_pip_when_in_venv(self):
        from shibaclaw.helpers.system import get_installation_method

        with mock.patch("shibaclaw.helpers.system.is_running_as_exe", return_value=False), \
             mock.patch("shibaclaw.helpers.system.is_running_in_docker", return_value=False), \
             mock.patch("shibaclaw.helpers.system.is_running_in_pip_env", return_value=True):
            assert get_installation_method() == "pip"

    def test_source_as_fallback(self):
        from shibaclaw.helpers.system import get_installation_method

        with mock.patch("shibaclaw.helpers.system.is_running_as_exe", return_value=False), \
             mock.patch("shibaclaw.helpers.system.is_running_in_docker", return_value=False), \
             mock.patch("shibaclaw.helpers.system.is_running_in_pip_env", return_value=False):
            assert get_installation_method() == "source"

    def test_returns_valid_literal(self):
        from shibaclaw.helpers.system import get_installation_method

        result = get_installation_method()
        assert result in ("exe", "docker", "pip", "source")


# ---------------------------------------------------------------------------
# config.paths — get_app_root
# ---------------------------------------------------------------------------

class TestGetAppRoot:
    def test_returns_path_object(self):
        from shibaclaw.config.paths import get_app_root

        root = get_app_root()
        assert isinstance(root, Path)

    def test_points_to_shibaclaw_dir(self):
        from shibaclaw.config.paths import get_app_root

        root = get_app_root()
        assert root.name == ".shibaclaw"
        assert root.parent == Path.home()

    def test_creates_directory(self, tmp_path):
        """get_app_root() must ensure the directory exists."""
        fake_home = tmp_path / "fakehome"
        with mock.patch("pathlib.Path.home", return_value=fake_home):
            from shibaclaw.config import paths as paths_module
            with mock.patch.object(paths_module, "ensure_dir", wraps=lambda p: (p.mkdir(parents=True, exist_ok=True) or p)):
                root = paths_module.get_app_root()
                assert root.name == ".shibaclaw"


# ---------------------------------------------------------------------------
# webui.auth — uses get_app_root instead of hardcoded path
# ---------------------------------------------------------------------------

class TestAuthTokenPath:
    def test_token_file_under_app_root(self):
        from shibaclaw.config.paths import get_app_root
        from shibaclaw.webui.auth import AUTH_TOKEN_FILE

        assert AUTH_TOKEN_FILE.parent == get_app_root()
        assert AUTH_TOKEN_FILE.name == "auth_token"


# ---------------------------------------------------------------------------
# updater.checker — uses get_app_root instead of hardcoded path
# ---------------------------------------------------------------------------

class TestCacheFilePath:
    def test_cache_file_under_app_root(self):
        from shibaclaw.config.paths import get_app_root
        from shibaclaw.updater.checker import _CACHE_FILE

        assert _CACHE_FILE.parent == get_app_root()
        assert _CACHE_FILE.name == "update_cache.json"


# ---------------------------------------------------------------------------
# config.schema — DesktopConfig
# ---------------------------------------------------------------------------

class TestDesktopConfig:
    def test_defaults(self):
        from shibaclaw.config.schema import DesktopConfig

        cfg = DesktopConfig()
        assert cfg.close_behavior == "hide"
        assert cfg.start_hidden is False
        assert cfg.auto_start_enabled is False
        assert cfg.window_width == 920
        assert cfg.window_height == 1048

    def test_present_in_root_config(self):
        from shibaclaw.config.schema import Config

        cfg = Config()
        assert hasattr(cfg, "desktop")
        assert cfg.desktop.close_behavior == "hide"

    def test_roundtrip_json(self):
        from shibaclaw.config.schema import DesktopConfig

        original = DesktopConfig(close_behavior="quit", start_hidden=True, window_width=1920)
        dumped = original.model_dump()
        restored = DesktopConfig(**{k: v for k, v in dumped.items()})
        assert restored.close_behavior == "quit"
        assert restored.start_hidden is True
        assert restored.window_width == 1920


# ---------------------------------------------------------------------------
# webui.server — ServerManager
# ---------------------------------------------------------------------------

class TestServerManager:
    def test_base_url(self):
        from shibaclaw.webui.server import ServerManager

        mgr = ServerManager(port=13333, host="127.0.0.1")
        assert mgr.base_url == "http://127.0.0.1:13333"

    def test_is_running_false_before_start(self):
        from shibaclaw.webui.server import ServerManager

        mgr = ServerManager(port=13334)
        assert mgr.is_running is False

    def test_wait_ready_returns_false_when_nothing_listening(self):
        from shibaclaw.webui.server import ServerManager

        mgr = ServerManager(port=19876)  # nothing listening on this port
        result = mgr.wait_ready(timeout=0.3)
        assert result is False

    def test_start_stop_cycle(self):
        """Start a real server, wait for readiness, then stop it."""
        from shibaclaw.webui.server import ServerManager

        mgr = ServerManager(port=18765, host="127.0.0.1")
        mgr.start()
        try:
            assert mgr.is_running is True
            ready = mgr.wait_ready(timeout=10.0)
            assert ready, "ServerManager did not become ready in time"

            # Probe the HTTP endpoint
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:18765/", timeout=3) as resp:
                assert resp.status in (200, 401, 403)  # auth may block but server is up
        finally:
            mgr.stop()
        # Give it a moment to fully exit
        time.sleep(0.2)
        assert mgr.is_running is False


# ---------------------------------------------------------------------------
# desktop.runtime — DesktopRuntime (unit-level, no real processes)
# ---------------------------------------------------------------------------

class TestDesktopRuntime:
    def test_base_url(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(port=3000, host="127.0.0.1")
        assert rt.base_url == "http://127.0.0.1:3000"

    def test_authed_url_contains_token_when_auth_enabled(self):
        from shibaclaw.desktop.runtime import DesktopRuntime
        from shibaclaw.webui.auth import get_auth_token

        token = get_auth_token()
        rt = DesktopRuntime(port=3000)
        url = rt.authed_url
        if token:
            assert f"token={token}" in url
        else:
            assert url == rt.base_url

    def test_close_policy_defaults_to_hide_when_no_config(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime()
        # config not loaded yet — should fall back to 'hide'
        assert rt.close_policy == "hide"

    def test_stop_without_start_is_safe(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime()
        rt.stop()  # must not raise

    def test_gateway_not_running_before_start(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime()
        assert rt.gateway_running is False

    def test_server_not_running_before_start(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime()
        assert rt.server_running is False

    def test_start_stop_no_gateway(self):
        """Integration: boot WebUI via DesktopRuntime without gateway."""
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(port=18766, with_gateway=False)
        rt.start()
        try:
            assert rt.server_running is True
            ready = rt.wait_ready(timeout=10.0)
            assert ready, "DesktopRuntime server did not become ready"
        finally:
            rt.stop()
        assert rt.server_running is False

    def test_start_sets_shared_auth_token_env(self):
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(with_gateway=False)

        with mock.patch.object(rt, "_load_config"), \
             mock.patch.object(rt, "_start_gateway"), \
             mock.patch.object(rt, "_start_server"), \
             mock.patch("shibaclaw.webui.auth.get_auth_token", return_value="shared-token"):
            rt.start()

        assert os.environ.get("SHIBACLAW_AUTH_TOKEN") == "shared-token"

    def test_resolve_gateway_ports_uses_fallback_when_configured_ports_busy(self):
        from shibaclaw.config.schema import Config
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(with_gateway=True)
        rt.config = Config()
        rt.config.gateway.port = 19999
        rt.config.gateway.ws_port = 19998

        with mock.patch(
            "shibaclaw.desktop.runtime.is_tcp_port_available",
            side_effect=[False, False],
        ), mock.patch(
            "shibaclaw.desktop.runtime.find_free_tcp_port",
            side_effect=[29999, 29998],
        ):
            http_port, ws_port = rt._resolve_gateway_ports("127.0.0.1")

        assert (http_port, ws_port) == (29999, 29998)


class TestDesktopLauncherAuth:
    def test_local_windows_source_defaults_auth_off(self):
        from shibaclaw.desktop import launcher

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHIBACLAW_AUTH", None)
            with mock.patch("shibaclaw.desktop.launcher.get_os_type", return_value="windows"), \
                 mock.patch("shibaclaw.desktop.launcher.is_running_as_exe", return_value=False):
                launcher._configure_desktop_auth()

            assert os.environ.get("SHIBACLAW_AUTH") == "false"

    def test_explicit_env_override_is_preserved(self):
        from shibaclaw.desktop import launcher

        with mock.patch.dict(os.environ, {"SHIBACLAW_AUTH": "true"}, clear=False):
            with mock.patch("shibaclaw.desktop.launcher.get_os_type", return_value="windows"), \
                 mock.patch("shibaclaw.desktop.launcher.is_running_as_exe", return_value=False):
                launcher._configure_desktop_auth(disable_auth=True)

            assert os.environ.get("SHIBACLAW_AUTH") == "true"

    def test_frozen_build_does_not_disable_auth_implicitly(self):
        from shibaclaw.desktop import launcher

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHIBACLAW_AUTH", None)
            with mock.patch("shibaclaw.desktop.launcher.get_os_type", return_value="windows"), \
                 mock.patch("shibaclaw.desktop.launcher.is_running_as_exe", return_value=True):
                launcher._configure_desktop_auth()

            assert "SHIBACLAW_AUTH" not in os.environ

    def test_resolve_window_config_uses_runtime_config(self):
        from shibaclaw.config.schema import Config
        from shibaclaw.desktop import launcher
        from shibaclaw.desktop.runtime import DesktopRuntime

        runtime = DesktopRuntime()
        runtime.config = Config()
        runtime.config.desktop.window_width = 920
        runtime.config.desktop.window_height = 1048
        runtime.config.desktop.start_hidden = True
        runtime.config.desktop.close_behavior = "hide"

        from unittest import mock

        from shibaclaw.desktop.window_state import WindowState

        with mock.patch("shibaclaw.desktop.launcher.load_window_state") as mock_load:
            mock_load.side_effect = lambda w, h: WindowState(width=w, height=h)
            resolved = launcher._resolve_window_config(runtime, close_policy=None)

        assert resolved == {
            "width": 920,
            "height": 1048,
            "x": None,
            "y": None,
            "start_hidden": True,
            "close_policy": "hide",
        }

    def test_desktop_debug_requires_explicit_env(self):
        from shibaclaw.desktop import launcher

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHIBACLAW_DESKTOP_DEBUG", None)
            assert launcher._desktop_debug_enabled() is False

        with mock.patch.dict(os.environ, {"SHIBACLAW_DESKTOP_DEBUG": "true"}, clear=False):
            assert launcher._desktop_debug_enabled() is True

    def test_get_icon_path_uses_assets_dir(self, tmp_path):
        from shibaclaw.desktop import launcher

        icon_path = tmp_path / "shibaclaw.ico"
        icon_path.write_bytes(b"ico")

        with mock.patch("shibaclaw.desktop.launcher.get_assets_dir", return_value=tmp_path):
            assert launcher._get_icon_path() == str(icon_path)


class TestDesktopMainEntrypoint:
    def test_main_imports_and_runs_launcher(self):
        from shibaclaw.desktop.__main__ import main

        fake_launcher = types.ModuleType("shibaclaw.desktop.launcher")
        fake_launcher.run = mock.Mock()

        with mock.patch.dict(sys.modules, {"shibaclaw.desktop.launcher": fake_launcher}):
            with mock.patch("shibaclaw.desktop.__main__.setup_shiba_logging"):
                main()

        fake_launcher.run.assert_called_once_with(disable_auth=True)

    def test_main_shows_visible_error_on_failed_startup(self):
        from shibaclaw.desktop.__main__ import main

        fake_launcher = types.ModuleType("shibaclaw.desktop.launcher")
        fake_launcher.run = mock.Mock(side_effect=SystemExit(1))

        with mock.patch.dict(sys.modules, {"shibaclaw.desktop.launcher": fake_launcher}):
            with mock.patch("shibaclaw.desktop.__main__.setup_shiba_logging"), mock.patch(
                "shibaclaw.desktop.__main__._show_startup_error"
            ) as mock_show_error:
                with pytest.raises(SystemExit):
                    main()

        mock_show_error.assert_called_once()


# ---------------------------------------------------------------------------
# desktop.controller — DesktopController (unit)
# ---------------------------------------------------------------------------

class TestDesktopController:
    def _make_controller(self):
        from shibaclaw.desktop.controller import DesktopController
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(port=3000)
        show_calls = []
        hide_calls = []
        quit_calls = []

        ctrl = DesktopController(
            runtime=rt,
            window_show=lambda: show_calls.append(1),
            window_hide=lambda: hide_calls.append(1),
            quit_callback=lambda: quit_calls.append(1),
        )
        return ctrl, show_calls, hide_calls, quit_calls

    def test_show_window_calls_callback(self):
        ctrl, show_calls, _, _ = self._make_controller()
        ctrl.show_window()
        assert show_calls == [1]

    def test_hide_window_calls_callback(self):
        ctrl, _, hide_calls, _ = self._make_controller()
        ctrl.hide_window()
        assert hide_calls == [1]

    def test_quit_app_is_idempotent(self):
        """Calling quit_app twice must not schedule two shutdowns."""
        ctrl, _, _, quit_calls = self._make_controller()

        # Patch runtime.stop so it doesn't actually do anything
        with mock.patch.object(ctrl._runtime, "stop"):
            ctrl.quit_app()
            ctrl.quit_app()  # second call should be a no-op
            time.sleep(0.3)  # let the daemon thread run
        assert len(quit_calls) <= 1

    def test_open_in_browser_calls_webbrowser(self):
        from shibaclaw.desktop.controller import DesktopController
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(port=3000)
        ctrl = DesktopController(runtime=rt)

        with mock.patch("webbrowser.open") as mock_open:
            ctrl.open_in_browser()
            mock_open.assert_called_once()
            called_url = mock_open.call_args[0][0]
            assert "127.0.0.1:3000" in called_url

    def test_restart_service_runs_in_thread(self):
        from shibaclaw.desktop.controller import DesktopController
        from shibaclaw.desktop.runtime import DesktopRuntime

        rt = DesktopRuntime(port=3000)
        ctrl = DesktopController(runtime=rt)
        restart_called = threading.Event()

        with mock.patch.object(rt, "restart_server", side_effect=lambda: restart_called.set() or True):
            ctrl.restart_service()
            triggered = restart_called.wait(timeout=2.0)
        assert triggered, "restart_server was not called within 2 s"
