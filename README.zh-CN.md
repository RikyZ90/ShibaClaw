<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>自托管的、安全优先的 AI 智能体，内置 Web UI</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">功能</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#security">安全</a> ·
  <a href="#memory-system">记忆</a> ·
  <a href="#supported-providers">提供商</a> ·
  <a href="#architecture">架构</a> ·
  <a href="#channels">渠道</a> ·
  <a href="#troubleshooting">故障排查</a>
</p>

<p align="center">
  🌐 <a href="./README.zh-CN.md">简体中文</a> ·
  <a href="./README.es.md">Español</a> ·
  <a href="./README.pt-BR.md">Português (BR)</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.de.md">Deutsch</a> ·
  <a href="./README.fr.md">Français</a>
</p>

---

> [!NOTE]
> 发布说明见 [CHANGELOG.md](./CHANGELOG.md)。

<details open>
<summary>📢 <b>最新动态 — v0.9.9</b>（点击展开）</summary>

**最新版本（2026-07-19）：**

- **渠道配置下拉框** —— 渠道配置中的 `group_policy` 字段现在在 WebUI 中使用下拉选择器，带来更好的使用体验。
- **现代 Linux 上的外部包安装（PEP 668）** —— 在 pip 操作遇到 `externally-managed-environment` 错误时自动注入 `--break-system-packages`。
- **子智能体会话密钥传递** —— 为子智能体元数据添加 `session_key`，以便在并行执行时保持正确的上下文。
- **RAG 软重启导入错误** —— 修复安装本地 RAG 插件后软重启时动态 RAG 导入的 `NameError`。
- **瞬时 LLM 错误处理** —— 将 `'empty choices'` 加入瞬时错误标记，以便在收到空 API 响应时自动重试。
- **密钥更新时的渠道热重载** —— 修复更新密钥时渠道热重载未触发的问题。
- **主动学习工具选择** —— 优雅处理主动学习中不支持的 `tool_choice` 参数。
- **移除 Base64 工具输出编码** —— 移除了工具输出的 Base64 编码逻辑，以简化处理流程。

**未发布（进行中）：**

- **Telegram AI / 智能体 Bot API 功能** —— 访客模式（`answerGuestQuery`）、通过 `sendMessageDraft` 的私聊流式输出、机器人间消息、Business / Chat Automation 更新，以及 Managed Bot 更新追踪。详见 `docs/TELEGRAM_AI_FEATURES.md`。
- **Telegram 配置标志** —— `streaming`、`guestMode`、`allowBotMessages`、`businessEnabled`、`managedBotsEnabled`。

完整版本历史请查看 [CHANGELOG.md](./CHANGELOG.md)。

</details>

---

ShibaClaw 是一个自托管的 AI 智能体，可在你自己的机器或服务器上运行：一个 Python 引擎，内置 Web UI，原生支持 28 家模型提供商，并集成了 11 个聊天平台（Discord、Telegram、Slack、WhatsApp、Matrix 等）。它围绕三大优先事项构建 —— 简洁、安全与隐私 —— 防御能力（如安装时 CVE 审计、提示注入包裹、SSRF 防护）内置于核心引擎，而非作为外部胶水代码附加。

<p align="center">
  <img src="assets/webui_chat.webp" width="640" alt="ShibaClaw WebUI chat">
</p>

> [!NOTE]
> 发布说明见 [CHANGELOG.md](./CHANGELOG.md)。

## 功能

- **安全优先核心** —— 加密凭据保险库、安装时 CVE 审计、提示注入包裹、SSRF/DNS 重绑定防护
- **三级记忆** —— 工作记忆、语义记忆（FAISS）和程序性记忆，具备主动学习与自动压缩
- **28 家提供商，原生 SDK** —— OpenAI、Anthropic、Gemini、DeepSeek 等，无 LiteLLM 代理层
- **Web 与移动端** —— 将 WebUI 暴露到局域网，即可在手机上使用同一个智能体
- **Windows 桌面应用** —— 带系统托盘集成的原生启动器
- **MCP 就绪** —— 连接任意 MCP 服务器，工具自动注册

## 快速开始

**要求：** Docker，或通过 pip 方式需要 Python 3.12+。Windows 自动安装程序两者都不需要 —— 它附带预构建的桌面应用。

### 自动安装程序（推荐）

一条命令即可下载最新版本、创建快捷方式并启动界面。

> [!TIP]
> 自带模型：连接本地端点（Ollama、LM Studio）或通过 OpenRouter 使用免费 API 额度，零成本开始聊天。

**Windows（PowerShell）：**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS：**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> 在 Windows 上，此命令会从最新的 GitHub Release 下载预构建的桌面应用 —— 无需 Python，并会在桌面/开始菜单创建快捷方式，可通过“应用和功能”干净卸载。在 Linux/macOS 上，脚本会在隔离的虚拟环境中通过 pip 安装。

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # 从 Docker Hub 拉取
docker exec -it shibaclaw-gateway shibaclaw print-token
```

打开 `http://localhost:3000`，粘贴令牌，并按照引导向导操作。将 `shibaclaw-web` 暴露到你的局域网（例如通过反向代理），即可从手机访问。

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # 在 :3000 启动 WebUI + 智能体引擎
```

打开 `http://localhost:3000` 并按照引导向导操作，或运行 `shibaclaw onboard` 执行相同设置的 CLI 版本。

---

## 安全

通常分散在应用胶水代码或外部代理中的防御能力，在 ShibaClaw 核心中默认开启、直接提供。

| 层级 | 作用 |
|---|---|
| 安装时审计 | 在执行前审计 `pip` 和 `npm` —— 拦截严重/高危 CVE |
| 提示注入包裹与预扫描 | 用随机生成的 `<tool_output_...>` 边界包裹每个工具结果；用正则预扫描越狱内容 |
| Shell 加固 | 20+ 拒绝模式、转义规范化、内部 URL 检测 |
| 本地优先引擎 | 原生命令模拟器（`ls`、`cat`）绕过子进程开销；离线 `tiktoken` 回退 |
| 网络防护 | SSRF 过滤、重定向重新验证、DNS 重绑定安全解析 |
| 工作区沙箱 | 文件工具与文件浏览器锁定在配置的工作区内 |
| 访问控制 | Bearer 令牌认证、恒定时间校验、渠道白名单、可选速率限制 |
| 分布式引擎 | UI（约 128 MB）与智能体大脑（约 256 MB+）解耦 |

每个工具结果都被包裹在带有随机 nonce 的动态生成边界中（例如 `<tool_output_a1b2c3d4>`），因此攻击者无法提前关闭标签或通过工具输出注入伪造的系统指令 —— 该边界在每个会话中都是不可预测的。

> [!TIP]
> 此包裹机制也可作为独立的 [Muzzle](https://github.com/RikyZ90/Muzzle) 使用，这是一个零依赖的 Python 库，可放入任何智能体框架（LangChain、LlamaIndex、CrewAI、AutoGen 或自定义循环）中。

## 记忆系统

ShibaClaw 采用三级记忆架构：

1. **工作记忆**（每会话）—— 滚动上下文，具备自动摘要与令牌感知截断
2. **语义记忆**（跨会话）—— FAISS + sentence-transformers 向量存储，具备自动事实提取与语义搜索
3. **程序性记忆**（技能与自动化）—— 以可复用技能保存的学习工作流，以及类 cron 的调度

主动学习会自动提取并存储有用的事实，自动压缩可防止上下文溢出，会话以仅追加的 JSONL 形式存储，便于快速、缓存友好的日志记录。

## MCP 与集成

ShibaClaw 支持 Model Context Protocol，因此无需修改核心代码即可连接任意兼容 MCP 的服务器 —— Google Drive、Slack、GitHub、PostgreSQL 等。可从设置面板配置服务器。

对于热门 SaaS 工具（Gmail、Google Drive、Slack、GitHub、Outlook……），ShibaClaw 集成了 [Klavis](https://klavis.ai)：一个 API 密钥即可获得一键式 OAuth 连接，而无需为每个提供商手动注册 OAuth 应用。已连接的应用会在活动会话中自动注册为 MCP 服务器。

## 支持的提供商

ShibaClaw 使用原生 SDK —— 无 LiteLLM 代理 —— 并从所选模型或带提供商前缀的模型 ID 解析提供商。所有已配置的提供商目录会在 WebUI 中合并为一个可搜索列表。

**API 密钥**

| 提供商 | 环境变量 |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Google Gemini | `GEMINI_API_KEY`¹ |
| Groq | `GROQ_API_KEY` |
| Moonshot | `MOONSHOT_API_KEY` |
| MiniMax | `MINIMAX_API_KEY` |
| Zhipu AI | `ZAI_API_KEY` |
| DashScope | `DASHSCOPE_API_KEY` |

¹ 设置 `GEMINI_API_KEY` 即可 —— OpenAI 兼容端点已预配置。

**网关 / 代理** —— OpenRouter、AiHubMix、SiliconFlow、VolcEngine、BytePlus，通过密钥前缀或 `api_base` 自动检测。

**本地** —— Ollama、LM Studio、llama.cpp、vLLM，或任意 OpenAI 兼容端点。

> [!NOTE]
> 在 Docker 中，`localhost` 指向容器内部。要访问主机上的本地服务器（LM Studio、Ollama），在 Windows/macOS 上使用 `http://host.docker.internal:PORT`，在原生 Linux 上使用 `http://172.17.0.1:PORT`。

**OAuth**

| 提供商 | 流程 | 设置 |
|----------|------|-------|
| OpenRouter | PKCE 浏览器流程，将返回的 API 密钥存入提供商配置 | WebUI 设置 |
| GitHub Copilot | 设备流程，自动刷新令牌 | `shibaclaw provider login github-copilot` 或 WebUI 设置 |
| OpenAI Codex | PKCE 浏览器流程 | `shibaclaw provider login openai-codex` 或 WebUI 设置 |
| Google Gemini CLI | PKCE 浏览器流程，需要 `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` 和 `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET` 环境变量。**注意：** 非官方第三方集成，Google 可能施加账户限制。如有顾虑，请使用单独的账户。 | WebUI 设置 |

对于 OpenRouter，回调默认复用当前 WebUI 的 URL 和端口，因此 `http://localhost:3000` 并非专用的 OAuth 端口。如果你在反向代理后暴露 WebUI，或需要不同的公共回调来源，请在启动服务器前设置 `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host`。

### 💡 专业提示：高性价比与高级模型

ShibaClaw 即使不花费昂贵的 API 费用也能表现出色：
- **免费/开放模型：** 我们强烈推荐使用 **OpenRouter** 访问强大的免费模型，如 `nvidia/nemotron-3-super-120b-a12b:free` 或 `gemma-4-31b-it:free`。
- **无限高级模型：** 如果你使用 **GitHub Copilot** OAuth 集成，即可零额外成本访问 `raptor`（`oswe-vscode-prime`）等高级模型， effectively 获得无限请求。

***

## 📊 ShibaClaw 对比（安全优先）

> [!NOTE]
> OpenRouter 的 OAuth 回调复用当前 WebUI 的 URL 和端口。在反向代理后，请在启动服务器前设置 `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL`。

对于零成本使用，OpenRouter 的免费额度（例如 `nvidia/nemotron-3-super-120b-a12b:free`）和 GitHub Copilot OAuth 集成（无限访问 `raptor` 等模型）都无需付费 API 密钥即可良好运行。

## 架构

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| 服务 | 角色 | 默认端口 |
|---|---|---|
| `shibaclaw-gateway` | 核心智能体循环、消息总线、渠道集成 | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI（Starlette + WebSocket）、自动化服务 | 3000 |

两者共享 `~/.shibaclaw/` 卷（配置、工作区、记忆、自动化任务、媒体缓存）。单独运行 `shibaclaw web` 会在单一进程中启动智能体 + WebUI + 自动化，无需网关容器。

**技术栈** —— Uvicorn/Starlette（ASGI）、原生 WebSocket、原生 JS + Marked.js + Highlight.js 前端、JSONL 仅追加会话。

**资源占用** —— 每个组件（网关、WebUI）空闲约 120 MB / 峰值约 350 MB。Docker Compose 将每个容器上限设为 512 MB / 预留 256 MB；工具输出以有界缓冲区流式传输，因此长时间运行的命令不会撑爆内存。

## CLI 参考

```bash
shibaclaw web               # 启动 WebUI（进程内运行智能体 + 自动化）
shibaclaw gateway           # 仅启动网关（用于 Docker 拆分）
shibaclaw onboard           # 基于 CLI 的首次设置向导
shibaclaw agent -m "Hello"  # 通过终端发送一次性消息
shibaclaw agent             # 带历史记录的交互式 REPL
shibaclaw status            # 提供商、工作区、OAuth 健康检查
shibaclaw print-token       # 显示 WebUI 认证令牌
shibaclaw channels status   # 列出已启用的渠道
shibaclaw provider login <p># OAuth 登录（github-copilot、openai-codex）
shibaclaw desktop           # 启动 Windows 桌面应用
```

## 渠道

| 渠道 | 类型 | 说明 |
|---|---|---|
| WebUI | 内置 | 主界面，完整功能访问 |
| Discord | 机器人 | 富嵌入、斜杠命令、附件 |
| Telegram | 机器人 | 内联键盘、媒体、回复标记 |
| WhatsApp | 插件 | 通过 WhatsApp Web |
| Slack | 机器人 | Block kit、线程、应用提及 |
| DingTalk | 机器人 | 企业消息 |
| Feishu/Lark | 机器人 | 富卡片、交互元素 |
| QQ | 机器人 | 群聊与私聊消息 |
| WeCom | 机器人 | 职场沟通 |
| Matrix | 机器人 | 去中心化、端到端加密 |
| MoChat | 机器人 | 微信生态 |

每个渠道在 WebUI 设置中独立配置，并支持配置更改时的热重载。

## 插件系统

ShibaClaw 通过 Python 入口点发现插件：

- **渠道插件** —— 实现 `BaseChannel`，可通过 `shibaclaw.integrations` 发现
- **TTS 插件** —— 实现 `BaseTTS`，可通过 `shibaclaw.tts` 发现

内置：`shibaclaw-channel-whatsapp`（WhatsApp Web）和 `shibaclaw-tts-supertonic`（免费、离线 ONNX 语音合成，31 种语言）。可从 WebUI 设置 > 插件中安装或移除插件，支持热重载和版本固定。要构建你自己的插件，请参阅 [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md)。

## 文本转语音

内置的 Supertonic 引擎在 ONNX 上离线运行（无 PyTorch 依赖，仅 CPU），支持 31 种语言，具备 `F1`/`M1` 语音配置和可调语速，并通过浏览器内组件播放。在 WebUI 设置 > TTS 中启用。

## 自动化与调度

后台任务按类 cron 的调度或事件触发器（消息、Webhook、系统事件）运行，在隔离的会话中执行，不会污染聊天历史。可从自动化面板管理、监控和查看日志；任务通过 JSONL 存储跨重启持久化。

## 知识库（RAG）

本地、隐私优先的检索增强生成：将文档组织到命名集合中（PDF、CSV、HTML、TXT、Markdown），通过拖放上传，并使用基于 `all-MiniLM-L6-v2` 嵌入的 FAISS 索引进行搜索。智能体可在对话中调用 `knowledge_search`，或使用 `@kb:name` 定位特定集合。它是可选依赖 —— 通过 `pip install shibaclaw[rag]` 安装。

## 故障排查

| 问题 | 尝试 |
|---|---|
| 常规状态检查 | `shibaclaw status` |
| 容器日志 | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI 无法连接 | 用 `shibaclaw print-token` 检查令牌，验证端口绑定 |
| 提供商错误 | `shibaclaw status` 显示 API 密钥和 OAuth 状态 |
| 从 v0.9.5 升级后登录失败 | 运行 `shibaclaw reset-admin` |
| 安全策略 | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
查看 <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> 参与贡献，查看 <a href="./CHANGELOG.md">CHANGELOG.md</a> 了解发布历史。
</p>
