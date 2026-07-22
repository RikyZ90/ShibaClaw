<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>Agent IA auto-hébergé, axé sur la sécurité, avec une interface web intégrée</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">Fonctionnalités</a> ·
  <a href="#quick-start">Démarrage Rapide</a> ·
  <a href="#security">Sécurité</a> ·
  <a href="#memory-system">Mémoire</a> ·
  <a href="#supported-providers">Fournisseurs</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#channels">Canaux</a> ·
  <a href="#troubleshooting">Dépannage</a>
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
> Les notes de version se trouvent dans [CHANGELOG.md](./CHANGELOG.md).

<details open>
<summary>📢 <b>Nouveautés — v0.9.11</b> (cliquez pour déplier)</summary>

**Dernière version (2026-07-22) :**

- **Correction de faille d'injection de commandes dans ExecTool** — Résolution d'une vulnérabilité critique d'injection de commandes (CWE-78) dans l'exécution shell via `shlex` et exécution directe des processus (`create_subprocess_exec`).
- **Vulnérabilités de sécurité dans les dépendances** — Résolution des vulnérabilités de sécurité dans les dépendances npm du bridge en mettant à jour les substitutions pour `protobufjs` (v7.6.5) et `sharp` (v0.35.3).
- **Stabilité de la boucle d'agent et du guidage** — Correction des plantages de la commande `/update`, du routage de session et de l'émission d'événements pour les messages actifs.
- **Estimation des jetons WebUI** — Correction du traitement des types d'arguments sur le point de terminaison API `estimate_prompt_tokens` lors de la transmission de listes de messages.
- **Dépendances RAG Cloud** — Correction des limites de dépendances RAG Cloud et de la configuration du modèle d'embedding par défaut.

Consultez le [Changelog](./CHANGELOG.md) pour l'historique complet des versions.

</details>

---

ShibaClaw est un agent IA auto-hébergé que vous exécutez sur votre propre machine ou serveur : un moteur Python avec interface web intégrée, un support natif pour 28 fournisseurs de modèles et 11 intégrations de plateformes de chat (Discord, Telegram, Slack, WhatsApp, Matrix et plus). Il est construit autour de trois priorités —— simplicité, sécurité et confidentialité —— avec des défenses comme l'audit CVE à l'installation, l'encapsulation d'injection de prompts et la protection SSRF intégrées au moteur central plutôt que rajoutées en tant que colle externe.

<p align="center">
  <img src="assets/shibdemo.webp" width="480" alt="ShibaClaw Desktop Demo" style="margin-right: 12px; vertical-align: middle;">
  <img src="assets/shibmobiledemo.webp" width="188" alt="ShibaClaw Mobile Demo" style="vertical-align: middle;">
</p>

> [!NOTE]
> Les notes de version se trouvent dans [CHANGELOG.md](./CHANGELOG.md).

## Fonctionnalités

- **Cœur axé sur la sécurité** —— coffre de credentials chiffré, audit CVE à l'installation, encapsulation d'injection de prompts, protection SSRF/DNS-rebinding
- **Mémoire à trois niveaux** —— mémoire de travail, sémantique (FAISS) et procédurale, avec apprentissage proactif et auto-compaction
- **28 fournisseurs, SDK natifs** —— OpenAI, Anthropic, Gemini, DeepSeek et plus, sans couche proxy LiteLLM
- **Web et mobile** —— exposez la WebUI sur votre LAN et utilisez le même agent depuis votre téléphone
- **Application de bureau Windows** —— lanceur natif avec intégration à la barre d'état système
- **Prêt pour MCP** —— connectez n'importe quel serveur MCP, les outils sont auto-enregistrés

## Démarrage Rapide

**Prérequis :** Docker, ou Python 3.12+ pour la voie pip. L'installateur automatique Windows n'a besoin d'aucun des deux —— il embarque une application de bureau pré-construite.

### Installateur automatique (recommandé)

Une seule commande télécharge la dernière version, crée les raccourcis et lance l'interface.

> [!TIP]
> Apportez votre propre modèle : connectez-vous de façon transparente à des endpoints locaux (Ollama, LM Studio) ou utilisez des niveaux API gratuits via OpenRouter pour discuter à coût zéro.

**Windows (PowerShell) :**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS :**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> Sous Windows, cela télécharge l'application de bureau pré-construite depuis la dernière GitHub Release —— Python non requis, avec raccourcis Bureau et Menu Démarrer et désinstallation propre via Applications & fonctionnalités. Sous Linux/macOS, le script installe via pip dans un environnement virtuel isolé.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # tire depuis Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Ouvrez **http://localhost:3000**, collez le token et suivez l'assistant d'onboarding. Exposez `shibaclaw-web` sur votre LAN (ex. via proxy inverse) et ouvrez la même URL depuis votre téléphone pour discuter en mobile.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # démarre WebUI + moteur d'agent sur :3000
```

Ouvrez **http://localhost:3000** et suivez l'assistant.  
Préférez la CLI ? `shibaclaw onboard` exécute la même configuration guidée depuis le terminal.

---

## Sécurité

Les défenses normalement dispersées dans le code de liaison de l'app ou dans des proxys externes sont livrées dans le cœur de ShibaClaw, activées par défaut.

| Couche | Ce qu'elle fait |
|---|---|
| Audit à l'installation | Audite `pip` et `npm` avant exécution —— bloque les CVE critiques/élevées |
| Encapsulation d'injection de prompts et pré-analyse | Encapsule chaque résultat d'outil dans une limite `<tool_output_...>` aléatoire ; pré-analyse regex des jailbreaks |
| Durcissement du shell | 20+ motifs de refus, normalisation des échappements, détection d'URL internes |
| Moteur local-first | Émulateur de commandes natif (`ls`, `cat`) évite le surcoût des sous-processus ; repli `tiktoken` hors ligne |
| Garde réseau | Filtrage SSRF, revalidation des redirections, résolution sûre contre le DNS-rebinding |
| Sandbox de l'espace de travail | Outils de fichiers et explorateur verrouillés sur l'espace de travail configuré |
| Contrôle d'accès | Auth par jeton Bearer, vérifications à temps constant, listes blanches de canaux, rate limiting optionnel |
| Moteur distribué | UI (~128 Mo) découplée du cerveau de l'agent (~256 Mo+) |

Chaque résultat d'outil est encapsulé dans une limite générée dynamiquement avec un nonce aléatoire (ex. `<tool_output_a1b2c3d4>`), si bien qu'un attaquant ne peut ni fermer prématurément la balise ni injecter de fausses instructions système via la sortie de l'outil —— la limite est imprévisible par session.

> [!TIP]
> Ce mécanisme d'encapsulation est aussi disponible séparément sous la forme de [Muzzle](https://github.com/RikyZ90/Muzzle), une bibliothèque Python sans dépendance que vous pouvez intégrer à n'importe quel framework d'agents (LangChain, LlamaIndex, CrewAI, AutoGen ou une boucle personnalisée).

## Système de Mémoire

ShibaClaw utilise une architecture mémoire à trois niveaux :

1. **Mémoire de travail** (par session) —— contexte défilant avec résumé automatique et troncature consciente des tokens
2. **Mémoire sémantique** (entre sessions) —— magasin vectoriel FAISS + sentence-transformers avec extraction automatique de faits et recherche sémantique
3. **Mémoire procédurale** (compétences et automatisations) —— flux de travail appris enregistrés comme compétences réutilisables, plus des planifications de type cron

L'apprentissage proactif extrait et stocke automatiquement des faits utiles, l'auto-compaction empêche le débordement du contexte, et les sessions sont stockées en JSONL en ajout seul pour un journalisme rapide et favorable au cache.

## MCP et Intégrations

ShibaClaw parle le Model Context Protocol, il peut donc se connecter à n'importe quel serveur compatible MCP —— Google Drive, Slack, GitHub, PostgreSQL et plus —— sans modifier le code central. Configurez les serveurs depuis le panneau Paramètres.

Pour les outils SaaS populaires (Gmail, Google Drive, Slack, GitHub, Outlook...), ShibaClaw s'intègre avec [Klavis](https://klavis.ai) : une seule clé API vous donne des connexions OAuth en un clic au lieu d'enregistrer manuellement une app OAuth auprès de chaque fournisseur. Les apps connectées sont auto-enregistrées comme serveurs MCP dans la session active.

## Fournisseurs Pris en Charge

ShibaClaw utilise des SDK natifs —— sans proxy LiteLLM —— et résout le fournisseur à partir du modèle sélectionné ou d'un ID de modèle préfixé par le fournisseur. Tous les catalogues de fournisseurs configurés sont fusionnés en une liste recherchable dans la WebUI.

**Clé API**

| Fournisseur | Variable d'environnement |
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

¹ Définir `GEMINI_API_KEY` suffit —— l'endpoint compatible OpenAI est pré-configuré.

**Passerelle / proxy** —— OpenRouter, AiHubMix, SiliconFlow, VolcEngine, BytePlus, auto-détectés par préfixe de clé ou `api_base`.

**Local** —— Ollama, LM Studio, llama.cpp, vLLM, ou n'importe quel endpoint compatible OpenAI.

> [!NOTE]
> Dans Docker, `localhost` pointe à l'intérieur du conteneur. Pour atteindre un serveur local sur l'hôte (LM Studio, Ollama), utilisez `http://host.docker.internal:PORT` sur Windows/macOS ou `http://172.17.0.1:PORT` sur Linux natif.

**OAuth**

| Fournisseur | Flux | Configuration |
|----------|------|-------|
| OpenRouter | Flux PKCE navigateur, stocke la clé API renvoyée dans la config du fournisseur | Paramètres WebUI |
| GitHub Copilot | Flux device, rafraîchissement automatique du jeton | `shibaclaw provider login github-copilot` ou Paramètres WebUI |
| OpenAI Codex | Flux PKCE navigateur | `shibaclaw provider login openai-codex` ou Paramètres WebUI |
| Google Gemini CLI | Flux PKCE navigateur, nécessite les variables d'environnement `SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` et `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET`. **Note :** Intégration tierce non officielle ; Google peut appliquer des restrictions de compte. Utilisez un compte séparé si cela vous préoccupe. | Paramètres WebUI |

Pour OpenRouter, le callback réutilise par défaut l'URL et le port actuels de la WebUI, donc `http://localhost:3000` n'est pas un port OAuth dédié. Si vous exposez la WebUI derrière un proxy inverse ou avez besoin d'une origine de callback publique différente, définissez `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` avant de démarrer le serveur.

### 💡 Pro Tip : Modèles économiques et premium

ShibaClaw fonctionne de manière exceptionnelle même sans dépenser en API :
- **Modèles gratuits/ouverts :** nous recommandons d'utiliser **OpenRouter** pour accéder à des modèles gratuits puissants comme `nvidia/nemotron-3-super-120b-a12b:free` ou `gemma-4-31b-it:free`.
- **Premium illimité :** si vous utilisez l'intégration OAuth **GitHub Copilot**, vous obtenez l'accès à des modèles premium comme `raptor` (`oswe-vscode-prime`) à coût zéro, vous donnant des requêtes illimitées.

***

## 📊 Comment ShibaClaw se compare (Sécurité d'abord)

> [!NOTE]
> Le callback OAuth d'OpenRouter réutilise l'URL et le port actuels de la WebUI. Derrière un proxy inverse, définissez `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL` avant de démarrer le serveur.

Pour une utilisation à coût zéro, tant le niveau gratuit d'OpenRouter (ex. `nvidia/nemotron-3-super-120b-a12b:free`) que l'intégration OAuth GitHub Copilot (accès illimité à des modèles comme `raptor`) fonctionnent bien sans clé API payante.

## Architecture

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| Service | Rôle | Port par défaut |
|---|---|---|
| `shibaclaw-gateway` | Boucle centrale de l'agent, bus de messages, intégrations de canaux | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket), service d'automatisation | 3000 |

Les deux partagent le volume `~/.shibaclaw/` (config, workspace, mémoire, jobs d'automatisation, cache média). `shibaclaw web` seul exécute agent + WebUI + automatisations dans un seul processus, sans conteneur passerelle.

**Stack** —— Uvicorn/Starlette (ASGI), WebSocket natif, frontend JS vanilla + Marked.js + Highlight.js, sessions JSONL en ajout seul.

**Utilisation des ressources** —— ~120 Mo au repos / ~350 Mo en pic par composant (passerelle, WebUI). Docker Compose plafonne chaque conteneur à 512 Mo / 256 Mo réservés ; les sorties d'outils sont diffusées avec des tampons bornés afin que les commandes longues ne fassent pas exploser la mémoire.

## Référence CLI

```bash
shibaclaw web               # Démarre la WebUI (agent + automatisations en processus)
shibaclaw gateway           # Démarre uniquement la passerelle (pour le split Docker)
shibaclaw onboard           # Assistant de configuration initiale en CLI
shibaclaw agent -m "Hello"  # Message unique via le terminal
shibaclaw agent             # REPL interactive avec historique
shibaclaw status            # Fournisseur, workspace, healthcheck OAuth
shibaclaw print-token       # Affiche le jeton d'auth WebUI
shibaclaw channels status   # Liste les canaux activés
shibaclaw provider login <p># Connexion OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Lance l'app de bureau Windows
```

## Canaux

| Canal | Type | Notes |
|---|---|---|
| WebUI | Intégré | Interface principale, accès complet aux fonctionnalités |
| Discord | Bot | Rich embeds, commandes slash, pièces jointes |
| Telegram | Bot | Claviers inline, médias, markup de réponse |
| WhatsApp | Plugin | Via WhatsApp Web |
| Slack | Bot | Block kit, threads, mentions d'app |
| DingTalk | Bot | Messagerie d'entreprise |
| Feishu/Lark | Bot | Cartes riches, éléments interactifs |
| QQ | Bot | Messages de groupe et privés |
| WeCom | Bot | Communication en entreprise |
| Matrix | Bot | Décentralisé, chiffrement E2E |
| MoChat | Bot | Écosystème WeChat |

Chaque canal est configuré indépendamment dans les Paramètres WebUI et prend en charge le rechargement à chaud lors des changements de configuration.

## Système de Plugins

ShibaClaw découvre les plugins via les points d'entrée Python :

- **Plugins de canal** —— implémentent `BaseChannel`, découvrables via `shibaclaw.integrations`
- **Plugins TTS** —— implémentent `BaseTTS`, découvrables via `shibaclaw.tts`

Intégrés : `shibaclaw-channel-whatsapp` (WhatsApp Web) et `shibaclaw-tts-supertonic` (synthèse vocale ONNX gratuite et hors ligne, 31 langues). Installez ou supprimez des plugins depuis Paramètres WebUI > Plugins, avec rechargement à chaud et épinglage de version. Pour en créer un, voir [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).

## Synthèse Vocale (TTS)

Le moteur Supertonic intégré fonctionne hors ligne sur ONNX (sans dépendance PyTorch, CPU uniquement), prend en charge 31 langues avec des profils vocaux `F1`/`M1` et une vitesse ajustable, et lit via un widget intégré au navigateur. Activez-le dans Paramètres WebUI > TTS.

## Automatisation et Planification

Les tâches en arrière-plan s'exécutent selon des planifications de type cron ou des déclencheurs d'événements (messages, webhooks, événements système), dans des sessions isolées qui ne polluent pas l'historique de chat. Gérez, surveillez et consultez les journaux depuis le panneau Automatisations ; les jobs persistent après redémarrage via le stockage JSONL.

## Base de Connaissances (RAG)

Génération augmentée par récupération locale et axée sur la confidentialité : organisez les documents en collections nommées (PDF, CSV, HTML, TXT, Markdown), téléversez par glisser-déposer et recherchez avec un index FAISS sur les embeddings `all-MiniLM-L6-v2`. L'agent peut appeler `knowledge_search` pendant la conversation, ou cibler une collection spécifique avec `@kb:name`. C'est une dépendance optionnelle —— installez avec `pip install shibaclaw[rag]`.

## Dépannage

| Problème | Essayez |
|---|---|
| Vérification d'état générale | `shibaclaw status` |
| Journaux de conteneur | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI ne se connecte pas | Vérifiez le jeton avec `shibaclaw print-token`, validez la liaison de port |
| Erreurs de fournisseur | `shibaclaw status` affiche la clé API et l'état OAuth |
| Échec de connexion après mise à jour depuis v0.9.5 | Exécutez `shibaclaw reset-admin` |
| Politique de sécurité | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
Voir <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> pour contribuer et <a href="./CHANGELOG.md">CHANGELOG.md</a> pour l'historique des versions.
</p>
