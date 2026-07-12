<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw 🐕</h1>
<h3 align="center">El agente de IA que <b>simplemente funciona</b> — de forma segura, privada y sin supervisión.</h3>

> Traducción de [README.md](./README.md) — puede no estar actualizada (sincronizado a v0.9.4).

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28 Proveedores · 11 Canales de Chat · WebUI Integrada · Núcleo con Seguridad Primero · Listo para MCP</b>
</p>

<h3 align="center">Construido sobre tres pilares: <b>Simplicidad · Seguridad · Privacidad</b></h3>

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
<summary>📢 <b>Última versión: v0.9.6</b> — Haz clic para ver las novedades</summary>

### Añadido
- **🔐 Bóveda de credenciales cifrada (Actualización de seguridad importante)** — Hemos reformado fundamentalmente la gestión de secretos. ShibaClaw ahora utiliza una robusta bóveda cifrada simétrica AES-128/256 (`credentials.enc` y `credentials.key`) a través de Fernet. Esto aísla por completo todos los secretos de integración de terceros (claves API, tokens de bot, contraseñas de correo electrónico) de los archivos de configuración de texto plano, evitando fugas accidentales.
- **🌐 Flujos nativos de xAI y OAuth avanzado** — Integración de flujos de código de dispositivo / OAuth nativos directamente en la WebUI. Ahora puede autenticarse sin problemas con **xAI / Grok** utilizando mecanismos oficiales de código de dispositivo, junto con GitHub Copilot, OpenAI Codex y OpenRouter, eliminando por completo la necesidad de tocar las claves API manualmente.
- **🤖 Ecosistema ampliado de proveedores de modelos** — Se agregó soporte completo e inmediato para los modelos líderes de la industria, incluidos **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** y **Zhipu Z.AI**.
- **Protección de archivos de Windows** — Se integró un plan de respaldo específico de la plataforma utilizando `icacls` para aplicar un control de acceso estricto solo para el usuario en claves y bóvedas bajo Windows.

### Cambiado
- **🎨 Rediseño visual completo de la WebUI** — Se renovó toda la interfaz de usuario para establecer una estética seria, profesional y centrada en el producto (inspirada en Linear y Stripe). Se eliminó sistemáticamente la "basura visual" generada por IA, incluidos los fondos de glassmorphism (`backdrop-filter: blur`), el texto con gradiente decorativo, los brillos dorados excesivos y las animaciones flotantes. Se reemplazaron los bordes laterales arbitrarios con tintes de fondo semánticos limpios, se unificó el sistema de radio de borde bajo una escala de token estricta (4px/8px/12px) y se optimizó el contraste de color en temas oscuros para cumplir con los estándares WCAG.

### Solucionado
- **Respaldos de texto plano inseguros** — Se refactorizó el flujo de incorporación de WebUI y la configuración de Github OAuth para almacenar los tokens recuperados directamente en la bóveda cifrada en lugar de fallar al validarlos contra cambios de esquema.
- **Condiciones de carrera en actualizaciones de la bóveda** — Se envolvieron todas las operaciones de credenciales modificadoras bajo un `threading.Lock` para garantizar la seguridad durante las actualizaciones simultáneas de la WebUI.
- **Pérdida de datos por corrupción silenciosa** — Se configuró el flujo de carga de la bóveda para lanzar un `RuntimeError` en fallas de descifrado en lugar de devolver una base de datos vacía que sobrescribiría accidentalmente los secretos existentes.
- **Cachés de criptografía conscientes de la ruta** — Se reemplazó la caché global de Fernet de clave única con un mapa específico de la ruta para evitar conflictos de reutilización de claves en entornos de scripts.
- **Endurecimiento completo de la bóveda del canal** — Se integraron y verificaron ayudantes de resolución de bóveda para DingTalk, Feishu, QQ, MoChat, Discord y el complemento de canal de WhatsApp.
- **Configuración perfecta de aplicaciones conectadas** — Se solucionó un error de UX donde guardar la clave API de Klavis por primera vez requería cerrar y reabrir el menú manualmente. La WebUI ahora actualiza automáticamente los estados de la aplicación y habilita los botones de conexión de inmediato sin necesidad de recargar.
- **Linting del código base de Python** — Se corrigieron errores de análisis estático de `Ruff`, incluyendo el despliegue de declaraciones multilínea y la limpieza de importaciones no utilizadas y variables no definidas en los módulos principales (`channel.py`, `utils.py`, `gateway.py`).

### Optimizado
- **Carga de WebUI e inicialización de WebSocket** — Se migraron los activos frontend de WebUI para usar `esbuild` para el empaquetado y la minificación. La arquitectura modular de ES6 ahora se compila en un solo `bundle.js` e `index.css`, reduciendo drásticamente la sobrecarga de solicitudes HTTP y solucionando condiciones de carrera en los bucles de inicialización de la conexión WebSocket.

Consulta el [Changelog](./CHANGELOG.md) para el historial completo de versiones.

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ Inicio Rápido

### 🚀 Instalador Automático (Recomendado)

La forma más sencilla de empezar. Un solo comando descarga la última versión, crea accesos directos e inicia la interfaz.

**Trae tu propio modelo**: Conéctate sin problemas a endpoints locales (Ollama, LM Studio) o usa niveles gratuitos de API vía OpenRouter para chatear a costo cero.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **Nota**: En Windows, esto descarga la app de escritorio preconstruida desde la última GitHub Release — no requiere Python. Se crean automáticamente accesos directos en el Escritorio y Menú Inicio, y la app aparece en Aplicaciones y características para una desinstalación limpia. En Linux/macOS, el script instala vía pip en un entorno virtual aislado.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # obtiene la imagen de Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Abre **http://localhost:3000**, pega el token y sigue el asistente de inicio.

Expón `shibaclaw-web` en tu LAN (ej. vía proxy inverso) y abre la misma URL desde tu móvil para chatear con tu agente en móvil.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # inicia WebUI + motor del agente en :3000
```

Abre **http://localhost:3000** y sigue el asistente de inicio.  
¿Prefieres la CLI? `shibaclaw onboard` ejecuta la misma configuración guiada desde la terminal.

***

## ✨ Todo en un Solo Agente

<table>
<tr>
<td align="center" width="33%">

### 🛡️ Seguridad Primero
Auditoría CVE, envoltura de<br>inyección de prompts, guarda SSRF — <b>activado por defecto</b>

</td>
<td align="center" width="33%">

### 🧠 Memoria Inteligente
Sistema de 3 niveles con aprendizaje<br>proactivo y auto-compactación

</td>
<td align="center" width="33%">

### 🌐 28 Proveedores
SDK nativos, sin proxy LiteLLM<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Web y Móvil
Expón la WebUI en tu LAN y<br>usa el mismo agente desde el móvil

</td>
<td align="center" width="33%">

### 🖥️ App de Escritorio
Lanzador nativo de Windows con bandeja,<br>combinación perfecta con la WebUI

</td>
<td align="center" width="33%">

### 🔌 Listo para MCP
Conecta cualquier servidor MCP,<br>herramientas auto-registradas

</td>
</tr>
</table>

***

## ¿Por qué ShibaClaw? Simplemente funciona. 🐕

> **¿Cansado de agentes que requieren más supervisión que tu propio trabajo?**  
> ShibaClaw se diseña en torno a un principio: <b>simplemente funciona</b> — de forma segura, fiable y sin mantenimiento constante.

La mayoría de los frameworks de agentes de IA tratan la seguridad como una ocurrencia tardía, te dejan luchando con la compatibilidad de proveedores o te obligan a supervisar configuraciones. ShibaClaw cambia el guion: la seguridad no es un complemento, es <b>la base</b>.

Lo que hace diferente a ShibaClaw:
- **Capas de seguridad integradas en el núcleo** — auditoría CVE en instalación, envoltura de inyección de prompts en cada resultado de herramienta, protección SSRF/DNS-rebinding
- **Soporte nativo de proveedores** — 28 proveedores vía sus SDK oficiales, sin capa proxy que depurar
- **Configuración en un comando** — Docker o pip, sigue el asistente, chateas en unos minutos
- **Funciona en todas partes** — Terminal, WebUI, Discord, Telegram, WhatsApp, app de escritorio Windows y más

***

## 🛡️ Seguridad, Integrada

Defensas que normalmente están dispersas en el código de unión de la app o en proxies externos — en ShibaClaw se incluyen en el núcleo, <b>activadas por defecto</b>.

### Capas de Seguridad del Núcleo

| Capa | Qué hace |
|---|---|
| 🔍 Auditoría en instalación | Audita `pip` y `npm` antes de ejecutar — bloquea CVE críticos/altos antes de que lleguen |
| 🛡️ Envoltura de inyección de prompts y pre-escaneo | Envuelve cada resultado de herramienta en un límite `<tool_output_...>` aleatorio. Aplica pre-escaneo regex para jailbreaks y **codificación Base64** para cargas no confiables |
| 🔒 Endurecimiento de shell | 20+ patrones de denegación, normalización de escape (`\x..`, `\u....`), detección de URL interna |
| ⚡ Motor Local-First | Emulador de comandos nativo (`ls`, `cat`) evita overhead de subproceso; fallback `tiktoken` offline-first para ejecución aislada |
| 🌐 Guardia de red | Filtrado SSRF, revalidación de redirección, resolución segura contra DNS-rebinding |
| 📁 Sandbox de espacio de trabajo | Herramientas de archivo y navegador bloqueados al espacio de trabajo configurado |
| 🔑 Control de acceso | Auth Bearer token, comprobaciones de tiempo constante, listas blancas de canales, rate limiting opcional |
| 🧠 Motor Distribuido | UI (≈128 MB) desacoplada del cerebro del agente (≈256 MB+) — huella mínima por proceso |

### 🛡️ Envoltura de Inyección de Prompts (Sandboxing de Herramientas)

En lugar de simplemente devolver salidas crudas de herramientas al LLM, ShibaClaw envuelve cada resultado en un límite tipo XML generado dinámicamente con un <b>nonce aleatorio</b> (ej. `<tool_output_a1b2c3d4>`).

> 💡 <b>Defensa Independiente</b>: Este mecanismo central de seguridad (Envoltura Aleatoria de Salida de Herramientas) se ha desacoplado y empaquetado como una librería Python independiente sin dependencias llamada [Muzzle](https://github.com/RikyZ90/Muzzle). Puedes usar Muzzle para proteger cualquier framework de agentes (LangChain, LlamaIndex, CrewAI, AutoGen o bucles LLM personalizados) con esta misma técnica.

Por qué importa: los atacantes a menudo intentan cerrar prematuramente etiquetas o inyectar falsas instrucciones de sistema dentro de salidas de herramientas (como contenido de páginas web). Usando un límite aleatorio generado por iteración, el agente puede diferenciar de forma fiable entre instrucciones de sistema reales y cargas inyectadas. Además, cualquier intento de inyectar la etiqueta de cierre específica dentro del contenido se sana y escapa automáticamente, asegurando que el sandbox permanezca hermético y el prompt de sistema original tenga prioridad.

### 🔍 Auto-escaneo de Paquetes en Instalación

Antes de ejecutar cualquier comando `pip`, `npm` o `apt` de instalación, ShibaClaw intercepta la acción y analiza las dependencias. Ejecuta herramientas como `pip-audit` o `npm audit --json` para escanear vulnerabilidades conocidas contra bases de datos CVE antes de aplicar cualquier cambio.

Por qué importa: desplaza la seguridad totalmente a la izquierda. En lugar de bloquear ciegamente gestores de paquetes o depender de escaneos post-instalación, evalúa el árbol de dependencias exacto <i>antes</i> de la ejecución. Si un paquete contiene CVE críticos/altos, o si se detectan banderas sospechosas (como `--allow-unauthenticated` para `apt`), la instalación se bloquea. Esto permite a la IA construir software autónomamente sin convertir el host en una responsabilidad.

Política de divulgación completa y versiones soportadas: [SECURITY.md](./SECURITY.md)

***

## 🖥️ App de Escritorio Nativa (Windows)

ShibaClaw ofrece un **Lanzador de Escritorio Windows** totalmente integrado, construido con `pywebview`.  
Ofrece una experiencia local sin necesidad de gestionar ventanas de terminal en segundo plano.

- **Integración con Bandeja del Sistema**: Cierra la ventana para minimizar ShibaClaw silenciosamente a la bandeja. Clic derecho en el icono Shiba para reabrir la UI, acceder a logs del espacio de trabajo, visitar el sitio o salir del motor con elegancia.
- **Auto-Login**: Al usar el Lanzador de Escritorio localmente, la autenticación WebUI se omite por defecto para una experiencia local-first más fluida.
- **WebUI Integrada**: No necesitas abrir tu propio navegador; la WebUI corre en un marco de ventana nativo dedicado.
- **Portátil y Ligera**: Empaquetada como carpeta independiente única con PyInstaller para ejecutarse al instante sin requerir Python en el host.

Si instalaste vía `pip`:
```bash
shibaclaw desktop
```

O descarga el ejecutable Windows preconstruido directamente desde la última release:

> **[⬇ Descargar ShibaClaw.exe (última)](https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip)**  
> Notas completas de la release → [github.com/RikyZ90/ShibaClaw/releases/latest](https://github.com/RikyZ90/ShibaClaw/releases/latest)

***

## 🌐 WebUI

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

La WebUI está integrada — no requiere frontend separado ni Node.js.

Expónla en tu red local y abre la misma URL desde tu móvil o tablet — sin apps extra, solo un navegador.

- **Chat** — conversaciones multi-sesión con streaming en vivo de llamadas a herramientas, bloques de pensamiento, tiempo transcurrido y cambio de modelo por sesión desde el pie del chat
- **RAG Local y Bases de Conocimiento** — arrastra y suelta o sube documentos (PDF, CSV, HTML, TXT) para crear colecciones locales, consúltalas vía búsqueda semántica y fija colecciones activas a sesiones
- **Menciones de Contexto (@)** — autocompleta y vincula bases de conocimiento, servidores MCP y apps conectadas en tus mensajes usando `@`
- **Búsqueda de modelos multi-proveedor** — un selector unificado buscable fusiona modelos de todos los proveedores configurados, muestra etiquetas de proveedor y cambia el proveedor runtime en vivo al cambiar el modelo de sesión
- **Perfiles de Agente** — cambia personalidades por sesión (Hacker, Builder, Planner, Reviewer) con avatares dinámicos
- **Navegador de archivos** — navega, ve y edita archivos del espacio de trabajo en el navegador (sandbox limitado al espacio de trabajo)
- **Voz** — speech-to-text vía APIs de audio compatibles con OpenAI y TTS nativo del navegador
- **Configuración** — configura modelo de sesión por defecto, modelo de memoria/consolidación, proveedores, herramientas, servidores MCP, canales, skills y OAuth desde un panel único
- **Asistente de inicio** — configuración guiada primera vez: elige proveedor, ingresa API key o inicia OAuth, elige modelo
- **Visor de contexto** — inspecciona el prompt de sistema completo y desglose de uso de tokens
- **Monitor de gateway** — health check y reinicio con un clic
- **Flujos OAuth** — GitHub Copilot, OpenAI Codex y OpenRouter configurables desde el modal de ajustes; OpenRouter guarda la API key devuelta directamente en ajustes del proveedor
- **Renderizado endurecido** — chat Markdown escapa HTML crudo, nombres de archivo renderizan mediante nodos DOM seguros, auth expirada regresa limpiamente a login sin bucles de reconexión
- **Auto-actualización** — comprueba releases de GitHub cada 12h, notifica en la UI y en todos los canales activos
- **Centro de Notificaciones (WIP)** — icono de campana con badge de no leídos, push WebSocket en tiempo real, deep-link por notificación a la sesión relacionada; cubre automatizaciones en segundo plano, respuestas del agente y alertas de actualización
- **Responsiva** — funciona genial en escritorio y móvil; abre la misma UI del agente desde tu sofá, no solo desde tu escritorio

### ⚡ Selección Dinámica de Modelo

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

Cambia modelos por sesión — ya no un único modelo global, sino una elección flexible para cada conversación.

- **Búsqueda Multi-Proveedor**: Busca todos los modelos de todos tus proveedores configurados (OpenRouter, GitHub Copilot, Anthropic, etc.) en un solo desplegable.
- **Enrutamiento Consciente de Sesión**: Cada sesión recuerda su modelo elegido. Puedes tener una sesión de código con `Claude 3.5 Sonnet` y una de investigación con `Gemma 4` simultáneamente.
- **Cambio en Tiempo de Ejecución**: Cambia modelos instantáneamente sin reiniciar el agente; el gateway resuelve automáticamente el endpoint correcto basado en el modelo seleccionado.
- **Modelo de Memoria Dedicado**: Configura un modelo y proveedor separados específicamente para consolidación de memoria y aprendizaje proactivo, asegurando extracción de estado de alta calidad sin afectar tu presupuesto de chat.
- **Por Defecto Primero**: Nuevas sesiones inician automáticamente con el modelo por defecto configurado en ajustes, asegurando consistencia inmediata.

### 🤖 Perfiles de Agente

Cambia la personalidad del agente sobre la marcha sin perder contexto. Cada perfil sobrescribe el prompt de sistema (SOUL.md) manteniendo modelo, memoria y herramientas compartidos. Perfiles por sesión — ejecuta una auditoría de seguridad en una pestaña y planifica arquitectura en otra.

Perfiles integrados: Default · Builder · Planner · Reviewer · <b>Hacker</b> (experto en seguridad élite con 50+ recomendaciones de herramientas, metodologías OWASP/MITRE/NIST, puntuación CVSS y avatar cyber-shiba personalizado).

Crea tus propios perfiles interactivamente — el agente te guía definiendo la persona y guarda todo automáticamente.

***

## 🧠 Sistema Avanzado de Memoria de 3 Niveles

La memoria de ShibaClaw no es solo un buffer de chat rodante; es un sistema estructurado y proactivo diseñado para continuidad operacional a largo plazo.

- **`USER.md` (Identidad y Preferencias):** Almacena hechos personales duraderos, estilos de comunicación y preferencias de idioma. El agente lee esto para saber <i>quién eres</i>.
- **`MEMORY.md` (Estado Operacional):** El conocimiento de trabajo del agente. Rastrea detalles del entorno, entidades recurrentes y estado del proyecto.
- **`HISTORY.md` (Archivo de Sesiones):** Un ledger solo-apéndice, buscable, de sesiones pasadas con resúmenes etiquetados y con marca de tiempo.

En lugar de inflar el prompt de sistema con miles de mensajes, ShibaClaw cuenta con un **bucle de Aprendizaje Proactivo**. Cada N mensajes, un proceso LLM en segundo plano extrae silenciosamente nuevos hechos duraderos y actualiza `USER.md` y `MEMORY.md`, sin interrumpir la conversación. Cuando `MEMORY.md` crece demasiado, una rutina de auto-compactación resume y deduplica el contexto, priorizando estado reciente mientras mantiene el uso de tokens dentro de presupuestos estrictos. Cuando el agente necesita contexto más antiguo, puede buscar autónomamente `HISTORY.md` usando TF-IDF y puntuación de recencia. Esta separación de preocupaciones asegura que el agente se mantenga hiper-consciente del proyecto actual sin nunca tocar límites de tokens o perder foco.

***

## 🛠️ Funciones

### Flujo de Trabajo y Razonamiento

- **Enrutamiento de sesión modelo-primero** — cada sesión almacena su propio modelo seleccionado, y ShibaClaw resuelve el backend de proveedor correcto desde ese modelo en tiempo de ejecución
- **Delegación de fondo enfocada** — la herramienta `spawn` puede descargar una tarea específica y reportar de vuelta a la sesión principal cuando termina
- **Razonamiento avanzado** — soporta pensamiento extendido (Anthropic), esfuerzo de razonamiento (OpenAI o-series) y cadenas DeepSeek-R1

### Herramientas

| Herramienta | Qué hace |
|------|-------------|
| `exec` | Comandos shell con 20+ guardias de patrones de denegación, normalización de encoding y escaneo CVE |
| `read_file` / `write_file` / `edit_file` | Lecturas paginadas, reemplazo difuso búsqueda-y-reemplaza, directorios padre auto-creados |
| `web_search` | Brave, Tavily, SearXNG, Jina o DuckDuckGo (fallback, sin key necesaria) |
| `web_fetch` | HTTP fetch con protección SSRF, defensa DNS rebinding y validación de redirección |
| `memory_search` | Búsqueda rankeada sobre historial de sesión (TF-IDF + recencia + puntuación de importancia) |
| `knowledge_search` | Búsqueda semántica sobre colecciones locales de Base de Conocimiento activas/mencionadas (FAISS vector store) |
| `message` | Mensajería cross-canal con adjuntos multimedia |
| `automation` | Gestiona o programa trabajos en segundo plano (expresiones cron, intervalos, fechas ISO, timezone-aware) |
| `spawn` | Worker de fondo opcional para una tarea enfocada; reporta de vuelta a la sesión principal cuando termina |
| MCP | Conecta cualquier servidor MCP (stdio, SSE o streamable HTTP) — herramientas auto-registradas como `mcp_<server>_<tool>` |

### Canales

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

Todos los canales enrutan a través del mismo bus de mensajes. WhatsApp usa un bridge Node.js (Baileys) para enlace basado en QR.

### Skills

8 skills integradas (GitHub, weather, summarize, tmux, automation, memory guide, skill-creator, ClawHub browser). Las skills son archivos Markdown con frontmatter YAML y scripts opcionales — crea las tuyas o instala desde [ClawHub](https://clawhub.ai/). Fija skills usadas frecuentemente para cargarlas en cada conversación.

### Automatización

- **Motor de Automatizaciones** — trabajos programados persistentes, timezone-aware y rutinas de intervalo en segundo plano gestionadas vía modal UI unificado y almacenadas en `automation.json`. Soporta `every`, `cron` y `at`. Trabajos perdidos se adelantan automáticamente al inicio para evitar tormentas de ejecución.
- **Integración TASK.md** — el motor usa `TASK.md` como fuente de verdad unificada para rutinas de fondo, saltando el LLM completamente cuando las tareas están vacías para ahorrar tokens y procesando solo directivas activas.

Si actualizas desde una release antigua, `HEARTBEAT.md` ha sido deprecado y removido. Tus tareas y horarios deben migrarse a `TASK.md` y la nueva UI de Automatizaciones.

### 🔌 Plugins y TTS (Texto a Voz)

- **Sistema de Plugins Instalables** — Extiende las capacidades del agente con plugins Python dinámicos e instalables (ej. síntesis de voz, integraciones personalizadas) gestionados directamente desde los ajustes de la WebUI. Ver [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) para cómo construir los tuyos.
- **TTS Local Offline Gratuito (Supertonic)** — Obtén text-to-speech de alta calidad, cero coste, totalmente offline out of the box con el plugin **Supertonic TTS** (síntesis de voz basada en ONNX). Soporta 31 idiomas, voces personalizadas (`F1` / `M1`) y velocidad de habla ajustable, sintetiza automáticamente respuestas de voz.
- **Reproductor de Audio en Navegador** — Reproduce los mensajes de voz del agente directamente dentro de la UI del chat vía un widget de audio glassmórfico personalizado con timeline buscable y control de duración.

***

## 🔌 Ecosistema MCP

ShibaClaw es totalmente compatible con el **Model Context Protocol (MCP)**, transformando el agente de una herramienta standalone en un hub de IA plug-and-play.

En lugar de depender solo de skills integradas, ShibaClaw puede conectar a cualquier servidor MCP-compliant, otorgando instantáneamente a tu agente acceso a un vasto universo de fuentes de datos externas y herramientas profesionales sin modificar una sola línea de código del núcleo.

Por qué importa:
- **Extensibilidad Instantánea**: Conecta servidores MCP hechos por la comunidad para Google Drive, Slack, GitHub, PostgreSQL y más.
- **Herramientas Estandarizadas**: Aprovecha un protocolo universal para comunicación IA-a-herramienta, asegurando estabilidad e interoperabilidad.
- **Arquitectura Desacoplada**: Mantén tu agente ligero mientras escalas sus capacidades a través de una red distribuida de servidores MCP.

Configura tus servidores MCP directamente en el panel **Configuración** para empezar a expandir los horizontes de ShibaClaw.

### 🌐 Apps (Integración Klavis)

Para hacer la configuración de herramientas SaaS populares (como Gmail, Google Drive, Google Docs, Slack, GitHub, Outlook, etc.) lo más fluida posible, ShibaClaw se integra con **Klavis** (`klavis.ai`).

En lugar de forzar a usuarios a crear manualmente credenciales de desarrollador individuales, configurar pantallas de consentimiento OAuth y establecer URLs de redirección para cada servicio en Google Cloud o Microsoft Azure console, ShibaClaw permite gestionar todas estas integraciones vía una interfaz unificada **Connected Apps**:

- **Una Sola API Key**: Solo obtén una API key de [klavis.ai](https://klavis.ai) y guárdala en los ajustes del Backend de ShibaClaw.
- **Conexiones en Un Clic**: Conecta o desconecta Gmail, Slack y otros servicios con un clic usando login OAuth seguro gestionado directamente por el gateway Klavis.
- **Servidores MCP Auto-Generados**: Una vez que una app está conectada, ShibaClaw configura automáticamente el servidor MCP apropiado con herramientas estándar, registrándolas sin fisuras en la sesión activa del agente.

***

## 🌐 Proveedores Soportados

ShibaClaw usa SDKs nativos (sin proxy LiteLLM) y resuelve el proveedor activo desde el modelo seleccionado o el ID de modelo canónico con prefijo de proveedor. En la WebUI, todos los catálogos de proveedores configurados se fusionan en una lista única buscable, mientras cada sesión mantiene su propio modelo elegido.

### API Key

| Proveedor | Variable de Entorno |
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

¹ Establecer `GEMINI_API_KEY` en el entorno es suficiente — no se requiere key almacenada. El endpoint OpenAI-compatible de Google está pre-configurado.

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — auto-detectados por prefijo de key o `api_base`.

### Local

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · cualquier endpoint OpenAI-compatible(`http://localhost:1234/v1`)

> **Nota para usuarios Docker:** Si ejecutas ShibaClaw vía Docker Compose, `localhost` apunta dentro del contenedor. Para conectar a un servidor local en tu máquina host (como LM Studio u Ollama en Windows/Mac), usa:
> `http://host.docker.internal:1234/v1` (o `11434` para Ollama). En Linux nativo, usa `http://172.17.0.1:port`.

### OAuth

| Proveedor | Flujo | Configuración |
|----------|------|-------|
| OpenRouter | Flujo PKCE navegador, guarda la API key devuelta en config del proveedor | Ajustes WebUI |
| GitHub Copilot | Flujo dispositivo, auto-refresh de token | `shibaclaw provider login github-copilot` o Ajustes WebUI |
| OpenAI Codex | Flujo PKCE navegador | `shibaclaw provider login openai-codex` o Ajustes WebUI |

Para OpenRouter, el callback reusa la URL y puerto actual de la WebUI por defecto, así que `http://localhost:3000` no es un puerto dedicado solo OAuth. Si expones la WebUI detrás de un proxy inverso o necesitas un origen de callback público diferente, establece `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` antes de iniciar el servidor.

### 💡 Consejo Pro: Modelos Económicos y Premium

ShibaClaw rinde excepcionalmente bien incluso sin uso costoso de API:
- **Modelos Gratis/Abiertos:** Recomendamos encarecidamente usar **OpenRouter** para acceder a modelos gratuitos potentes como `nvidia/nemotron-3-super-120b-a12b:free` o `gemma-4-31b-it:free`.
- **Premium Ilimitado:** Si usas la integración OAuth de **GitHub Copilot**, obtienes acceso a modelos premium como `raptor` (`oswe-vscode-prime`) a coste cero adicional, dándote efectivamente requests ilimitados.

***

## 📊 Cómo Compara ShibaClaw (Seguridad-primero)

> Esta tabla es una **instantánea aproximada centrada en seguridad**, basada solo en lo documentado explícitamente en repos/docs públicos a mayo 2026.  
> `❓` significa "no claramente documentado / no verificado", <b>no</b> "no existe".

| Característica de Seguridad | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| Auditoría CVE en instalación (pip, npm, apt) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Envoltura de inyección de prompts en cada resultado de herramienta | ✅ | ❌ | ❌ | ❌ | ❌ |
| Protección SSRF + DNS-rebinding integrada | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClaw se enfoca en enviar estas defensas en el motor del núcleo, activadas por defecto, para que no tengas que pegar escáneres y proxies externos solo para correr un agente de forma segura.

***

## 🏗️ Arquitectura

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Servicio | Rol | Puerto Por Defecto |
|---------|------|--------------|
| `shibaclaw-gateway` | Bucle del agente central, bus de mensajes, integraciones de canal | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket nativo), servicio de automatizaciones | 3000 |

Ambos comparten el volumen `~/.shibaclaw/` (config, espacio de trabajo, memoria, trabajos de automatización, caché de medios).

### Modo Single-proceso

`shibaclaw web` ejecuta agente + WebUI + automatizaciones en un solo proceso — sin contenedor gateway necesario.

### Stack

| Capa | Tecnología |
|-------|-----------|
| Servidor | Uvicorn → Starlette (ASGI) |
| Tiempo real | WebSocket nativo (`/ws` en WebUI, puerto `19998` en gateway) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sesiones | JSONL solo-apéndice por sesión (cache-friendly para prefijos de prompt LLM) |

### Uso de recursos

| Componente | Inactivo | Pico (instalar/compilar) |
|-----------|------|------------------------|
| Gateway | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Compose establece límite de 512 MB / reserva de 256 MB por contenedor. La salida de herramientas se transmite con buffers acotados, así que comandos de larga duración (`apt`, `npm install`) no pueden inflar la memoria.

***

## 🔧 Referencia CLI

```bash
shibaclaw web               # Inicia WebUI (agente + automatizaciones in-process)
shibaclaw gateway           # Inicia solo gateway (para Docker split)
shibaclaw onboard           # Asistente de configuración inicial basado en CLI
shibaclaw agent -m "Hello"  # Mensaje único vía terminal
shibaclaw agent             # REPL interactivo con historial
shibaclaw status            # Health check de proveedor, espacio de trabajo, OAuth
shibaclaw print-token       # Muestra token de auth WebUI
shibaclaw channels status   # Lista canales habilitados
shibaclaw provider login <p># Login OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Lanza app de escritorio Windows
```

***

## 🐛 Solución de Problemas

| Problema | Intenta |
|---------|-----|
| Chequeo general de estado | `shibaclaw status` |
| Logs de contenedor | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI no conecta | Verifica token con `shibaclaw print-token`, verifica binding de puerto |
| Errores de proveedor | `shibaclaw status` muestra API key y estado OAuth |
| Política de seguridad | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 Contribuir

Ver [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs bienvenidos.

Plugins (tanto canales como motores TTS) son extensibles vía Python entry points. Ver [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) para una guía completa sobre construcción de plugins personalizados.Creación de skills documentada en [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) y el skill integrado `skill-creator`.

Integradores de gateway: ver [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) para el contrato WebSocket en puerto `19998`.

***

## 🌟 Únete a la Manada ShibaClaw

ShibaClaw es construido por un desarrollador, mantenido por la comunidad, y creciendo rápido.  
Si te ahorró tiempo, aseguró tu flujo de trabajo, o solo te hizo sonreír — <b>deja una estrella</b> ⭐

> "El agente de IA que simplemente funciona. Sin supervisión requerida." 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Star el repo</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">Cómprame un café</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Abre un issue</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Envía un PR</a>
</p>