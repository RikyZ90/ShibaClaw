# Ollama

Run ShibaClaw with a local LLM served by Ollama. ShibaClaw uses its OpenAI-compatible provider adapter, so configure Ollama's `/v1` endpoint explicitly. A local model can supply inference for the WebUI, memory-assisted conversations, tools and automations without a cloud model API key.

## Requirements and authentication

- [Install Ollama](https://ollama.com/download), run its server and download a model that fits your RAM/VRAM.
- ShibaClaw must be able to reach the server from its own process or container.
- Choose a model with tool support for agent tasks. The small `llama3.2:3b` model below is an initial connectivity example, not a recommendation for every workload; its [official model page](https://ollama.com/library/llama3.2) lists tool support.

The [local OpenAI-compatible endpoint](https://docs.ollama.com/api/openai-compatibility) does not require a real API key; Ollama ignores the compatibility key value. ShibaClaw supplies a placeholder when no key is set. Remote proxies and Ollama's cloud service can have different authentication and billing requirements.

## Setup

1. With Ollama running, download and confirm the example model:

   ```sh
   ollama pull llama3.2:3b
   ollama list
   ```

   If no Ollama server is running, start it with `ollama serve` in a separate terminal. Do not start a second server if the desktop application already serves port 11434.

2. In **Settings → Providers → Ollama**, set **API Base URL** to `http://localhost:11434/v1`. Leave the API key empty for a standard local server.
3. In **Settings → Agent**, select **Ollama**, choose `ollama/llama3.2:3b` and save. A partial file-based configuration is:

   ```json
   {
     "agents": {
       "defaults": {
         "provider": "ollama",
         "model": "ollama/llama3.2:3b"
       }
     },
     "providers": {
       "ollama": {
         "apiBase": "http://localhost:11434/v1"
       }
     }
   }
   ```

   The `ollama/` prefix identifies the ShibaClaw provider; the adapter sends `llama3.2:3b` to Ollama. Although registry metadata contains a bare `http://localhost:11434` default, this adapter does not append `/v1`; set the full compatibility base shown above.

4. Send a short WebUI message, or run:

   ```sh
   shibaclaw agent "Say hello in one sentence."
   ```

### Docker or another host

Inside a ShibaClaw container, `localhost` refers to that container. For Ollama on a Windows/macOS Docker Desktop host, use `http://host.docker.internal:11434/v1`. On native Linux, use a reachable host address or a Docker host-gateway mapping; do not assume the bridge gateway is always the same IP.

Ollama must listen on an interface reachable by that container, and firewall/proxy rules must permit the connection. Use the [official networking guidance](https://docs.ollama.com/faq) when changing its listener. If both services share a Docker network, use the Ollama service name and port instead.

## Limits and privacy

- Performance depends on model size, quantization, hardware and concurrency. A small model that answers a greeting may still struggle with long context, tool selection or multi-step tasks.
- Match ShibaClaw's `agents.defaults.contextWindowTokens` to the context actually configured in Ollama, not just the model's advertised maximum. Changing ShibaClaw's budget does not change Ollama's server/model context allocation.
- Inference stays on your machine only when the selected model is local. Ollama also supports cloud models; [its FAQ](https://docs.ollama.com/faq) explains local-only mode. Separately, enabled ShibaClaw web tools, MCP servers, channels or cloud embedding services can make network requests.
- A standard local Ollama endpoint has no authentication. Keep it on trusted interfaces or protect it with network controls/authentication rather than publishing port 11434 openly. Model licenses still apply.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Connection refused | Confirm Ollama is running and the configured address is reachable from ShibaClaw's process/container. |
| HTTP 404 on chat/model discovery | Check the API base includes `/v1`, and that the model tag appears in `ollama list`. |
| Model not found | Pull the exact tag; `llama3.2`, `llama3.2:3b` and another quantization/tag must match the server's installed IDs. |
| Text works, tools fail | Use a model with tool support and verify the installed Ollama version supports the required compatibility features. |
| Slow responses, out-of-memory or truncated context | Check RAM/VRAM, choose a smaller model, reduce concurrent tasks and align context settings with Ollama's allocation. |

Checked against [provider construction](../../shibaclaw/cli/base.py), [the OpenAI-compatible adapter](../../shibaclaw/thinkers/openai_provider.py), [prefix handling](../../shibaclaw/thinkers/base.py) and Ollama's official documentation on **2026-10-24**. No local Ollama server, model download or hardware performance test was run for this documentation change.

[All integrations](README.md) · [Main README](../../README.md)
