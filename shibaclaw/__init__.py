"""
shibaclaw - An autonomous AI agent framework designed for loyalty and intelligence.
Guided by the spirit of the Shiba, built for the modern age.
"""

import re
from importlib.metadata import PackageNotFoundError, version

try:
    _raw = version("shibaclaw")
    # PEP 440 normalizes "0.0.8a" → "0.0.8a0"; strip trailing 0 on pre-release suffix.
    __version__ = re.sub(r"((?:a|b|rc)\d*?)0$", r"\1", _raw)
except PackageNotFoundError:
    __version__ = "dev"

__logo__ = "🐕‍🦺"
