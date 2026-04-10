"""Socket.IO event handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import asyncio
import base64
import io
import time
import uuid
import urllib.parse
import mimetypes
from pathlib import Path
from typing import Any, Dict

import socketio
from loguru import logger

from .auth import _auth_enabled, verify_token_value
from .agent_manager import agent_manager

processing_state: Dict[str, Dict[str, Any]] = {}


def _room(session_key: str) -> str:
    return f"session:{session_key}"


def _build_attachments(media_paths: list[str]) -> list[Dict[str, str]]:
    atts = []
    for m_path in media_paths:
        p = Path(m_path)
        res = mimetypes.guess_type(m_path)
        atts.append({
            "name": p.name,
            "url": f"/api/file-get?path={urllib.parse.quote(str(p.absolute()))}",
            "type": res[0] or "application/octet-stream"
        })
    return atts


def register_socket_handlers(sio: socketio.AsyncServer, sessions: Dict[str, Dict]):
    """Register all Socket.IO event handlers."""

    async def _emit_session_status(room: str, session_key: str) -> None:
        ps = processing_state.get(session_key)
        if ps and ps.get("processing"):
            await sio.emit("session_status", {
                "session_key": session_key,
                "processing": True,
                "msg_id": ps.get("msg_id", ""),
                "events": ps.get("events", []),
                "started_at": ps.get("started_at", 0),
            }, room=room)
        else:
            await sio.emit("session_status", {
                "session_key": session_key,
                "processing": False,
            }, room=room)

    @sio.event
    async def connect(sid, environ, auth=None):
        if _auth_enabled():
            token = auth.get("token") if isinstance(auth, dict) else None
            if not verify_token_value(token):
                logger.warning("🔒 Socket.IO connection rejected (invalid token) from {}", sid)
                raise socketio.exceptions.ConnectionRefusedError("Unauthorized")

        query = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        provided_id = query.get("session_id", [None])[0]

        session_id = provided_id if provided_id else f"webui:{sid[:8]}"
        sessions[sid] = {"session_key": session_id, "processing": False, "queue": []}
        logger.info("🌐 WebUI client connected: {} (Session: {})", sid, session_id)

        await sio.enter_room(sid, _room(session_id))

        await sio.emit("connected", {
            "session_id": session_id,
            "message": "🐕 ShibaClaw WebUI connected!",
        }, room=sid)

        await _emit_session_status(sid, session_id)

    @sio.event
    async def disconnect(sid):
        session = sessions.pop(sid, None)
        if session:
            await sio.leave_room(sid, _room(session["session_key"]))
        logger.info("🌐 WebUI client disconnected: {}", sid)

    @sio.event
    async def user_message(sid, data):
        await agent_manager.ensure_agent()
        if agent_manager.agent is None:
            await sio.emit("error", {"message": "Agent not configured."}, room=sid)
            return

        content = data.get("content", "").strip()
        session = sessions.setdefault(sid, {"session_key": f"webui:{sid[:8]}", "processing": False, "queue": []})
        session_key = session["session_key"]
        sk_room = _room(session_key)

        media_paths = []
        attachments_data = []
        for att in data.get("attachments", []):
            url = att.get("url", "")
            if att.get("type", "").startswith("image/"):
                try:
                    p_str = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("path", [None])[0]
                    if p_str: media_paths.append(p_str)
                except Exception: pass
            else:
                content += f"\n\n[Attached file: {att.get('name', 'file')}]"

            attachments_data.append({
                "name": att.get("name"),
                "url": url,
                "type": att.get("type")
            })

        msg = {
            "id": str(uuid.uuid4())[:8],
            "content": content,
            "media": media_paths if media_paths else None,
            "attachments": attachments_data
        }

        if session.get("processing"):
            session.setdefault("queue", []).append(msg)
            await sio.emit("message_ack", {"id": msg["id"], "content": content, "session_key": session_key}, room=sk_room)
            await sio.emit("message_queued", {"id": msg["id"], "position": len(session["queue"]), "session_key": session_key}, room=sk_room)
            return

        session["processing"] = True
        await sio.emit("message_ack", {"id": msg["id"], "content": content, "session_key": session_key}, room=sk_room)

        async def run_agent_job(message):
            processing_state[session_key] = {
                "processing": True,
                "msg_id": message["id"],
                "events": [],
                "started_at": time.time(),
            }

            async def on_progress(text: str, *, tool_hint: bool = False):
                event_type = "agent_tool" if tool_hint else "agent_thinking"
                evt = {"type": event_type, "id": message["id"], "content": text, "tool_hint": tool_hint}
                ps = processing_state.get(session_key)
                if ps:
                    ps["events"].append(evt)
                await sio.emit(event_type, {
                    "id": message["id"], "content": text,
                    "tool_hint": tool_hint, "session_key": session_key
                }, room=sk_room)

            try:
                outbound = await agent_manager.agent.process_direct(
                    content=message["content"],
                    session_key=session_key,
                    channel="webui",
                    chat_id=session_key,
                    on_progress=on_progress,
                    media=message.get("media"),
                    metadata={"session_key": session_key, "message_id": message["id"]}
                )

                if outbound is None:
                    return

                response_content = outbound.content or "No response."
                media_list = outbound.media or []

                pm = getattr(agent_manager.agent, "sessions", None)
                final_atts = _build_attachments(media_list)
                
                if pm:
                    sess = pm.get_or_create(session_key)
                    if sess and sess.messages:
                        for m_idx in range(len(sess.messages)-1, -1, -1):
                            if sess.messages[m_idx].get("role") == "user":
                                sess.messages[m_idx].setdefault("metadata", {})["attachments"] = message.get("attachments", [])
                                break
                        for m_idx in range(len(sess.messages)-1, -1, -1):
                            if sess.messages[m_idx].get("role") == "assistant":
                                if final_atts:
                                    sess.messages[m_idx].setdefault("metadata", {})["attachments"] = final_atts
                                pm.save(sess)
                                break

                content_to_send = response_content if response_content != "No response." else ""
                if not content_to_send and not final_atts:
                    return

                await sio.emit("agent_response", {
                    "id": message["id"],
                    "content": content_to_send,
                    "attachments": final_atts,
                    "session_key": session_key
                }, room=sk_room)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("WebUI processing error")
                await sio.emit("error", {"message": f"Error: {e}", "session_key": session_key}, room=sk_room)
            finally:
                q = session.get("queue") or []
                if q:
                    next_msg = q.pop(0)
                    session["task"] = asyncio.create_task(run_agent_job(next_msg))
                else:
                    session["processing"] = False
                    session.pop("task", None)
                    processing_state.pop(session_key, None)
                    await _emit_session_status(sk_room, session_key)

        session["task"] = asyncio.create_task(run_agent_job(msg))

    @sio.event
    async def stop_agent(sid, data=None):
        session = sessions.get(sid, {})
        if "task" in session:
            session["task"].cancel()
        session["queue"] = []
        session["processing"] = False
        sk = session.get("session_key", "")
        processing_state.pop(sk, None)
        await sio.emit("agent_response", {"id": "stop", "content": "🐕 Halted the hunt.", "session_key": sk}, room=_room(sk))

    @sio.event
    async def new_session(sid, data=None):
        old_session = sessions.get(sid)
        if old_session:
            await sio.leave_room(sid, _room(old_session["session_key"]))
        new_key = f"webui:{uuid.uuid4().hex[:8]}"
        if sid in sessions:
            sessions[sid]["session_key"] = new_key
        await sio.enter_room(sid, _room(new_key))
        await sio.emit("session_reset", {"session_id": new_key, "message": "New session started."}, room=sid)

    @sio.event
    async def switch_session(sid, data=None):
        session_id = (data or {}).get("session_id", "").strip()
        if not session_id:
            return
        if sid in sessions:
            old_key = sessions[sid]["session_key"]
            await sio.leave_room(sid, _room(old_key))
            sessions[sid]["session_key"] = session_id
            await sio.enter_room(sid, _room(session_id))
            logger.info("🔀 WebUI {} switched to session: {}", sid, session_id)
            await _emit_session_status(sid, session_id)

    @sio.event
    async def transcribe_audio(sid, data):
        """Receive base64 audio and return transcribed text via OpenAI-compatible STT."""
        from openai import AsyncOpenAI

        config = agent_manager.config
        if not config:
            return {"error": "Agent not configured"}

        raw = data.get("audio")
        if not raw:
            return {"error": "No audio provided"}

        try:
            audio_bytes = base64.b64decode(raw)
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"

            client_kwargs = {"api_key": config.audio.api_key or "not-set"}
            if config.audio.provider_url:
                client_kwargs["base_url"] = config.audio.provider_url

            client = AsyncOpenAI(**client_kwargs)
            res = await client.audio.transcriptions.create(
                model=config.audio.model or "whisper-large-v3-turbo",
                file=audio_file,
                response_format="text"
            )

            return {"text": str(res).strip()}
        except Exception as e:
            logger.exception("Audio transcription failed")
            return {"error": str(e)}
