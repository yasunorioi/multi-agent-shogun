---
name: audit
description: >
  Use when: (1) お針子がsubtaskの成果物を監査する時、(2) 老中が監査依頼を発行した時、
  (3) 足軽のコミットを18点ルーブリック(品質15点+ポリシー3点)で採点する時、(4) /audit コマンドが呼ばれた時。
  NOT for: コードレビュー以外の一般的なファイル確認。
allowed-tools: Bash(git *), Bash(python3 scripts/botsunichiroku.py *)
---

# audit - Skill Definition

**Skill ID**: `audit`
**Trigger**: `/audit`
**Category**: Quality Assurance / Code Review
**Version**: 1.1.0
**Created**: 2026-03-11

---

## Overview

足軽のsubtask成果物を18点ルーブリック（品質5観点15点 + ポリシー準拠3点）で採点し、監査レポートを出力する。
お針子が毎回ルーブリックを説明し直す問題を解消するための統一スキル。

**合格基準**: 15点以上 → `approved` / 10-14点 → `rejected_trivial` / 9点以下 → `rejected_judgment`

---

## Use Cases

- 足軽のコミット成果物を監査する
- 老中が監査依頼を発行する際の標準フロー
- お針子が先行割当タスクを監査する際の手順書

---

## Skill Input

以下のいずれかを引数として受け取る:

```
/audit <subtask_id> [commit_hash] [repo_path]
/audit subtask_XXX abc1234 /path/to/repo
```

引数なしの場合は、以下の順でコンテキストから自動推定:
1. `queue/inbox/roju_ohariko.yaml` の直近未読監査依頼
2. `queue/inbox/roju_reports.yaml` の直近未読完了報告

## Pre-injected Context (Shell Interpolation)

以下の情報はスキル発火時に自動取得され、プロンプトに埋め込まれる:

### 直近コミット情報
```
!`git log --oneline -5`
```

### 直近の変更差分サマリ
```
!`git diff --stat HEAD~1 HEAD`
```

### 未読の監査依頼（あれば）
```
!`python3 scripts/botsunichiroku.py audit list --status pending 2>/dev/null | head -10`
```

### 直近の完了報告
```
!`grep -A5 'status: notification' queue/inbox/roju_reports.yaml 2>/dev/null | tail -12`
```

---

## Implementation Steps

### Step 1: 入力パース

```bash
# 引数またはYAMLからsubtask_id・commit_hash・repo_pathを取得
subtask_id="subtask_XXX"   # 必須
commit_hash="<hash>"        # 省略可（報告書から取得）
repo_path="."               # 省略可（デフォルト: カレント）
```

roju_reports.yaml から commit_hash を探す場合:
```bash
# 没日録CLI経由で報告詳細を取得
python3 scripts/botsunichiroku.py report list --subtask subtask_XXX --json
# → summary/detail_ref フィールドにコミット番号が記載されている
```

### Step 2: コミット実在確認

commit_hash が指定された場合は Bash ツールで確認。指定なし（HEADデフォルト）の場合は上記
Pre-injected Context の「直近コミット情報」（`!`git log --oneline -5`` の出力）を参照せよ。

```bash
cd <repo_path>
git log --oneline <commit_hash> 2>/dev/null | head -1
# 出力なし → 即FAIL（コミット不在）
```

**コミット不在の場合**: 以下を出力して監査終了:
```yaml
audit:
  subtask_id: subtask_XXX
  commit: <hash>
  score: 0/18
  verdict: FAIL
  findings: "コミット <hash> が存在しない。作業未完了の可能性。"
```

### Step 3: 変更差分レビュー

commit_hash 指定なし（HEADデフォルト）の場合は上記 Pre-injected Context の
「直近の変更差分サマリ」（`!`git diff --stat HEAD~1 HEAD`` の出力）を活用せよ。
全差分が必要な場合は Bash ツールで取得:

```bash
git diff <commit_hash>~1 <commit_hash>
# マージコミットの場合: git show <commit_hash>
```

確認すべき点:
- 変更ファイル一覧（`git diff --name-only`）
- 追加/削除行数
- インラインコメント・命名規則
- 意図しないファイル（`.env`, `*.pyc`, `node_modules/` 等）の混入

### Step 4: テスト実行

```bash
# pytest が使えるか確認
cd <repo_path>
if [ -f pytest.ini ] || [ -f setup.cfg ] || [ -d tests/ ]; then
    python -m pytest --tb=short 2>&1 | tail -20
else
    echo "テストなし → testsスコアは判定による"
fi
```

テストが存在しない場合: `tests` カテゴリは以下で判定:
- 「テスト不要な変更（設定ファイル・ドキュメント）」→ 3点
- 「実装コードの変更だがテストなし」→ 2点（殿の「テストは書け」原則より）

### Step 5: 18点ルーブリック採点

5カテゴリ × 3点満点 = 15点（品質） + ポリシー準拠3点(PC1-PC3) = **18点満点**

| カテゴリ | 3点（PASS） | 2点（MINOR） | 1点（FAIL） |
|---------|------------|-------------|------------|
| **correctness**（正確性） | 要件通り動作。インボックスの `description` と一致 ※1 | 軽微な不備あり。動作はする | 要件未達。主要機能が動かない |
| **tests**（テスト） | テスト全PASS / テスト不要な変更 | 一部スキップ or 警告あり | テスト失敗 / 実装コードに対しテスト未実装 |
| **code_quality**（品質） | 可読性・命名良好。殿の「シンプル志向」に沿う | 軽微な改善余地（命名・コメント等） | 保守困難。過剰抽象化・意味不明命名・重複コード |
| **completeness**（完全性） | 全要件カバー。`notes` の全指示を実施 | 一部未対応（軽微） | 主要要件欠落 |
| **no_regressions**（回帰なし） | 既存機能への影響なし | 軽微な副作用（動作には影響しない） | 既存機能を破壊 |

#### ポリシー準拠（+3点）

| カテゴリ | 1点（PASS） | 0点（FAIL） |
|---------|------------|------------|
| **PC1**（F001-F006違反なし） | git diff + コミット内容にポリシー違反コマンドがない | 違反あり |
| **PC2**（権限境界遵守） | 自分のinbox以外のYAMLを書き換えていない | 逸脱あり |
| **PC3**（報告真正性） | 報告内のcommitハッシュをgit logで実在確認 | ハッシュ不在/不一致 |

> PC3は特に重要: cmd_284-300ハルシネーション事故の再発防止。

> ※1 **「動けば合格」原則（correctness 3点）**: コードの美しさ・アーキテクチャの洗練は評価対象外。
> 動作し、要件を満たし、既存を壊さなければ3点。過剰に厳しく採点しない。

**殿の判断基準（採点時に参照）**:
- 「動けば合格」: correctness 3点の条件を厳しくしすぎない
- 「過剰設計は不合格」: code_quality で抽象化過多・設定項目多すぎは減点
- 「テストは書け」: 実装変更にテストなしは tests 2点以下
- 「ドキュメントは最小限」: ドキュメント過多で実装が薄い場合は completeness 減点

#### Few-shot Examples（判定例）

**事例A — 17/18 approved**: subtask_786（ルール2ピタゴラスイッチ書き換え）
- correctness(3): 温度段階・ch番号・緊急停止ライン全て殿指定と完全一致
- code_quality(3): rule_engineとの整合性旧版より向上 / completeness(3): 全要件カバー
- no_regressions(3): commit acb9056・push確認済み / tests(2): 軽微な懸念1点減
→ **要件完全充足・証跡あり → 典型的合格例**

**事例B — 13/18 rejected_trivial**: subtask_755（OpenAI SDK互換化）
- correctness(3): SDK差し替え全形式正確、pytest 455件PASS
- code_quality(2)/completeness(2)/no_regressions(2)/tests(2): 空行重複1箇所が複数カテゴリに波及
→ **動作・要件充足だが書式軽微問題 → 空行削除のみで再提出可能**

**事例C — 6/18 rejected_judgment**: subtask_829（統合テスト）
- correctness(2): bloom_router.sh 16件PASSはお針子実機確認済み
- completeness(1)/no_regressions(1)/tests(0): コミットなし・report addなし・証跡ゼロ
→ **実装は動くが証跡完全欠落 → エビデンス再整備が必要**

**事例D — 17/18 approved**: subtask_986（archive昇格+nginx修正）
- correctness(3): archive昇格ロジック・nginx設定修正が要件通り動作。全機能確認済み
- code_quality(3): INSERT OR REPLACEによる冪等設計。再実行安全
- completeness(3): 全要件カバー / no_regressions(3): 既存機能への影響なし
- tests(2): テスト一部懸念あり（1点減）
→ **冪等設計・証跡完備 → 高スコア合格の典型例**

**事例E — 13/18 approved（合格下限）**: subtask_952（雑談板+thread_replies追加、148行）
- correctness(3): 雑談板新規作成・thread_replies動作確認済み
- code_quality(2): 148行実装。可読性は良好だが軽微な改善余地
- completeness(2): 一部要件対応漏れあり / no_regressions(3): 既存機能への影響なし
- tests(1): 実装コードに対しテスト未実装（殿「テストは書け」原則 → 2点未満）
→ **動作・要件はほぼ充足だが合格下限 → テスト不足が減点主因**

**事例F — 13/18 approved（合格下限）**: subtask_953（DATサーバー新規681行）
- correctness(3): DAT形式変換・配信機能が要件通り動作。標準ライブラリのみで実装
- code_quality(3): 681行の大規模実装だが標準ライブラリのみ使用（殿の「シンプル志向」合致）
- completeness(2): 主要要件カバー済みだが一部対応漏れ / no_regressions(2): 軽微な副作用
- tests(1): 大規模新規実装に対しテスト未実装
→ **標準ライブラリ限定は加点評価だがテスト不足が足を引く → 合格下限**

> **※ rejected事例0件注記（2026-03-26時点）**: 現行監査記録において rejected（10点未満）の事例は0件。
> 全件が approved（合格圏内10点以上）に収まっている。現行基準が甘い可能性がある。
> 今後のrejected事例蓄積に備え、採点基準の厳格化・再調整を検討されたし。

### Step 6: 監査レポート出力

```yaml
audit:
  subtask_id: subtask_XXX
  commit: <hash>
  score: XX/18
  breakdown:
    correctness: X      # 1-3
    tests: X            # 1-3
    code_quality: X     # 1-3
    completeness: X     # 1-3
    no_regressions: X   # 1-3
    pc1_policy: X       # 0-1
    pc2_boundary: X     # 0-1
    pc3_authenticity: X # 0-1
  verdict: PASS         # 15点以上=PASS / 10-14=rejected_trivial / 9以下=rejected_judgment
  findings: "具体的な指摘事項。合格ならば特記事項なし、または良かった点。"
```

**verdict の対応**（ohariko.md の監査フォーマットとの対応）:

| スコア | verdict（スキル内） | result（高札API/YAML） |
|-------|-------------------|----------------------|
| 15-18点 | PASS | `approved` |
| 10-14点 | CONDITIONAL_PASS | `rejected_trivial`（軽微な修正で合格可能） |
| 1-9点 | FAIL | `rejected_judgment`（根本的な問題） |

### Step 7: 15点未満の場合 — 修正指示

`rejected_trivial` または `rejected_judgment` の場合、findings に以下を含める:

```
## 修正要求
- ファイル: <path/to/file.py>
  行: <line_number>
  問題: <具体的な問題>
  修正案: <具体的な修正方法>

- ファイル: <path/to/other_file.py>
  行: <line_number>
  問題: <具体的な問題>
  修正案: <具体的な修正方法>
```

抽象的な「改善してください」は禁止。「何のファイルの何行目をどう直す」まで記載すること。

### Step 8: 高札API登録

```bash
python3 scripts/botsunichiroku.py subtask update subtask_XXX --audit-status done
# approved → --audit-status done
# rejected_trivial/rejected_judgment → --audit-status rejected（YAMLにfindings記載）
# 失敗時: → Step 8をスキップしてStep 9へ（YAMLにインライン記載）
```

`result` の値: `approved` / `rejected_trivial` / `rejected_judgment`

### Step 9: roju_ohariko.yaml へ報告

```bash
# ファイルを Read してから Edit で追記
Read queue/inbox/roju_ohariko.yaml
```

```yaml
# 追記内容（audit_reports リストの末尾に追加）
  - subtask_id: subtask_XXX
    summary: "監査合格(17/18): correctness・completeness完全。コード品質良好。PC1-PC3全PASS。"
    detail_ref: "python3 scripts/botsunichiroku.py audit list --subtask subtask_XXX"
    timestamp: "YYYY-MM-DDTHH:MM:SS"   # date "+%Y-%m-%dT%H:%M:%S" で取得
    read: false
```

高札ダウン時のフォールバック（`detail_ref` の代わりに `findings` をインライン記載）:
```yaml
  - subtask_id: subtask_XXX
    summary: "監査合格(17/18)"
    findings: |
      correctness: 3, tests: 3, code_quality: 2, completeness: 3, no_regressions: 3
      軽微: foo.py L42 命名改善余地あり
    timestamp: "YYYY-MM-DDTHH:MM:SS"
    read: false
```

---

## Quick Reference

```
/audit subtask_XXX [hash] [repo]

Step 1: パース（subtask_id / commit / repo）
Step 2: git log --oneline <hash>（不在→即FAIL）
Step 3: git diff <hash>~1 <hash>
Step 4: pytest（なければスキップ）
Step 5: 5カテゴリ×3点 + PC1-PC3×1点 = 18点採点
Step 6: YAMLレポート出力
Step 7: 15点未満→修正指示（ファイル・行・修正案）
Step 8: subtask update --audit-status
Step 9: Edit queue/inbox/roju_ohariko.yaml
```

---

## Score Reference

```
18点: 完璧。褒めてよい。
17点: 優秀。合格。
15点: 合格ライン。
14点: rejected_trivial（軽微な修正で合格）
10-13点: rejected_trivial（複数の軽微な問題）
9点以下: rejected_judgment（根本的な問題。再実装レベル）
0点: コミット不在 or 全要件未達
```

---

## Notes

- **スキルネスト禁止**: このSKILL.mdは単独で完結。他スキルを呼び出さない
- **口調**: スキル手順書のためペルソナ強制なし。お針子のツンデレ口調は任意
- **タイムスタンプ**: `date "+%Y-%m-%dT%H:%M:%S"` で取得。推測禁止
- **Read before Edit**: roju_ohariko.yaml は必ずReadしてからEditすること
