# Changelog

All notable changes to this project are documented in this file.

## [0.0.15] - 2026-04-07

### Fixed
- **Context window overrun** — Fixed token estimation undercounting that caused sessions to exceed the context window. `estimate_prompt_tokens()` now includes message roles, tool calls, and structural overhead (+4 tokens per message).
- **Telegram proxy saved as `{}` instead of `null`** — Fixed `_deep_merge` in `api.py` to explicitly handle `None` values (previously `null` patches were ignored or overwritten). Fixed WebUI JS to correctly type `null` config fields as `"null"` instead of `"object"`, preventing empty inputs from being serialized as `{}` when saving channel settings (fixes #11).

## [0.0.14] - 2026-04-06

### Fixed
- **Gateway health check in bare metal setups** — Fixed false "Gateway Down" status in WebUI when running `pip install` setups. The health check now correctly uses the configured `gateway.host` value (e.g. `127.0.0.1`) instead of defaulting to the Docker-only `shibaclaw-gateway` hostname.
- Affected functions: `api_gateway_health`, `_gateway_request`, `api_gateway_restart` in `api.py`, and `_poll_github_token` in `oauth_github.py`.

## [0.0.13] - 2026-04-06

### Added
- **Email channel UI** — Reorganized email settings in WebUI into three sections: 📥 Email IN (IMAP), 📤 Email OUT (SMTP), ⚙️ General, with human-readable labels and proper input types.
- **Config auto-migration** — Email channel fields are now automatically populated with defaults on server startup if missing, without overwriting existing values.

### Fixed
- **Security: Socket.IO authentication bypass** — Removed `/socket.io` from public paths so WebSocket connections now require a valid auth token.
- **Security: Auth token leakage in URLs** — Removed the auth token from upload response URLs to prevent credential exposure in server logs and browser history.
- **Security: SSRF in update manifest validation** — Replaced naive `startswith()` checks with proper `urlparse()` validation and an explicit hostname allowlist (`github.com`, `raw.githubusercontent.com`).
- **Security: Timing attack on token comparison** — Switched to `hmac.compare_digest()` for constant-time auth token verification.
- **Stability: Race condition in task callback cleanup** — Added safe task removal with `ValueError` handling to prevent crashes during concurrent `/stop` commands.
- **Correctness: Severity comparison logic** — Rewrote `Severity.__ge__()` and `__gt__()` to use an explicit score mapping, eliminating incorrect comparison results.

### Changed
- **Auth middleware** — Added `hmac` import and hardened `check_token()` with constant-time comparison for both header and query-param tokens.

## [0.0.12] - 2026-04-05

### Added
- Guided onboarding in both CLI and WebUI, with provider detection from environment variables, OAuth handoff, model selection, template refresh, and optional channel setup.
- A new automation panel in the WebUI sidebar showing cron jobs and heartbeat status, including manual trigger actions.
- Ranked `memory_search` over `memory/HISTORY.md`, combining recency, importance, and keyword relevance.
- Heartbeat status and manual trigger endpoints exposed through the gateway and proxied in the WebUI.
- Expanded regression coverage for heartbeat telemetry, WebUI background delivery, overdue cron jobs, and memory search/template behavior.

### Changed
- Long-term memory is now split between `USER.md` for durable personal profile data and `memory/MEMORY.md` for operational project context.
- `memory/MEMORY.md` now follows a priority-based structure: `Environment`, `Entities`, `Project State`, and `Dynamic Context`.
- `shibaclaw onboard` is now the primary setup command; the old `--wizard` flow has been removed in favor of the new guided experience.
- The WebUI now includes onboarding entry points from startup, settings, and the empty-state experience, plus a refreshed footer layout.
- Release metadata now includes a dedicated `CHANGELOG.md`, a richer 0.0.12 update manifest, and automatic manifest upload in the release workflow.

### Fixed
- Scheduled jobs created from WebUI or channels now keep a stable session target for delivery, including WebUI sessions and threaded channel flows.
- One-shot `at` cron jobs that become overdue while the service is down now execute on startup instead of remaining stuck forever.
- Cron execution no longer races between Docker containers: the WebUI process is now the single cron runner and initializes eagerly on startup.
- Heartbeat delivery now chooses a stable target session, can notify WebUI sessions directly, and exposes live telemetry for troubleshooting.
- Update manifest path handling is normalized so the update panel can correctly identify changed personal files in this and older manifest formats.

### Upgrade Notes
- Run `shibaclaw onboard` after upgrading if you want to refresh workspace templates and built-in skills for the new onboarding and memory layout.
- Existing `USER.md`, `memory/MEMORY.md`, `memory/HISTORY.md`, and workspace skill files are preserved unless you explicitly overwrite them.
- Restart the WebUI or Docker stack after upgrading so cron and heartbeat services pick up the new session-aware routing logic.