import pytest
from unittest.mock import MagicMock
from starlette.requests import Request
from shibaclaw.webui.api import api_context_get


@pytest.mark.asyncio
async def test_api_context_get_estimate_prompt_tokens_bug(monkeypatch):
    request = MagicMock(spec=Request)
    request.query_params = {"session_id": "test_session"}
    request.app = MagicMock()

    agent_manager = MagicMock()
    agent_manager.pm.get_or_create.return_value = MagicMock(metadata={"knowledge_bases": []})
    agent_manager.get_session_messages.return_value = []
    request.app.state.agent_manager = agent_manager

    # To pass "if not agent_manager.config" check
    cfg = MagicMock()
    cfg.workspace_path = "/tmp"
    cfg.agents.defaults.provider = "test"
    cfg.agents.defaults.context_window_tokens = 4000
    agent_manager.config = cfg

    import shibaclaw.webui.api

    shibaclaw.webui.api.agent_manager = agent_manager

    def mock_build_real_system_prompt(*args, **kwargs):
        return ("System prompt text", 10)

    def mock_build_runtime_block(*args, **kwargs):
        return "Runtime text block"

    monkeypatch.setattr(
        "shibaclaw.webui.api._build_real_system_prompt", mock_build_real_system_prompt
    )
    monkeypatch.setattr(
        "shibaclaw.agent.context.ScentBuilder.build_runtime_block", mock_build_runtime_block
    )

    response = await api_context_get(request)
    assert response.status_code == 200

    import json

    data = json.loads(response.body)
    assert len(data) > 0
