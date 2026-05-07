import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from starlette.requests import Request

from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.brain.manager import PackManager, Session
from shibaclaw.config.schema import Config
from shibaclaw.helpers.model_ids import canonicalize_model_id
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.sessions import api_sessions_get


def _session_request(session_id: str) -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/api/sessions/{session_id}",
            "path_params": {"session_id": session_id},
            "headers": [],
            "client": ("127.0.0.1", 12345),
        },
        receive,
    )


def test_canonicalize_model_id_matches_default_model_tail():
    cfg = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "github_copilot/gpt-4.1",
                }
            }
        }
    )

    assert canonicalize_model_id(cfg, "gpt-4.1") == "github_copilot/gpt-4.1"


def test_canonicalize_model_id_uses_single_configured_provider():
    cfg = Config.model_validate(
        {
            "agents": {"defaults": {"model": "custom/default"}},
            "providers": {"custom": {"apiBase": "http://localhost:1234/v1"}},
        }
    )

    assert (
        canonicalize_model_id(cfg, "qwen2.5-coder", configured_names=["custom"])
        == "custom/qwen2.5-coder"
    )


def test_api_sessions_get_normalizes_legacy_raw_model(tmp_path: Path):
    async def _run() -> None:
        original_config = agent_manager.config
        original_provider = agent_manager.provider

        cfg = Config.model_validate(
            {
                "agents": {
                    "defaults": {
                        "workspace": str(tmp_path),
                        "model": "github_copilot/gpt-4.1",
                    }
                }
            }
        )

        agent_manager.config = cfg
        agent_manager.provider = object()

        try:
            pm = PackManager(cfg.workspace_path)
            session = pm.get_or_create("webui:test")
            session.metadata["model"] = "gpt-4.1"
            pm.save(session)

            response = await api_sessions_get(_session_request("webui:test"))
            payload = json.loads(response.body)
            reloaded = pm.get_or_create("webui:test")

            assert response.status_code == 200
            assert payload["model"] == "github_copilot/gpt-4.1"
            assert reloaded.metadata["model"] == "github_copilot/gpt-4.1"
        finally:
            agent_manager.config = original_config
            agent_manager.provider = original_provider

    asyncio.run(_run())


def test_process_message_uses_canonicalized_session_model(tmp_path: Path):
    async def _run() -> None:
        cfg = Config.model_validate(
            {
                "agents": {
                    "defaults": {
                        "workspace": str(tmp_path),
                        "model": "github_copilot/gpt-4.1",
                    }
                }
            }
        )

        session = Session(key="webui:test", metadata={"model": "gpt-4.1"})
        captured: dict[str, str | None] = {}

        class FakeSessions:
            def get_or_create(self, key: str) -> Session:
                return session

            def save(self, current_session: Session) -> None:
                session.metadata.update(current_session.metadata)

            def invalidate(self, key: str) -> None:
                return None

        class FakeMemoryConsolidator:
            memory_max_prompt_tokens = 2000

            async def maybe_consolidate_by_tokens(self, current_session: Session) -> None:
                return None

            async def maybe_proactive_learn(self, current_session: Session) -> None:
                return None

        async def fake_run_agent_loop(*args, **kwargs):
            captured["model"] = kwargs.get("model")
            return "ok", None, [{"role": "assistant", "content": "ok"}]

        def discard_background(coro) -> None:
            coro.close()

        brain = object.__new__(ShibaBrain)
        brain.provider = object()
        brain.config = cfg
        brain.session_router = None
        brain.sessions = FakeSessions()
        brain.memory_consolidator = FakeMemoryConsolidator()
        brain._set_tool_context = lambda *args, **kwargs: None
        brain.tools = SimpleNamespace(get=lambda name: None)
        brain.context = SimpleNamespace(build_messages=lambda **kwargs: [])
        brain._available_channels = []
        brain.bus = SimpleNamespace()
        brain._run_agent_loop = fake_run_agent_loop
        brain._save_turn = lambda current_session, messages, skip: None
        brain._schedule_background = discard_background

        message = SimpleNamespace(
            channel="webui",
            sender_id="user",
            chat_id="test",
            content="hello",
            session_key="webui:test",
            metadata={},
            media=None,
        )

        response = await ShibaBrain._process_message(brain, message, session_key="webui:test")

        assert response is not None
        assert captured["model"] == "github_copilot/gpt-4.1"
        assert session.metadata["model"] == "github_copilot/gpt-4.1"

    asyncio.run(_run())
