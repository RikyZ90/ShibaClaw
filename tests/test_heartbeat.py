import asyncio
from types import SimpleNamespace

import pytest

from shibaclaw.brain.manager import PackManager
from shibaclaw.cli.gateway import resolve_cron_target, resolve_webui_session_key, select_heartbeat_target
from shibaclaw.cron.service import CronService
from shibaclaw.cron.types import CronJob, CronJobState, CronPayload, CronSchedule
from shibaclaw.heartbeat.service import HeartbeatService
from shibaclaw.webui.agent_manager import AgentManager


class FakeSocketIO:
    def __init__(self):
        self.calls = []

    async def emit(self, event, payload, room=None):
        self.calls.append((event, payload, room))


class TestHeartbeatTargetSelection:
    def test_prefers_enabled_external_channel(self):
        sessions = [
            {"key": "webui:recent", "updated_at": "2026-04-05T12:00:00"},
            {"key": "telegram:12345", "updated_at": "2026-04-05T11:59:00"},
        ]

        target = select_heartbeat_target(sessions, {"telegram"})

        assert target.channel == "telegram"
        assert target.chat_id == "12345"
        assert target.session_key == "telegram:12345"

    def test_falls_back_to_webui_when_no_external_channel_is_available(self):
        sessions = [
            {"key": "webui:recent", "updated_at": "2026-04-05T12:00:00"},
            {"key": "cli:direct", "updated_at": "2026-04-05T11:59:00"},
        ]

        target = select_heartbeat_target(sessions, set())

        assert target.channel == "webui"
        assert target.chat_id == "recent"
        assert target.session_key == "webui:recent"


class TestCronTargetResolution:
    def test_uses_stable_webui_session_key_when_present(self):
        job = CronJob(
            id="cron-1",
            name="WebUI job",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            payload=CronPayload(
                message="Run task",
                deliver=True,
                channel="webui",
                to="sid-1234567890",
                session_key="webui:session-a",
            ),
            state=CronJobState(),
        )

        target = resolve_cron_target(job)

        assert target.channel == "webui"
        assert target.chat_id == "session-a"
        assert target.session_key == "webui:session-a"

    def test_falls_back_to_derived_webui_session_key_for_legacy_jobs(self):
        job = CronJob(
            id="cron-2",
            name="Legacy WebUI job",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            payload=CronPayload(
                message="Run task",
                deliver=True,
                channel="webui",
                to="abcdef1234567890",
            ),
            state=CronJobState(),
        )

        target = resolve_cron_target(job)

        assert target.channel == "webui"
        assert target.chat_id == "abcdef12"
        assert target.session_key == resolve_webui_session_key(None, "abcdef1234567890")


class TestWebuiHeartbeatDelivery:
    @pytest.mark.asyncio
    async def test_deliver_background_notification_persists_and_emits(self, tmp_path):
        manager = AgentManager()
        manager.config = SimpleNamespace(workspace_path=tmp_path)

        socket = FakeSocketIO()
        manager.set_socket_io(
            socket,
            {
                "sid-active": {"session_key": "webui:recent", "processing": False, "queue": []},
                "sid-other": {"session_key": "webui:other", "processing": False, "queue": []},
            },
        )

        result = await manager.deliver_background_notification(
            "webui:recent",
            "Heartbeat completed.",
            source="heartbeat",
        )

        assert result == {"delivered": True, "matched_sessions": 1}
        assert len(socket.calls) == 1
        event, payload, room = socket.calls[0]
        assert event == "agent_response"
        assert room == "sid-active"
        assert payload["content"] == "Heartbeat completed."

        session = PackManager(tmp_path).get_or_create("webui:recent")
        assert session.messages[-1]["role"] == "assistant"
        assert session.messages[-1]["content"] == "Heartbeat completed."
        assert session.messages[-1]["metadata"] == {
            "background": True,
            "source": "heartbeat",
        }

    @pytest.mark.asyncio
    async def test_deliver_background_notification_can_emit_without_persisting(self, tmp_path):
        manager = AgentManager()
        manager.config = SimpleNamespace(workspace_path=tmp_path)

        socket = FakeSocketIO()
        manager.set_socket_io(
            socket,
            {
                "sid-active": {"session_key": "webui:recent", "processing": False, "queue": []},
            },
        )

        result = await manager.deliver_background_notification(
            "webui:recent",
            "Cron completed.",
            source="cron",
            persist=False,
        )

        assert result == {"delivered": True, "matched_sessions": 1}
        assert len(socket.calls) == 1
        assert PackManager(tmp_path)._get_session_path("webui:recent").exists() is False


class TestCronOverdueJobFiring:
    @pytest.mark.asyncio
    async def test_overdue_at_job_fires_on_start(self, tmp_path):
        fired = []

        async def on_job(job):
            fired.append(job.id)
            return "done"

        svc = CronService(tmp_path / "jobs.json", on_job=on_job)
        import time
        past_ms = int(time.time() * 1000) - 60_000
        svc.add_job(
            name="overdue",
            schedule=CronSchedule(kind="at", at_ms=past_ms),
            message="hello",
            delete_after_run=True,
        )
        assert len(svc.list_jobs(include_disabled=True)) == 1
        await svc.start()
        svc.stop()
        assert len(fired) == 1
        assert svc.list_jobs(include_disabled=True) == []

    @pytest.mark.asyncio
    async def test_overdue_at_job_not_refired_if_already_run(self, tmp_path):
        fired = []

        async def on_job(job):
            fired.append(job.id)
            return "done"

        svc = CronService(tmp_path / "jobs.json", on_job=on_job)
        import time
        past_ms = int(time.time() * 1000) - 60_000
        job = svc.add_job(
            name="already-run",
            schedule=CronSchedule(kind="at", at_ms=past_ms),
            message="hello",
        )
        job.state.last_run_at_ms = past_ms + 1000
        svc._save_store()
        await svc.start()
        svc.stop()
        assert len(fired) == 0


class TestHeartbeatService:
    @pytest.mark.asyncio
    async def test_start_runs_first_tick_immediately(self, tmp_path):
        service = HeartbeatService(
            workspace=tmp_path,
            provider=object(),
            model="test-model",
            interval_s=3600,
        )
        tick_seen = asyncio.Event()

        async def fake_tick():
            tick_seen.set()
            service.stop()

        service._tick = fake_tick

        await service.start()
        await asyncio.wait_for(tick_seen.wait(), timeout=0.2)
        await asyncio.sleep(0)

    def test_status_returns_telemetry(self, tmp_path):
        service = HeartbeatService(
            workspace=tmp_path,
            provider=object(),
            model="test-model",
            interval_s=1800,
        )
        s = service.status()
        assert s["enabled"] is True
        assert s["interval_s"] == 1800
        assert s["heartbeat_file_exists"] is False
        assert s["last_check_ms"] is None

        (tmp_path / "HEARTBEAT.md").write_text("- [ ] test task")
        s = service.status()
        assert s["heartbeat_file_exists"] is True

    def test_status_reflects_telemetry_after_updates(self, tmp_path):
        service = HeartbeatService(
            workspace=tmp_path,
            provider=object(),
            model="test-model",
        )
        import time
        now_ms = int(time.time() * 1000)
        service._last_check_ms = now_ms
        service._last_action = "skip"
        service._last_run_ms = now_ms - 5000
        service._last_error = "boom"
        s = service.status()
        assert s["last_check_ms"] == now_ms
        assert s["last_action"] == "skip"
        assert s["last_run_ms"] == now_ms - 5000
        assert s["last_error"] == "boom"
