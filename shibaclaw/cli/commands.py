"""CLI entry point for ShibaClaw."""

from __future__ import annotations

import asyncio
import typer
from pathlib import Path
from typing import Optional
from rich.table import Table

from shibaclaw import __logo__, __version__
from .utils import console, setup_shiba_logging
from .base import _load_runtime_config, _make_provider

app = typer.Typer(
    name="shibaclaw",
    context_settings={"help_option_names": ["-h", "--help"]},
    help=f"{__logo__} shibaclaw - Personal AI Assistant",
    no_args_is_help=True,
)


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} shibaclaw v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
):
    """shibaclaw - Personal AI Assistant."""
    pass


@app.command()
def print_token():
    """Print the WebUI authentication token."""
    from shibaclaw.webui.server import get_auth_token
    token = get_auth_token()
    if token:
        console.print(f"[green]🔑 Token: {token}[/green]")
    else:
        console.print("[yellow]No token found or authentication disabled.[/yellow]")


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
    host: Optional[str] = typer.Option(None, "--host", "-H", help="Gateway host (default: 127.0.0.1 or from config)"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Gateway port"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Start the shibaclaw gateway."""
    from .gateway import gateway_command
    asyncio.run(gateway_command(host=host, port_override=port, workspace=workspace, verbose=verbose, config_path=config))


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="WebUI host"),
    port: int = typer.Option(3000, "--port", "-p", help="WebUI port"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Start the ShibaClaw WebUI in the browser."""
    from .base import _load_runtime_config, _make_provider
    from shibaclaw.webui.server import run_server, get_auth_token

    setup_shiba_logging()
    cfg = _load_runtime_config(config, workspace)
    provider = _make_provider(cfg, exit_on_error=False)

    token = get_auth_token()
    console.print(f"{__logo__} [bold gold1]ShibaClaw WebUI[/bold gold1]")
    console.print(f"  [cyan]➜ http://{host}:{port}[/cyan]")
    if token:
        console.print(f"  [green]🔑 Token:[/green] [bold]{token[:4] + '*' * (len(token)-4)}[/bold]")
    if provider is None:
        console.print("")
        console.print("  [dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]")

    asyncio.run(run_server(port=port, host=host, config=cfg, provider=provider))


@app.command()
def agent(
    message: Optional[str] = typer.Argument(None, help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show runtime logs"),
):
    """Interact with the agent directly."""
    from .agent import agent_command
    cfg = _load_runtime_config(config, workspace)
    agent_command(message=message, session_id=session_id, config_obj=cfg, markdown=markdown, logs=logs)


@app.command()
def status():
    """Show shibaclaw status."""
    from shibaclaw.config.loader import get_config_path, load_config
    from .auth import _oauth_provider_status
    from shibaclaw.thinkers.registry import PROVIDERS

    cfg_path, cfg = get_config_path(), load_config()
    console.print(f"{__logo__} [bold]shibaclaw Status[/bold]\n")
    console.print(f"Config: {cfg_path} {'[green]✓[/green]' if cfg_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {cfg.workspace_path} {'[green]✓[/green]' if cfg.workspace_path.exists() else '[red]✗[/red]'}")

    if cfg_path.exists():
        console.print(f"Model: [bold cyan]{cfg.agents.defaults.model}[/bold cyan]")
        for spec in PROVIDERS:
            p = getattr(cfg.providers, spec.name, None)
            if p:
                if spec.is_oauth:
                    status_text = _oauth_provider_status(spec)
                elif spec.is_local:
                    status_text = f"[green]✓ {p.api_base}[/green]" if p.api_base else "[dim]not set[/dim]"
                else:
                    status_text = "[green]✓[/green]" if p.api_key else "[dim]not set[/dim]"
                console.print(f"{spec.label}: {status_text}")


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from shibaclaw.integrations.registry import discover_all
    from shibaclaw.config.loader import load_config
    cfg = load_config()
    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    for name, cls in sorted(discover_all().items()):
        enabled = False
        section = getattr(cfg.channels, name, None)
        if isinstance(section, dict):
            enabled = section.get("enabled", False)
        elif section:
            enabled = getattr(section, "enabled", False)
        table.add_row(cls.display_name, "[green]✓[/green]" if enabled else "[dim]✗[/dim]")
    console.print(table)


provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


@provider_app.command("login")
def provider_login_cmd(provider: str = typer.Argument(..., help="OAuth provider")):
    """Authenticate with an OAuth provider."""
    from .auth import provider_login
    provider_login(provider)


if __name__ == "__main__":
    app()