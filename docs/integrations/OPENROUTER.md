# OpenRouter

Connect ShibaClaw to multiple cloud model providers through OpenRouter's OpenAI-compatible API. The gateway preserves model namespaces such as `anthropic/...` and `google/...`; tool calling and streaming depend on the selected model and upstream provider.

## Requirements and authentication

- An OpenRouter account and access to the selected model, with credits when the model requires payment.
- Outbound access to OpenRouter. Browser authorization also needs a callback URL that your browser can reach.
- Either an OpenRouter API key or browser authorization through the WebUI.

OpenRouter's [PKCE authorization flow](https://openrouter.ai/docs/guides/overview/auth/oauth) returns an account-linked API key; it does not grant a separate subscription allowance. Requests use that account's credits and limits.

## Setup

Choose one authentication method:

- **Browser:** open **Settings → OAuth → OpenRouter → Login**, authorize in the browser and return to ShibaClaw. The server exchanges the code and saves the returned API key through its credential manager.
- **API key:** enter a key in **Settings → Providers → OpenRouter → API Key** and save. The provider also reads the server's `OPENROUTER_API_KEY` environment variable when no key is supplied by settings.

Then open **Settings → Agent**, select **OpenRouter**, choose an ID from the available models and save. A partial non-secret configuration is:

```json
{
  "agents": {
    "defaults": {
      "provider": "openrouter",
      "model": "MODEL_ID_FROM_PICKER"
    }
  },
  "providers": {
    "openrouter": {
      "apiBase": "https://openrouter.ai/api/v1"
    }
  }
}
```

Keep the publisher namespace in the selected model ID. For example, a returned `anthropic/...` ID remains an OpenRouter model when the explicit provider is `openrouter`.

Send a short WebUI message, or run `shibaclaw agent "Say hello in one sentence."`. This makes a model request using your account.

### Browser callbacks and reverse proxies

The callback uses the current WebUI origin and port, followed by `/api/oauth/openrouter/callback/...`; `localhost:3000` is the usual WebUI address, not a separate OAuth-only listener. Complete login within the five-minute flow timeout.

If the browser reaches ShibaClaw through a reverse proxy, set the following in the **server environment before startup**, using the browser-reachable WebUI origin:

```text
SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-webui.example
```

Forward the callback path to the same running ShibaClaw instance. The value must be an absolute HTTP(S) URL. If a remote server advertises `localhost`, the browser interprets that as the browser's own machine; configure the correct origin instead. An API key avoids the browser callback requirement.

## Limits and security

- Free model variants have request caps, and model availability can change. Paid models consume credits; key budgets and upstream rate limits also apply. Consult [OpenRouter's current limits](https://openrouter.ai/docs/api_reference/limits) instead of assuming that a `:free` model is unlimited or permanently available.
- OpenRouter and the selected upstream provider receive the model context. Review the routing/data policies appropriate to your account before sending sensitive information.
- Protect the returned key as an API credential. Use a restricted key budget where appropriate, keep callback URLs/codes private and use HTTPS for a remotely accessed WebUI.
- **Settings → OAuth → Disconnect** removes the stored OpenRouter key and OAuth entry. If `OPENROUTER_API_KEY` remains in the server environment, remove it and restart; the WebUI reports this requirement. Local disconnect does not promise provider-side key revocation.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Browser cannot return to ShibaClaw | Check the callback origin, proxy routing and the URL shown by the active flow. Restart login after correcting the server environment. |
| Callback expired or does not match | Use one fresh login flow; callbacks depend on in-memory flow/PKCE state and do not survive a server restart. |
| Login succeeds but model is wrong | Select OpenRouter explicitly and save the desired model in Agent settings; login does not choose a model. |
| 401 / insufficient credits or budget / 429 | Check the key, account balance, key budget and current provider limits; honor retry/reset information. |
| Tools fail with a model that chats normally | Choose an available model/upstream supporting tool calling; basic text generation alone does not establish agent-tool compatibility. |

Checked against [provider metadata](../../shibaclaw/thinkers/registry.py), [PKCE/key persistence](../../shibaclaw/webui/oauth_github.py), [OAuth tests](../../tests/test_webui_oauth.py) and [disconnect tests](../../tests/test_oauth_disconnect_persistence.py) on **2026-10-24**. No live key or paid inference request was used.

[All integrations](README.md) · [Main README](../../README.md)
