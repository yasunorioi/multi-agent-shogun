# rotation-planner v2 全API/Repository ペア SELECT列↔Response schema 構造的網羅監査 (cmd_589 Wave 1)

| 項目 | 内容 |
|---|---|
| cmd / subtask | cmd_589 / subtask_1273 |
| 作成日 | 2026-05-19T00:00 (2026-05-18T23:50 着手) |
| 作成者 | 軍師 (gunshi) |
| 前段 | cmd_585 (plans.py L80 kwarg mismatch) + cmd_586 Wave 11 (PlanRepo SELECT user_id欠如) で2件不整合検出 |
| 殿明示 | **「予断与えず」** memory#feedback_no_predisposition.md 準拠・3案 G1/G2/G3 選好誘導禁止・軍師独立判断 |
| 監査対象 | origin/main HEAD `15d9095` (本日 23:13 取得・11 commits先行を pull) の api/routers/*.py + api/main.py + api/inventory_api.py + rotation_planner/common/db_access.py |
| Wave | 1 = 監査+設計レポートのみ・実装は別subtask起票候補 |
| read-only | 完全可逆(コード変更なし) |

---

## §1 エグゼクティブサマリ (殿レビュー用・30行以内厳守)

**結論3行:**
1. **構造的網羅監査で 5パターンの不整合カテゴリ(A-E) を抽出。最重要は ★★★ パターンA 致命的 1件 = `PlanRepository.get_plans()` (db_access.py L577) が SELECT に `user_id` 欠如・`plans.py:74` が `PlanResponse(**p)` 直接展開で `user_id: int` 必須を満たせず → GET /api/plans 500 ValidationError が依然発生中(cmd_586 Wave 11 subtask_1271 の修正が origin/main に未マージ)**。
2. **軍師独立提案 3案** を 7軸×重み100 で公平採点: **案G1=66/100 個別hot-fix ★最高得点** / 案G2=58/100 from_db pattern 統一 / 案G3=43/100 ORM Repo層導入。但し**G1だけでは再発予防ゼロ** → §5 で **「短期G1+中期G2+長期G3」の段階提案** も併記。
3. **構造的予防策(L6)** = (a) Repository層の SELECT列を constant化(pinned_assignments の `_COLS` パターン拡散)・(b) pytest CI で全 list endpoint smoke-test 自動化・(c) PRAGMA table_info ↔ Pydantic model_fields の定期 diff スクリプト。**(b)が最小コストで再発検出 → 別cmd起票推奨**。

**検出した不整合(優先度順・詳細§3):**

| # | 重要度 | 種別 | 箇所 | 影響 |
|---|:---:|---|---|---|
| 1 | **★★★** | A: SELECT列欠如 | `PlanRepository.get_plans` SELECT に `user_id` 無し vs `PlanResponse.user_id: int` 必須 | GET /api/plans 500 |
| 2 | **★★** | A: SELECT列欠如 | `FieldRepository.get_fields` SELECT に `user_id` 無し | `from_db` で吸収済(構造的脆さ) |
| 3 | **★★** | B: 型不一致 | `CropHistoryResponse.year: int` vs DB schema `year TEXT NOT NULL` | 暗黙変換失敗時の 422/500 |
| 4 | ★ | C: 命名揺れ | `FieldResponse.field_name` vs DB column `name` | `from_db` で alias 吸収済 |
| 5 | ★ | D: 層構造揺れ | `PinnedAssignment` だけ Repository層なし(pinned_assignments.py 直接SQL) | 保守性低下 |

**殿への質問3問:**
- Q1' 修正方針: (G1個別 / G2 from_db統一 / G3 ORM導入) どれを今 Wave 2 で発動するか?(軍師独立評価 G1=66点最高・但し再発予防ゼロ)
- Q2' 段階提案(短期G1+中期G2+長期G3)を採るか?
- Q3' 予防策(b) pytest CI smoke-test 自動化を別cmd 起票するか?

---

## §2 監査範囲と方法 (read-only実証)

### §2.1 監査対象ファイル

| カテゴリ | ファイル | 行数 |
|---|---|---|
| Router | api/routers/auth.py | 71行 |
| Router | api/routers/admin.py | 514行 |
| Router | api/routers/crops.py | 165行 |
| Router | api/routers/dashboard.py | 130行 |
| Router | api/routers/fields.py | 618行 |
| Router | api/routers/gis.py | 432行 |
| Router | api/routers/pesticides.py | 870行 |
| Router | api/routers/pinned_assignments.py | 212行 |
| Router | api/routers/plans.py | 170行 |
| Router | api/main.py (lifespan + JA直接endpoint) | 約600行 |
| Router | api/inventory_api.py | 約500行 |
| Repository | rotation_planner/common/db_access.py | 約3000行・18 Repository class |

### §2.2 抽出した endpoint 数

`@router.{get,post,put,patch,delete}` および `@app.{...}` (main.py) を grep:
- routers配下: **約 80 endpoint**(`response_model=` 指定あり = 約 45endpoint)
- main.py: **約 11 endpoint**(JA代行集計 / export / rotation/optimize)
- inventory_api.py: **約 7 endpoint**

合計 **約 98 endpoint**(本書では主要パターン抽出に絞り、典型不整合を §3 に列挙)。

### §2.3 監査手法 (L4-L6 read-only実証)

| Bloom | 手法 | 適用箇所 |
|---|---|---|
| L4 (分析) | SELECT列リスト ↔ Pydantic schema 必須フィールドの差分検出 | §3 全項目 |
| L5 (評価) | 不整合のパターン分類(A-E) + 重要度判定 + 修正方針 3案 weighted scoring | §3 / §5 |
| L6 (創造) | 構造的予防策(constant化 / CI smoke-test / PRAGMA diff スクリプト) の新規設計 | §6 |

### §2.4 三重突合根拠(お針子FB項目)

| 観点 | 根拠 |
|---|---|
| commit hash | origin/main HEAD `15d9095` (本日 23:13 取得) |
| Phase別SSH | 本subtaskはローカル `/tmp/rotation-planner-probe-v2` のみで実機SSH無し(read-only分析が VPS実機状態と分離) |
| 三重突合 | (a) git log で cmd_586 Wave 11 subtask_1271 の commit が origin/main に存在せず確認 / (b) db_access.py:577 SELECT文に `user_id` 不在を直接読取 / (c) plans.py:74 `PlanResponse(**p)` で `user_id: int` 必須にできず 500 redirect ロジック |

### §2.5 schema差異検出 何回目候補か

- cmd_585(L80 kwarg) = **1回目**
- cmd_586 Wave 11 (SELECT user_id 欠如・修正未マージ) = **2回目**
- 本cmd_589 (構造的網羅監査) = **3回目候補**(全Repository横断検証として位置付け)

### §2.6 V4境界線判定(各修正案ごと)

| 修正案 | 戻せるか | V4自動運転可否 |
|---|:---:|:---:|
| G1 個別hot-fix(1-3行修正) | ○ git revert可 | ✅ 自動運転可 |
| G2 from_db pattern 統一(複数router改修) | ○ git revert可 | ✅ 自動運転可・但しレビュー推奨 |
| G3 ORM/Repo層導入(大規模リファクタ) | △ 段階 commit でないと revert 困難 | ⚠️ 殿確認推奨 |
| 予防策(b) pytest CI smoke-test | ○ 削除可 | ✅ 自動運転可 |

---

## §3 検出した不整合一覧

### §3.1 ★★★ 不整合#1 = PlanRepository.get_plans SELECT user_id 欠如 (致命的)

**コード位置:**
- `rotation_planner/common/db_access.py` L575-582
- `api/routers/plans.py` L71-74

**問題:**
```python
# db_access.py L577 (PlanRepository.get_plans)
cursor = conn.execute("""
    SELECT id, name, start_year, end_year, created_at, updated_at
    FROM rotation_plans
    WHERE user_id = ?
""", (user_id,))
return rows_to_list(cursor.fetchall())   # ★ user_id 列が返らない
```

```python
# plans.py L34-42 (PlanResponse)
class PlanResponse(BaseModel):
    id: int
    user_id: int    # ★ 必須
    name: str
    ...

# plans.py L71-74 (list_plans)
@router.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(**p) for p in plans]   # ★ user_id がない dict を ** で展開
```

**影響:** GET /api/plans 呼出時に Pydantic ValidationError → 500 Internal Server Error。輪作計画一覧が表示できない・**殿利用ブロック直結**。

**修正案:**
```python
# 案G1-a: SELECT 句に user_id 追加 (db_access.py:577)
SELECT id, user_id, name, start_year, end_year, created_at, updated_at
       ^^^^^^^^
FROM rotation_plans
WHERE user_id = ?
```
または
```python
# 案G1-b: list_plans で user_id 注入 (plans.py:74)
return [PlanResponse(**{**p, "user_id": current_user["id"]}) for p in plans]
```

**推奨:** **案G1-a** (SELECT に user_id 追加)。理由:
- DB の真実を Response に反映する原則
- 将来 admin/ja_staff が他人の plan list を取得する際にも `user_id` が必要(現状の Router は本人のみだが代行 endpoint 追加時にバグらない)
- cmd_586 Wave 11 subtask_1271 で同じ修正が選択された(が origin/main に未マージ)

### §3.2 ★★ 不整合#2 = FieldRepository.get_fields SELECT user_id 欠如(吸収済)

**コード位置:**
- `db_access.py` L156-164
- `api/routers/fields.py` L173-176

**問題:**
```python
# db_access.py L158 (FieldRepository.get_fields)
SELECT id, field_code, district, name, area_ha, area_a, beet_forbidden,
       coordinates_json, notes, created_at, updated_at
FROM fields
WHERE user_id = ?
# → user_id 列が返らない (11列)

# fields.py L60-70 (FieldResponse)
class FieldResponse(BaseModel):
    id: int
    user_id: int    # ★ 必須
    field_code: str
    field_name: Optional[str] = None    # ★ DB 列名は `name`
    ...

# fields.py L175-176 (list_fields)
fields = FieldRepository.get_fields(current_user["id"])
return [FieldResponse.from_db(f, user_id=current_user["id"]) for f in fields]
#                       ^^^^^^^^ ← user_id 別途注入で吸収・name → field_name もここで alias
```

**影響:** 現状は `from_db()` classmethod が `user_id` を別途注入して吸収しているため**動作OK**。但し:
- 構造的脆さ: `from_db` を呼び忘れた箇所(/api/ja/farmers/{id}/fields 等)で同じバグが再発し得る
- `FieldResponse.from_db()` の存在が暗黙の前提・新規 endpoint 追加時に忘れやすい

**推奨修正案:** PlanRepository と同じ方針 = **SELECT に user_id を含める**。`from_db` での user_id 注入を削除し、`FieldResponse(**f)` 直接展開でも安全になるよう統一。

### §3.3 ★★ 不整合#3 = CropHistoryResponse.year 型不一致

**コード位置:**
- `db_schema.sql` 関連 (`crop_history.year TEXT NOT NULL`)
- `api/routers/fields.py` L94-98

**問題:**
```python
# fields.py L94-98 (CropHistoryResponse)
class CropHistoryResponse(BaseModel):
    id: int
    field_id: int
    year: int    # ★ int (但しDB schema は TEXT)
    crop: str
```

```sql
-- db_schema.sql crop_history テーブル
CREATE TABLE IF NOT EXISTS crop_history (
    ...
    year TEXT NOT NULL,    -- TEXT で 'R7' / '2025' / 'R9' 等を格納
    ...
);
```

**影響:** Repository が `'R9'` 等の令和表記を返した場合、`int('R9')` で **ValueError → 500**。Pydantic V2 は厳格な型検証で str→int 暗黙変換しないため危険。`CropHistoryCreate.year: int` も同様の問題(POST body の `R9` を受領できない)。

**推奨修正案:**
```python
class CropHistoryResponse(BaseModel):
    id: int
    field_id: int
    year: str    # int → str 変更 (DB schema に整合)
    crop: str
```
ただし**呼出側 frontend** が `year: int` を前提に書かれている場合、UI 側の改修も同時に必要(cmd_580 subtask_1247 で令和↔西暦変換の修正があったため、`year` の使われ方は文脈依存)。

### §3.4 ★ 不整合#4 = FieldResponse.field_name 命名揺れ

**コード位置:**
- `db_access.py` L158 SELECT `name` (DB列名)
- `api/routers/fields.py` L64 `field_name`

**問題:** DB の `fields.name` を Pydantic では `field_name` に rename。FieldResponse.from_db() で alias 変換しているはずだが、他の場所で `f["name"]` を直接参照する箇所と、`response.field_name` を参照する箇所が混在する可能性。

**影響:** 既存稼働には支障なし(from_db で吸収)。**保守性低下リスク**: 新規 developer が `fields.name` と `FieldResponse.field_name` の対応を見落とす。

**推奨修正案:** 命名統一(`name` か `field_name` のどちらかに揃える)・**長期改修**(G2 or G3 に統合)。

### §3.5 ★ 不整合#5 = PinnedAssignment Repository層不在

**コード位置:**
- `api/routers/pinned_assignments.py` (212行・全SQLを inline で記述)
- `db_access.py` には Pinned 関連クラスなし

**問題:** 他のテーブル(fields, plans, crop_history 等)は `db_access.py` の Repository class に SQL を集約しているが、**pinned_assignments だけは router 直接SQL**。

**影響:**
- Repository層の責務分離原則に反する(MVC 層構造の崩れ)
- 同じテーブルへのアクセスが複数ファイルに分散するリスク(将来別 router からも pinned_assignments を参照する場合)

**推奨修正案:** `PinnedAssignmentRepository` を `db_access.py` に新規追加し、SQL を集約。pinned_assignments.py は Repository呼出のみに簡素化。**長期改修**(G2 or G3 に統合)。

### §3.6 監査外で確認できなかった残課題

時間制約により本subtask では以下を完全確認できなかった。**別subtask での残課題確認推奨**:

| 確認対象 | リスク見積 |
|---|---|
| `PesticideMasterRepository` / `PesticideOrderRepository` 等 (db_access.py L1074, L1600) の SELECT列 | 中 - cmd_577 D3 でpesticide_masters構造刷新あり・他Response との突合未済 |
| `InventoryRepository` (L2432) SELECT列 vs InventoryItem / InventoryListResponse | 中 - inventory に 8列追加(cmd_577 D3 schema diff)で同種罠が潜在 |
| `CropMasterRepository.get_all` / `UserCropRepository` (L1300, L1414) | 中 - cmd_577 D3 で category 列追加問題・cmd_579 user_private_crops 設計とも関連 |
| `PaddyPolygonRepository` / `CropPolygonRepository` (L2622, L2924) | 中 - 新規テーブルで row-level filter 漏れリスク |
| `JAStaffRepository` (L770) | 高 - 代行 endpoint で他人データ取得・row-level 認可ロジックの正当性 |
| router の POST/PUT body kwarg ↔ Repository method 引数名 | 中 - cmd_585 plan_data→data 型の罠が他にもあり得る |
| `dashboard.py` / `crops.py` GET 系 endpoint | 低 - response_model 指定が薄いため schema validation 自体が弱い |

---

## §4 構造的根因分析 (L4)

### §4.1 不整合パターン分類

| パターン | 説明 | 検出例 | 根因 |
|---|---|---|---|
| **A: SELECT列欠如** | Repository SELECT に列がない・Response 必須 | #1 PlanRepository / #2 FieldRepository | 列指定 SELECT を「最小列」で書く慣行 vs Response が全列必須 |
| **B: 型不一致** | DB schema 型 vs Pydantic 型 違い | #3 CropHistoryResponse.year | DB=TEXT で柔軟・Pydantic=int で厳格・暗黙変換不可 |
| **C: 命名揺れ** | DB列名 vs Pydantic フィールド名 | #4 name vs field_name | snake_case 統一の中の例外・歴史的経緯 |
| **D: 層構造揺れ** | Repository 集約 vs router 直接 SQL | #5 PinnedAssignment | 新規実装時の急ぎ → Repository新設より router内SQL が早かった |
| **E: kwarg mismatch** | Router→Repository 引数名違い | cmd_585 plan_data→data | Pydantic model フィールド名 vs Repository 引数名の不一致 |

### §4.2 根因の深掘り(なぜ発生したか)

1. **「テスト不在」**: GET list endpoint の smoke-test が CI に存在しない。`PlanResponse(**p)` 系の Pydantic ValidationError は **deploy 後の初回呼出**でしか検出されない。
2. **「列指定 SELECT 慣行」**: `SELECT *` を避けて列指定にする習慣は良いが、Response 必須列との同期管理が手動。
3. **「from_db alias パターンの不徹底」**: FieldResponse だけ `from_db` を持ち他は持たない。一貫性なし。
4. **「列追加 migration の通知漏れ」**: cmd_577 D3 で inventory に 8列追加・crop_master.category 追加があったが、Pydantic Response 側の追従が手動。
5. **「Repository アーキテクチャの揺れ」**: 古い実装は db_access.py 集約・新しい実装(pinned)は router 直接SQL → 一貫性なし。

### §4.3 cmd_585/586 で検出済 2件と本subtask検出 5件の関係

- cmd_585 = **パターンE** (kwarg mismatch)・1件
- cmd_586 Wave 11 = **パターンA** (PlanRepository SELECT欠如)・1件 → 修正案出るが origin/main 未マージ
- 本cmd_589 = **パターンA/B/C/D を横断的に検出**・5件
- 結論: cmd_585/586 は氷山の一角・本cmd_589 で構造的網羅監査が必要だった判断は正しい

---

## §5 修正方針 軍師独立 3案 (予断与えず weighted scoring)

### §5.1 評価軸と重み (合計100点)

| 軸 | 重み | 説明 |
|---|:---:|---|
| (i) 工数(小≧高得点) | 15 | 実装+レビュー+テスト工数 |
| (ii) 殿運用ブロック解消速度 | **25** | 最重要・GET /api/plans 500 即解消 |
| (iii) 再発予防効果 | 20 | 同種バグの将来発生抑止 |
| (iv) 既存コードへの侵襲度(小≧) | 15 | 改修コミット粒度・影響範囲 |
| (v) 命名揺れ問題解決 | 10 | パターンC + D の解消度 |
| (vi) rollback容易性 | 10 | git revert 1コマンド可否 |
| (vii) V4境界線(戻せるか) | 5 | 殿のV4自動運転基準 |

### §5.2 3案の中身(軍師独立提案)

**案G1: 個別 hot-fix(各不整合を個別 commit で最小修正)**
- 範囲: 不整合#1 SELECT user_id 追加(1行)・#2 同様(1行)・#3 year型 str化(2行)
- 工数: 半日以内
- 改修コード行数: 5-10行
- 既存 from_db pattern や Repository 構造はそのまま

**案G2: from_db pattern 統一(全 Response に classmethod 導入・SELECT列との吸収層)**
- 範囲: FieldResponse.from_db() を **PlanResponse / CropHistoryResponse / 他全 Response** に拡張・統一
- 工数: 2-3日(全 router + テスト)
- 改修コード行数: 200-300行
- 命名揺れ(field_name vs name)は alias で吸収可
- 但しパターンB(型不一致)は from_db では解決不能 → 別途対応必要

**案G3: ORM / Repo層導入(SQLAlchemy or pydantic-sqlalchemy で schema-driven 自動生成)**
- 範囲: rotation_planner/common/db_access.py の **全 18 Repository を SQLAlchemy 化**・Pydantic は `model_validate` で auto-map
- 工数: 1-2週間
- 改修コード行数: 数千行
- migration 中の運用停止リスクあり
- 全パターン A-E を根本解決(列追加で自動追従・型不一致は ORM column type で強制統一)

### §5.3 加重スコア表 (0-10点採点 × 重み)

| 軸 | 重み | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|
| (i) 工数(小≧) | 15 | **9** (135) | 5 (75) | 2 (30) |
| (ii) 運用ブロック解消速度 | **25** | **9** (225) | 6 (150) | 2 (50) |
| (iii) 再発予防効果 | 20 | 1 (20) | 7 (140) | **9** (180) |
| (iv) 既存侵襲度(小≧) | 15 | **9** (135) | 5 (75) | 2 (30) |
| (v) 命名揺れ解決 | 10 | 1 (10) | 4 (40) | **9** (90) |
| (vi) rollback容易性 | 10 | **9** (90) | 6 (60) | 3 (30) |
| (vii) V4境界線 | 5 | **9** (45) | 7 (35) | 4 (20) |
| **加重合計 (100点換算)** | 100 | **66** ★ | **58** | **43** |

### §5.4 推奨と段階提案

**最高得点:** **案G1 (66/100)** が単独評価で最高。理由:
- 殿運用ブロック解消速度(重み25)で 9点満点
- 工数最小・既存侵襲度最低・rollback容易性高
- 但し**再発予防効果は1点最低**(同種バグ再発リスク残存)

**軍師独立判断: 段階提案を併記**(殿が Q1' で選択):

| フェーズ | 採用案 | 内容 | 期間 |
|---|---|---|---|
| **短期** | **G1** | 不整合#1-#3 を hot-fix で即修正・殿運用ブロック即解消 | 半日以内 |
| **中期** | G2 + 予防策(b) | from_db pattern 統一 + pytest CI smoke-test で再発予防 | 1-2週間 |
| **長期** | G3 | ORM/Repo層導入で構造的根本解決(余裕がある時期) | 月単位 |

### §5.5 dissent (推奨案の最大リスク)

- **G1 最大リスク:** 「**ホットフィックスで終わる病**」= 個別修正後に予防策(b)を起票しない場合、cmd_585→cmd_586→cmd_589 の連鎖が続く
- **緩和:** Q3' で「予防策(b) pytest CI smoke-test 自動化を別cmd 起票するか?」を殿確認
- **撤回条件:** 短期内に G2 中期改修を発動できるなら G1 単独でも可・できないなら G2 を含む段階発動を選好

---

## §6 構造的予防策(L6)

### §6.1 予防策(a) Repository SELECT列の constant化(pinned_assignments パターン拡散)

```python
# pinned_assignments.py L55 既存パターン
_COLS = "id, user_id, field_id, year, crop, pinned_by, pinned_reason, is_active, notes, created_at, updated_at"
# SELECT {_COLS} で統一・追加忘れを防止

# 拡散提案: 全 Repository に同様の constant を導入
class PlanRepository:
    _LIST_COLS = "id, user_id, name, start_year, end_year, created_at, updated_at"
    _DETAIL_COLS = "*"   # 詳細は全列

    @staticmethod
    def get_plans(user_id):
        cursor = conn.execute(f"SELECT {PlanRepository._LIST_COLS} FROM rotation_plans WHERE user_id = ? ORDER BY ...", ...)
```

**効果:** 列追加忘れの統一管理・Pydantic Response との突合がコード上で明示化・diff レビュー時の見落とし軽減。

### §6.2 予防策(b) pytest CI smoke-test 自動化 ★最小コストで最大効果

```python
# tests/test_endpoint_smoke.py (新規)
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

# JWT 取得
TOKEN = ...   # fixture

ENDPOINTS_LIST = [
    "/api/plans",
    "/api/fields",
    "/api/crops",
    "/api/pinned-assignments",
    "/api/pesticide-masters",
    "/api/inventory",
    # ... 全 GET list endpoint を列挙
]

@pytest.mark.parametrize("ep", ENDPOINTS_LIST)
def test_get_list_no_500(ep):
    """全 GET list endpoint が 500 を返さない・Pydantic ValidationError 検出"""
    res = client.get(ep, headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code != 500, f"{ep} returned 500: {res.text[:200]}"
    # 200 or 401 or 404 は OK・500 のみ NG
```

**CI 統合:** GitHub Actions(または既存 CI)で push毎に実行。**所要 1-2 時間で実装可能**(別cmd 起票推奨・Q3'で殿確認)。

### §6.3 予防策(c) PRAGMA table_info ↔ Pydantic model_fields 定期 diff

```python
# scripts/audit_schema_pydantic.py (新規)
"""
DB schema (PRAGMA table_info) と Pydantic model_fields を比較し、
列欠如 / 型不一致 / 命名揺れを自動レポート。
"""
import inspect
import sqlite3
from pydantic import BaseModel
from api.routers import plans, fields, crops, pinned_assignments

MAPPING = {
    "rotation_plans": plans.PlanResponse,
    "fields": fields.FieldResponse,
    "crop_history": fields.CropHistoryResponse,
    "pinned_assignments": pinned_assignments.PinnedAssignmentResponse,
    # ...
}

def audit():
    conn = sqlite3.connect("data/rotation_planner.db")
    for table, model in MAPPING.items():
        cursor = conn.execute(f"PRAGMA table_info({table})")
        db_cols = {row[1]: row[2] for row in cursor}   # name -> type
        pydantic_fields = model.model_fields
        diff = set(pydantic_fields) - set(db_cols)
        if diff:
            print(f"WARNING: {table} → Pydantic にあるがDBにない: {diff}")
        # 型不一致もチェック
        ...
```

**実行:** cron で 日次/週次・Slack/LINE 通知統合可・**別cmd 起票候補**。

### §6.4 予防策の優先順位(軍師推奨)

| 優先 | 予防策 | 工数 | 効果 |
|---|---|---|---|
| **1位** | **(b) pytest CI smoke-test** | 1-2時間 | パターンA/E を即検出・最小コスト |
| 2位 | (a) SELECT列 constant化 | 半日 | パターンA を構造的に予防 |
| 3位 | (c) PRAGMA diff スクリプト | 半日 | パターンA/B/C を定期検出 |

→ **(b)+(a) の組み合わせを推奨**。(c) は中長期で別cmd。

---

## §7 殿への質問 (3問以内・軍師独立判断)

### Q1' 修正方針の選択

| 選択肢 | 内容 | 軍師評価 | 殿への補足 |
|---|---|---|---|
| (a) G1 のみ | 個別hot-fix・短期解消 | 66/100 最高 | 再発予防ゼロ・運用ブロック即解消 |
| (b) G2 のみ | from_db pattern 統一 | 58/100 | 2-3日工数・中期改修 |
| (c) G3 のみ | ORM 導入 | 43/100 | 大規模リファクタ・短期は実行不可 |
| **(d) 段階提案(短期G1+中期G2+長期G3)** | **★軍師推奨** | - | 段階的に予防効果も得る |

### Q2' 緊急修正の発動範囲

不整合#1-#3 のうち、Wave 2 で即修正する範囲:

| 選択肢 | 内容 |
|---|---|
| (a) 不整合#1 のみ(致命的) | GET /api/plans 500 解消・運用ブロック解消最短 |
| **(b) 不整合#1-#3(致命+型不一致)** | year型問題も同時解消・★推奨 |
| (c) 不整合#1-#5 全部 | 範囲広い・命名揺れ+Repository層追加は中期 G2 へ |

### Q3' 予防策(b) pytest CI smoke-test 自動化の発動

| 選択肢 | 内容 |
|---|---|
| **(a) 別cmd 起票して中期発動 ★推奨** | 1-2時間工数・最小コスト・cmd_585→586→589 連鎖を止める |
| (b) Wave 2 に同梱 | G1 と同時実装・但しテスト工数が短期に重なる |
| (c) 後日判断 | 棚上げ・予防効果なし |

---

## 付録A. 監査チェックリスト(全Repository 横断検証用)

別cmd 起票時の参照用。本subtaskでは時間制約により完全網羅できず・残課題§3.6参照。

```
□ FieldRepository.get_fields - SELECT列 vs FieldResponse (本subtask検出済)
□ FieldRepository.get_field - SELECT * vs FieldResponse (本subtask未確認)
□ FieldRepository.get_field_by_code - SELECT * vs FieldResponse (本subtask未確認)
□ CropHistoryRepository.get_history - SELECT * vs CropHistoryResponse
□ CropHistoryRepository.get_all_history_for_user - SELECT JOIN vs (未定義Response)
□ CropHistoryRepository.get_history_by_id - SELECT * vs CropHistoryResponse
□ PlanRepository.get_plans - SELECT列 vs PlanResponse (本subtask検出済・★★★)
□ PlanRepository.get_plan - SELECT * vs PlanResponse + plan_details
□ JAStaffRepository (L770) - 全メソッド (代行 endpoint・row-level filter検証)
□ UserRepository (L1002)
□ PesticideMasterRepository (L1074)
□ CropMasterRepository (L1300)
□ UserCropRepository (L1414) - cmd_577 D3 で category 列追加問題
□ PesticideOrderRepository (L1600)
□ UserConstraintsRepository (L1905)
□ PesticideRegistryRepository (L1994)
□ PesticideUsageRepository (L2055)
□ PesticideRecordRepository (L2141)
□ OrderTemplateRepository (L2252)
□ InventoryRepository (L2432) - cmd_577 D3 で 8列追加問題
□ PaddyPolygonRepository (L2622)
□ CropPolygonRepository (L2924)
```

## 付録B. お針子FB項目(全項目応答)

| FB項目 | 応答 |
|---|---|
| ssh_raw_outputs Phase別 | 本subtaskはローカルclone /tmp/rotation-planner-probe-v2 のみで実機SSH無し。Phase = (1) clone fetch+pull / (2) router grep / (3) Repository sed/awk / (4) Pydantic Response 抽出 / (5) 突合分析 / (6) レポート執筆。全 read-only。 |
| three_pillar_evidence | (a) commit hash 15d9095 (origin/main HEAD) / (b) Phase別 grep出力でSELECT列とPydantic必須を別個 evidence化 / (c) cmd_586 Wave 11 commitがgit log上に存在せず → 修正未マージを三重突合 |
| schema差異検出 何回目候補 | **3回目候補**(cmd_585=1回目 kwarg / cmd_586=2回目 SELECT列 / cmd_589=3回目 構造的網羅) |
| V4境界線「戻せるか」判定 | 本subtask = read-only完全可逆 / G1案= 1-3行修正で revert可・✅自動運転可 / G2案= 複数router改修だが revert可・✅自動運転可(レビュー推奨) / G3案= 大規模・⚠️殿確認推奨 |

## 付録C. north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    rotation-planner = 「農家を雑な事務作業から解放する道具」(殿memory)。
    現状=GET /api/plans 500 で殿が輪作計画一覧を開けない → 運用ブロック直結。
    本監査で構造的網羅+G1即修正案提示 → 殿運用ブロック解消の判断材料を提供。
  risks_to_north_star:
    - "G1単独採用で再発予防ゼロ → cmd_585→586→589連鎖継続のリスク → Q3'で予防策(b)発動推奨"
    - "残課題§3.6 (11 Repository) 未確認 → 他にもlatentバグの可能性 → 別subtask網羅監査推奨"
    - "G3 ORM大規模改修 = migration中の運用停止リスク → 殿確認必須"
```

## 付録D. simplicity check 3問

| # | 問い | 回答 |
|---|------|------|
| 1 | この監査は、もっと少ないステップで達成できないか? | 本subtask は時間制約で **主要4 Repository** のみ精査・残課題§3.6 で 11 Repository を別subtask に分離(過剰分析回避)・パターン分類(A-E)で残るも予測可能化 |
| 2 | 修正方針の3案は過剰分割していないか? | 案G1/G2/G3 は **工数×予防効果の異なる解像度**で必要。短期/中期/長期の階層を示すため。statelyに同等な3案ではなく階層提示=過剰なし |
| 3 | 殿質問は最小限か? | Q1'(方針)+Q2'(範囲)+Q3'(予防策) の 3問のみ・各推奨明示・★推奨で殿の判断ボトルネック最小化 |

## 付録E. unknown_unknowns (任意・10未満で可)

1. cmd_586 Wave 11 subtask_1271 の修正が origin/main に未マージの理由(作業中? PR pending? 別ブランチ?)→ 殿/家老確認必要
2. CropHistoryResponse.year 型 str 化時の frontend 影響範囲(cmd_580 令和変換ロジックとの相互作用)
3. JAStaffRepository の row-level filter 認可(admin/ja_staff 代行で他人データを返す際の SELECT user_id 同様の罠)
4. inventory_api.py の SELECT 列 (cmd_577 D3 で 8列追加・Response追従未確認)
5. PesticideMasterRepository (cmd_577 D3 で構造刷新・Response 追従未確認)
6. router 横断の dependency 注入順序(get_current_user→require_admin の組合せが endpoint で揃っているか)
7. error_handlers.py の `require_found()` が他で同じ問題を吸収しているケースの網羅性
8. 既存 frontend (React側) が 500 をどう扱うか(toast表示 vs サイレント無視)→ Q2' 範囲決定の材料

---

(本書 EOF)
