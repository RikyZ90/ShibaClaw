"""MCP loopback OAuth failures with no browser, sockets or provider requests."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

from shibaclaw.config.schema import MCPOAuthConfig
from shibaclaw.security import credential_manager, oauth_flow
from shibaclaw.security.oauth_store import OAuthTokenStore


class _Writer:
    def __init__(self):
        self.response = b""
        self.closed = False
        self.waited = False

    def write(self, data):
        self.response += data

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


class _Listener:
    def __init__(self, handler):
        self.callback = handler.__self__
        self.sockets = [SimpleNamespace(getsockname=lambda: ("127.0.0.1", 49152))]
        self.closed = False
        self.waited = False

    async def __aenter__(self):
        return self

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


@pytest.fixture
async def login(monkeypatch, tmp_path):
    # OAuthTokenStore ignores store_dir; replace the vault and keyring boundary.
    monkeypatch.setattr(credential_manager, "_FERNET_CACHE", {})
    monkeypatch.setattr(credential_manager, "_load_or_create_key", lambda _: Fernet.generate_key())
    manager = credential_manager.CredentialManager(store_dir=tmp_path)
    monkeypatch.setattr(credential_manager, "get_credential_manager", lambda: manager)
    store = OAuthTokenStore()
    cfg = MCPOAuthConfig(
        auth_url="https://provider.test/auth",
        token_url="https://provider.test/token",
        client_id="test-client",
    )
    listeners, urls, posts, tasks = [], [], [], []
    opened = asyncio.Event()
    response = httpx.Response(200, json={"access_token": "retry-token"})

    async def start_server(handler, *, host, port):
        assert (host, port) == ("127.0.0.1", 0)
        listener = _Listener(handler)
        listeners.append(listener)
        return listener

    def open_browser(url):
        urls.append(url)
        opened.set()
        return True

    async def post(client, url, data, **kwargs):
        assert url == cfg.token_url
        posts.append(data)
        if isinstance(login.response, Exception):
            raise login.response
        return login.response

    monkeypatch.setattr(oauth_flow.asyncio, "start_server", start_server)
    monkeypatch.setattr(oauth_flow.webbrowser, "open", open_browser)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    flow = oauth_flow.OAuthFlow(store=store)

    async def begin(timeout=10):
        opened.clear()
        task = asyncio.create_task(flow.authorize("mcp-test", cfg, callback_timeout=timeout))
        tasks.append(task)
        await asyncio.wait_for(opened.wait(), timeout=1)
        return task

    async def callback(params=None, listener=None, token=None):
        listener = listener or listeners[-1]
        query = parse_qs(urlparse(urls[-1]).query)
        if params is None:
            params = {"code": "retry-code", "state": query["state"][0]}
        reader = asyncio.StreamReader()
        path = f"/callback/{token or listener.callback.token}?{urlencode(params)}"
        reader.feed_data(f"GET {path} HTTP/1.1\r\n\r\n".encode())
        reader.feed_eof()
        writer = _Writer()
        await listener.callback._handle(reader, writer)
        assert writer.closed and writer.waited
        return writer.response

    def cleaned():
        assert listeners
        assert all(listener.closed and listener.waited for listener in listeners)
        assert all(listener.callback._future.done() for listener in listeners)
        assert all(task.done() for task in tasks)

    def empty():
        assert store.load_token("mcp-test") is None
        assert store.list_servers() == []
        assert not (tmp_path / "credentials.enc").exists()
        cleaned()

    async def retry():
        old_url = urls[-1]
        login.response = response
        task = await begin()
        assert urls[-1] != old_url
        assert listeners[-1].callback is not listeners[-2].callback
        assert (await callback()).startswith(b"HTTP/1.1 200")
        assert await asyncio.wait_for(task, timeout=1) == {"access_token": "retry-token"}
        # Read via a fresh manager, so an in-memory cache cannot fake persistence.
        fresh = credential_manager.CredentialManager(store_dir=tmp_path)
        assert fresh.get_secret("oauth_tokens", "mcp-test")["access_token"] == "retry-token"
        assert posts[-1]["code"] == "retry-code"
        assert posts[-1]["redirect_uri"] == parse_qs(urlparse(urls[-1]).query)["redirect_uri"][0]
        cleaned()

    login = SimpleNamespace(
        begin=begin, callback=callback, cleaned=cleaned, empty=empty, retry=retry, posts=posts,
        urls=urls, listeners=listeners, response=response,
    )
    yield login
    # Also release resources when an assertion or a deliberately broken guard fails.
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for listener in listeners:
        listener.close()
        await listener.wait_closed()
        listener.callback._future.cancel()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "error", "status"),
    [
        ({}, "no code", 200),
        ({"code": ""}, "no code", 200),
        ({"code": "bad-code", "state": None}, "state mismatch", 200),
        ({"code": "bad-code", "state": "wrong"}, "state mismatch", 200),
        ({"error": "access_denied"}, "OAuth error: access_denied", 400),
        ({"error": "server_error"}, "OAuth error: server_error", 400),
    ],
    ids=["missing-code", "empty-code", "missing-state", "wrong-state", "user-cancel", "provider-error"],
)
async def test_callback_failure_cleans_up_and_allows_retry(login, params, error, status):
    task = await login.begin()
    state = parse_qs(urlparse(login.urls[-1]).query)["state"][0]
    params = {"state": state, **params}
    if params["state"] is None:
        del params["state"]
    response = await login.callback(params)
    assert response.startswith(f"HTTP/1.1 {status}".encode())
    with pytest.raises(RuntimeError, match=error):
        await asyncio.wait_for(task, timeout=1)
    assert login.posts == []
    login.empty()
    await login.retry()


@pytest.mark.asyncio
async def test_wrong_callback_token_is_refused_and_login_continues(login):
    task = await login.begin()
    state = parse_qs(urlparse(login.urls[-1]).query)["state"][0]
    response = await login.callback({"code": "stray-code", "state": state}, token="wrong")
    assert response.startswith(b"HTTP/1.1 400")
    assert not login.listeners[0].callback._future.done()
    assert login.posts == []
    assert (await login.callback()).startswith(b"HTTP/1.1 200")
    assert await asyncio.wait_for(task, timeout=1) == {"access_token": "retry-token"}
    assert [post["code"] for post in login.posts] == ["retry-code"]
    login.cleaned()


@pytest.mark.asyncio
async def test_timeout_ignores_late_callback_and_allows_retry(login):
    task = await login.begin(timeout=0)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(task, timeout=1)
    assert login.listeners[0].callback._future.cancelled()
    login.empty()
    # A handler still running when the login ends must not change its outcome.
    await login.callback()
    assert login.listeners[0].callback._future.cancelled()
    assert login.posts == []
    login.empty()
    await login.retry()


@pytest.mark.asyncio
async def test_cancelled_authorize_cleans_up_and_allows_retry(login):
    task = await login.begin()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    assert login.listeners[0].callback._future.cancelled()
    assert login.posts == []
    login.empty()
    await login.retry()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "exception", "error"),
    [
        (httpx.Response(503, json={"error": "unavailable"}), RuntimeError, "returned 503"),
        (httpx.Response(200, json={"refresh_token": "incomplete"}), RuntimeError, "missing 'access_token'"),
        (httpx.ConnectError("offline"), httpx.ConnectError, "offline"),
    ],
    ids=["http-error", "missing-access-token", "transport-error"],
)
async def test_token_exchange_failure_cleans_up_and_allows_retry(login, response, exception, error):
    login.response = response
    task = await login.begin()
    await login.callback()
    with pytest.raises(exception, match=error):
        await asyncio.wait_for(task, timeout=1)
    assert len(login.posts) == 1
    login.empty()
    await login.retry()


@pytest.mark.asyncio
async def test_persistence_failure_cleans_up_and_allows_retry(login, monkeypatch, tmp_path):
    write_bytes = Path.write_bytes

    def fail_vault_write(path, data):
        if path == tmp_path / "credentials.enc":
            raise PermissionError("vault write denied")
        return write_bytes(path, data)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", fail_vault_write)
        task = await login.begin()
        await login.callback()
        with pytest.raises(PermissionError, match="vault write denied"):
            await asyncio.wait_for(task, timeout=1)
    assert len(login.posts) == 1
    login.empty()
    await login.retry()


@pytest.mark.asyncio
async def test_cancelling_one_login_leaves_concurrent_login_pending(login, tmp_path):
    first = await login.begin()
    first_listener = login.listeners[-1]
    second = await login.begin()
    second_listener = login.listeners[-1]
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert first_listener.closed and first_listener.waited
    assert first_listener.callback._future.cancelled()
    assert not second.done()
    assert not second_listener.closed
    assert not second_listener.callback._future.done()
    assert login.posts == []
    assert OAuthTokenStore().load_token("mcp-test") is None
    assert not (tmp_path / "credentials.enc").exists()
    # The cancelled flow's late callback cannot finish the other login.
    await login.callback(listener=first_listener)
    assert not second.done()
    await login.callback(listener=second_listener)
    assert await asyncio.wait_for(second, timeout=1) == {"access_token": "retry-token"}
    assert len(login.posts) == 1
    assert second_listener.closed and second_listener.waited
    assert OAuthTokenStore().load_token("mcp-test")["access_token"] == "retry-token"
