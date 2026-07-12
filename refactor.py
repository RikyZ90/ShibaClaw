import re

path = r'c:\Users\Rikyz\.gemini\antigravity\scratch\shibaclaw_next\shibaclaw\agent\loop.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Import MCPManager
content = content.replace('from shibaclaw.agent.context import ScentBuilder', 'from shibaclaw.agent.mcp_manager import MCPManager\nfrom shibaclaw.agent.context import ScentBuilder')

# 2. Init modifications
old_init = '''        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._mcp_queue: asyncio.Queue = asyncio.Queue()
        self._mcp_worker_task: asyncio.Task = asyncio.create_task(self._mcp_worker())
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []'''

new_init = '''        self._running = False
        self.mcp = MCPManager(self.tools)
        if mcp_servers:
            self.mcp.reconfigure(mcp_servers)
            
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []'''
content = content.replace(old_init, new_init)

# 3. reconfigure modifications
old_reconfig = '''        # MCP: reconfigure incrementally
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
                logger.error("MCP reconnection after reconfigure failed: {}", exc)'''

new_reconfig = '''        # MCP: reconfigure incrementally
        new_mcp = new_cfg.tools.mcp_servers or {}
        mcp_changed = self.mcp.reconfigure(new_mcp)

        # Re-register default tools (always needed for exec/web/restrict changes)
        self.tools = SkillVault()
        self.mcp.tools = self.tools
        self._register_default_tools()

        # MCP: reconnect incrementally so tools are updated immediately
        if mcp_changed and new_mcp:
            try:
                await self.mcp.connect()
            except Exception as exc:
                logger.error("MCP reconnection after reconfigure failed: {}", exc)'''
content = content.replace(old_reconfig, new_reconfig)

# 4. _register_default_tools modification
old_reg = '''        try:
            from shibaclaw.agent.tools.mcp import register_active_mcp_tools
            register_active_mcp_tools(self.tools)
        except Exception as e:
            logger.error("Failed to restore active MCP tools on registry rebuild: {}", e)'''

new_reg = '''        self.mcp.restore_active_tools()'''
content = content.replace(old_reg, new_reg)

# 5. Connect and close usages
content = content.replace('await self._connect_mcp()', 'await self.mcp.connect()')

old_close_mcp = '''    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
        fut = asyncio.get_running_loop().create_future()
        await self._mcp_queue.put(("close", fut))
        res = await fut
        if isinstance(res, Exception):
            raise res'''

new_close_mcp = '''    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
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
        
        await self.mcp.close()'''
content = content.replace(old_close_mcp, new_close_mcp)

# 6. Delete _mcp_configs_differ
content = re.sub(r'    def _mcp_configs_differ\(a: dict, b: dict\) -> bool:.*?    def process_message\(self, msg: InboundMessage\) -> None:', '    def process_message(self, msg: InboundMessage) -> None:', content, flags=re.DOTALL)

# 7. Delete worker and related functions
content = re.sub(r'    async def _mcp_worker\(self\) -> None:.*?    def _set_tool_context\(', '    def _set_tool_context(', content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
