"""Resetting a chat model override restores the configured model on the next turn."""

import copy
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.brain.manager import PackManager
from shibaclaw.config.schema import Config
from shibaclaw.thinkers.base import LLMResponse
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.sessions import api_sessions_get, api_sessions_patch


def _request(session_id, payload=None):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload or {}).encode(), "more_body": False}

    return Request({
        "type": "http", "method": "PATCH" if payload is not None else "GET",
        "path": f"/api/sessions/{session_id}", "headers": [],
        "path_params": {"session_id": session_id},
    }, receive)


@pytest.mark.asyncio
@pytest.mark.parametrize("reset_model", [None, ""])
async def test_session_model_reset_restores_default_next_turn_without_losing_metadata(
    tmp_path, monkeypatch, reset_model,
):
    monkeypatch.setattr("shibaclaw.brain.manager.get_legacy_sessions_dir", lambda: tmp_path / "legacy")
    cfg = Config.model_validate({
        "agents": {"defaults": {"workspace": str(tmp_path), "model": "custom/org/default-model"}},
        "providers": {"custom": {"name": "Local", "apiBase": "http://127.0.0.1:1234/v1"}},
        "providerEndpoints": {"endpoint_override": {"provider": "custom", "apiBase": "http://127.0.0.1:5678/v1"}},
    })
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "manifest.json").write_text(json.dumps({"writer": {"label": "Writer"}}), encoding="utf-8")
    original_cfg = cfg.model_dump()
    session_id = "webui:reset-model"
    ui_sessions = PackManager(tmp_path)
    session = ui_sessions.get_or_create(session_id)
    session.metadata = {
        "model": "endpoint_override/org/previous-model", "profile_id": "writer",
        "reasoning_effort": "high", "nickname": "Keep this chat", "knowledge_bases": ["saved-kb"],
    }
    session.add_message("user", "Previous question")
    session.add_message("assistant", "Previous answer")
    ui_sessions.save(session)
    original_messages = copy.deepcopy(session.messages)
    original_metadata = copy.deepcopy(session.metadata)

    default_provider = MagicMock()
    default_provider.get_default_model.return_value = cfg.agents.defaults.model
    default_provider.chat_with_retry_streaming = AsyncMock(return_value=LLMResponse(content="Default reply", finish_reason="stop"))
    previous_provider = MagicMock()
    brain = ShibaBrain(
        bus=MagicMock(), provider=default_provider, workspace=tmp_path, config=cfg,
        model=cfg.agents.defaults.model, session_manager=PackManager(tmp_path),
        web_search_config=cfg.tools.web.search, exec_config=cfg.tools.exec,
    )
    brain.mcp.connect = AsyncMock()
    # Keep the real turn and provider selection; exclude unrelated background learning.
    brain._schedule_background = lambda coro: coro.close()
    brain._provider_cache["endpoint_override"] = previous_provider
    assert brain.sessions.get_or_create(session_id).metadata["model"] == original_metadata["model"]
    monkeypatch.setattr(agent_manager, "config", cfg)
    monkeypatch.setattr(agent_manager, "_pack_manager", ui_sessions)

    response = await api_sessions_patch(_request(session_id, {"model": reset_model}))
    assert response.status_code == 200
    response = await api_sessions_get(_request(session_id))
    payload = json.loads(response.body)
    assert not payload["model"]
    assert payload["messages"] == original_messages
    assert payload["profile_id"] == "writer"
    assert payload["reasoning_effort"] == "high"
    assert payload["knowledge_bases"] == ["saved-kb"]

    result = await brain.process_direct("Next question", session_key=session_id, channel="webui", chat_id="reset-model")
    assert result.content == "Default reply"
    default_provider.chat_with_retry_streaming.assert_awaited_once()
    call = default_provider.chat_with_retry_streaming.await_args.kwargs
    assert call["model"] == cfg.agents.defaults.model
    assert call["reasoning_effort"] == "high"
    assert any(message.get("content") == "Previous question" for message in call["messages"])
    previous_provider.chat_with_retry_streaming.assert_not_called()

    response = await api_sessions_get(_request(session_id))
    payload = json.loads(response.body)
    assert not payload["model"]
    assert payload["messages"][:len(original_messages)] == original_messages
    reloaded = PackManager(tmp_path).get_or_create(session_id)
    assert reloaded.metadata == {**original_metadata, "model": reset_model}
    assert cfg.model_dump() == original_cfg
