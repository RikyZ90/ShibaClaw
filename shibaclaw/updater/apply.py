"""Apply a ShibaClaw update using the normalized updater contract."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx
from shibaclaw.updater.detector import PYPI_PACKAGE, get_installation_method
from shibaclaw.updater.manifest import normalize_manifest_path


def _old_dir(workspace_root: Path, new_version: str) -> Path:
    """Return the _old/<version>/ directory inside the workspace root."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = workspace_root / "_old" / f"{date_str}_{new_version}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _get_exe_install_dir() -> Path | None:
    """Return the .shibaclaw install root by walking up from sys.executable.

    Expected layout:  <install_dir>/.shibaclaw/app/ShibaClaw/ShibaClaw.exe
    We walk upward from the exe directory looking for a parent whose name is
    '.shibaclaw'.  If not found we fall back to $HOME/.shibaclaw so that
    install.ps1 always receives an explicit -InstallDir argument.
    """
    try:
        exe_path = Path(sys.executable).resolve()
        # Walk up at most 6 levels to find a directory named ".shibaclaw"
        candidate = exe_path.parent
        for _ in range(6):
            if candidate.name.lower() == ".shibaclaw":
                return candidate
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
    except Exception:
        pass

    # Fallback: use the standard default location
    try:
        return Path.home() / ".shibaclaw"
    except Exception:
        return None


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
            timeout=600,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "output": str(exc), "command": " ".join(cmd)}

    success = result.returncode == 0
    if success:
        from shibaclaw.updater.checker import invalidate_cache
        invalidate_cache()

    return {
        "ok": success,
        "output": result.stdout + result.stderr,
        "command": " ".join(cmd),
    }


def _exe_upgrade(
    version: str,
    download_url: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    import tempfile
    from shibaclaw.config.paths import get_runtime_root

    if not download_url:
        return {"ok": False, "output": "No download URL provided."}

    installer_url = (
        "https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/scripts/install/install.ps1"
    )
    temp_ps1 = Path(tempfile.gettempdir()) / f"shibaclaw_install_{version}.ps1"

    downloaded = False
    try:
        with httpx.Client(follow_redirects=True, timeout=15.0) as client:
            response = client.get(installer_url)
            response.raise_for_status()
            temp_ps1.write_text(response.text, encoding="utf-8")
            downloaded = True
    except Exception:
        pass

    if not downloaded:
        bundled_ps1 = get_runtime_root() / "scripts" / "install" / "install.ps1"
        if bundled_ps1.exists():
            try:
                shutil.copy2(str(bundled_ps1), str(temp_ps1))
                downloaded = True
            except Exception:
                pass

    if not downloaded:
        return {"ok": False, "output": "Could not download or locate install.ps1 script."}

    zip_path = Path(tempfile.gettempdir()) / f"shibaclaw_release_{version}.zip"
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            with client.stream("GET", download_url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                current = 0
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        current += len(chunk)
                        if progress_cb:
                            try:
                                progress_cb(current, total)
                            except Exception:
                                pass
    except Exception as exc:
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
        return {"ok": False, "output": f"Failed to download update package: {exc}"}

    # Resolve install_dir robustly — always pass it explicitly to the PS1 script
    install_dir = _get_exe_install_dir()
    install_dir_str = str(install_dir) if install_dir else ""

    try:
        detached_process = 0x00000008
        create_new_process_group = 0x00000200

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(temp_ps1),
            "-Version", version,
            "-LocalZipPath", str(zip_path),
        ]

        if install_dir_str:
            cmd.extend(["-InstallDir", install_dir_str])

        subprocess.Popen(
            cmd,
            creationflags=detached_process | create_new_process_group,
            close_fds=True,
            cwd=tempfile.gettempdir(),
        )

        from loguru import logger
        logger.info(
            "exe updater: launched installer for v{} | install_dir={} | cmd={}",
            version,
            install_dir_str or "(not passed)",
            " ".join(cmd),
        )

        return {"ok": True, "output": "Installer script launched successfully."}
    except Exception as exc:
        return {"ok": False, "output": f"Failed to launch installer: {exc}"}


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

    if install_method in ("pip", "exe"):
        normalized.setdefault("action_kind", "automatic")
    else:
        normalized.setdefault("action_kind", "manual-command")
    normalized.setdefault(
        "action_label",
        "Update now" if install_method in ("pip", "exe") else "Run suggested update command",
    )

    default_cmd = "git pull --ff-only && pip install -e ."
    if install_method == "pip":
        default_cmd = "pip install --upgrade shibaclaw"
    elif install_method == "exe":
        default_cmd = (
            'powershell -c "irm https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/scripts/install/install.ps1 | iex"'
        )

    normalized.setdefault("action_command", default_cmd)
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
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Apply an update or return a manual-action report for non-pip/non-exe installs."""
    normalized = _normalize_update_request(update_info, manifest)
    install_method = normalized["install_method"]
    version = normalized.get("latest") or (manifest or {}).get("version") or "unknown"

    if install_method not in ("pip", "exe") or normalized.get("action_kind") != "automatic":
        return _manual_report(normalized, version)

    backup = _backup_personal_files(manifest, workspace_root, version)

    if install_method == "exe":
        download_url = normalized.get("action_url") or normalized.get("download_url")
        apply_result = _exe_upgrade(version, download_url, progress_cb)
    else:
        apply_result = _pip_upgrade(version)

    message = (
        f"Updated ShibaClaw to {version}."
        if apply_result.get("ok")
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
        "pip": apply_result if install_method == "pip" else None,
        "exe": apply_result if install_method == "exe" else None,
        "backup": backup,
    }
