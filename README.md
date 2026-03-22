<p align="center">
  <img src="shibaclaw_logo.jpg" width="800" alt="...">
</p>

# 🐕‍🦺 ShibaClaw

ShibaClaw is a loyal, intelligent, and lightweight personal AI assistant framework. Built to serve and protect your digital workspace.

## 🐾 Key Features
- **Fast & Faithful**: Minimal startup time and dependencies.
- **Multi-channel**: Support for Telegram, Discord, Slack, WhatsApp, and more.
- **Always Alert**: Built-in cron and heartbeat task scheduler.
- 🧩 **Skills Registry**: Modular and extensible skill system with native ClawhHub marketplace support
- ⚡ **Parallel Multi-Agent Execution**: A built-in fan-out orchestration model that spawns and coordinates specialized sub-agents concurrently for faster, scalable task resolution
- **Advanced Thinking**: Support for OpenAI, Azure, LiteLLM, and deep-reasoning thinkers.
- **🛡️ Built-in Security**: Protected against Indirect Prompt Injection via structural wrapping and strict security policies.

## 🔒 Loyal Only to You
Like the most devoted guard dog, ShibaClaw is trained to obey only its master. Thanks to its advanced **Tool Output Wrapping** system, the framework is hardened against *Indirect Prompt Injection* attacks. It treats external data from websites, files, or tools as literal information—never as new instructions. Your orders are final; to ShibaClaw, external noise is just a squirrel 🐿️.

## 🐾 Quick Start

Ready to hunt? Choose your path:

### 🐋 Docker (Recommended)
```bash
docker compose up -d
docker exec -it shibaclaw-gateway shibaclaw onboard --wizard
```

### 🐍 Bare Metal
```bash
pip install .
shibaclaw onboard --wizard
shibaclaw agent -m "Hello Shiba!"
```

See the full [Easy Deploy Guide](./deploy_guide.md) for detailed instructions and troubleshooting.

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

OAuth providers require a dedicated login step.

Requirements:
- `pip install oauth-cli-kit` (for OpenAI Codex)

Commands:
- `shibaclaw provider login openai-codex`
- `shibaclaw provider login github-copilot`


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
- `bridge/` - WhatsApp connectivity module
- `tests/` - verification and tests
- `assets/` - project branding and visuals

ShibaClaw: Smart. Loyal. Powerful. 🐕

## Credits & Acknowledgements

This project was inspired by Nanobot❤️(https://github.com/HKUDS/nanobot)
by HKUDS, released under the MIT License.
