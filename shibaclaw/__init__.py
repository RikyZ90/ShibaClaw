"""
shibaclaw - An autonomous AI agent framework designed for loyalty and intelligence.
Guided by the spirit of the Shiba, built for the modern age.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("shibaclaw")
except PackageNotFoundError:
    __version__ = "dev"

__logo__ = "🐕‍🦺"
