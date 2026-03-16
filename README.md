<div align="center">

# multi-agent-shogun

**Claude Code + tmux によるマルチエージェント並列開発基盤**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)

*戦国軍制モチーフの階層構造で複数プロジェクトを並行管理*

[English](README_EN.md)

</div>

---

複数の Claude Code インスタンスを tmux 上で同時に実行し、戦国時代の軍制のように階層的に統率するシステムです。コマンド1つで最大8体のAIエージェントが並列稼働し、タスク分解・実行・監査・戦略立案を自律的に行います。

## 階層構造

```
上様（人間）
  │
  ▼ 指示
┌──────────────┐
│   SHOGUN     │ ← 総大将
│   (将軍)     │
└──────┬───────┘
       │ YAML経由
       ▼
┌──────────────┐     ┌──────────────┐
│    ROJU      │     │   GUNSHI     │ ← 戦略立案・L4-L6分析
│   (老中)     │────▶│   (軍師)     │
└──────┬───────┘     └──────────────┘
       │                    ↑
       ▼                    │ 監査結果
┌───┐ ┌───┐ ┌───┐  ┌──────────────┐
│足 │ │足 │ │部 │  │   OHARIKO    │ ← 事後監査・先行割当
│軽 │ │軽 │ │屋 │  │  (お針子)    │
│ 1 │ │ 2 │ │子 │  └──────────────┘
└───┘ └───┘ └───┘
```

| エージェント | 人数 | 役割 | デフォルトモデル |
|------------|------|------|--------------|
| 将軍 | 1 | 総大将。殿の命令を即座に委譲 | Opus |
| 老中 | 1 | 全プロジェクト統括。タスク分解・割当・品質管理 | Opus |
| 足軽 | 2 | 実働部隊。コード実装・テスト | Sonnet |
| 部屋子 | 1 | 老中直轄の調査・分析実働 | Opus |
| 軍師 | 1 | 戦略立案・Bloom L4-L6分析・North Star設計 | Opus |
| お針子 | 1 | 2段階監査（仕様準拠チェック + ルーブリック採点） | Sonnet |
| 高札 | 1台 | FTS5全文検索API + 連想記憶エンジン（Docker） | - |
| 獏 | 1台 | 夢見デーモン（1h周期 Web検索 + 日次サマリ） | - |

---

## 通信プロトコル v3

エージェント間の通信はイベント駆動（ポーリング禁止）。YAML inbox + tmux send-keys で非同期連携。

| 機能 | 説明 |
|------|------|
| **Request ID 相関** | 全通信に UUID 短縮8文字を付与。指示→報告が1対1で紐付き |
| **Drain-on-Read** | inbox 読み取り時に自動クリア |
| **Identity Re-injection** | コンパクション復帰時にエージェントの身元・タスクを自動注入 |
| **高札API報告登録** | 報告本文をDB登録、YAML inboxにはサマリ+参照IDのみ |

```
指示: 将軍 → YAML → 老中 → YAML → 足軽/部屋子
分析: 老中 → YAML → 軍師 → YAML → 老中（Bloom L4-L6委譲）
報告: 足軽 → 高札API + YAML → 老中 → dashboard.md
監査: お針子 → YAML → 老中（2段階: Phase1仕様準拠 + Phase2ルーブリック）
```

## 記憶の四層モデル

```
Layer 1: Memory MCP     ← 殿の好み・ルール（セッション跨ぎ永続）
Layer 2: Project YAML   ← プロジェクト固有情報（config/, context/）
Layer 3a: YAML通信      ← 進行中タスク（揮発）
Layer 3b: 没日録DB      ← 完了済みタスク + 日記（SQLite永続）
Layer 4: Session        ← instructions/*.md（コンパクションでsummary化）
```

instructions は最小限のルール+インデックスのみ保持し、詳細手順は高札（`localhost:8080/docs/`）から必要時に取得する「掟上今日子方式」を採用。

## 主要コンポーネント

### 没日録（データベース）

| コンポーネント | 説明 |
|--------------|------|
| `scripts/botsunichiroku.py` | 没日録CLI — cmd/subtask/report/agent/diary の CRUD |
| `scripts/init_db.py` | DB初期化（commands, subtasks, reports, agents, diary_entries 等） |
| `data/botsunichiroku.db` | SQLite DB（正データ。dashboard.md は二次情報） |

### 通信・制御

| コンポーネント | 説明 |
|--------------|------|
| `scripts/inbox_write.sh` | inbox 書き込み（Request ID 自動生成） |
| `scripts/inbox_read.sh` | inbox 読み取り（Drain-on-Read） |
| `scripts/identity_inject.sh` | コンパクション復帰時の身元自動注入 |
| `scripts/worker_ctl.sh` | ワーカー動的起動/停止 |
| `scripts/shogun-gc.sh` | 報告 YAML 自動 GC（直近10件保持） |

### 高札（検索・知識API）

| コンポーネント | 説明 |
|--------------|------|
| `tools/kousatsu/` | 高札API — FTS5全文検索 + docs配信 + 連想記憶エンジン（Docker） |
| `scripts/build_cooccurrence.py` | 共起行列構築（連想記憶用） |

### 夢見・探索

| コンポーネント | 説明 |
|--------------|------|
| `scripts/dream.py` | 夢見機能 — 殿の興味マップ × 直近キーワードで Web検索 |
| `scripts/baku.py` | 獏デーモン — 1時間毎に dream.py 実行、毎朝7時に日次サマリ |

### 監査・品質

| コンポーネント | 説明 |
|--------------|------|
| `scripts/audit_grading.py` | お針子ルーブリック採点（5カテゴリ × 3点 = 15点満点） |
| `scripts/gatekeeper_f006.sh` | pre-commit フック — GitHub Issue/PR 誤投稿防止 |

### 日記・まとめ

| コンポーネント | 説明 |
|--------------|------|
| `scripts/diary_matome.py` | 2chまとめ風HTML + 2ch互換dat生成（JDim/Jane Style対応） |
| `data/matome/` | まとめHTML出力先 |
| `data/matome/shogun/` | 2ch互換板ディレクトリ（dat/, subject.txt, SETTING.TXT） |

---

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
| Docker | 高札API に必要 |
| Python 3.10+ | 没日録CLI・夢見機能に必要 |
| nginx（任意） | 2chまとめHTMLの配信用 |

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
tmux attach-session -t ooku        # 軍師+お針子+高札+獏を確認
```

エイリアス（`first_setup.sh` が自動設定）: `css`=shogun, `csm`=multiagent, `cso`=ooku

## 使い方

1. 将軍セッションに接続して命令を出す
2. 将軍がタスクを老中に委譲（ノンブロッキング）
3. 老中が五つの問いでタスクを分解、Bloom-based routing で軍師/足軽に振り分け
4. 足軽・部屋子が並列で実装・調査を実行
5. お針子が2段階監査（Phase1: 仕様準拠チェック → Phase2: ルーブリック採点）
6. 結果は `dashboard.md` に集約、没日録DBに永続記録

### 2chブラウザで閲覧

没日録の全活動を2ch互換dat形式で生成。JDim, Jane Style, Siki等で閲覧可能。

```bash
python3 scripts/diary_matome.py --full-rebuild   # 全スレ生成
python3 scripts/diary_matome.py                   # 今日分のみ
```

nginx経由で配信する場合:
```bash
sudo ln -s ~/multi-agent-shogun/data/matome/shogun /var/www/html/botsunichiroku
# → 2chブラウザで http://localhost/botsunichiroku/ を板登録
```

---

<details>
<summary><b>トラブルシューティング</b></summary>

### エージェントが落ちた

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

### 高札APIが応答しない

```bash
cd tools/kousatsu && docker compose up -d   # 高札を起動
curl -s http://localhost:8080/health        # ヘルスチェック
```

</details>

---

## 本家 fork との差分

このリポジトリは [yohey-w/multi-agent-shogun](https://github.com/yohey-w/multi-agent-shogun) の fork です。以下が独自拡張部分：

| 機能 | 概要 |
|------|------|
| **高札 v2 連想記憶エンジン** | FTS5全文検索 + Hopfield共起行列による関連知見の自動抽出 |
| **軍師 (GUNSHI)** | Bloom-based routing による戦略立案・L4-L6分析の専門エージェント |
| **お針子2段階監査** | Phase1: 仕様準拠チェック（早期FAIL）、Phase2: 15点ルーブリック採点 |
| **夢見システム** | 殿の興味マップ × 没日録キーワードのクロスによるセレンディピティ検索 |
| **獏デーモン** | 1時間毎の夢見 + 日次サマリ（人間が寝ている間もシステムが学習） |
| **AI日記** | エージェントの思考過程を記録。コンパクション復帰時の文脈補完 |
| **2ch互換dat生成** | 没日録の全活動を2chブラウザで閲覧可能（dat + subject.txt） |
| **没日録 auto-enrich** | cmd 登録時に自動で高札APIに知見キャッシュ |
| **通信プロトコル v3** | Request ID相関、Drain-on-Read、高札API報告登録 |
| **Identity Re-injection** | コンパクション復帰時の身元・タスク自動注入 |
| **pre-commit Gatekeeper** | GitHub Issue/PR 誤投稿・リポ誤爆の自動防止 |

---

## クレジット

[Claude-Code-Communication](https://github.com/Akira-Papa/Claude-Code-Communication) by Akira-Papa をベースに開発。

## ライセンス

[MIT](LICENSE)
