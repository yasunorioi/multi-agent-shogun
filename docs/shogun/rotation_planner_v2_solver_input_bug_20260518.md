# rotation-planner v2: ソルバー入力R9計画反映バグ調査 (cmd_583 Wave 1)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1251 / cmd_583 |
| 作成日時 | 2026-05-18T16:34 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象ファイル | /var/www/rotation-planner-v2/app/frontend/app/src/lib/rotationSolver.js (415行) |
| 報告書範囲 | read-only調査+設計のみ (実装は別cmd判断) |
| 関連 | cmd_581 subtask_1250 (R9表示修正完了)・本cmd_583は構造的後続バグ |

---

## §1 エグゼクティブサマリ

**症状**: 殿が手動入力したR9計画を**ソルバーが無視し別作物提案**。cmd_581 subtask_1250 の fallback は**表示専用**でソルバー入力には未反映。

**判定**: **B = 既存機能で対応不可** (要 軍師L5-L6設計依頼)

**根拠**:
- ソルバーは `plan` を**空オブジェクトから計算開始** (rotationSolver.js:260)
- `field.history` は **過去年判定の制約計算用** のみ (L78, L140, L190)
- 未来年plan固定機能 (pinned/locked/fixed) → **実装なし**
- 既存制約テーブル (crop_constraints/user_constraints) → 量制約・transition制約のみ・**特定field×year×crop固定機能なし**
- 既存制約API (`/api/constraints` GET/PUT) → 上記2テーブルの拡張のみ

**推奨アクション**: 
- **別cmd_584 起票 (軍師依頼)** で「特定field×year×crop固定制約」設計
- 案候補3つ提示 (§5)

**殿への質問** (3問以内・家老指示):
- Q1: 別cmd_584 起票 (軍師依頼)・承認可否?
- Q2: 設計案 (1/2/3) のうちどの方向を軍師に依頼するか?
- Q3: 当面ソルバー実行回避 (殿手動運用継続) → cmd_584完了後の本格実装まで pending で良いか?

---

## §2 Phase 1 ソルバー実装精読結果

### ファイル構造
- `rotationSolver.js` 415行・export RotationSolver class + createDefaultConstraints + generateResultTables
- 主要メソッド: getLastNCrops, checkGapConstraint, checkTransitionConstraint, getValidCrops, calculateYearStats, checkCapConstraint, checkFieldCountConstraint, calculateTransitionScore, calculateGapBonus, evaluateSolution, solve (推定)

### plan vs history の役割

```javascript
// rotationSolver.js:71-82 getLastNCrops()
for (let i = 1; i <= n; i++) {
  if (yearIdx - i >= 0) {
    const prevYear = this.allYears[yearIdx - i];
    if (this.pastYears.includes(prevYear)) {
      cropsList.push(this.fields[fieldIdx].history[prevYear] || UNKNOWN_MARKER);  // ★過去年=history
    } else {
      cropsList.push(plan[`${fieldIdx},${prevYear}`] || UNKNOWN_MARKER);          // ★未来年=plan (計算中の解)
    }
  }
}
```

**観察**:
- 過去年判定: history (DB crop_history) を読む
- 未来年判定: **plan (計算途中の解候補)** のみ・**history を未来年として読まない**
- → ソルバーは「ユーザー手動入力の未来年計画」を制約として認識する手段がない

### ソルバーの本体 (solve loop 推定)

```javascript
// rotationSolver.js:260+ (solve関数の冒頭)
const plan = {};  // ★空のオブジェクトから計算開始
...
let validCrops = this.getValidCrops(fieldIdx, year, plan);  // valid crop 列挙
// → 制約に基づいて最良 crop 選択
```

**観察**:
- `plan = {}` で開始 → **過去のhistory入力は反映されない**
- ソルバーは「自由解探索」モードでスタート

### grep結果

| キーワード | 件数 | 検出箇所 |
|---|---|---|
| plan | 39件 | 計算ロジック内 (制約評価・最適化) |
| history | 5件 | 過去年判定のみ (L78, L140, L190) + L386/L402 (subtask_1250修正・表示専用) |
| **pinned / fixed / lock / manual / user.input** | **0件** | **実装なし** |
| constraint | 多数 | forbiddenTransitions/preferredTransitions/cropMins/cropCaps/minFields/maxFields/minGapYears/mainCrops/unknownMode の 9種類のみ |

---

## §3 Phase 2 既存制約機能 schema+grep結果

### crop_constraints schema
```sql
CREATE TABLE crop_constraints (
    id, user_id, crop, cap_ha, min_ha, min_gap_years, min_fields, max_fields, created_at
);
-- UNIQUE(user_id, crop)
```
→ **作物別の量制約のみ** (特定年×特定field 固定なし)

### user_constraints schema (yasu の現状)
```sql
CREATE TABLE user_constraints (
    id, user_id, constraints_json, forbidden_transitions, preferred_transitions, main_crops, created_at, updated_at
);
-- UNIQUE(user_id)
```

yasu の constraints_json (既に設定済):
```json
[
  {"crop": "春小麦", "min_ha": 0, "cap_ha": 8, "min_gap_years": 4, ...},
  {"crop": "秋小麦", "cap_ha": 8, "min_gap_years": 4, ...},
  {"crop": "大豆", "cap_ha": 12, "min_gap_years": 4, ...},
  ...
]
forbidden_transitions: "春小麦->秋小麦,秋小麦->春小麦"
```
→ **ユーザー全体の制約のみ・特定field×year×crop固定機能なし**

### rotation_plans + plan_details
```sql
CREATE TABLE rotation_plans (id, user_id, name, start_year, end_year, constraints_json, metadata_json, ...);
CREATE TABLE plan_details (id, plan_id, field_id, year, crop, ...);
-- plan_details UNIQUE(plan_id, field_id, year)
```
→ **「ソルバー出力結果の保存先」用途** (start_year/end_year 名前付き計画)
→ 「事前計画→ソルバー初期解」用途には**現状使われていない**

### constraint API (plans.py:137-)
- `GET /api/constraints` → user_constraints返却
- `PUT /api/constraints` → user_constraints更新
- **field×year×crop 単位の制約API なし**

### crop_history 参照箇所 (frontend全体)
- `rotationSolver.js`:
  - L140 (calculateYearStats 過去年判定)
  - L386 (fieldTable 過去年 row[year])
  - **L388 (fieldTable 未来年 fallback・subtask_1250)** ← 表示のみ
  - L402 (summary 過去年)
  - **L404 (summary 未来年 fallback・subtask_1250)** ← 表示のみ
- `Rotation.jsx`:
  - L86/L89/L92 (loadHistories で fieldHistories state構築)
- `DataManagement.jsx`:
  - L206 (CSV download時のファイル名のみ)

### pin/lock/fix grep (frontend全体)
- `pinned / fixed_crop / lockYear / manualOverride` → **全て 0件** (実装なし)

---

## §4 判定: B = 既存機能で対応不可

### 既存機能で何が出来るか
- ✓ ユーザー全体の制約 (作物別の量・transition)
- ✓ 過去年(history)を踏まえた制約評価
- ✓ ソルバー出力後の保存 (rotation_plans + plan_details)
- ✓ 表示時の plan>history fallback (subtask_1250)

### 既存機能で何が出来ないか
- ✗ **特定field×year×crop の固定制約** ← 殿が手動R9計画した内容を「変更不可」とソルバーに認識させる手段
- ✗ **plan の初期値設定** ← ソルバー実行前に「ここはR9 飼料作物」と設定する手段
- ✗ **history の未来年経路** ← ソルバーは過去年でしか history を見ない

### 必要な機能 (実装案・§5で詳述)
- 新規制約タイプ「pinned_assignments」: (field_id, year, crop) tuple list
- ソルバー入力に pinned_assignments を渡す
- ソルバー初期化時に plan に pinned_assignments を pre-fill
- 計算ループで pinned セルは変更不可とする

→ 軍師L5-L6 設計依頼必須 (新規制約タイプ設計+API設計+ソルバーアルゴリズム改修+UI入力経路)

---

## §5 修正案 (B判定: 別cmd_584 起票案)

### 案1: 既存テーブル流用 (最小変更・推奨)
- **rotation_plans + plan_details** を「事前計画 = ユーザー手動入力」として使用 (現状: ソルバー出力後の保存先)
- ほ場一覧UI が R9計画入力時に POST `/api/plans` (新規プラン作成) or 既存プラン update
- ソルバー実行時に plan_details を読み込んで plan 初期値として pre-fill
- UI: 「事前計画あり」表示+「ソルバーで補完」モード追加

**長所**: 既存テーブル流用・schema変更最小
**短所**: rotation_plans は本来「ソルバー出力の名前付きスナップショット」用途・semantic重複

### 案2: 新規 pinned_assignments テーブル追加
```sql
CREATE TABLE pinned_assignments (
    id, user_id, field_id, year, crop, pinned_at, ...
);
```
- 新規API: GET/POST/DELETE `/api/pinned-assignments`
- ソルバー入力に pinned_assignments 渡す
- ほ場一覧UIで pin/unpin 切り替え

**長所**: semantic明確・将来拡張容易 (pin解除/期限付き pin等)
**短所**: 新規テーブル+API+UI+ソルバー改修・工数大

### 案3: crop_history 拡張 (is_pinned カラム追加)
```sql
ALTER TABLE crop_history ADD COLUMN is_pinned INTEGER DEFAULT 0;
```
- 殿が手動入力したcrop_history行は is_pinned=1
- ソルバーが crop_history WHERE is_pinned=1 を pin として読む
- 過去年=history既存・未来年=is_pinned=1のhistory行 を pin

**長所**: テーブル追加なし・既存crop_historyに統合
**短所**: crop_history のsemantic肥大 (履歴 vs 計画 vs pinned 計画 混在)

### 推奨: 案2 (新規 pinned_assignments)
- semantic分離・将来 plan_details との連携も clean
- 但し**軍師の判断**で案1/3 採用可・本subtaskは推奨提示まで

### rollback (案2採用時)
- DROP TABLE pinned_assignments
- ソルバー改修部分は git revert

---

## §6 殿への質問 (3問以内・家老指示)

| # | 質問 |
|---|---|
| **Q1** | 別cmd_584 起票 (軍師L5-L6設計依頼) 承認可否? (軍師に「特定field×year×crop固定制約」設計を依頼) |
| **Q2** | 設計案1/2/3 のうち、軍師に**どの方向**を依頼するか? (推奨: 案2 pinned_assignments・但し軍師判断で1/3も可) |
| **Q3** | 当面の運用: ソルバー実行を回避し殿手動運用継続でよいか? それともcmd_584完了まで何か暫定回避策(例: 表示専用のヒント追加等)を別subtask起票するか? |

### 補足: cmd_581 subtask_1250 fallback との関係
- subtask_1250 の fallback は **表示専用** (plan>history) で構造的解決ではなかった
- ソルバー実行後は plan 優先 → 殿手動R9計画 (history) が plan で上書き
- → cmd_583 で構造的バグ確認・軍師依頼での本格修正へ移行

---

## 付録: 実行コマンド一覧 (read-only・F006継続)

```bash
# Phase 1 ソルバー精読
sudo -u webapp wc -l /var/www/.../rotationSolver.js
sudo -u webapp head -100 /var/www/.../rotationSolver.js
sudo -u webapp grep -nE "plan|history|fixed|lock|pinned|manual|constraint" /var/www/.../rotationSolver.js
sudo -u webapp grep -nE "constrain|require|must|cannot|forbid" /var/www/.../rotationSolver.js
sudo -u webapp grep -nE "^export|function solve|class.*Solver" /var/www/.../rotationSolver.js

# Phase 2 schema精読
sudo -u webapp sqlite3 $DB ".tables"
sudo -u webapp sqlite3 $DB ".schema crop_constraints"
sudo -u webapp sqlite3 $DB ".schema user_constraints"
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM user_constraints WHERE user_id=6;"
sudo -u webapp sqlite3 $DB ".schema rotation_plans"
sudo -u webapp sqlite3 $DB ".schema plan_details"

# Phase 2 frontend+API grep
sudo -u webapp grep -rnE "crop_history|histories\[|field\.history" .../frontend/app/src/lib/ .../pages/
sudo -u webapp grep -rnE "constraint|/api/constraints" .../api/routers/
sudo -u webapp grep -nE "constraint|pinnedCrop|fixedCrop|手動|lockYear" .../Rotation.jsx
sudo -u webapp grep -rnE "pinned|fixed_crop|lockYear|manualOverride" .../frontend/app/src/
```

書き込み・サービス操作・ファイル変更は一切なし。

---

(cmd_583 Wave 1 判定B確定・別cmd_584 軍師依頼起票判断は殿承認待ち)
