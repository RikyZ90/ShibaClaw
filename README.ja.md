<p align="center">
  <img src="assets/shibaclaw_logo_readme.webp" width="640" alt="ShibaClaw">
</p>

<h1 align="center">ShibaClaw</h1>

<p align="center"><i>セルフホスト型、セキュリティ最優先の AI エージェント（内蔵 Web UI 付き）</i></p>

<p align="center">
  <a href="https://pypi.org/project/shibaclaw/"><img src="https://img.shields.io/pypi/v/shibaclaw.svg?style=flat-square&color=orange" alt="version"></a>
  <a href="https://pepy.tech/projects/shibaclaw"><img src="https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.12-blue?style=flat-square&logo=python&logoColor=white" alt="python">
  <a href="https://github.com/RikyZ90/ShibaClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/RikyZ90/ShibaClaw?style=flat-square&label=license&color=blue" alt="license"></a>
  <a href="https://deepwiki.com/RikyZ90/ShibaClaw"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <a href="#features">機能</a> ·
  <a href="#quick-start">クイックスタート</a> ·
  <a href="#security">セキュリティ</a> ·
  <a href="#memory-system">メモリ</a> ·
  <a href="#supported-providers">プロバイダ</a> ·
  <a href="#architecture">アーキテクチャ</a> ·
  <a href="#channels">チャンネル</a> ·
  <a href="#troubleshooting">トラブルシューティング</a>
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
> リリースノートは [CHANGELOG.md](./CHANGELOG.md) にあります。

<details open>
<summary>📢 <b>最新情報 — v0.9.9</b>（クリックで展開）</summary>

**最新リリース（2026-07-19）：**

- **チャンネル設定のドロップダウン** —— チャンネル設定の `group_policy` フィールドが WebUI でドロップダウン選択式になり、UX が向上しました。
- **モダン Linux での外部パッケージ導入（PEP 668）** —— pip 操作で `externally-managed-environment` エラー時に `--break-system-packages` を自動注入します。
- **サブエージェントのセッションキー伝播** —— 並列実行時のコンテキスト維持のため、サブエージェントのメタデータに `session_key` を追加しました。
- **RAG ソフト再起動のインポートエラー** —— ローカル RAG プラグイン導入時にソフト再起動で発生していた動的 RAG インポートの `NameError` を修正しました。
- **一時的な LLM エラー処理** —— 空の API 応答時に自動リトライするため、一時エラーマーカーに `'empty choices'` を追加しました。
- **シークレット更新時のチャンネルホットリロード** —— シークレット更新時にホットリロードが発動しない問題を修正しました。
- **プロアクティブ学習のツール選択** —— プロアクティブ学習で未対応の `tool_choice` パラメータを適切に処理するようになりました。
- **Base64 ツール出力エンコードの削除** —— パイプラインを簡略化するため、ツール出力の Base64 エンコード処理を削除しました。

**未リリース（進行中）：**

- **Telegram AI / エージェント Bot API 機能** —— ゲストモード（`answerGuestQuery`）、`sendMessageDraft` によるプライベートチャットのストリーミング、ボット間メッセージ、Business / Chat Automation 更新、および Managed Bot 更新の追跡。詳細は `docs/TELEGRAM_AI_FEATURES.md`。
- **Telegram 設定フラグ** —— `streaming`、`guestMode`、`allowBotMessages`、`businessEnabled`、`managedBotsEnabled`。

完全なリリース履歴は [Changelog](./CHANGELOG.md) を参照してください。

</details>

---

ShibaClaw は、自分のマシンやサーバーで動かすセルフホスト型の AI エージェントです。Python エンジンに内蔵 Web UI を備え、28 のモデルプロバイダにネイティブ対応し、11 のチャットプラットフォーム（Discord、Telegram、Slack、WhatsApp、Matrix など）と統合します。シンプルさ・セキュリティ・プライバシーの 3 本柱を中心に構築されており、インストール時の CVE 監査、プロンプトインジェクションのラップ、SSRF 保護といった防御は、外部の糊付けコードではなくコアエンジンに組み込まれています。

<p align="center">
  <img src="assets/webui_chat.webp" width="640" alt="ShibaClaw WebUI chat">
</p>

> [!NOTE]
> リリースノートは [CHANGELOG.md](./CHANGELOG.md) にあります。

## 機能

- **セキュリティ最優先のコア** —— 暗号化された認証情報保管庫、インストール時 CVE 監査、プロンプトインジェクションのラップ、SSRF/DNS リバインディング保護
- **3 層メモリ** —— ワーキング・セマンティック（FAISS）・プロシージャル。プロアクティブ学習と自動圧縮付き
- **28 プロバイダ、ネイティブ SDK** —— OpenAI、Anthropic、Gemini、DeepSeek など。LiteLLM プロキシ層なし
- **Web とモバイル** —— WebUI を LAN に公開すれば、スマホから同じエージェントを利用可能
- **Windows デスクトップアプリ** —— システムトレイ統合付きのネイティブランチャー
- **MCP 対応** —— 任意の MCP サーバーに接続でき、ツールが自動登録される

## クイックスタート

**要件：** Docker、または pip 経路の場合は Python 3.12+。Windows 自動インストーラーはどちらも不要 —— あらかじめビルドされたデスクトップアプリを同梱しています。

### 自動インストーラー（推奨）

1 つのコマンドで最新リリースをダウンロードし、ショートカットを作成して UI を起動します。

> [!TIP]
> 持参モデル：ローカルエンドポイント（Ollama、LM Studio）に接続するか、OpenRouter の無料 API 枠を使ってゼロコストでチャットを始められます。

**Windows（PowerShell）：**
```powershell
iwr -useb https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1 | iex
```

**Linux / macOS：**
```bash
curl -fsSL https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.sh | bash
```

> [!NOTE]
> Windows では、最新の GitHub Release からプリビルドのデスクトップアプリをダウンロードします —— Python 不要。デスクトップとスタートメニューにショートカットが作成され、「アプリと機能」からクリーンにアンインストールできます。Linux/macOS ではスクリプトが分離仮想環境へ pip でインストールします。

### Docker

```bash
curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
docker compose up -d     # Docker Hub から取得
docker exec -it shibaclaw-gateway shibaclaw print-token
```

**http://localhost:3000** を開き、トークンを貼り付けてオンボードウィザードに従います。スマホから使うには `shibaclaw-web` を LAN に公開（リバースプロキシ等）し、同じ URL を開きます。

### pip

```bash
pip install shibaclaw
shibaclaw web --with-gateway   # :3000 で WebUI + エージェントエンジンを起動
```

**http://localhost:3000** を開きウィザードに従います。  
CLI が良ければ `shibaclaw onboard` で同じガイド付きセットアップを端末から実行できます。

---

## セキュリティ

セキュリティは通常アプリの糊付けコードや外部プロキシに散らばっていますが、ShibaClaw ではコアに組み込まれ、デフォルトで有効です。

| 層 | 内容 |
|---|---|
| インストール時監査 | 実行前に `pip` と `npm` を監査 —— 重大/高 CVE をブロック |
| プロンプトインジェクションのラップと事前スキャン | 各ツール結果をランダムな `<tool_output_...>` 境界で囲む。 jailbreak を正規表現で事前スキャン |
| シェルの堅牢化 | 20 以上の拒否パターン、エスケープ正規化、内部 URL 検出 |
| ローカル優先エンジン | ネイティブコマンドエミュレータ（`ls`、`cat`）がサブプロセスオーバーヘッドを回避。オフライン `tiktoken` フォールバック |
| ネットワークガード | SSRF フィルタリング、リダイレクト再検証、DNS リバインディング安全解決 |
| ワークスペースサンドボックス | ファイルツールとファイルブラウザを設定済みワークスペースにロック |
| アクセス制御 | Bearer トークン認証、一定時間比較、チャンネル許可リスト、任意のレート制限 |
| 分散エンジン | UI（約 128 MB）とエージェント脳（約 256 MB+）を分離 |

各ツール結果は、ランダムな nonce を持つ動的生成境界（例：`<tool_output_a1b2c3d4>`）で囲まれるため、攻撃者はタグを早閉じしたり、ツール出力を通じて偽のシステム指示を注入できません —— 境界はセッションごとに予測不可能です。

> [!TIP]
> このラップ機構は [Muzzle](https://github.com/RikyZ90/Muzzle) として単独でも利用できます。これはゼロ依存の Python ライブラリで、任意のエージェントフレームワーク（LangChain、LlamaIndex、CrewAI、AutoGen、独自ループ）に組み込めます。

## メモリシステム

ShibaClaw は 3 層のメモリアーキテクチャを採用しています：

1. **ワーキングメモリ**（セッション内） —— 自動要約とトークン認識型切り詰めを行うローリングコンテキスト
2. **セマンティックメモリ**（セッション間） —— FAISS + sentence-transformers ベクトルストア。自動事実抽出と意味検索
3. **プロシージャルメモリ**（スキルと自動化） —— 再利用可能なスキルとして保存された学習済みワークフローと cron 風スケジュール

プロアクティブ学習が有用な事実を自動抽出・保存し、自動圧縮がコンテキストの溢れを防ぎ、セッションはキャッシュに優しい高速ログのためのみ追加型 JSONL として保存されます。

## MCP と統合

ShibaClaw は Model Context Protocol に対応しているため、コアコードを変更せずに任意の MCP 準拠サーバー（Google Drive、Slack、GitHub、PostgreSQL など）に接続できます。サーバーは設定パネルから構成します。

人気の SaaS ツール（Gmail、Google Drive、Slack、GitHub、Outlook……）向けに、ShibaClaw は [Klavis](https://klavis.ai) と統合しています。1 つの API キーでワンクリック OAuth 接続が得られ、各プロバイダごとに OAuth アプリを手動登録する必要がありません。接続済みアプリはアクティブセッションで自動的に MCP サーバーとして登録されます。

## 対応プロバイダ

ShibaClaw はネイティブ SDK を使用します —— LiteLLM プロキシなし。選択したモデル、またはプロバイダ接頭辞付きモデル ID からプロバイダを解決します。設定済みのすべてのプロバイダカタログは WebUI で 1 つの検索可能なリストに統合されます。

**API キー**

| プロバイダ | 環境変数 |
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

¹ `GEMINI_API_KEY` を設定するだけで十分です —— OpenAI 互換エンドポイントは事前設定済みです。

**ゲートウェイ / プロキシ** —— OpenRouter、AiHubMix、SiliconFlow、VolcEngine、BytePlus。キー接頭辞または `api_base` で自動検出。

**ローカル** —— Ollama、LM Studio、llama.cpp、vLLM、または任意の OpenAI 互換エンドポイント。

> [!NOTE]
> Docker では `localhost` はコンテナ内を指します。ホスト上のローカルサーバー（LM Studio、Ollama）に到達するには、Windows/macOS では `http://host.docker.internal:PORT`、ネイティブ Linux では `http://172.17.0.1:PORT` を使用してください。

**OAuth**

| プロバイダ | フロー | 設定 |
|----------|------|-------|
| OpenRouter | PKCE ブラウザフロー。返された API キーをプロバイダ設定に保存 | WebUI 設定 |
| GitHub Copilot | デバイスフロー。トークン自動更新 | `shibaclaw provider login github-copilot` または WebUI 設定 |
| OpenAI Codex | PKCE ブラウザフロー | `shibaclaw provider login openai-codex` または WebUI 設定 |
| Google Gemini CLI | PKCE ブラウザフロー。`SHIBACLAW_GEMINI_OAUTH_CLIENT_ID` と `SHIBACLAW_GEMINI_OAUTH_CLIENT_SECRET` 環境変数が必要。`**注意：** 非公式のサードパーティ統合。Google がアカウント制限を適用する場合があります。懸念がある場合は別アカウントを使用してください。 | WebUI 設定 |

OpenRouter のコールバックはデフォルトで現在の WebUI の URL とポートを再利用するため、`http://localhost:3000` は専用の OAuth ポートではありません。WebUI をリバースプロキシ配下に公開する場合や、別の公開コールバック起点が必要な場合は、サーバー起動前に `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` を設定してください。

### 💡 プロ向けヒント：費用対効果とプレミアムモデル

ShibaClaw は高額な API を使わなくても非常に良く動作します：
- **無料/オープンモデル：** 強力な無料モデル（例：`nvidia/nemotron-3-super-120b-a12b:free` や `gemma-4-31b-it:free`）にアクセスするには **OpenRouter** の利用を強くお勧めします。
- **無制限プレミアム：** **GitHub Copilot** の OAuth 統合を使えば、`raptor`（`oswe-vscode-prime`）のようなプレミアムモデルに追加費用ゼロでアクセスでき、事実上無制限のリクエストが得られます。

***

## 📊 ShibaClaw の比較（セキュリティ最優先）

> [!NOTE]
> OpenRouter の OAuth コールバックは現在の WebUI の URL とポートを再利用します。リバースプロキシ配下では、サーバー起動前に `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL` を設定してください。

ゼロコスト利用には、OpenRouter の無料枠（例：`nvidia/nemotron-3-super-120b-a12b:free`）と GitHub Copilot OAuth 統合（`raptor` などのモデルへの無制限アクセス）のどちらも、有料 API キーなしで良好に動作します。

## アーキテクチャ

<p align="center">
  <img src="assets/arch.png" width="640" alt="ShibaClaw architecture">
</p>

**Docker Compose**

| サービス | 役割 | デフォルトポート |
|---|---|---|
| `shibaclaw-gateway` | コアエージェントループ、メッセージバス、チャンネル統合 | 19999 (HTTP) · 19998 (WS) |
| `shibaclaw-web` | WebUI（Starlette + WebSocket）、自動化サービス | 3000 |

両者は `~/.shibaclaw/` ボリューム（設定、ワークスペース、メモリ、自動化ジョブ、メディアキャッシュ）を共有します。単独の `shibaclaw web` はエージェント + WebUI + 自動化を単一プロセスで実行し、ゲートウェイコンテナは不要です。

**スタック** —— Uvicorn/Starlette（ASGI）、ネイティブ WebSocket、バニラ JS + Marked.js + Highlight.js フロントエンド、JSONL のみ追加型セッション。

**リソース使用量** —— コンポーネント（ゲートウェイ、WebUI）ごとにアイドル時約 120 MB / ピーク時約 350 MB。Docker Compose は各コンテナを 512 MB / 予約 256 MB に制限。ツール出力は有界バッファでストリーミングされるため、長時間コマンドでもメモリが爆発しません。

## CLI リファレンス

```bash
shibaclaw web               # WebUI 起動（プロセス内でエージェント + 自動化）
shibaclaw gateway           # ゲートウェイのみ起動（Docker 分割用）
shibaclaw onboard           # CLI ベースの初回セットアップウィザード
shibaclaw agent -m "Hello"  # ターミナルからのワンショットメッセージ
shibaclaw agent             # 履歴付き対話型 REPL
shibaclaw status            # プロバイダ、ワークスペース、OAuth のヘルスチェック
shibaclaw print-token       # WebUI 認証トークンを表示
shibaclaw channels status   # 有効なチャンネルを一覧表示
shibaclaw provider login <p># OAuth ログイン（github-copilot、openai-codex）
shibaclaw desktop           # Windows デスクトップアプリを起動
```

## チャンネル

| チャンネル | 種類 | 備考 |
|---|---|---|
| WebUI | 内蔵 | メインインターフェース、全機能アクセス |
| Discord | Bot | リッチ埋め込み、スラッシュコマンド、添付ファイル |
| Telegram | Bot | インラインキーボード、メディア、返信マークアップ |
| WhatsApp | プラグイン | WhatsApp Web 経由 |
| Slack | Bot | Block kit、スレッド、アプリメンション |
| DingTalk | Bot | 企業メッセージング |
| Feishu/Lark | Bot | リッチカード、インタラクティブ要素 |
| QQ | Bot | グループ・プライベートメッセージ |
| WeCom | Bot | 職場コミュニケーション |
| Matrix | Bot | 分散型、E2E 暗号化 |
| MoChat | Bot | WeChat エコシステム |

各チャンネルは WebUI 設定で個別に構成され、設定変更時のホットリロードに対応しています。

## プラグインシステム

ShibaClaw は Python のエントリーポイント経由でプラグインを発見します：

- **チャンネルプラグイン** —— `BaseChannel` を実装、`shibaclaw.integrations` から発見可能
- **TTS プラグイン** —— `BaseTTS` を実装、`shibaclaw.tts` から発見可能

内蔵：`shibaclaw-channel-whatsapp`（WhatsApp Web）と `shibaclaw-tts-supertonic`（無料・オフライン ONNX 音声合成、31 言語）。WebUI 設定 > プラグインからプラグインのインストール・削除ができ、ホットリロードとバージョン固定に対応。独自のプラグイン作成は [`docs/PLUGINS_DEVELOPMENT_GUIDE.md`](./docs/PLUGINS_DEVELOPMENT_GUIDE.md) を参照。

## テキスト読み上げ（TTS）

内蔵の Supertonic エンジンは ONNX 上でオフライン動作（PyTorch 非依存、CPU のみ）し、31 言語に対応。`F1`/`M1` 音声プロファイルと調整可能な速度を備え、ブラウザ内ウィジェットで再生します。WebUI 設定 > TTS で有効化してください。

## 自動化とスケジューリング

バックグラウンドタスクは cron 風のスケジュールまたはイベントトリガー（メッセージ、webhook、システムイベント）で実行され、チャット履歴を汚染しない分離セッションで動作します。自動化パネルから管理・監視・ログ閲覧ができ、ジョブは JSONL 保存により再起動後も保持されます。

## ナレッジベース（RAG）

ローカル・プライバシー最優先の検索拡張生成：ドキュメントを命名コレクション（PDF、CSV、HTML、TXT、Markdown）に整理し、ドラッグ＆ドロップでアップロード、`all-MiniLM-L6-v2` 埋め込み上の FAISS インデックスで検索します。エージェントは会話中に `knowledge_search` を呼び出すか、`@kb:name` で特定のコレクションを指定できます。これはオプション依存で、`pip install shibaclaw[rag]` でインストールします。

## トラブルシューティング

| 問題 | 対処 |
|---|---|
| 一般的な状態確認 | `shibaclaw status` |
| コンテナログ | `docker logs shibaclaw-gateway` / `docker logs shibaclaw-web` |
| WebUI に接続できない | `shibaclaw print-token` でトークンを確認、ポートバインドを検証 |
| プロバイダエラー | `shibaclaw status` で API キーと OAuth 状態を表示 |
| v0.9.5 からアップグレード後のログイン失敗 | `shibaclaw reset-admin` を実行 |
| セキュリティポリシー | [`SECURITY.md`](./SECURITY.md) |

---

<p align="center">
貢献は <a href="./CONTRIBUTING.md">CONTRIBUTING.md</a> を、リリース履歴は <a href="./CHANGELOG.md">CHANGELOG.md</a> を参照してください。
</p>
