# ArSprout 自前クラウド基盤設計

> **正式リポジトリ**: `github.com:yasunorioi/unipi-agri-ha.git` (ローカル: `/home/yasu/unipi-agri-ha`)
> priority: medium | karo: roju
> Updated: 2026-02-07
> Phase 1-3 設計完了（cmd_108〜113）。次は実機構築・検証フェーズ。

## 検証済み事項

| 項目 | 結果 | 日付 |
|------|------|------|
| Pico 2 W + MicroPython v1.27.0 | ✅ 動作確認 | 2026-02-07 |
| WiFi → MQTT pub/sub | ✅ 疎通確認 | 2026-02-07 |
| ArSprout UECS-CCM データ取得 | ✅ 気象6種リアルタイム | 2026-02-07 |
| ArSprout Mosquitto | 稼働中だがpublishなし（SQLite直書き） | 2026-02-07 |
| VPN経由SSH接続 (arpi@10.10.0.10) | ✅ 公開鍵認証OK (RTT 99ms) | 2026-02-08 |
| UniPi 1.1 I2C疎通 (MCP23008 0x20) | ✅ i2cdetect検出成功 | 2026-02-08 |
| UniPi 1.1 リレーON/OFF (smbus2) | ✅ ArSprout停止時のみ動作 | 2026-02-08 |
| HA連携方式調査 | 推奨1位: Modbus TCP, 2位: MQTT Bridge | 2026-02-08 |

### UECS-CCM で取れるデータ（192.168.1.71）

| type | 意味 | 単位 | 備考 |
|------|------|------|------|
| WAirTemp | 外気温 | ℃ | -9.2℃（冬期） |
| WAirHumid | 外湿度 | % | 75% |
| WWindSpeed | 風速 | m/s | 0.0（無風時） |
| WWindDir16 | 風向 | 16方位 | 2 |
| WRainfall | 降雨 | - | 0（降雨なし） |
| WRainfallAmt.cMC | 降水量 | mm | 0.0 |
| Irriopr | 灌水運転 | 0/1 | 制御フラグ |
| cnd.cMC | 条件 | 0/1 | 内部フラグ |

### ArSprout SQLite（compo_log）で取れるデータ

| compo_id | 種別 | 値域 | 備考 |
|----------|------|------|------|
| 7 | SEN_TMP（外気温） | -10〜-4℃ | 稼働中 |
| 8 | SEN_RH（外湿度） | 46〜77% | 稼働中 |
| 10 | SEN_SPD（風速） | 0〜2.66 m/s | 稼働中 |
| 11 | SEN_DIR（風向） | 2〜12° | 稼働中 |
| 27 | SEN_SWT（水分） | 0.005〜0.012 | 稼働中 |
| 40 | ACT_SWT_IRR（灌水） | 0/1 | 時々ON |
| 55 | SEN | ≈0 | ほぼ無データ |
| 51 | SEN | 0 | 無データ |

## フェーズ1: センサー試用 + MicroPythonライブラリ ✅ 設計完了（cmd_108）

- [x] DFRobot SEN0575 降雨センサー MicroPythonドライバ作成
- [x] I2Cセンサードライバ（SHT3x/SHT4x, BH1750）
- [x] MicroPython共通ライブラリ設計
  - WiFi/Ethernet抽象化層
  - MQTT接続管理（再接続、LWT）
  - OTAアップデート機構
  - I2Cセンサードライバ群
- [x] W5500-EVB-Pico-PoE対応設計
- 成果物: `unipi-agri-ha/micropython/`

## フェーズ2: 自前クラウド基盤構築 ✅ 設計完了（cmd_109）

- [x] InfluxDB インストール・設定手順書+スクリプト
- [x] Grafana インストール・設定手順書+スクリプト
- [x] Telegraf（MQTT → InfluxDB）設定
- [x] UECS-CCM → MQTT ブリッジスクリプト
- [x] Grafana ダッシュボード（気象6種+制御フラグ、12パネル）
- 成果物: `unipi-agri-ha/cloud_server/`

## フェーズ3: 実運用移行 ✅ 設計完了（cmd_111〜112）

- [x] Picoノード実機配置設計書
- [x] OTAアップデート運用手順書（お針子監査合格）
- [x] LINE Messaging API アラート連携ガイド（LINE Notify終了対応済み）
- [x] 統合テスト手順書（E2E検証ガイド）
- [x] ArSprout → HA + Pico 制御移行計画書（全10章557行）
- 成果物: `unipi-agri-ha/docs/`

## 最終ゴール: ArSprout SDカード廃棄

ArSproutの価値はハード側（UniPi 1.1リレー、安全回路、ウォッチドッグ）。
ソフト（SDカード）はHA+Node-REDで完全置き換え、廃棄する。

```
Picoノード群 → MQTT → HA（データ収集+制御の一元管理）
                        ├── Node-RED（ArSprout制御ロジック引き継ぎ）
                        ├── LINE Messaging API（アラート）
                        ├── InfluxDB + Grafana（長期保存・可視化）
                        └── ArSprout HW制御（UniPi 1.1 GPIO/Modbus経由）
```

※ UECS-CCM→MQTTブリッジは不要。HAが直接データを拾う。

## ハードウェア設計（進行中）

### センサーノード基板（cmd_122）
Grove Shield for Pi Pico代替。W5500-EVB-Pico-PoEにスタック接続。
- Grove I2C×2（I2C0: GP4/GP5, I2C1: GP6/GP7）
- ADC×3（GP26/GP27/GP28、土壌水分等）
- 1-Wire（GP2、DS18B20土壌温度）
- ファンPWM駆動回路（NchMOSFET、ソフトスタート対応）
- PoE電源: 8W総出力、ファン含め4W程度で余裕十分

### アクチュエータノード基板（cmd_123）
Pico 2 W(WiFi)にスタック。制御盤内設置。
- 4chリレー（GP10:灌水、GP11:バルブ、GP12:換気扇、GP13:汎用）
- フォトカプラ絶縁 + フライバックダイオード
- 端子台によるAC/DC負荷接続

### 筐体設計（完了）
- 強制換気式、30mmファン、OpenSCAD設計済み
- 成果物: arsprout_analysis/cad/enclosure/, docs/ENCLOSURE_DESIGN.md

### UniPi 1.1リレー制御 ✅ 実機検証済み（cmd_132, 2026-02-08）
- I2C経由（MCP23008、アドレス0x20）でリレーON/OFF → **smbus2で動作確認済み**
- OLATレジスタ(0x0A)でリレー状態読み取り可能 → **読み書き正常動作確認済み**
- I2Cバス上の他デバイス: 0x18(MCP9808温度), 0x3e, 0x50, 0x57, 0x68
- **重要**: ArSproutプロセス(Java SpringBoot PID392)がMCP23008を占有。I2C直接制御はArSprout停止後のみ可能
- HA連携推奨: **1位 Modbus TCP**(27点) > 2位 MQTT Bridge(24点) > 3位 EVOK REST API(19点) > 4位 I2C直接(13点/非推奨)
- SSH接続: arpi@10.10.0.10（公開鍵認証、VPN RTT 99ms）
- python3-smbus インストール済み（apt）
- 駆動系ブレーカーは落としてあるため、リモートテスト可能

## テスト環境（実機構成）

### W5500-EVB-Pico-PoE + Grove Shield for Pi Pico（スタック接続）

- **ファームウェア**: MicroPython v1.27.0
- **電源**: PoE給電（802.3af）
- **デバイスパス**: /dev/ttyACM0 or /dev/ttyACM1（`ls /dev/ttyACM*` で確認）

#### ピンアサイン

| 機能 | ピン | 備考 |
|------|------|------|
| I2C0 SDA | GP8 | Grove I2Cポート1 |
| I2C0 SCL | GP9 | Grove I2Cポート1 |
| I2C1 SDA | GP6 | Grove I2Cポート2 |
| I2C1 SCL | GP7 | Grove I2Cポート2 |
| SPI (W5500専用) | GP16-GP21 | **使用不可** — MISO/CS/SCK/MOSI/RST/INT |
| ADC | GP26-GP28 | 使用可（アナログ兼用） |
| Digital | D16/D18/D20 | **使用不可**（W5500 SPI競合） |

#### MicroPython初期化例
```python
from machine import Pin, I2C
i2c0 = I2C(0, sda=Pin(8), scl=Pin(9))   # Grove I2Cポート1
i2c1 = I2C(1, sda=Pin(6), scl=Pin(7))   # Grove I2Cポート2
print(i2c0.scan())  # → [0x44, 0x62, 0x76] 等
```

### 接続済みセンサー

| センサー | 型番 | I2Cアドレス | 計測項目 | 備考 |
|---------|------|-----------|---------|------|
| SCD41 | SCD41 | 0x62 | CO2(ppm) + 温度(℃) + 湿度(%) | Grove I2C接続。温度は+3.29℃オフセット必要 |
| SHT40 | ENV IV内蔵 | 0x44 | 温度(℃) + 湿度(%) | M5Stack ENV IV。**温度基準センサー** |
| BMP280 | ENV IV内蔵 | 0x76 or 0x77 | 気圧(hPa) + 温度(℃) | M5Stack ENV IV。温度は+0.60℃オフセット |

### 温度較差計測結果（subtask_332, 2026-02-09）

10回×30秒計測、SHT40基準で較正:

| センサー | 平均(℃) | 標準偏差(℃) | オフセット | 用途推奨 |
|---------|---------|------------|----------|---------|
| SHT40 | 25.91 | 0.040 | 0.0（基準） | **温度・湿度の主センサー** |
| SCD41 | 22.61 | 0.049 | +3.29℃ | CO2値のみ使用推奨。温度は精度低 |
| BMP280 | 25.31 | 0.039 | +0.60℃ | 気圧のみ使用推奨。温度は参考値 |

SCD41の3.3℃差の原因: 通風不足（Grove筐体内の空気滞留）+ NDIR方式CO2センサーの温度精度限界。
config.pyにオフセット値設定済み。

### 切腹ルール（厳守）

**`cat /dev/ttyACMx` 禁止。`mpremote` を使え。**
catするとシリアルポートがロックされ、MicroPython REPLに復帰不可能になる。

```bash
# 正しいアクセス方法
mpremote connect /dev/ttyACM0
mpremote run script.py
mpremote mount .
```

### 関連スキル・リファレンス

| リソース | パス | 内容 |
|---------|------|------|
| Grove Shieldガイド | .claude/skills/pico-grove-shield-guide.md | ピン配置・制約・Grove接続方法 |
| W5500ガイド | .claude/skills/w5500-evb-pico-guide.md | SPI初期化・Ethernet・MQTT |
| クイックリファレンス | memory/w5500_quickref.md | コピペ用コード集（SPI/I2C/MQTT） |

## 次フェーズ: ソフトウェア（今すぐ可能）

- [ ] Node-RED制御ロジック再実装（cmd_124、温度制御・灌水・アラート）
- [ ] InfluxDB+Grafana+Telegraf設定検証（cmd_125）
- [x] UniPi 1.1リレーI2C疎通テスト（VPN経由）→ cmd_132完了、ArSprout停止時のみI2C制御可
- [ ] LINE Messaging APIアラート実機テスト

## 次フェーズ: 実機構築・検証（3月〜）

- [ ] HA OS SDカード作成 → ArSprout Pi に差し替え
- [ ] HAからUniPi 1.1リレー制御確認（EVOK/Modbus経由）
- [ ] Picoノード実機ファームウェア書き込み（BOOTSEL+ブラウザ）+ センサー接続テスト
- [ ] W5500-EVB-Pico-PoE実機MQTT疎通
- [ ] OTA実機テスト
- [ ] ArSprout SDカード完全廃棄

## ネットワーク構成

```
[インターネット]
    │
    ├── さくらクラウド VPNサーバー（153.127.46.167:31820）
    │       │
    │       ├── 10.10.0.10   ArSprout（ハウス内）
    │       ├── 10.10.0.100  Windows PC
    │       └── 10.10.0.101  Ubuntu PC
    │
[ハウス内LAN]
    │
    ├── 192.168.1.71  ArSprout本体（Pi4J + UniPi 1.1）
    ├── 192.168.1.74  テストノード（殿自作）
    └── 192.168.1.xx  Picoノード群（将来）

[自宅LAN]
    │
    ├── 192.168.15.14  Ubuntu PC（Mosquitto, InfluxDB, Grafana）
    └── 192.168.15.15  Pico 2 W テスト
```

### Starlink回線特性（実機テスト時の注意）

殿のインターネット回線は **Starlink**（衛星インターネット）。
衛星ハンドオーバーにより **数秒〜数十秒の瞬断が頻発** する。

| 影響を受ける操作 | 症状 | 対策 |
|----------------|------|------|
| VPN越しSSH | セッション切断 | `ServerAliveInterval 15` + `ServerAliveCountMax 3` を ~/.ssh/config に設定 |
| mpremote | タイムアウト・切断 | タイムアウト長めに設定、切断時はリトライ |
| scp/rsync | 転送中断 | `--partial --progress` で中断再開対応 |
| 長時間コマンド | 切断で中断 | **tmux/screen内で実行**し、切断されても継続 |
| MQTT | 一時切断 | 再接続ロジック組み込み済み、影響少ない |

```
# ~/.ssh/config 推奨設定（ArSprout向け）
Host arsprout
    HostName 10.10.0.10
    User arpi
    ServerAliveInterval 15
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

**足軽への注意**: VPN越しの実機操作では必ずtmux/screen内で作業すること。Starlink瞬断で切断されても作業が失われない。

## 技術選定

| 項目 | 選定 | 理由 |
|------|------|------|
| マイコン | Pico 2 W / W5500-EVB-Pico-PoE | RP2350、OTA対応 |
| FW | MicroPython v1.27.0 | OTA対応、統一 |
| 通信 | MQTT (Mosquitto) | 軽量、標準 |
| 時系列DB | InfluxDB | 大量ポイント、Grafana連携 |
| 可視化 | Grafana | ダッシュボード + アラート |
| アラート | Grafana → LINE Messaging API | LINE Notify終了済み(2025/3)、Messaging APIに移行 |
| 制御 | Home Assistant | ArSprout置き換え |
| センサーI/F | I2C（Grove）基本 | 殿の方針 |
| ノード通信 | PoE基本、WiFi制御盤付近のみ | 殿の方針 |
