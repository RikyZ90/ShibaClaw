# Model integrations

Connect ShibaClaw's self-hosted AI agent to a local LLM or a cloud model provider. These integrations supply model inference; ShibaClaw supplies the WebUI, memory, tools, MCP connections and automations.

| Integration | Connection | Start here |
| --- | --- | --- |
| [OpenAI Codex](OPENAI_CODEX.md) | ChatGPT account OAuth through the Codex adapter | An account with eligible Codex access |
| [Claude](CLAUDE.md) | Native Anthropic SDK, plus an existing subscription OAuth adapter | Read the provider-policy and native startup caveats first |
| [GitHub Copilot](GITHUB_COPILOT.md) | GitHub device login and a Copilot endpoint bridge | An account with Copilot access; account limits apply |
| [OpenRouter](OPENROUTER.md) | API key or browser authorization that creates an API key | One account for multiple upstream model providers |
| [Ollama](OLLAMA.md) | Local OpenAI-compatible HTTP endpoint | A running Ollama server and a downloaded model |
| [Custom endpoint](CUSTOM.md) | OpenAI-compatible Chat Completions through CustomThinker | An API base URL, credentials and a supported model |

## Configure a provider and a model

1. [Install and start ShibaClaw](../../README.md), then open its authenticated WebUI.
2. For API keys, use **Settings → Providers**. For browser/device login, use **Settings → OAuth** and the integration's instructions.
3. In **Settings → Agent**, select the provider and an available model, then save. Authentication alone does not select the model.
4. Send a short message in the WebUI, or run `shibaclaw agent "Say hello in one sentence."` using the same ShibaClaw installation and user account. This invokes the configured provider and can consume its allowance or incur charges.

The examples on these pages are partial configuration snippets to merge into `~/.shibaclaw/config.json`; preserve the rest of your configuration. On Windows, `~` means your user profile. Replace `MODEL_ID_FROM_PICKER` with an ID returned for your account. Use the WebUI for secrets rather than placing them in example JSON or source control. Restart a CLI/server process after editing its configuration manually.

Provider names in configuration use underscores, such as `openai_codex` and `github_copilot`; the corresponding CLI login commands accept hyphens. An explicit provider selection avoids ambiguous automatic matching when several providers are configured.

## Credentials, privacy and limits

- Cloud integrations send the model's conversation context, which can include retrieved memory, tool definitions and tool results, to the selected service. Self-hosting ShibaClaw does not make cloud inference local.
- Provider API keys entered through the current settings flow use ShibaClaw's credential manager. OAuth storage differs: the Copilot bridge uses a local token file, Claude compatibility code shares Claude's credentials file, and Codex uses `oauth-cli-kit` storage. Do not assume every provider credential is in the encrypted vault.
- Protect the WebUI token, credential files and backups. Redact tokens, authorization codes and callback URLs before sharing logs. Disconnecting in ShibaClaw removes local access as described on each page; revoke authorization at the provider if you need to invalidate the remote credential.
- Model availability, billing, subscription eligibility, context size and tool support belong to the provider/model. OAuth does not grant unlimited or universally free use. Agent tool loops, sub-agents and automations can make multiple model requests for one user task.
- A configured status confirms locally available credentials, not a successful request or permission to use every listed model.

Implementation and provider-policy references were checked on **2026-10-24**. Provider policies and model catalogs can change; the linked official documentation takes precedence for account eligibility and billing.

[Back to the main README](../../README.md)
