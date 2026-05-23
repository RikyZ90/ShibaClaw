"""Discord channel implementation using Discord Gateway websocket."""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
import websockets
from loguru import logger
from pydantic import Field

from shibaclaw.bus.events import OutboundMessage
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.paths import get_media_dir
from shibaclaw.config.schema import Base
from shibaclaw.helpers.helpers import split_message
from shibaclaw.integrations.base import BaseChannel

DISCORD_API_BASE = "https://discord.com/api/v10"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20MB
MAX_MESSAGE_LEN = 2000  # Discord message character limit
TYPING_INTERVAL_S = 8


@dataclass(slots=True)
class _StreamBuf:
    text: str = ""
    message_id: str | None = None
    last_edit: float = 0.0
    pending_text: str | None = None


class DiscordConfig(Base):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377
    group_policy: Literal["mention", "open"] = "mention"
    streaming: bool = True
    proxy: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None


class DiscordChannel(BaseChannel):
    """Discord channel using Gateway websocket."""

    name = "discord"
    display_name = "Discord"
    _STREAM_EDIT_INTERVAL = 0.8

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return DiscordConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = DiscordConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: DiscordConfig = config
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._seq: int | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._stream_bufs: dict[str, _StreamBuf] = {}
        self._http: httpx.AsyncClient | None = None
        self._bot_user_id: str | None = None

    async def start(self) -> None:
        """Start the Discord gateway connection."""
        if not self.config.token:
            logger.error("Discord bot token not configured")
            return

        self._running = True
        proxy_url = self._proxy_url()
        client_kwargs: dict[str, Any] = {"timeout": 30.0}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        self._http = httpx.AsyncClient(**client_kwargs)

        while self._running:
            try:
                logger.info("Connecting to Discord gateway...")
                connect_kwargs: dict[str, Any] = {}
                if proxy_url:
                    connect_kwargs["proxy"] = proxy_url
                async with websockets.connect(self.config.gateway_url, **connect_kwargs) as ws:
                    self._ws = ws
                    await self._gateway_loop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Discord gateway error: {}", e)
                if self._running:
                    logger.info("Reconnecting to Discord gateway in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the Discord channel."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()
        self._stream_bufs.clear()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._http:
            await self._http.aclose()
            self._http = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Discord REST API, including file attachments."""
        if not self._http:
            logger.warning("Discord HTTP client not initialized")
            return

        chat_id = str(msg.chat_id)
        url = f"{DISCORD_API_BASE}/channels/{chat_id}/messages"
        headers = {"Authorization": f"Bot {self.config.token}"}
        metadata = msg.metadata or {}
        is_progress = bool(metadata.get("_progress"))
        reply_to = self._reply_target(msg)

        try:
            if is_progress and self.config.streaming:
                await self._send_or_edit_progress(
                    chat_id, url, headers, msg.content or "", reply_to
                )
                return

            sent_media = False
            failed_media: list[str] = []
            next_reply_to = reply_to

            for media_path in msg.media or []:
                if await self._send_file(url, headers, media_path, reply_to=next_reply_to):
                    sent_media = True
                    next_reply_to = None
                else:
                    failed_media.append(Path(media_path).name)

            chunks = split_message(msg.content or "", MAX_MESSAGE_LEN)
            if not chunks and failed_media and not sent_media:
                chunks = split_message(
                    "\n".join(f"[attachment: {name} - send failed]" for name in failed_media),
                    MAX_MESSAGE_LEN,
                )

            progress = self._stream_bufs.pop(chat_id, None)
            if progress and progress.message_id:
                if chunks:
                    first_chunk = chunks.pop(0)
                    if await self._edit_message(chat_id, headers, progress.message_id, first_chunk):
                        next_reply_to = None
                    else:
                        chunks.insert(0, first_chunk)
                else:
                    await self._delete_message(chat_id, headers, progress.message_id)

            if not chunks:
                return

            for i, chunk in enumerate(chunks):
                payload: dict[str, Any] = {"content": chunk}

                if i == 0 and next_reply_to and not sent_media:
                    payload["message_reference"] = {"message_id": next_reply_to}
                    payload["allowed_mentions"] = {"replied_user": False}

                if await self._send_payload(url, headers, payload) is None:
                    break
                next_reply_to = None
        finally:
            if not is_progress:
                await self._stop_typing(chat_id)

    async def _send_payload(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send a single Discord API payload with retry on rate-limit."""
        for attempt in range(3):
            try:
                response = await self._http.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    logger.warning("Discord rate limited, retrying in {}s", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                if not response.content:
                    return {}
                try:
                    data = response.json()
                except ValueError:
                    return {}
                return data if isinstance(data, dict) else {}
            except Exception as e:
                if attempt == 2:
                    logger.error("Error sending Discord message: {}", e)
                else:
                    await asyncio.sleep(1)
        return None

    async def _edit_message(
        self,
        chat_id: str,
        headers: dict[str, str],
        message_id: str,
        content: str,
    ) -> bool:
        text = split_message(content, MAX_MESSAGE_LEN)[0] if content else ""
        if not text:
            return False
        url = f"{DISCORD_API_BASE}/channels/{chat_id}/messages/{message_id}"
        for attempt in range(3):
            try:
                response = await self._http.patch(url, headers=headers, json={"content": text})
                if response.status_code == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    logger.warning("Discord rate limited, retrying in {}s", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return True
            except Exception as e:
                if attempt == 2:
                    logger.error("Error editing Discord message {}: {}", message_id, e)
                else:
                    await asyncio.sleep(1)
        return False

    async def _delete_message(
        self,
        chat_id: str,
        headers: dict[str, str],
        message_id: str,
    ) -> bool:
        url = f"{DISCORD_API_BASE}/channels/{chat_id}/messages/{message_id}"
        for attempt in range(3):
            try:
                response = await self._http.delete(url, headers=headers)
                if response.status_code == 429:
                    data = response.json()
                    retry_after = float(data.get("retry_after", 1.0))
                    logger.warning("Discord rate limited, retrying in {}s", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                return True
            except Exception as e:
                if attempt == 2:
                    logger.warning("Error deleting Discord message {}: {}", message_id, e)
                else:
                    await asyncio.sleep(1)
        return False

    async def _send_or_edit_progress(
        self,
        chat_id: str,
        url: str,
        headers: dict[str, str],
        content: str,
        reply_to: str | None,
    ) -> None:
        text = split_message(content, MAX_MESSAGE_LEN)[0] if content else ""
        if not text:
            return

        buf = self._stream_bufs.get(chat_id)
        if buf is None or not buf.message_id:
            payload: dict[str, Any] = {"content": text}
            if reply_to:
                payload["message_reference"] = {"message_id": reply_to}
                payload["allowed_mentions"] = {"replied_user": False}
            sent = await self._send_payload(url, headers, payload)
            if sent is None:
                return
            message_id = sent.get("id")
            if isinstance(message_id, str) and message_id:
                self._stream_bufs[chat_id] = _StreamBuf(
                    text=text,
                    message_id=message_id,
                    last_edit=time.monotonic(),
                )
            return

        if buf.text == text and buf.pending_text is None:
            return

        buf.pending_text = text
        now = time.monotonic()
        if (now - buf.last_edit) < self._STREAM_EDIT_INTERVAL:
            return

        target_text = buf.pending_text or text
        if target_text == buf.text:
            buf.pending_text = None
            return

        if await self._edit_message(chat_id, headers, buf.message_id, target_text):
            buf.text = target_text
            buf.last_edit = now
            buf.pending_text = None

    def _reply_target(self, msg: OutboundMessage) -> str | None:
        if isinstance(msg.reply_to, str) and msg.reply_to:
            return msg.reply_to
        message_id = (msg.metadata or {}).get("message_id")
        if message_id is None:
            return None
        message_id = str(message_id).strip()
        return message_id or None

    def _proxy_url(self) -> str | None:
        proxy = (self.config.proxy or "").strip()
        if not proxy:
            return None
        if not self.config.proxy_username:
            return proxy

        parsed = urlsplit(proxy)
        if not parsed.scheme or not parsed.hostname or parsed.username or parsed.password:
            return proxy

        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        username = quote(self.config.proxy_username, safe="")
        password = self.config.proxy_password or ""
        credentials = username if not password else f"{username}:{quote(password, safe='')}"
        netloc = f"{credentials}@{host}"
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

    async def _send_file(
        self,
        url: str,
        headers: dict[str, str],
        file_path: str,
        reply_to: str | None = None,
    ) -> bool:
        """Send a file attachment via Discord REST API using multipart/form-data."""
        path = Path(file_path)
        if not path.is_file():
            logger.warning("Discord file not found, skipping: {}", file_path)
            return False

        if path.stat().st_size > MAX_ATTACHMENT_BYTES:
            logger.warning("Discord file too large (>20MB), skipping: {}", path.name)
            return False

        payload_json: dict[str, Any] = {}
        if reply_to:
            payload_json["message_reference"] = {"message_id": reply_to}
            payload_json["allowed_mentions"] = {"replied_user": False}

        for attempt in range(3):
            try:
                with open(path, "rb") as f:
                    files = {"files[0]": (path.name, f, "application/octet-stream")}
                    data: dict[str, Any] = {}
                    if payload_json:
                        data["payload_json"] = json.dumps(payload_json)
                    response = await self._http.post(url, headers=headers, files=files, data=data)
                if response.status_code == 429:
                    resp_data = response.json()
                    retry_after = float(resp_data.get("retry_after", 1.0))
                    logger.warning("Discord rate limited, retrying in {}s", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                response.raise_for_status()
                logger.info("Discord file sent: {}", path.name)
                return True
            except Exception as e:
                if attempt == 2:
                    logger.error("Error sending Discord file {}: {}", path.name, e)
                else:
                    await asyncio.sleep(1)
        return False

    async def _gateway_loop(self) -> None:
        """Main gateway loop: identify, heartbeat, dispatch events."""
        if not self._ws:
            return

        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from Discord gateway: {}", raw[:100])
                continue

            op = data.get("op")
            event_type = data.get("t")
            seq = data.get("s")
            payload = data.get("d")

            if seq is not None:
                self._seq = seq

            if op == 10:
                # HELLO: start heartbeat and identify
                interval_ms = payload.get("heartbeat_interval", 45000)
                await self._start_heartbeat(interval_ms / 1000)
                await self._identify()
            elif op == 0 and event_type == "READY":
                logger.info("Discord gateway READY")
                # Capture bot user ID for mention detection
                user_data = payload.get("user") or {}
                self._bot_user_id = user_data.get("id")
                logger.info("Discord bot connected as user {}", self._bot_user_id)
            elif op == 0 and event_type == "MESSAGE_CREATE":
                await self._handle_message_create(payload)
            elif op == 7:
                # RECONNECT: exit loop to reconnect
                logger.info("Discord gateway requested reconnect")
                break
            elif op == 9:
                # INVALID_SESSION: reconnect
                logger.warning("Discord gateway invalid session")
                break

    async def _identify(self) -> None:
        """Send IDENTIFY payload."""
        if not self._ws:
            return

        identify = {
            "op": 2,
            "d": {
                "token": self.config.token,
                "intents": self.config.intents,
                "properties": {
                    "os": "shibaclaw",
                    "browser": "shibaclaw",
                    "device": "shibaclaw",
                },
            },
        }
        await self._ws.send(json.dumps(identify))

    async def _start_heartbeat(self, interval_s: float) -> None:
        """Start or restart the heartbeat loop."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        async def heartbeat_loop() -> None:
            while self._running and self._ws:
                payload = {"op": 1, "d": self._seq}
                try:
                    await self._ws.send(json.dumps(payload))
                except Exception as e:
                    logger.warning("Discord heartbeat failed: {}", e)
                    break
                await asyncio.sleep(interval_s)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        """Handle incoming Discord messages."""
        author = payload.get("author") or {}
        if author.get("bot"):
            return

        sender_id = str(author.get("id", ""))
        channel_id = str(payload.get("channel_id", ""))
        content = payload.get("content") or ""
        guild_id = payload.get("guild_id")

        if not sender_id or not channel_id:
            return

        if not self.is_allowed(sender_id):
            return

        # Check group channel policy (DMs always respond if is_allowed passes)
        if guild_id is not None:
            if not self._should_respond_in_group(payload, content):
                return

        content_parts = [content] if content else []
        media_paths: list[str] = []
        media_dir = get_media_dir("discord")

        for attachment in payload.get("attachments") or []:
            url = attachment.get("url")
            filename = attachment.get("filename") or "attachment"
            size = attachment.get("size") or 0
            if not url or not self._http:
                continue
            if size and size > MAX_ATTACHMENT_BYTES:
                content_parts.append(f"[attachment: {filename} - too large]")
                continue
            try:
                media_dir.mkdir(parents=True, exist_ok=True)
                file_path = (
                    media_dir / f"{attachment.get('id', 'file')}_{filename.replace('/', '_')}"
                )
                resp = await self._http.get(url)
                resp.raise_for_status()
                file_path.write_bytes(resp.content)
                media_paths.append(str(file_path))
                content_parts.append(f"[attachment: {file_path}]")
            except Exception as e:
                logger.warning("Failed to download Discord attachment: {}", e)
                content_parts.append(f"[attachment: {filename} - download failed]")

        reply_to = (payload.get("referenced_message") or {}).get("id")

        await self._start_typing(channel_id)

        await self._handle_message(
            sender_id=sender_id,
            chat_id=channel_id,
            content="\n".join(p for p in content_parts if p) or "[empty message]",
            media=media_paths,
            metadata={
                "message_id": str(payload.get("id", "")),
                "guild_id": guild_id,
                "reply_to": reply_to,
            },
        )

    def _should_respond_in_group(self, payload: dict[str, Any], content: str) -> bool:
        """Check if bot should respond in a group channel based on policy."""
        if self.config.group_policy == "open":
            return True

        if self.config.group_policy == "mention":
            # Check if bot was mentioned in the message
            if self._bot_user_id:
                # Check mentions array
                mentions = payload.get("mentions") or []
                for mention in mentions:
                    if str(mention.get("id")) == self._bot_user_id:
                        return True
                # Also check content for mention format <@USER_ID>
                if f"<@{self._bot_user_id}>" in content or f"<@!{self._bot_user_id}>" in content:
                    return True
            logger.debug(
                "Discord message in {} ignored (bot not mentioned)", payload.get("channel_id")
            )
            return False

        return True

    async def _start_typing(self, channel_id: str) -> None:
        """Start periodic typing indicator for a channel."""
        await self._stop_typing(channel_id)

        async def typing_loop() -> None:
            url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
            headers = {"Authorization": f"Bot {self.config.token}"}
            while self._running:
                try:
                    await self._http.post(url, headers=headers)
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.debug("Discord typing indicator failed for {}: {}", channel_id, e)
                    return
                await asyncio.sleep(TYPING_INTERVAL_S)

        self._typing_tasks[channel_id] = asyncio.create_task(typing_loop())

    async def _stop_typing(self, channel_id: str) -> None:
        """Stop typing indicator for a channel."""
        task = self._typing_tasks.pop(channel_id, None)
        if task:
            task.cancel()
