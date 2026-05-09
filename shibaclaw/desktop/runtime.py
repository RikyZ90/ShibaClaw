"""Desktop runtime orchestrator for ShibaClaw.

Provides a single :class:`DesktopRuntime` that boots and tears down the
full stack (config, provider, gateway subprocess, WebUI server) for use by
the native Windows launcher and future tray integration.

The CLI ``web`` command continues to use its own subprocess management so
this module has *no* side-effects at import time.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Any

from loguru import logger

from shibaclaw.config.schema import Config
from shibaclaw.helpers.system import find_free_tcp_port, get_os_type, is_tcp_port_available


class DesktopRuntime:
    """Orchestrates config, provider, gateway subprocess, and WebUI server.

    Typical lifecycle::

        rt = DesktopRuntime()
        rt.start(port=3000)
        rt.wait_ready()
        # ... use rt.base_url, rt.auth_token ...
        rt.stop()
    """

    def __init__(
        self,
        config_path: str | None = None,
        workspace: str | None = None,
        port: int = 3000,
        host: str = "127.0.0.1",
        with_gateway: bool = True,
    ) -> None:
        self._config_path = config_path
        self._workspace = workspace
        self._port = port
        self._host = host
        self._with_gateway = with_gateway

        self.config: Config | None = None
        self.provider: Any | None = None

        self._gateway_proc: subprocess.Popen | None = None
        self._server_mgr: Any | None = None  # ServerManager, imported lazily
        self._gateway_monitor: threading.Thread | None = None
        self._stopping = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bootstrap config, provider, gateway, and WebUI server."""
        self._load_config()
        self._ensure_shared_auth_token()
        self._start_gateway()
        self._start_server()

    def wait_ready(self, timeout: float = 20.0) -> bool:
        """Block until the WebUI HTTP port is reachable (or timeout)."""
        if self._server_mgr is None:
            return False
        return self._server_mgr.wait_ready(timeout=timeout)

    def stop(self) -> None:
        """Shut down the WebUI server and gateway subprocess cleanly."""
        self._stopping = True
        self._stop_server()
        self._stop_gateway()

    def restart_server(self) -> bool:
        """Stop then restart the WebUI server in place (no new process).

        Returns True when the server is reachable again after the restart.
        """
        self._stop_server()
        self._start_server()
        return self.wait_ready(timeout=15.0)

    def _restart_gateway(self) -> None:
        """Stop then restart the gateway subprocess in place."""
        logger.info("Restarting gateway subprocess…")
        self._stop_gateway()
        self._start_gateway()
        logger.info("Gateway subprocess restarted")

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def auth_token(self) -> str | None:
        from shibaclaw.webui.auth import get_auth_token

        return get_auth_token()

    @property
    def authed_url(self) -> str:
        """Return a URL with the auth token pre-embedded as a query param.

        The WebUI front-end reads ``?token=`` on first load and saves it to
        localStorage so subsequent requests are authenticated automatically.
        """
        token = self.auth_token
        if token:
            return f"{self.base_url}/?token={token}"
        return self.base_url

    @property
    def gateway_running(self) -> bool:
        return (
            self._gateway_proc is not None
            and self._gateway_proc.poll() is None
        )

    @property
    def server_running(self) -> bool:
        return self._server_mgr is not None and self._server_mgr.is_running

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        from shibaclaw.cli.base import _load_runtime_config, _make_provider

        self.config = _load_runtime_config(self._config_path, self._workspace)
        self.provider = _make_provider(self.config, exit_on_error=False)

    def _ensure_shared_auth_token(self) -> None:
        """Create one token in the parent process and share it with subprocesses."""
        from shibaclaw.webui.auth import get_auth_token

        token = get_auth_token()
        if token:
            os.environ["SHIBACLAW_AUTH_TOKEN"] = token

    @property
    def close_policy(self) -> str:
        """Return the close-button policy from config, defaulting to 'hide'."""
        if self.config is not None:
            return self.config.desktop.close_behavior
        return "hide"

    def _start_gateway(self) -> None:
        if not self._with_gateway or self.config is None:
            return

        gateway_host = "127.0.0.1"
        gateway_port, gateway_ws_port = self._resolve_gateway_ports(gateway_host)

        os.environ["SHIBACLAW_GATEWAY_HOST"] = gateway_host
        os.environ["SHIBACLAW_WEBUI_URL"] = f"http://127.0.0.1:{self._port}"
        self.config.gateway.host = gateway_host
        self.config.gateway.port = gateway_port
        self.config.gateway.ws_port = gateway_ws_port

        gw_cmd = [
            sys.executable,
            "-m",
            "shibaclaw",
            "gateway",
            "--host",
            gateway_host,
            "--port",
            str(gateway_port),
            "--ws-port",
            str(gateway_ws_port),
        ]
        if self._workspace:
            gw_cmd.extend(["--workspace", self._workspace])
        if self._config_path:
            gw_cmd.extend(["--config", self._config_path])

        extra_kwargs: dict = {}
        if get_os_type() == "windows":
            extra_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        gateway_env = os.environ.copy()
        gateway_env["SHIBACLAW_SILENT"] = "true"
        gateway_env["PYTHONIOENCODING"] = "utf-8"

        logger.debug("Starting gateway subprocess: {}", gw_cmd)
        self._gateway_proc = subprocess.Popen(gw_cmd, env=gateway_env, **extra_kwargs)

        # Wait up to 45s for the actual ShibaClaw health endpoint to answer (increased for first-run setup)
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            if self._gateway_proc.poll() is not None:
                logger.error("Gateway process exited early")
                self._gateway_proc = None
                raise RuntimeError(
                    f"Managed gateway failed to start on {gateway_host}:{gateway_port}. "
                    "Check for a conflicting local service on the configured gateway ports."
                )
            if self._is_gateway_ready(gateway_host, gateway_port):
                logger.debug(
                    "Gateway is ready on HTTP {} and WS {}",
                    gateway_port,
                    gateway_ws_port,
                )
                self._start_gateway_monitor()
                return
            time.sleep(0.1)

        self._stop_gateway()
        raise RuntimeError(
            f"Managed gateway did not become healthy on {gateway_host}:{gateway_port}. "
            "Another local service may be occupying the configured ports."
        )

    def _resolve_gateway_ports(self, gateway_host: str) -> tuple[int, int]:
        assert self.config is not None

        configured_http = self.config.gateway.port
        configured_ws = self.config.gateway.ws_port
        if is_tcp_port_available(gateway_host, configured_http) and is_tcp_port_available(
            gateway_host, configured_ws
        ):
            return configured_http, configured_ws

        fallback_http = find_free_tcp_port(gateway_host)
        fallback_ws = find_free_tcp_port(gateway_host, exclude={fallback_http})
        logger.warning(
            "Gateway ports {} / {} are unavailable on {}. Using fallback ports {} / {}.",
            configured_http,
            configured_ws,
            gateway_host,
            fallback_http,
            fallback_ws,
        )
        return fallback_http, fallback_ws

    def _is_gateway_ready(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.5) as conn:
                conn.sendall(b"GET /health HTTP/1.0\r\nHost: gw\r\n\r\n")
                payload = conn.recv(2048)
        except OSError:
            return False

        marker = b"\r\n\r\n"
        if marker not in payload:
            return False
        try:
            body = json.loads(payload.split(marker, 1)[1].decode("utf-8", errors="ignore"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
        return body.get("status") in ("ok", "idle")

    def _start_server(self) -> None:
        from shibaclaw.webui.server import ServerManager
        from shibaclaw.webui.routers.system import set_restart_callback

        self._server_mgr = ServerManager(
            port=self._port,
            host=self._host,
            config=self.config,
            provider=self.provider,
        )
        self._server_mgr.start()
        set_restart_callback(self._restart_gateway)

    def _stop_server(self) -> None:
        if self._server_mgr is not None:
            self._server_mgr.stop()
            self._server_mgr = None

    def _stop_gateway(self) -> None:
        if self._gateway_proc is None:
            return
        proc = self._gateway_proc
        self._gateway_proc = None
        logger.debug("Terminating gateway subprocess (pid={})", proc.pid)
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Gateway did not exit; killing")
                proc.kill()
        except OSError:
            pass

    def _start_gateway_monitor(self) -> None:
        """Start a daemon thread that watches the gateway subprocess.

        If the gateway exits with code 0 (restart requested via WebUI) and we
        are not in a full shutdown, automatically relaunch it.
        """
        def _monitor() -> None:
            proc = self._gateway_proc
            if proc is None:
                return
            proc.wait()
            if self._stopping:
                return
            exit_code = proc.returncode
            logger.info("Gateway subprocess exited with code {}", exit_code)
            if exit_code == 0:
                logger.info("Gateway requested restart; relaunching…")
                try:
                    self._start_gateway()
                except Exception as exc:
                    logger.error("Failed to relaunch gateway: {}", exc)

        t = threading.Thread(target=_monitor, name="shibaclaw-gw-monitor", daemon=True)
        t.start()
        self._gateway_monitor = t
