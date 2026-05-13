"""In-memory notification store for the WebUI notification center."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

NotificationActionKind = Literal["none", "session", "url", "command", "settings-tab"]


@dataclass(slots=True)
class NotificationAction:
    kind: NotificationActionKind = "none"
    label: str = ""
    target: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "label": self.label,
            "target": self.target,
        }


@dataclass(slots=True)
class NotificationItem:
    id: str
    kind: str
    source: str
    title: str
    message: str
    timestamp: int
    read: bool = False
    session_key: str = ""
    action: NotificationAction = field(default_factory=NotificationAction)
    metadata: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp,
            "read": self.read,
            "session_key": self.session_key,
            "action": self.action.to_dict(),
            "metadata": dict(self.metadata),
        }


class NotificationManager:
    def __init__(self, *, max_items: int = 200) -> None:
        self._max_items = max_items
        self._lock = threading.Lock()
        self._items: list[NotificationItem] = []

    def _coerce_kind(
        self,
        *,
        kind: str | None,
        source: str,
        session_key: str,
        metadata: dict[str, Any],
    ) -> str:
        if kind:
            return kind
        if metadata.get("category"):
            return str(metadata["category"])
        if source == "background" and session_key:
            return "agent_response"
        return source or "system"

    def _default_title(self, *, kind: str, source: str) -> str:
        titles = {
            "update": "Update available",
            "heartbeat": "Heartbeat task completed",
            "cron": "Cron job completed",
            "agent_response": "Agent response ready",
            "memory_compact": "Memory compacted",
            "memory_compacted": "Memory compacted",
        }
        return titles.get(kind) or titles.get(source) or "Notification"

    def _coerce_action(
        self,
        *,
        kind: str,
        session_key: str,
        metadata: dict[str, Any],
        action: dict[str, Any] | None,
    ) -> NotificationAction:
        payload = dict(action or metadata.get("action") or {})
        action_kind = str(payload.get("kind") or "").strip().lower()
        if action_kind in {"session", "url", "command", "settings-tab"}:
            return NotificationAction(
                kind=action_kind,  # type: ignore[arg-type]
                label=str(payload.get("label") or "Open"),
                target=str(payload.get("target") or ""),
            )

        if kind == "update":
            return NotificationAction(kind="settings-tab", label="Open updater", target="update")
        if session_key:
            return NotificationAction(kind="session", label="Open session", target=session_key)
        if metadata.get("action_url"):
            return NotificationAction(
                kind="url",
                label=str(metadata.get("action_label") or "Open link"),
                target=str(metadata.get("action_url") or ""),
            )
        if metadata.get("action_command"):
            return NotificationAction(
                kind="command",
                label=str(metadata.get("action_label") or "Copy command"),
                target=str(metadata.get("action_command") or ""),
            )
        return NotificationAction()

    def _dedupe_key(
        self,
        *,
        dedupe_key: str | None,
        kind: str,
        source: str,
        session_key: str,
        metadata: dict[str, Any],
    ) -> str | None:
        if dedupe_key:
            return dedupe_key
        if kind == "update" or source == "update":
            install_method = metadata.get("install_method") or "unknown"
            latest = metadata.get("latest") or metadata.get("display_latest") or "unknown"
            return f"update:{install_method}:{latest}"
        if kind == "memory_compact" or source == "memory_compact":
            return f"memory:{session_key or 'global'}"
        return None

    def create_notification(
        self,
        *,
        message: str,
        kind: str | None = None,
        source: str = "system",
        title: str | None = None,
        session_key: str = "",
        action: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        read: bool = False,
        timestamp: int | None = None,
    ) -> dict[str, Any]:
        safe_metadata = dict(metadata or {})
        resolved_kind = self._coerce_kind(
            kind=kind,
            source=source,
            session_key=session_key,
            metadata=safe_metadata,
        )
        resolved_action = self._coerce_action(
            kind=resolved_kind,
            session_key=session_key,
            metadata=safe_metadata,
            action=action,
        )
        resolved_title = (title or safe_metadata.get("title") or self._default_title(kind=resolved_kind, source=source)).strip()
        resolved_message = (message or safe_metadata.get("body") or "").strip()
        created_at = int(timestamp or time.time())
        resolved_dedupe = self._dedupe_key(
            dedupe_key=dedupe_key,
            kind=resolved_kind,
            source=source,
            session_key=session_key,
            metadata=safe_metadata,
        )

        if not resolved_message:
            raise ValueError("Notification message is required")

        with self._lock:
            if resolved_dedupe:
                for existing in self._items:
                    if existing.dedupe_key == resolved_dedupe:
                        existing.kind = resolved_kind
                        existing.source = source
                        existing.title = resolved_title
                        existing.message = resolved_message
                        existing.timestamp = created_at
                        existing.read = False if not read else existing.read
                        existing.session_key = session_key
                        existing.action = resolved_action
                        existing.metadata = safe_metadata
                        self._items.sort(key=lambda item: item.timestamp, reverse=True)
                        return existing.to_dict()

            item = NotificationItem(
                id=uuid.uuid4().hex[:12],
                kind=resolved_kind,
                source=source,
                title=resolved_title,
                message=resolved_message,
                timestamp=created_at,
                read=read,
                session_key=session_key,
                action=resolved_action,
                metadata=safe_metadata,
                dedupe_key=resolved_dedupe,
            )
            self._items.insert(0, item)
            if len(self._items) > self._max_items:
                del self._items[self._max_items :]
            return item.to_dict()

    def create_from_event(
        self,
        *,
        content: str,
        source: str,
        session_key: str = "",
        metadata: dict[str, Any] | None = None,
        msg_type: str = "response",
    ) -> dict[str, Any]:
        safe_metadata = dict(metadata or {})
        message = (safe_metadata.get("body") or content or "").strip()
        kind = safe_metadata.get("category") or safe_metadata.get("kind") or source or msg_type
        if kind == "response" and session_key:
            kind = "agent_response"
        if source == "background" and session_key:
            kind = "agent_response"
        return self.create_notification(
            message=message,
            kind=str(kind),
            source=source,
            title=safe_metadata.get("title"),
            session_key=session_key,
            metadata=safe_metadata,
            dedupe_key=safe_metadata.get("dedupe_key"),
        )

    def list_notifications(self, *, limit: int = 50, unread_only: bool = False) -> dict[str, Any]:
        safe_limit = max(1, min(limit, self._max_items))
        with self._lock:
            items = [item for item in self._items if not unread_only or not item.read]
            notifications = [item.to_dict() for item in items[:safe_limit]]
            unread_count = sum(1 for item in self._items if not item.read)
            total_count = len(self._items)
        return {
            "notifications": notifications,
            "unread_count": unread_count,
            "total_count": total_count,
        }

    def mark_read(self, notification_id: str | None = None) -> int:
        with self._lock:
            if notification_id:
                for item in self._items:
                    if item.id == notification_id:
                        item.read = True
                        return 1
                return 0

            count = 0
            for item in self._items:
                if not item.read:
                    item.read = True
                    count += 1
            return count

    def delete(self, notification_id: str | None = None) -> int:
        with self._lock:
            if notification_id:
                before = len(self._items)
                self._items = [item for item in self._items if item.id != notification_id]
                return before - len(self._items)

            removed = len(self._items)
            self._items = []
            return removed


notification_manager = NotificationManager()
