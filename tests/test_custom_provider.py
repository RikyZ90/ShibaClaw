"""Custom endpoint contracts through the real SDK, without network or credentials."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from shibaclaw.thinkers import openai_provider
from shibaclaw.thinkers.custom_provider import CustomThinker

MESSAGES = [{"role": "user", "content": "What is the weather in Rome?"}]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Read weather",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }
]
USAGE = {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}


@pytest.fixture
def custom_endpoint(monkeypatch):
    """Inject only HTTP transport; keep CustomThinker construction and SDK parsing."""
    requests = []
    responses = []

    def handle(request):
        requests.append(request)
        assert responses, "Unexpected extra request (including retries)"
        return responses.pop(0)

    def client(**kwargs):
        return AsyncOpenAI(
            **kwargs,
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
        )

    monkeypatch.setattr(openai_provider, "AsyncOpenAI", client)
    thinker = CustomThinker(
        api_key="fixture-key",
        api_base="https://llm.example.test/v1",
        default_model="fixture-model",
    )
    return thinker, requests, responses


def stream_response(deltas, finish_reason="stop", usage=None):
    chunks = [
        {
            "id": "fixture",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "fixture-model",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        for delta in deltas
    ]
    chunks.append(
        {**chunks[0], "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]}
    )
    if usage is not None:
        chunks.append({**chunks[0], "choices": [], "usage": usage})
    data = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=data + "data: [DONE]\n\n",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("usage", [None, USAGE])
async def test_custom_stream_text_and_optional_terminal_usage(custom_endpoint, usage):
    thinker, requests, responses = custom_endpoint
    responses.append(stream_response([{"content": "Hello"}, {"content": "!"}], usage=usage))
    tokens = []

    async def on_token(token):
        tokens.append(token)

    try:
        result = await thinker.chat_streaming(MESSAGES, on_token=on_token)
    finally:
        await thinker._client.close()

    assert result.content == "Hello!"
    assert tokens == ["Hello", "!"]
    assert result.finish_reason == "stop"
    assert result.usage == (usage or {})
    assert len(requests) == 1
    assert str(requests[0].url) == "https://llm.example.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer fixture-key"
    body = json.loads(requests[0].content)
    assert body["model"] == "fixture-model"
    assert body["stream"] is True
    # The public CustomThinker path currently has no include_usage opt-in.
    assert "stream_options" not in body
    assert "reasoning_effort" not in body


@pytest.mark.asyncio
async def test_custom_stream_tools_reasoning_and_followup_history(custom_endpoint):
    thinker, requests, responses = custom_endpoint
    details = [{"type": "reasoning.encrypted", "id": "r1", "data": "opaque-fixture"}]
    responses.append(
        stream_response(
            [
                {"reasoning_content": "Check ", "reasoning_details": details},
                {
                    "reasoning_content": "weather.",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "weather", "arguments": '{"city":'},
                        }
                    ],
                },
                {"tool_calls": [{"index": 0, "function": {"arguments": '"Rome"}'}}]},
            ],
            finish_reason="tool_calls",
            usage=USAGE,
        )
    )
    responses.append(
        httpx.Response(
            200,
            json={
                "id": "followup",
                "object": "chat.completion",
                "created": 1,
                "model": "fixture-model",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "It is sunny."},
                    }
                ],
                "usage": USAGE,
            },
        )
    )
    try:
        result = await thinker.chat_streaming(MESSAGES, tools=TOOLS)
        assert result.finish_reason == "tool_calls"
        assert result.content is None
        assert result.reasoning_content == "Check weather."
        assert result.reasoning_details == details
        assert result.usage == USAGE
        assert len(result.tool_calls) == 1
        call = result.tool_calls[0]
        assert (call.id, call.name, call.arguments) == ("call_1", "weather", {"city": "Rome"})
        assistant = {
            "role": "assistant",
            "content": None,
            "tool_calls": [call.to_openai_tool_call()],
            "reasoning_content": result.reasoning_content,
            "reasoning_details": result.reasoning_details,
        }
        tool_result = {"role": "tool", "tool_call_id": call.id, "content": "sunny"}
        followup = await thinker.chat([*MESSAGES, assistant, tool_result], tools=TOOLS)
    finally:
        await thinker._client.close()

    assert followup.content == "It is sunny."
    assert followup.usage == USAGE
    assert len(requests) == 2
    assert json.loads(requests[0].content)["tools"] == TOOLS
    history = json.loads(requests[1].content)["messages"]
    assert history == [*MESSAGES, assistant, tool_result]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    "status,message,extra",
    [
        (400, "Unsupported parameter: reasoning_effort", {"reasoning_effort": "low"}),
        (401, "Invalid API key", {}),
    ],
)
async def test_custom_endpoint_errors_are_reported_without_silent_fallback(
    custom_endpoint,
    streaming,
    status,
    message,
    extra,
):
    thinker, requests, responses = custom_endpoint
    responses.append(httpx.Response(status, json={"error": {"message": message}}))
    try:
        method = thinker.chat_streaming if streaming else thinker.chat
        result = await method(MESSAGES, **extra)
    finally:
        await thinker._client.close()

    assert result.finish_reason == "error"
    assert message in result.content
    assert result.tool_calls == []
    assert len(requests) == 1
    if extra:
        assert json.loads(requests[0].content)["reasoning_effort"] == "low"
