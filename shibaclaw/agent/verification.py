"""Operator-configured project checks, with process-backed evidence."""

import asyncio
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Awaitable, Callable

from shibaclaw.agent.sandbox_ctx import turn_permission_mode, turn_permission_workspace
from shibaclaw.agent.tools.shell import ExecTool
from shibaclaw.agent.turn_journal import JournalError, TurnJournal, RESULT_CAP
from shibaclaw.config.schema import VerificationConfig


def finish_verification(plan: dict, status: str) -> dict:
    result = deepcopy(plan)
    if result.get("status") in {"pending", "running"} or (
        status == "timed_out" and result.get("status") == "cancelled"
    ):
        outcome = status if status in {"cancelled", "timed_out"} else "incomplete"
        result.update(status=outcome, finished_at=time.time())
        for check in result.get("checks", []):
            if check["status"] in {"pending", "running"} or (
                status == "timed_out" and check["status"] == "cancelled"
            ):
                check.update(status=outcome, finished_at=time.time())
    return result


def project_path(workspace: Path, configured: str, restrict: bool) -> Path:
    path = Path(configured).expanduser()
    path = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
    mode = turn_permission_mode()
    restricted = restrict if mode is None else mode != "full"
    root = (turn_permission_workspace() or workspace).resolve()
    if restricted and not path.is_relative_to(root):
        raise ValueError("Verification project is outside the permitted workspace.")
    if not path.is_dir():
        raise ValueError("Verification project directory does not exist.")
    return path


def prepare_verification(
    config: VerificationConfig, project: str | None, workspace: Path, restrict: bool
) -> dict:
    if project is None:
        return {"status": "not_configured", "checks": []}
    if project not in config.projects:
        raise ValueError(f"Unknown verification project: {project}")
    settings = config.projects[project]
    cwd = project_path(workspace, settings.path, restrict)
    return {
        "project": project,
        "cwd": str(cwd),
        "status": "pending",
        "checks": [
            {**check.model_dump(), "status": "pending", "exit_code": None, "output": ""}
            for check in settings.checks
        ],
    }


async def run_verification(
    plan: dict,
    *,
    executor: ExecTool,
    workspace: Path,
    restrict: bool,
    exec_allowed: bool,
    journal: TurnJournal,
    session_key: str,
    task_id: str,
    stop_reason: Callable[[], str | None],
    progress: Callable[[dict], Awaitable[None]],
    is_private: Callable[[], bool] | None = None,
) -> dict:
    """Run each configured check once. No model text determines the outcome."""
    result = deepcopy(plan)
    if result["status"] == "not_configured":
        return result
    if not exec_allowed or turn_permission_mode() == "readonly":
        result.update(status="blocked", reason="Exec is disabled by the task's permissions.")
        for check in result["checks"]:
            check["status"] = "not_run"
        await progress(result)
        return result

    result.update(status="running", started_at=time.time())
    await progress(result)
    try:
        if is_private and is_private():
            journal.root = None
        turn = journal.scope(session_key)
        for index, check in enumerate(result["checks"]):
            if reason := stop_reason():
                result.update(status="cancelled", reason=reason)
                break
            # Recheck symlinks and directory scope before every invocation.
            if project_path(workspace, result["cwd"], restrict) != Path(result["cwd"]):
                raise ValueError("Verification project directory changed during the task.")
            check.update(status="running", started_at=time.time())
            await progress(result)

            async def execute() -> str:
                try:
                    evidence = await executor.execute_result(
                        check["command"], working_dir=result["cwd"], timeout=check["timeout"]
                    )
                finally:
                    # execute_claimed records the outcome only after this returns.
                    if is_private and is_private():
                        journal.root = None
                output = evidence.output
                if len(output) > 6000:
                    output = (
                        output[:3000] + "\n...[verification log truncated]...\n" + output[-3000:]
                    )
                payload = {
                    "status": evidence.status,
                    "exit_code": evidence.exit_code,
                    "output": output,
                    "output_truncated": len(evidence.output) > 6000,
                }
                # Escaped newlines/control characters must fit the journal too.
                encoded = json.dumps(payload, ensure_ascii=False)
                while len(encoded) > RESULT_CAP:
                    half = len(payload["output"]) // 3
                    payload["output"] = (
                        payload["output"][:half]
                        + "\n...[verification log truncated]...\n"
                        + payload["output"][-half:]
                    )
                    payload["output_truncated"] = True
                    encoded = json.dumps(payload, ensure_ascii=False)
                return encoded

            if is_private and is_private():
                journal.root = None
            stored, halt = await journal.execute_claimed(
                session_key, f"{task_id}:verification:{index}", "verification", execute, turn=turn
            )
            if halt:
                check.update(status="incomplete", output=stored)
            else:
                # This JSON is generated by execute(), never by stdout or an LLM.
                evidence = json.loads(stored)
                check.update(evidence)
            check["finished_at"] = time.time()
            check["duration_ms"] = round((check["finished_at"] - check["started_at"]) * 1000)
            await progress(result)
            if halt:
                result.update(
                    status="incomplete", reason="A previous check has an uncertain outcome."
                )
                break
        else:
            statuses = {c["status"] for c in result["checks"]}
            result["status"] = (
                "passed"
                if all(c["status"] == "passed" and c["exit_code"] == 0 for c in result["checks"])
                else next(
                    (
                        state
                        for state in ("failed", "timed_out", "blocked", "incomplete")
                        if state in statuses
                    ),
                    "incomplete",
                )
            )
    except asyncio.CancelledError:
        result["status"] = "cancelled"
        for check in result["checks"]:
            if check["status"] == "running":
                check.update(status="cancelled", finished_at=time.time())
        result["finished_at"] = time.time()
        await progress(result)
        raise
    except (JournalError, OSError, ValueError) as exc:
        result.update(status="incomplete", reason=str(exc))
    for check in result["checks"]:
        if check["status"] == "pending":
            check["status"] = "not_run"
        elif check["status"] == "running":
            check.update(status="incomplete", finished_at=time.time())
    result["finished_at"] = time.time()
    await progress(result)
    return result
