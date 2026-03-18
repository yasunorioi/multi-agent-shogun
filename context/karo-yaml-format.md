# タスクYAML・報告YAMLフォーマット

> 本ファイルは高札経由で配信: `curl -s http://localhost:8080/docs/context/karo-yaml-format.md`

## タスクYAML（queue/inbox/ashigaru{N}.yaml）

家老が足軽にタスクを割り当てる際のフォーマット：

```yaml
tasks:
- request_id: a3f7b2c1          # v3: UUID短縮8文字（家老が生成）
  subtask_id: subtask_123
  cmd_id: cmd_45
  status: assigned
  description: "タスクの説明"
  project: multiagent            # context/{project}.md を読む指示
  target_path: instructions/karo.md
  wave: 2
  assigned_by: roju
  needs_audit: false
  assigned_at: "2026-02-08T10:30:00"
```

> **v3移行注記**: `request_id` は v3 で追加。省略可（v2互換）。付与されている場合は報告時に同じIDを返すこと。

## 報告YAML（queue/inbox/roju_reports.yaml）

足軽が老中に報告する際のフォーマット：

```yaml
- request_id: a3f7b2c1          # v3: 指示時と同じIDを返す（あれば）
  subtask_id: subtask_123
  cmd_id: cmd_45
  worker: ashigaru1
  status: done                   # done | error | blocked
  reported_at: "2026-02-08T11:45:00"
  summary: "1行サマリ"
  skill_candidate: null
  read: false                    # 家老確認後 true に変更
```

> **v3移行注記**: `request_id` がタスクYAMLに含まれていれば、報告時にそのまま返す。なければ省略。

### summaryフィールド規約（80文字制限）

| 項目 | 内容 |
|------|------|
| **上限** | 80文字（inbox_write.sh が自動切り詰め） |
| **切り詰め時** | 80文字 + `…` に短縮、原文は `full_summary` フィールドに保存 |
| **警告出力** | stderr に `[inbox_write] WARNING: summary truncated (N→80 chars)` |
| **除外対象** | `type=stophook_notification` は切り詰め対象外 |

**推奨フォーマット**: `summary` は「結果+数値+commit hash」のみ。詳細は `report add` の `findings` に記載せよ。

```
# 良い例（短く・機械可読）
summary: "W7-a統合テスト全22件PASS commit 51a75f9"

# 悪い例（長すぎ・自動切り詰め対象）
summary: "足軽1がsubtask_929のW8-③a統合テストを実施し、inbox_write.shにsummary長バリデーション..."
```

**詳細参照方法（detail_ref）**:
```
python3 scripts/botsunichiroku.py report list --subtask subtask_XXX
```

## お針子retry-loop報告YAML（roju_ohariko.yaml audit_results拡張）

お針子がDIAGNOSE→APPLY→再監査ループ時に使用するフォーマット：

```yaml
- subtask_id: subtask_XXX
  retry_count: 1                       # 0=初回, 1=1回目修正, 2=最大
  failure_category: "技術的誤り"        # prompt不足|要件誤解|技術的誤り|回帰|フォーマット不備|null
  retry_of: "subtask_XXX_attempt_1"    # 前回audit結果への参照
  summary: "再監査: retry_count=1, 前回findingsを修正確認"
  # ... 既存フィールド（timestamp, read等）
```

> **env指定**: `RETRY_COUNT=1 FAILURE_CATEGORY="技術的誤り" RETRY_OF="subtask_XXX_attempt_1" bash scripts/inbox_write.sh ...`
> **上限**: retry_count=2超でエラー（老中エスカレーション必須）。rejected_judgment(9点以下)は自動ループ禁止。

## お針子報告YAML（queue/inbox/roju_ohariko.yaml）

```yaml
audit_reports:
- request_id: b4e8c3d2          # v3: 監査依頼時のID（あれば）
  subtask_id: subtask_123
  summary: "監査合格: 4観点クリア"
  detail_ref: "curl -s localhost:8080/audit/subtask_123"
  timestamp: "2026-02-08T12:00:00"
  read: false
```

## 注意事項

- `read` フィールドは家老が確認後 `true` に更新（Edit tool使用）
- `status=error/blocked` の場合、summary にエラー内容・ブロック理由を詳述
- v3では `inbox_read.sh --drain` でDB永続化済みエントリを自動削除可能
- フォールバック: shogun-gc.sh で手動GC（直近10件保持）
- `request_id` 生成: `python3 -c "import uuid; print(str(uuid.uuid4())[:8])"`
