
from pathlib import Path


def _get_version():
    """Determine the version from pyproject.toml, internal manifest, or installed metadata."""
    # 1. Try to read from pyproject.toml if we are in a dev/source environment
    try:
        root_pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if root_pyproject.exists():
            with open(root_pyproject, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version = "):
                        return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass

    # 2. Try to read from internal update_manifest.json (reliable for bundled EXE)
    try:
        manifest_path = Path(__file__).parent / "updater" / "update_manifest.json"
        if manifest_path.exists():
            import json
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "unknown")
    except Exception:
        pass

    # 3. Fallback to installed package metadata
    try:
        import re
        from importlib.metadata import version
        _raw = version("shibaclaw")
        return re.sub(r"((?:a|b|rc)\d*?)0$", r"\1", _raw)
    except Exception:
        return "dev"

__version__ = _get_version()
__logo__ = "🐕‍🦺"
