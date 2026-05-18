# rotation-planner v2: ほ場一覧R9計画→輪作画面 反映バグ調査 (cmd_581 Wave 1)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1249 / cmd_581 |
| 作成日時 | 2026-05-18T16:10 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp |
| 対象ファイル | /var/www/rotation-planner-v2/app/frontend/app/src/lib/rotationSolver.js:388 |
| 報告書範囲 | read-only調査+設計のみ (実装は別subtask) |
| 関連 | cmd_580 subtask_1247 (R8表示修正完了)・cmd_581 はその次の連続バグ |

---

## §1 エグゼクティブサマリ

**症状**: yasuがほ場一覧でR9計画を手動入力(自動保存・F5消えず)→ 輪作計画画面に反映されない

**真因**: **X1 (別テーブル参照ミスマッチ)** 確定 — ほ場一覧=`crop_history`保存・Rotation.jsx 未来年=ソルバー結果(`plan`オブジェクト)取得・両者が**異なるデータ source**

**詳細**: `rotationSolver.js:388` で `row[year] = plan[`${i},${year}`] || ''` のみ・**`field.history` を fallback しない**。ソルバー未実行のyasuでは未来年=空。

**殿仮説検証**:
- crop_plans別テーブル疑い: **否定** (crop_plans テーブル不存在)
- 結論: 同じcrop_historyだが Rotation.jsx の構築ロジックで分岐(過去年=history・未来年=plan)

**推奨修正案 (最小変更)**:
`rotationSolver.js:388` 1行 fallback 追加:
```javascript
row[year] = plan[`${i},${year}`] || field.history[year] || '';
```
ソルバー未実行時は crop_history を fallback 表示。

**殿への申し送り** (運用フィードバック反映):
- 「現場的に他に選択肢がないからほ場一覧で計画入力した」= **UI設計課題**・別cmd記録
- 現UIは「計画は Rotation.jsx でソルバー実行で生成」前提だが、農家は手入力したい場合あり

---

## §2 Phase 1 DB実体スナップショット

### users.yasu
```
id=6 username=yasu role=farmer
```

### rotation_plans (yasu) — **0件** (空)
- yasu は Rotation.jsx でのソルバー実行・計画保存を未実施

### plan_details (yasu経由) — **0件** (rotation_plans 0件のため)

### crop_plans テーブル — **不存在** (`.schema crop_plans` 出力なし)
- 殿仮説「crop_plans別テーブル疑い」は否定

### crop_history (yasu R9=2027) — **9件存在** ★
```
field_id=4 year=2027 飼料作物
field_id=5 year=2027 飼料作物
field_id=6 year=2027 飼料作物
field_id=7 year=2027 飼料作物
field_id=8 year=2027 飼料作物
field_id=18 year=2027 長なす
field_id=19 year=2027 長なす
field_id=20 year=2027 長なす
field_id=21 year=2027 長なす
```
- crop_history 全件: 29 (R8=2026:20件 + R9=2027:9件)
- 殿の手動入力は **crop_history テーブルに保存されている**

### fields schema
- fields テーブルに計画用カラム無し (`notes` 等の既存カラムのみ)
- → R9計画は fields の追加カラムではなく crop_history で管理

### 全テーブル (cmd_577後の追加含む)
```
_migration_log, crop_constraints, crop_history, crop_master, crop_polygons,
famic_import_log, fields, inventory, inventory_csv_operations, inventory_transactions,
order_templates, organizations, paddy_polygons, pesticide_masters, pesticide_orders,
pesticide_records, pesticide_registry, pesticide_usage, plan_details, rotation_plans,
user_constraints, user_crops, users
```

---

## §3 Phase 2 API+SQL精読結果

### Rotation.jsx 主要構造
```javascript
// Rotation.jsx:37-45 (年度計算)
const currentReiwaYear = new Date().getFullYear() - 2018;  // 8 (2026年)
const pastYears = useMemo(() => [`R${currentReiwaYear - 1}`, `R${currentReiwaYear}`], ...);  // [R7, R8]
const futureYearsList = useMemo(() =>
  Array.from({ length: futureYears }, (_, i) => `R${currentReiwaYear + 1 + i}`),  // [R9, R10, R11, R12]
  ...);

// Rotation.jsx:81-99 loadHistories (subtask_1247修正済)
const loadHistories = async () => {
    for (const field of fields) {
      const history = await fieldApi.getHistory(field.id);
      for (const h of history) {
        const reiwaYear = Number(h.year) - 2018;
        histories[field.id][`R${reiwaYear}`] = h.crop;  // R8/R9両方 保存される
      }
    }
};

// Rotation.jsx:99-107 prepareFields
return fields.map((f, i) => ({
  fieldId: String(f.id),
  history: fieldHistories[f.id] || {},  // R8/R9含む全history
  ...
}));

// Rotation.jsx:178 ソルバー結果→ generateResultTables
const { fieldTable, summaryTable } = generateResultTables(
  solverFields, pastYears, futureYearsList, ...);

// Rotation.jsx:345-348 filteredFieldTable
const filteredFieldTable = useMemo(() => {
    if (!result || !result.fieldTable) return [];  ★ソルバー未実行なら空
    return result.fieldTable;
}, ...);

// Rotation.jsx:596 render
{allYears.map((y) => (
  <td><span>{row[y] || '-'}</span></td>  ★ row[`R9`] が空なら "-"
))}
```

### rotationSolver.js:376-414 generateResultTables ★問題箇所★
```javascript
export function generateResultTables(fields, pastYears, futureYears, plan, crops) {
  const allYears = [...pastYears, ...futureYears];
  const fieldTable = fields.map((field, i) => {
    const row = { field_code, district, area_ha };
    for (const year of allYears) {
      if (pastYears.includes(year)) {
        row[year] = field.history[year] || '';        // 過去年: history参照 ✓
      } else {
        row[year] = plan[`${i},${year}`] || '';       // ★未来年: plan のみ・history fallback無し★
      }
    }
    return row;
  });
  ...
}
```

### POST /api/fields/{id}/history (lib/api.js:128 addHistory)
- ほ場一覧 (Fields.jsx:280, 323) で R9計画入力時に呼ばれる
- `api.post('/api/fields/${fieldId}/history', { field_id, year, crop })`
- DB側: crop_history に year=2027(西暦) で保存

### API router
- /api/plans (POST/PUT) → rotation_plans 操作
- /api/fields/{id}/history (POST) → crop_history 操作
- **plan系 と history系 が完全独立**

---

## §4 真因特定 (X1-X5判定)

| 仮説 | 判定 | 根拠 |
|---|---|---|
| **X1 別テーブル参照ミスマッチ** | **確定** | ほ場一覧=crop_history保存・Rotation.jsx未来年=`plan[i,year]`参照・両者異なるdata source |
| X2 未来年カラム範囲制約 | 否定 | futureYearsList で R9-R12 列展開済(allYears L330) |
| X3 令和変換漏れ未来年経路 | 否定 | subtask_1247の修正は R8/R9両方カバー(year-2018 式) |
| X4 UI設計問題 | **部分肯定** | 「ほ場一覧で計画入力可能」だが Rotation.jsx は「ソルバー結果のみ表示」・**UI/データ層の意図不一致** |
| X5 その他 | — | — |

### 追加発見: 殿運用フィードバック「現場的に他に選択肢」のUI設計課題
- Rotation.jsx 設計意図: 制約条件設定 → ソルバー実行 → 計画自動生成 → 表示
- 農家の実態: 「経験で来年これ作りたい」を直接入力したい → ほ場一覧で年度+作物入力
- → 入力経路 (Fields.jsx history POST) と表示経路 (Rotation.jsx plan map) が**設計上の cross over なし**

---

## §5 修正案 (最小変更+rollback)

### 案A (推奨・1行 fallback 追加)

`rotationSolver.js:388` を以下に修正:
```javascript
// 修正前:
row[year] = plan[`${i},${year}`] || '';
// 修正後:
row[year] = plan[`${i},${year}`] || field.history[year] || '';
```
**長所**:
- 1行変更・最小影響
- ソルバー未実行時は crop_history fallback → ほ場一覧入力したR9計画が即可視化
- ソルバー実行後は plan が priority(計算結果優先)・既存動作維持
- rollback容易 (git revert 1コミット)

**短所**:
- summary table (L392-409) は同じパターンだが本subtask対象外 (別fix候補・案A+)

### 案A+ (推奨拡張): summary table も同様に fallback

```javascript
// rotationSolver.js:399 修正前:
c = plan[`${i},${year}`];
// 修正後:
c = plan[`${i},${year}`] || fields[i].history[year];
```

### 案B (UI設計改修・別cmd起票候補)
ほ場一覧の「R9計画入力欄」を撤去 or 明示的に「Rotation.jsxに反映」ボタン追加。
→ 殿運用フィードバック対応・cmd_582等で起票判断。

### 案C (rotation_plans table保存方式へ統合)
Fields.jsx の R9入力時に POST /api/plans (rotation_plans) として保存・crop_history と分離。
→ 大規模リファクタリング・本subtask対象外。

### Rollback (案A実施後)
```bash
ssh debian@... 'cd /var/www/rotation-planner-v2/app && \
  sudo -u webapp git checkout HEAD~1 -- frontend/app/src/lib/rotationSolver.js && \
  sudo -u webapp bash -lc "source ~/.nvm/nvm.sh && nvm use default && cd frontend/app && npm run build"'
```

### 殿運用フィードバック記録 (§5明示)
**「現場的に他に選択肢がないからほ場一覧で計画入力した」**
- 本cmd_581では真因特定+案A修正までの記録 (UI改修は別cmd候補)
- UI設計の根本見直しは将来cmd で軍師戦略書 fix候補

---

## §6 殿への質問

| # | 質問 |
|---|---|
| Q1 | **修正案A承認可否** (rotationSolver.js L388 fallback追加・1行) |
| Q2 | **案A+(summary table含む 2箇所修正)** か **案A(L388 1箇所)** か |
| Q3 | upstream PR要否 (本修正の origin push可否・D2撤廃後の正攻法継続) |
| Q4 | UI設計改修 (案B) を別cmd_582等で起票するか・しばらく案A運用継続するか |
| Q5 | summary table の fallback も plan>history で問題ないか (将来 plan で別作物が割り当てられた場合は plan を優先・現挙動と一致) |

---

## 付録: 実行コマンド一覧 (read-only・F006抑制継続)

```bash
# Phase 1 DB SELECT (sqlite3 read-only)
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM users/rotation_plans/plan_details/crop_history/fields WHERE user_id=..."
sudo -u webapp sqlite3 $DB ".schema crop_plans" → 空(テーブル不在確認)
sudo -u webapp sqlite3 $DB ".tables"

# Phase 1 API router探索
sudo -u webapp grep -rnE "@router\.(patch|put|post).*plan" .../api/routers/
sudo -u webapp grep -rnE "crop_plans|rotation_plans|plan_details" .../api/routers/

# Phase 2 frontend精読
sudo -u webapp grep -nE "pastYears|futureYearsList|loadHistories|prepareFields|fieldTable" Rotation.jsx
sudo -u webapp sed -n "375,415p" .../lib/rotationSolver.js
sudo -u webapp grep -rnE "addHistory|/api/fields.*history" .../frontend/app/src/
```

書き込み・サービス操作・ファイル変更は一切なし。

---

(cmd_581 Wave 1 真因特定 X1 確定+案A推奨・実装は別subtaskで起票判断)
