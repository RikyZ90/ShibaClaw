"""CLI entry point for ShibaClaw."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer

from shibaclaw import __logo__, __version__
from shibaclaw.helpers.logging import setup_shiba_logging

from .base import _load_runtime_config, _make_provider
from .utils import safe_print

app = typer.Typer(
    name="shibaclaw",
    context_settings={"help_option_names": ["-h", "--help"]},
    help=f"{__logo__} shibaclaw - Personal AI Assistant",
    no_args_is_help=True,
)


def version_callback(value: bool):
    if value:
        safe_print(f"{__logo__} shibaclaw v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
):
    """shibaclaw - Personal AI Assistant."""
    pass


@app.command()
def reset_password(
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Specific username to reset"),
):
    """Reset the admin user password."""
    import getpass
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()
    if not cm.is_setup():
        safe_print("[yellow]No admin user configured yet. Run the WebUI setup first.[/yellow]")
        return

    admin_user = username or cm.get_admin_username()
    if not admin_user:
         safe_print("[red]Could not determine admin username.[/red]")
         return

    safe_print(f"Resetting password for user: [cyan]{admin_user}[/cyan]")
    new_pwd = getpass.getpass("New Password: ")
    confirm_pwd = getpass.getpass("Confirm Password: ")

    if new_pwd != confirm_pwd:
        safe_print("[red]Passwords do not match.[/red]")
        return

    if len(new_pwd) < 6:
        safe_print("[red]Password must be at least 6 characters.[/red]")
        return

    # We cheat the old_password requirement by directly rewriting the hash
    data = cm._load_all()
    from hashlib import scrypt
    import secrets
    salt = secrets.token_hex(16)
    hashed = scrypt(
        new_pwd.encode(), salt=salt.encode(), n=16384, r=8, p=1,
    ).hex()
    data["admin_user"]["password_hash"] = hashed
    data["admin_user"]["salt"] = salt
    data["admin_user"]["username"] = admin_user
    cm._save_all(data)

    safe_print("[green]Password reset successful.[/green]")


@app.command()
def onboard(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Initialize shibaclaw configuration and workspace."""
    from .onboard import onboard_command

    onboard_command(workspace=workspace, config_override=config)


@app.command()
def gateway(
    host: Optional[str] = typer.Option(
        None, "--host", "-H", help="Gateway host (default: 127.0.0.1 or from config)"
    ),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Gateway port"),
    ws_port: Optional[int] = typer.Option(None, "--ws-port", help="Gateway WebSocket port"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Start the shibaclaw gateway."""
    from .gateway import gateway_command

    asyncio.run(
        gateway_command(
            host=host,
            port_override=port,
            ws_port_override=ws_port,
            workspace=workspace,
            verbose=verbose,
            config_path=config,
        )
    )


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="WebUI host"),
    port: int = typer.Option(3000, "--port", "-p", help="WebUI port"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
    with_gateway: bool = typer.Option(
        False, "--with-gateway", "-g", help="Start the gateway in the background automatically"
    ),
):
    """Start the ShibaClaw WebUI in the browser."""
    import os
    import socket
    import subprocess
    import sys
    import time

    from shibaclaw.helpers.system import find_free_tcp_port, is_tcp_port_available
    from shibaclaw.webui.server import run_server

    from .base import _load_runtime_config

    setup_shiba_logging()
    cfg = _load_runtime_config(config, workspace)
    provider = _make_provider(cfg, exit_on_error=False)

    gateway_proc = None
    gateway_host = "127.0.0.1"
    gateway_port = cfg.gateway.port
    gateway_ws_port = cfg.gateway.ws_port
    if with_gateway:
        if not is_tcp_port_available(gateway_host, gateway_port) or not is_tcp_port_available(
            gateway_host, gateway_ws_port
        ):
            fallback_http = find_free_tcp_port(gateway_host)
            fallback_ws = find_free_tcp_port(gateway_host, exclude={fallback_http})
            safe_print(
                "[yellow]Gateway ports busy; using fallback ports "
                f"{fallback_http}/{fallback_ws} instead of {gateway_port}/{gateway_ws_port}.[/yellow]"
            )
            gateway_port = fallback_http
            gateway_ws_port = fallback_ws
            cfg.gateway.port = gateway_port
            cfg.gateway.ws_port = gateway_ws_port

        os.environ["SHIBACLAW_GATEWAY_HOST"] = gateway_host
        os.environ["SHIBACLAW_WEBUI_URL"] = f"http://127.0.0.1:{port}"
        cfg.gateway.host = gateway_host
        safe_print("[cyan]➤ Starting Gateway process background...[/cyan]")
        safe_print("[dim]  (Optimized memory: ~128MB UI + ~512MB Gateway)[/dim]")
        if getattr(sys, "frozen", False):
            # Frozen .exe (PyInstaller): -m flag is not available
            gw_cmd = [
                sys.executable,
                "gateway",
                "--host",
                gateway_host,
                "--port",
                str(gateway_port),
                "--ws-port",
                str(gateway_ws_port),
            ]
        else:
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
        if workspace:
            gw_cmd.extend(["--workspace", workspace])
        if config:
            gw_cmd.extend(["--config", config])

        gw_extra_kwargs: dict = {}
        if sys.platform == "win32":
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            gw_extra_kwargs["creationflags"] = create_no_window

        gateway_proc = subprocess.Popen(gw_cmd, env=os.environ.copy(), **gw_extra_kwargs)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if gateway_proc.poll() is not None:
                raise typer.Exit(code=1)
            try:
                with socket.create_connection((gateway_host, gateway_port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)

    safe_print(f"{__logo__} [bold gold1]ShibaClaw WebUI[/bold gold1]")
    safe_print(f"  [cyan]➤ http://{host}:{port}[/cyan]")
    if provider is None:
        safe_print("")
        safe_print(
            "  [dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]"
        )

    def stop_gateway_proc():
        nonlocal gateway_proc
        if gateway_proc:
            safe_print("[yellow]➤ Terminating Gateway process...[/yellow]")
            try:
                gateway_proc.terminate()
                gateway_proc.wait(timeout=5)
            except Exception:
                try:
                    gateway_proc.kill()
                except Exception:
                    pass
            gateway_proc = None

    def restart_gateway_proc(pre_start_hook=None):
        """Stop and relaunch the managed gateway subprocess.

        Used as the restart callback for plugin install/uninstall so that
        only the gateway is recycled — the WebUI server stays alive.
        """
        nonlocal gateway_proc
        if gateway_proc:
            try:
                gateway_proc.terminate()
                gateway_proc.wait(timeout=5)
            except Exception:
                try:
                    gateway_proc.kill()
                except Exception:
                    pass
            gateway_proc = None

        if pre_start_hook:
            try:
                pre_start_hook()
            except Exception as e:
                logger.error("pre_start_hook failed: {}", e)

        if with_gateway:
            gw_restart_kwargs: dict = {}
            if sys.platform == "win32":
                _cnw = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                gw_restart_kwargs["creationflags"] = _cnw
            gateway_proc = subprocess.Popen(gw_cmd, env=os.environ.copy(), **gw_restart_kwargs)

    from shibaclaw.webui.routers.system import set_restart_callback, set_shutdown_callback

    set_shutdown_callback(stop_gateway_proc)
    if with_gateway:
        set_restart_callback(restart_gateway_proc)

    try:
        asyncio.run(run_server(port=port, host=host, config=cfg, provider=provider))
    finally:
        stop_gateway_proc()


@app.command()
def desktop(
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="WebUI host"),
    port: int = typer.Option(3000, "--port", "-p", help="WebUI port"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
    with_gateway: bool = typer.Option(
        True, "--with-gateway/--no-gateway", "-g", help="Start the gateway automatically"
    ),
    close_policy: Optional[str] = typer.Option(
        None,
        "--close-policy",
        help="Override the configured close behavior: 'hide' or 'quit'",
    ),
    no_auth: bool = typer.Option(
        False,
        "--no-auth",
        help="Disable WebUI auth for this desktop launch. On local Windows source runs auth is already disabled by default unless SHIBACLAW_AUTH is set.",
    ),
):
    """Start ShibaClaw in a native desktop window (Windows)."""
    from shibaclaw.desktop.launcher import run as launcher_run

    setup_shiba_logging()
    launcher_run(
        port=port,
        host=host,
        config_path=config,
        workspace=workspace,
        with_gateway=with_gateway,
        close_policy=close_policy,
        disable_auth=no_auth,
    )


@app.command()
def agent(
    message: Optional[str] = typer.Argument(None, help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to config file"),
    markdown: bool = typer.Option(
        True, "--markdown/--no-markdown", help="Render output as Markdown"
    ),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show runtime logs"),
):
    """Interact with the agent directly."""
    from .agent import agent_command

    cfg = _load_runtime_config(config, workspace)
    agent_command(
        message=message, session_id=session_id, config_obj=cfg, markdown=markdown, logs=logs
    )


@app.command()
def status():
    """Show shibaclaw status."""
    from shibaclaw.config.loader import get_config_path, load_config
    from shibaclaw.thinkers.registry import PROVIDERS

    from .auth import _oauth_provider_status

    cfg_path, cfg = get_config_path(), load_config()
    safe_print(f"{__logo__} [bold]shibaclaw Status[/bold]\n")
    safe_print(f"Config: {cfg_path} {'[green]✓[/green]' if cfg_path.exists() else '[red]✗[/red]'}")
    safe_print(
        f"Workspace: {cfg.workspace_path} {'[green]✓[/green]' if cfg.workspace_path.exists() else '[red]✗[/red]'}"
    )
    if cfg_path.exists():
        safe_print(f"Model: [bold cyan]{cfg.agents.defaults.model}[/bold cyan]")
        for spec in PROVIDERS:
            p = getattr(cfg.providers, spec.name, None)
            if p:
                if spec.is_oauth:
                    status_text = _oauth_provider_status(spec)
                elif spec.is_local:
                    status_text = (
                        f"[green]✓ {p.api_base}[/green]" if p.api_base else "[dim]not set[/dim]"
                    )
                else:
                    # ProviderConfig no longer has a plain api_key field;
                    # resolve from vault (also falls back to env vars via
                    # _provider_has_credentials in the caller chain).
                    status_text = (
                        "[green]✓[/green]"
                        if p.resolve_api_key(spec.name)
                        else "[dim]not set[/dim]"
                    )
                safe_print(f"{spec.label}: {status_text}")


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from shibaclaw.config.loader import load_config
    from shibaclaw.integrations.registry import discover_all, discover_channel_names

    cfg = load_config()
    discovered = discover_all()
    all_module_names = set(discover_channel_names())
    from rich.table import Table

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    shown: set[str] = set()
    for name, cls in sorted(discovered.items()):
        shown.add(name)
        enabled = False
        section = getattr(cfg.channels, name, None)
        if isinstance(section, dict):
            enabled = section.get("enabled", False)
        elif section:
            enabled = getattr(section, "enabled", False)
        table.add_row(cls.display_name, "[green]✓[/green]" if enabled else "[dim]✗[/dim]")
    for name in sorted(all_module_names - shown):
        section = getattr(cfg.channels, name, None)
        enabled = False
        if isinstance(section, dict):
            enabled = section.get("enabled", False)
        elif section:
            enabled = getattr(section, "enabled", False)
        label = name.capitalize()
        status = "[yellow]! missing dep[/yellow]" if enabled else "[dim]✗ missing dep[/dim]"
        table.add_row(label, status)
    safe_print(table)


provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


@provider_app.command("login")
def provider_login_cmd(provider: str = typer.Argument(..., help="OAuth provider")):
    """Authenticate with an OAuth provider."""
    from .auth import provider_login

    provider_login(provider)


if __name__ == "__main__":
    app()
