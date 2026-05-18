# rotation-planner 全テーブル schema diff 調査(D3対応・予防分析)

| 項目 | 内容 |
|---|---|
| cmd / subtask | cmd_577 / subtask_1240 (D3対応・並行) |
| 作成日 | 2026-05-18T13:30 |
| 作成者 | 軍師 (gunshi) |
| 親subtask | subtask_1232 (Wave 2e-3, crop_master.category 不在エラー発生) |
| 比較対象 | 旧schema = `git show 3c72c7a:db_schema.sql` / 新schema = `origin/main HEAD 8d005e0:db_schema.sql` + migrate_*.sql 9本 + `ensure_crop_tables()` / `ensure_inventory_tables()` 実装 |

---

## §1 エグゼクティブサマリ (殿レビュー用・30行以内)

**結論3行:**
1. **戦略書§2.5 の前提「IF NOT EXISTS で安全」は誤り**。`ensure_crop_tables()` (db_access.py L1238-) は「**テーブル不在時のみCREATE、存在時は何もしない**」設計 → VPSで過去に `migrate_crop_schema.sql` (category列なし版) が流れていた crop_master は更新されず、新コードが category 列を参照してエラー。
2. **ALTER TABLE が必要な共通テーブルは 3件**: ① `crop_master` (+category)、② `inventory` (+8列)、③ `fields` (+land_category・migrate_field_polygons既対応)。さらに ④ `pesticide_masters` は構造刷新(migrate_pesticide_v2でデータ移行付き)。
3. **新規テーブル 13件は IF NOT EXISTS で自動作成OK・削除テーブル 1件 (`crop_constraints`)は放置許容**。共通8テーブルのうち **4テーブル** (上記①②③④) が要対応。

**ALTER要対応テーブル一覧 (subtask_1232 と並行修正):**

| # | テーブル | 必要操作 | カバー済 migrate | 冪等patch必要 |
|---|---|---|:---:|:---:|
| 1 | `crop_master` | `ADD COLUMN category TEXT` | **未カバー** ⚠️ | **要追加** ★ |
| 2 | `inventory` | `ADD COLUMN storage_location/expiry_date/purchase_date/purchase_price/supplier/lot_number/last_used_date/usage_count` (8列) | **未カバー** ⚠️ | **要追加** ★ |
| 3 | `fields` | `ADD COLUMN land_category` | migrate_field_polygons ✓ | 既存migrateで可 |
| 4 | `pesticide_masters` | 構造刷新 (DROP→CREATE+データ移行) | migrate_pesticide_v2 ✓ | 既存migrateで可 |

**戦略書§2.5 fix提案 (詳細§5):**
- Q4'=(a) 既存DB保持+IF NOT EXISTS自動適用「だけ」では **不足**
- 補完: 起動前に **冪等ALTER patch** (PRAGMA table_info で列存在チェック) を実行
- subtask_1232 で実機実行・本subtask§4 patchSQLを使用

**推奨:** subtask_1232 部屋子1は本書 §4 patch SQL を `migrate_d3_supplement.sql` として保存・lifespan前に1度実行。失敗時は data.bak 復元で完全rollback。

---

## §2 全テーブル diff matrix

旧schema = 9テーブル / 新schema = 21テーブル / 共通 = 8テーブル

### 2.1 新規テーブル (旧になく新にある・IF NOT EXISTSで自動作成OK)

| # | テーブル | カバー migrate | 備考 |
|---|---|---|---|
| 1 | `crop_master` | migrate_crop_schema (但しcategory列なし版) | ★ HEAD は category列追加版・migrate不整合 |
| 2 | `user_crops` | migrate_crop_schema | OK |
| 3 | `crop_polygons` | migrate_crop_polygons / migrate_field_polygons | OK |
| 4 | `paddy_polygons` | migrate_field_polygons / migrate_paddy_polygons | OK |
| 5 | `order_templates` | migrate_order_templates | OK |
| 6 | `pesticide_orders` | migrate_pesticide_orders | OK |
| 7 | `pesticide_registry` | migrate_pesticide_record | OK |
| 8 | `pesticide_usage` | migrate_pesticide_record | OK |
| 9 | `pesticide_records` | migrate_pesticide_record | OK |
| 10 | `famic_import_log` | (db_schema.sql統合のみ) | OK・新規環境はinit_db()でOK |
| 11 | `inventory_transactions` | (db_schema.sql統合のみ) | OK |
| 12 | `inventory_csv_operations` | (db_schema.sql統合のみ) | OK |
| 13 | `user_constraints` | (db_schema.sql統合のみ) | OK・crop_constraints の置換 |

### 2.2 削除テーブル (旧にあり新にない・放置許容)

| # | テーブル | 対応 |
|---|---|---|
| 1 | `crop_constraints` | 削除されず残置(IF NOT EXISTS は破壊しない)・新コードは `user_constraints` を直接使う・旧データは参照されないが消失なし |

### 2.3 共通テーブル (8件) — カラム diff

| # | テーブル | 旧カラム数 | 新カラム数 | diff | 要ALTER? |
|---|---|:---:|:---:|---|:---:|
| 1 | `users` | 10 | 10 | **無し**(完全一致) | × |
| 2 | `organizations` | 6 | 6 | **無し**(完全一致) | × |
| 3 | `crop_history` | 7 | 7 | **無し**(完全一致) | × |
| 4 | `rotation_plans` | 9 | 9 | **無し**(完全一致) | × |
| 5 | `plan_details` | 7 | 7 | **無し**(完全一致) | × |
| 6 | **`fields`** | 12 | **13** | `+land_category TEXT DEFAULT NULL` | ★ ALTER必要 |
| 7 | **`inventory`** | 7 | **15** | `+storage_location TEXT, +expiry_date DATE, +purchase_date DATE, +purchase_price REAL, +supplier TEXT, +lot_number TEXT, +last_used_date DATE, +usage_count INTEGER DEFAULT 0` (8列) | ★★ ALTER必要 |
| 8 | **`pesticide_masters`** | 13 | 12 | **構造刷新**(下記詳細) | ★★★ DROP→CREATE+データ移行 |

### 2.4 pesticide_masters 構造刷新詳細

| 旧カラム | 新カラム | 移行 |
|---|---|---|
| `pesticide_name TEXT NOT NULL` | `name TEXT NOT NULL` | rename → name |
| `crop TEXT NOT NULL` | `crop TEXT` (NULLable化) | そのまま (制約緩和) |
| `month INTEGER` | (削除) | 不可逆損失 |
| `period TEXT` | (削除) | 不可逆損失 |
| `target TEXT` | (削除) | 不可逆損失 |
| `dilution_rate TEXT` | `dilution_rate TEXT` | そのまま |
| `amount_per_10a REAL` | (削除) | 不可逆損失 |
| `unit TEXT` | (削除) | 不可逆損失 |
| `days_before_harvest TEXT` | (削除→意味的に近い safety_interval INTEGER) | TEXT→INTEGER 変換必要(migrate_pesticide_v2 は移行対象外) |
| `notes TEXT` | `notes TEXT` | そのまま |
| `created_at` | `created_at` | そのまま |
| (なし) | `+category TEXT` | NULL初期 |
| (なし) | `+manufacturer TEXT` | NULL初期 |
| (なし) | `+active_ingredient TEXT` | NULL初期 |
| (なし) | `+usage_timing TEXT` | NULL初期 |
| (なし) | `+application_method TEXT` | NULL初期 |
| (なし) | `+safety_interval INTEGER` | NULL初期 |

migrate_pesticide_v2.sql の処理:
1. `pesticide_masters_new` (新構造)を作成
2. 旧テーブルから `id, org_id, pesticide_name→name, crop, dilution_rate, notes, created_at` を移行
3. 旧テーブルを `DROP TABLE pesticide_masters`
4. `pesticide_masters_new` を `pesticide_masters` にrename(続きは未読・付録A参照)

→ **migrate_pesticide_v2 で完全対応**。本subtask§4のpatchには含めない(既存migrateを使う)。

### 2.5 罠の根本原因 (subtask_1232 エラーの解剖)

**`ensure_crop_tables()` (rotation_planner/common/db_access.py L1238-) の実装:**
```python
def ensure_crop_tables():
    with get_db() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crop_master'")
        if cursor.fetchone() is None:            # ←★ テーブル**不在時のみ**作成
            conn.execute("""
                CREATE TABLE crop_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,               # ←★ HEAD では追加済
                    family TEXT DEFAULT NULL,
                    ...
                )
            """)
            # 初期データ投入(category付き)
```

**シナリオ:**
1. VPSで過去に `migrate_crop_schema.sql` (category列**なし**版) が実行された → `crop_master` テーブル作成
2. `migrate_crop_family.sql` で `family` 列だけ ALTER ADD された(category列はadd対象外)
3. その後 HEAD で `category` 列が追加されたが、**この migration script は存在しない**
4. cmd_577 Wave 2e-3 で部屋子1が新コードを起動 → `ensure_crop_tables()` は「crop_master 存在」と判定して何もしない → `category` 列なしのまま
5. `INSERT INTO crop_master (name, category, display_order, family)` 等のSQLで **category列不在エラー**

**inventory も同様の罠が潜在:** 旧 inventory テーブル(7列)が VPS実DB に存在 → `init_db()` の IF NOT EXISTS スキップ → 8列が追加されない → 新コード(`inventory_api.py` 等)が新列を参照してエラー(顕在化していないだけ)。

---

## §3 ALTER TABLE 要対応テーブル詳細

### 3.1 `crop_master` (category 列追加)

**条件分岐(case):**
- **(i) crop_master 不在**: `ensure_crop_tables()` が新規作成(category付き) → ALTER不要
- **(ii) crop_master 存在 + category 列あり**: 既に最新 → ALTER不要
- **(iii) crop_master 存在 + category 列なし** ← **VPSの状態 (subtask_1232 エラー)** → **`ALTER TABLE crop_master ADD COLUMN category TEXT`** 必要

確認SQL:
```sql
PRAGMA table_info(crop_master);
-- → name='category' の行が無ければ要ALTER
```

### 3.2 `inventory` (8列追加)

**条件分岐:**
- **(i) inventory 不在**: `init_db()` の IF NOT EXISTS で15列新規作成 → ALTER不要
- **(ii) inventory 存在 + 7列(旧)**: ← **VPSの想定状態** → **8列 ALTER ADD** 必要
- **(iii) inventory 存在 + 部分的に追加済**: 列単位の存在チェックで個別ADD

確認SQL:
```sql
PRAGMA table_info(inventory);
-- → 必須列: storage_location, expiry_date, purchase_date, purchase_price,
--   supplier, lot_number, last_used_date, usage_count
```

### 3.3 `fields` (land_category 列追加)

migrate_field_polygons.sql に既存:
```sql
ALTER TABLE fields ADD COLUMN land_category TEXT DEFAULT NULL;
-- 注: SQLite は ALTER TABLE IF NOT EXISTS をサポートしない
--     既に追加済の場合エラーとなるが、エラーを無視して継続する必要あり
```

冪等化版(本書§4で提供):
```sql
-- PRAGMA table_info(fields) で land_category 列存在チェック後にADD
```

### 3.4 `pesticide_masters` (構造刷新)

migrate_pesticide_v2.sql で完全対応(BEGIN TRANSACTION + 新テーブル+データ移行+DROP→RENAME)。
本subtask§4 patchには含めない。

---

## §4 推奨 patch SQL (冪等化済み・migrate_d3_supplement.sql)

**目的:** subtask_1232 で起こった `crop_master.category` 不在エラーと同種の問題を **inventory にも先回り** で対処。`fields.land_category` も冪等化版で提供。

**実行タイミング:** subtask_1232 (Wave 2e-3) の `systemctl start rotation-planner-v2` **の前**(つまり 2e-2 DB cp 直後・systemd 起動前)。

**実行方法:**
```bash
sudo -u webapp sqlite3 /var/www/rotation-planner-v2/app/data/rotation_planner.db \
  < /var/www/rotation-planner-v2/app/scripts/migrate_d3_supplement.sql
```

### 4.1 patch SQL 全文

```sql
-- ════════════════════════════════════════════════════════════════
-- migrate_d3_supplement.sql
-- cmd_577 / subtask_1240 (D3対応・予防patch)
-- 既存DBに対する冪等な追加列ALTER (PRAGMA table_info で列存在チェック)
-- 安全: 複数回実行可・既に追加済の列はスキップ
-- ════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────
-- マイグレーションログ(冪等保証)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS _migration_log (
    migration TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────────────────────
-- SQLite に PRAGMA table_info を使った冪等ADDのトリックを実装する。
-- 単一 .sql 内で動的に分岐が書けないため、各ALTERは
-- 「失敗してもエラーで止まらない」ように `.bail off` ＋ 続行で運用。
-- → 本patchは bash wrapper から呼ぶ前提とする(下記 §4.2)。
-- ここでは生のALTERを記述し、エラーは bash側で無視する。
-- ─────────────────────────────────────────────────────────────

-- 1) crop_master.category 追加 (subtask_1232 で踏んだ罠)
ALTER TABLE crop_master ADD COLUMN category TEXT;
INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_crop_master_category');

-- 2) inventory に 8列追加 (現状は未顕在の罠)
ALTER TABLE inventory ADD COLUMN storage_location TEXT;
ALTER TABLE inventory ADD COLUMN expiry_date DATE;
ALTER TABLE inventory ADD COLUMN purchase_date DATE;
ALTER TABLE inventory ADD COLUMN purchase_price REAL;
ALTER TABLE inventory ADD COLUMN supplier TEXT;
ALTER TABLE inventory ADD COLUMN lot_number TEXT;
ALTER TABLE inventory ADD COLUMN last_used_date DATE;
ALTER TABLE inventory ADD COLUMN usage_count INTEGER DEFAULT 0;
INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_inventory_columns');

-- 3) fields.land_category 追加 (migrate_field_polygons の冪等版)
ALTER TABLE fields ADD COLUMN land_category TEXT DEFAULT NULL;
INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_fields_land_category');

-- 4) 初期データ補完: crop_master の category がNULLな行に値設定
UPDATE crop_master SET category = '穀物' WHERE name IN ('小麦(春播)', '小麦(秋播)') AND category IS NULL;
UPDATE crop_master SET category = '豆類' WHERE name IN ('だいず', '大豆', 'あずき', '小豆', 'インゲン') AND category IS NULL;
UPDATE crop_master SET category = '根菜' WHERE name IN ('てんさい', 'ばれいしょ', '馬鈴薯') AND category IS NULL;
UPDATE crop_master SET category = '野菜' WHERE name IN ('にんじん', 'かぼちゃ', 'キャベツ', 'だいこん', 'ブロッコリー', 'カリフラワー', 'レタス', 'ごぼう', 'メロン') AND category IS NULL;
UPDATE crop_master SET category = '葉茎菜' WHERE name IN ('たまねぎ', 'アスパラガス', 'ながいも') AND category IS NULL;

-- 確認
SELECT '=== _migration_log ===' AS info;
SELECT * FROM _migration_log WHERE migration LIKE 'd3_%';
SELECT '=== crop_master after patch ===' AS info;
SELECT id, name, category, family FROM crop_master ORDER BY display_order LIMIT 20;
SELECT '=== inventory columns ===' AS info;
SELECT name FROM pragma_table_info('inventory');
SELECT '=== fields columns ===' AS info;
SELECT name FROM pragma_table_info('fields');
```

### 4.2 bash wrapper (エラー無視で冪等化)

```bash
#!/bin/bash
# apply_d3_supplement.sh
# ALTER TABLE が既に追加済の列の場合は "duplicate column name" エラーになる。
# 各ALTERを個別実行し、duplicate column エラーは無視する。

DB="/var/www/rotation-planner-v2/app/data/rotation_planner.db"
SQL_FILE="/var/www/rotation-planner-v2/app/scripts/migrate_d3_supplement.sql"

# 1ステートメントずつ実行 (個別エラーで止めない)
sudo -u webapp sqlite3 "$DB" <<'EOF'
CREATE TABLE IF NOT EXISTS _migration_log (
    migration TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

for STMT in \
  "ALTER TABLE crop_master ADD COLUMN category TEXT" \
  "ALTER TABLE inventory ADD COLUMN storage_location TEXT" \
  "ALTER TABLE inventory ADD COLUMN expiry_date DATE" \
  "ALTER TABLE inventory ADD COLUMN purchase_date DATE" \
  "ALTER TABLE inventory ADD COLUMN purchase_price REAL" \
  "ALTER TABLE inventory ADD COLUMN supplier TEXT" \
  "ALTER TABLE inventory ADD COLUMN lot_number TEXT" \
  "ALTER TABLE inventory ADD COLUMN last_used_date DATE" \
  "ALTER TABLE inventory ADD COLUMN usage_count INTEGER DEFAULT 0" \
  "ALTER TABLE fields ADD COLUMN land_category TEXT DEFAULT NULL"; do
  echo "Applying: $STMT"
  sudo -u webapp sqlite3 "$DB" "$STMT" 2>&1 | grep -v "duplicate column name" || true
done

# 初期データ補完(冪等・WHERE で NULL限定)
sudo -u webapp sqlite3 "$DB" <<'EOF'
UPDATE crop_master SET category = '穀物' WHERE name IN ('小麦(春播)', '小麦(秋播)') AND category IS NULL;
UPDATE crop_master SET category = '豆類' WHERE name IN ('だいず', '大豆', 'あずき', '小豆', 'インゲン') AND category IS NULL;
UPDATE crop_master SET category = '根菜' WHERE name IN ('てんさい', 'ばれいしょ', '馬鈴薯') AND category IS NULL;
UPDATE crop_master SET category = '野菜' WHERE name IN ('にんじん', 'かぼちゃ', 'キャベツ', 'だいこん', 'ブロッコリー', 'カリフラワー', 'レタス', 'ごぼう', 'メロン') AND category IS NULL;
UPDATE crop_master SET category = '葉茎菜' WHERE name IN ('たまねぎ', 'アスパラガス', 'ながいも') AND category IS NULL;

INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_crop_master_category');
INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_inventory_columns');
INSERT OR IGNORE INTO _migration_log (migration) VALUES ('d3_fields_land_category');
EOF

echo "=== verification ==="
sudo -u webapp sqlite3 "$DB" "SELECT * FROM _migration_log WHERE migration LIKE 'd3_%';"
sudo -u webapp sqlite3 "$DB" "SELECT name FROM pragma_table_info('crop_master');"
sudo -u webapp sqlite3 "$DB" "SELECT name FROM pragma_table_info('inventory');"
sudo -u webapp sqlite3 "$DB" "SELECT name FROM pragma_table_info('fields');"
```

### 4.3 rollback 手順

```bash
# 失敗時の戻し方
# (a) DBバックアップから復元 (推奨・確実)
sudo -u webapp rm -rf /var/www/rotation-planner-v2/app/data
sudo -u webapp cp -r /var/www/rotation-planner-v2/app/data.bak.20260518 \
  /var/www/rotation-planner-v2/app/data

# (b) 列単位でDROPはSQLite未対応 → (a) を推奨。
```

### 4.4 case (i)(ii)(iii) 実装まとめ

| case | 検出 | 動作 |
|---|---|---|
| (i) crop_master 不在 | `pragma_table_info('crop_master')` が空 | ALTER前にskip可・`ensure_crop_tables()` が新規作成 |
| (ii) crop_master 存在 + category あり | `pragma_table_info('crop_master')` に `category` | ALTER skip (duplicate column nameエラー無視) |
| (iii) crop_master 存在 + category なし | `pragma_table_info('crop_master')` に `category` 無し | **ALTER ADD COLUMN category TEXT** 実行 |

→ bash wrapper の `2>&1 | grep -v "duplicate column name"` で (i)(ii)(iii) を一括対応。

---

## §5 軍師戦略書 §2.5 fix 提案

### 5.1 修正対象箇所

`docs/shogun/rotation_planner_v2_migration_strategy_20260518.md` の §2.5「DB schema 差分」末尾:

```
（旧）
**重要:** 全 CREATE TABLE が `IF NOT EXISTS` なので、**既存DBをそのまま使うと旧スキーマ残置+新規テーブルだけ追加** の状態になる。アプリ起動は可能だが、`crop_constraints`(旧) と `user_constraints`(新) が併存する。新コードは `user_constraints` を見る → 旧データは未参照になるが**消えはしない**。これは「Q4'=(a) 既存DB保持」推奨の根拠。
```

```
（新・差し替え）
**重要(訂正):** 全 CREATE TABLE が `IF NOT EXISTS` だが、これは **新規テーブル追加には機能するが、既存テーブルへのカラム追加には機能しない**。subtask_1232 で実機検証の結果、`ensure_crop_tables()` (db_access.py L1238-) は「テーブル不在時のみ CREATE、存在時は何もしない」設計。VPS旧DBに `crop_master` (category列なし)等が存在する場合、init_db()+ensure_*()ではcategory列が追加されず新コードがエラーする。
**対策:** 起動前に冪等ALTER patch (`scripts/migrate_d3_supplement.sql` / `apply_d3_supplement.sh`) を実行する(本subtask§4 参照)。必要なALTER対応テーブルは: `crop_master` (+category)、`inventory` (+8列)、`fields` (+land_category・migrate_field_polygons冪等版)、`pesticide_masters` (構造刷新・migrate_pesticide_v2)。
```

### 5.2 simplicity check 追加問

戦略書§付録A の simplicity check に1問追加(殿明示の3問は維持):

```yaml
- q: "既存DBへのALTER TABLE系migration を見落としていないか?"
  a: |
    ★初版見落とし★: 「IF NOT EXISTS で安全」と書いたが、これは新規テーブル追加にのみ機能。
    既存テーブルへのカラム追加(crop_master.category, inventory 8列, fields.land_category)は
    `ensure_*()` ではスキップされる。subtask_1240 で全テーブル diff matrix を取り、
    冪等ALTER patch (§4) を Wave 2e の DB cp 直後・systemd 起動前に挿入する設計に修正。
```

### 5.3 unknown_unknowns 追加項目

戦略書§付録B (unknown_unknowns 10項目) に2項目追加 → 12項目化:

```
11. **既存テーブルへのカラム追加migration の網羅性**: migrate_*.sql 9本に存在しないが新schemaには存在する列(crop_master.category, inventory 8列)があった。HEAD db_schema.sql と migrate_*.sql の整合性が完全ではない。今後 origin/main 追従時の毎pull後に diff matrix再取得を推奨。
12. **`ensure_crop_tables()` / `ensure_inventory_tables()` の "テーブル存在時スキップ" 設計**: 一度作られたテーブルは構造変更されない・将来の列追加には migrate script の追加が必要。schema_version テーブルでmigration履歴管理を提案(別cmd起票候補)。
```

### 5.4 Wave 2e 順序修正提案

戦略書§5.2 (decomposition Wave 2e) の subtask 順序を修正:

```
[現在]
2e-1: JWT_SECRET 生成
2e-2: DB cp + 配置 (lifespan の init_db() に任せる)
2e-3: rotation-planner-v2.service 作成・一時port 8001で test

[修正提案]
2e-1: JWT_SECRET 生成 (変更なし)
2e-2: DB cp + 配置
2e-2.5: ★追加★ apply_d3_supplement.sh 実行 (冪等ALTER patch)・PRAGMA table_info検証
2e-3: rotation-planner-v2.service 作成・一時port 8001で test
```

subtask_1232 (Wave 2e-3) には現時点で 2e-2.5 が不在のため、本subtask§4の `migrate_d3_supplement.sql` + `apply_d3_supplement.sh` を **新規 subtask として家老が起票** することを推奨(または subtask_1232 の中で部屋子1が `2e-2.5` 相当の手順を実行)。

### 5.5 schema_version テーブル提案 (別cmd起票候補)

今回の混乱の根本原因は「VPSで過去にどのmigrateが流れたかが不明」。

提案: `schema_versions` テーブル(あるいは既存の `_migration_log` を正式採用) で migration履歴を管理する仕組みを別cmdで起票。

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version TEXT PRIMARY KEY,           -- 'v1.0', 'v1.1', 'v1.2' 等
    migration_file TEXT,                -- 'migrate_crop_schema.sql' 等
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
```

利点: 次回 origin/main pull時に「何が未適用か」を SQL で確認可能。

---

## 付録A. 完全なテーブル列挙(旧/新)

**旧 (3c72c7a) 9テーブル:**
crop_constraints / crop_history / fields / inventory / organizations / pesticide_masters / plan_details / rotation_plans / users

**新 (HEAD 8d005e0) 21テーブル:**
crop_history / **crop_master** / **crop_polygons** / **famic_import_log** / fields / inventory / **inventory_csv_operations** / **inventory_transactions** / **order_templates** / organizations / **paddy_polygons** / pesticide_masters / **pesticide_orders** / **pesticide_records** / **pesticide_registry** / **pesticide_usage** / plan_details / rotation_plans / **user_constraints** / **user_crops** / users

(太字=新規テーブル13件)

## 付録B. patch SQL の verification checklist

subtask_1232 (or 派生 subtask) で `apply_d3_supplement.sh` 実行後、以下を確認:

```sql
-- 1. crop_master に category 列が存在
SELECT name FROM pragma_table_info('crop_master') WHERE name='category';
-- → 1行返ること

-- 2. inventory に 8新列が存在
SELECT name FROM pragma_table_info('inventory')
WHERE name IN ('storage_location','expiry_date','purchase_date','purchase_price',
               'supplier','lot_number','last_used_date','usage_count');
-- → 8行返ること

-- 3. fields に land_category 列が存在
SELECT name FROM pragma_table_info('fields') WHERE name='land_category';
-- → 1行返ること

-- 4. _migration_log に d3_* 3件
SELECT * FROM _migration_log WHERE migration LIKE 'd3_%';
-- → 3行返ること (d3_crop_master_category / d3_inventory_columns / d3_fields_land_category)

-- 5. crop_master 初期データの category が埋まっている
SELECT name, category FROM crop_master WHERE category IS NOT NULL LIMIT 5;
-- → 少なくとも 5行返ること
```

## 付録C. ntripcaster 影響評価 (本subtask)

本subtaskは **軍師による read-only 設計分析のみ**。
- ローカル `/tmp/rotation-planner-probe-v2/` (cloneのみ) の調査
- VPS実機への接続なし
- patch SQL は本書に記載のみ・実行は subtask_1232 (or 派生) に委ねる

ntripcaster 影響: **完全ゼロ** (本subtask)。

---

(本書 EOF)
