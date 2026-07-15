<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="800" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>
<h3 align="center">「ただ動く」AIエージェント — 安全に、プライベートに、放置しても大丈夫。</h3>

> [README.md](./README.md) の翻訳 — 最新でない可能性があります（v0.9.4 に同期）。

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>   
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.11-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <b>28のプロバイダー · 11のチャットチャンネル · 内蔵WebUI · セキュリティ優先コア · MCP対応</b>
</p>

<h3 align="center">3つの柱: <b>シンプル · セキュリティ · プライバシー</b></h3>

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
<summary>📢 <b>最新リリース: v0.9.8</b> — クリックで変更点を表示</summary>

### 追加
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
- **WebUIの読み込みとWebSocketの初期化** — バンドルとミニファイに`esbuild`を使用するようにWebUIフロントエンドアセットを移行しました。モジュール式のES6アーキテクチャは単一の`bundle.js`と`index.css`にコンパイルされるようになり、HTTPリクエストのオーバーヘッドを大幅に削減し、WebSocket接続初期化ループにおける競合状態を修正しました。

完全なリリース履歴については [Changelog](./CHANGELOG.md) を参照してください。

</details>

***

<p align="center">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
</p>

***

## ⚡ クイックスタート

### 🚀 自動インストーラー（推奨）

最も簡単な開始方法。1コマンドで最新リリースをダウンロードし、ショートカットを作成してUIを起動します。

**自身のモデルを持ち込み**：ローカルエンドポイント（Ollama、LM Studio）に接続、またはOpenRouterの無料枠でゼロコストからチャットできます。

**Windows (PowerShell):**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS (Terminal):**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> **注意**：Windowsでは最新GitHub Releaseのプリビルドデスクトップアプリをダウンロードします — Python不要。デスクトップとスタートメニューのショートカットが自動作成され、アプリと機能に表示されてクリーンにアンインストールできます。Linux/macOSではスクリプトが分離仮想環境へpipでインストールします。

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # Docker Hubから取得
docker exec -it shibaclaw-gateway shibaclaw print-token
```

**http://localhost:3000** を開き、トークンを貼り付けてオンボードウィザードに従います。

`shibaclaw-web` をLANに公開（リバースプロキシ等）し、同じURLをスマホで開くとモバイルで利用できます。

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # WebUI + エージェントエンジンを :3000 で起動
```

**http://localhost:3000** を開きウィザードに従います。  
CLIが良ければ `shibaclaw onboard` で同じガイド付きセットアップを端末から実行できます。

***

## ✨ 1つのエージェントですべて

<table>
<tr>
<td align="center" width="33%">

### 🛡️ セキュリティ優先
CVE監査、プロンプトインジェクション<br>ラップ、SSRFガード — <b>デフォルト有効</b>

</td>
<td align="center" width="33%">

### 🧠 スマートメモリ
3層システム、プロアクティブな<br>学習と自動圧縮

</td>
<td align="center" width="33%">

### 🌐 28のプロバイダー
ネイティブSDK、LiteLLMプロキシ不要<br>OpenAI · Anthropic · Gemini · DeepSeek...

</td>
</tr>
<tr>
<td align="center" width="33%">

### 📱 Webとモバイル
WebUIをLANに公開し、<br>同じエージェントをスマホから

</td>
<td align="center" width="33%">

### 🖥️ デスクトップアプリ
トレイ付きネイティブWindows<br>ランチャー、WebUIと相性抜群

</td>
<td align="center" width="33%">

### 🔌 MCP対応
任意のMCPサーバーに接続、<br>ツール自動登録

</td>
</tr>
</table>

***

## なぜShibaClaw？ 単に動くから。🐕

> **実際の仕事よりも世話が必要なエージェントに疲れましたか？**  
> ShibaClawは1つの原則を中心に設計されています: <b>ただ動く</b> — 安全に、確実に、常時メンテ不要。

多くのAIエージェントフレームワークはセキュリティを後付けとし、プロバイダー互換性に苦しめ、設定の世話を強います。ShibaClawは脚本をひっくり返します。セキュリティは後付けではなく<b>土台</b>です。

ShibaClawの違い：
- **コアに組み込まれたセキュリティ層** — インストール時CVE監査、各ツール結果のプロンプトインジェクションラップ、SSRF/DNSリバインディング保護
- **ネイティブプロバイダー対応** — 公式SDK経由の28プロバイダー、デバッグするプロキシ層なし
- **1コマンドセットアップ** — Dockerまたはpip、ウィザードに従うだけで約1分でチャット
- **どこでも動く** — ターミナル、WebUI、Discord、Telegram、WhatsApp、Windowsデスクトップ等

***

## 🛡️ セキュリティ、組み込み

通常アプリの糊コードや外部プロキシに散在する防御 — ShibaClawではコアに同梱され、<b>デフォルト有効</b>です。

### コアセキュリティ層

| 層 | 内容 |
|---|---|
| 🔍 インストール時監査 | 実行前に `pip` と `npm` を監査 — 重大/高 CVEを着陸前にブロック |
| 🛡️ プロンプトインジェクションラップと事前スキャン | 各ツール結果をランダムな `<tool_output_...>` 境界でラップ。脱獄に対し正規表現事前スキャンと、不信ペイロードへの **Base64エンコード** を適用 |
| 🔒 シェル硬化 | 20以上の拒否パターン、エスケープ正規化（`\x..`、`\u....`）、内部URL検出 |
| ⚡ ローカル優先エンジン | ネイティブコマンドエミュレーター（`ls`、`cat`）がサブプロセスオーバーヘッドを回避；エアギャップ実行向けオフライン優先 `tiktoken` フォールバック |
| 🌐 ネットワークガード | SSRFフィルタリング、リダイレクト再検証、DNSリバインディング安全解決 |
| 📁 ワークスペースサンドボックス | ファイルツールとブラウザを設定ワークスペースにロック |
| 🔑 アクセス制御 | Bearerトークン認証、一定時間検証、チャンネル許可リスト、任意のレート制限 |
| 🧠 分散エンジン | UI（約128MB）とエージェント脳（約256MB+）を分離 — プロセスごと最小フットプリント |

### 🛡️ プロンプトインジェクションラップ（ツールサンドボックス）

ShibaClawは生のツール出力をそのままLLMに戻す代わりに、<b>ランダムなnonce</b>（例: `<tool_output_a1b2c3d4>`）付きの動的生成XML風境界で各結果をラップします。

> 💡 <b>独立した防御</b>: このコアセキュリティ機構（ランダムツール出力ラップ）は依存ゼロの独立Pythonライブラリ [Muzzle](https://github.com/RikyZ90/Muzzle) として分離・パッケージ化されています。同じ技術で任意のフレームワーク（LangChain、LlamaIndex、CrewAI、AutoGen、独自LLMループ）を保護できます。

なぜ重要か: 攻撃者はタグを早く閉じたり、ツール出力（Webページ等）内に偽のシステム命令を注入しようとします。反復ごとに生成されるランダム境界により、エージェントは本物の命令と注入ペイロードを確実に見分けられます。さらに、内容への特定の閉じタグ注入試行は自動的にサニタイズ・エスケープされ、サンドボックスが破られず元のシステムプロンプトが優先されます。

### 🔍 インストール時パッケージ自動スキャン

`pip`、`npm`、`apt` を実行する前にShibaClawは動作を傍受して依存を解析し、`pip-audit` や `npm audit --json` でCVEデータベースへの既知脆弱性を変更適用前にスキャンします。

なぜ重要か: セキュリティを完全に左にシフトします。パッケージマネージャーを盲目的にブロックしたり事後スキャンに頼るのではなく、実行<i>前</i>に正確な依存ツリーを評価します。パッケージに重大/高CVEが含まれるか、疑わしいフラグ（`apt` の `--allow-unauthenticated` 等）が検出された場合、インストールはブロックされます。これによりAIはホストを負債にせず自律的にソフトウェアを構築できます。

開示方針と対応バージョン: [SECURITY.md](./SECURITY.md)

***

## 🖥️ ネイティブデスクトップアプリ（Windows）

ShibaClawは `pywebview` 製の完全統合 **Windowsデスクトップランチャー** を備えます。  
バックグラウンド端末ウィンドウを管理せずにシームレスなローカル体験を提供します。

- **システムトレイ統合**: ウィンドウを閉じるとShibaClawが静かにトレイに最小化。Shibaアイコンを右クリックでUI再表示、ログ閲覧、サイト訪問、エンジン終了。
- **自動ログイン**: デスクトップランチャーをローカルで使うとWebUI認証はデフォルトでバイパスされスムーズ。
- **埋め込みWebUI**: 別ブラウザ不要。WebUIは専用ネイティブウィンドウ内で動作。
- **ポータブル軽量**: PyInstallerで単一フォルダにパッケージ化、ホストにPython不要で即実行。

`pip` でインストールした場合:
```bash
shibaclaw desktop
```

または最新リリースのプリビルドWindows実行ファイルを直接ダウンロード:

> **[⬇ ShibaClaw.exeをダウンロード（最新）](https://github.com/RikyZ90/ShibaClaw/releases/latest/download/ShibaClaw-windows.zip)**  
> リリースノート → [github.com/RikyZ90/ShibaClaw/releases/latest](https://github.com/RikyZ90/ShibaClaw/releases/latest)

***

## 🌐 WebUI

<p align="center">
  <img src="assets/settings.webp" width="420" height="250" alt="Settings">
  <img src="assets/webui_welcome.webp" width="380" height="250" alt="WebUI Welcome Screen">
  <img src="assets/webui_chat.webp" width="380" height="250" alt="WebUI Chat with Agent">
</p>

WebUIは内蔵 — 別フロントエンドやNode.jsは不要です。

ローカルネットワークに公開し、スマホやタブレットから同じURLを開くだけ — 追加アプリ不要、ブラウザのみ。

- **チャット** — ツール呼び出し・思考ブロック・経過時間のライブストリーミングと、フッターからのセッションごとモデル切替を備えたマルチセッション
- **ローカルRAGと知識ベース** — ドキュメント（PDF、CSV、HTML、TXT）をドラッグ＆ドロップまたはアップロードでローカルコレクション作成、意味検索で照会
- **コンテキストメンション(@)** — メッセージ内で `@` を使い知識ベース・MCPサーバー・接続アプリを補完・バインド
- **クロスプロバイダーモデル検索** — 全プロバイダーのモデルを1つの選択肢に統合、ラベル表示とセッション変更時のプロバイダー切替
- **エージェントプロフィール** — セッションごとにペルソナ（Hacker、Builder、Planner、Reviewer）を動的アバターで切替
- **ファイルブラウザ** — ワークスペースファイルをブラウザで閲覧・編集（サンドボックス）
- **音声** — OpenAI互換音声API経由の音声テキスト変換とブラウザネイティブTTS
- **設定** — デフォルトセッション・メモリ/圧縮モデル・プロバイダー・ツール・MCP・チャンネル・スキル・OAuthを1パネルで
- **オンボードウィザード** — プロバイダー選択、APIキー入力またはOAuth開始、モデル選択のガイド付き初回設定
- **コンテキストビューア** — 完全なシステムプロンプトとトークン使用内訳を検査
- **ゲートウェイモニター** — ヘルスチェックとワンクリック再起動
- **OAuthフロー** — GitHub Copilot、OpenAI Codex、OpenRouterを設定モーダルから設定可能
- **硬化されたレンダリング** — チャットMarkdownは生HTMLをエスケープ、ファイル名は安全DOM、期限切れ認証は再接続ループなくログインへ
- **自動更新** — 12時間ごとにGitHubリリースを確認、UIと全チャンネルに通知
- **通知センター（WIP）** — 未読バッジ付きベル、リアルタイムWebSocketプッシュ、通知ごとのセッション深リンク
- **レスポンシブ** — デスクトップとモバイルで良好

### ⚡ 動的モデル選択

<p align="center">
  <img src="assets/model_sel.webp" width="600" alt="Dynamic Model Selector">
</p>

セッションごとにモデル変更 — 単一グローバルではなく会話ごとの柔軟な選択。

- **マルチプロバイダー検索**: 設定済み全プロバイダー（OpenRouter、GitHub Copilot、Anthropic等）の全モデルを1ドロップダウンで検索。
- **セッション認識ルーティング**: 各セッションが選択モデルを記憶。`Claude 3.5 Sonnet`のコーディングと `Gemma 4`の研究を同時に。
- **実行時切替**: エージェント再起動なしで即座にモデル切替；ゲートウェイが選択モデルから正しいエンドポイントを解決。
- **専用メモリモデル**: メモリ圧縮とプロアクティブ学習用に別モデル・プロバイダーを設定。
- **デフォルト優先**: 新セッションは設定のデフォルトモデルで自動開始。

### 🤖 エージェントプロフィール

コンテキストを失わずその場でペルソナ切替。各プロフィールはシステムプロンプト（SOUL.md）を上書きし、モデル・メモリ・ツールを共有。セッションごと。

内蔵: Default · Builder · Planner · Reviewer · <b>Hacker</b>（50以上のツール推奨、OWASP/MITRE/NIST手法、CVSSスコア、サイバー柴犬アバターを持つエリートセキュリティ専門家）。

自身のプロフィールを対話的に作成可能。

***

## 🧠 高度な3層メモリシステム

ShibaClawのメモリは単なるチャットバッファではなく、長期運用の継続性のために設計された構造的・プロアクティブなシステムです。

- **`USER.md`（アイデンティティと好み）:** 永続的な個人事实、コミュニケーションスタイル、言語好み。
- **`MEMORY.md`（運用状態）:** エージェントの作業知識。環境詳細、再発エンティティ、プロジェクト状態を追跡。
- **`HISTORY.md`（セッションアーカイブ）:** タイムスタンプ・タグ付き要約を持つ追加専用・検索可能な過去セッション台帳。

何千ものメッセージでプロンプトを膨らませる代わり、**プロアクティブ学習ループ**を備えます。NメッセージごとにバックグラウンドLLMが新事実を静かに抽出し `USER.md` と `MEMORY.md` を会話を中断せず更新。`MEMORY.md` が大きくなると自動圧縮が要約・重複排除し、最近の状態を優先しつつトークン予算内に維持。古い文脈が必要な時はTF-IDFと新鲜度スコアで `HISTORY.md` を自律検索します。

***

## 🛠️ 機能

### ワークフローと推論

- **モデル優先セッションルーティング** — 各セッションが自身のモデルを保存、実行時にプロバイダーを解決
- **フォーカスされたバックグラウンド委任** — `spawn` ツールが特定タスクをオフロードし完了時に報告
- **高度な推論** — 拡張思考（Anthropic）、推論強度（OpenAI o-series）、DeepSeek-R1チェーン

### ツール

| ツール | 内容 |
|------|-------------|
| `exec` | 20以上の拒否パターン、エンコード正規化、CVEスキャン付きシェルコマンド |
| `read_file` / `write_file` / `edit_file` | ページネーション読み取り、あいまい置換、親ディレクトリ自動作成 |
| `web_search` | Brave、Tavily、SearXNG、Jina、またはDuckDuckGo（キー不要フォールバック） |
| `web_fetch` | SSRF保護、DNSリバインディング防御、リダイレクト検証付きHTTP取得 |
| `memory_search` | セッション履歴のランク検索（TF-IDF + 新鲜度 + 重要度） |
| `knowledge_search` | アクティブ/言及ローカル知識ベースの意味検索（FAISS） |
| `message` | メディア添付付きクロスチャンネルメッセージ |
| `automation` | バックグラウンドジョブ管理・スケジュール（cron、間隔、ISO日付、タイムゾーン対応） |
| `spawn` | フォーカスされたタスク用の任意バックグラウンドワーカー |
| MCP | 任意のMCPサーバー（stdio、SSE、streamable HTTP）接続 — ツールは `mcp_<server>_<tool>` として自動登録 |

### チャンネル

Telegram · Discord · Slack · WhatsApp · Matrix · Email · DingTalk · Feishu · QQ · WeCom · MoChat

全チャンネルは同じメッセージバスを経由。WhatsAppはNode.jsブリッジ（Baileys）でQRリンク。

### スキル

8つの内蔵スキル（GitHub、weather、summarize、tmux、automation、memory guide、skill-creator、ClawHub browser）。YAML frontmatterと任意スクリプトを持つMarkdownファイル — 自身で作るか [ClawHub](https://clawhub.ai/) からインストール。

### 自動化

- **自動化エンジン** — 永続的・タイムゾーン対応のスケジュールジョブとバックグラウンドルーチンを統一UIで管理し `automation.json` に保存。`every`、`cron`、`at` に対応。見逃したジョブは起動時に自動早送り。
- **TASK.md統合** — エンジンは `TASK.md` をバックグラウンドの単一情報源とし、空の時はLLMをスキップ。

旧バージョンからアップグレードする場合 `HEARTBEAT.md` は廃止。タスクとスケジュールは `TASK.md` と新自動化UIへ移行してください。

### 🔌 プラグインとTTS

- **インストール可能プラグインシステム** — WebUI設定から管理する動的Pythonプラグインで拡張。作り方は [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md)。
- **無料オフラインローカルTTS（Supertonic）** — ONNX音声合成による高品質・ゼロコスト・完全オフラインTTS。31言語、カスタム音声（`F1`/`M1`）、速度調整に対応。
- **ブラウザ内オーディオプレーヤー** — シーク可能タイムライン付きガラス風ウィジェットでチャットUI内に音声再生。

***

## 🔌 MCPエコシステム

ShibaClawは **Model Context Protocol (MCP)** に完全対応し、エージェントを単体ツールからプラグアンドプレイAIハブへ変換します。

内蔵スキルのみに頼るのではなく、任意のMCP準拠サーバーに接続し、コアコードを一行も変えずに膨大な外部データと専門ツールを即座に獲得できます。

なぜ重要か:
- **即時拡張性**: Google Drive、Slack、GitHub、PostgreSQL等のコミュニティMCPサーバーを接続。
- **標準化ツール**: AIとツールの通信に共通プロトコルで安定性と相互運用性を確保。
- **分離アーキテクチャ**: 分散MCPネットワークで能力を拡張しつつエージェントを軽量に。

**設定**パネルでMCPサーバーを直接設定。

### 🌐 アプリ（Klavis統合）

Gmail、Google Drive、Google Docs、Slack、GitHub、Outlook等の人気SaaSツール設定をシームレスにするため、ShibaClawは **Klavis**（`klavis.ai`）と統合します。

各サービスごとにGoogle CloudやAzureで開発者認証情報を手作りする代わり、統一 **Connected Apps** インターフェースで全統合を管理:
- **単一API Key**: [klavis.ai](https://klavis.ai) から1つのキーを取得しバックエンド設定に保存。
- **ワンクリック接続**: Klavisゲートウェイが管理する安全OAuthでGmail、Slack等を接続/切断。
- **自動生成MCPサーバー**: アプリ接続時にShibaClawが適切なMCPサーバーと標準ツールを自動設定しアクティブセッションへ登録。

***

## 🌐 対応プロバイダー

ShibaClawはネイティブSDK（LiteLLMプロキシ不要）を使用し、選択モデルまたは正規プロバイダー接頭モデルIDからアクティブプロバイダーを解決します。WebUIでは全カタログが1つの検索リストに統合され、各セッションは自身のモデルを保持。

### API Key

| プロバイダー | 環境変数 |
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

¹ 環境に `GEMINI_API_KEY` を設定するだけで十分。GoogleのOpenAI互換エンドポイントは事前設定済み。

### ゲートウェイ / プロキシ

OpenRouter · AiHubMix · SiliconFlow · VolcEngine · BytePlus — キープレフィックスまたは `api_base` で自動検出。

### ローカル

Ollama (`http://localhost:11434`) · LM Studio · llama.cpp · vLLM · 任意のOpenAI互換エンドポイント（`http://localhost:1234/v1`）

> **Docker利用者へ:** Docker Composeで実行する場合 `localhost` はコンテナ内を指します。ホストのローカルサーバー（Windows/MacのLM StudioやOllama）へ接続するには `http://host.docker.internal:1234/v1`（Ollamaは `11434`）を使用。ネイティブLinuxでは `http://172.17.0.1:port`。

### OAuth

| プロバイダー | フロー | 設定 |
|----------|------|-------|
| OpenRouter | PKCEブラウザフロー、返されたAPIキーを保存 | WebUI設定 |
| GitHub Copilot | デバイスフロー、自動トークン更新 | `shibaclaw provider login github-copilot` またはWebUI設定 |
| OpenAI Codex | PKCEブラウザフロー | `shibaclaw provider login openai-codex` またはWebUI設定 |

OpenRouterはコールバックが現在のWebUI URLとポートをデフォルト再利用するため `http://localhost:3000` は専用OAuthポートではありません。リバースプロキシ配下や別の公開コールバック起点が必要な場合、サーバー起動前に `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` を設定。

### 💡 プロのtip: 費用対効果とプレミアムモデル

- **無料/オープンモデル:** **OpenRouter** で `nvidia/nemotron-3-super-120b-a12b:free` や `gemma-4-31b-it:free` 等の強力な無料モデルを強く推奨。
- **無制限プレミアム:** **GitHub Copilot** OAuth統合で `raptor`（`oswe-vscode-prime`）等のプレミアムモデルを追加費用ゼロで利用、実質無制限リクエスト。

***

## 📊 ShibaClaw比較（セキュリティ優先）

> この表は2026年5月時点の公開リポジトリ/ドキュメントで明示記載されたもののみに基づく**大まかなセキュリティ焦点のスナップショット**。`❓` は「明記/未確認」であり「存在しない」では<b>ありません</b>。

| セキュリティ機能 | ShibaClaw | OpenClaw | Hermes Agent | Nanobot | ZeroClaw |
|---|:---:|:---:|:---:|:---:|:---:|
| インストール時CVE監査（pip、npm、apt） | ✅ | ❌ | ❌ | ❌ | ❌ |
| 各ツール結果のプロンプトインジェクションラップ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 組み込みSSRF + DNSリバインディング保護 | ✅ | ❌ | ❌ | ❌ | ❌ |

ShibaClawはこれら防御をコアエンジンにデフォルト有効で搭載し、安全にエージェントを動かすために外部スキャナーやプロキシを継ぎ接ぎする必要をなくします。

***

## 🏗️ アーキテクチャ

<p align="center">
  <img src="assets/arch.png" width="800" alt="ShibaClaw Architecture">
</p>

### Docker Compose

| サービス | 役割 | デフォルトポート |
|---------|------|--------------|
| `shibaclaw-gateway` | コアエージェントループ、メッセージバス、チャンネル統合 | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI（Starlette + ネイティブWebSocket）、自動化サービス | 3000 |

両者は `~/.shibaclaw/` ボリューム（設定、ワークスペース、メモリ、自動化ジョブ、メディアキャッシュ）を共有。

### 単一プロセスモード

`shibaclaw web` はエージェント + WebUI + 自動化を単一プロセスで実行 — ゲートウェイコンテナ不要。

### スタック

| 層 | 技術 |
|-------|-----------|
| サーバー | Uvicorn → Starlette (ASGI) |
| リアルタイム | ネイティブWebSocket（WebUIの `/ws`、ゲートウェイのポート `19998`） |
| フロントエンド | Vanilla JS · Marked.js · Highlight.js |
| セッション | セッションごとJSONL追加専用 |

### リソース使用

| コンポーネント | アイドル | ピーク（インストール/コンパイル） |
|-----------|------|------------------------|
| ゲートウェイ | ~120 MB | ~350 MB |
| WebUI | ~120 MB | ~350 MB |

Docker Composeはコンテナごと512MB上限 / 256MB予約を設定。ツール出力は有界バッファでストリーミング。

***

## 🔧 CLIリファレンス

```bash
shibaclaw web               # WebUI起動（エージェント＋自動化をプロセス内）
shibaclaw gateway           # ゲートウェイのみ起動（Docker分割用）
shibaclaw onboard           # CLI版初回セットアップウィザード
shibaclaw agent -m "Hello"  # 端末からの一回メッセージ
shibaclaw agent             # 履歴付き対話REPL
shibaclaw status            # プロバイダー、ワークスペース、OAuthヘルスチェック
shibaclaw print-token       # WebUI認証トークン表示
shibaclaw channels status   # 有効チャンネル一覧
shibaclaw provider login <p># OAuthログイン（github-copilot、openai-codex）
shibaclaw desktop           # Windowsデスクトップアプリ起動
```

***

## 🐛 トラブルシューティング

| 問題 | 試してください |
|---------|-----|
| 一般ステータス確認 | `shibaclaw status` |
| コンテナログ | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUIが接続しない | `shibaclaw print-token` でトークン確認、ポートバインド検証 |
| プロバイダーエラー | `shibaclaw status` がAPIキーとOAuth状態を表示 |
| セキュリティポリシー | [`SECURITY.md`](./SECURITY.md) |

***

## 🤝 コントリビュート

[`CONTRIBUTING.md`](./CONTRIBUTING.md) を参照 — PR歓迎。

プラグイン（チャンネルとTTSエンジン）はPython entry pointsで拡張可能。作り方は [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md)。スキル作成は [`docs/CHANNEL_PLUGIN_GUIDE.md`](./docs/CHANNEL_PLUGIN_GUIDE.md) と内蔵 `skill-creator` スキル。

ゲートウェイ統合者はポート `19998` のWebSocket契約を [`docs/GATEWAY_PROTOCOL.md`](./docs/GATEWAY_PROTOCOL.md) で。

***

## 🌟 ShibaClawパックに加わろう

ShibaClawは1人の開発者が構築し、コミュニティが保守し、急速に成長しています。  
時間を節約し、ワークフローを守り、あるいはただ笑顔にしたなら — <b>スターをください</b> ⭐

> 「ただ動くAIエージェント。世話は不要。」 🐕

<p align="center">
  ⭐ <a href="https://github.com/RikyZ90/ShibaClaw">スターを付ける</a> &nbsp;·&nbsp;
  ☕ <a href="https://buymeacoffee.com/rikyz90f">コーヒーをおごる</a> &nbsp;·&nbsp;
  🐛 <a href="https://github.com/RikyZ90/ShibaClaw/issues">issueを開く</a> &nbsp;·&nbsp;
  🔧 <a href="https://github.com/RikyZ90/ShibaClaw/pulls">PRを送る</a>
</p>