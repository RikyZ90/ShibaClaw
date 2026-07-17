"""Brain management for conversation history — the memory of the Shiba."""

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
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

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a legal tool-call boundary."""
        unconsolidated = self.messages[self.last_consolidated :]
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
            for key in ("tool_calls", "tool_call_id", "name"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


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

    def save(self, session: Session) -> None:
        """Save a session to disk."""
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

                    updated_at = datetime.fromtimestamp(mtime).isoformat()
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
