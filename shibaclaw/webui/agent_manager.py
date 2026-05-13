"""Lightweight agent proxy for the WebUI - delegates processing to the gateway."""

from __future__ import annotations

from typing import Any, Dict, Optional


class AgentManager:
    """Thin config holder and WebSocket bridge.  All LLM work runs in the gateway."""

    def __init__(self):
        self.config: Optional[Any] = None
        self.provider: Optional[Any] = None
        self.oauth_jobs: Dict[str, Dict] = {}
        self._pack_manager: Optional[Any] = None

    @property
    def pm(self) -> Any:
        if not self._pack_manager and self.config:
            from shibaclaw.brain.manager import PackManager
            self._pack_manager = PackManager(self.config.workspace_path)
        return self._pack_manager

    async def deliver_background_notification(
        self,
        session_key: str,
        content: str,
        *,
        source: str = "background",
        persist: bool = True,
        msg_type: str = "response",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist and deliver a background notification to matching browser sessions."""
        if not content:
            return {"delivered": False, "matched_sessions": 0}

        notification = None

        # For broadcasting (empty session_key), we don't persist to any specific session
        if persist and session_key:
            try:
                if not self.config:
                    self.load_latest_config()
                pm = self.pm
                if self.config and pm:
                    session = pm.get_or_create(session_key)
                    stored_metadata = {"background": True, "source": source}
                    if metadata:
                        stored_metadata["notification"] = metadata
                    session.add_message(
                        "assistant",
                        content,
                        metadata=stored_metadata,
                    )
                    pm.save(session)
            except Exception:
                pass  # persist failure must not block notification creation

        try:
            from shibaclaw.helpers.notification_manager import notification_manager

            notification = notification_manager.create_from_event(
                content=content,
                source=source,
                session_key=session_key,
                metadata=metadata,
                msg_type=msg_type,
            )
        except Exception:
            notification = None

        # Deliver via native WebSocket handler
        from shibaclaw.webui.ws_handler import broadcast_notification, deliver_to_browsers

        deliver_kwargs = {
            "source": source,
            "msg_type": msg_type,
        }
        if metadata is not None:
            deliver_kwargs["metadata"] = metadata

        delivered = await deliver_to_browsers(
            session_key,
            content,
            **deliver_kwargs,
        )

        if notification is not None:
            await broadcast_notification(notification)

        return {
            "delivered": delivered > 0,
            "matched_sessions": delivered,
            "notification": notification,
        }

    def load_latest_config(self):
        """Load the latest config from disk."""
        from shibaclaw.config.loader import load_config

        self.config = load_config()
        self._pack_manager = None

        try:
            from shibaclaw.cli.commands import _make_provider

            self.provider = _make_provider(self.config, exit_on_error=False)
        except Exception:
            self.provider = None

    async def reset_agent(self):
        """Reload local config and signal gateway to pick up changes via full restart."""
        self.load_latest_config()
        from shibaclaw.webui.utils import _gateway_request

        await _gateway_request("POST", "/restart")

    async def reload_config(self, new_cfg: Any) -> None:
        """Apply new config in-memory and signal gateway to hot-reload without restarting."""
        self.config = new_cfg
        self._pack_manager = None
        try:
            from shibaclaw.cli.commands import _make_provider

            self.provider = _make_provider(new_cfg, exit_on_error=False)
        except Exception:
            self.provider = None
        from shibaclaw.webui.utils import _gateway_request

        await _gateway_request("POST", "/reload")

    async def archive_via_gateway(self, snapshot: list[dict]):
        """Send session snapshot to the gateway for memory archival."""
        from shibaclaw.webui.utils import _gateway_post

        await _gateway_post("/api/archive", {"snapshot": snapshot})


agent_manager = AgentManager()
