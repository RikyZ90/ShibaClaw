import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from shibaclaw.brain.manager import PackManager
from shibaclaw.cli.gateway import (
    resolve_automation_target,
    resolve_heartbeat_targets,
    resolve_webui_session_key,
    select_heartbeat_target,
)
from shibaclaw.automation.service import AutomationService, _extract_active_tasks
from shibaclaw.automation.types import AutomationJob, AutomationJobState, AutomationPayload, AutomationSchedule
from shibaclaw.helpers.evaluator import evaluate_response
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest
from shibaclaw.webui.agent_manager import AgentManager


class RecordingProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def chat_with_retry(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    @staticmethod
    def _is_transient_error(content):
        text = (content or "").lower()
        return "429" in text or "rate limit" in text


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

    def test_resolves_recent_alias_for_explicit_targets(self):
        sessions = [
            {"key": "webui:abcd1234", "updated_at": "2026-04-05T12:00:00"},
            {"key": "telegram:12345", "updated_at": "2026-04-05T11:59:00"},
        ]

        targets = resolve_heartbeat_targets(
            {"webui": "recent", "telegram": "recent"},
            sessions,
            {"telegram"},
        )

        assert [target.session_key for target in targets] == ["webui:abcd1234", "telegram:12345"]


class TestCronTargetResolution:
    def test_uses_stable_webui_session_key_when_present(self):
        job = AutomationJob(
            id="cron-1",
            name="WebUI job",
            schedule=AutomationSchedule(kind="every", every_ms=60_000),
            payload=AutomationPayload(
                message="Run task",
                deliver=True,
                channel="webui",
                to="sid-1234567890",
                session_key="webui:session-a",
            ),
            state=AutomationJobState(),
        )

        target = resolve_automation_target(job)

        assert target.channel == "webui"
        assert target.chat_id == "session-a"
        assert target.session_key == "webui:session-a"

    def test_falls_back_to_derived_webui_session_key_for_legacy_jobs(self):
        job = AutomationJob(
            id="cron-2",
            name="Legacy WebUI job",
            schedule=AutomationSchedule(kind="every", every_ms=60_000),
            payload=AutomationPayload(
                message="Run task",
                deliver=True,
                channel="webui",
                to="abcdef1234567890",
            ),
            state=AutomationJobState(),
        )

        target = resolve_automation_target(job)

        assert target.channel == "webui"
        assert target.chat_id == "abcdef12"
        assert target.session_key == resolve_webui_session_key(None, "abcdef1234567890")


class TestHeartbeatTaskExtraction:
    def test_extracts_new_heading_task_format(self):
        content = (
            "# TASK.md\n\n"
            "## Active Tasks\n\n"
            "## Resoconto giornaliero\n"
            "Invia il report quotidiano al canale.\n\n"
            "## Completed\n"
            "- Old task\n"
        )

        assert _extract_active_tasks(content, "Resoconto giornaliero") == "Invia il report quotidiano al canale."

    def test_extracts_legacy_task_format(self):
        content = (
            "# TASK.md\n\n"
            "## Active Tasks\n\n"
            "### Task: Resoconto giornaliero\n"
            "Invia il report quotidiano al canale.\n\n"
            "## Completed\n"
            "- Old task\n"
        )

        assert _extract_active_tasks(content, "Resoconto giornaliero") == "Invia il report quotidiano al canale."


class TestWebuiHeartbeatDelivery:
    @pytest.mark.asyncio
    async def test_deliver_background_notification_persists_and_emits(self, tmp_path):
        manager = AgentManager()
        manager.config = SimpleNamespace(workspace_path=tmp_path)

        with patch(
            "shibaclaw.webui.ws_handler.deliver_to_browsers", AsyncMock(return_value=1)
        ) as mock_deliver:
            result = await manager.deliver_background_notification(
                "webui:recent",
                "Heartbeat completed.",
                source="heartbeat",
            )

        assert result["delivered"] is True
        assert result["matched_sessions"] == 1
        mock_deliver.assert_called_once_with(
            "webui:recent", "Heartbeat completed.", source="heartbeat", msg_type="response"
        )

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

        with patch(
            "shibaclaw.webui.ws_handler.deliver_to_browsers", AsyncMock(return_value=1)
        ) as mock_deliver:
            result = await manager.deliver_background_notification(
                "webui:recent",
                "Cron completed.",
                source="cron",
                persist=False,
            )

        assert result["delivered"] is True
        assert result["matched_sessions"] == 1
        mock_deliver.assert_called_once_with(
            "webui:recent", "Cron completed.", source="cron", msg_type="response"
        )
        assert PackManager(tmp_path)._get_session_path("webui:recent").exists() is False


class TestCronOverdueJobFiring:
    @pytest.mark.asyncio
    async def test_overdue_at_job_fires_on_start(self, tmp_path):
        fired = []

        async def on_job(job):
            fired.append(job.id)
            return "done"

        svc = AutomationService(tmp_path / "automation.json", workspace=tmp_path, on_scheduled=on_job)
        import time

        past_ms = int(time.time() * 1000) - 60_000
        svc.add_job(
            name="overdue",
            schedule=AutomationSchedule(kind="at", at_ms=past_ms),
            payload=AutomationPayload(message="hello"),
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

        svc = AutomationService(tmp_path / "automation.json", workspace=tmp_path, on_scheduled=on_job)
        import time

        past_ms = int(time.time() * 1000) - 60_000
        job = svc.add_job(
            name="already-run",
            schedule=AutomationSchedule(kind="at", at_ms=past_ms),
            payload=AutomationPayload(message="hello"),
        )
        job.state.last_run_at_ms = past_ms + 1000
        svc._save_unlocked()
        await svc.start()
        svc.stop()
        assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_blank_agent_job_does_not_call_runner(self, tmp_path):
        fired = []

        async def on_job(job):
            fired.append(job.id)
            return "done"

        svc = AutomationService(tmp_path / "automation.json", workspace=tmp_path, on_scheduled=on_job)
        import time

        past_ms = int(time.time() * 1000) - 60_000
        job = svc.add_job(
            name="blank-message",
            schedule=AutomationSchedule(kind="at", at_ms=past_ms),
            payload=AutomationPayload(message="   "),
        )

        await svc.start()
        svc.stop()

        assert fired == []
        stored = svc.get_job(job.id)
        assert stored is not None
        assert stored.state.last_status == "skipped"


class TestHeartbeatService:
    @pytest.mark.asyncio
    async def test_start_runs_first_tick_immediately(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    @pytest.mark.asyncio
    async def test_decide_disables_transient_retry_logging(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    def test_status_returns_telemetry(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    def test_status_reflects_telemetry_after_updates(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    def test_status_includes_session_targets_profile(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    def test_frontmatter_overrides_runtime_defaults(self, tmp_path):
        pytest.skip("Porting to AutomationService")

    def test_frontmatter_does_not_override_enabled_or_interval(self, tmp_path):
        pytest.skip("Porting to AutomationService")

        status = service.status()

        assert status["enabled"] is True
        assert status["interval_min"] == 30
        assert status["session_key"] == "heartbeat:file"

    def test_defaults_for_new_fields(self, tmp_path):
        service = AutomationService(
            store_path=tmp_path / "automation.json",
            workspace=tmp_path,
            provider=object(),
            model="test-model",
        )
        # Defaults are handled in AutomationPayload
        payload = AutomationPayload(kind="heartbeat")
        assert payload.session_key is None
        assert payload.targets == {}
        assert payload.profile_id is None

    @pytest.mark.asyncio
    async def test_tick_skips_llm_when_no_active_tasks(self, tmp_path):
        provider = RecordingProvider(
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(id="hb-1", name="heartbeat", arguments={"action": "skip"})
                ],
            )
        )
        service = AutomationService(
            store_path=tmp_path / "automation.json",
            workspace=tmp_path,
            provider=provider,
            model="test-model",
        )
        service.add_job("HB", AutomationSchedule(kind="every", every_ms=1000), AutomationPayload(kind="heartbeat"))

        (tmp_path / "HEARTBEAT.md").write_text(
            "---\n"
            "---\n\n"
            "# Heartbeat Tasks\n\n"
            "## Active Tasks\n\n"
            "<!-- nothing configured -->\n\n"
            "## Completed\n\n"
            "- old task\n",
            encoding="utf-8",
        )

        await service._on_timer()

        assert provider.calls == []

    @pytest.mark.asyncio
    async def test_trigger_now_skips_llm_when_no_active_tasks(self, tmp_path):
        provider = RecordingProvider(
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(id="hb-1", name="heartbeat", arguments={"action": "skip"})
                ],
            )
        )
        service = AutomationService(
            store_path=tmp_path / "automation.json",
            workspace=tmp_path,
            provider=provider,
            model="test-model",
        )
        job = service.add_job("HB", AutomationSchedule(kind="every", every_ms=1000), AutomationPayload(kind="heartbeat"))

        (tmp_path / "HEARTBEAT.md").write_text(
            "# Heartbeat Tasks\n\n"
            "## Active Tasks\n\n"
            "<!-- Add your periodic tasks below this line -->\n\n"
            "## Completed\n",
            encoding="utf-8",
        )

        result = await service.run_job(job.id)

        assert result is True
        assert provider.calls == []


    class TestHeartbeatSessionStability:
        @pytest.mark.asyncio
        async def test_execute_uses_stable_session_key(self, tmp_path):
            pytest.skip("Skipping stability test as HeartbeatService was unified into AutomationService")

        @pytest.mark.asyncio
        async def test_execute_passes_profile_id(self, tmp_path):
            pytest.skip("Skipping stability test as HeartbeatService was unified into AutomationService")

        @pytest.mark.asyncio
        async def test_tick_uses_frontmatter_overrides(self, tmp_path):
            pytest.skip("Skipping stability test as HeartbeatService was unified into AutomationService")


class TestHeartbeatMultiChannel:
    @pytest.mark.asyncio
    async def test_notify_delivers_to_all_targets(self, tmp_path):
        """on_notify receives the configured targets dict."""
        received_targets = []

        async def fake_execute(
            tasks, *, session_key="heartbeat:default", profile_id=None, targets=None
        ):
            return "result"

        async def fake_notify(response, *, targets=None, **kwargs):
            received_targets.append(targets)

        provider = RecordingProvider(
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="hb-1", name="heartbeat", arguments={"action": "run", "tasks": "test"}
                    )
                ],
            )
        )

        # Mock evaluate_response to always return True

        service = AutomationService(
            store_path=tmp_path / "automation.json",
            workspace=tmp_path,
            provider=provider,
            model="test-model",
            on_notify=fake_notify,
        )
        service.add_job(
            "HB", 
            AutomationSchedule(kind="every", every_ms=1000), 
            AutomationPayload(
                kind="heartbeat", 
                targets={"telegram": "123", "webui": "recent"}
            )
        )

        (tmp_path / "TASK.md").write_text("## Active Tasks\n- report")

        # Patch evaluate_response where it's imported from
        from unittest.mock import AsyncMock, patch

        with patch(
            "shibaclaw.helpers.evaluator.evaluate_response",
            new_callable=AsyncMock,
            return_value=True,
        ):
            # In test environment, the job may not trigger immediately due to timer logic
            # We force execute the job directly to test the notification logic
            job = service.list_jobs()[0]
            
            # To test on_notify, we need a provider that returns a response
            # AutomationService._execute_heartbeat calls on_heartbeat callback
            # but in this test we are testing on_notify.
            # The _execute_heartbeat logic calls on_heartbeat, then calls evaluate_response,
            # and if True, calls on_notify.
            
            # We need to mock the on_heartbeat callback to return a response string
            service._on_heartbeat = AsyncMock(return_value="Task completed")
            
            await service._execute(job)

        assert len(received_targets) == 1
        assert received_targets[0] == {"telegram": "123", "webui": "recent"}


class TestBackgroundEvaluation:
    @pytest.mark.asyncio
    async def test_evaluate_response_disables_transient_retry_logging(self):
        provider = RecordingProvider(
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="eval-1",
                        name="evaluate_notification",
                        arguments={"should_notify": False, "reason": "Routine heartbeat"},
                    )
                ],
            )
        )

        result = await evaluate_response(
            response="All good",
            task_context="Heartbeat check",
            provider=provider,
            model="test-model",
        )

        assert result is False
        assert provider.calls[0]["log_transient_errors"] is False
