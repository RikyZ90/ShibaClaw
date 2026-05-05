"""Custom logging configuration for ShibaClaw."""

import os
import sys

from loguru import logger


def _is_debug_env() -> bool:
    return os.environ.get("SHIBACLAW_DEBUG", "").lower() in ("1", "true", "yes", "on")


def setup_shiba_logging(level: str = "INFO", show_path: bool = False):
    """
    Setup a compact, readable log format for terminal usage.

    Format example:
    [08:00:00] INFO    System | Gateway started
    """
    if _is_debug_env():
        level = "DEBUG"
        show_path = True

    logger.remove()

    fmt = (
        "<blue>{time:HH:mm:ss}</blue> "
        "<level>{level: ^8}</level> "
        "<bold><white>🐾 {extra[component]: <7}</white></bold> "
        "<white>»</white> <level>{message}</level>"
    )

    if show_path:
        fmt += " <dim>({name}:{function}:{line})</dim>"

    debug_mode = level.upper() == "DEBUG"
    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            format=fmt,
            level=level,
            colorize=True,
            backtrace=debug_mode,
            diagnose=debug_mode,
        )

    logger.configure(extra={"component": "System"})
    return logger
