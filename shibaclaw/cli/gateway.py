"""Gateway service runner and health server for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import logging
from pathlib import Path
from typing import Any, Optional
from rich.panel import Panel
from shibaclaw import __logo__, __version__
from .utils import console
from shibaclaw.helpers.logging import setup_shiba_logging

async def gateway_command(
    host: Optional[str] = None,
    port_override: Optional[int] = None,
    workspace: Optional[str] = None,
    verbose: bool = False,
    config_path: Optional[str] = None,
):
    """Start the shibaclaw gateway."""
    from .commands import _load_runtime_config, _make_provider
    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.bus.queue import MessageBus
    from shibaclaw.integrations.manager import ChannelManager
    from shibaclaw.config.paths import get_cron_dir
    from shibaclaw.cron.service import CronService
    from shibaclaw.heartbeat.service import HeartbeatService
    from shibaclaw.brain.manager import PackManager
    from shibaclaw.webui.server import get_auth_token

    setup_shiba_logging(level="DEBUG" if verbose else "INFO")
    if verbose: logging.basicConfig(level=logging.DEBUG)

    config = _load_runtime_config(config_path, workspace)
    port = port_override if port_override is not None else config.gateway.port
    host = host if host is not None else (config.gateway.host or "127.0.0.1")

    auth_token = get_auth_token()
    if auth_token:
        console.print(f"  [dim]🔑 To retrieve the WebUI token, run:[/dim] [bold cyan]docker exec -it shibaclaw-gateway shibaclaw print-token[/bold cyan]")

    bus = MessageBus()
    provider = _make_provider(config, exit_on_error=False)
    if provider is None:
        console.print("[yellow]🐾 Entering idle mode...[/yellow]")
        console.print("[yellow]You can now run:[/yellow] [bold]docker exec -it shibaclaw-gateway shibaclaw onboard --wizard[/bold]")

    session_manager = PackManager(config.workspace_path)
    cron = CronService(get_cron_dir() / "jobs.json")

    agent = ShibaBrain(
        bus=bus, provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        context_window_tokens=config.agents.defaults.context_window_tokens,
        web_search_config=config.tools.web.search,
        web_proxy=config.tools.web.proxy,
        exec_config=config.tools.exec,
        cron_service=cron,
        mcp_servers=config.tools.mcp_servers,
        channels_config=config.channels,
        learning_enabled=config.agents.defaults.learning_enabled,
        learning_interval=config.agents.defaults.learning_interval,
        memory_max_prompt_tokens=config.agents.defaults.memory_max_prompt_tokens,
        memory_compact_threshold_tokens=config.agents.defaults.memory_compact_threshold_tokens,
    )

    # ── Cron Logic ──
    async def on_cron_job(job) -> str | None:
        reminder_note = f"[Scheduled Task] Timer finished.\n\nTask '{job.name}' triggered.\nMessage: {job.payload.message}"
        outbound = await agent.process_direct(reminder_note, f"cron:{job.id}", job.payload.channel or "cli", job.payload.to or "direct")
        return outbound.content if outbound else ""
    cron.on_job = on_cron_job

    channels = ChannelManager(config, bus)

    # ── Heartbeat Logic ──
    def _pick_heartbeat_target() -> tuple[str, str]:
        enabled = set(channels.enabled_channels)
        for item in session_manager.list_sessions():
            key = item.get("key", "")
            if ":" in key:
                c, cid = key.split(":", 1)
                if c not in {"cli", "system"} and c in enabled: return c, cid
        return "cli", "direct"

    async def on_heartbeat_execute(tasks: str) -> str:
        c, cid = _pick_heartbeat_target()
        outbound = await agent.process_direct(tasks, "heartbeat", c, cid, on_progress=lambda *_: None)
        return outbound.content if outbound else ""

    async def on_heartbeat_notify(response: str) -> None:
        from shibaclaw.bus.events import OutboundMessage
        c, cid = _pick_heartbeat_target()
        if c != "cli" and response:
            await bus.publish_outbound(OutboundMessage(channel=c, chat_id=cid, content=response))

    hb_cfg = config.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=config.workspace_path, provider=provider, model=agent.model,
        on_execute=on_heartbeat_execute, on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s, enabled=hb_cfg.enabled
    )

    # ── Unified Status ──
    status_parts = [f"[bold gold1]{__logo__} ShibaClaw Gateway v{__version__}[/bold gold1] [dim](port {port})[/dim]", ""]
    if channels.enabled_channels: status_parts.append(f"  [green]✓[/green] [bold]Channels:[/bold] {', '.join(channels.enabled_channels)}")
    else: status_parts.append("  [yellow]⚠ No channels enabled[/yellow]")
    
    c_status, hb_info = cron.status(), f"[green]✓[/green] [bold]Heartbeat:[/bold] {hb_cfg.interval_s}s" if hb_cfg.enabled else "[dim]Heartbeat: disabled[/dim]"
    status_parts.append(f"  [green]✓[/green] [bold]Cron:[/bold] {c_status['jobs']} jobs" if c_status["jobs"] > 0 else "  [dim]Cron: idle[/dim]")
    status_parts.append(f"  {hb_info}")
    webui_url = os.environ.get("SHIBACLAW_WEBUI_URL", "http://localhost:3000")
    status_parts.append(f"\n  [cyan]🖥️  WebUI:[/cyan] [link={webui_url}]{webui_url}[/link]")
    console.print(Panel("\n".join(status_parts), expand=False, border_style="blue"))

    # ── Server Loop ──
    _state = {"restart": False}

    async def run():
        _start_time = time.time()
        
        async def _health_handler(reader, writer):
            nonlocal _state
            try:
                data = await asyncio.wait_for(reader.read(2048), timeout=2)
                if b"POST" in data and b"/restart" in data:
                    if auth_token and f"Authorization: Bearer {auth_token}".encode() not in data:
                        writer.write(b"HTTP/1.0 401 Unauthorized\r\n\r\n")
                    else:
                        writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"status": "restarting"}).encode())
                        _state["restart"] = True
                        asyncio.get_event_loop().call_later(0.5, lambda: [t.cancel() for t in asyncio.all_tasks()])
                elif b"GET" in data:
                    writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps({
                        "status": "ok" if provider else "idle", "uptime": int(time.time() - _start_time), "provider_ready": provider is not None
                    }).encode())
                await writer.drain()
            except Exception: pass
            finally: writer.close()

        health_srv = await asyncio.start_server(_health_handler, host, port)
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(agent.run(), channels.start_all(), health_srv.serve_forever())
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\n🔄 Restart requested..." if _state["restart"] else "\nShutting down...")
        finally:
            await agent.close_mcp()
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    await run()

    if _state["restart"]:
        # Re-exec the current process to apply new config (bare-metal + Docker)
        os.execv(sys.executable, [sys.executable] + sys.argv)
