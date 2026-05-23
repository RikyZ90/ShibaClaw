import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest

from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule
from shibaclaw.agent.tools.cron import CronTool


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

    jobs = service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == job.id

    fetched = service.get_job(job.id)
    assert fetched is not None
    assert fetched.id == job.id

    assert service.remove_job(job.id) is True
    assert service.get_job(job.id) is None
    assert len(service.list_jobs()) == 0


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
    tool = CronTool(cron_service=service)
    tool.set_context(channel="test_channel", chat_id="test_chat")

    result = await tool.execute(action="add", message="Test reminder", every_seconds=10)
    assert "Created job" in result

    jobs = service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0].payload.message == "Test reminder"
    assert jobs[0].payload.channel == "test_channel"
    assert jobs[0].payload.to == "test_chat"

    list_result = await tool.execute(action="list")
    assert "Test reminder" in list_result

    job_id = jobs[0].id
    remove_result = await tool.execute(action="remove", job_id=job_id)
    assert f"Removed job {job_id}" in remove_result
    assert len(service.list_jobs()) == 0


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
