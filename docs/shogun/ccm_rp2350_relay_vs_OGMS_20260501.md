# ccm_rp2350_relay vs OGMS 3者比較レポート

- **作成日**: 2026-05-01T21:48:35
- **作成者**: ashigaru6（部屋子1）
- **cmd**: cmd_568 / subtask_1200
- **比較対象**: A=独立リポ / B=uecs-hw側 / C=OGMS（github.com/yasunorioi/OGMS）

---

## §1. サマリ

### 系譜判定結論

| 系譜 | 判定 | 根拠概要 |
|---|---|---|
| **C(OGMS) = B系譜の正本（agri-relay派生）** | ✅確定 | OGMS初期commit `a6986d5 feat: agri-relay v1.0.0` 確認 / 5論理単位の関数定義がBとC間で完全一致（`enum RelayOwner`/`SerialPIO sen0575Serial`） / cmd_525で agri-relay→OGMS リネーム履歴あり |
| **A(独立リポ) は別系統（ArSprout CCMスレーブ）** | ✅確定 | A README "ArSprout CCMスレーブ" / `web_ccm.h` 保有 / `modbus_slave.h`(Slave) / B・Cと別目的（CCM-UDP multicast前提） |
| **両系譜統合** | ❌否定 | A固有の web_ccm.h / modbus_slave.h はC不在。CCM全廃（commit 7ae92f2）でA→C統合は否定 |

### 5論理単位 反映状況一覧（C=OGMS）

| # | 論理単位 | C反映 | 主要根拠ファイル |
|---|---|:---:|---|
| 1 | リレー所有権管理 | ✅反映済 | `ogms.ino:297` `enum RelayOwner` / `claimRelay`/`releaseRelay` |
| 2 | SCD4x CO2/温湿度 | ✅反映済 | `sensor_registry.h` (0x62 SCD41) / `web_api.h` (g_scd41_co2/temp/hum公開) |
| 3 | CO2 Guard（換気連動） | ✅反映済 | `web_protection.h` (co2Guard.enabled/threshold_ppm/CO2_GUARD_ACTIONS UI完備) |
| 4 | SEN0575（DFRobot排水センサ） | ✅反映済 | `ogms.ino:65` `SerialPIO sen0575Serial(GPIO44/45, 64)` / `web_dashboard.h` ステータス表示 |
| 5 | 排水率算出 | ✅反映済 | `ogms.ino` `last_drain_rate` / `web_api.h` `drain_rate` JSON公開 |

**結論**: B(uecs-hw)の uncommitted 5論理単位は **全てC(OGMS)に既に反映済**。
→ cmd_566 (B uncommitted commit) は **重複作業**であり、Bは廃止 or C参照化が合理的。

---

## §2. C(OGMS) 基本情報

- **remote**: `https://github.com/yasunorioi/OGMS.git`
- **HEAD**: `182c0de5cac7f6bd10ae1711c2541188e902a91b`
- **最新commit**: `2026-04-25 21:23:14 yasunorioi  docs: add architecture diagram (Mermaid) to README`
- **総commit数**: 38
- **初期commit**: `a6986d5 feat: agri-relay v1.0.0 — スタンドアロン温室リレーコントローラ`（agri-relay起源）
- **リネーム履歴**: `87fd868 feat: cmd_525 Wave1 agri-relay→OGMS リネーム完了`
- **現FW版**: v2.1.0（commit b339226 `feat: v2.1.0 USB-NCM + Modbus RTU Master + Webページyield修正`）
- **README識別**: "OGMS — Open Greenhouse Management System (RP2350B)"

### Cファイル構成（17ソースファイル + docs）

```
ogms.ino (92642B)            // メインスケッチ
modbus_master.h (5216B)      // Modbus RTU Master（v2.1.0新規）
sensor_registry.h            // I2Cセンサーレジストリ
sw_watchdog.h                // SWウォッチドッグ
usb_ncm.h / usb_ncm_init.cpp // USB-NCM (TinyUSB)
web_api.h                    // JSON API
web_common.h / web_config.h  // 共通HTML / 設定UI
web_dashboard.h              // ダッシュボード
web_greenhouse.h             // 温室UI
web_irrigation.h             // 灌水UI（drain_rate表示含む）
web_modbus.h                 // Modbus UI
web_mqtt.h                   // MQTT設定UI（CCM代替）
web_ota.h                    // OTA更新UI
web_protection.h             // 保護機能UI（CO2 Guard含む）
web_i18n.h                   // 多言語化（EN/JP）
docs/operation-manual.md/pdf // 操作マニュアル
```

---

## §3. A vs C 差分

### ファイル一覧差分（非.git/build/.pio）

```
A 固有 : web_ccm.h, modbus_slave.h, ccm_rp2350_relay.ino, build/, tools/, docs/setup-side-window.md, .tmux.conf
C 固有 : ogms.ino, modbus_master.h, web_greenhouse.h, web_irrigation.h, web_mqtt.h, web_protection.h, LICENSE, .gitignore
共通(差分あり): README.md, platformio.ini, web_api.h, web_common.h, web_config.h, web_dashboard.h, web_modbus.h, docs/operation-manual.md, docs/operation-manual.pdf, docs/pdf-header.tex
共通(同一)  : sensor_registry.h, sw_watchdog.h, usb_ncm.h, usb_ncm_init.cpp, web_i18n.h, web_ota.h
```

### 主要相違点

| 項目 | A | C |
|---|---|---|
| メインsketch名 | `ccm_rp2350_relay.ino` (49141B) | `ogms.ino` (92642B) |
| 通信プロトコル | **CCM** (UECS-UDP multicast) | **MQTT** (PubSubClient) ← commit 7ae92f2 で全廃 |
| Modbus | Slave (`modbus_slave.h`) | **Master** (`modbus_master.h` v2.1.0新規) |
| 機能領域 | I/Oスレーブ専業 | 温室自律制御（greenhouse/irrigation/protection UI追加） |
| platformio追加lib | なし | `knolleary/PubSubClient@^2.8`, `4-20ma/ModbusMaster@^2.0.1` |
| README系譜 | "ArSprout CCMスレーブ" | "OGMS — Open Greenhouse Management System" |

→ **A は ArSprout CCM 互換の純粋スレーブ、C は agri-relay 系の自律温室制御FW**。別系統。

---

## §4. B vs C 差分（本cmd核心）

### ファイル一覧差分

```
B 固有 : ccm_rp2350_relay.ino (143570B uncommitted, モノリシック)
C 固有 : ogms.ino (92642B), modbus_master.h, usb_ncm.h, usb_ncm_init.cpp,
         web_api.h/common.h/config.h/dashboard.h/greenhouse.h/i18n.h/
         irrigation.h/modbus.h/mqtt.h/ota.h/protection.h, docs/, LICENSE, .gitignore
共通(差分あり): README.md, platformio.ini
共通(同一)  : sensor_registry.h, sw_watchdog.h
```

### platformio.ini 差分

| 項目 | B | C |
|---|---|---|
| TinyUSB | `-DUSE_TINYUSB=0` | **`-DUSE_TINYUSB=1`** |
| USB-NCM | 未対応 | **`-DCFG_TUD_NCM=1`** |
| TinyUSB wrap | なし | `-Wl,--wrap=TinyUSB_Device_Init` |
| SCD4x lib version | `^0.4.0` | `^1.1.0` |
| MQTT lib | なし | **`PubSubClient@^2.8`** |
| Modbus Master lib | なし | **`ModbusMaster@^2.0.1`** |
| Modbus Slave lib | なし | なし（A側のみ） |

→ **C はBの上位互換**（USB-NCM/MQTT/ModbusMaster追加）

### 構造差分

- **B はモノリシック**（3ファイル: ino+README+platformio.ini+sensor_registry.h+sw_watchdog.h）
- **C は分割構造**（17ソース、Webページ/プロトコルごとにヘッダー独立）

### サイズ比較

| ファイル | A | B | C |
|---|---|---|---|
| メインino | 49141B | **143570B** (uncommitted) | 92642B |
| ソースファイル数 | 14 | **3** | 17 |

→ B は uncommitted 機能込みで肥大化、C は分割化で各ファイル適度。**実機能は B≒C** だが C は構造化済み。

### 直接比較サンプル（B/C 完全一致行）

```
[B] ccm_rp2350_relay.ino:69  : SerialPIO sen0575Serial(SEN0575_TX_PIN, SEN0575_RX_PIN, 64);
[C] ogms.ino:65              : SerialPIO sen0575Serial(SEN0575_TX_PIN, SEN0575_RX_PIN, 64);

[B] ccm_rp2350_relay.ino:261 : enum RelayOwner : uint8_t {
[C] ogms.ino:297             : enum RelayOwner : uint8_t {
```

→ **完全一致。BとCは同一系譜**。

---

## §5. 5論理単位 反映状況（cmd_566識別の uncommitted 機能群）

| # | 論理単位 | C反映 | 根拠（grep結果） |
|---|---|:---:|---|
| 1 | リレー所有権管理 | ✅**反映済** | `ogms.ino`: `enum RelayOwner : uint8_t` / `void claimRelay(uint8_t ch, RelayOwner owner)` / `void releaseRelay(uint8_t ch, RelayOwner owner)` |
| 2 | SCD4x CO2/温湿度 | ✅**反映済** | `sensor_registry.h`: `SENSOR_SCD41 // 0x62 - CO2/Temp/Hum` / `{0x62, SENSOR_SCD41, "SCD41"}` ／ `web_api.h`: `g_scd41_co2`, `g_scd41_temp`, `g_scd41_hum`, `scd41_ok`, `scd41_detected` ／ `web_protection.h`: `"CO2 Guard (requires SCD41)"` |
| 3 | CO2 Guard（換気連動） | ✅**反映済** | `web_protection.h`: `co2Guard.enabled`, `co2Guard.threshold_ppm`, `CO2_GUARD_ACTIONS`, `co2Guard.actions[i].relay_ch`, `co2Guard.actions[i].duration_sec` ／ getField "co2_en"/"co2thr"/"cd<N>" UI完備 |
| 4 | SEN0575（DFRobot排水センサ） | ✅**反映済** | `ogms.ino`: `// ========== SEN0575 TTL UART (GPIO44/45 expansion header) ==========` / `const int SEN0575_TX_PIN = 44; // RP2350 TX → SEN0575 C/R(RX)` / `SerialPIO sen0575Serial(SEN0575_TX_PIN, SEN0575_RX_PIN, 64)` ／ `web_dashboard.h`: `SEN0575 ✓/✗` バッジ表示 ／ `web_api.h`: `sen0575_ok` |
| 5 | 排水率算出 | ✅**反映済** | `ogms.ino`: `float last_drain_rate; // 直近の排水率` / `irriRun[i].last_drain_rate = drainRate;` ／ `web_api.h`: `ir["drain_rate"] = round(irriRun[i].last_drain_rate * 1000) / 10.0` ／ `web_irrigation.h`: `'... DUTY '+r.duty+'% (drain:'+r.drain_rate+'%)'` |

**判定: 5/5 全反映済**。Cの方が表記改善（C側はチェックマーク `✓` 追加でUX改善あり）。

---

## §6. 系譜判定（A後継 / B後継 / 統合 / 独立）

### 確定: **C(OGMS) = B(uecs-hw内ccm_rp2350_relay)系譜の正本**

#### 根拠1: OGMS git log の起源証拠

```
a6986d5 feat: agri-relay v1.0.0 — スタンドアロン温室リレーコントローラ  ← OGMS最古commit
...
87fd868 feat: cmd_525 Wave1 agri-relay→OGMS リネーム完了
...
b339226 feat: v2.1.0 USB-NCM + Modbus RTU Master + Webページyield修正  ← 最新機能commit
182c0de docs: add architecture diagram (Mermaid) to README             ← HEAD
```

→ **agri-relay 起源 → cmd_525 で OGMS にリネーム → v2.1.0 まで進化**

#### 根拠2: 5論理単位の関数定義が B と C で完全一致

ピン定義（GPIO44/45）/関数シグネチャ（`enum RelayOwner`, `claimRelay`, `releaseRelay`）/コメント文（"SEN0575 TTL UART (GPIO44/45 expansion header)"）が **完全一致**。
独立実装ではあり得ない一致度 → 同一コードベース由来。

#### 根拠3: cmd_565 殿裁定との整合

- Q1: uecs側B = agri-relay系FW別目的(温室自律制御) ✅ 確定
- Q2: リネーム不要 — 既に **OGMS** として公開済み

→ B は agri-relay 派生、C は OGMS（agri-relay リネーム後）。**同系譜**。

#### A は別系統（独立確定）

- A README: "ArSprout CCMスレーブ"（CCM-UDP multicast前提）
- A: `web_ccm.h` / `modbus_slave.h` 保有 → C不在
- C: CCM全廃 commit 7ae92f2 "feat: CCM全廃→MQTT置換" → A流れと逆
- A は ArSprout 互換の純粋I/Oスレーブとして独立進化中

### B と C の関係（時系列推定）

```
[time]
agri-relay (殿リポ)
  ├─ a6986d5 v1.0.0 ─┐                                              │ uecs-hw に C/P
  │                  │                                              ▼
  ├─ ...             │                       B (uecs-hw内 ccm_rp2350_relay)
  │                  │                       ├─ commit (8b5f901, 3371ffa, b2685da, fc1b411, 2128879)
  │                  │                       └─ uncommitted (143570B、5論理単位)
  ├─ 87fd868 cmd_525 リネーム→OGMS
  ├─ 7ae92f2 CCM全廃→MQTT
  ├─ b339226 v2.1.0 USB-NCM+ModbusMaster
  └─ 182c0de HEAD（5論理単位含む）

A (独立リポ /home/yasu/ccm_rp2350_relay) ── 別系統 ArSprout CCMスレーブ
```

---

## §7. 後続cmd起票判断材料（殿向け選択肢提示）

### cmd_566（B uncommitted commit）の方針

| 選択肢 | 内容 | 推奨度 |
|---|---|---|
| α: cmd_566 打ち切り | B uncommittedはC側に既反映のため commit作業不要。Bは git checkout で uncommitted 破棄 | ★★★（最も合理的） |
| β: B を C のサブモジュール化 | uecs-hw/arduino/ccm_rp2350_relay を git submodule(OGMS) に置換 | ★★☆（uecs-hw全体構造への影響あり） |
| γ: B を OGMS 旧版アーカイブとして残す | uncommitted破棄+RENAMETO=ccm_rp2350_relay_legacy みたいな形 | ★☆☆（混乱の元） |
| δ: cmd_566継続（B側でcommit） | C側に既存機能をBにcommitして二重管理化 | ✗（重複作業・非推奨） |

### A の扱い

- A（/home/yasu/ccm_rp2350_relay）は **ArSprout CCM互換の独立リポ**として維持。
- C(OGMS) と用途が違う（CCM-UDP multicast vs MQTT）ため統合不可・統合不要。
- v1.3.0-modbus（cmd_521移行版）として独立進化を継続。

### Cの今後

- v2.1.0 (USB-NCM + Modbus RTU Master) が最新
- Mermaid アーキテクチャ図追加済（最新HEAD）
- 公開済みだがArsprout/UECSコミュニティへ周知未実施（memory: 2026-04-25殿裁定で非公開維持方針あり、ただしOGMSは既public化済み）

---

## §8. 殿への重点質問（1-3件）

### Q1【最優先】: cmd_566 の方針

**B（uecs-hw内 ccm_rp2350_relay）の uncommitted は C(OGMS) に既に反映済**であることが確定した。  
cmd_566 を **打ち切り（選択肢α）** とし、Bは git checkout で uncommitted 破棄でよろしいか？  
それとも別の扱いを希望されるか？

### Q2: B のディレクトリ自体の扱い

uecs-hardwares リポジトリ内の `arduino/ccm_rp2350_relay/` ディレクトリは:
- (a) 削除（OGMS に一本化）
- (b) git submodule(OGMS) に置換
- (c) README.md に「OGMSへ移行済」のリダイレクト記述だけ残して空に
- (d) このまま放置（混乱は許容）

どれを希望されるか？

### Q3: A(独立リポ) と C(OGMS) の役割分担明文化

A=ArSprout CCMスレーブ専業 / C=OGMS自律温室制御 という棲み分けで進めてよろしいか？  
両リポ README に「A は B/C と別系統」明記の追記要否を確認したい。

---

## 付録: コマンド・データ証跡

```bash
# OGMS 取得
cd /tmp && git clone https://github.com/yasunorioi/OGMS.git OGMS_clone
# HEAD: 182c0de5cac7f6bd10ae1711c2541188e902a91b
# 38 commits / 17 source files / ogms.ino 92642B

# A vs C ファイル差分
diff -rq /home/yasu/ccm_rp2350_relay /tmp/OGMS_clone

# B vs C ファイル差分
diff -rq /home/yasu/uecs-hardwares/arduino/ccm_rp2350_relay /tmp/OGMS_clone

# 5論理単位 grep on C
grep -ri "RelayOwner|SCD4x|co2_guard|SEN0575|drain_rate" /tmp/OGMS_clone --include="*.ino" --include="*.h"
```

### read-only確認

- A (`/home/yasu/ccm_rp2350_relay`): **書き込み0件**（read-only厳守）
- B (`/home/yasu/uecs-hardwares/arduino/ccm_rp2350_relay`): **書き込み0件**（read-only厳守）
- C (`/tmp/OGMS_clone`): **書き込み0件**（read-only厳守、cloneのみ）
- F006 厳守: GitHub Issue/PR/コメント投稿0件
