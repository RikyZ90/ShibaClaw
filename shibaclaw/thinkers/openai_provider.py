"""OpenAI-compatible provider implementation using the official openai SDK."""

import os
import secrets
import string
import uuid
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from shibaclaw.thinkers.base import Thinker, LLMResponse, ToolCallRequest
from shibaclaw.thinkers.registry import find_by_model, find_gateway, ProviderSpec

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
        
        # Detect gateway or specific config if present
        self._gateway = find_gateway(provider_name, api_key, api_base)
        
        # Determine actual key and base URL
        resolved_key = self._resolve_api_key(api_key, self._gateway, default_model)
        resolved_base = api_base or (self._gateway.default_api_base if self._gateway else None)
        
        # Stable session affinity for custom backends
        default_headers = {
            "x-session-affinity": uuid.uuid4().hex,
            **(extra_headers or {}),
        }
        
        if self._gateway and self._gateway.is_gateway:
            # Some gateways like OpenRouter recommend sending a referrer
            default_headers.setdefault("HTTP-Referer", "https://github.com/RikyZ90/ShibaClaw")
            default_headers.setdefault("X-Title", "ShibaClaw")
            
        logger.debug(f"OpenAIThinker init: api_key={'SET' if api_key else 'UNSET'} resolved_key={'SET' if resolved_key else 'UNSET'} base_url={resolved_base}")
            
        self._client = AsyncOpenAI(
            api_key=resolved_key or "no-key",
            base_url=resolved_base,
            default_headers=default_headers,
        )

    def _resolve_api_key(self, api_key: str | None, spec: ProviderSpec | None, model: str) -> str | None:
        """Resolve the API key from kwargs or environment variables."""
        if api_key:
            return api_key
        
        s = spec or find_by_model(model)
        if s and s.env_key:
            return os.environ.get(s.env_key)
        
        return None

    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying strip prefixes if needed."""
        # For pure OpenAI client, we don't need litellm_prefix logic!
        # Instead, we just need to respect `strip_model_prefix` if the gateway demands bare models.
        if self._gateway and self._gateway.strip_model_prefix:
            if "/" in model:
                model = model.split("/")[-1]
                
        # For non-gateway standard usage (e.g. hitting OpenAI directly)
        elif not self._gateway:
            spec = find_by_model(model)
            if spec and "/" in model and model.startswith(f"{spec.name}/"):
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
                return LLMResponse(content=f"Error calling LLM: {body.strip()[:500]}", finish_reason="error")
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
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id or _short_tool_id(),
                    name=tc.function.name,
                    arguments=args,
                    provider_specific_fields=_extract_extra_fields(
                        tc, {"id", "type", "function", "index"},
                    ) or None,
                    function_provider_specific_fields=_extract_extra_fields(
                        tc.function, {"name", "arguments"},
                    ) or None,
                ))

        u = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": u.prompt_tokens if u else 0,
            "completion_tokens": u.completion_tokens if u else 0,
            "total_tokens": u.total_tokens if u else 0,
        } if u else {}

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=getattr(msg, "reasoning_content", None),
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
                tool_calls.append(ToolCallRequest(
                    id=tc["id"] or _short_tool_id(),
                    name=tc["name"],
                    arguments=args,
                    provider_specific_fields=tc["provider_specific_fields"] or None,
                    function_provider_specific_fields=tc["function_provider_specific_fields"] or None,
                ))

            return LLMResponse(
                content=content_text or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage_data,
                reasoning_content=reasoning_content or None,
            )
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error calling LLM: {body.strip()[:500]}", finish_reason="error")
            return LLMResponse(content=f"Error calling LLM: {e}", finish_reason="error")
