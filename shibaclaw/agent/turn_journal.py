"""Append-only turn journal.

A tool call is recorded before any I/O. The same id is never executed twice.
Input ids dedupe redelivery. Stop is ``hard`` or ``when_idle``.
``root is None`` keeps the journal in memory (incognito / ephemeral).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
RESULT_CAP = 8000
REFUSAL = "Session journal cannot be resumed. This turn was not run."

_OPEN = {"ready", "awaiting", "canceling"}
_UNFINISHED = "This tool call did not finish. It was not started again."
_STOP_HARD = "Stopped. This tool was not started."
_STOP_IDLE = "Stopping when idle. This tool was not started."


class JournalError(Exception):
    """The journal cannot be trusted."""


class UnsupportedVersionError(JournalError):
    """A record version this process does not understand."""


class JournalCorruptError(JournalError):
    """A record could not be parsed. Fail closed."""


@dataclass(frozen=True)
class Claim:
    run: bool
    halt: bool = False
    result: str = ""


class TurnJournal:
    def __init__(self, root: Path | None) -> None:
        self.root = root
        self._memory: dict[str, list[dict[str, Any]]] = {}
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)

    def accept_input(self, session_key: str, input_id: str | None) -> bool:
        """False only after this input's turn was saved.

        A crash before ``commit_turn`` leaves the input open, so a redelivery
        resumes that same turn instead of dropping the request.
        """
        text = str(input_id or "").strip()
        if not text:
            self._open_turn_record(session_key, "")
            return True
        status = self._input_status(session_key, text)
        if status == "done":
            return False
        if status == "open":
            return True
        self._open_turn_record(session_key, text)
        return True

    def commit_turn(self, session_key: str) -> None:
        """The session turn is saved. A redelivery of its input is a duplicate."""
        self._close_open_turn(session_key)

    def scope(self, session_key: str) -> int:
        """Capture a turn scope for work that can outlive the parent turn."""
        return self._scope(session_key)

    def claim(self, session_key: str, op_id: str, tool: str, *, turn: int | None = None) -> Claim:
        """Record ``ready`` before the caller performs I/O."""
        mode = self.stop_mode(session_key)
        if mode == "hard":
            return Claim(False, True, _STOP_HARD)
        if mode == "when_idle":
            return Claim(False, True, _STOP_IDLE)
        op_id = str(op_id or tool)
        turn = self._scope(session_key) if turn is None else turn
        current = self._operations(session_key, turn=turn).get(op_id)
        if current is None:
            self._append(
                session_key,
                {
                    "kind": "operation",
                    "id": op_id,
                    "turn": turn,
                    "tool": tool,
                    "idempotency": op_id,
                    "status": "ready",
                },
            )
            return Claim(True)
        status = current["status"]
        if status in _OPEN:
            self.mark(session_key, op_id, "interrupted", _UNFINISHED, turn=turn)
            return Claim(False, False, _UNFINISHED)
        return Claim(False, False, current["result"] or _UNFINISHED)

    async def execute_claimed(
        self,
        session_key: str,
        op_id: str,
        tool: str,
        run: Callable[[], Awaitable[str]],
        *,
        turn: int | None = None,
    ) -> tuple[str, bool]:
        turn = self._scope(session_key) if turn is None else turn
        claim = self.claim(session_key, op_id, tool, turn=turn)
        if not claim.run:
            return claim.result, claim.halt
        op_id = str(op_id or tool)
        self.mark(session_key, op_id, "awaiting", turn=turn)
        try:
            result = await run()
        except asyncio.CancelledError:
            self.mark(session_key, op_id, "canceled", "canceled", turn=turn)
            raise
        except JournalError:
            raise
        except Exception as exc:
            result = f"Error: Tool '{tool}' failed: {exc}"
            self.mark(session_key, op_id, "failed", result, turn=turn)
            return result, False
        if not isinstance(result, str):
            result = str(result)
        status = "failed" if result.startswith("Error") else "completed"
        self.mark(session_key, op_id, status, result, turn=turn)
        return result, False

    def mark(
        self, session_key: str, op_id: str, status: str, result: str = "", *, turn: int | None = None
    ) -> None:
        if len(result) <= RESULT_CAP:
            stored = result
        else:
            stored = result[:RESULT_CAP] + "\n...[journal truncated]"
        self._append(
            session_key,
            {
                "kind": "operation",
                "id": str(op_id),
                "turn": self._scope(session_key) if turn is None else turn,
                "status": status,
                "result": stored,
            },
        )

    def note_truncation(self, session_key: str, source: str, reason: str) -> None:
        self._append(
            session_key,
            {"kind": "context", "change": "truncated", "source": source, "reason": reason},
        )

    def consume_interruptions(self, session_key: str) -> str | None:
        pending = [op for op in self._operations(session_key).values() if op["status"] in _OPEN]
        if not pending:
            return None
        lines = []
        for op in pending:
            self.mark(session_key, op["id"], "interrupted", _UNFINISHED)
            lines.append(f"- {op['tool'] or 'tool'} ({op['id']})")
        body = "\n".join(lines)
        return "[journal] These tool calls did not finish and were not started again:\n" + body

    def request_stop(self, session_key: str, mode: str) -> None:
        if mode not in {"hard", "when_idle"}:
            raise ValueError(mode)
        self._append(session_key, {"kind": "stop", "mode": mode})
        if mode != "hard":
            return
        for op in list(self._operations(session_key).values()):
            if op["status"] in _OPEN:
                self.mark(session_key, op["id"], "canceled", "canceled")

    def stop_mode(self, session_key: str) -> str | None:
        mode = ""
        for row in self._load(session_key):
            if row.get("kind") == "stop":
                mode = str(row.get("mode") or "")
        return mode or None

    def clear_stop(self, session_key: str) -> None:
        if self.stop_mode(session_key):
            self._append(session_key, {"kind": "stop", "mode": ""})

    def _scope(self, session_key: str) -> int:
        """Open turn, or 0 when the caller has not started one."""
        return self._open_turn(session_key) or 0

    def _open_turn(self, session_key: str) -> int | None:
        open_id: int | None = None
        for row in self._load(session_key):
            if row.get("kind") != "turn":
                continue
            turn_id = int(row["id"])
            if row.get("status") == "open":
                open_id = turn_id
            elif row.get("status") == "done" and open_id == turn_id:
                open_id = None
        return open_id

    def _open_turn_record(self, session_key: str, input_id: str) -> int:
        self._close_open_turn(session_key)
        turn_id = 1
        for row in self._load(session_key):
            if row.get("kind") == "turn":
                turn_id = max(turn_id, int(row["id"]) + 1)
        self._append(
            session_key,
            {"kind": "turn", "id": turn_id, "status": "open", "input": input_id},
        )
        if input_id:
            self._append(
                session_key,
                {"kind": "input", "id": input_id, "status": "open", "turn": turn_id},
            )
        return turn_id

    def _close_open_turn(self, session_key: str) -> None:
        turn_id = self._open_turn(session_key)
        if turn_id is None:
            return
        input_id = ""
        for row in self._load(session_key):
            if row.get("kind") == "turn" and int(row.get("id") or 0) == turn_id:
                input_id = str(row.get("input") or "")
        self._append(session_key, {"kind": "turn", "id": turn_id, "status": "done"})
        if input_id:
            self._append(
                session_key,
                {"kind": "input", "id": input_id, "status": "done", "turn": turn_id},
            )

    def _input_status(self, session_key: str, input_id: str) -> str | None:
        status: str | None = None
        for row in self._load(session_key):
            if row.get("kind") == "input" and str(row.get("id") or "") == input_id:
                status = str(row.get("status") or "open")
        return status

    def _operations(self, session_key: str, *, turn: int | None = None) -> dict[str, dict[str, str]]:
        scope = self._scope(session_key) if turn is None else turn
        found: dict[str, dict[str, str]] = {}
        for row in self._load(session_key):
            if row.get("kind") != "operation":
                continue
            op_id = str(row.get("id") or "")
            if not op_id:
                continue
            row_turn = int(row["turn"]) if "turn" in row else 0
            if row_turn != scope:
                continue
            current = found.setdefault(op_id, {"id": op_id, "tool": "", "status": "", "result": ""})
            if row.get("tool"):
                current["tool"] = str(row["tool"])
            if row.get("status"):
                current["status"] = str(row["status"])
            if row.get("result") is not None and "result" in row:
                current["result"] = str(row.get("result") or "")
        return found

    def _append(self, session_key: str, row: dict[str, Any]) -> None:
        record = {"v": FORMAT_VERSION, "session": session_key, **row}
        if self.root is None:
            self._memory.setdefault(session_key, []).append(record)
            return
        path = self._path(session_key)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _load(self, session_key: str) -> list[dict[str, Any]]:
        if self.root is None:
            return list(self._memory.get(session_key, []))
        path = self._path(session_key)
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalCorruptError(f"{path.name}:{lineno}") from exc
            if not isinstance(row, dict) or row.get("v") != FORMAT_VERSION:
                raise UnsupportedVersionError(f"{path.name}:{lineno}")
            rows.append(row)
        return rows

    def _path(self, session_key: str) -> Path:
        assert self.root is not None
        digest = hashlib.sha256(session_key.encode()).hexdigest()
        return self.root / f"{digest}.jsonl"
