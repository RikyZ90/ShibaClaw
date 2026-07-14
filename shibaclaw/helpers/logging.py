"""Custom logging configuration for ShibaClaw."""

import logging
import os
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentation.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _is_debug_env() -> bool:
    return os.environ.get("SHIBACLAW_DEBUG", "").lower() in ("1", "true", "yes", "on")


class UnicodeSafeStream:
    """Wrapper around sys.stderr/sys.stdout to safely encode unicode characters.
    This prevents UnicodeEncodeError crashes on Windows when printing emojis.
    """
    def __init__(self, stream):
        self.stream = stream
        self.encoding = getattr(stream, "encoding", "utf-8") or "utf-8"

    def write(self, message):
        try:
            self.stream.write(message)
        except UnicodeEncodeError:
            # Fallback to safely replacing invalid characters
            safe_message = message.encode(self.encoding, errors="replace").decode(self.encoding)
            self.stream.write(safe_message)

    def flush(self):
        self.stream.flush()

    def isatty(self):
        if hasattr(self.stream, "isatty"):
            return self.stream.isatty()
        return False

    def __getattr__(self, name):
        return getattr(self.stream, name)


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
        safe_stderr = UnicodeSafeStream(sys.stderr)
        try:
            logger.add(
                safe_stderr,
                format=fmt,
                level=level,
                colorize=True,
                backtrace=debug_mode,
                diagnose=debug_mode,
            )
        except Exception:
            # Fallback to no-color, no-emoji if the above fails
            logger.add(
                safe_stderr,
                format="[{time:HH:mm:ss}] {level: <8} {extra[component]: <7} | {message}",
                level=level,
                colorize=False,
            )

    logger.configure(extra={"component": "System"})

    # Intercept standard logging messages and route them to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    return logger
