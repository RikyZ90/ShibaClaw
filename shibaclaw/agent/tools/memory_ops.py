"""Memory maintenance tools: forget lines and propose skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shibaclaw.agent.memory import ScentKeeper
from shibaclaw.agent.skill_workshop import SkillWorkshop
from shibaclaw.agent.tools.base import Tool


class MemoryForgetTool(Tool):
    """Remove matching lines from MEMORY.md and HISTORY.md."""

    def __init__(self, workspace: Path):
        self._store = ScentKeeper(workspace)

    @property
    def name(self) -> str:
        return "memory_forget"

    @property
    def description(self) -> str:
        return (
            "Preview or remove lines containing a needle string from MEMORY.md and "
            "HISTORY.md (case-insensitive). Default is preview-only; set confirm=true "
            "after showing the user the preview to quarantine and delete matches. "
            "Does not delete the files. Use when the user asks to forget specific facts "
            "or redact sensitive text from long-term memory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "needle": {
                    "type": "string",
                    "description": "Substring to match; matching lines are removed when confirmed.",
                },
                "confirm": {
                    "type": "boolean",
                    "description": (
                        "Must be true to actually quarantine/remove. "
                        "False/omitted returns a preview only."
                    ),
                },
            },
            "required": ["needle"],
        }

    async def execute(self, *, needle: str, confirm: bool = False, **_: Any) -> str:
        if not (needle or "").strip():
            return "Error: needle is required."
        counts = await self._store.forget_memory_lines(needle, confirm=bool(confirm))
        if counts.get("error"):
            return f"Error: {counts['error']}"
        if counts.get("preview"):
            return json.dumps({"ok": True, **counts}, ensure_ascii=False)
        return json.dumps({"ok": True, "removed": counts}, ensure_ascii=False)


class ProposeSkillTool(Tool):
    """Queue a skill proposal in the Skill Workshop."""

    def __init__(self, workspace: Path):
        self._workshop = SkillWorkshop(workspace)

    @property
    def name(self) -> str:
        return "propose_skill"

    @property
    def description(self) -> str:
        return (
            "Propose a new agent skill for owner review. Queues SKILL.md content in "
            "the Skill Workshop (max 3 pending). Does not install until approved."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill directory name (alphanumeric, dash, underscore).",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of what the skill does.",
                },
                "skill_md": {
                    "type": "string",
                    "description": "Full SKILL.md markdown content.",
                },
            },
            "required": ["name", "description", "skill_md"],
        }

    async def execute(
        self,
        *,
        name: str,
        description: str,
        skill_md: str,
        **_: Any,
    ) -> str:
        result = self._workshop.propose(
            name=name,
            description=description,
            skill_md=skill_md,
            source="agent",
        )
        return json.dumps(result, ensure_ascii=False)
