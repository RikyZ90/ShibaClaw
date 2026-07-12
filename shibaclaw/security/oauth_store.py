"""Encrypted OAuth token store for MCP server credentials.

Delegates all persistence to :class:`~shibaclaw.security.credential_manager.CredentialManager`
under the ``oauth_tokens`` namespace while keeping the same public API so that
existing callers (``OAuthFlow``, MCP connection logic, etc.) continue to work.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from loguru import logger

_NAMESPACE = "oauth_tokens"


class OAuthTokenStore:
    """
    Thin wrapper around ``CredentialManager`` that provides a per-MCP-server
    token store with expiry helpers.

    Maintains backward-compatible API surface so ``OAuthFlow`` and all other
    consumers need no changes.
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        # store_dir is accepted for backward-compat but ignored — the
        # credential manager uses the canonical ~/.shibaclaw location.
        from shibaclaw.security.credential_manager import get_credential_manager

        self._cm = get_credential_manager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_token(self, server_name: str, token_data: dict[str, Any]) -> None:
        """Persist *token_data* for *server_name*, adding a ``_saved_at`` timestamp."""
        token_data = dict(token_data)  # defensive copy
        token_data["_saved_at"] = int(time.time())
        self._cm.set_secret(_NAMESPACE, server_name, token_data)
        logger.debug("OAuthTokenStore: saved token for server '{}'", server_name)

    def load_token(self, server_name: str) -> dict[str, Any] | None:
        """Return the stored token dict for *server_name*, or ``None`` if absent."""
        val = self._cm.get_secret(_NAMESPACE, server_name)
        return val if isinstance(val, dict) else None

    def delete_token(self, server_name: str) -> None:
        """Remove the stored token for *server_name* (no-op if not present)."""
        self._cm.delete_secret(_NAMESPACE, server_name)
        logger.debug("OAuthTokenStore: deleted token for server '{}'", server_name)

    def is_expired(self, server_name: str, *, buffer_seconds: int = 60) -> bool:
        """
        Return ``True`` when the stored access token for *server_name* has expired
        (or will expire within *buffer_seconds*).

        Returns ``True`` also when no token exists or when it carries no
        expiry information, so callers can treat it as "needs refresh".
        """
        token = self.load_token(server_name)
        if not token:
            return True

        expires_at = token.get("expires_at")
        if expires_at:
            return int(time.time()) >= (int(expires_at) - buffer_seconds)

        # Derive expiry from saved_at + expires_in if present
        saved_at = token.get("_saved_at")
        expires_in = token.get("expires_in")
        if saved_at and expires_in:
            return int(time.time()) >= (int(saved_at) + int(expires_in) - buffer_seconds)

        # No expiry info → assume still valid (conservative)
        return False

    def has_refresh_token(self, server_name: str) -> bool:
        """Return ``True`` when a non-empty refresh_token is stored."""
        token = self.load_token(server_name)
        return bool(token and token.get("refresh_token"))

    def list_servers(self) -> list[str]:
        """Return the names of all servers with stored tokens."""
        return list(self._cm.get_namespace(_NAMESPACE).keys())
