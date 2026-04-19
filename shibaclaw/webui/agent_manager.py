"""Lightweight agent proxy for the WebUI - delegates processing to the gateway."""

from __future__ import annotations

from typing import Any, Optional, Dict

from loguru import logger


class AgentManager:
    """Thin config holder and WebSocket bridge.  All LLM work runs in the gateway."""

    def __init__(self):
        self.config: Optional[Any] = None
        self.provider: Optional[Any] = None
        self.oauth_jobs: Dict[str, Dict] = {}

    async def deliver_background_notification(
        self,
        session_key: str,
        content: str,
        *,
        source: str = "background",
        persist: bool = True,
        msg_type: str = "response",
    ) -> dict[str, Any]:
        """Persist and deliver a background notification to matching browser sessions."""
        if not content:
            return {"delivered": False, "matched_sessions": 0}
        
        # For broadcasting (empty session_key), we don't persist to any specific session
        if persist and session_key:
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

        # Deliver via native WebSocket handler
        from shibaclaw.webui.ws_handler import deliver_to_browsers
        delivered = await deliver_to_browsers(session_key, content, source=source, msg_type=msg_type)

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


agent_manager = AgentManager()