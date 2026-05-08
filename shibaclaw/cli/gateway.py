"""Gateway service runner and health server for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

import websockets
from loguru import logger
from rich.panel import Panel

from shibaclaw import __logo__, __version__
from shibaclaw.helpers.logging import setup_shiba_logging

from .utils import console


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
        session_key = (
            resolve_webui_session_key(job.payload.session_key, job.payload.to) or session_key
        )
        chat_id = session_key.split(":", 1)[1] if ":" in session_key else session_key

    return HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=session_key)


def select_heartbeat_target(
    sessions: list[dict[str, Any]],
    enabled_channels: set[str],
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
            resolved.append(
                HeartbeatTarget(channel="webui", chat_id=chat_id, session_key=session_key)
            )
            continue

        chat_id = target_value or "direct"
        resolved.append(
            HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=f"{channel}:{chat_id}")
        )

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
                logger.info(
                    "{}: delivered response to WebUI session {}", source.capitalize(), session_key
                )
                return True
            logger.debug(
                "{}: WebUI notify endpoint returned {} from {}",
                source.capitalize(),
                result.status_code,
                base_url,
            )
        except Exception as exc:
            logger.debug(
                "{}: failed to notify WebUI via {}: {}", source.capitalize(), base_url, exc
            )

    logger.warning(
        "{}: unable to deliver response to WebUI session {}", source.capitalize(), session_key
    )
    return False


async def gateway_command(
    host: Optional[str] = None,
    port_override: Optional[int] = None,
    ws_port_override: Optional[int] = None,
    workspace: Optional[str] = None,
    verbose: bool = False,
    config_path: Optional[str] = None,
):
    """Start the shibaclaw gateway."""
    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.brain.manager import PackManager
    from shibaclaw.bus.queue import MessageBus
    from shibaclaw.config.paths import get_cron_dir
    from shibaclaw.cron.service import CronService
    from shibaclaw.heartbeat.service import HeartbeatService
    from shibaclaw.helpers.helpers import sync_profiles, sync_skills
    from shibaclaw.integrations.manager import ChannelManager
    from shibaclaw.webui.server import get_auth_token

    from .commands import _load_runtime_config, _make_provider

    setup_shiba_logging(level="DEBUG" if verbose else "INFO")
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    config = _load_runtime_config(config_path, workspace)
    port = port_override if port_override is not None else config.gateway.port
    ws_port = ws_port_override if ws_port_override is not None else config.gateway.ws_port
    host = host if host is not None else (config.gateway.host or "127.0.0.1")

    sync_skills(config.workspace_path)
    sync_profiles(config.workspace_path)

    auth_token = get_auth_token()

    def _current_auth_token() -> str | None:
        return get_auth_token(refresh=True)
    bus = MessageBus(rate_limit_per_minute=config.gateway.rate_limit_per_minute)
    provider = _make_provider(config, exit_on_error=False)
    if provider is None:
        console.print("[yellow]🐾 Entering idle mode...[/yellow]")
        console.print(
            "[dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]"
        )

    session_manager = PackManager(config.workspace_path)
    cron = CronService(get_cron_dir() / "jobs.json")

    from shibaclaw.brain.routing import SessionRouter
    session_router = SessionRouter()

    agent = ShibaBrain(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        config=config,
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
        session_router=session_router,
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
        response: str,
        *,
        targets: dict[str, str] | None = None,
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
                # Try WebSocket broadcast first, fall back to HTTP callback
                if _ws_clients:
                    await _broadcast_ws_event(
                        "session.notify",
                        {
                            "content": response,
                            "source": "heartbeat",
                            "persist": True,
                        },
                        session_key=target.session_key,
                    )
                else:
                    await notify_webui_session(
                        target.session_key, response, auth_token, source="heartbeat"
                    )
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
        workspace=config.workspace_path,
        provider=provider,
        model=agent.model,
        on_execute=on_heartbeat_execute,
        on_notify=on_heartbeat_notify,
        interval_s=hb_cfg.interval_s,
        enabled=hb_cfg.enabled,
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
        status_parts.append(
            "  [dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]"
        )
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
    status_parts.append(
        "  [dim]Run [bold]shibaclaw print-token[/bold] to show the WebUI auth token[/dim]"
    )
    console.print(Panel("\n".join(status_parts), expand=False, border_style="blue"))

    _state = {"restart": False}

    async def _do_reload() -> None:
        """Hot-reload all components from the saved config file without restarting the process."""
        nonlocal config, provider
        try:
            new_cfg = _load_runtime_config(config_path, workspace)
        except Exception as e:
            logger.error("Hot-reload: failed to load config: {}", e)
            return

        # If network-binding settings changed, fall back to a full restart
        net_changed = (
            new_cfg.gateway.host != config.gateway.host
            or new_cfg.gateway.port != config.gateway.port
            or new_cfg.gateway.ws_port != config.gateway.ws_port
        )
        if net_changed:
            logger.warning(
                "Hot-reload: gateway host/port changed — falling back to full restart"
            )
            _state["restart"] = True
            asyncio.get_event_loop().call_later(
                0.5, lambda: [t.cancel() for t in asyncio.all_tasks()]
            )
            return

        try:
            new_provider = _make_provider(new_cfg, exit_on_error=False)
            config = new_cfg
            provider = new_provider

            await agent.reconfigure(new_cfg, new_provider)
            await channels.reconfigure(new_cfg)
            hb_cfg = new_cfg.gateway.heartbeat
            await heartbeat.reconfigure(hb_cfg, new_provider, agent.model)
            logger.info("Hot-reload complete")
        except Exception as e:
            logger.error("Hot-reload failed: {}", e)

    update_check_interval = float(os.environ.get("SHIBACLAW_UPDATE_CHECK_HOURS", "12")) * 3600

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
                    logger.info(
                        "🆕 Update available: {} → {} (pip install --upgrade shibaclaw)",
                        current,
                        latest,
                    )
                    await on_heartbeat_notify(msg)
                else:
                    logger.debug(
                        "Update check: already on latest version ({}).", result.get("current", "?")
                    )
            except Exception as e:
                logger.debug("Update check failed: {}", e)
            await asyncio.sleep(update_check_interval)

    # ── WebSocket server for realtime WebUI↔Gateway communication ───
    _ws_clients: set[websockets.ServerConnection] = set()
    _ws_start_time = time.time()

    async def _ws_handler(websocket: websockets.ServerConnection):
        """Handle a single WebSocket connection from the WebUI."""
        authed = False
        try:
            # First message must be hello with auth token
            raw = await asyncio.wait_for(websocket.recv(), timeout=10)
            hello = json.loads(raw)
            if hello.get("type") != "hello":
                await websocket.close(4001, "Expected hello")
                return
            expected_token = _current_auth_token()
            if expected_token and hello.get("token") != expected_token:
                await websocket.send(json.dumps({"type": "error", "error": "unauthorized"}))
                await websocket.close(4003, "Unauthorized")
                return
            authed = True
            _ws_clients.add(websocket)
            await websocket.send(
                json.dumps(
                    {
                        "type": "hello_ok",
                        "version": __version__,
                        "provider_ready": provider is not None,
                        "uptime": int(time.time() - _ws_start_time),
                    }
                )
            )
            logger.info("🔌 WebUI WebSocket client connected")

            async for raw_msg in websocket:
                try:
                    msg = json.loads(raw_msg)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg_type = msg.get("type", "")
                request_id = msg.get("id", str(uuid.uuid4())[:8])

                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

                elif msg_type == "request":
                    action = msg.get("action", "")
                    payload = msg.get("payload", {})
                    await _handle_ws_request(websocket, request_id, action, payload)

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.debug("WS handler error: {}", e)
        finally:
            _ws_clients.discard(websocket)
            if authed:
                logger.info("🔌 WebUI WebSocket client disconnected")

    async def _handle_ws_request(ws, request_id: str, action: str, payload: dict):
        """Dispatch a WebSocket request from the WebUI."""
        nonlocal _state

        def _ok(data: dict | None = None):
            return json.dumps(
                {"type": "response", "id": request_id, "ok": True, "payload": data or {}}
            )

        def _err(error: str):
            return json.dumps({"type": "response", "id": request_id, "ok": False, "error": error})

        try:
            if action == "status":
                await ws.send(
                    _ok(
                        {
                            "status": "ok" if provider else "idle",
                            "uptime": int(time.time() - _ws_start_time),
                            "provider_ready": provider is not None,
                        }
                    )
                )

            elif action == "chat":
                if not provider:
                    await ws.send(_err("no_provider"))
                    return

                async def _run_chat(ws, request_id, payload):
                    async def _on_ws_progress(text, *, tool_hint=False):
                        try:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "event",
                                        "name": "chat.progress",
                                        "request_id": request_id,
                                        "payload": {"c": text, "h": tool_hint},
                                    }
                                )
                            )
                        except websockets.ConnectionClosed:
                            pass

                    async def _on_ws_response_token(token_text):
                        try:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "event",
                                        "name": "chat.response_token",
                                        "request_id": request_id,
                                        "payload": {"c": token_text},
                                    }
                                )
                            )
                        except websockets.ConnectionClosed:
                            pass

                    try:
                        out = await agent.process_direct(
                            content=payload.get("content", ""),
                            session_key=payload.get("session_key", "webui:direct"),
                            channel=payload.get("channel", "webui"),
                            chat_id=payload.get("chat_id", "direct"),
                            on_progress=_on_ws_progress,
                            on_response_token=_on_ws_response_token,
                            media=payload.get("media"),
                            metadata=payload.get("metadata"),
                            profile_id=payload.get("profile_id"),
                        )
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "response",
                                    "id": request_id,
                                    "ok": True,
                                    "payload": {
                                        "content": out.content if out else "",
                                        "media": out.media if out else [],
                                    },
                                }
                            )
                        )
                    except Exception as e:
                        try:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "response",
                                        "id": request_id,
                                        "ok": False,
                                        "error": str(e),
                                    }
                                )
                            )
                        except websockets.ConnectionClosed:
                            pass

                asyncio.create_task(_run_chat(ws, request_id, payload))

            elif action == "restart":
                await ws.send(_ok({"status": "restarting"}))
                _state["restart"] = True
                asyncio.get_event_loop().call_later(
                    0.5, lambda: [t.cancel() for t in asyncio.all_tasks()]
                )

            elif action == "cron.list":

                def _ser(j):
                    return {
                        "id": j.id,
                        "name": j.name,
                        "enabled": j.enabled,
                        "schedule": {
                            "kind": j.schedule.kind,
                            "atMs": j.schedule.at_ms,
                            "everyMs": j.schedule.every_ms,
                            "expr": j.schedule.expr,
                            "tz": j.schedule.tz,
                        },
                        "payload": {
                            "message": j.payload.message,
                            "deliver": j.payload.deliver,
                            "channel": j.payload.channel,
                            "to": j.payload.to,
                        },
                        "state": {
                            "nextRunAtMs": j.state.next_run_at_ms,
                            "lastRunAtMs": j.state.last_run_at_ms,
                            "lastStatus": j.state.last_status,
                            "lastError": j.state.last_error,
                        },
                        "deleteAfterRun": j.delete_after_run,
                    }

                await ws.send(
                    _ok({"jobs": [_ser(j) for j in cron.list_jobs(include_disabled=True)]})
                )

            elif action == "cron.trigger":
                job_id = payload.get("job_id", "")
                ran = await cron.run_job(job_id, force=True)
                await ws.send(_ok({"triggered": ran}))

            elif action == "heartbeat.status":
                await ws.send(_ok(heartbeat.status()))

            elif action == "heartbeat.trigger":
                try:
                    result = await heartbeat.trigger_now()
                    await ws.send(_ok({"triggered": True, "response": result}))
                except Exception as e:
                    await ws.send(_err(str(e)))

            elif action == "archive":
                snapshot = payload.get("snapshot", [])
                archived = False
                if snapshot and hasattr(agent, "memory_consolidator"):
                    try:
                        await agent.memory_consolidator.archive_snapshot(snapshot)
                        archived = True
                    except Exception:
                        pass
                await ws.send(_ok({"archived": archived}))

            else:
                await ws.send(_err(f"unknown action: {action}"))

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            try:
                await ws.send(_err(str(e)))
            except Exception:
                pass

    async def _broadcast_ws_event(name: str, payload: dict, session_key: str | None = None):
        """Broadcast an event to all connected WebSocket clients."""
        msg = json.dumps(
            {
                "type": "event",
                "name": name,
                "session_key": session_key,
                "payload": payload,
            }
        )
        for ws in list(_ws_clients):
            try:
                await ws.send(msg)
            except Exception:
                _ws_clients.discard(ws)

    async def on_cron_job(job) -> str | None:
        """Execute a cron job: run an agent turn then deliver the response."""
        from shibaclaw.bus.events import OutboundMessage

        session_key = job.payload.session_key or f"cron:{job.id}"

        async def _noop_progress(*_args, **_kwargs) -> None:
            return None

        out = await agent.process_direct(
            job.payload.message,
            session_key,
            channel="cron",
            chat_id=job.id,
            on_progress=_noop_progress,
            metadata={"hidden": True},
        )
        response = out.content if out else ""
        if not response:
            return None

        if job.payload.deliver and job.payload.channel and job.payload.to:
            await bus.publish_outbound(
                OutboundMessage(
                    channel=job.payload.channel,
                    chat_id=job.payload.to,
                    content=response,
                )
            )
        elif _ws_clients:
            await _broadcast_ws_event(
                "session.notify",
                {"content": response, "source": "cron", "persist": False},
                session_key=session_key,
            )
        else:
            await notify_webui_session(
                session_key, response, auth_token, source="cron", persist=False
            )

        return response

    cron.on_job = on_cron_job

    async def run():
        _start_time = time.time()
        _ws_start_time = _start_time

        async def _health_handler(reader, writer):
            nonlocal _state
            try:
                data = await asyncio.wait_for(reader.read(65536), timeout=5)
                request_line = data.split(b"\r\n", 1)[0].decode(errors="ignore")

                def _check_auth() -> bool:
                    expected_token = _current_auth_token()
                    if not expected_token:
                        return True
                    return f"Authorization: Bearer {expected_token}".encode() in data

                def _json_response(body: dict, status: int = 200) -> bytes:
                    phrase = (
                        "OK"
                        if status == 200
                        else ("Unauthorized" if status == 401 else "Not Found")
                    )
                    payload = json.dumps(body, ensure_ascii=False).encode()
                    return (
                        f"HTTP/1.0 {status} {phrase}\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(payload)}\r\n"
                        f"\r\n"
                    ).encode() + payload

                def _parse_body() -> dict:
                    idx = data.find(b"\r\n\r\n")
                    if idx < 0:
                        return {}
                    try:
                        return json.loads(data[idx + 4 :])
                    except (json.JSONDecodeError, ValueError):
                        return {}

                def _serialize_cron_job(j) -> dict:
                    return {
                        "id": j.id,
                        "name": j.name,
                        "enabled": j.enabled,
                        "schedule": {
                            "kind": j.schedule.kind,
                            "atMs": j.schedule.at_ms,
                            "everyMs": j.schedule.every_ms,
                            "expr": j.schedule.expr,
                            "tz": j.schedule.tz,
                        },
                        "payload": {
                            "message": j.payload.message,
                            "deliver": j.payload.deliver,
                            "channel": j.payload.channel,
                            "to": j.payload.to,
                        },
                        "state": {
                            "nextRunAtMs": j.state.next_run_at_ms,
                            "lastRunAtMs": j.state.last_run_at_ms,
                            "lastStatus": j.state.last_status,
                            "lastError": j.state.last_error,
                        },
                        "deleteAfterRun": j.delete_after_run,
                    }

                if "POST" in request_line and "/restart" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        writer.write(_json_response({"status": "restarting"}))
                        _state["restart"] = True
                        asyncio.get_event_loop().call_later(
                            0.5, lambda: [t.cancel() for t in asyncio.all_tasks()]
                        )
                elif "POST" in request_line and "/reload" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        writer.write(_json_response({"status": "reloading"}))
                        await writer.drain()
                        asyncio.create_task(_do_reload())
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
                elif "POST" in request_line and "/api/chat" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    elif not provider:
                        writer.write(_json_response({"error": "no_provider"}, 503))
                    else:
                        body = _parse_body()
                        writer.write(
                            b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\nConnection: close\r\n\r\n"
                        )
                        await writer.drain()

                        async def _on_progress(text, *, tool_hint=False):
                            writer.write(
                                (
                                    json.dumps(
                                        {"t": "p", "c": text, "h": tool_hint}, ensure_ascii=False
                                    )
                                    + "\n"
                                ).encode()
                            )
                            await writer.drain()

                        try:
                            out = await agent.process_direct(
                                content=body.get("content", ""),
                                session_key=body.get("session_key", "webui:direct"),
                                channel=body.get("channel", "webui"),
                                chat_id=body.get("chat_id", "direct"),
                                on_progress=_on_progress,
                                media=body.get("media"),
                                metadata=body.get("metadata"),
                                profile_id=body.get("profile_id"),
                            )
                            writer.write(
                                (
                                    json.dumps(
                                        {
                                            "t": "r",
                                            "content": out.content if out else "",
                                            "media": out.media if out else [],
                                        },
                                        ensure_ascii=False,
                                    )
                                    + "\n"
                                ).encode()
                            )
                        except Exception as e:
                            writer.write(
                                (
                                    json.dumps({"t": "e", "error": str(e)}, ensure_ascii=False)
                                    + "\n"
                                ).encode()
                            )
                elif "GET" in request_line and "/api/cron/list" in request_line:
                    writer.write(
                        _json_response(
                            {
                                "jobs": [
                                    _serialize_cron_job(j)
                                    for j in cron.list_jobs(include_disabled=True)
                                ]
                            }
                        )
                    )
                elif "POST" in request_line and "/api/cron/trigger/" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        job_id = (
                            request_line.split("/api/cron/trigger/")[1].split(" ")[0].split("?")[0]
                        )
                        ran = await cron.run_job(job_id, force=True)
                        writer.write(_json_response({"triggered": ran}))
                elif "POST" in request_line and "/api/archive" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        body = _parse_body()
                        snapshot = body.get("snapshot", [])
                        archived = False
                        if snapshot and hasattr(agent, "memory_consolidator"):
                            try:
                                await agent.memory_consolidator.archive_snapshot(snapshot)
                                archived = True
                            except Exception:
                                pass
                        writer.write(_json_response({"archived": archived}))
                elif "GET" in request_line:
                    writer.write(
                        _json_response(
                            {
                                "status": "ok" if provider else "idle",
                                "uptime": int(time.time() - _start_time),
                                "provider_ready": provider is not None,
                            }
                        )
                    )
                else:
                    writer.write(_json_response({"error": "not found"}, 404))
                await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()

        health_srv = await asyncio.start_server(_health_handler, host, port)

        ws_server = await websockets.serve(
            _ws_handler, host, ws_port, ping_interval=None, ping_timeout=None
        )
        logger.info("🔌 Gateway WebSocket server listening on {}:{}", host, ws_port)

        try:
            await cron.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
                health_srv.serve_forever(),
                ws_server.serve_forever(),
                _update_check_loop(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            if _state["restart"]:
                console.print("\n🔄 Restarting...")
            else:
                console.print("\nShutting down...")
        finally:
            try:
                await agent.close_mcp()
            except asyncio.CancelledError:
                pass
            heartbeat.stop()
            cron.stop()
            agent.stop()
            try:
                await channels.stop_all()
            except asyncio.CancelledError:
                pass

    await run()

    if _state["restart"]:
        os.execv(sys.executable, [sys.executable] + sys.argv)
