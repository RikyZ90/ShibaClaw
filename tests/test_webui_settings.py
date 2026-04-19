import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from shibaclaw.config.loader import _migrate_config
from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.settings import api_settings_post


def _json_request(payload: dict) -> Request:
    body = json.dumps(payload).encode("utf-8")

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/settings",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
        },
        receive,
    )


@pytest.mark.asyncio
async def test_api_settings_post_replaces_deleted_mcp_servers(monkeypatch):
    import shibaclaw.cli.commands as commands_module
    import shibaclaw.config.loader as loader_module

    original_config = agent_manager.config
    original_provider = agent_manager.provider
    saved_configs = []

    async def fake_reset_agent():
        return None

    def fake_save_config(config, config_path=None):
        saved_configs.append(config)

    monkeypatch.setattr(
        agent_manager,
        "config",
        Config.model_validate(
            {
                "tools": {
                    "mcpServers": {
                        "keep": {"command": "python", "args": ["-m", "keep"]},
                        "delete": {"command": "python", "args": ["-m", "delete"]},
                    }
                }
            }
        ),
    )
    monkeypatch.setattr(agent_manager, "provider", None)
    monkeypatch.setattr(agent_manager, "reset_agent", fake_reset_agent)
    monkeypatch.setattr(loader_module, "save_config", fake_save_config)
    monkeypatch.setattr(commands_module, "_make_provider", lambda cfg, exit_on_error=False: SimpleNamespace())

    try:
        response = await api_settings_post(
            _json_request({"tools": {"mcpServers": {"keep": {"command": "python", "args": ["-m", "keep"]}}}})
        )

        assert response.status_code == 200
        assert set(agent_manager.config.tools.mcp_servers) == {"keep"}
        assert saved_configs
        assert set(saved_configs[-1].tools.mcp_servers) == {"keep"}
    finally:
        agent_manager.config = original_config
        agent_manager.provider = original_provider


def test_migrate_config_keeps_empty_mcp_servers_empty():
    migrated = _migrate_config({"channels": {}, "tools": {"mcpServers": {}}})

    assert migrated["tools"]["mcpServers"] == {}
