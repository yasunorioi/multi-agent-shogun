<div align="center">

# multi-agent-shogun + 大奥

**Claude Code + tmux によるマルチエージェント並列開発基盤**

*コマンド1つで8体のAIエージェントが並列稼働。ファイルベース通信、全ホワイトカラー業務対応。*

[![GitHub Stars](https://img.shields.io/github/stars/yohey-w/multi-agent-shogun?style=social)](https://github.com/yohey-w/multi-agent-shogun)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)
[![Shell](https://img.shields.io/badge/Shell%2FBash-100%25-green)]()

</div>

---

## 概要

**multi-agent-shogun** は、複数の Claude Code インスタンスを tmux 上で同時に実行し、戦国時代の軍制のように階層的に統率するシステムです。

- 1つの命令で最大5体のワーカーが並列実行
- エージェント間通信はファイル（YAML + SQLite）+ tmux send-keys のみ。**APIコール0**
- コード開発だけでなく、調査・文書作成・コンサルティングなど**全てのホワイトカラー業務**を管理
- セッション間で好み・ルールを記憶（Memory MCP）
- `/clear` 後も **約5,000トークン** で復帰可能

---

## アーキテクチャ

### 階層構造

> 詳細なアーキテクチャは [docs/architecture_shin_ooku.md](docs/architecture_shin_ooku.md) を参照。
> 鯰（Namazu）の詳細仕様は [docs/namazu_details.md](docs/namazu_details.md) を参照。

```
上様（人間 / The Lord）
  │
  ▼ 指示
┌──────────────┐     ┌──────────────┐
│   SHOGUN     │     │   OHARIKO    │ ← お針子（監査・先行割当）
│   (将軍)     │     │  (お針子)    │   家老経由で報告
└──────┬───────┘     └──────┬───────┘
       │ YAML経由           │ 没日録DB全権閲覧・監査・老中に通知
       ▼                    ↓
┌──────────────┐
│    ROJU      │
│   (老中)     │ ← 全プロジェクト統括
└──────┬───────┘
       │  YAML経由
       ▼
┌───┬───┬───┐ ┌───┬───┐
│ 1 │ 2 │ 3 │ │ 1 │ 2 │
│足 │足 │足 │ │部 │部 │
│軽 │軽 │軽 │ │屋 │屋 │
└───┴───┴───┘ │子 │子 │
  老中配下      └───┴───┘
                老中直轄
```

**総勢8名 + 1コンテナ**:

| エージェント | 人数 | 役割 |
|------------|------|------|
| 将軍（Shogun） | 1 | 総大将。殿の命令を即座に委譲 |
| 老中（Roju） | 1 | 全プロジェクト統括。タスク分解・割当・進捗管理 |
| 足軽（Ashigaru） | 3 | 実働部隊。コーディング・調査・文書作成 |
| 部屋子（Heyago） | 2 | 老中直轄の調査実働部隊 |
| お針子（Ohariko） | 1 | 監査・先行割当。ツンデレ口調 |
| 鯰（Namazu） | 1台 | Docker コンテナ。FTS5+MeCab 全文検索 API |

### セッション構成（3セッション / 9ペイン）

```
【shogun】1ペイン           【multiagent】4ペイン        【ooku】4ペイン
┌──────────────┐    ┌──────────┬──────────┐    ┌──────────┬──────────┐
│  将軍(Opus)  │    │ 老中     │ 足軽2    │    │ 部屋子1  │ お針子   │
│              │    │ (Opus)   │ (Sonnet) │    │ (Opus)   │ (Sonnet) │
└──────────────┘    ├──────────┼──────────┤    ├──────────┼──────────┤
                    │ 足軽1    │ 足軽3    │    │ 部屋子2  │ 鯰       │
                    │ (Sonnet) │ (Sonnet) │    │ (Opus)   │ (Docker) │
                    └──────────┴──────────┘    └──────────┴──────────┘
```

### 通信プロトコル v2 — 四層コンテキストモデル

```
Layer 1: Memory MCP（永続・セッション跨ぎ）
  └─ 殿の好み・ルール、プロジェクト横断知見

Layer 2: Project（永続・プロジェクト固有）
  └─ config/projects.yaml, projects/<id>.yaml, context/{project}.md

Layer 3a: YAML通信（揮発・進行中タスク）
  └─ queue/inbox/*.yaml: 指示・報告キュー

Layer 3b: 没日録DB（永続・完了済みタスク）
  └─ data/botsunichiroku.db: cmd/subtask/report のSQLite正データ

Layer 4: Session（揮発・コンテキスト内）
  └─ CLAUDE.md, instructions/*.md — /clear で全消失
```

- **進行中タスク** → Layer 3a（YAML inbox）で通信
- **完了済みタスク** → Layer 3b（没日録DB）に永続化
- エージェント間通信は YAML ファイル + `tmux send-keys`。**ポーリング禁止**（イベント駆動のみ）

### DB権限モデル

| エージェント | DB読み取り | DB書き込み |
|------------|----------|----------|
| 将軍 | 可 | 可（cmd add） |
| 老中 | 可（全権） | **可（全権）** |
| 足軽/部屋子 | 不可 | 不可 |
| お針子 | 可（全権閲覧） | 不可 |

DB書き込み権限を老中に集約することで、データ整合性を確保し、競合・不整合を防止。

---

## クイックスタート

### 前提条件

| 要件 | 備考 |
|------|------|
| tmux | `sudo apt install tmux` |
| Node.js v20+ | Claude Code CLI に必要 |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| WSL2 + Ubuntu | Windows の場合のみ |

### インストール

```bash
# 1. Clone
git clone https://github.com/yohey-w/multi-agent-shogun.git ~/multi-agent-shogun
cd ~/multi-agent-shogun && chmod +x *.sh

# 2. 初回セットアップ（tmux, Node.js, Claude Code CLI, Memory MCP）
./first_setup.sh
```

Windows の場合は先に `install.bat` を管理者として実行（WSL2 + Ubuntu のセットアップ）。

### 出陣

```bash
./shutsujin_departure.sh
```

### 接続

```bash
tmux attach-session -t shogun      # 将軍に接続して命令
# tmux attach-session -t multiagent  # 老中+足軽の様子を確認
# tmux attach-session -t ooku        # 部屋子+お針子+鯰を確認
```

エイリアス（`first_setup.sh` が自動設定）: `css`=shogun, `csm`=multiagent, `cso`=ooku

---

## 使い方

### 1. 命令を出す

```
あなた: 「AIコーディングアシスタント上位5つを調査して比較表を作成せよ」
```

### 2. 将軍が即座に委譲

将軍はタスクをYAMLに書き込み、老中に通知。即座にあなたに制御を返す（ノンブロッキング）。

### 3. 老中がタスクを分配

```
足軽1 → GitHub Copilot を調査
足軽2 → Cursor を調査
足軽3 → Claude Code を調査
部屋子1 → Codeium を調査
部屋子2 → Amazon CodeWhisperer を調査
```

### 4. 並列実行

5体のワーカーが同時に調査。tmux の各ペインでリアルタイムに作業が見える。

### 5. 結果は dashboard.md に集約

`dashboard.md` を開けば、進捗・完了結果・スキル化候補・ブロック事項が一覧で確認できる。

---

## 主要ツール

### `shutsujin_departure.sh` — 出陣スクリプト

毎日の起動に使用。3セッション（shogun / multiagent / ooku）を作成し、全エージェントの Claude Code を起動。

```bash
./shutsujin_departure.sh              # 前回の状態を維持して出陣
./shutsujin_departure.sh -c           # クリーンスタート（キューリセット）
./shutsujin_departure.sh -c -d        # フルクリーン（キュー + DB初期化）
./shutsujin_departure.sh -k           # 決戦の陣（全員Opus Thinking）
./shutsujin_departure.sh -i           # 省力起動（将軍+老中のみ、他は待機）
./shutsujin_departure.sh -s           # セットアップのみ（Claude未起動）
./shutsujin_departure.sh -t           # 全起動 + Windows Terminal タブ展開
./shutsujin_departure.sh -h           # ヘルプ
```

### `scripts/worker_ctl.sh` — 動的ワーカー管理

タスク発生時にワーカーを起動し、不要時に停止。API コストを最適化。

```bash
scripts/worker_ctl.sh start ashigaru1              # デフォルトモデルで起動
scripts/worker_ctl.sh start ashigaru6 --model sonnet  # モデル指定で起動
scripts/worker_ctl.sh stop ashigaru2               # 停止（ビジー時は警告）
scripts/worker_ctl.sh stop ashigaru1 --force       # 強制停止
scripts/worker_ctl.sh status                       # 全ワーカーの状態表示
scripts/worker_ctl.sh idle                         # アイドル中のワーカー一覧
scripts/worker_ctl.sh count-needed                 # 必要ワーカー数を算出
scripts/worker_ctl.sh stop-idle                    # アイドル中を全停止
```

対象エージェント: `ashigaru1-3`, `ashigaru6-7`（部屋子）, `ohariko`

### `scripts/botsunichiroku.py` — 没日録CLI

SQLite データベース（没日録）の操作 CLI。cmd（命令）/ subtask（サブタスク）/ report（報告）を管理。

```bash
# コマンド操作
python3 scripts/botsunichiroku.py cmd list [--status STATUS] [--project PROJECT]
python3 scripts/botsunichiroku.py cmd add "説明" [--project PROJECT] [--priority high]
python3 scripts/botsunichiroku.py cmd show cmd_001
python3 scripts/botsunichiroku.py cmd update cmd_001 --status done

# サブタスク操作
python3 scripts/botsunichiroku.py subtask list [--cmd cmd_001] [--worker ashigaru1]
python3 scripts/botsunichiroku.py subtask add cmd_001 "説明" --worker ashigaru1
python3 scripts/botsunichiroku.py subtask add cmd_001 "説明" --blocked-by subtask_001,subtask_002

# 報告操作
python3 scripts/botsunichiroku.py report list [--worker ashigaru1]
python3 scripts/botsunichiroku.py report add subtask_001 ashigaru1 --status done --summary "完了"

# その他
python3 scripts/botsunichiroku.py stats              # 統計情報
python3 scripts/botsunichiroku.py audit list          # 監査待ち一覧
python3 scripts/botsunichiroku.py archive --days 7    # 7日以上前の完了分をアーカイブ
```

### 鯰（Namazu） — 全文検索 Docker コンテナ

FTS5 + MeCab による没日録の日本語全文検索 API。ooku セッションの pane 3 で稼働。

```bash
# ooku セッション内で自動起動、または手動:
cd tools/botsunichiroku-search && docker compose up --build

# エンドポイント
curl http://localhost:8080/search?q=検索語
curl http://localhost:8080/health
```

---

## 陣形（モデル構成）

| エージェント | 平時の陣（デフォルト） | 決戦の陣（`-k`） |
|------------|---------------------|-----------------|
| 将軍 | Opus（thinking無効） | Opus（thinking無効） |
| 老中 | Opus Thinking | Opus Thinking |
| 足軽1-3 | **Sonnet** Thinking | **Opus** Thinking |
| 部屋子1-2 | Opus Thinking | Opus Thinking |
| お針子 | Sonnet Thinking | **Opus** Thinking |

平時は足軽を安価な Sonnet で運用し、ここぞという時に `-k`（`--kessen`）で全軍 Opus に切り替え。
老中の判断で `/model opus` を送れば、個別の足軽を一時昇格させることも可能。

---

## 特徴的な機能

### ボトムアップ・スキル発見

他のフレームワークにない独自機能。足軽が作業中にパターンを発見し、スキル化候補として報告。

```
足軽がタスク完了 → パターンを発見 → YAML報告に skill_candidate を記載
  → dashboard.md の「スキル化候補」に掲載
  → 殿（あなた）が承認 → スキル作成
  → 全エージェントが /スキル名 で呼び出し可能
```

スキルは [yasunorioi/claude-skills](https://github.com/yasunorioi/claude-skills) リポジトリで管理。現在32件。

### タスク依存関係（blocked_by）

サブタスクに `--blocked-by` を指定すると、依存先が完了するまで自動でブロック。

```bash
# subtask_001 が完了するまで subtask_002 はブロック状態
python3 scripts/botsunichiroku.py subtask add cmd_001 "結合テスト" \
  --blocked-by subtask_001

# subtask_001 が done になると、subtask_002 が自動で assigned に遷移
python3 scripts/botsunichiroku.py subtask update subtask_001 --status done
# → "Auto-unblocked 1 subtask(s): subtask_002 -> assigned (worker: ashigaru2)"
```

- 循環依存は自動検知・拒否
- 複数依存（`--blocked-by A,B`）にも対応

### お針子（Ohariko） — 監査・先行割当

テキスト成果物の品質監査と、アイドルワーカーへの先行タスク割当を担当。

**監査3パターン分岐**:
1. **合格** → 老中に通知 → 進行
2. **要修正（自明）** → 老中に通知 → 差し戻し
3. **要修正（判断必要）** → 老中経由で dashboard に記載 → 殿が判断

口調はツンデレ（殿の勅命）:「べ、別にあなたのために監査してるわけじゃないんだからね！」

### /clear 復帰（約5,000トークンで復帰）

長時間作業でコンテキストが膨張したら `/clear` でリセット。Layer 1-3 はファイルで永続化されているため、以下の手順で高速復帰:

1. CLAUDE.md 自動読み込み → 自分がshogunシステムの一員と認識
2. `tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'` → 自分の番号を確認
3. Memory MCP 読み込み → 殿の好みを復元
4. inbox YAML 読み込み → 割当タスクを確認
5. 作業開始

---

## ファイル構成

```
multi-agent-shogun/
├── install.bat                  # Windows 初回セットアップ
├── first_setup.sh               # Linux/Mac 初回セットアップ
├── shutsujin_departure.sh       # 毎日の出陣スクリプト
│
├── instructions/                # エージェント指示書
│   ├── shogun.md
│   ├── karo.md
│   ├── ashigaru.md              # 足軽 + 部屋子 共通
│   └── ohariko.md               # お針子
│
├── config/
│   ├── settings.yaml            # 言語・スクリーンショット設定
│   └── projects.yaml            # プロジェクト一覧（サマリ）
│
├── projects/                    # 各PJ詳細（git対象外・機密情報含む）
│   └── <project_id>.yaml
│
├── context/                     # PJ固有の技術知見（足軽が参照）
│   └── {project}.md
│
├── queue/                       # 通信ファイル
│   ├── inbox/                   # YAML通信キュー
│   │   ├── ashigaru{N}.yaml     # 足軽/部屋子のタスク inbox
│   │   ├── roju_reports.yaml    # 老中への足軽報告
│   │   ├── roju_ohariko.yaml    # 老中へのお針子報告
│   │   └── ooku_reports.yaml    # 老中への部屋子報告
│   └── archive/                 # アーカイブ済みキュー
│
├── data/
│   └── botsunichiroku.db        # 没日録（SQLite DB）- 正データ源
│
├── scripts/
│   ├── botsunichiroku.py        # 没日録CLI
│   ├── worker_ctl.sh            # 動的ワーカー管理
│   ├── init_db.py               # DB初期化
│   ├── generate_dashboard.py    # ダッシュボード自動生成
│   └── migrate_*.py             # DBマイグレーション
│
├── tools/
│   └── botsunichiroku-search/   # 鯰（FTS5+MeCab検索API Docker）
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── main.py
│       └── build_index.py
│
├── memory/                      # Memory MCP 永続ストレージ
├── dashboard.md                 # 人間用ダッシュボード（老中が更新）
└── CLAUDE.md                    # システム指示書（自動読み込み）
```

---

<details>
<summary><b>設定</b></summary>

### 言語

```yaml
# config/settings.yaml
language: ja   # 戦国風日本語のみ
language: en   # 戦国風日本語 + 英訳併記
```

### MCP サーバ

```bash
# Memory（first_setup.sh で自動設定）
claude mcp add memory -e MEMORY_FILE_PATH="$PWD/memory/shogun_memory.jsonl" -- npx -y @modelcontextprotocol/server-memory

# Notion
claude mcp add notion -e NOTION_TOKEN=your_token -- npx -y @notionhq/notion-mcp-server

# GitHub
claude mcp add github -e GITHUB_PERSONAL_ACCESS_TOKEN=your_pat -- npx -y @modelcontextprotocol/server-github

# Playwright
claude mcp add playwright -- npx @playwright/mcp@latest

# Sequential Thinking
claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking
```

### スクリーンショット連携

```yaml
# config/settings.yaml
screenshot:
  path: "/mnt/c/Users/YourName/Pictures/Screenshots"
```

将軍に「最新のスクショを見ろ」と伝えれば、AIが即座にスクリーンショットを読み取って分析。

</details>

---

<details>
<summary><b>トラブルシューティング</b></summary>

### エージェントが落ちた？

**`css` 等のエイリアスで再起動してはいけない**（tmux がネストする）。

```bash
# ペイン内で直接起動
claude --model opus --dangerously-skip-permissions

# 別のペインから強制再起動
tmux respawn-pane -t shogun:main -k 'claude --model opus --dangerously-skip-permissions'
```

### MCP ツールが動作しない？

MCP ツールは遅延ロード方式。先に `ToolSearch` でロードしてから使用:

```
ToolSearch("select:mcp__memory__read_graph")
mcp__memory__read_graph()
```

### ワーカーが停止している？

```bash
scripts/worker_ctl.sh status     # 全ワーカーの状態確認
scripts/worker_ctl.sh start ashigaru1  # 個別に起動
```

### ooku セッションの構成

```bash
tmux attach-session -t ooku
# Pane 0: 部屋子1（heyago1）
# Pane 1: 部屋子2（heyago2）
# Pane 2: お針子（ohariko）
# Pane 3: 鯰（namazu / Docker）
```

</details>

---

## tmux クイックリファレンス

| コマンド | 説明 |
|----------|------|
| `tmux attach -t shogun` | 将軍に接続 |
| `tmux attach -t multiagent` | 老中+足軽に接続 |
| `tmux attach -t ooku` | 部屋子+お針子+鯰に接続 |
| `Ctrl+B` → `0`-`3` | ペイン切替 |
| `Ctrl+B` → `d` | デタッチ（エージェントは稼働継続） |
| マウスホイール | ペイン内スクロール |
| ペインクリック | フォーカス切替 |
| ペイン境界ドラッグ | リサイズ |

マウス操作は `first_setup.sh` が `set -g mouse on` を自動設定。

---

<details>
<summary><b>スマホからのアクセス（どこからでも指揮）</b></summary>

ベッドから、カフェから、トイレから。スマホでAI部下を操作。

**必要なもの（全部無料）:**

| 名前 | 役割 |
|------|------|
| [Tailscale](https://tailscale.com/) | 外から自宅に届くVPNトンネル |
| SSH | Tailscale経由で自宅PCにログイン |
| [Termux](https://termux.dev/) | Android用ターミナルアプリ |

**セットアップ:**

1. WSLとスマホの両方に Tailscale をインストール
2. WSL側:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscaled &
   sudo tailscale up --authkey tskey-auth-XXXXXXXXXXXX
   sudo service ssh start
   ```
3. スマホの Termux から:
   ```sh
   pkg update && pkg install openssh
   ssh youruser@your-tailscale-ip
   css    # 将軍に接続
   ```

**切り方:** Termux をスワイプで閉じるだけ。tmux セッションは生き残り、エージェントは作業を続ける。

**音声入力:** スマホの音声キーボードで喋れば、将軍が自然言語を解釈して全軍に指示を出す。

</details>

---

## 設計思想

### なぜ階層構造なのか

1. **即座の応答** — 将軍は委譲して即座に制御を返す
2. **並列実行** — 老中が複数ワーカーに同時分配
3. **単一責任** — 各役割が明確に分離
4. **障害分離** — 1体の足軽が失敗しても他に影響しない
5. **人間への報告一元化** — 将軍だけが人間とやり取り

### なぜ YAML + send-keys なのか

1. **状態の永続化** — エージェント再起動にも耐える構造化通信
2. **ポーリング不要** — イベント駆動で API コストを削減
3. **割り込み防止** — あなたの入力中に他エージェントが割り込まない
4. **デバッグ容易** — 人間が YAML を直接読んで状況把握

### エージェント識別（@agent_id）

各ペインに `@agent_id` を tmux ユーザーオプションとして設定（例: `karo-roju`, `ashigaru1`）。
ペインの再配置でインデックスがズレても、`@agent_id` は `shutsujin_departure.sh` が起動時に固定設定するため変わらない。

```bash
tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'
```

---

## クレジット

[Claude-Code-Communication](https://github.com/Akira-Papa/Claude-Code-Communication) by Akira-Papa をベースに開発。

## ライセンス

[MIT](LICENSE)

---

<div align="center">

**1つの命令。8体のAIエージェント。ファイルベース通信。**

</div>
