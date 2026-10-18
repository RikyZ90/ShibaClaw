"""Bounded, session-scoped delegation history. Private run content never touches disk."""

import hashlib
import json
import os
import time
from copy import deepcopy
from pathlib import Path

from loguru import logger
from shibaclaw.agent.verification import finish_verification

TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "incomplete"}


class TaskRuns:
    def __init__(self, workspace: Path):
        self.root = workspace / "memory" / "task_runs"
        self.sessions: dict[str, dict[str, dict]] = {}
        self.private: set[str] = set()

    def _path(self, key: str) -> Path:
        return self.root / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def is_private(self, key: str) -> bool:
        if self._path(key).with_suffix(".private").exists():
            self.private.add(key)
        return key in self.private

    def snapshot(self, key: str) -> list[dict]:
        self.is_private(key)
        if key not in self.sessions:
            rows = []
            if key not in self.private:
                try:
                    rows = json.loads(self._path(key).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    pass
            self.sessions[key] = {}
            for row in rows if isinstance(rows, list) else []:
                if (
                    not isinstance(row, dict)
                    or row.get("session_key") != key
                    or not row.get("task_id")
                ):
                    continue
                if row.get("status") not in TERMINAL:
                    row["verification"] = finish_verification(row.get("verification", {}), "incomplete")
                    if row.get("execution_status") in {None, "running"}:
                        row["execution_status"] = "incomplete"
                    row.update(
                        status="incomplete",
                        error="Gateway restarted before this task finished.",
                        finished_at=time.time(),
                    )
                    row["revision"] = row.get("revision", 0) + 1
                self.sessions[key][row["task_id"]] = row
        return deepcopy(list(self.sessions[key].values()))

    def put(self, key: str, task_id: str, **changes) -> dict:
        self.snapshot(key)
        rows = self.sessions[key]
        row = rows.setdefault(task_id, {"task_id": task_id, "session_key": key, "revision": 0})
        # Terminal outcomes cannot be overwritten by delayed progress events.
        if row.get("status") in TERMINAL:
            return deepcopy(row)
        row.update(changes)
        row["revision"] += 1
        if row.get("status") in TERMINAL:
            row["finished_at"] = time.time()
        completed = [tid for tid, item in rows.items() if item.get("status") in TERMINAL]
        for tid in completed[:-100]:
            rows.pop(tid, None)
        self._save(key)
        return deepcopy(row)

    def set_private(self, key: str, *, persist: bool = False) -> None:
        self.private.add(key)
        if persist:
            # A content-free tombstone lets an offline gateway observe a privacy
            # toggle before its next write, without storing private task content.
            self.root.mkdir(parents=True, exist_ok=True)
            self._path(key).with_suffix(".private").touch()
        self._path(key).unlink(missing_ok=True)

    def clear(self, key: str) -> None:
        self.sessions[key] = {}
        self._path(key).unlink(missing_ok=True)

    def _save(self, key: str) -> None:
        if key in self.private or self._path(key).with_suffix(".private").exists():
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self._path(key)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(list(self.sessions[key].values()), ensure_ascii=False), encoding="utf-8"
            )
            os.replace(tmp, path)
            if self._path(key).with_suffix(".private").exists():
                path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not persist task history: {}", exc)
