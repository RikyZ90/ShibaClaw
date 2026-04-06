"""Memory system for persistent agent memory."""

from __future__ import annotations

import asyncio
import json
import weakref
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from shibaclaw.helpers.helpers import ensure_dir, estimate_message_tokens, estimate_prompt_tokens, estimate_prompt_tokens_chain

if TYPE_CHECKING:
    from shibaclaw.thinkers.base import Thinker
    from shibaclaw.brain.manager import Session, PackManager


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Persist consolidated memory: history entry + updated MEMORY.md + updated USER.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "Paragraph: [YYYY-MM-DD HH:MM] [#tag1 #tag2] [★1-5] summary of key events/decisions.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Deduplicated Markdown MEMORY.md. Sections: ## Environment, ## Entities, "
                        "## Project State, ## Dynamic Context. Remove obsolete/duplicate items. "
                        "Personal profile → USER.md. Target ≤1500 tokens. Return current content if unchanged.",
                    },
                    "user_update": {
                        "type": "string",
                        "description": "Updated USER.md. Keep existing structure. Store durable personal facts/preferences. "
                        "Return current content if unchanged.",
                    },
                },
                "required": ["history_entry", "memory_update", "user_update"],
            },
        },
    },
]

_PROACTIVE_LEARN_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "update_long_term_memory",
            "description": "Update USER.md and MEMORY.md with new durable facts. Does NOT create history entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_update": {
                        "type": "string",
                        "description": "Deduplicated Markdown MEMORY.md. Sections: ## Environment, ## Entities, "
                        "## Project State, ## Dynamic Context. Add new findings, remove outdated entries. "
                        "Personal profile → USER.md. Target ≤1500 tokens. Return current content if unchanged.",
                    },
                    "user_update": {
                        "type": "string",
                        "description": "Updated USER.md. Keep existing structure. Store durable personal facts/preferences. "
                        "Return current content if unchanged.",
                    },
                },
                "required": ["memory_update", "user_update"],
            },
        },
    },
]


def _ensure_text(value: Any) -> str:
    """Normalize tool-call payload values to text for file storage."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize_save_memory_args(args: Any) -> dict[str, Any] | None:
    """Normalize provider tool-call arguments to the expected dict shape."""
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None
    return args if isinstance(args, dict) else None


def _normalize_update_memory_args(args: Any) -> dict[str, Any] | None:
    """Normalize update_long_term_memory payload."""
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None
    return args if isinstance(args, dict) else None

_TOOL_CHOICE_ERROR_MARKERS = (
    "tool_choice",
    "toolchoice",
    "does not support",
    'should be ["none", "auto"]',
)


def _is_tool_choice_unsupported(content: str | None) -> bool:
    """Detect provider errors caused by forced tool_choice being unsupported."""
    text = (content or "").lower()
    return any(m in text for m in _TOOL_CHOICE_ERROR_MARKERS)


class ScentKeeper:
    """Persistent memory files: USER.md, MEMORY.md, and HISTORY.md."""

    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(self, workspace: Path):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.user_file = workspace / "USER.md"
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self._consecutive_failures = 0
        self._file_lock = asyncio.Lock()

    def read_user_profile(self) -> str:
        if self.user_file.exists():
            return self.user_file.read_text(encoding="utf-8")
        return ""

    async def write_user_profile(self, content: str) -> None:
        async with self._file_lock:
            self.user_file.write_text(content, encoding="utf-8")

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    async def write_long_term(self, content: str) -> None:
        async with self._file_lock:
            self.memory_file.write_text(content, encoding="utf-8")

    async def append_history(self, entry: str) -> None:
        """Prepend new entry so most recent archives appear at the top."""
        async with self._file_lock:
            existing = ""
            if self.history_file.exists():
                existing = self.history_file.read_text(encoding="utf-8")
            new_content = entry.rstrip() + "\n\n" + existing
            self.history_file.write_text(new_content, encoding="utf-8")

    def estimate_memory_tokens(self) -> int:
        """Estimate token count of the current MEMORY.md content."""
        content = self.read_long_term()
        if not content:
            return 0
        return estimate_prompt_tokens([{"role": "user", "content": content}])

    def get_memory_context(self, max_tokens: int = 0) -> str:
        """Return long-term memory for system prompt injection.

        If *max_tokens* > 0 and the content exceeds the budget, sections
        are dropped from the bottom up (keeping headers) and a truncation
        marker is appended.
        """
        long_term = self.read_long_term()
        if not long_term:
            return ""

        if max_tokens > 0:
            tokens = estimate_prompt_tokens([{"role": "user", "content": long_term}])
            if tokens > max_tokens:
                long_term = self._truncate_to_budget(long_term, max_tokens)

        return f"## Long-term Memory\n{long_term}" if not long_term.lstrip().startswith("#") else long_term

    @staticmethod
    def _truncate_to_budget(text: str, max_tokens: int) -> str:
        """Keep Markdown sections from the top until the token budget is exhausted."""
        import re as _re
        sections = _re.split(r'(?=^## )', text, flags=_re.MULTILINE)
        kept: list[str] = []
        for section in sections:
            candidate = "\n".join(kept + [section])
            tokens = estimate_prompt_tokens([{"role": "user", "content": candidate}])
            if tokens > max_tokens and kept:
                break
            kept.append(section)
        truncated = "\n".join(kept).rstrip()
        return truncated + "\n\n[MEMORY TRUNCATED — search HISTORY.md for older context]"

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        lines = []
        for message in messages:
            role = message.get("role", "unknown").upper()
            ts = message.get("timestamp", "?")[:16]
            content = message.get("content") or ""
            if role == "ASSISTANT" and message.get("tool_calls"):
                calls = [tc.get("function", {}).get("name", "unknown") for tc in message["tool_calls"]]
                if content:
                    content += "\n"
                content += f"[Tool Calls: {', '.join(calls)}]"
            if role == "TOOL" and content:
                if len(content) > 300:
                    content = content[:150] + "\n...[TRUNCATED]...\n" + content[-150:]
            if role in ("USER", "ASSISTANT") and len(content) > 500:
                content = content[:250] + "\n...[TRUNCATED]...\n" + content[-250:]
            if not content.strip():
                continue
            tools = f" [executed: {', '.join(message['tools_used'])}]" if message.get("tools_used") else ""
            lines.append(f"[{ts}] {role}{tools}: {content.strip()}")
        return "\n".join(lines)

    async def consolidate(
        self,
        messages: list[dict],
        provider: Thinker,
        model: str,
    ) -> bool:
        if not messages:
            return True

        current_user = self.read_user_profile()
        current_memory = self.read_long_term()
        prompt = f"""Consolidate this conversation. Call save_memory with:
- history_entry: timestamped tagged summary
- memory_update: updated MEMORY.md (operational facts only, personal profile → USER.md)
- user_update: updated USER.md (personal facts/preferences only)

## Current USER.md
{current_user or "(empty)"}

## Current MEMORY.md
{current_memory or "(empty)"}

## Conversation
{self._format_messages(messages)}"""

        chat_messages = [
            {"role": "system", "content": "You are a memory consolidation assistant. Call save_memory."},
            {"role": "user", "content": prompt},
        ]

        try:
            forced = {"type": "function", "function": {"name": "save_memory"}}
            response = await provider.chat_with_retry(
                messages=chat_messages,
                tools=_SAVE_MEMORY_TOOL,
                model=model,
                tool_choice=forced,
            )

            if response.finish_reason == "error" and _is_tool_choice_unsupported(response.content):
                logger.warning("Forced tool_choice unsupported, retrying with auto")
                response = await provider.chat_with_retry(
                    messages=chat_messages,
                    tools=_SAVE_MEMORY_TOOL,
                    model=model,
                    tool_choice="auto",
                )

            if not response.has_tool_calls:
                logger.warning(
                    "Memory consolidation: Shiba did not call save_memory "
                    "(finish_reason={}, content_len={}, content_preview={})",
                    response.finish_reason,
                    len(response.content or ""),
                    (response.content or "")[:200],
                )
                return await self._fail_or_raw_archive(messages)

            args = _normalize_save_memory_args(response.tool_calls[0].arguments)
            if args is None:
                logger.warning("Memory consolidation: unexpected save_memory arguments")
                return await self._fail_or_raw_archive(messages)

            if "history_entry" not in args or "memory_update" not in args:
                logger.warning("Memory consolidation: save_memory payload missing required fields")
                return await self._fail_or_raw_archive(messages)

            entry = args["history_entry"]
            update = args["memory_update"]
            user_update = args.get("user_update", current_user)

            if entry is None or update is None or user_update is None:
                logger.warning("Memory consolidation: save_memory payload contains null required fields")
                return await self._fail_or_raw_archive(messages)

            entry = _ensure_text(entry).strip()
            if not entry:
                logger.warning("Memory consolidation: history_entry is empty after normalization")
                return await self._fail_or_raw_archive(messages)

            await self.append_history(entry)
            update = _ensure_text(update)
            user_update = _ensure_text(user_update)
            if update != current_memory:
                await self.write_long_term(update)
            if user_update.strip() and user_update != current_user:
                await self.write_user_profile(user_update)

            self._consecutive_failures = 0
            logger.info("🐕 Memory consolidation done for {} traces", len(messages))
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return await self._fail_or_raw_archive(messages)

    async def compact_long_term(
        self,
        provider: Thinker,
        model: str,
        target_tokens: int = 1500,
    ) -> bool:
        current = self.read_long_term()
        if not current:
            return True

        current_tokens = self.estimate_memory_tokens()
        if current_tokens <= target_tokens:
            return True

        logger.info(
            "🐕 Memory compaction triggered: {} tokens (target {})",
            current_tokens, target_tokens,
        )

        prompt = (
            f"Compact this long-term memory to under {target_tokens} tokens.\n"
            "Rules:\n"
            "1. Keep all unique, important operational facts (environment details, recurring entities, project state).\n"
            "2. Remove duplicates, verbose explanations, and resolved/obsolete items.\n"
            "3. Preserve Markdown structure with ## headings.\n"
            "4. Remove personal profile or communication preference details that belong in USER.md.\n"
            "5. Return only the compacted Markdown.\n\n"
            f"## Current MEMORY.md\n{current}"
        )
        chat_messages = [
            {"role": "system", "content": "You are a memory compaction assistant. Output only the compacted Markdown."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await provider.chat_with_retry(
                messages=chat_messages, tools=[], model=model,
            )
            compacted = (response.content or "").strip()
            if not compacted:
                logger.warning("Memory compaction returned empty — skipping")
                return False

            new_tokens = estimate_prompt_tokens([{"role": "user", "content": compacted}])
            if new_tokens >= current_tokens:
                logger.warning(
                    "Memory compaction did not reduce size ({} -> {}) — skipping",
                    current_tokens, new_tokens,
                )
                return False

            await self.write_long_term(compacted)
            logger.info(
                "🐕 Memory compacted: {} -> {} tokens",
                current_tokens, new_tokens,
            )
            return True
        except Exception:
            logger.exception("Memory compaction failed")
            return False

    async def proactive_consolidate(
        self,
        messages: list[dict],
        provider: Thinker,
        model: str,
    ) -> bool:
        if not messages:
            return True

        current_user = self.read_user_profile()
        current_memory = self.read_long_term()
        prompt = f"""Extract new durable facts from the recent interaction. Call update_long_term_memory.
- Personal profile/preferences → user_update (USER.md)
- Operational facts (env, entities, project state) → memory_update (MEMORY.md)
- If nothing new, return current content unchanged.

## Current USER.md
{current_user or "(empty)"}

## Current MEMORY.md
{current_memory or "(empty)"}

## Recent Interaction
{self._format_messages(messages)}"""

        chat_messages = [
            {"role": "system", "content": "You are a fact-extraction assistant. Call update_long_term_memory."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await provider.chat_with_retry(
                messages=chat_messages,
                tools=_PROACTIVE_LEARN_TOOL,
                model=model,
                tool_choice={"type": "function", "function": {"name": "update_long_term_memory"}},
            )

            if response.finish_reason == "error" or not response.has_tool_calls:
                response = await provider.chat_with_retry(
                    messages=chat_messages,
                    tools=_PROACTIVE_LEARN_TOOL,
                    model=model,
                    tool_choice="auto"
                )

            if not response.has_tool_calls:
                return False

            call = response.tool_calls[0]
            args = _normalize_update_memory_args(call.arguments)
            if args is None or "memory_update" not in args:
                return False

            update = _ensure_text(args["memory_update"]).strip()
            user_update = _ensure_text(args.get("user_update", current_user))
            if update and update != current_memory:
                await self.write_long_term(update)
            if user_update.strip() and user_update != current_user:
                await self.write_user_profile(user_update)
            if (update and update != current_memory) or (user_update.strip() and user_update != current_user):
                logger.info("🐕 Proactive Learning: updated USER.md and long-term memory with new traces.")

            return True
        except Exception as e:
            logger.debug("Proactive Learning failed (swallowed): {}", e)
            return False

    async def _fail_or_raw_archive(self, messages: list[dict]) -> bool:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        await self._raw_archive(messages)
        self._consecutive_failures = 0
        return True

    async def _raw_archive(self, messages: list[dict]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        await self.append_history(
            f"[{ts}] [RAW] {len(messages)} messages\n"
            f"{self._format_messages(messages)}"
        )
        logger.warning(
            "🐕 Scent trail lost: raw-archived {} messages", len(messages)
        )


class PackMemory:

    _MAX_CONSOLIDATION_ROUNDS = 5

    def __init__(
        self,
        workspace: Path,
        provider: Thinker,
        model: str,
        sessions: PackManager,
        context_window_tokens: int,
        build_messages: Callable[..., list[dict[str, Any]]],
        get_tool_definitions: Callable[[], list[dict[str, Any]]],
        learning_enabled: bool = True,
        learning_interval: int = 10,
        memory_max_prompt_tokens: int = 2000,
        memory_compact_threshold_tokens: int = 1600,
        consolidation_model: str | None = None,
    ):
        self.store = ScentKeeper(workspace)
        self.provider = provider
        self.model = model
        self.consolidation_model = consolidation_model or model
        self.sessions = sessions
        self.context_window_tokens = context_window_tokens
        self.learning_enabled = learning_enabled
        self.learning_interval = learning_interval
        self.memory_max_prompt_tokens = memory_max_prompt_tokens
        self.memory_compact_threshold_tokens = memory_compact_threshold_tokens
        self._build_messages = build_messages
        self._get_tool_definitions = get_tool_definitions
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get_lock(self, session_key: str) -> asyncio.Lock:
        return self._locks.setdefault(session_key, asyncio.Lock())

    async def consolidate_messages(self, messages: list[dict[str, object]]) -> bool:
        return await self.store.consolidate(messages, self.provider, self.consolidation_model)

    def pick_consolidation_boundary(
        self,
        session: Session,
        tokens_to_remove: int,
    ) -> tuple[int, int] | None:
        """Pick a user-turn boundary that removes enough old prompt tokens."""
        start = session.last_consolidated
        if start >= len(session.messages) or tokens_to_remove <= 0:
            return None

        removed_tokens = 0
        last_boundary: tuple[int, int] | None = None
        for idx in range(start, len(session.messages)):
            message = session.messages[idx]
            if idx > start and message.get("role") == "user":
                last_boundary = (idx, removed_tokens)
                if removed_tokens >= tokens_to_remove:
                    return last_boundary
            removed_tokens += estimate_message_tokens(message)

        return last_boundary

    def estimate_session_prompt_tokens(self, session: Session) -> tuple[int, str]:
        history = session.get_history(max_messages=0)
        channel, chat_id = (session.key.split(":", 1) if ":" in session.key else (None, None))
        probe_messages = self._build_messages(
            history=history,
            current_message="[token-probe]",
            channel=channel,
            chat_id=chat_id,
            memory_max_prompt_tokens=self.memory_max_prompt_tokens,
        )
        return estimate_prompt_tokens_chain(
            self.provider,
            self.model,
            probe_messages,
            self._get_tool_definitions(),
        )

    async def archive_snapshot(self, messages: list[dict[str, object]]) -> bool:
        if not messages:
            return True
        for _ in range(self.store._MAX_FAILURES_BEFORE_RAW_ARCHIVE):
            if await self.consolidate_messages(messages):
                await self.maybe_compact_memory()
                return True
        await self.maybe_compact_memory()
        return True

    async def maybe_consolidate_by_tokens(self, session: Session) -> None:
        if not session.messages or self.context_window_tokens <= 0:
            return

        lock = self.get_lock(session.key)
        async with lock:
            trigger = int(self.context_window_tokens * 0.6)
            target = int(self.context_window_tokens * 0.4)
            estimated, source = self.estimate_session_prompt_tokens(session)
            if estimated <= 0:
                return
            if estimated < trigger:
                logger.debug(
                    "Token consolidation idle {}: {}/{} via {}",
                    session.key,
                    estimated,
                    trigger,
                    source,
                )
                return

            for round_num in range(self._MAX_CONSOLIDATION_ROUNDS):
                if estimated <= target:
                    return

                boundary = self.pick_consolidation_boundary(session, max(1, estimated - target))
                if boundary is None:
                    logger.debug(
                        "Token consolidation: no safe boundary for {} (round {})",
                        session.key,
                        round_num,
                    )
                    return

                end_idx = boundary[0]
                chunk = session.messages[session.last_consolidated:end_idx]
                if not chunk:
                    return

                logger.info(
                    "Token consolidation round {} for {}: {}/{} via {}, chunk={} msgs",
                    round_num,
                    session.key,
                    estimated,
                    self.context_window_tokens,
                    source,
                    len(chunk),
                )
                if not await self.consolidate_messages(chunk):
                    return
                session.last_consolidated = end_idx
                self.sessions.save(session)

                estimated, source = self.estimate_session_prompt_tokens(session)
                if estimated <= 0:
                    return

    async def maybe_proactive_learn(self, session: Session) -> None:
        if not self.learning_enabled or self.learning_interval <= 0:
            return
        count = len(session.messages) - session.last_learned
        if count < self.learning_interval:
            return
        chunk = session.messages[session.last_learned:]
        if not chunk:
            return

        lock = self.get_lock(session.key)
        async with lock:
            logger.debug("🐕 Proactive Learning starting for {} ({} new messages)", session.key, len(chunk))
            session.last_learned = len(session.messages)
            self.sessions.save(session)

            success = await self.store.proactive_consolidate(chunk, self.provider, self.consolidation_model)
            if not success:
                logger.debug("🐕 Proactive Learning skipped/failed for {}", session.key)
        await self.maybe_compact_memory()

    async def maybe_compact_memory(self) -> None:
        if self.memory_compact_threshold_tokens <= 0:
            return
        mem_tokens = self.store.estimate_memory_tokens()
        if mem_tokens > self.memory_compact_threshold_tokens:
            await self.store.compact_long_term(
                self.provider, self.consolidation_model,
                target_tokens=self.memory_compact_threshold_tokens,
            )