import re
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

def _get_version():
    """Determine the version from pyproject.toml or installed metadata."""
    # 1. Try to read from pyproject.toml if we are in a dev/source environment
    try:
        # Check parent directory of shibaclaw/ (the repo root)
        root_pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if root_pyproject.exists():
            with open(root_pyproject, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version = "):
                        return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass

    # 2. Fallback to installed package metadata
    try:
        _raw = version("shibaclaw")
        # PEP 440 normalizes "0.0.8a" → "0.0.8a0"; strip trailing 0 on pre-release suffix.
        return re.sub(r"((?:a|b|rc)\d*?)0$", r"\1", _raw)
    except PackageNotFoundError:
        return "dev"

__version__ = _get_version()
__logo__ = "🐕‍🦺"
