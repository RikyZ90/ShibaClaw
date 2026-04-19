import asyncio
import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.oauth_github import start_codex_oauth
from shibaclaw.webui.routers.oauth import api_oauth_login


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


class TestOAuthRouter:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("provider", "helper_name"),
        [
            ("github_copilot", "start_github_oauth"),
            ("openai_codex", "start_codex_oauth"),
        ],
    )
    async def test_api_oauth_login_dispatches_to_webui_helper(self, monkeypatch, provider, helper_name):
        import shibaclaw.webui.oauth_github as oauth_helpers

        agent_manager.oauth_jobs.clear()

        async def fake_helper(job_id, jobs):
            jobs[job_id]["status"] = "done"
            return SimpleNamespace(body=json.dumps({"provider": provider, "job_id": job_id}).encode("utf-8"))

        monkeypatch.setattr(oauth_helpers, helper_name, fake_helper)

        response = await api_oauth_login(_json_request({"provider": provider}))
        payload = json.loads(response.body)

        assert payload["provider"] == provider
        assert payload["job_id"] in agent_manager.oauth_jobs


class TestCodexOAuth:
    @pytest.mark.asyncio
    async def test_start_codex_oauth_exposes_auth_url_and_accepts_manual_code(self, monkeypatch, tmp_path):
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
        monkeypatch.setattr(pkce, "_parse_authorization_input", lambda raw: ("auth-code-xyz", "state-123"))
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
        monkeypatch.setattr(server, "_start_local_server", lambda state, on_code: (None, "disabled for test"))
        monkeypatch.setattr(storage, "FileTokenStorage", FakeStorage)
        monkeypatch.setattr(oauth_module.os.path, "expanduser", lambda _: str(tmp_path))

        jobs = {"job-1": {"provider": "openai_codex", "status": "running", "logs": []}}
        response = await start_codex_oauth("job-1", jobs)
        payload = json.loads(response.body)

        assert payload["provider"] == "openai_codex"
        assert payload["auth_url"].startswith("https://auth.openai.test/oauth/authorize?")
        assert jobs["job-1"]["auth_url"] == payload["auth_url"]

        jobs["job-1"]["_code_holder"]["value"] = "http://localhost:1455/auth/callback?code=auth-code-xyz&state=state-123"
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
