# Gateway WebSocket Protocol Contract

This document describes the **Gateway WebSocket API** used by the ShibaClaw WebUI, desktop launcher, and third-party clients to talk to the agent runtime.

It is distinct from the **browser WebUI WebSocket** (`WS /ws` on the WebUI port, default `3000`). That layer is documented in [`API_REFERENCE.md`](./API_REFERENCE.md#websocket). External integrators building against the agent core should use **this** gateway protocol.

> **Stability:** Fields marked **stable** are intended for third-party parsers. Unmarked or `internal` fields may change between minor releases. Event `name` values and top-level envelope keys (`type`, `id`, `ok`, `action`, `payload`, `error`, `request_id`) are stable.

---

## Endpoints

| Transport | Default | Purpose |
|-----------|---------|---------|
| Gateway WebSocket | `ws://127.0.0.1:19998` | Primary realtime API (`config.gateway.ws_port`) |
| Gateway HTTP | `http://127.0.0.1:19999` | Health, cron, chat NDJSON fallback (`config.gateway.port`) |

In Docker Compose: gateway HTTP `19999`, gateway WS `19998`, WebUI `3000`.

Auth: when a WebUI token is configured, send it in the `hello` handshake (WS) or as `Authorization: Bearer <token>` (HTTP). Run `shibaclaw print-token` to display the token.

---

## Connection handshake

1. Client opens a WebSocket to the gateway WS port.
2. Client sends **hello** (first message, required):

```json
{
  "type": "hello",
  "token": "<optional-bearer-token>",
  "version": "0.4.6"
}
```

3. Server responds with **hello_ok** or closes the connection:

```json
{
  "type": "hello_ok",
  "version": "0.4.6",
  "provider_ready": true,
  "uptime": 1234
}
```

| Field | Stability | Meaning |
|-------|-----------|---------|
| `type` | stable | `"hello_ok"` |
| `version` | stable | Gateway software version |
| `provider_ready` | stable | `true` when an LLM provider is configured |
| `uptime` | stable | Seconds since gateway start |

On auth failure the server may send `{"type":"error","error":"unauthorized"}` and close with code `4003`.

---

## Envelope types

All gateway WebSocket messages are JSON objects with a **`type`** field.

| `type` | Direction | Purpose |
|--------|-----------|---------|
| `hello` / `hello_ok` | both | Handshake |
| `ping` / `pong` | both | Keep-alive |
| `request` | client → server | RPC-style action |
| `response` | server → client | RPC result (correlated by `id`) |
| `event` | server → client | Streaming progress or push notification |
| `error` | server → client | Fatal handshake / protocol error |

---

## Requests and responses

### Client request envelope (stable)

```json
{
  "type": "request",
  "id": "a1b2c3d4",
  "action": "chat",
  "payload": {}
}
```

| Field | Stability | Notes |
|-------|-----------|-------|
| `type` | stable | Always `"request"` |
| `id` | stable | Client-generated correlation id (8+ chars recommended) |
| `action` | stable | Action name (see table below) |
| `payload` | stable | Action-specific object; may be `{}` |

### Server response envelope (stable)

Success:

```json
{
  "type": "response",
  "id": "a1b2c3d4",
  "ok": true,
  "payload": {}
}
```

Failure:

```json
{
  "type": "response",
  "id": "a1b2c3d4",
  "ok": false,
  "error": "no_provider"
}
```

| Field | Stability | Notes |
|-------|-----------|-------|
| `type` | stable | Always `"response"` |
| `id` | stable | Matches the request `id` |
| `ok` | stable | `true` = success, `false` = failure |
| `payload` | stable | Present when `ok: true` |
| `error` | stable | Present when `ok: false`; machine-readable string |

### Supported actions

| `action` | `payload` (stable keys) | Response `payload` |
|----------|-------------------------|--------------------|
| `status` | — | `status`, `uptime`, `provider_ready` |
| `chat` | `content`, `session_key`, `channel`, `chat_id`, `media`, `metadata`, `profile_id` | Final chat result via streaming events + terminal `response` |
| `restart` | — | `status: "restarting"` |
| `cron.list` | — | `jobs[]` |
| `cron.trigger` | `job_id` | `triggered` |
| `heartbeat.status` | — | heartbeat status object |
| `heartbeat.trigger` | — | `triggered`, `response` |
| `archive` | `snapshot` | `archived` |

Unknown actions return `ok: false`, `error: "unknown action: …"`.

---

## Chat streaming events

`action: "chat"` is **async**: the gateway acknowledges by emitting zero or more **`event`** messages, then a terminal **`response`** with the same `id`.

### Event envelope (stable)

```json
{
  "type": "event",
  "name": "chat.progress",
  "request_id": "a1b2c3d4",
  "payload": {}
}
```

| Field | Stability | Notes |
|-------|-----------|-------|
| `type` | stable | Always `"event"` |
| `name` | stable | Event kind (see below) |
| `request_id` | stable | Correlates to the `chat` request `id` |
| `payload` | stable | Event-specific body |
| `session_key` | stable | Present on push events (`session.notify`); optional on chat events |

### Event catalog

| `name` | Role | Stable `payload` keys |
|--------|------|------------------------|
| `chat.progress` | Background agent progress, reasoning summaries, tool status | `c` (string chunk), `h` (bool tool hint) |
| `chat.response_token` | **Final answer token stream** (user-visible reply) | `c` (string token) |
| `session.notify` | Push notification to WebUI clients (heartbeat, cron, updates) | `content`, `source`, `persist`, `msg_type`, `metadata` |

#### Interpreting `chat.progress`

- **`h: false`** — agent progress / thinking UI text. The WebUI maps this to a `thinking` event. Content may include provider reasoning summaries depending on model configuration; it is **not** a separate hidden-reasoning channel on the gateway wire format today.
- **`h: true`** — tool execution hint. The WebUI maps this to a `tool` event.

#### Interpreting `chat.response_token`

Incremental tokens for the **final assistant reply**. Concatenate `payload.c` values in order to reconstruct streamed answer text before the terminal response arrives.

#### Push: `session.notify`

Broadcast to connected clients when background work completes (heartbeat, cron, update checks). Not tied to an active chat `request_id` unless the gateway sets one.

---

## Chat request payload (stable)

```json
{
  "content": "Summarize the repo",
  "session_key": "webui:abc12345",
  "channel": "webui",
  "chat_id": "abc12345",
  "media": ["/absolute/or/workspace-relative/path.png"],
  "metadata": {
    "session_key": "webui:abc12345",
    "message_id": "msg_1",
    "attachments": []
  },
  "profile_id": "default"
}
```

| Field | Stability | Notes |
|-------|-----------|-------|
| `content` | stable | User message text |
| `session_key` | stable | Session identifier (`webui:…`, `cli:direct`, channel keys) |
| `channel` | stable | Origin channel (`webui`, `cli`, `telegram`, …) |
| `chat_id` | stable | Channel-specific chat id |
| `media` | stable | Optional list of image paths for multimodal input |
| `metadata` | stable | Opaque passthrough; `message_id` recommended for UI correlation |
| `profile_id` | stable | Agent profile override |

### Terminal chat response payload (stable)

When the turn completes successfully:

```json
{
  "type": "response",
  "id": "a1b2c3d4",
  "ok": true,
  "payload": {
    "content": "Full assistant reply text",
    "media": ["workspace/output.png"]
  }
}
```

| Field | Stability | Notes |
|-------|-----------|-------|
| `content` | stable | Final assistant message (may duplicate streamed tokens) |
| `media` | stable | Generated file paths attached to the reply |

---

## Success and error semantics

### Successful chat turn

A client should treat a chat request as **successful** when it receives:

1. Zero or more `event` messages with matching `request_id`, then
2. A terminal `response` with the same `id` and **`ok: true`**.

Typical event sequence:

```
event chat.progress (h:false) …   # optional thinking/progress
event chat.progress (h:true)  …   # optional tool hints
event chat.response_token     …   # optional streamed answer tokens
response ok:true              …   # terminal — turn complete
```

If `chat.response_token` events were received, `payload.content` in the final `response` should match the concatenated stream (modulo whitespace normalization).

### Failed chat turn

Failure modes:

| Signal | Meaning |
|--------|---------|
| `response` with `ok: false` | Turn failed; read `error` string |
| WebSocket closes mid-stream | Treat as `connection_lost` |
| No terminal `response` before disconnect | Incomplete turn — surface as error |

Common `error` values: `no_provider`, exception text from agent runtime, `unknown action: …`, `unauthorized`.

### Non-chat requests

Non-streaming actions (`status`, `cron.list`, …) complete with a **single** `response`. Success = `ok: true` within the client timeout.

---

## HTTP NDJSON fallback

When WebSocket is unavailable, clients may POST to the gateway HTTP port:

```http
POST /api/chat HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{"content":"Hello","session_key":"webui:direct","channel":"webui","chat_id":"direct"}
```

Response: `Content-Type: application/x-ndjson` — one JSON object per line:

| Line `t` | Maps to WS | Stable fields |
|----------|------------|---------------|
| `p` | `chat.progress` | `c`, `h` |
| `r` | terminal success | `content`, `media` |
| `e` | terminal error | `error` |

There is **no** `rt` line in the HTTP fallback today; token streaming is WebSocket-only (`chat.response_token`).

---

## WebUI browser protocol (reference)

Third-party **frontends** that embed the stock WebUI connect to `ws://<webui-host>:3000/ws`, not directly to the gateway port. That protocol uses different message types (`message`, `thinking`, `response_chunk`, `response`, …) and is documented in [`API_REFERENCE.md`](./API_REFERENCE.md#websocket).

The WebUI server translates gateway events internally via `gateway_client.chat_stream()`.

---

## Implementation references

| Component | Path |
|-----------|------|
| Gateway WS server | `shibaclaw/cli/gateway.py` |
| WebUI gateway client | `shibaclaw/webui/gateway_client.py` |
| Browser WS handler | `shibaclaw/webui/ws_handler.py` |
| Default ports | `shibaclaw/config/schema.py` (`gateway.port`, `gateway.ws_port`) |

---

*Derived from source — ShibaClaw v0.4.6. Fixes [#26](https://github.com/RikyZ90/ShibaClaw/issues/26).*
