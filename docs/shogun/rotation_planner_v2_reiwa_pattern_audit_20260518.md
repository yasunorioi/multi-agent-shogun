# rotation-planner v2: 令和↔西暦変換パターン監査報告書

**作成**: 2026-05-18 / 足軽1 (ashigaru1) / subtask_1248  
**対象**: `/var/www/rotation-planner-v2/app/frontend/app/src/pages/`  
**目的**: Rotation.jsx L86 `R${h.year}` バグ(subtask_1246確認済)と同種パターンを他画面で検出

---

## §1 エグゼクティブサマリー

| 項目 | 結果 |
|------|------|
| 検出候補ファイル数 | 6ファイル |
| **不具合確定** | **1件 (Rotation.jsx:88・subtask_1247で修正中)** |
| **正常・修正不要** | 5件 |
| 新規修正要候補 | **0件** |

**結論**: Rotation.jsx:88 以外に同種不具合なし。subtask_1247 の修正のみで cmd_580 は完結する。

---

## §2 Phase 1 grep 全出力（生SSH）

```
=== R${...year...} パターン検出 ===
./pages/Rotation.jsx:88:          histories[field.id][`R${h.year}`] = h.crop;
./pages/Plans.jsx:102:      const year = `R${d.year}`;

=== バッククォートR${ 単純パターン (template literal 令和連結候補) ===
./pages/Rotation.jsx:39:    return [`R${currentReiwaYear - 1}`, `R${currentReiwaYear}`];
./pages/Rotation.jsx:44:    return Array.from({ length: futureYears }, (_, i) => `R${currentReiwaYear + 1 + i}`);
./pages/Rotation.jsx:88:          histories[field.id][`R${h.year}`] = h.crop;
./pages/Plans.jsx:102:      const year = `R${d.year}`;
./pages/FieldRegister.jsx:24:      choices.push({ value: `R${reiwa}`, label: `令和${reiwa}年` });
./pages/FieldRegister.jsx:37:  return `R${reiwa}`;

=== h.year / crop_history.*year / fiscal_year / 令和 / reiwa パターン ===
./pages/Fields.jsx:116:            const yearStr = String(h.year);
./pages/Fields.jsx:255:      const existing = existingHistory.find((h) => h.year === y);
./pages/Fields.jsx:558:                      <td>{h.year}年</td>
./pages/Rotation.jsx:36:  // 過去年を計算（現在の令和年から過去2年）
./pages/Rotation.jsx:88:          histories[field.id][`R${h.year}`] = h.crop;
./pages/FieldRegister.jsx:11: * 年度選択肢を生成（令和形式）
./pages/FieldRegister.jsx:18:  const currentReiwa = fiscalYear - 2018; // 2019年 = 令和1年
./pages/FieldRegister.jsx:22:    const reiwa = currentReiwa + i;
./pages/FieldRegister.jsx:23:    if (reiwa > 0) {
./pages/FieldRegister.jsx:24:      choices.push({ value: `R${reiwa}`, label: `令和${reiwa}年` });
./pages/FieldRegister.jsx:31: * 現在の年度を取得（令和形式）
./pages/FieldRegister.jsx:36:  const reiwa = fiscalYear - 2018;
./pages/FieldRegister.jsx:37:  return `R${reiwa}`;
./pages/DataManagement.jsx:181:            year: h.year,
./pages/DataManagement.jsx:195:      const rows = allHistory.map(h => [h.field_code, h.field_name, h.year, h.crop]);
./pages/DataManagement.jsx:454:              const reiwa = parseInt(yearStr.substring(1));
./pages/DataManagement.jsx:455:              if (!isNaN(reiwa)) year = 2018 + reiwa;
./pages/DataManagement.jsx:481:              historyByYear[h.year] = h.crop;

=== 既に正しく令和変換 (-2018 / -2019 / reiwaYear) ===
(該当なし)

=== pages/ 一覧 ===
CropSettings.jsx  Dashboard.jsx  DataManagement.jsx  FieldRegister.jsx
Fields.jsx  JAAggregation.jsx  Login.jsx  PesticideMasters.jsx
PesticideOrders.jsx  PesticideRecords.jsx  Plans.jsx  Rotation.jsx
SystemInfo.jsx  UserManagement.jsx
```

---

## §3 候補ファイル別判定

### 3-1. Rotation.jsx:88 — **不具合確定（修正中）**

```jsx
// Rotation.jsx L82-L92 (loadHistories 関数)
const loadHistories = async () => {
  const histories = {};
  for (const field of fields) {
    try {
      const history = await fieldApi.getHistory(field.id);
      histories[field.id] = {};
      for (const h of history) {
        histories[field.id][`R${h.year}`] = h.crop;  // ← L88
      }
    } catch { ... }
  }
  setFieldHistories(histories);
};
```

**判定**: 不具合あり  
**理由**: `h.year` は `crop_history` テーブルの `year` 列（INTEGER・西暦4桁。例: `2024`）。`R${2024}` = `"R2024"` というキーが生成され、令和形式のキー `"R6"` と不一致→ 過去作付履歴が輪作計算に反映されない。  
**対応**: subtask_1247 (部屋子1) で修正中。本subtaskのスコープ外。

---

### 3-2. Plans.jsx:102 — **正常・修正不要**

```jsx
// Plans.jsx L94-L113 (formatPlanDetails 関数)
const formatPlanDetails = (plan) => {
  const fieldMap = {};
  const years = new Set();
  for (const d of plan.details) {
    const fieldId = d.field_id;
    const year = `R${d.year}`;   // ← L102
    years.add(year);
    ...
  }
};
```

**判定**: 正常  
**理由**: `d.year` は `plan_details` テーブルの `year` 列（TEXT・令和年数字のみ。例: `"7"`）。  
根拠: Rotation.jsx の `savePlan` (L265-L285) で保存時に `yearNum = parseInt(year.replace('R', ''))` を実行し、令和年の数字部分（`7`, `8`…）のみを DB に INSERT している。  
したがって `R${d.year}` = `R${7}` = `"R7"` → 正しい令和形式が生成される。

**証拠コード (Rotation.jsx L265-L285)**:
```jsx
const details = [];
for (const [key, crop] of Object.entries(result.plan)) {
  const [fieldIdx, year] = key.split(',');
  const yearNum = parseInt(year.replace('R', ''));  // "R7" → 7
  details.push({
    field_id: fields[parseInt(fieldIdx)].id,
    year: yearNum,   // ← 令和年数字(7,8...)をDBに保存
    crop,
  });
}
```

---

### 3-3. FieldRegister.jsx:24, 37 — **正常・修正不要**

```jsx
// FieldRegister.jsx L11-L37
const currentReiwa = fiscalYear - 2018;   // 西暦→令和変換済み
choices.push({ value: `R${reiwa}`, label: `令和${reiwa}年` });  // L24
return `R${reiwa}`;  // L37
```

**判定**: 正常  
**理由**: `reiwa` は `fiscalYear - 2018` で既に令和年に変換済み（例: 2026→8）。`R${8}` = `"R8"` → 正しい。

---

### 3-4. Rotation.jsx:39, 44 — **正常・修正不要**

```jsx
const currentReiwaYear = new Date().getFullYear() - 2018;  // 令和年に変換
return [`R${currentReiwaYear - 1}`, `R${currentReiwaYear}`];  // L39
return Array.from({ length: futureYears }, (_, i) => `R${currentReiwaYear + 1 + i}`);  // L44
```

**判定**: 正常  
**理由**: `currentReiwaYear` は `getFullYear() - 2018` で令和年に変換済み。

---

### 3-5. Fields.jsx:116, 255, 558 — **令和変換バグなし（別注意あり）**

**L116**: `const yearStr = String(h.year);`  
→ `h.year` を文字列化後 L119 で `if (yearStr.startsWith('R'))` チェックあり → R形式も西暦もどちらも対応済み。令和変換バグなし。

**L255**: `existingHistory.find((h) => h.year === y)` → `bulkHistoryYears` は `currentFiscalYear - 3` 等の西暦整数。`h.year` も西暦整数のため一致比較は正常。

**L558**: `<td>{h.year}年</td>` → `crop_history.year` の生値（西暦4桁: 2024）をそのまま「2024年」と表示。  
→ 令和表示への変換はされていないが、**これは表示仕様の問題**であり、本調査対象の「R${...}による令和連結バグ」ではない。別途確認が必要であれば新規subtaskで対応。

---

### 3-6. DataManagement.jsx:181, 195, 454-455, 481 — **正常**

- **L181, L195**: CSV出力で `h.year`（西暦4桁）をそのまま出力 → 仕様として西暦CSV出力
- **L454-455**: CSV取込で `R7` → `2018 + 7 = 2025` へ変換 → 正しい令和→西暦変換
- **L481**: `historyByYear[h.year] = h.crop` → 連作チェック用マップ（西暦キー）→ 正常

---

## §4 修正要候補一覧・subtask提案

| ファイル | 行 | パターン | 判定 | 対応 |
|---------|---|---------|------|------|
| Rotation.jsx | 88 | `R${h.year}` | **不具合** | subtask_1247で修正中（新規不要） |
| Plans.jsx | 102 | `R${d.year}` | 正常 | 不要 |
| FieldRegister.jsx | 24, 37 | `R${reiwa}` | 正常 | 不要 |
| Rotation.jsx | 39, 44 | `R${currentReiwaYear±n}` | 正常 | 不要 |
| Fields.jsx | 558 | `{h.year}年` | 表示仕様(西暦) | 別途要確認（新規検討） |

**新規subtask提案**: Fields.jsx:558 の `{h.year}年` が西暦表示（例: 「2024年」）である点について、令和表示（例: 「令和6年」）への統一が必要かどうか、殿に確認を推奨。ただし本調査スコープ外・低優先度。

---

## §5 殿への質問

**Q: Fields.jsx:558 の作付履歴表示が西暦(「2024年」)であることは仕様として正しいか？**  
→ 輪作計画画面は令和表示統一、ほ場登録画面の履歴一覧のみ西暦表示となっている。UI統一の観点から令和表示に揃えるかどうかの方針確認を推奨（必須ではない）。

---

*報告者: 足軽1 (ashigaru1) / subtask_1248 / 2026-05-18*
