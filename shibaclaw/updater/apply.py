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
from shibaclaw.config.paths import get_app_root


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

    success = result.returncode == 0
    if success:
        from shibaclaw.updater.checker import invalidate_cache
        invalidate_cache()
        
    return {
        "ok": success,
        "output": result.stdout + result.stderr,
        "command": " ".join(cmd),
    }


def _exe_upgrade(version: str, download_url: str, progress_cb: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Download the Windows release, extract it, and execute a replacement batch script."""
    import zipfile
    import os

    if not download_url:
        return {"ok": False, "output": "No download URL provided for EXE update."}

    temp_dir = get_app_root() / "_update_temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = temp_dir / "update.zip"
    
    try:
        with httpx.stream("GET", download_url, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total_bytes:
                        progress_cb(downloaded, total_bytes)
                        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)
            
        extracted_exe_path = None
        for root, dirs, files in os.walk(temp_dir):
            if "ShibaClaw.exe" in files:
                extracted_exe_path = Path(root)
                break
                
        if not extracted_exe_path:
            return {"ok": False, "output": "ShibaClaw.exe not found in downloaded zip."}
            
        current_exe_dir = Path(sys.executable).parent
        
        needs_admin = False
        test_file = current_exe_dir / ".update_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            needs_admin = True
        except Exception:
            pass
            
        import tempfile
        import time
        bat_path = Path(tempfile.gettempdir()) / f"shibaclaw_update_{int(time.time())}.bat"
        
        bat_content = [
            "@echo off",
        ]
        
        if needs_admin:
            bat_content.extend([
                "net session >nul 2>&1",
                "if %errorLevel% neq 0 (",
                "    powershell -Command \"Start-Process '%~f0' -Verb RunAs\"",
                "    exit /b",
                ")"
            ])
            
        bat_content.extend([
            "timeout /t 8 /nobreak",
            "set /a retry=0",
            ":loop",
            f'xcopy /S /Y /E /I "{extracted_exe_path}\\*" "{current_exe_dir}\\" >nul 2>&1',
            "if %errorlevel% neq 0 (",
            "    set /a retry+=1",
            "    if %retry% lss 15 (",
            "        timeout /t 1 /nobreak >nul",
            "        goto loop",
            "    )",
            ")",
            f'rmdir /S /Q "{temp_dir}"',
            f'start "" "{current_exe_dir}\\ShibaClaw.exe"',
            'del "%~f0"'
        ])
        
        bat_path.write_text("\n".join(bat_content), encoding="utf-8")
        
        detached_process = 0x00000008
        create_new_process_group = 0x00000200
        subprocess.Popen(
            [str(bat_path)],
            creationflags=detached_process | create_new_process_group,
            close_fds=True,
            cwd=tempfile.gettempdir()
        )
        
        return {"ok": True, "output": "Update downloaded, batch script started."}
    except Exception as exc:
        return {"ok": False, "output": f"Update failed: {exc}"}


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
    
    if install_method == "pip" or install_method == "exe":
        normalized.setdefault("action_kind", "automatic")
    else:
        normalized.setdefault("action_kind", "manual-command")
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
