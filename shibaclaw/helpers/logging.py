"""Custom logging configuration for ShibaClaw."""

import sys

from loguru import logger


def setup_shiba_logging(level: str = "INFO", show_path: bool = False):
    """
    Setup a compact, readable log format for terminal usage.

    Format example:
    [08:00:00] INFO    System | Gateway started
    """
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
