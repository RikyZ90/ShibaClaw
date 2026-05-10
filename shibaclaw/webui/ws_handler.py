"""Native WebSocket handler for browser ↔ WebUI communication.

Replaces the Socket.IO layer (socket_io.py) with a lightweight JSON
protocol over standard WebSocket.  The event names are kept identical
so the browser adapter is a thin wrapper around native WebSocket.
"""

from __future__ import annotations

import asyncio
import base64
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
sessions: Dict[str, Dict[str, Any]] = {}  # ws_id → session state
processing_state: Dict[str, Dict[str, Any]] = {}  # session_key → processing info
_ws_clients: Dict[str, WebSocket] = {}  # ws_id → WebSocket instance


def _build_attachments(media_paths: list[str]) -> list[Dict[str, str]]:
    atts = []
    for m_path in media_paths:
        p = Path(m_path)
        res = mimetypes.guess_type(m_path)
        atts.append(
            {
                "name": p.name,
                "url": f"/api/file-get?path={urllib.parse.quote(str(p.absolute()))}",
                "type": res[0] or "application/octet-stream",
            }
        )
    return atts


async def _emit_to_session(session_key: str, msg: dict, *, exclude: str | None = None):
    """Send a message to all WebSocket clients subscribed to a session."""
    raw = json.dumps(msg)
    for ws_id, state in list(sessions.items()):
        if state.get("session_key") == session_key and ws_id != exclude:
            ws = _ws_clients.get(ws_id)
            if ws:
                try:
                    await ws.send_text(raw)
                except Exception:
                    pass


async def _emit_to_ws(ws: WebSocket, msg: dict):
    """Send a message to a specific WebSocket client."""
    try:
        await ws.send_text(json.dumps(msg))
    except Exception:
        pass


async def ws_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint handler for browser clients."""
    await websocket.accept()
    ws_id = str(uuid.uuid4())[:12]

    # ── Auth ──
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        msg = json.loads(raw)
    except Exception:
        await websocket.close(4001, "Expected auth message")
        return

    if msg.get("type") != "auth":
        await websocket.close(4001, "Expected auth message")
        return

    if _auth_enabled():
        token = msg.get("token")
        if not verify_token_value(token):
            await _emit_to_ws(websocket, {"type": "error", "message": "Unauthorized"})
            await websocket.close(4003, "Unauthorized")
            logger.warning("🔒 WebSocket rejected (invalid token) from {}", ws_id)
            return

    # ── Session setup ──
    provided_id = msg.get("session_id")
    session_id = provided_id if provided_id else f"webui:{ws_id[:8]}"
    sessions[ws_id] = {"session_key": session_id, "processing": False, "queue": []}
    _ws_clients[ws_id] = websocket
    logger.info("🌐 WebUI client connected: {} (Session: {})", ws_id, session_id)

    profile_id = "default"
    try:
        if agent_manager.config and agent_manager.pm:
            pm = agent_manager.pm
            sess = pm.get_or_create(session_id)
            profile_id = sess.metadata.get("profile_id", "default")
    except Exception:
        pass

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
        sessions.pop(ws_id, None)
        _ws_clients.pop(ws_id, None)
        logger.info("🌐 WebUI client disconnected: {}", ws_id)


async def _emit_session_status(ws: WebSocket, session_key: str):
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
                "events": ps.get("events", []),
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


async def _handle_user_message(ws_id: str, ws: WebSocket, data: dict):
    """Handle an incoming user message."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        await _emit_to_ws(ws, {"type": "error", "message": "No configuration found."})
        return

    content = data.get("content", "").strip()
    session = sessions.setdefault(
        ws_id, {"session_key": f"webui:{ws_id[:8]}", "processing": False, "queue": []}
    )
    session_key = session["session_key"]
    cached_profile_id = session.get("profile_id")

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
            except Exception:
                pass
        else:
            content += f"\n\n[Attached file: {att.get('name', 'file')}]"
        attachments_data.append({"name": att.get("name"), "url": url, "type": att.get("type")})

    msg = {
        "id": data.get("id", str(uuid.uuid4())[:8]),
        "content": content,
        "media": media_paths if media_paths else None,
        "attachments": attachments_data,
    }

    if session.get("processing"):
        session.setdefault("queue", []).append(msg)
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
                "position": len(session["queue"]),
                "session_key": session_key,
            },
        )
        return

    session["processing"] = True
    await _emit_to_session(
        session_key,
        {"type": "message_ack", "id": msg["id"], "content": content, "session_key": session_key},
    )
    # Emit session status to update UI about processing state
    await _emit_session_status_all(session_key)

    async def run_agent_job(message):
        processing_state[session_key] = {
            "processing": True,
            "msg_id": message["id"],
            "events": [],
            "started_at": time.time(),
        }

        try:
            payload = {
                "content": message["content"],
                "session_key": session_key,
                "channel": "webui",
                "chat_id": session_key,
                "media": message.get("media"),
                "metadata": {
                    "session_key": session_key,
                    "message_id": message["id"],
                    "attachments": message.get("attachments", []),
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
            except Exception:
                pass

            response_content = ""
            response_media: list[str] = []

            async for event in gateway_client.chat_stream(payload):
                if event.get("t") == "p":
                    event_type = "tool" if event.get("h") else "thinking"
                    evt = {
                        "type": event_type,
                        "id": message["id"],
                        "content": event.get("c", ""),
                        "tool_hint": event.get("h", False),
                    }
                    ps = processing_state.get(session_key)
                    if ps:
                        ps["events"].append(evt)
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
                elif event.get("t") == "e":
                    raise RuntimeError(event.get("error", "Gateway error"))

            final_atts = _build_attachments(response_media)


            if not response_content and not final_atts:
                # Even when content is empty, we must send a response event
                # so the browser finalises any streaming bubble and resets
                # processing state.  Only skip if nothing was streamed either.
                pass

            await _emit_to_session(
                session_key,
                {
                    "type": "response",
                    "id": message["id"],
                    "content": response_content,
                    "attachments": final_atts,
                    "session_key": session_key,
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
            q = session.get("queue") or []
            if q:
                next_msg = q.pop(0)
                session["task"] = asyncio.create_task(run_agent_job(next_msg))
            else:
                session["processing"] = False
                session.pop("task", None)
                processing_state.pop(session_key, None)
                await _emit_session_status_all(session_key)

    session["task"] = asyncio.create_task(run_agent_job(msg))


async def _emit_session_status_all(session_key: str):
    """Send session status to all clients subscribed to this session."""
    for ws_id, state in list(sessions.items()):
        if state.get("session_key") == session_key:
            ws = _ws_clients.get(ws_id)
            if ws:
                await _emit_session_status(ws, session_key)


async def _handle_stop(ws_id: str):
    """Handle stop_agent request."""
    session = sessions.get(ws_id, {})
    if "task" in session:
        session["task"].cancel()
    session["queue"] = []
    session["processing"] = False
    sk = session.get("session_key", "")
    processing_state.pop(sk, None)
    await _emit_to_session(
        sk,
        {
            "type": "response",
            "id": "stop",
            "content": "🐕 Halted the hunt.",
            "session_key": sk,
        },
    )


async def _handle_new_session(ws_id: str, ws: WebSocket, data: dict):
    """Handle new_session request."""
    sessions.get(ws_id)
    new_key = f"webui:{uuid.uuid4().hex[:8]}"
    if ws_id in sessions:
        sessions[ws_id]["session_key"] = new_key

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


async def _handle_switch_session(ws_id: str, ws: WebSocket, data: dict):
    """Handle switch_session request."""
    session_id = (data or {}).get("session_id", "").strip()
    if not session_id:
        return
    if ws_id in sessions:
        sessions[ws_id]["session_key"] = session_id
        logger.info("🔀 WebUI {} switched to session: {}", ws_id, session_id)
        await _emit_session_status(ws, session_id)


async def _handle_transcribe(ws_id: str, ws: WebSocket, data: dict):
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
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        api_key = config.audio.api_key
        base_url = config.audio.provider_url

        if not api_key and not base_url:
            groq = config.providers.groq
            if groq and groq.api_key:
                api_key = groq.api_key
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
            ws, {"type": "transcribe_result", "id": request_id, "text": str(res).strip()}
        )
    except Exception as e:
        logger.exception("Audio transcription failed")
        await _emit_to_ws(ws, {"type": "transcribe_result", "id": request_id, "error": str(e)})


# ── Public API for agent_manager / gateway events ────────────


async def deliver_to_browsers(
    session_key: str, content: str, *, source: str = "background", msg_type: str = "response"
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
        "attachments": [],
        "session_key": session_key,
    }
    delivered = 0

    # If session_key is empty, broadcast to all connected clients
    if session_key == "":
        for ws in _ws_clients.values():
            try:
                await ws.send_text(json.dumps(payload))
                delivered += 1
            except Exception:
                pass
    else:
        # Original behavior: deliver only to matching session
        for ws_id, state in list(sessions.items()):
            if state.get("session_key") != session_key:
                continue
            ws = _ws_clients.get(ws_id)
            if ws:
                try:
                    await ws.send_text(json.dumps(payload))
                    delivered += 1
                except Exception:
                    pass
    return delivered
