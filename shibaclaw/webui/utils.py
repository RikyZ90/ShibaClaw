"""Shared utilities and helpers for the WebUI API routes."""

from __future__ import annotations

import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Set, Optional

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.auth import get_auth_token

_LOCAL_HOSTS = frozenset(("0.0.0.0", "::", "", "127.0.0.1", "localhost"))


def _unique_hosts(*candidates: str) -> list[str]:
    hosts: list[str] = []
    for host in candidates:
        if host and host not in hosts:
            hosts.append(host)
    return hosts

def _resolve_gateway_hosts() -> tuple[list[str], int]:
    """Return (hosts, port) for reaching the gateway health server.

    Covers bare-metal (127.0.0.1) and Docker (container hostname) transparently.
    Custom hosts set explicitly are always tried first.
    """
    if not agent_manager.config:
        return [], 0
    gw = agent_manager.config.gateway
    port = gw.port
    env_host = os.environ.get("SHIBACLAW_GATEWAY_HOST", "").strip()
    docker_host = "shibaclaw-gateway"

    if env_host:
        if env_host in _LOCAL_HOSTS:
            return _unique_hosts("127.0.0.1", gw.host, docker_host), port
        return _unique_hosts(env_host, gw.host), port

    if gw.host in _LOCAL_HOSTS:
        hosts = _unique_hosts("127.0.0.1", docker_host)
    else:
        hosts = [gw.host]
    return hosts, port



def _deep_merge(base: dict, patch: dict):
    """Deep merge a dictionary patch onto base."""
    for k, v in patch.items():
        if v is None:
            base[k] = None
        elif isinstance(v, dict):
            if isinstance(base.get(k), dict):
                _deep_merge(base[k], v)
            elif not v:
                base[k] = None
            else:
                base[k] = v
        elif isinstance(v, str) and isinstance(base.get(k), str):
            if v == _redact_one(base.get(k)):
                continue
            base[k] = v
        else:
            base[k] = v


def _redact_secrets(obj: Any, keys_to_redact: Optional[Set[str]] = None) -> Any:
    """Recursively redact sensitive fields in a config-like dict."""
    _keys = keys_to_redact or {
        "api_key", "apiKey", "access_token", "accessToken",
        "token", "secret", "password", "key", "auth_token"
    }
    if isinstance(obj, dict):
        return {
            k: (_redact_one(v) if k.lower() in _keys else _redact_secrets(v, _keys))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_secrets(item, _keys) for item in obj]
    return obj


def _redact_one(val: Any) -> Any:
    """Redact a single string value, keeping only the last 4 characters."""
    if not isinstance(val, str) or not val:
        return val
    if len(val) <= 4:
        return "****"
    return "*" * (len(val) - 4) + val[-4:]


def _resolve_workspace_path(path_str: str | None) -> Path | None:
    if not agent_manager.config:
        return None
    workspace = agent_manager.config.workspace_path.resolve()
    if not path_str:
        return workspace
    raw = Path(path_str)
    resolved = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not resolved.is_relative_to(workspace):
        return None
    return resolved


# Global caches for context
_workspace_context_cache = {
    "file_state": {},  # filename -> mtime
    "file_tokens": 0,
    "sections": [],
}
_session_context_cache: Dict[str, Dict[str, Any]] = {}
_system_prompt_cache: Dict[str, Any] = {
    "prompt": "",
    "tokens": 0,
    "file_state": {},
    "settings": {},
}


def _build_real_system_prompt(wp: Path, defaults, profile_id: str | None = None) -> tuple[str, int]:
    """Build the real system prompt via ScentBuilder and return (prompt, tokens).

    Uses a mtime-based cache to avoid re-reading disk on every poll.
    """
    from shibaclaw.agent.context import ScentBuilder
    from shibaclaw.helpers.helpers import estimate_prompt_tokens

    # Check mtime of all files that feed into the system prompt
    builder = ScentBuilder(wp)
    check_files = [wp / f for f in ScentBuilder.BOOTSTRAP_FILES] + [
        wp / "memory" / "MEMORY.md",
    ]
    # Include the profile-specific SOUL.md in the mtime check
    if profile_id and profile_id != "default":
        check_files.append(wp / "profiles" / profile_id / "SOUL.md")

    current_state = {}
    for p in check_files:
        if p.exists():
            current_state[str(p)] = p.stat().st_mtime

    current_settings = {
        "memory_max_prompt_tokens": defaults.memory_max_prompt_tokens,
        "profile_id": profile_id or "default",
    }

    if (
        current_state == _system_prompt_cache["file_state"]
        and current_settings == _system_prompt_cache["settings"]
        and _system_prompt_cache["prompt"]
    ):
        return _system_prompt_cache["prompt"], _system_prompt_cache["tokens"]

    prompt = builder.build_system_prompt(
        memory_max_prompt_tokens=defaults.memory_max_prompt_tokens,
        profile_id=profile_id,
    )
    tokens = estimate_prompt_tokens([{"role": "system", "content": prompt}])

    _system_prompt_cache["prompt"] = prompt
    _system_prompt_cache["tokens"] = tokens
    _system_prompt_cache["file_state"] = current_state
    _system_prompt_cache["settings"] = current_settings

    return prompt, tokens


def _compute_session_tokens(session_id: str, wp: Path, pm, estimate_message_tokens):
    """Compute and cache message tokens for a session."""
    cache = _session_context_cache.get(session_id, {})
    session = pm.get_or_create(session_id)
    msgs = session.messages
    msg_count = len(msgs)

    if cache.get("msg_count") == msg_count and cache.get("workspace_path") == str(wp):
        return cache["msg_tokens"], cache["msg_lines"]

    msg_tokens = 0
    msg_lines = []

    for m in msgs:
        msg_tokens += estimate_message_tokens(m)
        role = m.get("role", "?").upper()
        ts = (m.get("timestamp") or "")[:16]
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        preview = (content or "")[:200]
        if len(content or "") > 200:
            preview += "…"
        tools = ""
        if m.get("tools_used"):
            tools = f" `[{', '.join(m['tools_used'])}]`"
        msg_lines.append(f"- **{role}** {ts}{tools}: {preview}")

    _session_context_cache[session_id] = {
        "msg_count": msg_count,
        "msg_tokens": msg_tokens,
        "msg_lines": msg_lines,
        "workspace_path": str(wp),
    }
    return msg_tokens, msg_lines


async def _gateway_request(method: str, path: str) -> dict | None:
    """Send a request to the gateway, preferring WebSocket when available."""
    from .gateway_client import gateway_client

    # Map well-known HTTP paths to WS actions
    _path_to_action = {
        "/": "status",
        "/api/cron/list": "cron.list",
        "/heartbeat/status": "heartbeat.status",
    }

    action = _path_to_action.get(path)
    if action and gateway_client.connected:
        return await gateway_client.request(action)

    # Fallback: raw HTTP
    hosts, port = _resolve_gateway_hosts()
    if not hosts:
        return None

    auth_token = get_auth_token()
    auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5.0,
            )
            try:
                writer.write(f"{method} {path} HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(8192), timeout=10.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    return json.loads(data[body_start + 4:])
        except Exception:
            continue
    return None


async def _gateway_post(path: str, body: dict) -> dict | None:
    """Send a POST to the gateway, preferring WebSocket when available."""
    from .gateway_client import gateway_client

    _path_to_action = {
        "/restart": "restart",
        "/heartbeat/trigger": "heartbeat.trigger",
        "/api/archive": "archive",
    }

    action = _path_to_action.get(path)
    if action and gateway_client.connected:
        return await gateway_client.request(action, body)

    # Handle cron trigger: /api/cron/trigger/{job_id}
    if path.startswith("/api/cron/trigger/") and gateway_client.connected:
        job_id = path.split("/")[-1]
        return await gateway_client.request("cron.trigger", {"job_id": job_id})

    # Fallback: raw HTTP
    hosts, port = _resolve_gateway_hosts()
    if not hosts:
        return None

    auth_token = get_auth_token()
    payload = json.dumps(body, ensure_ascii=False).encode()
    auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5.0,
            )
            try:
                writer.write(
                    (
                        f"POST {path} HTTP/1.0\r\n"
                        f"Host: gw\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(payload)}\r\n"
                        f"{auth_hdr}"
                        f"\r\n"
                    ).encode() + payload
                )
                await writer.drain()
                data = await asyncio.wait_for(reader.read(65536), timeout=30.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    return json.loads(data[body_start + 4:])
        except Exception:
            continue
    return None


async def _gateway_chat_stream(payload: dict):
    """Stream chat response from the gateway, preferring WebSocket.

    Yields dicts: {"t":"p","c":text,"h":bool} for progress,
                  {"t":"r","content":str,"media":list} for final result,
                  {"t":"e","error":str} on error.
    """
    from .gateway_client import gateway_client

    if gateway_client.connected:
        async for event in gateway_client.chat_stream(payload):
            yield event
        return

    # Fallback: HTTP NDJSON streaming
    hosts, port = _resolve_gateway_hosts()
    if not hosts:
        raise ConnectionError("Gateway not configured")

    auth_token = get_auth_token()
    body = json.dumps(payload, ensure_ascii=False).encode()
    last_exc: Exception | None = None

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0,
            )
        except Exception as exc:
            last_exc = exc
            continue

        try:
            auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""
            writer.write(
                (
                    f"POST /api/chat HTTP/1.1\r\n"
                    f"Host: gw\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    f"{auth_hdr}"
                    f"\r\n"
                ).encode() + body
            )
            await writer.drain()

            # Skip HTTP response headers
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=30.0)
                if line in (b"\r\n", b"\n", b""):
                    break

            # Yield NDJSON events
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=600.0)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)
            return
        except GeneratorExit:
            return
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    raise ConnectionError(f"Gateway unreachable: {last_exc}")
