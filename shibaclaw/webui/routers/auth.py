"""Auth API routes — setup, login, verify, status."""

from __future__ import annotations

from loguru import logger
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from shibaclaw.webui.auth import _auth_enabled, _is_user_setup


# ------------------------------------------------------------------
# POST /api/auth/setup  —  first-run admin user creation
# ------------------------------------------------------------------


async def api_auth_setup(request: Request):
    """Create the admin user.  Only allowed once (first run)."""
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()

    if await run_in_threadpool(cm.is_setup):
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

    ok = await run_in_threadpool(cm.setup_user, username, password)
    if not ok:
        return JSONResponse({"error": "Setup failed."}, status_code=500)

    # Migrate existing config.json secrets into the credential vault
    try:
        _migrate_config_secrets_to_vault(cm)
    except Exception:
        logger.exception("Failed to migrate config secrets into vault")

    # Issue a session token immediately so the user doesn't need to login again
    session_token = await run_in_threadpool(cm.create_session_token)

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

    if not await run_in_threadpool(cm.is_setup):
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

    if not await run_in_threadpool(cm.verify_password, username, password):
        logger.warning("Failed login attempt for user '{}' from {}",
                        username, request.client.host if request.client else "unknown")
        return JSONResponse(
            {"error": "Invalid username or password."},
            status_code=401,
        )

    session_token = await run_in_threadpool(cm.create_session_token)
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
    """Verify a session token."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()

    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})

    # Try session token
    from shibaclaw.security.credential_manager import CredentialManager
    if await run_in_threadpool(CredentialManager.verify_session_token, token):
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
# POST /api/auth/change-password
# ------------------------------------------------------------------

async def api_auth_change_password(request: Request):
    """Change the admin password."""
    from shibaclaw.security.credential_manager import get_credential_manager

    cm = get_credential_manager()
    if not await run_in_threadpool(cm.is_setup):
        return JSONResponse({"error": "Admin user not configured."}, status_code=400)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not old_password or not new_password:
        return JSONResponse({"error": "Both old and new passwords are required."}, status_code=400)

    if len(new_password) < 6:
        return JSONResponse({"error": "New password must be at least 6 characters."}, status_code=400)

    username = await run_in_threadpool(cm.get_admin_username)
    if not username:
        return JSONResponse({"error": "Admin user not configured."}, status_code=400)

    ok = await run_in_threadpool(cm.change_password, username, old_password, new_password)
    if not ok:
        return JSONResponse({"error": "Incorrect old password."}, status_code=401)

    logger.info("Admin password changed successfully.")
    return JSONResponse({"status": "ok"})


# ------------------------------------------------------------------
# Migration helper
# ------------------------------------------------------------------


def _migrate_config_secrets_to_vault(cm) -> None:
    """Move plain-text secrets from config.json into the encrypted vault.

    Called once during setup.  After migration the secrets are removed from
    config.json and the file is re-saved.
    """
    import json
    import os
    import tempfile
    from shibaclaw.config.loader import get_config_path, _migrate_secrets_from_raw_dict

    path = get_config_path()
    if not path.exists():
        return

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if _migrate_secrets_from_raw_dict(data, cm):
            # Save the raw data back (now without secrets)
            with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_name = tmp.name
            os.replace(tmp_name, path)
            logger.info("Migrated plain-text secrets from config.json → encrypted vault.")
    except Exception:
        logger.exception("Failed to run full migration of secrets into vault")
