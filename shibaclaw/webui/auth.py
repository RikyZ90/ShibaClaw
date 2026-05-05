"""Authentication and middleware for the WebUI."""

from __future__ import annotations

import hmac
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.config.paths import get_app_root

AUTH_TOKEN_FILE = get_app_root() / "auth_token"


def _auth_enabled() -> bool:
    return os.environ.get("SHIBACLAW_AUTH", "true").lower() not in ("false", "0", "no", "off")


def _load_or_generate_token() -> str:
    env_token = os.environ.get("SHIBACLAW_AUTH_TOKEN", "").strip()
    if env_token:
        return env_token
    if AUTH_TOKEN_FILE.exists():
        saved = AUTH_TOKEN_FILE.read_text().strip()
        if saved:
            return saved
    token = secrets.token_hex(16)
    AUTH_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_TOKEN_FILE.write_text(token)
    try:
        AUTH_TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return token


def _read_existing_token() -> str:
    """Read the current auth token from env or disk without generating a new one."""
    env_token = os.environ.get("SHIBACLAW_AUTH_TOKEN", "").strip()
    if env_token:
        return env_token
    if AUTH_TOKEN_FILE.exists():
        saved = AUTH_TOKEN_FILE.read_text().strip()
        if saved:
            return saved
    return ""


_AUTH_TOKEN: str = _load_or_generate_token() if _auth_enabled() else ""


def get_auth_token(refresh: bool = False) -> str | None:
    global _AUTH_TOKEN

    if not _auth_enabled():
        return None

    if refresh:
        refreshed = _read_existing_token()
        if refreshed:
            _AUTH_TOKEN = refreshed

    if not _AUTH_TOKEN:
        _AUTH_TOKEN = _load_or_generate_token()

    if _AUTH_TOKEN:
        return _AUTH_TOKEN
    return None


def verify_token_value(token_candidate: str | None) -> bool:
    auth_token = get_auth_token(refresh=True)
    if not _auth_enabled() or not auth_token:
        return True
    candidate = (token_candidate or "").strip()
    return bool(candidate) and hmac.compare_digest(candidate, auth_token)


def mask_token(token: str) -> str:
    if len(token) <= 4:
        return "****"
    return token[:4] + "*" * (len(token) - 4)


def check_token(request: Request) -> bool:
    auth_header = request.headers.get("authorization", "")
    token_candidate = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    return verify_token_value(token_candidate)


PUBLIC_PATHS = ("/static/", "/api/auth/", "/api/file-get", "/api/oauth/openrouter/callback")


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
