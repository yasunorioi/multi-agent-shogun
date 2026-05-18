# rotation-planner v2: API router × Repository 引数名突合監査

**作成**: 2026-05-18 / 足軽1 (ashigaru1) / subtask_1258  
**対象**: `/var/www/rotation-planner-v2/app/api/routers/*.py` × `rotation_planner/common/db_access.py`  
**目的**: cmd_585 subtask_1256 で確認した `plans.py L80 plan_data≠data kwarg mismatch` と同種不具合を全router体系調査

---

## §1 エグゼクティブサマリー

| 種別 | 件数 | 詳細 |
|------|------|------|
| **Type A: kwarg名mismatch (TypeError確実)** | **2件** | plans.py:80, pesticides.py:261 |
| **Type B: 引数数mismatch (TypeError確実)** | **1件** | pesticides.py:255 |
| **Type C: dict内キー名mismatch (更新無効)** | **1件** | pesticides.py:294-302 |
| 正常 | 多数 | fields.py, gis.py, crops.py 等 |

**影響**: 農薬発注 (`/api/pesticide-orders`) の**作成・取得・更新** 3操作が全て壊れている可能性が高い。

---

## §2 全 API router × Repository ペア突合表

### 2-1. plans.py

| router呼出 | file:line | kwarg/引数 | Repository def | 一致？ |
|-----------|----------|-----------|---------------|-------|
| `PlanRepository.create_plan(user_id=..., plan_data={...})` | plans.py:80 | `plan_data=` | `def create_plan(user_id, data)` | **❌ mismatch** |
| `PlanRepository.update_plan(plan_id, update_data)` | plans.py:119 | 位置引数 | `def update_plan(plan_id, data)` | ✅ |
| `PlanRepository.delete_plan(plan_id)` | plans.py:130 | 位置引数 | `def delete_plan(plan_id)` | ✅ |
| `UserConstraintsRepository.save_constraints(user_id=..., constraints=..., forbidden_transitions=..., preferred_transitions=..., main_crops=...)` | plans.py:157 | kwarg名全一致 | `def save_constraints(user_id, constraints, forbidden_transitions="", ...)` | ✅ |

### 2-2. pesticides.py

| router呼出 | file:line | kwarg/引数 | Repository def | 一致？ |
|-----------|----------|-----------|---------------|-------|
| `PesticideOrderRepository.get_orders(user_id, year)` | pesticides.py:255 | 2引数 | `def get_orders(user_id: int)` | **❌ 引数過剰** |
| `PesticideOrderRepository.create_order(user_id=..., plan_id=..., year=..., items=...)` | pesticides.py:261 | `plan_id=`, `year=`, `items=` | `def create_order(user_id, data: Dict)` | **❌ 構造的mismatch** |
| `PesticideOrderRepository.update_order(order_id, update_data)` | pesticides.py:302 | 位置引数・dictキー: `year`, `items`, `notes` | `def update_order(order_id, data: Dict)` ← dataキー: `target_year`, `order_data`, `status` | **❌ dictキー名不一致** |
| `PesticideMasterRepository.create(master.model_dump())` | pesticides.py:205 | 位置引数 | `def create(data: Dict)` | ✅ |
| `PesticideMasterRepository.update(master_id, master.model_dump())` | pesticides.py:212 | 位置引数 | `def update(master_id, data: Dict)` | ✅ |
| `PesticideRecordRepository.create_record(user_id=..., data=...)` | pesticides.py:556 | `data=` kwarg | `def create_record(user_id, data: Dict)` | ✅ |
| `PesticideRecordRepository.update_record(record_id, record.model_dump())` | pesticides.py:601 | 位置引数 | `def update_record(record_id, data: Dict)` | ✅ |

### 2-3. fields.py

| router呼出 | file:line | kwarg/引数 | Repository def | 一致？ |
|-----------|----------|-----------|---------------|-------|
| `FieldRepository.create_field(user_id=..., data={...})` | fields.py:194 | `data=` kwarg | `def create_field(user_id, data: Dict)` | ✅ |
| `FieldRepository.create_field(user_id=..., data={...})` | fields.py:307 (KML bulk) | `data=` kwarg | 同上 | ✅ |
| `FieldRepository.update_field(field_id, update_data)` | fields.py:243 | 位置引数 | `def update_field(field_id, data: Dict)` | ✅ |
| `FieldRepository.delete_field(field_id)` | fields.py:253 | 位置引数 | `def delete_field(field_id)` | ✅ |
| `CropHistoryRepository.add_history(field_id, western_year, field.crop_name)` | fields.py:211 | 位置引数 | `def add_history(field_id, year, crop, is_inferred=False)` | ✅ |

### 2-4. gis.py

| router呼出 | file:line | kwarg/引数 | Repository def | 一致？ |
|-----------|----------|-----------|---------------|-------|
| `PaddyPolygonRepository.create(field_id=..., geometry=..., area_ha=..., is_converted=..., conversion_start_year=..., source=..., notes=...)` | gis.py:186 | 全kwarg名一致 | `def create(field_id, geometry, area_ha, is_converted=False, ...)` | ✅ |
| `PaddyPolygonRepository.update(polygon_id, **kwargs)` | gis.py:234 | `**kwargs` | `def update(polygon_id, **kwargs)` | ✅ |
| `CropPolygonRepository.create(field_id=..., year=..., crop_name=..., geometry=..., area_ha=..., notes=...)` | gis.py:303 | 全kwarg名一致 | `def create(field_id, year, crop_name, geometry, area_ha, notes=None)` | ✅ |
| `CropPolygonRepository.update(polygon_id, **kwargs)` | gis.py:345 | `**kwargs` | `def update(polygon_id, **kwargs)` | ✅ |

### 2-5. crops.py

| router呼出 | file:line | kwarg/引数 | Repository def | 一致？ |
|-----------|----------|-----------|---------------|-------|
| `UserCropRepository.set_user_crops(user_id, crop_ids)` | crops.py:82 | 位置引数 | `def set_user_crops(user_id, crop_ids)` | ✅ |
| `UserCropRepository.set_custom_name(user_id, crop_id, custom_name)` | crops.py:88 | 位置引数 | `def set_custom_name(...)` | ✅ |
| `UserCropRepository.add_user_crop(user_id, parent_crop_id, custom_name)` | crops.py:110 | 位置引数 | `def add_user_crop(user_id, parent_crop_id, custom_name=None)` | ✅ |
| `UserCropRepository.remove_user_crop(user_id, user_crop_id)` | crops.py:130 | 位置引数 | `def remove_user_crop(user_id, user_crop_id)` | ✅ |

### 2-6. dashboard.py / auth.py / admin.py

| router呼出 | file:line | 判定 |
|-----------|----------|------|
| 全て get 系 (get_fields, get_history, get_orders, get_plans 等) | dashboard.py | ✅ 引数過不足なし |
| auth.py | — | Repository呼出なし |
| admin.py | — | Repository呼出なし |

---

## §3 mismatch 候補詳細

### 3-1. plans.py:80 — `plan_data` ≠ `data` (Type A)

```python
# plans.py L79-84 (router)
plan_id = PlanRepository.create_plan(
    user_id=current_user["id"],
    plan_data={          # ← kwarg名: plan_data
        "name": plan.name,
        ...
    }
)

# db_access.py L621 (Repository)
def create_plan(user_id: int, data: Dict[str, Any]) -> int:
#                              ^^^^
```

**症状**: `TypeError: create_plan() got an unexpected keyword argument 'plan_data'` → `/api/plans` POST が常に 500 → subtask_1256で確認済・subtask_1257で修正中。

---

### 3-2. pesticides.py:255 — `get_orders(user_id, year)` 引数過剰 (Type B)

```python
# pesticides.py L255 (router)
orders = PesticideOrderRepository.get_orders(current_user["id"], year)
#                                                                 ^^^^

# db_access.py L1604 (Repository)
def get_orders(user_id: int) -> List[Dict[str, Any]]:
# year引数なし
```

**症状**: `TypeError: get_orders() takes 1 positional argument but 2 were given` → `/api/pesticide-orders?year=...` の呼出時に500。`year=None` の場合も同様。

---

### 3-3. pesticides.py:261-266 — `create_order` 構造的 kwarg mismatch (Type A)

```python
# pesticides.py L261-266 (router)
order_id = PesticideOrderRepository.create_order(
    user_id=current_user["id"],
    plan_id=order.plan_id,   # ← 余分なkwarg
    year=order.year,         # ← 余分なkwarg
    items=order.items        # ← 余分なkwarg
    # data=... が渡されていない
)

# db_access.py L1651 (Repository)
def create_order(user_id: int, data: Dict[str, Any]) -> int:
#                              ^^^^ data kwarg が必要
# 内部で data['name'], data['target_year'], data['order_data'] 等を参照
```

**症状**: `TypeError: create_order() got an unexpected keyword argument 'plan_id'` → `/api/pesticide-orders` POST が常に 500。

**修正案**: router側を以下に変更:
```python
order_id = PesticideOrderRepository.create_order(
    user_id=current_user["id"],
    data={
        "rotation_plan_id": order.plan_id,
        "target_year": order.year,
        "order_data": {"items": order.items},
        "name": f"発注_{order.year}",   # name フィールド必須かどうか確認要
    }
)
```
※ `data['name']` が Repository内で `data['name']` として直接アクセスされるため、name キーが必須。スキーマ要確認。

---

### 3-4. pesticides.py:294-302 — update_order dict キー名不一致 (Type C)

```python
# pesticides.py L294-302 (router)
update_data = {}
if order_update.year is not None:
    update_data["year"] = order_update.year    # ← "year"
if order_update.items is not None:
    update_data["items"] = order_update.items  # ← "items"
if order_update.notes is not None:
    update_data["notes"] = order_update.notes  # ← "notes" (Repositoryに対応キーなし)

PesticideOrderRepository.update_order(order_id, update_data)

# db_access.py L1686 (Repository) が期待するキー
# "name", "target_year", "area_unit", "order_data", "status"
# ← "year" や "items" や "notes" キーは一切チェックされない
```

**症状**: TypeError は起きないが、`year`/`items`/`notes` 更新が全て無視される。PUTリクエストが200を返しても実際には DB が更新されない。

**修正案**: router側のキー名を変更:
```python
update_data["target_year"] = order_update.year    # year → target_year
update_data["order_data"] = {"items": order_update.items}  # items → order_data構造体
# "notes" は Repository update_order に対応なし → 別途対応要
```

---

## §4 修正要件抽出

| # | ファイル | 行 | 修正種別 | 修正対象 | 修正内容 |
|---|---------|---|---------|---------|---------|
| 1 | plans.py | 80 | kwarg名変更 | router側 | `plan_data=` → `data=` |
| 2 | pesticides.py | 255 | 引数削除 or Repository拡張 | どちらか | router側: year引数削除→全件取得後Pythonフィルタ / またはRepository側: `def get_orders(user_id, year=None)` 追加 |
| 3 | pesticides.py | 261-266 | kwarg構造改修 | router側 | 個別kwarg → `data={...}` 形式に変更。data内キー名もRepository期待値に合わせる |
| 4 | pesticides.py | 294-302 | dictキー名修正 | router側 | `"year"` → `"target_year"`, `"items"` → `"order_data"` |

**優先度**:
- #1 (plans.py) → subtask_1257で修正中（最高優先）
- #2 (get_orders引数過剰) → 高優先（一覧取得が壊れている）
- #3 (create_order構造) → 高優先（作成が壊れている）
- #4 (update_order キー) → 中優先（更新が無効化されている）

---

## §5 別subtask提案

| subtask案 | 対象 | 内容 | 優先度 |
|----------|-----|------|-------|
| cmd_586 Wave 2a | pesticides.py:255 | `get_orders(user_id, year)` → Repository側 `year=None` 引数追加（または router側フィルタ変更） | 高 |
| cmd_586 Wave 2b | pesticides.py:261-266 | `create_order` 呼出を `data={...}` 形式に改修 + キー名修正 | 高 |
| cmd_586 Wave 2c | pesticides.py:294-302 | `update_order` の update_data キー名修正 | 中 |

Wave 2a-2c は同一ファイル (pesticides.py) の修正なので1subtaskにまとめることも可能。

---

## §6 殿への質問

**Q1: pesticides.py の農薬発注機能は現在実際に使用されているか？**  
→ Type A/B の mismatch により `/api/pesticide-orders` の GET/POST が常に500のはずだが、それでも実害が生じていない場合は、この機能が未使用 or フロントエンドから呼ばれていない可能性がある。影響範囲確認のため状況確認を推奨。

**Q2: `create_order` の `data['name']` は必須か？**  
→ Repository 内で `data['name']` を直接参照しているため、`name` キーなしの場合 KeyError が起きる。フロントエンドの PesticideOrderCreate スキーマに `name` フィールドがなく、修正時にスキーマ追加の要否を確認されたい。

---

## §7 Phase 1-2 生SSH出力

```
=== API router一覧 ===
admin.py  auth.py  crops.py  dashboard.py  fields.py  gis.py
__init__.py  pesticides.py  pinned_assignments.py  plans.py  __pycache__

=== db_access.py: Repository class一覧(抜粋) ===
142: class FieldRepository
352: class CropHistoryRepository
561: class PlanRepository
770: class JAStaffRepository
1002: class UserRepository
1074: class PesticideMasterRepository
1300: class CropMasterRepository
1414: class UserCropRepository
1600: class PesticideOrderRepository
1758: class MigrationUtils
1905: class UserConstraintsRepository
1994: class PesticideRegistryRepository
2055: class PesticideUsageRepository
2141: class PesticideRecordRepository
2252: class OrderTemplateRepository
2432: class InventoryRepository
2622: class PaddyPolygonRepository
2924: class CropPolygonRepository
(合計: 3184行)

=== 主要mismatch確認: pesticides.py L261-266 ===
@router.post("/api/pesticide-orders", ...)
def create_pesticide_order(order: PesticideOrderCreate, ...):
    order_id = PesticideOrderRepository.create_order(
        user_id=current_user["id"],
        plan_id=order.plan_id,   # ← mismatch
        year=order.year,         # ← mismatch
        items=order.items        # ← mismatch
    )

=== db_access.py L1651: create_order定義 ===
def create_order(user_id: int, data: Dict[str, Any]) -> int:
    ...
    data['name']        # ← name必須
    data['target_year'] # ← target_yearキー期待
    data.get('order_data', {})  # ← order_dataキー期待

=== db_access.py L1604: get_orders定義 ===
def get_orders(user_id: int) -> List[Dict[str, Any]]:
# year引数なし(pesticides.py L255で year を第2引数として渡している)
```

---

*報告者: 足軽1 (ashigaru1) / subtask_1258 / 2026-05-18*
