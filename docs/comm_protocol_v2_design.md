# 通信プロトコル v2 全体設計書

> **Version**: 1.0
> **Author**: ashigaru5 (Opus Thinking)
> **Parent CMD**: cmd_127
> **Date**: 2026-02-08
> **Status**: Draft — 家老レビュー後にお針子監査

---

## 1. 設計意図・背景

### 1.1 現行方式の問題点

現行の通信プロトコルは **DB CLI 中心方式** である。全てのタスク割当・ステータス更新・報告が `python3 scripts/botsunichiroku.py` CLI を経由する。

```
【現行方式】
家老 → python3 scripts/botsunichiroku.py subtask add ... → DB書き込み → CLI出力
足軽 → python3 scripts/botsunichiroku.py subtask show ... → DB読み取り → CLI出力
足軽 → python3 scripts/botsunichiroku.py subtask update ... → DB書き込み → CLI出力
足軽 → python3 scripts/botsunichiroku.py report add ... → DB書き込み → CLI出力
家老 → python3 scripts/botsunichiroku.py report list → DB読み取り → CLI出力
```

**問題1: トークンコスト**

| 操作 | 推定トークン消費 | 発生頻度/タスク |
|------|----------------|----------------|
| `subtask add`（家老） | ~200 tok（コマンド+出力） | 1回 |
| `subtask show`（足軽） | ~300 tok（コマンド+出力） | 1回 |
| `subtask update --status in_progress`（足軽） | ~150 tok | 1回 |
| `subtask update --status done`（足軽） | ~150 tok | 1回 |
| `report add`（足軽） | ~250 tok（コマンド+長文引数） | 1回 |
| `report list`（家老） | ~400 tok（全報告スキャン） | 1回 |
| **合計** | **~1,450 tok/タスク** | — |

1日50タスク処理の場合、通信だけで **~72,500トークン** を消費する（`subtask show` や `report list` を複数回実行する場合はさらに増加）。

**問題2: Bashツール呼び出しオーバーヘッド**

各CLI操作はBashツール呼び出しを要する。Claude Codeのツール呼び出し1回は、単純なRead/Edit操作に比べて起動コストが大きい。特に足軽の `/clear` 復帰時に `subtask list` + `subtask show` の2回のCLI呼び出しが必要で、復帰コストが高い。

**問題3: 報告の長文引数問題**

`report add` のサマリをシェル引数で渡す場合、引用符のエスケープ問題が頻発する。YAML直接書き込みなら自然にマルチラインが書ける。

### 1.2 YAML直接操作の利点

| 観点 | DB CLI 方式 | YAML 直接方式 |
|------|------------|-------------|
| トークンコスト | CLI出力が大きい（~150-400 tok/回） | Read/Editは軽量（~50-100 tok/回） |
| ツール呼び出し | Bash（重い） | Read/Edit（軽い） |
| マルチライン | シェル引用符のエスケープ問題 | YAMLで自然に記述可 |
| 復帰コスト | CLI 2回呼び出し（~500 tok） | Read 1回（~200 tok） |
| アトミック性 | SQLite が保証 | flock で保証（inbox_write.sh） |
| 検索・集計 | SQL で柔軟に対応可 | 大量データには不向き |

### 1.3 設計方針

**YAML通信 + DB永続の二層アーキテクチャ** を採用する。

- **リアルタイム通信**: YAML ファイル（高速・低トークン）
- **永続化・集計**: SQLite DB（高信頼性・検索可能）
- **役割分離**: 足軽はYAMLのみ触る。DBへの書き込みは家老のみが行う

---

## 2. 二層アーキテクチャ

### 2.1 概念図

```
┌─────────────────────────────────────────────────────────┐
│                    第1層: YAML通信層                      │
│              （リアルタイム・低トークン）                   │
│                                                          │
│  queue/inbox/{agent}.yaml     ← 起動シグナル（inbox方式） │
│  queue/tasks/ashigaru{N}.yaml ← タスク割当内容            │
│  queue/reports/ashigaru{N}_report.yaml ← 報告内容         │
│                                                          │
│  ┌──────┐  inbox_write  ┌──────┐  inbox_write  ┌──────┐ │
│  │将軍  │──────────────→│家老  │──────────────→│足軽  │ │
│  └──────┘               └──┬───┘←──────────────└──────┘ │
│                            │         inbox_write         │
│                            │                             │
└────────────────────────────┼─────────────────────────────┘
                             │ 家老がDBに書き込み
                             │ （cmd完了時・アーカイブ時）
┌────────────────────────────┼─────────────────────────────┐
│                    第2層: DB永続層                         │
│              （永続化・集計・監査）                         │
│                            ▼                             │
│           data/botsunichiroku.db (SQLite)                 │
│           ┌──────────────────────────┐                   │
│           │ commands   │ subtasks    │                    │
│           │ reports    │ agents      │                    │
│           └──────────────────────────┘                   │
│                            ▲                             │
│           お針子 ──────────┘ DB閲覧のみ（書き込み不可）     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 2.2 レイヤー責務

| レイヤー | 責務 | 読み書き権限 | データ寿命 |
|---------|------|------------|----------|
| 第1層: YAML通信層 | リアルタイムのタスク割当・報告・起動通知 | 全エージェント（自分のファイルのみ） | 揮発的（/clear後に再読込） |
| 第2層: DB永続層 | 完了タスクの永続化、履歴管理、集計・監査 | **家老=読み書き**、お針子=閲覧のみ、足軽/部屋子=権限なし | 永続（セッション跨ぎ） |

### 2.3 データフロー原則

```
■ タスクライフサイクル

1. 将軍 → queue/shogun_to_karo.yaml に cmd 追記（従来通り）
2. 家老 → queue/tasks/ashigaru{N}.yaml にタスク書き込み（YAML直接）
3. 家老 → queue/inbox/ashigaru{N}.yaml に起動通知（inbox_write.sh）
4. 足軽 → queue/tasks/ashigaru{N}.yaml を Read で確認
5. 足軽 → 作業実行
6. 足軽 → queue/reports/ashigaru{N}_report.yaml に報告書き込み（Edit）
7. 足軽 → queue/inbox/karo.yaml に完了通知（inbox_write.sh）
8. 家老 → 報告YAML読み取り → DB永続化（python3 scripts/botsunichiroku.py）
```

**要点**: 足軽は DB CLI を一切使わない。YAML の Read/Edit のみで完結する。

---

## 3. 通信フロー図

### 3.1 タスク割当フロー（将軍→家老→足軽）

```
将軍                        家老                        足軽N
 │                           │                           │
 │ cmd追記                   │                           │
 │ (shogun_to_karo.yaml)     │                           │
 │ + inbox_write karo        │                           │
 │──────────────────────────→│                           │
 │                           │                           │
 │                           │ Read shogun_to_karo.yaml  │
 │                           │ タスク分解・計画策定       │
 │                           │                           │
 │                           │ Write tasks/ashigaru{N}.yaml
 │                           │ (タスク内容をYAMLで記述)   │
 │                           │──────────────────────────→│
 │                           │                           │
 │                           │ inbox_write ashigaru{N}   │
 │                           │ "タスクYAMLを確認せよ"     │
 │                           │──────────────────────────→│
 │                           │                           │
 │                           │                    inbox受信
 │                           │                    Read tasks/ashigaru{N}.yaml
 │                           │                    作業開始
```

### 3.2 報告フロー（足軽→家老→DB永続化）

```
足軽N                       家老                        DB
 │                           │                           │
 │ 作業完了                  │                           │
 │                           │                           │
 │ Edit reports/ashigaru{N}_report.yaml                  │
 │ (報告をYAMLで記述)        │                           │
 │                           │                           │
 │ inbox_write karo          │                           │
 │ "任務完了、報告確認されよ" │                           │
 │──────────────────────────→│                           │
 │                           │                           │
 │                    inbox受信                          │
 │                    Read reports/*.yaml（全報告スキャン）│
 │                           │                           │
 │                           │ python3 botsunichiroku.py │
 │                           │ report add ... (DB永続化) │
 │                           │──────────────────────────→│
 │                           │                           │
 │                           │ dashboard.md 更新         │
 │                           │                           │
```

### 3.3 /clear復帰フロー（足軽）

```
/clear実行
  │
  ▼ CLAUDE.md 自動読み込み
  │
  ▼ Step 1: tmux display-message → ashigaru{N}
  │
  ▼ Step 2: mcp__memory__read_graph（~700 tok）
  │
  ▼ Step 3: Read queue/tasks/ashigaru{N}.yaml（~200 tok）
  │   → status: assigned → タスク詳細を直接読める（CLI不要）
  │   → status: idle → 次の指示を待つ
  │
  ▼ Step 4: タスクの project フィールドがあれば context/{project}.md を Read
  │
  ▼ 作業開始（合計 ~3,500 tok で復帰。現行比 -1,500 tok）
```

**現行との比較**:

| 項目 | 現行（DB CLI方式） | v2（YAML方式） | 削減 |
|------|-------------------|---------------|------|
| タスク確認 | `subtask list` + `subtask show` (2回Bash) | Read 1回 | -300 tok |
| 復帰総コスト | ~5,000 tok | ~3,500 tok | **-30%** |

### 3.4 コンパクション復帰フロー（足軽）

```
コンパクション発生
  │
  ▼ summaryが残っている
  │
  ▼ Step 1: tmux display-message → ashigaru{N}
  │
  ▼ Step 2: Read instructions/ashigaru.md
  │
  ▼ Step 3: Read queue/tasks/ashigaru{N}.yaml
  │   → 正データ。summaryより信頼性が高い
  │
  ▼ Step 4: 作業再開
```

### 3.5 お針子監査フロー

```
家老                        お針子                      DB
 │                           │                           │
 │ needs_audit=1 のsubtask完了│                          │
 │                           │                           │
 │ subtask update            │                           │
 │ --audit-status pending    │                           │
 │──────────────────────────────────────────────────────→│
 │                           │                           │
 │ [お針子がIDLEの場合のみ]   │                           │
 │ inbox_write ohariko       │                           │
 │ "subtask_XXX の監査を依頼" │                           │
 │──────────────────────────→│                           │
 │                           │                           │
 │                    inbox受信                          │
 │                    subtask show（DB読み取りのみ）      │
 │                           │─ ─ ─ ─読み取り─ ─ ─ ─ ─→│
 │                           │                           │
 │                    成果物ファイルを Read               │
 │                    品質チェック（4観点）                │
 │                           │                           │
 │                    Edit ohariko_audit.yaml（監査報告）  │
 │                    inbox_write karo                    │
 │                    "監査結果: 合格/要修正"              │
 │←──────────────────────────│                           │
 │                           │                           │
 │ Read ohariko_audit.yaml                               │
 │ report add（DB永続化）     │                           │
 │ subtask update             │                           │
 │ --audit-status done        │                           │
 │──────────────────────────────────────────────────────→│
```

**注**: お針子は DB への **書き込みを行わない**（閲覧のみ）。監査結果は `queue/reports/ohariko_audit.yaml` に記録し、inbox_write で家老に通知する。家老が YAML を読み取り DB に永続化する。これにより **DB書き込み権限は家老のみ** の原則を徹底する。

---

## 4. inbox YAML フォーマット定義

### 4.1 inbox ファイル配置

```
queue/inbox/
├── karo.yaml           # 老中（karo-roju）宛
├── midaidokoro.yaml    # 御台所宛
├── ohariko.yaml        # お針子宛
├── ashigaru1.yaml      # 足軽1宛
├── ashigaru2.yaml      # 足軽2宛
├── ...
├── ashigaru5.yaml      # 足軽5宛
├── ashigaru6.yaml      # 部屋子1宛（ashigaru6）
├── ashigaru7.yaml      # 部屋子2宛（ashigaru7）
└── ashigaru8.yaml      # 部屋子3宛（ashigaru8）
```

### 4.2 inbox YAMLスキーマ

```yaml
# queue/inbox/{agent}.yaml
messages:
  - id: msg_20260208_193045_a1b2c3d4   # ユニークID（タイムスタンプ+ランダム）
    from: karo                          # 送信元エージェント
    timestamp: "2026-02-08T19:30:45"    # 送信時刻
    type: task_assigned                 # メッセージ種別（後述）
    content: "タスクYAMLを確認し実行せよ。"  # 本文（短文）
    read: false                         # 既読フラグ
  - id: msg_20260208_193200_e5f6g7h8
    from: ashigaru3
    timestamp: "2026-02-08T19:32:00"
    type: report_received
    content: "足軽3号、任務完了。報告YAML確認されよ。"
    read: true
```

### 4.3 メッセージ種別（type）

| type | 送信元 → 宛先 | 用途 |
|------|-------------|------|
| `cmd_new` | 将軍 → 家老 | 新規cmd通知 |
| `task_assigned` | 家老 → 足軽/部屋子 | タスク割当通知 |
| `report_received` | 足軽/部屋子 → 家老 | 報告完了通知 |
| `audit_request` | 家老 → お針子 | 監査依頼 |
| `audit_result` | お針子 → 家老 | 監査結果報告 |
| `preemptive_assign` | お針子 → 足軽/部屋子 | 先行割当通知 |
| `preemptive_notify` | お針子 → 家老 | 先行割当実施報告 |
| `clear_command` | 家老 → 足軽/部屋子 | /clear 発行（特殊: 直接send-keys） |
| `model_switch` | 家老 → 足軽/部屋子 | /model 切替（特殊: 直接send-keys） |

### 4.4 特殊メッセージ（直接send-keys）

`clear_command` と `model_switch` は inbox ファイルではなく、直接 send-keys で送信する。理由:
- `/clear` はClaude Codeの組み込みコマンドであり、会話入力として送信する必要がある
- `/model` も同様

これらは inbox_watcher.sh の特殊処理（upstream互換）で対処する。

### 4.5 オーバーフロー保護

inbox ファイルの肥大化を防ぐため、50メッセージ超過時に古い既読メッセージを自動削除する（inbox_write.sh 内の処理。upstream互換）。

---

## 5. タスクYAML / 報告YAMLフォーマット定義

### 5.1 タスクYAML（queue/tasks/ashigaru{N}.yaml）

```yaml
# queue/tasks/ashigaru{N}.yaml
# 家老が書き込み、足軽が読み取り
status: assigned          # idle | assigned | in_progress | done | failed | blocked
cmd_id: cmd_127           # 親cmd
subtask_id: subtask_293   # サブタスクID（DB永続化時に使用）
wave: 1                   # 実行ウェーブ
project: shogun           # プロジェクトID
assigned_by: roju         # 割当元家老（roju | ooku）
target_path: /home/yasu/multi-agent-shogun
description: |
  【核心設計書】通信プロトコルv2の全体設計書を作成せよ。
  成果物: docs/comm_protocol_v2_design.md
  ...（詳細な指示）
notes: ""                 # 追加注記（オプション）
needs_audit: true         # 監査要否
model_override: ""        # モデル昇格/降格時のみ（opus | sonnet | 空文字=デフォルト）
progress: {}              # 途中経過（/clear前に足軽が記録）
```

### 5.2 報告YAML（queue/reports/ashigaru{N}_report.yaml）

```yaml
# queue/reports/ashigaru{N}_report.yaml
# 足軽が書き込み、家老が読み取り→DB永続化
cmd_id: cmd_127
subtask_id: subtask_293
worker: ashigaru5
status: done              # done | failed | blocked
timestamp: "2026-02-08T19:45:00"
summary: |
  タスク完了。通信プロトコルv2の全体設計書を作成。
  docs/comm_protocol_v2_design.md に出力済み。
  7章構成で現行方式との比較、フロー図、スキーマ定義を含む。
files_modified:
  - docs/comm_protocol_v2_design.md
skill_candidate:
  name: ""                # スキル化候補（該当なしなら空文字）
  description: ""
```

### 5.3 足軽のステータス遷移

```
idle ──[家老がYAML書き込み]──→ assigned
         ──[足軽がYAML更新]──→ in_progress
         ──[足軽がYAML更新]──→ done / failed / blocked
         ──[家老がDB永続化]──→ idle（次タスク待ち）
```

足軽は自分のタスクYAMLの `status` を Edit で更新する。DB CLI は不要。

---

## 6. DB書き込みタイミング

### 6.1 原則: 家老のみがDBに書く

| タイミング | 家老の操作 | DB操作 |
|-----------|-----------|--------|
| cmd受領時 | shogun_to_karo.yaml 読み取り | `cmd add`（新規cmd登録） |
| タスク割当時 | tasks/ashigaru{N}.yaml 書き込み | `subtask add`（サブタスク登録） |
| 報告受信時 | reports/ashigaru{N}_report.yaml 読み取り | `report add`（報告永続化）+ `subtask update --status done` |
| 監査トリガー時 | needs_audit 確認 | `subtask update --audit-status pending` |
| 監査結果受信時 | お針子のinbox通知 + ohariko_audit.yaml 読み取り | `report add`（監査報告永続化）+ `subtask update --audit-status done`（合格/要修正はfindingsで判別） |
| cmd完了時 | 全subtask完了確認 | `cmd update --status done` |

### 6.2 何がDBから消えるか（消えないか）

| データ | YAML（第1層） | DB（第2層） |
|--------|-------------|-----------|
| タスク割当内容 | 上書きされる（次タスクで） | 永続保存 |
| 報告内容 | 上書きされる（次報告で） | 永続保存 |
| ステータス遷移履歴 | 最新のみ | 全履歴保存 |
| inbox メッセージ | 50件でローテーション | 保存しない |

### 6.3 DB書き込みの簡略化

現行では足軽が直接DB CLIを叩いていたが、v2では家老が一括永続化する。足軽1タスクあたりの家老のDB操作:

```bash
# 報告受信時に一括永続化（家老の操作）
python3 scripts/botsunichiroku.py report add $SUBTASK_ID $WORKER \
  --status done --summary "$(cat queue/reports/ashigaru${N}_report.yaml | ...)"
python3 scripts/botsunichiroku.py subtask update $SUBTASK_ID --status done
```

家老にDB操作を集約することで:
- 足軽のトークンコスト削減
- DB書き込みの一元管理（整合性向上）
- 足軽の /clear 復帰が高速化

---

## 7. お針子との連携

### 7.1 方針: お針子はDB閲覧のみ（書き込み廃止）

お針子の DB 書き込みを廃止し、**DB書き込み権限は家老のみ** の原則を徹底する。

**設計変更**:
- お針子は DB を **閲覧のみ** で使用する（`subtask show`, `subtask list`, `cmd list` 等の読み取り系コマンド）
- 監査結果は YAML（`queue/reports/ohariko_audit.yaml`）に記録し、inbox_write で家老に通知
- 家老が YAML を読み取り、DB への永続化（`report add`, `subtask update --audit-status`）を一括実行

**理由**:
1. **権限の単純化**: DB書き込み権限を家老に集約することで、データ整合性の責任が明確になる
2. **足軽と同じ設計パターン**: 足軽もYAML報告→家老がDB永続化の流れ。お針子も同じパターンに統一
3. **お針子の本質**: 監査の本質は「読んで判断する」こと。DB書き込みは副次的操作であり家老に委譲可能

### 7.2 お針子の通信経路（v2での変更点）

| 通信 | 現行方式 | v2方式 | 変更理由 |
|------|---------|--------|---------|
| 家老→お針子（監査依頼） | send-keys | **inbox_write** | 統一的なinbox方式に |
| お針子→家老（監査結果） | send-keys | **inbox_write + 監査報告YAML** | inbox方式 + YAML報告 |
| お針子→足軽（先行割当） | send-keys | **inbox_write** | 統一的なinbox方式に |
| お針子のDB読み取り | DB CLI | DB CLI（変更なし） | 監査に必須 |
| お針子のDB書き込み | DB CLI | **廃止** | 家老に集約（権限単純化） |

### 7.3 DB権限マトリクス（3段階）

殿の最終裁定に基づく v2 のDB権限体系。3段階に明確に分離する。

| 操作 | 家老 | お針子 | 足軽/部屋子 |
|------|------|--------|------------|
| DB読み取り（`subtask show/list`, `cmd show/list`, `report list`） | **可** | **可** | **不可** |
| DB書き込み（`subtask add/update`, `report add`, `cmd add/update`） | **可** | **不可** | **不可** |
| 成果物ファイルの Read | **可** | **可** | **可** |
| YAML Read/Edit（タスク・報告） | **可** | 監査YAML のみ | **可（自分のファイルのみ）** |
| inbox_write（通知） | **可** | **可** | **可** |

**原則**:
- **家老** = DB唯一の書き込み権限者。全データの永続化責任を負う
- **お針子** = DB閲覧のみ（監査に過去ログ参照が必要なため）。書き込みはYAML経由で家老に委譲
- **足軽/部屋子** = DB権限なし。YAML通信層（第1層）のみで完結

### 7.4 監査報告YAML（queue/reports/ohariko_audit.yaml）

```yaml
# queue/reports/ohariko_audit.yaml
# お針子が書き込み、家老が読み取り→DB永続化
subtask_id: subtask_293
result: pass              # pass | fail
summary: "4観点クリア。品質は及第点よ。"
findings:
  - "軽微: Section 3のインデントが不統一"
timestamp: "2026-02-08T20:30:00"
```

### 7.5 監査フロー（v2）

```
1. 家老: subtask update --audit-status pending（DB操作）
2. 家老: inbox_write ohariko "subtask_XXXの監査依頼" audit_request karo
   ↓ inbox_watcher.sh がお針子を起こす
3. お針子: Read queue/inbox/ohariko.yaml → 監査依頼を確認
4. お針子: subtask show（DB読み取りのみ）→ 成果物ファイルを Read
5. お針子: 品質チェック（4観点）
6. お針子: Edit queue/reports/ohariko_audit.yaml（監査結果をYAMLに記録）
7. お針子: inbox_write karo "監査結果: 合格/要修正" audit_result ohariko
   ↓ inbox_watcher.sh が家老を起こす
8. 家老: Read queue/inbox/karo.yaml → 監査通知を確認
9. 家老: Read queue/reports/ohariko_audit.yaml → 監査詳細を確認
10. 家老: report add（監査報告をDB永続化）+ subtask update --audit-status done
```

---

## 8. 本家（yohey-w）inbox方式との互換性メモ

### 8.1 本家の方式概要

本家（yohey-w/multi-agent-shogun v3.0）の通信プロトコル:

| 要素 | 本家の方式 |
|------|-----------|
| 起動通知 | `inbox_write.sh` → `inbox_watcher.sh`（inotifywait） |
| タスク割当 | `queue/tasks/ashigaru{N}.yaml`（YAML直接） |
| 報告 | `queue/reports/ashigaru{N}_report.yaml`（YAML直接） |
| 永続化 | なし（YAML が正データ） |
| 監査 | なし（お針子なし） |
| DB | なし |

### 8.2 我々のv2との差分

| 要素 | 本家 v3.0 | 我々の v2 | 差分理由 |
|------|----------|----------|---------|
| inbox方式 | **共通** | **共通** | 互換 |
| タスクYAML | **共通** | **共通** | 互換 |
| 報告YAML | **共通** | **共通** | 互換 |
| DB永続化 | なし | **あり（没日録）** | 監査・履歴・集計が必要 |
| お針子 | なし | **あり** | 品質保証のため |
| 2-karo体制 | 1-karo | **2-karo（老中+御台所）** | 内部/外部分離 |
| 部屋子 | なし | **あり** | 御台所配下の調査部隊 |
| inbox agent名 | karo, ashigaru1-8 | karo, midaidokoro, ohariko, ashigaru1-8 | agent追加 |

### 8.3 互換性の維持方針

```
         本家 (yohey-w)              我々 (private fork)
         ┌─────────────┐            ┌──────────────────┐
共通層   │ inbox_write  │ ←──互換──→ │ inbox_write      │
         │ task YAML    │            │ task YAML        │
         │ report YAML  │            │ report YAML      │
         └─────────────┘            └──────────────────┘
                                     ┌──────────────────┐
独自層                               │ 没日録DB（永続化）│
(本家にはない)                       │ お針子（監査）    │
                                     │ 2-karo体制       │
                                     │ 部屋子           │
                                     └──────────────────┘
```

**共通層は互換を維持する**。これにより:
- 本家の inbox_write.sh / inbox_watcher.sh をそのまま流用可能
- 将来、本家に貢献したい機能だけ切り出してPRを出せる
- 本家の更新を共通層に追従するコストが低い

**独自層は我々のみ**。没日録DB・お針子・2-karo・部屋子は本家にはない機能であり、互換性を気にする必要がない。

### 8.4 inbox_write.sh の移植

本家の `scripts/inbox_write.sh` をほぼそのまま使用可能。変更点:

| 項目 | 本家 | 我々（変更点） |
|------|------|-------------|
| ターゲットagent名 | karo, ashigaru1-8 | + midaidokoro, ohariko, ashigaru6-8 |
| flock | あり | あり（変更なし） |
| オーバーフロー保護 | 50件 | 50件（変更なし） |
| inotifywait | あり | あり（変更なし） |

inbox_watcher.sh の起動対象にお針子・御台所を追加するのみ。

---

## 9. 移行計画

### 9.1 段階的移行（Big Bang禁止）

| フェーズ | 内容 | 影響範囲 |
|---------|------|---------|
| Phase 1 | inbox_write.sh 導入 + inbox_watcher.sh 起動 | send-keys → inbox_write に置換 |
| Phase 2 | 足軽のDB CLI操作を廃止 → YAML Read/Edit に移行 | instructions/ashigaru.md 改修 |
| Phase 3 | 家老のDB永続化フローを追加 | instructions/karo.md 改修 |
| Phase 4 | CLAUDE.md の通信プロトコルセクション更新 | CLAUDE.md 改修 |
| Phase 5 | お針子の通知手段をinbox_writeに統一 | instructions/ohariko.md 改修 |
| Phase 6 | 回帰テスト（/clear復帰、コンパクション復帰、全通信パターン） | 全エージェント |

### 9.2 後方互換

移行中は **YAML方式とDB CLI方式の両方が動作する** 状態を維持する。足軽がDB CLIを使っても正常に動作し、YAML Read/Editを使っても動作する。全足軽が移行完了してからDB CLI依存を削除する。

---

## 10. 期待される効果

### 10.1 トークンコスト削減（1タスクあたり）

| 操作 | 現行（DB CLI） | v2（YAML+DB） | 削減 |
|------|--------------|-------------|------|
| subtask add（家老、CLI→CLI） | ~200 tok | ~200 tok（変更なし） | 0 |
| タスクYAML書き込み（家老、v2新規） | — | ~100 tok（Write） | +100 |
| タスク確認（足軽） | ~300 tok（CLI） | ~100 tok（Read） | -200 |
| ステータス更新 ×2（足軽） | ~300 tok（CLI） | ~100 tok（Edit） | -200 |
| 報告作成（足軽） | ~250 tok（CLI） | ~100 tok（Edit） | -150 |
| 報告スキャン（家老） | ~400 tok（CLI） | ~100 tok（Read） | -300 |
| DB永続化（家老、v2新規） | — | ~350 tok（report add + subtask update） | +350 |
| **1タスクあたり合計** | **~1,450 tok** | **~1,050 tok** | **-400 tok（-28%）** |

**内訳**: 足軽のCLI操作廃止で -550 tok、家老の報告スキャン軽量化で -300 tok（計 -850 tok）。代わりに家老がYAML書き込み+DB永続化を引き受け +450 tok。差し引き **-400 tok/タスク**。足軽の負荷は **-65%**（850→300 tok）と大幅に軽減される。

1日50タスク × 削減400 tok = **1日あたり約20,000トークン削減**。

**補足: /clear復帰コスト**（タスクごとではなく /clear 発行時のみ発生）

| 項目 | 現行 | v2 | 削減 |
|------|------|-----|------|
| タスク確認（`subtask list` + `subtask show`） | ~500 tok | ~200 tok（Read 1回） | -300 tok |

### 10.2 その他の効果

| 効果 | 説明 |
|------|------|
| /clear復帰の高速化 | CLI 2回→Read 1回で -30% |
| 報告の品質向上 | YAML直接記述でマルチライン自然記述 |
| 通信の信頼性向上 | inbox_watcher.sh のinotifywait + ファイル永続 |
| 本家との互換性 | 共通層のinbox方式が一致 |
| 役割の明確化 | 3段階DB権限: 家老=読み書き、お針子=閲覧のみ、足軽/部屋子=権限なし（YAML専用） |

---

## 付録A: ファイル構成（v2完成後）

```
queue/
├── shogun_to_karo.yaml         # 将軍→家老 cmd（従来通り）
├── inbox/                       # 【新規】inbox方式
│   ├── karo.yaml               # 老中宛
│   ├── midaidokoro.yaml        # 御台所宛
│   ├── ohariko.yaml            # お針子宛
│   ├── ashigaru1.yaml          # 足軽1宛
│   ├── ...
│   └── ashigaru8.yaml          # 部屋子3宛
├── tasks/                       # タスク割当（従来通り、YAML直接R/W）
│   ├── ashigaru1.yaml
│   ├── ...
│   └── ashigaru8.yaml
├── reports/                     # 報告（従来通り、YAML直接R/W）
│   ├── ashigaru1_report.yaml
│   ├── ...
│   ├── ashigaru8_report.yaml
│   └── ohariko_audit.yaml      # 【新規】お針子の監査報告
├── skill_candidates.yaml        # スキル化候補
└── archive/                     # アーカイブ済み
scripts/
├── inbox_write.sh               # 【新規】inbox書き込み（本家から移植）
├── inbox_watcher.sh             # 【新規】inbox監視（本家から移植）
└── botsunichiroku.py            # 没日録CLI（家老=読み書き、お針子=読み取りのみ）
data/
└── botsunichiroku.db            # 没日録（永続化・監査用）
```

## 付録B: 用語集

| 用語 | 説明 |
|------|------|
| 第1層（YAML通信層） | リアルタイム通信に使うYAMLファイル群 |
| 第2層（DB永続層） | 永続化・集計・監査に使うSQLite DB |
| inbox | エージェントごとの受信ボックス（YAML） |
| inbox_write.sh | flockによるアトミックなinbox書き込みスクリプト |
| inbox_watcher.sh | inotifywaitによるファイル変更監視+nudge送信スクリプト |
| nudge | inbox_watcherが送る短い起動シグナル（"inbox3" 等） |
| 没日録 | botsunichiroku.db。永続化されたタスク・報告のDB |
