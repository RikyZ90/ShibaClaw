import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
with patch("shibaclaw.webui.server._auth_enabled", return_value=False):
    from shibaclaw.webui.server import create_app
    app = create_app()

@pytest.fixture
def workspace_dir(tmp_path):
    mem_dir = tmp_path / "memory" / "knowledge"
    mem_dir.mkdir(parents=True)
    return tmp_path

@pytest.fixture
def mock_agent_manager(workspace_dir):
    from shibaclaw.webui.agent_manager import agent_manager
    from unittest.mock import MagicMock
    agent_manager.config = MagicMock()
    agent_manager.config.workspace_path = workspace_dir
    yield agent_manager

@pytest.mark.asyncio
async def test_knowledge_api_create_list(mock_agent_manager):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create
        res = await client.post("/api/knowledge", json={"id": "col1", "name": "Collection 1"})
        assert res.status_code == 201
        
        # List
        res = await client.get("/api/knowledge")
        assert res.status_code == 200
        data = res.json()
        assert "collections" in data
        assert len(data["collections"]) == 1
        assert data["collections"][0]["id"] == "col1"
