from importlib.metadata import entry_points
from loguru import logger
from shibaclaw.tts.base import BaseTTS

def discover_local_tts_plugins() -> dict[str, type[BaseTTS]]:
    """Discover local TTS plugins stored in the user's plugins directory."""
    import sys
    import pkgutil
    import importlib
    from shibaclaw.config.paths import get_plugins_dir

    plugins_dir = get_plugins_dir()
    if str(plugins_dir) not in sys.path:
        sys.path.insert(0, str(plugins_dir))

    plugins: dict[str, type[BaseTTS]] = {}
    if not plugins_dir.exists():
        return plugins

    for _, name, ispkg in pkgutil.iter_modules([str(plugins_dir)]):
        if not ispkg:
            continue
        try:
            mod = importlib.import_module(name)
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and issubclass(obj, BaseTTS) and obj is not BaseTTS:
                    short_name = name.replace("shibaclaw_tts_", "").replace("shibaclaw_", "")
                    plugins[short_name] = obj
                    break
        except Exception as e:
            logger.debug("Failed to load local TTS plugin {}: {}", name, e)

    return plugins


def discover_tts_plugins() -> dict[str, type[BaseTTS]]:
    plugins: dict[str, type[BaseTTS]] = {}
    for ep in entry_points(group="shibaclaw.tts"):
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, BaseTTS):
                plugins[ep.name] = cls
        except Exception as e:
            logger.debug("Failed to load TTS plugin {}: {}", ep.name, e)
            
    local_plugins = discover_local_tts_plugins()
    return {**plugins, **local_plugins}
