from types import SimpleNamespace
import asyncio

from shibaclaw.thinkers.openai_provider import OpenAIThinker


def test_parse_response_preserves_provider_specific_tool_call_fields():
    thinker = object.__new__(OpenAIThinker)
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="default_api:list_dir",
            arguments='{"path": "/tmp"}',
            model_extra={"vendor_field": "nested-extra"},
        ),
        model_extra={
            "thought_signature": "sig-123",
            "provider_field": "top-extra",
        },
    )
    msg = SimpleNamespace(content=None, tool_calls=[tool_call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=None,
    )

    parsed = OpenAIThinker._parse_response(thinker, response)

    assert len(parsed.tool_calls) == 1
    serialized = parsed.tool_calls[0].to_openai_tool_call()
    assert serialized["thought_signature"] == "sig-123"
    assert serialized["provider_field"] == "top-extra"
    assert serialized["function"]["vendor_field"] == "nested-extra"


def test_tool_call_serialization_flattens_extra_fields():
    thinker = object.__new__(OpenAIThinker)
    tool_call = SimpleNamespace(
        id="call_2",
        function=SimpleNamespace(
            name="default_api:list_dir",
            arguments='{"path": "/Users"}',
        ),
        model_extra={"thought_signature": "sig-456"},
    )
    msg = SimpleNamespace(content=None, tool_calls=[tool_call])
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")],
        usage=None,
    )

    serialized = OpenAIThinker._parse_response(thinker, response).tool_calls[0].to_openai_tool_call()

    assert "provider_specific_fields" not in serialized
    assert "function" in serialized
    assert serialized["thought_signature"] == "sig-456"


def test_chat_streaming_preserves_provider_specific_tool_call_fields():
    class FakeStream:
        def __init__(self, chunks):
            self._chunks = chunks

        def __aiter__(self):
            self._iter = iter(self._chunks)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    class FakeCompletions:
        def __init__(self, chunks):
            self._chunks = chunks

        async def create(self, **kwargs):
            return FakeStream(self._chunks)

    thinker = object.__new__(OpenAIThinker)
    thinker.default_model = "gemini-3.1-flash-lite-preview"
    thinker._gateway = None
    thinker._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions([
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason=None,
                            delta=SimpleNamespace(
                                content=None,
                                reasoning_content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id="call_stream_1",
                                        function=SimpleNamespace(
                                            name="default_api:list_dir",
                                            arguments='{"path": "/tmp"}',
                                            model_extra={"vendor_field": "nested-extra"},
                                        ),
                                        model_extra={"thought_signature": "sig-stream"},
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            finish_reason="tool_calls",
                            delta=SimpleNamespace(
                                content=None,
                                reasoning_content=None,
                                tool_calls=None,
                            ),
                        ),
                    ],
                ),
            ]),
        ),
    )

    response = asyncio.run(
        OpenAIThinker.chat_streaming(
            thinker,
            messages=[{"role": "user", "content": "hi"}],
        ),
    )

    assert len(response.tool_calls) == 1
    serialized = response.tool_calls[0].to_openai_tool_call()
    assert serialized["thought_signature"] == "sig-stream"
    assert serialized["function"]["vendor_field"] == "nested-extra"
