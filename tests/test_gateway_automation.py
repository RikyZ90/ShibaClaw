"""Exercise gateway automation handlers without starting servers or an agent."""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from loguru import logger

from shibaclaw.automation.service import AutomationService
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule
from shibaclaw.cli.gateway_protocol import (
    http_json_response,
    serialize_automation_job,
    ws_err,
    ws_ok,
)
from shibaclaw.cli.gateway_utils import (
    deliver_scheduled_job_result,
    resolve_automation_target,
)


GATEWAY_PATH = Path(__file__).resolve().parents[1] / "shibaclaw" / "cli" / "gateway.py"


def gateway_handler(name, **bindings):
    tree = ast.parse(GATEWAY_PATH.read_text(encoding="utf-8"))
    handler = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )
    # Preserve nonlocal state in the real handlers without running gateway startup.
    wrapper = ast.parse(f"def bind():\n    _state = {{}}\n    return {name}\n")
    wrapper.body[0].body.insert(1, handler)
    namespace = {
        "asyncio": asyncio,
        "json": json,
        "logger": logger,
        "AutomationJob": AutomationJob,
        "http_json_response": http_json_response,
        "serialize_automation_job": serialize_automation_job,
        "ws_ok": ws_ok,
        "ws_err": ws_err,
        **bindings,
    }
    exec(compile(ast.fix_missing_locations(wrapper), str(GATEWAY_PATH), "exec"), namespace)
    return namespace["bind"]()


@pytest.mark.parametrize("transport", ["ws", "http"])
@pytest.mark.parametrize("enabled", [False, True, None])
async def test_create_preserves_initial_enabled_state(tmp_path, transport, enabled):
    service = AutomationService(tmp_path / "automation.json", tmp_path)
    body = {
        "name": "New task",
        "schedule": {"kind": "every", "everyMs": 60_000},
        "payload": {"message": "Run task", "profileId": "research"},
    }
    if enabled is not None:
        body["enabled"] = enabled

    if transport == "ws":
        handler = gateway_handler("_handle_ws_request", automation=service)
        socket = SimpleNamespace(send=AsyncMock())
        await handler(socket, "request-1", "automation.create", body)
        response = json.loads(socket.send.await_args.args[0])
        assert response["ok"] is True
        response_job = response["payload"]
    else:
        handler = gateway_handler(
            "_health_handler", automation=service, _current_auth_token=lambda: None,
        )
        reader = SimpleNamespace(read=AsyncMock(return_value=(
            b"POST /api/automation/jobs HTTP/1.1\r\n\r\n" + json.dumps(body).encode()
        )))
        writer = SimpleNamespace(write=Mock(), drain=AsyncMock(), close=Mock())
        await handler(reader, writer)
        raw = writer.write.call_args.args[0]
        assert raw.split(b"\r\n", 1)[0].split()[1] == b"201"
        response_job = json.loads(raw.split(b"\r\n\r\n", 1)[1])

    expected_enabled = enabled is not False
    assert response_job["enabled"] is expected_enabled
    assert response_job["payload"]["profileId"] == "research"
    reloaded = AutomationService(tmp_path / "automation.json", tmp_path)
    persisted = reloaded.get_job(response_job["id"])
    assert persisted.enabled is expected_enabled
    assert bool(persisted.state.next_run_at_ms) is expected_enabled


@pytest.mark.parametrize("session_key", [None, "webui:chosen"])
async def test_scheduled_execution_preserves_profile_and_isolates_duplicate_names(session_key):
    process = AsyncMock(return_value=SimpleNamespace(content="Done"))
    deliver = AsyncMock()
    handler = gateway_handler(
        "on_scheduled_job",
        agent=SimpleNamespace(process_direct=process),
        bus=SimpleNamespace(publish_outbound=AsyncMock()),
        notify_webui_session=AsyncMock(),
        _broadcast_ws_event=AsyncMock(),
        _ws_clients=set(),
        deliver_scheduled_job_result=deliver,
    )
    for job_id in ["job-1", "job-2"]:
        job = AutomationJob(
            id=job_id,
            name="Same title",
            schedule=AutomationSchedule(kind="every", every_ms=60_000),
            payload=AutomationPayload(
                message="Run task", profile_id="research", session_key=session_key,
                model="custom-model",
            ),
        )
        assert await handler(job) == "Done"

    assert [call.args[1] for call in process.await_args_list] == (
        [session_key, session_key] if session_key else ["automation:job-1", "automation:job-2"]
    )
    for call in process.await_args_list:
        assert call.kwargs["profile_id"] == "research"
        assert call.kwargs["model"] == "custom-model"
    assert deliver.await_count == 2


@pytest.mark.parametrize("explicit_to", [None, "explicit-chat"])
async def test_scheduled_delivery_supports_saved_target_map(explicit_to):
    job = AutomationJob(
        id="saved-job", name="Saved task",
        schedule=AutomationSchedule(kind="every", every_ms=60_000),
        payload=AutomationPayload(
            message="Run task", deliver=True, channel="telegram", to=explicit_to,
            targets={"telegram": "123456", "discord": "unrelated"},
        ),
    )
    bus_publish = AsyncMock()
    await deliver_scheduled_job_result(
        job, "Done", bus_publish=bus_publish, notify_webui=AsyncMock(),
        broadcast_ws_event=AsyncMock(), has_gateway_ws_clients=False, auth_token=None,
    )
    bus_publish.assert_awaited_once()
    outbound = bus_publish.await_args.args[0]
    assert outbound.channel == "telegram"
    assert outbound.chat_id == (explicit_to or "123456")


@pytest.mark.parametrize("session_key", [None, "webui:stable"])
def test_webui_target_map_keeps_session_resolution(session_key):
    job = AutomationJob(
        id="saved-webui-job", name="Saved task",
        schedule=AutomationSchedule(kind="every", every_ms=60_000),
        payload=AutomationPayload(
            channel="webui", targets={"webui": "abcdef1234567890"},
            session_key=session_key,
        ),
    )
    target = resolve_automation_target(job)
    assert target.session_key == (session_key or "webui:abcdef12")
    assert target.chat_id == ("stable" if session_key else "abcdef12")
