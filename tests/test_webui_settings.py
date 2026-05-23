import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from shibaclaw.config.loader import _migrate_config
from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.settings import api_models_get, api_settings_post


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


def _get_request(path: str = "/api/models", query_string: str = "") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query_string.encode("utf-8"),
            "headers": [],
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


@pytest.mark.asyncio
async def test_api_models_get_aggregates_all_configured_providers(monkeypatch):
    import shibaclaw.cli.auth as auth_module
    import shibaclaw.cli.base as base_module

    original_config = agent_manager.config
    original_provider = agent_manager.provider

    class FakeProvider:
        def __init__(self, provider_name: str):
            self.provider_name = provider_name

        async def get_available_models(self):
            if self.provider_name == "openrouter":
                return [{"id": "google/gemma-4-31b-it", "name": "Gemma 4 31B"}]
            if self.provider_name == "github_copilot":
                return [{"id": "gpt-4.1", "name": "GPT-4.1"}]
            return []

    def fake_make_provider(cfg, exit_on_error=False):
        return FakeProvider(cfg.agents.defaults.provider)

    monkeypatch.setattr(
        agent_manager,
        "config",
        Config.model_validate(
            {
                "agents": {"defaults": {"model": "openrouter/google/gemma-4-31b-it"}},
                "providers": {
                    "openrouter": {"apiKey": "sk-or-test"},
                    "githubCopilot": {},
                },
            }
        ),
    )
    monkeypatch.setattr(agent_manager, "provider", None)
    monkeypatch.setattr(base_module, "_make_provider", fake_make_provider)
    monkeypatch.setattr(
        auth_module,
        "_is_oauth_authenticated",
        lambda spec: spec.name == "github_copilot",
    )

    try:
        response = await api_models_get(_get_request())
        payload = json.loads(response.body)

        assert response.status_code == 200
        assert payload["errors"] == []
        assert payload["models"] == [
            {
                "id": "openrouter/google/gemma-4-31b-it",
                "raw_id": "google/gemma-4-31b-it",
                "name": "Gemma 4 31B",
                "provider": "openrouter",
                "provider_label": "OpenRouter",
            },
            {
                "id": "github_copilot/gpt-4.1",
                "raw_id": "gpt-4.1",
                "name": "GPT-4.1",
                "provider": "github_copilot",
                "provider_label": "Github Copilot",
            },
        ]
    finally:
        agent_manager.config = original_config
        agent_manager.provider = original_provider
