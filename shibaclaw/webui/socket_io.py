"""Socket.IO event handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import asyncio
import uuid
import urllib.parse
import mimetypes
from pathlib import Path
from typing import Any, Dict

import socketio
from loguru import logger

from .auth import _auth_enabled, get_auth_token, mask_token
from .agent_manager import agent_manager


def register_socket_handlers(sio: socketio.AsyncServer, sessions: Dict[str, Dict]):
    """Register all Socket.IO event handlers."""

    @sio.event
    async def connect(sid, environ, auth=None):
        auth_token = get_auth_token()
        if _auth_enabled() and auth_token:
            token = auth.get("token") if isinstance(auth, dict) else None
            if token != auth_token:
                logger.warning("🔒 Socket.IO connection rejected (invalid token) from {}", sid)
                raise socketio.exceptions.ConnectionRefusedError("Unauthorized")

        query = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        provided_id = query.get("session_id", [None])[0]
        
        session_id = provided_id if provided_id else f"webui:{sid[:8]}"
        sessions[sid] = {"session_key": session_id, "processing": False, "queue": []}
        logger.info("🌐 WebUI client connected: {} (Session: {})", sid, session_id)
        
        await sio.emit("connected", {
            "session_id": session_id,
            "message": "🐕 ShibaClaw WebUI connected!",
        }, room=sid)

    @sio.event
    async def disconnect(sid):
        sessions.pop(sid, None)
        logger.info("🌐 WebUI client disconnected: {}", sid)

    @sio.event
    async def user_message(sid, data):
        """Handle user messages with queuing and agent processing."""
        await agent_manager.ensure_agent()
        if agent_manager.agent is None:
            await sio.emit("error", {"message": "Agent not configured."}, room=sid)
            return

        content = data.get("content", "").strip()
        session = sessions.setdefault(sid, {"session_key": f"webui:{sid[:8]}", "processing": False, "queue": []})
        session_key = session["session_key"]

        # Parse media/attachments
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
            await sio.emit("message_ack", {"id": msg["id"], "content": content}, room=sid)
            await sio.emit("message_queued", {"id": msg["id"], "position": len(session["queue"])}, room=sid)
            return

        session["processing"] = True
        await sio.emit("message_ack", {"id": msg["id"], "content": content}, room=sid)

        async def run_agent_job(message):
            async def on_progress(text: str, *, tool_hint: bool = False):
                event = "agent_tool" if tool_hint else "agent_thinking"
                await sio.emit(event, {"id": message["id"], "content": text, "tool_hint": tool_hint}, room=sid)

            try:
                outbound = await agent_manager.agent.process_direct(
                    content=message["content"],
                    session_key=session_key,
                    channel="webui",
                    chat_id=sid,
                    on_progress=on_progress,
                    media=message.get("media"),
                    metadata={"sid": sid}
                )

                if outbound is None: return

                response_content = outbound.content or "No response."
                media_list = outbound.media or []

                # Update history with attachments
                pm = getattr(agent_manager.agent, "sessions", None)
                if pm:
                    sess = pm.get_or_create(session_key)
                    if sess and sess.messages:
                        # User message attachments
                        for m_idx in range(len(sess.messages)-1, -1, -1):
                            if sess.messages[m_idx].get("role") == "user":
                                sess.messages[m_idx].setdefault("metadata", {})["attachments"] = message.get("attachments", [])
                                break
                        # Agent message attachments
                        for m_idx in range(len(sess.messages)-1, -1, -1):
                            if sess.messages[m_idx].get("role") == "assistant":
                                auth_token = get_auth_token() or ""
                                agent_atts = []
                                for m_path in media_list:
                                    p = Path(m_path)
                                    res = mimetypes.guess_type(m_path)
                                    agent_atts.append({
                                        "name": p.name,
                                        "url": f"/api/file-get?path={urllib.parse.quote(str(p.absolute()))}&token={auth_token}",
                                        "type": res[0] or "application/octet-stream"
                                    })
                                if agent_atts:
                                    sess.messages[m_idx].setdefault("metadata", {})["attachments"] = agent_atts
                                pm.save(sess)
                                break

                # Final response emit
                auth_token = get_auth_token() or ""
                final_atts = []
                for m_path in media_list:
                    p = Path(m_path)
                    res = mimetypes.guess_type(m_path)
                    final_atts.append({
                        "name": p.name,
                        "url": f"/api/file-get?path={urllib.parse.quote(str(p.absolute()))}&token={auth_token}",
                        "type": res[0] or "application/octet-stream"
                    })

                content_to_send = response_content if response_content != "No response." else ""
                if not content_to_send and not final_atts:
                    return  # truly nothing to send

                await sio.emit("agent_response", {
                    "id": message["id"],
                    "content": content_to_send,
                    "attachments": final_atts
                }, room=sid)

            except asyncio.CancelledError:
                pass  # stop_agent handler already notified the user
            except Exception as e:
                logger.exception("WebUI processing error")
                await sio.emit("error", {"message": f"Error: {e}"}, room=sid)
            finally:
                q = session.get("queue") or []
                if q:
                    next_msg = q.pop(0)
                    session["task"] = asyncio.create_task(run_agent_job(next_msg))
                else:
                    session["processing"] = False
                    session.pop("task", None)

        session["task"] = asyncio.create_task(run_agent_job(msg))

    @sio.event
    async def stop_agent(sid, data=None):
        session = sessions.get(sid, {})
        if "task" in session:
            session["task"].cancel()
        session["queue"] = []
        session["processing"] = False
        await sio.emit("agent_response", {"id": "stop", "content": "🐕 Halted the hunt."}, room=sid)

    @sio.event
    async def new_session(sid, data=None):
        new_key = f"webui:{uuid.uuid4().hex[:8]}"
        if sid in sessions: sessions[sid]["session_key"] = new_key
        await sio.emit("session_reset", {"session_id": new_key, "message": "New session started."}, room=sid)

    @sio.event
    async def switch_session(sid, data=None):
        """Switch the active session key for an existing client without resetting the UI."""
        session_id = (data or {}).get("session_id", "").strip()
        if not session_id:
            return
        if sid in sessions:
            sessions[sid]["session_key"] = session_id
            logger.info("🔀 WebUI {} switched to session: {}", sid, session_id)
