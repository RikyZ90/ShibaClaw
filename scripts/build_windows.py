"""Build the portable Windows desktop bundle with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PKG_RESOURCES_WARNING_FILTER = (
    "ignore:pkg_resources is deprecated as an API:UserWarning"
)


def _sync_packaged_update_manifest() -> None:
    """Keep the bundled updater manifest in sync with the repo root manifest."""
    source_manifest = ROOT / "update_manifest.json"
    packaged_manifest = ROOT / "shibaclaw" / "updater" / "update_manifest.json"

    if source_manifest.exists():
        packaged_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_manifest, packaged_manifest)


def _check_build_environment() -> None:
    if sys.version_info >= (3, 14):
        raise SystemExit(
            "Windows desktop packaging currently requires Python 3.12 or 3.13. "
            "pywebview/pythonnet is not yet building cleanly on Python 3.14."
        )

    missing = []
    for module_name in ("PyInstaller", "PIL", "pystray", "webview"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)

    if missing:
        raise SystemExit(
            "Missing desktop build dependencies: "
            + ", ".join(missing)
            + ". Install them with: pip install -e \".[windows-native,dev]\""
        )


def main() -> None:
    _check_build_environment()
    _sync_packaged_update_manifest()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_icons.py")], check=True, cwd=ROOT)

    pyinstaller_env = os.environ.copy()
    current_filters = pyinstaller_env.get("PYTHONWARNINGS", "")
    if _PKG_RESOURCES_WARNING_FILTER not in current_filters:
        pyinstaller_env["PYTHONWARNINGS"] = (
            f"{_PKG_RESOURCES_WARNING_FILTER},{current_filters}"
            if current_filters
            else _PKG_RESOURCES_WARNING_FILTER
        )

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(ROOT / "shibaclaw.spec"), "--noconfirm", "--clean"],
        check=True,
        cwd=ROOT,
        env=pyinstaller_env,
    )


if __name__ == "__main__":
    main()
