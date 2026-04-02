"""Check GitHub releases for a newer version of ShibaClaw."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from shibaclaw import __version__

GITHUB_REPO = "RikyZ90/ShibaClaw"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_CACHE_TTL = 3600  # seconds — re-check at most once per hour
_CACHE_FILE = Path.home() / ".shibaclaw" / "update_cache.json"


def _load_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - data.get("checked_at", 0) < _CACHE_TTL:
                return data
    except Exception:
        pass
    return {}


def _save_cache(data: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _parse_version(v: str) -> tuple[int, ...]:
    """Convert 'v1.2.3', '1.2.3a', '1.2.3-beta' etc. to (1, 2, 3) for comparison.

    Only the leading numeric part of each segment is used, so pre-release
    suffixes like 'a', 'b', 'rc1' are stripped. This means:
      0.0.7a  == 0.0.7   (no update triggered)
      0.0.8a  >  0.0.7   (update triggered)
    """
    v = v.lstrip("v")
    parts = re.split(r"[.\-]", v)
    result = []
    for p in parts:
        m = re.match(r"^(\d+)", p)
        if m:
            result.append(int(m.group(1)))
    return tuple(result) if result else (0,)


def check_for_update(force: bool = False) -> dict[str, Any]:
    """
    Check GitHub for the latest release.

    Returns a dict:
        {
            "current": "0.0.7",
            "latest": "0.0.8",
            "update_available": True,
            "release_url": "https://github.com/...",
            "manifest_url": "https://.../update_manifest.json",  # or None
            "checked_at": 1234567890,
            "error": None,
        }
    """
    if not force:
        cached = _load_cache()
        if cached:
            return cached

    result: dict[str, Any] = {
        "current": __version__,
        "latest": __version__,
        "update_available": False,
        "release_url": None,
        "manifest_url": None,
        "checked_at": int(time.time()),
        "error": None,
    }

    try:
        req = urllib.request.Request(
            _API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"ShibaClaw/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        release_url = data.get("html_url", "")
        assets = data.get("assets", [])

        manifest_url = next(
            (a["browser_download_url"] for a in assets if a.get("name") == "update_manifest.json"),
            None,
        )

        result["latest"] = tag.lstrip("v")
        result["release_url"] = release_url
        result["manifest_url"] = manifest_url
        result["update_available"] = _parse_version(tag) > _parse_version(__version__)

    except urllib.error.URLError as e:
        result["error"] = f"Network error: {e.reason}"
    except Exception as e:
        result["error"] = str(e)

    _save_cache(result)
    return result


def invalidate_cache() -> None:
    """Remove the cached check result so the next call hits GitHub."""
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except Exception:
        pass
