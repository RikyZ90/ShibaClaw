"""Download and parse an update manifest attached to a GitHub release."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from shibaclaw import __version__


def fetch_manifest(manifest_url: str) -> dict[str, Any]:
    """
    Download and return the parsed update_manifest.json from a release asset URL.

    Expected manifest shape:
    {
        "version": "0.0.12",
        "release_notes": "Short human-readable summary...",
        "changes": [
            {
                "path": "USER.md",
                "overwrite": true,
                "note": "Added Language Preferences section"
            },
            {
                "path": "skills/memory/SKILL.md",
                "overwrite": true
            }
        ]
    }
    """
    req = urllib.request.Request(
        manifest_url,
        headers={"User-Agent": f"ShibaClaw/{__version__}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_manifest_path(path: str) -> str:
    """Normalize manifest paths to workspace-relative form."""
    normalized = (path or "").replace("\\", "/").lstrip("./")
    prefixes = (
        ("shibaclaw/templates/memory/", "memory/"),
        ("templates/memory/", "memory/"),
        ("shibaclaw/templates/", ""),
        ("templates/", ""),
        ("shibaclaw/", ""),
    )
    for prefix, replacement in prefixes:
        if normalized.startswith(prefix):
            return replacement + normalized[len(prefix):]
    return normalized


def personal_files_in_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only the changes that involve personal/template files requiring user attention."""
    _PERSONAL_PATHS = {
        "USER.md",
        "SOUL.md",
        "AGENTS.md",
        "HEARTBEAT.md",
        "TOOLS.md",
        "memory/MEMORY.md",
        "memory/HISTORY.md",
    }
    result = []
    for change in manifest.get("changes", []):
        path = normalize_manifest_path(change.get("path", ""))
        is_skill = path.startswith("skills/") and path.endswith("SKILL.md")
        if path in _PERSONAL_PATHS or is_skill:
            result.append({**change, "path": path})
    return result
