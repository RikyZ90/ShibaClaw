import re
from pathlib import Path

# Paths
base_dir = Path(r"c:\Users\Rikyz\.gemini\antigravity\scratch\shibaclaw_next")
files = {
    "README.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Latest Release: v0.9.6</b> — Click to see what's new",
        "link": "See the [Changelog](./CHANGELOG.md) for full release history.",
        "points": """### Added
- **🔐 Encrypted Credentials Vault (Major Security Update)** — We have fundamentally overhauled secret management. ShibaClaw now utilizes a robust AES-128/256 symmetric encrypted vault (`credentials.enc` and `credentials.key`) via Fernet. This entirely isolates all third-party integration secrets (API keys, bot tokens, email passwords) from plaintext config files, preventing accidental leaks.
- **🌐 Native xAI & Advanced OAuth Flows** — Integrated real, native OAuth / Device Code flows directly into the WebUI. You can now authenticate seamlessly with **xAI / Grok** using official device code mechanisms, alongside GitHub Copilot, OpenAI Codex, and OpenRouter, completely removing the need to touch API keys manually.
- **🤖 Expanded Model Providers Ecosystem** — Added full, out-of-the-box support for the industry's leading models including **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax**, and **Zhipu Z.AI**.
- **Windows File Protection** — Integrated platform-specific fallback using `icacls` to enforce strict user-only access control on keys and vaults under Windows.

### Changed
- **🎨 Complete WebUI Visual Redesign** — Overhauled the entire user interface to establish a serious, professional, and product-focused aesthetic (inspired by Linear and Stripe). Systematically removed AI-generated "visual slop" including glassmorphism backgrounds (`backdrop-filter: blur`), decorative gradient text, excessive gold glows, and float animations. Replaced arbitrary side-stripe borders with clean, semantic background tints, unified the border-radius system under a strict token scale (4px/8px/12px), and optimized color contrast across dark themes to meet WCAG standards.

### Fixed
- **Insecure Plaintext Fallbacks** — Refactored WebUI onboarding and Github OAuth settings flow to store retrieved tokens directly in the encrypted vault rather than failing to validate them against schema changes.
- **Race Conditions in Vault Updates** — Wrapped all modifying credential operations under a `threading.Lock` to guarantee safety during concurrent WebUI updates.
- **Silent Corruption Data Loss** — Configured the vault loading flow to raise a `RuntimeError` on decrypt failures rather than returning an empty database which would accidentally overwrite existing secrets.
- **Path-Aware Cryptography Caches** — Replaced global single-key Fernet cache with a path-specific map to prevent key reuse conflicts in script environments.
- **Complete Channel Vault-First Hardening** — Integrated and verified vault resolution helpers for DingTalk, Feishu, QQ, MoChat, Discord, and the WhatsApp channel plugin.
- **Connected Apps Seamless Configuration** — Fixed a UX bug where saving the Klavis API Key for the first time required manually closing and reopening the menu. The WebUI now automatically refreshes the App states and enables the Connect buttons immediately without a reload.
- **Python Codebase Linting** — Addressed `Ruff` static analysis errors including unrolling multi-line statements and cleaning up unused imports and undefined variables across core modules (`channel.py`, `utils.py`, `gateway.py`).

### Optimized
- **WebUI Loading & WebSocket Initialization** — Migrated WebUI frontend assets to use `esbuild` for bundling and minification. The modular ES6 architecture is now compiled into a single `bundle.js` and `index.css`, drastically reducing HTTP request overhead and fixing race conditions in WebSocket connection initialization loops."""
    },
    "README.de.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Neueste Version: v0.9.6</b> — Klicken für Neuerungen",
        "link": "Vollständiger Verlauf im [Changelog](./CHANGELOG.md).",
        "points": """### Hinzugefügt
- **🔐 Verschlüsselter Anmeldedatentresor (Wichtiges Sicherheitsupdate)** — Wir haben die Verwaltung von Geheimnissen grundlegend überarbeitet. ShibaClaw verwendet jetzt über Fernet einen robusten symmetrisch verschlüsselten AES-128/256-Tresor (`credentials.enc` und `credentials.key`). Dies isoliert alle Integrationsgeheimnisse von Drittanbietern (API-Schlüssel, Bot-Token, E-Mail-Passwörter) vollständig von Klartext-Konfigurationsdateien und verhindert versehentliche Lecks.
- **🌐 Native xAI & Fortgeschrittene OAuth-Abläufe** — Echte, native OAuth- / Gerätecode-Abläufe direkt in die WebUI integriert. Sie können sich jetzt nahtlos mit **xAI / Grok** über offizielle Gerätecode-Mechanismen authentifizieren, neben GitHub Copilot, OpenAI Codex und OpenRouter, sodass die manuelle Eingabe von API-Schlüsseln vollständig entfällt.
- **🤖 Erweitertes Modell-Provider-Ökosystem** — Vollständige Out-of-the-Box-Unterstützung für die führenden Modelle der Branche hinzugefügt, darunter **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** und **Zhipu Z.AI**.
- **Windows-Dateischutz** — Plattformspezifischer Fallback mit `icacls` integriert, um eine strikte, nur für Benutzer zugängliche Zugriffskontrolle auf Schlüssel und Tresore unter Windows zu erzwingen.

### Geändert
- **🎨 Komplette visuelle Neugestaltung der WebUI** — Die gesamte Benutzeroberfläche wurde überarbeitet, um eine seriöse, professionelle und produktfokussierte Ästhetik zu etablieren (inspiriert von Linear und Stripe). Systematische Entfernung von KI-generiertem „visuellem Slop“, einschließlich Glassmorphismus-Hintergründen (`backdrop-filter: blur`), dekorativem Verlaufstext, übermäßigem Goldglühen und Schwebeanimationen. Beliebige Seitenstreifenränder wurden durch saubere, semantische Hintergrundtönungen ersetzt, das Rahmenradiussystem unter einer strengen Token-Skala (4px/8px/12px) vereinheitlicht und der Farbkontrast bei dunklen Themen optimiert, um WCAG-Standards zu entsprechen.

### Behoben
- **Unsichere Klartext-Fallbacks** — Das WebUI-Onboarding und der Github-OAuth-Einstellungsfluss wurden umstrukturiert, um abgerufene Token direkt im verschlüsselten Tresor zu speichern, anstatt sie nicht anhand von Schemaänderungen zu validieren.
- **Race-Conditions bei Tresor-Updates** — Alle modifizierenden Anmeldedaten-Operationen wurden in ein `threading.Lock` gepackt, um die Sicherheit bei gleichzeitigen WebUI-Updates zu gewährleisten.
- **Stiller Datenverlust durch Korruption** — Der Tresor-Ladefluss wurde so konfiguriert, dass bei Entschlüsselungsfehlern ein `RuntimeError` ausgelöst wird, anstatt eine leere Datenbank zurückzugeben, die vorhandene Geheimnisse versehentlich überschreiben würde.
- **Pfadbewusste Kryptografie-Caches** — Der globale Fernet-Cache mit nur einem Schlüssel wurde durch eine pfadspezifische Zuordnung ersetzt, um Konflikte bei der Schlüsselwiederverwendung in Skriptumgebungen zu verhindern.
- **Vollständige Tresor-Härtung für Kanäle** — Tresor-Auflösungs-Helfer für DingTalk, Feishu, QQ, MoChat, Discord und das WhatsApp-Kanal-Plugin integriert und verifiziert.
- **Nahtlose Konfiguration verbundener Apps** — Ein UX-Fehler wurde behoben, bei dem das erste Speichern des Klavis-API-Schlüssels das manuelle Schließen und erneute Öffnen des Menüs erforderte. Die WebUI aktualisiert nun automatisch die App-Zustände und aktiviert die Verbinden-Schaltflächen sofort ohne Neuladen.
- **Python-Codebase-Linting** — Ruff-Statikanalysefehler behoben, einschließlich des Auflösens mehrzeiliger Anweisungen und des Bereinigens nicht verwendeter Importe und undefinierter Variablen in Kernmodulen (`channel.py`, `utils.py`, `gateway.py`).

### Optimiert
- **WebUI-Laden & WebSocket-Initialisierung** — Frontend-Assets der WebUI migriert, um `esbuild` für das Bundling und die Minimierung zu verwenden. Die modulare ES6-Architektur wird nun in eine einzige `bundle.js` und `index.css` kompiliert, was den HTTP-Anfrage-Overhead drastisch reduziert und Race-Conditions in WebSocket-Verbindungsinitialisierungsschleifen behebt."""
    },
    "README.es.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Última versión: v0.9.6</b> — Haz clic para ver las novedades",
        "link": "Consulta el [Changelog](./CHANGELOG.md) para el historial completo de versiones.",
        "points": """### Añadido
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
- **Carga de WebUI e inicialización de WebSocket** — Se migraron los activos frontend de WebUI para usar `esbuild` para el empaquetado y la minificación. La arquitectura modular de ES6 ahora se compila en un solo `bundle.js` e `index.css`, reduciendo drásticamente la sobrecarga de solicitudes HTTP y solucionando condiciones de carrera en los bucles de inicialización de la conexión WebSocket."""
    },
    "README.fr.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Dernière version : v0.9.6</b> — Cliquez pour voir les nouveautés",
        "link": "Consultez le [Changelog](./CHANGELOG.md) para l'historique complet des versions.",
        "points": """### Ajouté
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
- **Chargement de l'interface Web et initialisation de WebSocket** — Migration des ressources frontend de l'interface Web pour utiliser `esbuild` pour le regroupement et la minification. L'architecture modulaire ES6 est désormais compilée dans un seul fichier `bundle.js` et `index.css`, réduisant considérablement la surcharge des requêtes HTTP et corrigeant les conditions de concurrence dans les boucles d'initialisation de connexion WebSocket."""
    },
    "README.ja.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>最新リリース: v0.9.6</b> — クリックで変更点を表示",
        "link": "完全なリリース履歴については [Changelog](./CHANGELOG.md) を参照してください。",
        "points": """### 追加
- **🔐 暗号化された資格情報保管庫（重大なセキュリティアップデート）** — 秘密情報の管理を根本的に刷新しました。ShibaClawは、Fernetを介した堅牢なAES-128/256対称暗号化保管庫（`credentials.enc`および`credentials.key`）を利用するようになりました。これにより、サードパーティ統合のすべての秘密情報（APIキー、ボットトークン、電子メールパスワード）がプレーンテキストの設定ファイルから完全に隔離され、偶発的な漏洩が防止されます。
- **🌐 ネイティブxAIと高度なOAuthフロー** — 本物のネイティブOAuth / デバイスコードフローをWebUIに直接統合しました。APIキーを手動で操作する必要が完全になくなり、GitHub Copilot、OpenAI Codex、OpenRouterに加えて、公式のデバイスコードメカニズムを使用して**xAI / Grok**とシームレスに認証できるようになりました。
- **🤖 拡張されたモデルプロバイダーエコシステム** — **Anthropic (Claude)**、**xAI (Grok)**、**Qwen (アリババ)**、**MiniMax**、**Zhipu Z.AI**を含む、業界をリードするモデルの完全な標準サポートを追加しました。
- **Windowsファイル保護** — Windows環境において、キーと保管庫に対する厳格なユーザー専用のアクセス制御を強制するため、`icacls`を使用したプラットフォーム固有のフォールバックを統合しました。

### 変更
- **🎨 WebUIのビジュアルデザインの完全な刷新** — ユーザーインターフェース全体を刷新し、本格的でプロフェッショナルな、製品重視の美学（LinearやStripeからインスピレーションを得たもの）を確立しました。グラスモーフィズム背景（`backdrop-filter: blur`）、装飾的なグラデーションテキスト、過剰なゴールドの輝き、フローティングアニメーションなどのAI生成による「ビジュアルスロップ」を体系的に排除しました。任意のサイドストライプ境界線をクリーンで意味のある背景色に変更し、境界半径システムを厳格なトークンスケール（4px/8px/12px）の下で統一し、暗いテーマ全体の色のコントラストを最適化してWCAG基準を満たすようにしました。

### 修正
- **安全でないプレーンテキストのフォールバック** — WebUIのオンボーディングとGithub OAuth設定フローを再構築し、取得したトークンをスキーマ変更に対して検証できずに失敗するのではなく、暗号化された保管庫に直接保存するようにしました。
- **保管庫更新における競合状態** — 同時のWebUI更新中における安全性を保証するため、すべての資格情報変更操作を`threading.Lock`でラップしました。
- **サイレントな破損によるデータ消失** — 復号化に失敗した場合に、既存 of 秘密情報を誤って上書きしてしまう空のデータベースを返すのではなく、`RuntimeError`を発生させるように保管庫のロードフローを構成しました。
- **パスを認識する暗号化キャッシュ** — スクリプト環境におけるキーの再利用競合を防ぐため、グローバルな単一キーFernetキャッシュをパス特定のマップに置き換えました。
- **完全なチャンネル保管庫優先のハードニング** — DingTalk、Feishu、QQ、MoChat、Discord、およびWhatsAppチャンネルプラグイン用の保管庫解決ヘルパーを統合し、検証しました。
- **接続済みアプリのシームレスな構成** — Klavis APIキーを初めて保存するときに、手動でメニューを閉じて再開する必要があったUXのバグを修正しました。WebUIは自動的にアプリの状態を更新し、リロードなしで即座に接続ボタンを有効にするようになりました。
- **Pythonコードベースのリンティング** — コアモジュール（`channel.py`、`utils.py`、`gateway.py`）全体で、複数行のステートメントの展開や、未使用のインポートおよび未定義の変数のクリーンアップを含む、`Ruff`静的解析エラーに対惜しました。

### 最適化
- **WebUIの読み込みとWebSocketの初期化** — バンドルとミニファイに`esbuild`を使用するようにWebUIフロントエンドアセットを移行しました。モジュール式のES6アーキテクチャは単一の`bundle.js`と`index.css`にコンパイルされるようになり、HTTPリクエストのオーバーヘッドを大幅に削減し、WebSocket接続初期化ループにおける競合状態を修正しました。"""
    },
    "README.pt-BR.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Última versão: v0.9.6</b> — Clique para ver as novidades",
        "link": "Veja o [Changelog](./CHANGELOG.md) para o histórico completo de lançamentos.",
        "points": """### Adicionado
- **🔐 Cofre de credenciais criptografado (Grande atualização de segurança)** — Reformulamos fundamentalmente o gerenciamento de segredos. O ShibaClaw agora utiliza um cofre criptografado simétrico AES-128/256 robusto (`credentials.enc` e `credentials.key`) via Fernet. Isso isola completamente todos os segredos de integração de terceiros (chaves de API, tokens de bot, senhas de e-mail) dos arquivos de configuração em texto simples, evitando vazamentos acidentais.
- **🌐 Fluxos nativos de xAI e OAuth avançado** — Integrados fluxos nativos reais de OAuth / Código de dispositivo diretamente na WebUI. Agora você pode se autenticar perfeitamente com o **xAI / Grok** usando mecanismos oficiais de código de dispositivo, junto com o GitHub Copilot, OpenAI Codex e OpenRouter, eliminando completamente a necessidade de tocar em chaves de API manualmente.
- **🤖 Ecossistema de provedores de modelos expandido** — Adicionado suporte completo e pronto para uso para os principais modelos do setor, incluindo **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** e **Zhipu Z.AI**.
- **Proteção de arquivos do Windows** — Integrado fallback específico da plataforma usando `icacls` para impor controle de acesso estrito apenas ao usuário em chaves e cofres no Windows.

### Alterado
- **🎨 Redesenho visual completo da WebUI** — Reformulamos toda a interface do usuário para estabelecer uma estética séria, profissional e focada no produto (inspirada no Linear e Stripe). Removemos sistematicamente o "lixo visual" gerado por IA, incluindo fundos de glassmorphism (`backdrop-filter: blur`), texto decorativo em gradiente, brilhos dourados excessivos e animações de flutuação. Substituímos bordas laterais arbitrárias por tons de fundo semânticos limpos, unificamos o sistema de raio de borda sob uma escala de token estrita (4px/8px/12px) e otimizamos o contraste de cores em temas escuros para atender aos padrões WCAG.

### Corrigido
- **Fallbacks inseguros em texto simples** — Refatorado o fluxo de integração da WebUI e as configurações do Github OAuth para armazenar tokens recuperados diretamente no cofre criptografado em vez de falhar ao validá-los contra mudanças de esquema.
- **Condições de corrida em atualizações de cofre** — Envolvidas todas as operações de credenciais modificadoras em um `threading.Lock` para garantir a segurança durante atualizações simultâneas da WebUI.
- **Perda de dados por corrupção silenciosa** — Configurado o fluxo de carregamento do cofre para lançar um `RuntimeError` em falhas de descriptografia em vez de retornar um banco de dados vazio, o que substituiria acidentalmente os segredos existentes.
- **Caches de criptografia com reconhecimento de caminho** — Substituído o cache global do Fernet de chave única por um mapa específico do caminho para evitar conflitos de reutilização de chaves em ambientes de script.
- **Endurecimento completo do cofre de canais** — Integrados e verificados auxiliares de resolução de cofre para DingTalk, Feishu, QQ, MoChat, Discord e o plugin de canal do WhatsApp.
- **Configuração perfeita de aplicativos conectados** — Corrigido um bug de UX onde salvar a chave de API do Klavis pela primeira vez exigia fechar e reabrir manualmente o menu. A WebUI agora atualiza automaticamente os estados do aplicativo e ativa os botões de conexão imediatamente, sem recarga.
- **Linting do código base Python** — Corrigidos os erros de análise estática do `Ruff`, incluindo o desdobramento de instruções multilinha e a limpeza de importações não utilizadas e variáveis não definidas em módulos principais (`channel.py`, `utils.py`, `gateway.py`).

### Otimizado
- **Carregamento da WebUI e inicialização do WebSocket** — Migrados ativos de frontend da WebUI para usar `esbuild` para empacotamento e minificação. A arquitetura ES6 modular agora é compilada em um único `bundle.js` e `index.css`, reduzindo drasticamente a sobrecarga de requisições HTTP e corrigindo condições de corrida em loops de inicialização de conexões WebSocket."""
    },
    "README.zh-CN.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>最新版本：v0.9.6</b> —— 点击查看更新内容",
        "link": "完整版本历史请查看 [Changelog](./CHANGELOG.md)。",
        "points": """- ** WebUI 更新后登录警告** —— 在 WebUI（更新日志模态框和更新设置面板）中添加了警告框，如果更新后出现登录问题，请在终端中运行 `shibaclaw reset-admin`。
- **⬆️ 版本升级** —— 将所有配置文件和项目文件更新为 `v0.9.6`。"""
    }
}

for filename, data in files.items():
    filepath = base_dir / filename
    if not filepath.exists():
        continue
        
    content = filepath.read_text(encoding='utf-8')
    
    # Update the synchronization note
    content = content.replace(f"v{data['sync_from']}", f"v{data['sync_to']}")
    
    # Clean up any existing warning box to ensure idempotency
    content = re.sub(r'> \[\!WARNING\].*?restore access\.\s*', '', content, flags=re.DOTALL)
    
    # Construct details and the warning alert box above it
    new_details = f"""> [!WARNING]
> If you experience login issues with the WebUI post-update, please run `shibaclaw reset-admin` in your terminal/console to restore access.

<details open>
<summary>{data['summary']}</summary>

{data['points']}

{data['link']}

</details>"""
    
    # Replace the details block
    details_pattern = re.compile(r'<details open>.*?</details>', re.DOTALL)
    content = details_pattern.sub(new_details, content)
    
    filepath.write_text(content, encoding='utf-8')
    print(f"Updated {filename}")
