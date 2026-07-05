"""OAuth 2.0 Authorization Code flow with PKCE for MCP HTTP endpoints."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import time
import urllib.parse
import webbrowser
from typing import Any

import httpx
from loguru import logger

from shibaclaw.security.oauth_store import OAuthTokenStore

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _generate_pkce_pair() -> tuple[str, str]:
    """Return *(code_verifier, code_challenge)* using S256 method."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------


class _CallbackServer:
    """
    Minimal async HTTP server that captures the OAuth callback.

    Listens on 127.0.0.1 at a random available port.  After receiving the
    first ``/callback`` request it resolves a future and shuts down.
    """

    _HTML_OK = (
        "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
        "<h2>&#x2705; ShibaClaw authorised!</h2>"
        "<p>You can close this tab now.</p></body></html>"
    )
    _HTML_ERR = (
        "<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
        "<h2>&#x274C; Authorisation failed</h2>"
        "<p>{error}</p></body></html>"
    )

    def __init__(self) -> None:
        self._future: asyncio.Future[dict[str, str]] = asyncio.get_running_loop().create_future()
        self._server: asyncio.Server | None = None
        self.port: int = 0
        self.token: str = secrets.token_urlsafe(16)

    async def start(self) -> None:
        """Start the server and populate ``self.port``."""
        self._server = await asyncio.start_server(
            self._handle,
            host="127.0.0.1",
            port=0,  # OS assigns a free port
        )
        self.port = self._server.sockets[0].getsockname()[1]
        await self._server.__aenter__()
        logger.debug("OAuthCallbackServer: listening on http://127.0.0.1:{}/callback/{}", self.port, self.token)

    async def wait_for_code(self, timeout: float = 120.0) -> dict[str, str]:
        """Block until the callback arrives or *timeout* seconds elapse."""
        return await asyncio.wait_for(self._future, timeout=timeout)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.read(4096), timeout=5)
            request_line = raw.decode(errors="replace").split("\r\n", 1)[0]
            # e.g. "GET /callback?code=xxx&state=yyy HTTP/1.1"
            parts = request_line.split(" ")
            if len(parts) < 2:
                return

            path = parts[1]
            if f"/callback/{self.token}" not in path:
                body = self._HTML_ERR.format(error="Invalid or missing callback token").encode()
                await self._respond(writer, 400, body)
                return

            qs = urllib.parse.urlparse(path).query
            params = dict(urllib.parse.parse_qsl(qs))

            if "error" in params:
                body = self._HTML_ERR.format(error=params["error"]).encode()
                await self._respond(writer, 400, body)
                if not self._future.done():
                    self._future.set_exception(
                        RuntimeError(f"OAuth error: {params['error']}")
                    )
            else:
                body = self._HTML_OK.encode()
                await self._respond(writer, 200, body)
                if not self._future.done():
                    self._future.set_result(params)
        except Exception as exc:
            logger.debug("OAuthCallbackServer: handler error: {}", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    async def _respond(writer: asyncio.StreamWriter, status: int, body: bytes) -> None:
        phrase = {200: "OK", 400: "Bad Request"}.get(status, "Unknown")
        response = (
            f"HTTP/1.1 {status} {phrase}\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body
        writer.write(response)
        await writer.drain()


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


class OAuthFlow:
    """
    Full OAuth 2.0 Authorization Code + PKCE flow for MCP HTTP endpoints.

    Usage::

        flow = OAuthFlow()
        token = await flow.authorize(server_name="notion", cfg=mcp_cfg)
        # token == {"access_token": "...", "refresh_token": "...", ...}
    """

    def __init__(self, store: OAuthTokenStore | None = None) -> None:
        self._store = store or OAuthTokenStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def authorize(
        self,
        server_name: str,
        cfg: Any,  # MCPOAuthConfig
        *,
        callback_timeout: float = 120.0,
    ) -> dict[str, Any]:
        """
        Run the full Authorization Code + PKCE flow.

        1. Starts a local callback HTTP server on a random port.
        2. Opens the user's browser at the provider's ``auth_url``.
        3. Waits for the browser redirect to ``http://127.0.0.1:<port>/callback``.
        4. Exchanges the ``code`` for tokens via ``token_url``.
        5. Persists and returns the token dict.
        """
        code_verifier, code_challenge = _generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        callback_server = _CallbackServer()
        await callback_server.start()
        redirect_uri = f"http://127.0.0.1:{callback_server.port}/callback/{callback_server.token}"

        auth_params: dict[str, str] = {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if cfg.scopes:
            auth_params["scope"] = " ".join(cfg.scopes)

        auth_url = cfg.auth_url + "?" + urllib.parse.urlencode(auth_params)

        logger.info(
            "OAuthFlow[{}]: opening browser for authorisation — {}", server_name, auth_url
        )
        try:
            webbrowser.open(auth_url)
        except Exception:
            # Headless env: print URL for manual use
            print(f"\n[ShibaClaw] Open this URL to authorise '{server_name}':\n{auth_url}\n")

        try:
            params = await callback_server.wait_for_code(timeout=callback_timeout)
        finally:
            await callback_server.stop()

        # Validate state to prevent CSRF
        if params.get("state") != state:
            raise RuntimeError(
                f"OAuthFlow[{server_name}]: state mismatch — possible CSRF attack"
            )

        code = params.get("code")
        if not code:
            raise RuntimeError(f"OAuthFlow[{server_name}]: no code in callback params")

        token_data = await self._exchange_code(
            server_name=server_name,
            cfg=cfg,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )
        self._store.save_token(server_name, token_data)
        logger.info("OAuthFlow[{}]: authorisation successful", server_name)
        return token_data

    async def refresh(
        self,
        server_name: str,
        cfg: Any,  # MCPOAuthConfig
    ) -> dict[str, Any]:
        """
        Use the stored refresh_token to obtain a fresh access_token.

        Raises ``RuntimeError`` when no refresh token is available.
        """
        stored = self._store.load_token(server_name)
        if not stored or not stored.get("refresh_token"):
            raise RuntimeError(
                f"OAuthFlow[{server_name}]: no refresh_token stored — run full auth flow first"
            )

        payload: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": stored["refresh_token"],
            "client_id": cfg.client_id,
        }
        if cfg.client_secret:
            payload["client_secret"] = cfg.client_secret

        token_data = await self._post_token(cfg.token_url, payload)

        # Preserve existing refresh_token when provider omits it from the response
        if "refresh_token" not in token_data:
            token_data["refresh_token"] = stored["refresh_token"]

        self._store.save_token(server_name, token_data)
        logger.info("OAuthFlow[{}]: token refreshed", server_name)
        return token_data

    async def get_valid_token(
        self,
        server_name: str,
        cfg: Any,  # MCPOAuthConfig
        *,
        callback_timeout: float = 120.0,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Convenience method: return a valid (non-expired) token dict.

        Decision tree:
        - No stored token → full authorize() flow (if interactive) or error.
        - Expired + has refresh_token → refresh().
        - Expired + no refresh_token → full authorize() flow (if interactive) or error.
        - Not expired → return stored token directly.
        """
        stored = self._store.load_token(server_name)

        if not stored:
            if not interactive:
                raise RuntimeError(
                    f"OAuth token for '{server_name}' not found. Please authenticate via the WebUI."
                )
            return await self.authorize(server_name, cfg, callback_timeout=callback_timeout)

        if self._store.is_expired(server_name):
            if self._store.has_refresh_token(server_name):
                try:
                    return await self.refresh(server_name, cfg)
                except Exception as exc:
                    logger.warning(
                        "OAuthFlow[{}]: refresh failed ({}), re-authorising", server_name, exc
                    )
            if not interactive:
                raise RuntimeError(
                    f"OAuth token for '{server_name}' is expired and cannot be refreshed silently. Please re-authenticate."
                )
            return await self.authorize(server_name, cfg, callback_timeout=callback_timeout)

        return stored

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _exchange_code(
        self,
        *,
        server_name: str,
        cfg: Any,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": cfg.client_id,
            "code_verifier": code_verifier,
        }
        if cfg.client_secret:
            payload["client_secret"] = cfg.client_secret

        return await self._post_token(cfg.token_url, payload)

    @staticmethod
    async def _post_token(token_url: str, payload: dict[str, str]) -> dict[str, Any]:
        """
        POST to *token_url* and return the parsed JSON response.

        Raises ``RuntimeError`` on HTTP errors or missing ``access_token``.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                token_url,
                data=payload,
                headers={"Accept": "application/json"},
            )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Token endpoint returned {resp.status_code}: {resp.text[:300]}"
            )

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            data: dict[str, Any] = resp.json()
        else:
            # Some providers return application/x-www-form-urlencoded
            try:
                data = resp.json()
            except Exception:
                data = dict(urllib.parse.parse_qsl(resp.text))
        if "access_token" not in data:
            raise RuntimeError(f"Token response missing 'access_token': {data}")

        # Normalise expires_at from expires_in when absent
        if "expires_in" in data and "expires_at" not in data:
            data["expires_at"] = int(time.time()) + int(data["expires_in"])

        return data
