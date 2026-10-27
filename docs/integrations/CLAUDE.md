# Claude / Anthropic

ShibaClaw has a native Anthropic SDK adapter for Claude text generation, streaming and tool use. It also contains a Claude subscription OAuth compatibility flow. These are different authentication paths, and neither implies that a Claude subscription includes unrestricted third-party API use.

## Choose an access path

Anthropic's [current authentication policy](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account) recommends API keys for third-party tools. Any permitted subscription access through third-party tools can be conditional and charged to usage credits; identity misrepresentation and routing third-party traffic against subscription limits are prohibited. This repository's subscription flow reuses Claude Code's public OAuth client and client-identification headers. Its presence is not evidence of Anthropic approval for ShibaClaw. Use a provider-authorized API route rather than treating subscription OAuth as a way around billing or restrictions.

The shared provider factory accepts an Anthropic API key without requiring an OAuth login. Independent Anthropic endpoints use the native adapter and keep their credentials separate. Local regression tests cover startup and model routing; they do not establish connectivity or account access to Anthropic's live service.

## Native configuration and authentication

1. Create a Claude Console API key with the necessary account/billing access, following the [official API prerequisites](https://platform.claude.com/docs/en/api/overview).
2. Choose **Settings → Provider → Anthropic +**, enter the API key and click **Save endpoint**. Existing legacy configurations also read the server's `ANTHROPIC_API_KEY` environment variable; independent endpoint instances use their own key.
3. In **Settings → Agent**, choose a Claude model from that endpoint, or type a model ID and choose the corresponding **Use** option. Keep the normal API base unless you deliberately operate a compatible endpoint. An existing legacy configuration can use:

   ```json
   {
     "agents": {
       "defaults": {
         "provider": "anthropic",
         "model": "anthropic/MODEL_ID_FROM_PICKER"
       }
     }
   }
   ```

4. After confirming the provider starts, send a short WebUI message, or use `shibaclaw agent "Summarize your capabilities in two sentences."`. API use is billed by the selected provider.

The existing subscription compatibility flow is exposed at **Settings → OAuth → Claude → Login** and `shibaclaw provider login anthropic`. It opens `claude.ai`, requests authorization and expects the complete returned `code#state` value; it checks the state before exchanging the code. Documenting this implementation is not a recommendation to use it without provider authorization.

## Storage, limits and security

- API credentials entered through settings use the credential manager. Subscription compatibility credentials are written to `~/.claude/.credentials.json` under `claudeAiOauth`, outside ShibaClaw's vault. The file can also be used by Claude Code under the same OS account.
- The OAuth adapter attempts token refresh from that file. **Settings → OAuth → Claude → Disconnect** removes its `claudeAiOauth` entry, which can also affect another application sharing that login. Other file entries are preserved.
- Models, context limits, reasoning options and tool support vary. Configure only capabilities supported by the selected model and your account; a model-list failure does not prove that a named model is available.
- Your model context is sent to Anthropic or the gateway you select. Keep credentials and authorization codes private, and use provider-side revocation when remote access must be invalidated.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| API key saved, provider still “not configured” | The native factory limitation above can cause this. Report the behavior with the installed version and redacted logs; use an authorized gateway route while it remains unresolved. |
| Code rejected by subscription compatibility flow | It expects the complete value including `#` and the state from that same active login. Do not mix codes between login attempts. |
| 401/403 or subscription login rejected | Check provider eligibility and policy. Do not change identity headers or copy unrelated tokens to bypass rejection. |
| Usage/rate-limit error | Check the Console or gateway's allowance and billing; a web subscription does not automatically provide API credit. |
| Disconnect changes Claude Code's login | Both can use the same `~/.claude/.credentials.json`; reconnect only in an application authorized for that account. |

Checked against [the native adapter](../../shibaclaw/thinkers/anthropic_provider.py), [provider factory](../../shibaclaw/cli/base.py), [subscription flow](../../shibaclaw/cli/subscription_oauth.py) and [isolated subscription tests](../../tests/test_subscription_oauth.py) on **2026-10-24**. No live Claude account was used to verify eligibility or billing.

[All integrations](README.md) · [Main README](../../README.md)
