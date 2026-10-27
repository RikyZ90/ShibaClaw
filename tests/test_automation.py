import asyncio
from unittest.mock import AsyncMock

import pytest

from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationPayload, AutomationSchedule
from shibaclaw.agent.tools.automation import AutomationTool


def test_automation_service_add_get_remove_job(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)

    schedule = AutomationSchedule(kind="every", every_ms=60000)
    payload = AutomationPayload(kind="scheduled", message="Test message")

    job = service.add_job(name="Test Job", schedule=schedule, payload=payload)
    assert job.id is not None
    assert job.name == "Test Job"
    assert job.schedule.kind == "every"
    assert job.payload.message == "Test message"

    reloaded = AutomationService(store_path=store_path, workspace=tmp_path)
    assert reloaded.list_jobs()[0].payload.message == "Test message"

    jobs = service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job.id

    fetched = service.get_job(job.id)
    assert fetched is not None
    assert fetched.id == job.id

    assert service.remove_job(job.id) is True
    assert service.get_job(job.id) is None
    assert len(service.list_jobs()) == 0


def test_job_model_survives_reload(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)
    service.add_job(
        name="Codex job",
        schedule=AutomationSchedule(kind="every", every_ms=60000),
        payload=AutomationPayload(
            kind="scheduled",
            message="x",
            model="openai-codex/gpt-6-sol",
        ),
    )
    reloaded = AutomationService(store_path=store_path, workspace=tmp_path)
    assert reloaded.list_jobs()[0].payload.model == "openai-codex/gpt-6-sol"


def test_automation_service_update_job(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)

    schedule = AutomationSchedule(kind="every", every_ms=60000)
    payload = AutomationPayload(kind="scheduled", message="Initial message")
    job = service.add_job(name="Initial Job", schedule=schedule, payload=payload)

    patch_data = {
        "name": "Updated Job",
        "enabled": False,
        "schedule": {"kind": "every", "everyMs": 120000},
        "payload": {"message": "Updated message"},
    }
    updated = service.update_job(job.id, patch_data)
    assert updated is not None
    assert updated.name == "Updated Job"
    assert updated.enabled is False
    assert updated.schedule.every_ms == 120000
    assert updated.payload.message == "Updated message"


def test_automation_service_enable_job(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)

    schedule = AutomationSchedule(kind="every", every_ms=60000)
    payload = AutomationPayload(kind="scheduled", message="Test")
    job = service.add_job(name="Test", schedule=schedule, payload=payload)

    assert job.enabled is True
    service.enable_job(job.id, False)
    assert job.enabled is False
    assert job.state.next_run_at_ms == 0

    service.enable_job(job.id, True)
    assert job.enabled is True
    assert job.state.next_run_at_ms > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("schedule", [
    AutomationSchedule(kind="every", every_ms=60000),
    AutomationSchedule(kind="at", at_ms=1),
])
async def test_new_disabled_job_stays_disabled_after_reload_and_start(tmp_path, schedule):
    executed = []

    async def on_scheduled(job):
        executed.append(job.id)

    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)
    job = service.add_job(
        name="Disabled job", schedule=schedule,
        payload=AutomationPayload(kind="scheduled", message="Do not run"),
        enabled=False,
    )
    assert job.enabled is False
    assert job.state.next_run_at_ms == 0

    reloaded = AutomationService(
        store_path=store_path, workspace=tmp_path, on_scheduled=on_scheduled,
    )
    try:
        await reloaded.start()
        persisted = reloaded.get_job(job.id)
        assert persisted.enabled is False
        assert persisted.state.next_run_at_ms == 0
        assert persisted.state.run_count == 0
        assert reloaded.status()["next_wake_at_ms"] is None
        assert executed == []
    finally:
        reloaded.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("session_key", [None, "webui:explicit"])
async def test_same_named_heartbeat_jobs_use_unique_sessions(tmp_path, monkeypatch, session_key):
    (tmp_path / "TASK.md").write_text(
        "## Active Tasks\n## Shared name\n- Inspect changes\n", encoding="utf-8",
    )
    on_heartbeat = AsyncMock(return_value="")
    service = AutomationService(
        store_path=tmp_path / "automation.json", workspace=tmp_path,
        on_heartbeat=on_heartbeat, provider=object(),
    )
    monkeypatch.setattr(service, "_heartbeat_decide", AsyncMock(return_value=("run", "Inspect changes")))
    jobs = [
        service.add_job(
            name="Shared name", schedule=AutomationSchedule(kind="every", every_ms=60000),
            payload=AutomationPayload(kind="heartbeat", session_key=session_key),
        )
        for _ in range(2)
    ]

    for job in jobs:
        await service._execute(job)

    assert jobs[0].id != jobs[1].id
    assert [call.kwargs["session_key"] for call in on_heartbeat.await_args_list] == [
        session_key or f"automation:{job.id}" for job in jobs
    ]


def test_automation_service_delete_after_run_recurring(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)

    schedule = AutomationSchedule(kind="every", every_ms=60000)
    payload = AutomationPayload(kind="scheduled", message="Delete Me")
    # Recurring job but marked for deletion after run
    job = service.add_job(name="RecurringDelete", schedule=schedule, payload=payload, delete_after_run=True)

    assert job.id in service._jobs
    
    # Manually trigger execution
    import asyncio
    asyncio.run(service._execute(job))
    
    # Should be removed from registry
    assert job.id not in service._jobs


@pytest.mark.asyncio
async def test_automation_service_run_job(tmp_path):
    store_path = tmp_path / "automation.json"
    on_scheduled_called = asyncio.Event()
    called_job = None

    async def on_scheduled(job):
        nonlocal called_job
        called_job = job
        on_scheduled_called.set()
        return "Done"

    service = AutomationService(
        store_path=store_path,
        workspace=tmp_path,
        on_scheduled=on_scheduled,
    )

    schedule = AutomationSchedule(kind="every", every_ms=60000)
    payload = AutomationPayload(kind="scheduled", message="Hello")
    job = service.add_job(name="RunTest", schedule=schedule, payload=payload)

    triggered = await service.run_job(job.id, force=True)
    assert triggered is True

    await asyncio.wait_for(on_scheduled_called.wait(), timeout=2.0)
    assert called_job is not None
    assert called_job.id == job.id


@pytest.mark.asyncio
async def test_cron_tool_integration(tmp_path):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)
    tool = AutomationTool(automation_service=service)
    tool.set_context(channel="test_channel", chat_id="test_chat")

    result = await tool.execute(action="add", message="Test reminder", every_seconds=10)
    assert "Created job" in result

    jobs = service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].payload.message == "Test reminder"
    # Now defaults to isolated background session
    assert jobs[0].payload.channel == "automation"
    assert jobs[0].payload.to == "background"

    list_result = await tool.execute(action="list")
    assert "Test reminder" in list_result

    job_id = jobs[0].id
    remove_result = await tool.execute(action="remove", job_id=job_id)
    assert f"Removed job {job_id}" in remove_result
    assert len(service.list_jobs()) == 0

    # Test explicit target channel
    await tool.execute(action="add", message="Delivery", every_seconds=10, target_channel="tg", target_chat_id="123")
    jobs = service.list_jobs()
    assert jobs[0].payload.channel == "tg"
    assert jobs[0].payload.to == "123"


def test_automation_service_legacy_migration(tmp_path):
    legacy_path = tmp_path / "jobs.json"
    import json
    legacy_data = {
        "jobs": [
            {
                "id": "migrated-1",
                "name": "Legacy Cron Job",
                "enabled": True,
                "deleteAfterRun": False,
                "createdAtMs": 1700000000000,
                "updatedAtMs": 1700000000000,
                "schedule": {"kind": "every", "everyMs": 60000},
                "payload": {"message": "Migrated message", "deliver": True, "channel": "tg", "to": "123"},
                "state": {"nextRunAtMs": 1700000060000},
            }
        ]
    }
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)

    jobs = service.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "migrated-1"
    assert job.name == "Legacy Cron Job"
    assert job.payload.message == "Migrated message"
    assert job.payload.deliver is True
    assert job.payload.channel == "tg"
    assert job.payload.to == "123"
    assert store_path.exists() is True
