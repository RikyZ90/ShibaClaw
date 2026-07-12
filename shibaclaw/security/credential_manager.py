"""Encrypted vault for credentials and user authentication.

Provides:
- Single-admin user registration & password verification (scrypt-hashed).
- Namespaced secret storage (API keys, OAuth tokens, etc.) encrypted via Fernet.
- Session token generation for WebUI login.

All data is persisted in a single ``credentials.enc`` file; the Fernet key
lives alongside it in ``credentials.key`` with 0o600 permissions.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import subprocess
import threading
import time
from hashlib import scrypt
from pathlib import Path
from typing import Any

from loguru import logger

_STORE_FILENAME = "credentials.enc"
_KEY_FILENAME = "credentials.key"

_FERNET_CACHE: dict[Path, "Any"] = {}
_CREDENTIAL_MANAGER_INSTANCE: "CredentialManager | None" = None

# Session tokens issued on login, mapped token → expiry epoch
_ACTIVE_SESSIONS: dict[str, float] = {}
_SESSION_TTL_SECONDS = 86400  # 24 h


def _get_store_dir() -> Path:
    """Return the stable ~/.shibaclaw directory for credential storage."""
    from shibaclaw.config.paths import get_app_root

    return get_app_root()


def _load_or_create_key(key_path: Path) -> bytes:
    """Load an existing Fernet key or generate and persist a new one."""
    from cryptography.fernet import Fernet

    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    if platform.system() != "Windows":
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
    else:
        try:
            subprocess.run(
                ["icacls", str(key_path), "/inheritance:r", "/grant:r", f"{os.getlogin()}:F"],
                capture_output=True
            )
        except Exception:
            pass
    logger.debug("CredentialManager: generated new encryption key at {}", key_path)
    return key


# ======================================================================
# CredentialManager
# ======================================================================


class CredentialManager:
    """
    Fernet-encrypted, JSON-backed vault for secrets and admin credentials.

    Internal structure of the decrypted JSON::

        {
            "admin_user": {
                "username": "...",
                "password_hash": "...",
                "salt": "..."
            },
            "secrets": {
                "<namespace>": {
                    "<key>": <value>,
                    ...
                }
            }
        }
    """

    def __init__(self, store_dir: Path | None = None) -> None:
        base = store_dir or _get_store_dir()
        self._store_path = base / _STORE_FILENAME
        self._key_path = base / _KEY_FILENAME
        self._fernet = self._build_fernet()
        self._cache: dict[str, Any] = {}
        self._cache_mtime: float | None = None
        self._lock = threading.Lock()

    def _build_fernet(self):
        global _FERNET_CACHE
        if self._key_path in _FERNET_CACHE:
            return _FERNET_CACHE[self._key_path]
        from cryptography.fernet import Fernet

        key = _load_or_create_key(self._key_path)
        _FERNET_CACHE[self._key_path] = Fernet(key)
        return _FERNET_CACHE[self._key_path]

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> dict[str, Any]:
        """Decrypt and deserialise the store.  Returns ``{}`` on any error."""
        if not self._store_path.exists():
            return {}
        try:
            mtime = self._store_path.stat().st_mtime
            if self._cache_mtime == mtime:
                return self._cache
            raw = self._store_path.read_bytes()
            plaintext = self._fernet.decrypt(raw)
            self._cache = json.loads(plaintext)
            self._cache_mtime = mtime
            return self._cache
        except Exception as exc:
            logger.error("CredentialManager: CRITICAL — vault corrupted: {}", exc)
            raise RuntimeError(f"Credential vault corrupted: {exc}") from exc

    def _save_all(self, data: dict[str, Any]) -> None:
        """Serialise and encrypt the entire store to disk."""
        try:
            plaintext = json.dumps(data).encode()
            ciphertext = self._fernet.encrypt(plaintext)
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_bytes(ciphertext)
            self._cache = data
            self._cache_mtime = self._store_path.stat().st_mtime
            if platform.system() != "Windows":
                try:
                    os.chmod(self._store_path, 0o600)
                except OSError:
                    pass
            else:
                try:
                    subprocess.run(
                        ["icacls", str(self._store_path), "/inheritance:r", "/grant:r", f"{os.getlogin()}:F"],
                        capture_output=True
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.error("CredentialManager: failed to save store: {}", exc)

    # ------------------------------------------------------------------
    # Admin user management
    # ------------------------------------------------------------------

    def is_setup(self) -> bool:
        """Return ``True`` if an admin user has been registered."""
        data = self._load_all()
        return "admin_user" in data

    def setup_user(self, username: str, password: str) -> bool:
        """Create the single admin user.  Returns ``False`` if already set up."""
        with self._lock:
            data = self._load_all()
            if "admin_user" in data:
                return False

            salt = secrets.token_hex(16)
            hashed = scrypt(
                password.encode(), salt=salt.encode(), n=16384, r=8, p=1,
            ).hex()

            data["admin_user"] = {
                "username": username,
                "password_hash": hashed,
                "salt": salt,
            }
            self._save_all(data)
            logger.info("CredentialManager: admin user '{}' created.", username)
            return True

    def verify_password(self, username: str, password: str) -> bool:
        """Verify *username* / *password* against the stored admin record."""
        data = self._load_all()
        user = data.get("admin_user")
        if not user:
            return False
        if user["username"] != username:
            return False

        salt = user["salt"]
        expected = user["password_hash"]
        actual = scrypt(
            password.encode(), salt=salt.encode(), n=16384, r=8, p=1,
        ).hex()
        return secrets.compare_digest(expected, actual)

    def get_admin_username(self) -> str | None:
        """Return the registered admin username, or ``None``."""
        data = self._load_all()
        user = data.get("admin_user")
        return user["username"] if user else None

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change the admin password.  Returns ``False`` on auth failure."""
        with self._lock:
            if not self.verify_password(username, old_password):
                return False
            data = self._load_all()
            salt = secrets.token_hex(16)
            hashed = scrypt(
                new_password.encode(), salt=salt.encode(), n=16384, r=8, p=1,
            ).hex()
            data["admin_user"]["password_hash"] = hashed
            data["admin_user"]["salt"] = salt
            self._save_all(data)
            logger.info("CredentialManager: password changed for '{}'.", username)
            return True

    # ------------------------------------------------------------------
    # Session tokens
    # ------------------------------------------------------------------

    @staticmethod
    def create_session_token() -> str:
        """Issue a new session token (stored in-memory)."""
        token = secrets.token_hex(32)
        _ACTIVE_SESSIONS[token] = time.time() + _SESSION_TTL_SECONDS
        return token

    @staticmethod
    def verify_session_token(token: str) -> bool:
        """Return ``True`` if *token* is a valid, non-expired session."""
        expiry = _ACTIVE_SESSIONS.get(token)
        if expiry is None:
            return False
        if time.time() >= expiry:
            _ACTIVE_SESSIONS.pop(token, None)
            return False
        return True

    @staticmethod
    def revoke_session_token(token: str) -> None:
        _ACTIVE_SESSIONS.pop(token, None)

    @staticmethod
    def cleanup_expired_sessions() -> int:
        """Remove expired sessions. Returns how many were purged."""
        now = time.time()
        expired = [t for t, exp in _ACTIVE_SESSIONS.items() if now >= exp]
        for t in expired:
            del _ACTIVE_SESSIONS[t]
        return len(expired)

    # ------------------------------------------------------------------
    # Generic secrets (API keys, OAuth, etc.)
    # ------------------------------------------------------------------

    def set_secret(self, namespace: str, key: str, value: Any) -> None:
        """Store a secret value under *namespace* / *key*."""
        with self._lock:
            data = self._load_all()
            data.setdefault("secrets", {}).setdefault(namespace, {})[key] = value
            self._save_all(data)

    def get_secret(self, namespace: str, key: str) -> Any | None:
        """Retrieve a secret, or ``None`` if missing."""
        data = self._load_all()
        return data.get("secrets", {}).get(namespace, {}).get(key)

    def delete_secret(self, namespace: str, key: str) -> None:
        """Delete a single secret."""
        with self._lock:
            data = self._load_all()
            ns = data.get("secrets", {}).get(namespace, {})
            if key in ns:
                del ns[key]
                self._save_all(data)

    def get_namespace(self, namespace: str) -> dict[str, Any]:
        """Return all secrets in *namespace* as a plain dict."""
        data = self._load_all()
        return dict(data.get("secrets", {}).get(namespace, {}))

    def set_namespace(self, namespace: str, payload: dict[str, Any]) -> None:
        """Overwrite an entire namespace."""
        with self._lock:
            data = self._load_all()
            data.setdefault("secrets", {})[namespace] = payload
            self._save_all(data)

    def delete_namespace(self, namespace: str) -> None:
        """Remove an entire namespace."""
        with self._lock:
            data = self._load_all()
            if namespace in data.get("secrets", {}):
                del data["secrets"][namespace]
                self._save_all(data)

    def list_namespaces(self) -> list[str]:
        """List all secret namespaces."""
        data = self._load_all()
        return list(data.get("secrets", {}).keys())


# ======================================================================
# Singleton accessor
# ======================================================================


def get_credential_manager() -> CredentialManager:
    """Return the global ``CredentialManager`` singleton."""
    global _CREDENTIAL_MANAGER_INSTANCE
    if _CREDENTIAL_MANAGER_INSTANCE is None:
        _CREDENTIAL_MANAGER_INSTANCE = CredentialManager()
    return _CREDENTIAL_MANAGER_INSTANCE
