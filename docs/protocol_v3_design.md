# 通信プロトコル v3 設計書

> **Status**: draft
> **Date**: 2026-03-08
> **Author**: ashigaru6 (subtask_813 / cmd_368)

## 1. v2→v3 差分一覧

| # | 機能 | v2 | v3 |
|---|------|----|----|
| 1 | **Request ID相関** | なし（subtask_idで暗黙紐付け） | 全通信にrequest_id(UUID短縮8文字)付与 |
| 2 | **Drain-on-Read** | read:true/false手動管理 + shogun-gc.sh手動実行 | inbox_read.sh で読み取り→stdout→自動drain |
| 3 | **Identity Re-injection** | CLAUDE.md手動復帰 + tmux @agent_id手動確認 | identity_inject.sh で自動身元注入テキスト生成 |
| 4 | 後方互換 | - | v2形式YAMLもv3で読める（request_idなし=レガシー） |

## 2. Request ID 相関

### 2.1 概要

指示→報告の1対1紐付けを実現する。家老が指示発行時にrequest_idを生成し、足軽/部屋子/お針子は報告時に同じIDを返す。未応答request_idの追跡で通信ロスト検出が可能になる。

### 2.2 request_id仕様

- **形式**: UUID v4の先頭8文字（例: `a3f7b2c1`）
- **生成者**: 指示を発行する側（家老がsubtask割当時、お針子が監査結果報告時）
- **生成方法**: `python3 -c "import uuid; print(str(uuid.uuid4())[:8])"`
- **一意性**: 8文字hex = 4.3億通り。1日100タスクでも衝突確率は実質ゼロ
- **省略時**: request_idなし = v2レガシー形式として処理（後方互換）

### 2.3 YAMLフォーマット Before/After

#### タスク割当YAML（queue/inbox/ashigaru{N}.yaml）

**Before (v2)**:
```yaml
tasks:
- subtask_id: subtask_123
  cmd_id: cmd_45
  status: assigned
  assigned_by: roju
  description: "タスクの説明"
  # ...
```

**After (v3)**:
```yaml
tasks:
- request_id: a3f7b2c1        # ← NEW
  subtask_id: subtask_123
  cmd_id: cmd_45
  status: assigned
  assigned_by: roju
  description: "タスクの説明"
  # ...
```

#### 報告YAML（queue/inbox/roju_reports.yaml）

**Before (v2)**:
```yaml
reports:
- subtask_id: subtask_123
  worker: ashigaru1
  status: done
  summary: "作業内容の報告"
  read: false
  reported_at: "2026-03-08T12:00:00"
```

**After (v3)**:
```yaml
reports:
- request_id: a3f7b2c1        # ← NEW: 指示時と同じID
  subtask_id: subtask_123
  worker: ashigaru1
  status: done
  summary: "作業内容の報告"
  read: false
  reported_at: "2026-03-08T12:00:00"
```

#### お針子報告YAML（queue/inbox/roju_ohariko.yaml）

**Before (v2)**:
```yaml
audit_reports:
- subtask_id: subtask_123
  summary: "監査合格"
  detail_ref: "curl -s localhost:8080/audit/subtask_123"
  timestamp: "2026-03-08T12:00:00"
  read: false
```

**After (v3)**:
```yaml
audit_reports:
- request_id: b4e8c3d2        # ← NEW
  subtask_id: subtask_123
  summary: "監査合格"
  detail_ref: "curl -s localhost:8080/audit/subtask_123"
  timestamp: "2026-03-08T12:00:00"
  read: false
```

### 2.4 通信ロスト検出

家老が以下のコマンドで未応答request_idを検出:

```bash
# scripts/request_tracker.sh check
# 発行済みrequest_id（inbox YAML内のassigned）と
# 応答済みrequest_id（reports YAML内のdone/error）を突合
# 差分 = 未応答（ロスト候補）
```

**検出ロジック**:
1. 全ashigaru{N}.yamlからrequest_id + assigned_atを収集
2. roju_reports.yaml + roju_ohariko.yamlからrequest_id + reported_atを収集
3. 差分（発行済み - 応答済み）= 未応答リスト
4. assigned_atから1時間以上経過 → 通信ロスト候補としてdashboard.md「要対応」に記載

**I/F定義（scripts/request_tracker.sh）**:

```
Usage: scripts/request_tracker.sh <subcommand>

Subcommands:
  generate             UUID短縮8文字を生成してstdoutに出力
  check [--threshold MINUTES]  未応答request_idを検出（デフォルト60分）
  list                 全request_idの状態一覧

Exit codes:
  0 = 未応答なし（または一覧表示成功）
  1 = 未応答あり（checkのみ）
  2 = エラー

Output (check):
  JSON: {"lost": [{"request_id": "...", "subtask_id": "...", "assigned_at": "...", "worker": "..."}]}
```

### 2.5 inbox_write.sh への統合

inbox_write.shの引数に `[request_id]` を追加:

```bash
# v3: request_id付き
bash scripts/inbox_write.sh roju_reports "完了報告" report_completed ashigaru1 a3f7b2c1

# v2互換: request_idなし（従来通り動作）
bash scripts/inbox_write.sh roju_reports "完了報告" report_completed ashigaru1
```

## 3. Drain-on-Read

### 3.1 概要

inbox YAMLの肥大化を防ぐ。現在はread:true/falseフラグの手動管理 + shogun-gc.sh手動実行だが、v3では「読んだら自動クリア」を導入する。

### 3.2 設計方針

- **drain対象**: DB永続化済みエントリのみ（安全策）
- **drain非対象**: DB未永続化エントリ（read:falseのまま残す）
- **shogun-gc.sh**: drain漏れのフォールバックとして維持（廃止しない）

### 3.3 I/F定義（scripts/inbox_read.sh）

```
Usage: scripts/inbox_read.sh <inbox_name> [options]

Arguments:
  inbox_name    読み取り対象（例: roju_reports, roju_ohariko, ashigaru1）

Options:
  --drain       読み取り後にread:trueエントリを自動削除（デフォルト: off）
  --format json|yaml|summary  出力形式（デフォルト: summary）
  --unread-only 未読（read:false）のみ表示
  --mark-read   表示したエントリをread:trueに更新（drain前提ステップ）

Exit codes:
  0 = 成功（エントリあり）
  1 = エントリなし
  2 = エラー

Output (stdout):
  指定形式で未読/全エントリを出力
```

### 3.4 drain フロー

```
家老がinbox確認
  │
  ▼ inbox_read.sh roju_reports --unread-only --format summary
  │   → 未読エントリをstdoutに表示
  │
  ▼ 家老がDB永続化（botsunichiroku.py report add ...）
  │
  ▼ inbox_read.sh roju_reports --mark-read
  │   → 処理済みエントリを read:true に更新
  │
  ▼ inbox_read.sh roju_reports --drain
  │   → read:true エントリを自動削除
  │   → flock排他制御 + atomic write（inbox_write.shと同じ方式）
  │
  ▼ YAML軽量化完了
```

### 3.5 安全策

1. **drain前の検証**: read:trueエントリのsubtask_idが没日録DBに存在するか確認
   ```python
   # DB存在チェック
   result = subprocess.run(
       ["python3", "scripts/botsunichiroku.py", "subtask", "show", subtask_id],
       capture_output=True
   )
   if result.returncode != 0:
       # DB未登録 → drainしない（データロスト防止）
       skip_drain(entry)
   ```
2. **dry-run**: `--drain --dry-run` で削除候補の表示のみ（実削除なし）
3. **flock排他制御**: inbox_write.shと同じlockfile方式で競合防止
4. **atomic write**: tmpfile + os.replace（部分読み取り防止）

### 3.6 shogun-gc.sh との関係

| 機能 | inbox_read.sh --drain | shogun-gc.sh |
|------|----------------------|--------------|
| 実行タイミング | 家老の報告処理直後（即時） | 手動 or cron（バッチ） |
| 対象 | read:trueエントリ | read:true かつ KEEP件超過分 |
| DB検証 | する（安全） | しない（read:trueを信頼） |
| 位置付け | **プライマリ（v3推奨）** | **フォールバック（drain漏れ対策）** |
| 廃止 | - | しない（保険として維持） |

## 4. Identity Re-injection

### 4.1 概要

コンパクション復帰時に自動で身元情報を注入する。現在はCLAUDE.mdの復帰手順を手動で実行しているが、v3ではstop_hookまたはCLAUDE.md復帰フローから呼び出すスクリプトで自動化する。

### 4.2 I/F定義（scripts/identity_inject.sh）

```
Usage: scripts/identity_inject.sh [options]

Options:
  --agent-id ID  エージェントID指定（省略時: tmux @agent_idから自動取得）
  --format text|json  出力形式（デフォルト: text）

Exit codes:
  0 = 成功
  1 = agent_id取得失敗
  2 = エラー

Output (stdout, text format):
  汝は{role}（{agent_id}）である。
  ペイン: {pane}
  現在の割当タスク:
    - {subtask_id} ({cmd_id}): {description} [status: {status}]
  報告先: {report_yaml}
  instructions: {instructions_path}
```

### 4.3 生成ロジック

```python
# 1. agent_id → role/pane/instructions マッピング
AGENT_MAP = {
    "shogun":    {"role": "将軍",  "pane": "shogun:main.0",       "instructions": "instructions/shogun.md"},
    "karo-roju": {"role": "老中",  "pane": "multiagent:agents.0", "instructions": "instructions/karo.md"},
    "ashigaru1": {"role": "足軽1", "pane": "multiagent:agents.1", "instructions": "instructions/ashigaru.md"},
    "ashigaru6": {"role": "部屋子1","pane": "multiagent:agents.2", "instructions": "instructions/ashigaru.md"},
    "ohariko":   {"role": "お針子", "pane": "ooku:agents.0",      "instructions": "instructions/ohariko.md"},
}

# 2. inbox YAMLから割当タスク取得
#    足軽/部屋子: ashigaru{N}.yaml の status: assigned
#    家老: roju_reports.yaml + roju_ohariko.yaml の read:false件数
#    お針子: audit pending件数（DB参照）

# 3. テキスト生成してstdoutに出力
```

### 4.4 呼び出しパターン

#### パターンA: stop_hookからの呼び出し（推奨）

stop_hook_inbox.sh にコンパクション検出ロジックを追加:

```bash
# コンパクション検出: last_assistant_messageに "summary" が含まれる
# または conversation_turnが急減した場合
if echo "$LAST_MSG" | grep -qiE 'コンパクション|compaction|summary.*generated'; then
    IDENTITY=$(bash "$SCRIPT_DIR/scripts/identity_inject.sh" --agent-id "$AGENT_ID")
    # block理由にidentity情報を含める
    REASON="コンパクション復帰検出。$IDENTITY"
fi
```

**注意**: コンパクション検出は誤検出リスクあり。確実な検出は困難なため、パターンBとの併用を推奨。

#### パターンB: CLAUDE.md復帰フローからの呼び出し

CLAUDE.mdの復帰手順 Step 1 を以下に置き換え:

```
▼ Step 1: 身元自動注入
│   IDENTITY=$(bash scripts/identity_inject.sh)
│   → 役割・ペイン・割当タスク・報告先が一括表示される
```

**メリット**: 誤検出なし（手動トリガー）
**デメリット**: エージェントがCLAUDE.mdの手順を忘れている場合は機能しない

#### パターンC: 併用（推奨構成）

1. stop_hookでコンパクション検出 → identity_inject.shの出力をblock理由に含める（パターンA）
2. CLAUDE.md復帰手順にもidentity_inject.sh呼び出しを記載（パターンB、フォールバック）
3. /clear後の復帰でもStep 1でidentity_inject.shを呼ぶ

### 4.5 stop_hook_inbox.sh 改修箇所

```diff
+ # ─── 5.5 コンパクション復帰検出 ───
+ # summaryの特徴的パターンでコンパクションを推定
+ COMPACTION_DETECTED=false
+ if echo "$LAST_MSG" | grep -qiE 'エージェントの役割|コンパクション復帰|summary生成'; then
+     COMPACTION_DETECTED=true
+ fi
+
+ # コンパクション検出時: identity情報をblock理由に注入
+ if [ "$COMPACTION_DETECTED" = true ]; then
+     IDENTITY=$(bash "$SCRIPT_DIR/scripts/identity_inject.sh" --agent-id "$AGENT_ID" 2>/dev/null || echo "")
+     if [ -n "$IDENTITY" ]; then
+         REASON="コンパクション復帰検出。身元情報: ${IDENTITY}"
+         REASON_ESCAPED=$(echo "$REASON" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
+         echo "{\"decision\": \"block\", \"reason\": ${REASON_ESCAPED}}"
+         exit 0
+     fi
+ fi
```

## 5. 後方互換性

### 5.1 v2形式の読み取り

v3のスクリプト群はv2形式YAML（request_idなし）を正常に処理する:

```python
# request_idの取得（v2互換）
request_id = entry.get("request_id", None)  # v2ならNone
if request_id:
    # v3処理（request_id追跡）
else:
    # v2フォールバック（subtask_idのみで処理）
```

### 5.2 段階的移行

| Phase | 期間 | 内容 |
|-------|------|------|
| Phase 0 | 即時 | 設計書承認。本ドキュメント |
| Phase 1 | Wave2 | identity_inject.sh実装 + CLAUDE.md復帰フロー更新 |
| Phase 2 | Wave2 | inbox_read.sh実装 + 家老の報告処理フロー更新 |
| Phase 3 | Wave3 | request_tracker.sh実装 + inbox_write.sh拡張 |
| Phase 4 | Wave3 | 全YAML通信にrequest_id付与開始 |

### 5.3 移行中の共存

- Phase 1-2: request_idなし（v2形式のまま）。drain + identityのみ先行導入
- Phase 3以降: 新規指示にはrequest_id付与。旧エントリはrequest_idなしのまま
- 完全移行: 旧エントリが全てdrain/GCされた時点でv2サポート停止可能（急がない）

## 6. instructions/*.md 改修箇所一覧

| ファイル | 改修内容 | Phase |
|----------|---------|-------|
| **CLAUDE.md** | /clear復帰Step 1をidentity_inject.sh呼び出しに更新 | 1 |
| **CLAUDE.md** | コンパクション復帰手順にidentity_inject.sh追記 | 1 |
| **instructions/karo.md** | 報告処理フローにinbox_read.sh --drain追加 | 2 |
| **instructions/karo.md** | タスク割当時にrequest_id生成手順追加 | 3 |
| **context/karo-yaml-format.md** | 全YAMLフォーマットにrequest_idフィールド追加 | 3 |
| **context/karo-sendkeys.md** | 変更なし（send-keysプロトコル自体は不変） | - |
| **context/karo-clear.md** | /clearフローのSTEP 6にrequest_id付き通知 | 3 |
| **context/karo-audit.md** | 監査依頼にrequest_id付与 | 3 |
| **context/karo-botsunichiroku.md** | 変更なし（DB側にrequest_idカラム追加は別ADR） | - |
| **instructions/ashigaru.md** | 報告時にrequest_idを返す手順追加 | 3 |
| **instructions/ohariko.md** | 監査報告にrequest_id追加 | 3 |
| **scripts/stop_hook_inbox.sh** | コンパクション検出 + identity_inject呼び出し追加 | 1 |

## 7. Wave2 実装分担案

### Wave2-A: identity_inject.sh（部屋子向け）

- scripts/identity_inject.sh 新規作成
- CLAUDE.md 復帰フロー更新（Step 1置換）
- stop_hook_inbox.sh コンパクション検出追加
- テスト: 各agent_idでの出力確認

### Wave2-B: inbox_read.sh（足軽向け）

- scripts/inbox_read.sh 新規作成
- --drain, --mark-read, --unread-only, --format オプション実装
- flock排他制御 + atomic write
- DB存在チェック（drain安全策）
- テスト: drain後のYAMLファイルサイズ確認、競合テスト

### Wave3-A: request_tracker.sh（部屋子向け）

- scripts/request_tracker.sh 新規作成（generate/check/list）
- inbox_write.sh にrequest_id引数追加
- context/karo-yaml-format.md 更新

### Wave3-B: instructions改修（足軽向け）

- instructions/karo.md, ashigaru.md, ohariko.md の改修
- context/karo-clear.md, karo-audit.md の改修
- 全エージェントの報告フローにrequest_id返却手順追加

## 付録A: スクリプト一覧（v3新規）

| スクリプト | 用途 | 引数 | 出力 |
|-----------|------|------|------|
| scripts/identity_inject.sh | 身元情報生成 | [--agent-id ID] [--format text\|json] | テキスト or JSON |
| scripts/inbox_read.sh | inbox読み取り+drain | \<inbox_name\> [--drain] [--mark-read] [--format] | YAML/JSON/summary |
| scripts/request_tracker.sh | request_id管理 | generate \| check [--threshold MIN] \| list | UUID8文字 \| JSON |

## 付録B: 既存スクリプトの改修

| スクリプト | 改修内容 | 後方互換 |
|-----------|---------|---------|
| scripts/inbox_write.sh | 第5引数にrequest_id追加（省略可） | 既存呼び出しはそのまま動作 |
| scripts/stop_hook_inbox.sh | コンパクション検出 + identity_inject呼び出し | 既存フローに影響なし |
| scripts/shogun-gc.sh | 変更なし（drain漏れフォールバックとして維持） | - |
