"""Authentication and middleware for the WebUI.

Supports User/password authentication — admin user configured via the WebUI
setup wizard; login produces a session token verified on every request.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# ------------------------------------------------------------------
# Feature flag
# ------------------------------------------------------------------


def _auth_enabled() -> bool:
    return os.environ.get("SHIBACLAW_AUTH", "true").lower() not in ("false", "0", "no", "off")


# ------------------------------------------------------------------
# Session-based auth (new)
# ------------------------------------------------------------------


def _is_user_setup() -> bool:
    """Return True if an admin user has been registered in the credential vault."""
    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        return get_credential_manager().is_setup()
    except Exception:
        return False


def _verify_session_token(token: str) -> bool:
    """Return True if *token* is a valid, non-expired session token."""
    from shibaclaw.security.credential_manager import CredentialManager
    return CredentialManager.verify_session_token(token)


# ------------------------------------------------------------------
# Unified token check
# ------------------------------------------------------------------


def mask_token(token: str) -> str:
    if len(token) <= 4:
        return "****"
    return token[:4] + "*" * (len(token) - 4)


def check_token(request: Request) -> bool:
    """Validate a request's credentials.

    Accepts:
    - ``Authorization: Bearer <session_token>`` (from user/password login)
    """
    auth_header = request.headers.get("authorization", "")
    token_candidate = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""

    if not token_candidate:
        return False

    # Verify session token (user/password login)
    return _verify_session_token(token_candidate)


# ------------------------------------------------------------------
# Paths that bypass auth
# ------------------------------------------------------------------

PUBLIC_PATHS = (
    "/static/",
    "/api/auth/",
    "/api/file-get",
    "/api/oauth/openrouter/callback",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _auth_enabled():
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)
        if path == "/":
            return await call_next(request)
        if not check_token(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)


def get_cors_origins(port: int = 3000, host: str = "127.0.0.1") -> list[str]:
    env = os.environ.get("SHIBACLAW_CORS_ORIGINS", "").strip()
    if env == "*":
        return ["*"]
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    origins = [
        "http://localhost",
        "http://127.0.0.1",
        "https://localhost",
        "https://127.0.0.1",
    ]
    if port not in (80, 443):
        origins += [
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
            f"https://localhost:{port}",
            f"https://127.0.0.1:{port}",
        ]
    if host not in ("127.0.0.1", "localhost", "0.0.0.0", "::"):
        origins += [f"http://{host}", f"https://{host}"]
        if port not in (80, 443):
            origins += [f"http://{host}:{port}", f"https://{host}:{port}"]
    return origins
