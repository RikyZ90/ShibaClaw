import asyncio
import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from shibaclaw.config.schema import Config
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.oauth_github import start_codex_oauth, start_openrouter_oauth
from shibaclaw.webui.routers.oauth import api_oauth_login, api_oauth_openrouter_callback


def _json_request(payload: dict) -> Request:
    body = json.dumps(payload).encode("utf-8")

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/oauth/login",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )


def _get_request(path: str, query_string: str = "", path_params: dict | None = None) -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query_string.encode("utf-8"),
            "headers": [(b"host", b"127.0.0.1:3000")],
            "scheme": "http",
            "server": ("127.0.0.1", 3000),
            "path_params": path_params or {},
        },
        receive,
    )


class TestOAuthRouter:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("provider", "helper_name"),
        [
            ("openrouter", "start_openrouter_oauth"),
            ("github_copilot", "start_github_oauth"),
            ("openai_codex", "start_codex_oauth"),
        ],
    )
    async def test_api_oauth_login_dispatches_to_webui_helper(
        self, monkeypatch, provider, helper_name
    ):
        import shibaclaw.webui.oauth_github as oauth_helpers

        agent_manager.oauth_jobs.clear()

        async def fake_helper(*args):
            job_id = args[-2] if len(args) == 3 else args[0]
            jobs = args[-1]
            jobs[job_id]["status"] = "done"
            return SimpleNamespace(
                body=json.dumps({"provider": provider, "job_id": job_id}).encode("utf-8")
            )

        monkeypatch.setattr(oauth_helpers, helper_name, fake_helper)

        response = await api_oauth_login(_json_request({"provider": provider}))
        payload = json.loads(response.body)

        assert payload["provider"] == provider
        assert payload["job_id"] in agent_manager.oauth_jobs


class TestCodexOAuth:
    @pytest.mark.asyncio
    async def test_start_codex_oauth_exposes_auth_url_and_accepts_manual_code(
        self, monkeypatch, tmp_path
    ):
        import oauth_cli_kit.flow as flow
        import oauth_cli_kit.pkce as pkce
        import oauth_cli_kit.providers as providers
        import oauth_cli_kit.server as server
        import oauth_cli_kit.storage as storage

        import shibaclaw.webui.oauth_github as oauth_module

        saved_tokens = []
        observed = {}

        class FakeStorage:
            def __init__(self, token_filename):
                self.token_filename = token_filename

            def save(self, token):
                saved_tokens.append((self.token_filename, token))

        def fake_exchange(code, verifier, provider):
            observed["code"] = code
            observed["verifier"] = verifier
            observed["provider"] = provider

            async def _run():
                return SimpleNamespace(
                    access="access-token",
                    refresh="refresh-token",
                    expires=123456789,
                    account_id="acct-123",
                )

            return _run

        monkeypatch.setattr(flow, "_exchange_code_for_token_async", fake_exchange)
        monkeypatch.setattr(pkce, "_create_state", lambda: "state-123")
        monkeypatch.setattr(pkce, "_generate_pkce", lambda: ("verifier-123", "challenge-123"))
        monkeypatch.setattr(
            pkce, "_parse_authorization_input", lambda raw: ("auth-code-xyz", "state-123")
        )
        monkeypatch.setattr(
            providers,
            "OPENAI_CODEX_PROVIDER",
            SimpleNamespace(
                client_id="client-id",
                authorize_url="https://auth.openai.test/oauth/authorize",
                redirect_uri="http://localhost:1455/auth/callback",
                scope="openid profile",
                default_originator="nanobot",
                token_filename="codex.json",
            ),
        )
        monkeypatch.setattr(
            server, "_start_local_server", lambda state, on_code: (None, "disabled for test")
        )
        monkeypatch.setattr(storage, "FileTokenStorage", FakeStorage)
        monkeypatch.setattr(oauth_module.os.path, "expanduser", lambda _: str(tmp_path))

        jobs = {"job-1": {"provider": "openai_codex", "status": "running", "logs": []}}
        response = await start_codex_oauth("job-1", jobs)
        payload = json.loads(response.body)

        assert payload["provider"] == "openai_codex"
        assert payload["auth_url"].startswith("https://auth.openai.test/oauth/authorize?")
        assert jobs["job-1"]["auth_url"] == payload["auth_url"]

        jobs["job-1"]["_code_holder"]["value"] = (
            "http://localhost:1455/auth/callback?code=auth-code-xyz&state=state-123"
        )
        jobs["job-1"]["_code_event"].set()

        for _ in range(50):
            if jobs["job-1"]["status"] == "done":
                break
            await asyncio.sleep(0)

        assert jobs["job-1"]["status"] == "done"
        assert observed["code"] == "auth-code-xyz"
        assert observed["verifier"] == "verifier-123"
        assert observed["provider"].client_id == "client-id"
        assert saved_tokens and saved_tokens[0][0] == "codex.json"
        cred_path = tmp_path / ".config" / "shibaclaw" / "openai_codex" / "credentials.json"
        assert cred_path.exists()
        cred_data = json.loads(cred_path.read_text(encoding="utf-8"))
        assert cred_data["access"] == "access-token"
        assert cred_data["refresh"] == "refresh-token"
        assert cred_data["account_id"] == "acct-123"


class TestOpenRouterOAuth:
    @pytest.mark.asyncio
    async def test_start_openrouter_oauth_returns_auth_url_and_tracks_pkce_state(self):
        jobs = {"job-1": {"provider": "openrouter", "status": "running", "logs": []}}

        response = await start_openrouter_oauth(_get_request("/api/oauth/login"), "job-1", jobs)
        payload = json.loads(response.body)

        assert payload["provider"] == "openrouter"
        assert payload["status"] == "awaiting_redirect"
        assert payload["auth_url"].startswith("https://openrouter.ai/auth?")
        assert jobs["job-1"]["status"] == "awaiting_redirect"
        assert jobs["job-1"]["_openrouter_verifier"]
        assert jobs["job-1"]["_openrouter_flow"]
        assert jobs["job-1"]["callback_url"].startswith(
            "http://localhost:3000/api/oauth/openrouter/callback/job-1/"
        )
        assert jobs["job-1"]["_openrouter_timeout"] is not None

    @pytest.mark.asyncio
    async def test_start_openrouter_oauth_uses_explicit_callback_base_url_override(
        self, monkeypatch
    ):
        jobs = {"job-2": {"provider": "openrouter", "status": "running", "logs": []}}
        monkeypatch.setenv(
            "SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL", "https://chat.example.test:8443"
        )

        response = await start_openrouter_oauth(_get_request("/api/oauth/login"), "job-2", jobs)
        payload = json.loads(response.body)

        assert payload["callback_url"].startswith(
            "https://chat.example.test:8443/api/oauth/openrouter/callback/job-2/"
        )
        assert jobs["job-2"]["callback_url"] == payload["callback_url"]

    @pytest.mark.asyncio
    async def test_openrouter_callback_exchanges_code_and_persists_api_key(self, monkeypatch):
        import shibaclaw.webui.oauth_github as oauth_module

        original_config = agent_manager.config
        original_provider = agent_manager.provider
        persisted_keys = []

        async def fake_exchange(code, code_verifier):
            assert code == "oauth-code-123"
            assert code_verifier == "verifier-123"
            return "sk-or-authenticated"

        async def fake_persist(api_key):
            persisted_keys.append(api_key)

        monkeypatch.setattr(oauth_module, "_exchange_openrouter_code_for_key", fake_exchange)
        monkeypatch.setattr(oauth_module, "_persist_openrouter_api_key", fake_persist)
        monkeypatch.setattr(agent_manager, "config", Config.model_validate({"providers": {"openrouter": {}}}))
        monkeypatch.setattr(agent_manager, "provider", None)

        agent_manager.oauth_jobs.clear()
        agent_manager.oauth_jobs["job-1"] = {
            "provider": "openrouter",
            "status": "awaiting_redirect",
            "logs": [],
            "_openrouter_verifier": "verifier-123",
            "_openrouter_flow": "flow-xyz",
            "_openrouter_timeout": None,
        }

        try:
            response = await api_oauth_openrouter_callback(
                _get_request(
                    "/api/oauth/openrouter/callback/job-1/flow-xyz",
                    "code=oauth-code-123",
                    {"job_id": "job-1", "flow_token": "flow-xyz"},
                )
            )
            body = response.body.decode("utf-8")

            assert response.status_code == 200
            assert "Login Successful" in body
            assert persisted_keys == ["sk-or-authenticated"]
            assert agent_manager.oauth_jobs["job-1"]["status"] == "done"
        finally:
            agent_manager.config = original_config
            agent_manager.provider = original_provider

    @pytest.mark.asyncio
    async def test_openrouter_callback_still_accepts_legacy_query_state(self, monkeypatch):
        import shibaclaw.webui.oauth_github as oauth_module

        async def fake_exchange(code, code_verifier):
            assert code == "oauth-code-456"
            assert code_verifier == "verifier-456"
            return "sk-or-legacy"

        async def fake_persist(api_key):
            assert api_key == "sk-or-legacy"

        monkeypatch.setattr(oauth_module, "_exchange_openrouter_code_for_key", fake_exchange)
        monkeypatch.setattr(oauth_module, "_persist_openrouter_api_key", fake_persist)

        agent_manager.oauth_jobs.clear()
        agent_manager.oauth_jobs["job-legacy"] = {
            "provider": "openrouter",
            "status": "awaiting_redirect",
            "logs": [],
            "_openrouter_verifier": "verifier-456",
            "_openrouter_flow": "flow-legacy",
            "_openrouter_timeout": None,
        }

        response = await api_oauth_openrouter_callback(
            _get_request(
                "/api/oauth/openrouter/callback",
                "job_id=job-legacy&flow=flow-legacy&code=oauth-code-456",
            )
        )

        assert response.status_code == 200
        assert agent_manager.oauth_jobs["job-legacy"]["status"] == "done"
