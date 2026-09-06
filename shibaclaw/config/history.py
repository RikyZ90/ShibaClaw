"""Config change audit log (redacted snapshots)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_HISTORY_NAME = "config_history.jsonl"
_MAX_LINES = 500


def _history_path() -> Path:
    from shibaclaw.config.paths import get_app_root

    return get_app_root() / _HISTORY_NAME


def _redact(obj: Any) -> Any:
    """Recursively mask secret-looking values."""
    secret_keys = {
        "apikey",
        "api_key",
        "token",
        "password",
        "secret",
        "clientsecret",
        "client_secret",
        "privatekey",
        "private_key",
        "access_token",
        "refresh_token",
    }
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_l = str(k).lower().replace("-", "_")
            if key_l in secret_keys or any(s in key_l for s in ("password", "secret", "token", "apikey")):
                if v in (None, "", []):
                    out[k] = v
                else:
                    out[k] = "***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def append_config_history(
    *,
    actor: str = "system",
    reason: str = "save_config",
    data: dict[str, Any] | None = None,
    changed_keys: list[str] | None = None,
) -> None:
    """Append one redacted config-change record."""
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "reason": reason,
            "changed_keys": changed_keys or [],
            "snapshot": _redact(data or {}),
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _trim(path)
    except Exception as e:
        logger.debug("config history append failed: {}", e)


def list_config_history(limit: int = 50) -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, min(limit, 200)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    out.reverse()
    return out


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= _MAX_LINES:
            return
        path.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass
