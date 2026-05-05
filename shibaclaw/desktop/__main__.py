"""Entry point for the packaged or pip-installed ShibaClaw desktop app."""

from __future__ import annotations

import sys

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

    print(message, file=sys.stderr)


def main() -> None:
    import multiprocessing
    multiprocessing.freeze_support()

    # Intercept subprocess calls (e.g. gateway) when bundled by PyInstaller
    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "shibaclaw":
        from shibaclaw.cli.commands import app
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        sys.exit(app())
    elif len(sys.argv) >= 2 and sys.argv[1] == "gateway":
        # Just in case it's called as ShibaClaw.exe gateway
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