"""Brain management for conversation history — the memory of the Shiba."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from shibaclaw.config.paths import get_legacy_sessions_dir
from shibaclaw.helpers.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # Number of messages already consolidated into HISTORY.md/MEMORY.md
    last_learned: int = 0  # Index up to which the agent has "proactively learned" from.

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), **kwargs}
        self.messages.append(msg)
        self.updated_at = datetime.now()

    @staticmethod
    def _find_legal_start(messages: list[dict[str, Any]]) -> int:
        """Find first index where every tool result has a matching assistant tool_call."""
        declared: set[str] = set()
        start = 0
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and tc.get("id"):
                        declared.add(str(tc["id"]))
            elif role == "tool":
                tid = msg.get("tool_call_id")
                if tid and str(tid) not in declared:
                    start = i + 1
                    declared.clear()

        return start

    @staticmethod
    def _parse_message_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return None
        return timestamp.astimezone().replace(tzinfo=None) if timestamp.tzinfo else timestamp

    def get_history(
        self, max_messages: int = 500, max_age_hours: float | None = None
    ) -> list[dict[str, Any]]:
        """Return unconsolidated messages aligned to a legal tool-call boundary."""
        unconsolidated = self.messages[self.last_consolidated :]
        if max_age_hours is not None and max_age_hours > 0:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            for index, message in enumerate(unconsolidated):
                timestamp = self._parse_message_timestamp(message.get("timestamp"))
                if timestamp is not None and timestamp >= cutoff:
                    unconsolidated = unconsolidated[index:]
                    break
            else:
                unconsolidated = []
        sliced = unconsolidated if max_messages <= 0 else unconsolidated[-max_messages:]

        # Drop leading non-user messages to avoid starting mid-turn when possible.
        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                sliced = sliced[i:]
                break

        # Some providers reject orphan tool results if the matching assistant
        # tool_calls message fell outside the fixed-size history window.
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for message in sliced:
            entry: dict[str, Any] = {"role": message["role"], "content": message.get("content", "")}
            for key in ("tool_calls", "tool_call_id", "name", "reasoning_details"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()

    def rewind(self, to_index: int) -> int:
        """Truncate messages to ``to_index`` (exclusive end), aligned to a legal boundary.

        Returns the actual keep length.
        """
        if to_index <= 0:
            self.messages = []
            self.last_consolidated = 0
            self.last_learned = 0
            self.updated_at = datetime.now()
            return 0
        keep = min(to_index, len(self.messages))
        sliced = self.messages[:keep]
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]
        self.messages = sliced
        self.last_consolidated = min(self.last_consolidated, len(self.messages))
        self.last_learned = min(self.last_learned, len(self.messages))
        self.updated_at = datetime.now()
        return len(self.messages)

    def fork_messages(self, from_index: int) -> list[dict[str, Any]]:
        """Return a copy of messages up to ``from_index`` on a legal boundary."""
        keep = max(0, min(from_index, len(self.messages)))
        sliced = list(self.messages[:keep])
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]
        return sliced


class PackManager:
    """
    Manages conversation sessions for the Shiba pack.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}
        self._cache_mtime_ns: dict[str, int | None] = {}
        self._cache_persisted_messages_count: dict[str, int] = {}
        self._cache_persisted_last_consolidated: dict[str, int] = {}
        self._cache_persisted_last_learned: dict[str, int] = {}
        self._cache_persisted_metadata_json: dict[str, str] = {}
        self._list_sessions_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _get_session_mtime_ns(self, key: str) -> int | None:
        """Return the current mtime for a session file, if it exists."""
        path = self._get_session_path(key)
        try:
            return path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """Get an existing session or create a new one."""
        current_mtime = self._get_session_mtime_ns(key)

        if key in self._cache:
            cached_mtime = self._cache_mtime_ns.get(key)
            if current_mtime == cached_mtime:
                return self._cache[key]

            session = self._load(key)
            if session is not None:
                self._cache[key] = session
                self._cache_mtime_ns[key] = current_mtime
                return session

            self._cache.pop(key, None)
            self._cache_mtime_ns.pop(key, None)

        session = self._load(key)
        if session is None:
            session = Session(key=key)
            self._cache_persisted_messages_count[key] = 0
            self._cache_persisted_last_consolidated[key] = 0
            self._cache_persisted_last_learned[key] = 0
            self._cache_persisted_metadata_json[key] = "{}"

        self._cache[key] = session
        self._cache_mtime_ns[key] = current_mtime
        return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)

        # Check for legacy migration
        if not path.exists():
            legacy_path = self.legacy_sessions_dir / f"{safe_filename(key)}.jsonl"
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0
            last_learned = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                        last_consolidated = data.get("last_consolidated", 0)
                        last_learned = data.get("last_learned", 0)
                    else:
                        messages.append(data)

            self._cache_persisted_messages_count[key] = len(messages)
            self._cache_persisted_last_consolidated[key] = last_consolidated
            self._cache_persisted_last_learned[key] = last_learned
            self._cache_persisted_metadata_json[key] = json.dumps(metadata, sort_keys=True)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
                last_learned=last_learned,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    async def asave(self, session: Session) -> None:
        """Save a session without blocking the asyncio event loop."""
        await asyncio.to_thread(self.save, session)

    def purge_persisted_session(self, key: str) -> bool:
        """Delete on-disk JSONL for *key* and invalidate related caches.

        Keeps the in-memory session (if any) so an active incognito turn
        continues in RAM. Returns True if a file was removed.
        """
        path = self._get_session_path(key)
        deleted = False
        if path.exists():
            try:
                path.unlink()
                deleted = True
            except OSError as e:
                logger.warning("Failed to purge session file {}: {}", path, e)
        self._cache_persisted_messages_count.pop(key, None)
        self._cache_persisted_last_consolidated.pop(key, None)
        self._cache_persisted_last_learned.pop(key, None)
        self._cache_persisted_metadata_json.pop(key, None)
        self._cache_mtime_ns[key] = None
        # Drop list-cache entries for this path.
        path_str = str(path)
        self._list_sessions_cache = {
            p: v for p, v in self._list_sessions_cache.items() if p != path_str
        }
        return deleted

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        # Incognito: keep in-memory only (lost on restart).
        if session.metadata.get("incognito") or session.metadata.get("ephemeral"):
            self._cache[session.key] = session
            self._cache_mtime_ns[session.key] = None
            # Defense-in-depth: wipe any previously persisted file.
            self.purge_persisted_session(session.key)
            return

        path = self._get_session_path(session.key)
        key = session.key
        path.parent.mkdir(parents=True, exist_ok=True)

        can_append = (
            path.exists()
            and key in self._cache_persisted_messages_count
            and len(session.messages) >= self._cache_persisted_messages_count[key]
            and session.last_consolidated == self._cache_persisted_last_consolidated.get(key, 0)
            and session.last_learned == self._cache_persisted_last_learned.get(key, 0)
            and json.dumps(session.metadata, sort_keys=True)
            == self._cache_persisted_metadata_json.get(key, "{}")
        )

        try:
            if can_append:
                new_msgs = session.messages[self._cache_persisted_messages_count[key] :]
                if new_msgs:
                    with open(path, "a", encoding="utf-8") as f:
                        for msg in new_msgs:
                            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
                self._cache_persisted_messages_count[key] = len(session.messages)
            else:
                tmp_path = path.with_suffix(".jsonl.tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    metadata_line = {
                        "_type": "metadata",
                        "key": session.key,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "metadata": session.metadata,
                        "last_consolidated": session.last_consolidated,
                        "last_learned": session.last_learned,
                    }
                    f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
                    for msg in session.messages:
                        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

                os.replace(tmp_path, path)

                self._cache_persisted_messages_count[key] = len(session.messages)
                self._cache_persisted_last_consolidated[key] = session.last_consolidated
                self._cache_persisted_last_learned[key] = session.last_learned
                self._cache_persisted_metadata_json[key] = json.dumps(
                    session.metadata, sort_keys=True
                )

            self._cache[session.key] = session
            self._cache_mtime_ns[session.key] = self._get_session_mtime_ns(session.key)
        except Exception:
            logger.exception("Failed to save session {}", session.key)

    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)
        self._cache_mtime_ns.pop(key, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with metadata."""
        sessions = []
        new_cache = {}
        try:
            entries = os.scandir(self.sessions_dir)
        except FileNotFoundError:
            return []

        with entries:
            for entry in entries:
                if not entry.is_file() or not entry.name.endswith(".jsonl"):
                    continue
                try:
                    path_str = entry.path
                    mtime = entry.stat().st_mtime

                    cached_data = self._list_sessions_cache.get(path_str)
                    if cached_data and cached_data[0] == mtime:
                        sessions.append(cached_data[1])
                        new_cache[path_str] = cached_data
                        continue

                    updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    with open(path_str, encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line:
                            data = json.loads(first_line)
                            if data.get("_type") == "metadata":
                                meta = data.get("metadata", {})
                                key = data.get("key") or entry.name[:-6].replace("_", ":", 1)
                                session_meta = {
                                    "key": key,
                                    "nickname": meta.get("nickname"),
                                    "profile_id": meta.get("profile_id", "default"),
                                    "created_at": data.get("created_at"),
                                    "updated_at": updated_at,
                                    "path": path_str,
                                }
                                sessions.append(session_meta)
                                new_cache[path_str] = (mtime, session_meta)
                except Exception:
                    continue

        self._list_sessions_cache = new_cache
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def fork_session(self, source_key: str, from_index: int) -> Session | None:
        """Create a new session with messages forked from ``source_key``."""
        src = self.get_or_create(source_key)
        msgs = src.fork_messages(from_index)
        new_key = f"{source_key}:fork:{uuid_short()}"
        session = Session(key=new_key)
        session.messages = msgs
        session.metadata = {
            **{k: v for k, v in src.metadata.items() if k not in {"incognito", "ephemeral"}},
            "forked_from": source_key,
            "fork_index": from_index,
            "nickname": (src.metadata.get("nickname") or source_key) + " (fork)",
        }
        self._cache[new_key] = session
        self.save(session)
        return session

    def rewind_session(self, key: str, to_index: int) -> Session | None:
        session = self.get_or_create(key)
        session.rewind(to_index)
        # Force full rewrite
        self._cache_persisted_messages_count.pop(key, None)
        self.save(session)
        return session

    def search_messages(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Scan session JSONL bodies for an exact case-insensitive phrase.

        Returns newest-first hits with session_key, role, timestamp, snippet.
        """
        needle = (query or "").strip().lower()
        if not needle:
            return []
        try:
            lim = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            lim = 20

        hits: list[dict[str, Any]] = []
        try:
            entries = os.scandir(self.sessions_dir)
        except FileNotFoundError:
            return []

        with entries:
            files = [e for e in entries if e.is_file() and e.name.endswith(".jsonl")]
        files.sort(key=lambda e: e.stat().st_mtime, reverse=True)

        for entry in files:
            if len(hits) >= lim:
                break
            session_key = ""
            try:
                with open(entry.path, encoding="utf-8") as f:
                    for line in f:
                        if len(hits) >= lim:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("_type") == "metadata":
                            session_key = str(data.get("key") or session_key)
                            continue
                        content = data.get("content")
                        if isinstance(content, list):
                            parts: list[str] = []
                            for block in content:
                                if isinstance(block, dict) and isinstance(
                                    block.get("text"), str
                                ):
                                    parts.append(block["text"])
                                elif isinstance(block, str):
                                    parts.append(block)
                            text = "\n".join(parts)
                        elif isinstance(content, str):
                            text = content
                        else:
                            continue
                        if needle not in text.lower():
                            continue
                        if not session_key:
                            session_key = entry.name[:-6].replace("_", ":", 1)
                        idx = text.lower().find(needle)
                        start = max(0, idx - 40)
                        end = min(len(text), idx + len(needle) + 60)
                        snippet = text[start:end].replace("\n", " ")
                        if start > 0:
                            snippet = "…" + snippet
                        if end < len(text):
                            snippet = snippet + "…"
                        hits.append(
                            {
                                "session_key": session_key,
                                "role": data.get("role", ""),
                                "timestamp": data.get("timestamp"),
                                "snippet": snippet[:240],
                            }
                        )
            except OSError:
                continue
        return hits


def uuid_short() -> str:
    import uuid

    return uuid.uuid4().hex[:8]
