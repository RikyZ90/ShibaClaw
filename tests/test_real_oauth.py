import asyncio
import json
from types import SimpleNamespace
import pytest
from starlette.requests import Request

from shibaclaw.config.schema import ProviderConfig
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.oauth_generic import start_generic_oauth
from shibaclaw.webui.routers.oauth import api_oauth_code


def _get_request(path: str, query_string: str = "", method: str = "GET") -> Request:
    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": query_string.encode("utf-8"),
            "headers": [(b"host", b"localhost:3000")],
            "scheme": "http",
            "server": ("127.0.0.1", 3000),
        },
        receive,
    )


class TestRealOAuthFlows:
    @pytest.mark.asyncio
    async def test_resolve_api_key_falls_back_to_oauth_tokens(self, tmp_path, monkeypatch):
        # Setup mock credential manager
        class FakeCredentialManager:
            def __init__(self):
                self.secrets = {
                    "providers": {},
                    "oauth_tokens": {
                        "anthropic": {"access_token": "oauth-claude-token-abc"}
                    }
                }
            def get_secret(self, ns, key):
                if ns == "providers":
                    return self.secrets["providers"].get(key)
                if ns == "oauth_tokens":
                    return self.secrets["oauth_tokens"].get(key)
                return None

        monkeypatch.setattr(
            "shibaclaw.security.credential_manager.get_credential_manager",
            lambda: FakeCredentialManager()
        )

        cfg = ProviderConfig()
        key = cfg.resolve_api_key("anthropic")
        assert key == "oauth-claude-token-abc"

    @pytest.mark.asyncio
    async def test_start_generic_oauth_device_flow_xai(self, monkeypatch):
        jobs = {"job-xai": {"provider": "xai", "status": "running", "logs": []}}
        
        # Mock xAI device code post response
        import httpx
        async def fake_post(*args, **kwargs):
            return SimpleNamespace(
                json=lambda: {
                    "device_code": "dev-code-123",
                    "user_code": "USER-456",
                    "verification_uri": "https://accounts.x.ai/oauth2/device",
                    "interval": 1,
                    "expires_in": 10
                }
            )
        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        request = _get_request("/api/oauth/login")
        response = await start_generic_oauth(request, "job-xai", jobs, "xai", "xAI / Grok")
        payload = json.loads(response.body)

        assert payload["user_code"] == "USER-456"
        assert payload["verification_uri"] == "https://accounts.x.ai/oauth2/device"
        assert jobs["job-xai"]["status"] == "awaiting_code"

    @pytest.mark.asyncio
    async def test_initiate_paste_flow_xai_fallback(self, monkeypatch):
        # Mock httpx to return an empty response so device_code is missing
        class FakeResponse:
            def json(self): return {}
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb): pass
            async def post(self, *args, **kwargs): return FakeResponse()

        monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FakeClient())

        jobs = {"job-xai-paste": {"provider": "xai", "status": "running", "logs": []}}
        request = _get_request("/api/oauth/login")
        
        response = await start_generic_oauth(request, "job-xai-paste", jobs, "xai", "xAI / Grok")
        payload = json.loads(response.body)

        assert payload["status"] == "awaiting_paste"
        assert "console.x.ai" in payload["console_url"]
        assert jobs["job-xai-paste"]["status"] == "awaiting_paste"
    @pytest.mark.asyncio
    async def test_submit_pasted_token_via_code_endpoint(self, monkeypatch):
        # Mock httpx to trigger fallback
        class FakeResponse:
            def json(self): return {}
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, exc_type, exc_val, exc_tb): pass
            async def post(self, *args, **kwargs): return FakeResponse()

        monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: FakeClient())

        jobs = {"job-paste": {"provider": "xai", "status": "running", "logs": []}}
        monkeypatch.setattr(agent_manager, "oauth_jobs", jobs)

        saved_tokens = []
        class FakeStore:
            def save_token(self, provider, token_data):
                saved_tokens.append((provider, token_data))

        monkeypatch.setattr("shibaclaw.security.oauth_store.OAuthTokenStore", FakeStore)

        # 1. Initialize the paste flow
        req_start = _get_request("/api/oauth/login")
        await start_generic_oauth(req_start, "job-paste", jobs, "xai", "xAI / Grok")

        # Mock the request payload
        async def mock_receive():
            return {
                "type": "http.request",
                "body": json.dumps({"job_id": "job-paste", "code": "xai-testkey"}).encode("utf-8"),
                "more_body": False
            }
        
        req = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/oauth/code",
                "headers": [(b"content-type", b"application/json")]
            },
            mock_receive
        )

        # Call code submit endpoint
        response = await api_oauth_code(req)
        assert response.status_code == 200

        # Wait a tick for background task to resolve
        await asyncio.sleep(0.05)

        assert jobs["job-paste"]["status"] == "done"
        assert saved_tokens[0][0] == "xai"
        assert saved_tokens[0][1]["access_token"] == "xai-testkey"
