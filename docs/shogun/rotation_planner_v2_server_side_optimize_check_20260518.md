# rotation-planner v2: server-side /api/rotation/optimize endpoint 調査報告書

**作成**: 2026-05-18 / 足軽1 (ashigaru1) / subtask_1263  
**対象**: `/var/www/rotation-planner-v2/app/api/main.py` + `rotation_planner/app/optimizer.py`  
**目的**: subtask_1261 で frontend JS ソルバーの pinned 経路断裂を確認後、OR-Tools server-side endpoint に同種断裂がないか予防調査

---

## §1 結論

| 項目 | 結果 |
|------|------|
| server-side `/api/rotation/optimize` 存在 | **YES** (`main.py:619`・routers/ 外に直接定義) |
| 同種 pinned 経路断裂 | **YES** — OR-Tools モードで pinned assignments が完全未実装 |
| 修正の要否 | **要** — 別 subtask 起票推奨 (§4) |

**影響**: OR-Tools ソルバーモード選択時に pinned assignments が一切考慮されない。JS ソルバー側 (subtask_1262 修正中) と同種だが、実装レベルでさらに深い断裂 (スキーマ・バックエンド両方に pinned フィールドなし)。

---

## §2 grep 結果全文 (Phase 1 生SSH)

```
=== rotation/optimize/solve関連 router エンドポイント ===
(api/routers/ 内に rotation/optimize/solve ファイルなし)

=== /api/rotation /api/optimize /api/solve パターン ===
api/main.py:464:@app.post("/api/rotation/import-csv", ...)
api/main.py:619:@app.post("/api/rotation/optimize", response_model=RotationOptimizeResponse)
api/main.py.bak.20260518_1254:462 (bak): 同内容

=== Repository側 optimize/solve関連 ===
rotation_planner/app/optimizer.py:373:    def solve(...)   # RotationPlannerHeuristic.solve
rotation_planner/app/optimizer.py:422:    def solve(...)   # RotationPlannerORTools.solve

=== rotation/optimize router ファイル有無 ===
no rotation/optimize/solve router
(main.py に直接 @app.post で定義)

=== main.py include_router 全件 ===
157: app.include_router(inventory_router)
158: app.include_router(auth_router)
159: app.include_router(admin_router)
160: app.include_router(fields_router)
161: app.include_router(crops_router)
162: app.include_router(plans_router)
163: app.include_router(pesticides_router)
164: app.include_router(gis_router)
165: app.include_router(dashboard_router)
166: app.include_router(pinned_router)
(rotation/optimize は include_router ではなく直接 @app.post)

=== Phase 2: optimizer.py pinned 参照 ===
(0件 — pinned/Pinned/fixed_assignments/fixed_crop いずれも未検出)

=== Phase 2: main.py pinned 参照 ===
89: from api.routers.pinned_assignments import router as pinned_router
166: app.include_router(pinned_router)
(optimize_rotation 関数内に pinned 参照なし)
```

---

## §3 実装精読

### 3-1. RotationOptimizeRequest スキーマ (main.py L599-L608)

```python
class RotationOptimizeRequest(BaseModel):
    fields: List[Dict[str, Any]]
    crops: List[str]
    past_years: List[str]
    future_years: List[str]
    constraints: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None
    # ← pinned_assignments フィールド なし
```

### 3-2. optimize_rotation 関数 (main.py L619-L830)

```python
@app.post("/api/rotation/optimize", ...)
def optimize_rotation(req: RotationOptimizeRequest, ...):
    # ... 制約構築 ...

    planner = RotationPlannerORTools(
        field_objects,
        req.past_years,
        req.future_years,
        req.crops,
        constraints_obj
        # ← pinned_assignments 引数 なし (5引数)
    )
    plan, score, errors = planner.solve(
        timeout_seconds=timeout,
        high_precision=high_precision,
        district_grouping=district_grouping
    )
```

### 3-3. RotationPlannerORTools.__init__ (optimizer.py L394-L408)

```python
class RotationPlannerORTools:
    def __init__(self, fields: List[Field], past_years: List[str],
                 future_years: List[str], crops: List[str], constraints: Constraints):
        # ← pinned_assignments 引数 なし (5引数)
        self.fields = fields
        self.past_years = past_years
        ...
```

`optimizer.py` 全体で `pinned` キーワード参照: **0件**

### 3-4. frontend Rotation.jsx runOptimizationORTools (L200-L227)

```javascript
const requestData = {
  fields: solverFields.map((f) => ({ ... })),
  crops,
  past_years: pastYears,
  future_years: futureYearsList,
  constraints: constraints || {},
  options: { ... },
  // ← pinned_assignments なし
};
const response = await rotationApi.optimize(requestData);
```

### 3-5. JS ソルバーとの比較

| 項目 | JS ソルバー (subtask_1262修正中) | OR-Tools サーバー |
|-----|-------------------------------|----------------|
| pinned取得 | `PinnedAssignmentRepository.get_pinned` (修正後) | **なし** |
| ソルバー引数 | `RotationSolver(... , pinnedAssignments)` (修正後6引数) | `RotationPlannerORTools(... )` (5引数・pinned未対応) |
| requestData | `pinned_assignments` 追加予定 (修正後) | **フィールドなし** |
| スキーマ | frontend-only (JS) | `RotationOptimizeRequest` に pinned_assignmentsなし |

---

## §4 別 subtask 提案

OR-Tools モードの pinned 対応は **3層の修正** が必要:

| 修正箇所 | 内容 |
|---------|------|
| `main.py` (L599) `RotationOptimizeRequest` | `pinned_assignments: Optional[List[Dict]] = None` フィールド追加 |
| `main.py` (L619) `optimize_rotation` 関数 | `req.pinned_assignments` を取得し、pinned制約として `constraints_obj` または `planner.solve()` に渡す |
| `optimizer.py` `RotationPlannerORTools` | `pinned_assignments` を受け取り、CP-SAT モデルにハード制約として追加 |
| `Rotation.jsx` `runOptimizationORTools` | `requestData` に `pinned_assignments` 追加 (subtask_1262 で frontend pinned取得済みなら流用可) |

**subtask 提案**:

```
cmd_586 Wave 6: OR-Tools server-side pinned 対応
- target: main.py + optimizer.py + Rotation.jsx(runOptimizationORTools)
- 優先度: 中 (OR-Toolsモードはデフォルト非選択・影響範囲限定)
- 前提: subtask_1262(JS ソルバー pinned 対応) 完了後に連携実装
- 注意: RotationPlannerORTools.solve() への pinned ハード制約追加は
  OR-Tools CP-SAT モデルへの固定変数制約として実装要
```

**OR-Tools モードの実使用率確認推奨**:  
`solverType` は frontend state で `'js'` がデフォルト。OR-Tools モードを選択したユーザーのみ影響。実使用率が低ければ低優先度で対応可。

---

*報告者: 足軽1 (ashigaru1) / subtask_1263 / 2026-05-18*
