"""Check GitHub releases for a newer version."""

from __future__ import annotations
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

from shibaclaw import __version__

GITHUB_REPO = "RikyZ90/ShibaClaw"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_CACHE_TTL = 3600
_CACHE_FILE = Path.home() / ".shibaclaw" / "update_cache.json"


def _load_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if data.get("current") != __version__:
                return {}
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


def _parse_version(v: str) -> tuple:
    v = v.lstrip("v")
    m = re.match(r'^(\d+(?:\.\d+)*)\s*[-.]?\s*(a|alpha|b|beta|rc)?(\d*)\s*$', v, re.IGNORECASE)
    if not m:
        nums = re.findall(r'\d+', v)
        return tuple(int(n) for n in nums) + (3, 0) if nums else (0, 3, 0)
    numeric = tuple(int(x) for x in m.group(1).split('.'))
    suffix = (m.group(2) or '').lower()
    suffix_num = int(m.group(3)) if m.group(3) else 0
    _PRE_ORDER = {'a': 0, 'alpha': 0, 'b': 1, 'beta': 1, 'rc': 2}
    if suffix in _PRE_ORDER:
        return numeric + (_PRE_ORDER[suffix], suffix_num)
    return numeric + (3, 0)


def check_for_update(force: bool = False) -> dict[str, Any]:
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
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except Exception:
        pass