"""Terminal and IO utilities for the ShibaClaw CLI."""

import os
import select
import sys
from contextlib import contextmanager, nullcontext

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from shibaclaw import __logo__

console = Console()


def flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios

        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def restore_terminal(saved_attrs) -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if saved_attrs is None:
        return
    try:
        import termios

        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved_attrs)
    except Exception:
        pass


def render_interactive_ansi(render_fn) -> str:
    """Render Rich output to ANSI so prompt_toolkit can print it safely."""
    ansi_console = Console(
        force_terminal=True,
        color_system=console.color_system or "standard",
        width=console.width,
    )
    with ansi_console.capture() as capture:
        render_fn(ansi_console)
    return capture.get()


class ThinkingSpinner:
    """Spinner wrapper with pause support for clean progress output."""

    def __init__(self, enabled: bool):
        self._spinner = (
            console.status(
                "[dim]shibaclaw is [bold gold1]hunting[/bold gold1] for answers...[/dim]",
                spinner="dots",
            )
            if enabled
            else None
        )
        self._active = False

    def __enter__(self):
        if self._spinner:
            self._spinner.start()
        self._active = True
        return self

    def __exit__(self, *exc):
        self._active = False
        if self._spinner:
            self._spinner.stop()
        return False

    @contextmanager
    def pause(self):
        """Temporarily stop spinner while printing progress."""
        if self._spinner and self._active:
            self._spinner.stop()
        try:
            yield
        finally:
            if self._spinner and self._active:
                self._spinner.start()


def print_cli_progress_line(text: str, thinking: ThinkingSpinner | None) -> None:
    """Print a CLI progress line with an icon, pausing the spinner if needed."""
    icon = "[🐾]"
    if "search" in text.lower() or "find" in text.lower():
        icon = "[🔍]"
    elif "tool" in text.lower() or "exec" in text.lower():
        icon = "[🛠️]"
    elif "done" in text.lower() or "finish" in text.lower():
        icon = "[✅]"

    with thinking.pause() if thinking else nullcontext():
        console.print(f"  [orange3]{icon}[/orange3] [dim]{text}[/dim]")


def print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[gold1]{__logo__} shibaclaw[/gold1]")
    console.print(body)
    console.print()
