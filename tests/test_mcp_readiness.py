"""Readiness checks exercise MCP initialization and discovery without calling tools."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from starlette.requests import Request

from shibaclaw.agent.tools import mcp as agent_mcp
from shibaclaw.config.schema import Config, MCPServerConfig
from shibaclaw.webui.routers import mcp_manager


@pytest.fixture
def probe(monkeypatch):
    import mcp
    import mcp.client.sse
    import mcp.client.stdio
    import mcp.client.streamable_http

    session = AsyncMock()
    session.list_tools.return_value = SimpleNamespace(tools=[SimpleNamespace(name="example")])
    session.__aenter__.return_value = session
    opened = []
    closed = []

    @asynccontextmanager
    async def transport(kind, *args, **kwargs):
        opened.append((kind, args, kwargs))
        try:
            yield (object(), object(), None) if kind == "streamableHttp" else (object(), object())
        finally:
            closed.append(kind)

    monkeypatch.setattr(mcp, "ClientSession", lambda *args, **kwargs: session)
    monkeypatch.setattr(mcp.client.stdio, "stdio_client", lambda *a, **kw: transport("stdio", *a, **kw))
    monkeypatch.setattr(mcp.client.sse, "sse_client", lambda *a, **kw: transport("sse", *a, **kw))
    monkeypatch.setattr(mcp.client.streamable_http, "streamable_http_client", lambda *a, **kw: transport("streamableHttp", *a, **kw))
    # Keep the original GET/spawn probe offline too, to prove behavioural failures at the base.
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=httpx.Response(200)))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=SimpleNamespace(
        communicate=AsyncMock(return_value=(b"not MCP", b"")), returncode=0,
    )))

    async def run(kind="streamableHttp", **overrides):
        cfg = MCPServerConfig(**{
            "type": kind, "command": "example", "url": "https://example.test/mcp", **overrides,
        })
        monkeypatch.setattr(mcp_manager.agent_manager, "config", Config.model_validate({
            "tools": {"mcp_servers": {"example": cfg}},
        }))
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                           "path_params": {"name": "example"}})
        response = await mcp_manager.test_mcp_server(request)
        return json.loads(response.body)

    return SimpleNamespace(run=run, session=session, opened=opened, closed=closed)


@pytest.mark.parametrize("kind", ["stdio", "sse", "streamableHttp"])
async def test_ready_initializes_and_discovers_without_calling_tools(probe, kind):
    result = await probe.run(kind)
    assert result["ok"] is True
    assert result["transport"] == kind
    assert result["category"] == "ready"
    probe.session.initialize.assert_awaited_once()
    probe.session.list_tools.assert_awaited_once()
    probe.session.call_tool.assert_not_called()
    assert probe.closed == [kind]


async def test_empty_tool_list_is_ready(probe):
    probe.session.list_tools.return_value = SimpleNamespace(tools=[])
    result = await probe.run()
    assert result["category"] == "ready"
    assert result["ok"] is True
    probe.session.list_tools.assert_awaited_once()


@pytest.mark.parametrize("kind", ["stdio", "streamableHttp"])
async def test_non_mcp_peer_is_not_ready(probe, kind):
    probe.session.initialize.side_effect = ValueError("not a JSON-RPC response")
    result = await probe.run(kind)
    assert result["ok"] is False
    assert result["category"] == "MCP initialization failure"
    probe.session.list_tools.assert_not_called()
    assert probe.closed == [kind]


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failure(probe, status):
    request = httpx.Request("POST", "https://example.test/mcp")
    probe.session.initialize.side_effect = ExceptionGroup("transport", [httpx.HTTPStatusError(
        "denied", request=request, response=httpx.Response(status, request=request),
    )])
    result = await probe.run()
    assert result["ok"] is False
    assert result["category"] == "auth failure"


async def test_connection_refused(probe):
    probe.session.initialize.side_effect = ExceptionGroup("transport", [ConnectionRefusedError()])
    result = await probe.run()
    assert result["ok"] is False
    assert result["category"] == "connection refused"


@pytest.mark.parametrize("phase", ["auth", "initialize", "list_tools", "cleanup"])
async def test_timeout_is_bounded(probe, monkeypatch, phase):
    monkeypatch.setattr(mcp_manager, "_MCP_TEST_TIMEOUT", 0.01, raising=False)

    async def hang(*args, **kwargs):
        await asyncio.Event().wait()

    if phase == "auth":
        monkeypatch.setattr(agent_mcp, "_resolve_auth_headers", AsyncMock(side_effect=hang))
    elif phase == "cleanup":
        probe.session.__aexit__.side_effect = hang
    else:
        getattr(probe.session, phase).side_effect = hang
    result = await asyncio.wait_for(probe.run(), timeout=1)
    assert result["ok"] is False
    assert result["category"] == "timeout"
    assert probe.closed == ([] if phase == "auth" else ["streamableHttp"])


async def test_tool_discovery_failure(probe):
    probe.session.list_tools.side_effect = ValueError("invalid tool list")
    result = await probe.run()
    assert result["ok"] is False
    assert result["category"] == "tool discovery failure"
    probe.session.initialize.assert_awaited_once()
    probe.session.call_tool.assert_not_called()


async def test_oauth_login_stays_interactive_with_callback_time(probe, monkeypatch):
    monkeypatch.setattr(mcp_manager, "_MCP_TEST_TIMEOUT", 0.05, raising=False)
    calls = []

    async def login(name, cfg, **kwargs):
        calls.append(kwargs)
        await asyncio.sleep(0.1)  # longer than the MCP limit, shorter than the callback time
        return {}

    monkeypatch.setattr(agent_mcp, "_resolve_auth_headers", login)
    result = await probe.run(oauth={
        "auth_url": "https://example.test/auth", "token_url": "https://example.test/token",
        "client_id": "example", "callback_timeout": 1.0,
    })
    assert calls == [{}]
    assert result["category"] == "ready"


async def test_auth_resolution_failure_is_sanitized(probe, monkeypatch):
    secret = "header-secret env-secret https://user:password@example.test/mcp?token=query-secret"
    monkeypatch.setattr(agent_mcp, "_resolve_auth_headers", AsyncMock(side_effect=RuntimeError(secret)))
    result = await probe.run(headers={"Authorization": "header-secret"}, env={"TOKEN": "env-secret"})
    assert secret not in json.dumps(result)
    assert "secret" not in json.dumps(result)
    assert result["category"] == "auth failure"
    assert result["ok"] is False


async def test_peer_error_never_exposes_url_headers_or_env(probe, monkeypatch):
    url = "https://user:password@example.test/mcp?token=query-secret"
    config = MCPServerConfig(url=url, headers={"Authorization": "header-secret"}, env={"TOKEN": "env-secret"})
    monkeypatch.setattr(mcp_manager.agent_manager, "config", Config.model_validate({
        "tools": {"mcp_servers": {"example": config}},
    }))
    message = f"{url} header-secret env-secret\nTraceback: private details"
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(side_effect=ValueError(message)))
    probe.session.initialize.side_effect = ValueError(message)
    request = Request({"type": "http", "path_params": {"name": "example"}})
    response = await mcp_manager.test_mcp_server(request)
    body = response.body.decode()
    for private in ["user", "password", "query-secret", "header-secret", "env-secret", "Traceback"]:
        assert private not in body
    assert json.loads(body)["category"] == "MCP initialization failure"


@pytest.mark.parametrize("peer,category", [
    ("mcp", "ready"),
    ("html", "MCP initialization failure"),
    ("unauthorized", "auth failure"),
    ("refused", "connection refused"),
    ("hang", "timeout"),
    ("discovery", "tool discovery failure"),
])
async def test_real_sdk_with_mock_http_peer(monkeypatch, peer, category):
    """Use the real SDK protocol parser and transport with in-memory HTTP responses."""
    methods = []
    client_type = httpx.AsyncClient
    monkeypatch.setattr(mcp_manager, "_MCP_TEST_TIMEOUT", 0.05 if peer == "hang" else 1, raising=False)

    async def respond(request):
        assert request.headers["Authorization"] == "Bearer test-token"
        if peer == "hang":
            await asyncio.Event().wait()
        if peer == "refused":
            raise httpx.ConnectError("Connection refused", request=request)
        if peer == "unauthorized":
            return httpx.Response(401)
        if peer == "html":
            return httpx.Response(200, text="<html>Not MCP</html>")
        if request.method != "POST":
            return httpx.Response(405)
        message = json.loads(request.content)
        methods.append(message["method"])
        if "id" not in message:
            return httpx.Response(202)
        if message["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "test", "version": "1"}}
        elif peer == "discovery":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"],
                                           "error": {"code": -32601, "message": "unsupported"}})
        else:
            result = {"tools": []}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], "result": result})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client_type(
        **kw, transport=httpx.MockTransport(respond),
    ))
    monkeypatch.setattr(mcp_manager.agent_manager, "config", Config.model_validate({
        "tools": {"mcp_servers": {"example": {
            "url": "https://example.test/mcp", "headers": {"Authorization": "Bearer test-token"},
        }}},
    }))
    request = Request({"type": "http", "path_params": {"name": "example"}})
    response = await asyncio.wait_for(mcp_manager.test_mcp_server(request), timeout=2)
    result = json.loads(response.body)
    assert result["category"] == category
    assert result["ok"] is (category == "ready")
    assert "tools/call" not in methods
    if peer == "mcp":
        assert methods == ["initialize", "notifications/initialized", "tools/list"]


async def test_ready_response_does_not_expose_secrets(probe):
    result = await probe.run(
        url="https://user:password@example.test/mcp?token=query-secret",
        headers={"Authorization": "header-secret"}, env={"TOKEN": "env-secret"},
    )
    body = json.dumps(result)
    for private in ["user", "password", "query-secret", "header-secret", "env-secret"]:
        assert private not in body
    assert result["category"] == "ready"
