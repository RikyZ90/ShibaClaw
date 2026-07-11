"""Auth API routes — setup, login, verify, status."""

from __future__ import annotations

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.auth import _auth_enabled, _is_user_setup, verify_token_value


# ------------------------------------------------------------------
# POST /api/auth/setup  —  first-run admin user creation
# ------------------------------------------------------------------


async def api_auth_setup(request: Request):
    """Create the admin user.  Only allowed once (first run)."""
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()

    if cm.is_setup():
        return JSONResponse(
            {"error": "Admin user already configured."},
            status_code=409,
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return JSONResponse(
            {"error": "Both username and password are required."},
            status_code=400,
        )

    if len(password) < 6:
        return JSONResponse(
            {"error": "Password must be at least 6 characters."},
            status_code=400,
        )

    ok = cm.setup_user(username, password)
    if not ok:
        return JSONResponse({"error": "Setup failed."}, status_code=500)

    # Migrate existing config.json secrets into the credential vault
    try:
        _migrate_config_secrets_to_vault(cm)
    except Exception:
        logger.exception("Failed to migrate config secrets into vault")

    # Issue a session token immediately so the user doesn't need to login again
    session_token = cm.create_session_token()

    logger.info("Admin user '{}' created via WebUI setup.", username)
    return JSONResponse({
        "status": "ok",
        "session_token": session_token,
    })


# ------------------------------------------------------------------
# POST /api/auth/login
# ------------------------------------------------------------------


async def api_auth_login(request: Request):
    """Authenticate with username + password, return a session token."""
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()

    if not cm.is_setup():
        return JSONResponse(
            {"error": "Admin user not configured. Please run setup first."},
            status_code=403,
        )

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not cm.verify_password(username, password):
        logger.warning("Failed login attempt for user '{}' from {}",
                        username, request.client.host if request.client else "unknown")
        return JSONResponse(
            {"error": "Invalid username or password."},
            status_code=401,
        )

    session_token = cm.create_session_token()
    logger.info("User '{}' logged in from {}.",
                username, request.client.host if request.client else "unknown")
    return JSONResponse({
        "status": "ok",
        "session_token": session_token,
    })


# ------------------------------------------------------------------
# POST /api/auth/verify  —  legacy token verification
# ------------------------------------------------------------------


async def api_auth_verify(request: Request):
    """Verify a token (legacy or session)."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()

    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})

    # Try session token
    from shibaclaw.security.credential_manager import CredentialManager
    if CredentialManager.verify_session_token(token):
        return JSONResponse({"valid": True, "auth_required": True})

    # Try legacy token
    if verify_token_value(token):
        return JSONResponse({"valid": True, "auth_required": True})

    return JSONResponse({"valid": False, "auth_required": True})


# ------------------------------------------------------------------
# GET /api/auth/status
# ------------------------------------------------------------------


async def api_auth_status(request: Request):
    """Return auth state: whether auth is required, whether setup is done."""
    return JSONResponse({
        "auth_required": _auth_enabled(),
        "needs_setup": not _is_user_setup(),
    })


# ------------------------------------------------------------------
# Migration helper
# ------------------------------------------------------------------


def _migrate_config_secrets_to_vault(cm) -> None:
    """Move plain-text secrets from config.json into the encrypted vault.

    Called once during setup.  After migration the secrets are zeroed out
    in config.json and the file is re-saved.
    """
    from shibaclaw.config.loader import load_config, save_config
    from shibaclaw.config.schema import ProvidersConfig

    cfg = load_config()

    migrated = False

    # --- Provider API keys ---
    for field_name in ProvidersConfig.model_fields:
        provider_cfg = getattr(cfg.providers, field_name, None)
        if provider_cfg is None:
            continue
        if provider_cfg.api_key:
            cm.set_secret("providers", f"{field_name}.api_key", provider_cfg.api_key)
            provider_cfg.api_key = ""
            migrated = True

    # --- Web search API key ---
    if cfg.tools.web.search.api_key:
        cm.set_secret("tools", "web_search.api_key", cfg.tools.web.search.api_key)
        cfg.tools.web.search.api_key = ""
        migrated = True

    # --- Audio API key ---
    if cfg.audio.api_key:
        cm.set_secret("audio", "api_key", cfg.audio.api_key)
        cfg.audio.api_key = None
        migrated = True

    # --- Channel secrets (email password, bot tokens, etc.) ---
    if cfg.channels.model_extra:
        for ch_name, ch_data in cfg.channels.model_extra.items():
            if not isinstance(ch_data, dict):
                continue
            secret_keys = [
                k for k in ch_data
                if any(s in k.lower() for s in ("token", "password", "secret", "key"))
                and ch_data[k]
                and isinstance(ch_data[k], str)
            ]
            for sk in secret_keys:
                cm.set_secret("channels", f"{ch_name}.{sk}", ch_data[sk])
                ch_data[sk] = ""
                migrated = True

    # --- MCP OAuth secrets ---
    if cfg.tools and cfg.tools.mcp_servers:
        for server_name, server_cfg in cfg.tools.mcp_servers.items():
            if server_cfg.oauth and server_cfg.oauth.client_secret:
                cm.set_secret("mcp_servers", f"{server_name}.client_secret", server_cfg.oauth.client_secret)
                server_cfg.oauth.client_secret = None
                migrated = True

    if migrated:
        save_config(cfg)
        logger.info("Migrated plain-text secrets from config.json → encrypted vault.")
