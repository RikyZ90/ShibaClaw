"""Auto-discovery for built-in channel modules and external plugins."""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from shibaclaw.integrations.base import BaseChannel

_INTERNAL = frozenset({"base", "manager", "registry"})


def discover_channel_names() -> list[str]:
    """Return all built-in channel module names by scanning the package (zero imports)."""
    import shibaclaw.integrations as pkg

    return [
        name
        for _, name, ispkg in pkgutil.iter_modules(pkg.__path__)
        if name not in _INTERNAL and not ispkg
    ]


def load_channel_class(module_name: str) -> type[BaseChannel]:
    """Import *module_name* and return the first BaseChannel subclass found."""
    from shibaclaw.integrations.base import BaseChannel as _Base

    mod = importlib.import_module(f"shibaclaw.integrations.{module_name}")
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, _Base) and obj is not _Base:
            return obj
    raise ImportError(f"No BaseChannel subclass in shibaclaw.integrations.{module_name}")


def discover_plugins() -> dict[str, type[BaseChannel]]:
    """Discover external channel plugins registered via entry_points."""
    from importlib.metadata import entry_points

    plugins: dict[str, type[BaseChannel]] = {}
    for ep in entry_points(group="shibaclaw.integrations"):
        try:
            cls = ep.load()
            plugins[ep.name] = cls
        except Exception:
            pass
    return plugins


def discover_local_plugins() -> dict[str, type[BaseChannel]]:
    """Discover local plugins stored in the user's plugins directory."""
    import sys
    from shibaclaw.config.paths import get_plugins_dir
    from shibaclaw.integrations.base import BaseChannel as _Base

    plugins_dir = get_plugins_dir()
    if str(plugins_dir) not in sys.path:
        sys.path.insert(0, str(plugins_dir))

    plugins: dict[str, type[BaseChannel]] = {}
    if not plugins_dir.exists():
        return plugins

    for _, name, ispkg in pkgutil.iter_modules([str(plugins_dir)]):
        if not ispkg:
            continue
        try:
            mod = importlib.import_module(name)
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and issubclass(obj, _Base) and obj is not _Base:
                    # Strip 'shibaclaw-channel-' prefix if it exists to get the short name
                    short_name = name.replace("shibaclaw-channel-", "").replace("shibaclaw_", "")
                    plugins[short_name] = obj
                    break
        except Exception as e:
            logger.debug("Failed to load local plugin {}: {}", name, e)

    return plugins


def discover_all() -> dict[str, type[BaseChannel]]:
    """Return all channels: built-in (pkgutil) merged with external (entry_points).

    Built-in channels take priority — an external plugin cannot shadow a built-in name.
    """
    builtin: dict[str, type[BaseChannel]] = {}
    for modname in discover_channel_names():
        try:
            builtin[modname] = load_channel_class(modname)
        except ImportError as e:
            logger.debug("Channel '{}' not loadable: {}", modname, e)

    external = discover_plugins()
    local = discover_local_plugins()
    
    # Merge external and local, with local overriding external if duplicated
    all_external = {**external, **local}
    
    shadowed = set(all_external) & set(builtin)
    if shadowed:
        logger.warning("Plugin(s) shadowed by built-in channels (ignored): {}", shadowed)

    return {**all_external, **builtin}
