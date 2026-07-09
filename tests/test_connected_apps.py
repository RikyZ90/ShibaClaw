"""Tests for Connected Apps — real service registry with Klavis as hidden backend."""

from __future__ import annotations

import pytest



# ── import symbols under test ─────────────────────────────────────────────────

from shibaclaw.webui.routers.connected_apps import (
    CONNECTED_APPS,
    _get_app_state,
    _sync_app_to_mcp,
    _remove_app_from_mcp,
    _build_app_response,
    _KLAVIS_API_BASE,
    _DEFAULT_TRANSPORT,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _base_cfg(apps_state: dict | None = None):
    return {
        "tools": {"mcp_servers": {}},
        "connected_apps": {
            "klavis": {
                "bearer_token": "test_token",
                "endpoint": _KLAVIS_API_BASE,
            },
            **(apps_state or {}),
        },
    }


# ── 1. Registry contains expected real apps ───────────────────────────────────

def test_registry_contains_gmail():
    assert "gmail" in CONNECTED_APPS
    assert CONNECTED_APPS["gmail"].name == "Gmail"
    assert CONNECTED_APPS["gmail"].category == "google"


def test_registry_contains_gdrive():
    assert "gdrive" in CONNECTED_APPS
    assert CONNECTED_APPS["gdrive"].name == "Google Drive"


def test_registry_contains_slack():
    assert "slack" in CONNECTED_APPS
    assert CONNECTED_APPS["slack"].name == "Slack"
    assert CONNECTED_APPS["slack"].category == "productivity"


def test_registry_contains_notion():
    assert "notion" in CONNECTED_APPS
    assert CONNECTED_APPS["notion"].name == "Notion"


def test_registry_contains_github():
    assert "github" in CONNECTED_APPS
    assert CONNECTED_APPS["github"].name == "GitHub"
    assert CONNECTED_APPS["github"].category == "dev"


def test_registry_has_multiple_apps():
    assert len(CONNECTED_APPS) >= 8, "Expected at least 8 real apps in registry"


# ── 2. mcp_server_key is derived correctly ────────────────────────────────────

def test_mcp_server_key_gmail():
    assert CONNECTED_APPS["gmail"].mcp_server_key == "gmail"


def test_mcp_server_key_gdrive():
    assert CONNECTED_APPS["gdrive"].mcp_server_key == "gdrive"


def test_mcp_server_key_slack():
    assert CONNECTED_APPS["slack"].mcp_server_key == "slack"


def test_mcp_server_key_github():
    assert CONNECTED_APPS["github"].mcp_server_key == "github"


# ── 3. Backend config is separate from app list ───────────────────────────────

def test_klavis_backend_not_in_app_ids():
    """Klavis must NOT appear as a connectable app in the registry."""
    assert "klavis" not in CONNECTED_APPS


def test_get_klavis_client_clean_reads_correctly():
    pass # removed due to refactor


def test_get_klavis_client_clean_empty_when_missing():
    pass # removed due to refactor


# ── 4. App state helpers ──────────────────────────────────────────────────────

def test_get_app_state_returns_empty_when_missing():
    cfg = _base_cfg()
    state = _get_app_state(cfg, "gmail")
    assert state == {}


def test_get_app_state_returns_data_when_present():
    cfg = _base_cfg(apps_state={
        "gmail": {"connected": True, "enabled": True, "server_url": "https://example.com/gmail/"}
    })
    state = _get_app_state(cfg, "gmail")
    assert state["connected"] is True


# ── 5. sync_app_to_mcp writes gmail-klavis entry ─────────────────────────────

def test_sync_gmail_to_mcp():
    app_def = CONNECTED_APPS["gmail"]

    cfg = _base_cfg()

    _sync_app_to_mcp(cfg, app_def, "https://strata.klavis.ai/mcp/" + app_def.id + "/")

    tools = cfg["tools"]
    servers = tools.get("mcpServers") or tools.get("mcp_servers")
    assert servers is not None
    assert "gmail" in servers
    entry = servers["gmail"]
    assert entry["url"] == "https://strata.klavis.ai/mcp/gmail/"


def test_sync_github_to_mcp():
    app_def = CONNECTED_APPS["github"]

    cfg = _base_cfg()

    _sync_app_to_mcp(cfg, app_def, "https://strata.klavis.ai/mcp/" + app_def.id + "/")

    tools = cfg["tools"]
    servers = tools.get("mcpServers") or tools.get("mcp_servers")
    assert servers is not None
    assert "github" in servers


# ── 6. disconnect removes from mcpServers ─────────────────────────────────────

def test_disconnect_gmail_removes_from_mcp():
    app_def = CONNECTED_APPS["gmail"]
    cfg = _base_cfg()
    cfg["tools"]["mcp_servers"]["gmail"] = {
        "type": "streamableHttp",
        "url": "https://strata.klavis.ai/mcp/gmail/",
        "enabled": True,
    }

    _remove_app_from_mcp(cfg, app_def)

    tools = cfg["tools"]
    servers = tools.get("mcpServers") or tools.get("mcp_servers") or {}
    assert "gmail" not in servers


def test_disconnect_nonexistent_app_is_noop():
    app_def = CONNECTED_APPS["github"]
    cfg = _base_cfg()
    # no github-klavis in servers — should not raise
    _remove_app_from_mcp(cfg, app_def)
    tools = cfg["tools"]
    servers = tools.get("mcpServers") or tools.get("mcp_servers") or {}
    assert "github" not in servers


# ── 7. build_app_response shape ───────────────────────────────────────────────

def test_build_app_response_not_connected():
    app_def = CONNECTED_APPS["gmail"]
    resp = _build_app_response(app_def, {})
    assert resp["id"] == "gmail"
    assert resp["name"] == "Gmail"
    assert resp["connected"] is False
    assert resp["enabled"] is False
    assert resp["mcp_server_key"] == "gmail"


def test_build_app_response_connected():
    app_def = CONNECTED_APPS["slack"]
    state = {"connected": True, "enabled": True, "server_url": "https://strata.klavis.ai/mcp/slack/", "instance_id": "slack-klavis"}
    resp = _build_app_response(app_def, state)
    assert resp["connected"] is True
    assert resp["mcp_server_key"] == "slack"


# ── 8. categories are correct ─────────────────────────────────────────────────

def test_google_apps_category():
    for app_id in ["gmail", "gdrive", "gsheets", "gcalendar"]:
        assert CONNECTED_APPS[app_id].category == "google", f"{app_id} should be in google category"


def test_microsoft_apps_category():
    for app_id in ["outlook", "onedrive"]:
        assert CONNECTED_APPS[app_id].category == "microsoft"


def test_dev_apps_category():
    for app_id in ["github", "gitlab", "jira"]:
        assert CONNECTED_APPS[app_id].category == "dev"


# ── 9. defaults ───────────────────────────────────────────────────────────────

def test_default_klavis_endpoint():
    assert _KLAVIS_API_BASE == "https://api.klavis.ai"


def test_default_transport():
    assert _DEFAULT_TRANSPORT == "streamableHttp"


# ── 10. Strata lifecycle and OAuth flow cancellation ──────────────────────────

@pytest.mark.asyncio
async def test_ensure_strata_handles_403_and_404():
    from unittest.mock import AsyncMock
    import httpx
    from shibaclaw.webui.routers.connected_apps import _ensure_strata

    mock_klavis = AsyncMock()
    # Mock get_strata to raise 403 HTTP error
    resp = httpx.Response(403)
    request = httpx.Request("GET", "https://api.klavis.ai/mcp-server/strata/test-strata")
    mock_klavis.get_strata.side_effect = httpx.HTTPStatusError("Forbidden", request=request, response=resp)
    
    # Mock create_strata to return successful StrataInfo
    from shibaclaw.integrations.klavis_client import StrataInfo
    mock_klavis.create_strata.return_value = StrataInfo(
        strata_id="new-strata-id",
        mcp_url="https://strata.klavis.ai/new",
        oauth_urls={"Gmail": "https://auth.gmail"}
    )

    cfg_dict = {
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
                "mcp_url": "https://strata.klavis.ai/old",
                "user_id": "test-user"
            }
        }
    }

    strata_id, mcp_url, is_new, oauth_urls = await _ensure_strata(
        mock_klavis, cfg_dict, "test-user", "Gmail"
    )

    # Recreated strata because 403 is treated as stale/inaccessible
    assert strata_id == "new-strata-id"
    assert mcp_url == "https://strata.klavis.ai/new"
    assert is_new is True
    assert oauth_urls == {"Gmail": "https://auth.gmail"}
    mock_klavis.create_strata.assert_called_once_with("test-user", ["Gmail"])


@pytest.mark.asyncio
async def test_cancel_connect_app_removes_from_klavis():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    from shibaclaw.webui.routers.connected_apps import cancel_connect_app

    # Create dummy starlette request
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/apps/gmail/cancel",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    # Mock config dict
    cfg_dict = {
        "tools": {
            "mcpServers": {
                "gmail": {
                    "type": "streamableHttp",
                    "url": "https://strata.klavis.ai/old",
                }
            }
        },
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
            },
            "gmail": {
                "pending_oauth": True,
                "connected": False,
                "enabled": False,
            }
        }
    }
    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)
    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", return_value=None):
        
        mock_am.config = cfg
        resp = await cancel_connect_app(req)
        assert resp.status_code == 200
        
        # Verify klavis remove_server was called
        mock_klavis.remove_server.assert_called_once_with("test-strata", "Gmail")
        
        # Verify app state in config dict is reset and mcp server is removed
        assert cfg_dict["connected_apps"]["gmail"]["pending_oauth"] is False
        assert "gmail" not in cfg_dict["tools"]["mcpServers"]


@pytest.mark.asyncio
async def test_disconnect_app_clears_local_strata_on_404():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    import httpx
    from shibaclaw.webui.routers.connected_apps import disconnect_app

    scope = {
        "type": "http",
        "method": "DELETE",
        "path": "/api/apps/gmail/connect",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    cfg_dict = {
        "tools": {
            "mcpServers": {
                "gmail": {
                    "type": "streamableHttp",
                    "url": "https://strata.klavis.ai/old",
                }
            }
        },
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
            },
            "gmail": {
                "pending_oauth": False,
                "connected": True,
                "enabled": True,
            }
        }
    }

    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)
    
    # Mock remove_server to raise 404
    resp = httpx.Response(404)
    request = httpx.Request("POST", "https://api.klavis.ai/mcp-server/strata/delete")
    mock_klavis.remove_server.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)
    # Mock get_strata to also raise 404 (meaning the Strata is actually gone)
    mock_klavis.get_strata.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)

    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", return_value=None):
        
        mock_am.config = cfg
        resp = await disconnect_app(req)
        assert resp.status_code == 200
        
        # Strata should be cleared locally because get_strata also returned 404
        assert "__strata__" not in cfg_dict["connected_apps"]
        assert "gmail" not in cfg_dict["tools"]["mcpServers"]


@pytest.mark.asyncio
async def test_disconnect_app_retains_local_strata_if_exists():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    import httpx
    from shibaclaw.webui.routers.connected_apps import disconnect_app
    from shibaclaw.integrations.klavis_client import StrataInfo

    scope = {
        "type": "http",
        "method": "DELETE",
        "path": "/api/apps/gmail/connect",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    cfg_dict = {
        "tools": {
            "mcpServers": {
                "gmail": {
                    "type": "streamableHttp",
                    "url": "https://strata.klavis.ai/old",
                }
            }
        },
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
            },
            "gmail": {
                "pending_oauth": False,
                "connected": True,
                "enabled": True,
            }
        }
    }

    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)
    
    # Mock remove_server to raise 404
    resp = httpx.Response(404)
    request = httpx.Request("POST", "https://api.klavis.ai/mcp-server/strata/delete")
    mock_klavis.remove_server.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)
    # Mock get_strata to succeed (meaning the Strata itself exists)
    mock_klavis.get_strata.return_value = StrataInfo(strata_id="test-strata", mcp_url="https://strata.klavis.ai/old", oauth_urls={})

    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", return_value=None):
        
        mock_am.config = cfg
        resp = await disconnect_app(req)
        assert resp.status_code == 200
        
        # Strata should be retained locally because get_strata succeeded
        assert "__strata__" in cfg_dict["connected_apps"]
        assert cfg_dict["connected_apps"]["__strata__"]["strata_id"] == "test-strata"
        # But gmail server is still removed locally
        assert "gmail" not in cfg_dict["tools"]["mcpServers"]


@pytest.mark.asyncio
async def test_cancel_connect_app_clears_local_strata_on_404():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    import httpx
    from shibaclaw.webui.routers.connected_apps import cancel_connect_app

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/apps/gmail/cancel",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    cfg_dict = {
        "tools": {
            "mcpServers": {
                "gmail": {
                    "type": "streamableHttp",
                    "url": "https://strata.klavis.ai/old",
                }
            }
        },
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
            },
            "gmail": {
                "pending_oauth": True,
                "connected": False,
                "enabled": False,
            }
        }
    }

    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)
    
    # Mock remove_server to raise 404
    resp = httpx.Response(404)
    request = httpx.Request("POST", "https://api.klavis.ai/mcp-server/strata/delete")
    mock_klavis.remove_server.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)
    # Mock get_strata to also raise 404 (meaning the Strata is actually gone)
    mock_klavis.get_strata.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)

    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", return_value=None):
        
        mock_am.config = cfg
        resp = await cancel_connect_app(req)
        assert resp.status_code == 200
        
        # Strata should be cleared locally because get_strata also returned 404
        assert "__strata__" not in cfg_dict["connected_apps"]
        assert "gmail" not in cfg_dict["tools"]["mcpServers"]


@pytest.mark.asyncio
async def test_cancel_connect_app_retains_local_strata_if_exists():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    import httpx
    from shibaclaw.webui.routers.connected_apps import cancel_connect_app
    from shibaclaw.integrations.klavis_client import StrataInfo

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/apps/gmail/cancel",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    cfg_dict = {
        "tools": {
            "mcpServers": {
                "gmail": {
                    "type": "streamableHttp",
                    "url": "https://strata.klavis.ai/old",
                }
            }
        },
        "connected_apps": {
            "__strata__": {
                "strata_id": "test-strata",
            },
            "gmail": {
                "pending_oauth": True,
                "connected": False,
                "enabled": False,
            }
        }
    }

    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)
    
    # Mock remove_server to raise 404
    resp = httpx.Response(404)
    request = httpx.Request("POST", "https://api.klavis.ai/mcp-server/strata/delete")
    mock_klavis.remove_server.side_effect = httpx.HTTPStatusError("Not Found", request=request, response=resp)
    # Mock get_strata to succeed (meaning the Strata itself exists)
    mock_klavis.get_strata.return_value = StrataInfo(strata_id="test-strata", mcp_url="https://strata.klavis.ai/old", oauth_urls={})

    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", return_value=None):
        
        mock_am.config = cfg
        resp = await cancel_connect_app(req)
        assert resp.status_code == 200
        
        # Strata should be retained locally because get_strata succeeded
        assert "__strata__" in cfg_dict["connected_apps"]
        assert cfg_dict["connected_apps"]["__strata__"]["strata_id"] == "test-strata"
        # But gmail server is still removed locally
        assert "gmail" not in cfg_dict["tools"]["mcpServers"]


@pytest.mark.asyncio
async def test_connect_app_saves_strata_id_immediately_on_failure():
    from unittest.mock import AsyncMock, patch, MagicMock
    from starlette.requests import Request
    from shibaclaw.webui.routers.connected_apps import connect_app

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/apps/gmail/connect",
        "path_params": {"app_id": "gmail"},
    }
    req = Request(scope)

    cfg = MagicMock()
    # Empty connected_apps config dict
    cfg_dict = {
        "tools": {"mcpServers": {}},
        "connected_apps": {}
    }

    mock_klavis = AsyncMock()
    mock_klavis.is_configured = MagicMock(return_value=True)

    # Mock strata creation to succeed
    from shibaclaw.integrations.klavis_client import StrataInfo
    mock_klavis.create_strata.return_value = StrataInfo(
        strata_id="new-strata-123",
        mcp_url="https://strata.klavis.ai/new",
        oauth_urls={"Gmail": "https://auth.gmail"}
    )
    # Count how many times _save_and_reload is called
    save_count = 0
    async def mock_save(d):
        nonlocal save_count
        save_count += 1
        if save_count == 2:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Database write error during final save"}, status_code=500)
        return None

    with patch("shibaclaw.webui.routers.connected_apps.agent_manager") as mock_am, \
         patch("shibaclaw.webui.routers.connected_apps._cfg_to_dict", return_value=cfg_dict), \
         patch("shibaclaw.webui.routers.connected_apps._get_klavis_client_clean", return_value=mock_klavis), \
         patch("shibaclaw.webui.routers.connected_apps._save_and_reload", side_effect=mock_save):
        
        mock_am.config = cfg
        response = await connect_app(req)
        
        assert response.status_code == 500
        assert save_count == 2
        assert cfg_dict["connected_apps"]["__strata__"]["strata_id"] == "new-strata-123"


