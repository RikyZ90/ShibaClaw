"""OpenAI-compatible provider implementation using the official openai SDK."""

import asyncio
import os
import secrets
import string
import uuid
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from shibaclaw.thinkers.base import LLMResponse, Thinker, ToolCallRequest
from shibaclaw.thinkers.registry import ProviderSpec, find_by_model, find_by_name, find_gateway

_ALNUM = string.ascii_letters + string.digits


def _short_tool_id() -> str:
    """Generate a 9-char alphanumeric ID suitable for strict providers."""
    return "".join(secrets.choice(_ALNUM) for _ in range(9))


def _extract_extra_fields(obj: Any, known_keys: set[str]) -> dict[str, Any]:
    """Preserve provider-specific fields carried on SDK response objects.

    Some OpenAI-compatible providers, including Gemini, attach required metadata
    like `thought_signature` as extra fields on tool-call objects. The OpenAI SDK
    keeps those extras, but they need to be copied back into conversation history
    verbatim on the next turn.
    """
    extras: dict[str, Any] = {}

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key not in known_keys and value is not None:
                extras[key] = value
        return extras

    for attr_name in ("model_extra", "__pydantic_extra__"):
        attr = getattr(obj, attr_name, None)
        if isinstance(attr, dict):
            for key, value in attr.items():
                if key not in known_keys and value is not None:
                    extras[key] = value

    # Be explicit about known Gemini/OpenAI compatibility fields in case the SDK
    # exposes them as plain attributes instead of model extras.
    for key in ("thought_signature", "thoughtSignature"):
        value = getattr(obj, key, None)
        if value is not None and key not in known_keys:
            extras[key] = value

    return extras


def _extract_reasoning_details(obj: Any) -> list[dict[str, Any]] | None:
    value = getattr(obj, "reasoning_details", None)
    if value is None and isinstance(getattr(obj, "model_extra", None), dict):
        value = obj.model_extra.get("reasoning_details")
    if value is None and isinstance(getattr(obj, "__pydantic_extra__", None), dict):
        value = obj.__pydantic_extra__.get("reasoning_details")
    if value is None and isinstance(obj, dict):
        value = obj.get("reasoning_details")
    return value if isinstance(value, list) else None


def _reasoning_detail_key(detail: dict[str, Any], index: int) -> tuple[Any, ...]:
    """Return a stable identity for a streamed reasoning block."""
    if detail_id := detail.get("id"):
        return ("id", detail_id)
    if signature := detail.get("signature"):
        return ("signature", signature)
    return ("type-index", detail.get("type"), detail.get("index", index))


def _merge_reasoning_details(
    accumulated: list[dict[str, Any]], details: list[dict[str, Any]]
) -> None:
    """Replace repeated streamed reasoning blocks while preserving their order."""
    positions = {
        _reasoning_detail_key(detail, index): index for index, detail in enumerate(accumulated)
    }

    for index, detail in enumerate(details):
        key = _reasoning_detail_key(detail, index)
        position = positions.get(key)
        if position is None:
            positions[key] = len(accumulated)
            accumulated.append(detail)
        else:
            accumulated[position] = detail


class OpenAIThinker(Thinker):
    """
    Thinker using the native openai SDK for multi-provider support.

    Supports OpenAI, OpenRouter, DeepSeek, vLLM, Ollama, and any other
    OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "openai/gpt-4o",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._provider_name = provider_name

        # Detect gateway or specific config if present
        self._gateway = find_gateway(provider_name, api_key, api_base)

        # Determine actual key and base URL
        resolved_key = self._resolve_api_key(api_key, self._gateway, default_model)

        # If not a gateway, fallback to the provider's standard base URL (if known)
        if not self._gateway and provider_name:
            spec = find_by_name(provider_name)
        elif not self._gateway:
            spec = find_by_model(default_model)
        else:
            spec = self._gateway

        resolved_base = api_base or (spec.default_api_base if spec else None)

        # Stable session affinity for custom backends
        default_headers = {
            "x-session-affinity": uuid.uuid4().hex,
            **(extra_headers or {}),
        }

        if self._gateway and self._gateway.is_gateway:
            # Some gateways like OpenRouter recommend sending a referrer
            default_headers.setdefault("HTTP-Referer", "https://github.com/RikyZ90/ShibaClaw")
            default_headers.setdefault("X-Title", "ShibaClaw")

        logger.debug(
            f"OpenAIThinker init: api_key={'SET' if api_key else 'UNSET'} resolved_key={'SET' if resolved_key else 'UNSET'} base_url={resolved_base}"
        )

        self._client = AsyncOpenAI(
            api_key=resolved_key or "no-key",
            base_url=resolved_base,
            default_headers=default_headers,
        )

    def _resolve_api_key(
        self, api_key: str | None, spec: ProviderSpec | None, model: str
    ) -> str | None:
        """Resolve the API key from kwargs or environment variables."""
        if api_key:
            return api_key

        s = spec or find_by_model(model)
        if s and s.env_key:
            return os.environ.get(s.env_key)

        return None

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying strip prefixes if needed."""
        if model.split("/", 1)[0].startswith("endpoint_") and "/" in model:
            return model.split("/", 1)[1]
        # Get provider spec if we have a known provider
        provider_spec = find_by_name(self._provider_name) if self._provider_name else None

        # Strip provider prefix UNLESS the provider explicitly preserves it
        if not (provider_spec and getattr(provider_spec, "preserve_model_prefix", False)):
            stripped = self._strip_provider_prefix(model, getattr(self, "_provider_name", None))
            # For gateways, don't strip when the result is a bare name (no "/").
            # Models like "openrouter/free" or "openrouter/auto" are meta-router
            # IDs where the gateway name IS part of the model namespace.
            if (
                self._gateway
                and self._gateway.is_gateway
                and stripped
                and "/" not in stripped
                and "/" in model
            ):
                pass  # keep the original model with its prefix
            else:
                model = stripped

        # For pure OpenAI client, we don't need litellm_prefix logic!
        # Instead, we just need to respect `strip_model_prefix` if the gateway demands bare models.
        if self._gateway and self._gateway.strip_model_prefix:
            if "/" in model:
                model = model.split("/")[-1]

        # For non-gateway standard usage (e.g. hitting OpenAI directly)
        elif not self._gateway:
            spec = find_by_model(model)
            if (
                spec
                and not getattr(spec, "preserve_model_prefix", False)
                and "/" in model
                and model.startswith(f"{spec.name}/")
            ):
                # Strip prefix if it exists to pass bare model name to OpenAI
                model = model.split("/", 1)[1]

        return model

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    async def _catalog_rows(self) -> list[Any]:
        client = self._client
        base_url = getattr(client, "base_url", None)
        if base_url and getattr(base_url, "host", None) == "generativelanguage.googleapis.com":
            return await self._gemini_catalog()
        res = await asyncio.wait_for(client.models.list(), timeout=4.0)
        return list(res.data)

    async def _gemini_catalog(self) -> list[dict[str, Any]]:
        # The OpenAI-compatible /models route on this host returns 400.
        key = str(getattr(self._client, "api_key", "") or "")
        if key.startswith("AIza"):
            return await self._gemini_public_catalog(key)
        return await self._gemini_cli_catalog(key)

    async def _gemini_public_catalog(self, key: str) -> list[dict[str, Any]]:
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key},
            )
            res.raise_for_status()
        rows: list[dict[str, Any]] = []
        for item in res.json().get("models") or []:
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            mid = str(item.get("name") or "").split("/")[-1]
            if mid:
                rows.append({"id": mid, "name": item.get("displayName") or mid})
        return rows

    async def _gemini_cli_catalog(self, key: str) -> list[dict[str, Any]]:
        import httpx

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            loaded = await client.post(
                "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
                headers=headers,
                json={
                    "metadata": {
                        "ideType": "IDE_UNSPECIFIED",
                        "platform": "PLATFORM_UNSPECIFIED",
                        "pluginType": "GEMINI",
                    }
                },
            )
            loaded.raise_for_status()
            project = str(loaded.json().get("cloudaicompanionProject") or "")
            res = await client.post(
                "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels",
                headers=headers,
                json={"project": project} if project else {},
            )
            res.raise_for_status()
        models = res.json().get("models") or {}
        rows: list[dict[str, Any]] = []
        if isinstance(models, dict):
            for mid, info in models.items():
                label = (info or {}).get("displayName") or str(mid)
                rows.append({"id": str(mid), "name": label})
        return rows

    async def get_available_models(self) -> list[dict[str, Any]]:
        try:
            rows = await self._catalog_rows()
            models = []
            for m in rows:
                if isinstance(m, dict):
                    mid = str(m.get("id") or "")
                    entry: dict[str, Any] = {"id": mid, "name": m.get("name") or mid}
                    supported = m.get("supported_parameters") or m.get("supported_params")
                else:
                    entry = {"id": m.id, "name": getattr(m, "name", m.id)}
                    supported = getattr(m, "supported_parameters", None) or getattr(
                        m, "supported_params", None
                    )
                if supported and isinstance(supported, list):
                    entry["supported_parameters"] = supported
                for field in (
                    "reasoning_efforts",
                    "supported_reasoning_efforts",
                    "supported_reasoning_levels",
                    "reasoning_levels",
                ):
                    levels = m.get(field) if isinstance(m, dict) else getattr(m, field, None)
                    if levels is not None:
                        entry[field] = levels
                models.append(entry)
            return models
        except Exception as e:
            logger.error("Failed to fetch models from OpenAI/compatible provider: {}", e)
            return []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        original_model = model or self.default_model
        resolved_model = self._resolve_model(original_model)

        # Use openai native schema for messages
        sanitized_messages = self._sanitize_empty_content(messages)

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": sanitized_messages,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }

        self._apply_model_overrides(original_model, kwargs)

        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(
                    content=f"Error calling LLM: {body.strip()[:500]}", finish_reason="error"
                )
            return LLMResponse(content=f"Error calling LLM: {e}", finish_reason="error")

    def _parse_response(self, response: Any) -> LLMResponse:
        if not response.choices:
            return LLMResponse(content="Error: API returned empty choices.", finish_reason="error")

        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json_repair.loads(args)
                    except Exception:
                        args = {"raw": args}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id or _short_tool_id(),
                        name=tc.function.name,
                        arguments=args,
                        provider_specific_fields=_extract_extra_fields(
                            tc,
                            {"id", "type", "function", "index"},
                        )
                        or None,
                        function_provider_specific_fields=_extract_extra_fields(
                            tc.function,
                            {"name", "arguments"},
                        )
                        or None,
                    )
                )

        u = getattr(response, "usage", None)
        usage = (
            {
                "prompt_tokens": u.prompt_tokens if u else 0,
                "completion_tokens": u.completion_tokens if u else 0,
                "total_tokens": u.total_tokens if u else 0,
            }
            if u
            else {}
        )

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=getattr(msg, "reasoning_content", None),
            reasoning_details=_extract_reasoning_details(msg),
        )

    def get_default_model(self) -> str:
        return self.default_model

    async def chat_streaming(
        self,
        messages: list[dict[str, Any]],
        on_token: Any = None,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Stream OpenAI response, calling on_token for each text delta."""
        original_model = model or self.default_model
        resolved_model = self._resolve_model(original_model)

        sanitized_messages = self._sanitize_empty_content(messages)

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": sanitized_messages,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
            "stream": True,
        }

        self._apply_model_overrides(original_model, kwargs)

        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            content_text = ""
            tool_call_chunks: dict[int, dict] = {}
            finish_reason = "stop"
            usage_data = {}
            reasoning_content = ""
            reasoning_details: list[dict[str, Any]] = []

            stream = await self._client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if not chunk.choices:
                    # Usage chunk at the end
                    u = getattr(chunk, "usage", None)
                    if u:
                        usage_data = {
                            "prompt_tokens": getattr(u, "prompt_tokens", 0),
                            "completion_tokens": getattr(u, "completion_tokens", 0),
                            "total_tokens": getattr(u, "total_tokens", 0),
                        }
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                # Content tokens
                if delta and delta.content:
                    content_text += delta.content
                    if on_token:
                        await on_token(delta.content)

                # Reasoning content (DeepSeek-R1 etc.)
                if delta and getattr(delta, "reasoning_content", None):
                    reasoning_content += delta.reasoning_content
                if delta:
                    delta_reasoning_details = _extract_reasoning_details(delta)
                    if delta_reasoning_details:
                        _merge_reasoning_details(reasoning_details, delta_reasoning_details)

                # Tool call deltas
                if delta and getattr(delta, "tool_calls", None):
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_chunks:
                            tool_call_chunks[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                                "provider_specific_fields": {},
                                "function_provider_specific_fields": {},
                            }
                        tc = tool_call_chunks[idx]
                        if tc_delta.id:
                            tc["id"] = tc_delta.id
                        tc["provider_specific_fields"].update(
                            _extract_extra_fields(tc_delta, {"id", "type", "function", "index"}),
                        )
                        if tc_delta.function:
                            tc["function_provider_specific_fields"].update(
                                _extract_extra_fields(tc_delta.function, {"name", "arguments"}),
                            )
                            if tc_delta.function.name:
                                tc["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                tc["arguments"] += tc_delta.function.arguments

            # Build tool calls from accumulated chunks
            tool_calls = []
            for idx in sorted(tool_call_chunks.keys()):
                tc = tool_call_chunks[idx]
                args = tc["arguments"]
                try:
                    args = json_repair.loads(args) if args else {}
                except Exception:
                    args = {"raw": args}
                tool_calls.append(
                    ToolCallRequest(
                        id=tc["id"] or _short_tool_id(),
                        name=tc["name"],
                        arguments=args,
                        provider_specific_fields=tc["provider_specific_fields"] or None,
                        function_provider_specific_fields=tc["function_provider_specific_fields"]
                        or None,
                    )
                )

            return LLMResponse(
                content=content_text or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage_data,
                reasoning_content=reasoning_content or None,
                reasoning_details=reasoning_details or None,
            )
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            err_msg = body.strip()[:500] if body and body.strip() else str(e)

            if content_text or tool_call_chunks or reasoning_content:
                # We have partial data, do not discard it. Assemble what we have.
                tool_calls = []
                for idx in sorted(tool_call_chunks.keys()):
                    tc = tool_call_chunks[idx]
                    args = tc["arguments"]
                    try:
                        args = json_repair.loads(args) if args else {}
                    except Exception:
                        args = {"raw": args}
                    tool_calls.append(
                        ToolCallRequest(
                            id=tc["id"] or _short_tool_id(),
                            name=tc["name"],
                            arguments=args,
                            provider_specific_fields=tc["provider_specific_fields"] or None,
                            function_provider_specific_fields=tc[
                                "function_provider_specific_fields"
                            ]
                            or None,
                        )
                    )

                final_content = content_text
                if final_content:
                    final_content += f"\n\n[Stream interrupted: {err_msg}]"
                elif not tool_calls:
                    final_content = f"Error calling LLM: {err_msg}"

                return LLMResponse(
                    content=final_content or None,
                    tool_calls=tool_calls,
                    finish_reason="error",
                    usage=usage_data,
                    reasoning_content=reasoning_content or None,
                    reasoning_details=reasoning_details or None,
                )
            else:
                return LLMResponse(content=f"Error calling LLM: {err_msg}", finish_reason="error")
