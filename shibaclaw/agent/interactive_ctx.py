"""Per-turn interactive tool context via contextvars (concurrent-safe)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InteractiveTurnContext:
    channel: str = ""
    chat_id: str = ""
    session_key: str = ""
    initiator_user_id: str = ""
    origin_ws_id: str = ""


_turn: ContextVar[InteractiveTurnContext | None] = ContextVar(
    "shibaclaw_interactive_turn", default=None
)


def bind_interactive_turn(ctx: InteractiveTurnContext) -> Token:
    return _turn.set(ctx)


def reset_interactive_turn(token: Token | None) -> None:
    if token is None:
        return
    _turn.reset(token)


def turn_interactive() -> InteractiveTurnContext:
    return _turn.get() or InteractiveTurnContext()


def build_interactive_turn(
    *,
    channel: str = "",
    chat_id: str = "",
    session_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> InteractiveTurnContext:
    """Derive turn context from channel/chat/session + inbound metadata."""
    ch = channel or ""
    cid = chat_id or ""
    sk = session_key or (f"{ch}:{cid}" if ch and cid else "")
    meta = metadata or {}
    sender = meta.get("sender_id") or meta.get("user_id") or meta.get("from_user_id")
    if sender is None and ch == "telegram" and str(cid).lstrip("-").isdigit():
        if not str(cid).startswith("-"):
            sender = cid
    origin_ws = str(meta.get("origin_ws_id") or meta.get("ws_id") or "").strip()
    return InteractiveTurnContext(
        channel=ch,
        chat_id=cid,
        session_key=sk,
        initiator_user_id=str(sender).strip() if sender is not None else "",
        origin_ws_id=origin_ws,
    )
