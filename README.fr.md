<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw 🐕</h1>
<h3 align="center">L'agent IA qui <b>fonctionne, tout simplement</b> — en sécurité, en privé, sans babysitting.</h3>

> Traduction de [README.md](./README.md) — peut ne pas être à jour (synchronisé à v0.9.4).

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28 Fournisseurs · 11 Canaux de Chat · WebUI Intégrée · Cœur Sécurité-d'abord · Prêt pour MCP</b>
</p>

<h3 align="center">Bâti sur trois piliers : <b>Simplicité · Sécurité · Vie privée</b></h3>

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
<summary>📢 <b>Dernière version : v0.9.6</b> — Cliquez pour voir les nouveautés</summary>

### Ajouté
- **🔐 Coffre-fort de clés chiffré (Mise à jour de sécurité majeure)** — Nous avons fondamentalement remanié la gestion des secrets. ShibaClaw utilise désormais un coffre-fort chiffré symétrique AES-128/256 robuste (`credentials.enc` et `credentials.key`) via Fernet. Cela isole entièrement tous les secrets d'intégration tiers (clés API, jetons de bot, mots de passe de messagerie) des fichiers de configuration en texte brut, évitant ainsi les fuites accidentelles.
- **🌐 Flux OAuth natifs xAI et avancés** — Intégration de flux OAuth / code de périphérique natifs directement dans l'interface Web. Vous pouvez désormais vous authentifier de manière transparente avec **xAI / Grok** en utilisant les mécanismes officiels de code de périphérique, aux côtés de GitHub Copilot, OpenAI Codex et OpenRouter, éliminant ainsi complètement le besoin de manipuler manuellement les clés API.
- **🤖 Écosystème de fournisseurs de modèles élargi** — Ajout d'une prise en charge complète et prête à l'emploi des principaux modèles de l'industrie, notamment **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** et **Zhipu Z.AI**.
- **Protection des fichiers Windows** — Intégration d'un repli spécifique à la plateforme à l'aide d'`icacls` pour appliquer un contrôle d'accès strict réservé à l'utilisateur sur les clés et les coffres-forts sous Windows.

### Modifié
- **🎨 Refonte visuelle complète de l'interface Web** — Refonte de l'ensemble de l'interface utilisateur pour établir une esthétique sérieuse, professionnelle et axée sur le produit (inspirée de Linear et Stripe). Suppression systématique du « slop visuel » généré par l'IA, y compris les arrière-plans en glassmorphisme (`backdrop-filter: blur`), le texte en dégradé décoratif, les lueurs dorées excessives et les animations de flottement. Remplacement des bordures latérales arbitraires par des teintes de fond sémantiques propres, unification du système de rayon de bordure sous une échelle de jetons stricte (4px/8px/12px) et optimisation du contraste des couleurs sur les thèmes sombres pour répondre aux normes WCAG.

### Corrigé
- **Replis en texte brut non sécurisés** — Refactorisation du flux d'intégration de l'interface Web et des paramètres OAuth Github pour stocker les jetons récupérés directement dans le coffre-fort chiffré plutôt que de ne pas les valider par rapport aux modifications de schéma.
- **Conditions de concurrence dans les mises à jour du coffre-fort** — Encapsulation de toutes les opérations de modification de clés sous un verrou `threading.Lock` pour garantir la sécurité lors des mises à jour simultanées de l'interface Web.
- **Perde de données par corruption silencieuse** — Configuration du flux de chargement du coffre-fort pour lever une exception `RuntimeError` en cas d'échec du déchiffrement plutôt que de renvoyer une base de données vide, ce qui écraserait accidentellement les secrets existants.
- **Caches de cryptographie sensibles au chemin** — Remplacement du cache global Fernet à clé unique par une carte spécifique au chemin pour éviter les conflits de réutilisation des clés dans les environnements de script.
- **Renforcement complet du coffre-fort de canal** — Intégration et vérification des assistants de résolution de coffre-fort pour DingTalk, Feishu, QQ, MoChat, Discord et le plugin de canal WhatsApp.
- **Configuration transparente des applications connectées** — Correction d'un bug UX où la première sauvegarde de la clé API Klavis nécessitait de fermer et rouvrir manuellement le menu. L'interface Web actualise désormais automatiquement les états de l'application et active immédiatement les boutons de connexion sans rechargement.
- **Linting de la base de code Python** — Correction des erreurs d'analyse statique de `Ruff`, notamment le déploiement des instructions multilignes et le nettoyage des importations inutilisées et des variables non définies dans les modules principaux (`channel.py`, `utils.py`, `gateway.py`).

### Optimisé
- **Chargement de l'interface Web et initialisation de WebSocket** — Migration des ressources frontend de l'interface Web pour utiliser `esbuild` pour le regroupement et la minification. L'architecture modulaire ES6 est désormais compilée dans un seul fichier `bundle.js` et `index.css`, réduisant considérablement la surcharge des requêtes HTTP et corrigeant les conditions de concurrence dans les boucles d'initialisation de connexion WebSocket.

Consultez le [Changelog](./CHANGELOG.md) para l'historique complet des versions.

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ Démarrage rapide

### 🚀 Installateur automatique (Recommandé)

Le moyen le plus simple de commencer. Une commande télécharge la dernière version, crée les raccourcis et lance l'interface.

**Apportez votre propre modèle** : Connectez-vous de façon transparente à des endpoints locaux (Ollama, LM Studio) ou utilisez des niveaux API gratuits via OpenRouter pour discuter à coût zéro.

**Windows (PowerShell) :**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal) :**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **Note** : Sous Windows, cela télécharge l'application de bureau préconstruite depuis la dernière GitHub Release — Python non requis. Les raccourcis Bureau et Menu Démarrer sont créés automatiquement, et l'application apparaît dans Applications & fonctionnalités pour une désinstallation propre. Sous Linux/macOS, le script installe via pip dans un environnement virtuel isolé.

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # tire depuis Docker Hub
docker exec -it shibaclaw-gateway shibaclaw print-token
```

Ouvrez **http://localhost:3000**, collez le token et suivez l'assistant d'onboarding.

Exposez `shibaclaw-web` sur votre LAN (ex. via proxy inverse) et ouvrez la même URL depuis votre téléphone pour discuter en mobile.

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # démarre WebUI + moteur d'agent sur :3000
```

Ouvrez **http://localhost:3000** et suivez l'assistant.  
Préférez la CLI ? `shibaclaw onboard` exécute la même configuration guidée depuis le terminal.

***

## ✨ Tout dans un seul agent

<table>
<tr>
<td align="center" width="33%">

### 🛡️ Sécurité d'abord
Audit CVE, encapsulage<br>d'injection de prompt, garde SSRF — <b>activé par défaut</b>

</td>
<td align="center" width="33%">

### 🧠 Mémoire intelligente
Système à 3 niveaux avec apprentissage<br>proactif et auto-compaction

</td>
<td align="center" width="33%">

### 🌐 28 Fournisseurs
SDK natifs, aucun proxy LiteLLM<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Web et Mobile
Exposez la WebUI sur votre LAN et<br>utilisez le même agent depuis le mobile

</td>
<td align="center" width="33%">

### 🖥️ App de bureau
Lanceur Windows natif avec tray,<br>combinaison parfaite avec la WebUI

</td>
<td align="center" width="33%">

### 🔌 Prêt pour MCP
Connectez n'importe quel serveur MCP,<br>outils auto-enregistrés

</td>
</tr>
</table>

***

## Pourquoi ShibaClaw ? Ça marche, tout simplement. 🐕

> **Fatigué des agents qui exigent plus de babysitting que votre vrai travail ?**  
> ShibaClaw est conçu autour d'un principe : <b>ça marche, tout simplement</b> — en sécurité, de façon fiable et sans maintenance constante.

La plupart des frameworks d'agents IA traitent la sécurité comme une réflexion tardive, vous laissent lutter avec la compatibilité des fournisseurs ou vous forcent à surveiller les configurations. ShibaClaw renverse la situation : la sécurité n'est pas vissée dessus, elle est <b>le fondement</b>.

Ce qui rend ShibaClaw différent :
- **Couches de sécurité intégrées au cœur** — audit CVE à l'installation, encapsulage d'injection de prompt sur chaque résultat d'outil, protection SSRF/rebinding DNS
- **Support natif des fournisseurs** — 28 fournisseurs via leurs SDK officiels, aucune couche proxy à déboguer
- **Configuration en une commande** — Docker ou pip, suivez l'assistant, vous discutez en environ une minute
- **Fonctionne partout** — Terminal, WebUI, Discord, Telegram, WhatsApp, app de bureau Windows et plus

***

## 🛡️ Sécurité, intégrée

Les défenses normalement dispersées dans le glue de l'app ou les proxys externes — dans ShibaClaw elles sont livrées dans le cœur, <b>activées par défaut</b>.

### Couches de sécurité du cœur

| Couche | Ce qu'elle fait |
|---|---|
| 🔍 Audit à l'installation | Audite `pip` et `npm` avant exécution — bloque les CVE critiques/élevées avant qu'elles n'arrivent |
| 🛡️ Encapsulage d'injection de prompt et pré-scan | Encapsule chaque résultat d'outil dans une frontière `<tool_output_...>` aléatoire. Applique un pré-scan regex pour les jailbreaks et **encodage Base64** pour les charges non fiables |
| 🔒 Durcissement du shell | 20+ motifs de refus, normalisation d'échappement (`\x..`, `\u....`), détection d'URL interne |
| ⚡ Moteur Local-First | Émulateur de commandes natif (`ls`, `cat`) évite le surcoût de sous-processus ; repli `tiktoken` offline-first pour exécution isolée |
| 🌐 Garde réseau | Filtrage SSRF, revalidation de redirection, résolution sûre contre le rebinding DNS |
| 📁 Sandbox de l'espace de travail | Outils de fichiers et navigateur verrouillés sur l'espace de travail configuré |
| 🔑 Contrôle d'accès | Auth Bearer token, vérifications à temps constant, listes blanches de canaux, limite de débit optionnelle |
| 🧠 Moteur distribué | UI (≈128 MB) découplée du cerveau de l'agent (≈256 MB+) — empreinte minimale par processus |

### 🛡️ Encapsulage d'injection de prompt (Sandboxing d'outils)

Au lieu de simplement renvoyer les sorties brutes des outils au LLM, ShibaClaw encapsule chaque résultat dans une frontière de type XML générée dynamiquement avec un <b>nonce aléatoire</b> (ex. `<tool_output_a1b2c3d4>`).

> 💡 <b>Défense autonome</b> : Ce mécanisme de sécurité central (Encapsulage aléatoire de sortie d'outil) a été découplé et packagé comme une bibliothèque Python autonome sans dépendances, [Muzzle](https://github.com/RikyZ90/Muzzle). Vous pouvez utiliser Muzzle pour protéger n'importe quel framework d'agent (LangChain, LlamaIndex, CrewAI, AutoGen ou boucles LLM personnalisées) avec cette même technique.

Pourquoi cela compte : les attaquants tentent souvent de fermer prématurément des balises ou d'injecter de fausses instructions système dans les sorties d'outils (comme le contenu web). En utilisant une frontière aléatoire générée par itération, l'agent peut distinguer de façon fiable les vraies instructions système des charges injectées. De plus, toute tentative d'injecter la balise de fermeture spécifique dans le contenu est automatiquement assainie et échappée, garantissant que le sandbox reste étanche et que le prompt système original prime.

### 🔍 Auto-scan des paquets à l'installation

Avant d'exécuter toute commande d'installation `pip`, `npm` ou `apt`, ShibaClaw intercepte l'action et parse les dépendances. Il exécute des outils comme `pip-audit` ou `npm audit --json` pour scanner les vulnérabilités connues contre les bases CVE avant d'appliquer des changements.

Pourquoi cela compte : cela déplace la sécurité entièrement à gauche. Au lieu de bloquer aveuglément les gestionnaires de paquets ou de s'appuyer sur des scans post-installation, il évalue l'arbre de dépendances exact <i>avant</i> l'exécution. Si un paquet contient des CVE critiques/élevées, ou si des drapeaux suspects (comme `--allow-unauthenticated` pour `apt`) sont détectés, l'installation est bloquée. Cela permet à l'IA de construire du logiciel de façon autonome sans transformer l'hôte en passif.

Politique de divulgation et versions supportées : [SECURITY.md](./SECURITY.md).

***

## 🖥️ App de bureau native (Windows)

ShibaClaw dispose d'un **Lanceur de bureau Windows** entièrement intégré, construit avec `pywebview`.  
Il offre une expérience locale fluide sans gérer de fenêtres de terminal en arrière-plan.

- **Intégration de la barre d'état** : Fermez la fenêtre pour minimiser ShibaClaw silencieusement dans la barre d'état. Clic droit sur l'icône Shiba pour rouvrir l'UI, accéder aux logs, visiter le site ou quitter proprement le moteur.
- **Auto-Login** : En utilisation locale du Lanceur, l'authentification WebUI est contournée par défaut pour une expérience local-first plus fluide.
- **WebUI intégrée** : Pas besoin d'ouvrir votre navigateur ; la WebUI tourne dans un cadre de fenêtre native dédiée.
- **Portable et légère** : Packagée en un seul dossier autonome via PyInstaller pour s'exécuter instantanément sans Python sur l'hôte.

Si vous avez installé via `pip` :
```bash
shibaclaw desktop
```

Ou téléchargez l'exécutable Windows préconstruit directement depuis la dernière version :

> **[⬇ Télécharger ShibaClaw.exe (dernière)](https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip)**  
> Notes complètes → [github.com/RikyZ90/ShibaClaw/releases/latest](https://github.com/RikyZ90/ShibaClaw/releases/latest)

***

## 🌐 WebUI

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

La WebUI est intégrée — aucun frontend séparé ou Node.js requis.

Exposez-la sur votre réseau local et ouvrez la même URL depuis le téléphone ou la tablette — aucune app supplémentaire, juste un navigateur.

- **Chat** — conversations multi-sessions avec streaming en direct des appels d'outils, blocs de pensée, temps écoulé et changement de modèle par session depuis le pied du chat
- **RAG local & Bases de connaissances** — glissez-déposez ou uploadez des documents (PDF, CSV, HTML, TXT) pour créer des collections locales, interrogez-les via recherche sémantique
- **Mentions de contexte (@)** — autocomplétion et liaison des bases de connaissances, serveurs MCP et apps connectées dans vos messages via `@`
- **Recherche de modèles multi-fournisseurs** — un sélecteur unique fusionne les modèles de tous les fournisseurs configurés, affiche les labels et change le fournisseur runtime
- **Profils d'agent** — changez de persona par session (Hacker, Builder, Planner, Reviewer) avec avatars dynamiques
- **Explorateur de fichiers** — parcourez, visualisez et éditez les fichiers de l'espace de travail dans le navigateur (sandbox)
- **Voix** — speech-to-text via APIs audio compatibles OpenAI et TTS natif du navigateur
- **Paramètres** — configurez modèle de session, mémoire/consolidation, fournisseurs, outils, serveurs MCP, canaux, skills et OAuth depuis un panneau
- **Assistant d'onboarding** — configuration guidée : choisissez fournisseur, entrez API key ou lancez OAuth, choisissez modèle
- **Visualiseur de contexte** — inspectez le prompt système complet et la répartition des tokens
- **Moniteur de gateway** — health check et redémarrage en un clic
- **Flux OAuth** — GitHub Copilot, OpenAI Codex et OpenRouter configurables depuis les paramètres
- **Rendu durci** — le Markdown du chat échappe le HTML brut, les noms de fichiers via DOM sûr, l'auth expirée revient proprement au login
- **Auto-update** — vérifie les releases GitHub toutes les 12h, notifie dans l'UI et sur les canaux
- **Centre de notifications (WIP)** — cloche avec badge, push WebSocket temps réel, deep-link par notification
- **Responsive** — fonctionne bien sur desktop et mobile

### ⚡ Sélection dynamique de modèle

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

Changez de modèle par session — plus de modèle global unique, mais un choix flexible par conversation.

- **Recherche multi-fournisseurs** : Recherchez tous les modèles de tous vos fournisseurs (OpenRouter, GitHub Copilot, Anthropic, etc.) dans un seul menu déroulant.
- **Routage conscient des sessions** : Chaque session se souvient de son modèle. Vous pouvez avoir une session de code avec `Claude 3.5 Sonnet` et une session de recherche avec `Gemma 4` simultanément.
- **Changement à l'exécution** : Changez de modèle instantanément sans redémarrer ; le gateway résout le bon endpoint automatiquement.
- **Modèle de mémoire dédié** : Configurez un modèle et fournisseur séparés pour la consolidation et l'apprentissage proactif.
- **Défaut d'abord** : Les nouvelles sessions démarrent automatiquement avec le modèle par défaut.

### 🤖 Profils d'agent

Changez la personnalité de l'agent à la volée sans perdre le contexte. Chaque profil remplace le prompt système (SOUL.md) tout en partageant modèle, mémoire et outils. Profils par session.

Profils intégrés : Default · Builder · Planner · Reviewer · <b>Hacker</b> (expert sécurité d'élite avec 50+ recommandations d'outils, méthodologies OWASP/MITRE/NIST, scoring CVSS et avatar cyber-shiba).

Créez vos propres profils de façon interactive.

***

## 🧠 Système de mémoire avancé à 3 niveaux

La mémoire de ShibaClaw n'est pas un simple buffer de chat ; c'est un système structuré et proactif conçu pour la continuité opérationnelle à long terme.

- **`USER.md` (Identité & Préférences)** : Stocke faits personnels durables, styles de communication et préférences de langue.
- **`MEMORY.md` (État opérationnel)** : Le savoir de travail de l'agent. Suit détails environnement, entités récurrentes et état du projet.
- **`HISTORY.md` (Archive des sessions)** : Registre en append-only, recherchable, avec résumés horodatés et taggés.

Au lieu de gonfler le prompt système avec des milliers de messages, ShibaClaw dispose d'une **boucle d'apprentissage proactif**. Tous les N messages, un processus LLM en arrière-plan extrait silencieusement de nouveaux faits durables et met à jour `USER.md` et `MEMORY.md`, sans interrompre. Quand `MEMORY.md` devient trop grand, une routine d'auto-compaction résume et déduplique, en priorisant l'état récent tout en respectant le budget de tokens. Quand l'agent a besoin d'un contexte ancien, il peut rechercher `HISTORY.md` via TF-IDF et score de récence.

***

## 🛠️ Fonctionnalités

### Workflow & Raisonnement

- **Routage session-modèle d'abord** — chaque session stocke son modèle et ShibaClaw résout le backend fournisseur à l'exécution
- **Délégation de fond ciblée** — l'outil `spawn` peut décharger une tâche et rapporter dans la session principale
- **Raisonnement avancé** — thinking étendu (Anthropic), effort de raisonnement (OpenAI o-series) et chaînes DeepSeek-R1

### Outils

| Outil | Ce qu'il fait |
|------|-------------|
| `exec` | Commandes shell avec 20+ motifs de refus, normalisation d'encodage et scan CVE |
| `read_file` / `write_file` / `edit_file` | Lectures paginées, remplacement flou, répertoires parents auto-créés |
| `web_search` | Brave, Tavily, SearXNG, Jina ou DuckDuckGo (fallback sans clé) |
| `web_fetch` | HTTP avec protection SSRF, défense rebinding DNS et validation de redirection |
| `memory_search` | Recherche classée sur l'historique (TF-IDF + récence + importance) |
| `knowledge_search` | Recherche sémantique sur collections locales (FAISS) |
| `message` | Messagerie cross-canal avec pièces jointes |
| `automation` | Gère ou planifie des tâches (cron, intervalles, dates ISO, fuseau horaire) |
| `spawn` | Worker de fond optionnel pour une tâche ciblée ; rapporte à la session principale |
| MCP | Connectez n'importe quel serveur MCP (stdio, SSE ou HTTP) — outils enregistrés comme `mcp_<server>_<tool>` |

### Canaux

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

Tous les canaux passent par le même message bus. WhatsApp utilise un bridge Node.js (Baileys) pour liaison par QR.

### Skills

8 skills intégrées (GitHub, weather, summarize, tmux, automation, memory guide, skill-creator, ClawHub browser). Ce sont des fichiers Markdown avec frontmatter YAML et scripts optionnels — créez les vôtres ou installez depuis [ClawHub](https://clawhub.ai/).

### Automatisation

- **Moteur d'automatisation** — tâches planifiées persistantes et routines d'arrière-plan, gérées via UI et stockées dans `automation.json`. Supporte `every`, `cron` et `at`. Les tâches manquées sont avancées automatiquement au démarrage.
- **Intégration TASK.md** — le moteur utilise `TASK.md` comme source de vérité ; saute le LLM quand vide.

Si vous montez depuis une ancienne version, `HEARTBEAT.md` est obsolète et retiré. Migrez vers `TASK.md` et la nouvelle UI d'automatisation.

### 🔌 Plugins & TTS

- **Système de plugins installables** — Étendez l'agent avec plugins Python dynamiques gérés depuis la WebUI. Voir [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md).
- **TTS local offline gratuit (Supertonic)** — Synthèse vocale ONNX de haute qualité, zéro coût, totalement offline. Supporte 31 langues, voix custom (`F1`/`M1`) et vitesse ajustable.
- **Lecteur audio dans le navigateur** — lit les messages vocaux dans l'UI avec un widget glassmorphic.

***

## 🔌 Écosystème MCP

ShibaClaw est totalement compatible avec le **Model Context Protocol (MCP)**, transformant l'agent d'un outil autonome en hub IA plug-and-play.

Au lieu de dépendre seulement des skills intégrées, ShibaClaw peut se connecter à n'importe quel serveur MCP, accordant instantanément à l'agent un accès à un vaste univers de sources de données externes et d'outils professionnels sans modifier une seule ligne de code cœur.

Pourquoi cela compte :
- **Extensibilité instantanée** : Branchez des serveurs MCP communautaires pour Google Drive, Slack, GitHub, PostgreSQL et plus.
- **Outils standardisés** : Un protocole universel pour la communication IA-outil, assurant stabilité et interopérabilité.
- **Architecture découplée** : Gardez votre agent léger tout en étendant ses capacités via un réseau distribué de serveurs MCP.

Configurez vos serveurs MCP directement dans le panneau **Paramètres**.

### 🌐 Apps (Intégration Klavis)

Pour rendre la configuration d'outils SaaS populaires (Gmail, Google Drive, Google Docs, Slack, GitHub, Outlook, etc.) aussi fluide que possible, ShibaClaw s'intègre avec **Klavis** (`klavis.ai`).

Au lieu de forcer les utilisateurs à créer manuellement des credentials développeur pour chaque service, configurer des écrans de consentement OAuth et définir des URLs de redirection sur Google Cloud ou Azure, ShibaClaw permet de gérer toutes ces intégrations via une interface unifiée **Connected Apps** :

- **Une seule API Key** : Récupérez une seule clé sur [klavis.ai](https://klavis.ai) et sauvegardez-la dans les paramètres backend.
- **Connexions en un clic** : Connectez ou déconnectez Gmail, Slack et autres services d'un clic via OAuth sécurisé géré par le gateway Klavis.
- **Serveurs MCP auto-générés** : Une fois l'app connectée, ShibaClaw configure automatiquement le serveur MCP approprié avec outils standards, l'enregistrant dans la session active.

***

## 🌐 Fournisseurs supportés

ShibaClaw utilise des SDK natifs (pas de proxy LiteLLM) et résout le fournisseur actif depuis le modèle sélectionné ou l'ID modèle canonique préfixé. Dans la WebUI, tous les catalogues sont fusionnés en une liste recherchable, chaque session gardant son modèle.

### API Key

| Fournisseur | Variable d'env |
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

¹ Définir `GEMINI_API_KEY` dans l'environnement suffit — aucune clé stockée requise. L'endpoint OpenAI-compatible de Google est préconfiguré.

### Gateway / Proxy

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — détectés automatiquement par préfixe de clé ou `api_base`.

### Local

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · tout endpoint OpenAI-compatible (`http://localhost:1234/v1`)

> **Note pour utilisateurs Docker :** Si vous lancez ShibaClaw via Docker Compose, `localhost` pointe dans le conteneur. Pour vous connecter à un serveur local sur l'hôte (comme LM Studio ou Ollama sur Windows/Mac), utilisez :
> `http://host.docker.internal:1234/v1` (ou `11434` pour Ollama). Sur Linux natif, utilisez `http://172.17.0.1:port`.

### OAuth

| Fournisseur | Flux | Configuration |
|----------|------|-------|
| OpenRouter | Flux PKCE navigateur, stocke la clé API retournée | Paramètres WebUI |
| GitHub Copilot | Flux device, refresh auto du token | `shibaclaw provider login github-copilot` ou Paramètres |
| OpenAI Codex | Flux PKCE navigateur | `shibaclaw provider login openai-codex` ou Paramètres |

Pour OpenRouter, le callback réutilise l'URL et le port de la WebUI par défaut, donc `http://localhost:3000` n'est pas un port OAuth dédié. Si vous exposez la WebUI derrière un proxy inverse, définissez `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` avant le démarrage.

### 💡 Astuce Pro : Modèles économiques et Premium

- **Modèles Gratuits/Open** : Nous recommandons **OpenRouter** pour modèles gratuits puissants comme `nvidia/nemotron-3-super-120b-a12b:free` ou `gemma-4-31b-it:free`.
- **Premium illimité** : Avec l'intégration OAuth **GitHub Copilot**, vous accédez à des modèles premium comme `raptor` (`oswe-vscode-prime`) à coût zéro, vous donnant des requêtes illimitées.

***

## 📊 Comparaison ShibaClaw (Sécurité d'abord)

> Ce tableau est un **instantané approximatif centré sur la sécurité**, basé seulement sur ce qui est explicitement documenté dans les repos/docs publics à mai 2026.  
> `❓` signifie « non clairement documenté / non vérifié », <b>pas</b> « n'existe pas ».

| Fonctionnalité de sécurité | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| Audit CVE à l'installation (pip, npm, apt) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Encapsulage d'injection de prompt à chaque résultat | ✅ | ❌ | ❌ | ❌ | ❌ |
| Protection SSRF + rebinding DNS intégrée | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClaw se concentre sur le livraison de ces défenses dans le moteur cœur, activées par défaut, pour que vous n'ayez pas à assembler des scanners et proxys externes juste pour lancer un agent en sécurité.

***

## 🏗️ Architecture

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| Service | Rôle | Port par défaut |
|---------|------|--------------|
| `shibaclaw-gateway` | Boucle agent cœur, message bus, intégrations canaux | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI (Starlette + WebSocket natif), service d'automatisation | 3000 |

Les deux partagent le volume `~/.shibaclaw/` (config, workspace, mémoire, jobs, cache média).

### Mode single-process

`shibaclaw web` lance agent + WebUI + automatisations dans un seul processus — pas de conteneur gateway.

### Stack

| Couche | Technologie |
|-------|-----------|
| Serveur | Uvicorn → Starlette (ASGI) |
| Temps réel | WebSocket natif (`/ws` sur WebUI, port `19998` sur gateway) |
| Frontend | Vanilla JS · Marked.js · Highlight.js |
| Sessions | JSONL append-only par session |

### Usage ressources

| Composant | Idle | Pic (install/compile) |
|-----------|------|------------------------|
| Gateway | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Compose fixe limite 512 MB / 256 MB réservé par conteneur. Sorties d'outils streamées avec buffers bornés.

***

## 🔧 Référence CLI

```bash
shibaclaw web               # Démarre WebUI (agent + automatisations in-process)
shibaclaw gateway           # Démarre gateway seul (pour Docker split)
shibaclaw onboard           # Assistant de setup via CLI
shibaclaw agent -m "Hello"  # Message unique via terminal
shibaclaw agent             # REPL interactive avec historique
shibaclaw status            # Health check provider, workspace, OAuth
shibaclaw print-token       # Affiche le token auth WebUI
shibaclaw channels status   # Liste canaux activés
shibaclaw provider login <p># Login OAuth (github-copilot, openai-codex)
shibaclaw desktop           # Lance l'app de bureau Windows
```

***

## 🐛 Dépannage

| Problème | Essayer |
|---------|-----|
| Vérification générale | `shibaclaw status` |
| Logs conteneur | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI ne connecte pas | Vérifiez token avec `shibaclaw print-token`, validez bind de port |
| Erreurs fournisseur | `shibaclaw status` montre API key et état OAuth |
| Politique sécurité | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 Contribuer

Voir [`CONTRIBUTING.md`](./CONTRIBUTING.md) — PRs bienvenues.

Les plugins (canaux et moteurs TTS) s'étendent via Python entry points. Voir [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md). Création de skills dans [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) et le skill intégré `skill-creator`.

Intégrateurs gateway : voir [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) pour le contrat WebSocket sur le port `19998`.

***

## 🌟 Rejoignez la meute ShibaClaw

ShibaClaw est construit par un développeur, maintenu par la communauté et croît vite.  
S'il vous a fait gagner du temps, sécurisé votre flux, ou simplement fait sourire — <b>laissez une étoile</b> ⭐

> « L'agent IA qui fonctionne, tout simplement. Sans babysitting. » 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">Star le repo</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">Offrez-moi un café</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">Ouvrir une issue</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">Envoyer une PR</a>
</p>