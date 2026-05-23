from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from shibaclaw.cli.auth import _is_oauth_authenticated
from shibaclaw.thinkers.registry import PROVIDERS, find_by_name

if TYPE_CHECKING:
    from shibaclaw.config.schema import Config


def normalize_provider_name(provider_name: str | None) -> str:
    return (provider_name or "").strip().lower().replace("-", "_")


def split_model_id(model: str | None) -> tuple[str | None, str]:
    value = (model or "").strip()
    if not value or "/" not in value:
        return None, value

    prefix, rest = value.split("/", 1)
    spec = find_by_name(normalize_provider_name(prefix))
    if not spec:
        return None, value
    return spec.name, rest.strip()


def raw_model_id(model: str | None) -> str:
    provider_name, remainder = split_model_id(model)
    if provider_name:
        return remainder
    return (model or "").strip()


def configured_provider_names(cfg: Config | None) -> list[str]:
    if cfg is None:
        return []

    names: list[str] = []
    for spec in PROVIDERS:
        provider_cfg = getattr(cfg.providers, spec.name, None)

        if spec.name == "custom":
            ready = bool(provider_cfg and (provider_cfg.api_base or provider_cfg.api_key))
        elif spec.is_oauth:
            ready = _is_oauth_authenticated(spec)
        elif spec.name == "azure_openai":
            ready = bool(provider_cfg and provider_cfg.api_key and provider_cfg.api_base)
        elif spec.is_local:
            ready = bool(provider_cfg and provider_cfg.api_base)
        else:
            ready = cfg._provider_has_credentials(provider_cfg, spec)

        if ready:
            names.append(spec.name)

    return names


def canonicalize_model_id(
    cfg: Config | None,
    model: str | None,
    *,
    configured_names: Iterable[str] | None = None,
) -> str:
    value = (model or "").strip()
    if not value:
        return ""

    provider_name, raw_value = split_model_id(value)
    if provider_name:
        return f"{provider_name}/{raw_value}" if raw_value else value

    if cfg is None:
        return value

    default_model = canonicalize_model_id(None, cfg.agents.defaults.model)
    if default_model and raw_model_id(default_model) == value:
        return default_model

    forced_provider = normalize_provider_name(cfg.agents.defaults.provider)
    if forced_provider and forced_provider != "auto" and find_by_name(forced_provider):
        return f"{forced_provider}/{value}"

    provider_names = list(
        dict.fromkeys(
            normalize_provider_name(name)
            for name in (configured_names if configured_names is not None else configured_provider_names(cfg))
            if normalize_provider_name(name)
        )
    )
    provider_names = [name for name in provider_names if find_by_name(name)]
    if len(provider_names) == 1:
        return f"{provider_names[0]}/{value}"

    return value
