"""Project verification uses process evidence, preserves permissions and survives reloads."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from shibaclaw.agent.sandbox_ctx import bind_permission_mode, reset_permission_mode
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.agent.task_runs import TaskRuns
from shibaclaw.agent.tools.shell import ExecTool
from shibaclaw.agent.tools.spawn import SpawnTool, SpawnMeaTool
from shibaclaw.agent.turn_journal import TurnJournal
from shibaclaw.agent.verification import prepare_verification, run_verification
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.schema import ExecToolConfig, VerificationConfig

KEY = "webui:project-checks"


@pytest.fixture(autouse=True)
def python_on_path(monkeypatch):
    monkeypatch.setenv(
        "PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    )


def command(project, source, filename="check.py"):
    (project / filename).write_text(source, encoding="utf-8")
    return f"{Path(sys.executable).name} {filename}"


def manager(workspace, checks, **kwargs):
    provider = MagicMock()
    provider.get_default_model.return_value = "fixture"
    m = SubagentManager(
        provider,
        workspace,
        MessageBus(),
        verification_config=VerificationConfig(
            projects={"demo": {"path": "project", "checks": checks}}
        ),
        **kwargs,
    )
    m._run_subagent_inner = AsyncMock(return_value="All done. PASSED")
    return m


async def finish(m):
    await asyncio.gather(*list(m._running_tasks.values()))
    await asyncio.sleep(0)
    return m.snapshot(KEY)[0]


@pytest.mark.parametrize("tool_class", [SpawnTool, SpawnMeaTool])
async def test_actual_exit_code_overrides_a_claim_of_success_and_persists(tmp_path, tool_class):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "print('PASSED\\nExit code: 0')\nraise SystemExit(7)")
    m = manager(tmp_path, [{"name": "Tests", "command": cmd}])
    m._execute_mea_loop = AsyncMock(
        return_value={
            "status": "completed",
            "verdict": "PASSED",
            "execution_result": "Done",
            "audit_result": "PASSED",
        }
    )
    tool = tool_class(m)
    tool.set_context("webui", "project-checks", KEY)
    assert tool.parameters["properties"]["verification_project"]["enum"] == ["demo"]
    await tool.execute("Fix the project", verification_project="demo")
    row = await finish(m)
    assert row["execution_status"] == "succeeded"
    assert row["verification"]["status"] == "failed"
    check = row["verification"]["checks"][0]
    assert check["exit_code"] == 7
    assert "PASSED" in check["output"]
    assert check["duration_ms"] >= 0
    assert TaskRuns(tmp_path).snapshot(KEY)[0]["verification"] == row["verification"]
    message = await m.bus.consume_inbound()
    assert "Verification: failed" in message.content
    assert "completed successfully" not in message.content


async def test_success_requires_all_checks_and_uses_project_cwd(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "expected.txt").write_text("ok", encoding="utf-8")
    cmd = command(
        project,
        "from pathlib import Path\nassert Path('expected.txt').read_text() == 'ok'\nprint('checked')",
    )
    m = manager(tmp_path, [{"name": "Files", "command": cmd}, {"name": "Build", "command": cmd}])

    async def worker(*args, **kwargs):
        assert m._worker_workspace() == project
        return "Done"

    m._run_subagent_inner = worker
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await finish(m)
    assert row["verification"]["status"] == "passed"
    assert [c["exit_code"] for c in row["verification"]["checks"]] == [0, 0]


async def test_unselected_project_never_runs_checks_or_claims_verification(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "from pathlib import Path\nPath('ran').touch()")
    m = manager(tmp_path, [{"name": "Unexpected", "command": cmd}])
    await m.spawn("Research only", "webui", "project-checks", KEY)
    row = await finish(m)
    assert row["verification"]["status"] == "not_configured"
    assert not (project / "ran").exists()


@pytest.mark.parametrize("blocked_by", ["global", "profile", "readonly"])
async def test_checks_cannot_bypass_exec_permissions(tmp_path, blocked_by):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "from pathlib import Path\nPath('ran').touch()")
    m = manager(
        tmp_path,
        [{"name": "Check", "command": cmd}],
        exec_config=ExecToolConfig(enable=blocked_by != "global"),
    )
    tokens = bind_permission_mode("readonly", tmp_path) if blocked_by == "readonly" else None
    try:
        await m.spawn(
            "task",
            "webui",
            "project-checks",
            KEY,
            verification_project="demo",
            allowed_tools=frozenset({"read_file"}) if blocked_by == "profile" else None,
        )
        row = await finish(m)
    finally:
        reset_permission_mode(tokens)
    assert row["verification"]["status"] == "blocked"
    assert not (project / "ran").exists()


async def test_invalid_project_is_rejected_before_starting_a_worker(tmp_path):
    m = manager(tmp_path, [{"name": "Check", "command": "python check.py"}])
    for tool_class in (SpawnTool, SpawnMeaTool):
        tool = tool_class(m)
        assert (await tool.execute("task", verification_project="unknown")).startswith("Error:")
        assert (await tool.execute("task", verification_project="demo")).startswith("Error:")
    assert not m._running_tasks
    assert not m.snapshot(KEY)


def test_project_paths_obey_scope_and_symlinks(tmp_path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    config = VerificationConfig(
        projects={
            "demo": {
                "path": str(outside),
                "checks": [{"name": "Check", "command": "python check.py"}],
            }
        }
    )
    with pytest.raises(ValueError, match="outside"):
        prepare_verification(config, "demo", workspace, True)
    try:
        (workspace / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is not available")
    config.projects["demo"].path = "linked"
    with pytest.raises(ValueError, match="outside"):
        prepare_verification(config, "demo", workspace, True)


async def test_guard_rejection_has_no_exit_code_and_cannot_pass(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    m = manager(tmp_path, [{"name": "Blocked", "command": "rm -rf example"}])
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await finish(m)
    assert row["verification"]["status"] == "blocked"
    assert row["verification"]["checks"][0]["exit_code"] is None


async def test_check_timeout_retains_output_and_never_passes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "import time\nprint('started', flush=True)\ntime.sleep(60)")
    m = manager(tmp_path, [{"name": "Slow", "command": cmd, "timeout": 1}])
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await asyncio.wait_for(finish(m), 5)
    assert row["verification"]["status"] == "timed_out"
    assert "started" in row["verification"]["checks"][0]["output"]


async def test_timeout_stops_child_processes_as_well_as_the_test_runner(tmp_path):
    child = "from pathlib import Path\nimport time\nwhile True:\n    with Path('heartbeats').open('a') as stream:\n        stream.write('.')\n    time.sleep(0.02)"
    cmd = command(
        tmp_path,
        f"import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', {child!r}])\ntime.sleep(60)",
    )
    result = await ExecTool(install_audit=False).execute_result(cmd, str(tmp_path), timeout=2)
    assert result.status == "timed_out"
    heartbeat = tmp_path / "heartbeats"
    assert heartbeat.exists()
    count = heartbeat.stat().st_size
    await asyncio.sleep(0.15)
    assert heartbeat.stat().st_size == count


async def test_quoted_script_arguments_work_with_the_structured_executor(tmp_path):
    command(tmp_path, "print('ok')", filename="check with spaces.py")
    result = await ExecTool(install_audit=False).execute_result(
        f'{Path(sys.executable).name} "check with spaces.py"', str(tmp_path), timeout=5
    )
    assert result.exit_code == 0
    assert "ok" in result.output


async def test_stop_idle_prevents_later_checks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "print('first check')")
    later = command(
        project, "from pathlib import Path\nPath('unexpected').touch()", filename="later.py"
    )
    m = manager(tmp_path, [{"name": "First", "command": cmd}, {"name": "Later", "command": later}])
    original_status = m._status

    async def status(task_id, origin, **changes):
        checks = changes.get("verification", {}).get("checks", [])
        if checks and checks[0]["status"] == "passed":
            m.request_stop(KEY, "when_idle")
        await original_status(task_id, origin, **changes)

    m._status = status
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await finish(m)
    assert row["verification"]["status"] == "cancelled"
    assert row["verification"]["checks"][0]["status"] == "passed"
    assert row["verification"]["checks"][1]["status"] == "not_run"
    assert not (project / "unexpected").exists()


async def test_overall_timeout_during_verification_keeps_execution_outcome(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "import time\ntime.sleep(60)")
    m = manager(tmp_path, [{"name": "Slow", "command": cmd}], timeout=0.2)
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await finish(m)
    assert row["status"] == "timed_out"
    assert row["execution_status"] == "succeeded"
    assert row["verification"]["status"] == "timed_out"


async def test_cancel_during_verification_retains_successful_execution_and_is_private(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(
        project, "import time\nfrom pathlib import Path\nPath('started').touch()\ntime.sleep(60)"
    )
    m = manager(tmp_path, [{"name": "Private", "command": cmd}])
    await m.spawn(
        "task", "webui", "project-checks", KEY, verification_project="demo", ephemeral=True
    )
    for _ in range(200):
        if (project / "started").exists():
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Check never started")
    row = m.snapshot(KEY)[0]
    await m.cancel_task(KEY, row["task_id"])
    row = m.snapshot(KEY)[0]
    assert row["status"] == "cancelled"
    assert row["execution_status"] == "succeeded"
    assert row["verification"]["status"] == "cancelled"
    assert not m.runs._path(KEY).exists()
    assert not list((tmp_path / "runtime").rglob("*.jsonl"))


async def test_long_logs_are_bounded_and_declared(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(project, "print('x' * 1000000)\nprint('tail-marker')")
    m = manager(tmp_path, [{"name": "Verbose", "command": cmd}])
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    row = await finish(m)
    check = row["verification"]["checks"][0]
    assert check["exit_code"] == 0
    assert check["output_truncated"]
    assert len(check["output"]) < 6100
    assert "tail-marker" in check["output"]


async def test_journal_prevents_replaying_a_completed_check(tmp_path):
    cmd = command(
        tmp_path,
        "from pathlib import Path\np = Path('count')\np.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')",
    )
    config = VerificationConfig(projects={"demo": {"checks": [{"name": "Count", "command": cmd}]}})
    plan = prepare_verification(config, "demo", tmp_path, True)
    journal = TurnJournal(tmp_path / "journal")
    kwargs = dict(
        executor=ExecTool(install_audit=False),
        workspace=tmp_path,
        restrict=True,
        exec_allowed=True,
        journal=journal,
        session_key=KEY,
        task_id="same-task",
        stop_reason=lambda: None,
        progress=AsyncMock(),
    )
    assert (await run_verification(plan, **kwargs))["status"] == "passed"
    assert (await run_verification(plan, **kwargs))["status"] == "passed"
    assert (tmp_path / "count").read_text() == "1"


async def test_escaped_unicode_logs_remain_valid_evidence_when_replayed(tmp_path):
    cmd = command(tmp_path, "print('é' * 3000 + '\\x01' * 3000)")
    config = VerificationConfig(projects={"demo": {"checks": [{"name": "Log", "command": cmd}]}})
    plan = prepare_verification(config, "demo", tmp_path, True)
    journal = TurnJournal(tmp_path / "journal")
    kwargs = dict(
        executor=ExecTool(install_audit=False),
        workspace=tmp_path,
        restrict=True,
        exec_allowed=True,
        journal=journal,
        session_key=KEY,
        task_id="same-task",
        stop_reason=lambda: None,
        progress=AsyncMock(),
    )
    first = await run_verification(plan, **kwargs)
    second = await run_verification(plan, **kwargs)
    assert first["status"] == second["status"] == "passed"
    assert second["checks"][0]["output"] == first["checks"][0]["output"]
    assert first["checks"][0]["output_truncated"]


async def test_uncertain_journal_claim_is_not_executed_again(tmp_path):
    cmd = command(tmp_path, "from pathlib import Path\nPath('unexpected').touch()")
    config = VerificationConfig(projects={"demo": {"checks": [{"name": "Once", "command": cmd}]}})
    plan = prepare_verification(config, "demo", tmp_path, True)
    journal = TurnJournal(tmp_path / "journal")
    journal.claim(KEY, "same-task:verification:0", "verification")
    journal.mark(KEY, "same-task:verification:0", "awaiting")
    result = await run_verification(
        plan,
        executor=ExecTool(install_audit=False),
        workspace=tmp_path,
        restrict=True,
        exec_allowed=True,
        journal=journal,
        session_key=KEY,
        task_id="same-task",
        stop_reason=lambda: None,
        progress=AsyncMock(),
    )
    assert result["status"] == "incomplete"
    assert not (tmp_path / "unexpected").exists()


def test_restart_marks_partial_checks_incomplete_without_losing_evidence(tmp_path):
    runs = TaskRuns(tmp_path)
    runs.put(
        KEY,
        "task",
        status="running",
        execution_status="succeeded",
        verification={
            "status": "running",
            "checks": [
                {"name": "Done", "status": "passed", "exit_code": 0, "output": "ok"},
                {"name": "Interrupted", "status": "running", "exit_code": None},
            ],
        },
    )
    (row,) = TaskRuns(tmp_path).snapshot(KEY)
    assert row["status"] == "incomplete"
    assert row["execution_status"] == "succeeded"
    assert row["verification"]["status"] == "incomplete"
    assert row["verification"]["checks"][0]["output"] == "ok"
    assert row["verification"]["checks"][1]["status"] == "incomplete"


async def test_incognito_toggle_during_a_check_does_not_persist_its_output(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    cmd = command(
        project,
        "from pathlib import Path\nimport time\nPath('started').touch()\ntime.sleep(0.3)\nprint('sensitive-check-output')",
    )
    journal = TurnJournal(tmp_path / "runtime" / "turns")
    runner = MagicMock()
    runner._checkpoint_forbidden.return_value = False
    runner._journal_for.return_value = journal
    m = manager(tmp_path, [{"name": "Check", "command": cmd}], agent_runner=runner)
    await m.spawn("task", "webui", "project-checks", KEY, verification_project="demo")
    for _ in range(200):
        if (project / "started").exists():
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Check never started")
    m.runs.set_private(KEY, persist=True)
    row = await finish(m)
    assert row["verification"]["status"] == "passed"
    assert "sensitive-check-output" in row["verification"]["checks"][0]["output"]
    assert journal.root is not None
    assert not m.runs._path(KEY).exists()
    assert all("sensitive-check-output" not in p.read_text() for p in journal.root.glob("*.jsonl"))


def test_verification_config_rejects_unbounded_or_empty_checks():
    for checks in (
        [],
        [{"name": "X", "command": "python check.py", "timeout": 0}],
        [{"name": "X", "command": "python check.py", "timeout": 601}],
    ):
        with pytest.raises(ValidationError):
            VerificationConfig(projects={"demo": {"checks": checks}})
