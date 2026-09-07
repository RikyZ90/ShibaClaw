"""Skill Workshop: pending skill proposals (max 3) with approve/reject."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_MAX_PENDING = 3
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class SkillWorkshop:
    """Queue of proposed skills under workspace/skills/_workshop/."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.root = workspace / "skills" / "_workshop"
        self.pending_path = self.root / "pending.json"

    def _load(self) -> list[dict[str, Any]]:
        if not self.pending_path.exists():
            return []
        try:
            data = json.loads(self.pending_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.pending_path.write_text(
            json.dumps(items, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_pending(self) -> list[dict[str, Any]]:
        return self._load()

    def propose(
        self,
        *,
        name: str,
        description: str,
        skill_md: str,
        source: str = "agent",
    ) -> dict[str, Any]:
        name = (name or "").strip()
        if not _SAFE_NAME.match(name):
            return {"ok": False, "error": "invalid skill name"}
        if name.startswith("_"):
            return {"ok": False, "error": "name cannot start with underscore"}
        body = (skill_md or "").strip()
        if not body:
            return {"ok": False, "error": "skill_md required"}
        items = self._load()
        if len(items) >= _MAX_PENDING:
            return {
                "ok": False,
                "error": f"workshop queue full (max {_MAX_PENDING}); approve or reject first",
            }
        if any(i.get("name") == name for i in items):
            return {"ok": False, "error": f"proposal already pending for {name}"}
        item = {
            "id": f"{name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "name": name,
            "description": (description or "").strip()[:300],
            "skill_md": body,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        items.append(item)
        self._save(items)
        return {"ok": True, "proposal": {k: v for k, v in item.items() if k != "skill_md"}}

    def reject(self, proposal_id: str) -> dict[str, Any]:
        items = self._load()
        keep = [i for i in items if i.get("id") != proposal_id]
        if len(keep) == len(items):
            return {"ok": False, "error": "not found"}
        self._save(keep)
        return {"ok": True}

    def approve(self, proposal_id: str) -> dict[str, Any]:
        items = self._load()
        match = next((i for i in items if i.get("id") == proposal_id), None)
        if not match:
            return {"ok": False, "error": "not found"}
        name = match["name"]
        dest = self.workspace / "skills" / name
        if dest.exists():
            return {"ok": False, "error": f"skill {name} already exists"}
        try:
            dest.mkdir(parents=True, exist_ok=False)
            (dest / "SKILL.md").write_text(match.get("skill_md") or "", encoding="utf-8")
        except Exception as e:
            logger.error("workshop approve failed: {}", e)
            return {"ok": False, "error": str(e)}
        self._save([i for i in items if i.get("id") != proposal_id])
        return {"ok": True, "name": name, "path": str(dest)}
