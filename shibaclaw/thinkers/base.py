"""Base LLM provider interface."""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]
    provider_specific_fields: dict[str, Any] | None = None
    function_provider_specific_fields: dict[str, Any] | None = None

    def to_openai_tool_call(self) -> dict[str, Any]:
        """Serialize to an OpenAI-style tool_call payload.

        Provider-specific fields are merged back into the original OpenAI-compatible
        shape instead of being nested under an internal wrapper key. This lets
        transports like Gemini's OpenAI compatibility layer receive required fields
        such as `thought_signature` exactly where they were originally emitted.
        """
        tool_call = {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }
        if self.provider_specific_fields:
            tool_call.update(self.provider_specific_fields)
        if self.function_provider_specific_fields:
            tool_call["function"].update(self.function_provider_specific_fields)
        return tool_call


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 etc.
    reasoning_details: list[dict[str, Any]] | None = None  # OpenRouter/Gemini signatures.
    thinking_blocks: list[dict] | None = None  # Anthropic extended thinking

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass(frozen=True)
class GenerationSettings:
    """Default generation parameters for LLM calls.

    Stored on the provider so every call site inherits the same defaults
    without having to pass temperature / max_tokens / reasoning_effort
    through every layer.  Individual call sites can still override by
    passing explicit keyword arguments to chat() / chat_with_retry().
    """

    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: str | None = None


class Thinker(ABC):
    """
    Abstract base class for thinkers (LLM providers).

    Implementations should handle the specifics of each provider's API
    while maintaining a consistent interface.
    """

    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = (
        "408",
        "429",
        "rate limit",
        "500",
        "502",
        "503",
        "504",
        "overloaded",
        "timeout",
        "timed out",
        "connection",
        "server error",
        "temporarily unavailable",
        "sse stream",
        "json error",
        "empty choices",
    )
    _PERMANENT_ERROR_MARKERS = (
        "400",
        "401",
        "403",
        "invalid_api_key",
        "api_key_invalid",
        "unauthorized",
        "forbidden",
        "permission_denied",
        "model_not_found",
        "unknown_model",
        "invalid_model",
        "context_length_exceeded",
        "max_context_length",
        "token_limit_exceeded",
        "invalid_request_error",
        "bad_request",
    )

    _SENTINEL = object()
    _RESPONSE_CACHE: dict[str, LLMResponse] = {}
    _RESPONSE_CACHE_MAX = 8

    @classmethod
    def _remember_response(
        cls,
        messages: list[dict[str, Any]],
        model: str | None,
        response: LLMResponse,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> None:
        """Keep successful text replies for outages; never replay executable actions."""
        if response.finish_reason == "error" or response.tool_calls:
            return
        key = cls._get_cache_key(messages, model, tools, tool_choice)
        cls._RESPONSE_CACHE[key] = response
        while len(cls._RESPONSE_CACHE) > cls._RESPONSE_CACHE_MAX:
            cls._RESPONSE_CACHE.pop(next(iter(cls._RESPONSE_CACHE)))

    @classmethod
    def _recall_cached(
        cls,
        messages: list[dict[str, Any]],
        model: str | None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse | None:
        key = cls._get_cache_key(messages, model, tools, tool_choice)
        cached = cls._RESPONSE_CACHE.get(key)
        if cached is None:
            return None
        if cached.tool_calls:
            return None
        import copy
        recalled = copy.deepcopy(cached)
        if recalled.content:
            recalled.content += "\n\n[WARNING: This is a cached response returned due to LLM provider outage.]"
        return recalled

    @classmethod
    def _get_cache_key(
        cls,
        messages: list[dict[str, Any]],
        model: str | None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> str:
        # Tool IDs, arguments, results and provider reasoning/signature fields
        # are part of the request's identity, even when role/content match.
        tool_blob = json.dumps(
            {"tools": tools, "tool_choice": tool_choice},
            sort_keys=True,
            default=str,
        )
        return f"{model}:{tool_blob}:{json.dumps(messages, sort_keys=True, ensure_ascii=False)}"

    @staticmethod
    def _jitter_delay(base_delay: float) -> float:
        import random
        return base_delay / 2 + random.uniform(0, base_delay / 2)

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base
        self.generation: GenerationSettings = GenerationSettings()

    @staticmethod
    def _strip_provider_prefix(model: str | None, provider_name: str | None) -> str | None:
        """Strip an explicit leading provider prefix from a model identifier."""
        if not model or not provider_name or "/" not in model:
            return model
        prefix, rest = model.split("/", 1)
        if prefix.lower().replace("-", "_") == provider_name.lower().replace("-", "_"):
            return rest
        return model

    @staticmethod
    def _sanitize_empty_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize message content: fix empty blocks, strip internal _meta fields."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")
            
            if isinstance(content, str) and content and "_meta" not in msg:
                result.append(msg)
                continue

            if isinstance(content, str) and not content:
                clean = dict(msg)
                clean["content"] = None if (msg.get("role") == "assistant" and msg.get("tool_calls")) else "(empty)"
                result.append(clean)
                continue

            if isinstance(content, list):
                new_items: list[Any] = []
                changed = False
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") in ("text", "input_text", "output_text")
                        and not item.get("text")
                    ):
                        changed = True
                        continue
                    if isinstance(item, dict) and "_meta" in item:
                        new_items.append({k: v for k, v in item.items() if k != "_meta"})
                        changed = True
                    else:
                        new_items.append(item)
                if changed:
                    clean = dict(msg)
                    if new_items:
                        clean["content"] = new_items
                    elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                        clean["content"] = None
                    else:
                        clean["content"] = "(empty)"
                    result.append(clean)
                    continue

            if isinstance(content, dict):
                clean = dict(msg)
                clean["content"] = [content]
                result.append(clean)
                continue

            result.append(msg)
        return result

    @staticmethod
    def _sanitize_request_messages(
        messages: list[dict[str, Any]],
        allowed_keys: frozenset[str],
    ) -> list[dict[str, Any]]:
        """Keep only provider-safe message keys and normalize assistant content."""
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in allowed_keys}
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @abstractmethod
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
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier (provider-specific).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            tool_choice: Tool selection strategy ("auto", "required", or specific tool dict).

        Returns:
            LLMResponse with content and/or tool calls.
        """
        pass

    async def get_available_models(self) -> list[dict[str, str]]:
        """Fetch available models from the provider.
        
        Returns:
            list[dict[str, str]]: A list of models, each dict containing at least an 'id' key.
        """
        return []

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
        """Stream a chat completion, calling on_token(text_chunk) for each delta.

        Default implementation falls back to non-streaming chat().
        Providers override this to enable true token-by-token streaming.
        """
        response = await self.chat(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )
        if on_token and response.content and not response.has_tool_calls:
            await on_token(response.content)
        return response

    @classmethod
    def _is_permanent_error(cls, content: str | None) -> bool:
        err = (content or "").lower()
        return any(marker in err for marker in cls._PERMANENT_ERROR_MARKERS)

    @classmethod
    def _is_transient_error(cls, content: str | None) -> bool:
        if cls._is_permanent_error(content):
            return False
        err = (content or "").lower()
        return any(marker in err for marker in cls._TRANSIENT_ERROR_MARKERS)

    @staticmethod
    def _strip_image_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Replace image_url blocks with text placeholder. Returns None if no images found."""
        found = False
        result = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                new_content = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "image_url":
                        path = (b.get("_meta") or {}).get("path", "")
                        placeholder = f"[image: {path}]" if path else "[image omitted]"
                        new_content.append({"type": "text", "text": placeholder})
                        found = True
                    else:
                        new_content.append(b)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        return result if found else None

    _CHAT_TIMEOUT = 120  # seconds – safety net for hung LLM API calls

    async def _safe_chat(self, **kwargs: Any) -> LLMResponse:
        """Call chat() and convert unexpected exceptions to error responses."""
        try:
            return await asyncio.wait_for(
                self.chat(**kwargs), timeout=self._CHAT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return LLMResponse(
                content="Error calling LLM: request timed out",
                finish_reason="error",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("LLM Provider encountered an unexpected error")
            return LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = _SENTINEL,
        temperature: object = _SENTINEL,
        reasoning_effort: object = _SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
        log_transient_errors: bool = True,
        fallback_models: list[str] | None = None,
        origin_model: str | None = None,
    ) -> LLMResponse:
        """Call chat() with retry on transient provider failures.

        Parameters default to ``self.generation`` when not explicitly passed,
        so callers no longer need to thread temperature / max_tokens /
        reasoning_effort through every layer.
        """
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort

        kw: dict[str, Any] = dict(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )

        origin = model if origin_model is None else origin_model
        max_retries = len(self._CHAT_RETRY_DELAYS)
        for attempt in range(1, max_retries + 1):
            response = await self._safe_chat(**kw)

            if response.finish_reason != "error":
                self._remember_response(messages, model, response, tools, tool_choice)
                return response

            if not self._is_transient_error(response.content):
                err = (response.content or "").lower()
                if kw.get("reasoning_effort") and ("reasoning_effort" in err or "unsupported parameter" in err):
                    kw["reasoning_effort"] = None
                    continue
                stripped = self._strip_image_content(messages)
                if stripped is not None:
                    logger.warning("Non-transient LLM error with image content, retrying without images")
                    retried = await self._safe_chat(**{**kw, "messages": stripped})
                    self._remember_response(messages, model, retried, tools, tool_choice)
                    return retried
                return response

            base_delay = self._CHAT_RETRY_DELAYS[attempt - 1]
            delay = self._jitter_delay(base_delay)
            if log_transient_errors:
                logger.warning(
                    "LLM transient error (attempt {}/{}), retrying in {:.2f}s: {}",
                    attempt, max_retries, delay,
                    (response.content or "")[:120].lower(),
                )
            await asyncio.sleep(delay)
            if attempt == max_retries:
                break

        response = await self._safe_chat(**kw)
        if response.finish_reason != "error":
            self._remember_response(messages, model, response, tools, tool_choice)
            return response

        fallbacks = [m for m in (fallback_models or []) if m and m != model]
        if fallbacks:
            fallback = fallbacks[0]
            logger.warning("Primary model {} failed. Falling back to {}", model, fallback)
            kw_fallback = kw.copy()
            kw_fallback["model"] = fallback
            kw_fallback["fallback_models"] = fallbacks[1:]
            kw_fallback["origin_model"] = origin
            nxt = await self.chat_with_retry(**kw_fallback)
            if nxt.finish_reason != "error":
                return nxt
            response = nxt
        if origin_model is None:
            cached = self._recall_cached(messages, origin, tools, tool_choice)
            if cached is not None:
                logger.warning("LLM call failed completely. Falling back to cached response.")
                return cached
        return response

    async def chat_with_retry_streaming(
        self,
        messages: list[dict[str, Any]],
        on_token: Any = None,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = _SENTINEL,
        temperature: object = _SENTINEL,
        reasoning_effort: object = _SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
        fallback_models: list[str] | None = None,
        origin_model: str | None = None,
    ) -> LLMResponse:
        """Like chat_with_retry but uses streaming for the final response."""
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort

        kw: dict[str, Any] = dict(
            messages=messages, on_token=on_token, tools=tools,
            model=model, max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )

        origin = model if origin_model is None else origin_model
        max_retries = len(self._CHAT_RETRY_DELAYS)
        for attempt in range(1, max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self.chat_streaming(**kw), timeout=self._CHAT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                response = LLMResponse(
                    content="Error calling LLM: request timed out",
                    finish_reason="error",
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("LLM Provider encountered an unexpected error during streaming (attempt {})", attempt)
                response = LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

            if response.finish_reason != "error":
                self._remember_response(messages, model, response, tools, tool_choice)
                return response

            if not self._is_transient_error(response.content):
                err = (response.content or "").lower()
                if kw.get("reasoning_effort") and ("reasoning_effort" in err or "unsupported parameter" in err):
                    kw["reasoning_effort"] = None
                    continue
                return response

            base_delay = self._CHAT_RETRY_DELAYS[attempt - 1]
            delay = self._jitter_delay(base_delay)
            logger.warning(
                "LLM streaming transient error (attempt {}/{}), retrying in {:.2f}s: {}",
                attempt, max_retries, delay,
                (response.content or "")[:120].lower(),
            )
            await asyncio.sleep(delay)
            if attempt == max_retries:
                break

            err_lower = (response.content or "").lower()
            if "sse stream" in err_lower or "json error" in err_lower:
                logger.warning("Falling back to non-streaming due to SSE parser error")
                kw_chat = kw.copy()
                kw_chat.pop("on_token", None)
                kw_chat["fallback_models"] = fallback_models
                kw_chat["origin_model"] = origin
                response = await self.chat_with_retry(**kw_chat)
                if response.finish_reason == "error" and origin_model is None:
                    cached = self._recall_cached(messages, origin, tools, tool_choice)
                    if cached is not None:
                        logger.warning("LLM call failed after SSE fallback. Falling back to cached response.")
                        return cached
                return response

        # Final attempt
        try:
            response = await asyncio.wait_for(
                self.chat_streaming(**kw), timeout=self._CHAT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            response = LLMResponse(
                content="Error calling LLM: request timed out",
                finish_reason="error",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("LLM Provider encountered an unexpected error during final streaming attempt")
            response = LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

        if response.finish_reason != "error":
            self._remember_response(messages, model, response, tools, tool_choice)
            return response

        fallbacks = [m for m in (fallback_models or []) if m and m != model]
        if fallbacks:
            fallback = fallbacks[0]
            logger.warning("Primary model {} failed during streaming. Falling back to {}", model, fallback)
            kw_fallback = kw.copy()
            kw_fallback["model"] = fallback
            kw_fallback["fallback_models"] = fallbacks[1:]
            kw_fallback["origin_model"] = origin
            nxt = await self.chat_with_retry_streaming(**kw_fallback)
            if nxt.finish_reason != "error":
                return nxt
            response = nxt
        if origin_model is None:
            cached = self._recall_cached(messages, origin, tools, tool_choice)
            if cached is not None:
                logger.warning("LLM call failed completely during streaming. Falling back to cached response.")
                return cached
        return response

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
