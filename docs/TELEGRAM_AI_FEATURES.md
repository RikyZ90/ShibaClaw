# Telegram AI / Agent Features (Bot API 9.3–10.x)

ShibaClaw's Telegram channel supports the Bot API capabilities introduced for AI agents
in late 2025 / 2026. Enable or disable them under `channels.telegram` in `config.json`.

| Config key | Default | Feature |
|---|---|---|
| `streaming` | `true` | `sendMessageDraft` streaming in private chats |
| `guestMode` | `true` | Guest bots — reply when `@username` is used in any chat |
| `allowBotMessages` | `true` | Bot-to-bot messages (also enable in BotFather) |
| `businessEnabled` | `true` | Chat Automation / Business connection messages |
| `managedBotsEnabled` | `true` | Track Managed Bot create/token updates |

## BotFather / client setup

These flags alone are not enough — Telegram must allow the capability for your bot:

1. **Guest Mode** — enable Guest Mode for the bot (see [Telegram Guest Bots guide](https://core.telegram.org/bots/features#guest-bots)).
2. **Bot-to-bot** — enable bot-to-bot communication for both bots.
3. **Chat Automation** — users connect the bot under *Settings → Chat Automation*; the bot receives `business_connection` / `business_message` updates.
4. **Managed bots** — manager bots create child bots via the request-managed-bot keyboard flow; ShibaClaw records `managed_bot` updates (it does not auto-spawn unmanaged agents).

## Behaviour notes

- **Streaming drafts** work only in **private** chats (Telegram API constraint). Groups keep the existing progress-edit path.
- **Guest replies** use `answerGuestQuery` (not `sendMessage`). Guest turns get an isolated session key `telegram:guest:<query_id>`.
- **Rich Messages** (`sendRichMessage` / rich blocks) are **not** wired yet — `python-telegram-bot` 22.8 does not expose those methods. Planned when PTB adds them.

## Example config

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "allowFrom": ["*"],
      "streaming": true,
      "guestMode": true,
      "allowBotMessages": true,
      "businessEnabled": true,
      "managedBotsEnabled": true
    }
  }
}
```
