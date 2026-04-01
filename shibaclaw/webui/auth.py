"""Authentication and middleware for the ShibaClaw WebUI."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

# ── Token-based authentication ───────────────────────────────────
AUTH_TOKEN_DIR = Path.home() / ".shibaclaw"
AUTH_TOKEN_FILE = AUTH_TOKEN_DIR / "auth_token"


def _auth_enabled() -> bool:
    """Check if auth is enabled (default: True)."""
    return os.environ.get("SHIBACLAW_AUTH", "true").lower() not in ("false", "0", "no", "off")


def _load_or_generate_token() -> str:
    """Load token from env/file, or generate a new one."""
    # 1. Environment variable override
    env_token = os.environ.get("SHIBACLAW_AUTH_TOKEN", "").strip()
    if env_token:
        return env_token

    # 2. Load from file
    if AUTH_TOKEN_FILE.exists():
        saved = AUTH_TOKEN_FILE.read_text().strip()
        if saved:
            return saved

    # 3. Generate new token
    token = secrets.token_hex(16)
    AUTH_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_TOKEN_FILE.write_text(token)
    try:
        AUTH_TOKEN_FILE.chmod(0o600)
    except OSError:
        pass  # Windows might not support chmod 600 directly
    return token


# Global auth token for the module
_AUTH_TOKEN: str = _load_or_generate_token() if _auth_enabled() else ""


def get_auth_token() -> str | None:
    """Return the current auth token."""
    if _auth_enabled() and _AUTH_TOKEN:
        return _AUTH_TOKEN
    return None


def mask_token(token: str) -> str:
    """Return a masked version of a token for safe logging."""
    if len(token) <= 4:
        return "****"
    return token[:4] + "*" * (len(token) - 4)


def check_token(request: Request) -> bool:
    """Validate the auth token from Authorization header or query param."""
    if not _auth_enabled() or not _AUTH_TOKEN:
        return True
    
    # 1. Check Authorization: Bearer <token>
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:].strip() == _AUTH_TOKEN:
        return True
    
    # 2. Check query parameter as fallback (needed for direct browser links/downloads)
    token_param = request.query_params.get("token")
    if token_param == _AUTH_TOKEN:
        return True
    
    return False


# Paths that don't require auth (static assets, auth endpoints, socket.io)
PUBLIC_PATHS = ("/static/", "/api/auth/", "/socket.io")


class AuthMiddleware(BaseHTTPMiddleware):
    """Token-based auth middleware — blocks unauthenticated HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        if not _auth_enabled():
            return await call_next(request)

        path = request.url.path

        # Allow public paths through
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        # Root page — serve index.html always (JS handles login screen)
        if path == "/":
            return await call_next(request)

        # All /api/* routes require valid token
        if not check_token(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)


def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from env or safe defaults."""
    env = os.environ.get("SHIBACLAW_CORS_ORIGINS", "").strip()
    if env == "*":
        return ["*"]  # explicit opt-in to wildcard
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
        "https://localhost",
        "https://127.0.0.1",
    ]
