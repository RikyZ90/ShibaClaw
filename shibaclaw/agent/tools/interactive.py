"""Interactive tools: ask_user, request_credential, update_progress, session_search."""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from shibaclaw.agent.interactive import DEFAULT_INTERACTIVE_TIMEOUT, get_interactive_hub
from shibaclaw.agent.interactive_ctx import build_interactive_turn, turn_interactive
from shibaclaw.agent.tools.base import Tool
from shibaclaw.brain.manager import PackManager
from shibaclaw.bus.events import OutboundMessage

_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_RUNTIME_NS = "runtime"


class AskUserTool(Tool):
    """Ask the user a structured question with optional buttons (WebUI / Telegram)."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ) -> None:
        self._send_callback = send_callback

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        # Bind per-task ContextVar — shared tool instances stay stateless.
        from shibaclaw.agent.interactive_ctx import bind_interactive_turn

        bind_interactive_turn(
            build_interactive_turn(
                channel=channel,
                chat_id=chat_id,
                session_key=session_key,
                metadata=metadata,
            )
        )

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return (
            "Ask the user a structured question with optional clickable choices. "
            "Prefer this over guessing when a clear decision is needed. "
            "Returns the selected option id/label (or free-text / skip)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Question to show the user",
                },
                "options": {
                    "type": "array",
                    "description": "Optional choices (id + label)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["id", "label"],
                    },
                },
                "allow_free_text": {
                    "type": "boolean",
                    "description": "Allow a free-text answer (default true)",
                },
                "allow_skip": {
                    "type": "boolean",
                    "description": "Show a Skip action (default true)",
                },
            },
            "required": ["prompt"],
        }

    async def execute(
        self,
        prompt: str,
        options: list[dict[str, Any]] | None = None,
        allow_free_text: bool = True,
        allow_skip: bool = True,
        **_kwargs: Any,
    ) -> str:
        ctx = turn_interactive()
        prompt = (prompt or "").strip()
        if not prompt:
            return "Error: prompt is required"

        clean_options: list[dict[str, str]] = []
        for opt in options or []:
            if not isinstance(opt, dict):
                continue
            oid = str(opt.get("id") or "").strip()
            label = str(opt.get("label") or oid).strip()
            if oid and label:
                clean_options.append({"id": oid, "label": label})

        hub = get_interactive_hub()
        telegram_wired = False
        session_key = ctx.session_key
        if (
            ctx.channel.lower() == "telegram"
            and clean_options
            and self._send_callback
            and ctx.chat_id
        ):
            chat_id = ctx.chat_id
            send_cb = self._send_callback

            async def telegram_emit(event: dict[str, Any]) -> None:
                rid = str(event.get("request_id") or "")
                opts = event.get("options") or clean_options
                kb = [
                    {"id": str(o.get("id")), "label": str(o.get("label") or o.get("id"))}
                    for o in opts
                    if isinstance(o, dict) and o.get("id")
                ]
                await send_cb(
                    OutboundMessage(
                        channel="telegram",
                        chat_id=chat_id,
                        content=str(event.get("prompt") or prompt),
                        metadata={
                            "ask_request_id": rid,
                            "inline_keyboard": kb,
                        },
                    )
                )

            hub.set_emit(telegram_emit, session_key=session_key)
            telegram_wired = True

        try:
            payload: dict[str, Any] = {
                "prompt": prompt,
                "options": clean_options,
                "allow_free_text": bool(allow_free_text),
                "allow_skip": bool(allow_skip),
                "channel": ctx.channel,
            }
            if ctx.initiator_user_id:
                payload["initiator_user_id"] = ctx.initiator_user_id
                payload["allowed_user_ids"] = [ctx.initiator_user_id]
            if ctx.origin_ws_id:
                payload["origin_ws_id"] = ctx.origin_ws_id
            result = await hub.request(
                kind="ask",
                session_key=session_key,
                payload=payload,
                timeout=DEFAULT_INTERACTIVE_TIMEOUT,
            )
        finally:
            if telegram_wired:
                hub.set_emit(None, session_key=session_key)

        if result.get("skipped") or result.get("error") == "no_interactive_ui":
            lines = [f"Question for user: {prompt}"]
            if clean_options:
                lines.append("Options:")
                for i, opt in enumerate(clean_options, 1):
                    lines.append(f"  {i}. [{opt['id']}] {opt['label']}")
            lines.append(
                "No interactive UI available — ask the user in chat and wait for their reply."
            )
            return "\n".join(lines)

        if result.get("error") == "timeout":
            return "User did not answer in time (timeout)."

        if not result.get("ok", True):
            return f"Ask cancelled: {result.get('error', 'unknown')}"

        if result.get("skipped") is True or result.get("action") == "skip":
            return "User skipped the question."

        option_id = result.get("option_id")
        label = result.get("label")
        text = result.get("text")
        if option_id:
            return f"User selected option id={option_id}" + (
                f" label={label}" if label else ""
            )
        if text:
            return f"User replied: {text}"
        return f"User response: {result}"


class RequestCredentialTool(Tool):
    """Request a secret via masked WebUI prompt; store in vault; never return value."""

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        from shibaclaw.agent.interactive_ctx import bind_interactive_turn

        bind_interactive_turn(
            build_interactive_turn(
                channel=channel,
                chat_id=chat_id,
                session_key=session_key,
                metadata=metadata,
            )
        )

    @property
    def name(self) -> str:
        return "request_credential"

    @property
    def description(self) -> str:
        return (
            "Request a secret from the user via a masked prompt. "
            "The secret is stored in the encrypted vault and NEVER returned "
            "to you or written into chat history. "
            "Use only on WebUI / owner sessions. "
            "After storage, other tools may read it via vault namespace "
            f"'{_RUNTIME_NS}' and the given key."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title shown on the prompt",
                },
                "key": {
                    "type": "string",
                    "description": (
                        f"Vault key under namespace '{_RUNTIME_NS}' "
                        "(letters, digits, ._ - only)"
                    ),
                },
                "hint": {
                    "type": "string",
                    "description": "Optional hint (never include the secret itself)",
                },
            },
            "required": ["title", "key"],
        }

    async def execute(
        self,
        title: str,
        key: str,
        hint: str | None = None,
        **_kwargs: Any,
    ) -> str:
        ctx = turn_interactive()
        title = (title or "").strip()
        key = (key or "").strip()
        if not title or not key:
            return "Error: title and key are required"
        if not _SAFE_KEY_RE.match(key):
            return (
                "Error: key must match [A-Za-z0-9_.-]{1,64} "
                "(no spaces or path separators)"
            )
        if ctx.channel and ctx.channel.lower() not in {
            "webui",
            "cli",
            "system",
            "",
        }:
            return (
                "Error: request_credential is only allowed on WebUI/CLI. "
                "Do not collect secrets over chat channels."
            )

        hub = get_interactive_hub()
        payload: dict[str, Any] = {
            "title": title,
            "key": key,
            "namespace": _RUNTIME_NS,
            "hint": (hint or "").strip(),
            "channel": ctx.channel,
        }
        if ctx.origin_ws_id:
            payload["origin_ws_id"] = ctx.origin_ws_id
        result = await hub.request(
            kind="credential",
            session_key=ctx.session_key,
            payload=payload,
            timeout=DEFAULT_INTERACTIVE_TIMEOUT,
        )

        if result.get("error") == "no_interactive_ui" or result.get("skipped"):
            return (
                "Error: no interactive UI to collect a secret safely. "
                "Ask the operator to set the vault entry in Settings instead."
            )
        if result.get("error") == "timeout":
            return "Credential request timed out; secret was not stored."
        if result.get("action") == "skip" or result.get("skipped") is True:
            return "User skipped the credential request; nothing stored."
        if not result.get("ok", False):
            return f"Credential request failed: {result.get('error', 'unknown')}"

        if result.get("stored") is False:
            return "Credential was not stored."

        return (
            f"Credential stored as vault ref {_RUNTIME_NS}/{key}. "
            "Value is not available to the model."
        )


class UpdateProgressTool(Tool):
    """Publish a durable session progress card (plan / status / steps)."""

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        from shibaclaw.agent.interactive_ctx import bind_interactive_turn

        bind_interactive_turn(
            build_interactive_turn(
                channel=channel,
                chat_id=chat_id,
                session_key=session_key,
                metadata=metadata,
            )
        )

    @property
    def name(self) -> str:
        return "update_progress"

    @property
    def description(self) -> str:
        return (
            "Update the durable session progress card shown in the WebUI "
            "(title, status, and optional step list). Survives reconnects "
            "for the current turn. Use for long multi-step work."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Card title"},
                "status": {
                    "type": "string",
                    "description": "working | done | blocked | error",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered step labels (optional)",
                },
                "detail": {
                    "type": "string",
                    "description": "Optional short status detail",
                },
            },
            "required": ["title", "status"],
        }

    async def execute(
        self,
        title: str,
        status: str,
        steps: list[str] | None = None,
        detail: str | None = None,
        **_kwargs: Any,
    ) -> str:
        ctx = turn_interactive()
        title = (title or "").strip() or "Progress"
        status = (status or "working").strip().lower()
        if status not in {"working", "done", "blocked", "error"}:
            status = "working"
        clean_steps = [str(s).strip() for s in (steps or []) if str(s).strip()][:20]
        card = {
            "title": title[:120],
            "status": status,
            "steps": clean_steps,
            "detail": (detail or "").strip()[:300],
            "session_key": ctx.session_key,
        }
        hub = get_interactive_hub()
        hub.set_progress_card(ctx.session_key, card)
        try:
            await hub.emit({"kind": "progress_card", **card})
        except Exception:
            pass
        return f"Progress card updated: {status} — {title}"


class SessionSearchTool(Tool):
    """Search past conversation transcripts (owner WebUI/CLI only)."""

    _ALLOWED_CHANNELS = frozenset({"webui", "cli", "system"})

    def __init__(self, sessions: PackManager) -> None:
        self._sessions = sessions

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        from shibaclaw.agent.interactive_ctx import bind_interactive_turn

        bind_interactive_turn(
            build_interactive_turn(
                channel=channel,
                chat_id=chat_id,
                session_key=session_key,
                metadata=metadata,
            )
        )

    @property
    def name(self) -> str:
        return "session_search"

    @property
    def description(self) -> str:
        return (
            "Search visible text across past conversation sessions by exact "
            "words or phrases. Owner WebUI/CLI only. Returns matching session "
            "keys, roles, and snippets."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search phrase"},
                "limit": {
                    "type": "integer",
                    "description": "Max hits (default 20, max 50)",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 20, **_kwargs: Any) -> str:
        ctx = turn_interactive()
        if ctx.channel.strip().lower() not in self._ALLOWED_CHANNELS:
            return (
                "Error: session_search is only available on WebUI/CLI "
                "(not Telegram or other chat channels)."
            )
        q = (query or "").strip()
        if not q:
            return "Error: query is required"
        try:
            lim = max(1, min(int(limit or 20), 50))
        except (TypeError, ValueError):
            lim = 20
        hits = self._sessions.search_messages(q, limit=lim)
        if not hits:
            return f"No matches for {q!r}."
        lines = [f"Found {len(hits)} hit(s) for {q!r}:"]
        for h in hits:
            lines.append(
                f"- [{h.get('session_key')}] {h.get('role')}: {h.get('snippet')}"
            )
        return "\n".join(lines)
