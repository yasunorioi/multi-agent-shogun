# 足軽 Instructions 改修案：DB CLI → YAML Inbox 方式への移行

> **作成日**: 2026-02-08
> **作成者**: ashigaru1
> **目的**: 足軽がDB CLIを使わず、YAMLファイル操作のみで全業務を完結できるようにする

---

## 1. 現行 instructions/ashigaru.md の DB CLI 参照箇所一覧

### 1.1 ワークフローセクション（行40-71）

#### 箇所1: タスク確認（行40）
```yaml
- step: 2
  action: check_tasks
  target: "python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned"
  note: "没日録DBから自分のタスク確認"
```

#### 箇所2: ステータス更新（in_progress）（行43-45）
```yaml
- step: 3
  action: update_status
  target: "python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --status in_progress"
  value: in_progress
```

#### 箇所3: 報告記録（行49-51）
```yaml
- step: 5
  action: write_report
  target: "python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} --status done --summary '報告内容'"
  note: "没日録DBに報告を記録"
```

#### 箇所4: ステータス更新（done）（行53-55）
```yaml
- step: 6
  action: update_status
  target: "python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --status done"
  value: done
```

#### 箇所5: DB CLIコマンド一覧（行68-71）
```yaml
db_commands:
  list_tasks: "python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned"
  show_task: "python3 scripts/botsunichiroku.py subtask show SUBTASK_ID"
  add_report: "python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} --status done --summary '...'"
```

### 1.2 自分のタスク確認セクション（行175-197）

#### 箇所6: タスク確認方法（行186-191）
```bash
# 自分に割り当てられたタスクを確認
python3 scripts/botsunichiroku.py subtask list --worker ashigaru{自分の番号} --status assigned

# タスクの詳細を確認
python3 scripts/botsunichiroku.py subtask show SUBTASK_ID
```

### 1.3 報告の書き方セクション（行295-334）

#### 箇所7: 基本報告形式（行301-305）
```bash
python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} \
  --status done \
  --summary "タスク完了。WBS 2.3節を作成。担当者3名、期間を2/1-2/15に設定。"
```

#### 箇所8: スキル化候補付き報告（行309-314）
```bash
python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} \
  --status done \
  --summary "タスク完了。README改善を実施。初心者向けセットアップガイドを追加。" \
  --skill-name "readme-improver" \
  --skill-desc "README.mdを初心者向けに改善するパターン。他プロジェクトでも有用。"
```

### 1.4 コンパクション復帰手順（行384-404）

#### 箇所9: 正データ確認（行389-393）
```markdown
1. **没日録DB（自分のタスク）** — subtask list で確認
   - {N} は自分の番号（`tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'` で確認。出力の数字部分が番号）
   - status が assigned なら未完了。subtask show で詳細確認して作業を再開せよ
   - status が done または該当なしなら完了済み。次の指示を待て
```

#### 箇所10: 復帰後の行動（行402-404）
```markdown
2. タスク確認: `python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned`
3. status: assigned なら、`subtask show SUBTASK_ID` で詳細確認し、作業を再開
```

### 1.5 /clear後の復帰手順（行406-467）

#### 箇所11: /clear前にやるべきこと（行426-431）
```bash
2. **タスクが途中であれば**: subtask update で progress フィールドに途中状態を記録
   python3 scripts/botsunichiroku.py subtask update SUBTASK_ID \
     --progress '{"completed": ["file1.ts", "file2.ts"], "remaining": ["file3.ts"], "approach": "共通インターフェース抽出後にリファクタリング"}'
```

### 1.6 コンテキスト読み込み手順（行490-500）

#### 箇所12: タスク確認手順（行495-497）
```markdown
4. **subtask list --worker ashigaru{N} --status assigned で自分の指示確認**
5. **subtask show SUBTASK_ID で詳細確認**
```

### 1.7 自律判断ルール（行522-537）

#### 箇所13: 異常時の自己判断（行536-537）
```markdown
- 自身のコンテキストが30%を切ったら → 現在のタスクの進捗を subtask update で記録し、家老に「コンテキスト残量少」と報告
```

---

## 2. CLAUDE.md の DB CLI 参照箇所一覧

### 2.1 /clear後の復帰フロー（行57-101）

#### 箇所14: タスク確認（行84-88）
```markdown
▼ Step 3: 自分の割当タスク確認（~800トークン）
│   python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned
│   → 割当があれば: python3 scripts/botsunichiroku.py subtask show SUBTASK_ID で詳細確認
│   → 割当なしなら: 次の指示を待つ
│   → assigned_by フィールドで報告先家老を確認（roju=multiagent:agents.0, ooku=ooku:agents.0）
```

### 2.2 将軍の必須行動（行310-355）

#### 箇所15: 報告の確認（行327-329）
```markdown
### 3. 報告の確認
- 足軽の報告は没日録DBで管理: `python3 scripts/botsunichiroku.py report list --worker ashigaru{N}`
- 家老からの報告待ちの際はこれを確認
```

---

## 3. YAML Inbox 方式への書き換え案（Before/After）

### 3.1 基本設計

#### 新しいファイル構成
```
queue/inbox/
  ├── ashigaru1.yaml      # 足軽1のタスク inbox
  ├── ashigaru2.yaml      # 足軽2のタスク inbox
  ├── ...
  ├── ashigaru8.yaml      # 部屋子3のタスク inbox
  ├── roju_reports.yaml   # 老中への報告 inbox
  └── ooku_reports.yaml   # 御台所への報告 inbox
```

#### Inbox YAMLフォーマット（タスク）
```yaml
# queue/inbox/ashigaru1.yaml
tasks:
  - id: subtask_294
    cmd_id: cmd_127
    status: assigned  # assigned | in_progress | done | blocked | failed
    project: shogun
    target_path: /home/yasu/multi-agent-shogun
    description: |
      【足軽instructions改修案】現行 instructions/ashigaru.md を精読し、
      DB CLI参照箇所を全て特定。YAML inbox方式への書き換え案を作成せよ。
    notes: ""
    needs_audit: true
    assigned_by: roju  # roju | ooku
    assigned_at: "2026-02-08T10:59:37"
    completed_at: null
    progress: {}  # 途中状態の記録（/clear前に使用）
```

#### Inbox YAMLフォーマット（報告）
```yaml
# queue/inbox/roju_reports.yaml
reports:
  - id: report_001
    subtask_id: subtask_294
    worker: ashigaru1
    status: done  # done | failed | blocked
    timestamp: "2026-02-08T11:30:00"
    summary: |
      タスク完了。docs/ashigaru_instructions_changes.md を作成。
      DB CLI参照箇所15箇所を特定し、YAML方式への書き換え案を提示。
    skill_candidate:
      name: "instructions-refactorer"
      description: "instructionsファイルの特定パターンを一括書き換え"
    read: false  # 家老が読んだかフラグ
```

### 3.2 各箇所の書き換え案

#### 書き換え1: タスク確認（ワークフロー）

**Before**:
```yaml
- step: 2
  action: check_tasks
  target: "python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned"
  note: "没日録DBから自分のタスク確認"
```

**After**:
```yaml
- step: 2
  action: check_tasks
  target: "Read queue/inbox/ashigaru{N}.yaml"
  note: "自分のinboxからタスク確認（status: assigned を探す）"
```

---

#### 書き換え2: ステータス更新（in_progress）

**Before**:
```yaml
- step: 3
  action: update_status
  target: "python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --status in_progress"
  value: in_progress
```

**After**:
```yaml
- step: 3
  action: update_status
  target: "Edit queue/inbox/ashigaru{N}.yaml"
  value: in_progress
  note: "該当タスクの status フィールドを assigned → in_progress に変更"
```

---

#### 書き換え3: 報告記録

**Before**:
```yaml
- step: 5
  action: write_report
  target: "python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} --status done --summary '報告内容'"
  note: "没日録DBに報告を記録"
```

**After**:
```yaml
- step: 5
  action: write_report
  target: "Edit queue/inbox/{karo}_reports.yaml"
  note: "家老の報告inboxに新規報告を追記（assigned_by で報告先を判定：roju → roju_reports.yaml, ooku → ooku_reports.yaml）"
```

---

#### 書き換え4: ステータス更新（done）

**Before**:
```yaml
- step: 6
  action: update_status
  target: "python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --status done"
  value: done
```

**After**:
```yaml
- step: 6
  action: update_status
  target: "Edit queue/inbox/ashigaru{N}.yaml"
  value: done
  note: "該当タスクの status フィールドを in_progress → done に変更"
```

---

#### 書き換え5: DB CLIコマンド一覧セクションの削除

**Before**:
```yaml
# DB CLI
db_commands:
  list_tasks: "python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned"
  show_task: "python3 scripts/botsunichiroku.py subtask show SUBTASK_ID"
  add_report: "python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} --status done --summary '...'"
```

**After**:
```yaml
# Inbox YAML操作
inbox_operations:
  read_tasks: "Read queue/inbox/ashigaru{N}.yaml"
  update_status: "Edit queue/inbox/ashigaru{N}.yaml（該当タスクのstatusフィールド変更）"
  write_report: "Edit queue/inbox/{karo}_reports.yaml（新規報告を追記）"
  note: "assigned_by フィールドで報告先を判定（roju=roju_reports.yaml, ooku=ooku_reports.yaml）"
```

---

#### 書き換え6: タスク確認方法（自分のタスク確認セクション）

**Before**:
```bash
# 自分に割り当てられたタスクを確認
python3 scripts/botsunichiroku.py subtask list --worker ashigaru{自分の番号} --status assigned

# タスクの詳細を確認
python3 scripts/botsunichiroku.py subtask show SUBTASK_ID
```

**After**:
```bash
# 自分に割り当てられたタスクを確認
Read queue/inbox/ashigaru{自分の番号}.yaml
# → tasks リストの中から status: assigned を探す

# タスクの詳細はすべて同じYAMLに記載されている
# description, notes, target_path, project 等をそのまま参照
```

---

#### 書き換え7-8: 報告の書き方セクション

**Before（基本形式）**:
```bash
python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} \
  --status done \
  --summary "タスク完了。WBS 2.3節を作成。担当者3名、期間を2/1-2/15に設定。"
```

**After（基本形式）**:
```bash
# 1. 自分のinboxで該当タスクの assigned_by を確認
Read queue/inbox/ashigaru{N}.yaml
# → assigned_by: roju なら roju_reports.yaml, ooku なら ooku_reports.yaml

# 2. 家老の報告inboxに新規報告を追記
Edit queue/inbox/roju_reports.yaml
# 以下の形式で reports リストの末尾に追加:
# - id: report_XXX  # 既存のreport IDから連番を推測
#   subtask_id: SUBTASK_ID
#   worker: ashigaru{N}
#   status: done
#   timestamp: "YYYY-MM-DDTHH:MM:SS"  # date "+%Y-%m-%dT%H:%M:%S" で取得
#   summary: |
#     タスク完了。WBS 2.3節を作成。担当者3名、期間を2/1-2/15に設定。
#   skill_candidate: null
#   read: false
```

**Before（スキル化候補付き）**:
```bash
python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} \
  --status done \
  --summary "タスク完了。README改善を実施。初心者向けセットアップガイドを追加。" \
  --skill-name "readme-improver" \
  --skill-desc "README.mdを初心者向けに改善するパターン。他プロジェクトでも有用。"
```

**After（スキル化候補付き）**:
```bash
Edit queue/inbox/roju_reports.yaml
# skill_candidate フィールドに記載:
# - id: report_XXX
#   subtask_id: SUBTASK_ID
#   worker: ashigaru{N}
#   status: done
#   timestamp: "2026-02-08T11:30:00"
#   summary: |
#     タスク完了。README改善を実施。初心者向けセットアップガイドを追加。
#   skill_candidate:
#     name: "readme-improver"
#     description: "README.mdを初心者向けに改善するパターン。他プロジェクトでも有用。"
#   read: false
```

---

#### 書き換え9-10: コンパクション復帰手順

**Before**:
```markdown
1. **没日録DB（自分のタスク）** — subtask list で確認
   - {N} は自分の番号（`tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'` で確認。出力の数字部分が番号）
   - status が assigned なら未完了。subtask show で詳細確認して作業を再開せよ
   - status が done または該当なしなら完了済み。次の指示を待て

（中略）

2. タスク確認: `python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned`
3. status: assigned なら、`subtask show SUBTASK_ID` で詳細確認し、作業を再開
```

**After**:
```markdown
1. **Inbox YAML（自分のタスク）** — Read queue/inbox/ashigaru{N}.yaml
   - {N} は自分の番号（`tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'` で確認。出力の数字部分が番号）
   - tasks リストの中から status: assigned を探す
   - 該当があれば作業を再開、なければ次の指示を待つ

（中略）

2. タスク確認: `Read queue/inbox/ashigaru{N}.yaml`
3. status: assigned のタスクがあれば、同じYAML内の description, notes, target_path を確認して作業を再開
```

---

#### 書き換え11: /clear前にやるべきこと

**Before**:
```bash
2. **タスクが途中であれば**: subtask update で progress フィールドに途中状態を記録
   python3 scripts/botsunichiroku.py subtask update SUBTASK_ID \
     --progress '{"completed": ["file1.ts", "file2.ts"], "remaining": ["file3.ts"], "approach": "共通インターフェース抽出後にリファクタリング"}'
```

**After**:
```bash
2. **タスクが途中であれば**: Edit queue/inbox/ashigaru{N}.yaml で progress フィールドに途中状態を記録
   # 該当タスクの progress フィールドを更新:
   progress:
     completed:
       - file1.ts
       - file2.ts
     remaining:
       - file3.ts
     approach: "共通インターフェース抽出後にリファクタリング"
```

---

#### 書き換え12: コンテキスト読み込み手順

**Before**:
```markdown
4. **subtask list --worker ashigaru{N} --status assigned で自分の指示確認**
5. **subtask show SUBTASK_ID で詳細確認**
```

**After**:
```markdown
4. **Read queue/inbox/ashigaru{N}.yaml で自分の指示確認**（status: assigned のタスクを探す）
5. **同じYAML内の description, notes, target_path, project を確認**（全ての情報が1ファイルに集約）
```

---

#### 書き換え13: 自律判断ルール

**Before**:
```markdown
- 自身のコンテキストが30%を切ったら → 現在のタスクの進捗を subtask update で記録し、家老に「コンテキスト残量少」と報告
```

**After**:
```markdown
- 自身のコンテキストが30%を切ったら → Edit queue/inbox/ashigaru{N}.yaml で progress フィールドに進捗を記録し、家老に「コンテキスト残量少」と報告
```

---

## 4. /clear復帰フローの改修案（CLAUDE.md）

### 4.1 現行フロー（DB CLI版）

```
/clear実行
  │
  ▼ CLAUDE.md 自動読み込み（本セクションを認識）
  │
  ▼ Step 1: 自分のIDを確認
  │   tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'
  │   → 出力例: ashigaru3 → 自分は足軽3（数字部分が番号）
  │
  ▼ Step 2: Memory MCP 読み込み（~700トークン）
  │   ToolSearch("select:mcp__memory__read_graph")
  │   mcp__memory__read_graph()
  │   → 殿の好み・ルール・教訓を復元
  │   ※ 失敗時もStep 3以降を続行せよ（タスク実行は可能。殿の好みは一時的に不明になるのみ）
  │
  ▼ Step 3: 自分の割当タスク確認（~800トークン）
  │   python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned
  │   → 割当があれば: python3 scripts/botsunichiroku.py subtask show SUBTASK_ID で詳細確認
  │   → 割当なしなら: 次の指示を待つ
  │   → assigned_by フィールドで報告先家老を確認（roju=multiagent:agents.0, ooku=ooku:agents.0）
  │
  ▼ Step 4: プロジェクト固有コンテキストの読み込み（条件必須）
  │   タスクYAMLに project フィールドがある場合 → context/{project}.md を必ず読む
  │   タスクYAMLに target_path がある場合 → 対象ファイルを読む
  │   ※ projectフィールドがなければスキップ可
  │
  ▼ 作業開始
```

### 4.2 改修後フロー（YAML Inbox版）

```
/clear実行
  │
  ▼ CLAUDE.md 自動読み込み（本セクションを認識）
  │
  ▼ Step 1: 自分のIDを確認
  │   tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'
  │   → 出力例: ashigaru3 → 自分は足軽3（数字部分が番号）
  │
  ▼ Step 2: Memory MCP 読み込み（~700トークン）
  │   ToolSearch("select:mcp__memory__read_graph")
  │   mcp__memory__read_graph()
  │   → 殿の好み・ルール・教訓を復元
  │   ※ 失敗時もStep 3以降を続行せよ（タスク実行は可能。殿の好みは一時的に不明になるのみ）
  │
  ▼ Step 3: 自分の割当タスク確認（~800トークン）
  │   Read queue/inbox/ashigaru{N}.yaml
  │   → tasks リストの中から status: assigned を探す
  │   → 割当があれば: 同じYAML内の description, notes, target_path, project, assigned_by を確認
  │   → 割当なしなら: 次の指示を待つ
  │   → assigned_by フィールドで報告先家老を確認（roju=roju_reports.yaml, ooku=ooku_reports.yaml）
  │
  ▼ Step 4: プロジェクト固有コンテキストの読み込み（条件必須）
  │   タスクYAMLに project フィールドがある場合 → context/{project}.md を必ず読む
  │   タスクYAMLに target_path がある場合 → 対象ファイルを読む
  │   ※ projectフィールドがなければスキップ可
  │
  ▼ 作業開始
```

### 4.3 変更点サマリ

| 項目 | DB CLI版 | YAML Inbox版 |
|------|---------|-------------|
| タスク確認 | `python3 scripts/botsunichiroku.py subtask list ...` | `Read queue/inbox/ashigaru{N}.yaml` |
| タスク詳細 | `python3 scripts/botsunichiroku.py subtask show SUBTASK_ID` | 同じYAML内に全情報あり（追加読み込み不要） |
| 報告先判定 | DB CLIの出力から assigned_by を読む | YAML内の assigned_by を読む |
| トークン消費 | ~800トークン（CLI実行+出力） | ~600トークン（YAMLファイル1つ） |

---

## 5. 報告フロー改修案

### 5.1 現行報告フロー（DB CLI版）

```
タスク完了
  │
  ▼ Step 1: 報告をDBに記録
  │   python3 scripts/botsunichiroku.py report add SUBTASK_ID ashigaru{N} \
  │     --status done --summary "..." [--skill-name "..." --skill-desc "..."]
  │
  ▼ Step 2: 報告先家老の状態確認
  │   tmux capture-pane -t multiagent:agents.0 -p | tail -5
  │   → idle なら Step 4, busy なら Step 3
  │
  ▼ Step 3: busy の場合リトライ（最大3回）
  │   sleep 10 → Step 2 に戻る
  │
  ▼ Step 4: send-keys 送信（2回に分ける）
  │   【1回目】tmux send-keys -t multiagent:agents.0 'ashigaru{N}、任務完了でござる。報告書を確認されよ。'
  │   【2回目】tmux send-keys -t multiagent:agents.0 Enter
  │
  ▼ Step 5: 到達確認（必須）
  │   sleep 5
  │   tmux capture-pane -t multiagent:agents.0 -p | tail -5
  │   → 家老が thinking / working 状態なら到達OK
  │   → プロンプト待ち（❯）のままなら再送（最大2回）
```

### 5.2 改修後報告フロー（YAML Inbox版）

```
タスク完了
  │
  ▼ Step 1: 自分のinboxで該当タスクの assigned_by を確認
  │   Read queue/inbox/ashigaru{N}.yaml
  │   → assigned_by: roju なら roju_reports.yaml
  │   → assigned_by: ooku なら ooku_reports.yaml
  │
  ▼ Step 2: 家老の報告inboxに新規報告を追記
  │   Edit queue/inbox/{karo}_reports.yaml
  │   → reports リストの末尾に新規報告を追加
  │   → id は既存報告から連番を推測（report_001, report_002, ...）
  │   → timestamp は `date "+%Y-%m-%dT%H:%M:%S"` で取得
  │   → skill_candidate はあれば記載、なければ null
  │   → read: false で初期化
  │
  ▼ Step 3: 自分のinboxでタスクステータスを done に更新
  │   Edit queue/inbox/ashigaru{N}.yaml
  │   → 該当タスクの status: in_progress → done
  │   → completed_at: "YYYY-MM-DDTHH:MM:SS" を記録
  │
  ▼ Step 4: 報告先家老の状態確認
  │   tmux capture-pane -t multiagent:agents.0 -p | tail -5
  │   → idle なら Step 6, busy なら Step 5
  │
  ▼ Step 5: busy の場合リトライ（最大3回）
  │   sleep 10 → Step 4 に戻る
  │
  ▼ Step 6: send-keys 送信（2回に分ける）
  │   【1回目】tmux send-keys -t multiagent:agents.0 'ashigaru{N}、任務完了でござる。報告書を確認されよ。'
  │   【2回目】tmux send-keys -t multiagent:agents.0 Enter
  │
  ▼ Step 7: 到達確認（必須）
  │   sleep 5
  │   tmux capture-pane -t multiagent:agents.0 -p | tail -5
  │   → 家老が thinking / working 状態なら到達OK
  │   → プロンプト待ち（❯）のままなら再送（最大2回）
```

### 5.3 変更点サマリ

| 項目 | DB CLI版 | YAML Inbox版 |
|------|---------|-------------|
| 報告先判定 | DBから assigned_by 取得 | 自分のinbox YAMLから assigned_by 取得 |
| 報告記録 | `python3 scripts/botsunichiroku.py report add ...` | `Edit queue/inbox/{karo}_reports.yaml`（新規報告を追記） |
| タスク完了 | `python3 scripts/botsunichiroku.py subtask update ... --status done` | `Edit queue/inbox/ashigaru{N}.yaml`（status を done に変更） |
| ファイル操作 | 0回（CLIのみ） | 2-3回（Read 1回 + Edit 2回） |

---

## 6. 足軽が使わなくなるコマンド一覧

### 6.1 完全廃止コマンド

以下のコマンドは、YAML Inbox方式への移行後、足軽は**一切使用しない**。

| コマンド | 用途 | 代替手段 |
|---------|------|---------|
| `python3 scripts/botsunichiroku.py subtask list` | タスク一覧取得 | `Read queue/inbox/ashigaru{N}.yaml` |
| `python3 scripts/botsunichiroku.py subtask show` | タスク詳細確認 | 同上（全情報が1ファイルに集約） |
| `python3 scripts/botsunichiroku.py subtask update` | タスクステータス更新 | `Edit queue/inbox/ashigaru{N}.yaml`（status フィールド変更） |
| `python3 scripts/botsunichiroku.py report add` | 報告記録 | `Edit queue/inbox/{karo}_reports.yaml`（新規報告を追記） |
| `python3 scripts/botsunichiroku.py report list` | 報告一覧取得 | 使用しない（家老のみ使用） |

### 6.2 家老のみ使用するコマンド（足軽は無関係）

以下のコマンドは、家老がDB管理・dashboard更新に使用する。足軽は知る必要がない。

| コマンド | 用途 | 使用者 |
|---------|------|--------|
| `python3 scripts/botsunichiroku.py cmd list` | コマンド一覧 | 家老 |
| `python3 scripts/botsunichiroku.py cmd add` | コマンド作成 | 家老 |
| `python3 scripts/botsunichiroku.py subtask add` | サブタスク作成 | 家老 |
| `python3 scripts/botsunichiroku.py subtask assign` | タスク割当 | 家老 |
| `python3 scripts/botsunichiroku.py report list` | 報告一覧取得 | 家老 |

---

## 7. 足軽ユーザー観点での検証

### 7.1 主要業務フローの完結性チェック

#### ✅ タスク受領から完了報告まで

1. **タスク確認**: `Read queue/inbox/ashigaru{N}.yaml` → status: assigned のタスクを探す
2. **タスク開始**: `Edit queue/inbox/ashigaru{N}.yaml` → status: assigned → in_progress
3. **作業実行**: description, target_path, notes を参照しながら作業
4. **報告作成**:
   - 報告先確認: `Read queue/inbox/ashigaru{N}.yaml` → assigned_by を確認
   - 報告記録: `Edit queue/inbox/{karo}_reports.yaml` → 新規報告を追記
5. **タスク完了**: `Edit queue/inbox/ashigaru{N}.yaml` → status: in_progress → done
6. **家老通知**: send-keys で家老を起こす

**結論**: 全フローが `Read` と `Edit` のみで完結。DB CLI不要。✅

---

#### ✅ /clear後の復帰

1. **ID確認**: `tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'`
2. **Memory MCP**: `mcp__memory__read_graph()`
3. **タスク確認**: `Read queue/inbox/ashigaru{N}.yaml` → status: assigned を探す
4. **コンテキスト読み込み**: project フィールドがあれば `Read context/{project}.md`
5. **作業開始**: 通常フローに戻る

**結論**: 復帰フローも `Read` のみで完結。DB CLI不要。✅

---

#### ✅ コンパクション復帰

1. **ID確認**: `tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'`
2. **instructions読み込み**: `Read instructions/ashigaru.md`
3. **タスク確認**: `Read queue/inbox/ashigaru{N}.yaml` → status: assigned を探す
4. **作業再開**: 通常フローに戻る

**結論**: 復帰フローも `Read` のみで完結。DB CLI不要。✅

---

#### ✅ タスク途中で /clear される場合

1. **/clear前**: `Edit queue/inbox/ashigaru{N}.yaml` → progress フィールドに途中状態を記録
2. **/clear後**: `Read queue/inbox/ashigaru{N}.yaml` → progress フィールドから復元
3. **作業再開**: 通常フローに戻る

**結論**: 途中状態の保存・復元も `Edit` と `Read` で完結。DB CLI不要。✅

---

### 7.2 エッジケースの検証

#### ケース1: 複数タスクが同時に割り当てられた場合

**シナリオ**: inbox に status: assigned のタスクが2つ以上ある

**対応**:
1. `Read queue/inbox/ashigaru{N}.yaml` で全タスクを確認
2. 先頭の assigned タスクから順に処理（または家老の指示に従う）
3. 各タスクは個別に status を in_progress → done に変更

**結論**: YAML内のリスト操作のみで対応可能。DB CLI不要。✅

---

#### ケース2: タスクが blocked になった場合

**シナリオ**: 作業中に依存関係・権限不足等でブロックされた

**対応**:
1. `Edit queue/inbox/ashigaru{N}.yaml` → status: in_progress → blocked
2. `Edit queue/inbox/{karo}_reports.yaml` → status: blocked の報告を追記
3. notes フィールドにブロック理由を記載
4. send-keys で家老に報告

**結論**: YAML編集のみで対応可能。DB CLI不要。✅

---

#### ケース3: タスクが failed になった場合

**シナリオ**: 作業中にエラーが発生し、タスクが失敗した

**対応**:
1. `Edit queue/inbox/ashigaru{N}.yaml` → status: in_progress → failed
2. `Edit queue/inbox/{karo}_reports.yaml` → status: failed の報告を追記
3. summary にエラー内容を詳細記載
4. send-keys で家老に報告

**結論**: YAML編集のみで対応可能。DB CLI不要。✅

---

#### ケース4: 家老が異なる複数のタスクが混在する場合

**シナリオ**: inbox に assigned_by: roju と assigned_by: ooku のタスクが混在

**対応**:
1. タスク開始時に assigned_by を確認
2. 報告時に適切な報告inbox（roju_reports.yaml または ooku_reports.yaml）を選択
3. send-keys も適切な家老ペイン（multiagent:agents.0 または ooku:agents.0）に送信

**結論**: YAML内のフィールド参照のみで対応可能。DB CLI不要。✅

---

### 7.3 総合結論

**足軽は DB CLI を一切使わずに、全業務を完結できる。**

- タスク確認: `Read queue/inbox/ashigaru{N}.yaml`
- ステータス更新: `Edit queue/inbox/ashigaru{N}.yaml`
- 報告記録: `Edit queue/inbox/{karo}_reports.yaml`
- 復帰フロー: `Read` のみで完結

**メリット**:
1. **学習コスト削減**: DB CLIの引数・オプションを覚える必要がない
2. **トークン削減**: CLI実行のオーバーヘッドがない（~200トークン/回削減）
3. **視認性向上**: YAMLファイルを直接見るため、タスク全体像を把握しやすい
4. **エラー回避**: CLI実行エラー（パス間違い、引数ミス等）が発生しない
5. **Read/Edit一貫性**: Claude Codeの基本ツールのみで完結し、混乱が減る

**デメリット**:
1. **YAMLフォーマット厳守**: インデント・構文ミスでYAMLが壊れるリスク
2. **ID管理の手動化**: report ID等を手動で推測・採番する必要あり
3. **並行編集リスク**: 家老が同じYAMLを同時編集すると競合の可能性（ただし、現行の足軽同士の競合リスクと同等）

**推奨**: メリットがデメリットを大きく上回る。YAML方式への移行を推奨する。

---

## 8. 補足: 家老側の対応

足軽がYAML inbox方式に移行しても、家老は引き続きDB CLIを使用する。
家老の責務は以下の通り：

1. **タスク割当**: DB CLIで subtask 作成 → inbox YAMLに書き出し → send-keys で足軽を起こす
2. **報告確認**: inbox YAMLの reports リストを読み、read: false の報告を処理
3. **DB同期**: 足軽の報告を inbox から DB に転記（dashboard更新時）
4. **inbox整理**: 完了したタスク・読んだ報告を inbox から削除または archive

**家老の改修範囲**:
- instructions/karo.md の「タスク割当フロー」「報告確認フロー」を YAML inbox 対応に改修
- DB ↔ YAML の同期スクリプト作成（オプション）

---

## 9. 次のステップ

本改修案を殿・将軍に提出し、承認を得る。

承認後の作業:
1. **inbox YAMLテンプレート作成**: queue/inbox/ashigaru1.yaml ～ ashigaru8.yaml, roju_reports.yaml, ooku_reports.yaml
2. **instructions/ashigaru.md 改修**: 本書の書き換え案を反映
3. **CLAUDE.md 改修**: /clear復帰フローを YAML inbox 版に変更
4. **instructions/karo.md 改修**: 家老のタスク割当・報告確認フローを YAML inbox 対応に変更
5. **足軽1名でパイロット運用**: ashigaru1 のみ YAML inbox 方式で運用し、問題を検証
6. **全足軽・部屋子に展開**: 問題なければ全エージェントに展開

---

**以上、足軽 instructions 改修案でござる。**
