import asyncio
import json
from types import SimpleNamespace

import httpx

from shibaclaw.agent.tools.web import WebSearchTool

UA = "youdotcom-integration/RikyZ90-ShibaClaw"
PAYLOAD = {
    "results": {
        "web": [
            {
                "url": "https://example.org/a",
                "title": "A",
                "description": "desc a",
                "snippets": ["one", "two", "three"],
            },
            {"url": "https://example.org/b", "title": "B", "description": "desc b"},
        ],
        "news": [{"url": "https://example.org/n", "title": "N", "description": "news"}],
    }
}


def _tool(handler, key="", provider="youcom"):
    cfg = SimpleNamespace(provider=provider, max_results=5, base_url="", resolve_api_key=lambda: key)
    tool = WebSearchTool(cfg)  # type: ignore[arg-type]
    tool._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return tool


def test_youcom_keyless(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")  # must never reach You.com
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    out = asyncio.run(_tool(handler).execute("shiba", count=3))
    req = seen[0]
    assert req.method == "GET"
    assert str(req.url).startswith("https://api.you.com/v1/agents/search")
    assert req.url.params["query"] == "shiba" and req.url.params["count"] == "3"
    assert req.headers["User-Agent"] == UA
    assert "X-API-Key" not in req.headers
    assert "1. A\n   https://example.org/a\n   one two" in out
    assert "2. B\n   https://example.org/b\n   desc b" in out
    assert "3. N" in out


def test_youcom_keyed_from_vault():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    asyncio.run(_tool(handler, key="vault-key").execute("q", count=2))
    req = seen[0]
    assert req.method == "POST" and str(req.url) == "https://ydc-index.io/v1/search"
    assert req.headers["X-API-Key"] == "vault-key" and req.headers["User-Agent"] == UA
    assert json.loads(req.content) == {"query": "q", "count": 2}


def test_youcom_keyed_from_env(monkeypatch):
    monkeypatch.setenv("YDC_API_KEY", "env-key")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    asyncio.run(_tool(handler, provider="you.com").execute("q"))
    assert seen[0].headers["X-API-Key"] == "env-key"


def test_youcom_errors(monkeypatch):
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    out = asyncio.run(_tool(lambda r: httpx.Response(429)).execute("q"))
    assert "keyless search limit" in out
    out = asyncio.run(_tool(lambda r: httpx.Response(401), key="bad").execute("q"))
    assert "rejected the search API key" in out
    out = asyncio.run(_tool(lambda r: httpx.Response(200, json={"results": {}})).execute("q"))
    assert out == "No results for: q"
