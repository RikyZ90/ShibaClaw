import re
from pathlib import Path

# Paths
base_dir = Path(r"c:\Users\Rikyz\.gemini\antigravity\scratch\shibaclaw_next")
files = {
    "README.de.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>Neueste Version: v0.9.5</b> — Klicken für Neuerungen",
        "link": "Vollständiger Verlauf im [Changelog](./CHANGELOG.md).",
        "points": """- **🔐 Verschlüsselter Credentials-Tresor** — Wir haben die Sicherheit komplett überarbeitet. ShibaClaw nutzt jetzt einen robusten AES-128/256 symmetrisch verschlüsselten Tresor (`credentials.enc` und `credentials.key`), um API-Schlüssel, Bot-Tokens und Passwörter sicher zu speichern. Features: Tresor-First-Auflösung, Thread-Sicherheit, Anti-Korruptionsschutz und strenge OS-Level-Berechtigungen (`0o600` auf Unix und `icacls` ACLs auf Windows).
- **🌐 Native OAuth- & Device-Code-Flows** — Nahtlose, native Authentifizierungs-Flows direkt in der WebUI hinzugefügt. Sie können sich jetzt mühelos über **xAI / Grok**, **GitHub Copilot**, **Google Gemini CLI**, **OpenAI Codex** und **OpenRouter** anmelden, ohne jemals einen API-Schlüssel berühren zu müssen!
- **🤖 Unterstützung für neue Anbieter** — Umfassende Integrationen für **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** und **Z.AI** hinzugefügt, wodurch Sie sofortigen Zugriff auf die besten State-of-the-Art-Modelle auf dem Markt haben.
- **🛡️ Gehärtete Kanalauflösung** — Komplette Auflösungs-Updates für Discord, DingTalk, Feishu, QQ, MoChat und das WhatsApp-Kanal-Plugin.
- **⚡ Blitzschnelle WebUI & Polierte UX** — Das Frontend wurde auf eine vollständig gebündelte ES6-Architektur via `esbuild` für sofortiges Laden migriert, und die Connected Apps UX wurde geglättet, um eine nahtlose Klavis-Backend-Konfiguration ohne manuelles Neuladen zu ermöglichen."""
    },
    "README.es.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>Última versión: v0.9.5</b> — Haz clic para ver las novedades",
        "link": "Consulta el [Changelog](./CHANGELOG.md) para el historial completo de versiones.",
        "points": """- **🔐 Bóveda de credenciales cifrada** — Hemos renovado la seguridad por completo. ShibaClaw ahora utiliza una robusta bóveda cifrada simétrica AES-128/256 (`credentials.enc` y `credentials.key`) para almacenar de forma segura claves API, tokens de bots y contraseñas. Cuenta con resolución prioritaria de bóveda, seguridad de hilos, protección anticorrupción y permisos estrictos a nivel de sistema operativo (`0o600` en Unix y `icacls` ACLs en Windows).
- **🌐 Flujos nativos de OAuth y Device Code** — Flujos de autenticación nativos integrados directamente en la WebUI. ¡Ahora puedes iniciar sesión sin esfuerzo a través de **xAI / Grok**, **GitHub Copilot**, **Google Gemini CLI**, **OpenAI Codex** y **OpenRouter** sin tocar nunca una clave API!
- **🤖 Soporte para nuevos proveedores** — Integraciones completas añadidas para **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** y **Z.AI**, dándote acceso inmediato a los mejores modelos de vanguardia del mercado.
- **🛡️ Resolución de canales fortalecida** — Actualizaciones completas de resolución para Discord, DingTalk, Feishu, QQ, MoChat y el plugin del canal de WhatsApp.
- **⚡ WebUI ultrarrápida y UX pulida** — Se migró el frontend a una arquitectura ES6 completamente empaquetada a través de `esbuild` para una carga instantánea, y se suavizó la UX de Connected Apps para permitir una configuración de backend de Klavis perfecta sin recargas manuales."""
    },
    "README.fr.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>Dernière version : v0.9.5</b> — Cliquez pour voir les nouveautés",
        "link": "Consultez le [Changelog](./CHANGELOG.md) pour l'historique complet des versions.",
        "points": """- **🔐 Coffre-fort d'identifiants chiffré** — Nous avons entièrement revu la sécurité. ShibaClaw utilise désormais un coffre-fort chiffré symétrique robuste AES-128/256 (`credentials.enc` et `credentials.key`) pour stocker en toute sécurité les clés API, les jetons de bot et les mots de passe. Il comprend une résolution prioritaire du coffre-fort, une sécurité des threads, une protection contre la corruption et des autorisations strictes au niveau du système d'exploitation (`0o600` sur Unix et `icacls` ACLs sur Windows).
- **🌐 Flux OAuth & Device Code natifs** — Ajout de flux d'authentification natifs et fluides directement dans l'interface Web (WebUI). Vous pouvez désormais vous connecter sans effort via **xAI / Grok**, **GitHub Copilot**, **Google Gemini CLI**, **OpenAI Codex** et **OpenRouter** sans jamais manipuler de clé API !
- **🤖 Nouveaux fournisseurs pris en charge** — Ajout d'intégrations complètes pour **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** et **Z.AI**, vous donnant un accès immédiat aux meilleurs modèles de pointe du marché.
- **🛡️ Résolution de canaux renforcée** — Mises à jour complètes de la résolution pour Discord, DingTalk, Feishu, QQ, MoChat et le plugin de canal WhatsApp.
- **⚡ WebUI ultra-rapide & UX soignée** — Migration du frontend vers une architecture ES6 entièrement groupée via `esbuild` pour un chargement instantané, et amélioration de l'UX des Connected Apps pour permettre une configuration backend Klavis fluide sans rechargement manuel."""
    },
    "README.ja.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>最新リリース: v0.9.5</b> — クリックで変更点を表示",
        "link": "完全なリリース履歴については [Changelog](./CHANGELOG.md) を参照してください。",
        "points": """- **🔐 暗号化された認証情報ボルト** — セキュリティを全面的に刷新しました。ShibaClaw は、API キー、ボットトークン、パスワードを安全に保存するために、堅牢な AES-128/256 対称暗号化ボルト（`credentials.enc` および `credentials.key`）を使用するようになりました。ボルト優先の解決、スレッドセーフ、破損防止保護、および厳密な OS レベルのアクセス許可（Unix では `0o600`、Windows では `icacls` ACL）を備えています。
- **🌐 ネイティブ OAuth ＆ デバイスコードフロー** — WebUI 内に直接、シームレスでネイティブな認証フローを追加しました。API キーに一切触れることなく、**xAI / Grok**、**GitHub Copilot**、**Google Gemini CLI**、**OpenAI Codex**、**OpenRouter** 経由で簡単にログインできるようになりました！
- **🤖 新規プロバイダーのサポート** — **Anthropic（Claude）**、**xAI（Grok）**、**Qwen（Alibaba）**、**MiniMax**、および **Z.AI** の包括的な統合を追加し、市場で最高の最先端モデルに即座にアクセスできるようになりました。
- **🛡️ チャネル解決の強化** — Discord、DingTalk、Feishu、QQ、MoChat、および WhatsApp チャネルプラグインの完全な解決アップデート。
- **⚡ 超高速WebUIと洗練されたUX** — 即時ロードのために、フロントエンドを`esbuild`を介して完全にバンドルされたES6アーキテクチャに移行し、Connected AppsのUXをスムーズにして、手動リロードなしでシームレスなKlavisバックエンド設定を可能にしました。"""
    },
    "README.pt-BR.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>Última versão: v0.9.5</b> — Clique para ver as novidades",
        "link": "Veja o [Changelog](./CHANGELOG.md) para o histórico completo de lançamentos.",
        "points": """- **🔐 Cofre de Credenciais Criptografado** — Renovamos totalmente a segurança. O ShibaClaw agora usa um robusto cofre criptografado simétrico AES-128/256 (`credentials.enc` e `credentials.key`) para armazenar com segurança chaves de API, tokens de bots e senhas. Possui resolução com prioridade para o cofre, thread-safety, proteção contra corrupção e permissões estritas no nível do SO (`0o600` no Unix e `icacls` ACLs no Windows).
- **🌐 Fluxos Nativos OAuth e Device Code** — Adicionados fluxos de autenticação nativos diretamente na WebUI. Agora você pode fazer login sem esforço via **xAI / Grok**, **GitHub Copilot**, **Google Gemini CLI**, **OpenAI Codex** e **OpenRouter** sem nunca tocar em uma chave de API!
- **🤖 Suporte a Novos Provedores** — Integrações abrangentes adicionadas para **Anthropic (Claude)**, **xAI (Grok)**, **Qwen (Alibaba)**, **MiniMax** e **Z.AI**, oferecendo acesso imediato aos melhores modelos de ponta do mercado.
- **🛡️ Resolução de Canais Reforçada** — Atualizações completas de resolução para Discord, DingTalk, Feishu, QQ, MoChat e o plugin do canal do WhatsApp.
- **⚡ WebUI ultrarrápida e UX aprimorada** — O frontend foi migrado para uma arquitetura ES6 totalmente empacotada via `esbuild` para carregamento instantâneo, e a UX dos Connected Apps foi suavizada para permitir a configuração contínua do backend Klavis sem recarregamentos manuais."""
    },
    "README.zh-CN.md": {
        "sync_from": "v0.9.4",
        "sync_to": "v0.9.5",
        "summary": "📢 <b>最新版本：v0.9.5</b> —— 点击查看更新内容",
        "link": "完整版本历史请查看 [Changelog](./CHANGELOG.md)。",
        "points": """- **🔐 加密凭证保管库** —— 我们全面升级了安全性。ShibaClaw 现在使用强大的 AES-128/256 对称加密保管库（`credentials.enc` 和 `credentials.key`）来安全存储 API 密钥、Bot Token 和密码。它具有优先使用保管库、线程安全、防损坏保护以及严格的操作系统级权限控制（Unix 上为 `0o600`，Windows 上为 `icacls` ACL）。
- **🌐 原生 OAuth 和设备代码流** —— 在 WebUI 中直接添加了无缝的、原生的身份验证流程。您现在可以轻松通过 **xAI / Grok**、**GitHub Copilot**、**Google Gemini CLI**、**OpenAI Codex** 和 **OpenRouter** 登录，而无需再接触任何 API 密钥！
- **🤖 支持新的提供商** —— 增加了对 **Anthropic (Claude)**、**xAI (Grok)**、**Qwen (Alibaba)**、**MiniMax** 和 **Z.AI** 的全面集成，让您能够立即使用市场上最好的前沿模型。
- **🛡️ 强化的渠道解析** —— 针对 Discord、钉钉（DingTalk）、飞书（Feishu）、QQ、MoChat 以及 WhatsApp 渠道插件的全面解析更新。
- **⚡ 极速WebUI和完善的UX** —— 通过`esbuild`将前端迁移到完全捆绑的ES6架构以实现即时加载，并优化了Connected Apps的用户体验，无需手动刷新即可无缝配置Klavis后端。"""
    }
}

for filename, data in files.items():
    filepath = base_dir / filename
    if not filepath.exists():
        continue
        
    content = filepath.read_text(encoding='utf-8')
    
    # Update the synchronization note
    content = content.replace(f"v{data['sync_from']}", f"v{data['sync_to']}")
    
    # Replace the details block
    details_pattern = re.compile(r'<details open>.*?</details>', re.DOTALL)
    
    new_details = f"""<details open>
<summary>{data['summary']}</summary>

{data['points']}

{data['link']}

</details>"""
    
    content = details_pattern.sub(new_details, content)
    filepath.write_text(content, encoding='utf-8')
    print(f"Updated {filename}")
