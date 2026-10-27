from __future__ import annotations

import asyncio
import copy
import time

from loguru import logger
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.utils import _deep_merge, _redact_secrets
from typing import Any

# Sensitive key-name fragments used for vault-backed placeholder injection
_SECRET_KEY_FRAGMENTS = ("token", "password", "secret", "key", "api_key", "apikey")


def _filter_redacted(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _filter_redacted(v) for k, v in data.items() if v != "***" and v != "****"}
    elif isinstance(data, list):
        return [_filter_redacted(item) for item in data]
    return data


def _normalize_provider_name(provider_name: str) -> str:
    from shibaclaw.helpers.model_ids import normalize_provider_name

    return normalize_provider_name(provider_name)


def _provider_label(provider_name: str) -> str:
    from shibaclaw.thinkers.registry import find_by_name

    spec = find_by_name(provider_name)
    return spec.label if spec else provider_name.replace("_", " ").title()


def _canonical_model_id(provider_name: str, raw_model_id: str) -> str:
    if provider_name.startswith("endpoint_"):
        return f"{provider_name}/{raw_model_id}"
    if "/" in raw_model_id:
        prefix = _normalize_provider_name(raw_model_id.split("/", 1)[0])
        if prefix == _normalize_provider_name(provider_name):
            return raw_model_id
    return f"{provider_name}/{raw_model_id}"


def _extract_reasoning_efforts(model: dict[str, Any]) -> list[str]:
    """Read reasoning levels exposed by a provider's model catalog."""
    for key in (
        "reasoning_efforts",
        "supported_reasoning_efforts",
        "supported_reasoning_levels",
        "reasoning_levels",
    ):
        raw_efforts = model.get(key)
        if not isinstance(raw_efforts, list):
            continue
        efforts = []
        for item in raw_efforts:
            value = item.get("effort") if isinstance(item, dict) else item
            if isinstance(value, str) and value.strip():
                efforts.append(value.strip().lower())
        if efforts:
            return efforts
    return []


def _normalize_model_entry(provider_name: str, model: dict[str, Any]) -> dict[str, Any] | None:
    from shibaclaw.thinkers.registry import get_model_reasoning_efforts

    raw_id = str((model or {}).get("id") or "").strip()
    if not raw_id:
        return None

    canonical_id = _canonical_model_id(provider_name, raw_id)
    name = str((model or {}).get("name") or raw_id).strip()
    efforts = _extract_reasoning_efforts(model)
    efforts = efforts or get_model_reasoning_efforts(raw_id) or get_model_reasoning_efforts(canonical_id)

    if not efforts and isinstance(model, dict):
        supp = model.get("supported_parameters") or model.get("supported_params") or []
        if isinstance(supp, list):
            supp_str = " ".join(str(p).lower() for p in supp)
            if any(k in supp_str for k in ("reasoning", "include_reasoning", "reasoning_effort", "thinking")):
                efforts = ["low", "medium", "high"]

    return {
        "id": canonical_id,
        "raw_id": raw_id,
        "name": name,
        "provider": provider_name,
        "provider_label": _provider_label(provider_name),
        "supports_reasoning": bool(efforts),
        "reasoning_efforts": efforts,
    }



def _configured_provider_metadata(cfg) -> list[dict[str, Any]]:
    from shibaclaw.helpers.model_ids import configured_provider_names

    providers = []
    for provider_id in configured_provider_names(cfg):
        endpoint = cfg.provider_endpoints.get(provider_id)
        provider_cfg = endpoint or getattr(cfg.providers, provider_id)
        provider_type = endpoint.provider if endpoint else provider_id
        providers.append({
            "id": provider_id,
            "name": provider_cfg.name or _provider_label(provider_type),
            "api_base": provider_cfg.api_base or "",
            "provider": provider_type,
        })
    return providers


async def _fetch_provider_models(cfg, provider_name: str) -> list[dict[str, Any]]:
    from shibaclaw.cli.base import _make_provider
    from shibaclaw.thinkers.registry import find_by_name

    provider_name = _normalize_provider_name(provider_name)
    endpoint = cfg.provider_endpoints.get(provider_name)
    spec = find_by_name(endpoint.provider if endpoint else provider_name)
    if not spec:
        raise ValueError(f"Unknown provider: {provider_name}")
    if provider_name not in {item["id"] for item in _configured_provider_metadata(cfg)}:
        raise RuntimeError(f"Provider {provider_name} not configured")

    temp_cfg = cfg.model_copy(deep=True)
    temp_cfg.agents.defaults.provider = provider_name
    temp_cfg.agents.defaults.model = f"{provider_name}/dummy"

    temp_provider = _make_provider(temp_cfg, exit_on_error=False)
    if not temp_provider:
        raise RuntimeError(f"Provider {provider_name} not configured")

    models = await temp_provider.get_available_models()
    normalized: list[dict[str, Any]] = []
    for model in models:
        entry = _normalize_model_entry(provider_name, model)
        if entry:
            provider_cfg = endpoint or getattr(cfg.providers, provider_name)
            entry["provider_label"] = provider_cfg.name or _provider_label(spec.name)
            if endpoint:
                entry["api_base"] = endpoint.api_base or ""
            normalized.append(entry)
    return normalized


async def _fetch_all_configured_provider_models(
    cfg,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    provider_names = [item["id"] for item in _configured_provider_metadata(cfg)]

    if not provider_names:
        return [], []

    def _fetch_sync(provider_name: str) -> list[dict[str, Any]]:
        # shortcut: a blocking models.list stalls this loop and the 3s timeout
        # then drops the fast catalogs. Each provider runs in its own thread.
        return asyncio.run(_fetch_provider_models(cfg, provider_name))

    results = await asyncio.gather(
        *(
            asyncio.wait_for(asyncio.to_thread(_fetch_sync, provider_name), timeout=12.0)
            for provider_name in provider_names
        ),
        return_exceptions=True,
    )

    models: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for provider_name, result in zip(provider_names, results, strict=False):
        if isinstance(result, BaseException):
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


async def _inject_vault_placeholders(data: dict) -> dict:
    """For sensitive fields that are empty in the serialized config but have a value
    stored in the vault, inject a '***' placeholder so the webUI knows the secret
    is configured and shows a masked input instead of a blank field.

    This mirrors what _redact_secrets does for plaintext values, but targets the
    vault-backed case where the plain field is empty string.
    """
    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        if not await run_in_threadpool(cm.is_setup):
            return data
    except Exception:
        return data

    async def _maybe_mask(section: str, vault_key: str, cfg: dict, field: str) -> None:
        """If cfg[field] is empty but vault has a value, set cfg[field] = '***'."""
        if cfg.get(field, "") != "":
            return
        try:
            val = await run_in_threadpool(cm.get_secret, section, vault_key)
            if val:
                cfg[field] = "***"
        except Exception:
            pass

    # --- Provider API keys ---
    for provider_name, provider_cfg in (data.get("providers") or {}).items():
        if isinstance(provider_cfg, dict):
            await _maybe_mask("providers", f"{provider_name}.api_key", provider_cfg, "apiKey")
            if provider_cfg.get("apiKey", "") == "":
                from shibaclaw.config.loader import _provider_alias_to_snake
                snake = _provider_alias_to_snake(provider_name)
                if snake != provider_name:
                    await _maybe_mask("providers", f"{snake}.api_key", provider_cfg, "apiKey")

    for endpoint_id, endpoint_cfg in (data.get("providerEndpoints") or {}).items():
        if isinstance(endpoint_cfg, dict):
            await _maybe_mask("providers", f"{endpoint_id}.api_key", endpoint_cfg, "apiKey")

    # --- Web search API key ---
    try:
        search_cfg = data["tools"]["web"]["search"]
        if isinstance(search_cfg, dict):
            await _maybe_mask("tools", "web_search.api_key", search_cfg, "apiKey")
    except (KeyError, TypeError):
        pass

    # --- RAG API key ---
    rag_cfg = data.get("rag", {})
    if isinstance(rag_cfg, dict):
        await _maybe_mask("rag", "api_key", rag_cfg, "apiKey")

    # --- Audio API key ---
    audio_cfg = data.get("audio", {})
    if isinstance(audio_cfg, dict):
        await _maybe_mask("audio", "api_key", audio_cfg, "apiKey")

    # --- Channel secrets ---
    channel_secret_fields = {
        ("telegram", "token"), ("discord", "token"), ("slack", "bot_token"),
        ("slack", "app_token"), ("email", "imap_password"), ("email", "smtp_password"),
        ("matrix", "access_token"), ("wecom", "secret"), ("dingtalk", "client_secret"),
        ("feishu", "app_secret"), ("feishu", "verification_token"), ("qq", "secret"),
        ("mochat", "claw_token"), ("whatsapp", "bridge_token"),
    }
    for ch_name, ch_cfg in (data.get("channels") or {}).items():
        if not isinstance(ch_cfg, dict):
            continue
        import re
        for field in list(ch_cfg.keys()):
            if isinstance(ch_cfg.get(field), str):
                snake = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
                if (ch_name.lower(), snake) in channel_secret_fields:
                    await _maybe_mask("channels", f"{ch_name}.{snake}", ch_cfg, field)

    # --- MCP OAuth client secrets ---
    for server_name, server_cfg in (data.get("tools", {}).get("mcpServers") or {}).items():
        if not isinstance(server_cfg, dict):
            continue
        oauth = server_cfg.get("oauth", {})
        if isinstance(oauth, dict):
            await _maybe_mask("mcp_servers", f"{server_name}.client_secret", oauth, "clientSecret")

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
    data = await _inject_vault_placeholders(data)
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
        from pydantic import ValidationError
        from shibaclaw.config.schema import Config
        from shibaclaw.config.loader import (
            _migrate_secrets_from_raw_dict,
            _scrub_secrets_from_dump,
            _get_cm_if_active,
            get_config_path,
        )

        old_cfg = agent_manager.config
        merged = old_cfg.model_dump(mode="json", by_alias=True)
        if isinstance(data.get("tools"), dict) and "mcpServers" in data["tools"]:
            merged.setdefault("tools", {})["mcpServers"] = data["tools"]["mcpServers"]
        filtered_data = _filter_redacted(data)
        for key in ("providerEndpoints", "provider_endpoints"):
            if key in data:
                endpoints = filtered_data.pop(key, None)
                if isinstance(endpoints, dict):
                    previous = merged.get("providerEndpoints", {})
                    merged["providerEndpoints"] = {endpoint_id: previous.get(endpoint_id, {}) for endpoint_id in endpoints}
                    _deep_merge(merged["providerEndpoints"], endpoints)
                else:
                    merged["providerEndpoints"] = endpoints
        _deep_merge(merged, filtered_data)

        # ----------------------------------------------------------------
        # IMPORTANT: validate new_cfg from the FULL merged dict (with
        # secrets still present) so the in-memory config always holds the
        # real values and the webUI can read them back on the next GET.
        # ----------------------------------------------------------------
        try:
            new_cfg = Config.model_validate(merged)
        except ValidationError as e:
            errors = e.errors(include_input=False, include_context=False, include_url=False)
            message = "; ".join(f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in errors)
            logger.error("Validation failed: {}", message)
            return JSONResponse({"error": f"Invalid config: {message}"}, status_code=422)
        except Exception as e:
            logger.error("Config validation failed ({})", type(e).__name__)
            return JSONResponse({"error": "Invalid config"}, status_code=422)

        # ----------------------------------------------------------------
        # Persist to disk.
        # Work on a deep copy so we never mutate `merged` (which backs
        # new_cfg) when migrating/scrubbing for the on-disk representation.
        # ----------------------------------------------------------------
        disk_data = copy.deepcopy(merged)
        cm = _get_cm_if_active()
        if cm:
            for section in ("providerEndpoints", "provider_endpoints"):
                endpoint_inputs = data.get(section, {})
                if isinstance(endpoint_inputs, dict):
                    for endpoint_id, endpoint_input in endpoint_inputs.items():
                        if isinstance(endpoint_input, dict) and any(endpoint_input.get(key) == "" for key in ("apiKey", "api_key")):
                            cm.delete_secret("providers", f"{endpoint_id}.api_key")
            # Move plaintext secrets into the vault and remove from disk copy.
            _migrate_secrets_from_raw_dict(disk_data, cm)
            for endpoint in new_cfg.provider_endpoints.values():
                endpoint.api_key = ""
        # Belt-and-suspenders: zero out any residual plaintext only when vault active.
        _scrub_secrets_from_dump(disk_data, cm)

        import json
        import os
        import tempfile

        path = get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
            json.dump(disk_data, tmp, indent=2, ensure_ascii=False)
            tmp_name = tmp.name
        os.replace(tmp_name, path)

        agent_manager.config = new_cfg
        invalidate_models_cache()

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

_models_cache: tuple[float, list, list] | None = None
_models_cache_generation = 0


def invalidate_models_cache() -> None:
    """Refresh catalogs after settings or OAuth credentials change."""
    global _models_cache, _models_cache_generation
    _models_cache = None
    _models_cache_generation += 1


async def api_models_get(request: Request):
    """Get available models for one provider or aggregate all configured providers."""
    global _models_cache
    provider_name = request.query_params.get("provider")
    if not agent_manager.config:
        agent_manager.load_latest_config()

    cfg = agent_manager.config
    if not cfg:
        return JSONResponse({"error": "No config"}, status_code=400)
    providers = _configured_provider_metadata(cfg)
    if (
        not provider_name
        and _models_cache
        and _models_cache[1]
        and time.monotonic() - _models_cache[0] < 120
    ):
        return JSONResponse({"models": _models_cache[1], "errors": _models_cache[2], "providers": providers})

    if provider_name:
        try:
            models = await _fetch_provider_models(cfg, provider_name)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        return JSONResponse({"models": models, "errors": [], "providers": [item for item in providers if item["id"] == provider_name]})

    generation = _models_cache_generation
    models, errors = await _fetch_all_configured_provider_models(cfg)
    # A catalog fetched before an account/settings change must not refill the cache.
    if models and generation == _models_cache_generation:
        _models_cache = (time.monotonic(), models, errors)
    return JSONResponse({"models": models, "errors": errors, "providers": providers})
