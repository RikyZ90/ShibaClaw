
import importlib.metadata as importlib_metadata
import json
import re
import sys
import tomllib
from pathlib import Path


_PACKAGE_NAME = "shibaclaw"


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _runtime_root() -> Path:
    return _package_dir().parent


def _looks_like_source_checkout(root: Path) -> bool:
    return (
        (root / "pyproject.toml").exists()
        and (root / "README.md").exists()
        and (root / "shibaclaw" / "__init__.py").exists()
    )


def _read_pyproject_version(root: Path) -> str | None:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    version_value = (data.get("project") or {}).get("version")
    if not version_value:
        return None
    return str(version_value).strip() or None


def _read_manifest_version(package_dir: Path) -> str | None:
    manifest_path = package_dir / "updater" / "update_manifest.json"
    if not manifest_path.exists():
        return None

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version_value = data.get("version")
    if not version_value:
        return None
    return str(version_value).strip() or None


def _read_installed_metadata_version() -> str | None:
    try:
        raw_version = importlib_metadata.version(_PACKAGE_NAME)
    except importlib_metadata.PackageNotFoundError:
        return None
    except Exception:
        return None

    return re.sub(r"((?:a|b|rc)\d*?)0$", r"\1", raw_version)


def _get_version():
    """Determine the version from the active source checkout, metadata, or bundle manifest."""
    package_dir = _package_dir()
    runtime_root = _runtime_root()

    if getattr(sys, "frozen", False):
        return _read_manifest_version(package_dir) or _read_installed_metadata_version() or "dev"

    if _looks_like_source_checkout(runtime_root):
        return (
            _read_pyproject_version(runtime_root)
            or _read_installed_metadata_version()
            or _read_manifest_version(package_dir)
            or "dev"
        )

    return (
        _read_installed_metadata_version()
        or _read_manifest_version(package_dir)
        or _read_pyproject_version(runtime_root)
        or "dev"
    )

__version__ = _get_version()
__logo__ = "🐕‍🦺"
