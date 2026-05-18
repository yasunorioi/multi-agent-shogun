# rotation-planner VPS Gradio→FastAPI+React 全面移行 戦略書 (Wave 2c設計)

| 項目 | 内容 |
|---|---|
| cmd / subtask | cmd_577 / subtask_1224 |
| 作成日 | 2026-05-18T12:04 |
| 作成者 | 軍師 (gunshi) |
| 殿裁定 | 案β「最新版に入れ替え」採択(2026-05-18) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp (debian/webapp) |
| 乖離規模 | **57 commits** (`3c72c7a..origin/main HEAD = 8d005e0`) |
| ntripcaster | 稼働中・絶対保全 (port 2101, pid 3216892/3216893) |
| Wave | 2c=戦略+分解(本書)、2d-2g=実装(別subtask群) |

---

## §1 エグゼクティブサマリ (30行以内・殿レビュー用)

**結論3行:**
1. **案β2「別ディレクトリ並行構築」を推奨。** /var/www/rotation-planner-v2/ にFastAPI+React版を完成→systemd unit切替で**ダウンタイム30秒-2分**+rollback=unit戻し1コマンド。
2. **公式README L365-450 のデプロイ手順 (nginx + uvicorn 127.0.0.1:8000 + React dist 静的配信)** を採用。`scripts/install.sh` は旧Gradio版残置で**罠**(使うな)。
3. **JWT_SECRET 環境変数必須・必ず作成**(`api/deps.py` で起動時 RuntimeError)。**DB は init_db() の `CREATE TABLE IF NOT EXISTS` で新テーブル追加・旧テーブル放置許容**(破壊的migrationは別Waveで判断)。

**選択肢:** β1=in-place / **β2=別dir並行** ★推奨 / β3=別ポート両系統並行
**推奨理由:** 案β2はntripcaster保全(apt不使用・nvm)・低ダウンタイム・rollback容易の3軸で最高得点(加重38/45)。

**殿への質問(必須回答):**
- **Q1':** 案β2採用でよいか? (β1の方が好みならスコープ単純化)
- **Q2':** Node.js は **nvm + Node 20 LTS** で良いか? (apt nodejs=v18.x、apt npm=外部依存、nvmは webapp $HOME 配下で libstdc++ 影響ゼロ)
- **Q3':** React 配信は **nginx 追加** で良いか? (代替=FastAPI StaticFiles でnginx不要・公式READMEから逸脱)
- **Q4':** DB schema migration 方針:**(a) 既存DB保持+init_db()のIF NOT EXISTSのみ** / (b) migrate_*.sql を順次実行 / (c) 別DB作って scratch (推奨=(a)・破壊回避)
- **Q5':** ダウンタイム許容 30秒-2分 でよいか? (案β2想定)
- **Q6':** 旧Gradio版アーカイブ保持期間 **90日後削除** でよいか? (即削除/180日 等の指定があれば)

**展開:** 殿回答後、家老が Wave 2c-2g (subtask 11個) を起票・配布。

---

## §2 origin/main 構造調査結果

### 2.1 リポジトリ概要

| 項目 | 値 | 出典 |
|---|---|---|
| origin/main HEAD | `8d005e0` "docs: add architecture diagram (Mermaid) to README" | 2026-05-18T12:01 clone |
| VPS HEAD | `3c72c7a` (Gradio版・May07稼働中) | Wave 1報告 |
| 乖離 | **57 commits** | `git log --oneline 3c72c7a..HEAD \| wc -l` |
| 主要転換commit | `6f9e646 refactor: Gradio UI完全削除 + FastAPI移行` | git log |
| 直近の意味のあるchange | `34360fa fix: SQL identifier injection防御 / b701f9d docs: README.md改訂 FastAPI+React構成 / f1b681c fix: lifespan起動時にinit_db()` | git log |

### 2.2 FastAPI 構造 (`api/`)

| ファイル | 役割 |
|---|---|
| `api/main.py` (30148B) | アプリエントリ・FastAPI() 生成・lifespan で `init_db()` + `ensure_crop_tables()` + `ensure_inventory_tables()` 起動時実行・CORSは localhost のみ・JWT(HS256)・全 router 登録 |
| `api/deps.py` | JWT 認証依存性・`JWT_SECRET` 環境変数**必須**(未設定で `RuntimeError`)・`get_current_user` / `require_admin` 提供 |
| `api/error_handlers.py` | グローバル例外ハンドラ |
| `api/logging_config.py` | ロガー設定 |
| `api/routers/auth.py` | `/api/auth/login` (JWT発行) + `/api/auth/me` |
| `api/routers/admin.py` | 管理者操作 |
| `api/routers/{fields,crops,plans,pesticides,gis,dashboard}.py` | 機能別 |
| `api/inventory_api.py` | 在庫管理 |
| `api/requirements.txt` | (API個別依存) |

### 2.3 認証実装の差 (重要)

| 項目 | 旧Gradio版 (portal.py) | 新FastAPI版 (api/) |
|---|---|---|
| 認証スキップ | `DEBUG=1` 環境変数で skip (L827-833 Wave 2b調査済) | **なし** (常にJWT必須) |
| 認証方式 | Gradio セッション | JWT (HS256, JWT_SECRET 必須) |
| 初期ユーザー | DB users テーブル(認証ロジック共通) | 同左(`rotation_planner.common.authenticate`) |
| ja_user/ja123 | DB users 行があれば継続可 | 同左 (パスワードハッシュ実装が共通なので互換) |
| 管理ロール | `admin` / `farmer` | `admin` / `farmer` / `ja_staff` (1つ追加) |

→ **`ja_user/ja123` は DB users テーブルに行が存在し、共通の `authenticate()` が hash 一致を返す限り FastAPI 側でも継続ログイン可能。** Wave 2e-2 で要事前確認 (users テーブル中身を `SELECT username, role FROM users;` で目視)。

### 2.4 React 構造 (`frontend/app/`)

| 項目 | 値 |
|---|---|
| パッケージ | `app` (private) |
| 主要依存 | React 19.2 / Vite 7.2 / leaflet 1.9 / react-leaflet 5 / leaflet-draw 1 / @tanstack/react-table 8.21 / axios 1.13 / zustand 5 / react-router-dom 7.13 |
| ビルド | `npm install && npm run build` → `frontend/app/dist/` (vite build) |
| ビルド時Node要件 | **Node 18+** (Vite 7はNode 18.18+を推奨、安全側で **Node 20 LTS** を推奨) |
| dev サーバー | `npm run dev` (port 5173・本番では使わない) |

### 2.5 DB schema 差分 (VPS `3c72c7a` vs origin HEAD)

`db_schema.sql` Version 1.0 → 1.2 (Updated: 2026-02-02)。主要変更:

| 変更種別 | 内容 |
|---|---|
| 新規テーブル | `pesticide_masters`(再定義), `user_constraints`, `order_templates`, `inventory`, `inventory_transactions`, `inventory_csv_operations`, `paddy_polygons`, `crop_polygons`, `crop_master`, `user_crops`, `pesticide_registry`, `pesticide_usage`, `pesticide_records`, `famic_import_log`, `pesticide_orders` |
| 破壊的変更 | `crop_constraints` → `user_constraints` (構造完全刷新、面積上限の cap_ha/min_ha → constraints_json TEXT に集約) |
| 構造変更 | `pesticide_masters` フィールド再構成 (crop NOT NULL → NULLable, dilution_rate型変更等) |
| カラム追加 | `fields.land_category TEXT DEFAULT NULL` |
| migration script | `scripts/migrate_crop_family.sql` / `migrate_crop_polygons.sql` / `migrate_crop_schema.sql` / `migrate_field_polygons.sql` / `migrate_order_templates.sql` / `migrate_paddy_polygons.sql` / `migrate_pesticide_orders.sql` / `migrate_pesticide_record.sql` / `migrate_pesticide_v2.sql` (9本) |

**重要:** 全 CREATE TABLE が `IF NOT EXISTS` なので、**既存DBをそのまま使うと旧スキーマ残置+新規テーブルだけ追加** の状態になる。アプリ起動は可能だが、`crop_constraints`(旧) と `user_constraints`(新) が併存する。新コードは `user_constraints` を見る → 旧データは未参照になるが**消えはしない**。これは「Q4'=(a) 既存DB保持」推奨の根拠。

### 2.6 デプロイ手順の正解 (README L365-450)

**手動インストール手順** が README に正規記載 (移行先の根拠):

```bash
# 1. clone (別dir推奨: /var/www/rotation-planner-v2/app)
git clone https://github.com/yasunorioi/rotation-planner.git
cd app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r api/requirements.txt

# 2. フロントエンドビルド
cd frontend/app && npm install && npm run build && cd ../..

# 3. DB初期化(既存DBがあればskipし lifespan内の init_db() に任せる)
# python3 -c "from rotation_planner.common.db import init_db; init_db()"

# 4. JWT_SECRET 生成
# export JWT_SECRET="$(openssl rand -hex 32)"

# 5. API起動
uvicorn api.main:app --host 127.0.0.1 --port 8000

# 6. nginx 設定 (README L421-450) — React dist を静的配信、/api/ を uvicorn にプロキシ
```

### 2.7 ⚠️ install.sh の罠

`scripts/install.sh` (L56-73) は **Gradio版残置**:
```
ExecStart=/var/www/rotation-planner/app/venv/bin/python portal.py   # ← Gradio
Environment=GRADIO_SERVER_NAME=127.0.0.1
Environment=GRADIO_SERVER_PORT=7863
```
→ **使うな。README手動手順で構築せよ**。後続Waveで install.sh の origin修正PR提案を別cmdで起票検討(F006殿明示許可必要)。

---

## §3 移行手順 3案 比較評価 (L5 weighted scoring)

### 3.1 評価軸と重み

| 軸 | 重み | 説明 |
|---|---|---|
| north_star整合 | 3 | 殿が輪作計画機能の最新版を実用できる |
| ntripcaster保全 | 3 | port 2101 / libstdc++ / screen セッションに影響なし |
| ダウンタイム最小 | 2 | 殿が ja_user で使用中の連続性 |
| rollback容易性 | 2 | 失敗時の戻し手数 |
| 運用コスト(構築+保守) | 2 | 構築時間+二重運用負担 |
| DB schema migration安全性 | 2 | データ保全・破壊操作の有無 |

### 3.2 スコアリングマトリクス (0-3点)

| 案 | NS | NTRIP | DT | RB | OP | DB | **加重合計** |
|---|---|---|---|---|---|---|---|
| β1 in-place (同ディレクトリ更新) | 3 | 3 | 1 | 1 | 3 | 2 | 32 |
| **β2 別dir並行構築 ★推奨** | **3** | **3** | **3** | **3** | **2** | **2** | **38** |
| β3 別ポート両系統並行 | 2 | 3 | 3 | 3 | 1 | 1 | 31 |

### 3.3 各案の詳細

#### 案β1: in-place (同ディレクトリ更新)
**手順:** `systemctl stop` → `cp -r app app.bak` → `git pull` → `pip install` → `npm install && build` → `JWT_SECRET設定` → `systemd unit編集(uvicorn化)` → `start`
**ダウンタイム:** 8-12分 (npm install/build が支配項)
**rollback:** `systemctl stop` → `rm -rf app && mv app.bak app` → `systemctl start` (unit edit戻しも必要)
**長所:** ディスク節約・パス変更なし
**短所:** ダウンタイム長・unit編集ミスのリスク・JWT_SECRET未設定で起動失敗時の連鎖障害・systemd unit `ExecStart` を `portal.py` から `uvicorn` へ書き換えるリスク

#### 案β2: 別ディレクトリ並行構築 ★推奨
**手順:** `/var/www/rotation-planner-v2/app/` に clone → venv+pip→ npm build → JWT_SECRET 設定 → 一時port (例:8001) でテスト → `rotation-planner-v2.service` 作成・enable → 動作確認 → 既存 `rotation-planner.service` stop → -v2 を 127.0.0.1:8000 で start → nginx で port 80 → /api/ プロキシ → React dist 静的配信
**ダウンタイム:** 30秒-2分 (systemd unit切替+起動確認)
**rollback:** `systemctl stop rotation-planner-v2 && systemctl start rotation-planner` (旧unit/dir完全残存・1コマンド)
**長所:** 旧版完全残置で最終rollback担保・テスト期間取れる・ntripcasterに完全無影響・cutover瞬時
**短所:** ディスク2倍 (現実15G空きあるので問題なし)・DB の扱い (推奨=旧app/data/*.db をコピー or symlink で v2 が同じDBを参照)

#### 案β3: 別ポート両系統並行
**手順:** 案β2 と同じ構築後、**両 systemd unit を同時稼働**。Gradio=7863、FastAPI=8000 (or 7864)。
**ダウンタイム:** ほぼゼロ
**rollback:** 不要(両系統共存)
**長所:** 安全性最高
**短所:** 二系統メモリ・DB一貫性リスク(同DBに両アプリが書く)・最終的に Gradio を止める別Waveが必須・nginx routing 複雑化・運用負担2倍

### 3.4 推奨案 (β2) と rollback 手順

**推奨理由:**
1. **ntripcaster保全(weight 3)** で全案最高点。apt不要(nvm採用) / shared lib無影響 / 既存プロセス未触
2. **rollback容易性(weight 2)** で β2/β3 共に最高。だが β3 の運用コスト負担を回避するため β2 を選好
3. **ダウンタイム最小(weight 2)** で β2/β3 共に最高 (30秒vs ほぼゼロ・実用上差なし)
4. 案β2 は **「動くものを作ってから切替」** で殿のV4自動運転境界線「戻せるか否か」を最も明確に満たす

**rollback手順 (案β2想定):**
```bash
# 切替直後に異常検知した場合 (5分以内なら):
sudo systemctl stop rotation-planner-v2
sudo systemctl start rotation-planner       # 旧Gradio版復帰
# ntripcaster無影響再確認:
sudo ss -tlnp | grep 2101
ps -ef | grep -E 'ntrip|caster' | grep -v grep
```
- 旧 `/var/www/rotation-planner/app/` は **完全残置**(削除しない)
- 旧 `rotation-planner.service` は **disable のみで残置**(unit ファイル削除しない)
- DB は **症状による**: 起動確認のみなら旧DBに影響なし。書き込みテストした場合は要bak復元 (Wave 2e-2 で事前 cp バックアップ)

---

## §4 リスク評価 (L4 分析)

### 4.1 ntripcaster影響 リスクと緩和

| リスク | 発生確率 | 影響 | 緩和策 |
|---|---|---|---|
| `apt install nodejs npm` で libstdc++ ダウングレード | 中 | 高(ntripcaster cores) | **nvm採用 (apt不使用)** ・apt系コマンドはWave 2c-2g全期間禁止 |
| systemd ユニット操作で他サービス巻き込み | 低 | 中 | `systemctl restart` の対象は `rotation-planner.service` と `rotation-planner-v2.service` に限定 |
| nginx 新規インストールで shared lib影響 | 低 | 低 | nginx は既にinstall済か未確認 → 要 Wave 2c-2 で確認・未install時のみ apt install nginx を **殿確認後**実行 |
| screen セッション "ntrip" への誤接続 | 極低 | 高 | `screen -ls` 確認のみ・`screen -r ntrip` 禁止 |
| pid 3216892/3216893 への誤kill | 極低 | 高 | `pkill`系全面禁止・名前ベースのkill禁止 |

### 4.2 Node.js 導入方法 3案

| 案 | libstdc++影響 | LTS取得 | webapp権限内 | 推奨度 |
|---|:---:|:---:|:---:|---|
| apt install nodejs npm | **高(リスク)** | × Debian 12=v18.x | × 要 sudo | ✗ |
| nvm (Node Version Manager) | **無** | ○ 任意LTS | ○ $HOME 配下 | ★推奨 |
| nodesource repo (deb.nodesource.com) | 中 | ○ LTS | × 要 sudo | △ |

**推奨: nvm + Node 20 LTS**。`sudo -u webapp bash` でwebappとして `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash` → `source ~/.nvm/nvm.sh && nvm install --lts` → `~/.bashrc` に永続化。systemd unit に `Environment="PATH=/home/webapp/.nvm/versions/node/v20.x.x/bin:..."` 追加不要(`npm run build` はWave 2d-3 で対話的に実行・本番稼働はvenvの uvicorn のみで Node不要)。

### 4.3 React build配信方法 2案

| 案 | nginx要否 | TLS余地 | 設定複雑度 | 推奨 |
|---|:---:|:---:|:---:|---|
| nginx + React dist 静的配信 + /api/ プロキシ | 必要 | ○ certbot 追加可 | 中 | ★公式README推奨 |
| FastAPI StaticFiles でReact dist配信 | 不要 | △ TLS は別系統 | 低 | 簡易代替 |

**推奨: nginx 採用 (公式README)**。但し apt install nginx が未済の場合 ntripcaster影響評価を **Wave 2c-2 でbaseline取得後** に実施 (libnginx-* の依存解決でlibstdc++が動く可能性は低いが要確認)。

### 4.4 DB schema migration 不可逆性

| 操作 | 不可逆? | 推奨 |
|---|:---:|---|
| `init_db()` の `CREATE TABLE IF NOT EXISTS` 自動実行 | 可逆(新テーブル追加のみ) | ★既存DBそのままコピーで案β2 v2 dirに配置 |
| migrate_*.sql 9本 順次実行 | 中(構造変更含む) | スキップ可。新コードは `user_constraints` を直接見る・旧 `crop_constraints` は放置で問題なし |
| 旧テーブル DROP | **不可逆** | ✗ 当面禁止 (180日後の別Waveで判断) |
| 既存データ移行 (crop_constraints→user_constraints) | 中 | ★殿の旧データ依存度次第。**未確認**→Wave 2c-2 で `SELECT COUNT(*) FROM crop_constraints;` を確認・行0なら未使用で安全 |

**推奨: Q4'=(a) 既存DB保持+`init_db()`の `IF NOT EXISTS` のみ自動適用**。データ移行は別Waveで殿に判断委ねる。

### 4.5 認証連続性 (ja_user/ja123)

- `rotation_planner.common.authenticate(username, password)` は両版で同じ hash 関数(`hash_password()`)を使用
- VPS既存DB `users` テーブルに `ja_user` 行があり、パスワードハッシュが同じ実装なら **FastAPI側でもログイン継続可能**
- ロール拡張 `ja_staff` 追加だが既存 `farmer` / `admin` は維持
- **Wave 2c-2 でVPS既存DB users テーブルの ja_user 行存在+role+display_name を read-only で確認**

### 4.6 環境変数・.env 継承

| 項目 | 現Gradio版 (推測) | 新FastAPI版 |
|---|---|---|
| `GRADIO_SERVER_NAME` / `GRADIO_SERVER_PORT` | systemd unit Environment | **不要(削除)** |
| `JWT_SECRET` | 不要 | **新規必須**(openssl rand -hex 32 で生成・systemd EnvironmentFile に保存・600 perm) |
| `DEBUG` | `=1` で認証skip(portal.py L827-833) | **無視される** (新版は常にJWT必須) |
| 他 .env? | Wave 1報告で発見されず | 要 Wave 2c-2 で `/var/www/rotation-planner/app/.env` 存在確認 |

### 4.7 V4自動運転境界線判定 (殿哲学準拠)

| サブフェーズ | 戻せるか? | 自動運転可否 |
|---|:---:|:---:|
| Wave 2c-2 (DB/users/ports read-only調査) | ○ | ✅ 自動GO |
| Wave 2d (別dir clone+pip+npm build) | ○ (削除可) | ✅ 自動GO |
| Wave 2e-1 (JWT_SECRET生成) | ○ (再生成可) | ✅ 自動GO |
| Wave 2e-2 (DB cp バックアップ + コピー配置) | ○ (削除可) | ✅ 自動GO |
| Wave 2e-3 (rotation-planner-v2.service 作成・一時port 8001で起動テスト) | ○ (unit削除可) | ✅ 自動GO |
| Wave 2f-1, 2f-2 (動作確認) | ○ | ✅ 自動GO |
| **Wave 2f-3 (本切替 systemctl stop 旧 + start v2 + port 8000化)** | ○ (1コマンド戻し) | ✅ 自動GO・**お針子監査必須** |
| 旧rotation-planner.service の disable (削除はしない) | ○ (enable可能) | ✅ 自動GO |
| **旧 /var/www/rotation-planner/app/ の削除** | **✗ 不可逆** | **🛑 殿確認必須**(90日後の別cmdで起票) |
| nginx install (未installの場合) | ○ (apt remove可) | ⚠️ 殿確認推奨 (apt系のため) |

---

## §5 タスク分解 (Wave 2c-2g・decompose出力)

### 5.1 全体ガント (実線=依存・点線=並列)

```
Wave 2c (確定+調査)
  └─ 2c-1 殿質問回答取得 ──┐
     2c-2 既存DB/users/portsベースライン ─┐
                                          │
Wave 2d (構築)                            │
  ├─ 2d-1 clone+venv+pip install ─────────┤
  ├─ 2d-2 nvm + Node 20 LTS ──────────────┤ (並列可)
  └─ 2d-3 npm install + build  ←──────────┘ (2d-1+2d-2待ち)
                                          │
Wave 2e (設定)                            │
  ├─ 2e-1 JWT_SECRET + EnvironmentFile ───┘
  ├─ 2e-2 DB cp + 配置 + IF NOT EXISTS 適用 (2e-1並列可)
  └─ 2e-3 rotation-planner-v2.service 作成・port 8001でtest起動
                                          │
Wave 2f (動作確認+本切替)                   │
  ├─ 2f-1 API起動確認 (curl /api/auth/login ja_user)
  ├─ 2f-2 React build配信確認 (nginx or StaticFiles)
  ├─ 2f-3 本切替 (旧stop → v2 port 8000化 → start)  ★お針子監査
  └─ 2f-4 ntripcaster無影響再確認 + 全機能スモークテスト
                                          │
Wave 2g (整理・任意)                       │
  ├─ 2g-1 nginx設定 (殿Q3'=採用時のみ)
  ├─ 2g-2 旧rotation-planner.service disable (削除しない)
  └─ 2g-3 完了報告書 docs/shogun/rotation_planner_v2_migration_post_*.md
```

### 5.2 各 subtask 詳細

| # | id_hint | description | bloom | worker推奨 | 半日以内 | blocked_by | needs_audit | rollback |
|---|---------|-------------|-------|-----------|---------|-----------|-------------|----------|
| 2c-1 | subtask_1225 | 殿質問 Q1'-Q6' 回答取得 | L1(殿裁定) | 殿 | ○ | - | false | - |
| 2c-2 | subtask_1226 | VPS read-only ベースライン (既存DB schema version, users行, ntripcasterps, listen baseline, .env存在, nginx install状況) | L2 | 部屋子1 (Opus) | ○ | 2c-1 | false | read-only |
| 2d-1 | subtask_1227 | `/var/www/rotation-planner-v2/app/` に clone + venv + pip install (requirements.txt + api/requirements.txt) | L2 | 部屋子1 | ○ | 2c-2 | false | `rm -rf /var/www/rotation-planner-v2/` |
| 2d-2 | subtask_1228 | webappユーザーに nvm + Node 20 LTS 導入 (apt不使用) | L2 | 部屋子1 | ○ | 2c-2 (並列で2d-1とも可) | false | `rm -rf /home/webapp/.nvm /home/webapp/.bashrc編集差戻し` |
| 2d-3 | subtask_1229 | `frontend/app/` で `npm install && npm run build` → `dist/` 生成 | L3 | 部屋子1 | ○ | 2d-1, 2d-2 | false | `rm -rf frontend/app/dist frontend/app/node_modules` |
| 2e-1 | subtask_1230 | JWT_SECRET 生成 (`openssl rand -hex 32`) + `/etc/rotation-planner-v2.env` (600 perm) 作成 | L1 | 部屋子1 | ○ | 2c-2 | false | `rm -f /etc/rotation-planner-v2.env` |
| 2e-2 | subtask_1231 | 旧 `app/data/*.db` を `app-v2/data/` へ cp (バックアップは `data.bak.20260518/`) + lifespan による `init_db()` の `IF NOT EXISTS` 適用確認 | L4(慎重) | 足軽1 (Sonnet) | ○ | 2d-1 | **true** | `rm -rf app-v2/data && cp -r data.bak.20260518 app-v2/data` |
| 2e-3 | subtask_1232 | `rotation-planner-v2.service` 作成・**一時port 8001** で `systemctl start` テスト・`curl 127.0.0.1:8001/api/auth/login` で 401応答確認 (期待値: bodyなし→401) | L3 | 足軽1 | ○ | 2e-1, 2e-2, 2d-3 | false | `systemctl stop rotation-planner-v2 && rm /etc/systemd/system/rotation-planner-v2.service` |
| 2f-1 | subtask_1233 | ja_user/ja123 で `curl POST /api/auth/login` → JWT取得 → `/api/auth/me` で profile取得 | L2 | 部屋子1 | ○ | 2e-3 | false | - (read-only) |
| 2f-2 | subtask_1234 | (Q3'=nginxの場合) nginx設定+`nginx -t`+restart, dist静的配信+`/api/`プロキシ確認 / (Q3'=StaticFiles) FastAPIのStaticFiles実装 | L3-L4 | 部屋子1 + 足軽1 | ○ | 2f-1 | false | nginx設定削除/StaticFiles実装revert |
| 2f-3 | subtask_1235 | **本切替**: 旧 `systemctl stop rotation-planner` → v2 unit を port 8000化 → `systemctl restart rotation-planner-v2` → ntripcaster ps/2101確認 | L4 | 足軽1 | ○ | 2f-2 | **true(お針子)** | `systemctl stop rotation-planner-v2 && systemctl start rotation-planner` (1コマンド) |
| 2f-4 | subtask_1236 | 全機能スモークテスト (ja_userでログイン→ほ場一覧→輪作計画生成1件→ログアウト)・ntripcaster無影響再確認・listen baselineの差分確認 | L3 | 部屋子1 + お針子監査 | ○ | 2f-3 | お針子監査タスク自体 | - |
| 2g-1 | subtask_1237 | 旧 `rotation-planner.service` disable (削除しない・enable即復帰可能性維持) | L1 | 部屋子1 | ○ | 2f-4 | false | `systemctl enable rotation-planner` |
| 2g-2 | subtask_1238 | 旧 `/var/www/rotation-planner/app/` を `/var/www/rotation-planner/app.bak.20260518/` にrename(削除しない・90日後別cmdで判断) | L1 | 部屋子1 | ○ | 2f-4 | false | `mv app.bak.20260518 app` |
| 2g-3 | subtask_1239 | 完了報告書 `docs/shogun/rotation_planner_v2_migration_post_20260518.md` (Wave 2c-2g 実施結果・所要時間・ntripcaster baseline diff・残課題) | L3 | 部屋子1 | ○ | 2g-1, 2g-2 | false | - |

### 5.3 RACE-001 衝突確認

| 同時実行可能性 | 衝突ファイル |
|---|---|
| 2d-1 + 2d-2 | なし (clone は `/var/www/rotation-planner-v2/`、nvm は `/home/webapp/.nvm/`) |
| 2e-1 + 2e-2 | なし (env file は `/etc/`、DBコピーは `/var/www/.../v2/app/data/`) |
| 他は順次依存 | RACE-001 なし |

### 5.4 worktree 判定

- VPS実機操作中心。git worktree は **不要** (VPS上では git checkout に依存しない)。
- 軍師ローカル調査用clone (`/tmp/rotation-planner-probe-v2`) は本書執筆で消費済、Wave 2dでは使用しない (VPS上で直接clone)。

### 5.5 approval_status

- `pending_roju_review` — 老中レビュー → 殿に質問送付 → 殿回答後に各 subtask 起票

---

## §6 殿への質問 (再掲・回答テンプレート付き)

```
Q1' 移行案: [β1 in-place] / [β2 別dir並行 ★軍師推奨] / [β3 別ポート両系統]
   → 殿回答: _____

Q2' Node.js 導入: [nvm + Node 20 LTS ★軍師推奨] / [nodesource LTS] / [apt nodejs(v18)] / [導入しない(StaticFiles採用)]
   → 殿回答: _____

Q3' React 配信: [nginx + dist静的配信 ★公式README推奨] / [FastAPI StaticFiles で簡素化]
   → 殿回答: _____

Q4' DB migration: [(a) 既存DB保持+IF NOT EXISTS追加のみ ★軍師推奨] / [(b) migrate_*.sql 9本順次実行] / [(c) 別DBで scratch]
   → 殿回答: _____

Q5' ダウンタイム許容: [30秒-2分(β2想定) ★] / [10分(β1想定)] / [ほぼゼロ(β3想定)]
   → 殿回答: _____

Q6' 旧Gradio版アーカイブ保持: [90日 ★軍師推奨] / [180日] / [即削除] / [永久]
   → 殿回答: _____
```

軍師追加質問 (任意):
- **Q7' (security):** Wave 2bで温存された Deploy Key (write access ON) は Wave 2g 完了後にread-only格下げ or 削除するか? (継続write必要なら維持)
- **Q8' (V4):** 旧 `app/data/*.db` の **削除** は不可逆。V4自動運転境界線「殿確認必須」に該当 → 90日経過時に殿確認cmdを起票する設計でよいか?

---

## 付録A. simplicity check (殿命・3問)

| # | 問い | 回答 |
|---|------|------|
| 1 | この計画は、もっと少ないステップで達成できないか? | **検討済**。Wave 2g は任意 (nginx は Q3'=採用時のみ、disable+rename は90日後でも可)。最短は Wave 2c-2f の 12 subtasks。Wave 2g 3件は後発に切離せる。**3件 prune** |
| 2 | 足軽に渡すタスクの粒度は適切か? 過剰分割していないか? | 全 subtask 半日以内。最大が 2f-2 (nginx設定 or StaticFiles実装) で 2-3時間想定。**過剰分割なし**。逆に統合候補= 2e-2 (DBコピー)+ 2e-3 (unit作成・port 8001起動) を1本化すると足軽1の文脈切替が減るが、お針子監査単位を保つため分離維持。 |
| 3 | 本当に必要なタスクだけか? nice-to-have が紛れていないか? | 2g-3 (完了報告書) は nice-to-have 寄りだが、cmd_577 close の正式記録として残す価値あり。**3件prune後の総数: 12 subtask (Wave 2c-2f)** + 2g 任意3件 = 15件中 12件必須。 |

**結論: 3問パス**(検問結果=2g 3件を「任意・別cmd可」にdowngrade、必須 12 subtasks に絞る)

---

## 付録B. unknown_unknowns (殿命・10項目)

1. **JWT_SECRET管理場所**: systemd EnvironmentFile (`/etc/rotation-planner-v2.env`, 600 perm, webapp読取権限) を想定。Vault系は VPS導入なしの前提。
2. **既存VPSデータベースのschema version**: Wave 1 で確認していない。crop_constraints の行数 / user_constraints の存在を Wave 2c-2 で確認すべき。
3. **users テーブルの ja_user 行の存在**: パスワードハッシュ実装が新旧 hash_password() 共通の前提。Wave 2c-2 で `SELECT username, role, length(password_hash) FROM users WHERE username='ja_user';` で確認 (実hashは漏洩防止のため length のみ取得)。
4. **nvm/.bashrc の永続性**: webappユーザーの ~/.bashrc 末尾追記 (`source ~/.nvm/nvm.sh`)。systemd 起動の uvicorn は venv の python なので Node不要(npm はビルド時のみ)。
5. **React build時メモリ消費**: Node build 1-2GB ピーク。VPS空きRAM未確認 (Wave 1 で `free -h` 出力なし) → Wave 2c-2 で確認、不足ならローカル build + rsync の代替案(冒険的案)。
6. **systemd unit WorkingDirectory変更時のENV継承**: rotation-planner-v2.service は `EnvironmentFile=/etc/rotation-planner-v2.env` で明示指定すれば旧 unit と独立。
7. **data/ ディレクトリの引継ぎ**: 旧 `app/data/*.db` を新 `app-v2/data/` に cp で複製(共有しない・データ分岐リスクは案β2の宿命)。代替=symlink で同DB共有(rollback時に新版書込みの影響残るリスク)。**cp推奨・symlink却下**。
8. **settings.json 等の未コミット設定**: Wave 1 で `git status` に未追跡ファイル存在の言及あり (`data/settings.json` を `git stash` で退避とあった)。Wave 2c-2 で `app/` 内の未追跡ファイル一覧取得 → 新 app-v2 に手動コピー。
9. **nginx 既設状況**: Wave 1 ベースラインで nginx 確認なし(おそらく未install)。`apt install nginx` 必要時は **殿確認**(V4境界線=apt系)。代替=FastAPI StaticFiles (Q3'=StaticFiles)。
10. **CORS allowed_origins**: 新版は `["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]` のみ。同一オリジン化(nginx で 80→/api/→8000 / 80→/→dist)で CORS 不要だが、別ドメイン化やSSL終端を将来追加するなら CORS環境変数化が必要。今回スコープ外。

---

## 付録C. north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    rotation-planner = 「農家を雑な事務作業から解放する道具」(殿memory)。
    Gradio版は機能限定的・JS版輪作ソルバー等の最新機能(c6f60a7)が反映されない。
    FastAPI+React版への移行は殿の輪作計画機能の最新化と運用性向上に直結。
    案β2は ntripcaster 保全(別の殿価値)を確保しつつ最新版を提供できる唯一の妥協点。
  risks_to_north_star:
    - "切替失敗時の輪作計画機能不全 → 案β2のrollback容易性で緩和"
    - "ja_user体験の連続性破綻 (DEBUG=1認証スキップが消失) → Wave 2c-2でja_user行存在確認 + JWT正規ログイン誘導"
    - "ntripcaster影響(別プロジェクト)が出た場合の信頼失墜 → apt不使用(nvm採用) + 各subtask末尾でntripcaster確認"
    - "DB schema差での輪作計画plan_details データ移行漏れ → 既存DB保持(Q4'=a)で旧データ未参照だが消失なし"
```

---

## 付録D. 軍師見落としの可能性 (キャラ設定: 慎重さ△の自己補完)

1. **VPS既存DBファイルパスを確認していない**: `app/data/` 配下のDB名(rotation_planner.db か別名か) を Wave 2c-2 で `find /var/www/rotation-planner/app/data -name '*.db' -o -name '*.sqlite*'` で確定すべき。
2. **frontend/app/dist の gitignore**: 通常 `dist/` は .gitignore に入る。Wave 2d-3 で `npm run build` 後 dist 生成を必ず確認(無いと配信できない)。
3. **uvicorn の port 8000 競合**: agriha-linebot が 127.0.0.1:8000 を占有していないか確認 (Wave 1: linebot=8443なので衝突無さそうだが要再確認)。
4. **JWT_SECRET 紛失リスク**: バックアップ場所を殿に提示せず(本書付録Bで管理場所は明記したが、復旧手順は別途必要)。

---

## 付録E. v4 自動運転・モックアップ修正主義の織込

- 案β2 は **「動くv2 を作ってから切替」=モックを叩ける構造**。殿は Wave 2e-3 完了時点で `curl 127.0.0.1:8001/api/auth/login` を叩ける・実機 UI も別portで触れる(殿の手動 SSH ポートフォワード経由)。
- 修正点が出た場合、家老が追加 subtask を起票 → 部屋子1 が v2 dir 内で修正 → 殿が再度叩く。**Wave 2f-3 (本切替) までは「叩ける版」と「稼働版」が同居**。
- F006(GitHub) は **発動しない**(本Wave全期間で git push なし。VPSから origin/main を pull するのみ)
- HW OTA 該当なし

---

(本書 EOF)
