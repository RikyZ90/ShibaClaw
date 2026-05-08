"""Entry point for the packaged or pip-installed ShibaClaw desktop app."""

from __future__ import annotations

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

from shibaclaw.helpers.logging import setup_shiba_logging


def _show_startup_error(message: str) -> None:
    """Show a visible startup error, even for GUI script launches on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "ShibaClaw Desktop", 0x10)
            return
        except Exception:
            pass

    if sys.stderr is not None:
        try:
            print(message, file=sys.stderr)
        except Exception:
            pass


def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()

    # Intercept subprocess calls (e.g. gateway) when bundled by PyInstaller
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify-desktop":
        import webview  # noqa: F401
        import clr_loader  # noqa: F401
        import pythonnet  # noqa: F401
        from PIL import Image  # noqa: F401
        print("desktop-deps-ok")
        sys.exit(0)

    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "shibaclaw":
        from shibaclaw.cli.commands import app
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        sys.exit(app())
    elif len(sys.argv) >= 2 and sys.argv[1] == "gateway":
        from shibaclaw.cli.commands import app
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        sys.exit(app())

    setup_shiba_logging()
    try:
        from shibaclaw.desktop.launcher import run

        run(disable_auth=True)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else int(bool(exc.code))
        if code:
            _show_startup_error(
                "Unable to start ShibaClaw Desktop.\n\n"
                "If this came from a pip install, use 'shibaclaw desktop' from a terminal or "
                "install the desktop extras with: pip install -e \".[windows-native,dev]\"\n\n"
                "For the portable packaged app, use dist/ShibaClaw/ShibaClaw.exe instead of the CLI launcher."
            )
        raise
    except Exception as exc:
        _show_startup_error(
            "Unhandled error while starting ShibaClaw Desktop.\n\n"
            f"{exc.__class__.__name__}: {exc}"
        )
        raise


if __name__ == "__main__":
    main()
