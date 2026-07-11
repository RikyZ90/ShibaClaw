"""Native WebSocket handler for browser ↔ WebUI communication.

Replaces the Socket.IO layer (socket_io.py) with a lightweight JSON
protocol over standard WebSocket.  The event names are kept identical
so the browser adapter is a thin wrapper around native WebSocket.
"""

from __future__ import annotations

import asyncio
import base64
from collections import defaultdict, deque
import io
import json
import mimetypes
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict

from loguru import logger
from starlette.websockets import WebSocket, WebSocketDisconnect

from .agent_manager import agent_manager
from .auth import _auth_enabled, verify_token_value
from .gateway_client import gateway_client

# ── Shared state ─────────────────────────────────────────────
sessions: dict[str, dict[str, Any]] = {}  # ws_id → session state
processing_state: dict[str, dict[str, Any]] = {}  # session_key → processing info
_ws_clients: dict[str, WebSocket] = {}  # ws_id → WebSocket instance
_session_subscribers: dict[str, set[str]] = defaultdict(set)
_session_queues: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
_session_tasks: dict[str, asyncio.Task[None]] = {}

_MAX_SESSION_EVENTS = 200


def _make_session_state(session_key: str) -> dict[str, Any]:
    return {
        "session_key": session_key,
        "processing": False,
        "queue": _session_queues.setdefault(session_key, deque()),
    }


def _unsubscribe_ws(ws_id: str) -> None:
    state = sessions.get(ws_id)
    if not state:
        return
    session_key = state.get("session_key")
    if not session_key:
        return
    subscribers = _session_subscribers.get(session_key)
    if not subscribers:
        return
    subscribers.discard(ws_id)
    if not subscribers:
        _session_subscribers.pop(session_key, None)


def _subscribe_ws_to_session(ws_id: str, session_key: str) -> None:
    _unsubscribe_ws(ws_id)
    _session_subscribers[session_key].add(ws_id)


def _build_attachments(media_paths: list[str]) -> list[Dict[str, str]]:
    atts = []
    for m_path in media_paths:
        p = Path(m_path)
        if not p.is_absolute():
            cfg = agent_manager.config
            if cfg:
                p = (cfg.workspace_path / p).resolve()
        res = mimetypes.guess_type(str(p))
        mime_type = res[0]
        if not mime_type:
            ext = p.suffix.lower()
            if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                mime_type = f"image/{ext[1:]}"
                if ext == ".jpg":
                    mime_type = "image/jpeg"
                elif ext == ".svg":
                    mime_type = "image/svg+xml"
            else:
                mime_type = "application/octet-stream"
        
        atts.append(
            {
                "name": p.name,
                "url": f"/api/file-get?path={urllib.parse.quote(str(p))}",
                "type": mime_type,
            }
        )
    return atts


async def _emit_to_session(session_key: str, msg: dict[str, Any], *, exclude: str | None = None) -> None:
    """Send a message to all WebSocket clients subscribed to a session."""
    raw = json.dumps(msg)
    for ws_id in list(_session_subscribers.get(session_key, ())):
        if ws_id == exclude:
            continue
        ws = _ws_clients.get(ws_id)
        if ws:
            try:
                await ws.send_text(raw)
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)


async def _emit_to_ws(ws: WebSocket, msg: dict[str, Any]) -> None:
    """Send a message to a specific WebSocket client."""
    try:
        await ws.send_text(json.dumps(msg))
    except Exception as _e:
        logger.debug("Ignored error: {}", _e)


async def _synthesize_tts_response(config, response_content: str, final_atts: list) -> None:
    if config and config.audio.tts_enabled and config.audio.tts_provider == "supertonic":
        try:
            from shibaclaw.tts.registry import discover_tts_plugins
            tts_engines = discover_tts_plugins()
            if "supertonic" in tts_engines:
                tts_cls = tts_engines["supertonic"]
                tts_cfg = {
                    "tts_voice": config.audio.tts_voice,
                    "tts_speed": config.audio.tts_speed,
                    "tts_lang": config.audio.tts_lang,
                }
                tts_engine = tts_cls(tts_cfg)
                uploads_dir = config.workspace_path / "uploads"
                uploads_dir.mkdir(parents=True, exist_ok=True)
                file_name = f"voice_agent_{uuid.uuid4().hex[:8]}.wav"
                output_path = uploads_dir / file_name
                await tts_engine.synthesize(response_content, output_path)
                audio_url = f"/api/file-get?path={urllib.parse.quote(str(output_path.absolute()))}"
                final_atts.append({
                    "name": "voice_response.wav",
                    "url": audio_url,
                    "type": "audio/wav"
                })
        except Exception as e:
            logger.error("Backend TTS synthesis failed: {}", e)

async def ws_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint handler for browser clients."""
    await websocket.accept()
    ws_id = str(uuid.uuid4())[:12]

    # ── Auth ──
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        msg = json.loads(raw)
    except Exception:
        try:
            await websocket.close(4001, "Expected auth message")
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)
        return

    if msg.get("type") != "auth":
        try:
            await websocket.close(4001, "Expected auth message")
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)
        return

    if _auth_enabled():
        token = msg.get("token")
        if not verify_token_value(token):
            await _emit_to_ws(websocket, {"type": "error", "message": "Unauthorized"})
            try:
                await websocket.close(4003, "Unauthorized")
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
            logger.warning("🔒 WebSocket rejected (invalid token) from {}", ws_id)
            return

    # ── Session setup ──
    provided_id = msg.get("session_id")
    session_id = provided_id if provided_id else f"webui:{ws_id[:8]}"
    sessions[ws_id] = _make_session_state(session_id)
    _ws_clients[ws_id] = websocket
    _subscribe_ws_to_session(ws_id, session_id)
    logger.info("🌐 WebUI client connected: {} (Session: {})", ws_id, session_id)

    profile_id = "default"
    try:
        if agent_manager.config and agent_manager.pm:
            pm = agent_manager.pm
            sess = pm.get_or_create(session_id)
            profile_id = sess.metadata.get("profile_id", "default")
    except Exception as _e:
        logger.debug("Ignored error: {}", _e)

    await _emit_to_ws(
        websocket,
        {
            "type": "connected",
            "session_id": session_id,
            "profile_id": profile_id,
            "message": "🐕 ShibaClaw WebUI connected!",
        },
    )

    await _emit_session_status(websocket, session_id)

    # ── Message loop ──
    try:
        async for raw_msg in websocket.iter_text():
            try:
                data = json.loads(raw_msg)
            except (json.JSONDecodeError, ValueError):
                continue

            msg_type = data.get("type", "")

            if msg_type == "ping":
                await _emit_to_ws(websocket, {"type": "pong"})

            elif msg_type == "message":
                await _handle_user_message(ws_id, websocket, data)

            elif msg_type == "stop":
                await _handle_stop(ws_id)

            elif msg_type == "cancel":
                await _handle_cancel(ws_id, websocket, data)

            elif msg_type == "new_session":
                await _handle_new_session(ws_id, websocket, data)

            elif msg_type == "switch_session":
                await _handle_switch_session(ws_id, websocket, data)

            elif msg_type == "transcribe":
                await _handle_transcribe(ws_id, websocket, data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WS handler error: {}", e)
    finally:
        _unsubscribe_ws(ws_id)
        sessions.pop(ws_id, None)
        _ws_clients.pop(ws_id, None)
        logger.info("🌐 WebUI client disconnected: {}", ws_id)


async def _emit_session_status(ws: WebSocket, session_key: str) -> None:
    """Send processing status for a session."""
    ps = processing_state.get(session_key)
    if ps and ps.get("processing"):
        await _emit_to_ws(
            ws,
            {
                "type": "session_status",
                "session_key": session_key,
                "processing": True,
                "msg_id": ps.get("msg_id", ""),
                "events": list(ps.get("events", ())),
                "started_at": ps.get("started_at", 0),
            },
        )
    else:
        await _emit_to_ws(
            ws,
            {
                "type": "session_status",
                "session_key": session_key,
                "processing": False,
            },
        )


async def _handle_user_message(ws_id: str, ws: WebSocket, data: dict[str, Any]) -> None:
    """Handle an incoming user message."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        await _emit_to_ws(ws, {"type": "error", "message": "No configuration found."})
        return

    content = data.get("content", "").strip()

    import re
    mentioned_kbs = []
    mentioned_mcps = []
    mentioned_apps = []
    for match in re.finditer(r'@kb:(?:"([^"]+)"|([^\s]+))', content):
        mentioned_kbs.append(match.group(1) or match.group(2))
    for match in re.finditer(r'@mcp:(?:"([^"]+)"|([^\s]+))', content):
        mentioned_mcps.append(match.group(1) or match.group(2))
    for match in re.finditer(r'@app:(?:"([^"]+)"|([^\s]+))', content):
        mentioned_apps.append(match.group(1) or match.group(2))
    session = sessions.setdefault(
        ws_id, _make_session_state(f"webui:{ws_id[:8]}")
    )
    session_key = session["session_key"]
    cached_profile_id = session.get("profile_id")

    shared_q = _session_queues.setdefault(session_key, deque())
    if session.get("queue") is not shared_q:
        session["queue"] = shared_q

    media_paths = []
    attachments_data = []
    for att in data.get("attachments", []):
        url = att.get("url", "")
        if att.get("type", "").startswith("image/"):
            try:
                p_str = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("path", [None])[
                    0
                ]
                if p_str:
                    media_paths.append(p_str)
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
        else:
            content += f"\n\n[Attached file: {att.get('name', 'file')}]"
        attachments_data.append({"name": att.get("name"), "url": url, "type": att.get("type")})

    msg = {
        "id": data.get("id", str(uuid.uuid4())[:8]),
        "content": content,
        "media": media_paths if media_paths else None,
        "attachments": attachments_data,
        "mentioned_kbs": mentioned_kbs,
        "mentioned_mcps": mentioned_mcps,
        "mentioned_apps": mentioned_apps,
    }

    ps = processing_state.get(session_key)
    if ps and ps.get("processing"):
        try:
            res = await gateway_client.request(
                "steer",
                {
                    "session_key": session_key,
                    "content": content,
                    "media": media_paths if media_paths else None,
                    "attachments": attachments_data,
                },
            )
            if res and res.get("injected"):
                await _emit_to_session(
                    session_key,
                    {
                        "type": "message_ack",
                        "id": msg["id"],
                        "content": content,
                        "session_key": session_key,
                    },
                )
                return
        except Exception as e:
            logger.debug("Failed to steer agent: {}", e)

        shared_q.append(msg)
        await _emit_to_session(
            session_key,
            {
                "type": "message_ack",
                "id": msg["id"],
                "content": content,
                "session_key": session_key,
            },
        )
        await _emit_to_session(
            session_key,
            {
                "type": "message_queued",
                "id": msg["id"],
                "position": len(shared_q),
                "session_key": session_key,
            },
        )
        return

    processing_state[session_key] = {
        "processing": True,
        "msg_id": msg["id"],
        "events": deque(maxlen=_MAX_SESSION_EVENTS),
        "started_at": time.time(),
    }

    await _emit_to_session(
        session_key,
        {"type": "message_ack", "id": msg["id"], "content": content, "session_key": session_key},
    )
    await _emit_session_status_all(session_key)

    async def run_agent_job(message: dict[str, Any]) -> None:
        processing_state[session_key] = {
            "processing": True,
            "msg_id": message["id"],
            "events": deque(maxlen=_MAX_SESSION_EVENTS),
            "started_at": time.time(),
        }

        try:
            payload: dict[str, Any] = {
                "content": message["content"],
                "session_key": session_key,
                "channel": "webui",
                "chat_id": session_key,
                "media": message.get("media"),
                "metadata": {
                    "session_key": session_key,
                    "message_id": message["id"],
                    "attachments": message.get("attachments", []),
                    "mentioned_kbs": message.get("mentioned_kbs", []),
                    "mentioned_mcps": message.get("mentioned_mcps", []),
                    "mentioned_apps": message.get("mentioned_apps", []),
                },
            }

            if cached_profile_id and cached_profile_id != "default":
                payload["profile_id"] = cached_profile_id

            try:
                pm = agent_manager.pm
                if pm:
                    sess = pm.get_or_create(session_key)
                    pid = sess.metadata.get("profile_id")
                    if pid:
                        payload["profile_id"] = pid
                    elif cached_profile_id and cached_profile_id != "default":
                        sess.metadata["profile_id"] = cached_profile_id
                        pm.save(sess)
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)

            response_content = ""
            response_media: list[str] = []
            finish_reason = None

            async for event in gateway_client.chat_stream(payload, request_id=message["id"]):
                if event.get("t") == "p":
                    event_type = "tool" if event.get("h") else "thinking"
                    evt = {
                        "type": event_type,
                        "id": message["id"],
                        "content": event.get("c", ""),
                        "tool_hint": event.get("h", False),
                    }
                    curr_ps = processing_state.get(session_key)
                    if curr_ps:
                        curr_ps["events"].append(evt)
                    await _emit_to_session(
                        session_key,
                        {
                            "type": event_type,
                            "id": message["id"],
                            "content": event.get("c", ""),
                            "tool_hint": event.get("h", False),
                            "session_key": session_key,
                        },
                    )
                elif event.get("t") == "rt":
                    response_content += event.get("c", "")
                    await _emit_to_session(
                        session_key,
                        {
                            "type": "response_chunk",
                            "id": message["id"],
                            "content": event.get("c", ""),
                            "session_key": session_key,
                        },
                    )
                elif event.get("t") == "r":
                    response_content = event.get("content", "")
                    response_media = event.get("media", [])
                    finish_reason = event.get("finish_reason")
                elif event.get("t") == "e":
                    raise RuntimeError(event.get("error", "Gateway error"))

            config = agent_manager.config
            final_atts = _build_attachments(response_media)

            await _synthesize_tts_response(config, response_content, final_atts)

            await _emit_to_session(
                session_key,
                {
                    "type": "response",
                    "id": message["id"],
                    "content": response_content,
                    "attachments": final_atts,
                    "session_key": session_key,
                    "finish_reason": finish_reason,
                },
            )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("WebUI processing error")
            await _emit_to_session(
                session_key, {"type": "error", "message": f"Error: {e}", "session_key": session_key}
            )
        finally:
            q = _session_queues.get(session_key)
            if q:
                next_msg = q.popleft()
                _session_tasks[session_key] = asyncio.create_task(run_agent_job(next_msg))
            else:
                _session_tasks.pop(session_key, None)
                processing_state.pop(session_key, None)
                await _emit_session_status_all(session_key)

    _session_tasks[session_key] = asyncio.create_task(run_agent_job(msg))


async def _emit_session_status_all(session_key: str):
    """Send session status to all clients subscribed to this session."""
    for ws_id in list(_session_subscribers.get(session_key, ())):
        ws = _ws_clients.get(ws_id)
        if ws:
            await _emit_session_status(ws, session_key)


async def _handle_stop(ws_id: str) -> None:
    """Handle stop_agent request."""
    session = sessions.get(ws_id, {})
    sk = session.get("session_key", "")
    if sk:
        _session_queues.pop(sk, None)
        task = _session_tasks.get(sk)
        if task:
            task.cancel()
        else:
            processing_state.pop(sk, None)
            await _emit_session_status_all(sk)
        await _emit_to_session(
            sk,
            {
                "type": "response",
                "id": "stop",
                "content": "🐕 Halted the hunt.",
                "session_key": sk,
            },
        )


async def _handle_cancel(ws_id: str, ws: WebSocket, data: dict[str, Any]) -> None:
    """Handle granular request cancellation."""
    request_id = data.get("id")
    if request_id:
        await gateway_client.cancel_request(request_id)


async def _handle_new_session(ws_id: str, ws: WebSocket, data: dict[str, Any]) -> None:
    """Handle new_session request."""
    new_key = f"webui:{uuid.uuid4().hex[:8]}"
    if ws_id in sessions:
        sessions[ws_id]["session_key"] = new_key
        _subscribe_ws_to_session(ws_id, new_key)

    profile_id = (data or {}).get("profile_id", "default")
    if ws_id in sessions:
        sessions[ws_id]["profile_id"] = profile_id

    await _emit_to_ws(
        ws,
        {
            "type": "session_reset",
            "session_id": new_key,
            "profile_id": profile_id,
            "message": "New session started.",
        },
    )


async def _handle_switch_session(ws_id: str, ws: WebSocket, data: dict[str, Any]) -> None:
    """Handle switch_session request."""
    session_id = (data or {}).get("session_id", "").strip()
    if not session_id:
        return
    if ws_id in sessions:
        sessions[ws_id]["session_key"] = session_id
        _subscribe_ws_to_session(ws_id, session_id)
        logger.info("🔀 WebUI {} switched to session: {}", ws_id, session_id)
        await _emit_session_status(ws, session_id)


async def _handle_transcribe(ws_id: str, ws: WebSocket, data: dict[str, Any]) -> None:
    """Handle audio transcription request."""
    from openai import AsyncOpenAI

    request_id = data.get("id", str(uuid.uuid4())[:8])
    config = agent_manager.config
    if not config:
        await _emit_to_ws(
            ws, {"type": "transcribe_result", "id": request_id, "error": "Agent not configured"}
        )
        return

    raw = data.get("audio")
    if not raw:
        await _emit_to_ws(
            ws, {"type": "transcribe_result", "id": request_id, "error": "No audio provided"}
        )
        return

    try:
        audio_bytes = base64.b64decode(raw)
        uploads_dir = config.workspace_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"voice_user_{uuid.uuid4().hex[:8]}.wav"
        file_path = uploads_dir / file_name
        file_path.write_bytes(audio_bytes)
        audio_url = f"/api/file-get?path={urllib.parse.quote(str(file_path.absolute()))}"

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        api_key = config.audio.resolve_api_key()
        base_url = config.audio.provider_url

        if not api_key and not base_url:
            groq = config.providers.groq
            if groq and groq.resolve_api_key("groq"):
                api_key = groq.resolve_api_key("groq")
                base_url = groq.api_base or "https://api.groq.com/openai/v1"

        client_kwargs = {"api_key": api_key or "not-set"}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = AsyncOpenAI(**client_kwargs)
        res = await client.audio.transcriptions.create(
            model=config.audio.model or "whisper-large-v3-turbo",
            file=audio_file,
            response_format="text",
        )

        await _emit_to_ws(
            ws, {
                "type": "transcribe_result",
                "id": request_id,
                "text": str(res).strip(),
                "audio_url": audio_url
            }
        )
    except Exception as e:
        logger.exception("Audio transcription failed")
        await _emit_to_ws(ws, {"type": "transcribe_result", "id": request_id, "error": str(e)})


# ── Public API for agent_manager / gateway events ────────────


async def deliver_to_browsers(
    session_key: str,
    content: str,
    *,
    source: str = "background",
    msg_type: str = "response",
    metadata: dict | None = None,
    media: list[str] | None = None,
) -> int:
    """Deliver a background notification to matching browser WebSocket clients.

    Args:
        session_key: The session key to target. If empty string, broadcast to all connected clients.
        content: The message content to deliver.
        source: The source of the notification (default: "background").
        msg_type: The WebSocket message type to use (default: "response").

    Returns:
        The number of clients that received the message.
    """
    payload = {
        "type": msg_type,
        "id": str(uuid.uuid4())[:8],
        "content": content,
        "attachments": _build_attachments(media or []),
        "session_key": session_key,
        "source": source,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    delivered = 0

    # If session_key is empty, broadcast to all connected clients
    if session_key == "":
        for ws in _ws_clients.values():
            try:
                await ws.send_text(json.dumps(payload))
                delivered += 1
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)
    else:
        # Original behavior: deliver only to matching session
        raw = json.dumps(payload)
        for ws_id in list(_session_subscribers.get(session_key, ())):
            ws = _ws_clients.get(ws_id)
            if ws:
                try:
                    await ws.send_text(raw)
                    delivered += 1
                except Exception as _e:
                    logger.debug("Ignored error: {}", _e)
    return delivered


async def broadcast_notification(notification: dict[str, Any]) -> int:
    """Broadcast a notification-center event to all connected browser clients."""
    payload = {
        "type": "notification",
        "id": notification.get("id", str(uuid.uuid4())[:8]),
        "content": notification.get("message", ""),
        "session_key": notification.get("session_key", ""),
        "source": notification.get("source", "notification"),
        "metadata": notification,
    }

    delivered = 0
    for ws in list(_ws_clients.values()):
        try:
            await ws.send_text(json.dumps(payload))
            delivered += 1
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)
    return delivered
