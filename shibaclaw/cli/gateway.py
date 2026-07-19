"""Gateway service runner and health server for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from typing import Any, Optional

import websockets
from loguru import logger
from rich.panel import Panel

from shibaclaw import __logo__, __version__
from shibaclaw.helpers.logging import setup_shiba_logging

from .utils import get_console


from .gateway_utils import (
    HeartbeatTarget as HeartbeatTarget,
    resolve_webui_session_key as resolve_webui_session_key,
    resolve_automation_target as resolve_automation_target,
    deliver_scheduled_job_result as deliver_scheduled_job_result,
    select_heartbeat_target as select_heartbeat_target,
    resolve_heartbeat_targets as resolve_heartbeat_targets,
    notify_webui_session as notify_webui_session,
)

async def _cancel_all_tasks_gracefully() -> None:
    """Cancel every running asyncio task except the current one and wait for them to finish.

    This replaces the old ``call_later(0.5, lambda: [t.cancel() for t in all_tasks()])``
    pattern which left tasks in a "destroyed but pending" state because:
    - call_later schedules a sync callback — it cannot await the cancellation
    - tasks whose coroutines were blocked in wait_for / shield never got a chance to
      handle CancelledError before the event loop tore them down
    """
    current = asyncio.current_task()
    tasks = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


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
    from shibaclaw.automation.service import AutomationService
    from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule
    from shibaclaw.brain.manager import PackManager
    from shibaclaw.bus.queue import MessageBus
    from shibaclaw.config.paths import get_automation_dir
    from shibaclaw.helpers.helpers import sync_profiles, sync_skills, sync_workspace_templates
    from shibaclaw.integrations.manager import ChannelManager

    from .commands import _load_runtime_config, _make_provider

    setup_shiba_logging(level="DEBUG" if verbose else "INFO")

    config = _load_runtime_config(config_path, workspace)
    port = port_override if port_override is not None else config.gateway.port
    ws_port = ws_port_override if ws_port_override is not None else config.gateway.ws_port
    host = host if host is not None else (config.gateway.host or "127.0.0.1")

    sync_skills(config.workspace_path)
    sync_profiles(config.workspace_path)
    sync_workspace_templates(config.workspace_path, silent=True)

    def _current_auth_token() -> str | None:
        return None

    bus = MessageBus(rate_limit_per_minute=config.gateway.rate_limit_per_minute)
    provider = _make_provider(config, exit_on_error=False)
    if provider is None:
        get_console().print("[yellow]🐾 Entering idle mode...[/yellow]")
        get_console().print(
            "[dim]Open the WebUI to complete the setup or run:[/dim] [bold]shibaclaw onboard[/bold]"
        )

    session_manager = PackManager(config.workspace_path)

    from shibaclaw.brain.routing import SessionRouter

    session_router = SessionRouter()

    # ------------------------------------------------------------------
    # AutomationService callbacks
    # ------------------------------------------------------------------

    async def on_automation_notify(
        response: str,
        *,
        targets: dict[str, str] | None = None,
        source: str = "automation",
        persist: bool = True,
        metadata: dict[str, Any] | None = None,
        msg_type: str = "response",
    ) -> None:
        from shibaclaw.bus.events import OutboundMessage

        if not response:
            response = "Automation task completed."

        resolved_targets = resolve_heartbeat_targets(
            targets,
            session_manager.list_sessions(),
            set(channels.enabled_channels),
        )

        for target in resolved_targets:
            if target.channel == "webui":
                if _ws_clients:
                    await _broadcast_ws_event(
                        "session.notify",
                        {
                            "content": response,
                            "source": source,
                            "persist": persist,
                            "metadata": metadata,
                            "msg_type": msg_type,
                        },
                        session_key=target.session_key,
                    )
                else:
                    await notify_webui_session(
                        target.session_key,
                        response,
                        None,
                        source=source,
                        persist=persist,
                        metadata=metadata,
                        msg_type=msg_type,
                    )
                continue
            if target.channel == "cli":
                continue
            await bus.publish_outbound(
                OutboundMessage(channel=target.channel, chat_id=target.chat_id, content=response)
            )

        if not any(target.channel != "cli" for target in resolved_targets):
            logger.info("Automation: generated a response but found no deliverable session")

        webui_notified = any(t.channel == "webui" for t in resolved_targets)
        if not webui_notified:
            sys_payload = {
                "content": response,
                "source": source,
                "persist": False,
                "msg_type": "notification",
            }
            if _ws_clients:
                await _broadcast_ws_event("session.notify", sys_payload, session_key="")
            else:
                await notify_webui_session(
                    "", response, None, source=source, persist=False, msg_type="notification"
                )

    async def on_heartbeat_execute(
        tasks: str,
        *,
        session_key: str = "automation:heartbeat",
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
        exec_target = (
            resolved_targets[0]
            if resolved_targets
            else select_heartbeat_target(
                session_manager.list_sessions(), set(channels.enabled_channels)
            )
        )

        if not exec_target:
            logger.warning("No heartbeat target available. Aborting heartbeat execution.")
            return ""

        outbound = await agent.process_direct(
            tasks,
            session_key,
            exec_target.channel,
            exec_target.chat_id,
            on_progress=_noop_progress,
            profile_id=profile_id,
        )
        return outbound.content if outbound else ""

    async def on_scheduled_job(job: AutomationJob) -> str | None:
        """Execute a scheduled job: run an agent turn then optionally deliver."""
        session_key = job.payload.session_key or job.name or f"automation:{job.id}"

        async def _noop_progress(*_args, **_kwargs) -> None:
            return None

        out = await agent.process_direct(
            job.payload.message,
            session_key,
            channel="automation",
            chat_id=job.id,
            on_progress=_noop_progress,
            metadata={"hidden": True},
        )
        response = out.content if out else ""
        if not response:
            response = "Automation job executed successfully."

        await deliver_scheduled_job_result(
            job,
            response,
            bus_publish=bus.publish_outbound,
            notify_webui=notify_webui_session,
            broadcast_ws_event=_broadcast_ws_event,
            has_gateway_ws_clients=bool(_ws_clients),
            auth_token=None,
        )

        return response

    # Build AutomationService — replaces both CronService and HeartbeatService
    hb_cfg = config.gateway.heartbeat
    automation_store = get_automation_dir() / "automation.json"
    store_existed = automation_store.exists()

    automation = AutomationService(
        store_path=automation_store,
        workspace=config.workspace_path,
        on_scheduled=on_scheduled_job,
        on_heartbeat=on_heartbeat_execute,
        on_notify=on_automation_notify,
        provider=provider,
        model=hb_cfg.model or None,
    )

    # If heartbeat was enabled in config, register it as a heartbeat job
    # Only do this on first run (if store didn't exist) to allow users to delete it.
    _existing_hb = [j for j in automation.list_jobs() if j.payload.kind == "heartbeat"]
    if hb_cfg.enabled and not store_existed and not _existing_hb:
        from shibaclaw.automation.types import AutomationPayload, AutomationSchedule

        automation.add_job(
            name="Heartbeat",
            schedule=AutomationSchedule(
                kind="every",
                every_ms=hb_cfg.interval_min * 60 * 1000,
            ),
            payload=AutomationPayload(
                kind="heartbeat",
                session_key=hb_cfg.session_key,
                targets=hb_cfg.targets or {},
                profile_id=hb_cfg.profile_id,
            ),
        )
        logger.info(
            "AutomationService: registered heartbeat job from config (every {}m)",
            hb_cfg.interval_min,
        )

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
        automation_service=automation,
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

    # ------------------------------------------------------------------
    # Status banner
    # ------------------------------------------------------------------
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
    a_status = automation.status()
    status_parts.append(
        f"  [green]✓[/green] Automation: {a_status['scheduled']} scheduled, "
        f"{a_status['heartbeats']} heartbeat(s)"
        if a_status["jobs"] > 0
        else "  [dim]Automation: idle[/dim]"
    )
    webui_url = os.environ.get("SHIBACLAW_WEBUI_URL", "http://localhost:3000")
    status_parts.append(f"  [cyan]🖥️  WebUI:[/cyan] [link={webui_url}]{webui_url}[/link]")
    status_parts.append(
        "  [dim]Run [bold]shibaclaw print-token[/bold] to show the WebUI auth token[/dim]"
    )
    get_console().print(Panel("\n".join(status_parts), expand=False, border_style="blue"))

    _state = {"restart": False, "starting": True}

    async def _trigger_restart() -> None:
        """Schedule a graceful restart: cancel all tasks and let run() exit cleanly.

        Previously this used ``call_later(0.5, lambda: [t.cancel() ...])``, which
        is a sync callback and cannot await the cancellations.  Tasks blocked in
        ``wait_for`` / ``Future`` were left in a pending state and destroyed by the
        event loop, producing "Task was destroyed but it is pending!" warnings and
        leaving MCP stdio sub-processes running (causing the observed slowness on
        subsequent restarts).
        """
        await asyncio.sleep(0.1)  # yield so the HTTP/WS response is sent first
        await _cancel_all_tasks_gracefully()

    async def _do_reload() -> None:
        """Hot-reload all components from the saved config file."""
        nonlocal config, provider
        try:
            new_cfg = _load_runtime_config(config_path, workspace)
        except Exception as e:
            logger.error("Hot-reload: failed to load config: {}", e)
            return

        net_changed = (
            new_cfg.gateway.host != config.gateway.host
            or new_cfg.gateway.port != config.gateway.port
            or new_cfg.gateway.ws_port != config.gateway.ws_port
        )
        if net_changed:
            logger.warning("Hot-reload: gateway host/port changed — falling back to full restart")
            _state["restart"] = True
            asyncio.ensure_future(_trigger_restart())
            return

        try:
            new_provider = _make_provider(new_cfg, exit_on_error=False)
            config = new_cfg
            provider = new_provider

            await agent.reconfigure(new_cfg, new_provider)
            await channels.reconfigure(new_cfg)
            new_hb = new_cfg.gateway.heartbeat
            await automation.reconfigure(new_provider, new_hb.model or None)

            try:
                from shibaclaw.integrations.klavis_client import reload_klavis_client

                reload_klavis_client(base_url="https://api.klavis.ai")
            except Exception as e:
                logger.warning("Hot-reload: failed to reload Klavis client: {}", e)

            logger.info("Hot-reload complete")
        except Exception as e:
            logger.error("Hot-reload failed: {}", e)

    update_check_interval = float(os.environ.get("SHIBACLAW_UPDATE_CHECK_HOURS", "6")) * 3600

    async def _update_check_loop():
        await asyncio.sleep(60)
        while True:
            try:
                from shibaclaw.updater.checker import check_for_update

                result = await asyncio.get_event_loop().run_in_executor(None, check_for_update)
                if result.get("update_available"):
                    notification = result.get("notification") or {}
                    current = result.get("display_current") or result.get("current", "?")
                    latest = result.get("display_latest") or result.get("latest", "?")
                    msg = (
                        notification.get("text")
                        or result.get("summary")
                        or (f"🆕 *ShibaClaw update available!*\n{current} → {latest}")
                    )
                    if result.get("action_kind") == "automatic":
                        msg += "\n\n💡 _You can type_ `/update` _to install it now._"
                    logger.info("🆕 Update available: {} → {}", current, latest)
                    await on_automation_notify(
                        msg,
                        source="update",
                        metadata=notification,
                        msg_type="response",
                    )
                else:
                    logger.debug(
                        "Update check: already on latest version ({}).", result.get("current", "?")
                    )
            except Exception as e:
                logger.debug("Update check failed: {}", e)
            await asyncio.sleep(update_check_interval)

    # ── WebSocket server ─────────────────────────────────────────────────
    _ws_clients: set[websockets.ServerConnection] = set()
    _chat_tasks: dict[str, asyncio.Task] = {}
    _ws_start_time = time.time()

    async def _ws_handler(websocket: websockets.ServerConnection):
        authed = False
        try:
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
        nonlocal _state

        def _ok(data: dict | None = None):
            return json.dumps(
                {"type": "response", "id": request_id, "ok": True, "payload": data or {}}
            )

        def _err(error: str):
            return json.dumps({"type": "response", "id": request_id, "ok": False, "error": error})

        def _ser_job(j) -> dict:
            return {
                "id": j.id,
                "name": j.name,
                "enabled": j.enabled,
                "kind": j.payload.kind,
                "schedule": {
                    "kind": j.schedule.kind,
                    "atMs": j.schedule.at_ms,
                    "everyMs": j.schedule.every_ms,
                    "expr": j.schedule.expr,
                    "tz": j.schedule.tz,
                },
                "payload": {
                    "kind": j.payload.kind,
                    "message": j.payload.message,
                    "heartbeatFile": j.payload.heartbeat_file,
                    "deliver": j.payload.deliver,
                    "channel": j.payload.channel,
                    "to": j.payload.to,
                    "targets": j.payload.targets,
                },
                "state": {
                    "nextRunAtMs": j.state.next_run_at_ms,
                    "lastRunAtMs": j.state.last_run_at_ms,
                    "lastStatus": j.state.last_status,
                    "lastError": j.state.last_error,
                    "runCount": j.state.run_count,
                },
                "deleteAfterRun": j.delete_after_run,
            }

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
                    except asyncio.CancelledError:
                        try:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "response",
                                        "id": request_id,
                                        "ok": True,
                                        "payload": {
                                            "content": "",
                                            "media": [],
                                            "finish_reason": "cancelled",
                                        },
                                    }
                                )
                            )
                        except websockets.ConnectionClosed:
                            pass
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

                task = asyncio.create_task(_run_chat(ws, request_id, payload))
                _chat_tasks[request_id] = task
                task.add_done_callback(lambda t: _chat_tasks.pop(request_id, None))

            elif action == "cancel":
                target_id = payload.get("request_id", "")
                cancel_task = _chat_tasks.get(target_id)
                if cancel_task and not cancel_task.done():
                    cancel_task.cancel()
                    await ws.send(_ok({"cancelled": True, "request_id": target_id}))
                else:
                    await ws.send(_ok({"cancelled": False, "request_id": target_id}))

            elif action == "steer":
                session_key = payload.get("session_key")
                content = payload.get("content")
                media = payload.get("media")
                attachments = payload.get("attachments")
                injected = agent.inject_steering_message(
                    session_key=session_key,
                    content=content,
                    media=media,
                    attachments=attachments,
                )
                await ws.send(_ok({"injected": injected}))

            elif action == "restart":
                await ws.send(_ok({"status": "restarting"}))
                _state["restart"] = True
                asyncio.ensure_future(_trigger_restart())

            elif action == "reload":
                await ws.send(_ok({"status": "reloading"}))
                asyncio.create_task(_do_reload())

            # --- Automation (new unified actions) ---
            elif action == "automation.list":
                await ws.send(
                    _ok(
                        {"jobs": [_ser_job(j) for j in automation.list_jobs(include_disabled=True)]}
                    )
                )

            elif action == "automation.trigger":
                job_id = payload.get("job_id", "")
                ran = await automation.run_job(job_id, force=True)
                await ws.send(_ok({"triggered": ran}))

            elif action == "automation.status":
                await ws.send(_ok(automation.status()))

            elif action == "automation.enable":
                job_id = payload.get("job_id", "")
                enabled = payload.get("enabled", True)
                job = automation.enable_job(job_id, enabled)
                await ws.send(_ok({"ok": job is not None}))

            elif action == "automation.remove":
                job_id = payload.get("job_id", "")
                removed = automation.remove_job(job_id)
                await ws.send(_ok({"removed": removed}))

            elif action == "automation.create":
                from shibaclaw.automation.types import AutomationPayload, AutomationSchedule

                s = payload.get("schedule", {})
                p = payload.get("payload", {})
                name = payload.get("name", "")
                delete_after_run = payload.get(
                    "deleteAfterRun", payload.get("delete_after_run", False)
                )
                schedule = AutomationSchedule(
                    kind=s.get("kind", "every"),
                    at_ms=s.get("atMs", s.get("at_ms")),
                    every_ms=s.get("everyMs", s.get("every_ms")),
                    expr=s.get("expr"),
                    tz=s.get("tz"),
                )
                payload_obj = AutomationPayload(
                    kind=p.get("kind", "scheduled"),
                    message=p.get("message", ""),
                    heartbeat_file=p.get("heartbeatFile", p.get("heartbeat_file")),
                    deliver=p.get("deliver", False),
                    channel=p.get("channel"),
                    to=p.get("to"),
                    session_key=p.get("sessionKey", p.get("session_key")),
                    profile_id=p.get("profileId", p.get("profile_id")),
                    targets=p.get("targets") or {},
                )
                job = automation.add_job(name, schedule, payload_obj, delete_after_run)
                await ws.send(_ok(_ser_job(job)))

            elif action == "automation.get":
                job_id = payload.get("job_id", "")
                job = automation.get_job(job_id)
                if job:
                    await ws.send(_ok(_ser_job(job)))
                else:
                    await ws.send(_err("job not found"))

            elif action == "automation.update":
                job_id = payload.get("job_id", "")
                patch = payload.get("patch", {})
                job = automation.update_job(job_id, patch)
                if job:
                    await ws.send(_ok(_ser_job(job)))
                else:
                    await ws.send(_err("job not found"))

            # --- Backward-compat aliases (deprecated, keep for WebUI compat) ---
            elif action == "cron.list":
                scheduled = [
                    j
                    for j in automation.list_jobs(include_disabled=True)
                    if j.payload.kind == "scheduled"
                ]
                await ws.send(_ok({"jobs": [_ser_job(j) for j in scheduled]}))

            elif action == "cron.trigger":
                job_id = payload.get("job_id", "")
                ran = await automation.run_job(job_id, force=True)
                await ws.send(_ok({"triggered": ran}))

            elif action == "heartbeat.status":
                hb_jobs = [j for j in automation.list_jobs() if j.payload.kind == "heartbeat"]
                hb = hb_jobs[0] if hb_jobs else None
                await ws.send(
                    _ok(
                        {
                            "enabled": hb is not None and hb.enabled,
                            "running": automation.status()["running"],
                            "last_run_ms": hb.state.last_run_at_ms if hb else None,
                            "last_status": hb.state.last_status if hb else None,
                        }
                    )
                )

            elif action == "heartbeat.trigger":
                hb_jobs = [j for j in automation.list_jobs() if j.payload.kind == "heartbeat"]
                if not hb_jobs:
                    await ws.send(_err("no heartbeat job configured"))
                else:
                    ran = await automation.run_job(hb_jobs[0].id, force=True)
                    await ws.send(_ok({"triggered": ran}))

            elif action == "archive":
                snapshot = payload.get("snapshot", [])
                archived = False
                if snapshot and hasattr(agent, "memory_consolidator"):
                    try:
                        await agent.memory_consolidator.archive_snapshot(snapshot)
                        archived = True
                    except Exception as _e:
                        logger.debug("Ignored error: {}", _e)
                await ws.send(_ok({"archived": archived}))

            else:
                await ws.send(_err(f"unknown action: {action}"))

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            try:
                await ws.send(_err(str(e)))
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)

    async def _broadcast_ws_event(name: str, payload: dict, session_key: str | None = None):
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

    async def _webui_outbound_notify(
        session_key: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        system_event = metadata.get("system_event") if metadata else None
        msg_type = system_event if system_event else "response"

        payload = {
            "content": content,
            "source": "agent",
            "persist": False,
            "msg_type": msg_type,
        }
        if media:
            payload["media"] = media
        if metadata:
            payload["metadata"] = metadata
        if _ws_clients:
            await _broadcast_ws_event("session.notify", payload, session_key=session_key)
        else:
            await notify_webui_session(
                session_key,
                content,
                None,
                source="agent",
                persist=False,
                media=media,
                metadata=metadata,
                msg_type=msg_type,
            )

    channels._notify_webui = _webui_outbound_notify

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

                def _serialize_job(j) -> dict:
                    return {
                        "id": j.id,
                        "name": j.name,
                        "enabled": j.enabled,
                        "kind": j.payload.kind,
                        "schedule": {
                            "kind": j.schedule.kind,
                            "atMs": j.schedule.at_ms,
                            "everyMs": j.schedule.every_ms,
                            "expr": j.schedule.expr,
                            "tz": j.schedule.tz,
                        },
                        "payload": {
                            "kind": j.payload.kind,
                            "message": j.payload.message,
                            "heartbeatFile": j.payload.heartbeat_file,
                            "deliver": j.payload.deliver,
                            "channel": j.payload.channel,
                            "to": j.payload.to,
                            "targets": j.payload.targets,
                        },
                        "state": {
                            "nextRunAtMs": j.state.next_run_at_ms,
                            "lastRunAtMs": j.state.last_run_at_ms,
                            "lastStatus": j.state.last_status,
                            "lastError": j.state.last_error,
                            "runCount": j.state.run_count,
                        },
                        "deleteAfterRun": j.delete_after_run,
                    }

                if "POST" in request_line and "/restart" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        writer.write(_json_response({"status": "restarting"}))
                        await writer.drain()
                        _state["restart"] = True
                        asyncio.ensure_future(_trigger_restart())

                elif "POST" in request_line and "/reload" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        writer.write(_json_response({"status": "reloading"}))
                        await writer.drain()
                        asyncio.create_task(_do_reload())

                # --- Automation HTTP endpoints (new) ---
                elif "GET" in request_line and (
                    "/api/automation/jobs" in request_line or "/api/automation/list" in request_line
                ):
                    parts = request_line.split(" ")
                    path = parts[1] if len(parts) > 1 else ""
                    path = path.split("?")[0]
                    if path in ("/api/automation/jobs", "/api/automation/list"):
                        writer.write(
                            _json_response(
                                {
                                    "jobs": [
                                        _serialize_job(j)
                                        for j in automation.list_jobs(include_disabled=True)
                                    ]
                                }
                            )
                        )
                    elif path.startswith("/api/automation/jobs/"):
                        job_id = path.split("/api/automation/jobs/")[1]
                        job = automation.get_job(job_id)
                        if job:
                            writer.write(_json_response(_serialize_job(job)))
                        else:
                            writer.write(_json_response({"error": "not found"}, 404))

                elif "GET" in request_line and "/api/automation/status" in request_line:
                    writer.write(_json_response(automation.status()))

                elif "POST" in request_line and "/api/automation/jobs" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        parts = request_line.split(" ")
                        path = parts[1] if len(parts) > 1 else ""
                        path = path.split("?")[0]
                        if path == "/api/automation/jobs":
                            body = _parse_body()
                            from shibaclaw.automation.types import (
                                AutomationPayload,
                                AutomationSchedule,
                            )

                            s = body.get("schedule", {})
                            p = body.get("payload", {})
                            name = body.get("name", "")
                            delete_after_run = body.get(
                                "deleteAfterRun", body.get("delete_after_run", False)
                            )
                            schedule = AutomationSchedule(
                                kind=s.get("kind", "every"),
                                at_ms=s.get("atMs", s.get("at_ms")),
                                every_ms=s.get("everyMs", s.get("every_ms")),
                                expr=s.get("expr"),
                                tz=s.get("tz"),
                            )
                            payload_obj = AutomationPayload(
                                kind=p.get("kind", "scheduled"),
                                message=p.get("message", ""),
                                heartbeat_file=p.get("heartbeatFile", p.get("heartbeat_file")),
                                deliver=p.get("deliver", False),
                                channel=p.get("channel"),
                                to=p.get("to"),
                                session_key=p.get("sessionKey", p.get("session_key")),
                                profile_id=p.get("profileId", p.get("profile_id")),
                                targets=p.get("targets") or {},
                            )
                            job = automation.add_job(name, schedule, payload_obj, delete_after_run)

                            writer.write(_json_response(_serialize_job(job), 201))
                        elif path.endswith("/update"):
                            job_id = path.split("/api/automation/jobs/")[1].split("/update")[0]
                            body = _parse_body()
                            job = automation.update_job(job_id, body)

                            if job:
                                writer.write(_json_response(_serialize_job(job)))
                            else:
                                writer.write(_json_response({"error": "not found"}, 404))
                        elif path.endswith("/trigger"):
                            job_id = path.split("/api/automation/jobs/")[1].split("/trigger")[0]
                            ran = await automation.run_job(job_id, force=True)
                            writer.write(_json_response({"triggered": ran}))

                elif "DELETE" in request_line and "/api/automation/jobs/" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        parts = request_line.split(" ")
                        path = parts[1] if len(parts) > 1 else ""
                        path = path.split("?")[0]
                        job_id = path.split("/api/automation/jobs/")[1]
                        removed = automation.remove_job(job_id)
                        writer.write(_json_response({"removed": removed}))

                elif "POST" in request_line and "/api/automation/trigger/" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        job_id = (
                            request_line.split("/api/automation/trigger/")[1]
                            .split(" ")[0]
                            .split("?")[0]
                        )
                        ran = await automation.run_job(job_id, force=True)
                        writer.write(_json_response({"triggered": ran}))

                # --- Backward-compat HTTP aliases ---
                elif "GET" in request_line and "/heartbeat/status" in request_line:
                    hb_jobs = [j for j in automation.list_jobs() if j.payload.kind == "heartbeat"]
                    hb = hb_jobs[0] if hb_jobs else None
                    writer.write(
                        _json_response(
                            {
                                "enabled": hb is not None and hb.enabled,
                                "running": automation.status()["running"],
                                "last_run_ms": hb.state.last_run_at_ms if hb else None,
                                "last_status": hb.state.last_status if hb else None,
                            }
                        )
                    )

                elif "POST" in request_line and (
                    "/heartbeat/trigger" in request_line
                    or "/api/automation/trigger-heartbeats" in request_line
                ):
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        hb_jobs = [
                            j for j in automation.list_jobs() if j.payload.kind == "heartbeat"
                        ]
                        if hb_jobs:
                            ran = await automation.run_job(hb_jobs[0].id, force=True)
                            writer.write(_json_response({"triggered": ran}))
                        else:
                            writer.write(
                                _json_response({"triggered": False, "error": "no heartbeat job"})
                            )

                elif "GET" in request_line and "/api/cron/list" in request_line:
                    scheduled = [
                        j
                        for j in automation.list_jobs(include_disabled=True)
                        if j.payload.kind == "scheduled"
                    ]
                    writer.write(_json_response({"jobs": [_serialize_job(j) for j in scheduled]}))

                elif "POST" in request_line and "/api/cron/trigger/" in request_line:
                    if not _check_auth():
                        writer.write(_json_response({"error": "unauthorized"}, 401))
                    else:
                        job_id = (
                            request_line.split("/api/cron/trigger/")[1].split(" ")[0].split("?")[0]
                        )
                        ran = await automation.run_job(job_id, force=True)
                        writer.write(_json_response({"triggered": ran}))

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
                                        {"t": "p", "c": text, "h": tool_hint},
                                        ensure_ascii=False,
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
                            except Exception as _e:
                                logger.debug("Ignored error: {}", _e)
                        writer.write(_json_response({"archived": archived}))

                elif "GET" in request_line:
                    writer.write(
                        _json_response(
                            {
                                "status": "starting"
                                if _state.get("starting", False)
                                else ("ok" if provider else "idle"),
                                "uptime": int(time.time() - _start_time),
                                "provider_ready": provider is not None,
                            }
                        )
                    )
                else:
                    writer.write(_json_response({"error": "not found"}, 404))
                await writer.drain()
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
            finally:
                writer.close()

        health_srv = await asyncio.start_server(_health_handler, host, port)
        ws_server = await websockets.serve(
            _ws_handler, host, ws_port, ping_interval=None, ping_timeout=None
        )
        logger.info("🔌 Gateway WebSocket server listening on {}:{}", host, ws_port)

        try:
            await automation.start()

            async def _clear_starting():
                await asyncio.sleep(4.0)
                _state["starting"] = False

            asyncio.create_task(_clear_starting())

            await asyncio.gather(
                agent.run(),
                channels.start_all(),
                health_srv.serve_forever(),
                ws_server.serve_forever(),
                _update_check_loop(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            if _state["restart"]:
                get_console().print("\n🔄 Restarting...")
            else:
                get_console().print("\nShutting down...")
        finally:
            try:
                await asyncio.wait_for(channels.stop_all(), timeout=5.0)
            except Exception as e:
                logger.error("Error/timeout stopping channels during shutdown: {}", e)
            except asyncio.CancelledError:
                pass
            try:
                await asyncio.wait_for(agent.close_mcp(), timeout=5.0)
            except Exception as e:
                logger.error("Error/timeout closing MCP during shutdown: {}", e)
            except asyncio.CancelledError:
                pass
            automation.stop()
            agent.stop()

    await run()

    if _state["restart"]:
        if os.environ.get("SHIBACLAW_SILENT"):
            sys.exit(0)
        else:
            try:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                logger.error("Restart failed: os.execv raised {}. Falling back to subprocess.Popen...", e)
                import subprocess
                subprocess.Popen([sys.executable] + sys.argv)
                sys.exit(1)
