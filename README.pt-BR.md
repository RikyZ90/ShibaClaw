<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>Agente de IA autohospedado, com foco em segurança e uma interface web integrada</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">Recursos</a> ·
  <a href="#quick-start">Início Rápido</a> ·
  <a href="#security">Segurança</a> ·
  <a href="#memory-system">Memória</a> ·
  <a href="#supported-providers">Provedores</a> ·
  <a href="#architecture">Arquitetura</a> ·
  <a href="#channels">Canais</a> ·
  <a href="#troubleshooting">Solução de Problemas</a>
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
> As notas de versão estão em [CHANGELOG.md](./CHANGELOG.md).

<details open>
<summary>📢 <b>Novidades — v0.9.11</b> (clique para expandir)</summary>

**Última versão (2026-07-22):**

- **Correção de vulnerabilidade de injeção de comandos no ExecTool** — Resolvida uma vulnerabilidade crítica de injeção de comandos (CWE-78) na execução de shell usando análise segura de argumentos com `shlex` e execução direta de processos (`create_subprocess_exec`).
- **Vulnerabilidades de segurança em dependências** — Resolvidas vulnerabilidades de segurança em dependências npm do bridge atualizando os overrides para `protobufjs` (v7.6.5) e `sharp` (v0.35.3).
- **Estabilidade do loop de agente e direcionamento** — Corrigidas falhas no comando `/update`, roteamento de sessões e emissão de eventos para mensagens ativas.
- **Estimativa de tokens na WebUI** — Corrigido o tratamento de tipos de argumentos no endpoint da API `estimate_prompt_tokens` ao passar listas de mensagens.
- **Dependências de Cloud RAG** — Corrigidos os limites de dependência do Cloud RAG e a configuração do modelo de embedding padrão.

Veja o [Changelog](./CHANGELOG.md) para o histórico completo de lançamentos.

</details>

---

ShibaClaw é um agente de IA autohospedado que você executa na sua própria máquina ou servidor: um motor Python com interface web integrada, suporte nativo a 28 provedores de modelos e 11 integrações de plataformas de chat (Discord, Telegram, Slack, WhatsApp, Matrix e mais). É construído em torno de três prioridades —— simplicidade, segurança e privacidade —— com defesas como auditoria CVE na instalação, encapsulamento de injeção de prompts e proteção SSRF integradas no motor central em vez de coladas como código externo.

<p align="center">
  <img src="assets/shibdemo.webp" width="480" alt="ShibaClaw Desktop Demo" style="margin-right: 12px; vertical-align: middle;">
  <img src="assets/shibmobiledemo.webp" width="188" alt="ShibaClaw Mobile Demo" style="vertical-align: middle;">
</p>

> [!NOTE]
> As notas de versão estão em [CHANGELOG.md](./CHANGELOG.md).

## Recursos

- **Núcleo com foco em segurança** —— cofre de credenciais criptografado, auditoria CVE na instalação, encapsulamento de injeção de prompts, proteção SSRF/DNS-rebinding
- **Memória de três níveis** —— memória de trabalho, semântica (FAISS) e procedimental, com aprendizado proativo e auto-compactação
- **28 provedores, SDKs nativos** —— OpenAI, Anthropic, Gemini, DeepSeek e mais, sem camada proxy LiteLLM
- **Web e móvel** —— exponha a WebUI na sua LAN e use o mesmo agente pelo celular
- **App de desktop Windows** —— lançador nativo com integração à bandeja do sistema
- **Pronto para MCP** —— conecte qualquer servidor MCP, ferramentas auto-registradas

## Início Rápido

**Requisitos:** Docker, ou Python 3.12+ para a rota pip. O instalador automático do Windows não precisa de nenhum dos dois —— traz um app de desktop pré-construído.

### Instalador automático (recomendado)

Um comando baixa a última versão, cria atalhos e abre a interface.

> [!TIP]
> Traga seu próprio modelo: conecte-se a endpoints locais (Ollama, LM Studio) ou use níveis gratuitos de API via OpenRouter para conversar a custo zero.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS:**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> No Windows, isso baixa o app de desktop pré-construído da última GitHub Release —— não requer Python, com atalhos na Área de Trabalho/Menú Iniciar e desinstalação limpa via Aplicativos e Recursos. No Linux/macOS o script instala via pip em ambiente virtual isolado.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # puxa do Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Abra **http://localhost:3000**, cole o token e siga o assistente de onboarding. Exponha `shibaclaw-web` na sua LAN (ex. via proxy reverso) e abra a mesma URL no celular para conversar no mobile.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # inicia WebUI + motor do agente em :3000
```

Abra **http://localhost:3000** e siga o assistente.  
Prefere a CLI? `shibaclaw onboard` roda a mesma configuração guiada no terminal.

---

## Segurança

Defesas que normalmente estão espalhadas no código de cola do app ou em proxies externos são entregues no núcleo do ShibaClaw, ativadas por padrão.

| Camada | O que faz |
|---|---|
| Auditoria na instalação | Audita `pip` e `npm` antes de executar —— bloqueia CVE críticos/altos |
| Encapsulamento de injeção de prompts e pré-varredura | Envolve cada resultado de ferramenta em um limite `<tool_output_...>` aleatório; pré-varredura regex de jailbreaks |
| Endurecimento de shell | 20+ padrões de negação, normalização de escape, detecção de URL interna |
| Motor local-first | Emulador de comandos nativo (`ls`, `cat`) evita overhead de subprocesso; fallback `tiktoken` offline |
| Guarda de rede | Filtragem SSRF, revalidação de redirecionamento, resolução segura contra DNS-rebinding |
| Sandbox de workspace | Ferramentas de arquivo e explorador bloqueados ao workspace configurado |
| Controle de acesso | Auth Bearer token, verificações de tempo constante, listas brancas de canais, rate limiting opcional |
| Motor distribuído | UI (~128 MB) desacoplada do cérebro do agente (~256 MB+) |

Cada resultado de ferramenta é envolvido em um limite gerado dinamicamente com um nonce aleatório (ex. `<tool_output_a1b2c3d4>`), então um atacante não pode fechar prematuramente a tag nem injetar instruções de sistema falsas através da saída da ferramenta —— o limite é imprevisível por sessão.

> [!TIP]
> Esse mecanismo de encapsulamento também está disponível de forma independente como [Muzzle](https://github.com/RikyZ90/Muzzle), uma biblioteca Python sem dependências que você pode inserir em qualquer framework de agentes (LangChain, LlamaIndex, CrewAI, AutoGen ou um loop personalizado).

## Sistema de Memória

ShibaClaw usa uma arquitetura de memória de três níveis:

1. **Memória de trabalho** (por sessão) —— contexto rolante com resumo automático e truncamento consciente de tokens
2. **Memória semântica** (entre sessões) —— armazenamento vetorial FAISS + sentence-transformers com extração automática de fatos e busca semântica
3. **Memória procedimental** (habilidades e automações) —— fluxos de trabalho aprendidos salvos como habilidades reutilizáveis, além de agendamentos tipo cron

O aprendizado proativo extrai e armazena fatos úteis automaticamente, a auto-compactação evita o estouro de contexto, e as sessões são salvas como JSONL somente anexo para um registro rápido e amigável à cache.

## MCP e Integrações

ShibaClaw fala o Model Context Protocol, então pode se conectar a qualquer servidor compatível com MCP —— Google Drive, Slack, GitHub, PostgreSQL e mais —— sem alterar o código central. Configure os servidores no painel de Configurações.

Para ferramentas SaaS populares (Gmail, Google Drive, Slack, GitHub, Outlook...), o ShibaClaw integra com [Klavis](https://klavis.ai): uma única API key te dá conexões OAuth de um clique em vez de registrar manualmente um app OAuth com cada provedor. Os apps conectados são auto-registrados como servidores MCP na sessão ativa.

## Provedores Suportados

ShibaClaw usa SDKs nativos —— sem proxy LiteLLM —— e resolve o provedor a partir do modelo selecionado ou de um ID de modelo com prefixo de provedor. Todos os catálogos de provedores configurados são mesclados em uma lista buscável na WebUI.

**Chave de API**

| Provedor | Variável de ambiente |
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

¹ Definir `GEMINI_API_KEY` é suficiente —— o endpoint compatível com OpenAI vem pré-configurado.

**Gateway / proxy** —— OpenRouter, AiHubMix, SiliconFlow, VolcEngine, BytePlus, auto-detectados por prefixo de chave ou `api_base`.

**Local** —— Ollama, LM Studio, llama.cpp, vLLM, ou qualquer endpoint compatível com OpenAI.

> [!NOTE]
> No Docker, `localhost` aponta para dentro do contêiner. Para alcançar um servidor local no host (LM Studio, Ollama), use `http://host.docker.internal:PORT` no Windows/macOS ou `http://172.17.0.1:PORT` no Linux nativo.

**OAuth**

| Provedor | Fluxo | Configuração |
|----------|------|-------|
| OpenRouter | Fluxo PKCE no navegador, armazena a API key retornada na config do provedor | Configurações WebUI |
| GitHub Copilot | Fluxo de dispositivo, atualização automática do token | `shibaclaw provider login github-copilot` ou Configurações WebUI |
| OpenAI Codex | Fluxo PKCE no navegador | `shibaclaw provider login openai-codex` ou Configurações WebUI |
| Google Gemini CLI | Fluxo PKCE no navegador, requer as variáveis `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` e `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET`. **Nota:** Integração de terceiros não oficial; o Google pode aplicar restrições de conta. Use uma conta separada se for uma preocupação. | Configurações WebUI |

Para o OpenRouter, o callback reutiliza por padrão a URL e a porta atuais da WebUI, então `http://localhost:3000` não é uma porta exclusiva de OAuth. Se você expõe a WebUI atrás de um proxy reverso ou precisa de uma origem de callback pública diferente, defina `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` antes de iniciar o servidor.

### 💡 Pro Tip: Modelos Econômicos e Premium

O ShibaClaw tem desempenho excepcional mesmo sem gastar com API:
- **Modelos gratuitos/abertos:** Recomendamos usar o **OpenRouter** para acessar modelos gratuitos poderosos como `nvidia/nemotron-3-super-120b-a12b:free` ou `gemma-4-31b-it:free`.
- **Premium ilimitado:** Se você usa a integração OAuth do **GitHub Copilot**, ganha acesso a modelos premium como `raptor` (`oswe-vscode-prime`) a custo zero, dando a você solicitações ilimitadas.

***

## 📊 Como o ShibaClaw se Compara (Segurança Primeiro)

> [!NOTE]
> O callback OAuth do OpenRouter reutiliza a URL e a porta atuais da WebUI. Atrás de um proxy reverso, defina `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL` antes de iniciar o servidor.

Para uso a custo zero, tanto o nível gratuito do OpenRouter (ex. `nvidia/nemotron-3-super-120b-a12b:free`) quanto a integração OAuth do GitHub Copilot (acesso ilimitado a modelos como `raptor`) funcionam bem sem uma API key paga.

## Arquitetura

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| Serviço | Papel | Porta padrão |
|---|---|---|
| `shibaclaw-gateway` | Loop central do agente, barramento de mensagens, integrações de canais | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket), serviço de automações | 3000 |

Ambos compartilham o volume `~/.shibaclaw/` (config, workspace, memória, jobs de automação, cache de mídia). `shibaclaw web` sozinho executa agente + WebUI + automações em um único processo, sem contêiner gateway.

**Stack** —— Uvicorn/Starlette (ASGI), WebSocket nativo, frontend JS vanilla + Marked.js + Highlight.js, sessões JSONL somente anexo.

**Uso de recursos** —— ~120 MB ocioso / ~350 MB pico por componente (gateway, WebUI). Docker Compose limita cada contêiner a 512 MB / 256 MB reservados; a saída de ferramentas é transmitida com buffers limitados para que comandos longos não estourem a memória.

## Referência CLI

```bash
shibaclaw web               # Inicia a WebUI (agente + automações em processo)
shibaclaw gateway           # Inicia apenas o gateway (para split Docker)
shibaclaw onboard           # Assistente de configuração inicial via CLI
shibaclaw agent -m "Hello"  # Mensagem única via terminal
shibaclaw agent             # REPL interativo com histórico
shibaclaw status            # Provedor, workspace, saúde OAuth
shibaclaw print-token       # Mostra o token de autenticação WebUI
shibaclaw channels status   # Lista os canais habilitados
shibaclaw provider login <p># Login OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Abre o app de desktop Windows
```

## Canais

| Canal | Tipo | Notas |
|---|---|---|
| WebUI | Integrado | Interface principal, acesso completo |
| Discord | Bot | Embeds ricos, comandos slash, anexos |
| Telegram | Bot | Teclados inline, mídia, markup de resposta |
| WhatsApp | Plugin | Via WhatsApp Web |
| Slack | Bot | Block kit, threads, menções de app |
| DingTalk | Bot | Mensageria empresarial |
| Feishu/Lark | Bot | Cards ricos, elementos interativos |
| QQ | Bot | Mensagens de grupo e privadas |
| WeCom | Bot | Comunicação corporativa |
| Matrix | Bot | Descentralizado, criptografia E2E |
| MoChat | Bot | Ecossistema WeChat |

Cada canal é configurado independentemente nas Configurações WebUI e suporta recarga a quente em mudanças de configuração.

## Sistema de Plugins

ShibaClaw descobre plugins via entry points do Python:

- **Plugins de canal** —— implementam `BaseChannel`, descobríveis via `shibaclaw.integrations`
- **Plugins TTS** —— implementam `BaseTTS`, descobríveis via `shibaclaw.tts`

Embutidos: `shibaclaw-channel-whatsapp` (WhatsApp Web) e `shibaclaw-tts-supertonic` (síntese de voz ONNX gratuita e offline, 31 idiomas). Instale ou remova plugins nas Configurações WebUI > Plugins, com recarga a quente e fixação de versão. Para criar o seu, veja [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).

## Texto em Voz (TTS)

O motor Supertonic embutido roda offline sobre ONNX (sem dependência de PyTorch, só CPU), suporta 31 idiomas com perfis de voz `F1`/`M1` e velocidade ajustável, e reproduz via widget no navegador. Habilite em Configurações WebUI > TTS.

## Automação e Agendamento

Tarefas em segundo plano rodam em agendamentos tipo cron ou gatilhos de eventos (mensagens, webhooks, eventos do sistema), em sessões isoladas que não poluem o histórico de chat. Gerencie, monitore e veja logs no painel de Automações; os jobs persistem entre reinicializações via armazenamento JSONL.

## Base de Conhecimento (RAG)

Geração aumentada por recuperação local e com foco em privacidade: organize documentos em coleções nomeadas (PDF, CSV, HTML, TXT, Markdown), envie via arrastar e soltar, e busque com um índice FAISS sobre embeddings `all-MiniLM-L6-v2`. O agente pode chamar `knowledge_search` durante a conversa, ou apontar para uma coleção específica com `@kb:name`. É uma dependência opcional —— instale com `pip install shibaclaw[rag]`.

## Solução de Problemas

| Problema | Tente |
|---|---|
| Verificação geral de estado | `shibaclaw status` |
| Logs de contêiner | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI não conecta | Verifique o token com `shibaclaw print-token`, confira o bind da porta |
| Erros de provedor | `shibaclaw status` mostra a API key e o estado OAuth |
| Falha de login após atualizar do v0.9.5 | Execute `shibaclaw reset-admin` |
| Política de segurança | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
Veja <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> para contribuir e <a href="./CHANGELOG.md">CHANGELOG.md</a> para o histórico de lançamentos.
</p>
