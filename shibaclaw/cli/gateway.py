"""Gateway service runner and health server for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from rich.panel import Panel
from loguru import logger
from shibaclaw import __logo__, __version__
from .utils import console
from shibaclaw.helpers.logging import setup_shiba_logging


@dataclass(frozen=True)
class HeartbeatTarget:
    channel: str
    chat_id: str
    session_key: str


def resolve_webui_session_key(session_key: str | None, chat_id: str | None) -> str | None:
    if session_key:
        return session_key
    if not chat_id:
        return None
    if chat_id.startswith("webui:"):
        return chat_id
    return f"webui:{chat_id[:8]}"


def resolve_cron_target(job: Any) -> HeartbeatTarget:
    channel = job.payload.channel or "cli"
    chat_id = job.payload.to or "direct"
    session_key = job.payload.session_key or f"{channel}:{chat_id}"

    if channel == "webui":
        session_key = resolve_webui_session_key(job.payload.session_key, job.payload.to) or session_key
        chat_id = session_key.split(":", 1)[1] if ":" in session_key else session_key

    return HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=session_key)


def select_heartbeat_target(
    sessions: list[dict[str, Any]], enabled_channels: set[str],
) -> HeartbeatTarget:
    webui_candidate: HeartbeatTarget | None = None

    for item in sessions:
        key = item.get("key", "")
        if ":" not in key:
            continue

        channel, chat_id = key.split(":", 1)
        target = HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=key)

        if channel == "webui":
            webui_candidate = webui_candidate or target
            continue

        if channel not in {"cli", "system"} and channel in enabled_channels:
            return target

    if webui_candidate:
        return webui_candidate

    return HeartbeatTarget(channel="cli", chat_id="direct", session_key="cli:direct")


def _pick_recent_session_target(
    sessions: list[dict[str, Any]],
    channel: str,
) -> HeartbeatTarget | None:
    for item in sessions:
        key = item.get("key", "")
        if ":" not in key:
            continue
        key_channel, chat_id = key.split(":", 1)
        if key_channel != channel:
            continue
        return HeartbeatTarget(channel=key_channel, chat_id=chat_id, session_key=key)
    return None


def resolve_heartbeat_targets(
    configured_targets: dict[str, str] | None,
    sessions: list[dict[str, Any]],
    enabled_channels: set[str],
) -> list[HeartbeatTarget]:
    if not configured_targets:
        return [select_heartbeat_target(sessions, enabled_channels)]

    resolved: list[HeartbeatTarget] = []
    for channel, raw_target in configured_targets.items():
        target_value = (raw_target or "").strip()
        normalized = target_value.lower()

        if normalized in {"", "recent", "latest", "auto"}:
            recent = _pick_recent_session_target(sessions, channel)
            if recent is not None:
                resolved.append(recent)
                continue
            if channel in {"cli", "system"}:
                target_value = "direct"
            else:
                logger.warning(
                    "Heartbeat: target {}:{} has no matching recent session; skipping",
                    channel,
                    raw_target,
                )
                continue

        if channel == "webui":
            session_key = resolve_webui_session_key(
                target_value if target_value.startswith("webui:") else None,
                target_value,
            )
            if not session_key:
                continue
            chat_id = session_key.split(":", 1)[1] if ":" in session_key else session_key
            resolved.append(HeartbeatTarget(channel="webui", chat_id=chat_id, session_key=session_key))
            continue

        chat_id = target_value or "direct"
        resolved.append(HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=f"{channel}:{chat_id}"))

    return resolved


def _iter_webui_notify_urls() -> list[str]:
    raw_urls = [
        os.environ.get("SHIBACLAW_WEBUI_NOTIFY_URL", "").strip(),
        os.environ.get("SHIBACLAW_WEBUI_URL", "").strip(),
        "http://shibaclaw-web:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
    seen: set[str] = set()
    urls: list[str] = []

    for url in raw_urls:
        if not url:
            continue
        normalized = url.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)

    return urls


async def notify_webui_session(
    session_key: str,
    response: str,
    auth_token: str | None,
    *,
    source: str = "heartbeat",
    persist: bool = True,
) -> bool:
    if not session_key or not response:
        return False

    import httpx

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {
        "session_key": session_key,
        "content": response,
        "source": source,
        "persist": persist,
    }

    for base_url in _iter_webui_notify_urls():
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                result = await client.post(
                    f"{base_url}/api/internal/session-notify",
                    json=payload,
                    headers=headers,
                )
            if result.is_success:
                logger.info("{}: delivered response to WebUI session {}", source.capitalize(), session_key)
                return True
            logger.debug(
                "{}: WebUI notify endpoint returned {} from {}",
                source.capitalize(),
                result.status_code,
                base_url,
            )
        except Exception as exc:
            logger.debug("{}: failed to notify WebUI via {}: {}", source.capitalize(), base_url, exc)

    logger.warning("{}: unable to deliver response to WebUI session {}", source.capitalize(), session_key)
    return False


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
    from shibaclaw.helpers.helpers import sync_skills, sync_profiles

    setup_shiba_logging(level="DEBUG" if verbose else "INFO")
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    config = _load_runtime_config(config_path, workspace)
    port = port_override if port_override is not None else config.gateway.port
    host = host if host is not None else (config.gateway.host or "127.0.0.1")

    sync_skills(config.workspace_path)
    sync_profiles(config.workspace_path)

    auth_token = get_auth_token()
    bus = MessageBus(rate_limit_per_minute=config.gateway.rate_limit_per_minute)
    provider = _make_provider(config, exit_on_error=False)
    if provider is None:
        console.print("[yellow]🐾 Entering idle mode...[/yellow]")
        console.print("[dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]")

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
        restrict_to_workspace=config.tools.restrict_to_workspace,
        learning_enabled=config.agents.defaults.learning_enabled,
        learning_interval=config.agents.defaults.learning_interval,
        memory_max_prompt_tokens=config.agents.defaults.memory_max_prompt_tokens,
        memory_compact_threshold_tokens=config.agents.defaults.memory_compact_threshold_tokens,
    )

    channels = ChannelManager(config, bus)

    def _pick_heartbeat_target() -> HeartbeatTarget:
        return select_heartbeat_target(
            session_manager.list_sessions(),
            set(channels.enabled_channels),
        )

    async def on_heartbeat_execute(
        tasks: str,
        *,
        session_key: str = "heartbeat:default",
        profile_id: str | None = None,
        targets: dict[str, str] | None = None,
    ) -> str:
        async def _noop_progress(*_args, **_kwargs) -> None:
            return None

        resolved_targets = resolve_heartbeat_targets(
            targets,
            session_manager.list_sessions(),
            set(channels.enabled_channels),
        )
        exec_target = resolved_targets[0] if resolved_targets else _pick_heartbeat_target()

        outbound = await agent.process_direct(
            tasks,
            session_key,
            exec_target.channel,
            exec_target.chat_id,
            on_progress=_noop_progress,
            profile_id=profile_id,
        )
        return outbound.content if outbound else ""

    async def on_heartbeat_notify(
        response: str, *, targets: dict[str, str] | None = None,
    ) -> None:
        from shibaclaw.bus.events import OutboundMessage

        if not response:
            return

        resolved_targets = resolve_heartbeat_targets(
            targets,
            session_manager.list_sessions(),
            set(channels.enabled_channels),
        )

        for target in resolved_targets:
            if target.channel == "webui":
                await notify_webui_session(target.session_key, response, auth_token, source="heartbeat")
                continue
            if target.channel == "cli":
                continue
            await bus.publish_outbound(
                OutboundMessage(channel=target.channel, chat_id=target.chat_id, content=response)
            )

        if not any(target.channel != "cli" for target in resolved_targets):
            logger.info("Heartbeat: generated a response but found no deliverable session")

    hb_cfg = config.gateway.heartbeat
    heartbeat = HeartbeatService(
        workspace=config.workspace_path, provider=provider, model=agent.model,
        on_execute=on_heartbeat_execute, on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s, enabled=hb_cfg.enabled,
        session_key=hb_cfg.session_key,
        targets=hb_cfg.targets,
        profile_id=hb_cfg.profile_id,
    )

    status_parts = [
        f"[bold gold1]{__logo__} ShibaClaw Gateway v{__version__}[/bold gold1] [dim](port {port})[/dim]",
        "",
    ]
    if channels.enabled_channels:
        status_parts.append(f"  [green]✓[/green] Channels: {', '.join(channels.enabled_channels)}")
    if provider is None:
        status_parts.append("  [yellow]⚠ No AI provider configured[/yellow]")
        status_parts.append("  [dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]")
    c_status = cron.status()
    hb_info = f"✓ Heartbeat: {hb_cfg.interval_s}s" if hb_cfg.enabled else "Heartbeat: disabled"
    status_parts.append(
        f"  [green]✓[/green] Cron: {c_status['jobs']} jobs"
        if c_status["jobs"] > 0
        else "  [dim]Cron: idle[/dim]"
    )
    status_parts.append(f"  {hb_info}")
    webui_url = os.environ.get("SHIBACLAW_WEBUI_URL", "http://localhost:3000")
    status_parts.append(f"  [cyan]🖥️  WebUI:[/cyan] [link={webui_url}]{webui_url}[/link]")
    status_parts.append("  [dim]Run [bold]shibaclaw print-token[/bold] to show the WebUI auth token[/dim]")
    console.print(Panel("\n".join(status_parts), expand=False, border_style="blue"))

    _state = {"restart": False}

    _UPDATE_CHECK_INTERVAL = float(os.environ.get("SHIBACLAW_UPDATE_CHECK_HOURS", "12")) * 3600

    async def _update_check_loop():
        await asyncio.sleep(60)
        while True:
            try:
                from shibaclaw.updater.checker import check_for_update
                result = await asyncio.get_event_loop().run_in_executor(None, check_for_update)
                if result.get("update_available"):
                    current = result.get("current", "?")
                    latest = result.get("latest", "?")
                    release_url = result.get("release_url", "")
                    msg = (
                        f"🆕 *ShibaClaw update available!*\n"
                        f"Version {current} → {latest}\n"
                        f"pip: pip install --upgrade shibaclaw\n"
                        f"Docker: docker compose pull && docker compose up -d\n"
                        f"{release_url}"
                    ).strip()
                    logger.info("🆕 Update available: {} → {} (pip install --upgrade shibaclaw)", current, latest)
                    await on_heartbeat_notify(msg)
                else:
                    logger.debug("Update check: already on latest version ({}).", result.get("current", "?"))
            except Exception as e:
                logger.debug("Update check failed: {}", e)
            await asyncio.sleep(_UPDATE_CHECK_INTERVAL)

    async def run():
        _start_time = time.time()

        async def _health_handler(reader, writer):
            nonlocal _state
            try:
                data = await asyncio.wait_for(reader.read(4096), timeout=2)
                request_line = data.split(b"\r\n", 1)[0].decode(errors="ignore")

                def _check_auth() -> bool:
                    if not auth_token:
                        return True
                    return f"Authorization: Bearer {auth_token}".encode() in data

                def _json_response(body: dict, status: int = 200) -> bytes:
                    phrase = "OK" if status == 200 else ("Unauthorized" if status == 401 else "Not Found")
                    payload = json.dumps(body, ensure_ascii=False).encode()
                    return (
                        f"HTTP/1.0 {status} {phrase}\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(payload)}\r\n"
                        f"\r\n"
                    ).encode() + payload

                if "POST" in request_line and "/restart" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        writer.write(_json_response({"status": "restarting"}))
                        _state["restart"] = True
                        asyncio.get_event_loop().call_later(
                            0.5,
                            lambda: [t.cancel() for t in asyncio.all_tasks()]
                        )
                elif "GET" in request_line and "/heartbeat/status" in request_line:
                    writer.write(_json_response(heartbeat.status()))
                elif "POST" in request_line and "/heartbeat/trigger" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        try:
                            result = await heartbeat.trigger_now()
                            writer.write(_json_response({"triggered": True, "response": result}))
                        except Exception as e:
                            writer.write(_json_response({"triggered": False, "error": str(e)}))
                elif "GET" in request_line:
                    writer.write(_json_response({
                        "status": "ok" if provider else "idle",
                        "uptime": int(time.time() - _start_time),
                        "provider_ready": provider is not None,
                    }))
                else:
                    writer.write(_json_response({"error": "not found"}, 404))
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()

        health_srv = await asyncio.start_server(_health_handler, host, port)
        try:
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
                health_srv.serve_forever(),
                _update_check_loop(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            if _state["restart"]:
                console.print("\n🔄 Restarting...")
            else:
                console.print("\nShutting down...")
        finally:
            await agent.close_mcp()
            heartbeat.stop()
            agent.stop()
            await channels.stop_all()

    await run()

    if _state["restart"]:
        os.execv(sys.executable, [sys.executable] + sys.argv)