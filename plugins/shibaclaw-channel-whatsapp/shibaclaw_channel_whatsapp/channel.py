"""WhatsApp channel plugin using a Node.js bridge."""

import asyncio
import json
import mimetypes
from collections import OrderedDict
from typing import Any

from loguru import logger
from pydantic import Field

from shibaclaw.bus.events import OutboundMessage
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.schema import Base
from shibaclaw.integrations.base import BaseChannel


class WhatsAppConfig(Base):
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    bridge_token: str = ""
    allow_from: list[str] = Field(default_factory=list)

    def resolve_bridge_token(self) -> str:
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            cm = get_credential_manager()
            if cm.is_setup() or cm._store_path.exists():
                val = cm.get_secret("channels", "whatsapp.bridge_token")
                if val: return val
        except Exception: pass
        return self.bridge_token


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.

    The bridge uses @whiskeysockets/baileys to handle the WhatsApp Web protocol.
    Communication between Python and Node.js is via WebSocket.
    """

    name = "whatsapp"
    display_name = "WhatsApp"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return WhatsAppConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = WhatsAppConfig.model_validate(config)
        super().__init__(config, bus)
        self._ws = None
        self._connected = False
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()

    async def start(self) -> None:
        import websockets
        from urllib.parse import urlparse as _urlparse

        bridge_url = self.config.bridge_url

        try:
            _parsed = _urlparse(bridge_url)
            _host = (_parsed.hostname or "").lower()
            if _host not in ("localhost", "127.0.0.1", "::1", ""):
                logger.warning(
                    "⚠️  WhatsApp bridge_url ({}) is not on localhost. "
                    "The bridge_token is sent in cleartext — ensure the link is "
                    "encrypted or on a trusted private network.",
                    bridge_url,
                )
        except Exception:
            pass

        logger.info("Connecting to WhatsApp bridge at {}...", bridge_url)

        self._running = True

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    if self.config.resolve_bridge_token():
                        await ws.send(
                            json.dumps({"type": "auth", "token": self.config.resolve_bridge_token()})
                        )
                    self._connected = True
                    logger.info("Connected to WhatsApp bridge")

                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error("Error handling bridge message: {}", e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.warning("WhatsApp bridge connection error: {}", e)

                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        self._running = False
        self._connected = False

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        if not self._ws or not self._connected:
            logger.warning("WhatsApp bridge not connected")
            return

        chat_id = msg.chat_id
        if chat_id == "auto" or ("@" not in chat_id and not chat_id.isdigit()):
            allow_list = getattr(self.config, "allow_from", [])
            valid_ids = [uid for uid in allow_list if uid != "*"]
            if len(valid_ids) == 1:
                chat_id = valid_ids[0]
                if "@" not in chat_id:
                    chat_id = f"{chat_id}@s.whatsapp.net"
                logger.debug(
                    "Invalid chat_id '{}', falling back to allowed user {}", msg.chat_id, chat_id
                )
            elif len(valid_ids) > 1:
                logger.error(
                    "Invalid chat_id '{}'. Multiple allowed users, cannot auto-resolve.",
                    msg.chat_id,
                )
                return
            else:
                logger.error("Invalid chat_id: {}", msg.chat_id)
                return

        try:
            payload = {"type": "send", "to": chat_id, "text": msg.content}
            await self._ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.error("Error sending WhatsApp message: {}", e)

    async def _handle_bridge_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from bridge: {}", raw[:100])
            return

        msg_type = data.get("type")

        if msg_type == "message":
            # pn: old phone number style <phone>@s.whatsapp.net (deprecated)
            pn = data.get("pn", "")
            # sender: new LID style
            sender = data.get("sender", "")
            content = data.get("content", "")
            message_id = data.get("id", "")

            if message_id:
                if message_id in self._processed_message_ids:
                    return
                self._processed_message_ids[message_id] = None
                while len(self._processed_message_ids) > 1000:
                    self._processed_message_ids.popitem(last=False)

            user_id = pn if pn else sender
            sender_id = user_id.split("@")[0] if "@" in user_id else user_id
            logger.info("Sender {}", sender)

            if content == "[Voice Message]":
                logger.info(
                    "Voice message received from {}, but direct download from bridge is not yet supported.",
                    sender_id,
                )
                content = "[Voice Message: Transcription not available for WhatsApp yet]"

            media_paths = data.get("media") or []

            if media_paths:
                for p in media_paths:
                    mime, _ = mimetypes.guess_type(p)
                    media_type = "image" if mime and mime.startswith("image/") else "file"
                    media_tag = f"[{media_type}: {p}]"
                    content = f"{content}\n{media_tag}" if content else media_tag

            await self._handle_message(
                sender_id=sender_id,
                chat_id=sender,
                content=content,
                media=media_paths,
                metadata={
                    "message_id": message_id,
                    "timestamp": data.get("timestamp"),
                    "is_group": data.get("isGroup", False),
                },
            )

        elif msg_type == "status":
            status = data.get("status")
            logger.info("WhatsApp status: {}", status)

            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False

        elif msg_type == "qr":
            logger.info("Scan QR code in the bridge terminal to connect WhatsApp")

        elif msg_type == "error":
            logger.error("WhatsApp bridge error: {}", data.get("error"))
