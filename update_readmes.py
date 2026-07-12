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
        "points": """- **⚠️ WebUI Post-Update Login Warning** — Added warning box in the WebUI (Changelog modal and Update panel) to run `shibaclaw reset-admin` in your terminal if login issues occur post-update.
- **⬆️ Version Upgrade** — Updated all configuration and project files to `v0.9.6`."""
    },
    "README.de.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Neueste Version: v0.9.6</b> — Klicken für Neuerungen",
        "link": "Vollständiger Verlauf im [Changelog](./CHANGELOG.md).",
        "points": """- **⚠️ WebUI Post-Update Login-Warnung** — Warnhinweis in der WebUI (Changelog-Modal und Update-Panel) hinzugefügt, falls nach dem Update Login-Probleme auftreten: Bitte `shibaclaw reset-admin` im Terminal ausführen.
- **⬆️ Versions-Upgrade** — Aktualisierung aller Konfigurations- und Projektdateien auf `v0.9.6`."""
    },
    "README.es.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Última versión: v0.9.6</b> — Haz clic para ver las novedades",
        "link": "Consulta el [Changelog](./CHANGELOG.md) para el historial completo de versiones.",
        "points": """- **⚠️ Advertencia de inicio de sesión de WebUI post-actualización** — Se agregó un cuadro de advertencia en la WebUI (modal de Changelog y panel de actualización) para ejecutar `shibaclaw reset-admin` en tu terminal si ocurren problemas de inicio de sesión después de actualizar.
- **⬆️ Actualización de versión** — Se actualizaron todos los archivos de configuración y proyecto a la versión `v0.9.6`."""
    },
    "README.fr.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Dernière version : v0.9.6</b> — Cliquez pour voir les nouveautés",
        "link": "Consultez le [Changelog](./CHANGELOG.md) pour l'historique complet des versions.",
        "points": """- **⚠️ Avertissement de connexion WebUI post-mise à jour** — Ajout d'une boîte d'avertissement dans la WebUI (modal de Changelog et panneau de mise à jour) pour exécuter `shibaclaw reset-admin` dans votre terminal si des problèmes de connexion surviennent après la mise à jour.
- **⬆️ Mise à niveau de version** — Mise à jour de tous les fichiers de configuration et de projet vers la version `v0.9.6`."""
    },
    "README.ja.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>最新リリース: v0.9.6</b> — クリックで変更点を表示",
        "link": "完全なリリース履歴については [Changelog](./CHANGELOG.md) を参照してください。",
        "points": """- **⚠️ WebUI アップデート後のログイン警告** — アップデート後にログインの問題が発生した場合にターミナルで `shibaclaw reset-admin` を実行するよう促す警告ボックスを WebUI（変更履歴モーダルおよびアップデートパネル）に追加しました。
- **⬆️ バージョンアップグレード** — すべての設定およびプロジェクトファイルを `v0.9.6` に更新しました。"""
    },
    "README.pt-BR.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>Última versão: v0.9.6</b> — Clique para ver as novidades",
        "link": "Veja o [Changelog](./CHANGELOG.md) para o histórico completo de lançamentos.",
        "points": """- **⚠️ Aviso de login na WebUI pós-atualização** — Adicionada caixa de aviso na WebUI (modal Changelog e painel Update) para executar `shibaclaw reset-admin` no seu terminal caso ocorram problemas de login pós-atualização.
- **⬆️ Atualização de versão** — Atualizados todos os arquivos de configuração e do projeto para `v0.9.6`."""
    },
    "README.zh-CN.md": {
        "sync_from": "v0.9.5",
        "sync_to": "v0.9.6",
        "summary": "📢 <b>最新版本：v0.9.6</b> —— 点击查看更新内容",
        "link": "完整版本历史请查看 [Changelog](./CHANGELOG.md)。",
        "points": """- **⚠️ WebUI 更新后登录警告** —— 在 WebUI（更新日志模态框和更新设置面板）中添加了警告框，如果更新后出现登录问题，请在终端中运行 `shibaclaw reset-admin`。
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
