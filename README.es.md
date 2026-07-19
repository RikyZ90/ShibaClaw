<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>Agente de IA autohospedado, con prioridad en la seguridad y una interfaz web integrada</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">Características</a> ·
  <a href="#quick-start">Inicio Rápido</a> ·
  <a href="#security">Seguridad</a> ·
  <a href="#memory-system">Memoria</a> ·
  <a href="#supported-providers">Proveedores</a> ·
  <a href="#architecture">Arquitectura</a> ·
  <a href="#channels">Canales</a> ·
  <a href="#troubleshooting">Solución de Problemas</a>
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
> Las notas de versión están en [CHANGELOG.md](./CHANGELOG.md).

<details open>
<summary>📢 <b>Novedades — v0.9.8</b> (haz clic para expandir)</summary>

**Última versión (2026-07-15):**

- **Desplegables en la configuración de canales** —— los campos `group_policy` de la configuración de canales ahora usan selectores desplegables en la WebUI para una mejor experiencia.
- **Instalación de paquetes externos en Linux moderno (PEP 668)** —— inyecta automáticamente `--break-system-packages` ante errores `externally-managed-environment` durante las operaciones pip.
- **Propagación de clave de sesión en sub-agentes** —— se añadió `session_key` a los metadatos de sub-agentes para mantener el contexto correcto durante la ejecución paralela.
- **Error de importación en reinicio suave de RAG** —— se corrigió el `NameError` en las importaciones dinámicas de RAG durante reinicios suaves cuando el plugin RAG local está instalado.
- **Manejo de errores transitorios de LLM** —— se añadió `'empty choices'` a los marcadores de error transitorio para reintentar automáticamente ante respuestas API vacías.
- **Recarga en caliente de canales al actualizar secretos** —— se corrigió que la recarga en caliente no se disparaba al actualizar secretos.
- **Elección de herramienta en aprendizaje proactivo** —— maneja con elegancia el parámetro `tool_choice` no soportado en el aprendizaje proactivo.
- **Eliminada la codificación Base64 de salida de herramientas** —— se eliminó la lógica de codificación Base64 para simplificar el flujo.

**Sin publicar (en progreso):**

- **Funciones de Telegram AI / agent Bot API** —— Modo Invitado (`answerGuestQuery`), streaming en chat privado vía `sendMessageDraft`, mensajes bot-a-bot, actualizaciones de Business / Chat Automation y seguimiento de actualizaciones de Managed Bot. Ver `docs/TELEGRAM_AI_FEATURES.md`.
- **Indicadores de configuración de Telegram** —— `streaming`, `guestMode`, `allowBotMessages`, `businessEnabled`, `managedBotsEnabled`.

Consulta el [Changelog](./CHANGELOG.md) para el historial completo de versiones.

</details>

---

ShibaClaw es un agente de IA autohospedado que ejecutas en tu propia máquina o servidor: un motor Python con interfaz web integrada, soporte nativo para 28 proveedores de modelos y 11 integraciones de plataformas de chat (Discord, Telegram, Slack, WhatsApp, Matrix y más). Se construye en torno a tres prioridades —— simplicidad, seguridad y privacidad —— con defensas como la auditoría CVE en instalación, el encapsulado de inyección de prompts y la protección SSRF integradas en el motor central en lugar de añadirse como código externo.

<p align="center">
  <img src="assets/webui_chat.webp" width="640" alt="ShibaClaw WebUI chat">
</p>

> [!NOTE]
> Las notas de versión están en [CHANGELOG.md](./CHANGELOG.md).

## Características

- **Núcleo con prioridad en seguridad** —— bóveda de credenciales cifrada, auditoría CVE en instalación, encapsulado de inyección de prompts, protección SSRF/DNS-rebinding
- **Memoria de tres niveles** —— memoria de trabajo, semántica (FAISS) y procedimental, con aprendizaje proactivo y auto-compactación
- **28 proveedores, SDK nativos** —— OpenAI, Anthropic, Gemini, DeepSeek y más, sin capa proxy LiteLLM
- **Web y móvil** —— expón la WebUI en tu LAN y usa el mismo agente desde el móvil
- **App de escritorio para Windows** —— lanzador nativo con integración en la bandeja del sistema
- **Listo para MCP** —— conecta cualquier servidor MCP, las herramientas se registran automáticamente

## Inicio Rápido

**Requisitos:** Docker, o Python 3.12+ para la vía pip. El instalador automático de Windows no necesita ninguno de los dos —— incluye una app de escritorio preconstruida.

### Instalador automático (recomendado)

Un solo comando descarga la última versión, crea accesos directos e inicia la interfaz.

> [!TIP]
> Trae tu propio modelo: conéctate a endpoints locales (Ollama, LM Studio) o usa niveles gratuitos de API vía OpenRouter para chatear a costo cero.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS:**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> En Windows esto descarga la app de escritorio preconstruida desde la última GitHub Release —— no requiere Python, con accesos directos en el Escritorio/Menú Inicio y desinstalación limpia vía Aplicaciones y características. En Linux/macOS el script instala vía pip en un entorno virtual aislado.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # obtiene la imagen de Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Abre **http://localhost:3000**, pega el token y sigue el asistente de inicio. Expón `shibaclaw-web` en tu LAN (ej. vía proxy inverso) y abre la misma URL desde tu móvil para chatear con tu agente en móvil.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # inicia WebUI + motor del agente en :3000
```

Abre **http://localhost:3000** y sigue el asistente de inicio.  
¿Prefieres la CLI? `shibaclaw onboard` ejecuta la misma configuración guiada desde la terminal.

---

## Seguridad

Las defensas que normalmente están dispersas en el código de unión de la app o en proxies externos se incluyen en el núcleo de ShibaClaw, activadas por defecto.

| Capa | Qué hace |
|---|---|
| Auditoría en instalación | Audita `pip` y `npm` antes de ejecutar —— bloquea CVE críticos/altos |
| Encapsulado de inyección de prompts y pre-escaneo | Envuelve cada resultado de herramienta en un límite `<tool_output_...>` aleatorio; pre-escaneo regex de jailbreaks |
| Endurecimiento de shell | 20+ patrones de denegación, normalización de escape, detección de URL internas |
| Motor local-first | Emulador de comandos nativo (`ls`, `cat`) evita overhead de subproceso; fallback `tiktoken` offline |
| Guardia de red | Filtrado SSRF, revalidación de redirección, resolución segura contra DNS-rebinding |
| Sandbox de espacio de trabajo | Herramientas de archivo y explorador bloqueados al espacio de trabajo configurado |
| Control de acceso | Auth Bearer token, comprobaciones de tiempo constante, listas blancas de canales, rate limiting opcional |
| Motor distribuido | UI (~128 MB) desacoplada del cerebro del agente (~256 MB+) |

Cada resultado de herramienta se envuelve en un límite generado dinámicamente con un nonce aleatorio (ej. `<tool_output_a1b2c3d4>`), por lo que un atacante no puede cerrar prematuramente la etiqueta ni inyectar instrucciones de sistema falsas a través de la salida de la herramienta —— el límite es impredecible por sesión.

> [!TIP]
> Este mecanismo de encapsulado también está disponible de forma independiente como [Muzzle](https://github.com/RikyZ90/Muzzle), una biblioteca Python sin dependencias que puedes integrar en cualquier framework de agentes (LangChain, LlamaIndex, CrewAI, AutoGen o un bucle personalizado).

## Sistema de Memoria

ShibaClaw utiliza una arquitectura de memoria de tres niveles:

1. **Memoria de trabajo** (por sesión) —— contexto rodante con resumen automático y truncado consciente de tokens
2. **Memoria semántica** (entre sesiones) —— almacén vectorial FAISS + sentence-transformers con extracción automática de hechos y búsqueda semántica
3. **Memoria procedimental** (habilidades y automatizaciones) —— flujos de trabajo aprendidos guardados como habilidades reutilizables, además de programaciones tipo cron

El aprendizaje proactivo extrae y almacena hechos útiles automáticamente, la auto-compactación evita el desbordamiento del contexto, y las sesiones se guardan como JSONL de solo anexo para un registro rápido y amigable con la caché.

## MCP e Integraciones

ShibaClaw habla el Model Context Protocol, por lo que puede conectarse a cualquier servidor compatible con MCP —— Google Drive, Slack, GitHub, PostgreSQL y más —— sin cambiar el código central. Configura los servidores desde el panel de Ajustes.

Para herramientas SaaS populares (Gmail, Google Drive, Slack, GitHub, Outlook...), ShibaClaw se integra con [Klavis](https://klavis.ai): una sola API key te da conexiones OAuth de un clic en lugar de registrar manualmente una app OAuth con cada proveedor. Las apps conectadas se registran automáticamente como servidores MCP en la sesión activa.

## Proveedores Soportados

ShibaClaw usa SDK nativos —— sin proxy LiteLLM —— y resuelve el proveedor desde el modelo seleccionado o un ID de modelo con prefijo de proveedor. Todos los catálogos de proveedores configurados se fusionan en una lista buscable en la WebUI.

**Clave API**

| Proveedor | Variable de entorno |
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

¹ Configurar `GEMINI_API_KEY` es suficiente —— el endpoint compatible con OpenAI viene preconfigurado.

**Pasarela / proxy** —— OpenRouter, AiHubMix, SiliconFlow, VolcEngine, BytePlus, auto-detectados por prefijo de clave o `api_base`.

**Local** —— Ollama, LM Studio, llama.cpp, vLLM, o cualquier endpoint compatible con OpenAI.

> [!NOTE]
> En Docker, `localhost` apunta dentro del contenedor. Para acceder a un servidor local en el host (LM Studio, Ollama), usa `http://host.docker.internal:PORT` en Windows/macOS o `http://172.17.0.1:PORT` en Linux nativo.

**OAuth**

| Proveedor | Flujo | Configuración |
|----------|------|-------|
| OpenRouter | Flujo PKCE en navegador, guarda la API key devuelta en la config del proveedor | Ajustes WebUI |
| GitHub Copilot | Flujo de dispositivo, refresco automático de token | `shibaclaw provider login github-copilot` o Ajustes WebUI |
| OpenAI Codex | Flujo PKCE en navegador | `shibaclaw provider login openai-codex` o Ajustes WebUI |
| Google Gemini CLI | Flujo PKCE en navegador, requiere las variables `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` y `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET`. **Nota:** Integración de terceros no oficial; Google puede aplicar restricciones de cuenta. Usa una cuenta separada si es un problema. | Ajustes WebUI |

Para OpenRouter, la callback reutiliza por defecto la URL y puerto actuales de la WebUI, por lo que `http://localhost:3000` no es un puerto exclusivo de OAuth. Si expones la WebUI detrás de un proxy inverso o necesitas un origen de callback público distinto, define `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` antes de iniciar el servidor.

### 💡 Pro Tip: Modelos Económicos y Premium

ShibaClaw rinde excepcionalmente bien incluso sin gastar en API:
- **Modelos gratuitos/abiertos:** Recomendamos usar **OpenRouter** para acceder a modelos gratuitos potentes como `nvidia/nemotron-3-super-120b-a12b:free` o `gemma-4-31b-it:free`.
- **Premium ilimitado:** Si usas la integración OAuth de **GitHub Copilot**, obtienes acceso a modelos premium como `raptor` (`oswe-vscode-prime`) a costo cero, dándote solicitudes ilimitadas.

***

## 📊 Cómo se compara ShibaClaw (Seguridad Primero)

> [!NOTE]
> La callback OAuth de OpenRouter reutiliza la URL y puerto actuales de la WebUI. Detrás de un proxy inverso, define `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL` antes de iniciar el servidor.

Para uso a costo cero, tanto el nivel gratuito de OpenRouter (ej. `nvidia/nemotron-3-super-120b-a12b:free`) como la integración OAuth de GitHub Copilot (acceso ilimitado a modelos como `raptor`) funcionan bien sin una API key de pago.

## Arquitectura

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| Servicio | Rol | Puerto por defecto |
|---|---|---|
| `shibaclaw-gateway` | Bucle central del agente, bus de mensajes, integraciones de canales | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket), servicio de automatizaciones | 3000 |

Ambos comparten el volumen `~/.shibaclaw/` (config, workspace, memoria, trabajos de automatización, caché de medios). `shibaclaw web` por sí solo ejecuta agente + WebUI + automatizaciones en un solo proceso, sin contenedor gateway.

**Stack** —— Uvicorn/Starlette (ASGI), WebSocket nativo, frontend JS vanilla + Marked.js + Highlight.js, sesiones JSONL de solo anexo.

**Uso de recursos** —— ~120 MB en reposo / ~350 MB pico por componente (gateway, WebUI). Docker Compose limita cada contenedor a 512 MB / 256 MB reservados; la salida de herramientas se transmite con buffers acotados para que comandos largos no saturen la memoria.

## Referencia CLI

```bash
shibaclaw web               # Inicia la WebUI (agente + automatizaciones en proceso)
shibaclaw gateway           # Inicia solo el gateway (para split Docker)
shibaclaw onboard           # Asistente de configuración inicial en CLI
shibaclaw agent -m "Hello"  # Mensaje único vía terminal
shibaclaw agent             # REPL interactivo con historial
shibaclaw status            # Proveedor, workspace, chequeo de salud OAuth
shibaclaw print-token       # Muestra el token de autenticación WebUI
shibaclaw channels status   # Lista los canales habilitados
shibaclaw provider login <p># Login OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Lanza la app de escritorio Windows
```

## Canales

| Canal | Tipo | Notas |
|---|---|---|
| WebUI | Integrado | Interfaz principal, acceso completo |
| Discord | Bot | Embeds ricos, comandos slash, adjuntos |
| Telegram | Bot | Teclados en línea, medios, markup de respuesta |
| WhatsApp | Plugin | Vía WhatsApp Web |
| Slack | Bot | Block kit, hilos, menciones de app |
| DingTalk | Bot | Mensajería empresarial |
| Feishu/Lark | Bot | Tarjetas ricas, elementos interactivos |
| QQ | Bot | Mensajes de grupo y privados |
| WeCom | Bot | Comunicación laboral |
| Matrix | Bot | Descentralizado, cifrado E2E |
| MoChat | Bot | Ecosistema WeChat |

Cada canal se configura de forma independiente en Ajustes WebUI y soporta recarga en caliente ante cambios de configuración.

## Sistema de Plugins

ShibaClaw descubre plugins vía puntos de entrada de Python:

- **Plugins de canal** —— implementan `BaseChannel`, descubribles vía `shibaclaw.integrations`
- **Plugins TTS** —— implementan `BaseTTS`, descubribles vía `shibaclaw.tts`

Integrados: `shibaclaw-channel-whatsapp` (WhatsApp Web) y `shibaclaw-tts-supertonic` (síntesis de voz ONNX gratuita y offline, 31 idiomas). Instala o elimina plugins desde Ajustes WebUI > Plugins, con recarga en caliente y fijación de versión. Para crear el tuyo, consulta [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).

## Texto a Voz

El motor Supertonic integrado se ejecuta offline sobre ONNX (sin dependencia de PyTorch, solo CPU), soporta 31 idiomas con perfiles de voz `F1`/`M1` y velocidad ajustable, y se reproduce mediante un widget en el navegador. Habilítalo en Ajustes WebUI > TTS.

## Automatización y Programación

Las tareas en segundo plano se ejecutan en programaciones tipo cron o disparadores de eventos (mensajes, webhooks, eventos del sistema), en sesiones aisladas que no contaminan el historial de chat. Gestiona, monitorea y consulta registros desde el panel de Automatizaciones; los trabajos persisten entre reinicios vía almacenamiento JSONL.

## Base de Conocimiento (RAG)

Generación aumentada por recuperación local y con prioridad en la privacidad: organiza documentos en colecciones con nombre (PDF, CSV, HTML, TXT, Markdown), sube por arrastrar y soltar, y busca con un índice FAISS sobre embeddings `all-MiniLM-L6-v2`. El agente puede llamar a `knowledge_search` durante la conversación, o apuntar a una colección específica con `@kb:name`. Es una dependencia opcional —— instala con `pip install shibaclaw[rag]`.

## Solución de Problemas

| Problema | Prueba |
|---|---|
| Chequeo de estado general | `shibaclaw status` |
| Registros de contenedor | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI no conecta | Verifica el token con `shibaclaw print-token`, comprueba el puerto |
| Errores de proveedor | `shibaclaw status` muestra la API key y el estado OAuth |
| Fallo de login tras actualizar desde v0.9.5 | Ejecuta `shibaclaw reset-admin` |
| Política de seguridad | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
Consulta <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> para contribuir y <a href="./CHANGELOG.md">CHANGELOG.md</a> para el historial de versiones.
</p>
