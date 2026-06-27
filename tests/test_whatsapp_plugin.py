from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.server import create_app


@pytest.fixture
def mock_config(tmp_path):
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    with patch("shibaclaw.webui.auth._auth_enabled", return_value=False):
        yield config, object()


@pytest.fixture
def client(mock_config):
    config, provider = mock_config
    agent_manager.config = config
    agent_manager.provider = provider
    app = create_app(config=config, provider=provider)
    return TestClient(app)


def test_whatsapp_default_config():
    from shibaclaw_channel_whatsapp.channel import WhatsAppChannel, WhatsAppConfig
    cfg = WhatsAppChannel.default_config()
    assert cfg["bridgeUrl"] == "ws://localhost:3001"
    assert cfg["enabled"] is False
    assert "allowFrom" in cfg


def test_whatsapp_config_validation():
    from shibaclaw_channel_whatsapp.channel import WhatsAppConfig
    cfg = WhatsAppConfig.model_validate({
        "enabled": True,
        "bridgeUrl": "ws://localhost:3001",
        "bridgeToken": "secret",
        "allowFrom": ["*"],
    })
    assert cfg.enabled is True
    assert cfg.bridge_url == "ws://localhost:3001"
    assert cfg.bridge_token == "secret"
    assert cfg.allow_from == ["*"]


def test_whatsapp_not_in_builtin_registry():
    from shibaclaw.integrations.registry import discover_channel_names
    channels = discover_channel_names()
    assert "whatsapp" not in channels


def test_api_plugins_list_includes_whatsapp_available(client):
    with patch("shibaclaw.webui.routers.plugins.discover_plugins", return_value={}), \
         patch("shibaclaw.webui.routers.plugins.discover_tts_plugins", return_value={}):
        response = client.get("/api/plugins")
    assert response.status_code == 200
    data = response.json()
    available_names = [p["name"] for p in data["available"]]
    assert "shibaclaw-channel-whatsapp" in available_names


def test_api_plugins_list_whatsapp_installed_not_in_available(client):
    from shibaclaw_channel_whatsapp.channel import WhatsAppChannel
    mock_installed = {"whatsapp": WhatsAppChannel}

    with patch("shibaclaw.webui.routers.plugins.discover_plugins", return_value=mock_installed), \
         patch("shibaclaw.webui.routers.plugins.discover_tts_plugins", return_value={}):
        response = client.get("/api/plugins")
    assert response.status_code == 200
    data = response.json()
    available_names = [p["name"] for p in data["available"]]
    installed_names = [p["name"] for p in data["plugins"]]
    assert "shibaclaw-channel-whatsapp" not in available_names
    assert "whatsapp" in installed_names


@pytest.mark.asyncio
async def test_api_install_whatsapp_plugin(client):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Successfully installed", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("shibaclaw.webui.routers.system._schedule_restart_outside_loop"), \
         patch("shibaclaw.webui.routers.system._graceful_shutdown_server"):
        response = client.post("/api/plugins/install", json={"package": "shibaclaw-channel-whatsapp"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["restarting"] is True


@pytest.mark.asyncio
async def test_api_uninstall_whatsapp_plugin(client):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Successfully uninstalled", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("shibaclaw.webui.routers.system._schedule_restart_outside_loop"), \
         patch("shibaclaw.webui.routers.system._graceful_shutdown_server"):
        response = client.post("/api/plugins/uninstall", json={"package": "shibaclaw-channel-whatsapp"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["restarting"] is True
