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
        self._channel_manager: Optional[Any] = None
        self._bg_tasks: List[asyncio.Task] = []
        self._sio: Optional[Any] = None
        self._sessions: Dict[str, Dict] = {}
        self._init_lock = asyncio.Lock()

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

    async def _run_local_cron_job(self, job: Any) -> str | None:
        """Execute and deliver a scheduled job inside the WebUI process."""
        if not self.agent:
            logger.warning("Cron: WebUI runner triggered before agent initialization")
            return None

        from shibaclaw.bus.events import OutboundMessage
        from shibaclaw.cli.gateway import resolve_cron_target

        async def _noop_progress(*_args, **_kwargs) -> None:
            return None

        target = resolve_cron_target(job)
        reminder_note = (
            f"[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' triggered.\n"
            f"Message: {job.payload.message}"
        )
        outbound = await self.agent.process_direct(
            reminder_note,
            target.session_key,
            target.channel,
            target.chat_id,
            on_progress=_noop_progress,
        )
        response = outbound.content if outbound else ""

        if response and job.payload.deliver:
            if target.channel == "webui":
                result = await self.deliver_background_notification(
                    target.session_key,
                    response,
                    source="cron",
                    persist=False,
                )
                if not result["delivered"]:
                    logger.info("Cron: no active WebUI client matched session {}", target.session_key)
            elif target.channel != "cli" and self.bus:
                await self.bus.publish_outbound(
                    OutboundMessage(channel=target.channel, chat_id=target.chat_id, content=response)
                )
            else:
                logger.info("Cron: completed but found no deliverable session for job {}", job.id)

        return response

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
            from shibaclaw.integrations.manager import ChannelManager

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
                consolidation_model=self.config.agents.defaults.consolidation_model,
            )
            cron.on_job = self._run_local_cron_job
            await cron.start()

            # Shutdown old tasks if any
            for t in self._bg_tasks:
                t.cancel()
            self._bg_tasks.clear()

            # Initialize channels for OUTBOUND sending only — no inbound polling.
            # Polling is the gateway's responsibility; starting it here too would
            # cause a Telegram/Discord conflict when both containers run together.
            self._channel_manager = ChannelManager(self.config, self.bus)
            for name, channel in self._channel_manager.channels.items():
                await self._channel_manager._init_channel_for_sending(name, channel)
                logger.info("🔌 Channel {} ready for outbound sending", name)

            # Start core background tasks
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
                    logger.debug("⏩ Outbound message not for webui: {}:{}", msg.channel, msg.chat_id)
                    # Route cross-channel messages (Telegram, Discord, etc.) via ChannelManager
                    if self._channel_manager:
                        ch = self._channel_manager.channels.get(msg.channel)
                        if ch:
                            try:
                                await ch.send(msg)
                                logger.debug("📨 Delivered to {} channel", msg.channel)
                            except Exception as e:
                                logger.error("Error delivering to {}: {}", msg.channel, e)
                        else:
                            logger.warning("No channel handler for: {}", msg.channel)
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
        self._channel_manager = None

    async def archive_in_background(self, snapshot):
        """Fire-and-forget LLM archive to memory."""
        if not self.agent or not hasattr(self.agent, "memory_consolidator"):
            return
        
        try:
            await self.agent.memory_consolidator.archive_snapshot(snapshot)
        except Exception:
            logger.exception("Background archive failed (messages already deleted from session)")


# Singleton instance
agent_manager = AgentManager()
