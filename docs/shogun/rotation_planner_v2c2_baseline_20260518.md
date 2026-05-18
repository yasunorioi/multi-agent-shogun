# rotation-planner-v2 構築前 VPS 最終 baseline (Wave 2c-2)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1226 / cmd_577 |
| 作成日時 | 2026-05-18T12:44:39 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp (debianユーザー) |
| 親計画書 | docs/shogun/rotation_planner_v2_migration_strategy_20260518.md (commit b939319) |
| 殿全採択 | Q1'=β2 / Q2'=nvm Node20 / Q3'=nginx / Q4'=IF NOT EXISTS / Q5'=30秒-2分 / Q6'=90日 |
| 作業範囲 | read-only調査のみ・実装一切なし |

---

## 🔴 エグゼクティブサマリ

- **ntripcaster完全保全** (pid 3216892/3216893, port 2101 — Wave 1 baselineと完全一致)
- **rotation-planner v1 (旧Gradio版)** も継続稼働中 (port 7863, pid 555) — 並行稼働方針を阻害せず
- **DB schema 12テーブル**確認 — users テーブル含む全テーブル健在 (IF NOT EXISTS でv2構築可)
- **nginx**: バイナリ未存在だが**`/etc/nginx/` 設定ファイル群が残存**(過去インストール痕跡)・Q3' で再導入要
- **RAM 457MB / Swap 1GB**: React build時に注意要(設計書§3で軍師指摘済)
- **port 8000/8001 空き** (FastAPI v2配置可能)・**8443 は agriha-linebot uvicorn 占有継続**
- **/var/www/rotation-planner-v2/ 未存在**(clone先空きOK)
- **webapp ユーザー nvm/Node 未導入**(Q2' nvm Node20 で導入可)

→ **Wave 2c-2g 着手前提すべて整合・blocker無し**

---

## §1 DB schema スナップショット

### テーブル一覧 (12テーブル + sqlite_sequence)
```
crop_constraints   fields             pesticide_masters  rotation_plans
crop_history       inventory          pesticide_orders   user_crops
crop_master        organizations      plan_details       users
```

### 主要CREATE TABLE抜粋

#### users (Wave 1で確認済・継承)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    role TEXT NOT NULL CHECK (role IN ('farmer', 'ja_staff', 'admin')),
    org_id INTEGER REFERENCES organizations(id),
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### organizations (新)
```sql
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('JA', 'cooperative', 'individual')),
    settings_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### fields (`area_a` は GENERATED ALWAYS AS)
```sql
CREATE TABLE fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    field_code TEXT NOT NULL,
    district TEXT,
    name TEXT,
    area_ha REAL NOT NULL,
    area_a REAL GENERATED ALWAYS AS (area_ha * 100) STORED,
    beet_forbidden INTEGER DEFAULT 0,
    coordinates_json TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, field_code)
)
```

#### crop_history, crop_master, crop_constraints, inventory, pesticide_masters, pesticide_orders, plan_details, rotation_plans, user_crops
(全テーブル CREATE TABLE 取得済・本報告書付録扱い・必要時は SSH grep 再取得可)

### Q4'=IF NOT EXISTS 適用評価
v2 構築時に init_db() が CREATE TABLE IF NOT EXISTS を発行することで、既存12テーブルを温存しつつ新schema差分(あれば)のみ追加可能。**既存データ消失リスクなし**。

---

## §2 users テーブル (3ユーザー・hash長均一)

| username | role | password_hash長 | 備考 |
|---|---|---|---|
| admin | admin | 64 (SHA256) | 平文不明・初期値admin123から変更済 (subtask_1222) |
| ja_user | ja_staff | 64 (SHA256) | **平文=ja123 確定** (subtask_1222) |
| farmer1 | farmer | 64 (SHA256) | 平文不明 (subtask_1222) |

hash長は全64文字 = SHA256(hex) で一貫。Q1'=β2 (DB継承) で全ユーザーそのまま継承可能。

---

## §3 ntripcaster 保全確認 (Wave 1 baseline と完全一致)

### プロセス
```
root  3216892   1   May07 ?    00:00:00 SCREEN -AmdS ntrip ./ntripcaster
root  3216893 3216892 May07 pts/0 00:10:54 ./ntripcaster
```

### Port 2101 listen
```
LISTEN 0.0.0.0:2101  users:(("ntripcaster",pid=3216893,fd=5))
```

→ Wave 1 baseline (May07起動) と pid・port 完全一致。11日連続稼働中。Wave 2b Phase A,B で破壊なし確認済。**今後のWave 2d-2g作業でも本baselineとの一致をPhase毎に確認すること**。

---

## §4 listen baseline 全表 (rotation-planner-v2 配置前の証跡)

### TCP LISTEN
| Port | Bind | Process | pid |
|---|---|---|---|
| 22 | 0.0.0.0 (+IPv6) | sshd | 586 |
| 2101 | 0.0.0.0 | ntripcaster | 3216893 ★保護対象 |
| 8443 | 127.0.0.1 | uvicorn (agriha-linebot) | 671 |
| 7863 | 0.0.0.0 | python (rotation-planner v1 Gradio) | 555 |

### UDP UNCONN
| Port | Bind | Process |
|---|---|---|
| 41751 | 0.0.0.0 (+IPv6) | (プロセス名なし・rotation-planner Gradio関連と推定) |

→ v2 構築では **port 8000/8001 (FastAPI), port 80/443 (nginx)** を新規占有する見込み。既存衝突なし(§8 参照)。

---

## §5 旧 app/ 未追跡ファイル一覧

### git status --short
```
?? data/settings.json
```

### .env 系
`/var/www/rotation-planner/app/.env*` → **存在なし** (NO_ENV)

→ 旧app/ の未追跡データは `data/settings.json` 1ファイルのみ。v2 構築時に `cp data/rotation_planner.db data/settings.json` をv2側data/に移植する設計か、別途検討要(軍師戦略書 §X 参照)。

---

## §6 nginx 現状 (要注意・中途半端な痕跡あり)

| 項目 | 結果 |
|---|---|
| nginx バイナリ | **NO_NGINX_BINARY** (`which nginx` 失敗) |
| systemd unit | `/lib/systemd/system/nginx.service` 残存・**inactive (dead)** |
| /etc/nginx/ | 残存 (`conf.d/`, `fastcgi.conf` 等あり・Aug 29 2025 配置) |

### 評価
- 過去にnginxインストール→削除した痕跡。**設定ファイル群だけ残っている異常状態**。
- Q3'=nginx 採用時に `apt install nginx` するとconf.d/既存設定が温存され衝突リスク。
- **推奨対応 (Wave 2eで実施)**:
  1. `/etc/nginx/conf.d/*` の中身を事前バックアップ
  2. `apt install nginx` 前に `/etc/nginx/sites-available/`, `sites-enabled/` の有無確認
  3. インストール後、conf.d/default.conf (もしあれば) と新規v2 server block の衝突有無確認
- 殿確認事項候補: 「旧conf.d/* を削除してクリーンインストールするか・温存するか」

---

## §7 RAM + Disk 空き

### Memory
| 項目 | 値 |
|---|---|
| Total | 457 Mi |
| Used | 159 Mi |
| Free | 13 Mi |
| Shared | 492 Ki |
| buff/cache | 296 Mi |
| **Available** | **297 Mi** |

| Swap | 値 |
|---|---|
| Total | 1.0 Gi |
| Used | 209 Mi |
| Free | 814 Mi |

### Disk (/)
| Filesystem | Size | Used | Avail | Use% |
|---|---|---|---|---|
| /dev/vda2 | 25G | 8.7G | **15G** | 38% |

### 評価
- **RAM 457MB は小型VPS構成**。React build (`npm run build`) は最大数百MB消費し得る。Swap 1GB併用で凌げる可能性大だが、build中の OOM Killer 起動リスクあり。
- 推奨: build前に `free -h` 確認、build中は `vmstat 5` で swap 使用率モニタ。
- Disk 15G空きは十分(v2 clone+venv+node_modules で約500MB-1GB予測・余裕あり)。

---

## §8 port 8000/8001/8443 占有状況 (FastAPI v2用)

```
LISTEN 127.0.0.1:8443  users:(("uvicorn",pid=671,fd=7))  ← agriha-linebot 継続
```

| Port | 状態 | 用途候補 |
|---|---|---|
| 8000 | **空き** | rotation-planner-v2 FastAPI 第一候補 |
| 8001 | **空き** | rotation-planner-v2 FastAPI フォールバック |
| 8443 | **占有** (agriha-linebot uvicorn) | v2では使用しない |

→ FastAPI v2 は **port 8000** で起動できる(空き確認済)。nginx (port 80/443) からリバプロでv2 backendへルーティング設計可。

---

## §9 /var/www/rotation-planner-v2/ 未存在確認

```
ls: cannot access '/var/www/rotation-planner-v2': No such file or directory
```

→ Wave 2d-1 (clone+venv) の配置先として **クリーン状態**。既存ファイルとの衝突なし。

---

## §10 webapp ユーザー nvm/Node 未導入確認

| 項目 | 結果 |
|---|---|
| `/home/webapp/.nvm` | **不在** (`ls` 失敗) |
| `command -v node` | **NO_NODE** |

→ Wave 2d-2 (足軽1担当・nvm + Node 20導入) の前提整合。**クリーン状態から nvm install で導入可能**。

---

## 付録: 実行コマンド一覧 (read-only監査用)

```bash
# 全て ssh debian@ik1-421-42663.vs.sakura.ne.jp '...' 経由

# §1
sudo -u webapp sqlite3 DB ".tables"
sudo -u webapp sqlite3 DB "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;"

# §2
sudo -u webapp sqlite3 DB "SELECT username, role, length(password_hash) FROM users;"

# §3
ps -ef | grep -E "ntrip|caster" | grep -v grep
sudo ss -tlnp | grep 2101

# §4
sudo ss -tlnp / sudo ss -ulnp

# §5
cd /var/www/rotation-planner/app && sudo -u webapp git status --short
sudo ls -la /var/www/rotation-planner/app/.env*

# §6
which nginx / systemctl status nginx --no-pager / ls -la /etc/nginx

# §7
free -h / df -h /var/www

# §8
sudo ss -tlnp | grep -E ":8000|:8001|:8443"

# §9
ls -la /var/www/rotation-planner-v2

# §10
sudo -u webapp ls -la /home/webapp/.nvm
sudo -u webapp bash -c "command -v node || echo NO_NODE"
```

書き込み・サービス操作・設定変更は一切実行していない。SSH接続+sudo read-onlyコマンドのみ。

---

## Wave 2c-2g 着手判定

| 後続subtask | 担当 | 依存解消条件 | 本baseline での判定 |
|---|---|---|---|
| subtask_1227 | 部屋子1 (clone+venv+pip) | /var/www/rotation-planner-v2/ 未存在 | ✓ §9 |
| subtask_1228 | 足軽1 (nvm + Node 20) | webapp nvm 未導入 | ✓ §10 |
| subtask_1230 | 部屋子1 (JWT_SECRET生成) | DB schema 確認済 | ✓ §1 |

→ **3 subtask 同時 unblock 可能** (本subtask完了で家老が dispatch)

軍師指摘の RAM 制約 (§7) と nginx 設定残存 (§6) は Wave 2e (nginx設定) 着手時に再確認すること。
