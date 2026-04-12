"""Onboarding and configuration management for the ShibaClaw CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table

from shibaclaw import __logo__, __version__
from shibaclaw.cli.auth import _is_oauth_authenticated

console = Console()

# ---------------------------------------------------------------------------
# Providers shown during onboarding, in display order.
# (name, display_label, env_key, default_model, is_local, is_oauth)
# ---------------------------------------------------------------------------

_ONBOARD_PROVIDERS = [
    ("openrouter", "OpenRouter",     "OPENROUTER_API_KEY",  "google/gemma-3-27b-it:free", False, False),
    ("anthropic",  "Anthropic",      "ANTHROPIC_API_KEY",   "claude-opus-4-5",                       False, False),
    ("openai",     "OpenAI",         "OPENAI_API_KEY",      "gpt-4o",                                False, False),
    ("gemini",     "Gemini",         "GEMINI_API_KEY",      "gemini/gemini-2.0-flash",               False, False),
    ("deepseek",   "DeepSeek",       "DEEPSEEK_API_KEY",    "deepseek/deepseek-chat",                False, False),
    ("groq",       "Groq",           "GROQ_API_KEY",        "groq/llama-3.3-70b-versatile",         False, False),
    ("ollama",     "Ollama (local)", "",                    "ollama/llama3.2",                       True,  False),
    ("github_copilot", "GitHub Copilot (OAuth)", "",        "oswe-vscode-prime",                 False, True),
]


def _rule(title: str = "") -> None:
    console.print(Rule(f"[bold]{title}[/bold]" if title else "", style="orange3"))


def _detect_env_keys() -> dict[str, str]:
    """Return {provider_name: api_key} for any provider whose env var is set."""
    found: dict[str, str] = {}
    for name, _, env_key, *_ in _ONBOARD_PROVIDERS:
        if env_key and os.environ.get(env_key):
            found[name] = os.environ[env_key]
    return found


def _detect_oauth() -> list[str]:
    """Return provider names already authenticated via OAuth."""
    from shibaclaw.thinkers.registry import PROVIDERS
    return [
        spec.name for spec in PROVIDERS
        if spec.is_oauth and _is_oauth_authenticated(spec)
    ]


def _is_already_configured(config, name: str) -> bool:
    """Return True if the provider already has a key or OAuth in config."""
    p = getattr(config.providers, name, None)
    if p and p.api_key:
        return True
    return False


def _pick_provider(config, env_found: dict[str, str], oauth_found: list[str]):
    """
    Ask the user to pick a provider.
    Returns (provider_name, env_key, default_model, is_local, is_oauth) or None.
    """
    _rule("Step 1 / 3  —  LLM Provider")

    choices = [
        entry for entry in _ONBOARD_PROVIDERS
        if entry[0] not in env_found
        and entry[0] not in oauth_found
        and not _is_already_configured(config, entry[0])
    ]

    if not choices:
        console.print("[green]v[/green] Provider already configured.")
        return None

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("N", style="bold gold1", width=3)
    table.add_column("Provider")
    for i, (_, label, env_key, _, is_local, is_oauth) in enumerate(choices, 1):
        if is_local:
            note = "[dim](no API key needed)[/dim]"
        elif is_oauth:
            note = "[dim](OAuth — run: shibaclaw provider login)[/dim]"
        elif env_key:
            note = f"[dim]env: {env_key}[/dim]"
        else:
            note = ""
        table.add_row(str(i), f"{label}  {note}")
    console.print(table)

    raw = Prompt.ask("\n  Pick a number", default="1")
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(choices)):
            raise ValueError
    except ValueError:
        console.print("[red]  Invalid choice -- skipping provider setup.[/red]")
        return None

    return choices[idx][0], choices[idx][2], choices[idx][3], choices[idx][4], choices[idx][5]


def _ask_api_key(env_key: str, current_key: str) -> str | None:
    """Prompt for an API key. Returns the new key or the existing one."""
    _rule("Step 2 / 3  --  API Key")

    if current_key:
        masked = "*" * (len(current_key) - 4) + current_key[-4:]
        console.print(f"  Current key: [dim]{masked}[/dim]")
        if not Confirm.ask("  Replace it?", default=False):
            return current_key

    hint = f" (paste from env var {env_key})" if env_key else ""
    key = Prompt.ask(f"  API Key{hint}", password=True, default="")
    return key.strip() if key.strip() else None


def _ask_model(provider_name: str, default_model: str, current_model: str) -> str:
    """Prompt for a model name with a smart default."""
    _rule("Step 3 / 3  --  Model")

    suggested = current_model if current_model else default_model
    console.print(f"  Provider: [bold]{provider_name}[/bold]")
    console.print("  Check the provider website for the full list of available models.")
    model = Prompt.ask("  Model", default=suggested)
    return model.strip() or suggested


def _ask_channel() -> tuple[str, dict[str, Any]] | None:
    """Offer an optional channel. Returns (name, partial_config) or None."""
    _rule("Optional  --  Chat Channel")

    from shibaclaw.integrations.registry import discover_all
    channels = {
        name: cls.display_name
        for name, cls in sorted(discover_all().items())
        if hasattr(cls, "display_name")
    }
    if not channels:
        return None

    console.print(
        "  Connect a channel to chat via Telegram, Discord, etc.\n"
        "  [dim]You can skip and use the CLI or WebUI instead.[/dim]\n"
    )

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("N", style="bold gold1", width=3)
    table.add_column("Channel")
    table.add_row("0", "[dim]Skip[/dim]")
    names = list(channels.keys())
    for i, (name, label) in enumerate(channels.items(), 1):
        table.add_row(str(i), label)
    console.print(table)

    raw = Prompt.ask("\n  Pick a number (0 to skip)", default="0")
    try:
        idx = int(raw)
        if idx == 0:
            return None
        if not (1 <= idx <= len(names)):
            raise ValueError
    except ValueError:
        console.print("[dim]  Invalid -- skipping channel setup.[/dim]")
        return None

    chosen = names[idx - 1]
    console.print(
        f"\n  [bold]{channels[chosen]}[/bold]  -- enter your credentials.\n"
        "  Leave blank to skip and edit config.json manually.\n"
    )

    try:
        import importlib
        from pydantic import BaseModel
        mod = importlib.import_module(f"shibaclaw.integrations.{chosen}")
        from shibaclaw.integrations.registry import discover_all as _da
        cls = _da()[chosen]
        cfg_cls_name = cls.__name__.replace("Channel", "Config")
        cfg_cls = getattr(mod, cfg_cls_name, None)
    except Exception:
        cfg_cls = None

    partial: dict[str, Any] = {"enabled": False}

    if cfg_cls and issubclass(cfg_cls, BaseModel):
        for fname, finfo in cfg_cls.model_fields.items():
            if fname == "enabled":
                continue
            desc = finfo.description or fname.replace("_", " ").title()
            is_secret = any(k in fname.lower() for k in ("token", "key", "secret", "password"))
            val = Prompt.ask(f"  {desc}", password=is_secret, default="")
            if val.strip():
                partial[fname] = val.strip()

    if len(partial) > 1:
        partial["enabled"] = Confirm.ask(f"  Enable {channels[chosen]} now?", default=True)

    return chosen, partial


def _show_summary(config_path: Path, provider: str, model: str) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold green]v Setup complete![/bold green]\n\n"
            f"Provider: [cyan]{provider}[/cyan]\n"
            f"Model:    [cyan]{model}[/cyan]\n"
            f"Config:   [dim]{config_path}[/dim]",
            title=f"{__logo__} Ready to hunt!",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print("\n[bold]Next steps:[/bold]")
    console.print('  Chat:     [cyan]shibaclaw agent -m "Hello!"[/cyan]')
    console.print("  WebUI:    [cyan]shibaclaw web[/cyan]")
    console.print("  Gateway:  [cyan]shibaclaw gateway[/cyan]")
    console.print("\n  [dim]You can also onboard via the WebUI at[/dim] [bold cyan]http://localhost:3000[/bold cyan]\n")


# ---------------------------------------------------------------------------
# Plugin helpers (unchanged from previous version)
# ---------------------------------------------------------------------------

def _merge_missing_defaults(existing: Any, defaults: Any) -> Any:
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
    """Inject default config for all discovered channels (never overwrites user values)."""
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


# ---------------------------------------------------------------------------
# Gateway restart helper
# ---------------------------------------------------------------------------

def _try_restart_gateway(config) -> None:
    """If the gateway is running, POST /restart to reload config."""
    import urllib.request
    import urllib.error

    host = config.gateway.host or "127.0.0.1"
    port = config.gateway.port or 19999

    # Check if gateway is up
    try:
        req = urllib.request.Request(f"http://{host}:{port}/", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status != 200:
                return
    except Exception:
        return  # gateway not running

    # Send restart
    try:
        from shibaclaw.webui.server import get_auth_token
        token = get_auth_token()
        req = urllib.request.Request(f"http://{host}:{port}/restart", method="POST")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=5):
            pass
        console.print("[green]✓[/green] Gateway restart triggered — new config will be loaded.")
    except Exception:
        console.print("[dim]  Tip: restart the gateway to apply changes.[/dim]")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def onboard_command(
    workspace: Optional[str] = None,
    config_override: Optional[str] = None,
):
    """Initialize shibaclaw configuration and workspace."""
    from shibaclaw.config.loader import get_config_path, load_config, save_config, set_config_path
    from shibaclaw.config.paths import get_workspace_path
    from shibaclaw.config.schema import Config
    from shibaclaw.helpers.helpers import sync_workspace_templates

    if config_override:
        config_path = Path(config_override).expanduser().resolve()
        set_config_path(config_path)
    else:
        config_path = get_config_path()

    is_fresh = not config_path.exists()
    config = load_config(config_path) if not is_fresh else Config()

    if workspace:
        config.agents.defaults.workspace = workspace

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold gold1]{__logo__} shibaclaw v{__version__}[/bold gold1]\n"
            "[dim]Let's get you set up in a few steps.[/dim]",
            border_style="orange3",
            padding=(1, 2),
        )
    )

    # ENV scan: auto-populate keys found in environment
    env_found = _detect_env_keys()
    oauth_found = _detect_oauth()

    for name, key in env_found.items():
        label = next((p[1] for p in _ONBOARD_PROVIDERS if p[0] == name), name)
        masked = "*" * max(0, len(key) - 4) + key[-4:] if len(key) > 4 else "****"
        console.print(f"[green]v[/green] Detected [bold]{label}[/bold] key from environment ({masked})")
        p = getattr(config.providers, name, None)
        if p is not None and not p.api_key:
            p.api_key = key

    for name in oauth_found:
        label = next((p[1] for p in _ONBOARD_PROVIDERS if p[0] == name), name)
        console.print(f"[green]v[/green] [bold]{label}[/bold] already authenticated (OAuth)")

    # --- Provider selection (always shown) ---
    chosen_provider = config.agents.defaults.provider or "auto"
    chosen_model = config.agents.defaults.model

    # Show current config if already set
    has_any_provider = bool(env_found) or bool(oauth_found) or any(
        _is_already_configured(config, p[0]) for p in _ONBOARD_PROVIDERS
    )

    if has_any_provider and chosen_model:
        _rule("Step 1 / 3  —  LLM Provider")
        console.print(f"  Current provider: [bold cyan]{chosen_provider}[/bold cyan]")
        console.print(f"  Current model:    [bold cyan]{chosen_model}[/bold cyan]")
        change = Confirm.ask("\n  Change provider/model?", default=False)
        if change:
            has_any_provider = False  # force full selection

    if not has_any_provider or not chosen_model:
        result = _pick_provider(config, env_found, oauth_found)
        if result:
            pname, env_key, default_model, is_local, is_oauth = result

            if is_oauth:
                console.print(
                    f"\n  [yellow]Run [bold]shibaclaw provider login {pname.replace('_', '-')}[/bold]"
                    " to complete OAuth authentication.[/yellow]"
                )
            elif not is_local:
                current_key = getattr(getattr(config.providers, pname, None), "api_key", "") or ""
                new_key = _ask_api_key(env_key, current_key)
                if new_key:
                    p = getattr(config.providers, pname, None)
                    if p is not None:
                        p.api_key = new_key

            chosen_model = _ask_model(pname, default_model, config.agents.defaults.model)
            config.agents.defaults.model = chosen_model
            config.agents.defaults.provider = pname
            chosen_provider = pname
        elif not chosen_model:
            # No provider selected and no model — pick a default from env
            default_model = next(
                (p[3] for p in _ONBOARD_PROVIDERS
                 if p[0] in env_found or p[0] in oauth_found or _is_already_configured(config, p[0])),
                "google/gemma-3-27b-it:free",
            )
            _rule("Step 3 / 3  —  Model")
            chosen_model = _ask_model(chosen_provider, default_model, "")
            config.agents.defaults.model = chosen_model

    # Optional channel
    console.print()
    channel_result = _ask_channel()
    if channel_result:
        ch_name, ch_cfg = channel_result
        extras = dict(config.channels.model_extra or {})
        merged = _merge_missing_defaults(extras.get(ch_name, {}), ch_cfg)
        merged.update({k: v for k, v in ch_cfg.items() if v})
        extras[ch_name] = merged
        # Pydantic model_extra is read-only on frozen models; patch via __dict__
        object.__setattr__(config.channels, "__pydantic_extra__", extras)

    # Save
    save_config(config, config_path)
    console.print(f"\n[green]v[/green] Config saved at [dim]{config_path}[/dim]")

    # Inject plugin channel defaults (never clobbers user values)
    _onboard_plugins(config_path)

    # Workspace + template sync (asks before overwriting personalised files)
    console.print()
    workspace_path = get_workspace_path(config.workspace_path)
    if not workspace_path.exists():
        workspace_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]v[/green] Workspace created at [dim]{workspace_path}[/dim]")

    sync_workspace_templates(workspace_path, silent=False)

    _show_summary(config_path, chosen_provider, chosen_model)

    # Try to restart the gateway if it's running (applies new config)
    _try_restart_gateway(config)
