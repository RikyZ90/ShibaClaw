# Security Policy

## Supported Versions

| Version  | Supported          |
| -------- | ------------------ |
| 0.0.20+  | :white_check_mark: |
| < 0.0.20 | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ShibaClaw, **please report it responsibly**.

### How to Report

1. **Email**: Send details to **security@shibaclaw.dev** (or open a private advisory on GitHub).
2. **GitHub Security Advisories**: Use the [Report a Vulnerability](https://github.com/RikyZ90/ShibaClaw/security/advisories/new) form on this repository.

**Do NOT** open a public issue for security vulnerabilities.

### What to Include

- A description of the vulnerability and its potential impact.
- Steps to reproduce or a minimal proof-of-concept.
- The affected version(s) and component(s) (e.g. `security/network.py`, `agent/tools/shell.py`).

### What to Expect

- **Acknowledgement** within 48 hours.
- **Triage & Assessment** within 7 days.
- **Fix Timeline**: Critical/High severity fixes are targeted within 14 days of confirmation. Medium/Low within 30 days.
- **Credit**: Reporters will be credited in the release notes unless they prefer anonymity.

## Security Architecture

ShibaClaw implements defense-in-depth across multiple layers:

### Agent Execution

- **Shell deny-list**: The `exec` tool blocks 20+ dangerous patterns (fork bombs, `rm -rf /`, `sudo`, hex/unicode-encoded obfuscation, command substitution, `curl|bash`) before execution.
- **Install audit**: `pip install` commands are scanned for known CVEs via `pip-audit`. `npm install` commands are scanned via `npm audit`. Severity threshold is configurable (`installAuditBlockSeverity`).
- **Tool output truncation**: LLM context is protected from overflow via configurable character caps on tool results.
- **Structural randomized wrapping**: A random nonce is regenerated each turn and used to fence tool outputs, mitigating prompt injection from untrusted content.
- **Untrusted content banner**: Web-fetched content is explicitly marked with `[UNTRUSTED EXTERNAL CONTENT]` delimiters.
- **Workspace sandboxing**: File tools and the WebUI file browser are constrained to the configured workspace root.

### Network Security (SSRF Protection)

- All outbound fetches validate URLs against a blocklist of private/internal IP ranges (RFC 1918, CGN, link-local, loopback, IPv6 unique-local).
- DNS resolution results are checked before and after HTTP redirects.
- `resolve_and_pin()` provides DNS-rebinding-safe validation: resolved IPs are pinned so a second lookup cannot return a different (internal) address.

### Authentication

- WebUI auth uses a randomly generated bearer token validated with `hmac.compare_digest()` (constant-time) for both HTTP and Socket.IO authentication.
- The auth token is never included in file-serving URLs to prevent leakage via server logs or browser history.
- Socket.IO connections require authentication (not in the public path list).

### Channel Access Control

- Every channel enforces an `allow_from` whitelist. An empty list denies all access.
- The `ChannelManager` validates `allow_from` at startup and terminates if a configured channel still has an empty `allow_from`, forcing explicit access configuration.

### Rate Limiting

- The `MessageBus` supports optional per-sender rate limiting (`rate_limit_per_minute`). Disabled by default — enable it in config if exposed to untrusted users.

### Container Security

- **Base Image**: Uses `debian:bookworm-slim` via the Astral `uv` image.
- **Auto-Upgrade**: The `Dockerfile` includes an explicit `apt-get upgrade -y` step during build to ensure the latest security patches for system libraries (like `openssl` and `glibc`) are applied, regardless of the base image's refresh cycle.
- **Scanner Integration**: Official images are scanned on Docker Hub. High and Critical vulnerabilities in system packages are addressed via build-time upgrades or base image updates.

