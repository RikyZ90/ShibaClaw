import pytest

from shibaclaw.automation.grants import job_is_approved, operation_fingerprint
from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule


# Produced by the pre-model fingerprint algorithm for this persisted one-shot.
LEGACY_FINGERPRINT = "0ce6f69fc2dd4adb"


def legacy_job():
    return AutomationJob(
        id="legacy-job",
        name="Legacy job",
        schedule=AutomationSchedule(kind="at", at_ms=2000000000000),
        payload=AutomationPayload(message="Legacy approval"),
        require_approval=True,
        approved_fingerprint=LEGACY_FINGERPRINT,
    )


@pytest.mark.parametrize("model", [None, ""])
def test_default_model_preserves_legacy_approval(model):
    job = legacy_job()
    job.payload.model = model
    assert operation_fingerprint(job.schedule, job.payload) == LEGACY_FINGERPRINT
    assert job_is_approved(job)


def test_changing_explicit_model_requires_new_approval():
    job = legacy_job()
    job.payload.model = "openai/gpt-4.1"
    assert not job_is_approved(job)
    job.approved_fingerprint = operation_fingerprint(job.schedule, job.payload)
    assert job_is_approved(job)
    job.payload.model = "openai/gpt-4.1-mini"
    assert not job_is_approved(job)
    job.payload.model = None
    assert not job_is_approved(job)


@pytest.mark.asyncio
async def test_persisted_legacy_one_shot_executes_with_existing_approval(tmp_path):
    executed = []

    async def on_scheduled(job):
        executed.append(job.id)

    service = AutomationService(
        store_path=tmp_path / "automation.json", workspace=tmp_path,
        on_scheduled=on_scheduled,
    )
    persisted = service._job_to_dict(legacy_job())
    persisted["payload"].pop("model")
    job = service._job_from_dict(persisted)
    await service._execute(job)
    assert executed == ["legacy-job"]
    assert job.state.last_status == "ok"
    assert job.state.last_error == ""


@pytest.mark.parametrize("kind", ["heartbeat", "scheduled"])
@pytest.mark.parametrize("name", ["Initial task", "Different task"])
def test_renaming_heartbeat_requires_new_approval(tmp_path, kind, name):
    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)
    job = service.add_job(
        name="Initial task",
        schedule=AutomationSchedule(kind="every", every_ms=60000),
        payload=AutomationPayload(kind=kind, message="Run task"),
        require_approval=True,
    )
    service.approve_job(job.id)
    fingerprint = job.approved_fingerprint

    updated = service.update_job(job.id, {"name": name})

    needs_approval = kind == "heartbeat" and name != "Initial task"
    assert job_is_approved(updated) is not needs_approval
    assert updated.approved_fingerprint == (None if needs_approval else fingerprint)
    reloaded = AutomationService(store_path=store_path, workspace=tmp_path)
    assert job_is_approved(reloaded.get_job(job.id)) is not needs_approval


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [False, True])
async def test_startup_overdue_job_respects_persisted_approval(tmp_path, approved):
    executed = []

    async def on_scheduled(job):
        executed.append(job.id)

    store_path = tmp_path / "automation.json"
    service = AutomationService(store_path=store_path, workspace=tmp_path)
    job = service.add_job(
        name="Overdue task",
        schedule=AutomationSchedule(kind="at", at_ms=1),
        payload=AutomationPayload(message="Approval required"),
        require_approval=True,
    )
    if approved:
        service.approve_job(job.id)
    reloaded = AutomationService(
        store_path=store_path, workspace=tmp_path, on_scheduled=on_scheduled,
    )
    try:
        await reloaded.start()
        if reloaded._save_task:
            await reloaded._save_task
        persisted = reloaded.get_job(job.id)
        assert executed == ([job.id] if approved else [])
        assert persisted.state.last_status == ("ok" if approved else "skipped")
        assert persisted.state.last_error == ("" if approved else "approval_required")
        assert persisted.state.run_count == 1
        assert persisted.enabled is False
        assert persisted.state.next_run_at_ms == 0
    finally:
        reloaded.stop()
