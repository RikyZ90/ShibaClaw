import io
import sys

# Force UTF-8 encoding for standard streams to prevent crashes on Windows when printing emojis
if sys.platform == "win32":
    try:
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass

from shibaclaw.cli.commands import app

if __name__ == "__main__":
    app()
