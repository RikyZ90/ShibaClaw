"""Interactive chat loop and agent interaction for the ShibaClaw CLI."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any, Optional

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.markdown import Markdown
from rich.text import Text

from shibaclaw import __logo__

from .utils import (
    ThinkingSpinner,
    console,
    flush_pending_tty_input,
    print_agent_response,
    print_cli_progress_line,
    render_interactive_ansi,
    restore_terminal,
)

_PROMPT_SESSION: Optional[PromptSession] = None
_SAVED_TERM_ATTRS = None


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    try:
        import termios

        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    from shibaclaw.config.paths import get_cli_history_path

    history_file = get_cli_history_path()
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,
    )


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit."""
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='orange'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc


async def _print_interactive_line(text: str) -> None:
    """Print async interactive updates with prompt_toolkit-safe Rich styling."""

    def _write() -> None:
        icon = "[🐾]"
        if "search" in text.lower() or "find" in text.lower():
            icon = "[🔍]"
        elif "tool" in text.lower() or "exec" in text.lower():
            icon = "[🛠️]"

        ansi = render_interactive_ansi(
            lambda c: c.print(f"  [orange3]{icon}[/orange3] [dim]{text}[/dim]")
        )
        print_formatted_text(ANSI(ansi), end="")

    await run_in_terminal(_write)


async def _print_interactive_response(response: str, render_markdown: bool) -> None:
    """Print async interactive replies with prompt_toolkit-safe Rich styling."""

    def _write() -> None:
        ansi = render_interactive_ansi(
            lambda c: (
                c.print(),
                c.print(f"[gold1]{__logo__} shibaclaw[/gold1]"),
                c.print(Markdown(response) if render_markdown else Text(response)),
                c.print(),
            )
        )
        print_formatted_text(ANSI(ansi), end="")

    await run_in_terminal(_write)


def agent_command(
    message: Optional[str] = None,
    session_id: str = "cli:direct",
    config_obj: Optional[Any] = None,
    markdown: bool = True,
    logs: bool = False,
):
    """Interact with the agent directly."""
    from loguru import logger

    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.bus.queue import MessageBus
    from shibaclaw.config.paths import get_cron_dir
    from shibaclaw.cron.service import CronService

    if logs:
        logger.enable("shibaclaw")
    else:
        logger.disable("shibaclaw")

    bus = MessageBus()
    from .base import _make_provider

    provider = _make_provider(config_obj)

    cron_store_path = get_cron_dir() / "jobs.json"
    CronService(cron_store_path)

    agent_loop = ShibaBrain(
        bus=bus,
        provider=provider,
        workspace=config_obj.workspace_path,
        config=config_obj,
        model=config_obj.agents.defaults.model,
        max_iterations=config_obj.agents.defaults.max_tool_iterations,
        context_window_tokens=config_obj.agents.defaults.context_window_tokens,
        web_search_config=config_obj.tools.web.search,
        web_proxy=config_obj.tools.web.proxy,
        exec_config=config_obj.tools.exec,
        mcp_servers=config_obj.tools.mcp_servers,
        channels_config=config_obj.channels,
        restrict_to_workspace=config_obj.tools.restrict_to_workspace,
        learning_enabled=config_obj.agents.defaults.learning_enabled,
        learning_interval=config_obj.agents.defaults.learning_interval,
        memory_max_prompt_tokens=config_obj.agents.defaults.memory_max_prompt_tokens,
        memory_compact_threshold_tokens=config_obj.agents.defaults.memory_compact_threshold_tokens,
        consolidation_model=config_obj.agents.defaults.consolidation_model,
    )

    _thinking: Optional[ThinkingSpinner] = None

    async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
        ch = agent_loop.channels_config
        if ch and tool_hint and not ch.send_tool_hints:
            return
        if ch and not tool_hint and not ch.send_progress:
            return
        print_cli_progress_line(content, _thinking)

    if message:

        async def run_once():
            nonlocal _thinking
            _thinking = ThinkingSpinner(enabled=not logs)
            with _thinking:
                outbound = await agent_loop.process_direct(
                    message, session_id, on_progress=_cli_progress
                )
                resp = outbound.content if outbound else ""
            print_agent_response(resp, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        _init_prompt_session()
        console.print(
            f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n"
        )

        cli_channel, cli_chat_id = (
            session_id.split(":", 1) if ":" in session_id else ("cli", session_id)
        )

        def _handle_signal(signum, frame):
            restore_terminal(_SAVED_TERM_ATTRS)
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, _handle_signal)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            turn_done, turn_response = asyncio.Event(), []
            turn_done.set()

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.metadata.get("_progress"):
                            is_tool = msg.metadata.get("_tool_hint", False)
                            ch = agent_loop.channels_config
                            if not (
                                ch
                                and (
                                    (is_tool and not ch.send_tool_hints)
                                    or (not is_tool and not ch.send_progress)
                                )
                            ):
                                await _print_interactive_line(msg.content)
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            await _print_interactive_response(msg.content, render_markdown=markdown)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        if isinstance(sys.exc_info()[0], asyncio.CancelledError):
                            break
                        continue

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        cmd = user_input.strip()
                        if not cmd:
                            continue
                        if cmd.lower() in {"exit", "quit", "/exit", "/quit", ":q"}:
                            restore_terminal(_SAVED_TERM_ATTRS)
                            console.print("\nGoodbye!")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        from shibaclaw.bus.events import InboundMessage

                        await bus.publish_inbound(
                            InboundMessage(
                                channel=cli_channel,
                                sender_id="user",
                                chat_id=cli_chat_id,
                                content=user_input,
                            )
                        )

                        nonlocal _thinking
                        _thinking = ThinkingSpinner(enabled=not logs)
                        with _thinking:
                            await turn_done.wait()
                        _thinking = None

                        if turn_response:
                            print_agent_response(turn_response[0], render_markdown=markdown)
                    except (KeyboardInterrupt, EOFError):
                        restore_terminal(_SAVED_TERM_ATTRS)
                        console.print("\nGoodbye!")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                await asyncio.gather(bus_task, outbound_task, return_exceptions=True)
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())
