# OpenAI Codex

Use a ChatGPT account with eligible Codex access as ShibaClaw's model provider. The adapter calls Codex's backend Responses endpoint and supports streamed text and tool calls. It does not run the Codex CLI or import that CLI's tools, plugins or workspace settings.

## Requirements and authentication

- A ShibaClaw installation with `oauth-cli-kit`, which is a declared project dependency.
- An account allowed to use Codex, a browser for sign-in and outbound access to OpenAI's authentication and Codex services.
- Access to a model returned by the account's Codex catalog.

This provider uses account OAuth, separate from an OpenAI Platform API key. OpenAI distinguishes ChatGPT subscription authentication from separately billed API-key access in its [authentication documentation](https://learn.chatgpt.com/docs/auth). This repository's adapter uses `oauth-cli-kit` and Codex backend endpoints; it is not an implementation of the newer Sign in with ChatGPT integration. Do not infer approval for hosted or commercial reuse from the presence of working OAuth code; review OpenAI's [current app integration guidance](https://learn.chatgpt.com/docs/app-server).

## Setup

1. Open **Settings → OAuth → OpenAI Codex → Login**, follow the browser instructions and complete any callback/code step shown. For a terminal installation, the equivalent command is:

   ```sh
   shibaclaw provider login openai-codex
   ```

2. Open **Settings → Agent**, select **OpenAI Codex** and choose a model returned after login. The adapter retrieves a versioned Codex catalog and filters hidden/internal entries; an empty or failed catalog is not replaced with guessed model IDs.
3. Save the settings. A partial file-based equivalent is:

   ```json
   {
     "agents": {
       "defaults": {
         "provider": "openai_codex",
         "model": "openai-codex/MODEL_ID_FROM_PICKER"
       }
     }
   }
   ```

4. Send a short WebUI message, or run:

   ```sh
   shibaclaw agent "Explain what you can help me with in two sentences."
   ```

## Limits and credential handling

- Codex access and usage allowances depend on your account and workspace. The adapter cannot turn account access into unrestricted API access or increase the provider's limits.
- A pre-existing file-based Codex CLI login can be imported by `oauth-cli-kit`. The CLI is optional; ShibaClaw's login command can authenticate directly. Credentials kept only in another application's OS keyring are not a guaranteed import path.
- Treat the library's local token cache and `~/.codex/auth.json`, when present, as secrets outside ShibaClaw's vault. Do not share or commit them. A service/container has its own home directory and does not automatically inherit the host user's login.
- **Settings → OAuth → Disconnect** or `shibaclaw provider logout openai-codex` removes ShibaClaw's cached login and prevents automatic CLI-token re-import until an explicit successful login. It preserves the external Codex CLI login.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing dependency | Repair/update the ShibaClaw environment using its original installation method; `oauth-cli-kit` must be installed in that same environment. |
| Login succeeds but no models appear | Check account/workspace access, network errors and the installed ShibaClaw version. The model catalog is gated by the adapter's client protocol version. |
| Authentication or token-refresh error | Use the explicit login command again under the user running ShibaClaw. For a remote server, complete the exact flow the server presents. |
| A model ID is rejected | Select an ID from the current Codex picker, including the `openai-codex/` prefix; OpenAI API model names are not interchangeable with Codex catalog entries. |
| Usage-limit response | Check the account's usage/reset information; repeated login does not reset usage. |

Checked against [the provider](../../shibaclaw/thinkers/openai_codex_provider.py), [login/logout handling](../../shibaclaw/security/codex_oauth.py), [catalog tests](../../tests/test_openai_codex_models.py) and [disconnect tests](../../tests/test_oauth_disconnect_persistence.py) on **2026-10-24**. These tests use isolated or mocked authentication; they do not establish access for a particular account.

[All integrations](README.md) · [Main README](../../README.md)
