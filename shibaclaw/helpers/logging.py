"""Custom logging configuration for ShibaClaw."""

import sys
from loguru import logger

def setup_shiba_logging(level: str = "INFO", show_path: bool = False):
    """
    Setup a branded ShibaClaw logging format.
    
    Format example:
    [🐾 ShibaClaw] [08:00:00] [INFO] [Brain] >> Following the scent...
    """
    logger.remove()  # Remove default sink
    
    # Custom format with Shiba flair
    # component is passed via logger.bind(component="...")
    fmt = (
        "<white>[</white><yellow>🐾 ShibaClaw</yellow><white>]</white> "
        "<white>[</white><blue>{time:HH:mm:ss}</blue><white>]</white> "
        "<white>[</white><level>{level: <7}</level><white>]</white> "
        "<white>[</white><cyan>{extra[component]}</cyan><white>]</white> "
        " <bold>>></bold> <level>{message}</level>"
    )
    
    if show_path:
        fmt += " <dim>({name}:{function}:{line})</dim>"

    logger.add(
        sys.stderr,
        format=fmt,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # Default binding to avoid KeyError
    logger.configure(extra={"component": "System"})
    
    return logger
