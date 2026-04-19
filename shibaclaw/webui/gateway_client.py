"""Persistent WebSocket client for WebUI → Gateway communication.

Replaces the old HTTP-based helpers (_gateway_request, _gateway_post,
_gateway_chat_stream) with a single persistent connection that supports
request/response, streaming events, and push notifications.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import AsyncIterator, Callable

import websockets
from loguru import logger


class GatewayClient:
    """Singleton WebSocket client that connects to the gateway."""

    def __init__(self):
        self._ws: websockets.ClientConnection | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._stream_queues: dict[str, asyncio.Queue] = {}
        self._event_handlers: dict[str, list[Callable]] = {}
        self._connected = False
        self._recv_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._host: str = ""
        self._port: int = 0
        self._token: str = ""
        self._should_run = False

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    def configure(self, host: str, port: int, token: str):
        """Set connection parameters (called once at startup)."""
        self._host = host
        self._port = port
        self._token = token

    async def start(self):
        """Start the client and begin connecting."""
        self._should_run = True
        if not self._reconnect_task or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self):
        """Stop the client and close the connection."""
        self._should_run = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False

    async def _connect_once(self) -> bool:
        """Attempt a single connection to the gateway WS."""
        hosts = self._resolve_hosts()
        if not hosts:
            return False

        for host in hosts:
            uri = f"ws://{host}:{self._port}"
            try:
                ws = await asyncio.wait_for(
                    websockets.connect(
                        uri,
                        open_timeout=5,
                        ping_interval=None,
                        ping_timeout=None
                    ),
                    timeout=8,
                )
                # Send hello
                await ws.send(
                    json.dumps(
                        {
                            "type": "hello",
                            "token": self._token,
                            "version": _get_version(),
                        }
                    )
                )
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                resp = json.loads(raw)
                if resp.get("type") != "hello_ok":
                    await ws.close()
                    continue

                self._ws = ws
                self._connected = True
                logger.info("🔌 Gateway WS connected to {}:{}", host, self._port)

                # Start receive loop
                if self._recv_task and not self._recv_task.done():
                    self._recv_task.cancel()
                self._recv_task = asyncio.create_task(self._recv_loop())
                return True

            except Exception as e:
                logger.debug("Gateway WS connect to {}:{} failed: {}", host, self._port, e)
                continue
        return False

    async def _reconnect_loop(self):
        """Keep trying to connect until stopped."""
        delay = 1
        while self._should_run:
            if not self._connected:
                ok = await self._connect_once()
                if ok:
                    delay = 1
                else:
                    await asyncio.sleep(min(delay, 15))
                    delay = min(delay * 2, 15)
            else:
                await asyncio.sleep(3)

    async def _recv_loop(self):
        """Read messages from the gateway WebSocket."""
        ws = self._ws
        if not ws:
            return
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "pong":
                    continue

                elif msg_type == "response":
                    rid = msg.get("id", "")
                    # If this response belongs to a streaming request (e.g. chat),
                    # route it to the stream queue instead of _pending
                    if rid in self._stream_queues:
                        await self._stream_queues[rid].put(msg)
                    else:
                        fut = self._pending.pop(rid, None)
                        if fut and not fut.done():
                            fut.set_result(msg)

                elif msg_type == "event":
                    name = msg.get("name", "")
                    rid = msg.get("request_id")

                    # If this event belongs to a streaming request, queue it
                    if rid and rid in self._stream_queues:
                        await self._stream_queues[rid].put(msg)
                    else:
                        # Dispatch to registered handlers
                        for handler in self._event_handlers.get(name, []):
                            try:
                                await handler(msg)
                            except Exception as e:
                                logger.debug("Event handler error for {}: {}", name, e)

        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.debug("WS recv loop error: {}", e)
        finally:
            self._connected = False
            self._ws = None
            # Fail all pending requests
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result({"type": "response", "ok": False, "error": "connection_lost"})
            self._pending.clear()
            # Signal end to all stream queues
            for q in self._stream_queues.values():
                await q.put(None)
            self._stream_queues.clear()

    def on_event(self, name: str, handler: Callable):
        """Register a handler for gateway push events."""
        self._event_handlers.setdefault(name, []).append(handler)

    async def request(
        self, action: str, payload: dict | None = None, timeout: float = 30
    ) -> dict | None:
        """Send a request to the gateway and wait for the response."""
        if not self._connected or not self._ws:
            # Try HTTP fallback
            return await self._http_fallback(action, payload)

        request_id = str(uuid.uuid4())[:8]
        msg = json.dumps(
            {
                "type": "request",
                "id": request_id,
                "action": action,
                "payload": payload or {},
            }
        )

        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = fut

        try:
            await self._ws.send(msg)
            result = await asyncio.wait_for(fut, timeout=timeout)
            if result.get("ok"):
                return result.get("payload", {})
            return None
        except (asyncio.TimeoutError, Exception):
            self._pending.pop(request_id, None)
            return None

    async def chat_stream(self, payload: dict) -> AsyncIterator[dict]:
        """Send a chat request and yield progress events, then the final result.

        Yields dicts: {"t":"p","c":text,"h":bool} for progress,
                      {"t":"r","content":str,"media":list} for final result,
                      {"t":"e","error":str} on error.
        """
        if not self._connected or not self._ws:
            # Fall back to HTTP NDJSON streaming
            async for event in self._http_chat_stream_fallback(payload):
                yield event
            return

        request_id = str(uuid.uuid4())[:8]
        queue: asyncio.Queue = asyncio.Queue()
        self._stream_queues[request_id] = queue

        msg = json.dumps(
            {
                "type": "request",
                "id": request_id,
                "action": "chat",
                "payload": payload,
            }
        )

        try:
            await self._ws.send(msg)

            while True:
                item = await asyncio.wait_for(queue.get(), timeout=600)
                if item is None:
                    yield {"t": "e", "error": "connection_lost"}
                    return

                if item.get("type") == "event" and item.get("name") == "chat.progress":
                    p = item.get("payload", {})
                    yield {"t": "p", "c": p.get("c", ""), "h": p.get("h", False)}

                elif item.get("type") == "event" and item.get("name") == "chat.response_token":
                    p = item.get("payload", {})
                    yield {"t": "rt", "c": p.get("c", "")}

                elif item.get("type") == "response":
                    if item.get("ok"):
                        p = item.get("payload", {})
                        yield {
                            "t": "r",
                            "content": p.get("content", ""),
                            "media": p.get("media", []),
                        }
                    else:
                        yield {"t": "e", "error": item.get("error", "gateway error")}
                    return

        except asyncio.TimeoutError:
            yield {"t": "e", "error": "timeout"}
        except Exception as e:
            yield {"t": "e", "error": str(e)}
        finally:
            self._stream_queues.pop(request_id, None)

    # ── HTTP fallbacks (used when WS is not connected) ──────────────

    async def _http_fallback(self, action: str, payload: dict | None = None) -> dict | None:
        """Fall back to raw HTTP for simple requests."""
        from shibaclaw.webui.utils import _resolve_gateway_hosts

        hosts, port = _resolve_gateway_hosts()
        if not hosts:
            return None

        # Map actions to HTTP methods/paths
        method_map = {
            "status": ("GET", "/"),
            "restart": ("POST", "/restart"),
            "cron.list": ("GET", "/api/cron/list"),
            "heartbeat.status": ("GET", "/heartbeat/status"),
            "heartbeat.trigger": ("POST", "/heartbeat/trigger"),
        }
        if action in method_map:
            method, path = method_map[action]
            if method == "GET":
                return await _http_get(hosts, port, path, self._token)
            else:
                return await _http_post(hosts, port, path, payload or {}, self._token)

        if action == "cron.trigger":
            job_id = (payload or {}).get("job_id", "")
            return await _http_post(hosts, port, f"/api/cron/trigger/{job_id}", {}, self._token)

        if action == "archive":
            return await _http_post(hosts, port, "/api/archive", payload or {}, self._token)

        return None

    async def _http_chat_stream_fallback(self, payload: dict) -> AsyncIterator[dict]:
        """Fall back to HTTP NDJSON streaming for chat."""
        from shibaclaw.webui.utils import _resolve_gateway_hosts

        hosts, port = _resolve_gateway_hosts()
        if not hosts:
            raise ConnectionError("Gateway not configured")

        body = json.dumps(payload, ensure_ascii=False).encode()

        for host in hosts:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=10,
                )
            except Exception:
                continue

            try:
                auth_hdr = f"Authorization: Bearer {self._token}\r\n" if self._token else ""
                writer.write(
                    (
                        f"POST /api/chat HTTP/1.1\r\n"
                        f"Host: gw\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        f"{auth_hdr}\r\n"
                    ).encode()
                    + body
                )
                await writer.drain()

                while True:
                    line = await asyncio.wait_for(reader.readline(), timeout=30)
                    if line in (b"\r\n", b"\n", b""):
                        break

                while True:
                    line = await asyncio.wait_for(reader.readline(), timeout=600)
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

        raise ConnectionError("Gateway unreachable")

    def _resolve_hosts(self) -> list[str]:
        """Resolve gateway hosts for WebSocket connection."""
        env_host = os.environ.get("SHIBACLAW_GATEWAY_HOST", "").strip()
        docker_host = "shibaclaw-gateway"
        hosts = []

        if env_host:
            hosts.append(env_host)
        if self._host and self._host not in hosts:
            if self._host in ("0.0.0.0", "::", ""):
                hosts.append("127.0.0.1")
            else:
                hosts.append(self._host)
        if "127.0.0.1" not in hosts:
            hosts.append("127.0.0.1")
        if docker_host not in hosts:
            hosts.append(docker_host)
        return hosts


async def _http_get(hosts: list[str], port: int, path: str, token: str) -> dict | None:
    auth_hdr = f"Authorization: Bearer {token}\r\n" if token else ""
    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5,
            )
            try:
                writer.write(f"GET {path} HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(8192), timeout=10)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    return json.loads(data[body_start + 4 :])
        except Exception:
            continue
    return None


async def _http_post(hosts: list[str], port: int, path: str, body: dict, token: str) -> dict | None:
    payload = json.dumps(body, ensure_ascii=False).encode()
    auth_hdr = f"Authorization: Bearer {token}\r\n" if token else ""
    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5,
            )
            try:
                writer.write(
                    (
                        f"POST {path} HTTP/1.0\r\n"
                        f"Host: gw\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(payload)}\r\n"
                        f"{auth_hdr}\r\n"
                    ).encode()
                    + payload
                )
                await writer.drain()
                data = await asyncio.wait_for(reader.read(65536), timeout=30)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    return json.loads(data[body_start + 4 :])
        except Exception:
            continue
    return None


def _get_version() -> str:
    try:
        from shibaclaw import __version__

        return __version__
    except Exception:
        return "0.0.0"


# Singleton
gateway_client = GatewayClient()
