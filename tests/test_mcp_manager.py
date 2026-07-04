"""Tests for MCP Manager and OAuth routes."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

# ── minimal app fixture ────────────────────────────────────────────────────────

def _make_cfg(servers: dict | None = None) -> MagicMock:
    cfg = MagicMock()
    tools = MagicMock()
    tools.mcpServers = servers or {}
    tools.model_extra = {}
    cfg.tools = tools
    cfg.model_dump.return_value = {
        "tools": {"mcpServers": servers or {}}
    }
    return cfg


@pytest.fixture
def app():
    """Build a minimal Starlette test app with all MCP routes."""
    from starlette.applications import Starlette
    from starlette.routing import Route
    from shibaclaw.webui.routers.mcp_manager import (
        list_mcp_servers, get_mcp_server, upsert_mcp_server, delete_mcp_server,
        rename_mcp_server, test_mcp_server, oauth_manual_store, oauth_manual_clear,
    )
    from shibaclaw.webui.routers.mcp_oauth import (
        oauth_start, oauth_callback, oauth_status,
    )
    routes = [
        Route("/api/mcp/servers", list_mcp_servers, methods=["GET"]),
        Route("/api/mcp/servers/{name}", get_mcp_server, methods=["GET"]),
        Route("/api/mcp/servers/{name}", upsert_mcp_server, methods=["PUT"]),
        Route("/api/mcp/servers/{name}", delete_mcp_server, methods=["DELETE"]),
        Route("/api/mcp/servers/{name}/rename", rename_mcp_server, methods=["PATCH"]),
        Route("/api/mcp/servers/{name}/test", test_mcp_server, methods=["POST"]),
        Route("/api/mcp/servers/{name}/oauth", oauth_manual_store, methods=["POST"]),
        Route("/api/mcp/servers/{name}/oauth", oauth_manual_clear, methods=["DELETE"]),
        Route("/api/mcp/servers/{name}/oauth/start", oauth_start, methods=["POST"]),
        Route("/api/mcp/oauth/callback", oauth_callback, methods=["GET"]),
        Route("/api/mcp/oauth/status", oauth_status, methods=["GET"]),
    ]
    return Starlette(routes=routes)


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def mock_agent(monkeypatch):
    """Patch agent_manager for all tests."""
    cfg = _make_cfg()
    am = MagicMock()
    am.config = cfg
    am.save_config = MagicMock()
    monkeypatch.setattr("shibaclaw.webui.routers.mcp_manager.agent_manager", am)
    monkeypatch.setattr("shibaclaw.webui.routers.mcp_oauth.agent_manager", am)
    return am


# ── list ───────────────────────────────────────────────────────────────────────

class TestListMcpServers:
    def test_empty(self, client, mock_agent):
        mock_agent.config = _make_cfg({})
        r = client.get("/api/mcp/servers")
        assert r.status_code == 200
        assert r.json()["servers"] == []

    def test_with_servers(self, client, mock_agent):
        mock_agent.config = _make_cfg({"my-srv": {"url": "http://x", "type": "sse"}})
        r = client.get("/api/mcp/servers")
        assert r.status_code == 200
        servers = r.json()["servers"]
        assert len(servers) == 1
        assert servers[0]["_name"] == "my-srv"


# ── get ────────────────────────────────────────────────────────────────────────

class TestGetMcpServer:
    def test_found(self, client, mock_agent):
        mock_agent.config = _make_cfg({"s1": {"url": "http://a"}})
        r = client.get("/api/mcp/servers/s1")
        assert r.status_code == 200
        assert r.json()["server"]["_name"] == "s1"

    def test_not_found(self, client, mock_agent):
        mock_agent.config = _make_cfg({})
        r = client.get("/api/mcp/servers/nope")
        assert r.status_code == 404


# ── upsert ─────────────────────────────────────────────────────────────────────

class TestUpsertMcpServer:
    def test_valid(self, client, mock_agent):
        mock_agent.config = _make_cfg({})
        r = client.put("/api/mcp/servers/new-srv", json={"url": "http://x"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        mock_agent.save_config.assert_called_once()

    def test_invalid_json(self, client):
        r = client.put("/api/mcp/servers/bad", content=b"{not json}", headers={"Content-Type": "application/json"})
        assert r.status_code == 400


# ── delete ─────────────────────────────────────────────────────────────────────

class TestDeleteMcpServer:
    def test_found(self, client, mock_agent):
        mock_agent.config = _make_cfg({"srv": {"url": "http://x"}})
        r = client.delete("/api/mcp/servers/srv")
        assert r.status_code == 200

    def test_not_found(self, client, mock_agent):
        mock_agent.config = _make_cfg({})
        r = client.delete("/api/mcp/servers/ghost")
        assert r.status_code == 404


# ── rename ─────────────────────────────────────────────────────────────────────

class TestRenameMcpServer:
    def test_valid(self, client, mock_agent):
        mock_agent.config = _make_cfg({"old": {"url": "http://x"}})
        r = client.patch("/api/mcp/servers/old/rename", json={"new_name": "new"})
        assert r.status_code == 200
        assert r.json()["new_name"] == "new"

    def test_missing_new_name(self, client, mock_agent):
        mock_agent.config = _make_cfg({"old": {}})
        r = client.patch("/api/mcp/servers/old/rename", json={})
        assert r.status_code == 400

    def test_conflict_409(self, client, mock_agent):
        mock_agent.config = _make_cfg({"a": {}, "b": {}})
        r = client.patch("/api/mcp/servers/a/rename", json={"new_name": "b"})
        assert r.status_code == 409


# ── manual oauth ───────────────────────────────────────────────────────────────

class TestOauthManual:
    def test_store(self, client, mock_agent):
        mock_agent.config = _make_cfg({"srv": {"url": "http://x"}})
        r = client.post("/api/mcp/servers/srv/oauth", json={"access_token": "tok123"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_store_missing_token(self, client, mock_agent):
        mock_agent.config = _make_cfg({"srv": {"url": "http://x"}})
        r = client.post("/api/mcp/servers/srv/oauth", json={})
        assert r.status_code == 400

    def test_clear(self, client, mock_agent):
        mock_agent.config = _make_cfg({"srv": {"url": "http://x", "oauth": {"access_token": "t"}}})
        r = client.delete("/api/mcp/servers/srv/oauth")
        assert r.status_code == 200


# ── _build_headers ─────────────────────────────────────────────────────────────

class TestBuildHeaders:
    def test_with_oauth(self):
        from shibaclaw.webui.routers.mcp_manager import _build_headers
        sc = {"oauth": {"access_token": "mytoken"}}
        h = _build_headers(sc)
        assert h["Authorization"] == "Bearer mytoken"

    def test_empty(self):
        from shibaclaw.webui.routers.mcp_manager import _build_headers
        h = _build_headers({})
        assert "Authorization" not in h

    def test_direct_headers(self):
        from shibaclaw.webui.routers.mcp_manager import _build_headers
        sc = {"headers": {"X-Custom": "value"}}
        h = _build_headers(sc)
        assert h["X-Custom"] == "value"


# ── oauth start ────────────────────────────────────────────────────────────────

class TestOauthStart:
    def test_server_not_found(self, client, mock_agent):
        mock_agent.config = _make_cfg({})
        r = client.post("/api/mcp/servers/ghost/oauth/start")
        assert r.status_code == 404

    def test_no_url(self, client, mock_agent):
        mock_agent.config = _make_cfg({"srv": {"command": "npx"}})
        r = client.post("/api/mcp/servers/srv/oauth/start")
        assert r.status_code == 400


# ── oauth status ───────────────────────────────────────────────────────────────

class TestOauthStatus:
    def test_pending(self, client):
        from shibaclaw.webui.routers.mcp_oauth import _PENDING_OAUTH
        _PENDING_OAUTH["st123"] = {"created_at": time.time(), "server_name": "x",
                                   "code_verifier": "v", "client_id": "c",
                                   "token_endpoint": "http://t", "redirect_uri": "http://r"}
        r = client.get("/api/mcp/oauth/status?state=st123")
        assert r.status_code == 200
        assert r.json()["completed"] is False
        _PENDING_OAUTH.pop("st123", None)

    def test_completed(self, client):
        from shibaclaw.webui.routers.mcp_oauth import _PENDING_OAUTH
        _PENDING_OAUTH.pop("nonexistent", None)
        r = client.get("/api/mcp/oauth/status?state=nonexistent")
        assert r.status_code == 200
        assert r.json()["completed"] is True

    def test_missing_state(self, client):
        r = client.get("/api/mcp/oauth/status")
        assert r.status_code == 400


# ── oauth callback ─────────────────────────────────────────────────────────────

class TestOauthCallback:
    def test_missing_params(self, client):
        r = client.get("/api/mcp/oauth/callback", follow_redirects=False)
        assert r.status_code == 307
        assert "missing_params" in r.headers["location"]

    def test_invalid_state(self, client):
        r = client.get("/api/mcp/oauth/callback?code=abc&state=bad_state", follow_redirects=False)
        assert r.status_code == 307
        assert "invalid_state" in r.headers["location"]

    def test_error_param(self, client):
        r = client.get("/api/mcp/oauth/callback?error=access_denied", follow_redirects=False)
        assert r.status_code == 307
        assert "access_denied" in r.headers["location"]


# ── PKCE ───────────────────────────────────────────────────────────────────────

class TestPkce:
    def test_generate(self):
        import base64
        import hashlib
        from shibaclaw.webui.routers.mcp_oauth import _generate_pkce
        verifier, challenge = _generate_pkce()
        assert len(verifier) == 128
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        assert challenge == expected
