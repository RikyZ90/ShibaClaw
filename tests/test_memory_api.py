import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from shibaclaw.webui.server import create_app

app = create_app()

@pytest.fixture(autouse=True)
def disable_auth():
    with patch("shibaclaw.webui.auth._auth_enabled", return_value=False):
        yield

@pytest.fixture
def workspace_dir(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(parents=True)
    return tmp_path

@pytest.fixture
def mock_agent_manager(workspace_dir):
    from shibaclaw.webui.agent_manager import agent_manager
    agent_manager.config = MagicMock()
    agent_manager.config.workspace_path = workspace_dir
    yield agent_manager

@pytest.mark.asyncio
async def test_memory_api_get_and_save(mock_agent_manager, workspace_dir):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Initial GET
        res = await client.get("/api/memory")
        assert res.status_code == 200
        data = res.json()
        assert "memory" in data
        assert "user" in data
        assert "tokens" in data

        # Save MEMORY.md
        res = await client.post("/api/memory/save", json={
            "file": "MEMORY.md",
            "content": "## Environment\n- OS: Linux\n- Fact: SecretProject"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "saved"
        assert (workspace_dir / "memory" / "MEMORY.md").read_text(encoding="utf-8") == "## Environment\n- OS: Linux\n- Fact: SecretProject"

        # Save USER.md
        res = await client.post("/api/memory/save", json={
            "file": "USER.md",
            "content": "User prefers concise Python."
        })
        assert res.status_code == 200
        assert (workspace_dir / "USER.md").read_text(encoding="utf-8") == "User prefers concise Python."

        # Invalid file name
        res = await client.post("/api/memory/save", json={
            "file": "HACK.txt",
            "content": "invalid"
        })
        assert res.status_code == 400

@pytest.mark.asyncio
async def test_memory_api_forget(mock_agent_manager, workspace_dir):
    mem_file = workspace_dir / "memory" / "MEMORY.md"
    mem_file.write_text("## Environment\n- User secret token is 12345\n- Safe line here\n", encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Preview forget
        res = await client.post("/api/memory/forget", json={
            "needle": "12345",
            "confirm": False
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("preview") is True
        assert data.get("counts", {}).get("MEMORY.md") == 1
        # File should remain unchanged on preview
        assert "12345" in mem_file.read_text(encoding="utf-8")

        # Confirm forget
        res = await client.post("/api/memory/forget", json={
            "needle": "12345",
            "confirm": True
        })
        assert res.status_code == 200
        data = res.json()
        assert data.get("preview") is False
        assert data.get("MEMORY.md") == 1

        # Matching line should be gone and safe line preserved
        text = mem_file.read_text(encoding="utf-8")
        assert "12345" not in text
        assert "Safe line here" in text

        # Quarantine directory should contain forget archive
        qdir = workspace_dir / "memory" / "quarantine"
        assert qdir.exists()
        assert len(list(qdir.glob("*.md"))) == 1
