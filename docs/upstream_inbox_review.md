# 本家inbox方式レビューレポート

> **作成日**: 2026-02-09
> **作成者**: 部屋子1（heyago1）— Wave1レポート3本の統合
> **対象リポジトリ**: yohey-w/multi-agent-shogun（mainブランチ、2026-02-09時点）
> **入力レポート**:
> - subtask_323（部屋子1号）: inbox_watcher.sh + inbox_write.sh 詳細分析
> - subtask_324（部屋子2号）: cli_adapter.sh + shutsujin_departure.sh 詳細分析
> - subtask_325（部屋子3号）: instructions/ + コミット履歴 + 安定性評価
> **関連文書**: docs/upstream_v3_analysis.md（cmd_128、2026-02-08作成）

---

## Executive Summary

**推奨: Partial（部分採用）** — 本家のinbox方式は「inotifywaitによるファイル監視＋flockによる排他制御＋3段階nudge escalation」の堅実な設計だが、2/8〜2/9にsend-keys廃止→差し戻しの大きな設計反転があり、通信基盤がまだ安定途上（安定性評価3/5）である。完全移行は時期尚早。ただし、**nudge escalation（自動3段階リトライ）**と**inbox_write.sh（flock排他制御）**の2要素は我々の現行方式の弱点を補完する優れた設計であり、独立して部分採用可能。我々の独自資産（大奥/部屋子/お針子/没日録DB/3セッション構成）は本家に存在せず、完全移行では再実装コストが発生する。1〜2週間の安定化確認後に部分採用を開始し、段階的に取り込むことを推奨する。

---

## 1. 本家inbox方式の技術解説

### 1.1 アーキテクチャ概要（全体フロー図）

本家の通信方式は「書き込みと通知の完全分離」を設計原則とする。メッセージ本文はYAMLファイルに書き込み、通知（nudge）はinotifywaitが自動検知してsend-keysで短い文字列のみを送る。

```
【本家inbox方式 全体フロー】

送信側（家老/足軽）
  │
  ▼ bash scripts/inbox_write.sh <recipient> "<content>" [type] [from]
  │   ├─ flock排他ロック取得（5秒timeout × 3回retry）
  │   ├─ python3: YAML読み込み → メッセージ追加 → atomic write（tmpfile + os.replace）
  │   └─ flock自動解放
  │
  ▼ queue/inbox/{agent}.yaml に書き込み完了
  │
  ║ ← ここで送信側の責務は終了。send-keysは呼ばない。
  ║
  ▼ inbox_watcher.sh（常駐プロセス、エージェント毎に1個）
  │   ├─ inotifywait -q -t 30 -e modify -e close_write $INBOX
  │   │   ├─ rc=0: イベント発火（即時検知）
  │   │   ├─ rc=1: inode変更（atomic writeによるinode交換）→ 再監視
  │   │   └─ rc=2: 30秒タイムアウト（WSL2安全網）
  │   │
  │   ▼ process_unread()
  │       ├─ get_unread_info(): python3でYAML解析（lock-free）
  │       ├─ 特殊メッセージ（/clear, /model）→ send_cli_command()で直送
  │       └─ 通常メッセージ → nudge escalation判定
  │           ├─ Phase1 (0〜2分): send_wakeup("inboxN")
  │           ├─ Phase2 (2〜4分): Escape×2 + C-c + nudge
  │           └─ Phase3 (4分〜): /clear強制送信（5分cooldown付き）
  │
  ▼ tmux send-keys -t {pane} "inbox3"  ← 短いnudgeのみ（本文は送らない）
  │   sleep 0.3
  │   tmux send-keys -t {pane} Enter
  │
  ▼ 受信側エージェント
      └─ nudge受信 → Read queue/inbox/{自分}.yaml → 未読メッセージ処理
```

**核心**: 送信側（inbox_write.sh）はsend-keysを一切使わない。通知はwatcher（常駐プロセス）が自動配信する。

### 1.2 inbox_watcher.sh — ファイル監視メカニズム

| 項目 | 詳細 |
|------|------|
| ファイル | scripts/inbox_watcher.sh（約270行、7関数） |
| 引数 | `<agent_id> <pane_target> [cli_type]` |
| 監視方式 | inotifywait（Linuxカーネルinotify） |
| 監視対象 | 単一ファイル（`queue/inbox/{agent}.yaml`） |
| 監視イベント | `modify`, `close_write` |
| タイムアウト | 30秒（WSL2でinotifyイベントが不発になる問題の安全網） |
| テスト対応 | `__INBOX_WATCHER_TESTING__=1` で関数定義のみロード可能 |

**関数一覧**:

| 関数名 | 役割 |
|--------|------|
| `get_unread_info()` | YAML読み取り（lock-free）、未読数＋特殊メッセージ抽出 |
| `send_cli_command()` | /clear, /model等CLIコマンドをsend-keysで直送 |
| `agent_has_self_watch()` | エージェント自身のinotifywait有無チェック |
| `agent_is_busy()` | tmux capture-paneで「Working/Thinking/Planning/Sending」検出 |
| `send_wakeup()` | 通常nudge送信（Phase1） |
| `send_wakeup_with_escape()` | Escape×2＋C-c＋nudge（Phase2） |
| `process_unread()` | メインロジック: 未読処理＋エスカレーション判定 |

**inotifywait戻り値の処理**:
- `rc=0`: ファイル変更イベント発火（即時検知）
- `rc=1`: inode変更。Claude CodeのEdit/Writeはatomic write（tmpfile作成→os.replace）を行うため、元のinodeが消失しinotifywaitがDELETE_SELFを検出する。ファイル自体は新inodeで存在するため、ループ先頭で再監視する
- `rc=2`: 30秒タイムアウト。WSL2環境でinotifyイベントが発火しないケースの安全網

### 1.3 inbox_write.sh — 排他制御付き書き込み

| 項目 | 詳細 |
|------|------|
| ファイル | scripts/inbox_write.sh（約75行、関数なし） |
| 引数 | `<target_agent> <content> [type] [from]` |
| ロック方式 | flock(2)（カーネルレベル排他ロック） |
| ロックFD | 200（`${INBOX}.lock`） |
| ロックタイムアウト | 5秒 |
| リトライ | 最大3回、1秒間隔 |
| 書き込み方式 | atomic write（tmpfile → yaml.dump → os.replace） |
| メッセージ上限 | 50件（overflow protection: 全未読＋最新30件read保持） |

**書き込みフロー**:

```
inbox_write.sh <target> <content> [type] [from]
  │
  ▼ 引数バリデーション → INBOX未存在なら "messages: []" で初期化
  │
  ▼ MSG_ID生成: msg_YYYYMMDD_HHMMSS_{4bytes_random_hex}
  │
  ▼ flock取得ループ（最大3回）
  │   ├─ flock -w 5 200  ← FD200でINBOX.lockを排他ロック
  │   │   ├─ python3: YAML読み込み → 新メッセージ追加
  │   │   │   {id, from, timestamp, type, content, read: False}
  │   │   ├─ 50件超 → overflow protection
  │   │   ├─ tmpfile作成 → yaml.dump → os.replace（atomic rename）
  │   │   └─ サブシェル終了 → flock自動解放
  │   │
  │   └─ flock取得失敗 → sleep 1 → リトライ（3回失敗→exit 1）
  │
  └─ exit 0
```

**設計上の要点**:
- 読み取り側（watcher）はlock-free。atomic renameにより中間状態のファイルを読むことがない
- 書き込み側のみflockで排他制御。複数エージェントが同時にinbox_write.shを呼んでも安全
- 我々のRACE-001ルール（「同一ファイル書き込み禁止」の人間的制約）の代わりに、カーネルレベルのロックで解決

### 1.4 cli_adapter.sh — Multi-CLI抽象化

| 項目 | 詳細 |
|------|------|
| ファイル | lib/cli_adapter.sh（約230行、5公開関数＋2ヘルパー） |
| 対応CLI | Claude Code / Codex / Copilot / Kimi |
| 設定ソース | config/settings.yaml（python3でYAML解析） |

**公開関数一覧**:

| 関数 | 行数 | 役割 |
|------|------|------|
| `get_cli_type(agent_id)` | ~40行 | CLI種別決定（settings.yaml → default → "claude"） |
| `build_cli_command(agent_id)` | ~25行 | 起動コマンド生成（例: `claude --model opus --dangerously-skip-permissions`） |
| `get_instruction_file(agent_id)` | ~20行 | 指示書パス決定（CLI別: instructions/{role}.md, codex-{role}.md等） |
| `validate_cli_availability(cli_type)` | ~30行 | バイナリ存在チェック（command -v） |
| `get_agent_model(agent_id)` | ~35行 | モデル決定（shogun/karo→opus, ashigaru1-4→sonnet, 5-8→opus） |

**抽象化レイヤー図**:

```
config/settings.yaml
┌───────────────────────────────────────┐
│ cli:                                  │
│   default: claude                     │
│   agents:                             │
│     karo: {type: codex, model: ...}   │
└──────────────┬────────────────────────┘
               │ python3 yaml.safe_load
               ▼
lib/cli_adapter.sh
┌──────────────────────────────────────────────────────┐
│ get_cli_type() ──→ CLI種別決定                       │
│       │                                              │
│       ├──→ build_cli_command()   起動コマンド生成     │
│       ├──→ get_instruction_file() 指示書パス決定     │
│       └──→ get_agent_model()     モデル決定          │
│                                                      │
│ validate_cli_availability() バイナリ存在チェック      │
└──────────────────────────────────────────────────────┘
         │                              │
         ▼ 起動時                        ▼ 実行時
shutsujin_departure.sh            inbox_watcher.sh
┌───────────────────────┐    ┌──────────────────────────┐
│ source cli_adapter.sh │    │ CLI_TYPE引数で受取        │
│ ・起動コマンド生成     │    │ ・nudge送信(全CLI共通)    │
│ ・モデル名表示設定     │    │ ・/clear: CLI別変換       │
│ ・@agent_cli設定       │    │ ・/model: CLI別処理       │
└───────────────────────┘    └──────────────────────────┘
```

**注意**: 本家のget_instruction_fileは shogun/karo/ashigaru の3ロールのみ対応。midaidokoro/heyago/oharikoは未対応（case * → return 1）。

### 1.5 nudge escalation — 3段階自動リトライ

未読メッセージが放置されている時間に応じて、通知方法を段階的にエスカレーションする仕組み。

```
Phase 1（0〜2分）: Standard nudge
  ├─ agent self-watch? → Yes: SKIP（エージェントが自分で気づく）
  ├─ agent busy? → Yes: SKIP（Working中はnudge喪失リスク）
  └─ tmux send-keys "inboxN" + 0.3s + Enter

Phase 2（2〜4分）: Escape + nudge
  ├─ agent self-watch? → Yes: SKIP
  ├─ agent busy? → Yes: SKIP
  └─ Escape×2 + C-c（スタック入力クリア）→ send-keys "inboxN" + Enter

Phase 3（4分〜）: /clear 強制リセット
  ├─ 5分に1回制限（cooldown）
  ├─ CLI別分岐:
  │   ├─ Claude: /clear
  │   ├─ Codex: /new（/clearはCodexで未定義→CLI終了するため）
  │   └─ Copilot: Ctrl-C + 再起動
  └─ cooldown中はPhase2にフォールバック
```

**Redo Protocol**: Phase3で/clearされたエージェントは、家老がredo_ofフィールド付きの新task YAMLを作成し、再割当する仕組み。

### 1.6 shutsujin_departure.sh — 起動シーケンス

本家の全体起動フロー（inbox_watcher関連を中心に）:

| STEP | 内容 |
|------|------|
| 1 | 既存セッションkill（multiagent, shogun） |
| 1.5 | `--clean`時バックアップ |
| 2 | キュー確保＋inbox→Linux FSシンボリックリンク（WSL2対策） |
| 3 | `--clean`時ダッシュボード初期化 |
| 4 | tmux存在確認 |
| 5 | shogunセッション（1ペイン） |
| 5.1 | multiagentセッション（3×3=9ペイン） |
| 6 | Claude Code起動（将軍→家老→足軽の順） |
| 6.5 | 指示書読み込み→各エージェント自律実行 |
| **6.6** | **inbox_watcher起動（以下詳細）** |
| 6.8 | ntfyリスナー（settings.yamlで設定時のみ） |
| 7-8 | 環境確認表示、Windows Terminal展開 |

**STEP 6.6 inbox_watcher起動の詳細**:
1. `mkdir -p logs/`
2. inbox YAML初期化（10ファイル: shogun, karo, ashigaru1-8）
3. 既存プロセスkill: `pkill -f "inbox_watcher.sh"` + `pkill -f "inotifywait.*queue/inbox"`
4. **将軍はwatcherなし**（殿が直接操作するペインのためnudgeが邪魔）
5. 家老watcher: `nohup bash scripts/inbox_watcher.sh karo "{pane}" "$cli_type" &`
6. 足軽watcher（i=1..8）: `nohup bash scripts/inbox_watcher.sh "ashigaru{i}" "{pane}" "$cli_type" &`

**セッション構成の違い**:
- 本家: 2セッション（shogun + multiagent）、10ペイン（将軍1＋家老1＋足軽8）
- 我々: 3セッション（shogun + multiagent + ooku）、12ペイン

---

## 2. 我々の現行方式との差異比較表

| # | 観点 | 本家（inbox_watcher方式） | 我々（send-keys方式 v2） |
|---|------|--------------------------|------------------------|
| 1 | **通知方式** | inotifywait（OS監視）→ watcherが自動nudge | エージェント自身がtmux send-keys（手動2回） |
| 2 | **排他制御** | flock(2) カーネルレベルロック（5秒timeout, 3回retry） | RACE-001ルール（同一ファイル書き込み禁止の人間的制約） |
| 3 | **エスカレーション** | 自動3段階（nudge → Escape+nudge → /clear）、時間ベース | 手動リトライ3回・10秒間隔、自動/clearなし |
| 4 | **CLI対応** | Claude / Codex / Copilot / Kimi の4種 | Claude Code専用 |
| 5 | **セッション構成** | 2セッション（shogun + multiagent）、10ペイン | 3セッション（shogun + multiagent + ooku）、12ペイン |
| 6 | **ファイル構造** | 3種分離（task / report / inbox） | inbox統合型（指示＋報告を同一体系で管理） |
| 7 | **DB層** | なし（YAML only） | 没日録DB（botsunichiroku.db、SQLite） |
| 8 | **エージェント種別** | 将軍 / 家老 / 足軽（3種） | 将軍 / 老中 / 御台所 / 足軽 / 部屋子 / お針子（6種） |
| 9 | **テスト性** | batsテスト132+件、`__TESTING__=1`ガード付き | なし |
| 10 | **WSL2対応** | inbox→Linux FSシンボリックリンク（/mnt/c/でinotify不可対策） | 不要（Linux直接運用） |
| 11 | **常駐プロセス** | 1プロセス/エージェント（watcher 9個＋inotifywait 9個） | なし（エージェントが直接通信） |
| 12 | **到達確認** | 不要（YAMLファイルに永続化、watcherが再送） | capture-pane手動確認＋再送（最大2回） |
| 13 | **メッセージ永続性** | YAMLファイルに永続化（50件上限、overflow protection） | 揮発（没日録DBで完了後に永続化） |
| 14 | **busy検出** | Working / Thinking / Planning / Sending | thinking / Effecting / Boondoggling |
| 15 | **将軍ペイン保護** | watcherを起動しない | send-keys禁止ルール（dashboard.md更新のみ） |
| 16 | **send-keys分離** | テキスト＋Enter分離（0.3s gap）— 同じ方式 | テキスト＋Enter分離 — 同じ方式 |
| 17 | **atomic write対応** | inotifywait rc=1ハンドル（inode変更検知→再監視） | 不要（send-keys直接） |
| 18 | **安全ルール** | D001-D008（破壊操作禁止） | F001-F005（切腹ルール） |

---

## 3. 移行に必要な作業見積もり

### 3.1 完全移行（Full Migration）

本家のinbox方式を全面採用し、我々のsend-keys方式を完全に置き換える場合。

| # | 作業項目 | 対象ファイル | 変更量 |
|---|---------|-------------|--------|
| 1 | inbox_watcher.sh 移植 | scripts/inbox_watcher.sh（新規） | ~270行 |
| 2 | inbox_write.sh 移植 | scripts/inbox_write.sh（新規） | ~75行 |
| 3 | cli_adapter.sh 移植＋拡張 | lib/cli_adapter.sh（新規） | ~250行 |
| 4 | shutsujin_departure.sh 改修 | scripts/shutsujin_departure.sh | 大規模改修（ookuセッション＋watcher起動追加） |
| 5 | CLAUDE.md 通信プロトコル改訂 | CLAUDE.md | send-keys記述の全面書き換え |
| 6 | instructions/ashigaru.md 改訂 | instructions/ashigaru.md | 報告フロー・send-keys手順の全面書き換え |
| 7 | instructions/karo.md 改訂 | instructions/karo.md | スキャン方式の変更 |
| 8 | instructions/ohariko.md 改訂 | instructions/ohariko.md | 通信フロー変更 |
| 9 | 大奥対応拡張 | inbox_watcher.sh, cli_adapter.sh | 部屋子・お針子のwatcher追加（本家未対応） |
| 10 | inotify-tools インストール | システム依存 | `sudo apt install inotify-tools` |
| 11 | テスト作成 | tests/（新規） | batsテスト移植＋大奥テスト追加 |
| 12 | 没日録DB連携 | scripts/botsunichiroku.py | inbox YAML→DB連携の調整 |

**合計**: 12作業項目、10+ファイル変更、~1,000行の新規コード＋全instructions改訂
**想定工数**: 5〜7日（テスト含む）

**リスク**: 通信方式の全面変更は、運用中の全エージェントに影響する。段階的な移行が困難（旧方式と新方式の混在は複雑）。

### 3.2 部分採用（Partial Adoption）

本家の優れた要素のみを選択的に取り込む場合。

#### 採用候補A: nudge escalation（自動3段階リトライ）

| 作業項目 | 対象ファイル | 変更量 |
|---------|-------------|--------|
| escalationロジック移植 | scripts/nudge_escalation.sh（新規） | ~80行 |
| instructions/karo.md 改訂 | instructions/karo.md | escalation呼び出し追加 |
| CLAUDE.md 更新 | CLAUDE.md | エスカレーション説明追加 |

**効果**: 応答しないエージェントを自動復旧。現在の手動リトライ（3回・10秒間隔）を置き換え。
**工数**: 1日

#### 採用候補B: inbox_write.sh（flock排他制御）

| 作業項目 | 対象ファイル | 変更量 |
|---------|-------------|--------|
| inbox_write.sh 移植 | scripts/inbox_write.sh（新規） | ~75行 |
| instructions/ashigaru.md 改訂 | instructions/ashigaru.md | Edit直接→inbox_write.sh呼び出しに変更 |
| RACE-001ルール緩和 | CLAUDE.md, instructions/ | 同一ファイル書き込み禁止→flock排他に変更 |

**効果**: 複数足軽が同一報告YAMLに安全に書き込み可能。RACE-001の人間的制約をカーネルレベル制約に昇格。
**工数**: 1〜2日

#### 採用候補C: overflow protection

| 作業項目 | 対象ファイル | 変更量 |
|---------|-------------|--------|
| YAML肥大化防止ロジック | scripts/inbox_cleanup.sh（新規） or inbox_write.sh内 | ~20行 |

**効果**: inbox YAMLの無限肥大化を防止（50件上限、全未読＋最新30件read保持）。
**工数**: 半日

### 3.3 各作業のファイル数・工数概算

| 移行方式 | 新規ファイル | 既存変更ファイル | 合計行数 | 工数 |
|---------|------------|----------------|---------|------|
| **完全移行** | 4ファイル | 6+ファイル | ~1,000行新規＋大規模改訂 | 5〜7日 |
| **部分A: escalation** | 1ファイル | 2ファイル | ~80行新規 | 1日 |
| **部分B: flock排他** | 1ファイル | 2ファイル | ~75行新規 | 1〜2日 |
| **部分C: overflow** | 1ファイル | 0ファイル | ~20行新規 | 半日 |
| **部分A+B+C合計** | 3ファイル | 3ファイル | ~175行新規 | 2〜3日 |

---

## 4. 推奨

### 4.1 推奨案: Partial（部分採用）

**nudge escalation＋flock排他制御＋overflow protection の3要素を段階的に採用する。**

### 4.2 判断理由

#### 完全移行を推奨しない理由

1. **安定性が未確定**: 本家は2/8〜2/9の2日間でsend-keys関連7コミットの試行錯誤があった。pty direct write→send-keys差し戻しという大きな設計反転が発生しており、通信基盤がまだ流動的（安定性評価3/5）
2. **独自資産の再実装コスト**: 大奥（御台所/部屋子/お針子）、没日録DB、3セッション構成は本家に存在しない。完全移行ではこれらを全て再実装する必要がある
3. **inotifywait依存**: 我々はLinux直接運用だがinotify-toolsの追加依存が発生する。WSL2環境では30秒タイムアウトでの対策が必要
4. **移行中のリスク**: 通信方式の全面変更は運用中の全エージェントに影響し、旧方式と新方式の混在は複雑

#### 部分採用を推奨する理由

1. **nudge escalationは独立採用可能**: 既存のsend-keys方式の上にエスカレーションロジックを追加するだけで、通信基盤の変更は不要
2. **flock排他は我々の弱点を直接補完**: RACE-001（同一ファイル書き込み禁止の人間的制約）をカーネルレベル排他に置き換えることで、報告YAML書き込みの競合を根本解決
3. **工数が小さい**: 部分採用3要素合計で2〜3日。完全移行（5〜7日）の半分以下
4. **段階的に検証可能**: 各要素が独立しているため、1つずつ導入・検証できる

### 4.3 リスク

| リスク | 影響度 | 対策 |
|--------|--------|------|
| nudge escalation Phase3の/clear強制が暴走 | 中 | cooldown（5分制限）の設定値を保守的に。初期は10分に延長 |
| flock導入で足軽のBash呼び出し増加 | 低 | inbox_write.shはBash 1回で完結。現在のEdit直接と同等 |
| 本家の設計がさらに変わる可能性 | 中 | 部分採用なら影響範囲が限定的。本家のコミット監視を継続 |
| inotify-tools未インストール環境でのエラー | 低 | nudge escalationはinotifywait不要（send-keys＋タイマーで実装可能） |

### 4.4 次のアクション

| 順序 | アクション | 前提条件 |
|------|-----------|---------|
| 1 | 本家の安定化を1〜2週間監視 | 2/9以降の根本的設計変更がないことを確認 |
| 2 | 採用候補A（nudge escalation）を実装 | タイマーベースの3段階リトライ。inotifywait不要の方式で |
| 3 | 採用候補B（flock排他）を実装 | inbox_write.sh移植＋足軽報告フロー変更 |
| 4 | 採用候補C（overflow protection）を実装 | inbox_write.sh内 or 独立スクリプトで |
| 5 | 運用検証（1週間） | 3要素が安定動作することを確認 |
| 6 | 完全移行の再判断 | 本家の安定化＋部分採用の実績を踏まえて判断 |

---

**報告者**: 部屋子1（heyago1）
**作成完了日時**: 2026-02-09
