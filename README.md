<p align="center">
  <img src="assets/shibaclaw_logo_readme.jpg" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw 🐕</h1>
<h3 align="center">Security-first AI agent with built-in WebUI, native provider support, and hardened tools.</h3>

<p align="center">
  <a href="https://github.com/RikyZ90/ShibaClaw/releases"><img src="https://img.shields.io/badge/version-v0.0.28-orange?style=flat-square" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-≥3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://img.shields.io/badge/DeepWiki-docs-blue?style=flat-square&logo=gitbook&logoColor=white" alt="DeepWiki"></a>
</p>

---

ShibaClaw is a security-first AI agent that runs in your terminal or in a browser-based WebUI.
Instead of assuming the surrounding app will handle safety, it builds it into the core: install-time CVE auditing, randomized tool-output wrapping against prompt injection, SSRF and DNS rebinding protection, shell hardening, workspace sandboxing, and token auth.
You still get the practical pieces you need for daily use: WebUI & onboarding, 22 LLM providers, built-in file tools, long-term memory, 11 chat channels, cron, heartbeat, skills, and MCP support.

## Security, Built In

These are the defenses that are often left to app glue code or external proxies. In ShibaClaw they are part of the framework itself.

| Layer | Built in by default | Why it matters |
|---|---|---|
| Install-time audit | Audits `pip` and `npm` installs before execution; blocks critical/high CVEs | Catches risky dependencies before they land in the environment |
| Prompt-injection wrapping | Wraps every tool result in a randomized `<tool_output_...>` boundary and sanitizes closing tags | Untrusted pages and files stay data, not instructions |
| Shell hardening | 20+ deny patterns, escape normalization (`\x..`, `\u....`), internal URL detection | Blocks common destructive or obfuscated commands |
| Network guard | SSRF filtering, redirect revalidation, DNS-rebinding-safe resolution | Prevents web tools from pivoting into localhost or private networks |
| Workspace sandbox | File tools and the WebUI file browser stay inside the configured workspace | Reduces traversal and accidental host-wide access |
| Access control | Bearer token auth, constant-time token checks, channel allowlists, optional sender rate limiting | Safer when the agent is exposed beyond a local shell |

## Quick Start

### Docker

```bash
git clone https://github.com/RikyZ90/ShibaClaw.git && cd ShibaClaw
docker compose up -d --build
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Open **http://localhost:3000** — paste the token if auth is enabled, then complete the onboard wizard in the browser.

### pip

```bash
pip install shibaclaw
shibaclaw web --port 3000
```

Open **http://localhost:3000** and complete the onboard wizard.
Prefer the terminal? `shibaclaw onboard` runs the same guided setup from the CLI.

---

## WebUI

<p align="center">
  <img src="assets/settings.gif" width="420" alt="Settings">
  <img src="assets/webui_welcome.png" width="380" alt="WebUI Welcome Screen">&nbsp;&nbsp;
  <img src="assets/webui_chat.png" width="380" alt="WebUI Chat with Agent">
</p>

The WebUI is built-in — no separate frontend or Node.js required.

- **Chat** — multi-session conversations with live streaming of tool calls, thinking blocks, and elapsed time
- **Agent Profiles** — switch personas per session (Hacker, Builder, Planner, Reviewer) with dynamic avatars
- **File browser** — browse, view, and edit workspace files in-browser (sandboxed to workspace)
- **Voice** — speech-to-text via OpenAI-compatible audio APIs and browser-native TTS
- **Settings** — configure agent, provider, tools, MCP servers, channels, skills, and OAuth from a single panel
- **Onboard wizard** — guided first-time setup: pick a provider, enter API key or start OAuth, choose a model
- **Context viewer** — inspect the full system prompt and token usage breakdown
- **Gateway monitor** — health check and one-click restart
- **Auto-update** — checks GitHub releases every 12h, notifies in the UI and on all active channels
- **Responsive** — works on desktop and mobile

### Agent Profiles

<p align="center">
  <img src="assets/hacker-mode.gif" width="600" alt="Agent Profile Selector">
</p>

Switch the agent's personality on-the-fly without losing context. Each profile overrides the system prompt (SOUL.md) while keeping model, memory, and tools shared. Profiles are per-session — run a security audit in one tab and plan architecture in another.

**Built-in profiles:** Default · Builder · Planner · Reviewer · **Hacker** (elite security expert with 50+ tool recommendations, OWASP/MITRE/NIST methodologies, CVSS scoring, and a custom cyber-shiba avatar).

Create your own profiles interactively — the agent walks you through defining the persona and saves everything automatically.

---

## Features

### Memory & Workflow

- **Three-level memory** — `USER.md` (personal profile), `MEMORY.md` (operational facts), `HISTORY.md` (timestamped session archive with TF-IDF + recency search)
- **Proactive learning** — every N messages the agent silently consolidates new learnings into memory, without interrupting the conversation
- **Focused background delegation** — the `spawn` tool can offload a specific task and report back into the same session when done
- **Advanced reasoning** — supports extended thinking (Anthropic), reasoning effort (OpenAI o-series), and DeepSeek-R1 chains

### Tools

| Tool | What it does |
|------|-------------|
| `exec` | Shell commands with 20+ deny-pattern guards, encoding normalization, and CVE scanning |
| `read_file` / `write_file` / `edit_file` | Paginated reads, fuzzy find-and-replace, auto-created parent dirs |
| `web_search` | Brave, Tavily, SearXNG, Jina, or DuckDuckGo (fallback, no key needed) |
| `web_fetch` | HTTP fetch with SSRF protection, DNS rebinding defense, and redirect validation |
| `memory_search` | Ranked search over session history (TF-IDF + recency + importance scoring) |
| `message` | Cross-channel messaging with media attachments |
| `cron` | Schedule one-time or recurring jobs (cron expressions, intervals, ISO dates, timezone-aware) |
| `spawn` | Optional background worker for a focused task; reports back to the main session when done |
| MCP | Connect any MCP server (stdio, SSE, or streamable HTTP) — tools auto-registered as `mcp_<server>_<tool>` |

### Channels

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

All channels route through the same message bus. WhatsApp uses a Node.js bridge (Baileys) for QR-based linking.

### Skills

8 built-in skills (GitHub, weather, summarize, tmux, cron reference, memory guide, skill-creator, ClawHub browser). Skills are Markdown files with YAML frontmatter and optional scripts — create your own or install from [ClawHub](https://clawhub.ai/). Pin frequently-used skills to load them on every conversation.

### Automation

- **Cron service** — persistent, timezone-aware scheduled jobs stored in `jobs.json`. Supports `every`, `cron`, and `at` schedules. Overdue jobs fire on startup.
- **Heartbeat** — periodic wake-up reads `HEARTBEAT.md`, uses its frontmatter for interval/session/profile/targets, skips the LLM entirely when `Active Tasks` is empty, and only asks the model to decide when real active work exists.

If you are upgrading from an older release, it is recommended to reset your workspace `HEARTBEAT.md` once so you get the new frontmatter-based base template. Existing files still work, but they will not gain the new editable settings block automatically.

---

## Security Policy

The table above is the operational summary. The full disclosure process, supported versions, and defense-in-depth notes live in [SECURITY.md](./SECURITY.md).

---

## Supported Providers

ShibaClaw uses native SDKs (no LiteLLM proxy) and auto-detects the right provider from the model name.

### API Key

| Provider | Env Variable |
|----------|-------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Moonshot | `MOONSHOT_API_KEY` |
| MiniMax | `MINIMAX_API_KEY` |
| Zhipu AI | `ZAI_API_KEY` |
| DashScope | `DASHSCOPE_API_KEY` |

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — auto-detected by key prefix or `api_base`.

### Local

Ollama (`http://localhost:11434`) · vLLM · any OpenAI-compatible endpoint.

### OAuth

| Provider | Flow | Setup |
|----------|------|-------|
| GitHub Copilot | Device flow, auto token refresh | `shibaclaw provider login github-copilot` or WebUI Settings |
| OpenAI Codex | PKCE browser flow | `shibaclaw provider login openai-codex` or WebUI Settings |

---

## Architecture

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Service | Role | Default Port |
|---------|------|-------------|
| `shibaclaw-gateway` | Core agent loop, message bus, channel integrations | 19999 |
| `shibaclaw-web` | WebUI (Starlette + Socket.IO), cron service | 3000 |

Both share the `~/.shibaclaw/` volume (config, workspace, memory, cron jobs, media cache).

### Single-process mode

`shibaclaw web` runs agent + WebUI + cron in a single process — no gateway container needed.

### Stack

| Layer | Technology |
|-------|-----------|
| Server | Uvicorn → Starlette (ASGI) + python-socketio |
| Real-time | Socket.IO (WebSocket primary, polling fallback) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sessions | JSONL append-only per session (cache-friendly for LLM prompt prefixes) |

### Resource usage

| Component | RAM   |
|-----------|-----------|
| Gateway | < 200 MB |
| WebUI | < 200 MB |
| **Total (Docker)** | **< 400 MB** |

---

## CLI Reference

```bash
shibaclaw web               # Start WebUI (agent + cron in-process)
shibaclaw gateway            # Start gateway only (for Docker split)
shibaclaw onboard            # CLI-based first-time setup wizard
shibaclaw agent -m "Hello"   # One-shot message via terminal
shibaclaw agent              # Interactive REPL with history
shibaclaw status             # Provider, workspace, OAuth health check
shibaclaw print-token        # Show WebUI auth token
shibaclaw channels status    # List enabled channels
shibaclaw provider login <p> # OAuth login (github-copilot, openai-codex)
```

---

## Latest — v0.0.28

- **Heartbeat frontmatter config** — configure session, profile, interval, and output targets directly in `HEARTBEAT.md`
- **No-op heartbeat optimization** — no LLM call when `Active Tasks` is empty
- **Cron blank-job guard** — empty scheduled agent jobs are skipped instead of waking the model

→ [v0.0.28](./CHANGELOG.md): full details and upgrade notes, including the recommended `HEARTBEAT.md` reset

→ Full history in [CHANGELOG.md](./CHANGELOG.md)

---

## Troubleshooting

| Problem | Try |
|---------|-----|
| General status check | `shibaclaw status` |
| Container logs | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI won't connect | Check token with `shibaclaw print-token`, verify port binding |
| Provider errors | `shibaclaw status` shows API key and OAuth state |
| Security policy | [`SECURITY.md`](./SECURITY.md) |

---

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs welcome.

Channels are extensible via Python entry points (`shibaclaw.integrations`). Skill creation is documented in [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) and the built-in `skill-creator` skill.

---

## Credits

Inspired by [NanoBot](https://github.com/HKUDS/nanobot) by HKUDS — MIT License.

---

<p align="center">
  <b>If you like ShibaClaw and want to help it grow:</b><br>
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Drop a star</a> — 
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Open an issue</a> — 
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Send a PR</a> <br> contributions of any size are welcome
</p>