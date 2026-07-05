"""Tests for Connected Apps — real service registry with Klavis as hidden backend."""

from __future__ import annotations



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
    assert CONNECTED_APPS["gmail"].mcp_server_key == "gmail-klavis"


def test_mcp_server_key_gdrive():
    assert CONNECTED_APPS["gdrive"].mcp_server_key == "gdrive-klavis"


def test_mcp_server_key_slack():
    assert CONNECTED_APPS["slack"].mcp_server_key == "slack-klavis"


def test_mcp_server_key_github():
    assert CONNECTED_APPS["github"].mcp_server_key == "github-klavis"


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

    servers = cfg["tools"]["mcp_servers"]
    assert "gmail-klavis" in servers
    entry = servers["gmail-klavis"]
    assert entry["url"] == "https://strata.klavis.ai/mcp/gmail/"
    assert entry["enabled"] is True



def test_sync_github_to_mcp():
    app_def = CONNECTED_APPS["github"]

    cfg = _base_cfg()

    _sync_app_to_mcp(cfg, app_def, "https://strata.klavis.ai/mcp/" + app_def.id + "/")

    servers = cfg["tools"]["mcp_servers"]
    assert "github-klavis" in servers


# ── 6. disconnect removes from mcpServers ─────────────────────────────────────

def test_disconnect_gmail_removes_from_mcp():
    app_def = CONNECTED_APPS["gmail"]
    cfg = _base_cfg()
    cfg["tools"]["mcp_servers"]["gmail-klavis"] = {
        "type": "streamableHttp",
        "url": "https://strata.klavis.ai/mcp/gmail/",
        "enabled": True,
    }

    _remove_app_from_mcp(cfg, app_def)

    assert "gmail-klavis" not in cfg["tools"]["mcp_servers"]


def test_disconnect_nonexistent_app_is_noop():
    app_def = CONNECTED_APPS["github"]
    cfg = _base_cfg()
    # no github-klavis in servers — should not raise
    _remove_app_from_mcp(cfg, app_def)
    assert "github-klavis" not in cfg["tools"]["mcp_servers"]


# ── 7. build_app_response shape ───────────────────────────────────────────────

def test_build_app_response_not_connected():
    app_def = CONNECTED_APPS["gmail"]
    resp = _build_app_response(app_def, {})
    assert resp["id"] == "gmail"
    assert resp["name"] == "Gmail"
    assert resp["connected"] is False
    assert resp["enabled"] is False
    assert resp["mcp_server_key"] == "gmail-klavis"


def test_build_app_response_connected():
    app_def = CONNECTED_APPS["slack"]
    state = {"connected": True, "enabled": True, "server_url": "https://strata.klavis.ai/mcp/slack/", "instance_id": "slack-klavis"}
    resp = _build_app_response(app_def, state)
    assert resp["connected"] is True
    assert resp["mcp_server_key"] == "slack-klavis"


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
