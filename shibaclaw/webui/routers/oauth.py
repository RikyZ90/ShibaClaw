from __future__ import annotations

import os
import uuid

from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager


def get_oauth_providers_status() -> list[dict]:
    if not agent_manager.config:
        agent_manager.load_latest_config()

    providers = [
        {"name": "openrouter", "label": "OpenRouter"},
        {"name": "github_copilot", "label": "GitHub Copilot"},
        {"name": "openai_codex", "label": "OpenAI Codex"},
        {"name": "anthropic", "label": "Anthropic / Claude"},
        {"name": "google_gemini_cli", "label": "Google Gemini CLI"},
        {"name": "xai", "label": "xAI / Grok"},
        {"name": "qwen_oauth", "label": "Qwen / Alibaba"},
        {"name": "minimax_portal", "label": "MiniMax"},
        {"name": "z_ai", "label": "Z.AI / GLM"},
    ]
    result = []
    for p in providers:
        status, msg = "not_configured", ""
        try:
            if p["name"] == "openrouter":
                cfg = agent_manager.config
                # ProviderConfig no longer has a plain api_key field;
                # use resolve_api_key() which checks the vault.
                has_config_key = bool(
                    cfg and cfg.providers.openrouter.resolve_api_key("openrouter")
                )
                has_env = bool(os.environ.get("OPENROUTER_API_KEY"))
                status = "configured" if (has_config_key or has_env) else "not_configured"
                if has_config_key:
                    msg = "API key saved in config"
                elif has_env:
                    msg = "Using OPENROUTER_API_KEY from environment"
                else:
                    msg = "No configured API key"
            elif p["name"] == "openai_codex":
                try:
                    from oauth_cli_kit import get_token

                    tk = get_token()
                    if tk and getattr(tk, "access", None):
                        status, msg = (
                            "configured",
                            f"Account: {getattr(tk, 'account_id', 'unknown')}",
                        )
                except (ImportError, Exception):
                    status, msg = "not_configured", ""
            elif p["name"] == "github_copilot":
                home = os.path.expanduser("~")
                token_paths = [
                    os.path.join(home, ".shibaclaw", "github_copilot", "access-token"),
                ]
                has_cached = any(os.path.exists(tp) for tp in token_paths)
                has_env = bool(os.environ.get("GITHUB_COPILOT_TOKEN"))
                status = "configured" if (has_cached or has_env) else "not_configured"
                msg = (
                    "Authenticated"
                    if status == "configured"
                    else "No credentials found"
                )
            elif p["name"] in ("anthropic", "google_gemini_cli", "xai", "qwen_oauth", "minimax_portal", "z_ai"):
                from shibaclaw.security.oauth_store import OAuthTokenStore
                
                store = OAuthTokenStore()
                token = store.load_token(p["name"])
                if token and token.get("access_token"):
                    status = "configured"
                    msg = "Authenticated via OAuth"
                else:
                    status = "not_configured"
                    msg = "No credentials found"
        except Exception as e:
            status, msg = "error", str(e)
        result.append({**p, "status": status, "message": msg})
    return result

async def api_oauth_providers(request: Request):
    return JSONResponse({"providers": get_oauth_providers_status()})


async def api_oauth_login(request: Request):
    data = await request.json()
    provider = data.get("provider", "").replace("-", "_")
    generic_providers = {
        "anthropic": "Anthropic / Claude",
        "google_gemini_cli": "Google Gemini CLI",
        "xai": "xAI / Grok",
        "qwen_oauth": "Qwen / Alibaba",
        "minimax_portal": "MiniMax",
        "z_ai": "Z.AI / GLM",
    }
    if provider not in ("openrouter", "github_copilot", "openai_codex") and provider not in generic_providers:
        return JSONResponse({"error": "Unknown provider"}, status_code=404)

    job_id = str(uuid.uuid4())[:8]
    jobs = agent_manager.oauth_jobs
    jobs[job_id] = {"provider": provider, "status": "running", "logs": []}

    if provider == "openrouter":
        from ..oauth_github import start_openrouter_oauth

        return await start_openrouter_oauth(request, job_id, jobs)
    if provider == "github_copilot":
        from ..oauth_github import start_github_oauth

        return await start_github_oauth(job_id, jobs)
    elif provider == "openai_codex":
        from ..oauth_github import start_codex_oauth

        return await start_codex_oauth(job_id, jobs)
    elif provider in generic_providers:
        from ..oauth_generic import start_generic_oauth
        
        return await start_generic_oauth(request, job_id, jobs, provider, generic_providers[provider])


async def api_oauth_openrouter_callback(request: Request):
    from ..oauth_github import finish_openrouter_oauth

    return await finish_openrouter_oauth(request, agent_manager.oauth_jobs)


async def api_oauth_disconnect(request: Request):
    data = await request.json()
    provider = data.get("provider")
    if not provider:
        return JSONResponse({"error": "No provider specified"}, status_code=400)

    if provider == "openrouter":
        from shibaclaw.config.manager import config_manager
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        await run_in_threadpool(cm.delete_secret, "providers", "openrouter.api_key")
        config = config_manager.load_config()
        config.providers.openrouter.api_key = ""
        config_manager.save_config(config)
        await agent_manager.reload_config(config)
    elif provider == "openai_codex":
        try:
            import os
            from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
            from oauth_cli_kit.storage import FileTokenStorage
            
            storage = FileTokenStorage(token_filename=OPENAI_CODEX_PROVIDER.token_filename)
            token_path = storage.get_token_path()
            if os.path.exists(token_path):
                os.remove(token_path)
        except Exception:
            pass
    else:
        from shibaclaw.security.oauth_store import OAuthTokenStore
        store = OAuthTokenStore()
        store.delete_token(provider)

    return JSONResponse({"ok": True})

async def api_oauth_job(request: Request):
    job_id = request.path_params.get("job_id")
    jobs = agent_manager.oauth_jobs
    j = jobs.get(job_id)
    if not j:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse({"job": {k: v for k, v in j.items() if not k.startswith("_")}})


async def api_oauth_code(request: Request):
    data = await request.json()
    job_id, code = data.get("job_id"), data.get("code", "").strip()
    jobs = agent_manager.oauth_jobs
    j = jobs.get(job_id)
    if not j:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    event, holder = j.get("_code_event"), j.get("_code_holder")
    if not event or not holder:
        return JSONResponse({"error": "Job does not accept code input"}, status_code=400)
    holder["value"] = code
    event.set()
    j["logs"].append("📋 Code received, exchanging for token...")
    return JSONResponse({"ok": True})
