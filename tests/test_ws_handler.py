import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque

from shibaclaw.webui.ws_handler import (
    _handle_user_message,
    processing_state,
    sessions,
    _ws_clients,
    _session_tasks,
)
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.gateway_client import gateway_client


@pytest.mark.asyncio
async def test_ws_handler_reports_empty_gateway_result_instead_of_blank_response():
    agent_manager.config = MagicMock()
    agent_manager._pack_manager = MagicMock()
    session_key = "webui:empty_result"
    sessions["ws-empty"] = {"session_key": session_key, "processing": False, "queue": deque()}
    _ws_clients["ws-empty"] = MagicMock()

    async def empty_chat_stream(payload, request_id):
        yield {"t": "r", "content": "", "media": []}

    try:
        with patch("shibaclaw.webui.ws_handler._emit_to_session", AsyncMock()) as emit, \
             patch("shibaclaw.webui.ws_handler._emit_session_status_all", AsyncMock()), \
             patch.object(gateway_client, "chat_stream", side_effect=empty_chat_stream):
            await _handle_user_message("ws-empty", _ws_clients["ws-empty"], {"content": "hello", "id": "msg-empty"})
            await _session_tasks[session_key]

        events = [call.args[1] for call in emit.call_args_list]
        assert any(event.get("type") == "error" and "no response" in event.get("message", "") for event in events)
        assert not any(event.get("type") == "response" and not event.get("content") for event in events)
    finally:
        sessions.pop("ws-empty", None)
        _ws_clients.pop("ws-empty", None)
        processing_state.pop(session_key, None)


@pytest.mark.asyncio
async def test_ws_handler_multi_tab_race_condition():
    agent_manager.config = MagicMock()
    agent_manager._pack_manager = MagicMock()

    ws1 = MagicMock()
    ws2 = MagicMock()
    _ws_clients["ws1"] = ws1
    _ws_clients["ws2"] = ws2

    session_key = "webui:shared_session"
    sessions["ws1"] = {
        "session_key": session_key,
        "processing": False,
        "queue": deque(),
    }
    sessions["ws2"] = {
        "session_key": session_key,
        "processing": False,
        "queue": deque(),
    }

    first_job_started = asyncio.Event()
    first_job_can_finish = asyncio.Event()

    async def mock_chat_stream(payload, request_id):
        first_job_started.set()
        await first_job_can_finish.wait()
        yield {"t": "rt", "c": "Hello!"}

    with patch("shibaclaw.webui.ws_handler._emit_to_session", AsyncMock()), \
         patch("shibaclaw.webui.ws_handler._emit_to_ws", AsyncMock()), \
         patch("shibaclaw.webui.ws_handler._emit_session_status_all", AsyncMock()), \
         patch.object(gateway_client, "chat_stream", side_effect=mock_chat_stream):

        task1 = asyncio.create_task(
            _handle_user_message("ws1", ws1, {"content": "First message", "id": "msg1"})
        )

        await first_job_started.wait()

        assert processing_state[session_key]["processing"] is True

        await _handle_user_message("ws2", ws2, {"content": "Second message", "id": "msg2"})

        assert len(sessions["ws2"]["queue"]) == 1
        assert sessions["ws2"]["queue"][0]["id"] == "msg2"

        first_job_can_finish.set()
        await task1

        await asyncio.sleep(0.05)

        assert len(sessions["ws2"]["queue"]) == 0
        assert session_key not in processing_state
        
    sessions.clear()
    _ws_clients.clear()
    processing_state.clear()


@pytest.mark.asyncio
async def test_ws_handler_steering():
    agent_manager.config = MagicMock()
    ws1 = MagicMock()
    _ws_clients["ws1"] = ws1

    session_key = "webui:steering_session"
    sessions["ws1"] = {
        "session_key": session_key,
        "processing": True,
        "queue": deque(),
    }
    processing_state[session_key] = {
        "processing": True,
        "msg_id": "msg1",
        "events": deque(),
        "started_at": 12345,
    }

    mock_request = AsyncMock(return_value={"injected": True})

    with patch("shibaclaw.webui.ws_handler._emit_to_session", AsyncMock()) as mock_emit, \
         patch.object(gateway_client, "request", mock_request):

        await _handle_user_message("ws1", ws1, {"content": "Steering comment", "id": "msg2"})

        # Assert steer request was called
        mock_request.assert_called_once_with(
            "steer",
            {
                "session_key": session_key,
                "content": "Steering comment",
                "media": None,
                "attachments": [],
            }
        )

        # Assert it was NOT queued
        assert len(sessions["ws1"]["queue"]) == 0
        # Assert message_ack was emitted for msg2
        ack_call = [c for c in mock_emit.call_args_list if c[0][1].get("type") == "message_ack" and c[0][1].get("id") == "msg2"]
        assert len(ack_call) == 1

    sessions.clear()
    _ws_clients.clear()
    processing_state.clear()


@pytest.mark.asyncio
async def test_ws_handler_steering_fallback():
    agent_manager.config = MagicMock()
    ws1 = MagicMock()
    _ws_clients["ws1"] = ws1

    session_key = "webui:steering_session"
    sessions["ws1"] = {
        "session_key": session_key,
        "processing": True,
        "queue": deque(),
    }
    processing_state[session_key] = {
        "processing": True,
        "msg_id": "msg1",
        "events": deque(),
        "started_at": 12345,
    }

    mock_request = AsyncMock(return_value={"injected": False})

    with patch("shibaclaw.webui.ws_handler._emit_to_session", AsyncMock()), \
         patch.object(gateway_client, "request", mock_request):

        await _handle_user_message("ws1", ws1, {"content": "Normal comment", "id": "msg2"})

        # Assert steer request was called
        mock_request.assert_called_once()

        # Assert it was queued (because steering failed/was rejected)
        assert len(sessions["ws1"]["queue"]) == 1
        assert sessions["ws1"]["queue"][0]["id"] == "msg2"

    sessions.clear()
    _ws_clients.clear()
    processing_state.clear()



@pytest.mark.asyncio
@pytest.mark.parametrize(("final_text", "media"), [("Complete answer", []), ("", ["/tmp/image.png"])])
async def test_ws_handler_final_response_is_authoritative(monkeypatch, final_text, media):
    from shibaclaw.webui import ws_handler

    key, ws_id = "webui:render-final", "ws-render-final"
    socket = MagicMock(send_text=AsyncMock())
    monkeypatch.setattr(agent_manager, "config", MagicMock())
    monkeypatch.setattr(agent_manager, "_pack_manager", MagicMock())
    monkeypatch.setitem(sessions, ws_id, {"session_key": key, "processing": False, "queue": deque()})
    monkeypatch.setitem(_ws_clients, ws_id, socket)
    emit, tts = AsyncMock(), AsyncMock()
    monkeypatch.setattr(ws_handler, "_emit_to_session", emit)
    monkeypatch.setattr(ws_handler, "_emit_session_status_all", AsyncMock())
    monkeypatch.setattr(ws_handler, "_synthesize_tts_response", tts)

    async def stream(payload, request_id):
        yield {"t": "rt", "c": "Partial draft"}
        yield {"t": "r", "content": final_text, "media": media}

    monkeypatch.setattr(gateway_client, "chat_stream", stream)
    await _handle_user_message(ws_id, socket, {"content": "hello", "id": "render-final"})
    await _session_tasks[key]
    response, = [call.args[1] for call in emit.call_args_list if call.args[1].get("type") == "response"]
    assert response["content"] == final_text
    assert bool(response["attachments"]) == bool(media)
    assert tts.await_args.args[1] == final_text
