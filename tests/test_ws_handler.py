import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque

from shibaclaw.webui.ws_handler import (
    _handle_user_message,
    processing_state,
    sessions,
    _ws_clients,
)
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.gateway_client import gateway_client


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

    with patch("shibaclaw.webui.ws_handler._emit_to_session", AsyncMock()) as mock_emit, \
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

