"""Model information helpers for the codebase.

Provides model context window lookup and autocomplete suggestions using a static database.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# A static mapping replacing litellm's massive internal DB
_STATIC_MODEL_COST = {
    "claude-3-7-sonnet-20250219": {"max_input_tokens": 200000, "max_tokens": 8192},
    "claude-3-5-sonnet-20241022": {"max_input_tokens": 200000, "max_tokens": 8192},
    "claude-3-5-sonnet-20240620": {"max_input_tokens": 200000, "max_tokens": 8192},
    "claude-3-5-haiku-20241022": {"max_input_tokens": 200000, "max_tokens": 8192},
    "claude-3-opus-20240229": {"max_input_tokens": 200000, "max_tokens": 4096},
    "gpt-4o": {"max_input_tokens": 128000, "max_tokens": 16384},
    "gpt-4o-2024-05-13": {"max_input_tokens": 128000, "max_tokens": 16384},
    "gpt-4o-2024-08-06": {"max_input_tokens": 128000, "max_tokens": 16384},
    "gpt-4o-2024-11-20": {"max_input_tokens": 128000, "max_tokens": 16384},
    "gpt-4o-mini": {"max_input_tokens": 128000, "max_tokens": 16384},
    "gpt-4-turbo": {"max_input_tokens": 128000, "max_tokens": 4096},
    "o1": {"max_input_tokens": 200000, "max_tokens": 100000},
    "o1-preview": {"max_input_tokens": 128000, "max_tokens": 32768},
    "o1-mini": {"max_input_tokens": 128000, "max_tokens": 65536},
    "o3-mini": {"max_input_tokens": 200000, "max_tokens": 100000},
    "deepseek-chat": {"max_input_tokens": 64000, "max_tokens": 8192},
    "deepseek-coder": {"max_input_tokens": 64000, "max_tokens": 8192},
    "deepseek-reasoner": {"max_input_tokens": 64000, "max_tokens": 8192},
    "qwen-plus": {"max_input_tokens": 131072, "max_tokens": 8192},
    "qwen-max": {"max_input_tokens": 32768, "max_tokens": 8192},
    "qwen-turbo": {"max_input_tokens": 131072, "max_tokens": 8192},
    "glm-4-plus": {"max_input_tokens": 128000, "max_tokens": 8192},
    "glm-4-0520": {"max_input_tokens": 128000, "max_tokens": 8192},
    "glm-4-air": {"max_input_tokens": 128000, "max_tokens": 8192},
    "moonshot-v1-8k": {"max_input_tokens": 8000, "max_tokens": 4096},
    "moonshot-v1-32k": {"max_input_tokens": 32000, "max_tokens": 4096},
    "moonshot-v1-128k": {"max_input_tokens": 128000, "max_tokens": 4096},
    "kimi-k2.5": {"max_input_tokens": 128000, "max_tokens": 8192},
    "gemini-1.5-pro": {"max_input_tokens": 2000000, "max_tokens": 8192},
    "gemini-1.5-flash": {"max_input_tokens": 1000000, "max_tokens": 8192},
    "gemini-2.0-pro-exp-02-05": {"max_input_tokens": 2000000, "max_tokens": 8192},
    "gemini-2.0-flash": {"max_input_tokens": 1000000, "max_tokens": 8192},
    "MiniMax-Text-01": {"max_input_tokens": 128000, "max_tokens": 8192},
    "MiniMax-M2.1": {"max_input_tokens": 128000, "max_tokens": 8192},
    "llama3-8b-8192": {"max_input_tokens": 8192, "max_tokens": 8192},
    "llama3-70b-8192": {"max_input_tokens": 8192, "max_tokens": 8192},
    "gemma2-9b-it": {"max_input_tokens": 8192, "max_tokens": 8192},
    "mixtral-8x7b-32768": {"max_input_tokens": 32768, "max_tokens": 8192},
    "nemotron-70b-instruct": {"max_input_tokens": 8192, "max_tokens": 8192},
}


@lru_cache(maxsize=1)
def get_all_models() -> list[str]:
    """Get all known model names."""
    return sorted(_STATIC_MODEL_COST.keys())


def _normalize_model_name(model: str) -> str:
    """Normalize model name for comparison."""
    return model.lower().replace("-", "_").replace(".", "")


def find_model_info(model_name: str) -> dict[str, Any] | None:
    """Find model info with fuzzy matching."""
    if not _STATIC_MODEL_COST:
        return None

    if model_name in _STATIC_MODEL_COST:
        return _STATIC_MODEL_COST[model_name]

    base_name = model_name.split("/")[-1] if "/" in model_name else model_name
    base_normalized = _normalize_model_name(base_name)
    candidates = []

    for key, info in _STATIC_MODEL_COST.items():
        key_base = key.split("/")[-1] if "/" in key else key
        key_base_normalized = _normalize_model_name(key_base)

        score = 0
        if base_normalized == key_base_normalized:
            score = 100
        elif base_normalized in key_base_normalized:
            score = 80
        elif key_base_normalized in base_normalized:
            score = 70
        elif base_normalized[:10] in key_base_normalized:
            score = 50

        if score > 0:
            if info.get("max_input_tokens"):
                score += 10
            candidates.append((score, key, info))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]


def get_model_context_limit(model: str, provider: str = "auto") -> int | None:
    """Get the maximum input context tokens for a model."""
    info = find_model_info(model)
    if info:
        max_input = info.get("max_input_tokens")
        if max_input and isinstance(max_input, int):
            return max_input

        max_tokens = info.get("max_tokens")
        if max_tokens and isinstance(max_tokens, int):
            return max_tokens

    return None


@lru_cache(maxsize=1)
def _get_provider_keywords() -> dict[str, list[str]]:
    """Build provider keywords mapping from shibaclaw's provider registry."""
    try:
        from shibaclaw.thinkers.registry import PROVIDERS

        mapping = {}
        for spec in PROVIDERS:
            if spec.keywords:
                mapping[spec.name] = list(spec.keywords)
        return mapping
    except ImportError:
        return {}


def get_model_suggestions(partial: str, provider: str = "auto", limit: int = 20) -> list[str]:
    """Get autocomplete suggestions for model names."""
    all_models = get_all_models()
    if not all_models:
        return []

    partial_lower = partial.lower()
    partial_normalized = _normalize_model_name(partial)
    provider_keywords = _get_provider_keywords()

    allowed_keywords = None
    if provider and provider != "auto":
        allowed_keywords = provider_keywords.get(provider.lower())

    matches = []
    for model in all_models:
        model_lower = model.lower()

        if allowed_keywords:
            if not any(kw in model_lower for kw in allowed_keywords):
                continue

        if not partial:
            matches.append(model)
            continue

        if partial_lower in model_lower:
            pos = model_lower.find(partial_lower)
            score = 100 - pos
            matches.append((score, model))
        elif partial_normalized in _normalize_model_name(model):
            score = 50
            matches.append((score, model))

    if matches and isinstance(matches[0], tuple):
        matches.sort(key=lambda x: (-x[0], x[1]))
        matches = [m[1] for m in matches]
    else:
        matches.sort()

    return matches[:limit]


def format_token_count(tokens: int) -> str:
    """Format token count for display (e.g., 200000 -> '200,000')."""
    return f"{tokens:,}"
