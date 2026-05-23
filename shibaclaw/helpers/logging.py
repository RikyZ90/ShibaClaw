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

    # Detect if the output stream supports Unicode (emojis)
    supports_unicode = False
    try:
        # sys.stderr.encoding might be None or unreliable in some environments
        # but rich and loguru usually handle this. We check for UTF-8 or similar.
        encoding = getattr(sys.stderr, "encoding", "") or ""
        if encoding.lower() in ("utf-8", "utf8", "cp65001"):
            supports_unicode = True
    except Exception:
        pass

    shiba_icon = "🐾" if supports_unicode else ">>"
    sep_icon = "»" if supports_unicode else ">"

    fmt = (
        "<blue>{time:HH:mm:ss}</blue> "
        "<level>{level: ^8}</level> "
        f"<bold><white>{shiba_icon} {{extra[component]: <7}}</white></bold> "
        f"<white>{sep_icon}</white> <level>{{message}}</level>"
    )

    if show_path:
        fmt += " <dim>({name}:{function}:{line})</dim>"

    debug_mode = level.upper() == "DEBUG"
    if sys.stderr is not None:
        try:
            logger.add(
                sys.stderr,
                format=fmt,
                level=level,
                colorize=True,
                backtrace=debug_mode,
                diagnose=debug_mode,
            )
        except Exception:
            # Fallback to no-color, no-emoji if the above fails
            logger.add(
                sys.stderr,
                format="[{time:HH:mm:ss}] {level: <8} {extra[component]: <7} | {message}",
                level=level,
                colorize=False,
            )

    logger.configure(extra={"component": "System"})
    return logger
