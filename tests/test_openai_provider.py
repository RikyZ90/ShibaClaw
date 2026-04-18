from types import SimpleNamespace

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
