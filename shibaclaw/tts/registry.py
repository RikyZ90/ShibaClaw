from importlib.metadata import entry_points
from loguru import logger
from shibaclaw.tts.base import BaseTTS

def discover_tts_plugins() -> dict[str, type[BaseTTS]]:
    plugins: dict[str, type[BaseTTS]] = {}
    for ep in entry_points(group="shibaclaw.tts"):
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, BaseTTS):
                plugins[ep.name] = cls
        except Exception as e:
            logger.debug("Failed to load TTS plugin {}: {}", ep.name, e)
    return plugins
