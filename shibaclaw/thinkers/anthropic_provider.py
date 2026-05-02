"""Anthropic native provider implementation using the official anthropic SDK."""

import os
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from shibaclaw.thinkers.base import LLMResponse, Thinker, ToolCallRequest


class AnthropicThinker(Thinker):
    """
    Thinker using the native anthropic SDK for claude-* models.
    Supports prompt caching, unified tool formats, and advanced Anthropic features.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "claude-3-7-sonnet-20250219",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        self._client = AsyncAnthropic(
            api_key=resolved_key or "no-key",
            base_url=api_base or None,
            default_headers=extra_headers,
        )

    def _convert_messages(self, messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Convert standard messages to Anthropic's format and extract system prompt."""
        system_prompt = ""
        anthropic_messages = []

        for idx, msg in enumerate(messages):
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                # Anthropic handles system prompt at the top level
                if isinstance(content, str):
                    system_prompt += content + "\n\n"
                elif isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "text":
                            system_prompt += blk.get("text", "") + "\n\n"
                        elif isinstance(blk, str):
                            system_prompt += blk + "\n\n"

            elif role == "user":
                if isinstance(content, str):
                    anthropic_messages.append(
                        {"role": "user", "content": [{"type": "text", "text": content}]}
                    )
                elif isinstance(content, list):
                    # Extract image blocks assuming formatting is standard
                    new_content = []
                    for blk in content:
                        if isinstance(blk, dict):
                            if blk.get("type") == "text":
                                new_content.append({"type": "text", "text": blk.get("text", "")})
                            elif blk.get("type") == "image_url":
                                url = blk.get("image_url", {}).get("url", "")
                                if url.startswith("data:image"):
                                    # Assuming standard base64 data uri format
                                    meta, b64 = url.split(",", 1)
                                    mime = meta.split(":")[1].split(";")[0]
                                    new_content.append(
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": mime,
                                                "data": b64,
                                            },
                                        }
                                    )
                            else:
                                new_content.append(blk)
                        elif isinstance(blk, str):
                            new_content.append({"type": "text", "text": blk})
                    anthropic_messages.append({"role": "user", "content": new_content})

            elif role == "assistant":
                new_content = []
                if isinstance(content, str) and content:
                    new_content.append({"type": "text", "text": content})

                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    new_content.append(
                        {
                            "type": "tool_use",
                            "id": getattr(tc, "id", None) or tc.get("id"),
                            "name": tc["function"]["name"]
                            if isinstance(tc, dict)
                            else tc.function.name,
                            "input": getattr(tc.function, "arguments", None)
                            if not isinstance(tc, dict)
                            else (tc["function"].get("arguments") or {}),
                        }
                    )
                if new_content:
                    anthropic_messages.append({"role": "assistant", "content": new_content})

            elif role == "tool":
                result = str(content) if not isinstance(content, str) else content
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id"),
                                "content": result,
                            }
                        ],
                    }
                )

        return system_prompt.strip(), anthropic_messages

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI tool schema to Anthropic tool schema."""
        anthropic_tools = []
        for t in tools:
            fn = t.get("function")
            if fn:
                anthropic_tools.append(
                    {
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                    }
                )
        return anthropic_tools

    async def get_available_models(self) -> list[dict[str, str]]:
        try:
            res = await self._client.models.list()
            return [{"id": m.id, "name": m.display_name or m.id} for m in res.data]
        except Exception as e:
            logger.error("Failed to fetch models from Anthropic: {}", e)
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

        model = self._strip_provider_prefix(model or self.default_model, "anthropic")
        system_prompt, anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max(1, max_tokens),
            "messages": anthropic_messages,
            "temperature": temperature,
        }

        if system_prompt:
            kwargs["system"] = [
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ]

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await self._client.messages.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(content=f"Error calling Anthropic: {e}", finish_reason="error")

    def _parse_response(self, response: Any) -> LLMResponse:
        content_text = ""
        tool_calls = []
        thinking_blocks = []

        for blk in response.content:
            if blk.type == "text":
                content_text += blk.text
            elif blk.type == "tool_use":
                tool_calls.append(ToolCallRequest(id=blk.id, name=blk.name, arguments=blk.input))
            elif blk.type == "thinking":
                thinking_blocks.append({"type": "thinking", "text": blk.thinking})

        u = getattr(response, "usage", None)
        usage_data = {}
        if u:
            usage_data = {
                "prompt_tokens": getattr(u, "input_tokens", 0),
                "completion_tokens": getattr(u, "output_tokens", 0),
                "total_tokens": getattr(u, "input_tokens", 0) + getattr(u, "output_tokens", 0),
            }

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            usage=usage_data,
            thinking_blocks=thinking_blocks if thinking_blocks else None,
            finish_reason=response.stop_reason or "stop",
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
        """Stream Anthropic response, calling on_token for each text delta."""
        model = self._strip_provider_prefix(model or self.default_model, "anthropic")
        system_prompt, anthropic_messages = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max(1, max_tokens),
            "messages": anthropic_messages,
            "temperature": temperature,
        }

        if system_prompt:
            kwargs["system"] = [
                {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
            ]

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            content_text = ""
            tool_calls = []
            thinking_blocks = []
            usage_data = {}

            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text") and delta.text:
                            content_text += delta.text
                            if on_token:
                                await on_token(delta.text)
                        elif hasattr(delta, "thinking") and delta.thinking:
                            pass  # thinking deltas handled by on_progress in agent loop

                # Collect final message
                final = await stream.get_final_message()
                # Re-parse to get tool calls and structured data
                content_text = ""
                tool_calls = []
                thinking_blocks = []
                for blk in final.content:
                    if blk.type == "text":
                        content_text += blk.text
                    elif blk.type == "tool_use":
                        tool_calls.append(
                            ToolCallRequest(
                                id=blk.id,
                                name=blk.name,
                                arguments=blk.input,
                            )
                        )
                    elif blk.type == "thinking":
                        thinking_blocks.append({"type": "thinking", "text": blk.thinking})

                u = getattr(final, "usage", None)
                if u:
                    usage_data = {
                        "prompt_tokens": getattr(u, "input_tokens", 0),
                        "completion_tokens": getattr(u, "output_tokens", 0),
                        "total_tokens": getattr(u, "input_tokens", 0)
                        + getattr(u, "output_tokens", 0),
                    }

            return LLMResponse(
                content=content_text or None,
                tool_calls=tool_calls,
                usage=usage_data,
                thinking_blocks=thinking_blocks if thinking_blocks else None,
                finish_reason=final.stop_reason or "stop",
            )
        except Exception as e:
            return LLMResponse(content=f"Error calling Anthropic: {e}", finish_reason="error")
