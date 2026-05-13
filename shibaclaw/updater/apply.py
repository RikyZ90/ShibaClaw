"""Apply a ShibaClaw update using the normalized updater contract."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from shibaclaw.updater.detector import PYPI_PACKAGE, get_installation_method
from shibaclaw.updater.manifest import normalize_manifest_path


def _old_dir(workspace_root: Path, new_version: str) -> Path:
    """Return the _old/<version>/ directory inside the workspace root."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = workspace_root / "_old" / f"{date_str}_{new_version}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _pip_upgrade(version: str | None) -> dict[str, Any]:
    """Run a pip upgrade for the requested ShibaClaw version."""
    target = f"{PYPI_PACKAGE}=={version}" if version else PYPI_PACKAGE
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", target]
    if Path("/.dockerenv").exists():
        cmd.insert(-1, "--user")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "output": str(exc), "command": " ".join(cmd)}

    return {
        "ok": result.returncode == 0,
        "output": result.stdout + result.stderr,
        "command": " ".join(cmd),
    }


def _backup_personal_files(
    manifest: dict[str, Any] | None,
    workspace_root: Path,
    version: str,
) -> dict[str, Any]:
    """Copy personal files (overwrite=False) to _old/ before applying an update."""
    if not manifest:
        return {"moved": [], "skipped": []}

    old_dir = _old_dir(workspace_root, version or "unknown")
    moved: list[dict[str, str]] = []
    skipped: list[str] = []

    for change in manifest.get("changes", []):
        rel_path = normalize_manifest_path(change.get("path", ""))
        overwrite = change.get("overwrite", True)
        if not rel_path or overwrite:
            if rel_path:
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


def _normalize_update_request(
    update_info: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = dict(update_info or {})
    install_method = normalized.get("install_method") or get_installation_method()
    latest = normalized.get("latest") or (manifest or {}).get("version")

    normalized.setdefault("install_method", install_method)
    normalized.setdefault("latest", latest)
    normalized.setdefault("action_kind", "automatic" if install_method == "pip" else "manual-command")
    normalized.setdefault(
        "action_label",
        "Update now" if install_method == "pip" else "Run suggested update command",
    )
    normalized.setdefault(
        "action_command",
        "pip install --upgrade shibaclaw"
        if install_method == "pip"
        else "git pull --ff-only && pip install -e .",
    )
    return normalized


def _manual_report(update_info: dict[str, Any], version: str) -> dict[str, Any]:
    install_method = update_info.get("install_method") or "source"
    action_target = update_info.get("action_command") or update_info.get("action_url")
    message = update_info.get("summary") or "This update must be applied manually."
    if action_target:
        message = f"{message} Suggested action: {action_target}"

    return {
        "install_method": install_method,
        "version": version,
        "requires_manual_action": True,
        "restarting": False,
        "action_kind": update_info.get("action_kind"),
        "action_label": update_info.get("action_label"),
        "action_command": update_info.get("action_command"),
        "action_url": update_info.get("action_url") or update_info.get("release_url"),
        "message": message,
        "backup": {"moved": [], "skipped": []},
        "pip": None,
    }


def apply_update(
    update_info: dict[str, Any] | None,
    workspace_root: Path,
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply an update or return a manual-action report for non-pip installs."""
    normalized = _normalize_update_request(update_info, manifest)
    install_method = normalized["install_method"]
    version = normalized.get("latest") or (manifest or {}).get("version") or "unknown"

    if install_method != "pip" or normalized.get("action_kind") != "automatic":
        return _manual_report(normalized, version)

    backup = _backup_personal_files(manifest, workspace_root, version)
    pip_result = _pip_upgrade(version)
    message = (
        f"Updated ShibaClaw to {version}."
        if pip_result.get("ok")
        else f"Failed to update ShibaClaw to {version}."
    )

    return {
        "install_method": install_method,
        "version": version,
        "requires_manual_action": False,
        "restarting": False,
        "action_kind": normalized.get("action_kind"),
        "action_label": normalized.get("action_label"),
        "action_command": normalized.get("action_command"),
        "action_url": normalized.get("action_url") or normalized.get("release_url"),
        "message": message,
        "pip": pip_result,
        "backup": backup,
    }
