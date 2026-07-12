from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any
from loguru import logger

from shibaclaw.agent.tools.mcp import connect_mcp_servers, clear_mcp_sessions, register_active_mcp_tools


class MCPManager:
    """Manages MCP server connections, disconnections, and tool registry."""

    def __init__(self, tools_registry: Any):
        self.tools = tools_registry
        self._mcp_servers = {}
        self._mcp_connected = False
        self._mcp_connecting = False
        self._mcp_queue = asyncio.Queue()
        self._mcp_stack: AsyncExitStack | None = None
        self._background_tasks: set[asyncio.Task] = set()
        
        self._worker_task = asyncio.create_task(self._mcp_worker())

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
            clear_mcp_sessions()
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)

        self._mcp_connected = False

    async def connect(self) -> None:
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

    async def close(self) -> None:
        """Close MCP connections."""
        fut = asyncio.get_running_loop().create_future()
        await self._mcp_queue.put(("close", fut))
        try:
            await fut
        finally:
            if not self._worker_task.done():
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

    def reconfigure(self, new_servers: dict) -> bool:
        """Update MCP servers config. Returns True if changed."""
        changed = self._mcp_configs_differ(new_servers, self._mcp_servers)
        if changed:
            self._mcp_servers = new_servers
            self._mcp_connected = False
        return changed

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
                result[k] = {
                    field: v_dict.get(field)
                    for field in ("type", "command", "args", "env", "url", "headers", "oauth")
                }
            return result

        return _serialize(a) != _serialize(b)

    def restore_active_tools(self) -> None:
        """Restore active MCP tools into the registry."""
        try:
            register_active_mcp_tools(self.tools)
        except Exception as e:
            logger.error("Failed to restore active MCP tools on registry rebuild: {}", e)

    def register_background_task(self, task: asyncio.Task) -> None:
        """Register a background task to be awaited during MCP close."""
        self._background_tasks.add(task)
        task.add_done_callback(lambda t: self._background_tasks.discard(t) if t in self._background_tasks else None)
