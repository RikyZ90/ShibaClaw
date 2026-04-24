"""Message tool for sending messages to users."""

from pathlib import Path
from typing import Any, Awaitable, Callable

from shibaclaw.agent.tools.base import Tool
from shibaclaw.bus.events import OutboundMessage


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        default_message_id: str | None = None,
        workspace: Path | None = None,
        router: Any | None = None,
    ):
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id
        self._default_message_id = default_message_id
        self._workspace = workspace
        self._router = router
        self._sent_in_turn: bool = False

    def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id
        self._default_message_id = message_id

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        self._sent_in_turn = False

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return "Send a message to the user. Use this to respond to the user, particularly when you need to ATTACH files or media that you have created or located."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send to the user.",
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)",
                },
                "chat_id": {"type": "string", "description": "Optional: target chat/user ID"},
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: list of absolute file paths to attach/upload (images, audio, documents, etc.)",
                },
            },
            "required": ["content"],
        }

    async def execute(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        message_id: str | None = None,
        media: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        target_channel = channel or self._default_channel
        # Auto-resolve chat_id to "auto" if crossing boundaries without specific ID
        if channel and channel != self._default_channel:
            target_chat_id = chat_id or "auto"
        else:
            target_chat_id = chat_id or self._default_chat_id

        target_message_id = message_id or self._default_message_id

        if not target_channel or not target_chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        metadata = {
            "message_id": target_message_id,
        }
        if self._default_channel and self._default_chat_id:
            metadata["origin_channel"] = self._default_channel
            metadata["origin_chat_id"] = self._default_chat_id

        resolved_media = [self._resolve_media_path(p) for p in (media or [])]

        msg = OutboundMessage(
            channel=target_channel,
            chat_id=target_chat_id,
            content=content,
            media=resolved_media,
            metadata=metadata,
        )

        try:
            await self._send_callback(msg)
            if target_channel == self._default_channel and target_chat_id == self._default_chat_id:
                self._sent_in_turn = True
            elif self._router and self._default_channel and self._default_chat_id:
                origin_key = f"{self._default_channel}:{self._default_chat_id}"
                target_key = f"{target_channel}:{target_chat_id}"
                self._router.link(target_key, origin_key, ttl_seconds=600)
                
            media_info = f" with {len(resolved_media)} attachments" if resolved_media else ""
            return f"Message dispatched to {target_channel} (chat_id: {target_chat_id}){media_info}"
        except Exception as e:
            return f"Error sending message: {str(e)}"

    def _resolve_media_path(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        p = Path(path).expanduser()
        if not p.is_absolute() and self._workspace:
            p = self._workspace / p
        return str(p.resolve())
