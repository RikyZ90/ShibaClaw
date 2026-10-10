import copy
import json

import pytest

from shibaclaw.thinkers.base import LLMResponse, Thinker, ToolCallRequest


def test_sanitize_empty_content_early_return():
    msg = {"role": "user", "content": "hello"}
    messages = [msg]
    sanitized = Thinker._sanitize_empty_content(messages)
    assert sanitized[0] is msg


def test_sanitize_empty_content_empty_string():
    messages = [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "tc1"}]},
        {"role": "assistant", "content": ""},
    ]
    sanitized = Thinker._sanitize_empty_content(messages)

    assert sanitized[0]["content"] == "(empty)"
    assert sanitized[1]["content"] is None
    assert sanitized[2]["content"] == "(empty)"


def test_sanitize_empty_content_list():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": ""},
                {"type": "image_url", "image_url": {"url": "data:image/png"}, "_meta": {"path": "test"}},
            ],
        }
    ]
    sanitized = Thinker._sanitize_empty_content(messages)

    content = sanitized[0]["content"]
    assert len(content) == 2
    assert content[0] == {"type": "text", "text": "hello"}
    assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/png"}}


def test_get_model_reasoning_efforts():
    from shibaclaw.thinkers.registry import get_model_reasoning_efforts

    # OpenAI o-series & Azure/OpenRouter deployments
    assert get_model_reasoning_efforts("o1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("openai/o1-mini") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("openai/o3-mini") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("azure/my-o1-deploy") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("azure/o3-mini-test") == ["low", "medium", "high"]

    # Anthropic
    assert get_model_reasoning_efforts("anthropic/claude-3.7-sonnet") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("claude-3-7-sonnet-20250219") == ["low", "medium", "high"]

    # Gemini
    assert get_model_reasoning_efforts("gemini-2.0-flash-thinking-exp") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("google/gemini-2.5-flash") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("google/gemini-3.6-flash") == ["low", "medium", "high"]

    # DeepSeek
    assert get_model_reasoning_efforts("deepseek/deepseek-r1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("deepseek/r1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("ollama/r1:8b") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("deepseek-reasoner") == ["low", "medium", "high"]

    # Qwen QwQ
    assert get_model_reasoning_efforts("qwen/qwq-32b") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("qwq-32b-preview") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("qwen/qvq-72b") == ["low", "medium", "high"]

    # Grok
    assert get_model_reasoning_efforts("xai/grok-3") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("grok-3-think") == ["low", "medium", "high"]

    # Kimi / Moonshot
    assert get_model_reasoning_efforts("moonshot/kimi-k1.5") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("kimi-k2") == ["low", "medium", "high"]

    # GLM
    assert get_model_reasoning_efforts("zhipu/glm-4-zero-preview") == ["low", "medium", "high"]

    # Open Reasoning
    assert get_model_reasoning_efforts("marco-o1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("sky-t1") == ["low", "medium", "high"]
    assert get_model_reasoning_efforts("smallthinker") == ["low", "medium", "high"]

    # Non-reasoning models return []
    assert get_model_reasoning_efforts("gpt-4o") == []
    assert get_model_reasoning_efforts("claude-3-5-sonnet") == []
    assert get_model_reasoning_efforts("gemini-1.5-pro") == []
    assert get_model_reasoning_efforts("") == []


class _Scripted(Thinker):
    def __init__(self, replies: list[LLMResponse]):
        super().__init__()
        self.replies = list(replies)
        self.models: list[str | None] = []

    async def chat(self, **kwargs):
        self.models.append(kwargs.get("model"))
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]

    async def chat_streaming(self, **kwargs):
        return await self.chat(**kwargs)

    def get_default_model(self) -> str:
        return "primary"


@pytest.fixture(autouse=True)
def _clear_response_cache():
    Thinker._RESPONSE_CACHE.clear()
    yield
    Thinker._RESPONSE_CACHE.clear()


async def _no_sleep(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_permanent_error_does_not_retry(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 401 unauthorized", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    result = await chat(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert result.finish_reason == "error"
    assert thinker.models == ["primary"]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_transient_error_retries_and_caches_first_success(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 429 rate limit", finish_reason="error"),
        LLMResponse(content="ok", finish_reason="stop"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    result = await chat(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert result.content == "ok"
    assert len(Thinker._RESPONSE_CACHE) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_omitted_fallback_does_not_switch_model(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    thinker = _Scripted([
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    await chat(
        messages=[{"role": "user", "content": "hi"}],
        model="primary",
    )
    assert set(thinker.models) == {"primary"}


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_cache_does_not_return_tool_calls_when_tools_disabled(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    tool_reply = LLMResponse(
        content=None,
        tool_calls=[ToolCallRequest(id="1", name="exec", arguments={})],
        finish_reason="stop",
    )
    thinker = _Scripted([
        tool_reply,
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    messages = [{"role": "user", "content": "run"}]
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    await chat(messages=messages, model="primary", tools=[{"type": "function"}])
    result = await chat(
        messages=messages,
        model="primary",
        tools=None,
        tool_choice="none",
    )
    assert not result.tool_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_exhausted_fallback_uses_primary_cache(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    messages = [{"role": "user", "content": "same"}]
    thinker = _Scripted([
        LLMResponse(content="cached-primary", finish_reason="stop"),
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    await chat(messages=messages, model="primary")
    result = await chat(
        messages=messages,
        model="primary",
        fallback_models=["other"],
    )
    assert "cached-primary" in (result.content or "")


_TOOLS = [{
    "type": "function",
    "function": {"name": "exec", "parameters": {"type": "object"}},
}]
_OUTAGE_WARNING = "\n\n[WARNING: This is a cached response returned due to LLM provider outage.]"


def _tool_history(report="report-A", call_id="copy-A"):
    return [
        {"role": "system", "content": "Archive only the report that was copied."},
        {"role": "user", "content": "archive the report"},
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": call_id, "type": "function", "function": {
                "name": "exec",
                "arguments": json.dumps({"command": f"copy {report} archive"}),
            },
        }]},
        {"role": "tool", "tool_call_id": call_id, "name": "exec", "content": "Success"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("history_change", [
    "arguments", "call_id", "tool_name", "result_id", "result_name",
    "thought_signature", "reasoning_details", "thinking_blocks", "message_name",
])
async def test_outage_cache_does_not_cross_semantic_histories(monkeypatch, streaming, history_change):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    messages = _tool_history()
    other = copy.deepcopy(messages)
    call = other[2]["tool_calls"][0]
    if history_change == "arguments":
        call["function"]["arguments"] = json.dumps({"command": "copy report-B archive"})
    elif history_change == "call_id":
        call["id"] = "copy-B"
        other[3]["tool_call_id"] = "copy-B"
    elif history_change == "tool_name":
        call["function"]["name"] = "copy_file"
    elif history_change == "result_id":
        other[3]["tool_call_id"] = "different-result"
    elif history_change == "result_name":
        other[3]["name"] = "copy_file"
    elif history_change == "thought_signature":
        call["thought_signature"] = "provider-signature-B"
    elif history_change == "reasoning_details":
        other[2]["reasoning_details"] = [{"type": "reasoning.encrypted", "data": "reasoning-B"}]
    elif history_change == "thinking_blocks":
        other[2]["thinking_blocks"] = [{"type": "thinking", "thinking": "report-B", "signature": "B"}]
    elif history_change == "message_name":
        other[1]["name"] = "different-user"
    assert [(m["role"], m.get("content")) for m in messages] == [
        (m["role"], m.get("content")) for m in other
    ]
    thinker = _Scripted([
        LLMResponse(content="Archived report-A"),
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    await chat(messages=messages, model="primary", tools=_TOOLS)
    result = await chat(messages=other, model="primary", tools=_TOOLS)
    assert result.finish_reason == "error"
    assert not result.tool_calls
    assert len(thinker.models) == 5  # Initial success, then all four outage attempts.


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_live_tool_response_is_returned_but_never_replayed_from_cache(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    messages = _tool_history()
    tool_reply = LLMResponse(
        content="Archive the report",
        finish_reason="tool_calls",
        tool_calls=[ToolCallRequest(id="delete-A", name="exec", arguments={"command": "delete report-A"})],
    )
    thinker = _Scripted([
        tool_reply,
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    live = await chat(messages=messages, model="primary", tools=_TOOLS)
    assert live is tool_reply
    assert live.tool_calls[0].arguments == {"command": "delete report-A"}
    assert not Thinker._RESPONSE_CACHE

    # Also reject unsafe entries populated before the policy change or mutated by callers.
    Thinker._RESPONSE_CACHE[Thinker._get_cache_key(messages, "primary", _TOOLS)] = tool_reply
    result = await chat(messages=messages, model="primary", tools=_TOOLS)
    assert result.finish_reason == "error"
    assert not result.tool_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_exact_tool_history_can_recover_text_without_replaying_actions(monkeypatch, streaming):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    messages = _tool_history()
    cached_reply = LLMResponse(content="Archived report-A")
    thinker = _Scripted([
        cached_reply,
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    chat = thinker.chat_with_retry_streaming if streaming else thinker.chat_with_retry
    await chat(messages=messages, model="primary", tools=_TOOLS)
    result = await chat(messages=copy.deepcopy(messages), model="primary", tools=_TOOLS)
    assert result.content == "Archived report-A" + _OUTAGE_WARNING
    assert not result.tool_calls
    assert cached_reply.content == "Archived report-A"


class _SSEScripted(_Scripted):
    def __init__(self, replies, streaming_replies=None):
        super().__init__(replies)
        self.streaming_replies = list(streaming_replies or [
            LLMResponse(content="Error SSE stream parser", finish_reason="error"),
        ])
        self.streaming_models = []

    async def chat_streaming(self, **kwargs):
        self.streaming_models.append(kwargs.get("model"))
        if len(self.streaming_replies) > 1:
            return self.streaming_replies.pop(0)
        return self.streaming_replies[0]


def _record_retry_delays(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("asyncio.sleep", record_sleep)
    monkeypatch.setattr(Thinker, "_jitter_delay", staticmethod(lambda delay: delay))
    return delays


@pytest.mark.asyncio
async def test_sse_to_nonstream_outage_recovers_exact_cached_text(monkeypatch):
    delays = _record_retry_delays(monkeypatch)
    messages = _tool_history()
    thinker = _SSEScripted([
        LLMResponse(content="Exact cached answer"),
        LLMResponse(content="Error 503 overloaded", finish_reason="error"),
    ])
    await thinker.chat_with_retry(messages=messages, model="primary", tools=_TOOLS)
    result = await thinker.chat_with_retry_streaming(messages=messages, model="primary", tools=_TOOLS)
    assert result.content == "Exact cached answer" + _OUTAGE_WARNING
    assert result.finish_reason == "stop"
    assert not result.tool_calls
    assert thinker.streaming_models == ["primary"]
    assert thinker.models == ["primary"] * 5
    assert delays == [1, 1, 2, 4]


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback_succeeds", [False, True])
async def test_sse_fallback_models_are_tried_before_primary_cache(monkeypatch, fallback_succeeds):
    delays = _record_retry_delays(monkeypatch)
    messages = [{"role": "user", "content": "same"}]
    error = LLMResponse(content="Error 503 overloaded", finish_reason="error")
    final = LLMResponse(content="Fresh fallback answer") if fallback_succeeds else error
    thinker = _SSEScripted([LLMResponse(content="Primary cached answer"), *([error] * 4), final])
    await thinker.chat_with_retry(messages=messages, model="primary")
    # A child's own cache must not interrupt the remaining configured fallback chain.
    Thinker._remember_response(messages, "backup", LLMResponse(content="Backup cached answer"))
    result = await thinker.chat_with_retry_streaming(
        messages=messages, model="primary", fallback_models=["primary", "", "backup"],
    )
    expected = "Fresh fallback answer" if fallback_succeeds else "Primary cached answer" + _OUTAGE_WARNING
    assert result.content == expected
    assert thinker.streaming_models == ["primary"]
    assert thinker.models == ["primary"] * 5 + ["backup"] * (1 if fallback_succeeds else 4)
    assert delays == [1, 1, 2, 4] + ([] if fallback_succeeds else [1, 2, 4])


@pytest.mark.asyncio
async def test_sse_failure_inside_fallback_leaves_cache_lookup_to_outer_call(monkeypatch):
    delays = _record_retry_delays(monkeypatch)
    messages = [{"role": "user", "content": "same"}]
    error = LLMResponse(content="Error 503 overloaded", finish_reason="error")
    sse_error = LLMResponse(content="Error SSE stream parser", finish_reason="error")
    thinker = _SSEScripted([LLMResponse(content="Primary cached answer"), error], [*([error] * 4), sse_error])
    await thinker.chat_with_retry(messages=messages, model="primary")
    Thinker._remember_response(messages, "backup", LLMResponse(content="Backup cached answer"))
    result = await thinker.chat_with_retry_streaming(
        messages=messages, model="primary", fallback_models=["backup"],
    )
    assert result.content == "Primary cached answer" + _OUTAGE_WARNING
    assert thinker.streaming_models == ["primary"] * 4 + ["backup"]
    assert thinker.models == ["primary"] + ["backup"] * 4
    assert delays == [1, 2, 4, 1, 1, 2, 4]

