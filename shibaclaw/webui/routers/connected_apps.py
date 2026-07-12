"""Connected Apps router — real service registry with Klavis Strata as hidden MCP backend.

Klavis server names MUST match the McpServerName enum exactly:
  https://www.klavis.ai/docs/api-reference/strata/create

Strata lifecycle:
  - One Strata per ShibaClaw installation, created once and reused forever.
  - strataId is persisted in config under connected_apps.__strata__.strata_id.
  - On connect: if strataId exists in config, GET it from Klavis to verify;
    if missing or 404, create a new one (raises KlavisLimitError if limit hit).
  - POST /api/apps/backend/reset lets the user manually inject an existing
    strataId (recovered from Klavis dashboard) to bypass the creation limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.integrations.klavis_client import get_klavis_client, KlavisLimitError


# ── App registry ──────────────────────────────────────────────────────────────

@dataclass
class ConnectedAppDef:
    id: str
    name: str
    category: str
    icon: str
    description: str
    klavis_server_name: str
    mcp_server_key: str = field(init=False)

    def __post_init__(self) -> None:
        self.mcp_server_key = self.id


CONNECTED_APPS: dict[str, ConnectedAppDef] = {
    "gmail": ConnectedAppDef(id="gmail", name="Gmail", category="google", icon="email",
        description="Send and read emails via Google Gmail.", klavis_server_name="Gmail"),
    "gdrive": ConnectedAppDef(id="gdrive", name="Google Drive", category="google", icon="folder",
        description="Read and write files on Google Drive.", klavis_server_name="Google Drive"),
    "gsheets": ConnectedAppDef(id="gsheets", name="Google Sheets", category="google", icon="table_chart",
        description="Manage spreadsheets and data in Google Sheets.", klavis_server_name="Google Sheets"),
    "gdocs": ConnectedAppDef(id="gdocs", name="Google Docs", category="google", icon="description",
        description="Read and write documents in Google Docs.", klavis_server_name="Google Docs"),
    "gcalendar": ConnectedAppDef(id="gcalendar", name="Google Calendar", category="google", icon="calendar_today",
        description="Manage events and schedules in Google Calendar.", klavis_server_name="Google Calendar"),
    "outlook": ConnectedAppDef(id="outlook", name="Outlook Mail", category="microsoft", icon="mail",
        description="Send and read emails via Microsoft Outlook.", klavis_server_name="Outlook Mail"),
    "onedrive": ConnectedAppDef(id="onedrive", name="OneDrive", category="microsoft", icon="cloud",
        description="Read and write files on Microsoft OneDrive.", klavis_server_name="OneDrive"),
    "outlook_calendar": ConnectedAppDef(id="outlook_calendar", name="Outlook Calendar",
        category="microsoft", icon="event",
        description="Manage events and schedules in Outlook Calendar.", klavis_server_name="Outlook Calendar"),
    "slack": ConnectedAppDef(id="slack", name="Slack", category="productivity", icon="chat",
        description="Send messages and manage channels in Slack.", klavis_server_name="Slack"),
    "notion": ConnectedAppDef(id="notion", name="Notion", category="productivity", icon="notes",
        description="Read and write pages and databases in Notion.", klavis_server_name="Notion"),
    "linear": ConnectedAppDef(id="linear", name="Linear", category="productivity", icon="notes",
        description="Manage projects and issues in Linear.", klavis_server_name="Linear"),
    "github": ConnectedAppDef(id="github", name="GitHub", category="dev", icon="code",
        description="Manage repos, issues and pull requests on GitHub.", klavis_server_name="GitHub"),
    "gitlab": ConnectedAppDef(id="gitlab", name="GitLab", category="dev", icon="merge_type",
        description="Manage repos, issues and merge requests on GitLab.", klavis_server_name="GitLab"),
    "jira": ConnectedAppDef(id="jira", name="Jira", category="dev", icon="bug_report",
        description="Manage projects and issues in Jira.", klavis_server_name="Jira"),
    "confluence": ConnectedAppDef(id="confluence", name="Confluence", category="dev", icon="article",
        description="Read and write pages in Confluence.", klavis_server_name="Confluence"),
    "dropbox": ConnectedAppDef(id="dropbox", name="Dropbox", category="storage", icon="inventory_2",
        description="Read and write files in Dropbox.", klavis_server_name="Dropbox"),
    "box": ConnectedAppDef(id="box", name="Box", category="storage", icon="archive",
        description="Manage files and folders in Box.", klavis_server_name="Box"),
    "figma": ConnectedAppDef(id="figma", name="Figma", category="design", icon="palette",
        description="Browse and comment on designs in Figma.", klavis_server_name="Figma"),
    "hubspot": ConnectedAppDef(id="hubspot", name="HubSpot", category="crm", icon="contacts",
        description="Manage contacts and deals in HubSpot CRM.", klavis_server_name="HubSpot"),
    "salesforce": ConnectedAppDef(id="salesforce", name="Salesforce", category="crm", icon="business_center",
        description="Manage CRM records in Salesforce.", klavis_server_name="Salesforce"),
    "stripe": ConnectedAppDef(id="stripe", name="Stripe", category="crm", icon="payment",
        description="Access payments and subscriptions via Stripe.", klavis_server_name="Stripe"),
}

_CONNECTED_APPS_KEY = "connected_apps"
_STRATA_KEY = "__strata__"
_DEFAULT_TRANSPORT = "streamableHttp"
_KLAVIS_API_BASE = "https://api.klavis.ai"


# ── helpers ───────────────────────────────────────────────────────────────────

def _cfg_to_dict(cfg: Any) -> dict:
    if cfg is None:
        return {}
    try:
        return cfg.model_dump(mode="json", exclude_none=False)
    except Exception:
        pass
    try:
        return dict(cfg)
    except Exception:
        return {}


def _get_apps_cfg(cfg_dict: dict) -> dict:
    return cfg_dict.get(_CONNECTED_APPS_KEY) or {}


def _get_strata_meta(cfg_dict: dict) -> dict:
    return _get_apps_cfg(cfg_dict).get(_STRATA_KEY) or {}


def _get_app_state(cfg_dict: dict, app_id: str) -> dict:
    return _get_apps_cfg(cfg_dict).get(app_id) or {}


def _is_klavis_server(k: str, v: Any) -> bool:
    if isinstance(v, dict) and v.get("klavis_app"):
        return True
    if k.endswith("-klavis"):
        return True
    return False


def _sync_app_to_mcp(
    cfg_dict: dict,
    app_def: ConnectedAppDef,
    strata_mcp_url: str,
    headers: dict[str, str] | None = None,
) -> None:
    if "tools" not in cfg_dict or cfg_dict["tools"] is None:
        cfg_dict["tools"] = {}
    tools = cfg_dict["tools"]
    # Always use "mcpServers" — the camelCase alias produced by model_dump(mode="json").
    # Migrate legacy "mcp_servers" key if present.
    if "mcp_servers" in tools and "mcpServers" not in tools:
        tools["mcpServers"] = tools.pop("mcp_servers")
    if tools.get("mcpServers") is None:
        tools["mcpServers"] = {}
    entry: dict[str, Any] = {
        "type": _DEFAULT_TRANSPORT,
        "url": strata_mcp_url,
        "klavis_app": app_def.id,
    }
    if headers:
        entry["headers"] = headers
    tools["mcpServers"][app_def.mcp_server_key] = entry


def _remove_app_from_mcp(cfg_dict: dict, app_def: ConnectedAppDef) -> None:
    tools = cfg_dict.get("tools") or {}
    # Check both key variants for backward compatibility
    servers = tools.get("mcpServers") or tools.get("mcp_servers") or {}
    servers.pop(app_def.mcp_server_key, None)


def _build_app_response(app_def: ConnectedAppDef, app_state: dict) -> dict:
    return {
        "id": app_def.id,
        "name": app_def.name,
        "category": app_def.category,
        "icon": app_def.icon,
        "description": app_def.description,
        "enabled": app_state.get("enabled", False),
        "connected": app_state.get("connected", False),
        "mcp_server_key": app_def.mcp_server_key,
    }


async def _save_and_reload(cfg_dict: dict) -> JSONResponse | None:
    try:
        from shibaclaw.config.loader import save_config
        from shibaclaw.config.schema import Config
        new_cfg = Config.model_validate(cfg_dict)
        save_config(new_cfg)
        await agent_manager.reload_config(new_cfg)
        return None
    except Exception as exc:
        logger.exception("Failed to save config")
        return JSONResponse({"error": str(exc)}, status_code=500)


def _get_or_create_user_id(cfg_dict: dict) -> str:
    """Return a stable non-empty userId for this ShibaClaw instance."""
    import hashlib
    import os as _os

    uid = _get_strata_meta(cfg_dict).get("user_id") or ""
    if uid:
        return uid
    try:
        token = cfg_dict.get("gateway", {}).get("token") or ""
        if token:
            return hashlib.sha256(token.encode()).hexdigest()[:32]
    except Exception:
        pass
    return _os.urandom(16).hex()


def _get_klavis_client_clean() -> Any:
    from shibaclaw.integrations.klavis_client import reload_klavis_client
    return reload_klavis_client(base_url=_KLAVIS_API_BASE)


def _clear_stale_strata(cfg_dict: dict) -> None:
    apps_cfg = cfg_dict.get(_CONNECTED_APPS_KEY)
    if isinstance(apps_cfg, dict):
        apps_cfg.pop(_STRATA_KEY, None)
        # Forcibly disconnect all apps if strata is lost
        for k in list(apps_cfg.keys()):
            if k not in ("__backend__", "__strata__"):
                apps_cfg[k] = {"enabled": False, "connected": False, "pending_oauth": False}

    # Remove orphaned MCP servers from tools config
    tools = cfg_dict.get("tools")
    if isinstance(tools, dict):
        servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
        if tools.get(servers_key):
            tools[servers_key] = {
                k: v for k, v in tools[servers_key].items() if not _is_klavis_server(k, v)
            }

    logger.warning("Cleared stale strata_id from config and disconnected apps — will recreate on next connect.")


_LIMIT_ERROR_MSG = (
    "Klavis account has reached the maximum number of Strata instances (limit: 3). "
    "To fix: open the Klavis dashboard (https://www.klavis.ai/dashboard), find an existing "
    "Strata ID, then call POST /api/apps/backend/reset with body "
    '{"strata_id": "<your-existing-strata-id>", "mcp_url": "<strataServerUrl>"} '
    "to reuse it without creating a new one."
)


# ── Strata lifecycle helper ────────────────────────────────────────────────────

async def _ensure_strata(
    klavis: Any,
    cfg_dict: dict,
    user_id: str,
    server_name: str,
) -> tuple[str, str, bool, dict]:  # (strata_id, mcp_url, is_new, oauth_urls)
    """Return a valid (strata_id, mcp_url, is_new, oauth_urls), reusing existing or creating new.

    Strategy:
      1. If strata_id in config → GET it from Klavis to confirm it exists.
         On 404 → clear from config and fall through to create.
      2. If no strata_id → create new one.
         On KlavisLimitError → raise with human-friendly message.
    """
    strata_meta = _get_strata_meta(cfg_dict)
    strata_id = strata_meta.get("strata_id") or ""
    mcp_url = strata_meta.get("mcp_url") or ""

    if strata_id:
        try:
            info = await klavis.get_strata(strata_id)
            # Refresh mcp_url in case it changed
            if info.mcp_url:
                mcp_url = info.mcp_url
            logger.debug("Reusing existing Strata id={}", strata_id)
            return strata_id, mcp_url, False, info.oauth_urls
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.warning("Strata {} is inaccessible or gone from Klavis (status {}) — will recreate.", strata_id, exc.response.status_code)
                _clear_stale_strata(cfg_dict)
                strata_id = ""
            else:
                raise

    # Need to create
    try:
        info = await klavis.create_strata(user_id, [server_name])
        strata_id = info.strata_id
        mcp_url = info.mcp_url
        if _CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[_CONNECTED_APPS_KEY] is None:
            cfg_dict[_CONNECTED_APPS_KEY] = {}
        cfg_dict[_CONNECTED_APPS_KEY][_STRATA_KEY] = {
            "strata_id": strata_id,
            "mcp_url": mcp_url,
            "user_id": user_id,
        }
        logger.info("Created new Strata id={} url={}", strata_id, mcp_url)
        return strata_id, mcp_url, True, info.oauth_urls
    except KlavisLimitError:
        raise KlavisLimitError(_LIMIT_ERROR_MSG)


# ── route handlers ────────────────────────────────────────────────────────────

async def list_apps(request: Request) -> JSONResponse:
    """GET /api/apps"""
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    result = []
    for app_def in CONNECTED_APPS.values():
        app_state = _get_app_state(cfg_dict, app_def.id)
        result.append(_build_app_response(app_def, app_state))
    return JSONResponse({"apps": result})


async def connect_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/connect"""
    app_id = request.path_params.get("app_id", "")
    app_def = CONNECTED_APPS.get(app_id)
    if not app_def:
        return JSONResponse({"error": f"Unknown app: {app_id}"}, status_code=404)

    klavis = _get_klavis_client_clean()
    if not klavis.is_configured():
        return JSONResponse(
            {"error": "Klavis API key not configured. Go to ⚙ Configure backend and enter your Klavis API key."},
            status_code=503,
        )

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    if _CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[_CONNECTED_APPS_KEY] is None:
        cfg_dict[_CONNECTED_APPS_KEY] = {}

    user_id = _get_or_create_user_id(cfg_dict)
    if not user_id:
        import os as _os
        user_id = _os.urandom(16).hex()

    oauth_url = ""
    mcp_url = ""
    strata_id = ""

    try:
        strata_id, mcp_url, is_new_strata, existing_oauth_urls = await _ensure_strata(
            klavis, cfg_dict, user_id, app_def.klavis_server_name
        )

        if is_new_strata:
            # Save strata_id immediately so that if subsequent steps (inject_server etc.) fail,
            # we do not lose the strata_id and leak a Strata slot on Klavis.
            err = await _save_and_reload(cfg_dict)
            if err:
                logger.error("Failed to save newly created Strata ID to config: {}", err)

        oauth_url = existing_oauth_urls.get(app_def.klavis_server_name) or ""

        # If strata already existed and we didn't have the oauth url, we inject it.
        # If it was just created (is_new_strata), the server is already injected.
        if not is_new_strata and not oauth_url:
            try:
                inject_result = await klavis.inject_server(strata_id, app_def.klavis_server_name)
                logger.debug("inject_server result for {}: {}", app_id, inject_result)
                oauth_urls_map = (inject_result or {}).get("oauthUrls") or {}
                oauth_url = oauth_urls_map.get(app_def.klavis_server_name) or ""
                if not oauth_url:
                    try:
                        auth_status = await klavis.get_auth_status(strata_id, app_def.klavis_server_name)
                        oauth_url = (
                            auth_status.metadata.get("oauthUrl")
                            or auth_status.metadata.get("oauth_url")
                            or ""
                        )
                    except Exception as e:
                        logger.debug("get_auth_status after inject failed for {}: {}", app_id, e)
            except httpx.HTTPStatusError as exc:
                logger.error("inject_server failed for {}: {}", app_id, exc)
                raise
    except KlavisLimitError as exc:
        logger.error("Klavis limit reached: {}", exc)
        return JSONResponse({"error": str(exc)}, status_code=402)
    except Exception as exc:
        logger.exception("Klavis connect failed for app '{}'", app_id)
        return JSONResponse({"error": f"Klavis error: {exc}"}, status_code=502)

    cfg_dict[_CONNECTED_APPS_KEY][app_id] = {
        "enabled": False,
        "connected": False,
        "pending_oauth": True,
    }
    # Defer _sync_app_to_mcp until the user successfully completes the OAuth flow
    # (it will be executed inside get_app_status upon successful authentication check).
    err = await _save_and_reload(cfg_dict)
    if err:
        return err

    logger.info("OAuth initiated for app '{}' via Klavis Strata {}", app_id, strata_id)
    return JSONResponse({
        "ok": True,
        "app_id": app_id,
        "oauth_url": oauth_url,
        "strata_id": strata_id,
        "mcp_url": mcp_url,
        "requires_oauth": bool(oauth_url),
    })


async def disconnect_app(request: Request) -> JSONResponse:
    """DELETE /api/apps/{app_id}/connect"""
    app_id = request.path_params.get("app_id", "")
    app_def = CONNECTED_APPS.get(app_id)
    if not app_def:
        return JSONResponse({"error": f"Unknown app: {app_id}"}, status_code=404)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    klavis = _get_klavis_client_clean()
    if klavis.is_configured():
        strata_id = _get_strata_meta(cfg_dict).get("strata_id") or ""
        if strata_id:
            try:
                await klavis.remove_server(strata_id, app_def.klavis_server_name)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (403, 404):
                    try:
                        await klavis.get_strata(strata_id)
                        logger.info("Strata {} still exists on Klavis. Retaining local strata ID.", strata_id)
                    except httpx.HTTPStatusError as get_exc:
                        if get_exc.response.status_code in (403, 404):
                            logger.warning("Strata {} is indeed gone or inaccessible from Klavis (status {}). Clearing locally.", strata_id, get_exc.response.status_code)
                            _clear_stale_strata(cfg_dict)
                        else:
                            logger.warning("Klavis get_strata failed during disconnect check: {}", get_exc)
                    except Exception as get_exc:
                        logger.warning("Klavis get_strata failed during disconnect check: {}", get_exc)
                else:
                    logger.warning("Klavis remove_server failed for '{}': {}", app_id, exc)
            except Exception as exc:
                logger.warning("Klavis remove_server failed for '{}': {}", app_id, exc)

    apps_cfg = cfg_dict.get(_CONNECTED_APPS_KEY) or {}
    apps_cfg.pop(app_id, None)
    cfg_dict[_CONNECTED_APPS_KEY] = apps_cfg
    _remove_app_from_mcp(cfg_dict, app_def)

    err = await _save_and_reload(cfg_dict)
    if err:
        return err
    return JSONResponse({"ok": True, "app_id": app_id})



async def cancel_connect_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/cancel"""
    app_id = request.path_params.get("app_id", "")
    app_def = CONNECTED_APPS.get(app_id)
    if not app_def:
        return JSONResponse({"error": f"Unknown app: {app_id}"}, status_code=404)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    apps_cfg = cfg_dict.get(_CONNECTED_APPS_KEY) or {}
    if app_id in apps_cfg and apps_cfg[app_id].get("pending_oauth"):
        logger.info("Canceling OAuth flow for app '{}'", app_id)
        apps_cfg[app_id]["pending_oauth"] = False
        apps_cfg[app_id]["connected"] = False
        apps_cfg[app_id]["enabled"] = False
        cfg_dict[_CONNECTED_APPS_KEY] = apps_cfg

        klavis = _get_klavis_client_clean()
        if klavis.is_configured():
            strata_id = _get_strata_meta(cfg_dict).get("strata_id") or ""
            if strata_id:
                try:
                    await klavis.remove_server(strata_id, app_def.klavis_server_name)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404):
                        try:
                            await klavis.get_strata(strata_id)
                            logger.info("Strata {} still exists on Klavis. Retaining local strata ID.", strata_id)
                        except httpx.HTTPStatusError as get_exc:
                            if get_exc.response.status_code in (403, 404):
                                logger.warning("Strata {} is indeed gone or inaccessible from Klavis (status {}). Clearing locally.", strata_id, get_exc.response.status_code)
                                _clear_stale_strata(cfg_dict)
                            else:
                                logger.warning("Klavis get_strata failed during cancel check: {}", get_exc)
                        except Exception as get_exc:
                            logger.warning("Klavis get_strata failed during cancel check: {}", get_exc)
                    else:
                        logger.warning("Klavis remove_server failed during cancel for '{}': {}", app_id, exc)
                except Exception as exc:
                    logger.warning("Klavis remove_server failed during cancel for '{}': {}", app_id, exc)

        # Remove the MCP server since the OAuth was cancelled and it's not authenticated
        _remove_app_from_mcp(cfg_dict, app_def)

        err = await _save_and_reload(cfg_dict)
        if err:
            return err

    return JSONResponse({"ok": True})


async def get_app_status(request: Request) -> JSONResponse:
    """GET /api/apps/{app_id}/status"""
    app_id = request.path_params.get("app_id", "")
    app_def = CONNECTED_APPS.get(app_id)
    if not app_def:
        return JSONResponse({"error": f"Unknown app: {app_id}"}, status_code=404)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)
    app_state = dict(_get_app_state(cfg_dict, app_id))

    if app_state.get("connected") and not app_state.get("pending_oauth"):
        return JSONResponse(_build_app_response(app_def, app_state))

    klavis = get_klavis_client()
    if klavis.is_configured():
        strata_id = _get_strata_meta(cfg_dict).get("strata_id") or ""
        if strata_id:
            try:
                status = await klavis.get_auth_status(strata_id, app_def.klavis_server_name)
                if status.is_authenticated:
                    apps_cfg = cfg_dict.get(_CONNECTED_APPS_KEY) or {}
                    apps_cfg[app_id] = {"enabled": True, "connected": True, "pending_oauth": False}
                    cfg_dict[_CONNECTED_APPS_KEY] = apps_cfg

                    # Inject Bearer token headers into MCP server config so
                    # the Strata MCP proxy authenticates the tool calls.
                    klavis_api_key = ""
                    try:
                        from shibaclaw.security.credential_manager import get_credential_manager
                        vault_key = get_credential_manager().get_secret("connected_apps", "klavis_api_key")
                        if vault_key and isinstance(vault_key, str):
                            klavis_api_key = vault_key
                    except Exception:
                        pass
                    
                    if not klavis_api_key:
                        backend_cfg = apps_cfg.get("__backend__") or {}
                        klavis_api_key = backend_cfg.get("klavis_api_key") or ""
                        
                    if klavis_api_key:
                        strata_mcp_url = _get_strata_meta(cfg_dict).get("mcp_url", "")
                        if strata_mcp_url:
                            headers = {"Authorization": f"Bearer {klavis_api_key}"}
                            _sync_app_to_mcp(cfg_dict, app_def, strata_mcp_url, headers=headers)

                    await _save_and_reload(cfg_dict)
                    app_state = apps_cfg[app_id]
                else:
                    app_state["connected"] = False
                    app_state["enabled"] = False
            except Exception as e:
                logger.debug("Auth status check failed for {}: {}", app_id, e)

    return JSONResponse(_build_app_response(app_def, app_state))


async def get_backend_status(request: Request) -> JSONResponse:
    """GET /api/apps/backend"""
    klavis = get_klavis_client()
    cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg) if cfg else {}
    strata_meta = _get_strata_meta(cfg_dict)
    return JSONResponse({
        "configured": klavis.is_configured(),
        "has_strata": bool(strata_meta.get("strata_id")),
        "strata_id": strata_meta.get("strata_id") or None,
    })


async def save_backend_settings(request: Request) -> JSONResponse:
    """PUT /api/apps/backend — save Klavis API key."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    api_key = (body.get("bearer_token") or body.get("api_key") or "").strip()
    if not api_key:
        return JSONResponse({"error": "api_key / bearer_token is required"}, status_code=400)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    if _CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[_CONNECTED_APPS_KEY] is None:
        cfg_dict[_CONNECTED_APPS_KEY] = {}

    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        cm.set_secret("connected_apps", "klavis_api_key", api_key)
    except Exception as exc:
        logger.warning("Could not save Klavis API key to vault: {}", exc)
        if "__backend__" not in cfg_dict[_CONNECTED_APPS_KEY]:
            cfg_dict[_CONNECTED_APPS_KEY]["__backend__"] = {}
        cfg_dict[_CONNECTED_APPS_KEY]["__backend__"]["klavis_api_key"] = api_key

    err = await _save_and_reload(cfg_dict)
    if err:
        return err

    try:
        from shibaclaw.integrations.klavis_client import reload_klavis_client
        reload_klavis_client(api_key=api_key, base_url=_KLAVIS_API_BASE)
    except Exception as exc:
        logger.warning("Could not hot-reload KlavisClient: {}", exc)

    logger.info("Klavis API key saved via UI")
    return JSONResponse({"ok": True, "configured": True})


async def reset_strata(request: Request) -> JSONResponse:
    """POST /api/apps/backend/reset

    Inject an existing Klavis Strata ID into local config so ShibaClaw
    reuses it instead of trying to create a new one (which fails at limit 3).

    Body: { "strata_id": "<id>", "mcp_url": "<strataServerUrl>" }
    The mcp_url is optional — if omitted we fetch it from Klavis via GET.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    strata_id = (body.get("strata_id") or "").strip()
    if not strata_id:
        return JSONResponse({"error": "strata_id is required"}, status_code=400)

    mcp_url = (body.get("mcp_url") or "").strip()

    klavis = _get_klavis_client_clean()
    if not klavis.is_configured():
        return JSONResponse({"error": "Klavis API key not configured"}, status_code=503)

    # Verify the strata_id actually exists on Klavis
    try:
        info = await klavis.get_strata(strata_id)
        if not mcp_url:
            mcp_url = info.mcp_url
    except httpx.HTTPStatusError as exc:
        return JSONResponse(
            {"error": f"Strata {strata_id!r} not found on Klavis: HTTP {exc.response.status_code}"},
            status_code=404,
        )
    except Exception as exc:
        return JSONResponse({"error": f"Failed to verify strata: {exc}"}, status_code=502)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = _cfg_to_dict(cfg)

    if _CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[_CONNECTED_APPS_KEY] is None:
        cfg_dict[_CONNECTED_APPS_KEY] = {}

    apps_cfg = cfg_dict[_CONNECTED_APPS_KEY]
    # Forcibly disconnect all apps when changing strata manually
    for k in list(apps_cfg.keys()):
        if k not in ("__backend__", "__strata__"):
            apps_cfg[k] = {"enabled": False, "connected": False, "pending_oauth": False}

    # Remove orphaned MCP servers from tools config
    tools = cfg_dict.get("tools")
    if isinstance(tools, dict):
        servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
        if tools.get(servers_key):
            tools[servers_key] = {
                k: v for k, v in tools[servers_key].items() if not _is_klavis_server(k, v)
            }

    user_id = _get_or_create_user_id(cfg_dict)
    cfg_dict[_CONNECTED_APPS_KEY][_STRATA_KEY] = {
        "strata_id": strata_id,
        "mcp_url": mcp_url,
        "user_id": user_id,
    }

    err = await _save_and_reload(cfg_dict)
    if err:
        return err

    logger.info("Strata manually reset to id={} url={}", strata_id, mcp_url)
    return JSONResponse({
        "ok": True,
        "strata_id": strata_id,
        "mcp_url": mcp_url,
    })
