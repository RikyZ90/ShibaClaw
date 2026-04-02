"""Agent lifecycle and background task management for the WebUI."""

from __future__ import annotations

import asyncio
import uuid
import mimetypes
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List

from loguru import logger
from .auth import get_auth_token

class AgentManager:
    """Manages the ShibaBrain agent instance, configuration, and background consumers."""

    def __init__(self):
        self.agent: Optional[Any] = None
        self.bus: Optional[Any] = None
        self.config: Optional[Any] = None
        self.provider: Optional[Any] = None
        self._bg_tasks: List[asyncio.Task] = []
        self._sio: Optional[Any] = None
        self._sessions: Dict[str, Dict] = {}
        self._init_lock = asyncio.Lock()

    def set_socket_io(self, sio: Any, sessions: Dict[str, Dict]):
        self._sio = sio
        self._sessions = sessions

    def load_latest_config(self):
        """Load the latest config from disk."""
        from shibaclaw.config.loader import load_config
        self.config = load_config()

        try:
            from shibaclaw.cli.commands import _make_provider
            self.provider = _make_provider(self.config, exit_on_error=False)
        except Exception:
            self.provider = None

    async def ensure_agent(self):
        """Ensure the agent and its background consumers are running."""
        if self.agent is not None:
            return
        async with self._init_lock:
            if self.agent is not None:  # double-checked under lock
                return

            if self.config is None:
                self.load_latest_config()

            if self.config is None or self.provider is None:
                return

            from shibaclaw.agent.loop import ShibaBrain
            from shibaclaw.bus.queue import MessageBus
            from shibaclaw.config.paths import get_cron_dir
            from shibaclaw.cron.service import CronService

            self.bus = MessageBus()
            cron_store = get_cron_dir() / "jobs.json"
            cron = CronService(cron_store)

            self.agent = ShibaBrain(
                bus=self.bus,
                provider=self.provider,
                workspace=self.config.workspace_path,
                model=self.config.agents.defaults.model,
                max_iterations=self.config.agents.defaults.max_tool_iterations,
                context_window_tokens=self.config.agents.defaults.context_window_tokens,
                web_search_config=self.config.tools.web.search,
                web_proxy=self.config.tools.web.proxy or None,
                exec_config=self.config.tools.exec,
                cron_service=cron,
                mcp_servers=self.config.tools.mcp_servers,
                channels_config=self.config.channels,
                learning_enabled=self.config.agents.defaults.learning_enabled,
                learning_interval=self.config.agents.defaults.learning_interval,
                memory_max_prompt_tokens=self.config.agents.defaults.memory_max_prompt_tokens,
                memory_compact_threshold_tokens=self.config.agents.defaults.memory_compact_threshold_tokens,
            )
            await cron.start()

            # Shutdown old tasks if any
            for t in self._bg_tasks:
                t.cancel()
            self._bg_tasks.clear()

            # Start new background tasks
            task1 = asyncio.create_task(self.agent.run())
            task2 = asyncio.create_task(self._consume_outbound())
            self._bg_tasks.extend([task1, task2])

    async def _consume_outbound(self):
        """Consume messages from the bus and deliver to the WebUI clients."""
        if not self.bus or not self._sio:
            return

        auth_token = get_auth_token() or ""

        while True:
            try:
                msg = await asyncio.wait_for(self.bus.consume_outbound(), timeout=1.0)
                logger.debug("🚌 Consumed outbound: target={}:{}", msg.channel, msg.chat_id)
                
                if msg.channel == "webui" and msg.chat_id in self._sessions:
                    # Only handle non-progress system broadcasts
                    if not msg.metadata or not msg.metadata.get("_progress"):
                        logger.info("📢 Delivering outbound message to WebUI sid: {}", msg.chat_id)
                        
                        attachments = []
                        for m_path in (msg.media or []):
                            p = Path(m_path)
                            results = mimetypes.guess_type(m_path)
                            attachments.append({
                                "name": p.name,
                                "url": f"/api/file-get?path={urllib.parse.quote(str(p.absolute()))}&token={auth_token}",
                                "type": results[0] or "application/octet-stream"
                            })
                        
                        agent_resp = {
                            "id": str(uuid.uuid4())[:8],
                            "content": msg.content or "Task completed.",
                            "attachments": attachments
                        }
                        await self._sio.emit("agent_response", agent_resp, room=msg.chat_id)

                        # Persist to history
                        session_state = self._sessions[msg.chat_id]
                        session_key = session_state.get("session_key")
                        pm = getattr(self.agent, "sessions", None)
                        if session_key and pm:
                            logger.debug("💾 Persisting agent response to history for key: {}", session_key)
                            sess = pm.get_or_create(session_key)
                            sess.messages.append({
                                "role": "assistant",
                                "content": agent_resp["content"],
                                "timestamp": datetime.now().isoformat(),
                                "metadata": {"attachments": attachments}
                            })
                            pm.save(sess)
                    else:
                        logger.debug("⏭️ Skipping progress message in _consume_outbound")
                else:
                    logger.warning("⚠️ Outbound message target not found: {}:{}", msg.channel, msg.chat_id)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Outbound consumer error: {}", str(e))

    def reset_agent(self):
        """Stop tasks and clear agent instance so it recreates on next access."""
        if self.agent:
            try:
                self.agent.stop()
            except Exception:
                pass
        for t in self._bg_tasks:
            t.cancel()
        self._bg_tasks.clear()
        self.agent = None

    async def archive_in_background(self, snapshot):
        """Fire-and-forget LLM archive to memory."""
        if not self.agent or not hasattr(self.agent, "memory_consolidator"):
            return
        
        try:
            await self.agent.memory_consolidator.archive_messages(snapshot)
        except Exception:
            logger.exception("Background archive failed (messages already deleted from session)")


# Singleton instance
agent_manager = AgentManager()
