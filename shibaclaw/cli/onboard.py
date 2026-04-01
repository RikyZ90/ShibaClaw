"""Onboarding and configuration management for the ShibaClaw CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
import typer
from shibaclaw import __logo__
from .utils import console
from .auth import _is_oauth_authenticated

def _merge_missing_defaults(existing: Any, defaults: Any) -> Any:
    """Recursively fill in missing values from defaults without overwriting user config."""
    if not isinstance(existing, dict) or not isinstance(defaults, dict):
        return existing

    merged = dict(existing)
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = value
        else:
            merged[key] = _merge_missing_defaults(merged[key], value)
    return merged


def _onboard_plugins(config_path: Path) -> None:
    """Inject default config for all discovered channels."""
    from shibaclaw.integrations.registry import discover_all

    all_channels = discover_all()
    if not all_channels:
        return

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    channels = data.setdefault("channels", {})
    for name, cls in all_channels.items():
        if name not in channels:
            channels[name] = cls.default_config()
        else:
            channels[name] = _merge_missing_defaults(channels[name], cls.default_config())

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def onboard_command(
    workspace: Optional[str] = None,
    config_override: Optional[str] = None,
    wizard: bool = False,
):
    """Initialize shibaclaw configuration and workspace."""
    from shibaclaw.config.loader import get_config_path, load_config, save_config, set_config_path
    from shibaclaw.config.schema import Config
    from shibaclaw.config.paths import get_workspace_path
    from shibaclaw.helpers.helpers import sync_workspace_templates

    if config_override:
        config_path = Path(config_override).expanduser().resolve()
        set_config_path(config_path)
        console.print(f"[dim]Using config: {config_path}[/dim]")
    else:
        config_path = get_config_path()

    def _apply_workspace_override(loaded: Config) -> Config:
        if workspace:
            loaded.agents.defaults.workspace = workspace
        return loaded

    # Create or update config
    if config_path.exists():
        config = _apply_workspace_override(load_config(config_path))
    else:
        config = _apply_workspace_override(Config())

    # Auto-trigger wizard if no API keys or OAuth are configured
    if not wizard:
        from shibaclaw.thinkers.registry import PROVIDERS
        has_api = False
        for spec in PROVIDERS:
            if spec.is_oauth:
                if _is_oauth_authenticated(spec):
                    has_api = True
                    break
            elif spec.is_local:
                p = getattr(config.providers, spec.name, None)
                if p and p.api_base:
                    has_api = True
                    break
            else:
                p = getattr(config.providers, spec.name, None)
                if p and p.api_key:
                    has_api = True
                    break
        if not has_api:
            wizard = True
            console.print("[dim]No API keys detected. Starting configuration wizard...[/dim]")

    if config_path.exists():
        save_config(config, config_path)
        if not wizard:
            console.print(f"[green]✓[/green] Config updated at {config_path}")
    else:
        if not wizard:
            save_config(config, config_path)
            console.print(f"[green]✓[/green] Created config at {config_path}")

    # Run interactive wizard if enabled
    if wizard:
        from shibaclaw.cli.onboard_wizard import run_onboard
        try:
            result = run_onboard(initial_config=config)
            if not result.should_save:
                console.print("[yellow]Configuration discarded. No changes were saved.[/yellow]")
                return
            config = result.config
            save_config(config, config_path)
            console.print(f"[green]✓[/green] Config saved at {config_path}")
        except Exception as e:
            console.print(f"[red]✗[/red] Error during configuration: {e}")
            raise typer.Exit(1)
    
    _onboard_plugins(config_path)

    # Create workspace
    workspace_path = get_workspace_path(config.workspace_path)
    if not workspace_path.exists():
        workspace_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace_path}")

    sync_workspace_templates(workspace_path)

    agent_cmd = 'shibaclaw agent -m "Hello!"'
    gateway_cmd = "shibaclaw gateway"
    if config:
        agent_cmd += f" --config {config_path}"
        gateway_cmd += f" --config {config_path}"

    console.print(f"\n{__logo__} shibaclaw is ready!")
    console.print("\nNext steps:")
    if wizard:
        console.print(f"  1. Chat: [cyan]{agent_cmd}[/cyan]")
        console.print(f"  2. Start gateway: [cyan]{gateway_cmd}[/cyan]")
        console.print(f"  3. WebUI: [cyan]shibaclaw web --port 3000[/cyan]")
    else:
        console.print(f"  1. Add your API key to [cyan]{config_path}[/cyan]")
        console.print(f"  2. Chat: [cyan]{agent_cmd}[/cyan]")
        console.print(f"  3. WebUI: [cyan]shibaclaw web --port 3000[/cyan]")
