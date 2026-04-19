"""Authentication and OAuth provider management for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import os
from typing import Callable, Dict

import httpx
import typer

from shibaclaw import __logo__

from .utils import console


def _is_oauth_authenticated(spec) -> bool:
    """Return True if the OAuth provider is already authenticated."""
    home = os.path.expanduser("~")

    if spec.name == "openai_codex":
        codex_path = os.path.join(home, ".config", "shibaclaw", "openai_codex", "credentials.json")
        if os.path.exists(codex_path):
            return True
        try:
            from oauth_cli_kit import get_token

            token = get_token()
            return bool(token and getattr(token, "access", None))
        except Exception:
            return False

    if spec.name == "github_copilot":
        token_paths = [
            os.path.join(home, ".shibaclaw", "github_copilot", "access-token"),
            os.path.join(home, ".config", "shibaclaw", "github_copilot", "access-token"),
            os.path.join(home, ".config", "github-copilot", "hosts.json"),
        ]
        if os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_COPILOT_TOKEN"):
            return True
        return any(os.path.exists(tp) for tp in token_paths)

    return False


def _oauth_provider_status(spec) -> str:
    """Return status string for OAuth providers."""
    if spec.name == "openai_codex":
        try:
            from oauth_cli_kit import get_token

            token = get_token()
            if token and getattr(token, "access", None):
                return "[green]✓ (OAuth authenticated)[/green]"
            return "[dim]not authenticated[/dim]"
        except ImportError:
            return "[dim]oauth-cli-kit missing ([magenta]pip install oauth-cli-kit[/magenta])[/dim]"
        except Exception:
            return "[dim]not authenticated[/dim]"

    if spec.name == "github_copilot":
        try:
            from shibaclaw.thinkers.github_copilot_provider import GithubCopilotThinker

            async def _test():
                thinker = GithubCopilotThinker()
                await thinker.chat([{"role": "user", "content": "hi"}], max_tokens=1)

            asyncio.run(_test())
            return "[green]✓ (OAuth authenticated)[/green]"
        except ImportError:
            return "[dim]missing dependencies[/dim]"
        except Exception:
            return "[dim]not authenticated[/dim]"

    return "[dim]not configured[/dim]"


_LOGIN_HANDLERS: Dict[str, Callable] = {}


def register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn

    return decorator


def provider_login(provider: str):
    """Authenticate with an OAuth provider."""
    from shibaclaw.thinkers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(f"{__logo__} OAuth Login - {spec.label}\n")
    handler()


@register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive

        token = None
        try:
            token = get_token()
        except Exception:
            pass

        if not (token and token.access):
            console.print("[cyan]Starting interactive OAuth login...[/cyan]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(
            f"[green]✓ Authenticated with OpenAI Codex[/green]  [dim]{token.account_id}[/dim]"
        )
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@register_login("github_copilot")
def _login_github_copilot() -> None:
    console.print("[cyan]Starting GitHub Copilot device flow...[/cyan]\n")

    github_client_id = "Iv1.b507a08c87ecfe98"
    github_device_code_url = "https://github.com/login/device/code"
    github_access_token_url = "https://github.com/login/oauth/access_token"

    async def _run_flow():
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                github_device_code_url,
                headers={"Accept": "application/json"},
                json={"client_id": github_client_id, "scope": "read:user"},
                timeout=10,
            )
            resp_json = resp.json()

        user_code = resp_json.get("user_code", "")
        verification_uri = resp_json.get("verification_uri", "https://github.com/login/device")
        device_code = resp_json.get("device_code", "")
        interval = resp_json.get("interval", 5)
        expires_in = resp_json.get("expires_in", 900)

        if not device_code or not user_code:
            console.print("[red]❌ GitHub did not return a device code[/red]")
            raise typer.Exit(1)

        console.print(f"1. Go to: [bold blue]{verification_uri}[/bold blue]")
        console.print(f"2. Enter code: [bold yellow]{user_code}[/bold yellow]")
        console.print("\n[dim]Waiting for authorization...[/dim]")

        max_attempts = expires_in // interval
        for _ in range(max_attempts):
            await asyncio.sleep(interval)
            try:
                async with httpx.AsyncClient() as c:
                    tr = await c.post(
                        github_access_token_url,
                        headers={"Accept": "application/json"},
                        json={
                            "client_id": github_client_id,
                            "device_code": device_code,
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        },
                        timeout=10,
                    )
                    tj = tr.json()

                error = tj.get("error")
                if error == "authorization_pending":
                    continue
                elif error == "slow_down":
                    await asyncio.sleep(5)
                    continue
                elif error == "expired_token":
                    console.print("[red]❌ Device code expired. Try again.[/red]")
                    raise typer.Exit(1)
                elif error == "access_denied":
                    console.print("[red]❌ Access denied by user.[/red]")
                    raise typer.Exit(1)
                elif error:
                    console.print(f"[red]❌ GitHub error: {error}[/red]")
                    raise typer.Exit(1)

                access_token = tj.get("access_token")
                if access_token:
                    home = os.path.expanduser("~")
                    token_dir = os.path.join(home, ".config", "shibaclaw", "github_copilot")
                    os.makedirs(token_dir, exist_ok=True)
                    with open(os.path.join(token_dir, "access-token"), "w") as f:
                        f.write(access_token)
                    console.print("[green]✓ Successfully authenticated with GitHub Copilot[/green]")
                    return

            except Exception as httperr:
                console.print(f"[red]❌ Network error during polling: {httperr}[/red]")
                continue

        console.print("[red]❌ Timed out waiting for authorization[/red]")
        raise typer.Exit(1)

    try:
        asyncio.run(_run_flow())
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)
