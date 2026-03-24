# rotation-planner 委託業務モデル設計書

> **分析日**: 2026-03-22 | **軍師**（gunshi）
> **North Star**: 農業の現実を写し取れ。地主と作業者は別の人間だ

---

## 0. 現状分析

### 現行スキーマの「user_id問題」

```
fields.user_id ──→ users.id
                    │
                    ├── 「アプリのユーザー」
                    ├── 「ほ場の地主（荷主）」  ← 暗黙の前提
                    └── 「実際に畑を耕す人」    ← 暗黙の前提
```

**現実**: この3つは同一人物とは限らない。

| ケース | 地主 | 作業者 | アプリユーザー | 現行の扱い |
|--------|------|--------|---------------|-----------|
| 自作 | 田中さん | 田中さん | 田中さん | ✅ user_id=田中 で問題なし |
| 全委託 | 高齢の鈴木さん | 受託の田中さん | 田中さん | ❌ user_id=田中。鈴木さんが見えない |
| 一部委託（コンバインだけ） | 佐藤さん | 佐藤さん+田中さん(収穫のみ) | 佐藤さん | ❌ 田中さんの関与が記録されない |
| 年度変更 | 鈴木さん | 今年:田中、来年:佐藤 | ? | ❌ user_id は年度概念がない |

### 影響を受けるテーブル

| テーブル | user_id の意味 | 委託導入の影響 |
|---------|---------------|--------------|
| `fields` | ほ場の登録者（≒地主） | **直撃**: owner_id分離が必要 |
| `rotation_plans` | 計画の作成者 | **影響あり**: 全委託時の責任者問題 |
| `crop_history` | field_id経由 | 間接的 |
| `plan_details` | plan_id/field_id経由 | 間接的 |
| `user_constraints` | 制約の所有者 | 影響小 |
| `pesticide_records` | 散布記録者 | **影響あり**: 受託者が記録する場合 |
| `pesticide_orders` | 発注者 | **影響あり**: 受託者が代理発注する場合 |
| `inventory` | 在庫所有者 | 影響小 |

---

## 1. データモデル設計（最重要）

### 1a. 設計方針: 「最小侵襲」の原則

**やらないこと（過剰設計の回避）:**
- usersテーブルのroleに「landowner」「operator」を追加しない
  - 理由: 同一人物が地主でもあり受託者でもある。roleは排他的ではない
- fields.user_idの意味を変えない
  - 理由: 19テーブル+全API+フロントエンドに波及する。本番稼働中で致命的

**やること:**
- `owner_id` カラムを `fields` に追加（nullable）
- `field_contracts` テーブルを新設（年度別委託関係）
- 既存クエリの動作を一切壊さない

### 1b. fields テーブル拡張

> **注**: §8 裁定3-bにより owner_id は NOT NULL に変更。

```sql
-- Phase 1: owner_id追加（非破壊的マイグレーション）
-- 裁定3-b: NOT NULL。デフォルトは自分（user_id）
ALTER TABLE fields ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0;
UPDATE fields SET owner_id = user_id WHERE owner_id = 0;
-- owner_id = user_id → 自作（地主 = 管理者 = アプリユーザー）
-- owner_id ≠ user_id → 地主は別人、user_id（管理者）が実質耕作者
```

**解釈ルール:**
```python
def get_owner(field):
    """ほ場の地主（荷主）を返す"""
    return field.owner_id  # 裁定3-b: 常にowner_idが入っている

def get_operator(field):
    """ほ場の実質管理者を返す"""
    return field.user_id  # 常にuser_id = 管理者

def is_self_operated(field):
    """自作かどうか"""
    return field.owner_id == field.user_id
```

**なぜ user_id を「管理者」側に残すか:**
- 現行の全クエリが `WHERE user_id = ?` で「自分のほ場一覧」を取得している
- 受託者（田中さん）が日常的に使うのは自分が管理するほ場の一覧
- user_id = 管理者 のまま保てば、既存クエリの変更がゼロ
- 地主（鈴木さん）がほ場を見たい場合は `WHERE owner_id = ?` で別途取得

### 1c. field_contracts テーブル（作期別委託関係）

> **注**: §8の殿裁定3-a/3-b/3-cで大幅変更あり。下記は裁定適用後の最終形。

```sql
-- 前提: contractors テーブル（§8 裁定3-a）、crop_seasons テーブル（§8 裁定3-c）が先に存在

CREATE TABLE IF NOT EXISTS field_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    crop_season_id INTEGER NOT NULL REFERENCES crop_seasons(id),  -- 裁定3-c: fiscal_year→作期
    owner_user_id INTEGER NOT NULL REFERENCES users(id),          -- 裁定3-b: NOT NULL化
    owner_name TEXT,                               -- 地主名テキスト（地主=自分の場合は不要）
    contractor_id INTEGER NOT NULL REFERENCES contractors(id),    -- 裁定3-a: operator→contractor
    scope_type TEXT NOT NULL CHECK (scope_type IN ('full', 'partial')),
    scope_operations TEXT,  -- JSON配列: partial時の作業リスト
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_id, crop_season_id, contractor_id)  -- 裁定1踏襲+3-a/3-c適用
);
CREATE INDEX IF NOT EXISTS idx_field_contracts_field ON field_contracts(field_id);
CREATE INDEX IF NOT EXISTS idx_field_contracts_season ON field_contracts(crop_season_id);
CREATE INDEX IF NOT EXISTS idx_field_contracts_owner ON field_contracts(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_field_contracts_contractor ON field_contracts(contractor_id);
```

### 1d. 委託スコープの表現

```python
# scope_type = 'full' の場合
# → scope_operations は NULL or 空（全作業を委託）

# scope_type = 'partial' の場合
# → scope_operations に委託する作業をJSON配列で列挙
scope_operations_example = [
    "耕起",      # tillage
    "播種",      # seeding
    "防除",      # pest control
    "施肥",      # fertilization
    "収穫",      # harvesting
    "乾燥調製",   # drying/conditioning
]

# 例: コンバイン刈り取りだけ委託
# scope_type = 'partial', scope_operations = '["収穫"]'

# 例: 管理全部委託
# scope_type = 'full', scope_operations = NULL
```

**作業リストを固定マスタにしない理由:**
- 地域・作物によって作業の分類が異なる
- 「播種」と「定植」は作物によって使い分ける
- マスタ管理のコストに対してROIが低い
- JSON配列でフリーテキスト許容が現実的

### 1e. 年度変更・作期への対応

> **注**: §8 裁定3-cにより fiscal_year → crop_season_id に変更。

```
2026水稲作期(4月-10月): F001 → 鈴木(地主) → 田中(受託/全委託)
2026秋小麦作期(8月-翌8月): F001 → 鈴木(地主) → 佐藤(受託/一部委託:収穫のみ)
2027水稲作期: F001 → 鈴木(地主) → 自作（契約解除）
```

**表現:**
```sql
-- 作期を先に作成
INSERT INTO crop_seasons (name, start_date, end_date, fiscal_year, crop_type)
VALUES ('2026水稲', '2026-04-01', '2026-10-31', 2026, '水稲');

INSERT INTO crop_seasons (name, start_date, end_date, fiscal_year, crop_type)
VALUES ('2026秋小麦', '2026-08-01', '2027-08-31', 2026, '秋小麦');

-- 2026水稲: 全委託
INSERT INTO field_contracts
  (field_id, crop_season_id, owner_user_id, contractor_id, scope_type)
VALUES (1, /* 2026水稲.id */, 鈴木.id, /* 田中のcontractor.id */, 'full');

-- 2026秋小麦: 収穫のみ委託（年度またぎ）
INSERT INTO field_contracts
  (field_id, crop_season_id, owner_user_id, contractor_id, scope_type, scope_operations)
VALUES (1, /* 2026秋小麦.id */, 鈴木.id, /* 佐藤のcontractor.id */, 'partial', '["収穫"]');

-- 2027水稲: レコードなし → 自作
```

**設計判断:** 「契約なし = 自作」とする暗黙のデフォルト。これにより:
- 現行データに契約レコードを追加する必要がない（全て「自作」扱い）
- 委託開始時にのみレコードを作成する
- **秋小麦のような年度またぎ作期も、crop_seasonsのstart_date/end_dateで自然に表現できる**

---

## 2. 輪作計画への影響

### 2a. 全委託の場合

| 項目 | 現行 | 委託導入後 |
|------|------|-----------|
| 計画の作成者 | `rotation_plans.user_id` | **受託者**のuser_id（作業する人が計画を立てる） |
| ほ場の見え方 | user_idでフィルタ | 受託ほ場も見える（fields.user_id = 受託者） |
| 制約設定 | user_constraints.user_id | 受託者が自分の全ほ場（自作+受託）に対して制約を設定 |

**設計判断:** 全委託の場合、輪作計画の責任者は**受託者**。
- 理由: 受託者が畑を実際に管理し、作物ローテーションを決める
- 地主は結果を見るだけ（UIで閲覧権限を設定）

### 2b. 一部委託の場合

コンバイン収穫のみ委託の場合、輪作計画は**地主**（自作農家）が管理。
受託者はその年の「収穫」タスクだけ見えればよい。

→ **rotation_plans, plan_details は変更不要**。
fields.user_idが計画の管理者を示し、これは変わらない。

### 2c. crop_history への影響

crop_historyは `field_id` 経由で紐づく。field_idは変わらないため影響なし。
委託の有無に関わらず、作付履歴はほ場に紐づく。

---

## 3. 出荷管理システムとの連携設計

### 3a. アーキテクチャ

```
┌─────────────────────┐     ┌─────────────────────┐
│  rotation-planner   │     │  出荷管理システム     │
│  (SQLite DB A)      │     │  (SQLite DB B)       │
│                     │     │                      │
│  fields             │────→│  lots                │
│  field_contracts    │     │    .field_id (参照)   │
│  users              │     │    .owner_user_id     │
│  paddy_polygons     │     │  shipments           │
│  crop_polygons      │     │  warehouses          │
└─────────────────────┘     └──────────────────────┘
        │                              │
        └── API経由で連携 ──────────────┘
```

### 3b. 連携インターフェース

**rotation-planner → 出荷管理（提供API）:**

```python
# 荷主のほ場一覧（出荷管理のロット生成に使用）
GET /api/fields/by-owner/{owner_user_id}
# → owner_id = owner_user_id OR (owner_id IS NULL AND user_id = owner_user_id)

# ほ場の当年作物（ロットの作物自動入力に使用）
GET /api/fields/{field_id}/current-crop?year=2026
# → 既存エンドポイント（変更なし）

# ほ場のポリゴン（ジオフェンス判定に使用）
GET /api/fields/{field_id}/polygon
# → paddy_polygons or crop_polygons の geometry を返す
```

**出荷管理 → rotation-planner（参照のみ）:**
- `lots.field_id` で rotation-planner の field を参照
- `lots.owner_user_id` で荷主を参照（rotation-planner の users.id と一致）

### 3c. Phase 0 暫定運用（rotation-planner未拡張時）

```
出荷管理システム単独で動作:
┌──────────────────────┐
│  出荷管理 (DB B)     │
│                      │
│  owners              │ ← 独自テーブル（rotation-planner非依存）
│    .id               │
│    .name             │
│    .phone            │
│  lots                │
│    .owner_id         │ ← owners.id を参照
│    .field_code       │ ← 文字列（rotation-planner連携なし）
│    .crop             │ ← 手入力
└──────────────────────┘
```

**Phase 1移行時:** `owners.id` を `rotation-planner.users.id` にマッピング。
`lots.field_code` を `rotation-planner.fields.id` にマッピング。

### 3d. 暫定→正式の移行パス

```
Phase 0: 出荷管理 owners テーブル（独自管理）
  ↓ マイグレーション: owners.name で rotation-planner.users.display_name と突合
Phase 1: lots.owner_id → rotation-planner.users.id にFK追加
  ↓ field_code → field_id の突合
Phase 1+: lots.field_id → rotation-planner.fields.id にFK追加
```

---

## 4. マイグレーション戦略

### 4a. Phase別の変更範囲

| Phase | 変更対象 | 破壊的？ | 移行手順 |
|-------|---------|---------|---------|
| **Phase 0** | 出荷管理のみ | ❌ | rotation-planner変更なし |
| **Phase 1** | fields テーブル | ❌ | ALTER TABLE ADD COLUMN (nullable) |
| **Phase 2** | field_contracts テーブル | ❌ | CREATE TABLE (新規) |

### 4b. Phase 1 マイグレーション手順

```sql
-- 1. owner_idカラム追加（既存データに影響なし）
ALTER TABLE fields ADD COLUMN owner_id INTEGER REFERENCES users(id);

-- 2. 既存データ: owner_id = NULL のまま
--    → 解釈: owner_id IS NULL = 自作（user_id = 地主 = 作業者）
--    → データ移行不要

-- 3. インデックス追加
CREATE INDEX IF NOT EXISTS idx_fields_owner ON fields(owner_id);
```

**API後方互換性:**
```python
# 既存API: 変更なし
GET /api/fields  # user_idでフィルタ → 管理するほ場が返る（従来通り）

# 新規API追加
GET /api/fields/by-owner/{owner_id}  # 地主のほ場一覧
GET /api/fields/{field_id}/contract?year=2026  # 委託情報
```

### 4c. Phase 2 マイグレーション手順

```sql
-- field_contracts テーブル新規作成（既存テーブルに影響なし）
CREATE TABLE IF NOT EXISTS field_contracts (...);

-- 既存データ: 委託関係をユーザーが手動登録
-- バッチインポート機能（CSV）も用意すべき
```

### 4d. models.py 変更

> **注**: §8裁定3-a/3-b/3-c適用後の最終形。

```python
# Phase 1: Field dataclass にowner_id追加
@dataclass
class Field:
    id: int
    user_id: int      # 管理者（実質的な操作者）
    owner_id: int      # 地主（裁定3-b: NOT NULL、デフォルト=user_id）
    field_code: str
    # ... 以下既存フィールド

    @property
    def is_self_operated(self) -> bool:
        """自作かどうか"""
        return self.owner_id == self.user_id

# Phase 1: 裁定3-a 受託者マスタ
@dataclass
class Contractor:
    id: int
    user_id: Optional[int]  # アプリユーザーの場合
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None

# Phase 1: 裁定3-c 作期
@dataclass
class CropSeason:
    id: int
    name: str                  # "2026秋小麦"
    start_date: str            # "2026-08-01"
    end_date: str              # "2027-08-31"
    fiscal_year: int           # 播種年度
    crop_type: Optional[str] = None

# Phase 1: FieldContract（裁定3-a/3-b/3-c適用後）
@dataclass
class FieldContract:
    id: int
    field_id: int
    crop_season_id: int        # 裁定3-c: fiscal_year→作期
    owner_user_id: int         # 裁定3-b: NOT NULL
    contractor_id: int         # 裁定3-a: operator→contractor
    scope_type: str            # 'full' | 'partial'
    scope_operations: Optional[str] = None  # JSON配列
    owner_name: Optional[str] = None
    notes: Optional[str] = None
```

### 4e. db_access.py 変更

```python
# Phase 1: FieldRepository に追加
@staticmethod
def get_fields_by_owner(owner_id: int) -> List[Dict[str, Any]]:
    """地主のほ場一覧（owner_id一致 + owner_id=NULLかつuser_id一致）"""
    return db.execute("""
        SELECT * FROM fields
        WHERE owner_id = ? OR (owner_id IS NULL AND user_id = ?)
        ORDER BY district, field_code
    """, (owner_id, owner_id))

# Phase 2: FieldContractRepository 新規
class FieldContractRepository:
    @staticmethod
    def get_contract(field_id: int, year: int) -> Optional[Dict]:
        ...
    @staticmethod
    def set_contract(field_id, year, owner_id, operator_id, scope_type, operations=None):
        ...
```

---

## 5. 推奨案

### 5a. 段階的実装Wave案

```
Wave 1: Phase 0 — 出荷管理暫定運用
  ├── 出荷管理DBに独自owners + lots テーブル
  ├── rotation-planner変更なし
  └── 期間: 出荷管理MVP開発中（急がない）

Wave 2: Phase 1 — owner概念の分離
  ├── fields に owner_id 追加（ALTER TABLE）
  ├── models.py に effective_owner_id プロパティ追加
  ├── GET /api/fields/by-owner/{id} API追加
  ├── フロントに「地主」表示欄追加（任意入力）
  └── 期間: 1-2 subtask

Wave 3: Phase 2 — 委託テーブル
  ├── field_contracts テーブル新規作成
  ├── FieldContractRepository 新規
  ├── 委託管理API（CRUD）
  ├── 年度切替時の契約コピー機能
  ├── フロントに委託管理画面
  └── 期間: 3-5 subtask
```

### 5b. 代替案比較

| 案 | 説明 | 利点 | 欠点 | スコア |
|----|------|------|------|--------|
| **A: 3段階移行（推奨）** | Phase 0→1→2で段階的に | 非破壊的、各Phase独立して動作、撤退容易 | Wave 3まで全機能揃わない | **9** |
| **B: users.roleに地主/受託者追加** | roleを拡張 | シンプル | 同一人物が地主兼受託者のケースに対応不可。排他ロール前提のcan_access_all_dataが壊れる | 3 |
| **C: 別テーブルで完全分離（owners+operators）** | 新テーブル2つ | 正規化が完全 | fieldsからの参照を大幅に変更。API互換性破壊。19テーブル+全クエリに波及 | 4 |
| **D: JSON拡張（fields.metadata_json）** | 既存のカラムに追加情報を埋め込む | スキーマ変更ゼロ | 検索不可、型安全なし、将来の移行が困難 | 2 |

### 5c. 冒険的な案

**「ほ場ビュー」方式**: 物理テーブルを変更せず、VIEWで仮想的にownerを解決する。

```sql
CREATE VIEW field_ownership AS
SELECT
    f.*,
    COALESCE(fc.owner_user_id, f.user_id) AS effective_owner_id,
    COALESCE(fc.operator_user_id, f.user_id) AS effective_operator_id,
    fc.scope_type,
    fc.scope_operations
FROM fields f
LEFT JOIN field_contracts fc
    ON f.id = fc.field_id
    AND fc.fiscal_year = strftime('%Y', 'now');
```

利点: 既存クエリを一切変更せず、新クエリだけVIEWを使う。
リスク: VIEWは書き込み不可（INSERTできない）。パフォーマンスは実測が必要。
**Phase 1をスキップしてPhase 2に直行できる可能性がある。**

---

## 6. 見落としの可能性

1. **JA職員の視点**: JA職員（ja_staff）は管内の全ほ場を見る。委託関係もJA単位で集約表示が必要になるかもしれないが、現時点では設計しない
2. **地主がアプリを使わないケース**: owner_idがusersを参照するが、地主がアプリに登録していない場合がある。owner_idをnullableにした理由の一つだが、「地主名だけテキストで持つ」方が現実的かもしれない
3. **防除記録の帰属**: 受託者が散布した場合、pesticide_records.user_idは受託者。地主の帳簿に載せる必要がある場合の考慮が不足
4. **複数受託者**: 同一ほ場・同一年度に複数の受託者がいるケース（耕起は田中さん、収穫は佐藤さん）。UNIQUE(field_id, fiscal_year)だと1件しか入らない → 複数契約が必要な場合はUNIQUE制約を外す必要あり
5. **農薬発注への影響**: 受託ほ場の面積を受託者の発注計算に含めるか。含めるなら既存の面積集計ロジックに影響

**4番は重要。** 設計を修正すべきかもしれない:

```sql
-- 修正案: UNIQUE制約を (field_id, fiscal_year, operator_user_id) に変更
UNIQUE(field_id, fiscal_year, operator_user_id)
-- → 同一ほ場・同一年度に複数受託者を許可（作業が異なる場合）
```

---

## 7. 殿裁定（2026-03-22）

### 裁定1: 複数受託者 → 採用
`UNIQUE(field_id, fiscal_year, operator_user_id)` に変更。
耕起=田中、収穫=佐藤のケースは現実にある。耕作者が管理責任を持つ。

### 裁定2: 地主未登録 → owner_name テキスト保存
`field_contracts` に `owner_name TEXT` を追加。`owner_user_id` は nullable に変更。
理由: 子供3人が相続して全員県外在住、というパターンが実在する。
耕作者が地主名を入力するしかない。

### 裁定3: 防除記録 → 耕作者帰属
防除記録は耕作者（受託者）の帳簿に帰属。地主側への転記は対象外。
理由: 実質的に防除作業は耕作者のみが行うため。

### 設計原則（裁定から導出）
**「耕作者が主体」で一貫。地主は権利者であって管理者ではない。**

---

## 8. 殿裁定 第2弾（2026-03-24）

### 裁定3-a: 受託者テーブルの独立管理

**裁定**: 委託元（受託者）を `field_contracts` に埋め込まず、別テーブル `contractors` で独立管理。
`fields.user_id` とは別の外部キーで紐付け。

**理由**: 受託者は複数のほ場を横断して受託する。受託者の情報（名前・連絡先等）をほ場ごとに重複させるのは正規化に反する。

**設計変更**:

```sql
-- 新規テーブル: contractors（受託者マスタ）
CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),  -- アプリユーザーの場合
    name TEXT NOT NULL,                     -- 受託者名（user未登録でも可）
    phone TEXT,                             -- 連絡先（任意）
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_contractors_user ON contractors(user_id);
```

**field_contracts テーブルの変更**:

```sql
-- 旧: operator_user_id INTEGER NOT NULL REFERENCES users(id)
-- 新: contractor_id INTEGER NOT NULL REFERENCES contractors(id)

CREATE TABLE IF NOT EXISTS field_contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    crop_season_id INTEGER NOT NULL REFERENCES crop_seasons(id),  -- 裁定3-cで変更（後述）
    owner_user_id INTEGER NOT NULL REFERENCES users(id),          -- 裁定3-bで変更（後述）
    owner_name TEXT,                                               -- 地主名テキスト（owner_user_id=自分の場合は不要）
    contractor_id INTEGER NOT NULL REFERENCES contractors(id),     -- 裁定3-aで変更
    scope_type TEXT NOT NULL CHECK (scope_type IN ('full', 'partial')),
    scope_operations TEXT,  -- JSON配列: partial時の作業リスト
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_id, crop_season_id, contractor_id)  -- 裁定1踏襲: 同一作期に複数受託者を許可
);
```

**contractors vs users の関係**:
```
contractors.user_id → users.id（nullable）
  ├── user_id あり → アプリユーザーとして登録済みの受託者（自分のほ場も見える）
  └── user_id なし → アプリ未登録の外部受託者（名前と連絡先のみ）
```

→ 裁定2（owner_name テキスト保存）と同じ思想を受託者側にも適用。
usersテーブルに全員を登録する必要はない。

### 裁定3-b: owner_id NOT NULL + デフォルト自分

**裁定**: 地主未登録の場合は自分（生産者 = アプリユーザー）のものとする。NULL不可。デフォルトは自分のuser_id。

**設計変更**:

```sql
-- 旧: fields テーブル
-- ALTER TABLE fields ADD COLUMN owner_id INTEGER REFERENCES users(id);  -- nullable

-- 新: owner_id NOT NULL, デフォルト = user_id
ALTER TABLE fields ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0 REFERENCES users(id);
-- ※ SQLite ALTER TABLE ADD COLUMN に DEFAULT が必要。マイグレーション時に user_id をコピー。
```

**マイグレーション手順**:
```sql
-- Step 1: カラム追加（仮のデフォルト値0）
ALTER TABLE fields ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 0;

-- Step 2: 既存データを user_id で埋める（自作 = 自分が地主）
UPDATE fields SET owner_id = user_id WHERE owner_id = 0;

-- Step 3: 外部キー制約はSQLiteの制約により後付けできない
-- → アプリ層で参照整合性を担保
```

**解釈ルールの変更**:
```python
# 旧:
def get_owner(field):
    return field.owner_id if field.owner_id else field.user_id

# 新（裁定3-b適用後）:
def get_owner(field):
    return field.owner_id  # 常にowner_idが入っている。NULL不可。
    # 自作の場合: owner_id == user_id
    # 委託の場合: owner_id != user_id
```

**field_contracts.owner_user_id も NOT NULL に変更**:
```sql
owner_user_id INTEGER NOT NULL REFERENCES users(id),  -- 裁定3-b: NULL不可
```

→ 「地主がアプリ未登録の場合」は `owner_name` テキストで保持しつつ、
`owner_user_id` は管理している受託者自身のIDを入れる。
（= 「自分のほ場として管理するが、真の地主は別にいる」という表現）

### 裁定3-c: 作期（crop_season）概念の導入

**裁定**: 年度区切りは3/31だが、秋小麦は8月〜翌8月。単純な `fiscal_year INTEGER` では表現できない。作期（crop_season）の概念を導入し、1つの作期が複数年度にまたがるケースを扱えるようにせよ。

**背景**:
```
稲作:     4月播種 → 10月収穫 → 同一年度内で完結
秋小麦:   8月畑起こし → 翌8月収穫 → 2年度にまたがる
冬野菜:   10月定植 → 翌3月収穫 → 年度をまたぐ
```

**新規テーブル: crop_seasons（作期マスタ）**:

```sql
CREATE TABLE IF NOT EXISTS crop_seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,              -- "2026秋小麦", "2026水稲" 等の表示名
    start_date TEXT NOT NULL,        -- 作期開始日 "2026-08-01"
    end_date TEXT NOT NULL,          -- 作期終了日 "2027-08-31"
    fiscal_year INTEGER NOT NULL,    -- 主たる年度（管理会計上）= 播種年度
    crop_type TEXT,                  -- "秋小麦", "水稲", "大豆" 等（任意）
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name)
);
CREATE INDEX IF NOT EXISTS idx_crop_seasons_year ON crop_seasons(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_crop_seasons_dates ON crop_seasons(start_date, end_date);
```

**設計判断**:

| 項目 | 判断 | 理由 |
|------|------|------|
| start_date/end_date | TEXT（ISO 8601） | SQLiteの日付型はTEXT。比較はそのまま可能 |
| fiscal_year | 播種年度で決定 | 管理会計・JA報告の単位。8月播種の秋小麦は2026年度 |
| crop_type | 任意 | 作期に紐づけるが必須ではない。crop_historyと二重管理にしない |
| name | ユニーク | "2026秋小麦(F001)" 等でほ場単位にしてもよいが、過剰設計の恐れ |

**field_contracts への反映**:

```sql
-- 旧: fiscal_year INTEGER NOT NULL
-- 新: crop_season_id INTEGER NOT NULL REFERENCES crop_seasons(id)
```

これにより:
```sql
-- 秋小麦の委託（2026年8月〜2027年8月）
INSERT INTO crop_seasons (name, start_date, end_date, fiscal_year, crop_type)
VALUES ('2026秋小麦', '2026-08-01', '2027-08-31', 2026, '秋小麦');

-- この作期に対する委託契約
INSERT INTO field_contracts
  (field_id, crop_season_id, owner_user_id, contractor_id, scope_type)
VALUES (1, /* crop_season.id */, 鈴木.id, /* contractor.id */, 'full');
```

**crop_history への影響**:

現行の crop_history に `crop_season_id` を追加すべきかは検討が必要:
```sql
-- 案: crop_history にも作期を紐付け
ALTER TABLE crop_history ADD COLUMN crop_season_id INTEGER REFERENCES crop_seasons(id);
```

ただし既存の crop_history は年度（year）ベースで動いている。
**Phase 1では crop_history は変更せず、field_contracts のみ crop_season_id を使用する。**
crop_history への拡張は Phase 2以降の検討事項とする。

### 裁定3-c 補足: field_ownership VIEW の更新

```sql
-- 旧: fiscal_year = strftime('%Y', 'now') でフィルタ
-- 新: 現在日付が作期の期間内かで判定

CREATE VIEW field_ownership AS
SELECT
    f.*,
    COALESCE(fc.owner_user_id, f.owner_id) AS effective_owner_id,
    c.name AS contractor_name,
    c.user_id AS contractor_user_id,
    fc.scope_type,
    fc.scope_operations,
    cs.name AS season_name,
    cs.fiscal_year
FROM fields f
LEFT JOIN field_contracts fc
    ON f.id = fc.field_id
LEFT JOIN crop_seasons cs
    ON fc.crop_season_id = cs.id
    AND date('now') BETWEEN cs.start_date AND cs.end_date
LEFT JOIN contractors c
    ON fc.contractor_id = c.id;
```

---

## 9. 更新後のテーブル関連図

```
users
  │
  ├──→ fields.user_id（管理者=耕作者）
  ├──→ fields.owner_id（地主。NOT NULL、デフォルト=user_id）【裁定3-b】
  │
  ├──→ contractors.user_id（受託者がアプリユーザーの場合）
  │         │
  │         └──→ field_contracts.contractor_id【裁定3-a】
  │
  ├──→ field_contracts.owner_user_id（地主）
  │
  └──→ rotation_plans.user_id（変更なし）

crop_seasons【裁定3-c 新規】
  │
  └──→ field_contracts.crop_season_id

fields ←── field_contracts.field_id
```

---

## 10. 更新後のPhase別実装計画

### Phase 0: 出荷管理暫定運用（変更なし）
rotation-planner変更なし。出荷管理側で独自owner管理。

### Phase 1: owner分離 + contractors + crop_seasons

| 順序 | 作業 | subtask粒度 |
|------|------|------------|
| 1-1 | `fields` に `owner_id` カラム追加 + マイグレーション（全レコードに user_id をコピー） | 1 subtask |
| 1-2 | `contractors` テーブル新規作成 + FieldContractRepository | 1 subtask |
| 1-3 | `crop_seasons` テーブル新規作成 | 1 subtask |
| 1-4 | `field_contracts` テーブル新規作成（crop_season_id + contractor_id 参照） | 1 subtask |
| 1-5 | `field_ownership` VIEW 作成 | 1-2 と同一subtask |
| 1-6 | API追加: `GET /api/fields/by-owner/{id}`, `GET /api/contractors`, `GET /api/crop-seasons` | 1 subtask |
| 1-7 | models.py 更新: Field.owner_id, FieldContract, Contractor, CropSeason dataclass追加 | 1 subtask |

**計: 5-6 subtask、足軽2名で2-3日**

### Phase 2: フロントエンド + 委託管理画面

| 順序 | 作業 | subtask粒度 |
|------|------|------------|
| 2-1 | ほ場一覧に「地主」表示欄追加 | 1 subtask |
| 2-2 | 委託管理画面（CRUD） | 2-3 subtask |
| 2-3 | 作期管理画面 | 1-2 subtask |
| 2-4 | 年度/作期切替時の契約コピー機能 | 1 subtask |

**計: 5-7 subtask、足軽2-3名で3-5日**

---

## 11. 見落としの可能性（更新）

前回の6件に加えて:

7. **crop_seasons の粒度問題**: 作期をほ場単位にするか全体単位にするか。秋小麦の播種時期がほ場ごとに異なる場合、ほ場単位の作期が必要になる可能性。ただし現時点では全体単位で十分
8. **crop_seasons と crop_history の二重管理**: crop_history.year と crop_seasons.fiscal_year が異なる意味を持つ可能性。統合は Phase 2以降
9. **contractors テーブルの肥大化**: 受託者が多い地域では contractors が大きくなる。ただし農業法人が数十〜数百件程度なので実用上の問題なし
10. **fiscal_year の定義**: 播種年度 vs 収穫年度で混乱が生じうる。**播種年度で統一**する設計原則を明示すべき

---

*本文書は軍師（gunshi）による戦略分析である。殿裁定により設計更新（2026-03-24）。*
