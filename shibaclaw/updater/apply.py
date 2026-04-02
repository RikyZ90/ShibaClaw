"""Apply a ShibaClaw update: pip upgrade + backup personal files to _old/<version>/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _old_dir(workspace_root: Path, new_version: str) -> Path:
    """Return the _old/<version>/ directory inside the workspace root."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = workspace_root / "_old" / f"{date_str}_{new_version}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _pip_upgrade(version: str) -> dict[str, Any]:
    """Run pip install --upgrade shibaclaw==<version>.

    Uses --user when running inside a container (detected via /.dockerenv)
    so the upgrade persists on the mounted volume.
    Returns {"ok": bool, "output": str}.
    """
    target = f"shibaclaw=={version}" if version else "shibaclaw"
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", target]
    if Path("/.dockerenv").exists():
        cmd.insert(-1, "--user")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "ok": result.returncode == 0,
            "output": result.stdout + result.stderr,
        }
    except Exception as e:
        return {"ok": False, "output": str(e)}


def _backup_personal_files(
    manifest: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    """Move personal files (overwrite=False) to _old/ so the user keeps a backup.

    Only files that actually exist on disk are moved.
    Returns {"moved": [...], "skipped": [...]}.
    """
    new_version = manifest.get("version", "unknown")
    old_dir = _old_dir(workspace_root, new_version)

    moved: list[dict[str, str]] = []
    skipped: list[str] = []

    for change in manifest.get("changes", []):
        rel_path: str = change.get("path", "")
        overwrite: bool = change.get("overwrite", True)

        if not rel_path:
            continue

        # Personal files are those NOT overwritten — we back them up
        # so if the new version ships a new default, the user still has theirs.
        if overwrite:
            skipped.append(rel_path)
            continue

        local_file = workspace_root / rel_path
        if not local_file.exists():
            skipped.append(rel_path)
            continue

        dest = old_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(local_file), str(dest))
        moved.append({"from": str(local_file), "to": str(dest)})

    return {"moved": moved, "skipped": skipped}


def apply_update(
    manifest: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    """
    Apply update in two steps:

    1. Backup personal files (overwrite=False in manifest) to _old/<version>/
    2. Run pip install --upgrade shibaclaw==<version>

    Returns a report dict:
        {
            "pip": {"ok": bool, "output": str},
            "backup": {"moved": [...], "skipped": [...]},
            "version": str,
        }
    """
    new_version = manifest.get("version", "unknown")

    # Step 1: backup personal files before pip potentially overwrites defaults
    backup = _backup_personal_files(manifest, workspace_root)

    # Step 2: pip upgrade
    pip_result = _pip_upgrade(new_version)

    return {
        "version": new_version,
        "pip": pip_result,
        "backup": backup,
    }
