"""Interactive agent↔user requests (ask / credential / progress cards).

OpenClaw-2.0-inspired: secrets never return to the model; structured asks
pause the tool until the WebUI (or gateway) resolves them.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

PERMISSION_MODES = frozenset({"full", "workspace", "readonly"})
DEFAULT_INTERACTIVE_TIMEOUT = 300.0

EmitFn = Callable[[dict[str, Any]], Awaitable[None]]


class InteractiveHub:
    """In-process pending-request registry (lives in the gateway process)."""

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_meta: dict[str, dict[str, Any]] = {}
        # Per-session emitters avoid concurrent-turn races on a single callback.
        self._emitters: dict[str, EmitFn] = {}
        self._default_emit: EmitFn | None = None
        self._progress_cards: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def set_emit(self, callback: EmitFn | None, session_key: str | None = None) -> None:
        """Register emit callback for a session, or the process-wide default."""
        if session_key:
            if callback is None:
                self._emitters.pop(session_key, None)
            else:
                self._emitters[session_key] = callback
            return
        self._default_emit = callback

    def _resolve_emit(self, session_key: str) -> EmitFn | None:
        if session_key and session_key in self._emitters:
            return self._emitters[session_key]
        return self._default_emit

    async def emit(self, event: dict[str, Any]) -> None:
        """Fire-and-forget interactive/progress event (no wait)."""
        sk = str(event.get("session_key") or "")
        cb = self._resolve_emit(sk)
        if cb is None:
            return
        await cb(event)

    def get_progress_card(self, session_key: str) -> dict[str, Any] | None:
        return self._progress_cards.get(session_key)

    def set_progress_card(self, session_key: str, card: dict[str, Any]) -> None:
        self._progress_cards[session_key] = card

    def get_pending_meta(self, request_id: str) -> dict[str, Any] | None:
        return self._pending_meta.get(request_id)

    async def request(
        self,
        *,
        kind: str,
        session_key: str,
        payload: dict[str, Any],
        timeout: float = DEFAULT_INTERACTIVE_TIMEOUT,
    ) -> dict[str, Any]:
        """Emit an interactive prompt and wait for ``resolve``."""
        request_id = uuid.uuid4().hex[:12]
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        meta = {
            "kind": kind,
            "session_key": session_key,
            **{
                k: payload.get(k)
                for k in (
                    "key",
                    "namespace",
                    "title",
                    "options",
                    "initiator_user_id",
                    "allowed_user_ids",
                    "origin_ws_id",
                    "channel",
                )
                if k in payload
            },
        }
        async with self._lock:
            self._pending[request_id] = fut
            self._pending_meta[request_id] = meta

        event = {
            "kind": kind,
            "request_id": request_id,
            "session_key": session_key,
            **payload,
        }
        emit_cb = self._resolve_emit(session_key)
        if emit_cb is None:
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)
            return {
                "ok": False,
                "skipped": True,
                "error": "no_interactive_ui",
                "request_id": request_id,
            }

        try:
            await emit_cb(event)
        except Exception as e:
            logger.warning("Interactive emit failed: {}", e)
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)
            return {"ok": False, "error": f"emit_failed: {e}", "request_id": request_id}

        try:
            result = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
            if isinstance(result, dict):
                result.setdefault("request_id", request_id)
                return result
            return {"ok": True, "request_id": request_id, "value": result}
        except TimeoutError:
            return {"ok": False, "error": "timeout", "request_id": request_id}
        except asyncio.CancelledError:
            raise
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)
                self._pending_meta.pop(request_id, None)

    def resolve(
        self,
        request_id: str,
        response: dict[str, Any],
        *,
        session_key: str | None = None,
        origin_ws_id: str | None = None,
    ) -> bool:
        """Resolve a pending request (called from gateway ``interactive_reply``).

        For credential requests, if ``secret`` is present it is written to the
        vault here and stripped from the value returned to the waiting tool.

        When pending meta has ``session_key`` / ``origin_ws_id``, the reply must
        match (authorization boundary for WebUI multi-tab / multi-client).
        """
        fut = self._pending.get(request_id)
        if fut is None or fut.done():
            return False
        payload = dict(response) if isinstance(response, dict) else {"value": response}
        meta = self._pending_meta.get(request_id) or {}

        expected_sk = str(meta.get("session_key") or "").strip()
        if expected_sk:
            provided_sk = str(
                session_key if session_key is not None else payload.get("session_key") or ""
            ).strip()
            if provided_sk != expected_sk:
                logger.warning(
                    "interactive resolve denied: session_key mismatch for {}",
                    request_id,
                )
                return False

        expected_ws = str(meta.get("origin_ws_id") or "").strip()
        if expected_ws:
            provided_ws = str(
                origin_ws_id
                if origin_ws_id is not None
                else payload.get("origin_ws_id") or ""
            ).strip()
            # Soft check: prefer originating client, but allow any client that
            # already passed session_key binding (multi-tab same session).
            if provided_ws and provided_ws != expected_ws:
                logger.debug(
                    "interactive resolve: origin_ws_id differs for {} ({} vs {})",
                    request_id,
                    provided_ws,
                    expected_ws,
                )

        # Resolve option index → id/label when Telegram uses compact callback_data.
        if "option_index" in payload and isinstance(meta.get("options"), list):
            try:
                idx = int(payload["option_index"])
                opt = meta["options"][idx]
                if isinstance(opt, dict):
                    payload.setdefault("option_id", opt.get("id"))
                    payload.setdefault("label", opt.get("label") or opt.get("id"))
            except (TypeError, ValueError, IndexError):
                pass

        if meta.get("kind") == "credential" and isinstance(payload.get("secret"), str):
            secret = payload.pop("secret")
            if secret and payload.get("action") != "skip":
                ns = str(meta.get("namespace") or "runtime")
                key = str(meta.get("key") or "")
                if key:
                    try:
                        from shibaclaw.security.credential_manager import (
                            get_credential_manager,
                        )

                        get_credential_manager().set_secret(ns, key, secret)
                        payload["stored"] = True
                        payload["ok"] = True
                    except Exception as e:
                        logger.error("Failed to store credential: {}", e)
                        payload = {
                            "ok": False,
                            "error": f"store_failed: {e}",
                            "request_id": request_id,
                        }
            else:
                payload.setdefault("stored", False)
        payload.setdefault("ok", True)
        fut.set_result(payload)
        return True

    def cancel_all(self, reason: str = "cancelled") -> int:
        n = 0
        for rid, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_result({"ok": False, "error": reason, "request_id": rid})
                n += 1
        self._pending.clear()
        self._pending_meta.clear()
        return n


_HUB: InteractiveHub | None = None


def get_interactive_hub() -> InteractiveHub:
    global _HUB
    if _HUB is None:
        _HUB = InteractiveHub()
    return _HUB


def normalize_permission_mode(
    raw: Any,
    *,
    restrict_to_workspace: bool = True,
) -> str:
    """Return a valid permission mode; default mirrors global workspace restrict."""
    if isinstance(raw, str):
        mode = raw.strip().lower()
        if mode in PERMISSION_MODES:
            return mode
    return "workspace" if restrict_to_workspace else "full"
