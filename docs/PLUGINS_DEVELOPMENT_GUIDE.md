# ShibaClaw Plugin Development Guide

ShibaClaw supports dynamic, installable plugins to extend its capabilities. This guide explains how to create, test, and package custom plugins for both **Channels** and **TTS Engines**.

---

## Architecture Overview

ShibaClaw discovers external plugins dynamically using Python [entry points](https://packaging.python.org/en/latest/specifications/entry-points/). 

Plugins are packaged as standard Python packages and register themselves under specific entry point groups:
* `shibaclaw.integrations`: Custom communication channels (subclasses of `BaseChannel`).
* `shibaclaw.tts`: Custom Text-to-Speech engines (subclasses of `BaseTTS`).

---

## 🔌 1. Channel Plugins

A channel plugin handles communication with external chat platforms (e.g., Slack, Webhooks, custom APIs).

### Class Interface
To create a channel plugin, subclass `BaseChannel` from `shibaclaw.integrations.base`:

```python
import asyncio
from typing import Any
from shibaclaw.integrations.base import BaseChannel
from shibaclaw.bus.events import OutboundMessage

class CustomChannel(BaseChannel):
    name = "custom"
    display_name = "Custom Channel"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return {"enabled": False, "port": 9000, "allowFrom": []}

    async def start(self) -> None:
        self._running = True
        # Initialize listener or connection here.
        # This method MUST block or loop as long as the channel is running.
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        # Deliver message to external platform
        # msg.content contains the response string
        # msg.chat_id is the recipient identifier
        pass
```

### Receiving Messages
When your channel receives an incoming message, pass it to the ShibaClaw gateway using:
```python
await self._handle_message(
    sender_id=sender,
    chat_id=chat_id,
    content=text,
    media=media_paths, # Optional list of local file paths
)
```

---

## 🗣️ 2. TTS (Text-to-Speech) Plugins

A TTS plugin converts assistant text responses into spoken audio files.

### Class Interface
To create a TTS plugin, subclass `BaseTTS` from `shibaclaw.tts.base`:

```python
import asyncio
from pathlib import Path
from shibaclaw.tts.base import BaseTTS

class CustomTTS(BaseTTS):
    name = "custom_tts"
    display_name = "Custom Speech Synthesis"

    def __init__(self, config: dict):
        super().__init__(config)

    async def synthesize(self, text: str, output_path: Path) -> Path:
        # Convert text to audio and save to output_path.
        # Run synchronous speech generation inside an executor to avoid blocking the event loop:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._generate_audio, text, output_path)
        return output_path

    def _generate_audio(self, text: str, output_path: Path):
        # Implement actual audio synthesis here and write to output_path
        pass
```

---

## 📦 3. Packaging & Entry Points

To make your plugin discoverable, configure your `pyproject.toml` with the appropriate entry points.

### pyproject.toml Example

```toml
[project]
name = "shibaclaw-channel-custom"
version = "0.1.0"
dependencies = [
    "shibaclaw",
]

# For Channel integrations:
[project.entry-points."shibaclaw.integrations"]
custom = "shibaclaw_channel_custom.channel:CustomChannel"

# For TTS engines:
[project.entry-points."shibaclaw.tts"]
custom_tts = "shibaclaw_tts_custom.engine:CustomTTS"

[build-system]
requires = ["setuptools>=61.0.0"]
build-backend = "setuptools.build_meta"
```

---

## 🛠️ 4. Naming Conventions

To ensure security and compatibility, name your packages and entry points according to these rules:

| Plugin Type | PyPI/Git Package Name | Entry Point Key | Python Module Name |
| :--- | :--- | :--- | :--- |
| **Channel** | `shibaclaw-channel-{name}` | `{name}` | `shibaclaw_channel_{name}` |
| **TTS Engine** | `shibaclaw-tts-{name}` | `{name}` | `shibaclaw_tts_{name}` |

> [!IMPORTANT]
> The package name **must** start with `shibaclaw-` for the WebUI installation endpoints to allow installing or updating it.

---

## 🚀 5. Local Development Workflow

1. Clone or initialize your plugin project structure.
2. Install the plugin in editable mode in the ShibaClaw virtual environment:
   ```bash
   pip install -e .
   ```
3. Verify ShibaClaw detects your plugin:
   ```bash
   shibaclaw plugins list
   ```
4. If developing a channel, run the onboarding wizard to add default configurations to `config.json`:
   ```bash
   shibaclaw onboard
   ```
5. Launch the gateway to test your integration:
   ```bash
   shibaclaw gateway
   ```
