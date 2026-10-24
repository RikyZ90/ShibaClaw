# ShibaClaw vs OpenClaw, nanobot, Hermes Agent and other self-hosted AI agents

**Last verified: 2026-10-24.** This is a requirements-based comparison of four self-hosted AI assistants, maintained in the ShibaClaw repository. It is not a ranking, benchmark, or independent security audit.

Names below refer specifically to [openclaw/openclaw][openclaw], [HKUDS/nanobot][nanobot], and [NousResearch/hermes-agent][hermes]. Other projects with similar names are outside this comparison.

## How to read this comparison

The tables describe capabilities documented in the source snapshots below. A feature in a development checkout may not yet be in a published release. “Unknown / not verified” means this review did not establish the capability; it does not mean the project lacks it. Examples of providers and channels are selective, not complete inventories.

| Project | Source snapshot inspected |
| --- | --- |
| ShibaClaw | Local source at [`68c58392`](https://github.com/RikyZ90/ShibaClaw/tree/68c58392eceda4a0f5d43556b96cb04cbdfa6679); implementation links below refer to files in this checkout |
| OpenClaw | [`99aed8a2`](https://github.com/openclaw/openclaw/tree/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626) |
| nanobot | [`3c022ada`](https://github.com/HKUDS/nanobot/tree/3c022ada6ac60f3a378aec583056b24e11188134) |
| Hermes Agent | [`5894e750`](https://github.com/NousResearch/hermes-agent/tree/5894e750c3dba980d43b25aa29e3958149ba2c61) |

## Deployment and interface

| Requirement | ShibaClaw | OpenClaw | nanobot | Hermes Agent |
| --- | --- | --- | --- | --- |
| Self-hosted runtime | Python application with CLI and integrated server. [Package](../pyproject.toml), [server](../shibaclaw/webui/server.py) | Gateway on your own computer/server. [Overview][openclaw] | Python agent and gateway for local/server use. [Overview][nanobot] | Local CLI/gateway; also supports remote execution backends. [Overview][hermes] |
| Built-in browser UI | WebUI for chat, settings, memory, MCP and automations. [Server and routes](../shibaclaw/webui/server.py) | Gateway serves the bundled Control UI. [Control UI][openclaw-ui] | WebUI ships in the published Python wheel. [WebUI][nanobot] | Built-in administration dashboard; official Desktop provides a separate chat interface. [Dashboard][hermes-dashboard], [Desktop][hermes-desktop] |
| Windows support | Per-user setup bundles Python and the desktop runtime; WebView2 is a prerequisite. [Windows installation](WINDOWS_INSTALLATION.md) | Native CLI/Gateway; Windows Hub uses an app-owned WSL Gateway for local setup; Tauri desktop is another option. [Windows][openclaw-windows] | PowerShell installer; native Windows x64 package includes WebUI and terminal UI. [Installation][nanobot] | Native PowerShell installation for CLI, gateway and terminal UI; Desktop also supports Windows. [Installation][hermes], [Desktop][hermes-desktop] |
| Docker deployment | Dockerfile and Compose configuration. [Compose](../docker-compose.yml) | Optional containerized Gateway and separate sandbox configuration. [Docker][openclaw-docker] | Documented Docker/Compose gateway deployment. [Deployment][nanobot-deployment] | Agent-in-Docker deployment and Docker as a terminal execution backend are separate options. [Docker][hermes-docker] |
| Graphical desktop app | Windows pywebview launcher with tray integration and managed updates. [Installation](WINDOWS_INSTALLATION.md), [desktop package](../shibaclaw/desktop) | Official native/companion apps; Windows Hub and Windows/Linux Tauri options are documented. [Overview][openclaw], [Windows][openclaw-windows] | Standalone graphical desktop app: **Unknown / not verified**. Bundled browser UI and native terminal UI are documented. [Interfaces][nanobot] | Official Desktop for macOS Apple Silicon, Windows and Linux. [Desktop][hermes-desktop] |
| Installation path to evaluate | Bundled Windows setup, Docker, or Python 3.12+ with pip. [Quick Start](../README.md#quick-start) | Installer provisions a supported Node.js runtime when needed; Docker is optional. [Installation][openclaw] | Installer, `uv` or pip; Python 3.11+. Source development also requires Git and Bun. [Installation][nanobot] | OS installer or Desktop download; Docker has its own setup. [Installation][hermes], [Desktop][hermes-desktop], [Docker][hermes-docker] |

Installation complexity depends on the selected route, model server, credentials and channels. No installation-time or resource-use measurements were performed for this document.

## Memory, tools and AI automation

| Requirement | ShibaClaw | OpenClaw | nanobot | Hermes Agent |
| --- | --- | --- | --- | --- |
| Persistent memory | Markdown profile, long-term notes, history and consolidation; ranked history search. Optional RAG knowledge collections are separate. [Memory](../shibaclaw/agent/memory.py), [search](../shibaclaw/agent/tools/memory_search.py), [knowledge](../shibaclaw/agent/knowledge_manager.py) | Workspace memory files with memory-plugin search; SQLite is the default search store. [Memory][openclaw-memory] | Session history and long-term memory consolidated through Dream. [Overview][nanobot] | Curated persistent memory/user profile files, session recall and reusable skills. [Memory][hermes-memory], [overview][hermes] |
| Sub-agents / multi-agent work | Background sub-agents with context modes and task verification support. [Sub-agent manager](../shibaclaw/agent/subagent.py) | Background sub-agent sessions and multi-agent routing/policy documentation. [Sub-agents][openclaw-subagents] | Multi-agent delegation and long-horizon goals are documented. [Overview][nanobot] | Isolated sub-agents for parallel work, with configurable routing and limits. [Overview][hermes] |
| Scheduled tasks / automations | Unified scheduled-job and heartbeat service with persisted jobs. [Automation service](../shibaclaw/automation/service.py) | Built-in persistent scheduler, external triggers and configurable result delivery. [Automations][openclaw-cron] | Scheduled automations with task/calendar management in WebUI. [Overview][nanobot] | Built-in cron scheduler with messaging-platform delivery. [Overview][hermes] |
| Model Context Protocol (MCP) | Client support for stdio, SSE and streamable HTTP tools, with WebUI management. [MCP tool connections](../shibaclaw/agent/tools/mcp.py), [routes](../shibaclaw/webui/routers/mcp_manager.py) | MCP server mode plus saved outbound MCP definitions for eligible agent runtimes; registry and runtime consumption are distinct. [MCP][openclaw-mcp] | MCP integrations and Apps management in the bundled WebUI. [Overview][nanobot] | Standard install supports local stdio and remote HTTP MCP servers, with tool filtering and OAuth setup. [MCP][hermes-mcp] |

## Models and integrations

| Requirement | ShibaClaw | OpenClaw | nanobot | Hermes Agent |
| --- | --- | --- | --- | --- |
| Local LLMs | Ollama, LM Studio and custom OpenAI-compatible endpoints. [Provider registry](../shibaclaw/thinkers/registry.py) | Hosted and local model providers. [Overview][openclaw] | Ollama and local OpenAI-compatible servers such as vLLM. [Providers][nanobot-providers] | Self-hosted endpoints including Ollama and vLLM. [Providers][hermes-providers] |
| Cloud models | Native provider adapters and gateways including OpenAI, Anthropic and OpenRouter. [Registry](../shibaclaw/thinkers/registry.py) | Model/provider plugins; hosted models supported. [Overview][openclaw] | Cloud-provider configuration and model presets. [Providers][nanobot-providers] | Nous Portal, OpenRouter, OpenAI and other configured providers/endpoints. [Providers][hermes-providers] |
| Chat channels | Examples: Telegram, Discord, Slack, Matrix and email; WhatsApp is a separate channel plugin. [Built-in integrations](../shibaclaw/integrations), [WhatsApp plugin](../plugins/shibaclaw-channel-whatsapp) | Examples: Discord, iMessage, Slack, Teams, Telegram and WhatsApp. [Overview][openclaw] | Examples: Telegram, Discord, Slack, WeChat, email, Mattermost and Linear. [Overview][nanobot] | Messaging gateway includes Telegram, Discord, Slack, WhatsApp, Signal, Matrix and email. [Gateway][hermes-messaging] |
| Model-provider OAuth / account sign-in | WebUI routes include OpenAI Codex, GitHub Copilot, OpenRouter and other configured flows. [OAuth routes](../shibaclaw/webui/routers/oauth.py) | Documented OpenAI Codex/ChatGPT OAuth and provider-specific account flows. [OAuth][openclaw-oauth] | Documented OpenAI Codex and GitHub Copilot sign-in, among other flows. [Providers][nanobot-providers] | Documented Nous Portal, OpenAI Codex, GitHub Copilot and other provider flows. [Providers][hermes-providers] |

Model-provider sign-in is different from connecting a SaaS app through MCP/OAuth. For ShibaClaw, [connected apps](../shibaclaw/webui/services/connected_apps_service.py) and [MCP OAuth configuration](../shibaclaw/config/schema.py) are separate from model-provider authentication. Account eligibility, limits, billing and provider policies must be checked for the chosen integration; OAuth support does not imply free or unlimited inference.

## Security controls and boundaries

These are examples of documented controls, not a completeness checklist or a claim that one project is safer than another:

- **ShibaClaw:** encrypted credential storage with OS-keyring preference and restricted-file fallback; WebUI authentication; URL/DNS checks for SSRF protection; shell command guards and install auditing; external-content marking. See the [credential manager](../shibaclaw/security/credential_manager.py), [WebUI auth](../shibaclaw/webui/auth.py), [network guard](../shibaclaw/security/network.py), [shell tool](../shibaclaw/agent/tools/shell.py), and [web tool](../shibaclaw/agent/tools/web.py). Command filtering and workspace checks should not be interpreted as an OS-level isolation guarantee.
- **OpenClaw:** Gateway authentication, channel pairing/allowlists, tool permissions, security auditing and configurable sandboxing are documented. Its README explicitly says main-session tools run on the host unless sandboxing is configured. See [security guidance][openclaw-security] and the [README security section][openclaw].
- **nanobot:** channel allowlists, environment-variable secret references, workspace restrictions and optional Linux bubblewrap/macOS Seatbelt exec sandboxing are documented. Its security policy explicitly identifies the absence of a Windows exec-sandbox backend. See [security policy][nanobot-security].
- **Hermes Agent:** command approvals and deny rules, messaging authorization and isolated execution backends are documented. Approval modes and execution backend affect the effective boundary. See [security guidance][hermes-security] and [Docker deployment][hermes-docker].

Self-hosting determines where the agent runs. Requests can still reach configured model providers, chat platforms and external tools; evaluate that data path for the deployment you choose.

## Which project should you evaluate?

Start with the interface, deployment and trust boundary you need, then test your actual model, channel and workflow:

- **ShibaClaw** is worth evaluating when you want an integrated Python agent/WebUI, a bundled Windows installer, memory, MCP, sub-agents and scheduling, with the credential and network controls described above. [Quick Start](../README.md#quick-start), [Windows setup](WINDOWS_INSTALLATION.md).
- **OpenClaw** documents a Gateway-centered assistant across messaging channels, native/companion apps and model/runtime plugins. [Project overview][openclaw].
- **nanobot** documents a Python personal-agent framework with a bundled browser/terminal workbench, SDK/API integration and scheduled workflows. [Project overview][nanobot].
- **Hermes Agent** emphasizes agent-curated memory, reusable/self-improving skills, sub-agent delegation and CLI/Desktop/messaging interfaces. [Project overview][hermes].

All four overlap substantially. A feature label alone does not establish equivalent behavior, isolation, reliability, model quality or maintenance cost. Before choosing, verify the exact released version and try one representative task, a cross-session memory check and a scheduled run with your configuration.

## Maintenance and scope

This review used current repository files and official documentation; it did not install competing agents, run live account integrations, test security bypasses, or benchmark latency, cost or resource use. Community interfaces are not counted as built-in interfaces. No other self-hosted AI agents were assessed here; add a project only with a named canonical repository, dated sources and the same verification standard.

When updating a cell, refresh its source and snapshot date together. Preserve “Unknown / not verified” where the available evidence is insufficient.

[Back to ShibaClaw](../README.md)

[openclaw]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/README.md
[openclaw-ui]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/web/control-ui.md
[openclaw-windows]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/platforms/windows.md
[openclaw-docker]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/install/docker.md
[openclaw-memory]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/concepts/memory.md
[openclaw-subagents]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/tools/subagents.md
[openclaw-cron]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/automation/cron-jobs.md
[openclaw-mcp]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/cli/mcp.md
[openclaw-oauth]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/concepts/oauth.md
[openclaw-security]: https://github.com/openclaw/openclaw/blob/99aed8a2d9fdeb06024c1a60d4d22569d1cb9626/docs/gateway/security/index.md
[nanobot]: https://github.com/HKUDS/nanobot/blob/3c022ada6ac60f3a378aec583056b24e11188134/README.md
[nanobot-deployment]: https://github.com/HKUDS/nanobot/blob/3c022ada6ac60f3a378aec583056b24e11188134/docs/deployment.md
[nanobot-providers]: https://github.com/HKUDS/nanobot/blob/3c022ada6ac60f3a378aec583056b24e11188134/docs/providers.md
[nanobot-security]: https://github.com/HKUDS/nanobot/blob/3c022ada6ac60f3a378aec583056b24e11188134/SECURITY.md
[hermes]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/README.md
[hermes-dashboard]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/features/web-dashboard.md
[hermes-desktop]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/desktop.md
[hermes-docker]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/docker.md
[hermes-memory]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/features/memory.md
[hermes-mcp]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/features/mcp.md
[hermes-providers]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/integrations/providers.md
[hermes-messaging]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/messaging/index.md
[hermes-security]: https://github.com/NousResearch/hermes-agent/blob/5894e750c3dba980d43b25aa29e3958149ba2c61/website/docs/user-guide/security.md
