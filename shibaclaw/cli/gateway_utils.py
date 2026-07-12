"""Utility functions for the gateway service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from loguru import logger

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


def resolve_automation_target(job: Any) -> HeartbeatTarget:
    channel = job.payload.channel or "cli"
    chat_id = job.payload.to or "direct"
    session_key = job.payload.session_key or f"{channel}:{chat_id}"

    if channel == "webui":
        session_key = (
            resolve_webui_session_key(job.payload.session_key, job.payload.to) or session_key
        )
        chat_id = session_key.split(":", 1)[1] if ":" in session_key else session_key

    return HeartbeatTarget(channel=channel, chat_id=chat_id, session_key=session_key)


async def deliver_scheduled_job_result(
    job: Any,
    response: str,
    *,
    bus_publish: Callable[[Any], Awaitable[None]],
    notify_webui: Callable[..., Awaitable[bool]],
    broadcast_ws_event: Callable[[str, dict[str, Any], str | None], Awaitable[None]],
    has_gateway_ws_clients: bool,
    auth_token: str | None,
) -> None:
    """Deliver a scheduled automation result to its configured target."""
    from shibaclaw.bus.events import OutboundMessage

    target = resolve_automation_target(job)
    payload = {
        "content": response,
        "source": "automation",
        "msg_type": "response",
    }

    if job.payload.deliver:
        if target.channel == "webui":
            payload["persist"] = True
            if has_gateway_ws_clients:
                await broadcast_ws_event("session.notify", payload, session_key=target.session_key)
            else:
                await notify_webui(
                    target.session_key,
                    response,
                    auth_token,
                    source="automation",
                    persist=True,
                    msg_type="response",
                )
            return

        await bus_publish(
            OutboundMessage(channel=target.channel, chat_id=target.chat_id, content=response)
        )

        if has_gateway_ws_clients:
            await broadcast_ws_event(
                "session.notify",
                {
                    "content": response,
                    "source": "automation",
                    "persist": False,
                    "msg_type": "notification",
                },
                session_key="",
            )
        else:
            await notify_webui(
                "",
                response,
                auth_token,
                source="automation",
                persist=False,
                msg_type="notification",
            )
        return

    payload["persist"] = False
    if has_gateway_ws_clients:
        await broadcast_ws_event("session.notify", payload, session_key=target.session_key)
    else:
        await notify_webui(
            target.session_key,
            response,
            auth_token,
            source="automation",
            persist=False,
            msg_type="response",
        )


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
                    "Automation: target {}:{} has no matching recent session; skipping",
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
    source: str = "automation",
    persist: bool = True,
    metadata: dict[str, Any] | None = None,
    msg_type: str = "response",
    media: list[str] | None = None,
) -> bool:
    if not response:
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
        "msg_type": msg_type,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    if media is not None:
        payload["media"] = media

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


