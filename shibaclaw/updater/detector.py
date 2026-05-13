"""Runtime and installation detection helpers for the updater."""

from __future__ import annotations

import configparser
import subprocess
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

from shibaclaw import __version__
from shibaclaw.config.paths import get_runtime_root
from shibaclaw.helpers.system import (
    InstallMethod,
    get_installation_method as _system_installation_method,
    get_os_type,
    is_running_as_exe,
    is_running_in_docker,
)

PYPI_PACKAGE = "shibaclaw"
DOCKER_IMAGE = "rikyz90/shibaclaw"
GITHUB_REPO = "RikyZ90/ShibaClaw"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO}"
UPDATE_MANIFEST_ASSET = "update_manifest.json"
WINDOWS_RELEASE_ASSET = "ShibaClaw-windows.zip"
_OFFICIAL_REMOTE_URLS = {
    GITHUB_REPO_URL.lower(),
    f"{GITHUB_REPO_URL}.git".lower(),
    f"git@github.com:{GITHUB_REPO}.git".lower(),
    f"ssh://git@github.com/{GITHUB_REPO}.git".lower(),
}


def get_runtime_root_path() -> Path:
    """Return the root that contains the active ShibaClaw runtime."""
    return get_runtime_root().resolve()


def get_current_version() -> str:
    """Return the current ShibaClaw version string."""
    return __version__


def _looks_like_source_checkout(root: Path) -> bool:
    return (
        (root / "pyproject.toml").exists()
        and (root / "README.md").exists()
        and (root / "shibaclaw" / "__init__.py").exists()
    )


def _has_installed_distribution() -> bool:
    try:
        distribution(PYPI_PACKAGE)
        return True
    except PackageNotFoundError:
        return False
    except Exception:
        return False


def get_installation_method() -> InstallMethod:
    """Detect how ShibaClaw is currently installed.

    The updater treats editable checkouts as ``source`` even when a virtual
    environment is active so update suggestions stay aligned with the code
    location that is actually executing.
    """
    runtime_root = get_runtime_root_path()

    if is_running_as_exe():
        return "exe"
    if is_running_in_docker():
        return "docker"
    if _looks_like_source_checkout(runtime_root):
        return "source"
    if _has_installed_distribution() or _system_installation_method() == "pip":
        return "pip"
    return "source"


def is_git_checkout(root: Path | None = None) -> bool:
    """Return True when the runtime root is backed by a git checkout."""
    runtime_root = (root or get_runtime_root_path()).resolve()
    return (runtime_root / ".git").exists()


def _resolve_git_dir(root: Path) -> Path | None:
    git_marker = root / ".git"
    if git_marker.is_dir():
        return git_marker
    if git_marker.is_file():
        try:
            gitdir = git_marker.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if gitdir.startswith("gitdir:"):
            return (root / gitdir.split(":", 1)[1].strip()).resolve()
    return None


def _run_git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    stdout = completed.stdout.strip()
    return stdout or None


def _read_origin_from_git_config(root: Path) -> str | None:
    git_dir = _resolve_git_dir(root)
    if git_dir is None:
        return None

    config_path = git_dir / "config"
    if not config_path.exists():
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    if parser.has_option('remote "origin"', "url"):
        return parser.get('remote "origin"', "url").strip() or None
    return None


def normalize_git_remote_url(remote_url: str | None) -> str | None:
    """Normalize git remote URLs to a comparable lowercase form."""
    if not remote_url:
        return None

    normalized = remote_url.strip().rstrip("/")
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized.split(":", 1)[1]
    elif normalized.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + normalized[len("ssh://git@github.com/") :]

    return normalized.lower()


def get_git_remote_url(root: Path | None = None) -> str | None:
    """Return the checkout origin URL when one can be determined."""
    runtime_root = (root or get_runtime_root_path()).resolve()
    remote_url = _run_git(runtime_root, "remote", "get-url", "origin")
    if remote_url:
        return remote_url
    return _read_origin_from_git_config(runtime_root)


def is_official_repo_checkout(root: Path | None = None) -> bool:
    """Return True when the active source checkout points to the official repo."""
    normalized = normalize_git_remote_url(get_git_remote_url(root))
    return normalized in _OFFICIAL_REMOTE_URLS


def get_runtime_metadata(root: Path | None = None) -> dict[str, Any]:
    """Return updater-relevant runtime metadata."""
    runtime_root = (root or get_runtime_root_path()).resolve()
    remote_url = get_git_remote_url(runtime_root)
    return {
        "install_method": get_installation_method(),
        "current_version": get_current_version(),
        "os_type": get_os_type(),
        "runtime_root": str(runtime_root),
        "is_frozen": is_running_as_exe(),
        "is_git_checkout": is_git_checkout(runtime_root),
        "git_remote_url": remote_url,
        "is_official_checkout": is_official_repo_checkout(runtime_root),
    }


__all__ = [
    "DOCKER_IMAGE",
    "GITHUB_REPO",
    "GITHUB_REPO_URL",
    "PYPI_PACKAGE",
    "UPDATE_MANIFEST_ASSET",
    "WINDOWS_RELEASE_ASSET",
    "get_current_version",
    "get_git_remote_url",
    "get_installation_method",
    "get_runtime_metadata",
    "get_runtime_root_path",
    "is_git_checkout",
    "is_official_repo_checkout",
    "normalize_git_remote_url",
]
