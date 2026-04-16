"""Lightweight agent proxy for the WebUI - delegates processing to the gateway."""

from __future__ import annotations

import uuid
from typing import Any, Optional, Dict

from loguru import logger


class AgentManager:
    """Thin config holder and Socket.IO bridge.  All LLM work runs in the gateway."""

    def __init__(self):
        self.config: Optional[Any] = None
        self.provider: Optional[Any] = None
        self._sio: Optional[Any] = None
        self._sessions: Dict[str, Dict] = {}
        self.oauth_jobs: Dict[str, Dict] = {}

    def set_socket_io(self, sio: Any, sessions: Dict[str, Dict]):
        self._sio = sio
        self._sessions = sessions

    async def deliver_background_notification(
        self,
        session_key: str,
        content: str,
        *,
        source: str = "background",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Persist and emit a background notification to matching WebUI sessions."""
        if not session_key or not content:
            return {"delivered": False, "matched_sessions": 0}

        if persist:
            if not self.config:
                self.load_latest_config()
            if not self.config:
                return {"delivered": False, "matched_sessions": 0}

            from shibaclaw.brain.manager import PackManager

            pm = PackManager(self.config.workspace_path)
            session = pm.get_or_create(session_key)
            session.add_message(
                "assistant",
                content,
                metadata={"background": True, "source": source},
            )
            pm.save(session)

        delivered = 0
        payload = {
            "id": str(uuid.uuid4())[:8],
            "content": content,
            "attachments": [],
        }
        if self._sio:
            for sid, state in list(self._sessions.items()):
                if state.get("session_key") != session_key:
                    continue
                await self._sio.emit("agent_response", payload, room=sid)
                delivered += 1

        return {"delivered": delivered > 0, "matched_sessions": delivered}

    def load_latest_config(self):
        """Load the latest config from disk."""
        from shibaclaw.config.loader import load_config
        self.config = load_config()

        try:
            from shibaclaw.cli.commands import _make_provider
            self.provider = _make_provider(self.config, exit_on_error=False)
        except Exception:
            self.provider = None

    async def reset_agent(self):
        """Reload local config and signal gateway to pick up changes."""
        self.load_latest_config()
        from shibaclaw.webui.utils import _gateway_request
        await _gateway_request("POST", "/restart")

    async def archive_via_gateway(self, snapshot: list[dict]):
        """Send session snapshot to the gateway for memory archival."""
        from shibaclaw.webui.utils import _gateway_post
        await _gateway_post("/api/archive", {"snapshot": snapshot})


# Singleton instance
agent_manager = AgentManager()