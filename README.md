<div align="center">

# multi-agent-shogun

**Claude Code + tmux によるマルチエージェント並列開発基盤**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)

</div>

---

複数の Claude Code インスタンスを tmux 上で同時に実行し、戦国時代の軍制のように階層的に統率するシステムです。コマンド1つで最大6体のAIエージェントが並列稼働します。

## 階層構造

```
上様（人間）
  │
  ▼ 指示
┌──────────────┐     ┌──────────────┐
│   SHOGUN     │     │   OHARIKO    │ ← 監査・先行割当
│   (将軍)     │     │  (お針子)    │
└──────┬───────┘     └──────────────┘
       │ YAML経由
       ▼
┌──────────────┐
│    ROJU      │ ← 全プロジェクト統括
│   (老中)     │
└──────┬───────┘
       │
       ▼
┌───┐ ┌───┐
│ 1 │ │ 1 │
│足 │ │部 │
│軽 │ │屋 │
└───┘ │子 │
老中配下└───┘
       老中直轄
```

| エージェント | 人数 | 役割 |
|------------|------|------|
| 将軍 | 1 | 総大将。殿の命令を即座に委譲 |
| 老中 | 1 | 全プロジェクト統括。タスク分解・割当 |
| 足軽 | 1 | 実働部隊 |
| 部屋子 | 1 | 老中直轄の調査実働 |
| お針子 | 1 | 監査・先行割当 |
| 高札 | 1台 | FTS5+MeCab 全文検索 API（Docker） |

---

## 通信プロトコル v3

エージェント間の通信はイベント駆動（ポーリング禁止）。YAML inbox + tmux send-keys で非同期連携。

| 機能 | 説明 |
|------|------|
| **Request ID 相関** | 全通信に UUID 短縮8文字を付与。指示→報告が1対1で紐付き、通信ロストを検出 |
| **Drain-on-Read** | inbox 読み取り時に自動クリア。手動削除不要 |
| **Identity Re-injection** | コンパクション復帰時にエージェントの身元・現在タスクを自動注入 |

```
指示: 将軍 → YAML → 老中 → YAML → 足軽/部屋子
報告: 足軽 → YAML → 老中 → dashboard.md（将軍への割り込み禁止）
監査: お針子 → YAML → 老中（監査結果通知）
```

## 記憶の四層モデル

```
Layer 1: Memory MCP     ← 殿の好み・ルール（セッション跨ぎ永続）
Layer 2: Project YAML   ← プロジェクト固有情報
Layer 3a: YAML通信      ← 進行中タスク（揮発）
Layer 3b: 没日録DB      ← 完了済みタスク（SQLite永続）
Layer 4: Session        ← instructions/*.md（コンパクションでsummary化）
```

instructions は最小限のルール+インデックスのみ保持し、詳細手順は高札（`localhost:8080/docs/`）から必要時に取得する「掟上今日子方式」を採用。

## 主要コンポーネント

| コンポーネント | 説明 |
|--------------|------|
| `scripts/botsunichiroku.py` | 没日録 CLI（cmd/subtask/report の CRUD） |
| `scripts/inbox_write.sh` | inbox 書き込み（Request ID 自動生成） |
| `scripts/inbox_read.sh` | inbox 読み取り（Drain-on-Read） |
| `scripts/identity_inject.sh` | コンパクション復帰時の身元自動注入 |
| `scripts/worker_ctl.sh` | ワーカー動的起動/停止 |
| `scripts/shogun-gc.sh` | 報告 YAML 自動 GC（dry-run 対応） |
| `tools/kousatsu/` | 高札 API（FTS5 全文検索 + docs 配信） |
| `docs/adr/` | ADR（Architecture Decision Record） |

## 設計の影響源

| プロジェクト | 取り入れた設計パターン |
|------------|---------------------|
| [memx-core](https://github.com/RNA4219/memx-core) | ADR、自動 GC、Gatekeeper、knowledge 昇格 |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | Request ID 相関、Drain-on-Read、Identity Re-injection |
| [pm-skills](https://github.com/phuryn/pm-skills) | SKILL.md v1 フォーマット、ICE スコアリング |

---

## 前提条件

| 要件 | 備考 |
|------|------|
| tmux | `sudo apt install tmux` |
| Node.js v20+ | Claude Code CLI に必要 |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| WSL2 + Ubuntu | Windows の場合のみ |

## インストール

```bash
git clone https://github.com/yasunorioi/multi-agent-shogun.git ~/multi-agent-shogun
cd ~/multi-agent-shogun && chmod +x *.sh
./first_setup.sh
```

Windows の場合は先に `install.bat` を管理者として実行。

## 出陣

```bash
./shutsujin_departure.sh           # 通常起動
./shutsujin_departure.sh -c        # クリーンスタート（キューリセット）
./shutsujin_departure.sh -c -d     # フルクリーン（キュー + DB初期化）
./shutsujin_departure.sh -k        # 決戦の陣（全員Opus）
./shutsujin_departure.sh -i        # 省力起動（将軍+老中のみ）
./shutsujin_departure.sh -h        # ヘルプ
```

## 接続

```bash
tmux attach-session -t shogun      # 将軍に接続して命令
tmux attach-session -t multiagent  # 老中+足軽の様子を確認
tmux attach-session -t ooku        # お針子+高札を確認
```

エイリアス（`first_setup.sh` が自動設定）: `css`=shogun, `csm`=multiagent, `cso`=ooku

## 使い方

1. 将軍セッションに接続して命令を出す
2. 将軍がタスクを老中に委譲（ノンブロッキング）
3. 老中がタスクを分解し、足軽・部屋子に並列分配
4. お針子がテキスト成果物を自動監査
5. 結果は `dashboard.md` に集約

---

<details>
<summary><b>トラブルシューティング</b></summary>

### エージェントが落ちた

`css` 等のエイリアスで再起動してはいけない（tmux がネストする）。

```bash
# ペイン内で直接起動
claude --model opus --dangerously-skip-permissions

# 別ペインから強制再起動
tmux respawn-pane -t shogun:main -k 'claude --model opus --dangerously-skip-permissions'
```

### ワーカーが停止している

```bash
scripts/worker_ctl.sh status          # 全ワーカーの状態確認
scripts/worker_ctl.sh start ashigaru1 # 個別に起動
```

### MCP ツールが動作しない

MCP ツールは遅延ロード方式。先に `ToolSearch` でロードしてから使用。

</details>

---

## クレジット

[Claude-Code-Communication](https://github.com/Akira-Papa/Claude-Code-Communication) by Akira-Papa をベースに開発。

## ライセンス

[MIT](LICENSE)
