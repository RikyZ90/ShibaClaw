"""Klavis REST API client — Strata MCP gateway.

Base URL: https://api.klavis.ai  (NO /v1 prefix)

Verified endpoints (2026-07 OpenAPI):
  POST   /mcp-server/strata/create          {userId, servers?}
  GET    /mcp-server/strata/{strataId}      → {strataId, strataServerUrl, servers}
  POST   /mcp-server/strata/add             {strataId, servers: [McpServerName]}
  POST   /mcp-server/strata/delete          {strataId, servers: [McpServerName]}  (remove)
  GET    /mcp-server/strata/{id}/auth/{name}  → auth status

API key priority:
  1. KLAVIS_API_KEY env var
  2. connected_apps.__backend__.klavis_api_key in config
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger


KLAVIS_API_BASE = os.environ.get("KLAVIS_API_BASE", "https://api.klavis.ai")
_TIMEOUT = 20.0
# Klavis error code returned when the 3-Strata limit is hit
_LIMIT_REACHED_CODE = "P0001"
_LIMIT_REACHED_MSG = "limit reached"


@dataclass
class StrataInfo:
    strata_id: str
    mcp_url: str
    oauth_urls: dict[str, str]  # {server_name: oauth_url}


@dataclass
class AppAuthStatus:
    server_name: str
    is_authenticated: bool
    metadata: dict[str, Any]


class KlavisLimitError(Exception):
    """Raised when the Klavis account has hit the Strata creation limit."""


def _load_key_from_config() -> str:
    try:
        from shibaclaw.webui.agent_manager import agent_manager
        cfg = agent_manager.config
        if not cfg:
            agent_manager.load_latest_config()
            cfg = agent_manager.config
        if not cfg:
            return ""
        apps_cfg = cfg.connected_apps
        if not apps_cfg:
            return ""
        backend = (
            apps_cfg.model_extra.get("__backend__")
            if hasattr(apps_cfg, "model_extra") and apps_cfg.model_extra
            else None
        )
        if isinstance(backend, dict):
            raw = backend.get("klavis_api_key") or ""
            return "".join(raw.split())
    except Exception:
        pass
    return ""


class KlavisStrataClient:
    """Async HTTP client for Klavis Strata REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        raw_key = (
            api_key
            or os.environ.get("KLAVIS_API_KEY", "")
            or _load_key_from_config()
        )
        self._api_key = "".join(raw_key.split())
        self._base_url = (base_url or KLAVIS_API_BASE).rstrip("/")

        if not self._api_key:
            logger.warning(
                "🐾 System  » KLAVIS_API_KEY not set — Connected Apps will not work."
            )

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def reload(self, api_key: str | None = None, base_url: str | None = None) -> None:
        if api_key:
            self._api_key = "".join(api_key.split())
        if base_url:
            self._base_url = base_url.rstrip("/")
        logger.info("KlavisClient reloaded — configured={}", self.is_configured())

    # ── internal HTTP helper ─────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        url = f"{self._base_url}{path}"
        logger.debug("Klavis {} {} payload={}", method.upper(), path, json)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(
                method, url, headers=self._headers, json=json, params=params,
            )
            if not resp.is_success:
                try:
                    body = resp.text
                except Exception:
                    body = "<unreadable>"
                logger.error(
                    "Klavis {} {} → HTTP {} | body: {}",
                    method.upper(), path, resp.status_code, body,
                )
                # Detect limit-reached before raising so callers can handle it
                if resp.status_code == 500 and (
                    _LIMIT_REACHED_CODE in body or _LIMIT_REACHED_MSG in body.lower()
                ):
                    raise KlavisLimitError(body)
            resp.raise_for_status()
            return resp.json()

    # ── Strata endpoints ───────────────────────────────────────────────

    async def create_strata(self, user_id: str, server_names: list[str]) -> StrataInfo:
        """POST /mcp-server/strata/create — raises KlavisLimitError on limit hit."""
        if not user_id:
            raise ValueError("userId is required by Klavis API (minLength: 1)")
        payload: dict[str, Any] = {"userId": user_id}
        if server_names:
            payload["servers"] = server_names
        data = await self._request("POST", "/mcp-server/strata/create", json=payload)
        return StrataInfo(
            strata_id=data.get("strataId") or "",
            mcp_url=data.get("strataServerUrl") or "",
            oauth_urls=data.get("oauthUrls") or {},
        )

    async def get_strata(self, strata_id: str) -> StrataInfo:
        """GET /mcp-server/strata/{strataId} — returns existing Strata info."""
        data = await self._request("GET", f"/mcp-server/strata/{strata_id}")
        return StrataInfo(
            strata_id=data.get("strataId") or strata_id,
            mcp_url=data.get("strataServerUrl") or "",
            oauth_urls=data.get("oauthUrls") or {},
        )

    async def get_auth_status(self, strata_id: str, server_name: str) -> AppAuthStatus:
        """GET /mcp-server/strata/{strata_id}/auth/{server_name}"""
        data = await self._request(
            "GET", f"/mcp-server/strata/{strata_id}/auth/{server_name}"
        )
        return AppAuthStatus(
            server_name=server_name,
            is_authenticated=bool(
                data.get("isAuthenticated") or data.get("is_authenticated", False)
            ),
            metadata=data,
        )

    async def inject_server(self, strata_id: str, server_name: str) -> dict:
        """POST /mcp-server/strata/add — {strataId, servers:[name]}"""
        return await self._request(
            "POST", "/mcp-server/strata/add",
            json={"strataId": strata_id, "servers": [server_name]},
        )

    async def remove_server(self, strata_id: str, server_name: str) -> dict:
        """POST /mcp-server/strata/delete — {strataId, servers:[name]}"""
        return await self._request(
            "POST", "/mcp-server/strata/delete",
            json={"strataId": strata_id, "servers": [server_name]},
        )

    # keep old name as alias for callers that already use it
    async def init_strata(self, user_id: str, server_names: list[str]) -> StrataInfo:
        return await self.create_strata(user_id, server_names)


# ── process-level singleton ────────────────────────────────────────────────
_client: KlavisStrataClient | None = None


def get_klavis_client() -> KlavisStrataClient:
    global _client
    if _client is None:
        _client = KlavisStrataClient()
    return _client


def reload_klavis_client(api_key: str | None = None, base_url: str | None = None) -> KlavisStrataClient:
    global _client
    if _client is None:
        _client = KlavisStrataClient(api_key=api_key, base_url=base_url)
    else:
        if api_key:
            _client.reload(api_key=api_key, base_url=base_url)
        else:
            new_key = os.environ.get("KLAVIS_API_KEY", "") or _load_key_from_config()
            _client.reload(api_key=new_key, base_url=base_url)
    return _client
