## [0.8.5] - 2026-07-07

### Refactored
- **UI Architecture Split** — Decentralized the massive `ui_panels.js` God Object (3,400+ lines) into modular files (`settings_panel`, `update_panel`, `onboard_wizard`, `model_selector`, `auth_ui`, `plugins_panel`) to vastly improve Clean Code compliance and maintainability without introducing external build dependencies.
- **Event-Driven Modals** — Replaced fragile monkey-patching of `window.openModal` with a decoupled `shiba-modal-opened` VanillaJS CustomEvent mechanism.

### Fixed
- **Memory Leaks** — Resolved frontend memory leaks by adding a hard `MAX_POLLS` limit to OAuth polling flows and properly caching and clearing the gateway `setInterval` ID in `restartGateway()`.
- **Chat Scroll Hijacking** — Fixed a UI bug where `scrollToBottom()` would forcefully pull the user to the bottom of the page when actively scrolling up to read chat history.

### Optimized
- **Markdown Rendering** — Eliminated repeated `localStorage` read calls during rapid Markdown parsing operations by migrating to globally cached state variables.
- **Session Load Decomposition** — Decomposed the monolithic 250+ line `loadSession()` into four single-responsibility functions, improving stack trace clarity and parse execution speed.

## [0.8.3] - 2026-07-06

### Added
- **Agent Context Builder** — Implemented a new context builder and support infrastructure for enhanced agent runtime state management.

### Changed
- **Dependencies** — Bumped minimum dependency versions in `pyproject.toml` to the latest secure and stable versions across the environment.

### Fixed
- **TASK.md Comment Sanitization** — Resolved a CodeQL vulnerability (`js/incomplete-multi-character-sanitization`) by repeatedly stripping HTML comment tags from `TASK.md` parsing in a loop until none remain.
- **TASK.md Virtual Task Deletion** — Updated the WebUI task deletion logic to support all task heading variants (`## Task:`, `### Task:`, `## name`) case-insensitively, ensuring tasks are correctly removed from `TASK.md` when deleted from the UI.
- **Zip Slip & Path Traversal Mitigations** — Resolved a Zip Slip vulnerability in skill importing and path traversal risks in the plugin manager and updater version handling.
- **Config Load Optimization** — Eliminated redundant disk writes and onboarding scans by running plugin discovery once per process.
- **File Explorer Path Redaction** — Switched the explorer API to return relative paths instead of absolute local system paths, resolving information disclosure.
- **WebSocket Close Handling** — Wrapped early websocket closes in try-except blocks to prevent unhandled connection errors on drop.

## [0.8.2] - 2026-07-06

### Added
- **Task Automation Virtual Jobs** — Updated the WebUI Automation menu to automatically parse `TASK.md` and display "virtual jobs" for active tasks, allowing them to be quickly triggered or upgraded into independent automation routines.

### Fixed
- **Windows EXE Auto-Update** — Replaced `DETACHED_PROCESS` with `CREATE_NO_WINDOW` when launching the PowerShell auto-update script to prevent immediate crashes caused by invalid console handles upon parent exit.

### Changed
- **Connected Apps UX** — Moved the Connected Apps menu out of the Settings panel and into the main sidebar under Automation for faster access. The UI has been completely redesigned into a standalone, compact modal featuring a premium glassmorphic layout, animated hover effects, gradient backgrounds, and refined buttons.

## [0.8.1] - 2026-07-05

### Added
- **Klavis Strata Integration** — Integrated Klavis Strata support inside the connected apps dashboard, deferring the MCP sync until the user successfully completes the OAuth callback check rather than on setup start.

### Fixed
- **Session List Sorting** — Switched `list_sessions` to use the `.jsonl` session file modification time (`st_mtime`) for `updated_at` timestamps instead of metadata timestamps, ensuring recently modified sessions bubble to the top correctly.
- **Provider Key Persistence** — Fixed the Web UI settings panel to preserve provider API keys and custom API base URLs in `lastSettingsConfig` while expanding/collapsing accordion panels, avoiding data loss when saving settings.
- **Restart Console Descriptor Error** — Dropped `close_fds=True` from the Windows process spawning implementation when restarting the gateway to prevent bad file descriptor errors. Changed the restart thread to non-daemon (`daemon=False`).
- **Plugin Path Resolution** — Updated the `api_install_plugin` endpoint to resolve the target path under the `plugins/` subdirectory to match the reorganized repository structure.

### Optimized
- **Async & I/O Bottlenecks** — Offloaded synchronous SSRF DNS checks inside the MCP tool client to a separate execution thread to unblock the main event loop. Added an `st_mtime`-aware cache for `OAuthTokenStore` and a global cache for the Fernet encryption key to reduce CPU load and disk I/O overhead.
- **Concurrent Model Fetching** — Added a promise-based caching layer for settings model picker fetches (`_fetchingModelsPromise`) to prevent duplicate, concurrent API requests, resetting the cache only on settings mutations.
- **Gateway Shutdown Safety** — Added 5-second execution timeouts to both channel shutdowns (`channels.stop_all()`) and MCP clients closing (`agent.close_mcp()`) during gateway exit sequences.

## [0.8.0] - 2026-07-05

### Added
- **Connected Apps Interface** — Created a unified UI workflow to connect Gmail, Google Drive, Google Docs, Slack, GitHub, Outlook and other SaaS apps using **Klavis** (`klavis.ai`).
- **OAuth Path CSRF Protection** — Added unique runtime token validation to the local callback receiver endpoint (`/callback/{token}`) to secure OAuth authentication flows.

### Fixed
- **MCP Worker Race Condition** — Added locking mechanism to serialize parallel connection handshakes and reconnect sequences, preventing race conditions on the global session registry.
- **SSE Transport Fault Tolerance** — Handled background stream closures and Anyio transport errors gracefully, auto-triggering background reconnects instead of crashing task groups.
- **Anyio Stream Compatibility** — Satisfied structural isinstance checks in the ClientSession reader loop by subclassing the SSE stream wrapper from `anyio.abc.ObjectReceiveStream`.
- **Asyncio Lock Loop Binding** — Switched the MCP manager lock to lazy initialization to ensure it binds to the running gateway event loop rather than module import time.

### Changed
- **Config Reconnection Optimization** — Filtered MCP configurations so that reconfigure calls only trigger reconnections if connection-affecting fields (`type`, `command`, `args`, `env`, `url`, `headers`, `oauth`) have actually changed.
- **Frontend Fetch Migration** — Ported all Connected Apps fetch requests in `connected_apps.js` to use the global `authFetch` wrapper for proper authentication and session handling.
- **Polling Cancellation** — Introduced frontend `AbortController` cancellation to immediately terminate active status checks when connection modals are dismissed.

## [0.7.9] - 2026-07-04

### Added
- **MCP Server Manager** — Added a dedicated WebUI workflow to create, edit, test, and monitor MCP servers, including environment variable support and live connection status badges.
- **OAuth 2.0 PKCE for MCP** — Added secure OAuth-based authentication for custom MCP HTTP endpoints through a local callback flow.
- **CLI & System Routing Improvements** — Expanded the CLI command structure and added gateway/WebUI detection utilities for smoother startup and routing.

### Changed
- **MCP Tool Guidance** — Improved MCP tool usage instructions and JSON parameter casting for more reliable server tool execution.
- **Accessibility Polish** — Associated labels with inputs in settings and automation dialogs for better screen-reader support.

### Fixed
- **DingTalk SSRF Protection** — Hardened outbound URL validation in the DingTalk integration to block unsafe redirects.
- **Proxy Loader Resilience** — Fixed handling of empty proxy objects in configuration loading.

### Optimized
- **Automation Task Resolution** — Reduced the computational cost of heartbeat task evaluation for faster background processing.

## [0.7.8] - 2026-07-03

### Added
- **NVIDIA Provider Support** — Added NVIDIA as a supported LLM provider, expanding available model options.

### Fixed
- **Updater Relaunch Reliability** — Improved Windows updater install directory detection and relaunch handling so EXE updates recover more reliably after installation.

## [0.7.7] - 2026-07-03

### Fixed
- **Sentinel SSRF Protection** — Fixed server-side request forgery in `web_fetch` and `mcp` tool redirect handling by validating every resolved outbound URL before execution.

### Changed
- **Palette Accessibility** — Added ARIA labels and titles to icon-only buttons to improve screen reader support and accessible interaction.
- **SOUL Template Update** — Updated the `shibaclaw/templates/SOUL.md` system prompt template to reflect the latest guidance and persona behavior.

### Optimized
- **Cache System Helpers** — Improved cache system helper performance to speed up repeated system lookups and reduce response latency.

## [0.7.6] - 2026-06-28

### Fixed
- **Windows Updater Safety & UI Progress** — Hardened the Windows update mechanism against process lock race conditions and destructive folder deletions, forced TLS 1.2+ compatibility, and enabled real-time update download progress bars in the WebUI.

## [0.7.5] - 2026-06-27

### Changed
- **WhatsApp Integration** — Decoupled the WhatsApp channel from the core framework and moved it to a separate, installable plugin (`shibaclaw-channel-whatsapp`) to reduce core dependencies and allow independent updates.

## [0.7.4] - 2026-06-23

### Added
- **Agent Steering Mode** — Added capability to guide or steer the agent dynamically during its execution loop. The WebUI no longer blocks user input when the agent is processing; instead, sending a message will inject it directly into the current execution loop's context at the start of the next LLM iteration.
- **Steering Icon and Tooltip** — Adapted the WebUI send button icon to a navigation pointer (`navigation`) and updated the tooltip to "Steer the agent" when processing, showing visual feedback of the active steering state.
- **MCP Lazy Tool Loading** — Optimized MCP server connections to use a lazy loading/discovery strategy. Instead of registering every single tool natively, the agent registers generic `mcp_list_tools` and `mcp_call_tool` helpers and lists active servers in the system prompt, dramatically reducing token context overhead.

### Fixed
- **Authorized File Access Endpoint** — Hardened `/api/file-get` in `fs.py` by requiring either standard `Authorization` Bearer token headers or a `?token=` query parameter fallback.
- **WebUI Token-based Media Rendering** — Updated `chat.js` and `ui_panels.js` to route all image, audio, and attachment links through an `authUrl` query parameter helper, preventing unauthorized file disclosure.
- **Multi-Tab Session Queueing** — Resolved queue starvation in multi-tab configurations by unifying connection-level message queues under a single global `_session_queues` structure mapped by `session_key`.

### Optimized
- **Skills Metadata Cache** — Added an `st_mtime`-aware class-level metadata cache to `SkillsLoader` in `skills.py` to prevent reading and parsing YAML frontmatter from disk repeatedly.
- **Dependency Security Patches** — Upgraded `msgpack` to `>=1.2.1`, `pydantic-settings` to `>=2.14.2`, and `starlette` to `>=1.3.1` to resolve known CVE vulnerabilities.

## [0.7.3] - 2026-06-21

### Added
- **PowerShell Installer Parameters** — Added support for optional `-Version` and `-InstallDir` parameters in the PowerShell installation script `install.ps1`.
- **Packaged Installer Script** — Added `install.ps1` to the bundled PyInstaller package for local execution fallback.

### Fixed
- **Windows EXE Automatic Updates** — Transitioned `apply.py` to execute the official `install.ps1` installer in a detached background process for EXE updates, rather than manually extracting zip files and writing batch files.
- **Windows Process Lock Handling** — Handled locked executables in `install.ps1` by checking and waiting up to 30 seconds for any running `ShibaClaw` processes to exit, force-terminating them as a fallback.
- **Plugin Installation on Packaged EXE** — Prevented dynamic pip-based plugin installations and uninstallations in `plugins.py` when running from a packaged EXE, returning a clean error instead of failing.
- **Duplicate Desktop GUI Spawns** — Configured `__main__.py` to block launching python modules (e.g. `-m pip`) when compiled by PyInstaller, printing a stderr message and exiting instead of spawning duplicate GUI windows.
- **Desktop pywebview Freeze on Gateway Restart** — Resolved window freeze on plugin install/uninstall by waiting for the gateway to report a fully ready `"ok"` status before reloading the page, retrying configured port binding to prevent falling back to random ports, and thread-safely reconnecting the WebSocket gateway client.

### Changed
- **Provider Settings Panel Restyling** — Redesigned the Provider settings accordion list into a highly compact, responsive card grid supporting up to a 5-column layout on larger viewports. Improved the visual hierarchy by scaling down the icons, text labels, and card padding, and added keyword-based real-time filtering and inline expands.
- **Channels Settings Split Pane** — Transformed the Channels accordion list into a split-pane layout with a vertical list on the left and a dedicated configuration form on the right. Scoped settings state propagation to prevent duplicates during saves.

### Fixed
- **Plugins Tab Cleanup** — Updated the `/api/plugins` endpoint to exclude built-in channel integrations (e.g. WhatsApp, Telegram, Discord) from the "Installed Plugins" list, ensuring only actual external/installable plugins (like Supertonic TTS) are listed.
- **Plugin Installation Fallback** — Resolved local plugin path installation issues by resolving package names to absolute directory paths locally, and added a fallback to official GitHub repository subdirectories for remote users who don't have a local checkout.

### Added
- **Plugin Development Guide** — Added a comprehensive plugin development guide explaining how to develop both custom Channels and TTS engines for ShibaClaw, and linked it in the README.

## [0.7.0] - 2026-06-21

### Fixed
- **Memory Leak in Image Cache** — Capped the `ScentBuilder` image cache at a maximum of 32 images with FIFO eviction logic, preventing memory exhaustion (OOM) during long chat sessions with multiple image uploads.
- **Telegram Memory Leaks** — Enforced strict FIFO limits on Telegram integration dictionaries (`_chat_ids` capped at 500, `_message_threads` capped at 1000) to ensure bounded memory usage in active or high-traffic group channels.
- **WebUI Multi-Tab Race Condition** — Fixed a race condition where multiple open tabs of the same WebUI session could trigger parallel execution of the same message stream. The WebUI now uses a global `processing_state` dictionary keyed by the shared `session_key` to properly queue concurrent messages.
- **HTTP Fallback Status Verification** — Hardened the raw socket HTTP fallback client (`gateway_client.py`) by explicitly splitting and checking the status line for `b" 200 "`, avoiding false-positive successful responses when a 500 error body contained the string "200".
- **Windows EXE Updater Status UX** — Fixed a bug where Windows `.exe` updates were shown as failed (red icon) in the WebUI because success and output checks only evaluated `report.pip` instead of `report.exe`.
- **Windows Updater Process Lock** — Replaced `timeout` waits in the Windows self-replacing updater batch script with standard `ping` delays, preventing the update script from failing immediately when executed in non-interactive or detached shell environments.

### Optimized
- **Updater Network Performance** — Shifted the `httpx.Client` instantiation outside of the retry loop in the update checker (`checker.py`), enabling connection reuse and eliminating redundant DNS resolution and TLS handshakes during network retries.
- **Message Sanitization Speed** — Added a fast-path early return in `_sanitize_empty_content` during assistant context assembly to avoid shallow-copying messages that do not require sanitization or stripping of `_meta` fields.
- **Code Cleanups** — Removed redundant queue allocation in `_handle_stream` and cleaned up unused session retrieval code in `ws_handler.py`.

### Changed
- **Settings Menu Redesign & Premium UX** — Transformed the Settings interface into a dedicated, clean full-screen layout with vertical sidebar navigation, cohesive tab panels, and a mobile-optimized category dashboard.
- **Uninstaller Relocation & Lock-Free Execution** — Relocated `uninstall.ps1` from the `.shibaclaw` root to the `app\ShibaClaw\` directory next to `ShibaClaw.exe` to keep the root directory clean. The uninstaller now copies itself to the Windows `Temp` directory and delegates execution to that copy, allowing clean deletion of the `app` folder while preserving user files in the `.shibaclaw` root.

### Added
- **Automated Test Coverage** — Implemented a comprehensive suite of non-regression test cases verifying the bounded cache limits, the multi-tab websocket queueing, HTTP status parsing accuracy, and connection pool reuse.

## [0.6.6] - 2026-06-20

### Fixed
- **Native Windows Taskbar Icon** — Fixed an issue where the packaged Windows `.exe` displayed the generic Python icon in the taskbar instead of the ShibaClaw icon. The application now correctly bypasses explicitly setting `AppUserModelID` when running as a frozen executable to naturally group tasks and use the embedded `.exe` icon, and the `.NET` fallback dependencies (`clr`, `pythonnet`) have been explicitly added to the PyInstaller build to ensure pywebview host windows render the icon properly.
- **WebUI Update Progress Timeout** — Handled network errors and timeouts during long update operations (like pip dependencies installation) by showing an "Update in Progress" background state instead of a hard failure in the UI.
- **Windows EXE Update Installer Detection** — Fixed a bug where custom-packaged `ShibaClaw.exe` launchers were incorrectly identified as `pip` installations due to missing `sys.frozen` markers, which caused updates to restart only the gateway instead of triggering the native `.exe` self-replacing updater and shutting down the main app.

## [0.6.4] - 2026-06-16

### Changed
- **Default Dependencies** — Moved Telegram integration dependencies (`python-telegram-bot` and `python-socks`) to the default dependencies list to ensure the channel works out-of-the-box on all standard installations (such as default `pipx` or `pip` without extras).

## [0.6.3] - 2026-06-16

### Fixed
- **Telegram Auth & Security Check** — Moved authorization verification to occur *before* media downloads, preventing unauthorized users from triggering resource-heavy file downloads.
- **Telegram URL Escaping** — Resolved an issue where ampersands (`&`) in URLs were corrupted during Markdown-to-HTML conversion.
- **Telegram Edited Messages** — Added support for receiving and correctly handling `edited_message` updates from Telegram.
- **Telegram Memory Optimization** — Implemented strict FIFO caps and eviction logic for `_progress_messages` and cleaned up `_message_threads` to prevent slow memory leaks over time.
- **Telegram Media Group Auth** — Fixed media group buffering to ensure authorization checks are fully respected before processing group media.
- **CLI Channel Dependencies** — Improved the `channels status` CLI command to explicitly report missing optional dependencies for channels instead of silently marking them as broken or disabled.

## [0.6.2] - 2026-06-11

### Added
- **Configurable Agent Runtime Timeouts** — Made agent loop, tool, and subagent timeouts fully configurable under Settings -> Agent in the WebUI.
- **Granular Request Cancellation** — Added support for canceling individual active requests/streams via WebSocket request ID without affecting the rest of the session.

### Fixed
- **Timeout Messages** — Improved warning/error messages to display elapsed execution times and maximum allowed cap times.
- **Baileys Vulnerability Fix** — Patched message spoofing and app state corruption vulnerabilities (CVE-2026-48063) in the WhatsApp bridge by upgrading `@whiskeysockets/baileys` to `7.0.0-rc13` and adding input validation to drop spoofed `messages.upsert` events.

## [0.6.1] - 2026-06-05

### Fixed
- **Security Update** — Updated `starlette` to v1.2.1 to resolve a known vulnerability.

## [0.6.0] - 2026-06-02

### Added
- **Major Version Update** — Updated to version 0.6.0 with enhanced features and improvements.

## [0.5.8] - 2026-06-02

### Fixed
- **Windows CMD/PowerShell Window** — Fixed an issue where the background gateway console window remained open when launching ShibaClaw via the desktop shortcut by running the subprocess with `CREATE_NO_WINDOW`.
- **Native Windows Taskbar Icon** — Fixed a bug where the custom application icon was missing in the Windows taskbar for the desktop pywebview UI by explicitly setting the window icon when the page is fully loaded.
- **WebUI Pip Update Process & Spinner** — Fixed false-positive update timeout errors during slow pip installations by increasing the command timeout to 600 seconds and implementing an indeterminate progress spinner/loading bar to indicate background progress.

## [0.5.7] - 2026-06-02

### Fixed
- **Windows Install Icons** — Fixed an issue where the native Windows desktop and tray icons were missing during fresh installations by packaging the `assets` folder directly into the pip wheel and downloading the shortcut icon dynamically in the install script.
- **Install Logs UI** — Resolved encoding issues in the PowerShell installation script (`????`) and replaced generic logging emojis with a custom, Shiba-themed progress logging experience.

## [0.5.6] - 2026-06-02### Added
- **New One-Line Script Installers** — Introduced new automated installer scripts (`install.ps1` for Windows, `install.sh` for macOS/Linux) that set up ShibaClaw in a clean virtual environment using pip/pipx, with support for automatically creating desktop and start menu shortcuts.
- **Pip Update Cache Invalidation** — Added direct cache invalidation inside the updater after a successful pip/pipx upgrade to ensure the UI immediately reflects the update.

### Fixed
- **Windows Update Process Lock & Duplicate Processes** — Hardened the update restart sequence. Implemented graceful Uvicorn server shutdown to release TCP ports before spawning the new process, preventing duplicate processes or failed port bindings post-update.
- **Mobile UI Polish** — Fixed styling/rendering issues for chat bubbles and tables on mobile screens to improve readability and layout responsiveness.

## [0.5.5] - 2026-06-01

### Fixed
- **Automation Notifications** — Fixed a bug where completion notifications for scheduled jobs and cron tasks were not reaching the WebUI by implementing a dedicated delivery bridge in the gateway.
- **Automation / Heartbeat duplicate executions** — Prevented the global 30-minute heartbeat from re-executing tasks already managed by scheduled automations. Managed `TASK.md` sections are now ignored by the generic heartbeat resolver, and scheduled jobs are no longer mirrored back into `TASK.md` from the WebUI, so disabled or already-completed jobs are not triggered again unintentionally.
- **Tests** — Added regression coverage for global heartbeat filtering of automation-managed task sections and for named heartbeat jobs keeping their exact `TASK.md` section.

### Optimized
- **WebUI WebSocket Fan-out** — Optimized session message delivery from $O(N)$ to $O(1)$ using a subscriber index (`_session_subscribers`) and `collections.deque` for message queues.
- **Gateway Backpressure** — Decoupled event handlers into separate tasks and implemented bounded stream queues in `gateway_client.py` to prevent head-of-line blocking.
- **Automation I/O Reduction** — Implemented `TASK.md` parsing cache and debounced/batched persistence in `automation/service.py` to reduce disk writes.
- **HTTP Client Reuse** — Implemented `httpx.AsyncClient` reuse in `agent/tools/web.py` to eliminate repeated TCP/TLS handshakes.
- **Token Estimation Cache** — Refined cache invalidation logic in `agent/memory.py` for more efficient prompt token estimation.
- **Multimodal Encoding Cache** — Added an LRU cache for base64 image encoding in `agent/context.py` to reduce RAM spikes during prompt assembly.
- **Session Persistence** — Optimized session saving in `brain/manager.py` to use append-only writes for messages, avoiding full-file rewrites.

### Removed
- **Obsolete Code** — Deleted `shibaclaw/webui/socket_io.py` as it was superseded by the new WebSocket architecture.

## [0.5.4] - 2026-05-30

### Fixed
- **Automation — schedule kind inference** — When deserialising jobs the schedule `kind` is now inferred correctly from the stored fields (`expr`, `everyMs`, `atMs`) instead of defaulting to `every`, preventing cron jobs from being treated as intervals.
- **Automation — atomic & async-safe persistence** — Hardened automation persistence: writes are now atomic (temporary file + replace) and async-safe (`_save()` wraps I/O in the event loop executor and serialises saves), eliminating race conditions when multiple jobs save concurrently.
- **Automation — force-run behaviour** — Running one-shot `at` jobs with `force=True` now consistently clears `next_run_at_ms` and disables the job when appropriate, avoiding accidental re-scheduling of one-shot jobs.
- **Migration & startup** — Legacy job migration and overdue `at` job firing are now robust to missing/invalid schedule kinds, and startup execution of overdue jobs is deterministic and single-shot.
- **Tests** — Added and updated focused tests to cover legacy migration and overdue `at` job behaviour.

## [0.5.3] - 2026-05-29

### Fixed
- **Mobile Web UI — chat & input polish** — Fixed several mobile layout issues: chat bubbles now expand to a sensible width on small screens, inline Markdown tables are horizontally scrollable to avoid overflow, and the message input honors a new per-user mobile setting that allows Enter to insert a newline instead of sending the message.
- **Settings layout** — Aligned settings toggles and descriptions in the settings modal for consistent spacing and typography on mobile and desktop.

## [0.5.2] - 2026-05-28

### Added
- **Unified Automation Engine & UI** — Completely refactored the previously disjointed "Cron" and "Heartbeat" systems into a single, unified "Automations" engine. Automations now feature a dedicated, premium modal in the WebUI where users can intuitively create, toggle, and delete background tasks (both interval-based heartbeats and cron-scheduled jobs) from one centralized control center.
- **Automation Background Telemetry** — The WebUI now actively polls the status of background automation jobs during its health checks. When any automated job (cron, interval) executes silently in the background, the global status indicator intelligently switches to a pulsing gold "Executing..." badge, providing clear real-time visibility into agent background activity.
- **Modern Workspace Summary Widget** — Replaced the text-heavy workspace summary with a sleek, glassmorphic widget anchored at the bottom of the sidebar. It cleanly displays Active Channels (e.g. `WebUI`, `Telegram`), the Configured Provider, and a strict "Restrict WP" toggle status, leveraging unified `status-dot` styling.
- **Native TASK.md File Syncing** — The WebUI automation panel now reads, parses, and rewrites the `TASK.md` file natively via direct filesystem APIs (`fs_read`/`fs_write`). This eliminates reliance on error-prone LLM payload injection, guaranteeing that tasks are perfectly synchronized when jobs are toggled or deleted from the UI.

### Changed
- **Unified Workspace Tasks** — Removed the legacy `HEARTBEAT.md` file entirely. The system now exclusively uses `TASK.md` as the single source of truth for both background routines and automation payloads, reducing workspace clutter and standardizing how the agent interacts with its directives.

### Fixed
- **Boot Storm Prevention (Catch-up Execution)** — Fixed a major issue where the gateway would simultaneously execute all missed recurring jobs (cron/interval) upon startup after a period of downtime. The automation engine now implements a "fast-forward" mechanism on boot, silently advancing missed schedules to their *next* natural occurrence to prevent instant execution storms.
- **REST Method Overlapping** — Fixed a routing bug in `utils.py` where the API dispatcher incorrectly intercepted `DELETE` requests intended for `/api/automation/jobs`, treating them as `GET` requests and failing to delete tasks.
- **UI Text Truncation** — Fixed an overflow issue where the "Executing task..." status text was crashing into the borders of the `.status-micro` container by adopting the punchier and perfectly sized "Executing..." label.
- **Automation State Persistence** — Added the `running` state flag to the automation service core (`service.py`). The engine now correctly broadcasts when it begins executing a job, whereas previously it only reported terminal states (`ok` or `error`), leaving the frontend blind during execution.

## [0.4.6] - 2026-05-21
### Fixed
- **Windows Updater Process Lock** — Hardened the update installer batch script by explicitly killing all gateway child processes immediately prior to `xcopy`, rather than waiting up to 5 seconds for a graceful shutdown. This prevents the update script from copying files while they are still locked by the OS.
- **Update Cache Invalidation** — The update checker's local cache is now forcefully invalidated upon successfully applying an update. This ensures the UI correctly reflects that the latest version has been installed immediately upon restarting.
- **Hardened Update Batch Script** — Increased the timeout window of the Windows self-replacing updater from 3s to 8s, added the `/I` flag to `xcopy` to ensure proper directory treatment, and appended `>nul 2>&1` to suppress noisy shell output during detached execution.

## [0.4.5] - 2026-05-21
- **API Reference Documentation** — Completely overhauled `API_REFERENCE.md` to match the current WebUI behavior. Documented missing REST endpoints (e.g., `/api/models`, `/api/v1/notifications`, OAuth callbacks) and modernized the WebSocket specification to correctly reflect the `"type"`-based payload structure and missing server events. @dercar2

## [0.4.4] - 2026-05-19

### Added
- **Premium Update Progress UI** — Designed a stunning, glassmorphic download progress card in the WebUI with gold-gradient bars and pulsing animation for clear visual feedback.
- **Progress Persistence** — Prevented settings modal or tab switching from interrupting or resetting the active download progress display.

### Optimized
- **Context Bloat Mitigation** — Added smart truncation for past tool outputs within the conversation history, dramatically reducing token usage and preventing context window exhaustion during extended sessions.
  - Introduced `_HISTORY_TOOL_MAX_CHARS` (capped at 1500 characters) to `ScentBuilder` in `context.py`.
  - Tool outputs from past conversation turns are now automatically truncated to 1500 characters when constructing LLM prompts.
  - Active turn tool outputs remain fully available (up to the 8000 character limit) during active reasoning.
  - The complete raw outputs are preserved intact in session databases, ensuring the WebUI still renders full transcripts without data loss.

### Fixed
- **Windows EXE Updater Process Lock** — Hardened self-replacing update execution on Windows by cleanly terminating the background gateway child process prior to restarting.
- **Hardened Update Installer Script** — Refactored the update batch script to write/execute from `%TEMP%` to avoid directory locks, added robust xcopy write-retry loops up to 15 times, and configured self-deletion after successful installation.
- **WebView2 WebUI Cache Busting** — Implemented no-cache headers (`Cache-Control: no-cache, no-store, must-revalidate`) for all WebUI routes and static assets to prevent Windows desktop WebView2 from caching stale JavaScript or CSS.
- **Duplicate Action Button UX** — Fixed duplicate "Update now" buttons in the update available card by renaming the secondary manual update action label to "Manual download".

## [0.4.3] - 2026-05-17

### Added
- **Telegram Group Context Support** — Implemented advanced message tracking and context retention in Telegram group chats.
  - Added new `group_policy` configurations: `trigger` and `mention_or_trigger` (alongside existing `open` and `mention`).
  - Introduced `trigger_words` to configure custom keywords that trigger active bot responses in group chats.
  - Added `group_context_buffer_size` to control group conversation tracking.
  - Implemented a "non-reply" context accumulation flow (`no_reply` metadata): messages that do not directly trigger a bot response are silently saved into the active session history to maintain surrounding context without invoking the agent loop or showing typing indicators.
  - Group messages are now prefixed with the sender's identity (`sender_name: content`) to keep track of the group conversation history.

### Fixed
- **Desktop Launcher Persistence** — Fixed a bug where the native Windows Desktop Launcher (`pywebview`) wiped `localStorage` across application restarts because it was running in the default private mode. `private_mode=False` is now explicitly set, ensuring that UI preferences (like the GitHub star popup dismissal, active settings tab, and TTS settings) are properly persisted between sessions.

## [0.4.2] - 2026-05-17


### Added
- **Windows Auto-Start** — Added a "Run on Startup" option to the Windows System Tray menu. When enabled, ShibaClaw automatically launches when Windows boots up.
- **GitHub Star Popup** — Added an elegant, non-intrusive popup in the WebUI to encourage users to star the repository. The popup appears after a smart 45-second delay and permanently dismisses itself via `localStorage` once interacted with.
    
### Fixed
- **WebUI File Display** — Fixed an issue where files generated by the agent (e.g. images, text files) were missing from the chat UI or failing with 404 errors. Agent media paths are now correctly resolved to absolute workspace paths before being transmitted, and the WebSocket handler computes the serving URLs safely.
- **WebUI Auto-Focus** — Fixed a minor UI annoyance where the browser engine would incorrectly auto-focus and highlight the "Restart Gateway" button upon opening the desktop window.

## [0.4.1] - 2026-05-17
### Added
- **Thought Streaming UX** — Overhauled the model reasoning display in the WebUI. `<think>` blocks are now rendered as native, fluid `<details>` (accordion) components with glassmorphism styling and "Reasoning in progress" indicators, eliminating layout shifts during streaming.
- **Native Reasoning Support** — Added unified UI support for models that return native reasoning fields (like Gemini 2.0 Thinking or DeepSeek API) instead of raw `<think>` text blocks, ensuring all agent thoughts are rendered with the same beautiful accordion UX.
- **Thought Persistence** — Modified the agent loop and context management to preserve full reasoning history in the database. Reasoning blocks are now correctly recovered and displayed when refreshing the page or switching sessions.
- **Desktop Text Selection** — Enabled native text selection in the desktop WebView window (`ShibaClaw.exe`), allowing users to select and copy chat content.
- **Windows Automatic Updates** — Implemented and hardened the automatic self-replacing update system for Windows executables (`ShibaClaw.exe`), including seamless process hand-off and UAC elevation handling.
- **Update Progress UI** — Integrated a dynamic progress bar into the WebUI update modal, featuring real-time WebSocket progress reporting for instant user feedback during downloads and extraction.

### Fixed
- **Multilingual Support** *(thanks to @dercar2)* — Updated the tokenizer in `memory_search.py` to use Unicode-aware regular expressions (`\w+`) and aggressive case-folding. The agent can now successfully search and retrieve memories written in non-Latin alphabets (Cyrillic, CJK, etc.). Additionally, fixed a Telegram Markdown parsing bug (`telegram.py`) by replacing an ASCII-only regex with a Unicode word boundary, preventing the accidental corruption of non-Latin snake_case words.
- **Proactive Learning Data Loss** — Fixed a critical concurrency race condition where new messages arriving during a proactive consolidation cycle were incorrectly marked as "learned" without actually being saved.
- **Telegram Group Reply Bug** *(thanks to @dotvav)* — Fixed an issue in `telegram.py` where negative group chat IDs were mistakenly parsed as invalid strings, causing responses intended for group chats to be wrongly routed to user DMs.
- **WebUI Header Layout** *(thanks to @dercar2)* — Refined the sidebar interface by completely integrating the "Status" block into the top header next to the version badge, making it incredibly compact and styling it to match seamlessly. Shrunk the logo size and enforced `nowrap` layout so the badges fit perfectly on a single line on desktop displays. Also fixed a frustrating UX bug where the entire sidebar would auto-close whenever a user clicked the "Show X more" history button on mobile.
- **PowerShell False-Positive Guard** — Resolved an issue where PowerShell escape characters (like `` `n ``) triggered the "backtick execution" safety guard. The backtick block is now exclusively applied to POSIX (Linux/macOS) environments, as it is a safe character in PowerShell.
- **Thought Context Pollution** — Implemented dynamic stripping of `<think>` blocks from assistant messages *only* during prompt construction for the LLM API. This prevents token exhaustion (Context Pollution) while ensuring the WebUI still has access to the raw reasoning data.
- **Streaming Transition Flicker** — Updated WebSocket streaming logic to prevent the destructive removal of reasoning bubbles when the agent transitions between thinking and tool execution.
- **Empty Assistant Message Error** — Added a placeholder for assistant messages that contain *only* reasoning blocks, preventing "empty content" API errors from providers like OpenAI and Gemini after stripping the think tags.
- **OpenAI Stream Resilience** — Fixed intermittent "JSON error" issues injected into SSE streams during AI model response streaming by hardening the `chat_streaming` implementation in `OpenAIThinker` against malformed chunks and proxy/server interruptions.
- **PowerShell Formatting Commands Block** — Fixed a bug where PowerShell formatting cmdlets (like `Format-Table`, `Format-List`) were incorrectly blocked by the security guard. The regex for the destructive DOS `format` command was updated to use a negative lookahead, allowing safe PowerShell commands to pass through.

## [0.4.0] - 2026-05-16

### Fixed
- **Mobile WebUI Perfection** — Overhauled the mobile interface: fixed chat header overflows by hiding the width toggle on small screens, reduced element gap, and made input action buttons icon-only. Fixed session list scrolling issues by ensuring the history section has a guaranteed `min-height` and touch scrolling (`-webkit-overflow-scrolling: touch`), preventing other sidebar sections from collapsing it.
- **Notification Center Stability** — Major performance optimizations for the WebUI notification center: implemented `requestAnimationFrame` debouncing for `_render()` to prevent UI janking during rapid notification bursts, optimized the "mark all read" logic to avoid redundant `_upsert()` calls, and fixed accessibility by properly toggling `aria-hidden` on the dropdown.
- **Telegram Memory Leaks** — Fixed unbounded memory growth by adding a 500-entry FIFO eviction cap to `_chat_ids`.
- **Telegram Safety Guards** — Added a guard on `stop()` to prevent calling `updater.stop()` when the updater was never started, silencing noisy startup/shutdown exceptions. Protected the `_typing_loop` with a `try/except` block to handle non-numeric `chat_id`s, preventing silent crashes of the typing task.
- **Telegram Markdown Parsing** — Improved the `_markdown_to_telegram_html` converter to correctly parse nested bold and italic tags (e.g. `***text***`), ensuring complex agent formatting renders correctly in Telegram.

## [0.3.9] - 2026-05-15

### Added
- **Mobile Sidebar Auto-Close** — The sidebar drawer now closes automatically on mobile after selecting a session, starting a new session, clicking a hint card, executing a sidebar command, or opening any modal. A semi-transparent backdrop (`sidebar-backdrop`) is rendered behind the drawer; tapping it collapses the drawer. Pressing `Escape` or clicking outside the sidebar also closes it.
- **Sidebar Backdrop** — New `#sidebar-backdrop` element with a smooth opacity transition (`rgba(0,0,0,0.45)`) provides a native-app feel on mobile. Hidden on desktop via `sidebar.css`; activated only when `isMobileSidebar()` is true.
- **Version Resolution Regression Tests** — Added `tests/test_version_resolution.py` with three parametrized tests covering the frozen (EXE), source-checkout, and pip/docker version resolution branches.

### Fixed
- **Environment-Aware Version Resolution** — `shibaclaw/__init__.py` `_get_version()` now selects the appropriate source depending on runtime context:
  - **Frozen (PyInstaller EXE):** bundled `update_manifest.json` → installed metadata → `"dev"`
  - **Source checkout:** `pyproject.toml` → installed metadata → bundled manifest → `"dev"`
  - **Pip / Docker install:** installed metadata → bundled manifest → `pyproject.toml` → `"dev"`
  Previously all environments shared the same chain, causing pip/docker installs to read a stale internal manifest instead of the installed package metadata.
- **Hardcoded Version Fallback Removed** — The changelog UI (`ui_panels.js`) was falling back to `"0.3.6"` when no version was resolved at startup. Replaced with a `hasResolvedVersion` guard and a `/releases/latest` redirect so users always see the correct information.
- **Release Workflow Manifest Path** — The GitHub Actions publish job now attaches the repo-root `update_manifest.json` to releases instead of the internal `shibaclaw/updater/update_manifest.json` copy.

## [0.3.8] - 2026-05-13

### Added
- **WebUI Notification Center (WIP)** — Scaffolded the notification center UI: bell icon with unread badge, dropdown list, deep-link to related session, and clear-all action. **⚠️ This feature is still under active development and not fully stable:** some edge cases (e.g. sessions with no WebUI target configured, multiple open tabs) may not receive notifications reliably. These will be addressed in upcoming releases.
  - In-memory `NotificationManager` backend with per-session deduplication and persistence.
  - REST endpoints at `/api/v1/notifications` (GET, POST, DELETE, mark-read).
  - Real-time broadcast via WebSocket (`type: notification`) to all connected browser clients.
  - Notifications for: heartbeat completed, cron job completed, agent response (on a session/tab not currently in focus), and update available.
  - Event source prioritization: `source` field now takes precedence over generic `msg_type` when classifying notification `kind`.
- **Windows GPU Compositing Fix** — Added `--disable-gpu-compositing` flag via `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` on Windows builds to eliminate screen flickering caused by Edge WebView2 async GPU compositing during heavy DOM updates (e.g. streaming responses). Explicitly set `gui="edgechromium"` to prevent fallback to the legacy `mshtml` engine.
- **Update Check Realtime** — The update-available notification is now broadcast in real-time via WebSocket to all connected browser clients at the time of the version check (previously it was only stored).

### Fixed
- **Notification Pipeline** — Fixed an early-return in `deliver_background_notification` that aborted notification creation when `PackManager` failed during persistence. Persistence is now wrapped in `try/except` so the notification is always created and broadcast.
- **Heartbeat With No WebUI Target** — When no WebUI session was present on disk, `select_heartbeat_target` returned `cli:direct` and no notification reached the WebUI. A system broadcast is now always sent to the WebUI regardless.
- **Cron With External Channel** — Cron jobs configured with `deliver=True` on an external channel (e.g. Telegram) never notified the Notification Center. They now always send a WebUI broadcast as well.
- **`_on_session_notify` With Empty Session Key** — The condition `if sk and content` was discarding system-level broadcasts where `session_key` is empty. Changed to `if content`.
- **Agent Responses on Other Tabs** — Agent responses were only emitted to the current session's WebSocket. A server-side notification is now created and broadcast after every response; the JS suppresses the badge only when the user is focused on that exact session tab.
- **Empty Heartbeat/Cron LLM Response** — When the LLM returns no text (e.g. tool-call-only turn), a fallback message (`"Heartbeat task completed."` / `"Cron job executed successfully."`) is now generated so the notification is always triggered.

### Security
- **Protobuf Vulnerabilities** — Resolved 8 vulnerabilities (High/Moderate) in `protobufjs` and `@protobufjs/utf8` within the WhatsApp bridge by upgrading the package override to `v7.5.8`. Addresses code injection, prototype pollution, and multiple Denial of Service (DoS) vectors.


## [0.3.7] - 2026-05-10

### Security
- **Format String Vulnerability** — Fixed a potential format string vulnerability in the WebUI realtime client (`realtime.js`) by avoiding template literals in `console.error`.
- **Clear-text Logging** — Removed debug statements in the WebUI API (`api.py`) that logged sensitive raw HTTP payload data in clear text.
- **HTML Filtering** — Hardened the HTML tag stripping regex in the web tool (`web.py`) to correctly handle `>` characters inside attribute quotes, preventing tag bypasses, and fixed a CodeQL alert by properly escaping closing tags with trailing whitespace (e.g. `</script >`).
- **ReDoS Vulnerability** — Optimized the media parsing regular expression (`loop.py`) to prevent Catastrophic Backtracking (ReDoS) when processing malicious or malformed nested arrays.

### Fixed
- **UI Quote Escaping** — Fixed a bug in the settings panel (`ui_panels.js`) where double quotes were incorrectly replaced with themselves instead of the proper HTML entity (`&quot;`), potentially breaking input fields.
- **CI/CD Tests** — Fixed a `TypeError` in heartbeat service tests by passing the correct `interval_min` argument instead of the outdated `interval_s`.
- **CI/CD Warnings** — Suppressed third-party deprecation warnings (`websockets.legacy` and `uvicorn.protocols.websockets`) in pytest to prevent CI failures.
- **Linters** — Removed unused imports (`DWORD` from `ctypes.wintypes`, `re`, and `importlib.metadata`) across the codebase to resolve Ruff `F401` violations.
- **Desktop Restart Duplication** — Fixed the WebUI restart button spawning duplicate processes and tray icons in Desktop mode. The gateway subprocess now cleanly exits instead of calling `os.execv` when managed by `DesktopRuntime`, and a monitor thread automatically relaunches it. The WebUI server uses a registered callback to restart only the gateway instead of the entire parent process.
- **Install Audit Cross-Platform** — Fixed pip-audit execution on Windows by replacing the Unix-only `/dev/stdin` pipe with a cross-platform temporary file (`tempfile.NamedTemporaryFile`).
- **Heartbeat Hot-Reload Crash** — Fixed an `AttributeError` on `interval_s` during heartbeat configuration reloads.
- **Token Calculation Accuracy** — Removed duplicate variable assignment in `webui/api.py` that caused token estimations to incorrectly overwrite the total prompt token count.
- **Severity Heuristics Integrity** — Prevented `pip-audit` JSON parser from improperly overriding verified CVE severity scores with keyword-based heuristics when the original severity is known.
- **WebSocket Keepalive** — Enabled Uvicorn's `ws_ping_interval` and `ws_ping_timeout` to correctly drop dead browser WebSocket connections.

### Changed
- **Tiktoken Caching** — Implemented a module-level lazy load cache for the `tiktoken` encoding in `helpers.py`, preventing slow repeated encoding initialization on hot paths.
- **WebUI PackManager Optimization** — Centralized the memory-heavy `PackManager` instantiation into `AgentManager`, ensuring WebUI routes reuse the loaded context instead of re-instantiating it on every single HTTP request.
- **API Status Optimization** — Refactored `/api/status` to avoid redundant HTTP internal calls and JSON re-parsing when resolving OAuth provider states.
- **Background Tasks Resilience** — Startup coroutines (update checks, skill sync) in the WebUI server are now actively tracked with done callbacks to catch and log unhandled background exceptions.
- **Cron Concurrency** — Added an `asyncio.Lock` in `CronService` to prevent simultaneous automated jobs from corrupting `jobs.json` during concurrent state saves.
- **Heartbeat Interval Unit** — Converted the heartbeat interval from seconds (s) to minutes (min) throughout the system, including the WebUI settings, status display, and internal Pydantic configuration, ensuring consistency with the backend schema.
- **Dedicated Heartbeat Settings Tab** — Extracted heartbeat configuration into a dedicated tab in the WebUI. Added support for per-service model override, agent profile selection, and dynamic output channel routing based on active integrations.
- **Heartbeat Template Refactoring** — Removed silent frontmatter overrides from the default `HEARTBEAT.md` template to prioritize WebUI-based configuration while maintaining optional YAML overrides for power users.

## [0.3.4] - 2026-05-08

### Fixed
- Fixed CI build failure caused by native Matrix E2E dependencies (`python-olm`). Matrix is now included without E2E encryption in the Windows bundle.

## [0.3.3] - 2026-05-08

### Fixed
- Fixed CI build size by ensuring all integration channel dependencies (extras) are installed before packaging.
- Resolved local versioning discrepancy in PyInstaller bundles by reinstalling the editable package metadata.

## [0.3.2] - 2026-05-08

### Fixed
- Bundled native Windows runtime DLLs (pywebview, pythonnet, clr_loader) in GitHub Actions builds.
- Improved CI smoke testing to verify desktop native dependencies during packaging.

## [0.3.1] - 2026-05-08

### Fixed
- **OAuth model not recognised at startup** — When `provider` is `"auto"` and the saved model has no provider prefix (e.g. `oswe-vscode-prime` instead of `github_copilot/oswe-vscode-prime`), the provider resolver now correctly falls back to an authenticated OAuth provider instead of routing the model to a generic gateway that rejects it. Eliminates the "is not a valid model" error on every cold start.

### Changed
- **Code cleanup & optimisations** — Consolidated duplicate `_normalize_save_memory_args` / `_normalize_update_memory_args` into a single `_normalize_tool_args` helper; fixed indentation bug in `sync_workspace_templates` that caused redundant overwrite prompts; modernised typing imports in `brain/routing.py`; removed dead code in `cli/gateway.py`.

## [0.3.0] - 2026-05-07

### Added
- **Release Automation** — Added documentation and helpers for managing GitHub releases.
- **Native Windows Desktop Launcher** — Added a seamless pywebview-based Windows desktop client (`ShibaClaw.exe`) featuring a system tray icon, window state management, and bundled assets.

### Changed
- **Desktop WebUI Authentication** — Disabled authentication by default for the native Desktop launcher to improve the out-of-the-box local experience.
- **Session titles cleanup in WebUI history** — Sidebar session titles are now normalized by removing channel prefixes (e.g. `webui_`, `telegram_`, `heartbeat:`, `cron:`), keeping names cleaner and easier to scan.
- **Channel tag under session title** — Each session row now shows its channel as a dedicated tag on the subline (under the title), separate from date/time metadata for improved visual hierarchy.
- **Channel-aware badge palette** — Session channel tags now use coherent per-channel colors in the sidebar (`Web UI` gold/yellow, `Telegram` blue, `Discord` dark blue, `Heartbeat` dark violet, plus dedicated styles for `Cron`, `Slack`, `API`, and `CLI`).
- **Sidebar session subline alignment polish** — Refined spacing, pill sizing, and vertical alignment for channel tags and timestamp metadata to improve readability and consistency across active/inactive rows.

### Fixed
- **Desktop Windows Startup Crash** — Fixed a `NoneType` exception in `loguru` on Windows packaged builds (`console=False`) where `sys.stderr` is `None`.
- **Desktop Subprocess Fork Bomb** — Intercepted `gateway` commands in the PyInstaller entry point to prevent infinite recursive UI window spawning during gateway startup.
- **Cron Jobs Execution** — Fixed a bug where Cron jobs were not correctly wired into the agent lifecycle (Gateway callbacks were missing). The gateway now correctly arms and stops the internal cron loop during startup/shutdown.
- **Cron Jobs UI Visibility** — Added `hidden` metadata to cron task prompts so that routine reminder requests and task payloads do not clutter the WebUI chat session interface.
- **Cron Jobs blocking Timers** — Decoupled Cron execution by running tasks via asynchronous background workers. LLM response times will no longer block the main cron timer loop, resolving timeouts and "frozen" UI situations while processing automated tasks.

## [0.2.1] - 2026-05-03

### Fixed
- **Dependencies aligned** — Updated and pinned several Python dependencies to resolve version conflicts and improve installation reliability across environments.
- **WebUI sidebar polish** — Cleaned up sidebar layout and styling for better visual consistency; fixed minor alignment and overflow issues in the settings and navigation panels.

### Changed
- **Dependency maintenance** — Bumped `openai`, `httpx`, `pydantic`, and related packages to their latest compatible minor versions to pick up bug fixes and stability improvements.

## [0.2.0] - 2026-05-02

### ⚡ Dynamic Model Selection

<p align="center">
  <img src="assets/model_sel.jpg" width="600" alt="Agent Profile Selector">
</p>

**Change models per session** — no more single global model, but a flexible choice for every conversation.

- **Multi-Provider Search**: Search through all models from all your configured providers (OpenRouter, GitHub Copilot, Anthropic, etc.) in a single dropdown.
- **Session-Aware Routing**: Each session remembers its chosen model. You can have a coding session with `Claude 3.5 Sonnet` and a research session with `Gemma 4` simultaneously.
- **Runtime Switching**: Switch models instantly without restarting the agent; the gateway automatically resolves the correct endpoint based on the selected model.
- **Dedicated Memory Model**: Configure a separate model and provider specifically for memory consolidation and proactive learning, ensuring high-quality state extraction without affecting your chat budget.
- **Default-First**: New sessions automatically start with the default model set in settings, ensuring immediate consistency.

### Added
- **Cross-provider model catalog** — The WebUI now aggregates models from all configured providers into a single searchable catalog. Chat and settings both consume normalized model entries with canonical IDs and provider labels, so switching models no longer depends on a single provider-scoped dropdown.
- **Per-session model selection** — Every session can now store and use its own model independently. The chat footer includes a searchable model picker, making it practical to keep different sessions on different providers or reasoning tiers at the same time.
- **OpenRouter OAuth in the WebUI** — Added a browser PKCE flow for OpenRouter directly in Settings. On successful login, the returned API key is saved into the provider configuration automatically.


### Changed
- **Dynamic Settings Hot-Reload** — Saving settings in the WebUI no longer restarts the gateway process. The agent, channels, and heartbeat service are updated in-place via a new `POST /reload` endpoint on the gateway. Provider, model, tool configurations, MCP servers (lazy reconnect), and individual channels all hot-swap without interrupting active WebSocket connections or ongoing tasks. A full restart is still triggered automatically only when `gateway.host`, `gateway.port`, or `gateway.ws_port` change.
- **Model-first routing** — Runtime provider resolution is now driven by the selected model instead of a static global provider assumption. Canonical model IDs such as `openrouter/...` or `anthropic/...` are normalized before dispatch so the gateway reaches the correct backend endpoint.
- **Settings UX refresh** — The Agent tab is now centered on model choice: default model for new sessions, memory / consolidation model picker, and reusable searchable model menus. The old provider selector was removed from the Agent tab, and OAuth was moved directly below Providers in the settings sidebar.
- **Provider visibility in model search** — Chat and settings model pickers now show provider labels alongside model names, making mixed catalogs usable even when multiple providers expose similarly named models.

### Fixed
- **Custom Provider support** — The custom provider now correctly strips the `custom/` prefix before making requests and implements `get_available_models()`, enabling full integration with localized REST endpoints.
- **URL sanitization for providers** — Automatic stripping of trailing whitespaces and tabs in `api_base` properties, preventing invalid ASCII byte exceptions during chat fetches and model discovery.
- **Reasoning-only response visibility** — Chat responses consisting solely of reasoning blocks (e.g. some LM Studio or DeepSeek scenarios) without standard content are now safely rendered as Process Group bubbles in the WebUI.
- **GitHub Copilot model discovery** — Copilot now refreshes its short-lived session token before listing available models, fixing malformed authorization failures during catalog fetches.
- **Session override provider mismatches** — Session-level model overrides now ignore a forced global provider when the chosen model clearly belongs to another backend, ensuring the gateway actually switches provider at runtime.
- **WebUI / gateway session desync** — Session caches now reload when the underlying JSONL file changes on disk, preventing stale in-memory metadata from overriding model changes saved by the WebUI.
- **Model dropdown transparency** — The chat model dropdown and search input now use solid theme-backed colors instead of undefined CSS variables, eliminating transparent or unreadable menus.


## [0.1.8] - 2026-05-01

### Changed
- **WebUI client hardening** — Centralized safe DOM helpers for attachment links, icons, file-browser rows, and breadcrumb rendering so user-controlled labels are inserted via DOM nodes instead of HTML string interpolation.

### Fixed
- **WebUI XSS surfaces** — Escaped raw HTML in Markdown rendering, stopped interpolating attachment and file names into `innerHTML`, and switched confirm-dialog messages to `textContent` to prevent browser-side script injection from chat content, file names, or UI error strings.
- **WebUI logout/reconnect lifecycle** — Logging out or hitting a `401` now clears timers, stops automatic WebSocket reconnection, clears the cached auth token, and re-enters the login screen cleanly without background reconnect loops or duplicated startup state.
- **WebUI repeated bootstrap handlers** — `initSocket`, `initListeners`, file handlers, automation sections, and onboarding setup are now idempotent, preventing duplicated event handlers after login/logout cycles or repeated app startup.
- **Memory search runtime validation** — `memory_search` now rejects `top_k < 1` with a clear `ValueError` instead of returning misleading empty results or truncated output through negative slicing.
- **Python 3.14 test compatibility** — Memory search integration tests now run with `pytest-asyncio` coroutines instead of relying on the removed implicit main-thread event loop behavior.

## [0.1.7] - 2026-04-25

### Added
- **Reasoning Effort Fallback** — Implemented an automatic fallback mechanism for the `reasoning_effort` parameter. If a model does not support this parameter, the system now automatically retries the request without it instead of returning a 400 error.
- **WebUI Real-time Updates** — Enabled real-time message pushing via WebSockets for background tasks. Responses to subagent tasks are now delivered instantly to active WebUI sessions without requiring a page refresh.

### Changed
- **Subagent UI Privacy** — Subagent task summaries and technical logs are now hidden by default in the WebUI chat history. Users only see the final natural language response from the main agent, keeping the conversation clean while preserving the technical data in the session metadata.
- **Native Browser Integration Cleanup** — Temporarily removed the Native Browser (CDP) tools and settings to streamline the configuration process while the feature undergoes further refinement.
- **Lazy Session Creation** — Improved WebUI session management by preventing the immediate creation of empty session files on disk when clicking "New Session". Session files are now lazily generated only upon the first message, with `profile_id` cached in memory until persistence.
- **Smart Session Titling** — Enhanced the automatic session titling logic to prepend the source channel name (e.g., `Telegram_` or `webui_`) to the generated title based on the first message, providing better organization in the history list.

### Fixed
- **WebUI Context Reporting** — Fixed an issue where the WebUI token usage count didn't update after `autocompact` and could exceed 100%. The system now correctly calculates token usage based only on active (unconsolidated) messages and invalidates the context cache immediately when compaction occurs.
- **Gateway Attribute Error** — Resolved an `AttributeError: 'ToolsConfig' object has no attribute 'browser'` that caused gateway crashes after the browser configuration was removed. Fixed the initialization sequence in both `gateway.py` and `agent.py`.
- **WebUI Onboard 500 Error** — Fixed a `SyntaxError: Unexpected token 'I', "Internal S"...` error at the end of the onboarding wizard. This was caused by an `AttributeError` from a call to the deprecated `ensure_agent()` method in the onboard router.
- **Settings Router Cleanup** — Removed stale references and updated comments regarding the deprecated `ensure_agent()` method in the settings router.


## [0.1.6] - 2026-04-25

### Added
- **API Modularization & Routers** — Refactored the WebUI backend into dedicated API routers (`onboard`, `settings`, `sessions`, `gateway`, etc.), improving code organization and enabling easier extension of WebUI capabilities.
- **WebUI Communication Utilities** — Implemented specialized utilities for managing system prompts and session-aware gateway communication.

### Changed
- **Native WebSocket Transport** — Fully transitioned from Socket.IO to a custom, native WebSocket implementation. This change reduces dependency overhead and provides a more direct, robust communication channel between the WebUI and the agent gateway.

## [0.1.5] - 2026-04-24

### Fixed
- **Telegram (and other optional channels) not starting in Docker** — The `Dockerfile` installed only the base package (`uv pip install .`), silently skipping the `[telegram]` optional extra. The bot appeared configured but never loaded — no polling, no messages. Fixed by installing `.[telegram]` so `python-telegram-bot` is always present in the image. Channels relying on other optional extras (e.g. `[slack]`) should be added to the Dockerfile extra list similarly.

## [0.1.4] - 2026-04-24

### Fixed
- **`AttributeError: 'list' object has no attribute 'strip'`** — Memory consolidation crashed during `maybe_proactive_learn()` when messages contained multi-part content (OpenAI-style `[{"type": "text", "text": "..."}]` format). Added `_normalize_content()` to `ScentKeeper._format_messages()` to handle `str`, `list`, and `None` content uniformly. *(Thanks [@itskun](https://github.com/itskun) for the report! — [#18](https://github.com/RikyZ90/ShibaClaw/issues/18))*
- **Channel Status missing configured channels** — `shibaclaw channels status` silently omitted any channel whose optional dependency was not installed (e.g. Telegram without `python-telegram-bot`). Channels with unresolvable imports now appear in the table with a `! missing dep` indicator, making misconfigured setups immediately visible.

### Added
- **`SHIBACLAW_DEBUG` env var** — Set `SHIBACLAW_DEBUG=true` (or `1`/`yes`/`on`) to force `DEBUG` log level with full backtraces and source-file annotations, without needing the `--verbose` flag. Useful for Docker deployments. The variable is documented in `docker-compose.yml` as a commented-out example.

## [0.1.3] - 2026-04-19

### Added
- **Native OpenAI SDK Support**: Added `OpenAIThinker` to replace the generic compatibility wrapper, providing direct integration with the OpenAI Python SDK and supporting provider-specific tool call metadata preservation.
- **Advanced Configuration Loader**: Implemented a robust configuration system with automatic state migration and streamlined plugin onboarding.

### Fixed
- **MCP WebUI Visibility**: Resolved an issue affecting the display of MCP servers in the WebUI.
- **Gemini Streaming Tool Signatures**: Fixed an issue where Gemini streaming was dropping or malforming tool signatures. *(Thanks @shirik for the PR!)*

## [0.1.2] - 2026-04-19

### Fixed
- **CI/CD — 88 lint errors eliminated**: All `ruff` violations across the codebase have been resolved (naming conventions, unused imports, ambiguous variable names, import ordering, E402 module-level imports). CI workflows now pass cleanly on every release.
- **WebSocket connection drops during long tasks (`connection_lost`)**: Disabled automatic WebSocket ping/pong timeouts at all three transport layers (Uvicorn, gateway WS server, gateway WS client). The periodic "ping" mechanism was erroneously closing live connections when the agent was busy and could not respond in time.
- **Thinking panel flash / timer freeze**: Removed a spurious `hideThinking()` call from the `agent_response_chunk` event handler. Previously, each streamed response token was hiding the thinking panel, causing a visible flash when the model transitioned between generation and tool use, and making the elapsed-time counter appear frozen.
- **File browser and settings blocked while agent is running**: The gateway WebSocket handler was awaiting `agent.process_direct()` inline, which blocked the entire WS event loop for that client. Any concurrent request (e.g. health checks, settings) would time out until the agent finished. The chat handler is now launched as a separate `asyncio.Task`, keeping the handler loop free.
- **Gateway health check noise while processing**: `checkGatewayHealth()` in the frontend now skips entirely when `state.processing` is true, preventing unnecessary timeout errors and false "Gateway Down" status while the agent is working.

### Changed
- **`_CHAT_TIMEOUT` increased** from 120 s to 1800 s in `shibaclaw/thinkers/base.py` to accommodate complex multi-step reasoning tasks.

## [0.1.1] - 2026-04-19

### Fixed
- **Hotfix**: Fixed an `ImportError` on CLI startup (`setup_shiba_logging` missing from `shibaclaw/cli/utils.py`) caused by aggressive autolinting.

## [0.1.0] - 2026-04-19

### Added
- **Official API Documentation**: Full REST API reference is now available in `docs/API_REFERENCE.md`.
- **CI Pipeline**: Automated testing and linting (pytest + ruff) via GitHub Actions.
- **API Test Suite**: Proper integration tests for WebUI routers via Starlette TestClient.

### Changed
- **Beta Milestone**: Promoted project status from Alpha to Beta (`Development Status :: 4 - Beta`).
- **Refined Footprint**: Channel-specific SDKs (Telegram, Slack, DingTalk, Feishu, QQ, WeCom, Matrix) have been moved to optional extras for a leaner default install.
- **Dependencies**: Added upper bound on the `openai` dependency to prevent unexpected breaking changes from v3.0.0+.

## [0.0.40] - 2026-04-19

### Added
- **Memory compaction WebUI notification** — After auto-compaction, the backend now broadcasts a `memory_compacted` event to all connected WebUI clients. When the context viewer is open, it auto-refreshes to reflect the compacted token count.
- **WebSocket broadcast support** — `deliver_to_browsers()` now accepts an empty `session_key` to broadcast a message to all connected clients, with a configurable `msg_type` parameter for custom event types.
- **Session status emission on processing** — The WebSocket handler now emits `session_status` updates immediately when a message starts processing, keeping the UI in sync with the backend state.

### Fixed
- **WebUI stuck on "Connecting..."** — A JavaScript syntax error in `ui_panels.js` (mismatched bracket `});` instead of `}` in the memory compaction listener) prevented the entire file from executing. Since `ui_panels.js` defines `startApp()`, this blocked WebSocket initialization and left the UI permanently stuck on "Connecting..." with no token prompt and no errors in the console.

## [0.0.38] - 2026-04-18

### Added
- **Token-by-token response streaming** — The LLM response is now streamed to the browser in real time, character by character. Supported natively for all OpenAI-compatible providers (OpenRouter, GitHub Copilot, Groq, DeepSeek, etc.) and Anthropic via their respective streaming APIs. Providers without native streaming support (Azure, Custom, Codex) automatically fall back to delivering the full response in one shot without errors.
  - New abstract method `chat_streaming()` on `Thinker` base class, with a non-streaming default fallback so existing provider subclasses work unchanged.
  - New `chat_with_retry_streaming()` on `Thinker` base class with the same transient-error retry logic (backoff on 429/5xx) as `chat_with_retry()`.
  - `OpenAIThinker` and `AnthropicThinker` implement true streaming via `stream=True` / `messages.stream()`.
  - `GithubCopilotThinker` overrides `chat_streaming()` to refresh the short-lived OAuth session token before each streaming call (same pattern as its `chat()` override).
  - `on_response_token` callback threaded through `_run_agent_loop` → `_process_message` → `process_direct`.
  - Gateway emits `chat.response_token` WebSocket events for each text delta.
  - `GatewayClient.chat_stream()` yields `{"t": "rt"}` events for response token chunks.
  - `ws_handler` accumulates streamed content and forwards `response_chunk` messages to the browser.
  - Browser (`realtime.js`, `api_socket.js`) progressively renders each chunk into a live message bubble using the existing Markdown renderer; the bubble is finalised with the complete content when the `response` event arrives.

### Fixed
- **Streaming bubble stuck on tool call** — If the model emits text tokens then switches to a tool call (e.g. extended thinking before tool use), the partial streaming bubble is now immediately removed when a `thinking` or `tool` progress event arrives, preventing stale content from showing in the chat.
- **Processing state locked after empty response** — When the agent dispatches a reply through a channel tool (e.g. `MessageTool`) and returns no direct WebUI response, the WebSocket handler previously did an early return without emitting a `response` event, leaving `state.processing = true` and the send button permanently disabled until page reload. The `response` event is now always emitted.

## [0.0.38] - 2026-04-18

### Added
- **Native WebSocket transport** — Replaced Socket.IO with a native WebSocket layer. The gateway now runs a dedicated WS server on port `19998`; the WebUI connects via a new `realtime.js` adapter (drop-in replacement for the Socket.IO client). Eliminates the `python-socketio` dependency from the core install — moved to the optional `[mochat]` extra. New files: `gateway_client.py`, `ws_handler.py`, `realtime.js`.
- **Gemini raw env-var support** — `GEMINI_API_KEY` set in the environment is now accepted directly by the config and provider-matching logic without needing a stored key. Auto-detection via env var works alongside existing stored keys. *(Thanks [@shirik](https://github.com/shirik)!)*
- **Gemini OpenAI-compat endpoint** — `default_api_base` for the Gemini provider is now set to `https://generativelanguage.googleapis.com/v1beta/openai/`, enabling out-of-the-box routing without manual configuration. *(Thanks [@shirik](https://github.com/shirik)!)*

### Changed
- **WebUI provider API-key placeholders** — Settings panel and Onboard wizard now show provider-specific placeholder text (`AIza…` for Gemini, `sk-ant-…` for Anthropic, `gsk_…` for Groq, etc.) instead of the generic `sk-...`. *(Thanks [@shirik](https://github.com/shirik)!)*
- **`message` tool workspace context** — `MessageTool` now receives and uses the agent workspace path to resolve relative media file paths, improving file-attachment reliability across channels.

## [0.0.37] - 2026-04-17

### Fixed
- **Dependency Vulnerabilities (CVE)** — Critical security update resolving RCE in `protobufjs` via `overrides` in the WhatsApp bridge and updating `cryptography`, `pytest`, and `python-multipart` to safe versions.

## [0.0.36] - 2026-04-16

### Fixed
- **`web --with-gateway` host routing** — Bare-metal launches now force the spawned gateway onto local loopback and export the correct internal WebUI URL, fixing `Gateway unreachable: [Errno -2] Name or service not known` when the saved config still pointed to the Docker hostname `shibaclaw-gateway` or when the WebUI used a custom port.
- **File Explorer modal UX** — The Files popup now scrolls correctly on tall directories and no longer closes when clicking outside the dialog.
- **Cron store reload noise** — Reload bookkeeping now refreshes the saved mtime after a successful `jobs.json` load, preventing repeated external-reload logs for the same file and downgrading the message to debug.

### Changed
- **Release metadata & docs** — README, deploy guide, Docker memory guidance, and update metadata now reflect the thin WebUI architecture and the recommended `shibaclaw web --with-gateway` flow.

## [0.0.35] - 2026-04-16

### Added
- **Distributed Architecture (WebUI Proxying)** — Integrated a thin-client architecture for the WebUI. The `shibaclaw-web` process no longer instantiates the LLM, memory, or background consumers. It delegates all processing via a new internal streaming API on the `shibaclaw-gateway`.
- **NDJSON Streaming API** — The gateway now supports streaming agent progress and tool execution status via HTTP, allowing remote UI clients to maintain real-time interactivity.
- **Heartbeat & Cron Delegation** — Automated tasks are now unified and run strictly in the gateway process, even when triggered from the WebUI.

### Fixed
- **Massive RAM usage reduction** — Eliminated duplication of the entire agent core between processes. `shibaclaw-web` memory footprint dropped by nearly 90% (no longer loads heavy ML models or provider libraries internally).
- **Service dependencies** — Added `depends_on` in `docker-compose` to ensure the gateway is available before the UI attempts to proxy requests.

## [0.0.31] - 2026-04-14

### Fixed
- **`exec` tool broken (NameError)** — Added the missing `_BoundedBuffer` class definition in `shell.py`. In v0.0.30 the class was referenced but never defined, causing every shell command to fail with `NameError: name '_BoundedBuffer' is not defined`.

## [0.0.30] - 2026-04-14

### Fixed
- **Race condition dual consumer** — Fixed a bug where WebUI in standalone mode started both inbound polling and outbound dispatcher, causing lost messages because it competed with its own outbound consumer.
- **Missing feedback on long execution** — `ExecTool` now sends a progress heartbeat every 15s to the UI during long-running commands, so it doesn't look stuck.
- **Subagent context explosion** — Subagent tool results are now properly truncated at 8,000 chars to avoid exploding the context window.
- **Hanging agent loop** — Added 120s timeout to LLM provider calls, 660s timeout to tool execution, and 600s overall wall-clock loop cap to prevent infinite hangs.
- **Telegram Conflict error loop** — Replaced silent retry loop with graceful fallback to outbound-only mode if another bot instance is polling.
- **Gateway connection check** — Added retry backoff when checking if gateway is reachable to give Docker container startup time to bind ports, preventing false negative conflicts.

## [0.0.28] - 2026-04-14

### Added
- **Heartbeat frontmatter config** — `HEARTBEAT.md` now supports a real YAML config block at the top for `session_key`, `profile_id`, and explicit `targets`.
- **Heartbeat target aliases** — output targets like `webui: recent` or `telegram: recent` now resolve to the most recent session for that channel.

### Changed
- **Heartbeat template semantics** — the bundled `HEARTBEAT.md` template is now the actual source of heartbeat session/profile/target settings, while `enabled` and `interval_s` remain in global settings. Upgrading users are recommended to reset their workspace `HEARTBEAT.md` once to pick up the new base frontmatter block.
- **Heartbeat status UI** now shows the effective session key, profile, and targets.

### Fixed
- **Heartbeat token waste** — the heartbeat service no longer calls the LLM when `HEARTBEAT.md` has no real active tasks in the `Active Tasks` section.
- **Cron blank jobs** — agent-turn cron jobs with an empty message are now skipped instead of invoking the agent unnecessarily.

## [0.0.26] - 2026-04-11

### Fixed
- **Profile hover highlight** — dropdown items had no visible hover state because `--bg-hover` CSS variable was undefined; replaced with the correct `--bg-surface-hover`.
- **Welcome screen logo** now updates when switching profiles, matching the sidebar logo and chat avatars.

### Changed
- Removed dead CSS rules (`.chat-header-info h2`, `.chat-header-subtitle`) targeting elements no longer in the HTML.

## [0.0.25] - 2026-04-11

### Added
- **Agent Profiles — Per-Session Personas**
    - Switch the agent's personality on-the-fly via a dropdown in the chat header.
    - 5 built-in profiles: **Default** (original ShibaClaw), **Builder** (code-first, minimal chatter), **Planner** (strategic thinking, breaks down problems), **Reviewer** (critical eye, finds issues), **Hacker** (elite security expert).
    - Each profile overrides the agent's SOUL.md prompt — model, provider, and memory stay shared.
    - Profile selection is **per-session**: different sessions can use different personas simultaneously.
    - Profiles are stored as simple `profiles/<id>/SOUL.md` folders in the workspace — easy to read, edit, and version.
- **Custom Profile Creation via Agent**
    - "Create custom profile" button opens a new session with a structured prompt that walks you through defining a new persona interactively.
    - The agent generates the SOUL.md, saves it, and registers it in the manifest — no manual file editing needed.
- **Dynamic Profile Avatars**
    - Profiles can have a custom avatar image (configured via `avatar` field in `manifest.json`).
    - Switching profiles updates **all visible agent avatars** in the chat and sidebar in real-time.
    - Switching back to Default restores the original ShibaClaw logo.
- **Hacker Profile — Full Security Toolkit**
    - Elite security persona with deep expertise in 7 domains: web app security, network/AD attacks, code auditing, container/cloud, cryptography, reverse engineering, and forensics.
    - Includes a curated **toolkit of 50+ security tools and packages** (Python, Node.js, CLI) with quick-install commands.
    - Follows OWASP WSTG, PTES, MITRE ATT&CK, NIST, CIS Benchmarks, and Kill Chain methodologies.
    - Structured vulnerability reporting with CVSS v3.1/v4.0 scores, CWE, and MITRE ATT&CK mapping.
    - 10-step code audit checklist from attack surface mapping to full report.
    - Custom hacker avatar (red cyber-shiba with sunglasses).
- **Profile Startup Sync**
    - Built-in profile templates are auto-synced to the workspace on startup (like skills).
    - Corrupted or missing manifests are automatically repaired.
    - New fields (e.g. `avatar`) are merged into existing profiles without overwriting user customizations.
- **Profile API** (`/api/profiles`)
    - `GET /api/profiles` — list all profiles with metadata and avatar URLs.
    - `GET /api/profiles/{id}` — get profile details including SOUL.md content.
    - `POST /api/profiles` — create a new custom profile (with optional avatar).
    - `PUT /api/profiles/{id}` — update profile metadata, soul, or avatar.
    - `DELETE /api/profiles/{id}` — delete custom profiles (built-in profiles are protected).

### Changed
- **Context system prompt** is now profile-aware: cache keys and mtime tracking are per-profile.
- **Session metadata** stores `profile_id` — survives session switches and reconnections.
- **Socket.IO events** (`connected`, `session_reset`) emit `profile_id` for frontend sync.

## [0.0.23] - 2026-04-10

### Fixed
- **WebUI file/message attachment freeze** — `_consume_outbound` was matching sessions by socket `sid` instead of `session_key`, causing all messages dispatched via the `message()` tool to be silently dropped. The UI would hang indefinitely in loading state. Fixed session lookup, room target (`session:{key}`), and history persist logic.

## [0.0.22] - 2026-04-10

### Added
- **Skills Management WebUI**
    - New Settings → Skills panel: browse all installed skills (builtin + workspace), view descriptions, source badges, and missing requirements.
    - **Always Active Pinning** — pin skills to be loaded on every conversation. Configurable limit via `max_pinned_skills` (default 5).
    - **Skill Import** — upload `.zip` archives containing SKILL.md skill folders (UI uses automatic overwrite for a simpler flow).
    - **Skill Deletion** — delete workspace-scoped skills from the UI (builtin skills are protected).
    - **ClaWHub Link** — quick-access button to open https://clawhub.ai/ for community skill discovery.
- **Skills REST API** (`/api/skills`)
    - `GET /api/skills` — list all skills with metadata, availability, and pinned status.
    - `POST /api/skills/pin` — update the always-active pinned skills list.
    - `DELETE /api/skills/{name}` — remove a workspace skill.
    - `POST /api/skills/import` — multipart zip upload with conflict policy and dry-run mode.
- **Config: `pinned_skills` & `max_pinned_skills`**
    - New fields in `agents.defaults` for persistent always-active skill configuration.
    - Improved import compatibility for common zip layouts, including `SKILL.md` at archive root.

### Changed
- **Settings Redesign — Vertical Sidebar**
    - Settings modal redesigned from horizontal tabs to a vertical sidebar layout (9 sections: Agent, Provider, Tools, MCP, Gateway, Channels, Skills, OAuth, Update).
    - Last active tab is persisted in localStorage.
    - Responsive: sidebar collapses to horizontal icon strip at ≤700px viewport.
    - Modal enlarged to 880×700px to accommodate the new layout.

## [0.0.21] - 2026-04-10

### Added
- **DNS Rebinding Protection**
    - New `resolve_and_pin()` function in `security/network.py` that resolves a URL, validates all IPs, and returns pinned addresses to prevent DNS rebinding attacks (TOCTOU between validation and fetch).
    - Refactored internal helpers (`_resolve_all_ips`, `_check_ips`) shared by all validation entry points.
    - `validate_resolved_url()` now fully re-resolves hostnames on redirect instead of only checking IP literals.
- **Opt-In Per-Sender Rate Limiting**
    - `MessageBus` now supports `rate_limit_per_minute` (default `0` = disabled) using a sliding-window counter per sender.
    - New `gateway.rate_limit_per_minute` config field — set to e.g. `60` to cap inbound messages per sender. Disabled by default to preserve user freedom.
    - Exceeding the limit silently drops the message with a warning log.
- **WhatsApp Bridge Security Warning**
    - Logs a warning at startup if the WhatsApp bridge URL is not on localhost, since `bridge_token` is transmitted in cleartext over the WebSocket.
- **SECURITY.md**
    - Complete security policy: supported versions, responsible disclosure process (email + GitHub Security Advisories), response timeline, security architecture overview.

### Changed
- **npm Audit Already Implemented** — Confirmed and documented that `_audit_npm` was already wired in `install_audit.py` for npm/yarn/pnpm commands, parsing the npm audit v2+ JSON format. No code change needed — this was a documentation gap.

## [0.0.20] - 2026-04-10

### Added
- **Update Apply Endpoint**
    - New `POST /api/update/apply` endpoint to apply updates directly from the WebUI (backup personal files + pip upgrade + automatic restart).
- **OpenAI Codex OAuth in WebUI**
    - Codex login now works from the WebUI Settings → OAuth panel via `oauth-cli-kit` device flow, replacing the previous `501 Not Implemented` stub.
- **Documentation**
    - Added `shibaclaw web` mode to the deploy guide and useful commands table.
    - Added `memory` and `cron` skills to the skills README.

### Fixed
- **Runtime crash on server restart** — Added missing `import sys` in `system.py` that caused `NameError` when calling `/api/restart` or applying updates.
- **OAuth job state lost on restart** — Moved OAuth job tracking from fragile `globals()` dict to `AgentManager.oauth_jobs` instance attribute, preventing state loss during process lifecycle.
- **Fragile YAML frontmatter parsing in skills** — `get_skill_metadata()` now uses `yaml.safe_load` (PyYAML) for robust parsing of skill frontmatter, with automatic fallback to the previous line-by-line parser if PyYAML is unavailable.

### Changed
- **Dependencies** — Added `pyyaml>=6.0` as an explicit dependency for reliable skill metadata parsing.

## [0.0.19] - 2026-04-09

### Added
- **Agent Settings UI**
    - Model input field now has history tracking and auto-completion from previously used models.
    - Provider input field changed to a dropdown showing only configured providers (API key, local base URL, or OAuth), defaulting to "auto".
- **Audio Messaging Support (STT & TTS)**
    - Integrated multi-provider Speech-to-Text (STT) pipeline using OpenAI-compatible APIs (e.g., Groq/Whisper).
    - Browser-native Text-to-Speech (TTS) for agent responses with automatic markdown/code cleaning.
    - Automatic Voice Activity Detection (VAD) with silence threshold and duration settings.
- **WebUI Enhancements**
    - High-quality visual feedback for voice recording with pulse animation on the microphone button.
    - Transcription feedback: "Transcribing..." placeholder with shimmer effect during audio processing.
    - Dedicated "Voice & Audio" section in Agent Settings to configure provider URL, API key, and model.
    - TTS user preference persistence via `localStorage`.
- **Backend Improvements**
    - New `AudioConfig` schema for central management of speech settings.
    - Refactored `transcribe_audio` Socket.IO event handler for better performance and reliability.

### Changed
- **UI Refinements**
    - Improved chat input bar aesthetics: microphone and attachment (clip) buttons are now closer and visually aligned.
    - Text-to-Speech (Bot Voice) now defaults to "off" for a cleaner initial experience.

### Fixed
- **Code Hygiene**
    - Removed unused properties and redundant comments in speech and socket modules.
    - Refactored backend imports and improved error handling for transcription failures.

## [0.0.17] - 2026-04-08

### Added
- **WebUI Server Module**
    - New standalone `server.py` with `create_app()` / `run_server()` for cleaner separation of server lifecycle from API routes.
    - Automatic agent initialization, skill sync, and cron startup on server boot (background tasks).
    - Update check on startup with non-blocking notification.

### Changed
- **Architecture: Frontend Modularization**
    - `app.js` (3,289 lines) split into 8 focused modules in `static/js/`: `state.js`, `auth.js`, `utils.js`, `api_socket.js`, `chat.js`, `files.js`, `ui_panels.js`, `main.js`.
    - `index.css` (3,293 lines) split into 9 thematic stylesheets in `static/css/`: `vars.css`, `sidebar.css`, `chat.css`, `responsive.css`, `panels.css`, `modals.css`, `modals_responsive.css`, `login.css`, `components.css`. Entry `index.css` now uses `@import` directives.
    - index.html updated to load the new JS modules in dependency order.
- **Architecture: Backend Modularization**
    - `api.py` (1,038 lines) refactored: route handlers extracted into `shibaclaw/webui/routers/` package with 10 focused modules (`auth.py`, `sessions.py`, `settings.py`, `fs.py`, `gateway.py`, `heartbeat.py`, `oauth.py`, `cron.py`, `system.py`, `onboard.py`).
    - Shared helpers (`_gateway_request`, `_deep_merge`, `_redact_secrets`, `_resolve_workspace_path`, context caches) moved to new `shibaclaw/webui/utils.py` to prevent circular imports.
    - `api.py` now re-exports all route handlers for backward compatibility with `server.py`.
- **Codebase Cleanup**
    - Removed redundant comments and consolidated duplicated logic across `api.py`, `socket_io.py`, `loop.py`, and `app.js`.
    - Streamlined imports across backend modules.
    - Removed stale `.bak` backup files and `__pycache__` artifacts.
    - Replaced dangerous wildcard imports (`from utils import *`) with explicit named imports.

### Fixed
- **WebUI Visibility** — Fixed an issue where the interface would fail to render correctly or appear empty after a manual page refresh by ensuring correct script loading order and state initialization in the new modular architecture.
- **WebUI Context Endpoint** — Fixed `NameError: '_build_real_system_prompt' is not defined` caused by wildcard import ignoring underscore-prefixed private functions after the backend modularization.
- **Gateway Request** — Fixed truncated `_gateway_request()` function body in `utils.py` that was partially lost during extraction from `api.py`.
- **Config & Authentication** — Enhanced config loading, authentication handling, and socket.io integration in the standalone WebUI server module.

## [0.0.16] - 2026-04-08

### Changed
- **WebUI & API**
    - All `/api/file-get` APIs are now public and no longer require the authentication token in the query string. Attachment handling in WebUI and Socket.IO updated to remove the token from URLs.
    - Improved message ID handling in WebUI responses: `message_id` is now propagated if present in metadata.
    - Thread-safe settings synchronization in WebUI (`api_settings_post` now uses an asyncio lock).
    - Refactored restart functions (`_safe_argv`) to accept only flags and known subcommands, both in agent loop and WebUI.

### Fixed
- **Authentication**
    - Hardened: token comparison now only on Authorization header, no longer on query parameters.
    - `/api/file-get` added to `PUBLIC_PATHS` to avoid authentication errors on attachment downloads.
- **WebUI**
    - Fixed MCP settings display and save: the field is always `mcpServers` (camelCase) and a note is shown if only the example server is present.
    - Fixed attachment handling in WebUI and Socket.IO responses (token removed from URLs).
- **Config**
    - Automatic migration: MCP servers are now populated with all default fields if missing, and an example is added if the section is empty.
    - Onboarding plugins/channels is executed both on new creation and on loading existing config.
- **Agent loop**
    - Fixed regex for multiline media parsing in responses.
    - Corrected the position of the `MessageTool._sent_in_turn` check to avoid duplicate responses.

### Added
- **WebUI**
    - Asyncio lock for settings update.
    - Shared `_safe_argv` function between agent loop and WebUI for safe restart.
    - UI note for example MCP server.
    - Propagation of `message_id` in agent → WebUI responses.

## [0.0.15] - 2026-04-07

### Added
- **MCP Settings UI** — Added an MCP tab to the WebUI settings with support for configuring `tools.mcp_servers`, including stdio and HTTP/SSE server definitions.

### Fixed
- **Context window overrun** — Fixed token estimation undercounting that caused sessions to exceed the context window. `estimate_prompt_tokens()` now includes message roles, tool calls, and structural overhead (+4 tokens per message).
- **Compaction triggering too late** — Lowered the consolidation trigger threshold from 100% to 60% of context window, with a target of 40%, providing a safe margin before hitting the limit.
- **Telegram proxy saved as `{}` instead of `null`** — Fixed `_deep_merge` in WebUI API to correctly handle `None` values and empty dicts, preventing config corruption when the proxy field is cleared from Settings (#11).
- **WebUI gateway health check fallback** — Fixed intermittent `Gateway Down` status in Docker by centralizing gateway host resolution and ensuring the WebUI tries both local host and the Docker gateway hostname when the gateway is configured as `127.0.0.1`/`localhost`.
- **Heartbeat unreachable in standalone WebUI** — Fixed `heartbeat_status: gateway request failed` when running `shibaclaw web` without a separate gateway process. The WebUI now initializes its own `HeartbeatService` and falls back to it when the gateway is not available.
- **"Gateway Down" in standalone mode** — Fixed the WebUI health check reporting the gateway as down when running in bare-metal standalone mode. The health check now falls back to the local agent's status if no external gateway is found.

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
