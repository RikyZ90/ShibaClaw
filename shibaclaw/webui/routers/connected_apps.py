"""Connected Apps router — real service registry with Klavis Strata as hidden MCP backend."""

from __future__ import annotations

import httpx
from loguru import logger
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.integrations.klavis_client import get_klavis_client, KlavisLimitError
from shibaclaw.webui.services.connected_apps_service import (
    CONNECTED_APPS,
    CONNECTED_APPS_KEY,
    STRATA_KEY,
    KLAVIS_API_BASE,
    cfg_to_dict,
    get_app_state,
    build_app_response,
    save_and_reload,
    get_or_create_user_id,
    get_klavis_client_clean,
    ensure_strata,
    get_strata_meta,
    clear_stale_strata,
    remove_app_from_mcp,
    sync_app_to_mcp,
    is_klavis_server,
)


async def list_apps(request: Request) -> JSONResponse:
    """GET /api/apps"""
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = cfg_to_dict(cfg)

    result = []
    for app_def in CONNECTED_APPS.values():
        app_state = get_app_state(cfg_dict, app_def.id)
        result.append(build_app_response(app_def, app_state))
    return JSONResponse({"apps": result})


async def connect_app(request: Request) -> JSONResponse:
    """POST /api/apps/{app_id}/connect"""
    app_id = request.path_params.get("app_id", "")
    app_def = CONNECTED_APPS.get(app_id)
    if not app_def:
        return JSONResponse({"error": f"Unknown app: {app_id}"}, status_code=404)

    klavis = get_klavis_client_clean()
    if not klavis.is_configured():
        return JSONResponse(
            {"error": "Klavis API key not configured. Go to ⚙ Configure backend and enter your Klavis API key."},
            status_code=503,
        )

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    cfg_dict = cfg_to_dict(cfg)

    if CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[CONNECTED_APPS_KEY] is None:
        cfg_dict[CONNECTED_APPS_KEY] = {}

    user_id = get_or_create_user_id(cfg_dict)

    try:
        strata_id, mcp_url, is_new_strata, existing_oauth_urls = await ensure_strata(
            klavis, cfg_dict, user_id, app_def.klavis_server_name
        )

        if is_new_strata:
            err = await save_and_reload(cfg_dict)
            if err:
                logger.error("Failed to save newly created Strata ID to config: {}", err)

        oauth_url = existing_oauth_urls.get(app_def.klavis_server_name) or ""

        if not is_new_strata and not oauth_url:
            try:
                inject_result = await klavis.inject_server(strata_id, app_def.klavis_server_name)
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
        return JSONResponse({"error": str(exc)}, status_code=402)
    except Exception as exc:
        return JSONResponse({"error": f"Klavis error: {exc}"}, status_code=502)

    cfg_dict[CONNECTED_APPS_KEY][app_id] = {
        "enabled": False,
        "connected": False,
        "pending_oauth": True,
    }
    
    err = await save_and_reload(cfg_dict)
    if err:
        return err

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
    cfg_dict = cfg_to_dict(cfg)

    klavis = get_klavis_client_clean()
    if klavis.is_configured():
        strata_id = get_strata_meta(cfg_dict).get("strata_id") or ""
        if strata_id:
            try:
                await klavis.remove_server(strata_id, app_def.klavis_server_name)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (403, 404):
                    try:
                        await klavis.get_strata(strata_id)
                    except httpx.HTTPStatusError as get_exc:
                        if get_exc.response.status_code in (403, 404):
                            clear_stale_strata(cfg_dict)
            except Exception:
                pass

    apps_cfg = cfg_dict.get(CONNECTED_APPS_KEY) or {}
    apps_cfg.pop(app_id, None)
    cfg_dict[CONNECTED_APPS_KEY] = apps_cfg
    remove_app_from_mcp(cfg_dict, app_def)

    err = await save_and_reload(cfg_dict)
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
    cfg_dict = cfg_to_dict(cfg)

    apps_cfg = cfg_dict.get(CONNECTED_APPS_KEY) or {}
    if app_id in apps_cfg and apps_cfg[app_id].get("pending_oauth"):
        apps_cfg[app_id]["pending_oauth"] = False
        apps_cfg[app_id]["connected"] = False
        apps_cfg[app_id]["enabled"] = False
        cfg_dict[CONNECTED_APPS_KEY] = apps_cfg

        klavis = get_klavis_client_clean()
        if klavis.is_configured():
            strata_id = get_strata_meta(cfg_dict).get("strata_id") or ""
            if strata_id:
                try:
                    await klavis.remove_server(strata_id, app_def.klavis_server_name)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404):
                        try:
                            await klavis.get_strata(strata_id)
                        except httpx.HTTPStatusError as get_exc:
                            if get_exc.response.status_code in (403, 404):
                                clear_stale_strata(cfg_dict)
                except Exception:
                    pass

        remove_app_from_mcp(cfg_dict, app_def)

        err = await save_and_reload(cfg_dict)
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
    cfg_dict = cfg_to_dict(cfg)
    app_state = dict(get_app_state(cfg_dict, app_id))

    if app_state.get("connected") and not app_state.get("pending_oauth"):
        return JSONResponse(build_app_response(app_def, app_state))

    klavis = get_klavis_client()
    if klavis.is_configured():
        strata_id = get_strata_meta(cfg_dict).get("strata_id") or ""
        if strata_id:
            try:
                status = await klavis.get_auth_status(strata_id, app_def.klavis_server_name)
                if status.is_authenticated:
                    apps_cfg = cfg_dict.get(CONNECTED_APPS_KEY) or {}
                    apps_cfg[app_id] = {"enabled": True, "connected": True, "pending_oauth": False}
                    cfg_dict[CONNECTED_APPS_KEY] = apps_cfg

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
                        strata_mcp_url = get_strata_meta(cfg_dict).get("mcp_url", "")
                        if strata_mcp_url:
                            headers = {"Authorization": f"Bearer {klavis_api_key}"}
                            sync_app_to_mcp(cfg_dict, app_def, strata_mcp_url, headers=headers)

                    await save_and_reload(cfg_dict)
                    app_state = apps_cfg[app_id]
                else:
                    app_state["connected"] = False
                    app_state["enabled"] = False
            except Exception:
                pass

    return JSONResponse(build_app_response(app_def, app_state))


async def get_backend_status(request: Request) -> JSONResponse:
    """GET /api/apps/backend"""
    klavis = get_klavis_client()
    cfg = agent_manager.config
    cfg_dict = cfg_to_dict(cfg) if cfg else {}
    strata_meta = get_strata_meta(cfg_dict)
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
    cfg_dict = cfg_to_dict(cfg)

    if CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[CONNECTED_APPS_KEY] is None:
        cfg_dict[CONNECTED_APPS_KEY] = {}

    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        await run_in_threadpool(cm.set_secret, "connected_apps", "klavis_api_key", api_key)
    except Exception:
        if "__backend__" not in cfg_dict[CONNECTED_APPS_KEY]:
            cfg_dict[CONNECTED_APPS_KEY]["__backend__"] = {}
        cfg_dict[CONNECTED_APPS_KEY]["__backend__"]["klavis_api_key"] = api_key

    err = await save_and_reload(cfg_dict)
    if err:
        return err

    try:
        from shibaclaw.integrations.klavis_client import reload_klavis_client
        reload_klavis_client(api_key=api_key, base_url=KLAVIS_API_BASE)
    except Exception:
        pass

    return JSONResponse({"ok": True, "configured": True})


async def reset_strata(request: Request) -> JSONResponse:
    """POST /api/apps/backend/reset"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    strata_id = (body.get("strata_id") or "").strip()
    if not strata_id:
        return JSONResponse({"error": "strata_id is required"}, status_code=400)

    mcp_url = (body.get("mcp_url") or "").strip()

    klavis = get_klavis_client_clean()
    if not klavis.is_configured():
        return JSONResponse({"error": "Klavis API key not configured"}, status_code=503)

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
    cfg_dict = cfg_to_dict(cfg)

    if CONNECTED_APPS_KEY not in cfg_dict or cfg_dict[CONNECTED_APPS_KEY] is None:
        cfg_dict[CONNECTED_APPS_KEY] = {}

    apps_cfg = cfg_dict[CONNECTED_APPS_KEY]
    for k in list(apps_cfg.keys()):
        if k not in ("__backend__", "__strata__"):
            apps_cfg[k] = {"enabled": False, "connected": False, "pending_oauth": False}

    tools = cfg_dict.get("tools")
    if isinstance(tools, dict):
        servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
        if tools.get(servers_key):
            tools[servers_key] = {
                k: v for k, v in tools[servers_key].items() if not is_klavis_server(k, v)
            }

    user_id = get_or_create_user_id(cfg_dict)
    cfg_dict[CONNECTED_APPS_KEY][STRATA_KEY] = {
        "strata_id": strata_id,
        "mcp_url": mcp_url,
        "user_id": user_id,
    }

    err = await save_and_reload(cfg_dict)
    if err:
        return err

    return JSONResponse({
        "ok": True,
        "strata_id": strata_id,
        "mcp_url": mcp_url,
    })
