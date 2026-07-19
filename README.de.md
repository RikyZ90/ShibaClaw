<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>Selbstgehosteter, sicherheitsorientierter KI-Agent mit integrierter Web-Oberfläche</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">Funktionen</a> ·
  <a href="#quick-start">Schnellstart</a> ·
  <a href="#security">Sicherheit</a> ·
  <a href="#memory-system">Speicher</a> ·
  <a href="#supported-providers">Anbieter</a> ·
  <a href="#architecture">Architektur</a> ·
  <a href="#channels">Kanäle</a> ·
  <a href="#troubleshooting">Fehlerbehebung</a>
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
> Versionshinweise finden sich in [CHANGELOG.md](./CHANGELOG.md).

<details open>
<summary>📢 <b>Neuigkeiten — v0.9.9</b> (zum Ausklappen klicken)</summary>

**Neueste Version (2026-07-19):**

- **Dropdown-Auswahl in der Kanalkonfiguration** —— Die Felder `group_policy` der Kanalkonfiguration verwenden nun Dropdown-Auswahlen in der WebUI für eine bessere UX.
- **Externe Paketinstallation auf modernem Linux (PEP 668)** —— injiziert bei `externally-managed-environment`-Fehlern während pip-Operationen automatisch `--break-system-packages`.
- **Session-Key-Weitergabe in Sub-Agenten** —— `session_key` zu den Sub-Agent-Metadaten hinzugefügt, um den korrekten Kontext bei paralleler Ausführung zu erhalten.
- **RAG-Soft-Restart-Importfehler** —— `NameError` bei dynamischen RAG-Imports während Soft-Restarts behoben, wenn das lokale RAG-Plugin installiert ist.
- **Behandlung flüchtiger LLM-Fehler** —— `'empty choices'` zu den Markern für flüchtige Fehler hinzugefügt, um bei leeren API-Antworten automatisch erneut zu versuchen.
- **Kanal-Hot-Reload bei Secret-Updates** —— behoben, dass der Kanal-Hot-Reload bei Secret-Updates nicht ausgelöst wurde.
- **Tool-Auswahl beim proaktiven Lernen** —— behandelt den nicht unterstützten `tool_choice`-Parameter beim proaktiven Lernen ordnungsgemäß.
- **Base64-Tool-Ausgabekodierung entfernt** —— Base64-Kodierungslogik für Tool-Ausgaben entfernt, um die Pipeline zu vereinfachen.

**Unveröffentlicht (in Arbeit):**

- **Telegram AI / Agent Bot API-Funktionen** —— Gastmodus (`answerGuestQuery`), Streaming im Privatchat via `sendMessageDraft`, Bot-zu-Bot-Nachrichten, Business-/Chat-Automation-Updates und Tracking von Managed-Bot-Updates. Siehe `docs/TELEGRAM_AI_FEATURES.md`.
- **Telegram-Konfigurationsflags** —— `streaming`, `guestMode`, `allowBotMessages`, `businessEnabled`, `managedBotsEnabled`.

Vollständige Versionshistorie im [Changelog](./CHANGELOG.md).

</details>

---

ShibaClaw ist ein selbstgehosteter KI-Agent, den du auf deiner eigenen Maschine oder deinem Server betreibst: eine Python-Engine mit integrierter Web-Oberfläche, nativem SDK-Support für 28 Modellanbieter und 11 Chat-Plattform-Integrationen (Discord, Telegram, Slack, WhatsApp, Matrix und mehr). Er ist um drei Prioritäten herum aufgebaut —— Einfachheit, Sicherheit und Privatsphäre —— mit Verteidigungsmechanismen wie CVE-Audit bei der Installation, Prompt-Injection-Wrapping und SSRF-Schutz, die im Kern-Engine integriert sind, statt als externer Klebstoff angeheftet zu werden.

<p align="center">
  <img src="assets/webui_chat.webp" width="640" alt="ShibaClaw WebUI chat">
</p>

> [!NOTE]
> Versionshinweise finden sich in [CHANGELOG.md](./CHANGELOG.md).

## Funktionen

- **Sicherheitsorientierter Kern** —— verschlüsseltes Credential-Tresor, CVE-Audit bei Installation, Prompt-Injection-Wrapping, SSRF/DNS-Rebinding-Schutz
- **Dreistufiger Speicher** —— Working-, Semantic- (FAISS) und Procedural-Speicher mit proaktivem Lernen und Auto-Kompaktierung
- **28 Anbieter, native SDKs** —— OpenAI, Anthropic, Gemini, DeepSeek und mehr, keine LiteLLM-Proxy-Schicht
- **Web und mobil** —— WebUI im LAN bereitstellen und denselben Agenten vom Handy aus nutzen
- **Windows-Desktop-App** —— nativer Launcher mit System-Tray-Integration
- **MCP-bereit** —— beliebigen MCP-Server verbinden, Tools werden automatisch registriert

## Schnellstart

**Voraussetzungen:** Docker oder Python 3.12+ für den pip-Weg. Der Windows-Auto-Installer benötigt keines von beiden —— er liefert eine vorgebaute Desktop-App mit.

### Auto-Installer (empfohlen)

Ein Befehl lädt die neueste Version herunter, erstellt Verknüpfungen und startet die Oberfläche.

> [!TIP]
> Bring dein eigenes Modell mit: Verbinde dich nahtlos mit lokalen Endpunkten (Ollama, LM Studio) oder nutze kostenlose API-Tiers über OpenRouter, um kostenlos zu chatten.

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS:**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> Unter Windows wird die vorgebaute Desktop-App aus dem neuesten GitHub-Release heruntergeladen —— kein Python nötig, mit Verknüpfungen auf Desktop und Startmenü sowie sauberer Deinstallation über Apps & Features. Unter Linux/macOS installiert das Skript via pip in einer isolierten virtuellen Umgebung.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # zieht von Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Öffne **http://localhost:3000**, füge das Token ein und folge dem Onboard-Wizard. Lege `shibaclaw-web` in deinem LAN offen (z. B. per Reverse-Proxy) und öffne dieselbe URL am Handy für den Agenten mobil.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # startet WebUI + Agent-Engine auf :3000
```

Öffne **http://localhost:3000** und folge dem Wizard.  
Lieber CLI? `shibaclaw onboard` führt dasselbe geführte Setup im Terminal aus.

---

## Sicherheit

Verteidigungsmaßnahmen, die normalerweise über App-Kleber oder externe Proxys verstreut sind, sind im ShibaClaw-Kern enthalten und standardmäßig aktiv.

| Ebene | Was sie tut |
|---|---|
| Audit bei Installation | Auditiert `pip` und `npm` vor der Ausführung —— blockiert kritisch/hohe CVEs |
| Prompt-Injection-Wrapping & Vorab-Scan | Umhüllt jedes Tool-Ergebnis in eine zufällige `<tool_output_...>`-Grenze; Regex-Vorab-Scan auf Jailbreaks |
| Shell-Härtung | 20+ Ablehnungsmuster, Escape-Normalisierung, interne URL-Erkennung |
| Local-First-Engine | Nativer Befehls-Emulator (`ls`, `cat`) umgeht Subprozess-Overhead; offline `tiktoken`-Fallback |
| Netzwerk-Wache | SSRF-Filterung, Redirect-Revalidierung, DNS-Rebinding-sichere Auflösung |
| Workspace-Sandbox | Datei-Tools und Datei-Browser auf den konfigurierten Workspace beschränkt |
| Zugriffskontrolle | Bearer-Token-Auth, konstante Zeitprüfung, Kanal-Allowlists, optionales Rate Limiting |
| Verteilter Engine | UI (~128 MB) vom Agenten-Gehirn (~256 MB+) entkoppelt |

Jedes Tool-Ergebnis wird in eine dynamisch generierte Grenze mit zufälligem Nonce (z. B. `<tool_output_a1b2c3d4>`) eingehüllt, sodass ein Angreifer den Tag nicht vorzeitig schließen oder über die Tool-Ausgabe falsche Systemanweisungen injizieren kann —— die Grenze ist pro Sitzung unberechenbar.

> [!TIP]
> Dieser Wrapping-Mechanismus ist auch eigenständig als [Muzzle](https://github.com/RikyZ90/Muzzle) verfügbar, einer abhängigkeitsfreien Python-Bibliothek, die du in jedes Agenten-Framework (LangChain, LlamaIndex, CrewAI, AutoGen oder eine eigene Schleife) einhängen kannst.

## Speichersystem

ShibaClaw verwendet eine dreistufige Speicherarchitektur:

1. **Working-Speicher** (pro Sitzung) —— rollierender Kontext mit automatischer Zusammenfassung und token-bewusstem Abschneiden
2. **Semantic-Speicher** (übergreifend) —— FAISS + sentence-transformers Vektorstore mit automatischer Faktenextraktion und semantischer Suche
3. **Procedural-Speicher** (Skills & Automationen) —— gelernte Workflows als wiederverwendbare Skills gespeichert, plus cron-artige Zeitpläne

Proaktives Lernen extrahiert und speichert nützliche Fakten automatisch, Auto-Kompaktierung verhindert das Überlaufen des Kontexts, und Sitzungen werden als nur-anhängendes JSONL für schnelles, cache-freundliches Logging gespeichert.

## MCP & Integrationen

ShibaClaw spricht das Model Context Protocol und kann sich daher ohne Kerncode-Änderungen mit jedem MCP-kompatiblen Server verbinden —— Google Drive, Slack, GitHub, PostgreSQL und mehr. Server werden über das Einstellungspanel konfiguriert.

Für beliebte SaaS-Tools (Gmail, Google Drive, Slack, GitHub, Outlook...) integriert sich ShibaClaw mit [Klavis](https://klavis.ai): ein API-Schlüssel liefert OAuth-Verbindungen mit einem Klick, statt für jeden Anbieter manuell eine OAuth-App zu registrieren. Verbundene Apps werden in der aktiven Sitzung automatisch als MCP-Server registriert.

## Unterstützte Anbieter

ShibaClaw verwendet native SDKs —— kein LiteLLM-Proxy —— und löst den Anbieter aus dem ausgewählten Modell oder einer anbieterpräfixierten Modell-ID auf. Alle konfigurierten Anbieterkataloge werden in der WebUI zu einer durchsuchbaren Liste zusammengeführt.

**API-Schlüssel**

| Anbieter | Umgebungsvariable |
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

¹ `GEMINI_API_KEY` zu setzen genügt —— der OpenAI-kompatible Endpunkt ist vorkonfiguriert.

**Gateway / Proxy** —— OpenRouter, AiHubMix, SiliconFlow, VolcEngine, BytePlus, automatisch erkannt über Key-Präfix oder `api_base`.

**Lokal** —— Ollama, LM Studio, llama.cpp, vLLM oder ein beliebiger OpenAI-kompatibler Endpunkt.

> [!NOTE]
> In Docker zeigt `localhost` in den Container hinein. Um einen lokalen Server auf dem Host (LM Studio, Ollama) zu erreichen, verwende unter Windows/macOS `http://host.docker.internal:PORT` bzw. unter nativem Linux `http://172.17.0.1:PORT`.

**OAuth**

| Anbieter | Ablauf | Einrichtung |
|----------|------|-------|
| OpenRouter | PKCE-Browser-Flow, speichert zurückgegebenen API-Schlüssel in der Provider-Konfiguration | WebUI-Einstellungen |
| GitHub Copilot | Device-Flow, automatische Token-Auffrischung | `shibaclaw provider login github-copilot` oder WebUI-Einstellungen |
| OpenAI Codex | PKCE-Browser-Flow | `shibaclaw provider login openai-codex` oder WebUI-Einstellungen |
| Google Gemini CLI | PKCE-Browser-Flow, benötigt die Umgebungsvariablen `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` und `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET`. **Hinweis:** Inoffizielle Drittanbieter-Integration; Google kann Kontobeschränkungen anwenden. Bei Bedenken ein separates Konto verwenden. | WebUI-Einstellungen |

Für OpenRouter verwendet der Callback standardmäßig die aktuelle WebUI-URL und den Port, daher ist `http://localhost:3000` kein dedizierter OAuth-Port. Wenn du die WebUI hinter einem Reverse-Proxy bereitstellst oder einen anderen öffentlichen Callback-Ursprung benötigst, setze vor dem Serverstart `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host`.

### 💡 Profi-Tipp: Kostengünstige & Premium-Modelle

ShibaClaw funktioniert auch ohne teure API-Nutzung hervorragend:
- **Kostenlose/offene Modelle:** Wir empfehlen **OpenRouter**, um leistungsstarke kostenlose Modelle wie `nvidia/nemotron-3-super-120b-a12b:free` oder `gemma-4-31b-it:free` zu nutzen.
- **Unbegrenzte Premium:** Mit der **GitHub Copilot**-OAuth-Integration erhältst du Zugriff auf Premium-Modelle wie `raptor` (`oswe-vscode-prime`) zu null zusätzlichen Kosten, was dir effektiv unbegrenzte Anfragen gibt.

***

## 📊 Wie ShibaClaw im Vergleich abschneidet (Sicherheit zuerst)

> [!NOTE]
> Der OpenRouter-OAuth-Callback verwendet die aktuelle WebUI-URL und den Port. Hinter einem Reverse-Proxy setze vor dem Serverstart `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL`.

Für die kostenlose Nutzung funktionieren sowohl OpenRouters Free-Tier (z. B. `nvidia/nemotron-3-super-120b-a12b:free`) als auch die GitHub-Copilot-OAuth-Integration (unbegrenzter Zugriff auf Modelle wie `raptor`) ohne kostenpflichtigen API-Schlüssel gut.

## Architektur

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| Dienst | Rolle | Standardport |
|---|---|---|
| `shibaclaw-gateway` | Kern-Agenten-Loop, Message-Bus, Kanal-Integrationen | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket), Automatisierungsdienst | 3000 |

Beide teilen sich das Volume `~/.shibaclaw/` (Config, Workspace, Speicher, Automatisierungsjobs, Medien-Cache). `shibaclaw web` allein führt Agent + WebUI + Automatisierungen in einem Prozess aus, kein Gateway-Container nötig.

**Stack** —— Uvicorn/Starlette (ASGI), natives WebSocket, Vanilla-JS + Marked.js + Highlight.js Frontend, JSONL nur-anhängende Sitzungen.

**Ressourcenverbrauch** —— ~120 MB im Leerlauf / ~350 MB Spitze pro Komponente (Gateway, WebUI). Docker Compose begrenzt jeden Container auf 512 MB / 256 MB Reservierung; Tool-Ausgaben streamen mit begrenzten Puffern, sodass langlaufende Befehle den Speicher nicht sprengen.

## CLI-Referenz

```bash
shibaclaw web               # WebUI starten (Agent + Automatisierungen im Prozess)
shibaclaw gateway           # Nur Gateway starten (für Docker-Split)
shibaclaw onboard           # CLI-basiertes Erstsetup-Wizard
shibaclaw agent -m "Hello"  # Einmalige Nachricht via Terminal
shibaclaw agent             # Interaktive REPL mit Verlauf
shibaclaw status            # Provider-, Workspace-, OAuth-Healthcheck
shibaclaw print-token       # WebUI-Auth-Token anzeigen
shibaclaw channels status   # Aktivierte Kanäle auflisten
shibaclaw provider login <p># OAuth-Login (github-copilot, openai-codex)
shibaclaw desktop           # Windows-Desktop-App starten
```

## Kanäle

| Kanal | Typ | Hinweise |
|---|---|---|
| WebUI | Integriert | Hauptoberfläche, voller Funktionszugriff |
| Discord | Bot | Rich Embeds, Slash-Befehle, Anhänge |
| Telegram | Bot | Inline-Tastaturen, Medien, Reply-Markup |
| WhatsApp | Plugin | über WhatsApp Web |
| Slack | Bot | Block kit, Threads, App-Erwähnungen |
| DingTalk | Bot | Enterprise-Messaging |
| Feishu/Lark | Bot | Rich Cards, interaktive Elemente |
| QQ | Bot | Gruppen- & Privatnachrichten |
| WeCom | Bot | Workplace-Kommunikation |
| Matrix | Bot | Dezentral, E2E-Verschlüsselung |
| MoChat | Bot | WeChat-Ökosystem |

Jeder Kanal wird in den WebUI-Einstellungen unabhängig konfiguriert und unterstützt Hot-Reload bei Konfigurationsänderungen.

## Plugin-System

ShibaClaw entdeckt Plugins über Python-Entry-Points:

- **Kanal-Plugins** —— implementieren `BaseChannel`, über `shibaclaw.integrations` auffindbar
- **TTS-Plugins** —— implementieren `BaseTTS`, über `shibaclaw.tts` auffindbar

Eingebaut: `shibaclaw-channel-whatsapp` (WhatsApp Web) und `shibaclaw-tts-supertonic` (kostenlose, offline ONNX-Sprachsynthese, 31 Sprachen). Plugins über WebUI-Einstellungen > Plugins installieren oder entfernen, mit Hot-Reload und Versions-Pinning. Zum Eigenbau siehe [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).

## Text-zu-Sprache

Die eingebaute Supertonic-Engine läuft offline auf ONNX (keine PyTorch-Abhängigkeit, nur CPU), unterstützt 31 Sprachen mit `F1`/`M1`-Stimmprofilen und einstellbarer Geschwindigkeit und spielt über ein In-Browser-Widget ab. In WebUI-Einstellungen > TTS aktivieren.

## Automatisierung & Zeitplanung

Hintergrundaufgaben laufen nach cron-artigen Zeitplänen oder Ereignis-Triggern (Nachrichten, Webhooks, Systemereignisse) in isolierten Sitzungen, die den Chatverlauf nicht verschmutzen. Verwalte, überwache und sieh Logs über das Automatisierungs-Panel ein; Jobs bleiben über JSONL-Speicher über Neustarts hinweg erhalten.

## Wissensdatenbank (RAG)

Lokale, datenschutzorientierte Retrieval-Augmented Generation: Dokumente in benannten Sammlungen organisieren (PDF, CSV, HTML, TXT, Markdown), per Drag-and-Drop hochladen und mit einem FAISS-Index über `all-MiniLM-L6-v2`-Embeddings suchen. Der Agent kann `knowledge_search` im Gespräch aufrufen oder mit `@kb:name` eine bestimmte Sammlung ansprechen. Es ist eine optionale Abhängigkeit —— installiere mit `pip install shibaclaw[rag]`.

## Fehlerbehebung

| Problem | Versuch |
|---|---|
| Allgemeiner Statuscheck | `shibaclaw status` |
| Container-Logs | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI verbindet nicht | Token mit `shibaclaw print-token` prüfen, Port-Bindung verifizieren |
| Provider-Fehler | `shibaclaw status` zeigt API-Schlüssel und OAuth-Status |
| Login fehlgeschlagen nach Upgrade von v0.9.5 | `shibaclaw reset-admin` ausführen |
| Sicherheitsrichtlinie | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
Siehe <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> zum Mitwirken und <a href="./CHANGELOG.md">CHANGELOG.md</a> für die Versionshistorie.
</p>
