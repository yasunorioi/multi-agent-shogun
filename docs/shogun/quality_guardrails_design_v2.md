# 品質ガードレール一貫設計書 v2 — Phase 0-2 実装仕様

> **軍師統合分析** | cmd_437 subtask_970 | 2026-03-24
> **入力**: subtask_966(軍師サーベイ) + subtask_967(CogRouter+think) + subtask_968(AgentSpec+hooks) + subtask_969(ToolSafe+拒否)
> **North Star**: 外の知見を借りて内の仕組みを研ぎ澄ませ
> **殿の制約**: マクガイバー精神・月額ゼロ・既存の仕組みを壊すな

---

## 0. 設計思想

### 0.1 温室三層構造からの導出

殿が温室制御で確立した三層構造が、本設計の骨格:

```
爆発（緊急停止）  → Phase 0: Preflight Check + instructions変更
ガムテ（ルール）  → Phase 1: policy_checker.py + hooks
知恵（LLM判断）   → Phase 2: 適応的思考深度 + 自動ルーブリック
```

**下層が上層を黙らせる原則**: Phase 0のinstructions変更はPhase 1のhooksが入っても残る。Phase 1のhooksはPhase 2のLLM判断より優先。各Phaseは**加算的**であり、前のPhaseを置き換えない。

### 0.2 Phase間の非破壊性保証

| 導入 | Phase 0で入れるもの | Phase 1で変わるか | Phase 2で変わるか |
|---|---|---|---|
| Preflight Check | instructions/ashigaru.mdに追記 | 変わらない（hookで二重化） | 変わらない |
| 拒否3段階 | instructions/ashigaru.mdに追記 | hookがL1を自動ブロック | 変わらない |
| ルーブリック拡張 | instructions/ohariko.mdに追記 | 変わらない | verification_commands自動化 |
| effort設定 | launch_mbp.sh/settings.jsonに追記 | 変わらない | 動的effort切替に拡張 |
| policy_checker.py | — | **新規追加** | ルール自動生成に拡張 |
| TraceRecord | — | — | **新規追加** |

**Phase Nで入れたものがPhase N+1で不要になるケース: なし。** 全て加算的。

### 0.3 データモデル

Phase 0-2を貫通する中核データモデル:

```yaml
# === TraceRecord（Phase 2で完成、Phase 1で芽を出す） ===
trace:
  trace_id: "tr_20260324_subtask970_001"
  phase: preflight | runtime | postaudit     # 3本柱のどこで検出されたか
  agent: gunshi | ashigaru1 | ohariko        # 検出したエージェント
  verdict: pass | warn | deny                # 拒否3段階に対応
  rule_id: F001 | P3_FAIL | rubric_policy   # 何に引っかかったか
  target: "tmux send-keys -t shogun..."      # 対象のアクション/ファイル
  timestamp: "2026-03-24T20:14:46"
  parent_trace_id: null                      # 連鎖追跡用
```

- **Phase 0**: TraceRecordは存在しない。足軽の報告テキストに「P1-FAIL」等を含める
- **Phase 1**: policy_checker.pyのログ出力がTraceRecordの原型（ファイルログ）
- **Phase 2**: 没日録DBにtraceテーブル追加。お針子が全TraceRecordを集計

→ Phase 0で「P1-FAIL: 対象ファイル不在」という**文字列規約**を定めることで、Phase 1-2で機械的にパース可能にする。これが「Phase 0がPhase 1の邪魔にならない」ための鍵。

---

## 1. Phase 0: 即時実施（instructions変更のみ）

### 1.1 概要

| 項目 | 内容 |
|---|---|
| 変更対象 | instructions/ashigaru.md, instructions/ohariko.md, config/settings.yaml, scripts/launch_mbp.sh |
| 工数 | 足軽1名で半日 |
| 効果 | cmd_284-300型ハルシネーション事故の防止、API代削減 |
| リスク | 過剰拒否の可能性（閾値調整で対応） |
| 月額コスト | **ゼロ**（instructions変更のみ） |

### 1.2 足軽Preflight Check（instructions/ashigaru.md追記）

```markdown
## Preflight Check（タスク実行前・必須）

タスクYAMLを読んだ後、実行前に以下を確認せよ。
1つでもFAILなら status: infeasible で報告し、実行するな。

| # | チェック項目 | 方法 | FAIL条件 |
|---|---|---|---|
| P1 | 対象ファイル存在 | ls -la {target_path} | ファイルが存在しない |
| P2 | 前提subtask完了 | blocked_byが全てdone | 未完了のblocked_byあり |
| P3 | 権限充足 | 必要なコマンドが実行可能か | sudo必要だが権限なし |
| P4 | タスク明確性 | 何を実装するか具体的に特定できるか | 曖昧で特定不能 |
| P5 | context_files読了 | 全context_filesを読めるか | ファイル不在/アクセス不可 |

### 報告フォーマット（infeasible時）
  status: infeasible
  preflight_result: "P1-FAIL"
  reason: "対象ファイル src/foo.py が存在しない"
  evidence: "ls -la src/foo.py → No such file or directory"
  recommendation: "前提subtask_XXXの完了を確認、またはタスク記述の修正が必要"

### 報告フォーマット（全PASS時）
タスク実行前に以下を1行記載せよ（省略可だが推奨）:
  preflight_result: "ALL-PASS"
```

**設計意図**:
- `preflight_result: "P1-FAIL"` という文字列規約がPhase 1で機械的パース可能
- 足軽が自然言語で書くのではなく**コード**（Pn-FAIL/ALL-PASS）で書く
- Phase 1のpolicy_checker.pyはこの規約を前提にログ解析できる

### 1.3 拒否3段階モデル（instructions/ashigaru.md追記）

```markdown
## 拒否3段階（Preflight FAIL時の判断基準）

| Level | 名称 | 条件 | 行動 |
|---|---|---|---|
| L1 切腹 | HARD STOP | P1-FAIL, P2-FAIL, F001-F006該当 | **即座に拒否**。status: infeasible |
| L2 差止め | SOFT BLOCK | P3-FAIL, P4-FAIL, 200行超変更 | 老中にエスカレーション。status: blocked |
| L3 注意喚起 | CAUTION | P5-FAIL(一部), 初見パターン | 実行するが報告に注記。status: done + caution |

L1は無条件拒否。L2は老中の判断を仰げ。L3は自己判断で実行可。
```

**K8s Deny/Warn/Audit、Claude Code deny/ask/allow、guardrails-ai EXCEPTION/REASK/NOOPの
業界共通3段階パターンに準拠**（subtask_969の知見）。

### 1.4 お針子ルーブリック拡張（instructions/ohariko.md追記）

```markdown
## ポリシー準拠チェック（ルーブリック追加項目 +3点）

| # | チェック項目 | 配点 | 方法 |
|---|---|---|---|
| PC1 | F001-F006違反なし | 1点 | git diff + コミット内容にポリシー違反コマンドがないか |
| PC2 | 権限境界遵守 | 1点 | 自分のinbox以外のYAMLを書き換えていないか |
| PC3 | 報告真正性 | 1点 | 報告内のcommitハッシュをgit logで実在確認 |

15点ルーブリック → 18点ルーブリックに拡張。
PC3は特に重要: cmd_284-300事故の再発防止。
```

### 1.5 effort設定（config/settings.yaml + 起動スクリプト）

subtask_967の知見を適用。role別effort固定:

```yaml
# config/settings.yaml に追記
effort_routing:
  ashigaru: low       # 足軽: 実装タスクは低effort（トークン節約）
  heyako: low         # 部屋子: 同上
  gunshi: max         # 軍師: 戦略分析は最大effort
  ohariko: high       # お針子: 監査は高effort
  karo: high          # 老中: タスク分解は高effort
```

```bash
# scripts/launch_mbp.sh のエージェント起動行に追加
# 足軽起動例
claude --effort low  # 既存の起動オプションに追加
```

**即効性**: Claude Codeの `--effort` オプションと `/effort` コマンドは即使える。
`think hard`/`ultrathink` キーワードは軍師・お針子が必要時に手動発動。

### 1.6 Phase 0 変更ファイル一覧

| ファイル | 変更内容 | 行数（推定） |
|---|---|---|
| instructions/ashigaru.md | Preflight Check + 拒否3段階 追記 | +40行 |
| instructions/ohariko.md | PC1-PC3ルーブリック追記 | +15行 |
| config/settings.yaml | effort_routing セクション追記 | +8行 |
| scripts/launch_mbp.sh | --effort オプション追加 | +5行 |
| **合計** | | **+68行** |

---

## 2. Phase 1: 軽量スクリプト実装

### 2.1 概要

| 項目 | 内容 |
|---|---|
| 変更対象 | scripts/policy_checker.py(新規), settings.json(hook追記), scripts/gatekeeper_f006.sh(統合) |
| 工数 | 足軽1-2名で1日 |
| 効果 | F001/F004/シリアルcatの機械的ブロック、ポリシー違反の自動検出 |
| 前提 | Phase 0完了 |
| 月額コスト | **ゼロ**（ローカルPythonスクリプト） |

### 2.2 policy_checker.py（PreToolUse版・完成形）

subtask_968の足軽2が設計した§10.3のプロトタイプを正式採用。変更点:

1. **ログ出力追加**: TraceRecord原型をファイルに記録
2. **agent_id別ルール**: 軍師と足軽で異なるルールセット
3. **fail-open設計**: パースエラー時は通過（既存gatekeeper_f006.shがfail-closedで二重防御）

```python
#!/usr/bin/env python3
"""
policy_checker.py — Phase 1 PreToolUse Policy Checker
AgentSpec DSL inspired, Claude Code hooks compatible.

設計原則:
- fail-open (エラー時は通過。gatekeeper_f006.shがfail-closedで兜)
- ms級オーバーヘッド (正規表現マッチのみ、LLM呼び出しなし)
- TraceRecord原型をログ出力
"""
import json, os, re, subprocess, sys
from datetime import datetime

LOG_PATH = os.path.expanduser("~/multi-agent-shogun/logs/policy_violations.jsonl")

def get_agent_id() -> str:
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return "unknown"
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-t", pane, "-p", "#{@agent_id}"],
            capture_output=True, text=True, timeout=2
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def log_violation(agent_id, rule_id, target, decision):
    """TraceRecord原型をJSONLログに記録"""
    record = {
        "trace_id": f"tr_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "phase": "runtime",
        "agent": agent_id,
        "verdict": decision,
        "rule_id": rule_id,
        "target": target[:200],  # 長すぎるコマンドは切り詰め
        "timestamp": datetime.now().isoformat()
    }
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # ログ書き込み失敗は無視（fail-open）

# === ルール定義 ===
# (trigger_tool, check_fn, decision, rule_id, reason)
UNIVERSAL_RULES = [
    ("Bash",
     lambda cmd, _: bool(re.search(r'tmux\s+send-keys\s+.*-t\s+shogun', cmd)),
     "deny", "F001",
     "将軍への直接send-keys禁止。老中経由で報告せよ。"),
    ("Bash",
     lambda cmd, _: bool(re.search(r'while\s+true|sleep\s+\d+\s*&&\s*tmux', cmd, re.S)),
     "deny", "F004",
     "ポーリング禁止。イベント駆動で動け。"),
    ("Bash",
     lambda cmd, _: bool(re.search(r'cat\s+/dev/tty(ACM|USB)', cmd)),
     "deny", "SERIAL",
     "シリアルデバイス直接cat禁止。tmuxペインが破壊される。"),
]

ROLE_RULES = {
    "gunshi": [
        ("Edit",
         lambda _, path: bool(re.search(r'queue/inbox/ashigaru', path)),
         "deny", "F003",
         "軍師が足軽inboxに書き込み禁止。分析結果は老中に返せ。"),
        ("Write",
         lambda _, path: bool(re.search(r'queue/inbox/ashigaru', path)),
         "deny", "F003",
         "軍師が足軽inboxに書き込み禁止。分析結果は老中に返せ。"),
    ],
    "ohariko": [
        ("Edit",
         lambda _, path: not re.search(r'queue/inbox/(roju_ohariko|ohariko)', path)
                         and bool(re.search(r'queue/inbox/', path)),
         "deny", "OHARIKO_SCOPE",
         "お針子は自分のinbox以外のYAMLを書き換えるな。"),
    ],
}

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        sys.exit(0)  # fail-open

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    file_path = tool_input.get("file_path", "")

    agent_id = get_agent_id()

    # 全エージェント共通ルール
    all_rules = UNIVERSAL_RULES + ROLE_RULES.get(agent_id, [])

    for trigger, check_fn, decision, rule_id, reason in all_rules:
        if trigger != tool_name:
            continue
        target = command if tool_name == "Bash" else file_path
        if check_fn(target, file_path):
            log_violation(agent_id, rule_id, target, decision)
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": f"[{agent_id}] {reason}"
                }
            }
            print(json.dumps(out, ensure_ascii=False))
            return

if __name__ == "__main__":
    main()
```

### 2.3 settings.json hook設定

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/yasu/multi-agent-shogun/scripts/policy_checker.py",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "bash /home/yasu/multi-agent-shogun/scripts/gatekeeper_f006.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/yasu/multi-agent-shogun/scripts/policy_checker.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**二重防御**: policy_checker.py（fail-open）+ gatekeeper_f006.sh（fail-closed）。
どちらかが壊れても片方が機能する。温室三層構造の「下層が上層を黙らせる」原則。

### 2.4 Bloom Auto-Router v1（没日録類似検索ベース）

subtask_967の知見「subtask連続成功→effort降格」を実装:

```python
# scripts/bloom_router.py（老中のstep 6.5で呼び出し）
"""
Bloom Auto-Router v1: 没日録の類似タスク成功率でeffortを自動決定
"""
import subprocess, json

def route(description: str, bloom_level: int) -> str:
    """
    Returns: "low" | "medium" | "high" | "max"
    """
    # 没日録で類似タスクを検索
    result = subprocess.run(
        ["python3", "scripts/botsunichiroku.py", "search", description[:50]],
        capture_output=True, text=True, timeout=10
    )

    # 類似タスクが3件以上あり、全て成功 → 既知パターン → low
    # 類似タスクがあるが失敗あり → 要注意 → high
    # 類似タスクなし → 未知領域 → bloom_levelに従う
    lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
    similar_count = len(lines)

    if similar_count >= 3:
        # 既知パターン: CogRouterの「後半94.8%がL1に収束」
        return "low"
    elif similar_count >= 1:
        return "medium"
    else:
        # 未知領域: bloom_levelに従う
        if bloom_level <= 3:
            return "low"
        elif bloom_level <= 5:
            return "high"
        else:
            return "max"
```

### 2.5 Phase 1 変更ファイル一覧

| ファイル | 変更内容 | 行数（推定） | 新規/既存 |
|---|---|---|---|
| scripts/policy_checker.py | PreToolUseポリシーチェッカー | 90行 | **新規** |
| scripts/bloom_router.py | 自動Bloom Routing | 40行 | **新規** |
| .claude/settings.json | hook設定追記 | +20行 | 既存拡張 |
| logs/policy_violations.jsonl | 違反ログ（自動生成） | — | **新規（自動）** |
| **合計** | | **~150行** |

---

## 3. Phase 2: 高度統合

### 3.1 概要

| 項目 | 内容 |
|---|---|
| 変更対象 | 没日録DBスキーマ, お針子監査スクリプト, system prompt拡張 |
| 工数 | 軍師設計 + 足軽2-3名で2-3日 |
| 効果 | 品質の定量追跡、自動監査、適応的思考深度 |
| 前提 | Phase 0-1完了、policy_violations.jsonlにデータ蓄積 |
| 月額コスト | **ゼロ**（全てローカル処理） |

### 3.2 TraceRecordテーブル（没日録DB拡張）

```sql
-- data/botsunichiroku.db に追加
CREATE TABLE IF NOT EXISTS trace_records (
    trace_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL CHECK(phase IN ('preflight', 'runtime', 'postaudit')),
    agent TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK(verdict IN ('pass', 'warn', 'deny')),
    rule_id TEXT NOT NULL,
    target TEXT,
    subtask_id TEXT,
    cmd_id TEXT,
    timestamp TEXT NOT NULL,
    parent_trace_id TEXT,
    FOREIGN KEY (subtask_id) REFERENCES subtasks(subtask_id),
    FOREIGN KEY (parent_trace_id) REFERENCES trace_records(trace_id)
);

CREATE INDEX idx_trace_phase ON trace_records(phase);
CREATE INDEX idx_trace_agent ON trace_records(agent);
CREATE INDEX idx_trace_verdict ON trace_records(verdict);
```

**マイグレーション**: Phase 1のpolicy_violations.jsonlを一括インポート。

```python
# scripts/migrate_traces.py
import json, sqlite3
DB = "data/botsunichiroku.db"
LOG = "logs/policy_violations.jsonl"

conn = sqlite3.connect(DB)
# CREATE TABLE ... (上記)
with open(LOG) as f:
    for line in f:
        r = json.loads(line)
        conn.execute(
            "INSERT OR IGNORE INTO trace_records VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["trace_id"], r["phase"], r["agent"], r["verdict"],
             r["rule_id"], r.get("target"), None, None,
             r["timestamp"], None)
        )
conn.commit()
```

### 3.3 pass@1メトリクス自動計算

```sql
-- 没日録DBから計算
-- pass@1: 最初のsubmitでお針子PASSを通過した割合
SELECT
    strftime('%Y-%W', s.updated_at) as week,
    COUNT(CASE WHEN s.needs_audit = 1
               AND NOT EXISTS (
                   SELECT 1 FROM trace_records t
                   WHERE t.subtask_id = s.subtask_id
                   AND t.phase = 'postaudit'
                   AND t.verdict = 'deny'
               ) THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as pass_at_1_rate
FROM subtasks s
WHERE s.status = 'done'
GROUP BY week
ORDER BY week;
```

### 3.4 CogRouter模倣プロンプト（system prompt拡張）

subtask_967の知見「FTなし近似B」を採用:

```markdown
# instructions/ashigaru.md に追記（Phase 2）

## 認知深度の自己調整

タスクの各ステップで、以下の認知ルーティングを適用せよ:

<cognitive_routing>
- このステップは以前成功したパターンに類似しているか？
  → YES: 直接実行（深い思考不要）
- 失敗履歴のあるパターンか？
  → YES: 過去の失敗を振り返り、同じ轍を踏むな（think hard）
- 複数の選択肢があり、どれが正しいか不明か？
  → YES: 各選択肢のシミュレーションを行え（ultrathink）
- 上記のいずれにも該当しない場合:
  → 通常の深度で実行
</cognitive_routing>
```

**CogRouterとの対応**:
- 類似パターン → L1（本能的反応）
- 失敗履歴 → L3（経験統合）
- 選択肢シミュレーション → L4（戦略的計画）

### 3.5 TS-Flow方式のフィードバック注入

subtask_969の核心知見「止めずに誘導」を実装:

```python
# policy_checker.py Phase 2拡張: denyではなくfeedback注入
# L2（差止め）レベルの違反に対して

def feedback_response(agent_id, rule_id, reason):
    """TS-Flow方式: 止めずにフィードバックを注入し自己修正を促す"""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",  # 通過させるが...
            "additionalContext": (
                f"⚠️ ポリシー注意喚起 [{rule_id}]: {reason}\n"
                f"この操作は続行可能だが、報告時に以下を記載せよ:\n"
                f"  caution: \"{rule_id} - {reason}\"\n"
                f"意図的な操作であれば続行してよい。"
            )
        }
    }
```

**L1(切腹)はdeny、L2(差止め)はfeedback注入、L3(注意喚起)はallow+ログのみ。**

### 3.6 Verification Commands自動化

軍師のpredicted_outcomeを検証スクリプトに変換:

```yaml
# gunshi_analysis.yaml の predicted_outcome に追加（Phase 2）
verification_commands:
  - cmd: "test -f {path}"
    expect: "exit 0"
    type: goal_completion
    trace_rule: "VC_FILE_EXISTS"
  - cmd: "python3 -m pytest {test_path} -v --tb=short"
    expect: "passed"
    type: integrity
    trace_rule: "VC_TEST_PASS"
  - cmd: "git log --oneline -1 --format='%H'"
    expect: "matches report.commit_hash"
    type: compliance
    trace_rule: "VC_COMMIT_REAL"
```

お針子がこれを自動実行し、結果をTraceRecordに記録:

```bash
# お針子の監査スクリプト（Phase 2で自動化）
for vc in $(yq '.verification_commands[]' gunshi_analysis.yaml); do
    result=$(eval "$vc_cmd" 2>&1)
    if [[ $? -ne 0 ]]; then
        # TraceRecord: postaudit, deny
        python3 scripts/botsunichiroku.py trace add \
            --phase postaudit --verdict deny \
            --rule "$vc_trace_rule" --target "$vc_cmd"
    fi
done
```

### 3.7 Phase 2 変更ファイル一覧

| ファイル | 変更内容 | 行数（推定） | 新規/既存 |
|---|---|---|---|
| scripts/migrate_traces.py | jsonl→DB移行 | 30行 | **新規** |
| scripts/policy_checker.py | feedback注入 + L2/L3分岐 | +30行 | 既存拡張 |
| instructions/ashigaru.md | cognitive_routing追記 | +15行 | 既存拡張 |
| instructions/ohariko.md | verification_commands自動実行 | +20行 | 既存拡張 |
| data/botsunichiroku.db | trace_recordsテーブル | DDL | 既存拡張 |
| scripts/botsunichiroku.py | trace add/list/stats サブコマンド | +80行 | 既存拡張 |
| **合計** | | **~175行** |

---

## 4. Phase間のデータフロー全体図

```
Phase 0 (instructions)          Phase 1 (hooks+scripts)         Phase 2 (DB+自動化)
========================        ========================        ========================

足軽: Preflight Check           policy_checker.py               trace_records テーブル
  ↓ テキスト報告                  ↓ JSONL ログ                     ↓ SQL集計
"P1-FAIL: ファイル不在"          policy_violations.jsonl          pass@1, 違反率, 傾向
  ↓                               ↓                               ↓
老中: 判断                       老中: ログ確認                   ダッシュボード自動更新
  ↓                               ↓                               ↓
お針子: PC1-PC3手動チェック      お針子: ログ突合                  お針子: verification自動実行
                                                                   ↓
                                                                 TraceRecord連鎖追跡
                                                                 (preflight→runtime→postaudit)
```

**Phase 0で定めた「P1-FAIL」文字列規約が全Phaseを貫通する。**

---

## 5. リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| 過剰拒否で生産性低下 | 足軽が正当なタスクを拒否 | L2(差止め)とL3(注意喚起)を設け、L1のみ即停止 |
| policy_checker.pyの誤検知 | 正当なコマンドをブロック | fail-open設計 + gatekeeper_f006.shで二重防御 |
| 2ch移行との二重管理 | YAML前提の設計が陳腐化 | Phase 0-1はYAML/コマンドレベルの検査で2ch非依存 |
| effort固定による柔軟性低下 | 足軽が難タスクでlow effort | Phase 2のcognitive_routingで動的調整 |
| TraceRecord肥大化 | DBサイズ増加 | verdict=passはログしない。deny+warnのみ記録 |

---

## 6. 見落としの可能性

1. **hookチェーンの実行順序**: PreToolUseに複数hookを登録した場合の実行順序・fail時の挙動が未検証。policy_checker.pyがdenyを返した後、gatekeeper_f006.shは実行されるか？要テスト
2. **TMUX_PANE環境変数の継承**: hookスクリプトにTMUX_PANEが確実に渡されるか要検証。渡されない場合agent_id=unknownとなりrole別ルールが機能しない
3. **effort降格のフィードバックループ**: subtask連続成功→effort降格は「たまたま簡単だっただけ」のケースで危険。降格条件に「タスクの複雑さ（bloom_level）」も加味すべき
4. **お針子の18点ルーブリック**: 15→18点への変更は、過去の採点との比較可能性を損なう。正規化（パーセント表示）への切替も検討すべき
5. **足軽リサーチの知見で未反映**: subtask_969の「AEGIS Ed25519署名+監査ログ」は高度だが、マクガイバー精神にはやや過剰。Phase 3以降の検討に留める
6. **コンパクション時の拒否率変動**: arXiv:2512.02445の知見（長文脈で拒否率50%変動）への対策は、Phase 0のPreflight Checkでは不十分。コンパクション後のinstructions再読み込みが鍵

---

## 7. 実装依存グラフ

```
Phase 0                    Phase 1                    Phase 2
─────────────────────────────────────────────────────────────────
instructions変更 ──────┬── policy_checker.py ───────── TraceRecord DB
                       │       ↑                          ↑
effort_routing ────────┤── bloom_router.py ─────── cognitive_routing
                       │                                  ↑
ルーブリック拡張 ──────┴── settings.json hooks ──── verification自動化
                                 ↑
                       gatekeeper_f006.sh（既存）
```

**クリティカルパス**: Phase 0 → Phase 1のpolicy_checker.py → Phase 2のTraceRecord DB

---

## north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    Phase 0-2の一貫設計で、各Phaseが加算的に機能し前Phaseを破壊しない。
    温室三層構造（爆発→ガムテ→知恵）を忠実に踏襲。
    月額コストゼロ、全てローカルPython/Bash。マクガイバー精神に合致。
  risks_to_north_star:
    - "Phase 0の過剰拒否: 閾値調整に1-2週間の運用データが必要"
    - "Phase 1→2のマイグレーション: jsonl→DBの変換は単純だが、データ欠損リスクあり"
    - "2ch移行との時系列衝突: 2ch全面置換とPhase 1を同時進行すると混乱する恐れ"
```

## skill_candidate

```yaml
skill_candidate:
  name: "phase-consistent-design"
  description: "Phase 0-N の加算的設計テンプレート。各Phaseの非破壊性保証+データモデル貫通+依存グラフを含む"
```
