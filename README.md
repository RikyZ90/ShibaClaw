<p align="center">
  <img src="assets/shibaclaw_logo_readme.jpg" width="800" alt="...">
</p>

# Smart. Loyal. Powerful. 🐕

<p align="center">
  <a href="https://github.com/RikyZ90/ShibaClaw/releases"><img src="https://img.shields.io/badge/version-v0.0.7-orange?style=flat-square" alt="version"></a>
  <img src="https://img.shields.io/badge/python-≥3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square" alt="license"></a>
</p>

ShibaClaw is a **loyal, intelligent, and lightweight** personal AI assistant framework — built to serve and protect your digital workspace.

The **only** AI agent framework combining **extreme multi-layer security** (Structural Tool Output Wrapping against Prompt Injection + Smart Install Guard with live CVE scanning before every package install) with **minimal token consumption**, keeping your costs low without sacrificing power.

---

## 📢 News

> [!IMPORTANT]
> **v0.0.7** is out! Massive core modernization: complete removal of `litellm` dependency for faster and strictly-controlled native LLM API integration.<br>
> Smart Install Guard — Package installations are no longer blindly blocked. Instead they are **intercepted and audited for CVEs** using 

- **2026-03-31** 🔍 **Smart Install Guard** — Package installations (`pip install`, `npm install`, `apt install`, ...) are no longer blindly blocked. Instead they are **intercepted and audited for CVEs** using `pip-audit` and `npm audit` before execution. Only packages with critical/high severity vulnerabilities are blocked; clean packages install freely. Destructive operations (`uninstall`, `remove`, `purge`) remain blocked.
- **2026-03-29** 🛡️ Security Hardening — Enhanced Indirect Prompt Injection protection via **Randomized Tool Output Wrapping** (using dynamic nonces per-session) to prevent instructions from untrusted data hijacking the agent.
- **2026-03-29** 🐾 LiteLLM Dependency Removed — Architecture modernized to utilize native SDKs (`openai`, `anthropic`), dramatically reducing docker image sizes, startup times, and opaque dependency risks.
- **2026-03-29** 🔐 GitHub Copilot OAuth rewritten using raw asynchronous device flow for highly stable background token refresh without proxy dependencies.
- **2026-03-29** 💬 Session UI Refactor — Removed nested channels grouping. Conversations are now displayed in a sleek chronological feed with a "Show more" history pane.
- **2026-03-29** 🎨 UI/UX Polish — Native browser popups (`alert`, `confirm`, `prompt`) entirely replaced with custom CSS modal dialogs (`shibaDialog`).
- **2026-03-29** 🛡️ WebUI Settings Fix — Solved a critical bug causing Config `_deep_merge` to overwrite legitimate API keys with `****` redacted strings under the hood.
- **2026-03-29** 🔐 Gateway restart hardening — blocked unauthorized `/restart` via health endpoint and enforced token-based auth for web UI/gateway restart.
- **2026-03-29** 🛡️ Shell tool security — expanded `ExecTool.deny_patterns` to include `$()`, backticks, shell pipes, curl/wget piped shell, and `<()>` process substitution.
- **2026-03-29** ⚡ WebSockets & Gateway Stability — Annihilated "Scrollbar Jittering" and implemented a cache-busting `Gateway health` polling mechanism
- **2026-03-26** 🧠 Dynamic System Prompt — runtime context (timestamp, channel, iteration) refreshed on every LLM call for a more "alive" agent
- **2026-03-26** 🐾 SOUL.md template refined — clean formatting and richer personality definition
- **2026-03-24** 🖥️ WebUI token authentication (Jupyter-style) — secure access with auto-generated tokens
- **2026-03-24** 🔐 OAuth login from UI — authenticate GitHub Copilot & OpenAI Codex directly from Settings
- **2026-03-24** 💬 Chat history rendering fixes and wider message layout
- **2026-03-22** 🧩 Settings modal with tabs — Agent, Provider, Tools, Gateway, Channels, OAuth
- **2026-03-21** ⚡ Real-time WebUI — Socket.IO streaming, process groups, typing indicator
- **2026-03-20** 🐾 Interactive onboard wizard — pick your provider, model autocomplete, and go
- **2026-03-19** 🛡️ Indirect Prompt Injection protection via Tool Output Wrapping

---

## 🐾 Key Features
- **Fast & Faithful**: Minimal startup time and dependencies.
- **Multi-channel**: Support for Telegram, Discord, Slack, WhatsApp, and more.
- **Always Alert**: Built-in cron and heartbeat task scheduler.
- 🧩 **Skills Registry**: Modular and extensible skill system with native ClawhHub marketplace support
- ⚡ **Parallel Multi-Agent Execution**: A built-in fan-out orchestration model that spawns and coordinates specialized sub-agents concurrently for faster, scalable task resolution
- **Advanced Thinking**: Support for OpenAI, Azure, LiteLLM, and deep-reasoning thinkers.
- **🛡️ Built-in Security**: Protected against Indirect Prompt Injection via **Structural Randomized Wrapping** and strict per-session security policies.
- **🔍 Smart Install Guard**: Package installs are audited for CVEs before execution — safe packages install freely, vulnerable ones are blocked with a full CVE report.

## 🔒 Loyal Only to You
Like the most devoted guard dog, ShibaClaw is trained to obey only its master. Thanks to its advanced **Tool Output Wrapping** system, the framework is hardened against *Indirect Prompt Injection* attacks. It treats external data from websites, files, or tools as literal information—never as new instructions. Your orders are final; to ShibaClaw, external noise is just a squirrel 🐿️.

## 🔍 Smart Install Guard

When the agent attempts to run a package installation command, ShibaClaw no longer blindly blocks it. Instead, it **intercepts the command, audits the packages for known vulnerabilities (CVEs), and only proceeds if the risk is acceptable**.

### How It Works

1. **Detect** — The `ExecTool` recognizes install commands for `pip`, `npm`, `yarn`, `pnpm`, `apt`, `dnf`/`yum`, and `brew`.
2. **Audit** — Before execution, the packages are scanned:
   - **Python (`pip install ...`)** → `pip-audit --format json` checks against the OSV/PyPA advisory database.
   - **Node.js (`npm install ...`)** → `npm audit --json` checks against the npm security advisory database.
   - **System packages (`apt`/`dnf`)** → Safety flags (e.g. `--allow-unauthenticated`, `--nogpgcheck`) are checked; repository-level security is assumed.
   - **Homebrew** → Allowed with medium confidence (curated formulae).
3. **Decide** — Based on the configured severity threshold:
   - `critical` or `high` vulnerabilities → **install is blocked** and the agent receives a full CVE report.
   - `medium` or `low` vulnerabilities → **install proceeds** with a warning appended to the output.
   - No vulnerabilities → **install proceeds** cleanly.
4. **Fallback** — If audit tools are unavailable (no internet, `pip-audit` not installed), the install is **allowed with a warning** rather than blocked.

> **Destructive operations** (`pip uninstall`, `npm remove`, `apt-get remove`, `apt-get purge`) remain unconditionally blocked.

### Configuration

In `config.json` under `tools.exec`:

```json
{
  "tools": {
    "exec": {
      "installAudit": true,
      "installAuditTimeout": 120,
      "installAuditBlockSeverity": "high"
    }
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `installAudit` | `true` | Enable/disable vulnerability scanning for installs |
| `installAuditTimeout` | `120` | Seconds to wait for audit tools before falling back |
| `installAuditBlockSeverity` | `"high"` | Minimum severity to block: `critical`, `high`, `medium`, `low` |

---

## 🐾 Quick Start

Ready to hunt? Choose your path:

### 🐋 Docker (Recommended)
```bash
docker compose up -d --build                                  # gateway + webUI
docker exec -it shibaclaw-gateway shibaclaw onboard --wizard  # first-time setup
```
Open **http://localhost:3000** — to get your access token, run `shibaclaw print-token` and paste it in the login screen or use the direct URL with the token appended.

### 🐍 Bare Metal
```bash
pip install .
shibaclaw onboard --wizard       # first-time setup
shibaclaw web --port 3000        # start the WebUI (agent runs in-process)
```

See the full [Easy Deploy Guide](./deploy_guide.md) for detailed instructions and troubleshooting.

## 🖥️ WebUI

<p align="center">
  <img src="assets/webui_welcome.png" width="380" alt="WebUI Welcome Screen">&nbsp;&nbsp;
  <img src="assets/webui_chat.png" width="380" alt="WebUI Chat with Agent">
</p>

### Features at a Glance

- **🔐 Token authentication** — auto-generated access token printed at startup (disable with `SHIBACLAW_AUTH=false`)
- **Multi-session chat** — create, rename, archive, and switch between conversations
- **Live process groups** — watch agent reasoning and tool calls stream in with elapsed time
- **Settings modal** — configure model, provider, API keys, tools, gateway, channels, and OAuth providers
- **OAuth login from UI** — authenticate GitHub Copilot and OpenAI Codex directly from the Settings panel
- **Context viewer** — inspect workspace context and token usage
- **Gateway monitor** — health check and one-click restart of the core AI engine
- **Typing indicator** — animated feedback while the agent is working
- **Responsive** — works on desktop and mobile

<p align="center">
  <img src="assets/webui_settings_oauth.png" width="380" alt="Settings — OAuth Providers">
</p>

### Architecture

| Layer | Stack |
|-------|-------|
| **Server** | Uvicorn → Starlette (ASGI) + python-socketio |
| **Real-time** | Socket.IO 4.7.5 (WebSocket, polling fallback) |
| **Frontend** | Vanilla JS · Marked.js · Highlight.js (github-dark) |

| Container | Command | Port | Role |
|-----------|---------|------|------|
| `shibaclaw-gateway` | `shibaclaw gateway` | 19999 | Core AI loop + message bus |
| `shibaclaw-web` | `shibaclaw web --port 3000` | 3000 | WebUI (Starlette + Socket.IO) |

Both containers share the `.shibaclaw/` volume for config, workspace, tools, and cache.

> **📝 Bare metal:** The WebUI works fully without Docker — the agent runs in-process. The only unavailable feature is the gateway health monitor, which requires the separate gateway container.

## 🧩 Supported Providers

ShibaClaw includes a unified provider registry and supports a wide range of LLM backends.

### 🔑 API key-based providers
- OpenAI (`OPENAI_API_KEY`)
- Anthropic (`ANTHROPIC_API_KEY`)
- DeepSeek (`DEEPSEEK_API_KEY`)
- Gemini (`GEMINI_API_KEY`)
- Zhipu AI (`ZAI_API_KEY`, `ZHIPUAI_API_KEY`)
- DashScope (`DASHSCOPE_API_KEY`)
- Moonshot (`MOONSHOT_API_KEY`, `MOONSHOT_API_BASE`)
- MiniMax (`MINIMAX_API_KEY`)
- Groq (`GROQ_API_KEY`)

### 🔗 Gateway providers (auto-detected by key prefix / api_base)
- OpenRouter (`OPENROUTER_API_KEY`, auto key prefix `sk-or-`, base `openrouter`)
- AiHubMix (`OPENAI_API_KEY`, base `aihubmix`)
- SiliconFlow (`OPENAI_API_KEY`, base `siliconflow`)
- VolcEngine / BytePlus / Coding Plans (`OPENAI_API_KEY` + URL matching)

### 🏠 Local providers
- vLLM / generic OpenAI-compatible local server (`HOSTED_VLLM_API_KEY`, `api_base` config)
- Ollama (`OLLAMA_API_KEY`, `http://localhost:11434` default)

### 🔐 OAuth providers
- OpenAI Codex (OAuth, `openai-codex`)
- GitHub Copilot (OAuth, `github-copilot`)

OAuth providers require a one-time login. Use the **Settings → OAuth Provider** tab in the WebUI to check status and authenticate directly from the browser. The GitHub Copilot flow uses device codes; OpenAI Codex opens a browser-based PKCE flow.

CLI fallback:
```bash
shibaclaw provider login openai-codex   # oauth-cli-kit device flow
shibaclaw provider login github-copilot # litellm device flow
```

Requirements: `pip install oauth-cli-kit` (Codex) · `pip install litellm` (Copilot)

### Useful commands
- `shibaclaw status onboard --wizard`
- `shibaclaw status` (check provider status and OAuth flags)
- `shibaclaw agent -m "Hello"`

Status:
- `shibaclaw status` will show `✓ (OAuth)` for authenticated OAuth providers.

## ✅ Check Status & Troubleshooting

- `shibaclaw status` reports workspace, config path, and provider status.
- `docker logs shibaclaw-gateway` / `docker logs shibaclaw-agent` for container logs.
- Refer to `shibaclaw/thinkers/registry.py` for provider list and prefixing behavior.

## 🏗️ Project Structure
- `shibaclaw/` - core implementation
  - `webui/` - web interface (server.py + static assets)
  - `agent/` - AI agent loop and brain
  - `thinkers/` - LLM provider registry
  - `cli/` - CLI commands
- `bridge/` - WhatsApp connectivity module
- `tests/` - verification and tests
- `assets/` - project branding and visuals

## Credits & Acknowledgements

This project was inspired by Nanobot❤️(https://github.com/HKUDS/nanobot)
by HKUDS, released under the MIT License.
