# ShibaClaw REST API Reference

This document describes the full HTTP REST API exposed by the ShibaClaw WebUI server (default: `http://127.0.0.1:3000`).

## Table of Contents

- [Authentication](#authentication)
- [Status](#status)
- [Settings](#settings)
- [Sessions](#sessions)
- [Context](#context)
- [Skills](#skills)
- [Profiles](#profiles)
- [Gateway](#gateway)
- [Heartbeat](#heartbeat)
- [Cron](#cron)
- [Filesystem](#filesystem)
- [OAuth](#oauth)
- [Onboarding](#onboarding)
- [System / Updates](#system--updates)
- [Internal](#internal)
- [WebSocket](#websocket)

---

## Authentication

When authentication is enabled (via `SHIBACLAW_AUTH_TOKEN` environment variable), every request must include:

```
Authorization: Bearer <token>
```

Requests without a valid token will receive `401 Unauthorized`.

---

### `GET /api/auth/status`

Check whether authentication is required by the server.

**Response**

```json
{ "auth_required": true }
```

---

### `POST /api/auth/verify`

Verify an auth token value.

**Request body**

```json
{ "token": "your-secret-token" }
```

**Response**

```json
{ "valid": true, "auth_required": true }
```

| Field | Type | Description |
|---|---|---|
| `valid` | boolean | Whether the submitted token is accepted |
| `auth_required` | boolean | Whether auth is enabled at all |

---

## Status

### `GET /api/status`

Returns general server and agent status.

**Response**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "agent_configured": true,
  "provider": "openai",
  "model": "gpt-4o",
  "workspace": "/home/user/.shibaclaw/workspace",
  "gateway": true
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` or `"gateway_offline"` |
| `version` | string | Installed ShibaClaw version |
| `agent_configured` | boolean | Whether the agent is ready to serve requests |
| `provider` | string | Active LLM provider name |
| `model` | string | Active model identifier |
| `workspace` | string | Absolute path to the workspace directory |
| `gateway` | boolean | Whether the gateway process is reachable |

---

## Settings

### `GET /api/settings`

Get the current configuration. **Secrets are redacted** (API keys replaced with `"***"`).

**Response** — the full `Config` object serialised to JSON.

```json
{
  "agents": {
    "defaults": {
      "provider": "openai",
      "model": "gpt-4o",
      "context_window_tokens": 128000,
      "pinned_skills": [],
      "max_pinned_skills": 5
    }
  },
  "providers": {
    "openai": { "api_key": "***" }
  }
}
```

---

### `POST /api/settings`

Update configuration with a **partial** JSON object (deep-merged into the current config). On success, resets the running agent.

**Request body** (partial config)

```json
{
  "agents": {
    "defaults": {
      "model": "gpt-4o-mini"
    }
  }
}
```

**Response**

```json
{ "status": "updated" }
```

**Error responses**

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "No config" }` | Config not yet loaded |
| 422 | `{ "error": "Invalid config: ..." }` | Validation failure |

---

## Sessions

### `GET /api/sessions`

List all saved chat sessions.

**Response**

```json
{
  "sessions": [
    {
      "id": "abc123",
      "nickname": "My first session",
      "created_at": 1713500000,
      "message_count": 12
    }
  ]
}
```

---

### `GET /api/sessions/{session_id}`

Get details and message history for a specific session.

**Path params**

| Param | Description |
|---|---|
| `session_id` | Session identifier |

**Response**

```json
{
  "messages": [
    { "role": "user", "content": "Hello!" },
    { "role": "assistant", "content": "Hi there!" }
  ],
  "nickname": "My session",
  "profile_id": "default"
}
```

---

### `PATCH /api/sessions/{session_id}`

Update session metadata (nickname and/or profile).

**Request body** (all fields optional)

```json
{
  "nickname": "Renamed session",
  "profile_id": "my-profile"
}
```

**Response**

```json
{ "status": "updated", "profile_id": "my-profile" }
```

---

### `DELETE /api/sessions/{session_id}`

Permanently delete a session.

**Response**

```json
{ "status": "deleted" }
```

| Status | Body | Cause |
|---|---|---|
| 404 | `{ "error": "Session not found" }` | Unknown session ID |

---

### `POST /api/sessions/{session_id}/archive`

Archive a session: consolidates its messages into long-term memory via the gateway, then deletes the session file.

**Response**

```json
{ "status": "archived" }
```

---

## Context

### `GET /api/context`

Generate a detailed context summary including the assembled system prompt, token counts, and session messages.

**Query params**

| Param | Type | Default | Description |
|---|---|---|---|
| `session_id` | string | — | Include session messages in the summary |
| `summary` | boolean | false | Return only token counts (faster) |

**Full response**

```json
{
  "context": "## 🧠 System Prompt (1234 tokens)\n\n```markdown\n...\n```\n\n---\n\n## 💬 Session Messages (5 messages)\n...",
  "tokens": {
    "system_prompt": 1234,
    "tools": 0,
    "messages": 567,
    "total": 1801,
    "context_window": 128000,
    "usage_pct": 1
  }
}
```

**Summary-only response** (when `?summary=true`)

```json
{
  "tokens": {
    "system_prompt": 1234,
    "tools": 0,
    "messages": 567,
    "total": 1801,
    "context_window": 128000,
    "usage_pct": 1
  }
}
```

---

## Skills

### `GET /api/skills`

List all skills (built-in and workspace), with availability info and pinned status.

**Response**

```json
{
  "skills": [
    {
      "name": "web_search",
      "description": "Search the web using DuckDuckGo",
      "source": "builtin",
      "path": "/path/to/skill.md",
      "available": true,
      "missing_requirements": "",
      "always": false,
      "pinned": true
    }
  ],
  "pinned_skills": ["web_search"],
  "max_pinned_skills": 5
}
```

| Field | Type | Description |
|---|---|---|
| `source` | string | `"builtin"` or `"workspace"` |
| `available` | boolean | Whether all requirements are met |
| `missing_requirements` | string | Description of missing env vars or tools |
| `always` | boolean | Whether the skill is always loaded regardless of pinning |
| `pinned` | boolean | Whether this skill is currently pinned |

---

### `POST /api/skills/pin`

Set the complete list of pinned skills.

**Request body**

```json
{ "pinned_skills": ["web_search", "code_runner"] }
```

**Response**

```json
{ "status": "updated", "pinned_skills": ["web_search", "code_runner"] }
```

**Error responses**

| Status | Body | Cause |
|---|---|---|
| 422 | `{ "error": "Cannot pin more than N skills" }` | Exceeds `max_pinned_skills` |
| 422 | `{ "error": "Unknown skills: ..." }` | One or more skill names not found |

---

### `DELETE /api/skills/{name}`

Delete a workspace skill by name. Built-in skills cannot be deleted.

**Path params**

| Param | Description |
|---|---|
| `name` | Skill name |

**Response**

```json
{ "status": "deleted", "name": "my-skill" }
```

| Status | Body | Cause |
|---|---|---|
| 403 | `{ "error": "Cannot delete built-in skills" }` | Attempted to delete a built-in skill |
| 404 | `{ "error": "Skill '...' not found" }` | Unknown skill |

---

### `POST /api/skills/import`

Import skills from a `.zip` file upload.

**Request body** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | file | `.zip` archive containing skill files |
| `conflict` | string | `"overwrite"` (default), `"skip"`, or `"rename"` |
| `dry_run` | boolean | If `true`, simulate import without writing any files |

**Response**

```json
{
  "status": "ok",
  "dry_run": false,
  "imported": ["my-skill"],
  "imported_count": 1,
  "skipped": [],
  "errors": []
}
```

---

## Profiles

Profiles define custom agent identities (soul, avatar, description). The `default` profile always exists and cannot be deleted.

### `GET /api/profiles`

List all available profiles.

**Response**

```json
{
  "profiles": [
    {
      "id": "default",
      "label": "Default",
      "description": "The standard ShibaClaw agent",
      "avatar": null
    },
    {
      "id": "researcher",
      "label": "Researcher",
      "description": "Focused research assistant",
      "avatar": "🔬"
    }
  ]
}
```

---

### `GET /api/profiles/{profile_id}`

Get a specific profile, including its soul content.

**Response**

```json
{
  "id": "researcher",
  "label": "Researcher",
  "description": "Focused research assistant",
  "soul": "You are a meticulous research assistant...",
  "avatar": "🔬"
}
```

| Status | Body | Cause |
|---|---|---|
| 404 | `{ "error": "Profile not found" }` | Unknown profile ID |

---

### `POST /api/profiles`

Create a new custom profile.

**Request body**

```json
{
  "id": "researcher",
  "label": "Researcher",
  "description": "Focused research assistant",
  "soul": "You are a meticulous research assistant...",
  "avatar": "🔬"
}
```

| Field | Required | Constraints |
|---|---|---|
| `id` | ✅ | 2–50 alphanumeric chars, hyphens, underscores |
| `label` | ✅ | Non-empty string |
| `description` | ❌ | Optional string |
| `soul` | ❌ | Markdown text defining the agent's personality |
| `avatar` | ❌ | Emoji or short string |

**Response** — `201 Created`

```json
{
  "id": "researcher",
  "label": "Researcher",
  "description": "Focused research assistant",
  "soul": "...",
  "avatar": "🔬"
}
```

| Status | Body | Cause |
|---|---|---|
| 409 | `{ "error": "Profile already exists" }` | ID already in use |
| 422 | `{ "error": "id and label are required" }` | Missing required fields |
| 422 | `{ "error": "Invalid id: ..." }` | ID does not match naming rules |

---

### `PUT /api/profiles/{profile_id}`

Update an existing profile. All body fields are optional; only provided fields are changed.

**Request body**

```json
{
  "label": "Senior Researcher",
  "soul": "You are an expert...",
  "avatar": "🧪"
}
```

**Response** — the updated profile object.

| Status | Body | Cause |
|---|---|---|
| 404 | `{ "error": "Profile not found" }` | Unknown profile ID |

---

### `DELETE /api/profiles/{profile_id}`

Delete a custom profile. The `default` profile and built-in profiles cannot be deleted.

**Response**

```json
{ "status": "deleted" }
```

| Status | Body | Cause |
|---|---|---|
| 403 | `{ "error": "Cannot delete built-in or default profile" }` | Protected profile |

---

## Gateway

The gateway is a separate background process that handles LLM inference and long-running tasks.

### `GET /api/gateway-health`

Check gateway reachability. Tries WebSocket first, falls back to raw HTTP.

**Response**

```json
{
  "reachable": true,
  "status": "ok",
  "provider_ready": true
}
```

| Field | Type | Description |
|---|---|---|
| `reachable` | boolean | Whether the gateway is reachable |
| `reason` | string | Present when `reachable` is `false`: `"no_config"` or `"unreachable"` |

---

### `POST /api/gateway-restart`

Send a restart command to the gateway.

**Response**

```json
{ "status": "restarting" }
```

| Status | Body | Cause |
|---|---|---|
| 503 | `{ "error": "Gateway unreachable" }` | Cannot reach gateway |

---

## Heartbeat

The heartbeat module probes external resources or URLs on a schedule.

### `GET /api/heartbeat/status`

Proxy heartbeat status from the gateway.

**Response**

```json
{
  "reachable": true,
  "last_check": 1713500000,
  "status": "ok"
}
```

---

### `POST /api/heartbeat/trigger`

Manually trigger an immediate heartbeat check.

**Response** — forwarded from the gateway.

| Status | Body | Cause |
|---|---|---|
| 503 | `{ "error": "Gateway unreachable" }` | Cannot reach gateway |

---

## Cron

Scheduled jobs managed by the gateway.

### `GET /api/cron/jobs`

List all scheduled cron jobs.

**Response**

```json
{
  "jobs": [
    {
      "id": "daily-summary",
      "schedule": "0 8 * * *",
      "enabled": true,
      "last_run": 1713500000
    }
  ]
}
```

| Status | Body | Cause |
|---|---|---|
| 503 | `{ "jobs": [], "error": "gateway_unreachable" }` | Gateway offline |

---

### `POST /api/cron/jobs/{job_id}/trigger`

Manually trigger a specific cron job immediately.

**Path params**

| Param | Description |
|---|---|
| `job_id` | Cron job identifier |

**Response** — forwarded from the gateway.

| Status | Body | Cause |
|---|---|---|
| 503 | `{ "error": "Gateway unreachable" }` | Cannot reach gateway |

---

## Filesystem

All filesystem operations are sandboxed to the configured workspace directory.

### `POST /api/upload`

Upload one or more files into the workspace `uploads/` directory.

**Request body** — `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | file (repeatable) | One or more files to upload |

**Response**

```json
{
  "status": "success",
  "files": [
    {
      "filename": "document.pdf",
      "url": "/api/file-get?path=/abs/path/to/uploads/document.pdf"
    }
  ]
}
```

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "No files uploaded" }` | No `file` field in form |

---

### `GET /api/file-get`

Serve a file from the workspace. Restricted to paths within the workspace; images are cached for 1 hour.

**Query params**

| Param | Required | Description |
|---|---|---|
| `path` | ✅ | Absolute path to the file |

**Response** — the raw file bytes with inferred `Content-Type`.

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "No path provided" }` | Missing `path` param |
| 403 | `{ "error": "Forbidden" }` | Path is outside the workspace |
| 404 | `{ "error": "File not found" }` | File does not exist |

---

### `POST /api/file-save`

Overwrite a workspace file with new UTF-8 text content.

**Request body**

```json
{
  "path": "/abs/path/to/workspace/file.md",
  "content": "# New content\n\nHello world!"
}
```

**Response**

```json
{ "status": "ok", "path": "/abs/path/to/workspace/file.md", "bytes": 42 }
```

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "path and content are required" }` | Missing fields |
| 403 | `{ "error": "Forbidden" }` | Path outside workspace |
| 404 | `{ "error": "File not found" }` | File does not exist |

---

### `GET /api/fs/explore`

List the contents of a workspace directory.

**Query params**

| Param | Required | Description |
|---|---|---|
| `path` | ✅ | Absolute path to the directory |

**Response**

```json
{
  "current_path": "/abs/path/to/workspace/notes",
  "parent_path": "/abs/path/to/workspace",
  "items": [
    {
      "name": "ideas.md",
      "path": "notes/ideas.md",
      "is_dir": false,
      "size": 1024,
      "mtime": 1713500000.0
    },
    {
      "name": "archive",
      "path": "notes/archive",
      "is_dir": true,
      "size": null,
      "mtime": 1713400000.0
    }
  ]
}
```

Items are sorted: directories first, then files alphabetically.

| Status | Body | Cause |
|---|---|---|
| 403 | `{ "error": "Forbidden" }` | Path outside workspace |
| 404 | `{ "error": "Directory not found" }` | Path does not exist or is not a directory |

---

## OAuth

Manage OAuth-based LLM provider credentials.

### `GET /api/oauth/providers`

List OAuth-capable providers and their current auth status.

**Response**

```json
{
  "providers": [
    {
      "name": "github_copilot",
      "label": "GitHub Copilot",
      "status": "configured",
      "message": "Cached credentials found"
    },
    {
      "name": "openai_codex",
      "label": "OpenAI Codex",
      "status": "not_configured",
      "message": ""
    }
  ]
}
```

| `status` value | Meaning |
|---|---|
| `configured` | Valid credentials found |
| `not_configured` | No credentials stored |
| `error` | An unexpected error occurred |

---

### `POST /api/oauth/login`

Start an OAuth login flow for a provider. Returns a job object for polling.

**Request body**

```json
{ "provider": "github_copilot" }
```

Supported values: `"github_copilot"`, `"openai_codex"`.

**Response** — varies by provider, typically:

```json
{
  "job_id": "a1b2c3",
  "status": "running",
  "verification_uri": "https://github.com/login/device",
  "user_code": "ABCD-1234"
}
```

---

### `GET /api/oauth/job/{job_id}`

Poll the status of a running OAuth login job.

**Response**

```json
{
  "job": {
    "provider": "github_copilot",
    "status": "done",
    "logs": ["🔑 Waiting for authorization...", "✅ Token acquired"]
  }
}
```

| `status` value | Meaning |
|---|---|
| `running` | Still in progress |
| `done` | Successfully completed |
| `error` | Login failed |

| Status | Body | Cause |
|---|---|---|
| 404 | `{ "error": "Job not found" }` | Unknown job ID |

---

### `POST /api/oauth/code`

Submit a device authorization code to complete the OAuth flow.

**Request body**

```json
{ "job_id": "a1b2c3", "code": "ABCD-1234" }
```

**Response**

```json
{ "ok": true }
```

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "Job does not accept code input" }` | Flow does not require manual code |
| 404 | `{ "error": "Job not found" }` | Unknown job ID |

---

## Onboarding

First-run wizard endpoints for configuring providers and workspace templates.

### `GET /api/onboard/providers`

Return provider list with detection status (env vars, oauth, configured keys).

**Response**

```json
{
  "providers": [
    {
      "name": "openai",
      "label": "OpenAI",
      "env_key": "OPENAI_API_KEY",
      "default_model": "gpt-4o",
      "is_local": false,
      "is_oauth": false,
      "status": "env_detected"
    }
  ],
  "current_provider": "openai",
  "current_model": "gpt-4o"
}
```

| `status` value | Meaning |
|---|---|
| `available` | Provider is listed but not configured |
| `env_detected` | API key found in environment variables |
| `oauth_ok` | OAuth credentials present |
| `configured` | API key stored in config file |

---

### `GET /api/onboard/templates`

Return which workspace template files are new vs would be overwritten.

**Response**

```json
{
  "new_files": ["IDENTITY.md", "BOOTSTRAP.md", "memory/MEMORY.md"],
  "existing_files": ["SKILLS.md"]
}
```

---

### `POST /api/onboard/submit`

Apply the onboarding wizard: saves config, syncs workspace templates, and resets the agent.

**Request body**

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "sk-...",
  "overwrite_templates": ["IDENTITY.md"]
}
```

| Field | Required | Description |
|---|---|---|
| `provider` | ✅ | Provider name |
| `model` | ✅ | Model identifier |
| `api_key` | ❌ | API key (not needed for local/oauth providers) |
| `overwrite_templates` | ❌ | List of existing template filenames to overwrite |

**Response**

```json
{ "status": "ok" }
```

| Status | Body | Cause |
|---|---|---|
| 422 | `{ "error": "provider and model are required" }` | Missing required fields |

---

## System / Updates

### `GET /api/update/check`

Check the appropriate update source for the current installation method.

**Query params**

| Param | Default | Description |
|---|---|---|
| `force` | false | Bypass any cached check result |

**Response**

```json
{
  "install_method": "pip",
  "update_available": true,
  "current": "0.1.0",
  "latest": "0.2.0",
  "display_current": "0.1.0",
  "display_latest": "0.2.0",
  "action_kind": "automatic",
  "action_label": "Update now",
  "action_command": "pip install --upgrade shibaclaw",
  "action_url": "https://github.com/...",
  "release_url": "https://github.com/...",
  "download_url": null,
  "manifest_url": "https://github.com/.../update_manifest.json",
  "summary": "Version 0.2.0 is available on PyPI.",
  "notes": [],
  "notification": {
    "category": "update",
    "title": "ShibaClaw update available",
    "body": "Version 0.2.0 is available on PyPI.",
    "action_label": "Update now",
    "action_command": "pip install --upgrade shibaclaw",
    "action_url": "https://github.com/...",
    "text": "🆕 *ShibaClaw update available*\n0.1.0 → 0.2.0\nSuggested: pip install --upgrade shibaclaw"
  },
  "checked_at": 1710000000,
  "stale": false,
  "error": null
}
```

`install_method` is one of `pip`, `docker`, `exe`, or `source`. Even when `update_available` is `false`, manual-install methods can still return `action_*`, `summary`, and `notes` so the WebUI can render method-specific guidance. For `source`, official repository checkouts compare the local version against the latest GitHub release manifest version and return release-oriented guidance rather than inspecting `origin/main`.

---

### `GET /api/update/manifest`

Fetch the update manifest from a GitHub URL.

**Query params**

| Param | Required | Description |
|---|---|---|
| `url` | ✅ | HTTPS URL on `github.com` or `raw.githubusercontent.com` |

**Response**

```json
{
  "manifest": { "version": "0.2.0", "changes": [] },
  "personal_files": [
    {
      "path": "USER.md",
      "note": "Customized identity template"
    }
  ]
}
```

The `personal_files` list contains workspace files that will be backed up before applying a pip update.

| Status | Body | Cause |
|---|---|---|
| 400 | `{ "error": "Invalid manifest URL" }` | URL is not from an allowed GitHub host |

---

### `POST /api/update/apply`

Apply a ShibaClaw update using a normalized update payload. For `pip` installs this runs the upgrade, optionally backs up personal files from the manifest, and restarts the server. For `docker`, `exe`, and `source`, it returns manual-action guidance without mutating the local install. For `source`, the suggested manual action is release-oriented, for example `git fetch --tags && git checkout vX.Y.Z && pip install -e .`.

**Request body**

```json
{
  "update": {
    "install_method": "pip",
    "latest": "0.2.0",
    "action_kind": "automatic",
    "action_label": "Update now",
    "action_command": "pip install --upgrade shibaclaw"
  },
  "manifest": { "version": "0.2.0", "changes": [] }
}
```

Legacy manifest-only requests are still accepted for backward compatibility.

**Response**

```json
{
  "install_method": "pip",
  "version": "0.2.0",
  "requires_manual_action": false,
  "action_kind": "automatic",
  "action_label": "Update now",
  "action_command": "pip install --upgrade shibaclaw",
  "action_url": "https://github.com/...",
  "message": "Updated ShibaClaw to 0.2.0.",
  "backup": {
    "moved": [
      {
        "from": "C:/Users/example/.shibaclaw/workspace/USER.md",
        "to": "C:/Users/example/.shibaclaw/workspace/_old/2026-05-13_0.2.0/USER.md"
      }
    ],
    "skipped": []
  },
  "pip": { "ok": true, "output": "...", "command": "python -m pip install --upgrade shibaclaw==0.2.0" },
  "restarting": true
}
```

Manual methods return the same top-level structure with `requires_manual_action: true`, `pip: null`, and `restarting: false`.

---

### `POST /api/restart`

Restart the ShibaClaw WebUI server process immediately.

**Response**

```json
{ "status": "restarting" }
```

---

## Internal

These endpoints are used internally by other ShibaClaw components and are **not intended for external use**.

### `POST /api/internal/session-notify`

Receive a background notification from the gateway and broadcast it to connected WebUI clients.

**Request body**

```json
{
  "session_key": "abc123",
  "content": "Task completed.",
  "source": "background",
  "persist": true,
  "msg_type": "response",
  "metadata": {
    "category": "update",
    "title": "ShibaClaw update available",
    "action_command": "pip install --upgrade shibaclaw"
  }
}
```

**Response**

```json
{ "delivered": true, "matched_sessions": 1 }
```

---

## WebSocket

### `WS /ws`

The primary real-time channel for all agent interactions.

**Connection URL**

```
ws://127.0.0.1:3000/ws
```

**Authentication** — include the token as a query parameter when auth is enabled:

```
ws://127.0.0.1:3000/ws?token=<your-token>
```

### Client → Server messages

All messages are JSON objects with an `action` field.

#### Start a chat turn

```json
{
  "action": "chat",
  "session_id": "abc123",
  "message": "Hello, agent!",
  "profile_id": "default"
}
```

#### Interrupt the agent

```json
{ "action": "interrupt" }
```

#### Keep-alive ping

```json
{ "action": "ping" }
```

### Server → Client messages

All messages are JSON objects with a `type` field.

| `type` | Description |
|---|---|
| `pong` | Response to `ping` |
| `thinking` | Agent is processing |
| `chunk` | Streaming text chunk: `{ "type": "chunk", "content": "..." }` |
| `tool_call` | Agent is invoking a tool: `{ "type": "tool_call", "name": "...", "input": {...} }` |
| `tool_result` | Tool result: `{ "type": "tool_result", "name": "...", "output": "..." }` |
| `done` | Turn complete |
| `error` | An error occurred: `{ "type": "error", "message": "..." }` |
| `notification` | Background notification delivered to the session |

Background notifications may include `source` and `metadata` fields. Update notifications use `metadata.category = "update"` plus optional `title`, `body`, `action_command`, and `action_url` fields.

---

*Generated from source code — last updated with ShibaClaw v0.1.x*
