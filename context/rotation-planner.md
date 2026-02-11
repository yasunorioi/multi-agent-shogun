# rotation-planner 畑作農業管理アプリ

> **リポジトリ**: `github.com:yasunorioi/rotation-planner.git` (ローカル: `/home/yasu/rotation-planner`)
> priority: P1 | karo: roju
> Updated: 2026-02-11
> React版(FastAPI + Vite React)に一本化済み。Gradio版はレガシー凍結。
> mainマージ完了（2026-02-10）: feature/frontend-migration → main。78ファイル、+23,042行。

## 技術スタック

| Layer | 技術 | バージョン/備考 |
|-------|------|----------------|
| Frontend | React 18 + Vite | Zustand(状態管理), Leaflet(地図), Axios |
| Backend | FastAPI | Python, uvicorn |
| DB | SQLite | WALモード対応（Gradio版db.py） |
| 認証 | JWT | PyJWT, login/register/token |
| 最適化 | OR-Tools + JS Solver | Python版(OR-Tools) + JS版(軽量) |
| GIS | Shapely + pyproj | 空間演算・面積計算 |
| 農薬データ | FAMIC連携 | xlrd(XLS読み込み) |
| テスト | pytest | Backend: 8ファイル/148関数（React版） |

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────┐
│  React (Vite)                                       │
│  http://localhost:5173                               │
│  ├── Zustand (状態管理)                              │
│  ├── Leaflet + leaflet-draw (地図・ポリゴン描画)      │
│  └── Axios → /api/* へリクエスト                     │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP (JSON)
┌──────────────────▼──────────────────────────────────┐
│  FastAPI                                             │
│  http://localhost:8000                                │
│  ├── JWT認証ミドルウェア                              │
│  ├── api/main.py (3,630行 — 巨大ファイル注意)        │
│  ├── api/db_access.py (Repository層)                 │
│  └── api/models.py (データクラス)                     │
└──────────────────┬──────────────────────────────────┘
                   │ sqlite3
┌──────────────────▼──────────────────────────────────┐
│  SQLite                                              │
│  db_schema.sql + マイグレーションSQL群                │
│  19テーブル（共通12 + React拡張3 + Gradio GIS系2 +   │
│              マイグレーション系2）                    │
└─────────────────────────────────────────────────────┘
```

## ブランチ戦略

| ブランチ | 状態 | 説明 |
|---------|------|------|
| main | **現行開発ブランチ** | 2026-02-10に feature/frontend-migration をマージ済み |
| feature/frontend-migration | マージ済み | Gradio→React移行ブランチ（78ファイル、+23,042行） |

- **Gradio版はレガシー凍結**。今後の開発はReact版（main）のみ
- Gradio版のコード（portal.py, crop_settings.py等）はmainブランチに残存しているが、新規開発禁止

## DB設計（19テーブル）

### テーブル一覧

| # | テーブル名 | 用途 | 備考 |
|---|-----------|------|------|
| 1 | organizations | 組織マスタ（JA/個人） | id=1: JA北海道, id=2: 個人農家 |
| 2 | users | ユーザー | farmer/ja_staff/admin |
| 3 | fields | ほ場 | 11カラム（land_category含む） |
| 4 | crop_history | 作付履歴 | field_id + year でユニーク |
| 5 | rotation_plans | 輪作計画 | constraints_json に制約保存 |
| 6 | plan_details | 計画詳細 | plan×field×year の作付 |
| 7 | pesticide_masters | 防除マスタ | org_id=NULL で共通 |
| 8 | user_constraints | ユーザー制約 | constraints_json 内に隣接筆制約もJSON保存 |
| 9 | order_templates | 発注テンプレート | |
| 10 | inventory | 在庫 | React版で13カラムに拡張 |
| 11 | inventory_transactions | 入出庫履歴 | React版のみ |
| 12 | inventory_csv_operations | CSV操作ログ | React版のみ |
| 13 | **paddy_polygons** | **水田ポリゴン** | is_converted(畑地化), conversion_start_year |
| 14 | **crop_polygons** | **作付けポリゴン** | year別、crop_name別 |
| 15 | crop_master | 作物マスタ | family カラム（科名）含む。10作物シード |
| 16 | user_crops | ユーザー作物 | parent_crop_id → crop_master |
| 17 | pesticide_registry | 農薬登録(FAMIC) | registration_number でユニーク |
| 18 | pesticide_usage | 農薬適用(FAMIC) | pesticide_id → pesticide_registry |
| 19 | pesticide_orders | 農薬発注 | rotation_plan_id 連携 |

### マイグレーション注意事項

- テーブル1-12, 13-14: `db_schema.sql` に定義済み
- テーブル15-19: **別途マイグレーションSQLで作成**（db_schema.sqlに未統合）
  - `migrate_crop_schema.sql` → crop_master, user_crops
  - `migrate_pesticide_orders.sql` → pesticide_orders
  - `migrate_pesticide_record.sql` → pesticide_registry, pesticide_usage, pesticide_records, famic_import_log
  - `migrate_crop_family.sql` → crop_master に family カラム追加 + 9科シードデータ
- **課題**: 新規セットアップ時は db_schema.sql + 全マイグレーションSQL の実行が必要

### Gradio版のみ / React版のみ のテーブル差分

| 差分 | テーブル/カラム | 説明 |
|------|---------------|------|
| Gradio版で追加 | fields.land_category | 地目（畑/畑地化済/水田） |
| Gradio版で追加 | paddy_polygons | 水田ポリゴン管理 |
| Gradio版で追加 | crop_polygons | 作付けポリゴン管理 |
| Gradio版で追加 | crop_master.family | 作物科（migrate_crop_family.sql） |
| React版で拡張 | inventory (13カラム) | 保管場所, 有効期限, 仕入先等を追加 |
| React版のみ | inventory_transactions | 入出庫履歴 |
| React版のみ | inventory_csv_operations | CSV操作ログ |

## API構成（25エンドポイントグループ）

全て `api/main.py`（3,630行）に集約。将来の分割検討対象。

| グループ | パス | 主な機能 |
|---------|------|---------|
| 認証 | /api/auth/* | ログイン, ユーザー情報 |
| 管理 | /api/admin/* | ユーザー管理, バックアップ, システム情報 |
| ほ場 | /api/fields/* | CRUD, GPS, 作付履歴 |
| 輪作計画 | /api/plans/* | 計画CRUD |
| 制約 | /api/constraints/* | 輪作制約設定 |
| 作物 | /api/crops/*, /api/user-crops/*, /api/crop-families/* | 作物マスタ, ユーザー作物, 科マッピング |
| FAMIC | /api/famic/* | 農薬登録情報検索 |
| 防除 | /api/pesticide-masters/*, /api/pesticide-orders/*, /api/pesticide-records/* | マスタ, 発注, 記録 |
| 在庫 | /api/inventory/* | 在庫管理, 警告 |
| JA | /api/ja/* | JA集計 |
| 最適化 | /api/rotation/* | CSV入力, OR-Tools最適化, JS最適化 |
| GIS | /api/paddy-polygons/*, /api/crop-polygons/*, /api/aggregation/* | ポリゴンCRUD, 面積集計 |
| 筆ポリゴン | /api/fude-polygon/* | 農水省筆ポリゴン |
| GPS | /api/gps/* | 座標→ほ場マッチング |
| エクスポート | /api/export/* | CSV/KML出力 |
| ダッシュボード | /api/dashboard/* | 統計 |
| ヘルス | /api/health | ヘルスチェック |

### 認証方式

- JWT (PyJWT): login → access_token 発行 → Authorization: Bearer ヘッダー
- ロール: farmer, ja_staff, admin
- 初期ユーザー（db初期化時に自動作成）:
  - admin / admin123（管理者）
  - ja_staff / staff123（JA職員）
  - farmer_demo / demo123（農家デモ）

## フロントエンド（14ページ）

| # | パス | コンポーネント | 機能 |
|---|------|--------------|------|
| 1 | /login | Login | ログイン（公開） |
| 2 | / | Dashboard | ダッシュボード |
| 3 | /fields | Fields | ほ場一覧 |
| 4 | /field-register | FieldRegister | ほ場登録（Leaflet地図） |
| 5 | /rotation | Rotation | 輪作計画 |
| 6 | /plans | Plans | 計画一覧 |
| 7 | /crops | CropSettings | 作物設定 |
| 8 | /pesticide-orders | PesticideOrders | 農薬発注 |
| 9 | /pesticide-records | PesticideRecords | 防除記録 |
| 10 | /pesticide-masters | PesticideMasters | 防除マスタ |
| 11 | /data | DataManagement | データ管理 |
| 12 | /ja | JAAggregation | JA集計 |
| 13 | /users | UserManagement | ユーザー管理 |
| 14 | /system | SystemInfo | システム情報 |

ソースディレクトリ: `frontend/app/src/`

## データ標準

### FAMIC表記準拠

作物名は農林水産消費安全技術センター（FAMIC）の登録農薬検索で使用される正式名称に統一。

| FAMIC表記（正） | 旧Gradio版表記 |
|----------------|---------------|
| 小麦(春播) | 春小麦 |
| 小麦(秋播) | 秋小麦 |
| だいず | 大豆 |
| あずき | 小豆 |
| ばれいしょ | 馬鈴薯 |
| てんさい | （変更なし） |
| たまねぎ | 玉ねぎ |

### 作物科（crop_family）マッピング

隣接筆制約で使用。同科の作物を隣接ほ場で栽培しない。

| 科名 | 作物例 |
|------|--------|
| イネ科 | 小麦(春播), 小麦(秋播), とうもろこし, WCS |
| マメ科 | だいず, あずき, いんげん |
| アカザ科 | てんさい |
| ナス科 | ばれいしょ |
| アブラナ科 | キャベツ, だいこん, ブロッコリー, カリフラワー |
| セリ科 | にんじん |
| ウリ科 | かぼちゃ, メロン |
| キク科 | ごぼう, レタス |
| ユリ科 | たまねぎ, アスパラガス, ながいも |

## Gap Analysis サマリ

> 情報源: `docs/frontend_migration_gap_analysis.md`（subtask_334-336統合レポート）

### 全体状況

- 全36機能中 **26機能が移植済み**（React版）
- **P1欠落: 4件**（GIS系コア機能）
- React版が進んでいる機能: 4件
- 判定: **Conditional Go（条件付きマージ可）** → マージ完了済み（2026-02-10）

### P1欠落機能（4件）— 推定合計 4〜5日

| # | 機能 | 概要 | 推定工数 |
|---|------|------|---------|
| 1 | 水田ポリゴン | paddy_polygons テーブル + CRUD + KMLインポート | 2〜3日（2,3,4合算） |
| 2 | 作付けポリゴン | crop_polygons テーブル + CRUD + 前年コピー | （↑に含む） |
| 3 | 面積集計 | 作物×地目クロス集計 + 補助金サマリ + CSV出力 | （↑に含む） |
| 4 | crop_family + 隣接筆制約(PRO) | 科マッピング + 隣接グラフ + optimizer制約 | 1.5日 |

### React版が進んでいる機能（4件）

| # | 機能 | React版の実装 |
|---|------|-------------|
| 1 | JS版ソルバー | /api/rotation/optimize-js（OR-Tools不要の軽量版） |
| 2 | 在庫管理拡張 | 13カラム + 入出庫履歴 + 操作ログ |
| 3 | 在庫連動警告 | /api/inventory/warnings |
| 4 | FAMIC管理UI | 自動更新トグル + 利用規約同意フロー |

### テストカバレッジ差

| 項目 | Gradio版 | React版 |
|------|---------|---------|
| テストファイル数 | 32 | 8 |
| テスト関数数 | 414 | 148 |
| フレームワーク | pytest | pytest |

P1移植時に同時移植すべきテスト: 7ファイル（test_adjacency, test_aggregation_unit, test_aggregation_service_unit, test_crop_family, test_optimizer_adjacency, test_polygon_repository_unit, test_spatial_unit）

## P1移植仕様（足軽向け作業指示レベル）

### Phase 1: crop_family（0.5日）

**目的**: crop_master テーブルに family カラムを追加し、作物科マッピングを実現する。

**対象ファイル**:
- `scripts/migrate_crop_family.sql` → 適用（ALTERでfamilyカラム追加 + 9科UPDATEシード）
- `api/db_access.py` → `CropMasterRepository.get_family_map()` メソッド追加（{作物名: 科名} 辞書を返す）
- `api/main.py` → `/api/crop-families` エンドポイント確認（既存の場合は動作確認のみ）

**SQL**:
```sql
ALTER TABLE crop_master ADD COLUMN family TEXT DEFAULT NULL;
UPDATE crop_master SET family = 'イネ科' WHERE name IN ('小麦(春播)', '小麦(秋播)', 'とうもろこし', 'WCS');
UPDATE crop_master SET family = 'マメ科' WHERE name IN ('だいず', 'あずき', 'いんげん');
-- ... 以下9科分
```

**テスト**: test_crop_family.py を移植

**影響範囲**: Phase 3（隣接筆制約）の前提条件。先にこれを完了する必要がある。

### Phase 2: ポリゴン + 集計（2〜3日）

**目的**: 水田ポリゴン・作付けポリゴンのCRUD + 面積クロス集計を実現する。

**対象テーブル**:
- `paddy_polygons`: 水田ポリゴン（geometry, area_ha, is_converted, conversion_start_year, source）
- `crop_polygons`: 作付けポリゴン（field_id, year, crop_name, geometry, area_ha）

**Repository（api/db_access.py に追加）**:
- `PaddyPolygonRepository`: register, delete, update_conversion, import_kml, get_by_field
- `CropPolygonRepository`: register, delete, import_kml, copy_previous_year, get_by_field_year

**参照元（Gradio版）**:
- `field/paddy_crud.py` (338行) → PaddyPolygonRepository の元
- `field/crop_polygon_crud.py` (474行) → CropPolygonRepository の元
- `field/aggregation.py` (150行) → build_cross_tabulation(), format_cross_table_for_display()
- `field/aggregation_service.py` (203行) → get_cross_tabulation_for_user(), get_subsidy_summary(), export_csv()
- `field/spatial.py` → calculate_geodesic_area_ha(), determine_land_category(), split_crop_by_land_category()

**API（api/main.py に追加、8〜10エンドポイント）**:
- `/api/paddy-polygons` — GET(一覧), POST(登録), DELETE(削除), PUT(畑地化更新), POST(KMLインポート)
- `/api/crop-polygons` — GET(一覧), POST(登録), DELETE(削除), POST(KMLインポート), POST(前年コピー)
- `/api/aggregation` — GET(クロス集計), GET(補助金サマリ), GET(CSV出力)

**Frontend（3コンポーネント新規）**:
- PaddyPolygonUI — 水田ポリゴン登録・編集（Leaflet連携）
- CropPolygonUI — 作付けポリゴン登録・年別管理
- AggregationUI — クロス集計表表示 + CSV出力

**テスト**: test_polygon_repository_unit.py, test_aggregation_unit.py, test_aggregation_service_unit.py, test_spatial_unit.py を移植

**注意**: FieldRegister.jsx + FieldMap.jsx にポリゴン描画・編集のUI（Leaflet + leaflet-draw）は既に実装済み。バックエンド連携のみ追加。

### Phase 3: 隣接筆制約（1日）

**目的**: 隣接ほ場で同科の作物を栽培しない制約をoptimizer に追加する（PRO機能）。

**対象ファイル（Gradio版からの移植元）**:
- `field/spatial.py` L176-246:
  - `build_adjacency_graph(fields, buffer_m=1)` — STRtreeで隣接判定、バッファ距離でintersects
  - `get_adjacent_field_pairs(fields)` — 重複排除した隣接ペアリスト
- `app/optimizer.py` L91-110:
  - `check_adjacency_constraint(field_code, crop, year, constraints)` — crop_family_map で同科判定
- `app/constraints.py` L109-112:
  - `Constraints` データクラスに `adjacent_family_enabled`, `adjacency_pairs`, `crop_family_map` 追加

**React版への移植先**:
- `api/db_access.py` → spatial関数追加 or 別モジュール
- `api/main.py` → `/api/constraints` に adjacency パラメータ追加、`/api/rotation/optimize` に制約追加
- `frontend/app/src/` → ConstraintEditor.jsx にPROチェックボックス追加

**設計ポイント**:
- 隣接筆制約はPRO（有料）機能として実装（ソフトゲーティング）
- グラフ彩色問題の農地版: 科(family)で隣接筆を塗り分け + 時間軸 + 面積制約
- パフォーマンス注意: 現行はO(n²)、100枚超で遅くなる。将来STRtree導入でO(n log n)化が必要

**テスト**: test_adjacency.py, test_optimizer_adjacency.py を移植

## エラー処理設計（TODO）

### Gradio版 db.py の改善点（React版への移植対象）

| 改善項目 | Gradio版の実装 | React版の現状 |
|---------|---------------|-------------|
| WALモード | `PRAGMA journal_mode = WAL` | なし |
| タイムアウト | `timeout=30.0` | デフォルト(5秒) |
| 外部キー制約 | `PRAGMA foreign_keys = ON` | スキーマで宣言のみ |
| トランザクション | `transaction()` コンテキストマネージャ | なし |
| 例外分類 | DuplicateKeyError, NotNullViolationError, ForeignKeyViolationError | なし（素のsqlite3.Error） |
| 自動ロールバック | get_db() でエラー時自動rollback | なし |

### 移植方針

1. `api/db_access.py` の DB接続部分に WAL + timeout + FK を追加
2. `transaction()` コンテキストマネージャを導入
3. 例外分類クラスを追加（DuplicateKeyError 等）
4. 既存の各Repository メソッドを段階的にtransaction()対応に移行

## 開発環境

### 起動方法

```bash
cd /home/yasu/rotation-planner
./start-dev.sh
```

`start-dev.sh` の動作:
1. `venv/bin/activate` で仮想環境有効化
2. `api/main.py` をバックグラウンド起動（port 8000）
3. `frontend/app/` で `npm run dev` をバックグラウンド起動（port 5173）
4. Ctrl+C で両方停止

### ポート

| サービス | ポート | URL |
|---------|-------|-----|
| FastAPI (Backend) | 8000 | http://localhost:8000 |
| React (Frontend) | 5173 | http://localhost:5173 |

### 初期ユーザー

| ユーザー名 | パスワード | ロール |
|-----------|----------|-------|
| admin | admin123 | admin |
| ja_staff | staff123 | ja_staff |
| farmer_demo | demo123 | farmer |

### テスト実行

```bash
cd /home/yasu/rotation-planner
source venv/bin/activate
pytest tests/                    # バックエンドテスト
node frontend/test-node.js       # フロントエンドテスト（JS solver）
```

## 注意事項

- **api/main.py が3,630行の巨大ファイル**。全25エンドポイントグループが1ファイルに集約されている。将来分割検討対象
- **マイグレーションSQLが db_schema.sql に未統合**。新規セットアップ時は db_schema.sql + 全マイグレーションSQL の実行が必要
- **Gradio版はレガシー凍結**。今後の開発はReact版のみ。Gradio版コードは参照元としてのみ使用
- **パフォーマンス課題**: 隣接判定がO(n²)でほ場100枚超で破綻。JA管内（千〜万枚）では使えない。STRtree導入が必要
- **DB方針**: SQLite維持。PostGISは商用化フェーズまで不要。段階: ①STRtree → ②SpatiaLite → ③PostGIS
- **アプリの本質**: 輪作計画アプリではなく、農家を雑な事務作業から解放する道具。面積集計・補助金計算・防除記録の自動化が本丸

## ディレクトリ構成（主要ファイル）

```
/home/yasu/rotation-planner/
├── api/
│   ├── main.py              # FastAPI全エンドポイント (3,630行)
│   ├── db_access.py         # Repository層
│   ├── db.py                # DB接続（Gradio版に改善あり）
│   ├── models.py            # データクラス
│   └── db_schema.sql        # メインスキーマ
├── frontend/
│   └── app/
│       └── src/
│           ├── App.jsx       # ルーター定義
│           ├── pages/        # 14ページコンポーネント
│           └── components/   # 共通コンポーネント
├── field/                    # Gradio版GIS機能（移植元）
│   ├── spatial.py            # 空間演算（STRtree, 面積計算, 隣接判定）
│   ├── paddy_crud.py         # 水田ポリゴンCRUD
│   ├── crop_polygon_crud.py  # 作付けポリゴンCRUD
│   ├── aggregation.py        # クロス集計ロジック
│   └── aggregation_service.py # 集計サービス層
├── app/
│   ├── optimizer.py          # OR-Tools最適化 + 隣接制約
│   └── constraints.py        # 制約データクラス
├── scripts/
│   ├── migrate_crop_family.sql      # family カラム追加
│   ├── migrate_crop_schema.sql      # crop_master, user_crops
│   ├── migrate_pesticide_orders.sql # pesticide_orders
│   ├── migrate_pesticide_record.sql # pesticide_registry, usage, records, famic_import_log
│   └── backup_db.py                 # バックアップ（世代管理付き）
├── tests/                    # pytest テスト群
├── docs/
│   └── frontend_migration_gap_analysis.md  # 機能差分レポート
├── start-dev.sh              # 開発サーバー起動
└── venv/                     # Python仮想環境
```
