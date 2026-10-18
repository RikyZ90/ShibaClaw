"""Spawn tool for creating background subagents."""

import asyncio
from copy import deepcopy
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from shibaclaw.agent.tools.base import Tool

if TYPE_CHECKING:
    from shibaclaw.agent.subagent import SubagentManager


@dataclass(frozen=True)
class _SpawnContext:
    channel: str = "cli"
    chat_id: str = "direct"
    session_key: str = "cli:direct"
    model: str | None = None
    provider: Any | None = None
    ephemeral: bool = False
    allowed_tools: frozenset[str] | None = None
    parent_turn_id: str | None = None
    parent_messages: tuple[dict[str, Any], ...] | None = None


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._context: ContextVar[_SpawnContext] = ContextVar(
            "spawn_context", default=_SpawnContext()
        )

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        model: str | None = None,
        provider: Any | None = None,
        parent_messages: list[dict[str, Any]] | None = None,
        allowed_tools: frozenset[str] | None = None,
        parent_turn_id: str | None = None,
        **options: Any,
    ) -> None:
        """Set the origin context and active LLM configuration for subagent execution."""
        self._context.set(_SpawnContext(
            channel=channel,
            chat_id=chat_id,
            session_key=session_key or f"{channel}:{chat_id}",
            model=model,
            provider=provider,
            ephemeral=bool(options.get("ephemeral", False)),
            allowed_tools=allowed_tools,
            parent_turn_id=parent_turn_id,
            parent_messages=tuple(deepcopy(parent_messages)) if parent_messages is not None else None,
        ))

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["isolated", "fork"],
                    "description": (
                        "Context mode: 'isolated' (default, fresh clean context window for independent research/review) "
                        "or 'fork' (copies supervisor conversation history for worker continuation tasks)."
                    ),
                    "default": "isolated",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        mode: str = "isolated",
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        context = self._context.get()
        extra = {}
        if context.allowed_tools is not None:
            extra["allowed_tools"] = context.allowed_tools
        if context.parent_turn_id is not None:
            extra["parent_turn_id"] = context.parent_turn_id
        if context.ephemeral:
            extra["ephemeral"] = True
        return await self._manager.spawn(
            task=task,
            label=label,
            mode=mode,
            origin_channel=context.channel,
            origin_chat_id=context.chat_id,
            session_key=context.session_key,
            model=context.model,
            provider=context.provider,
            parent_messages=deepcopy(list(context.parent_messages)) if context.parent_messages is not None else None,
            **extra,
        )


class SpawnMeaTool(Tool):
    """Tool to execute a Manage-Execute-Audit (MEA) loop for complex tasks."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        # Shared tools need task-local context across concurrent provider awaits.
        self._context: ContextVar[_SpawnContext] = ContextVar(
            "spawn_mea_context", default=_SpawnContext()
        )

    def set_context(
        self,
        channel: str,
        chat_id: str,
        session_key: str | None = None,
        model: str | None = None,
        provider: Any | None = None,
        ephemeral: bool = False,
        parent_messages: list[dict[str, Any]] | None = None,
        allowed_tools: frozenset[str] | None = None,
        parent_turn_id: str | None = None,
        **options: Any,
    ) -> None:
        """Set the origin context and active LLM configuration for subagent execution."""
        self._context.set(_SpawnContext(
            channel=channel,
            chat_id=chat_id,
            session_key=session_key or f"{channel}:{chat_id}",
            model=model,
            provider=provider,
            allowed_tools=allowed_tools,
            parent_turn_id=parent_turn_id,
            ephemeral=ephemeral,
            parent_messages=tuple(deepcopy(parent_messages)) if parent_messages is not None else None,
        ))

    @property
    def name(self) -> str:
        return "spawn_mea"

    @property
    def description(self) -> str:
        return (
            "Execute a Manage-Execute-Audit (MEA) loop for a complex task. "
            "This runs the task in a clean, fresh context, and then automatically "
            "spawns an auditor subagent to verify the results (e.g., via tests or checks)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The complex task to execute and audit",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["isolated", "fork"],
                    "description": "Context mode for MEA subagents: 'isolated' (default) or 'fork'.",
                    "default": "isolated",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        mode: str = "isolated",
        **kwargs: Any,
    ) -> str:
        """Execute the MEA loop for the given task."""
        context = self._context.get()
        extra = {}
        if context.allowed_tools is not None:
            extra["allowed_tools"] = context.allowed_tools
        if context.parent_turn_id is not None:
            extra["parent_turn_id"] = context.parent_turn_id
        bg_task = asyncio.create_task(
            self._manager.execute_mea_loop(
                task=task,
                label=label,
                origin_channel=context.channel,
                origin_chat_id=context.chat_id,
                session_key=context.session_key,
                model=context.model,
                provider=context.provider,
                ephemeral=context.ephemeral,
                mode=mode,
                parent_messages=deepcopy(list(context.parent_messages)) if context.parent_messages is not None else None,
                **extra,
            )
        )
        self._manager.track(context.session_key, bg_task)
        return f"MEA Loop [{label or task[:30]}] started in the background. I will manage, execute, and audit the task, and notify you when complete."
