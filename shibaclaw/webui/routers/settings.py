from __future__ import annotations

import asyncio

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.utils import _deep_merge, _redact_secrets
from typing import Any

# Sensitive key-name fragments used for vault-backed placeholder injection
_SECRET_KEY_FRAGMENTS = ("token", "password", "secret", "key", "api_key", "apikey")


def _filter_redacted(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _filter_redacted(v) for k, v in data.items() if v != "***"}
    elif isinstance(data, list):
        return [_filter_redacted(item) for item in data]
    return data


def _normalize_provider_name(provider_name: str) -> str:
    return provider_name.lower().replace("-", "_")


def _provider_label(provider_name: str) -> str:
    from shibaclaw.thinkers.registry import find_by_name

    spec = find_by_name(provider_name)
    return spec.label if spec else provider_name.replace("_", " ").title()


def _canonical_model_id(provider_name: str, raw_model_id: str) -> str:
    if "/" in raw_model_id:
        prefix = _normalize_provider_name(raw_model_id.split("/", 1)[0])
        if prefix == _normalize_provider_name(provider_name):
            return raw_model_id
    return f"{provider_name}/{raw_model_id}"


def _normalize_model_entry(provider_name: str, model: dict[str, str]) -> dict[str, str] | None:
    raw_id = str((model or {}).get("id") or "").strip()
    if not raw_id:
        return None

    name = str((model or {}).get("name") or raw_id).strip()
    return {
        "id": _canonical_model_id(provider_name, raw_id),
        "raw_id": raw_id,
        "name": name,
        "provider": provider_name,
        "provider_label": _provider_label(provider_name),
    }


def _is_provider_configured(cfg, spec) -> bool:
    from shibaclaw.cli.auth import _is_oauth_authenticated

    provider_cfg = getattr(cfg.providers, spec.name, None)

    if spec.name == "custom":
        return bool(provider_cfg and (provider_cfg.api_base or provider_cfg.resolve_api_key()))
    if spec.is_oauth:
        return _is_oauth_authenticated(spec)
    if spec.name == "azure_openai":
        return bool(provider_cfg and provider_cfg.resolve_api_key(spec.name) and provider_cfg.api_base)
    if spec.is_local:
        return bool(provider_cfg and provider_cfg.api_base)
    return cfg._provider_has_credentials(provider_cfg, spec)


async def _fetch_provider_models(cfg, provider_name: str) -> list[dict[str, str]]:
    from shibaclaw.cli.base import _make_provider
    from shibaclaw.thinkers.registry import find_by_name

    provider_name = _normalize_provider_name(provider_name)
    spec = find_by_name(provider_name)
    if not spec:
        raise ValueError(f"Unknown provider: {provider_name}")
    if not _is_provider_configured(cfg, spec):
        raise RuntimeError(f"Provider {provider_name} not configured")

    temp_cfg = cfg.model_copy(deep=True)
    temp_cfg.agents.defaults.provider = provider_name
    temp_cfg.agents.defaults.model = f"{provider_name}/dummy"

    temp_provider = _make_provider(temp_cfg, exit_on_error=False)
    if not temp_provider:
        raise RuntimeError(f"Provider {provider_name} not configured")

    models = await temp_provider.get_available_models()
    normalized: list[dict[str, str]] = []
    for model in models:
        entry = _normalize_model_entry(provider_name, model)
        if entry:
            normalized.append(entry)
    return normalized


async def _fetch_all_configured_provider_models(cfg) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    from shibaclaw.thinkers.registry import PROVIDERS

    provider_names: list[str] = []
    for spec in PROVIDERS:
        if _is_provider_configured(cfg, spec):
            provider_names.append(spec.name)

    if not provider_names:
        return [], []

    results = await asyncio.gather(
        *(
            asyncio.wait_for(_fetch_provider_models(cfg, provider_name), timeout=6.0)
            for provider_name in provider_names
        ),
        return_exceptions=True,
    )

    models: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for provider_name, result in zip(provider_names, results, strict=False):
        if isinstance(result, Exception):
            logger.warning("Failed to fetch models from provider {}: {}", provider_name, result)
            errors.append({"provider": provider_name, "error": str(result)})
            continue
        models.extend(result)

    models.sort(
        key=lambda item: (
            (item.get("name") or item.get("raw_id") or item["id"]).casefold(),
            item.get("provider_label", "").casefold(),
            item.get("raw_id", "").casefold(),
        )
    )
    return models, errors


def _inject_vault_placeholders(data: dict) -> dict:
    """For sensitive fields that are empty in the serialized config but have a value
    stored in the vault, inject a '***' placeholder so the webUI knows the secret
    is configured and shows a masked input instead of a blank field.

    This mirrors what _redact_secrets does for plaintext values, but targets the
    vault-backed case where the plain field is empty string.
    """
    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        if not cm.is_setup():
            return data
    except Exception:
        return data

    def _maybe_mask(section: str, vault_key: str, cfg: dict, field: str) -> None:
        """If cfg[field] is empty but vault has a value, set cfg[field] = '***'."""
        if cfg.get(field, "") != "":
            return
        try:
            val = cm.get_secret(section, vault_key)
            if val:
                cfg[field] = "***"
        except Exception:
            pass

    # --- Provider API keys ---
    for provider_name, provider_cfg in (data.get("providers") or {}).items():
        if isinstance(provider_cfg, dict):
            _maybe_mask("providers", f"{provider_name}.api_key", provider_cfg, "apiKey")

    # --- Web search API key ---
    try:
        search_cfg = data["tools"]["web"]["search"]
        if isinstance(search_cfg, dict):
            _maybe_mask("tools", "web_search.api_key", search_cfg, "apiKey")
    except (KeyError, TypeError):
        pass

    # --- Audio API key ---
    audio_cfg = data.get("audio", {})
    if isinstance(audio_cfg, dict):
        _maybe_mask("audio", "api_key", audio_cfg, "apiKey")

    # --- Channel secrets ---
    for ch_name, ch_cfg in (data.get("channels") or {}).items():
        if not isinstance(ch_cfg, dict):
            continue
        for field in list(ch_cfg.keys()):
            if any(f in field.lower() for f in _SECRET_KEY_FRAGMENTS) and isinstance(ch_cfg.get(field), str):
                # Derive vault key: camelCase field → snake_case
                import re
                snake = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
                _maybe_mask("channels", f"{ch_name}.{field}", ch_cfg, field)
                # Also try snake_case vault key as fallback
                if ch_cfg.get(field, "") == "" and snake != field:
                    _maybe_mask("channels", f"{ch_name}.{snake}", ch_cfg, field)

    # --- MCP OAuth client secrets ---
    for server_name, server_cfg in (data.get("tools", {}).get("mcpServers") or {}).items():
        if not isinstance(server_cfg, dict):
            continue
        oauth = server_cfg.get("oauth", {})
        if isinstance(oauth, dict):
            _maybe_mask("mcp_servers", f"{server_name}.client_secret", oauth, "clientSecret")

    return data


async def api_settings_get(request: Request):
    """Get the current configuration (redacted)."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    data = agent_manager.config.model_dump(mode="json", by_alias=True)
    # Inject '***' for vault-backed secrets that have an empty plain field so
    # the webUI shows a masked placeholder instead of a blank input.
    data = _inject_vault_placeholders(data)
    return JSONResponse(_redact_secrets(data))


_settings_update_lock = asyncio.Lock()


async def api_settings_post(request: Request):
    """Update configuration and reload the agent (hot-reload, no restart required)."""
    async with _settings_update_lock:
        if not agent_manager.config:
            agent_manager.load_latest_config()
        if not agent_manager.config:
            return JSONResponse({"error": "No config"}, status_code=400)

        data = await request.json()
        from shibaclaw.config.schema import Config
        from shibaclaw.config.loader import _migrate_secrets_from_raw_dict

        old_cfg = agent_manager.config
        merged = old_cfg.model_dump(mode="json", by_alias=True)
        if isinstance(data.get("tools"), dict) and "mcpServers" in data["tools"]:
            merged.setdefault("tools", {})["mcpServers"] = data["tools"]["mcpServers"]
        filtered_data = _filter_redacted(data)
        _deep_merge(merged, filtered_data)

        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        if cm.is_setup():
            _migrate_secrets_from_raw_dict(merged, cm)

        try:
            new_cfg = Config.model_validate(merged)
        except Exception as e:
            return JSONResponse({"error": f"Invalid config: {e}"}, status_code=422)

        from shibaclaw.config.loader import get_config_path, _scrub_secrets_from_dump
        path = get_config_path()
        import json
        import os
        import tempfile
        path.parent.mkdir(parents=True, exist_ok=True)
        # Scrub any residual plaintext secrets before persisting (belt-and-suspenders
        # on top of _migrate_secrets_from_raw_dict which already popped them from merged)
        _scrub_secrets_from_dump(merged)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
            json.dump(merged, tmp, indent=2, ensure_ascii=False)
            tmp_name = tmp.name
        os.replace(tmp_name, path)
        agent_manager.config = new_cfg

        # Detect if network-binding gateway settings changed — those require a full restart
        net_changed = (
            new_cfg.gateway.host != old_cfg.gateway.host
            or new_cfg.gateway.port != old_cfg.gateway.port
            or new_cfg.gateway.ws_port != old_cfg.gateway.ws_port
        )

        if net_changed:
            try:
                from shibaclaw.cli.commands import _make_provider

                agent_manager.provider = _make_provider(new_cfg, exit_on_error=False)
            except Exception:
                agent_manager.provider = None
            await agent_manager.reset_agent()
            logger.info(
                "Config updated (full restart — network settings changed) by {}",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse({"status": "updated", "restarted": True})

        await agent_manager.reload_config(new_cfg)
        logger.info(
            "Config updated (hot-reload) by {}",
            request.client.host if request.client else "unknown",
        )

    return JSONResponse({"status": "updated", "restarted": False})

async def api_models_get(request: Request):
    """Get available models for one provider or aggregate all configured providers."""
    provider_name = request.query_params.get("provider")
    if not agent_manager.config:
        agent_manager.load_latest_config()

    cfg = agent_manager.config
    if not cfg:
        return JSONResponse({"error": "No config"}, status_code=400)

    if provider_name:
        try:
            models = await _fetch_provider_models(cfg, provider_name)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        return JSONResponse({"models": models, "errors": []})

    models, errors = await _fetch_all_configured_provider_models(cfg)
    return JSONResponse({"models": models, "errors": errors})
