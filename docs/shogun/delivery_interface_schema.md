# 納品インターフェーススキーマ定義

> **対象アーキテクチャ**: v4.0 三階建て（§2.1, §3.2準拠）
> **作成**: subtask_1079 / cmd_490

---

## 概要

1F支店（足軽）から2F合議場（検収板）への納品、および2F合議場からkenshu_gateへの判定投稿、それぞれのYAMLフォーマットを定義する。

**型付け方針（§3.2より）**: 1F→2F納品IFは**厳格**。不完全な納品をスキーマ検証で弾く。2F内合議は自由。2F→kenshu_gate判定は**厳格**。

---

## A. 検収板への納品フォーマット（1F → 2F）

BBS検収板へのスレ立て時、`body`フィールドに以下のYAMLを埋め込む。

```yaml
# 1F→2F 納品フォーマット v1.0
subject: "subtask_{XXXX} 納品: {1行サマリ}"  # スレタイ
body: |
  subtask_id: subtask_XXXX      # 必須 | string | 例: subtask_1079
  cmd_id: cmd_YYY               # 必須 | string | 例: cmd_490
  worker: ashigaru1             # 必須 | string | 担当足軽のagent_id
  branch: worktree-subtask-XXXX # 必須 | string | 作業worktreeブランチ名
  diff_summary:                 # 必須 | object
    files_changed: 3            #   変更ファイル数 (integer ≥ 0)
    insertions: 120             #   追加行数 (integer ≥ 0)
    deletions: 45               #   削除行数 (integer ≥ 0)
  test_result:                  # 必須 | object
    status: PASS                #   PASS / FAIL の2値 (string)
    count: 12                   #   テスト件数 (integer ≥ 0)
    coverage: "82%"             #   カバレッジ (string | null — テスト不要な変更はnull可)
  commit_hash: abc1234          # 必須 | string(7文字以上) | 最終コミットハッシュ
  self_review: |                # 必須 | string | 自己レビューコメント（1行以上）
    設計書§X.Yを読んで実装。要件Aは対応済み。
    懸念: Bの境界値テストは未実施。
```

### フィールド仕様

| フィールド | 必須/任意 | 型 | 制約 | 備考 |
|-----------|:--------:|-----|------|------|
| `subtask_id` | **必須** | string | `subtask_\d+` 形式 | 没日録DBのsubtask_idと一致 |
| `cmd_id` | **必須** | string | `cmd_\d+` 形式 | 親コマンドID |
| `worker` | **必須** | string | 登録済みagent_id | ashigaru1, ashigaru2, ashigaru6等 |
| `branch` | **必須** | string | `worktree-subtask-\d+` 形式 | mainブランチ禁止 |
| `diff_summary.files_changed` | **必須** | integer | ≥ 0 | |
| `diff_summary.insertions` | **必須** | integer | ≥ 0 | |
| `diff_summary.deletions` | **必須** | integer | ≥ 0 | |
| `test_result.status` | **必須** | enum | `PASS` / `FAIL` | |
| `test_result.count` | **必須** | integer | ≥ 0 | |
| `test_result.coverage` | 任意 | string \| null | 例: `"82%"` | テスト不要な変更（docs等）はnull |
| `commit_hash` | **必須** | string | 7文字以上の16進数 | git log実在確認必須（PC3） |
| `self_review` | **必須** | string | 1行以上 | 要件との対応・懸念事項を記載 |

### 検収板への投稿例（完成形）

```
[スレタイ] subtask_1079 納品: 納品IFスキーマ定義 delivery_interface_schema.md

subtask_id: subtask_1079
cmd_id: cmd_490
worker: ashigaru2
branch: worktree-subtask-1079
diff_summary:
  files_changed: 1
  insertions: 120
  deletions: 0
test_result:
  status: PASS
  count: 0
  coverage: null
commit_hash: 572b2d7
self_review: |
  v4_three_story_architecture.md §2.1・§3.2を読み設計。
  A・B両フォーマットを厳格型で定義。Bloom別ファストトラック記載済み。
```

---

## B. kenshu_gate 判定フォーマット（2F → 3F）

合議完了後、kenshu_gate板に判定結果をPOSTする。老中がこれを読み取り、マージまたは差し戻しを実行する。

```yaml
# kenshu_gate 判定フォーマット v1.0
subtask_id: subtask_XXXX        # 必須 | string | 対象subtask
cmd_id: cmd_YYY                 # 必須 | string | 対象コマンド
verdict: PASS                   # 必須 | enum | PASS / FAIL / CONDITIONAL の3値
reviewers:                      # 必須 | list<string> | 合議参加者（minimum_reviews: 2）
  - ohariko
  - gunshi
minimum_reviews: 2              # 必須 | integer | 最低参加者数。未達は自動FAIL扱い
summary: "全要件充足。テスト12件PASS。懸念事項なし。"  # 必須 | string | 判定理由1行
findings:                       # 任意 | list<string> | 指摘事項詳細（FAIL/CONDITIONALは必須）
  - "L.42: foo()の境界値テスト不足"
tiebreaker: null                # 任意 | string | タイブレーカー発動時の老中裁定理由
```

### フィールド仕様

| フィールド | 必須/任意 | 型 | 制約 | 備考 |
|-----------|:--------:|-----|------|------|
| `subtask_id` | **必須** | string | `subtask_\d+` 形式 | |
| `cmd_id` | **必須** | string | `cmd_\d+` 形式 | |
| `verdict` | **必須** | enum | `PASS` / `FAIL` / `CONDITIONAL` | |
| `reviewers` | **必須** | list | agent_id の配列 | |
| `minimum_reviews` | **必須** | integer | ≥ 2 | 未達時はverdictを無効化し老中裁定へ |
| `summary` | **必須** | string | 1行 | 老中が最初に読む要約 |
| `findings` | FAIL/CONDITIONAL時**必須** | list | 具体的指摘（ファイル・行・内容） | PASSでも良点記録は推奨 |
| `tiebreaker` | 任意 | string \| null | | お針子PASS+軍師FAIL等の裁定根拠 |

### verdict 判定基準

| verdict | 意味 | 老中アクション |
|---------|------|----------------|
| `PASS` | 合格。マージ可 | `git merge` → 没日録DB記録 |
| `FAIL` | 不合格。差し戻し | 任務板にリジェクト通知POST → 1Fに差し戻し |
| `CONDITIONAL` | 条件付き合格。軽微修正後マージ可 | 老中が修正してマージ |

### タイブレーカールール（§2.1より）

お針子（品質18点）と軍師（戦略的妥当性）は評価軸が異なるため、判断が食い違うことがある。

| ケース | 処理 |
|--------|------|
| お針子PASS + 軍師PASS | `verdict: PASS` |
| お針子FAIL + 軍師FAIL | `verdict: FAIL` |
| お針子PASS + 軍師FAIL | → **老中裁定**。`tiebreaker`フィールドに理由を記載 |
| お針子FAIL + 軍師PASS | → **老中裁定**。`tiebreaker`フィールドに理由を記載 |

> **原則**: タイブレーカーは「誰が偉いか」の問題ではない。「評価軸が違う」から生じる矛盾を老中が文脈判断する。

---

## Bloom別検収ファストトラック

| Bloomレベル | 検収方式 | 合議参加者 | kenshu_gate writer |
|------------|--------|----------|-------------------|
| L1-L3 | **ファストトラック** | 老中スポットチェックのみ（2F合議スキップ） | 老中 |
| L4-L6 | **フル合議** | お針子 + 軍師（+ 必要に応じ軍師板議論） | お針子 or 軍師 |

> L1-L3ファストトラックでは、B.フォーマットの`reviewers`は`[roju]`のみで可。`minimum_reviews`は1に緩和。

---

## フロー全体図

```
1F足軽
  └─ worktreeで実装 → git commit → BBS検収板にPOST（フォーマットA）
         ↓
2F合議場（検収板）
  └─ お針子・軍師が合議（BBSレス自由） → kenshu_gateにPOST（フォーマットB）
         ↓
3F本店（老中）
  ├─ PASS      → git merge → 没日録DB記録
  ├─ FAIL      → 任務板にリジェクト通知 → 1F差し戻し
  └─ CONDITIONAL → 老中が軽微修正 → git merge → 没日録DB記録
```

---

## 関連ドキュメント

- `docs/shogun/v4_three_story_architecture.md` — 三階建てアーキテクチャ全体設計
- `docs/shogun/v4_three_story_architecture.md §2.1` — 合議フロー・タイブレーカー・Bloom別ファストトラック
- `docs/shogun/v4_three_story_architecture.md §3.2` — 通信の型付け戦略
