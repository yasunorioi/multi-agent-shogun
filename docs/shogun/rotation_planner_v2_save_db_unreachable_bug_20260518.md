# rotation-planner v2: 保存DB未到達バグ 調査報告書

> **subtask**: subtask_1267 / **cmd**: cmd_588 Wave 1  
> **worker**: ashigaru2 / **date**: 2026-05-18T21:26:38  
> **調査方法**: read-only (grep/cat/SELECT/journald のみ)

---

## §1 エグゼクティブサマリ（30行以内）

**結論**: `POST /api/plans` がuvicornに**一度も到達していない**。

- `rotation_plans` テーブル全件=0（yasuに限らず全ユーザーで保存成功ゼロ）
- journaldに `POST /api/plans` のログが存在しない
- nginx `/api/` プロキシ設定・FastAPI実装・PlanRepositoryは論理的に正しい
- **問題はフロントエンド（Rotation.jsx savePlan関数）の実行フロー**

**真因候補（優先順）**:
1. **[最有力] Guard条件ブロック**: `result`=null または `saveName`が空で `alert('計画名を入力してください')` が出てreturn
2. **[有力] fields配列インデックスズレ**: 最適化後にfieldsが再fetchされ `fields[parseInt(fieldIdx)].id` がTypeError → POSTなし
3. **[調査要] `result.plan` キー形式不一致**: OR-Toolsソルバー使用時のplan形式が`{fieldIdx,year}`形式でない可能性

**推薦修正案**: 候補Bが根本修正（§6参照）

---

## §2 三柱証拠

| # | 証拠種別 | 内容 | 示すもの |
|---|---------|------|---------|
| E1 | DB | `SELECT COUNT(*) FROM rotation_plans` → **0件** | INSERT未達（全ユーザー共通） |
| E2 | journald | `grep "POST /api/plans" journal` → **0件** | HTTP POSTがuvicornに未到達 |
| E3 | nginx設定 | `location /api/ { proxy_pass http://127.0.0.1:8001; }` → **正しい** | プロキシ層に問題なし |

---

## §3 Phase 1: DB + API実装調査

### 3.1 DB状態

```sql
-- rotation_plans 全件
SELECT COUNT(*) FROM rotation_plans;  → 0

-- yasu ユーザー確認
SELECT id, username, role FROM users WHERE username="yasu";
→ 6 | yasu | farmer  ✅ 存在する

-- plan_details スキーマ
CREATE TABLE plan_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES rotation_plans(id) ON DELETE CASCADE,
    field_id INTEGER NOT NULL,
    year TEXT NOT NULL,
    crop TEXT NOT NULL,
    ...
);
```

**注意**: `plan_details.rotation_plan_id` は存在しない（正カラム名は `plan_id`）。タスク指示のクエリにミスあり（実害なし）。

### 3.2 API実装

```
api/routers/plans.py L77-88:
@router.post("/api/plans", status_code=201)
def create_plan(plan: PlanCreate, current_user = Depends(get_current_user)):
    plan_id = PlanRepository.create_plan(user_id=current_user["id"], data={...})
    return PlanResponse(**PlanRepository.get_plan(plan_id))
```

**エンドポイント**: `/api/plans` POST ✅  
**PlanRepository.create_plan**: 実装正常。IntegrityError/sqlite3.Errorは適切にraiseされる ✅  
**DBパス**: `Path(__file__).parent.parent.parent / "data" / "rotation_planner.db"` → `/var/www/rotation-planner-v2/app/data/rotation_planner.db` ✅  
**WorkingDirectory**: `/var/www/rotation-planner-v2/app` ✅

---

## §4 Phase 2: frontend 保存経路調査

### 4.1 保存関数の実装 (Rotation.jsx L277-310)

```javascript
const savePlan = async () => {
  // ① Guard条件
  if (!result || !saveName.trim()) {
    alert('計画名を入力してください');
    return;  // ← ここでreturnするとPOSTは送られない
  }

  try {
    const details = [];
    for (const [key, crop] of Object.entries(result.plan)) {
      const [fieldIdx, year] = key.split(',');          // "0,R7" → ["0","R7"]
      const yearNum = parseInt(year.replace('R', ''));   // "R7" → 7
      details.push({
        field_id: fields[parseInt(fieldIdx)].id,  // ← ② ここでTypeError可能性
        year: yearNum,
        crop,
      });
    }

    await planApi.create({          // ← ③ ここまで到達すればPOSTされる
      name: saveName,
      start_year: parseInt(futureYearsList[0].replace('R', '')),
      end_year: parseInt(futureYearsList[futureYearsList.length - 1].replace('R', '')),
      details,
    });
    ...
  } catch (err) {
    alert('保存に失敗しました: ' + (err.message || '不明なエラー'));
    // ← catchで飲み込まれる。POSTなし
  }
};
```

### 4.2 planApi.create の実装 (api.js L204)

```javascript
create: async (data) => {
  const res = await api.post('/api/plans', data);  // 相対URL → nginx経由 ✅
  return res.data;
},
```

### 4.3 JSソルバーの plan キー形式 (rotationSolver.js)

```javascript
plan[`${fieldIdx},${year}`] = bestCrop;  // → {"0,R7": "だいず", "1,R7": "小麦"...}
```

`savePlan` の `key.split(',')` はJSソルバー出力と**一致** ✅

### 4.4 journaldアクセスログ（全期間）

```
202.212.203.231 - GET /api/plans 200 OK        ← 殿のブラウザ（認証成功）
127.0.0.1       - POST /api/auth/login 401 ×7  ← cmd_586テスト（yasuパスワード違い）
POST /api/plans → 0件                          ← 一度も到達せず
```

---

## §5 Phase 3: 真因特定

### 5.1 候補整理

| 候補 | 説明 | 確率 | 根拠 |
|------|------|------|------|
| **①Guard条件ブロック** | result=null or saveName空でreturn | **高** | journaldにPOSTゼロ。最適化せず保存ボタン押下or saveName未入力 |
| **②fields配列TypeError** | 最適化後にfields再fetch → インデックスズレ → TypeError | **中** | savePlanはcatchで飲み込む。エラーでも殿は「失敗」alertに気づかない可能性 |
| **③OR-Toolsplan形式不一致** | OR-Toolsの`response.plan`がJSと別形式 | **低** | デフォルトはJSソルバー。OR-Tools未使用なら影響なし |
| ④API endpoint違い | なし | **なし** | `/api/plans`で一致 ✅ |
| ④Repository黙殺 | なし | **なし** | 例外は適切にraise ✅ |

### 5.2 最有力真因: 候補① Guard条件ブロック

`rotation_plans` が全件0 = 全ユーザーで保存成功ゼロ。殿だけでなく admin/ja_staffも0件。  
→ **設計上、保存操作が完了した実績がない**（テスト不足・UIフロー上の問題）。

最も単純な説明: 最適化 → saveName入力 → 保存ボタン、というUI操作フローが完結した実績がない。

### 5.3 候補②の詳細（根本的脆弱性）

```javascript
field_id: fields[parseInt(fieldIdx)].id
//        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
// fields配列は useFieldStore から取得。
// 最適化実行後にfetchFieldsが呼ばれてfieldsが更新されると
// fieldIdxがずれてfields[fieldIdx]がundefinedになりTypeError。
```

このコードは**fields配列のインデックス**と**result.planのfieldIdx**が完全同期している前提。
ページ操作でfieldsが変わると壊れる。根本修正が必要。

---

## §6 修正案

### 案A: 即時修正（Guard条件の改善）

```javascript
// 現状
if (!result || !saveName.trim()) {
  alert('計画名を入力してください');
  return;
}

// 改善案: 状態を分けてメッセージを明確化
if (!result) {
  alert('先に最適化を実行してください');
  return;
}
if (!saveName.trim()) {
  alert('計画名を入力してください');
  return;
}
```

**効果**: UIフロー上の問題を早期発見しやすくなる。

### 案B: 根本修正（fieldIdxをfield_idに変更）

```javascript
// 現状（脆弱）
field_id: fields[parseInt(fieldIdx)].id

// 修正案: JSソルバーがfieldIdxでなくfieldIdを返すように変更
// rotationSolver.js: plan[`${field.fieldId},${year}`] = crop
// Rotation.jsx: field_id: parseInt(fieldIdx)  ← fieldIdが直接入る
```

**効果**: fieldsの再fetch後もfield_idが正しく参照できる。

### 案C: エラーの可視化（デバッグ用）

```javascript
catch (err) {
  console.error('[savePlan] error:', err);  // console.errorを追加
  alert('保存に失敗しました: ' + (err.message || '不明なエラー'));
}
```

**効果**: ブラウザのDevToolsでエラー詳細を確認できる。

### 推薦修正順序

1. **案C**: すぐ実装可能。ブラウザコンソールで真因確定できる
2. **案A**: UX改善として実装
3. **案B**: 根本修正。テスト追加と合わせて実施

---

## §7 殿への質問（3問）

**Q1**: 「最適化→保存」操作時、`saveName`（計画名）を入力フィールドに記入した上で保存ボタンを押しましたか？ `alert('計画名を入力してください')` が表示されましたか？

**Q2**: 保存ボタンを押した際、ブラウザの画面に何か表示（alert等）がありましたか？ または何も起きませんでしたか？

**Q3**: JSソルバー（デフォルト）とOR-Toolsソルバーのどちらで最適化を試みましたか？

---

## 付録: SSH生データ

### Phase 1 出力抜粋

```
rotation_plans 全件: 0
yasu: id=6, role=farmer
plan_details.rotation_plan_id → "no such column" (正カラムはplan_id)
plans.py: @router.post("/api/plans") → PlanRepository.create_plan()
DB_PATH: /var/www/rotation-planner-v2/app/data/rotation_planner.db
```

### Phase 2 出力抜粋

```
api.js baseURL: import.meta.env.VITE_API_URL || '' (相対URL)
nginx: location /api/ { proxy_pass http://127.0.0.1:8001; } ✅
journal POST /api/plans: 0件
journal POST /api/auth/login: 401×7件 (127.0.0.1・テストスクリプト由来)
journal GET /api/plans: 200 OK×1件 (202.212.203.231・殿のブラウザ)
```
