"""Gateway/CLI store updates must preserve acknowledged and pending changes."""

import json
import asyncio
import os
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from shibaclaw.automation.grants import job_is_approved
from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationPayload, AutomationSchedule


def service_at(path):
    return AutomationService(path / "automation.json", workspace=path)


def add_job(service, name="task", **kwargs):
    return service.add_job(
        name,
        AutomationSchedule(kind="every", every_ms=60000),
        AutomationPayload(message=name),
        **kwargs,
    )


def test_disable_preserves_new_external_job(tmp_path):
    initial = service_at(tmp_path)
    job = add_job(initial)
    live = service_at(tmp_path)
    external = service_at(tmp_path)
    external_job = add_job(external, "CLI task")

    disabled = live.enable_job(job.id, False)

    assert disabled is live.get_job(job.id)
    assert disabled.enabled is False
    assert disabled.state.next_run_at_ms == 0
    disk = service_at(tmp_path)
    assert disk.get_job(job.id).enabled is False
    assert disk.get_job(external_job.id) is not None


def test_add_from_stale_service_preserves_all_acknowledged_ids(tmp_path):
    live = service_at(tmp_path)
    external = service_at(tmp_path)
    remote = add_job(external, "CLI task")

    local = add_job(live, "gateway task")

    assert live.get_job(local.id) is local
    assert {job.id for job in service_at(tmp_path).list_jobs()} == {remote.id, local.id}


def test_reload_merges_pending_run_state_and_preserves_job_reference(tmp_path):
    live = service_at(tmp_path)
    job = add_job(live)
    external = service_at(tmp_path)
    # A background run has completed but its coalesced save has not fired yet.
    job.state.run_count = 1
    job.state.last_status = "ok"
    job.state.last_run_at_ms = 123
    external.update_job(job.id, {"payload": {"message": "edited by CLI"}})

    assert live.sync_from_disk()
    assert live.get_job(job.id) is job
    assert job.payload.message == "edited by CLI"
    assert job.state.run_count == 1
    live._save_unlocked()

    persisted = service_at(tmp_path).get_job(job.id)
    assert persisted.payload.message == "edited by CLI"
    assert persisted.state.run_count == 1
    assert persisted.state.last_status == "ok"
    assert persisted.state.last_run_at_ms == 123


def test_pending_one_shot_removal_survives_reload(tmp_path):
    live = service_at(tmp_path)
    completed = add_job(live)
    external = service_at(tmp_path)
    live._jobs.pop(completed.id)  # delete_after_run before the background save
    remote = add_job(external, "CLI task")

    assert live.sync_from_disk()
    live._save_unlocked()

    assert {job.id for job in service_at(tmp_path).list_jobs()} == {remote.id}


def test_external_deletion_is_not_resurrected_by_pending_run_state(tmp_path):
    live = service_at(tmp_path)
    job = add_job(live)
    external = service_at(tmp_path)
    job.state.last_status = "ok"
    external.remove_job(job.id)

    live._save_unlocked()

    assert live.get_job(job.id) is None
    assert service_at(tmp_path).get_job(job.id) is None
    assert live.enable_job(job.id) is None


def test_running_job_completion_is_not_lost_during_executor_reload(tmp_path, monkeypatch):
    live = service_at(tmp_path)
    job = add_job(live)
    external = service_at(tmp_path)
    callback_started = threading.Event()
    callback_finished = threading.Event()
    finish_callback = threading.Event()
    snapshot_captured = threading.Event()
    finish_save = threading.Event()

    async def callback(_job):
        callback_started.set()
        await asyncio.to_thread(finish_callback.wait)
        callback_finished.set()

    live._on_scheduled = callback
    deserialize = live._job_from_dict
    calls = 0

    def pause_reconcile(value):
        nonlocal calls
        refreshed = deserialize(value)
        calls += 1
        if calls == 2:
            snapshot_captured.set()
            assert finish_save.wait(10)
        return refreshed

    with ThreadPoolExecutor(max_workers=2) as pool:
        run = pool.submit(asyncio.run, live._execute(job))
        save = None
        try:
            assert callback_started.wait(5)
            external.update_job(job.id, {"payload": {"message": "CLI edit"}})
            monkeypatch.setattr(live, "_job_from_dict", pause_reconcile)
            save = pool.submit(live._save_unlocked)
            assert snapshot_captured.wait(5)
            finish_callback.set()
            assert callback_finished.wait(5)
            with pytest.raises(TimeoutError):
                run.result(timeout=0.2)
        finally:
            finish_callback.set()
            finish_save.set()
        if save is not None:
            save.result(timeout=10)
        run.result(timeout=10)

    assert job.state.run_count == 1
    assert job.state.last_status == "ok"
    live._save_unlocked()
    persisted = service_at(tmp_path).get_job(job.id)
    assert persisted.payload.message == "CLI edit"
    assert persisted.state.run_count == 1
    assert persisted.state.last_status == "ok"


@pytest.mark.asyncio
async def test_manual_trigger_refreshes_external_disable_and_deletion(tmp_path):
    live = service_at(tmp_path)
    job = add_job(live)
    external = service_at(tmp_path)
    external.enable_job(job.id, False)

    assert await live.run_job(job.id) is False

    external.remove_job(job.id)
    assert await live.run_job(job.id, force=True) is False


def test_approval_uses_latest_external_operation(tmp_path):
    live = service_at(tmp_path)
    job = add_job(live, require_approval=True)
    external = service_at(tmp_path)
    external.update_job(job.id, {"payload": {"message": "current operation"}})

    approved = live.approve_job(job.id)

    assert approved.payload.message == "current operation"
    assert job_is_approved(approved)
    assert job_is_approved(service_at(tmp_path).get_job(job.id))


def test_reload_detects_store_replacement_with_equal_mtime(tmp_path):
    live = service_at(tmp_path)
    add_job(live)
    store = tmp_path / "automation.json"
    old_time = store.stat().st_mtime_ns
    external_job = add_job(service_at(tmp_path), "remote task")
    os.utime(store, ns=(old_time, old_time))

    assert live.sync_from_disk()
    assert live.get_job(external_job.id) is not None


def test_concurrent_processes_do_not_lose_new_jobs(tmp_path):
    store = tmp_path / "automation.json"
    add_job(service_at(tmp_path), "initial")
    worker_code = """
import sys, time
from pathlib import Path
from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationPayload, AutomationSchedule
root = Path(sys.argv[1])
worker = sys.argv[2]
service = AutomationService(root / 'automation.json', workspace=root)
(root / ('ready-' + worker)).touch()
deadline = time.monotonic() + 10
while not (root / 'start').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('worker barrier timed out')
    time.sleep(0.005)
for index in range(6):
    name = worker + '-' + str(index)
    service.add_job(name, AutomationSchedule(kind='every', every_ms=60000),
                    AutomationPayload(message=name))
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", worker_code, str(tmp_path), str(index)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(3)
    ]
    try:
        deadline = time.monotonic() + 15
        while not all((tmp_path / f"ready-{index}").exists() for index in range(3)):
            assert time.monotonic() < deadline, "process startup timed out"
            assert all(process.poll() is None for process in processes)
            time.sleep(0.01)
        (tmp_path / "start").touch()
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            assert process.returncode == 0, stdout + stderr
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    jobs = json.loads(store.read_text(encoding="utf-8"))["jobs"]
    assert len(jobs) == 19
    assert {job["name"] for job in jobs} == {"initial"} | {
        f"{worker}-{index}" for worker in range(3) for index in range(6)
    }
