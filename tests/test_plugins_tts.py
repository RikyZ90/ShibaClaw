from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient

from shibaclaw.config.schema import Config
from shibaclaw.tts.base import BaseTTS
from shibaclaw.tts.registry import discover_tts_plugins
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.server import create_app

class DummyTTS(BaseTTS):
    name = "dummy"
    display_name = "Dummy TTS"
    async def synthesize(self, text: str, output_path):
        return output_path

@pytest.fixture
def mock_config(tmp_path):
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    config.audio.tts_provider = "dummy"

    class DummyProvider:
        pass

    with patch("shibaclaw.webui.auth._auth_enabled", return_value=False):
        yield config, DummyProvider()

@pytest.fixture
def client(mock_config):
    config, provider = mock_config
    agent_manager.config = config
    agent_manager.provider = provider
    app = create_app(config=config, provider=provider)
    return TestClient(app)

def test_discover_tts_plugins():
    mock_ep = MagicMock()
    mock_ep.name = "dummy"
    mock_ep.load.return_value = DummyTTS

    with patch("shibaclaw.tts.registry.entry_points", return_value=[mock_ep]):
        plugins = discover_tts_plugins()
        assert "dummy" in plugins
        assert plugins["dummy"] == DummyTTS

def test_api_list_plugins(client):
    mock_ep = MagicMock()
    mock_ep.name = "dummy"
    mock_ep.load.return_value = DummyTTS

    with patch("shibaclaw.tts.registry.entry_points", return_value=[mock_ep]):
        response = client.get("/api/plugins")
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data
        assert "available" in data
        assert len(data["available"]) > 0

def test_api_install_plugin_validation(client):
    response = client.post("/api/plugins/install", json={"package": "invalid-name"})
    assert response.status_code == 400
    assert "official" in response.json()["error"]

    response = client.post("/api/plugins/install", json={})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_api_install_plugin_success(client):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Successfully installed", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("shibaclaw.webui.routers.system._schedule_restart_outside_loop") as mock_schedule, \
         patch("shibaclaw.webui.routers.system._graceful_shutdown_server") as mock_shutdown:
        response = client.post("/api/plugins/install", json={"package": "shibaclaw-tts-supertonic"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["restarting"] is True
        mock_exec.assert_called_once()

def test_api_uninstall_plugin_validation(client):
    response = client.post("/api/plugins/uninstall", json={"package": "invalid-name"})
    assert response.status_code == 400

    response = client.post("/api/plugins/uninstall", json={})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_api_uninstall_plugin_success(client):
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Successfully uninstalled", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("shibaclaw.webui.routers.system._schedule_restart_outside_loop") as mock_schedule, \
         patch("shibaclaw.webui.routers.system._graceful_shutdown_server") as mock_shutdown:
        response = client.post("/api/plugins/uninstall", json={"package": "shibaclaw-tts-supertonic"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["restarting"] is True
        mock_exec.assert_called_once()
