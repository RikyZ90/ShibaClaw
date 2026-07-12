<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw 🐕</h1>
<h3 align="center">Der KI-Agent, der <b>einfach funktioniert</b> — sicher, privat und ohne Babysitting.</h3>

> Übersetzung von [README.md](./README.md) — möglicherweise nicht aktuell (synchronisiert mit v0.9.4).

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28 Anbieter · 11 Chat-Kanäle · Integrierte WebUI · Sicherheits-Fokus · MCP-bereit</b>
</p>

<h3 align="center">Auf drei Säulen gebaut: <b>Einfachheit · Sicherheit · Privatsphäre</b></h3>

<p align="center">
  🌐 <a href="./README.zh-CN.md">简体中文</a> &nbsp;·&nbsp;
  <a href="./README.es.md">Español</a> &nbsp;·&nbsp;
  <a href="./README.pt-BR.md">Português (BR)</a> &nbsp;·&nbsp;
  <a href="./README.ja.md">日本語</a> &nbsp;·&nbsp;
  <a href="./README.de.md">Deutsch</a> &nbsp;·&nbsp;
  <a href="./README.fr.md">Français</a>
</p>

***

<details open>
<summary>📢 <b>Neueste Version: v0.9.5 (Big Release & Refactor)</b> — Klicken für Neuerungen</summary>

- **🔥 Big Security Refactor & 🔐 Verschlüsselter Credentials-Tresor** — Wir haben die Sicherheit komplett überarbeitet. ShibaClaw nutzt jetzt einen robusten AES-128/256 symmetrisch verschlüsselten Tresor (`credentials.enc` und `credentials.key`), um API-Schlüssel, Bot-Tokens und Passwörter sicher zu speichern. Features: Tresor-First-Auflösung, Thread-Sicherheit, Anti-Korruptionsschutz und strenge OS-Level-Berechtigungen (`0o600` auf Unix und `icacls` ACLs auf Windows).
- **🌐 Native OAuth- & Device-Code-Flows** — Nahtlose, native Authentifizierungs-Flows direkt in der WebUI hinzugefügt. Sie können sich jetzt mühelos über **xAI / Grok**, **GitHub Copilot**, **Google Gemini CLI**, **OpenAI Codex** und **OpenRouter** anmelden, ohne jemals einen API-Schlüssel berühren zu müssen!
- **🤖 Unterstützung für neue Anbieter** — Umfassende Integrationen für **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** und **Z.AI** hinzugefügt, wodurch Sie sofortigen Zugriff auf die besten State-of-the-Art-Modelle auf dem Markt haben.
- **🛡️ Gehärtete Kanalauflösung** — Komplette Auflösungs-Updates für Discord, DingTalk, Feishu, QQ, MoChat und das WhatsApp-Kanal-Plugin.
- **⚡ Blitzschnelle WebUI & Polierte UX** — Das Frontend wurde auf eine vollständig gebündelte ES6-Architektur via `esbuild` für sofortiges Laden migriert, und die Connected Apps UX wurde geglättet, um eine nahtlose Klavis-Backend-Konfiguration ohne manuelles Neuladen zu ermöglichen.

Vollständiger Verlauf im [Changelog](./CHANGELOG.md).

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ Schnellstart

### 🚀 Automatischer Installer (Empfohlen)

Der einfachste Einstieg. Ein Befehl lädt das neueste Release herunter, erstellt Verknüpfungen und startet die UI.

**Bring dein eigenes Modell mit**: Verbinde dich nahtlos mit lokalen Endpunkten (Ollama, LM Studio) oder nutze kostenlose API-Tiers über OpenRouter für Chats ohne Kosten.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **Hinweis**: Unter Windows wird die vorgebaute Desktop-App aus dem neuesten GitHub-Release geladen — kein Python nötig. Verknüpfungen auf Desktop und Startmenü werden automatisch erstellt, und die App erscheint unter „Apps & Features“ für saubere Deinstallation. Unter Linux/macOS installiert das Skript via pip in einer isolierten virtuellen Umgebung.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # zieht von Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Öffne **http://localhost:3000**, füge das Token ein und folge dem Onboard-Wizard.

Lege `shibaclaw-web` in deinem LAN offen (z. B. per Reverse-Proxy) und öffne dieselbe URL am Handy für den Agenten mobil.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # startet WebUI + Agent-Engine auf :3000
```

Öffne **http://localhost:3000** und folge dem Wizard.  
Lieber CLI? `shibaclaw onboard` führt dasselbe geführte Setup im Terminal aus.

***

## ✨ Alles in einem Agenten

<table>
<tr>
<td align="center" width="33%">

### 🛡️ Sicherheit zuerst
CVE-Audit, Prompt-Injection-<br>Wrap, SSRF-Guard — <b>standardmäßig an</b>

</td>
<td align="center" width="33%">

### 🧠 Smart Memory
3-Ebenen-System mit proaktivem<br>Lernen & Auto-Kompaktierung

</td>
<td align="center" width="33%">

### 🌐 28 Anbieter
Native SDKs, kein LiteLLM-Proxy<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Web & Mobile
WebUI im LAN bereitstellen und<br>denselben Agenten vom Handy nutzen

</td>
<td align="center" width="33%">

### 🖥️ Desktop-App
Nativer Windows-Launcher mit Tray,<br>perfekt mit der WebUI kombiniert

</td>
<td align="center" width="33%">

### 🔌 MCP-bereit
Beliebigen MCP-Server verbinden,<br>Tools automatisch registriert

</td>
</tr>
</table>

***

## Warum ShibaClaw? Einfach funktionieren. 🐕

> **Genervt von Agenten, die mehr Babysitting brauchen als deine eigentliche Arbeit?**  
> ShibaClaw folgt einem Prinzip: <b>es funktioniert einfach</b> — sicher, zuverlässig und ohne ständige Wartung.

Die meisten KI-Agenten-Frameworks behandeln Sicherheit als Afterthought, lassen dich mit Anbieterkompatibilität kämpfen oder zwingen dich, Konfigurationen zu hüten. ShibaClaw dreht den Spieß um: Sicherheit ist nicht angeschraubt, sie ist <b>das Fundament</b>.

Was ShibaClaw anders macht:
- **Sicherheitsschichten im Kern** — CVE-Audit bei Installation, Prompt-Injection-Wrap bei jedem Tool-Ergebnis, SSRF/DNS-Rebinding-Schutz
- **Native Anbieter-Unterstützung** — 28 Anbieter über deren offizielle SDKs, keine Proxy-Schicht zum Debuggen
- **Setup mit einem Befehl** — Docker oder pip, dem Wizard folgen, in etwa einer Minute chatten
- **Überall lauffähig** — Terminal, WebUI, Discord, Telegram, WhatsApp, Windows-Desktop-App und mehr

***

## 🛡️ Sicherheit, eingebaut

Abwehrmaßnahmen, die normalerweise in App-Glue oder externe Proxies verstreut sind — in ShibaClaw sind sie im Kern enthalten, <b>standardmäßig an</b>.

### Kern-Sicherheitsschichten

| Schicht | Was sie tut |
|---|---|
| 🔍 Audit bei Installation | Prüft `pip` und `npm` vor der Ausführung — blockiert kritische/hohe CVEs, bevor sie landen |
| 🛡️ Prompt-Injection-Wrap & Vorab-Scan | Kapselt jedes Tool-Ergebnis in eine zufällige `<tool_output_...>`-Grenze. Wendet Regex-Vorab-Scan auf Jailbreaks und **Base64-Kodierung** für unvertrauenswürdige Payloads an |
| 🔒 Shell-Härtung | 20+ Ablehnungsmuster, Escape-Normalisierung (`\x..`, `\u....`), interne-URL-Erkennung |
| ⚡ Local-First-Engine | Nativer Command-Emulator (`ls`, `cat`) umgeht Subprocess-Overhead; offline-zuerst `tiktoken`-Fallback für Air-Gapped-Ausführung |
| 🌐 Netzwerk-Guard | SSRF-Filterung, Redirect-Revalidierung, DNS-Rebinding-sichere Auflösung |
| 📁 Workspace-Sandbox | Datei-Tools und Datei-Browser auf den konfigurierten Workspace gesperrt |
| 🔑 Zugriffskontrolle | Bearer-Token-Auth, konstante Zeitprüfung, Kanal-Allowlists, optionales Rate-Limiting |
| 🧠 Verteiltes Engine | UI (≈128 MB) entkoppelt vom Agenten-Gehirn (≈256 MB+) — minimaler Footprint pro Prozess |

### 🛡️ Prompt-Injection-Wrapping (Tool-Sandboxing)

Anstatt rohe Tool-Ausgaben einfach zurück an das LLM zu füttern, kapselt ShibaClaw jedes Ergebnis in eine dynamisch generierte XML-artige Grenze mit einem <b>zufälligen Nonce</b> (z. B. `<tool_output_a1b2c3d4>`).

> 💡 <b>Eigenständige Verteidigung</b>: Dieser Kern-Sicherheitsmechanismus (Randomized Tool Output Wrapping) wurde als eigenständige, abhängigkeitsfreie Python-Bibliothek [Muzzle](https://github.com/RikyZ90/Muzzle) ausgekoppelt. Du kannst Muzzle nutzen, um jedes Agenten-Framework (LangChain, LlamaIndex, CrewAI, AutoGen oder eigene LLM-Loops) mit derselben Technik zu schützen.

Warum das wichtig ist: Angreifer versuchen oft, Tags vorzeitig zu schließen oder gefälschte Systemanweisungen in Tool-Ausgaben (wie Webseiteninhalte) einzuschleusen. Durch eine pro Iteration zufällig erzeugte Grenze kann der Agent echte Systemanweisungen zuverlässig von injizierten Payloads unterscheiden. Zudem wird jeder Versuch, das spezifische schließende Tag im Inhalt einzuschleusen, automatisch bereinigt und escaped — die Sandbox bleibt dicht und der ursprüngliche System-Prompt hat Vorrang.

### 🔍 Paket-Auto-Scan bei Installation

Bevor ShibaClaw einen `pip`-, `npm`- oder `apt`-Installationsbefehl ausführt, fängt es die Aktion ab und parst die Abhängigkeiten. Es führt Werkzeuge wie `pip-audit` oder `npm audit --json` aus, um bekannte Schwachstellen gegen CVE-Datenbanken zu scannen, bevor Änderungen angewendet werden.

Warum das wichtig ist: Es verschiebt die Sicherheit vollständig nach links. Statt Paketmanager blind zu blockieren oder auf Post-Install-Scans zu vertrauen, wird der exakte Abhängigkeitsbaum <i>vor</i> der Ausführung bewertet. Enthält ein Paket kritische/hohe CVEs oder werden verdächtige Flags (wie `--allow-unauthenticated` für `apt`) erkannt, wird die Installation blockiert. So kann die KI autonom Software bauen, ohne den Host zur Last zu machen.

Offenlegungsrichtlinie und unterstützte Versionen: [SECURITY.md](./SECURITY.md)

***

## 🖥️ Native Desktop-App (Windows)

ShibaClaw bietet einen voll integrierten **Windows Desktop-Launcher** auf Basis von `pywebview`.  
Er liefert ein nahtloses lokales Erlebnis, ohne Hintergrund-Terminalfenster verwalten zu müssen.

- **Tray-Integration**: Fenster schließen, um ShibaClaw lautlos in die Taskleiste zu minimieren. Rechtsklick auf das Shiba-Symbol öffnet die UI erneut, zeigt Workspace-Logs, öffnet die Website oder beendet die Engine sauber.
- **Auto-Login**: Bei lokaler Nutzung des Desktop-Launchers ist die WebUI-Authentifizierung standardmäßig umgangen für ein flüssigeres Local-First-Erlebnis.
- **Eingebettete WebUI**: Kein eigener Browser nötig; die WebUI läuft in einem dedizierten nativen Fensterrahmen.
- **Portabel & leicht**: Als einzelner eigenständiger Ordner mit PyInstaller gepackt, läuft sofort ohne Python auf dem Host.

Bei Installation via `pip`:
```bash
shibaclaw desktop
```

Oder lade die vorgebaute Windows-EXE direkt aus dem neuesten Release:

> **[⬇ ShibaClaw.exe herunterladen (neueste)](https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip)**  
> Vollständige Release-Notes → [github.com/RikyZ90/ShibaClaw/releases/latest](https://github.com/RikyZ90/ShibaClaw/releases/latest)

***

## 🌐 WebUI

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

Die WebUI ist integriert — kein separates Frontend oder Node.js nötig.

Lege sie in deinem lokalen Netzwerk offen und öffne dieselbe URL vom Handy oder Tablet — keine zusätzlichen Apps, nur ein Browser.

- **Chat** — Multi-Session-Unterhaltungen mit Live-Streaming von Tool-Aufrufen, Thinking-Blöcken, verstrichener Zeit und pro-Session-Modellwechsel vom Chat-Footer
- **Lokales RAG & Wissensbasen** — Dokumente (PDF, CSV, HTML, TXT) per Drag-and-Drop hochladen, semantisch durchsuchen, aktive Sammlungen an Sessions pinnen
- **Kontext-Erwähnungen (@)** — Autovervollständigung und Bindung von Wissensbasen, MCP-Servern und verbundenen Apps in Nachrichten via `@`
- **Modell-Suche über Anbieter hinweg** — eine suchende Auswahl vereint Modelle aller konfigurierten Anbieter, zeigt Anbieter-Labels und wechselt den Live-Runtime-Anbieter
- **Agent-Profile** — Persönlichkeiten pro Session wechseln (Hacker, Builder, Planner, Reviewer) mit dynamischen Avataren
- **Datei-Browser** — Workspace-Dateien im Browser durchsuchen, ansehen und bearbeiten (Sandbox)
- **Sprache** — Sprache-zu-Text über OpenAI-kompatible Audio-APIs und browser-natives TTS
- **Einstellungen** — Standard-Session-Modell, Memory/Konsolidierungsmodell, Anbieter, Tools, MCP-Server, Kanäle, Skills und OAuth aus einem Panel
- **Onboard-Wizard** — geführtes Erst-Setup: Anbieter wählen, API-Key eingeben oder OAuth starten, Modell wählen
- **Kontext-Viewer** — vollständigen System-Prompt und Token-Aufschlüsselung prüfen
- **Gateway-Monitor** — Health-Check und One-Click-Restart
- **OAuth-Flows** — GitHub Copilot, OpenAI Codex und OpenRouter konfigurierbar aus dem Einstellungs-Modal
- **Gehärtetes Rendering** — Chat-Markdown escaped rohes HTML, Dateinamen über sichere DOM-Knoten, abgelaufene Auth kehrt sauber zum Login zurück
- **Auto-Update** — prüft GitHub-Releases alle 12h, benachrichtigt in der UI und auf allen aktiven Kanälen
- **Benachrichtigungszentrum (WIP)** — Glocken-Icon mit Ungelesen-Badge, Echtzeit-WebSocket-Push, Deep-Link pro Benachrichtigung
- **Responsiv** — läuft großartig auf Desktop und Mobile

### ⚡ Dynamische Modellauswahl

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

Modelle pro Session wechseln — kein einzelnes globales Modell mehr, sondern eine flexible Wahl pro Konversation.

- **Multi-Anbieter-Suche**: Durchsuche alle Modelle aller konfigurierten Anbieter (OpenRouter, GitHub Copilot, Anthropic etc.) in einem Dropdown.
- **Session-bewusstes Routing**: Jede Session merkt sich ihr gewähltes Modell. Du kannst eine Coding-Session mit `Claude 3.5 Sonnet` und eine Research-Session mit `Gemma 4` gleichzeitig haben.
- **Runtime-Wechsel**: Wechsle Modelle sofort ohne Neustart; das Gateway löst den korrekten Endpunkt automatisch auf.
- **Dediziertes Memory-Modell**: Konfiguriere ein separates Modell und einen Anbieter speziell für Memory-Konsolidierung und proaktives Lernen.
- **Default-First**: Neue Sessions starten automatisch mit dem in den Einstellungen festgelegten Standardmodell.

### 🤖 Agent-Profile

Wechsle die Persönlichkeit des Agenten im laufenden Betrieb ohne Kontextverlust. Jedes Profil überschreibt den System-Prompt (SOUL.md), während Modell, Memory und Tools geteilt werden. Profile sind pro Session.

Eingebaute Profile: Default · Builder · Planner · Reviewer · <b>Hacker</b> (Elite-Sicherheitsexperte mit 50+ Tool-Empfehlungen, OWASP/MITRE/NIST-Methodik, CVSS-Scoring und custom Cyber-Shiba-Avatar).

Erstelle deine eigenen Profile interaktiv.

***

## 🧠 Erweitertes 3-Ebenen-Memory-System

ShibaClaws Memory ist kein rollender Chat-Puffer, sondern ein strukturiertes, proaktives System für langfristige operative Kontinuität.

- **`USER.md` (Identität & Präferenzen):** Speichert dauerhafte persönliche Fakten, Kommunikationsstile und Sprachpräferenzen.
- **`MEMORY.md` (Operativer Zustand):** Das Arbeitswissen des Agenten. Verfolgt Umgebungsdetails, wiederkehrende Entitäten und Projektstatus.
- **`HISTORY.md` (Session-Archiv):** Nur-anhängbares, durchsuchbares Ledger vergangener Sessions mit zeitgestempelten, getaggten Zusammenfassungen.

Statt den System-Prompt mit tausenden Nachrichten aufzublähen, verfügt ShibaClaw über eine **Proactive Learning-Schleife**. Alle N Nachrichten extrahiert ein Hintergrund-LLM-Prozess still neue dauerhafte Fakten und aktualisiert `USER.md` und `MEMORY.md`, ohne das Gespräch zu unterbrechen. Wird `MEMORY.md` zu groß, fasst eine Auto-Kompaktierungsroutine zusammen und dedupliziert, priorisiert kürzlichen Zustand und hält das Token-Budget ein. Braucht der Agent älteren Kontext, kann er `HISTORY.md` autonom via TF-IDF und Aktualitäts-Scoring durchsuchen.

***

## 🛠️ Funktionen

### Workflow & Reasoning

- **Modell-zuerst Session-Routing** — jede Session speichert ihr gewähltes Modell, ShibaClaw löst den korrekten Anbieter-Backend zur Laufzeit auf
- **Fokussierte Hintergrund-Delegation** — das `spawn`-Tool kann eine spezifische Aufgabe abladen und ins Haupt-Session zurückmelden
- **Fortgeschrittenes Reasoning** — unterstützt Extended Thinking (Anthropic), Reasoning Effort (OpenAI o-series) und DeepSeek-R1-Ketten

### Tools

| Tool | Was es tut |
|------|-------------|
| `exec` | Shell-Befehle mit 20+ Ablehnungsmustern, Encoding-Normalisierung und CVE-Scan |
| `read_file` / `write_file` / `edit_file` | Paginiertes Lesen, Fuzzy-Find-Replace, automatisch erstellte Elternverzeichnisse |
| `web_search` | Brave, Tavily, SearXNG, Jina oder DuckDuckGo (Fallback, kein Key nötig) |
| `web_fetch` | HTTP-Fetch mit SSRF-Schutz, DNS-Rebinding-Abwehr und Redirect-Validierung |
| `memory_search` | Gerankte Suche über Session-Verlauf (TF-IDF + Aktualität + Wichtigkeit) |
| `knowledge_search` | Semantische Suche über aktive/erwähnte lokale Wissensbasis-Sammlungen (FAISS-Vektorspeicher) |
| `message` | Cross-Channel-Messaging mit Medienanhängen |
| `automation` | Hintergrundjobs verwalten oder planen (cron-Ausdrücke, Intervalle, ISO-Daten, zeitzonenbewusst) |
| `spawn` | Optionaler Hintergrund-Worker für eine fokussierte Aufgabe; meldet zurück ins Haupt-Session |
| MCP | Beliebigen MCP-Server verbinden (stdio, SSE oder streamable HTTP) — Tools automatisch als `mcp_<server>_<tool>` registriert |

### Kanäle

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

Alle Kanäle laufen über denselben Message-Bus. WhatsApp nutzt eine Node.js-Bridge (Baileys) für QR-basierte Verknüpfung.

### Skills

8 eingebaute Skills (GitHub, weather, summarize, tmux, automation, memory guide, skill-creator, ClawHub browser). Skills sind Markdown-Dateien mit YAML-Frontmatter und optionalen Skripten — erstelle eigene oder installiere von [ClawHub](https://clawhub.ai/).

### Automatisierung

- **Automatisierungs-Engine** — persistente, zeitzonenbewusste geplante Jobs und Hintergrund-Intervalle, verwaltet via einheitlichem UI-Modal und in `automation.json` gespeichert. Unterstützt `every`, `cron` und `at`. Verpasste Jobs werden beim Start automatisch vorgespult.
- **TASK.md-Integration** — die Engine nutzt `TASK.md` als alleinige Quelle der Wahrheit für Hintergrund-Routinen und überspringt das LLM, wenn Aufgaben leer sind.

Beim Upgrade von einer älteren Release wurde `HEARTBEAT.md` veraltet und entfernt. Migriere deine Aufgaben und Zeitpläne zu `TASK.md` und der neuen Automatisierungs-UI.

### 🔌 Plugins & TTS (Text-to-Speech)

- **Installierbares Plugin-System** — Erweitere die Fähigkeiten des Agenten mit dynamischen, installierbaren Python-Plugins (z. B. Sprachsynthese, Custom-Integrationen), direkt aus den WebUI-Einstellungen verwaltet. Siehe [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).
- **Kostenloses Offline-TTS (Supertonic)** — Hochwertige, null-Kosten, vollständig offline Text-zu-Sprache out of the box mit dem **Supertonic TTS**-Plugin (ONNX-basierte Sprachsynthese). Unterstützt 31 Sprachen, Custom-Voices (`F1` / `M1`) und einstellbare Sprechgeschwindigkeit.
- **In-Browser-Audio-Player** — spielt Sprachnachrichten des Agenten direkt im Chat-UI via einem glassmorphen Audio-Widget mit seekbarer Timeline.

***

## 🔌 MCP-Ökosystem

ShibaClaw ist vollständig kompatibel mit dem **Model Context Protocol (MCP)** und verwandelt den Agenten von einem Standalone-Tool in einen Plug-and-Play-KI-Hub.

Anstatt nur auf eingebaute Skills zu vertrauen, kann ShibaClaw mit jedem MCP-konformen Server verbinden und dem Agenten sofort Zugriff auf ein riesiges Universum externer Datenquellen und professioneller Tools geben, ohne eine einzige Zeile Kerncode zu ändern.

Warum das wichtig ist:
- **Sofortige Erweiterbarkeit**: Schließe Community-MCP-Server für Google Drive, Slack, GitHub, PostgreSQL und mehr an.
- **Standardisierte Tooling**: Nutze ein universelles Protokoll für KI-zu-Tool-Kommunikation, für Stabilität und Interoperabilität.
- **Entkoppelte Architektur**: Halte deinen Agenten schlank, während du seine Fähigkeiten über ein verteiltes Netzwerk von MCP-Servern skalierst.

Konfiguriere deine MCP-Server direkt im **Einstellungs**-Panel.

### 🌐 Apps (Klavis-Integration)

Um beliebte SaaS-Tools (wie Gmail, Google Drive, Google Docs, Slack, GitHub, Outlook etc.) so nahtlos wie möglich einzurichten, integriert ShibaClaw mit **Klavis** (`klavis.ai`).

Anstatt Benutzer zu zwingen, für jeden Dienst einzeln Entwickler-Credentials auf Google Cloud oder Microsoft Azure zu erstellen, OAuth-Consent-Screens einzurichten und Redirect-URLs zu setzen, verwaltest du all diese Integrationen über eine einheitliche **Connected Apps**-Schnittstelle:

- **Einzelner API-Key**: Hole dir einen einzigen API-Key von [klavis.ai](https://klavis.ai) und speichere ihn in den ShibaClaw-Backend-Einstellungen.
- **One-Click-Verbindungen**: Verbinde oder trenne Gmail, Slack und andere Dienste mit einem Klick über sicheren OAuth-Login, direkt vom Klavis-Gateway verwaltet.
- **Automatisch generierte MCP-Server**: Sobald eine App verbunden ist, konfiguriert ShibaClaw automatisch den passenden MCP-Server mit Standard-Tools und registriert sie nahtlos in der aktiven Agenten-Session.

***

## 🌐 Unterstützte Anbieter

ShibaClaw nutzt native SDKs (kein LiteLLM-Proxy) und löst den aktiven Anbieter aus dem gewählten Modell oder der kanonischen anbieter-präfixierten Modell-ID auf. In der WebUI werden alle konfigurierten Anbieter-Kataloge zu einer einzigen durchsuchbaren Liste zusammengeführt, während jede Session ihr eigenes Modell behält.

### API-Key

| Anbieter | Env-Variable |
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

¹ `GEMINI_API_KEY` in der Umgebung zu setzen genügt — kein gespeicherter Key nötig. Der Google OpenAI-kompatible Endpunkt ist vorkonfiguriert.

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — automatisch erkannt via Key-Präfix oder `api_base`.

### Lokal

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · beliebiger OpenAI-kompatibler Endpunkt(`http://localhost:1234/v1`)

> **Hinweis für Docker-Nutzer:** Wenn du ShibaClaw via Docker Compose ausführst, zeigt `localhost` in den Container selbst. Um dich mit einem auf deinem Host laufenden lokalen Server (wie LM Studio oder Ollama auf Windows/Mac) zu verbinden, nutze:
> `http://host.docker.internal:1234/v1` (oder `11434` für Ollama). Auf nativem Linux nutze `http://172.17.0.1:port`.

### OAuth

| Anbieter | Flow | Setup |
|----------|------|-------|
| OpenRouter | PKCE-Browser-Flow, speichert zurückgegebenen API-Key in Anbieter-Config | WebUI-Einstellungen |
| GitHub Copilot | Device-Flow, automatische Token-Auffrischung | `shibaclaw provider login github-copilot` oder WebUI-Einstellungen |
| OpenAI Codex | PKCE-Browser-Flow | `shibaclaw provider login openai-codex` oder WebUI-Einstellungen |

Für OpenRouter verwendet der Callback standardmäßig die aktuelle WebUI-URL und den Port, daher ist `http://localhost:3000` kein dedizierter Nur-OAuth-Port. Wenn du die WebUI hinter einem Reverse-Proxy freigibst oder einen anderen öffentlichen Callback-Ursprung brauchst, setze `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` vor dem Serverstart.

### 💡 Profi-Tipp: Kosteneffektiv & Premium-Modelle

ShibaClaw funktioniert hervorragend, selbst ohne teure API-Nutzung:
- **Kostenlose/Open-Modelle:** Wir empfehlen dringend **OpenRouter**, um leistungsstarke kostenlose Modelle wie `nvidia/nemotron-3-super-120b-a12b:free` oder `gemma-4-31b-it:free` zu nutzen.
- **Unbegrenzte Premium:** Mit der **GitHub Copilot** OAuth-Integration erhältst du Zugriff auf Premium-Modelle wie `raptor` (`oswe-vscode-prime`) zu null zusätzlichen Kosten, was dir effektiv unbegrenzte Requests gibt.

***

## 📊 ShibaClaw im Vergleich (Sicherheit zuerst)

> Diese Tabelle ist ein **grober, sicherheitsfokussierter Snapshot**, basierend nur auf dem, was in öffentlichen Repos/Docs bis Mai 2026 explizit dokumentiert ist.  
> `❓` bedeutet „nicht klar dokumentiert / nicht geprüft“, <b>nicht</b> „existiert nicht“.

| Sicherheitsfunktion | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| CVE-Audit bei Installation (pip, npm, apt) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Prompt-Injection-Wrapping bei jedem Tool-Ergebnis | ✅ | ❌ | ❌ | ❌ | ❌ |
| Eingebauter SSRF + DNS-Rebinding-Schutz | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClaw konzentriert sich darauf, diese Verteidigungen im Kern-Engine auszuliefern, standardmäßig an, sodass du keine externen Scanner und Proxies zusammenkleben musst, um einen Agenten sicher zu betreiben.

***

## 🏗️ Architektur

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Service | Rolle | Standard-Port |
|---------|------|--------------|
| `shibaclaw-gateway` | Kern-Agent-Loop, Message-Bus, Kanal-Integrationen | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + nativer WebSocket), Automatisierungs-Service | 3000 |

Beide teilen sich das `~/.shibaclaw/`-Volume (Config, Workspace, Memory, Automatisierungs-Jobs, Medien-Cache).

### Single-Process-Modus

`shibaclaw web` führt Agent + WebUI + Automatisierungen in einem Prozess aus — kein Gateway-Container nötig.

### Stack

| Schicht | Technologie |
|-------|-----------|
| Server | Uvicorn → Starlette (ASGI) |
| Echtzeit | Nativer WebSocket (`/ws` auf WebUI, Port `19998` auf Gateway) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sessions | JSONL nur-anhängbar pro Session (cache-freundlich für LLM-Prompt-Präfixe) |

### Ressourcenverbrauch

| Komponente | Idle | Spitze (Install/Compile) |
|-----------|------|------------------------|
| Gateway | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Compose setzt ein Limit von 512 MB / 256 MB Reservierung pro Container. Tool-Ausgaben werden mit begrenzten Puffern gestreamt.

***

## 🔧 CLI-Referenz

```bash
shibaclaw web               # Startet WebUI (Agent + Automatisierungen in-process)
shibaclaw gateway           # Startet nur Gateway (für Docker-Split)
shibaclaw onboard           # CLI-basiertes Erst-Setup-Wizard
shibaclaw agent -m "Hello"  # Einmalige Nachricht via Terminal
shibaclaw agent             # Interaktive REPL mit Verlauf
shibaclaw status            # Provider-, Workspace-, OAuth-Health-Check
shibaclaw print-token       # Zeigt WebUI-Auth-Token
shibaclaw channels status   # Listet aktivierte Kanäle
shibaclaw provider login <p># OAuth-Login (github-copilot, openai-codex)
shibaclaw desktop           # Startet Windows-Desktop-App
```

***

## 🐛 Fehlerbehebung

| Problem | Versuch |
|---------|-----|
| Allgemeiner Status-Check | `shibaclaw status` |
| Container-Logs | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI verbindet nicht | Token mit `shibaclaw print-token` prüfen, Port-Bindung verifizieren |
| Provider-Fehler | `shibaclaw status` zeigt API-Key und OAuth-Status |
| Sicherheitsrichtlinie | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 Mitwirken

Siehe [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs willkommen.

Plugins (sowohl Kanäle als auch TTS-Engines) sind über Python-Entry-Points erweiterbar. Siehe [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) für eine umfassende Anleitung zum Bau eigener Plugins. Skill-Erstellung ist in [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) und dem eingebauten `skill-creator`-Skill dokumentiert.

Gateway-Integratoren: Siehe [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) für den WebSocket-Vertrag auf Port `19998`.

***

## 🌟 Tritt der ShibaClaw-Packung bei

ShibaClaw wird von einem Entwickler gebaut, von der Community gepflegt und wächst schnell.  
Wenn es dir Zeit gespart, deinen Workflow gesichert oder dich einfach zum Lächeln gebracht hat — <b>hinterlasse einen Stern</b> ⭐

> „Der KI-Agent, der einfach funktioniert. Kein Babysitting nötig.“ 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Repo sternen</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">Kauf mir einen Kaffee</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Issue öffnen</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">PR senden</a>
</p>