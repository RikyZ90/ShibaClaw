
import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.server import create_app


@pytest.fixture
def mock_config(tmp_path):
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    
    # Needs a dummy provider to ensure we don't err out during status check
    class DummyProvider:
        pass
        
    with patch("shibaclaw.webui.auth._auth_enabled", return_value=False):
        yield config, DummyProvider()


@pytest.fixture
def client(mock_config):
    config, provider = mock_config
    # Explicitly configure agent manager to avoid loading from disk in tests
    agent_manager.config = config
    agent_manager.provider = provider
    app = create_app(config=config, provider=provider)
    return TestClient(app)


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_api_auth_status(client):
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert "auth_required" in data


def test_api_auth_verify(client):
    response = client.post("/api/auth/verify", json={"token": "test"})
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "auth_required" in data


def test_api_settings_get(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "providers" in data


def test_api_sessions_list(client):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_api_context_summary(client):
    response = client.get("/api/context?summary=true")
    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data
    assert "system_prompt" in data["tokens"]


def test_api_gateway_health(client):
    response = client.get("/api/gateway-health")
    assert response.status_code == 200
    data = response.json()
    assert "reachable" in data


def test_api_cron_list(client):
    response = client.get("/api/cron/jobs")
    # Will likely return 503 since gateway is not mocked
    assert response.status_code in (200, 503)
    data = response.json()
    if response.status_code == 200:
        assert "jobs" in data
    else:
        assert "error" in data


def test_api_heartbeat_status(client):
    response = client.get("/api/heartbeat/status")
    # Will likely return 200 with unreachable=False if gateway isn't reached
    assert response.status_code == 200
    data = response.json()
    assert "reachable" in data


def test_api_skills_list(client):
    response = client.get("/api/skills")
    assert response.status_code == 200
    data = response.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)


def test_api_profiles_list(client):
    response = client.get("/api/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    assert isinstance(data["profiles"], list)
