# GitHub Copilot

Use GitHub account authentication to connect ShibaClaw to its Copilot model bridge. The adapter exchanges a GitHub OAuth token for a short-lived Copilot session token, then uses an OpenAI-compatible endpoint for model discovery, chat, streaming and tool calls.

This is a repository-maintained bridge to Copilot endpoints, including an internal token endpoint. It is not the GitHub Models API or a public stability guarantee from GitHub.

## Requirements and authentication

- A GitHub account with Copilot access and any organization permissions required for that account.
- A browser for GitHub's device authorization and outbound access to GitHub/Copilot services.
- An available model supported by both the account and the bridge's chat endpoint.

GitHub documents [plan/client-dependent model availability](https://docs.github.com/en/copilot/reference/ai-models/supported-models) and [usage credits and rate limits](https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/usage-limits). OAuth does not provide unlimited premium models or guarantee zero additional cost. Check your account's current allowance and spending settings before running automated tasks.

## Setup

1. Open **Settings → OAuth → GitHub Copilot → Login**, or run:

   ```sh
   shibaclaw provider login github-copilot
   ```

2. Open the verification URL shown by ShibaClaw, enter the displayed device code and review the application/scopes before authorizing. Keep the login flow running while ShibaClaw polls for completion.
3. In **Settings → Agent**, choose **GitHub Copilot**, fetch/select a currently available model and save. Do not rely on an old model nickname copied from a README. A partial file-based configuration is:

   ```json
   {
     "agents": {
       "defaults": {
         "provider": "github_copilot",
         "model": "github_copilot/MODEL_ID_FROM_PICKER"
       }
     }
   }
   ```

4. Send a short WebUI message, or run:

   ```sh
   shibaclaw agent "Explain this project's purpose in two sentences."
   ```

The adapter refreshes its short-lived Copilot session token as needed. A revoked/expired underlying GitHub login still requires reauthorization.

## Storage, limits and security

- The device-flow token is stored in `~/.shibaclaw/github_copilot/access-token` as a local token file, outside the encrypted credential vault. Restrict access to that OS account and protect backups.
- The server can also read `GITHUB_COPILOT_TOKEN`; it takes precedence over the token file. Supply secrets through your service's environment/secret mechanism rather than sharing a shell command containing a real token.
- **Settings → OAuth → Disconnect** removes the local file. `shibaclaw provider logout github-copilot` also removes it. If an environment token is set, remove it from the server environment and restart; WebUI disconnect reports that requirement rather than claiming success.
- A model listed for an official IDE/client is not guaranteed to work through this bridge. Endpoint changes, organization policy, account limits and model retirement can interrupt access.
- Cloud requests include the context ShibaClaw sends. Review GitHub's applicable policies and account permissions before connecting sensitive workspaces. Revoke the authorized application at GitHub when remote authorization must be invalidated.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Device authorization expires | Start a new login and complete the new code promptly; an old code cannot complete the new flow. |
| GitHub login works, token exchange returns 401/403 | Confirm Copilot entitlement and organization restrictions for that same account; reauthorize if necessary. |
| Empty model picker or model rejected | Refresh model discovery after login and choose a returned ID. Official-client availability alone is insufficient. |
| Rate-limit or exhausted-allowance response | Check GitHub usage/budgets and wait for a reset or adjust authorized usage. Repeated logins do not reset limits. |
| Still configured after disconnect | Check `GITHUB_COPILOT_TOKEN` in the server environment and restart after removing it. |

Checked against [the provider](../../shibaclaw/thinkers/github_copilot_provider.py), [device flow](../../shibaclaw/webui/oauth_github.py) and [disconnect tests](../../tests/test_oauth_disconnect_persistence.py) on **2026-10-24**. Account entitlement and live endpoint compatibility were not tested.

[All integrations](README.md) · [Main README](../../README.md)
