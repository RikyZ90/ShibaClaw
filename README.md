<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<h3 align="center">The AI agent that <b>runs reliably</b> — securely, privately, out of the box.</h3>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28 Providers · 11 Chat Channels · Built-in WebUI · Security-First Core · MCP Ready</b>
</p>

<h3 align="center">Built on three pillars: <b>Simplicity · Security · Privacy</b></h3>

<p align="center">
  🌐 <a href="./README.zh-CN.md">简体中文</a> &nbsp;·&nbsp;
  <a href="./README.es.md">Español</a> &nbsp;·&nbsp;
  <a href="./README.pt-BR.md">Português (BR)</a> &nbsp;·&nbsp;
  <a href="./README.ja.md">日本語</a> &nbsp;·&nbsp;
  <a href="./README.de.md">Deutsch</a> &nbsp;·&nbsp;
  <a href="./README.fr.md">Français</a>
</p>

***

> [!WARNING]
> If you experience login issues with the WebUI post v0.9.5 update, please run `shibaclaw reset-admin` in your terminal/console to restore access.

<details open>
<summary>📢 <b>Latest Release: v0.9.8</b> — Click to see what's new</summary>

### Added
- **Channel Config Dropdowns** — Changed `group_policy` fields in channel configuration to use dropdown selectors in the WebUI for better UX.

### Fixed
- **External Package Installation on Modern Linux (PEP 668)** — Auto-injects `--break-system-packages` on `externally-managed-environment` errors during pip operations.
- **Sub-agent Session Key Propagation** — Added `session_key` to sub-agent metadata for proper context during parallel execution.
- **RAG Soft Restart Import Error** — Fixed `NameError` for dynamic RAG imports during soft restarts when Local RAG plugin is installed.
- **Transient LLM Error Handling** — Added `'empty choices'` to transient error markers for automatic retry on empty API responses.
- **Channel Hot-Reload on Secret Updates** — Fixed channel hot-reload not triggering when secrets are updated.
- **Proactive Learning Tool Choice** — Gracefully handles unsupported `tool_choice` parameter in proactive learning.

### Changed
- **Removed Base64 Tool Output Encoding** — Eliminated Base64 encoding logic for tool outputs to simplify the pipeline.
- **Terminal Skeleton UI** — Refined terminal-style skeleton loader to be seamless and minimal.

### Documentation
- Improved Persian README localization and feature documentation.
- Fixed RTL issues in contribution guide and bullet points.

See the [Changelog](./CHANGELOG.md) for full release history.

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ Quick Start

### 🚀 Auto-Installer (Recommended)

The easiest way to get started. One command downloads the latest release, sets up shortcuts, and launches the UI.

**Bring your own model**: Seamlessly connect to local endpoints (Ollama, LM Studio) or use free API tiers via OpenRouter to start chatting at zero cost.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **Note**: On Windows, this downloads the pre-built desktop app from the latest GitHub Release — no Python required. Desktop and Start Menu shortcuts are created automatically, and the app appears in Apps & Features for clean uninstall. On Linux/macOS, the script installs via pip in an isolated virtual environment.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # pulls from Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Open **http://localhost:3000**, paste the token, and follow the onboard wizard.

Expose `shibaclaw-web` on your LAN (e.g. via reverse proxy) and open the same URL from your phone to chat with your agent on mobile.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # starts WebUI + agent engine on :3000
```

Open **http://localhost:3000** and follow the onboard wizard.
Prefer the CLI? `shibaclaw onboard` runs the same guided setup from the terminal.

***

## ✨ Everything in One Agent

<table>
<tr>
<td align="center" width="33%">

### 🛡️ Security-First
Encrypted vault, CVE audit,<br>prompt-injection wrap, SSRF guard

</td>
<td align="center" width="33%">

### 🧠 Smart Memory
3-level system with proactive<br>learning & auto-compaction

</td>
<td align="center" width="33%">

### 🌐 28 Providers
Native SDKs, no LiteLLM proxy<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Web & Mobile
Expose the WebUI on your LAN and<br>use the same agent from your phone

</td>
<td align="center" width="33%">

### 🖥️ Desktop App
Native Windows launcher with tray,<br>perfect combo with the WebUI

</td>
<td align="center" width="33%">

### 🔌 MCP Ready
Connect any MCP server,<br>tools auto-registered

</td>
</tr>
</table>

***

## Why ShibaClaw? Simply Works. 🐕

> **Tired of agents that need more hand-holding than your actual work?**
> ShibaClaw is engineered around one principle: <b>it runs reliably</b> — securely, reliably, and without constant maintenance.

Most AI agent frameworks treat security as an afterthought, leave you wrestling with provider compatibility, or force you to babysit configurations. ShibaClaw flips the script: security isn't bolted on, it's <b>the foundation</b>.

What makes ShibaClaw different:
- **Security layers built into the core** — CVE auditing at install time, prompt-injection wrapping on every tool result, SSRF/DNS-rebinding protection
- **Native provider support** — 28 providers via their official SDKs, no proxy layer to debug
- **One-command setup** — Docker or pip, follow the wizard, you're chatting in about a minute
- **Runs everywhere** — Terminal, WebUI, Discord, Telegram, WhatsApp, Windows desktop app, and more

***

## 🛡️ Security, Built In

Defenses that are normally scattered across app glue or external proxies — in ShibaClaw they ship in the core, <b>on by default</b>.

### Core Security Layers

| Layer | What it does |
|---|---|
| 🔍 Install-time audit | Audits `pip` and `npm` before execution — blocks critical/high CVEs before they land |
| 🛡️ Prompt-injection wrap & Pre-scan | Wraps every tool result in a randomized `<tool_output_...>` boundary. Applies regex pre-scanning for jailbreaks and **Base64 encoding** for untrusted payloads |
| 🔒 Shell hardening | 20+ deny patterns, escape normalization (`\x..`, `\u....`), internal URL detection |
| ⚡ Local-First Engine | Native Command Emulator (`ls`, `cat`) bypasses subprocess overhead; offline-first `tiktoken` fallback for air-gapped execution |
| 🌐 Network guard | SSRF filtering, redirect revalidation, DNS-rebinding-safe resolution |
| 📁 Workspace sandbox | File tools and file browser locked to the configured workspace |
| 🔑 Access control | Bearer token auth, constant-time checks, channel allowlists, optional rate limiting |
| 🧠 Distributed Engine | UI (~128 MB) decoupled from agent brain (~256 MB+) — minimal footprint per process |

### 🛡️ Prompt-Injection Wrapping (Tool Sandboxing)

Instead of simply feeding raw tool outputs back to the LLM, ShibaClaw wraps every tool result in a dynamically generated XML-like boundary with a <b>randomized nonce</b> (e.g., `<tool_output_a1b2c3d4>`).

> 💡 <b>Standalone Defense</b>: This core security mechanism (Randomized Tool Output Wrapping) has been decoupled and packaged as a standalone, zero-dependency Python library called [Muzzle](https://github.com/RikyZ90/Muzzle). You can use Muzzle to protect any agent framework (LangChain, LlamaIndex, CrewAI, AutoGen, or custom LLM loops) using this identical technique.

Why this matters: attackers often try to prematurely close tags or inject fake system instructions into tool outputs. The randomized boundary makes this statistically impossible — the agent only processes active directives.

***

## 🧠 Memory System

ShibaClaw implements a **three-tier memory architecture** that works together seamlessly:

### 1. Working Memory (Per-Session)
- Rolling conversation context with automatic summarization
- Token-aware window management with smart truncation
- Preserves critical information while discarding noise

### 2. Semantic Memory (Cross-Session)
- Persistent vector store using FAISS + sentence transformers
- Automatic fact extraction and embedding from conversations
- Semantic search across all historical interactions

### 3. Procedural Memory (Skills & Automations)
- Learned workflows saved as reusable skills
- Automation schedules with cron-like triggers
- Proactive learning from repeated patterns

### Key Features
- **Proactive Learning** — Agent automatically extracts and stores useful facts
- **Auto-Compaction** — Intelligent summarization prevents context overflow
- **O(1) History Append** — Optimized JSONL storage for fast session logging
- **Cross-Session Recall** — Access memories from any channel or session

***

## 🔌 MCP Ecosystem

ShibaClaw is fully compatible with the **Model Context Protocol (MCP)**, transforming the agent from a standalone tool into a plug-and-play AI hub.

Instead of relying solely on built-in skills, ShibaClaw can connect to any MCP-compliant server, instantly granting your agent access to a vast universe of external data sources and professional tools without modifying a single line of core code.

Why this matters:
- **Instant Extensibility**: Plug in community-made MCP servers for Google Drive, Slack, GitHub, PostgreSQL, and more.
- **Standardized Tooling**: Leverage a universal protocol for AI-to-tool communication, ensuring stability and interoperability.
- **Decoupled Architecture**: Keep your agent lean while scaling its capabilities through a distributed network of MCP servers.

Configure your MCP servers directly in the **Settings** panel to start expanding ShibaClaw's horizons.

### 🌐 Apps (Klavis Integration)

To make setting up popular SaaS tools (such as Gmail, Google Drive, Google Docs, Slack, GitHub, Outlook, etc.) as seamless as possible, ShibaClaw integrates with **Klavis** (`klavis.ai`).

Instead of forcing users to manually create individual developer credentials, configure OAuth consent screens, and set up redirect URLs for every single service on Google Cloud or Microsoft Azure console, ShibaClaw allows you to manage all of these integrations via a unified **Connected Apps** interface:

- **Single API Key**: Just grab a single API key from [klavis.ai](https://klavis.ai) and save it in the ShibaClaw Backend settings.
- **One-Click Connections**: Instantly connect or disconnect Gmail, Slack, and other services with a single click using secure OAuth login directly managed by the Klavis gateway.
- **Auto-Generated MCP Servers**: Once an app is connected, ShibaClaw automatically configures the appropriate MCP server with standard tools, registering them seamlessly into the active agent session.

***

## 🌐 Supported Providers

ShibaClaw uses native SDKs (no LiteLLM proxy) and resolves the active provider from the selected model or canonical provider-prefixed model ID. In the WebUI, all configured provider catalogs are merged into a single searchable list, while each session keeps its own chosen model.

### API Key

| Provider | Env Variable |
|----------|-------------|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` ¹ |
| Groq | `GROQ_API_KEY` |
| Moonshot | `MOONSHOT_API_KEY` |
| MiniMax | `MINIMAX_API_KEY` |
| Zhipu AI | `ZAI_API_KEY` |
| DashScope | `DASHSCOPE_API_KEY` |

¹ Setting `GEMINI_API_KEY` in the environment is sufficient — no stored key required. The Google OpenAI-compatible endpoint is pre-configured.

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — auto-detected by key prefix or `api_base`.

### Local

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · any OpenAI-compatible endpoint(`http://localhost:1234/v1`)

> **Note for Docker users:** If you run ShibaClaw via Docker Compose, `localhost` points inside the container itself. To connect to a local server running on your host machine (like LM Studio or Ollama on Windows/Mac), use:
> `http://host.docker.internal:1234/v1` (or `11434` for Ollama). On native Linux, use `http://172.17.0.1:port`.

### OAuth

| Provider | Flow | Setup |
|----------|------|-------|
| OpenRouter | PKCE browser flow, stores returned API key in provider config | WebUI Settings |
| GitHub Copilot | Device flow, auto token refresh | `shibaclaw provider login github-copilot` or WebUI Settings |
| OpenAI Codex | PKCE browser flow | `shibaclaw provider login openai-codex` or WebUI Settings |
| Google Gemini CLI | PKCE browser flow, requires `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` and `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET` env vars. **Note:** Unofficial third-party integration, Google may apply account restrictions. Use a separate account if this is a concern. | WebUI Settings |

For OpenRouter, the callback reuses the current WebUI URL and port by default, so `http://localhost:3000` is not a dedicated OAuth-only port. If you expose the WebUI behind a reverse proxy or need a different public callback origin, set `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` before starting the server.

### 💡 Pro Tip: Cost-Effective & Premium Models

ShibaClaw performs exceptionally well even without expensive API usage:
- **Free/Open Models:** We highly recommend using **OpenRouter** to access powerful free models like `nvidia/nemotron-3-super-120b-a12b:free` or `gemma-4-31b-it:free`.
- **Unlimited Premium:** If you use the **GitHub Copilot** OAuth integration, you gain access to premium models like `raptor` (`oswe-vscode-prime`) at zero additional cost, effectively giving you unlimited requests.

***

## 📊 How ShibaClaw Compares (Security-First)

> This table is a **rough, security-focused snapshot**, based only on what is explicitly documented in public repos/docs as of May 2026.
> `❓` means "not clearly documented / not checked", <b>not</b> "does not exist".

| Security Feature | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| Encrypted Credentials Vault (AES Fernet) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Install-time CVE auditing (pip, npm, apt) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Prompt-injection wrapping on every tool result | ✅ | ❌ | ❌ | ❌ | ❌ |
| SSRF + DNS-rebinding protection built-in | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClaw focuses on shipping these defenses in the core engine, on by default, so you do not have to glue together external scanners and proxies just to run an agent safely.

***

## 🏗️ Architecture

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Service | Role | Default Port |
|---------|------|--------------|
| `shibaclaw-gateway` | Core agent loop, message bus, channel integrations | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + native WebSocket), automations service | 3000 |

Both share the `~/.shibaclaw/` volume (config, workspace, memory, automation jobs, media cache).

### Single-Process Mode

`shibaclaw web` runs agent + WebUI + automations in a single process — no gateway container needed.

### Stack

| Layer | Technology |
|-------|-----------|
| Server | Uvicorn → Starlette (ASGI) |
| Real-time | Native WebSocket (`/ws` on WebUI, port `19998` on gateway) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sessions | JSONL append-only per session (cache-friendly for LLM prompt prefixes) |

### Resource Usage

| Component | Idle | Peak (install/compile) |
|-----------|------|------------------------|
| Gateway | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Compose sets a 512 MB limit / 256 MB reservation per container. Tool output is streamed with bounded buffers, so long-running commands (`apt`, `npm install`) can't blow up memory.

***

## 🔧 CLI Reference

```bash
shibaclaw web               # Start WebUI (agent + automations in-process)
shibaclaw gateway           # Start gateway only (for Docker split)
shibaclaw onboard           # CLI-based first-time setup wizard
shibaclaw agent -m "Hello"  # One-shot message via terminal
shibaclaw agent             # Interactive REPL with history
shibaclaw status            # Provider, workspace, OAuth health check
shibaclaw print-token       # Show WebUI auth token
shibaclaw channels status   # List enabled channels
shibaclaw provider login <p># OAuth login (github-copilot, openai-codex)
shibaclaw desktop           # Launch Windows desktop app
```

***

## 🔌 Channels (11 Integrations)

ShibaClaw connects to your favorite chat platforms out of the box:

| Channel | Type | Description |
|---------|------|-------------|
| **WebUI** | Built-in | Primary interface with full feature access |
| **Discord** | Bot | Rich embeds, slash commands, attachments |
| **Telegram** | Bot | Inline keyboards, media, reply markup |
| **WhatsApp** | Plugin | Via WhatsApp Web (plugin) |
| **Slack** | Bot | Block kit, threads, app mentions |
| **DingTalk** | Bot | Enterprise messaging |
| **Feishu/Lark** | Bot | Rich cards, interactive elements |
| **QQ** | Bot | Group & private messages |
| **WeCom** | Bot | Workplace communication |
| **Matrix** | Bot | Decentralized, E2E encryption |
| **MoChat** | Bot | WeChat ecosystem |

Channels are configured in the WebUI Settings panel. Each channel can be enabled/disabled independently and supports hot-reload on configuration changes.

***

## 🧩 Plugin System

ShibaClaw features a dynamic, installable plugin system for extending capabilities:

### Channel Plugins
Extend ShibaClaw to new chat platforms by implementing `BaseChannel`. Discoverable via `shibaclaw.integrations` entry point.

### TTS Plugins
Add custom text-to-speech engines by implementing `BaseTTS`. Discoverable via `shibaclaw.tts` entry point.

### Built-in Plugins
- **WhatsApp Channel** (`shibaclaw-channel-whatsapp`) — WhatsApp Web integration
- **Supertonic TTS** (`shibaclaw-tts-supertonic`) — Free, offline, ONNX-based speech synthesis (31 languages, custom voices)

### Plugin Management
- Install/uninstall plugins directly from WebUI Settings > Plugins
- Real-time hot-reload on install/uninstall (no restart needed)
- Version pinning and GitHub release installation support

See [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) for building custom plugins.

***

## 🎙️ Text-to-Speech (TTS)

### Supertonic (Built-in, Free & Offline)
- **31 Languages** — Broad multilingual support
- **Custom Voices** — `F1` (female) and `M1` (male) voice profiles
- **Adjustable Speed** — Control speech rate from the UI
- **ONNX Runtime** — Zero PyTorch dependency, runs on CPU
- **In-Browser Player** — Glassmorphic audio widget with seekable timeline

Enable in WebUI Settings > TTS, select voice and speed, and the agent will automatically synthesize voice responses.

***

## 🤖 Automation & Scheduling

Create background tasks that run on schedules or triggers:

- **Cron-like Scheduling** — Define recurring jobs with standard cron syntax
- **Event-Driven Triggers** — React to messages, webhooks, or system events
- **Isolated Execution** — Automations run in separate sessions to avoid polluting chat history
- **WebUI Management** — Create, edit, monitor, and view logs from the Automations panel
- **Persistence** — Jobs survive restarts via JSONL storage

***

## 📚 Knowledge Base (RAG)

Local, privacy-first Retrieval-Augmented Generation:

- **Collections** — Organize documents into named knowledge bases
- **Multi-Format Support** — PDF, CSV, HTML, TXT, Markdown
- **Drag-and-Drop Upload** — WebUI document management
- **Semantic Search** — FAISS vector index with `all-MiniLM-L6-v2` embeddings
- **Agent Tool** — `knowledge_search` tool for semantic queries during conversation
- **Explicit Mentions** — Use `@kb:name` in chat to target specific collections
- **Optional Dependency** — Install via `pip install shibaclaw[rag]` or WebUI plugin panel

***

## 🐛 Troubleshooting

| Problem | Try |
|---------|-----|
| General status check | `shibaclaw status` |
| Container logs | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI won't connect | Check token with `shibaclaw print-token`, verify port binding |
| Provider errors | `shibaclaw status` shows API key and OAuth state |
| Security policy | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs welcome.

Plugins (both channels and TTS engines) are extensible via Python entry points. See [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) for a comprehensive guide on building custom plugins. Skill creation is documented in [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) and the built-in `skill-creator` skill.

Gateway integrators: see [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) for the WebSocket contract on port `19998`.

***

## 🌟 Join the ShibaClaw Pack

ShibaClaw is built by one developer, maintained by the community, and growing fast.
If it saved you time, secured your workflow, or just made you smile — <b>leave a star</b> ⭐

> "The AI agent that runs reliably. No hand-holding required." 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Star the repo</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">Buy me a coffee</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Open an issue</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Send a PR</a>
</p>