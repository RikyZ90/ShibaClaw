"""Agent loop: the core engine where the Shiba hunts for answers."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import weakref
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, cast

from loguru import logger

from shibaclaw.agent.context import ScentBuilder
from shibaclaw.agent.memory import PackMemory, ScentKeeper
from shibaclaw.agent.skills import BUILTIN_SKILLS_DIR
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.agent.tools.automation import AutomationTool
from shibaclaw.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from shibaclaw.agent.tools.memory_search import MemorySearchTool
from shibaclaw.agent.tools.message import MessageTool
from shibaclaw.agent.tools.registry import SkillVault
from shibaclaw.agent.tools.shell import ExecTool
from shibaclaw.agent.tools.spawn import SpawnTool
from shibaclaw.agent.tools.web import WebFetchTool, WebSearchTool
from shibaclaw.agent.tools.knowledge import KnowledgeSearchTool
from shibaclaw.brain.manager import PackManager, Session
from shibaclaw.bus.events import InboundMessage, OutboundMessage
from shibaclaw.bus.queue import MessageBus
from shibaclaw.helpers.system import get_os_type
from shibaclaw.thinkers.base import Thinker

_MEDIA_RE = re.compile(r'\{\s*"media"\s*:\s*\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]\s*\}')

if TYPE_CHECKING:
    from shibaclaw.config.schema import ExecToolConfig, WebSearchConfig


class ShibaBrain:
    """The core agent loop."""

    _TOOL_RESULT_MAX_CHARS = 16_000
    _TOOL_RESULT_LOOP_MAX_CHARS = 8_000

    def __init__(
        self,
        bus: MessageBus,
        provider: Thinker | None,
        workspace: Path,
        config: Any | None = None,
        model: str | None = None,
        max_iterations: int = 10,
        context_window_tokens: int = 4000,
        web_search_config: WebSearchConfig | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        automation_service: Any | None = None,
        restrict_to_workspace: bool = True,
        session_manager: PackManager | None = None,
        mcp_servers: dict[str, Any] | None = None,
        channels_config: Any | None = None,
        learning_enabled: bool = True,
        learning_interval: int = 10,
        memory_max_prompt_tokens: int = 2000,
        memory_compact_threshold_tokens: int = 1600,
        consolidation_model: str | None = None,
        session_router: Any | None = None,
    ):
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.config = config
        self.model = model or (provider.get_default_model() if provider else "unknown")
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.automation_service = automation_service
        self.restrict_to_workspace = restrict_to_workspace
        self.session_router = session_router
        self.tool_timeout = config.agents.defaults.tool_timeout if config else int(os.getenv("SHIBACLAW_TOOL_TIMEOUT", "660"))
        self.loop_wall_timeout = config.agents.defaults.loop_wall_timeout if config else int(os.getenv("SHIBACLAW_LOOP_WALL_TIMEOUT", "600"))
        subagent_timeout = config.agents.defaults.subagent_timeout if config else int(os.getenv("SHIBACLAW_SUBAGENT_TIMEOUT", "600"))

        self.context = ScentBuilder(workspace)
        self.sessions = session_manager or PackManager(workspace)
        self.tools = SkillVault()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            web_search_config=self.web_search_config,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            timeout=subagent_timeout,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._mcp_queue: asyncio.Queue = asyncio.Queue()
        self._mcp_worker_task: asyncio.Task = asyncio.create_task(self._mcp_worker())
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._session_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._provider_cache: dict[str, Thinker] = {}
        self._steering_queues: dict[str, list[dict]] = {}
        self.memory_consolidator = PackMemory(
            workspace=workspace,
            provider=cast(Thinker, provider),
            model=self.model,
            sessions=self.sessions,
            context_window_tokens=context_window_tokens,
            build_messages=self.context.build_messages,
            get_tool_definitions=self.tools.get_definitions,
            learning_enabled=learning_enabled,
            learning_interval=learning_interval,
            memory_max_prompt_tokens=memory_max_prompt_tokens,
            memory_compact_threshold_tokens=memory_compact_threshold_tokens,
            consolidation_model=consolidation_model,
        )
        self.memory = ScentKeeper(workspace)
        self._available_channels = self._extract_enabled_channels()
        self._register_default_tools()
        logger.debug("Agent initialized for workspace: {}", workspace)

    def _extract_enabled_channels(self) -> list[str]:
        """Return names of enabled channels from channels_config."""
        if not self.channels_config:
            return []
        names: list[str] = []
        extras = getattr(self.channels_config, "__pydantic_extra__", None) or {}
        for name, section in extras.items():
            enabled = (
                section.get("enabled", False)
                if isinstance(section, dict)
                else getattr(section, "enabled", False)
            )
            if enabled:
                names.append(name)
        return names

    async def reconfigure(self, new_cfg: Any, new_provider: Any) -> None:
        """Hot-reload agent configuration without restarting the gateway process.

        Updates provider, model, and all tool/config references in-place.
        MCP connections are torn down first, then tools are re-registered, and
        MCP reconnection is awaited synchronously so the agent never has a
        window where MCP tools are missing.
        """
        self.provider = new_provider
        self.config = new_cfg
        self.model = new_cfg.agents.defaults.model or (
            new_provider.get_default_model() if new_provider else self.model
        )
        self.max_iterations = new_cfg.agents.defaults.max_tool_iterations
        self.context_window_tokens = new_cfg.agents.defaults.context_window_tokens
        self.restrict_to_workspace = new_cfg.tools.restrict_to_workspace
        self.web_proxy = new_cfg.tools.web.proxy
        self.web_search_config = new_cfg.tools.web.search
        self.exec_config = new_cfg.tools.exec
        self.tool_timeout = new_cfg.agents.defaults.tool_timeout
        self.loop_wall_timeout = new_cfg.agents.defaults.loop_wall_timeout
        self.channels_config = new_cfg.channels
        self._available_channels = self._extract_enabled_channels()
        self._provider_cache.clear()

        # MCP: reconfigure incrementally
        new_mcp = new_cfg.tools.mcp_servers or {}
        mcp_changed = self._mcp_configs_differ(new_mcp, self._mcp_servers)

        if mcp_changed:
            self._mcp_servers = new_mcp
            self._mcp_connected = False

        # Re-register default tools (always needed for exec/web/restrict changes)
        self.tools = SkillVault()
        self._register_default_tools()

        # MCP: reconnect incrementally so tools are updated immediately
        if mcp_changed and self._mcp_servers:
            try:
                await self._connect_mcp()
            except Exception as exc:
                logger.error("MCP reconnection after reconfigure failed: {}", exc)

        # Update memory consolidator provider/model
        self.memory_consolidator.provider = new_provider
        self.memory_consolidator.model = self.model
        self.memory_consolidator.learning_enabled = new_cfg.agents.defaults.learning_enabled
        self.memory_consolidator.learning_interval = new_cfg.agents.defaults.learning_interval

        # Update subagent manager
        self.subagents.reconfigure(new_cfg, new_provider)

        logger.info("ShibaBrain reconfigured (model={})", self.model)

    @staticmethod
    def _mcp_configs_differ(a: dict, b: dict) -> bool:
        """Compare two MCP server config dicts via JSON serialization, connection-affecting fields only."""
        def _serialize(servers: dict) -> dict:
            if not servers:
                return {}
            result = {}
            for k, v in servers.items():
                if hasattr(v, "model_dump"):
                    v_dict = v.model_dump(mode="json")
                elif isinstance(v, dict):
                    v_dict = v
                else:
                    v_dict = {}
                # Only include connection affecting fields to avoid unnecessary disconnects/reconnects
                result[k] = {
                    field: v_dict.get(field)
                    for field in ("type", "command", "args", "env", "url", "headers", "oauth")
                }
            return result

        return _serialize(a) != _serialize(b)

    def _resolve_provider_for_model(self, model: str | None) -> Thinker | None:
        """Return the provider instance that should serve the requested model."""
        if not self.config:
            return self.provider

        requested_model = model or self.model
        if requested_model == self.model:
            return self.provider

        try:
            temp_cfg = self.config.model_copy(deep=True)
            temp_cfg.agents.defaults.provider = "auto"
            requested_provider_name = temp_cfg.get_provider_name(requested_model)
        except Exception:
            return self.provider

        if not requested_provider_name:
            return self.provider

        cached_provider = self._provider_cache.get(requested_provider_name)
        if cached_provider:
            return cached_provider

        try:
            from shibaclaw.cli.base import _make_provider

            temp_cfg = self.config.model_copy(deep=True)
            temp_cfg.agents.defaults.provider = "auto"
            temp_cfg.agents.defaults.model = requested_model
            resolved_provider = _make_provider(temp_cfg, exit_on_error=False)
        except Exception as exc:
            logger.error(
                "Failed to build provider {} for model {}: {}",
                requested_provider_name,
                requested_model,
                exc,
            )
            return self.provider

        if resolved_provider:
            self._provider_cache[requested_provider_name] = resolved_provider
            return resolved_provider
        return self.provider

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
        self.tools.register(
            ReadFileTool(
                workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read
            )
        )
        for cls in (WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        if self.exec_config.enable:
            _os = get_os_type()
            logger.debug("ExecTool initialised for OS: {}", _os)
            self.tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    restrict_to_workspace=self.restrict_to_workspace,
                    path_append=self.exec_config.path_append,
                    install_audit=self.exec_config.install_audit,
                    install_audit_timeout=self.exec_config.install_audit_timeout,
                    install_audit_block_severity=self.exec_config.install_audit_block_severity,
                )
            )
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(KnowledgeSearchTool())
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(MemorySearchTool(workspace=self.workspace))
        self.tools.register(
            MessageTool(
                send_callback=self.bus.publish_outbound,
                workspace=self.workspace,
                router=self.session_router,
            )
        )
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.automation_service:
            self.tools.register(AutomationTool(self.automation_service))

        try:
            from shibaclaw.agent.tools.mcp import register_active_mcp_tools
            register_active_mcp_tools(self.tools)
        except Exception as e:
            logger.error("Failed to restore active MCP tools on registry rebuild: {}", e)

    def inject_steering_message(
        self,
        session_key: str,
        content: str,
        media: list[str] | None = None,
        attachments: list[dict] | None = None,
    ) -> bool:
        if session_key in self._steering_queues:
            self._steering_queues[session_key].append(
                {
                    "role": "user",
                    "content": content,
                    "media": media,
                    "attachments": attachments,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return True
        return False

    async def _mcp_worker(self) -> None:
        """Worker task that executes all MCP connection/disconnection requests.

        This ensures that self._mcp_stack is always entered and exited within
        the same asyncio Task, preventing anyio's cross-task RuntimeError.
        """
        try:
            while True:
                try:
                    op, fut = await self._mcp_queue.get()
                    if op == "connect":
                        try:
                            await self._do_connect_mcp()
                            fut.set_result(None)
                        except BaseException as e:
                            if not fut.done():
                                if isinstance(e, Exception):
                                    fut.set_result(e)
                                else:
                                    fut.set_exception(e)
                    elif op == "close":
                        try:
                            await self._do_close_mcp()
                            fut.set_result(None)
                        except BaseException as e:
                            if not fut.done():
                                if isinstance(e, Exception):
                                    fut.set_result(e)
                                else:
                                    fut.set_exception(e)
                    self._mcp_queue.task_done()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception("Error in MCP worker loop: {}", e)
        finally:
            try:
                await self._do_close_mcp()
            except Exception as e:
                logger.exception("Error during final MCP close in worker: {}", e)

    async def _do_connect_mcp(self) -> None:
        if not self._mcp_servers:
            return
        from shibaclaw.agent.tools.mcp import connect_mcp_servers

        try:
            if self._mcp_stack is None:
                self._mcp_stack = AsyncExitStack()
                await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except BaseException as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except BaseException as close_e:
                    logger.debug("Ignored exception during MCP stack aclose on connect failure: {}", close_e)
                finally:
                    self._mcp_stack = None
            raise

    async def _do_close_mcp(self) -> None:
        if self._background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._background_tasks, return_exceptions=True),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for background tasks during MCP close; cancelling")
                for task in self._background_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            finally:
                self._background_tasks.clear()

        if self._mcp_stack:
            stack = self._mcp_stack
            self._mcp_stack = None
            try:
                await stack.aclose()
            except BaseException as e:
                logger.debug("Exception during MCP stack aclose: {}", e)
            finally:
                await asyncio.sleep(0)

        try:
            from shibaclaw.agent.tools.mcp import clear_mcp_sessions
            clear_mcp_sessions()
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)

        self._mcp_connected = False

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        fut = asyncio.get_running_loop().create_future()
        await self._mcp_queue.put(("connect", fut))
        try:
            res = await fut
            if isinstance(res, Exception):
                raise res
        finally:
            self._mcp_connecting = False

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        session_key: str | None = None,
    ) -> None:
        """Update context for all tools that need routing info."""
        logger.debug(
            "🛠️ Setting tool context: channel={}, chat_id={}, message_id={}",
            channel,
            chat_id,
            message_id,
        )
        for name in ("message", "spawn", "automation"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    logger.debug("✅ Updating tool: {}", name)
                    if name == "message":
                        tool.set_context(channel, chat_id, message_id)
                    else:
                        tool.set_context(channel, chat_id, session_key)

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""

        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val}")'

        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_response_token: Callable[[str], Awaitable[None]] | None = None,
        *,
        channel: str | None = None,
        chat_id: str | None = None,
        skill_names: list[str] | None = None,
        profile_id: str | None = None,
        model: str | None = None,
        session_key: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop.

        The system prompt (``messages[0]``) is refreshed before every
        LLM call so the model always sees an up-to-date timestamp,
        channel info, and current iteration number.
        """
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        loop_start = time.monotonic()

        self.context.regenerate_nonce()
        static_prompt = self.context.build_static_prompt(
            skill_names,
            memory_max_prompt_tokens=self.memory_consolidator.memory_max_prompt_tokens,
            profile_id=profile_id,
        )
        active_model = model or self.model
        active_provider = self._resolve_provider_for_model(active_model)

        if not active_provider:
            return "No provider is configured for the selected model.", tools_used, messages

        # Tool definitions don't change mid-loop; compute once.
        tool_defs = self.tools.get_definitions()

        if session_key:
            self._steering_queues[session_key] = []

        while iteration < self.max_iterations:
            if session_key and session_key in self._steering_queues:
                steer_msgs = self._steering_queues[session_key]
                if steer_msgs:
                    logger.info("Steering loop with {} new messages", len(steer_msgs))
                    for msg in steer_msgs:
                        # Prefix the steering message so the LLM clearly understands it's an interruption
                        steer_text = f"**[USER INJECTION DURING TASK]**\n\n{msg['content']}"
                        
                        # Properly construct content with media so the model can see the images
                        content = self.context._build_user_content(steer_text, msg.get("media"))
                        
                        entry = {
                            "role": "user",
                            "content": content,
                        }
                        if msg.get("timestamp"):
                            entry["timestamp"] = msg.get("timestamp")
                            
                        metadata = {}
                        if msg.get("media"):
                            metadata["media"] = msg["media"]
                        if msg.get("attachments"):
                            metadata["attachments"] = msg["attachments"]
                        if metadata:
                            entry["metadata"] = metadata
                            
                        messages.append(entry)
                    self._steering_queues[session_key] = []
            # Wall-clock safety: abort if the loop has been running too long
            elapsed = time.monotonic() - loop_start
            if elapsed > self.loop_wall_timeout:
                logger.warning(f"Session wall timeout ({self.loop_wall_timeout}s) reached after {elapsed:.1f}s.")
                final_content = (
                    f"I reached the maximum time limit for processing "
                    f"(elapsed: {elapsed:.0f}s, cap: {self.loop_wall_timeout}s). "
                    f"Try breaking the task into smaller steps."
                )
                break
            iteration += 1

            active_kbs = None
            try:
                from shibaclaw.agent.knowledge_manager import KnowledgeManager
                import asyncio
                
                km = KnowledgeManager(self.context.workspace)
                all_collections = await asyncio.to_thread(km.list_collections)
                
                session_kb_ids = []
                if chat_id:
                    from shibaclaw.webui.agent_manager import agent_manager
                    if agent_manager.pm:
                        sess = agent_manager.pm.get_or_create(chat_id)
                        session_kb_ids = sess.metadata.get("knowledge_bases", [])
                
                mentioned_kb_names = [k.lower() for k in (metadata.get("mentioned_kbs", []) if metadata else [])]

                if all_collections and (session_kb_ids or mentioned_kb_names):
                    active_kbs = []
                    new_session_kb_ids = list(session_kb_ids)
                    changed = False
                    
                    for col in all_collections:
                        col_id = col.get("id", "")
                        col_name = col.get("name", "")
                        
                        is_mentioned = col_name.lower() in mentioned_kb_names
                        if is_mentioned and col_id not in new_session_kb_ids:
                            new_session_kb_ids.append(col_id)
                            changed = True
                            
                        if col_id in new_session_kb_ids:
                            col_desc = col.get("description", "")
                            desc_part = f" - Desc: {col_desc}" if col_desc else ""
                            active_kbs.append(f"ID: {col_id} (Name: '{col_name}'){desc_part}")
                            
                    if changed and chat_id:
                        from shibaclaw.webui.agent_manager import agent_manager
                        if agent_manager.pm:
                            sess = agent_manager.pm.get_or_create(chat_id)
                            sess.metadata["knowledge_bases"] = new_session_kb_ids
                            agent_manager.pm.save(sess)
            except Exception:
                pass

            live_block = self.context.build_runtime_block(
                channel=channel,
                chat_id=chat_id,
                iteration=iteration,
                max_iterations=self.max_iterations,
                available_channels=self._available_channels,
                active_kbs=active_kbs,
                metadata=metadata,
            )
            messages[0] = {
                "role": "system",
                "content": static_prompt + "\n\n---\n\n" + live_block,
            }

            response = await active_provider.chat_with_retry_streaming(
                messages=messages,
                on_token=on_response_token,
                tools=tool_defs,
                model=active_model,
            )

            if response.has_tool_calls:
                if on_progress:
                    thought = self._strip_think(response.content)
                    if thought:
                        await on_progress(thought)
                    tool_hint = self._tool_hint(response.tool_calls)
                    tool_hint = self._strip_think(tool_hint)
                    await on_progress(tool_hint, tool_hint=True)

                tool_call_dicts = [tc.to_openai_tool_call() for tc in response.tool_calls]
                messages = self.context.add_assistant_message(
                    messages,
                    response.content,
                    tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.debug("Tool call: {}({})", tool_call.name, args_str[:200])
                    try:
                        tool_future = asyncio.ensure_future(
                            self.tools.execute(tool_call.name, tool_call.arguments)
                        )
                        # Emit periodic "still working" progress while the
                        # tool runs, so the UI doesn't look stuck.
                        _heartbeat = 15  # seconds
                        _waited = 0
                        while not tool_future.done():
                            try:
                                await asyncio.wait_for(
                                    asyncio.shield(tool_future),
                                    timeout=min(_heartbeat, self.tool_timeout - _waited),
                                )
                            except asyncio.TimeoutError:
                                _waited += _heartbeat
                                if _waited >= self.tool_timeout:
                                    break
                                if on_progress:
                                    await on_progress(
                                        f"⏳ {tool_call.name} still running ({_waited}s)…",
                                        tool_hint=True,
                                    )
                                continue

                        if not tool_future.done():
                            tool_future.cancel()
                            result = (
                                f"Error: Tool '{tool_call.name}' timed out after "
                                f"{_waited}s (cap: {self.tool_timeout}s)"
                            )
                        else:
                            result = tool_future.result()
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        result = f"Error: Tool '{tool_call.name}' failed: {exc}"
                    if len(result) > self._TOOL_RESULT_LOOP_MAX_CHARS:
                        half = self._TOOL_RESULT_LOOP_MAX_CHARS // 2
                        result = (
                            result[:half]
                            + f"\n...[TRUNCATED — {len(result)} chars total]...\n"
                            + result[-half:]
                        )
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # Strip think from logs/debug output, but keep full content for memory (so UI can reload it)
                clean = self._strip_think(response.content)
                # Don't persist error responses to session history — they can
                # poison the context and cause permanent 400 loops (#1303).
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                
                messages = self.context.add_assistant_message(
                    messages,
                    response.content,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                # Preserve full content (including <think>) for the UI
                final_content = response.content
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        if session_key:
            self._steering_queues.pop(session_key, None)

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.debug("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
                continue
            except Exception as e:
                logger.warning("Error while consuming inbound message: {}. Continuing.", e)
                continue

            cmd = msg.content.strip().lower()
            if cmd == "/stop":
                await self._handle_stop(msg)
            elif cmd == "/restart":
                await self._handle_restart(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(
                    lambda t, k=msg.session_key: (
                        self._active_tasks.get(k, [])
                        and self._safe_remove_task(self._active_tasks.get(k, []), t)
                    )
                )

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"🐕 Halted {total} hunt(s)." if total else "No active scent to stop."
        await self.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )
        )

    _ALLOWED_SUBCOMMANDS = frozenset({"web", "gateway", "cli"})

    @staticmethod
    def _safe_argv() -> list[str]:
        """Return only trusted argv entries (flags + known subcommands)."""
        import sys
        if getattr(sys, "frozen", False):
            safe = [sys.executable]
            for arg in sys.argv[1:]:
                if arg.startswith("-") or arg in ShibaBrain._ALLOWED_SUBCOMMANDS:
                    safe.append(arg)
            return safe
        elif hasattr(sys, "orig_argv"):
            return sys.orig_argv
        else:
            return [sys.executable] + sys.argv

    async def _handle_restart(self, msg: InboundMessage) -> None:
        await self.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐕 Woof! Restarting the hunt...",
            )
        )

        safe_argv = self._safe_argv()

        async def _do_restart():
            await asyncio.sleep(1)
            import subprocess
            subprocess.Popen(safe_argv)
            os._exit(0)

        self._schedule_background(_do_restart())

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the per-session lock."""
        lock = self._session_locks.setdefault(msg.session_key, asyncio.Lock())
        async with lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="",
                            metadata=msg.metadata or {},
                        )
                    )
            except asyncio.CancelledError:
                logger.debug("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="Sorry, I encountered an error.",
                    )
                )

    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
        fut = asyncio.get_running_loop().create_future()
        await self._mcp_queue.put(("close", fut))
        res = await fut
        if isinstance(res, Exception):
            raise res

    def _schedule_background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(lambda t: self._safe_remove_task(self._background_tasks, t))

    @staticmethod
    def _safe_remove_task(tasks: list, task) -> None:
        try:
            tasks.remove(task)
        except ValueError:
            pass

    def stop(self) -> None:
        self._running = False
        if self._mcp_worker_task and not self._mcp_worker_task.done():
            self._mcp_worker_task.cancel()
        logger.debug("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str, bool], Awaitable[None]] | None = None,
        on_response_token: Callable[[str], Awaitable[None]] | None = None,
        profile_id_override: str | None = None,
    ) -> OutboundMessage | None:
        if self.provider is None:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐕 Shiba is idle. Please configure an AI provider in the WebUI to start hunting!",
            )
        if msg.channel == "system":
            channel, chat_id = (
                msg.chat_id.split(":", 1) if ":" in msg.chat_id else ("cli", msg.chat_id)
            )
            logger.debug("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            profile_id = session.metadata.get("profile_id") or None
            await self.memory_consolidator.maybe_consolidate_by_tokens(session)
            self._set_tool_context(
                channel,
                chat_id,
                msg.metadata.get("message_id"),
                session_key=key,
            )
            history = session.get_history(max_messages=0)
            current_role = "assistant" if msg.sender_id == "subagent" else "user"
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content,
                channel=channel,
                chat_id=chat_id,
                current_role=current_role,
                memory_max_prompt_tokens=self.memory_consolidator.memory_max_prompt_tokens,
                available_channels=self._available_channels,
                profile_id=profile_id,
            )
            final_content, _, all_msgs = await self._run_agent_loop(
                messages,
                channel=channel,
                chat_id=chat_id,
                profile_id=profile_id,
                session_key=key,
                metadata=msg.metadata,
            )
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=final_content or "Background task completed.",
            )

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        key = session_key or msg.session_key

        if self.session_router:
            if resolved_key := self.session_router.resolve(key):
                logger.info("Cross-session route: {} -> {}", key, resolved_key)
                key = resolved_key
        logger.debug(
            "Processing inbound message from {}:{} for session {}: {}",
            msg.channel,
            msg.sender_id,
            key,
            preview,
        )
        session = self.sessions.get_or_create(key)
        profile_id = profile_id_override or session.metadata.get("profile_id") or None
        if profile_id_override and session.metadata.get("profile_id") != profile_id_override:
            session.metadata["profile_id"] = profile_id_override
            self.sessions.save(session)

        # Normalize model ID if present
        if model := session.metadata.get("model"):
            from shibaclaw.helpers.model_ids import canonicalize_model_id

            canonical = canonicalize_model_id(self.config, model)
            if canonical != model:
                session.metadata["model"] = canonical
                self.sessions.save(session)

        cmd = msg.content.strip().lower()
        if cmd == "/new":
            snapshot = session.messages[session.last_consolidated :]
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)

            if snapshot:
                self._schedule_background(self.memory_consolidator.archive_snapshot(snapshot))

            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content="New session started."
            )
        if cmd == "/help":
            lines = [
                "🐕 shibaclaw commands:",
                "/new — Start a new conversation",
                "/stop — Stop the current task",
                "/restart — Restart the bot",
                "/help — Show available commands",
            ]
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="\n".join(lines),
            )
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        self._set_tool_context(
            msg.channel,
            msg.chat_id,
            msg.metadata.get("message_id"),
            session_key=key,
        )
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=0)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            memory_max_prompt_tokens=self.memory_consolidator.memory_max_prompt_tokens,
            available_channels=self._available_channels,
            profile_id=profile_id,
        )

        _user_entry = {"role": "user", "content": msg.content, "timestamp": datetime.now().isoformat()}
        metadata = {}
        if msg.metadata:
            metadata.update(msg.metadata)
        if msg.media:
            metadata["media"] = msg.media
        if metadata:
            _user_entry["metadata"] = metadata
        session.messages.append(_user_entry)
        self.sessions.save(session)
        
        if msg.metadata and msg.metadata.get("no_reply"):
            return None
        _pre_saved_count = 1

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = {"_progress": True, "_tool_hint": tool_hint, **(msg.metadata or {})}
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                    metadata=meta,
                )
            )

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages,
            on_progress=on_progress or _bus_progress,
            on_response_token=on_response_token,
            channel=msg.channel,
            chat_id=msg.chat_id,
            profile_id=profile_id,
            model=session.metadata.get("model") or None,
            session_key=key,
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        self._save_turn(session, all_msgs, 1 + len(history) + _pre_saved_count)
        self.sessions.save(session)
        self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
        self._schedule_background(self.memory_consolidator.maybe_proactive_learn(session))

        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None

        media_list = []
        media_match = _MEDIA_RE.search(final_content)
        if media_match:
            try:
                media_json = json.loads(media_match.group(0))
                raw_media = media_json.get("media", [])
                media_list = [
                    str((self.workspace / p).resolve()) if not Path(p).is_absolute() else p
                    for p in raw_media
                ]
                final_content = final_content.replace(media_match.group(0), "").strip()
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.debug("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            media=media_list,
            metadata=msg.metadata or {},
        )

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:

        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue

            if role == "assistant" and entry.get("tool_calls"):
                mt = self.tools.get("message")
                if mt and isinstance(mt, MessageTool) and mt.latest_resolved_media_map:
                    entry["tool_calls"] = json.loads(json.dumps(entry["tool_calls"]))
                    for tc in entry["tool_calls"]:
                        if tc.get("function", {}).get("name") == "message":
                            try:
                                args = json.loads(tc["function"]["arguments"])
                                if "media" in args and isinstance(args["media"], list):
                                    args["media"] = [
                                        mt.latest_resolved_media_map.get(p, p)
                                        for p in args["media"]
                                    ]
                                    tc["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
                            except Exception as _e:
                                logger.debug("Ignored error: {}", _e)

            if role == "assistant" and isinstance(content, str):
                media_match = _MEDIA_RE.search(content)
                if media_match:
                    try:
                        media_json = json.loads(media_match.group(0))
                        entry.setdefault("metadata", {})["media"] = media_json.get("media", [])
                        entry["content"] = content.replace(media_match.group(0), "").strip()
                        content = entry["content"]
                    except Exception as _e:
                        logger.debug("Ignored error: {}", _e)

            if (
                role == "tool"
                and isinstance(content, str)
                and len(content) > self._TOOL_RESULT_MAX_CHARS
            ):
                entry["content"] = content[: self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(
                    ScentBuilder._RUNTIME_CONTEXT_TAG
                ):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if (
                            c.get("type") == "text"
                            and isinstance(c.get("text"), str)
                            and c["text"].startswith(ScentBuilder._RUNTIME_CONTEXT_TAG)
                        ):
                            continue
                        if c.get("type") == "image_url" and c.get("image_url", {}).get(
                            "url", ""
                        ).startswith("data:image/"):
                            path = (c.get("_meta") or {}).get("path", "")
                            placeholder = f"[image: {path}]" if path else "[image]"
                            filtered.append({"type": "text", "text": placeholder})
                        else:
                            filtered.append(c)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_response_token: Callable[[str], Awaitable[None]] | None = None,
        on_notify: Callable[..., Awaitable[None]] | None = None,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        profile_id: str | None = None,
    ) -> OutboundMessage | None:
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            media=media,
            metadata=metadata or {},
        )
        return await self._process_message(
            msg,
            session_key=session_key,
            on_progress=on_progress,
            on_response_token=on_response_token,
            profile_id_override=profile_id,
        )
