"""Common base functions for ShibaClaw CLI commands."""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Optional
import typer
from .utils import console
from shibaclaw.config.schema import Config

def _load_runtime_config(config: Optional[str] = None, workspace: Optional[str] = None) -> Config:
    """Load config and optionally override the active workspace."""
    from shibaclaw.config.loader import load_config, set_config_path

    config_path = None
    if config:
        config_path = Path(config).expanduser().resolve()
        if not config_path.exists():
            console.print(f"[red]Error: Config file not found: {config_path}[/red]")
            raise typer.Exit(1)
        set_config_path(config_path)
        console.print(f"[dim]Using config: {config_path}[/dim]")

    loaded = load_config(config_path)
    if workspace:
        loaded.agents.defaults.workspace = workspace
    return loaded


def _make_provider(config: Config, exit_on_error: bool = True):
    """Create the appropriate Thinker from config."""
    from shibaclaw.thinkers.azure_openai_provider import AzureOpenAIThinker
    from shibaclaw.thinkers.base import GenerationSettings
    from shibaclaw.thinkers.openai_codex_provider import OpenAICodexThinker
    from shibaclaw.thinkers.registry import find_by_name, PROVIDERS
    from .auth import _is_oauth_authenticated

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        provider = OpenAICodexThinker(default_model=model)
    elif provider_name == "custom":
        from shibaclaw.thinkers.custom_provider import CustomThinker
        provider = CustomThinker(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
            extra_headers=p.extra_headers if p else None,
        )
    elif provider_name == "azure_openai":
        provider = AzureOpenAIThinker(
            api_key=p.api_key, api_base=p.api_base, default_model=model
        )
    elif provider_name == "github_copilot" or model.startswith("github_copilot/"):
        from shibaclaw.thinkers.github_copilot_provider import GithubCopilotThinker
        provider = GithubCopilotThinker(default_model=model)
    else:
        spec = find_by_name(provider_name) if provider_name else None
        has_env_key = bool(spec and spec.env_key and os.environ.get(spec.env_key))
        current_ready = (
            model.startswith("bedrock/")
            or (p and p.api_key)
            or has_env_key
            or (spec and (spec.is_oauth or spec.is_local))
        )
        if current_ready and spec and spec.is_oauth:
            current_ready = _is_oauth_authenticated(spec)

        if not current_ready:
            any_ready = False
            for s in PROVIDERS:
                if s.is_oauth:
                    if _is_oauth_authenticated(s): any_ready = True; break
                elif s.is_local:
                    lp = getattr(config.providers, s.name, None)
                    if lp and lp.api_base: any_ready = True; break
                else:
                    lp = getattr(config.providers, s.name, None)
                    if (lp and lp.api_key) or (s.env_key and os.environ.get(s.env_key)): any_ready = True; break

            if not any_ready:
                if exit_on_error:
                    console.print("\n🐾 [bold]Please run: shibaclaw onboard[/bold]")
                    sys.exit(0)
                return None
            else:
                console.print(f"[yellow]🐾 Current model [bold]{model}[/bold] is not configured.[/yellow]")
                if exit_on_error: sys.exit(0)
                return None
                
        if spec and spec.name == "anthropic":
            from shibaclaw.thinkers.anthropic_provider import AnthropicThinker
            provider = AnthropicThinker(
                api_key=p.api_key if p else None,
                api_base=config.get_api_base(model),
                default_model=model,
                extra_headers=p.extra_headers if p else None,
            )
        else:
            from shibaclaw.thinkers.openai_provider import OpenAIThinker
            provider = OpenAIThinker(
                api_key=p.api_key if p else None,
                api_base=config.get_api_base(model),
                default_model=model,
                extra_headers=p.extra_headers if p else None,
                provider_name=provider_name,
            )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    return provider
