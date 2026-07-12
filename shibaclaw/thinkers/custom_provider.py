"""Direct OpenAI-compatible provider — bypasses LiteLLM."""

from __future__ import annotations

import uuid
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from shibaclaw.thinkers.base import LLMResponse, Thinker, ToolCallRequest


class CustomThinker(Thinker):
    def __init__(
        self,
        api_key: str = "no-key",
        api_base: str = "http://localhost:8000/v1",
        default_model: str = "default",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        # Keep affinity stable for this provider instance to improve backend cache locality,
        # while still letting users attach provider-specific headers for custom gateways.
        default_headers = {
            "x-session-affinity": uuid.uuid4().hex,
            **(extra_headers or {}),
        }
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            default_headers=default_headers,
        )

    async def get_available_models(self) -> list[dict[str, str]]:
        try:
            res = await self._client.models.list()
            return [{"id": m.id, "name": getattr(m, "name", m.id)} for m in res.data]
        except Exception as e:
            logger.error("Failed to fetch models from custom provider: {}", e)
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
        resolved_model = self._strip_provider_prefix(model or self.default_model, "custom") or (model or self.default_model)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice=tool_choice or "auto")
        try:
            return self._parse(await self._client.chat.completions.create(**kwargs))
        except Exception as e:
            # JSONDecodeError.doc / APIError.response.text may carry the raw body
            # (e.g. "unsupported model: xxx") which is far more useful than the
            # generic "Expecting value …" message.  Truncate to avoid huge HTML pages.
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error: {body.strip()[:500]}", finish_reason="error")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

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
        resolved_model = self._strip_provider_prefix(model or self.default_model, "custom") or (model or self.default_model)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
            "stream": True,
        }
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs.update(tools=tools, tool_choice=tool_choice or "auto")
            
        try:
            stream = await self._client.chat.completions.create(**kwargs)
            content_text = ""
            reasoning_content = ""
            finish_reason = "stop"
            tool_call_chunks: dict[int, dict[str, Any]] = {}
            
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                    
                if getattr(delta, "content", None):
                    content_text += delta.content
                    if on_token:
                        await on_token(delta.content)
                        
                if getattr(delta, "reasoning_content", None):
                    reasoning_content += delta.reasoning_content
                    
                if getattr(delta, "tool_calls", None):
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_call_chunks:
                            tool_call_chunks[idx] = {"id": "", "name": "", "arguments": ""}
                        tc = tool_call_chunks[idx]
                        if getattr(tc_delta, "id", None):
                            tc["id"] = tc_delta.id
                        if tc_delta.function:
                            if getattr(tc_delta.function, "name", None):
                                tc["name"] += tc_delta.function.name
                            if getattr(tc_delta.function, "arguments", None):
                                tc["arguments"] += tc_delta.function.arguments
                                
            tool_calls = []
            for idx in sorted(tool_call_chunks.keys()):
                tc = tool_call_chunks[idx]
                args = tc["arguments"]
                if args:
                    try:
                        args = json_repair.loads(args)
                    except Exception:
                        args = {"raw": args}
                else:
                    args = {}
                tool_calls.append(ToolCallRequest(id=tc["id"], name=tc["name"], arguments=args))
                
            return LLMResponse(
                content=content_text or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                reasoning_content=reasoning_content or None
            )
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error: {body.strip()[:500]}", finish_reason="error")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def _parse(self, response: Any) -> LLMResponse:
        if not response.choices:
            return LLMResponse(
                content="Error: API returned empty choices. This may indicate a temporary service issue or an invalid model response.",
                finish_reason="error",
            )
        choice = response.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCallRequest(
                id=tc.id,
                name=tc.function.name,
                arguments=json_repair.loads(tc.function.arguments)
                if isinstance(tc.function.arguments, str)
                else tc.function.arguments,
            )
            for tc in (msg.tool_calls or [])
        ]
        u = response.usage
        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens,
            }
            if u
            else {},
            reasoning_content=getattr(msg, "reasoning_content", None) or None,
        )

    def get_default_model(self) -> str:
        return self.default_model
