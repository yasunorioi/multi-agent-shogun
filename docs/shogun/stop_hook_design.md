# Stop Hook Enhancement 設計書（cmd_274 Phase 2）

> Created: 2026-02-25
> Author: 老中（karo-roju）
> Status: Phase 1調査完了 → Phase 2設計

## 1. 現状把握

### 1.1 現行 stop_hook_inbox.sh（135行）— 既に稼働中
| 機能 | 状態 | 備考 |
|------|------|------|
| stop_hook_active 無限ループ防止 | ✅ 実装済み | origin互換 |
| tmux @agent_id エージェント識別 | ✅ 実装済み | 3セッション透過 |
| shogun/ohariko → approve固定 | ✅ 実装済み | 正しい設計 |
| karo: roju_reports + roju_ohariko 未読検知 | ✅ 実装済み | `read: false` grep |
| ashigaru: ashigaru{N}.yaml 未読検知 | ✅ 実装済み | `status: assigned` grep |
| サマリ生成（Python3 YAML parse, 最大5件） | ✅ 実装済み | 充分な品質 |
| block JSON出力 | ✅ 実装済み | origin互換 |
| **last_assistant_message 分析** | ❌ **未実装** | **origin由来の主要機能** |
| **自動通知（完了/エラー検知→老中通知）** | ❌ **未実装** | **安全網として有用** |
| **テスト環境変数（__STOP_HOOK_AGENT_ID）** | ❌ **未実装** | テスタビリティ |

### 1.2 不足スクリプト
| スクリプト | 状態 | 必要性 |
|-----------|------|--------|
| scripts/inbox_write.sh | ❌ 未作成 | 自動通知に必要（flock排他制御+atomic write） |
| scripts/inbox_watcher.sh | ❌ 未作成 | **不要**（Stop Hookが代替、ポーリング禁止） |

### 1.3 settings.json の問題
- 現行: `"timeout": 10000`
- Claude Code公式仕様: timeout単位は **秒**（デフォルト600秒）
- 10000秒 = 166分 → **異常に長い。10秒に修正すべき**
- origin参照値: 10秒

## 2. 設計方針

### 2.1 基本原則
- **既存の動作を壊さない**: 現行のinbox未読チェック+blockは維持
- **origin機能の選択的適合**: last_assistant_message分析を追加
- **send-keys通信との共存**: Stop Hook自動通知は安全網、send-keysは主経路
- **最小改修**: inbox_write.sh新規作成 + stop_hook_inbox.sh改修のみ

### 2.2 アーキテクチャ
```
足軽/部屋子がタスク完了
  │
  ├── [主経路] 足軽が報告YAML記入 + send-keys で老中を起こす（既存・変更なし）
  │
  └── [安全網] Stop Hook発火 ──→ last_assistant_message 分析
       │                            │
       │                            ├── 完了検出 → inbox_write.sh で老中に通知
       │                            └── エラー検出 → inbox_write.sh で老中に通知
       │
       └── inbox未読チェック（既存ロジック）
            ├── 未読あり → block JSON
            └── 未読なし → approve (exit 0)
```

**安全網の価値**: send-keysが失敗した場合、エージェントがエラーで停止した場合、
正常報告フローが完了しなかった場合に老中への通知が担保される。

## 3. 詳細設計

### 3.1 stop_hook_inbox.sh 改修

#### 追加箇所: last_assistant_message分析（agent_id取得後、inbox未読チェック前に挿入）

```bash
# ─── Analyze last_assistant_message ───
LAST_MSG=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('last_assistant_message', ''))
except:
    print('')
" 2>/dev/null || echo "")

if [ -n "$LAST_MSG" ]; then
    NOTIFY_TYPE=""
    NOTIFY_CONTENT=""

    # 完了検出パターン（日本語+英語、動詞+文脈ペアで誤検出防止）
    if echo "$LAST_MSG" | grep -qiE '任務完了|完了でござる|報告YAML.*更新|報告YAML.*記入|report.*updated|task completed|タスク完了|roju_reports.*更新'; then
        NOTIFY_TYPE="report_completed"
        NOTIFY_CONTENT="${AGENT_ID}、タスク完了検出。roju_reports確認されたし。"
    # エラー検出パターン
    elif echo "$LAST_MSG" | grep -qiE 'エラー.*中断|失敗.*中断|見つからない.*中断|abort|error.*abort|failed.*stop'; then
        NOTIFY_TYPE="error_report"
        NOTIFY_CONTENT="${AGENT_ID}、エラーで停止検出。確認されたし。"
    fi

    # 老中に自動通知（background、非ブロッキング）
    # shogun/ohariko はこのブロック到達前にexit 0済み（§3.1既存ロジック）
    if [ -n "$NOTIFY_TYPE" ]; then
        bash "$SCRIPT_DIR/scripts/inbox_write.sh" roju_reports \
            "$NOTIFY_CONTENT" "$NOTIFY_TYPE" "$AGENT_ID" &
    fi
fi
```

#### テスト環境変数の追加
```bash
# agent_id取得ロジックにテスト用override追加
if [ -n "${__STOP_HOOK_AGENT_ID+x}" ]; then
    AGENT_ID="$__STOP_HOOK_AGENT_ID"
elif [ -z "${TMUX_PANE:-}" ]; then
    exit 0
else
    AGENT_ID=$(tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}' 2>/dev/null || echo "")
fi

# SCRIPT_DIR override for testing
SCRIPT_DIR="${__STOP_HOOK_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
```

#### 完了/エラー検出パターン一覧

| パターン | NOTIFY_TYPE | 検出対象 |
|---------|-------------|---------|
| 任務完了 | report_completed | 足軽/部屋子の完了報告 |
| 完了でござる | report_completed | 足軽/部屋子の完了報告 |
| 報告YAML.*更新 | report_completed | YAML報告記入 |
| 報告YAML.*記入 | report_completed | YAML報告記入（我々独自） |
| report.*updated | report_completed | 英語の完了報告 |
| task completed | report_completed | 英語の完了報告 |
| タスク完了 | report_completed | 足軽/部屋子の完了報告 |
| roju_reports.*更新 | report_completed | 老中報告YAML更新（我々独自） |
| エラー.*中断 | error_report | エラーによる中断 |
| 失敗.*中断 | error_report | 失敗による中断 |
| 見つからない.*中断 | error_report | ファイル/リソース不在 |
| abort | error_report | 英語の中断 |
| error.*abort | error_report | 英語のエラー中断 |
| failed.*stop | error_report | 英語の失敗停止 |

### 3.2 inbox_write.sh 新規作成

我々のYAML構造に適合した安全書き込みユーティリティ。

#### 仕様
```
Usage: bash scripts/inbox_write.sh <target_inbox> <content> <type> <from>
Example: bash scripts/inbox_write.sh roju_reports "ashigaru1完了" report_completed ashigaru1
```

#### 設計要点
| 項目 | 設計 |
|------|------|
| 排他制御 | `flock -w 5`（5秒タイムアウト、最大3回リトライ） |
| 書き込み先 | `queue/inbox/{target_inbox}.yaml` の `reports:[]` セクション |
| atomic write | tmpfile + os.replace（部分読み取り防止） |
| オーバーフロー保護 | `stop_hook_notifications` type の50件超を刈り込み |
| 通知エントリ形式 | 下記参照 |

#### 通知エントリ形式（roju_reports.yaml に追加）
```yaml
  - subtask_id: stophook_notification
    worker: ashigaru1
    status: notification
    reported_at: "2026-02-25T14:00:00"
    summary: "ashigaru1、タスク完了検出。roju_reports確認されたし。"
    type: report_completed
    read: false
```

**重要**: `subtask_id: stophook_notification` で通常の報告と区別。
老中のサマリ生成ロジック（Python3）はこのエントリを通常報告と同様に処理可能
（`subtask_id` と `summary` フィールドが存在するため）。

#### origin との差分

| 項目 | origin | 我々 |
|------|--------|------|
| 書き込み先 | `karo.yaml` の `messages:[]` | `roju_reports.yaml` の `reports:[]` |
| エントリ形式 | id/from/timestamp/type/content/read | subtask_id/worker/status/reported_at/summary/type/read |
| .venv/bin/python3 | 使用 | **システムpython3**を使用（.venvは保証されない） |
| flock | ✅ | ✅（同一設計） |
| atomic write | ✅ tmpfile+os.replace | ✅（同一設計） |
| オーバーフロー保護 | 50メッセージ全体 | notification typeのみ50件制限 |

### 3.3 settings.json 修正

```json
"Stop": [
  {
    "command": "bash /home/yasu/multi-agent-shogun/scripts/stop_hook_inbox.sh",
    "timeout": 10
  }
]
```

変更: `10000` → `10`（10秒。origin準拠）

### 3.4 テスト設計

origin の10ユニットテスト + 5 E2Eテストを我々のシステムに適合。

#### ユニットテスト（tests/unit/test_stop_hook.bats）

| ID | テスト内容 | 方式 |
|----|----------|------|
| T-001 | stop_hook_active=true → exit 0（全処理スキップ） | env override |
| T-002 | TMUX_PANE空 + __STOP_HOOK_AGENT_ID未設定 → exit 0 | env unset |
| T-003 | agent_id=shogun → exit 0 | __STOP_HOOK_AGENT_ID=shogun |
| T-004 | agent_id=ohariko → exit 0 | __STOP_HOOK_AGENT_ID=ohariko |
| T-005 | 完了メッセージ → inbox_write呼び出し(report_completed) | mock inbox_write |
| T-006 | エラーメッセージ → inbox_write呼び出し(error_report) | mock inbox_write |
| T-007 | 中立メッセージ → inbox_write呼ばれない | mock inbox_write |
| T-008 | karo-roju + 未読あり → block JSON | テスト用inbox YAML |
| T-009 | ashigaru1 + assigned あり → block JSON | テスト用inbox YAML |
| T-010 | ashigaru1 + assigned なし → exit 0 | テスト用inbox YAML |

#### E2Eテスト（tests/e2e/e2e_stop_hook.bats）

| ID | テスト内容 |
|----|----------|
| E2E-001 | inbox_write.sh 基本動作（roju_reports.yamlに書き込み） |
| E2E-002 | 排他制御（並列2プロセス書き込み、データ破損なし） |
| E2E-003 | オーバーフロー保護（51件書き込み後、notification 50件以下） |
| E2E-004 | Stop Hook → inbox_write → karo検知 のフルフロー |

テスト隔離: `__STOP_HOOK_SCRIPT_DIR` で一時ディレクトリにリダイレクト。
本番ファイルに影響しない。

## 4. 影響範囲

### 4.1 変更ファイル一覧

| ファイル | 変更種別 | 推定行数 |
|---------|---------|---------|
| scripts/stop_hook_inbox.sh | **改修** | +35行（last_msg分析+テストenv var） |
| scripts/inbox_write.sh | **新規作成** | ~70行 |
| .claude/settings.json | **修正** | 1行（timeout） |
| tests/unit/test_stop_hook.bats | **新規作成** | ~120行 |
| tests/e2e/e2e_stop_hook.bats | **新規作成** | ~80行 |
| **合計** | | **~305行** |

### 4.2 影響しないもの

| 項目 | 理由 |
|------|------|
| 既存のsend-keys通信 | Stop Hook自動通知はsend-keysと独立（安全網） |
| 没日録DB | Stop HookはDB書き込みしない |
| 足軽/部屋子の報告フロー | 既存のYAML記入+send-keys手順は変更なし |
| お針子の監査フロー | ohariko→approve固定は維持 |
| permissions.allow | 追加不要（Stop Hookはsettings.json hooks設定で完結） |
| CLAUDE.md / instructions | 変更不要（Stop Hookは透過的に動作） |

## 5. 実装計画（Phase 3 サブタスク分割案）

| subtask | 担当候補 | 内容 | 依存 |
|---------|---------|------|------|
| A | 足軽/部屋子 | scripts/inbox_write.sh 新規作成 | なし |
| B | 足軽/部屋子 | scripts/stop_hook_inbox.sh 改修（last_msg分析+テストenv var追加） | Aに依存 |
| C | 足軽/部屋子 | .claude/settings.json timeout修正 | なし |
| D | 足軽/部屋子 | tests/unit/test_stop_hook.bats + tests/e2e/e2e_stop_hook.bats 作成 | A, Bに依存 |

**Wave構成案**:
- Wave 1: A（inbox_write.sh）+ C（timeout修正）— 並列可
- Wave 2: B（stop_hook改修）+ D（テスト）— A完了後

## 6. リスクと緩和策

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| inbox_write.sh のYAMLパースエラー | 通知が書き込めない | try/except + エラーログ。既存inbox検知に影響しない |
| 完了パターン誤検出 | 不要な通知が増える | 動詞+文脈ペアで精度確保。notification は read: true で消える |
| 完了パターン検出漏れ | 通知が来ない | 主経路（send-keys）が引き続き機能。安全網の検出漏れは許容可 |
| flock デッドロック | inbox_write がハング | 5秒タイムアウト + 3回リトライで緩和 |
| timeout修正の副作用 | Stop Hookが途中タイムアウト | 10秒あれば十分（現行処理は1秒以内） |

## 7. 将来拡張候補（Phase 5以降）

| フック | 用途 | 優先度 |
|--------|------|--------|
| SessionStart hook | セッション開始時の自動コンテキスト読み込み | 中 |
| PreCompact hook | コンパクション前の進捗自動保存 | 中 |
| TeammateIdle hook | 足軽idle検知→老中に通知 | 低 |
