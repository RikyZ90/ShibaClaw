from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from shibaclaw.config.schema import Config
from shibaclaw.helpers.notification_manager import notification_manager
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


@pytest.fixture(autouse=True)
def clear_notifications():
    notification_manager.delete()
    yield
    notification_manager.delete()


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


def test_api_update_check_returns_normalized_payload(client):
    payload = {
        "install_method": "pip",
        "current": "0.3.7",
        "latest": "0.3.8",
        "display_current": "0.3.7",
        "display_latest": "0.3.8",
        "update_available": True,
        "action_kind": "automatic",
        "action_label": "Update now",
        "action_command": "pip install --upgrade shibaclaw",
        "action_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "release_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "download_url": None,
        "manifest_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/update_manifest.json",
        "notification": {"category": "update", "text": "update available"},
        "checked_at": 123,
        "error": None,
        "stale": False,
        "summary": "Version 0.3.8 is available on PyPI.",
        "notes": [],
    }

    with patch("shibaclaw.updater.checker.check_for_update", return_value=payload):
        response = client.get("/api/update/check")

    assert response.status_code == 200
    data = response.json()
    assert data["install_method"] == "pip"
    assert data["action_kind"] == "automatic"
    assert data["notification"]["category"] == "update"


def test_api_update_apply_returns_manual_report_without_restart(client):
    report = {
        "install_method": "docker",
        "version": "0.3.8",
        "requires_manual_action": True,
        "restarting": False,
        "action_kind": "manual-command",
        "action_label": "Pull latest image",
        "action_command": "docker pull rikyz90/shibaclaw:latest",
        "action_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "message": "Manual update required.",
        "backup": {"moved": [], "skipped": []},
        "pip": None,
    }

    with patch("shibaclaw.updater.apply.apply_update", return_value=report):
        response = client.post(
            "/api/update/apply",
            json={"update": {"install_method": "docker", "action_kind": "manual-command"}},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["requires_manual_action"] is True
    assert data["restarting"] is False
    assert data["action_kind"] == "manual-command"


def test_api_notifications_create_list_and_mark_read(client):
    response = client.post(
        "/api/v1/notifications",
        json={
            "source": "agent_response",
            "kind": "agent_response",
            "title": "Agent response ready",
            "message": "The task is done.",
            "session_key": "webui:test-session",
            "action": {
                "kind": "session",
                "label": "Open session",
                "target": "webui:test-session",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    notification_id = payload["notification"]["id"]
    assert payload["unread_count"] == 1

    listed = client.get("/api/v1/notifications")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert len(listed_payload["notifications"]) == 1
    assert listed_payload["notifications"][0]["id"] == notification_id

    marked = client.post("/api/v1/notifications", json={"operation": "mark_read", "id": notification_id})
    assert marked.status_code == 200
    assert marked.json()["unread_count"] == 0


def test_api_notifications_delete_all(client):
    client.post(
        "/api/v1/notifications",
        json={
            "source": "update",
            "kind": "update",
            "title": "Update available",
            "message": "Version 0.3.8 is available.",
            "metadata": {"install_method": "pip", "latest": "0.3.8"},
        },
    )
    client.post(
        "/api/v1/notifications",
        json={
            "source": "heartbeat",
            "kind": "heartbeat",
            "title": "Heartbeat activity",
            "message": "Ping completed.",
        },
    )

    response = client.delete("/api/v1/notifications")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] == 2
    assert payload["total_count"] == 0
