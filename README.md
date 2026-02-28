<div align="center">

# multi-agent-shogun

**Claude Code + tmux によるマルチエージェント並列開発基盤**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)

</div>

---

複数の Claude Code インスタンスを tmux 上で同時に実行し、戦国時代の軍制のように階層的に統率するシステムです。コマンド1つで最大8体のAIエージェントが並列稼働します。

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
┌───┬───┬───┐ ┌───┬───┐
│ 1 │ 2 │ 3 │ │ 1 │ 2 │
│足 │足 │足 │ │部 │部 │
│軽 │軽 │軽 │ │屋 │屋 │
└───┴───┴───┘ │子 │子 │
  老中配下      └───┴───┘
                老中直轄
```

| エージェント | 人数 | 役割 |
|------------|------|------|
| 将軍 | 1 | 総大将。殿の命令を即座に委譲 |
| 老中 | 1 | 全プロジェクト統括。タスク分解・割当 |
| 足軽 | 3 | 実働部隊 |
| 部屋子 | 2 | 老中直轄の調査実働 |
| お針子 | 1 | 監査・先行割当 |
| 高札 | 1台 | FTS5+MeCab 全文検索 API（Docker） |

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
git clone https://github.com/yohey-w/multi-agent-shogun.git ~/multi-agent-shogun
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
tmux attach-session -t ooku        # 部屋子+お針子+高札を確認
```

エイリアス（`first_setup.sh` が自動設定）: `css`=shogun, `csm`=multiagent, `cso`=ooku

## 使い方

1. 将軍セッションに接続して命令を出す
2. 将軍がタスクを老中に委譲（ノンブロッキング）
3. 老中がタスクを分解し、足軽・部屋子に並列分配
4. 結果は `dashboard.md` に集約

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
