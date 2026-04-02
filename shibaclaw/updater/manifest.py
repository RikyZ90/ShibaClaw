"""Download and parse an update manifest attached to a GitHub release."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

from shibaclaw import __version__


def fetch_manifest(manifest_url: str) -> dict[str, Any]:
    """
    Download and return the parsed update_manifest.json from a release asset URL.

    Expected manifest shape:
    {
        "version": "0.0.8",
        "from_version": "0.0.7",
        "release_notes": "Short human-readable summary...",
        "changes": [
            {
                "path": "shibaclaw/templates/USER.md",
                "overwrite": true,
                "note": "Added Language Preferences section"
            },
            {
                "path": "shibaclaw/agent/loop.py",
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


def personal_files_in_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only the changes that involve personal/template files requiring user attention."""
    _PERSONAL_PATHS = {
        "shibaclaw/templates/USER.md",
        "shibaclaw/templates/SOUL.md",
        "shibaclaw/templates/AGENTS.md",
        "shibaclaw/templates/HEARTBEAT.md",
        "shibaclaw/templates/TOOLS.md",
        "shibaclaw/templates/memory/MEMORY.md",
    }
    result = []
    for change in manifest.get("changes", []):
        path = change.get("path", "")
        # Skill SKILL.md files are also personal
        is_skill = path.startswith("shibaclaw/skills/") and path.endswith("SKILL.md")
        if path in _PERSONAL_PATHS or is_skill:
            result.append(change)
    return result
