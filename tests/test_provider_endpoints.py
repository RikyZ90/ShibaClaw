"""Independent provider instances keep catalogs, routing and credentials isolated."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError
from starlette.requests import Request

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.cli.base import _make_provider
from shibaclaw.config.schema import Config
from shibaclaw.helpers.model_ids import canonicalize_model_id, configured_provider_names, raw_model_id, split_model_id
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers import settings


ENDPOINT = "endpoint_12345678-abcd"
OTHER_ENDPOINT = "endpoint_87654321-abcd"


class FakeVault:
    def __init__(self):
        self.secrets = {}

    def is_setup(self):
        return True

    def get_secret(self, namespace, key):
        return self.secrets.get((namespace, key))

    def set_secret(self, namespace, key, value):
        self.secrets[namespace, key] = value

    def delete_secret(self, namespace, key):
        self.secrets.pop((namespace, key), None)


@pytest.fixture(autouse=True)
def isolated_providers(monkeypatch):
    from shibaclaw.thinkers.registry import PROVIDERS

    for spec in PROVIDERS:
        if spec.env_key:
            monkeypatch.delenv(spec.env_key, raising=False)
    monkeypatch.setattr("shibaclaw.cli.auth._is_oauth_authenticated", lambda spec: False)
    vault = FakeVault()
    monkeypatch.setattr("shibaclaw.security.credential_manager.get_credential_manager", lambda: vault)
    monkeypatch.setattr("shibaclaw.config.history.append_config_history", lambda **kwargs: None)
    monkeypatch.setattr(settings, "_models_cache", None)
    return vault


def _config(**endpoint):
    return Config.model_validate({
        "agents": {"defaults": {"model": f"{ENDPOINT}/org/model"}},
        "providerEndpoints": {ENDPOINT: {"provider": "custom", "name": "Local", "apiBase": "http://localhost:1234/v1", **endpoint}},
    })


def _request(payload=None, *, query=""):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload or {}).encode(), "more_body": False}

    return Request({
        "type": "http", "method": "POST" if payload is not None else "GET",
        "path": "/api/settings", "headers": [], "query_string": query.encode(),
    }, receive)


def test_endpoint_ids_preserve_nested_model_names_and_uuid_hyphens():
    cfg = _config()
    assert split_model_id(f"{ENDPOINT}/openai/org/model") == (ENDPOINT, "openai/org/model")
    assert raw_model_id(f"{ENDPOINT}/openai/org/model") == "openai/org/model"
    assert split_model_id("organization/model") == (None, "organization/model")
    assert canonicalize_model_id(cfg, "another/model") == f"{ENDPOINT}/another/model"
    assert cfg.get_provider_name(f"{ENDPOINT}/org/model") == ENDPOINT
    assert settings._canonical_model_id(ENDPOINT, f"{ENDPOINT}/raw") == f"{ENDPOINT}/{ENDPOINT}/raw"


@pytest.mark.parametrize("provider", ["custom", "openai", "openrouter", "xai"])
def test_endpoint_factory_uses_only_its_own_key_base_headers_and_model(isolated_providers, monkeypatch, provider):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-environment-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unrelated-gateway-key")
    cfg = _config(provider=provider, extraHeaders={"X-Endpoint": "chosen"})
    cfg.agents.defaults.provider = "openai"
    thinker = _make_provider(cfg, exit_on_error=False)

    assert str(thinker._client.base_url) == "http://localhost:1234/v1/"
    assert thinker._client.api_key == "no-key"
    assert thinker._client.default_headers["X-Endpoint"] == "chosen"
    assert thinker._resolve_model(f"{ENDPOINT}/openai/org/model") == "openai/org/model"

    isolated_providers.set_secret("providers", f"{ENDPOINT}.api_key", "endpoint-secret")
    second = _make_provider(cfg, exit_on_error=False)
    assert second._client.api_key == "endpoint-secret"


@pytest.mark.parametrize("provider", ["custom", "openai", "ollama", "azure_openai"])
def test_legacy_base_only_provider_remains_configured_without_key(provider):
    cfg = Config.model_validate({
        "agents": {"defaults": {"model": f"{provider}/org/model"}},
        "providers": {provider: {"apiBase": "http://localhost:1234/v1"}},
    })
    assert provider in configured_provider_names(cfg)
    assert _make_provider(cfg, exit_on_error=False) is not None


@pytest.mark.parametrize("provider", ["anthropic", "xai"])
def test_legacy_api_key_does_not_require_oauth_login(isolated_providers, provider):
    isolated_providers.set_secret("providers", f"{provider}.api_key", "api-secret")
    cfg = Config.model_validate({"agents": {"defaults": {"model": f"{provider}/model"}}})
    assert provider in configured_provider_names(cfg)
    assert _make_provider(cfg, exit_on_error=False) is not None


@pytest.mark.asyncio
async def test_anthropic_endpoint_preserves_native_protocol_and_raw_model():
    cfg = _config(provider="anthropic", apiKey="native-key")
    thinker = _make_provider(cfg, exit_on_error=False)
    thinker._client.messages.create = AsyncMock(return_value=type("Response", (), {"content": [], "stop_reason": "end_turn", "usage": None})())
    await thinker.chat([{"role": "user", "content": "Hello"}], model=f"{ENDPOINT}/anthropic/raw-model")
    assert thinker._client.messages.create.await_args.kwargs["model"] == "anthropic/raw-model"
    assert thinker._client.api_key == "native-key"


@pytest.mark.parametrize("state", ["disabled", "deleted"])
@pytest.mark.parametrize("same_as_default", [False, True])
@pytest.mark.parametrize("padding", ["", " "])
def test_explicit_unavailable_endpoint_never_falls_back(state, same_as_default, padding):
    cfg = _config(enabled=False)
    cfg.agents.defaults.model = f"{padding}{cfg.agents.defaults.model}{padding}"
    if state == "deleted":
        cfg.provider_endpoints.clear()
    cfg.providers.openai.api_base = "http://fallback:1234/v1"
    assert _make_provider(cfg, exit_on_error=False) is None

    brain = object.__new__(ShibaBrain)
    brain.config = cfg
    brain.model = cfg.agents.defaults.model if same_as_default else "openai/default"
    brain.provider = object()
    brain._provider_cache = {ENDPOINT: object()}
    assert brain._resolve_provider_for_model(f"{padding}{ENDPOINT}/org/model{padding}") is None


def test_disabled_legacy_provider_is_neither_advertised_nor_used():
    cfg = Config.model_validate({
        "agents": {"defaults": {"model": "custom/model"}},
        "providers": {"custom": {"enabled": False, "apiBase": "http://disabled/v1"}, "openai": {"apiBase": "http://fallback/v1"}},
    })
    assert "custom" not in configured_provider_names(cfg)
    assert _make_provider(cfg, exit_on_error=False) is None


@pytest.mark.parametrize("data", [
    {"bad-id": {"provider": "custom"}},
    {ENDPOINT: {"provider": "unknown"}},
    {ENDPOINT: {"provider": "github_copilot"}},
])
def test_endpoint_configuration_rejects_unroutable_types_and_ids(data):
    with pytest.raises(ValidationError):
        Config.model_validate({"providerEndpoints": data})


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoints", [
    {"invalid-id": {"apiKey": "private-input-secret"}},
    {ENDPOINT: {"apiKey": "private-input-secret", "provider": "unknown"}},
])
async def test_invalid_endpoint_settings_do_not_disclose_key(monkeypatch, endpoints):
    monkeypatch.setattr(agent_manager, "config", _config())
    messages = []
    monkeypatch.setattr(settings.logger, "error", lambda message, *args: messages.append(message.format(*args)))
    response = await settings.api_settings_post(_request({"providerEndpoints": endpoints}))
    assert response.status_code == 422
    assert "private-input-secret" not in response.body.decode()
    assert all("private-input-secret" not in message for message in messages)


@pytest.mark.asyncio
async def test_model_catalog_keeps_duplicate_names_and_empty_sources(monkeypatch):
    cfg = _config()
    cfg.provider_endpoints[OTHER_ENDPOINT] = cfg.provider_endpoints[ENDPOINT].model_copy(update={"api_base": "http://localhost:5678/v1"})
    cfg.provider_endpoints["endpoint_hidden"] = cfg.provider_endpoints[ENDPOINT].model_copy(update={"enabled": False})
    cfg.providers.openai.api_base = "http://legacy/v1"
    cfg.providers.openai.name = "Legacy"
    fetched = []

    class Catalog:
        def __init__(self, provider_id):
            self.provider_id = provider_id

        async def get_available_models(self):
            fetched.append(self.provider_id)
            return [] if self.provider_id == "openai" else [{"id": "org/model"}]

    monkeypatch.setattr(agent_manager, "config", cfg)
    monkeypatch.setattr("shibaclaw.cli.base._make_provider", lambda temp_cfg, exit_on_error=False: Catalog(temp_cfg.agents.defaults.provider))
    response = await settings.api_models_get(_request())
    payload = json.loads(response.body)
    assert set(fetched) == {ENDPOINT, OTHER_ENDPOINT, "openai"}
    assert {model["id"] for model in payload["models"]} == {f"{ENDPOINT}/org/model", f"{OTHER_ENDPOINT}/org/model"}
    assert {model["provider_label"] for model in payload["models"]} == {"Local"}
    assert payload["providers"] == [
        {"id": "openai", "name": "Legacy", "api_base": "http://legacy/v1", "provider": "openai"},
        {"id": ENDPOINT, "name": "Local", "api_base": "http://localhost:1234/v1", "provider": "custom"},
        {"id": OTHER_ENDPOINT, "name": "Local", "api_base": "http://localhost:5678/v1", "provider": "custom"},
    ]
    response = await settings.api_models_get(_request(query=f"provider={OTHER_ENDPOINT}"))
    assert json.loads(response.body)["models"][0]["provider"] == OTHER_ENDPOINT


@pytest.mark.asyncio
async def test_endpoint_secret_settings_roundtrip_clear_and_delete(isolated_providers, monkeypatch, tmp_path):
    cfg = _config()
    cfg.provider_endpoints[OTHER_ENDPOINT] = cfg.provider_endpoints[ENDPOINT].model_copy()
    monkeypatch.setattr(agent_manager, "config", cfg)
    monkeypatch.setattr(agent_manager, "reload_config", AsyncMock())
    path = tmp_path / "config.json"
    monkeypatch.setattr("shibaclaw.config.loader.get_config_path", lambda: path)
    monkeypatch.setattr("shibaclaw.config.loader._get_cm_if_active", lambda: isolated_providers)

    response = await settings.api_settings_post(_request({"providerEndpoints": {ENDPOINT: {"apiKey": "private-endpoint-key"}}}))
    assert response.status_code == 200
    assert set(agent_manager.config.provider_endpoints) == {ENDPOINT}
    assert "private-endpoint-key" not in path.read_text()
    assert agent_manager.config.provider_endpoints[ENDPOINT].api_key == ""
    assert isolated_providers.get_secret("providers", f"{ENDPOINT}.api_key") == "private-endpoint-key"

    response = await settings.api_settings_get(_request())
    endpoint = json.loads(response.body)["providerEndpoints"][ENDPOINT]
    assert endpoint["apiKey"] == "****"
    endpoint["enabled"] = False
    response = await settings.api_settings_post(_request({"providerEndpoints": {ENDPOINT: endpoint}}))
    assert response.status_code == 200
    assert isolated_providers.get_secret("providers", f"{ENDPOINT}.api_key") == "private-endpoint-key"

    response = await settings.api_settings_post(_request({"providerEndpoints": {ENDPOINT: {"apiKey": "", "enabled": True}}}))
    assert response.status_code == 200
    assert agent_manager.config.provider_endpoints[ENDPOINT].resolve_api_key(ENDPOINT) == ""
    assert isolated_providers.get_secret("providers", f"{ENDPOINT}.api_key") is None

    response = await settings.api_settings_post(_request({"providerEndpoints": {}}))
    assert response.status_code == 200
    assert agent_manager.config.provider_endpoints == {}


@pytest.mark.asyncio
async def test_endpoint_keys_survive_without_vault(isolated_providers, monkeypatch, tmp_path):
    from shibaclaw.config import loader

    monkeypatch.setattr(agent_manager, "config", _config())
    monkeypatch.setattr(agent_manager, "reload_config", AsyncMock())
    monkeypatch.setattr(loader, "_get_cm_if_active", lambda: None)
    monkeypatch.setattr(isolated_providers, "is_setup", lambda: False)
    monkeypatch.setattr(loader, "_plugins_onboarded", True)
    path = tmp_path / "config.json"
    monkeypatch.setattr(loader, "get_config_path", lambda: path)
    response = await settings.api_settings_post(_request({"providerEndpoints": {ENDPOINT: {"apiKey": "only-copy-of-key"}}}))
    assert response.status_code == 200
    reloaded = loader.load_config(path)
    assert reloaded.provider_endpoints[ENDPOINT].resolve_api_key(ENDPOINT) == "only-copy-of-key"
    second_path = tmp_path / "saved.json"
    loader.save_config(reloaded, second_path)
    assert json.loads(second_path.read_text())["providerEndpoints"][ENDPOINT]["apiKey"] == "only-copy-of-key"
    response = await settings.api_settings_get(_request())
    assert "only-copy-of-key" not in response.body.decode()


def test_save_and_load_endpoint_key_migrate_to_vault(isolated_providers, monkeypatch, tmp_path):
    from shibaclaw.config import loader

    monkeypatch.setattr(loader, "_get_cm_if_active", lambda: isolated_providers)
    monkeypatch.setattr(loader, "_plugins_onboarded", True)
    path = tmp_path / "config.json"
    cfg = _config(apiKey="constructed-secret")
    loader.save_config(cfg, path)
    assert "constructed-secret" not in path.read_text()
    assert isolated_providers.get_secret("providers", f"{ENDPOINT}.api_key") == "constructed-secret"
    loaded = loader.load_config(path)
    assert loaded.provider_endpoints[ENDPOINT].resolve_api_key(ENDPOINT) == "constructed-secret"
    assert loaded.provider_endpoints[ENDPOINT].api_key == ""


@pytest.mark.asyncio
async def test_endpoint_request_sends_only_routing_prefix_stripped():
    from openai import AsyncOpenAI

    thinker = _make_provider(_config(), exit_on_error=False)
    requests = []

    async def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "completion", "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        async with AsyncOpenAI(api_key="no-key", base_url="http://endpoint/v1", http_client=client) as sdk:
            thinker._client = sdk
            await thinker.chat([{"role": "user", "content": "Hello"}], model=f"{ENDPOINT}/openai/org/model")
    assert requests[0]["model"] == "openai/org/model"
