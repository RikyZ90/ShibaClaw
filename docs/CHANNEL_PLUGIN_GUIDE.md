# Channel Plugin Guide

Build a custom shibaclaw channel in three steps: subclass, package, install.

## How It Works

shibaclaw discovers channel plugins via Python [entry points](https://packaging.python.org/en/latest/specifications/entry-points/). When `shibaclaw gateway` starts, it scans:

1. Built-in channels in `shibaclaw/channels/`
2. External packages registered under the `shibaclaw.integrations` entry point group

If a matching config section has `"enabled": true`, the channel is instantiated and started.

## Quick Start

We'll build a minimal webhook channel that receives messages via HTTP POST and sends replies back.

### Project Structure

```
shibaclaw-channel-webhook/
├── shibaclaw_channel_webhook/
│   ├── __init__.py          # re-export WebhookChannel
│   └── channel.py           # channel implementation
└── pyproject.toml
```

### 1. Create Your Channel

```python
# shibaclaw_channel_webhook/__init__.py
from shibaclaw_channel_webhook.channel import WebhookChannel

__all__ = ["WebhookChannel"]
```

```python
# shibaclaw_channel_webhook/channel.py
import asyncio
from typing import Any

from aiohttp import web
from loguru import logger

from shibaclaw.integrations.base import BaseChannel
from shibaclaw.bus.events import OutboundMessage


class WebhookChannel(BaseChannel):
    name = "webhook"
    display_name = "Webhook"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return {"enabled": False, "port": 9000, "allowFrom": []}

    async def start(self) -> None:
        """Start an HTTP server that listens for incoming messages.

        IMPORTANT: start() must block forever (or until stop() is called).
        If it returns, the channel is considered dead.
        """
        self._running = True
        port = self.config.get("port", 9000)

        app = web.Application()
        app.router.add_post("/message", self._on_request)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("Webhook listening on :{}", port)

        # Block until stopped
        while self._running:
            await asyncio.sleep(1)

        await runner.cleanup()

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        """Deliver an outbound message.

        msg.content  — markdown text (convert to platform format as needed)
        msg.media    — list of local file paths to attach
        msg.chat_id  — the recipient (same chat_id you passed to _handle_message)
        msg.metadata — may contain "_progress": True for streaming chunks
        """
        logger.info("[webhook] -> {}: {}", msg.chat_id, msg.content[:80])
        # In a real plugin: POST to a callback URL, send via SDK, etc.

    async def _on_request(self, request: web.Request) -> web.Response:
        """Handle an incoming HTTP POST."""
        body = await request.json()
        sender = body.get("sender", "unknown")
        chat_id = body.get("chat_id", sender)
        text = body.get("text", "")
        media = body.get("media", [])       # list of URLs

        # This is the key call: validates allowFrom, then puts the
        # message onto the bus for the agent to process.
        await self._handle_message(
            sender_id=sender,
            chat_id=chat_id,
            content=text,
            media=media,
        )

        return web.json_response({"ok": True})
```

### 2. Register the Entry Point

```toml
# pyproject.toml
[project]
name = "shibaclaw-channel-webhook"
version = "0.1.0"
dependencies = ["shibaclaw", "aiohttp"]

[project.entry-points."shibaclaw.integrations"]
webhook = "shibaclaw_channel_webhook:WebhookChannel"

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends._legacy:_Backend"
```

The key (`webhook`) becomes the config section name. The value points to your `BaseChannel` subclass.

### 3. Install & Configure

```bash
pip install -e .
shibaclaw plugins list      # verify "Webhook" shows as "plugin"
shibaclaw onboard           # auto-adds default config for detected plugins
```

Edit `~/.shibaclaw/config.json`:

```json
{
  "channels": {
    "webhook": {
      "enabled": true,
      "port": 9000,
      "allowFrom": ["*"]
    }
  }
}
```

### 4. Run & Test

```bash
shibaclaw gateway
```

In another terminal:

```bash
curl -X POST http://localhost:9000/message \
  -H "Content-Type: application/json" \
  -d '{"sender": "user1", "chat_id": "user1", "text": "Hello!"}'
```

The agent receives the message and processes it. Replies arrive in your `send()` method.

## BaseChannel API

### Required (abstract)

| Method | Description |
|--------|-------------|
| `async start()` | **Must block forever.** Connect to platform, listen for messages, call `_handle_message()` on each. If this returns, the channel is dead. |
| `async stop()` | Set `self._running = False` and clean up. Called when gateway shuts down. |
| `async send(msg: OutboundMessage)` | Deliver an outbound message to the platform. |

### Provided by Base

| Method / Property | Description |
|-------------------|-------------|
| `_handle_message(sender_id, chat_id, content, media?, metadata?, session_key?)` | **Call this when you receive a message.** Checks `is_allowed()`, then publishes to the bus. |
| `is_allowed(sender_id)` | Checks against `config["allowFrom"]`; `"*"` allows all, `[]` denies all. |
| `default_config()` (classmethod) | Returns default config dict for `shibaclaw onboard`. Override to declare your fields. |
| `transcribe_audio(file_path)` | Transcribes audio via Groq Whisper (if configured). |
| `is_running` | Returns `self._running`. |

### Message Types

```python
@dataclass
class OutboundMessage:
    channel: str        # your channel name
    chat_id: str        # recipient (same value you passed to _handle_message)
    content: str        # markdown text — convert to platform format as needed
    media: list[str]    # local file paths to attach (images, audio, docs)
    metadata: dict      # may contain: "_progress" (bool) for streaming chunks,
                        #              "message_id" for reply threading
```

## Config

Your channel receives config as a plain `dict`. Access fields with `.get()`:

```python
async def start(self) -> None:
    port = self.config.get("port", 9000)
    token = self.config.get("token", "")
```

`allowFrom` is handled automatically by `_handle_message()` — you don't need to check it yourself.

Override `default_config()` so `shibaclaw onboard` auto-populates `config.json`:

```python
@classmethod
def default_config(cls) -> dict[str, Any]:
    return {"enabled": False, "port": 9000, "allowFrom": []}
```

If not overridden, the base class returns `{"enabled": false}`.

## Naming Convention

| What | Format | Example |
|------|--------|---------|
| PyPI package | `shibaclaw-channel-{name}` | `shibaclaw-channel-webhook` |
| Entry point key | `{name}` | `webhook` |
| Config section | `channels.{name}` | `channels.webhook` |
| Python package | `shibaclaw_channel_{name}` | `shibaclaw_channel_webhook` |

## Local Development

```bash
git clone https://github.com/you/shibaclaw-channel-webhook
cd shibaclaw-channel-webhook
pip install -e .
shibaclaw plugins list    # should show "Webhook" as "plugin"
shibaclaw gateway         # test end-to-end
```

## Verify

```bash
$ shibaclaw plugins list

  Name       Source    Enabled
  telegram   builtin  yes
  discord    builtin  no
  webhook    plugin   yes
```
