# Custom OpenAI-compatible endpoints

Use the existing `CustomThinker` adapter for a server implementing OpenAI Chat Completions. Compatibility depends on the endpoint and selected model, especially for streaming, tools and optional reasoning fields.

## Configuration

1. In **Settings → Providers**, configure **Custom** with your endpoint's API base URL and credential. Use the compatibility base, such as `https://llm.example.com/v1`, rather than the full `/chat/completions` URL. The adapter does not append `/v1` for you.
2. In **Settings → Agent**, select **Custom** and a model supported by that endpoint. Model discovery uses its `/models` route; a successful catalog request alone does not verify chat or tool support.
3. Save and send a short message. Agent requests can consume the endpoint's allowance.

A partial configuration to merge into `~/.shibaclaw/config.json` is:

```json
{
  "agents": {
    "defaults": {
      "provider": "custom",
      "model": "MODEL_ID_FROM_PICKER"
    }
  },
  "providers": {
    "custom": {
      "apiBase": "https://llm.example.com/v1"
    }
  }
}
```

Replace the URL and model placeholder, enter credentials through the WebUI, and preserve the rest of your configuration. Restart the process after manually editing the file. From a container, `localhost` refers to that container, not your host machine.

For direct Python use, the corresponding constructor options are `CustomThinker(api_key=..., api_base=..., default_model=...)`. Keep real credentials out of source code and shared examples.

## Streaming and optional fields

- Text deltas are delivered to the async `on_token` callback. Streamed tool argument fragments are assembled into tool calls for the next turn.
- A final usage-only chunk with `choices: []` is accepted, including after the finish-reason chunk. If no usage-only chunk arrives, streamed usage remains empty; it is not estimated locally.
- The current public CustomThinker configuration and chat methods do **not** expose an `include_usage` toggle. For a model without registry overrides, the default request omits `stream_options`. An endpoint requiring `stream_options: {"include_usage": true}` will therefore not necessarily return streaming usage. Accepting usage chunks and requesting them are separate capabilities.
- `reasoning_content` and `reasoning_details` returned by compatible endpoints are retained in the response. When constructing history directly, preserve those assistant fields alongside tool calls before appending tool results. The adapter preserves them when serializing that history; this does not guarantee every server accepts them.
- Passing `reasoning_effort` sends it to the endpoint. If an endpoint rejects an optional field, the adapter reports `finish_reason="error"` with the server's error text; it does not silently remove that field and retry. Omit unsupported options in your calling code/configuration. Authentication failures are also reported as errors.

## Reproducible compatibility checks

Run these offline tests from a development installation:

```sh
pytest tests/test_custom_provider.py tests/test_openai_provider.py tests/test_thinker_base.py -q
```

The custom-provider tests use the real OpenAI SDK with an in-memory HTTP transport. They cover endpoint routing/authentication, text with and without terminal usage, fragmented tool calls, reasoning/history preservation, a tool-result follow-up, rejected optional fields and invalid credentials. They require no live endpoint or API key and do not certify a particular hosted service. No provider-specific production changes are needed for these fixtures.

See [CustomThinker](../../shibaclaw/thinkers/custom_provider.py), [the shared adapter](../../shibaclaw/thinkers/openai_provider.py), and [the tests](../../tests/test_custom_provider.py) for the exact behavior under test.

[All integrations](README.md) · [Main README](../../README.md)
