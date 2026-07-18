import pytest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from shibaclaw.thinkers.google_gemini_cli_provider import GoogleGeminiCLIThinker

class FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data

class FakeAsyncClient:
    def __init__(self, post_responses=None):
        self.post_responses = post_responses or []
        self.post_idx = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def post(self, url, **kwargs):
        if self.post_idx < len(self.post_responses):
            resp = self.post_responses[self.post_idx]
            self.post_idx += 1
            return resp
        return FakeResponse(200, {"access_token": "fake-access-token"})

@pytest.mark.asyncio
async def test_gemini_cli_thinker_refresh_success(monkeypatch):
    thinker = GoogleGeminiCLIThinker()

    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_ID", "fake_client_id")
    monkeypatch.setenv("SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET", "fake_client_secret")

    class FakeStore:
        def __init__(self):
            self.token_data = {"refresh_token": "old-refresh-token", "access_token": "expired-access-token"}
            self.saved = None
        def load_token(self, name):
            return self.token_data
        def is_expired(self, name, buffer_seconds=60):
            return True
        def save_token(self, name, data):
            self.saved = data

    fake_store = FakeStore()
    thinker._store = fake_store

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient([
        FakeResponse(200, {"access_token": "new-access-token"})
    ]))

    token = await thinker._get_session_token()
    assert token == "new-access-token"
    assert fake_store.saved is not None
    assert fake_store.saved["access_token"] == "new-access-token"
    assert fake_store.saved["refresh_token"] == "old-refresh-token"
