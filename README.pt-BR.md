<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw 🐕</h1>
<h3 align="center">O agente de IA que <b>simplesmente funciona</b> — com segurança, privacidade e sem babá.</h3>

> Tradução de [README.md](./README.md) — pode não estar atualizada (sincronizado a v0.9.4).

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28 Provedores · 11 Canais de Chat · WebUI Embutida · Núcleo com Segurança Primeiro · Pronto para MCP</b>
</p>

<h3 align="center">Construído sobre três pilares: <b>Simplicidade · Segurança · Privacidade</b></h3>

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
> If you experience login issues with the WebUI post-update, please run `shibaclaw reset-admin` in your terminal/console to restore access.

<details open>
<summary>📢 <b>Última versão: v0.9.6</b> — Clique para ver as novidades</summary>

- **⚠️ Aviso de login na WebUI pós-atualização** — Adicionada caixa de aviso na WebUI (modal Changelog e painel Update) para executar `shibaclaw reset-admin` no seu terminal caso ocorram problemas de login pós-atualização.
- **⬆️ Atualização de versão** — Atualizados todos os arquivos de configuração e do projeto para `v0.9.6`.

Veja o [Changelog](./CHANGELOG.md) para o histórico completo de lançamentos.

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ Início Rápido

### 🚀 Instalador Automático (Recomendado)

A forma mais fácil de começar. Um comando baixa a última versão, cria atalhos e abre a interface.

**Traga seu próprio modelo**: Conecte-se a endpoints locais (Ollama, LM Studio) ou use níveis gratuitos de API via OpenRouter para conversar a custo zero.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **Nota**: No Windows, isso baixa o app de desktop pré-construído da última GitHub Release — não requer Python. Atalhos na Área de Trabalho e Menu Iniciar são criados automaticamente, e o app aparece em Aplicativos e Recursos para desinstalação limpa. No Linux/macOS, o script instala via pip em ambiente virtual isolado.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # puxa do Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Abra **http://localhost:3000**, cole o token e siga o assistente.

Exponha `shibaclaw-web` na sua LAN (ex. via proxy reverso) e abra a mesma URL no celular para conversar no mobile.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # inicia WebUI + motor do agente em :3000
```

Abra **http://localhost:3000** e siga o assistente.  
Prefere a CLI? `shibaclaw onboard` roda a mesma configuração guiada no terminal.

***

## ✨ Tudo em um Agente

<table>
<tr>
<td align="center" width="33%">

### 🛡️ Segurança Primeiro
Auditoria CVE, envelopamento de<br>injeção de prompt, guarda SSRF — <b>ativado por padrão</b>

</td>
<td align="center" width="33%">

### 🧠 Memória Inteligente
Sistema de 3 níveis com aprendizado<br>proativo e auto-compactação

</td>
<td align="center" width="33%">

### 🌐 28 Provedores
SDKs nativos, sem proxy LiteLLM<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Web e Mobile
Exponha a WebUI na sua LAN e<br>use o mesmo agente no celular

</td>
<td align="center" width="33%">

### 🖥️ App de Desktop
Lançador nativo Windows com bandeja,<br>combinação perfeita com a WebUI

</td>
<td align="center" width="33%">

### 🔌 Pronto para MCP
Conecte qualquer servidor MCP,<br>ferramentas auto-registradas

</td>
</tr>
</table>

***

## Por que ShibaClaw? Simplesmente funciona. 🐕

> **Cansado de agentes que precisam mais babá que o seu próprio trabalho?**  
> ShibaClaw é construído em torno de um princípio: <b>simplesmente funciona</b> — com segurança, confiabilidade e sem manutenção constante.

A maioria dos frameworks de agentes de IA trata a segurança como pensamento tardio, deixa você brigando com compatibilidade de provedores ou força a babá de configurações. ShibaClaw muda o jogo: a segurança não é parafusada, é <b>a fundação</b>.

O que torna ShibaClaw diferente:
- **Camadas de segurança no núcleo** — auditoria CVE na instalação, envelopamento de injeção de prompt em cada resultado, proteção SSRF/DNS-rebinding
- **Suporte nativo a provedores** — 28 provedores via SDKs oficiais, sem camada proxy para depurar
- **Configuração em um comando** — Docker ou pip, siga o assistente, conversa em cerca de um minuto
- **Roda em todo lugar** — Terminal, WebUI, Discord, Telegram, WhatsApp, app desktop Windows e mais

***

## 🛡️ Segurança, Embutida

Defesas normalmente espalhadas pelo glue da app ou proxies externos — no ShibaClaw elas vêm no núcleo, <b>ativadas por padrão</b>.

### Camadas de Segurança do Núcleo

| Camada | O que faz |
|---|---|
| 🔍 Auditoria na instalação | Audita `pip` e `npm` antes de executar — bloqueia CVEs críticos/altos antes de chegarem |
| 🛡️ Envelopamento de injeção de prompt e pré-scan | Envelopa cada resultado em fronteira `<tool_output_...>` aleatória. Aplica pré-scan regex para jailbreaks e **codificação Base64** para cargas não confiáveis |
| 🔒 Endurecimento de shell | 20+ padrões de negação, normalização de escape (`\x..`, `\u....`), detecção de URL interna |
| ⚡ Motor Local-First | Emulador de comandos nativo (`ls`, `cat`) evita overhead de subprocesso; fallback `tiktoken` offline-first para execução isolada |
| 🌐 Guarda de rede | Filtragem SSRF, revalidação de redirecionamento, resolução segura contra DNS-rebinding |
| 📁 Sandbox de workspace | Ferramentas de arquivo e navegador travados ao workspace configurado |
| 🔑 Controle de acesso | Auth Bearer token, verificações de tempo constante, allowlists de canal, rate limiting opcional |
| 🧠 Motor Distribuído | UI (≈128 MB) desacoplada do cérebro do agente (≈256 MB+) — pegada mínima por processo |

### 🛡️ Envelopamento de Injeção de Prompt (Sandbox de Ferramentas)

Em vez de simplesmente devolver saídas cruas ao LLM, ShibaClaw envelopa cada resultado em uma fronteira tipo XML gerada dinamicamente com um <b>nonce aleatório</b> (ex., `<tool_output_a1b2c3d4>`).

> 💡 <b>Defesa Independente</b>: Este mecanismo central (Envelopamento Aleatório de Saída de Ferramenta) foi desacoplado e empacotado como biblioteca Python independente sem dependências, [Muzzle](https://github.com/RikyZ90/Muzzle). Use para proteger qualquer framework de agentes (LangChain, LlamaIndex, CrewAI, AutoGen ou loops LLM custom).

Por que importa: atacantes frequentemente tentam fechar prematuramente tags ou injetar instruções de sistema falsas dentro de saídas (como conteúdo web). Com fronteira aleatória por iteração, o agente distingue de forma confiável instruções reais de cargas injetadas. Além disso, qualquer tentativa de injetar a tag de fechamento específica é automaticamente sanitizada e escapada, mantendo o sandbox hermético.

### 🔍 Auto-scan de Pacotes na Instalação

Antes de executar qualquer `pip`, `npm` ou `apt`, ShibaClaw intercepta e analisa as dependências. Roda `pip-audit` ou `npm audit --json` para escanear vulnerabilidades contra bases CVE antes de aplicar mudanças.

Por que importa: desloca a segurança totalmente para a esquerda. Em vez de bloquear cegamente gerenciadores ou depender de pós-scan, avalia a árvore de dependências exata <i>antes</i> da execução. Se um pacote tem CVE crítico/alto, ou flags suspeitas (como `--allow-unauthenticated` no `apt`) são detectadas, a instalação é bloqueada.

Política de divulgação e versões suportadas: [SECURITY.md](./SECURITY.md).

***

## 🖥️ App de Desktop Nativo (Windows)

ShibaClaw traz um **Lançador de Desktop Windows** totalmente integrado, construído com `pywebview`.  
Oferece experiência local sem janelas de terminal em segundo plano.

- **Integração com Bandeja**: Feche a janela para minimizar silenciosamente para a bandeja. Clique direito no ícone Shiba para reabrir a UI, ver logs, visitar o site ou sair com elegância.
- **Auto-Login**: No desktop local, a autenticação WebUI é ignorada por padrão para experiência mais fluida.
- **WebUI Embutida**: Sem abrir navegador; a WebUI roda em janela nativa dedicada.
- **Portátil e Leve**: Empacotado como pasta única via PyInstaller, roda instantaneamente sem Python no host.

Se instalou via `pip`:
```bash
shibaclaw desktop
```

Ou baixe o executável Windows pré-construído da última versão:

> **[⬇ Baixar ShibaClaw.exe (última)](https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip)**  
> Notas → [github.com/RikyZ90/ShibaClaw/releases/latest](https://github.com/RikyZ90/ShibaClaw/releases/latest)

***

## 🌐 WebUI

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

A WebUI é embutida — sem frontend separado nem Node.js.

Exponha na rede local e abra a mesma URL no celular ou tablet — sem apps extras, só o navegador.

- **Chat** — conversas multi-sessão com streaming ao vivo de chamadas de ferramenta, blocos de pensamento, tempo e troca de modelo por sessão
- **RAG Local e Bases de Conhecimento** — arraste ou suba documentos (PDF, CSV, HTML, TXT) para criar coleções locais, consulte via busca semântica
- **Menções de Contexto (@)** — autocomplete e vincule bases, servidores MCP e apps conectados usando `@`
- **Busca de modelos multi-provedor** — seletor único funde modelos de todos os provedores, mostra rótulos e troca o provedor runtime
- **Perfis de Agente** — troque personas por sessão (Hacker, Builder, Planner, Reviewer) com avatares dinâmicos
- **Navegador de arquivos** — navegue, veja e edite arquivos do workspace no navegador (sandbox)
- **Voz** — speech-to-text via APIs de áudio compatíveis com OpenAI e TTS nativo do navegador
- **Configurações** — defina modelo de sessão, memória, provedores, ferramentas, servidores MCP, canais, skills e OAuth num painel
- **Assistente de onboard** — setup guiado: escolha provedor, API key ou OAuth, modelo
- **Visualizador de contexto** — inspecione o system prompt completo e o uso de tokens
- **Monitor de gateway** — health check e reinício com um clique
- **Fluxos OAuth** — GitHub Copilot, OpenAI Codex e OpenRouter configuráveis nas configurações
- **Renderização endurecida** — Markdown escapa HTML cru, nomes de arquivo via DOM seguro, auth expirada volta limpo ao login
- **Auto-update** — checa GitHub a cada 12h, notifica na UI e canais
- **Central de Notificações (WIP)** — sino com badge, push WebSocket tempo real, deep-link por notificação
- **Responsivo** — funciona em desktop e mobile

### ⚡ Seleção Dinâmica de Modelo

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

Troque modelos por sessão — não mais um modelo global, mas escolha flexível por conversa.

- **Busca Multi-Provedor**: Busque todos os modelos de todos os provedores (OpenRouter, GitHub Copilot, Anthropic, etc.) num dropdown.
- **Roteamento Consciente de Sessão**: Cada sessão lembra seu modelo. Tenha sessão de código com `Claude 3.5 Sonnet` e de pesquisa com `Gemma 4` simultaneamente.
- **Troca em Runtime**: Troque instantaneamente sem reiniciar; o gateway resolve o endpoint correto.
- **Modelo de Memória Dedicado**: Configure modelo e provedor separados para consolidação e aprendizado proativo.
- **Padrão Primeiro**: Novas sessões iniciam com o modelo padrão.

### 🤖 Perfis de Agente

Troque a personalidade do agente em tempo real sem perder contexto. Cada perfil sobrescreve o system prompt (SOUL.md) compartilhando modelo, memória e ferramentas. Perfis por sessão.

Perfis embutidos: Default · Builder · Planner · Reviewer · <b>Hacker</b> (especialista em segurança com 50+ recomendações, metodologias OWASP/MITRE/NIST, score CVSS e avatar cyber-shiba).

Crie seus próprios perfis interativamente.

***

## 🧠 Sistema Avançado de Memória de 3 Níveis

A memória do ShibaClaw não é só um buffer de chat; é um sistema proativo estruturado para continuidade operacional de longo prazo.

- **`USER.md` (Identidade e Preferências):** Fatos pessoais duráveis, estilos de comunicação e preferências de idioma.
- **`MEMORY.md` (Estado Operacional):** Conhecimento de trabalho do agente. Rastreia detalhes do ambiente, entidades recorrentes e estado do projeto.
- **`HISTORY.md` (Arquivo de Sessões):** Ledger só-apend, buscável, com resumos marcados por tempo.

Em vez de inflar o system prompt com milhares de mensagens, ShibaClaw tem um **loop de Aprendizado Proativo**. A cada N mensagens, um processo LLM em background extrai fatos e atualiza `USER.md` e `MEMORY.md` sem interromper. Quando `MEMORY.md` cresce demais, rotina de auto-compactação resume e dedup, priorizando estado recente. Quando o agente precisa de contexto antigo, busca `HISTORY.md` via TF-IDF e recência.

***

## 🛠️ Funcionalidades

### Workflow e Raciocínio

- **Roteamento de sessão modelo-primeiro** — cada sessão guarda seu modelo e o provedor é resolvido em runtime
- **Delegação de background focada** — a ferramenta `spawn` descarrega uma tarefa e reporta de volta
- **Raciocínio avançado** — thinking estendido (Anthropic), esforço de raciocínio (OpenAI o-series) e cadeias DeepSeek-R1

### Ferramentas

| Ferramenta | O que faz |
|------|-------------|
| `exec` | Comandos shell com 20+ padrões de negação, normalização de encoding e scan CVE |
| `read_file` / `write_file` / `edit_file` | Leituras paginadas, replace difuso, criação de diretórios pai |
| `web_search` | Brave, Tavily, SearXNG, Jina ou DuckDuckGo (fallback sem key) |
| `web_fetch` | HTTP com proteção SSRF, defesa DNS-rebinding e validação de redirecionamento |
| `memory_search` | Busca rankeada sobre histórico (TF-IDF + recência + importância) |
| `knowledge_search` | Busca semântica sobre coleções locais (FAISS) |
| `message` | Mensageria cross-canal com anexos |
| `automation` | Gerencia ou agenda tarefas (cron, intervalos, datas ISO, timezone) |
| `spawn` | Worker de background opcional para tarefa focada |
| MCP | Conecte qualquer servidor MCP (stdio, SSE ou HTTP) — ferramentas auto-registradas como `mcp_<server>_<tool>` |

### Canais

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

Todos os canais roteiam pelo mesmo message bus. WhatsApp usa bridge Node.js (Baileys) para vínculo via QR.

### Skills

8 skills embutidas (GitHub, weather, summarize, tmux, automation, memory guide, skill-creator, ClawHub browser). São arquivos Markdown com frontmatter YAML e scripts opcionais — crie ou instale via [ClawHub](https://clawhub.ai/).

### Automação

- **Motor de Automações** — tarefas agendadas persistentes e rotinas de background, gerenciadas via UI e salvas em `automation.json`. Suporta `every`, `cron` e `at`. Tarefas perdidas são adiantadas no startup.
- **Integração TASK.md** — o motor usa `TASK.md` como fonte de verdade; pula o LLM quando vazio.

Se atualizando de versão antiga, `HEARTBEAT.md` foi deprecado. Migre para `TASK.md` e a nova UI de Automações.

### 🔌 Plugins e TTS

- **Sistema de Plugins Instaláveis** — Estenda o agente com plugins Python dinâmicos gerenciados pela WebUI. Veja [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).
- **TTS Local Offline Gratuito (Supertonic)** — Síntese de voz ONNX de alta qualidade, zero custo, totalmente offline. Suporta 31 idiomas, vozes custom (`F1`/`M1`) e velocidade ajustável.
- **Player de Áudio no Navegador** — reproduz mensagens de voz na UI com widget glassmorphic.

***

## 🔌 Ecossistema MCP

ShibaClaw é totalmente compatível com o **Model Context Protocol (MCP)**, transformando o agente em hub de IA plug-and-play.

Em vez de depender só de skills embutidas, ShibaClaw conecta a qualquer servidor MCP, concedendo acesso a vasto universo de fontes de dados externas e ferramentas profissionais sem modificar o núcleo.

Por que importa:
- **Extensibilidade Instantânea**: Plugue servidores MCP da comunidade para Google Drive, Slack, GitHub, PostgreSQL e mais.
- **Ferramentas Padronizadas**: Protocolo universal para comunicação IA-ferramenta.
- **Arquitetura Desacoplada**: Mantenha o agente enxuto enquanto escala capacidades.

Configure seus servidores MCP no painel **Configurações**.

### 🌐 Apps (Integração Klavis)

Para facilitar a configuração de ferramentas SaaS populares (Gmail, Google Drive, Slack, GitHub, Outlook etc.), ShibaClaw integra com **Klavis** (`klavis.ai`).

Em vez de criar credenciais manualmente por serviço, gerencie tudo via **Connected Apps**:
- **Uma só API Key**: Pegue uma key em [klavis.ai](https://klavis.ai) e salve nas configurações.
- **Conexões em um Clique**: Conecte ou desconecte Gmail, Slack e outros via OAuth seguro gerenciado pelo gateway Klavis.
- **Servidores MCP Auto-Gerados**: Ao conectar, ShibaClaw configura o servidor MCP apropriado e registra suas ferramentas.

***

## 🌐 Provedores Suportados

ShibaClaw usa SDKs nativos (sem proxy LiteLLM) e resolve o provedor ativo a partir do modelo selecionado ou ID canônico com prefixo. Na WebUI, todos os catálogos são fundidos numa lista buscável, cada sessão mantendo seu modelo.

### API Key

| Provedor | Variável de Ambiente |
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

¹ Definir `GEMINI_API_KEY` no ambiente é suficiente. O endpoint OpenAI-compatível do Google vem pré-configurado.

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — auto-detectados por prefixo de key ou `api_base`.

### Local

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · qualquer endpoint OpenAI-compatível(`http://localhost:1234/v1`)

> **Nota para Docker:** Se roda via Docker Compose, `localhost` aponta dentro do container. Para conectar a servidor local no host (LM Studio ou Ollama no Windows/Mac), use:
> `http://host.docker.internal:1234/v1` (ou `11434` para Ollama). No Linux nativo use `http://172.17.0.1:port`.

### OAuth

| Provedor | Fluxo | Configuração |
|----------|------|-------|
| OpenRouter | Fluxo PKCE navegador, salva a API key devolvida | Configurações WebUI |
| GitHub Copilot | Fluxo device, auto-refresh de token | `shibaclaw provider login github-copilot` ou Configurações |
| OpenAI Codex | Fluxo PKCE navegador | `shibaclaw provider login openai-codex` ou Configurações |

Para OpenRouter, o callback reusa a URL/porta da WebUI por padrão, então `http://localhost:3000` não é porta OAuth dedicada. Se expõe a WebUI atrás de proxy reverso ou precisa de origem de callback pública diferente, defina `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` antes de iniciar.

### 💡 Dica Pro: Modelos Econômicos e Premium

- **Modelos Gratis/Abertos:** Recomendamos **OpenRouter** para modelos gratuitos potentes como `nvidia/nemotron-3-super-120b-a12b:free` ou `gemma-4-31b-it:free`.
- **Premium Ilimitado:** Com **GitHub Copilot** OAuth você acessa modelos premium como `raptor` (`oswe-vscode-prime`) a custo zero.

***

## 📊 Comparativo ShibaClaw (Segurança Primeiro)

> Esta tabela é um **snapshot aproximado focado em segurança**, baseado só no documentado publicamente até maio 2026.  
> `❓` significa "não claramente documentado / não verificado", <b>não</b> "não existe".

| Recurso de Segurança | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| Auditoria CVE na instalação (pip, npm, apt) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Envelopamento de injeção de prompt em cada resultado | ✅ | ❌ | ❌ | ❌ | ❌ |
| Proteção SSRF + DNS-rebinding embutida | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClaw foca em entregar essas defesas no motor do núcleo, ativadas por padrão.

***

## 🏗️ Arquitetura

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Serviço | Papel | Porta Padrão |
|---------|------|--------------|
| `shibaclaw-gateway` | Loop do agente, message bus, integrações de canal | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket nativo), serviço de automações | 3000 |

Ambos compartilham o volume `~/.shibaclaw/` (config, workspace, memória, jobs, cache).

### Modo single-process

`shibaclaw web` roda agente + WebUI + automações num processo — sem container gateway.

### Stack

| Camada | Tecnologia |
|-------|-----------|
| Servidor | Uvicorn → Starlette (ASGI) |
| Tempo real | WebSocket nativo (`/ws` na WebUI, porta `19998` no gateway) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sessões | JSONL só-apend por sessão |

### Uso de recursos

| Componente | Idle | Pico (instalar/compilar) |
|-----------|------|------------------------|
| Gateway | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Compose define limite de 512 MB / reserva de 256 MB por container. Saída de ferramentas é transmitida com buffers limitados.

***

## 🔧 Referência CLI

```bash
shibaclaw web               # Inicia WebUI (agente + automações in-process)
shibaclaw gateway           # Inicia só gateway (para Docker split)
shibaclaw onboard           # Assistente de setup via CLI
shibaclaw agent -m "Hello"  # Mensagem única via terminal
shibaclaw agent             # REPL interativo com histórico
shibaclaw status            # Health check de provedor, workspace, OAuth
shibaclaw print-token       # Mostra token de auth WebUI
shibaclaw channels status   # Lista canais habilitados
shibaclaw provider login <p># Login OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Lança app desktop Windows
```

***

## 🐛 Troubleshooting

| Problema | Tente |
|---------|-----|
| Checagem geral | `shibaclaw status` |
| Logs de container | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI não conecta | Verifique token com `shibaclaw print-token`, valide bind de porta |
| Erros de provedor | `shibaclaw status` mostra API key e estado OAuth |
| Política de segurança | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 Contribuindo

Veja [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs bem-vindos.

Plugins (canais e motores TTS) se estendem via Python entry points. Veja [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md). Criação de skills em [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) e o skill embutido `skill-creator`.

Integradores de gateway: veja [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) para o contrato WebSocket na porta `19998`.

***

## 🌟 Junte-se à Matilha ShibaClaw

ShibaClaw é construído por um desenvolvedor, mantido pela comunidade e crescendo rápido.  
Se te poupou tempo, protegeu seu fluxo, ou só te fez sorrir — <b>deixe uma estrela</b> ⭐

> "O agente de IA que simplesmente funciona. Sem babá." 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Dê uma estrela</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">Pague um café</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Abra um issue</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Envie um PR</a>
</p>