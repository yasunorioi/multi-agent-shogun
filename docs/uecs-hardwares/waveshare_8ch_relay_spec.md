# Waveshare Industrial 8ch Relay Module 仕様書 + FW設計案

> **Product**: RP2350-ETH-8DI-8RO (RP2350B版)
> **Author**: ashigaru6 (subtask_1073 / cmd_489)
> **Date**: 2026-04-05
> **Status**: デバイス未購入。公式デモコード+ボード定義ヘッダから全ピンマップ確定済み
> **情報源**: Waveshare公式Wiki + デモコードZIP (DEV_Config.h, waveshare_rp2350_eth_8di_8ro.h)

---

## 1. 製品概要

| 項目 | 値 |
|------|-----|
| 正式名称 | RP2350-ETH-8DI-8RO / RP2350-POE-ETH-8DI-8RO (PoE版) |
| MCU | **RP2350B** (dual ARM Cortex-M33 + dual RISC-V Hazard3, 150MHz) |
| Flash | 16MB (W25Q080互換) |
| SRAM | 520KB |
| リレー | 8ch (1NO+1NC / ch), **GPIO直接制御** |
| デジタル入力 | 8ch (フォトカプラ絶縁, プルアップ, アクティブLOW) |
| Ethernet | W5500 SPI接続, 10/100Mbps RJ45 |
| 電源 | DC 7~36V (スクリュー端子) / USB-C 5V |
| 寸法 | 175 x 90 x 40 mm |
| 取付 | DINレール |

### ESP32-S3版からの変更点

| 項目 | ESP32-S3版 | RP2350版 (採用) |
|------|-----------|----------------|
| リレー制御 | TCA9554 I2Cエキスパンダ | **GPIO直接制御** (単純) |
| 通信 | WiFi + Ethernet + BLE | **Ethernet only** |
| MCU | ESP32-S3 (240MHz, 16MB Flash) | RP2350B (150MHz, 16MB Flash) |
| フレームワーク | arduino-esp32 | **arduino-pico** (Earle Philhower) |
| WDT | esp_task_wdt API | **hardware/watchdog.h** (solar_node.ino同等) |

### 公式リソース

| リソース | URL |
|---------|-----|
| Wiki (非PoE) | https://www.waveshare.com/wiki/RP2350-ETH-8DI-8RO |
| Wiki (PoE) | https://www.waveshare.com/wiki/RP2350-POE-ETH-8DI-8RO (未公開) |
| デモコードZIP | https://files.waveshare.com/wiki/RP2350-ETH-8DI-8RO/RP2350-ETH-8DI-8RO.zip |
| RGB LEDデモ | https://files.waveshare.com/wiki/RP2350-ETH-8DI-8RO/RP2350-ETH-8DI-8RO-RGB.zip |
| 拡張デモ(Modbus) | https://files.waveshare.com/wiki/RP2350-ETH-8DI-8RO/RP2350-ETH-8DI-8RO-Expand.zip |
| arduino-pico | https://github.com/earlephilhower/arduino-pico |
| Board Manager URL | https://github.com/earlephilhower/arduino-pico/releases/download/4.5.2/package_rp2040_index.json |

---

## 2. リレー制御方式: GPIO直接制御

ESP32-S3版のTCA9554 I2Cエキスパンダと異なり、RP2350版は**GPIOで直接リレーを制御**する。

```cpp
// DEV_Config.h より（公式デモコード）
#define RELAY1_PIN 17
#define RELAY2_PIN 18
#define RELAY3_PIN 19
#define RELAY4_PIN 20
#define RELAY5_PIN 21
#define RELAY6_PIN 22
#define RELAY7_PIN 23
#define RELAY8_PIN 24
```

制御: `gpio_put(RELAY1_PIN, 1)` でON、`gpio_put(RELAY1_PIN, 0)` でOFF。

### リレースペック

| 項目 | 値 |
|------|-----|
| 接点形式 | 1NO + 1NC / ch |
| 最大開閉 (AC) | 10A @ 250VAC |
| 最大開閉 (DC) | 10A @ 30VDC |
| 絶縁 | フォトカプラ絶縁 |
| 端子 | スクリュー端子 (COM, NO, NC / ch) |

---

## 3. 全GPIOマップ（公式デモコード + ボード定義から確定）

### UART0 (デフォルト/USB Serial)

| 機能 | GPIO | 出典 |
|------|:----:|------|
| TX | GPIO0 | waveshare_rp2350_eth_8di_8ro.h |
| RX | GPIO1 | waveshare_rp2350_eth_8di_8ro.h |

### WS2812 RGB LED

| 機能 | GPIO | 出典 |
|------|:----:|------|
| WS2812 DIN | GPIO2 | waveshare_rp2350_eth_8di_8ro.h / RP2350_WS2812B_Test.c |

### ブザー (PWM)

| 機能 | GPIO | 出典 |
|------|:----:|------|
| BEEP | GPIO3 | DEV_Config.h |

### RS485 (UART1)

| 機能 | GPIO | 出典 |
|------|:----:|------|
| TX | GPIO4 | Serial.h (UART1_TX_PIN) |
| RX | GPIO5 | Serial.h (UART1_RX_PIN) |

### I2C0 (RTC用)

| 機能 | GPIO | 出典 |
|------|:----:|------|
| SDA | GPIO6 | waveshare_rp2350_eth_8di_8ro.h |
| SCL | GPIO7 | waveshare_rp2350_eth_8di_8ro.h |

### GPIO8 — 未割当

GPIO8は公式デモコードに定義なし。W5500 INT または予約の可能性あり。

### デジタル入力 (8ch, プルアップ, アクティブLOW)

| 入力CH | GPIO | 出典 |
|:------:|:----:|------|
| DI1 | GPIO9 | DEV_Config.h (IN1_PIN) |
| DI2 | GPIO10 | DEV_Config.h (IN2_PIN) |
| DI3 | GPIO11 | DEV_Config.h (IN3_PIN) |
| DI4 | GPIO12 | DEV_Config.h (IN4_PIN) |
| DI5 | GPIO13 | DEV_Config.h (IN5_PIN) |
| DI6 | GPIO14 | DEV_Config.h (IN6_PIN) |
| DI7 | GPIO15 | DEV_Config.h (IN7_PIN) |
| DI8 | GPIO16 | DEV_Config.h (IN8_PIN) |

DI入力はIRQ対応。公式デモではGPIO_IRQ_EDGE_RISE/EDGE_FALLでリレーを連動制御。

### リレー出力 (8ch, GPIO直接)

| リレーCH | GPIO | 出典 |
|:--------:|:----:|------|
| Relay 1 | GPIO17 | DEV_Config.h (RELAY1_PIN) |
| Relay 2 | GPIO18 | DEV_Config.h (RELAY2_PIN) |
| Relay 3 | GPIO19 | DEV_Config.h (RELAY3_PIN) |
| Relay 4 | GPIO20 | DEV_Config.h (RELAY4_PIN) |
| Relay 5 | GPIO21 | DEV_Config.h (RELAY5_PIN) |
| Relay 6 | GPIO22 | DEV_Config.h (RELAY6_PIN) |
| Relay 7 | GPIO23 | DEV_Config.h (RELAY7_PIN) |
| Relay 8 | GPIO24 | DEV_Config.h (RELAY8_PIN) |

### W5500 Ethernet (SPI0)

| 機能 | GPIO | 出典 |
|------|:----:|------|
| RST | GPIO25 | ethchip_spi.h (PIN_RST) |
| CS | GPIO33 | ethchip_spi.h (PIN_CS) |
| SCK | GPIO34 | ethchip_spi.h (PIN_SCK) |
| MOSI | GPIO35 | ethchip_spi.h (PIN_MOSI) |
| MISO | GPIO36 | ethchip_spi.h (PIN_MISO) |

### GPIOサマリ表

| GPIO | 機能 | 方向 |
|:----:|------|:----:|
| 0 | UART0 TX | OUT |
| 1 | UART0 RX | IN |
| 2 | WS2812 RGB LED | OUT |
| 3 | ブザー (PWM) | OUT |
| 4 | RS485 TX (UART1) | OUT |
| 5 | RS485 RX (UART1) | IN |
| 6 | I2C0 SDA (RTC) | I/O |
| 7 | I2C0 SCL (RTC) | OUT |
| 8 | (未割当) | — |
| 9-16 | DI1-DI8 | IN |
| 17-24 | Relay 1-8 | OUT |
| 25 | W5500 RST | OUT |
| 26-32 | (未使用) | — |
| 33 | W5500 CS | OUT |
| 34 | W5500 SCK | OUT |
| 35 | W5500 MOSI | OUT |
| 36 | W5500 MISO | IN |
| 37-47 | (未使用 / TFカード等) | — |

---

## 4. 通信インターフェース

| I/F | 詳細 |
|-----|------|
| USB Type-C | 電源供給 + ファームウェア書込み (UF2 drag-and-drop) + シリアル通信 |
| Ethernet | W5500 SPI接続, 10/100Mbps RJ45 |
| RS485 | 絶縁, TVS+サージ保護, 120Ω終端(ジャンパ切替), UART1 (GPIO4/5) |
| Modbus RTU | RS485経由 (デフォルト9600bps) |

### LED インジケータ

| LED | 色 | 機能 |
|-----|-----|------|
| PWR | 赤 | 電源 |
| TXD | 緑 | RS485送信 |
| RXD | 青 | RS485受信 |
| RGB | WS2812 | プログラマブル (GPIO2) |

---

## 5. Arduino (arduino-pico) 対応

### ボード設定

```
Board Manager URL: https://github.com/earlephilhower/arduino-pico/releases/download/4.5.2/package_rp2040_index.json
Board: "Waveshare RP2350-ETH-8DI-8RO" (ボード定義あり)
  → 未登録の場合: "Generic RP2350" で代用可
Flash Size: "16MB"
Upload: USB (UF2) or Picoprobe
```

### RP2350B GPIO特殊制約

RP2350B は48本のGPIOを持つ（RP2350Aは30本）。本ボードは高番号GPIO (33-36) をW5500に使用。

| GPIO | 制約 | 本ボードでの用途 |
|------|------|---------------|
| GPIO0-1 | UART0デフォルト | USB Serial |
| GPIO25 | — | W5500 RST |

strapping pin制約なし（RP2350はESP32系と異なりstrapping pinがない）。

### 必要ライブラリ

| ライブラリ | 用途 | 備考 |
|-----------|------|------|
| Ethernet (W5500) | Ethernet通信 | arduino-pico対応版 or WIZnet ioLibrary |
| PubSubClient | MQTT | 2.8+ |
| ArduinoJson | JSONシリアライズ | **v7.x** (arduino-picoはv7推奨) |
| LittleFS | 設定ファイル保存 | arduino-pico標準搭載 |
| Wire | I2C (RTC) | arduino-pico標準搭載 |

### Watchdog (RP2350 = Pico SDK)

solar_node.ino の sw_watchdog.h と **同一API** を使用可能:

```cpp
#include <hardware/watchdog.h>
#include <pico/time.h>

// HW WDT: watchdog_reboot(0, 0, timeout_ms)
// SW WDT: repeating_timer + swWdtFeed() パターン (sw_watchdog.h そのまま流用可)
```

---

## 6. FW設計案: waveshare_relay_node

### 6.1 アーキテクチャ概要

```
┌─────────────────────────────────────────┐
│ waveshare_relay_node.ino                │
│                                         │
│  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │ W5500   │  │ MQTT     │  │ HA     │ │
│  │ Ethernet│  │ Client   │  │ Disc.  │ │
│  └────┬────┘  └────┬─────┘  └───┬────┘ │
│       │            │             │      │
│       └────────────┼─────────────┘      │
│                    │                    │
│  ┌─────────────────┴──────────────────┐ │
│  │ GPIO Direct Relay Control          │ │
│  │ GPIO17-24 = Relay 1-8              │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ LittleFS │  │ Watchdog │  │ DI    │ │
│  │ Config   │  │ 3-Tier   │  │ 8ch   │ │
│  └──────────┘  └──────────┘  └───────┘ │
└─────────────────────────────────────────┘
```

### 6.2 MQTTトピック設計

mqtt_relay_bridge.py のトピック構造に完全準拠（変更なし）:

#### Subscribe (QoS=1)

```
agriha/{house_id}/relay/{ch}/set
```

ペイロード:
```json
{"value": 1, "duration_sec": 180, "reason": "irrigation_zone_1"}
```

#### Publish (QoS=1, retain=true)

```
agriha/{house_id}/relay/state
```

ペイロード:
```json
{
  "ch1": 0, "ch2": 0, "ch3": 1, "ch4": 0,
  "ch5": 0, "ch6": 0, "ch7": 0, "ch8": 0,
  "ts": 1740000000,
  "node_id": "waveshare_relay_01",
  "uptime": 3600
}
```

#### デジタル入力状態

```
agriha/{house_id}/di/state
```

### 6.3 HA MQTT Auto Discovery

solar_node.ino の `publishHADiscovery()` パターンを踏襲。

- リレー: `homeassistant/switch/waveshare_relay_01_ch{N}/config` (8ch)
- DI: `homeassistant/binary_sensor/waveshare_relay_01_di{N}/config` (8ch)

### 6.4 Watchdog 3段構え

| Tier | 方式 | タイムアウト | 実装 |
|------|------|:----------:|------|
| Tier 1 | HW WDT | 8秒 | `watchdog_enable(8000, true)` + `watchdog_update()` |
| Tier 2 | SW WDT | 5秒×3miss=15秒 | **sw_watchdog.h そのまま流用** |
| Tier 3 | 定期リブート | 10分 | `millis() >= REBOOT_INTERVAL` (solar_node.ino踏襲) |

sw_watchdog.h はPico SDK の `repeating_timer` + `watchdog_reboot()` を使用しており、RP2350でもそのまま動作する。

### 6.5 LittleFS config.json

```json
{
  "mqtt_broker": "192.168.15.14",
  "mqtt_port": 1883,
  "house_id": "h2",
  "node_id": "waveshare_relay_01",
  "ip": "192.168.15.xx",
  "subnet": "255.255.255.0",
  "gateway": "192.168.15.1",
  "dns": "8.8.8.8",
  "sensor_interval": 10
}
```

WiFiなし→Ethernet固定IP設定が必要。DHCP対応は将来検討。

### 6.6 安全設計

| 項目 | 方針 | 実装 |
|------|------|------|
| 起動時 | **全リレーOFF** | setup()でGPIO17-24を全てLOW |
| 通信断 | **フェイルセーフ** | MQTT接続失敗3回連続でリブート |
| duration超過 | 自動OFF | タイマーで指定秒後にリレーOFF |
| 電源断→復帰 | 全OFF | setup()で必ず全OFFから開始 |

#### 起動時全OFF

```cpp
void initRelaysOff() {
    for (int i = 0; i < 8; i++) {
        gpio_init(RELAY1_PIN + i);
        gpio_set_dir(RELAY1_PIN + i, GPIO_OUT);
        gpio_put(RELAY1_PIN + i, 0);  // OFF
    }
}
```

### 6.7 リレー制御関数

```cpp
const int RELAY_PINS[8] = {17, 18, 19, 20, 21, 22, 23, 24};
uint8_t relayState = 0x00;

void setRelay(uint8_t ch, bool on) {
    if (ch < 1 || ch > 8) return;
    uint8_t idx = ch - 1;
    gpio_put(RELAY_PINS[idx], on ? 1 : 0);
    if (on) relayState |= (1 << idx);
    else    relayState &= ~(1 << idx);
}
```

ESP32-S3版のI2C書込みと比べ、直接GPIO制御のため遅延なし・障害点なし。

---

## 7. 既存システムとの対応関係

| 項目 | 1棟目 (UniPi) | 2棟目 (Waveshare RP2350) |
|------|-------------|--------------------------|
| HW | UniPi Neuron + MCP23008 | RP2350B + GPIO直接 |
| 制御I/F | I2C (MCP23008) | **GPIO直接** (最も単純) |
| MQTT Bridge | mqtt_relay_bridge.py (Python) | waveshare_relay_node.ino (Arduino) |
| Subscribe | agriha/{hid}/relay/{ch}/set | 同一 |
| Publish | agriha/{hid}/relay/state | 同一 |
| ペイロード | {"ch1":0,...,"ts":N} | 同一 + node_id, uptime |
| house_id | h1 (h01) | h2 |
| HA Discovery | なし (Python側) | あり (FW内蔵) |
| WDT | — | sw_watchdog.h流用 (solar_node.inoと同パターン) |

**互換性**: MQTTトピック・ペイロード構造が同一のため、上位のLLM制御層 (uecs-llm) は house_id の切替のみで両棟を制御可能。

---

## 8. 2棟目チャンネル割当（殿裁定 2026-04-05）

### 8.1 リレー出力 (RO) 割当

| RO | GPIO | 用途 | 制御元 | 備考 |
|:--:|:----:|------|--------|------|
| RO1 | 17 | 側窓A 開 | uecs-llm | 温度・湿度制御 |
| RO2 | 18 | 側窓A 閉 | uecs-llm | 温度・湿度制御 |
| RO3 | 19 | 側窓B 開 | uecs-llm | 温度・湿度制御 |
| RO4 | 20 | 側窓B 閉 | uecs-llm | 温度・湿度制御 |
| RO5 | 21 | 電磁弁 | uecs-llm | 灌水制御 |
| RO6 | 22 | 循環扇1 | uecs-llm | 換気 |
| RO7 | 23 | 循環扇2 | uecs-llm | 換気 |
| RO8 | 24 | 予備 | — | 将来拡張用 |

### 8.2 デジタル入力 (DI) 割当

| DI | GPIO | 用途 | 信号型 | 備考 |
|:--:|:----:|------|--------|------|
| DI1-2 | 9-10 | 灌水量パルス | パルスカウント | 流量計連動 |
| DI3-4 | 11-12 | 窓リミット（A開/閉） | ON/OFF | 側窓A端点検出 |
| DI5-6 | 13-14 | 窓リミット（B開/閉） | ON/OFF | 側窓B端点検出 |
| DI7-8 | 15-16 | 予備 | — | 将来拡張用 |

> **注意**: DI割当は暫定。実機配線後に確定。パルスカウント対応はFW拡張が必要（現FWはON/OFFのみ）。

### 8.3 I2Cセンサー

| デバイス | アドレス | 用途 |
|---------|:-------:|------|
| SHT40 | 0x44 | 温湿度（設置済み確定） |

### 8.4 UART排水センサー（追加実装が必要）

RS485 (UART1, GPIO4/5) を使用。排水量・EC等の計測センサーを接続予定。
プロトコル詳細は実機到着後に確定。MQTTトピック: `agriha/{house_id}/sensor/drain/state`

### 8.5 WebUI（追加実装が必要）

RP2350のW5500 Ethernet上でHTTP server (port 80) を提供。

| 機能 | 説明 |
|------|------|
| 状態確認 | リレー状態(8ch)、DI状態(8ch)、センサー値、uptime、MQTT接続状況 |
| 手動操作 | 各リレーのON/OFF/Duration付きONボタン |
| 設定確認 | IP, MQTT broker, house_id, node_id |

制御判断はRPi側uecs-llmが担う。WebUIは保守・デバッグ用の補助機能。

### 8.6 FW役割分担

```
┌──────────────────────────┐     ┌───────────────────────┐
│ RP2350 FW (本機)         │     │ RPi uecs-llm          │
│                          │     │                       │
│ (1) センサー読取→MQTT pub│────→│ 制御判断 (TiDE予測+    │
│ (2) MQTT sub→リレー制御  │←────│  ルールエンジン)       │
│ (3) WebUI (状態+手動操作)│     │                       │
└──────────────────────────┘     └───────────────────────┘
```

---

## 9. 実装時の注意事項

1. **W5500 SPI**: spi0使用。arduino-picoでは `SPI.begin()` ではなくピン番号指定の初期化が必要（GPIO33-36は高番号）
2. **Ethernet Library選定**: WIZnet ioLibrary (公式デモ使用) か、arduino-pico対応の Ethernet ライブラリか要検証
3. **LittleFS**: arduino-picoではビルド時にFS領域を指定（メニューから選択可能）
4. **OTA**: UF2ドラッグ&ドロップが標準。MQTT経由のOTAは将来検討
5. **RS485/Modbus**: UART1 (GPIO4/5)。将来のUECS CCM連携で使用する可能性あり
6. **RTC**: PCF85063相当のRTCがI2C0 (GPIO6/7) に接続。NTP不要時のタイムスタンプに使用可
7. **GPIO8**: 未割当。W5500 INTの可能性があるが公式コードに定義なし。実機到着後に確認

---

## 付録A: ESP32-S3版 参考情報（旧 subtask_1071）

ESP32-S3版 (ESP32-S3-ETH-8DI-8RO) の情報は殿の方針変更 (subtask_1073) により不採用だが、
比較参考として主要差分を記録する。

| 項目 | ESP32-S3版 | RP2350版 |
|------|-----------|---------|
| リレー制御 | TCA9554 I2C (0x20) | GPIO直接 (GPIO17-24) |
| I2Cバス | SDA=GPIO42, SCL=GPIO41 | SDA=GPIO6, SCL=GPIO7 |
| W5500 SPI | CS=16,INT=12,SCK=15,MISO=14,MOSI=13 | CS=33,RST=25,SCK=34,MOSI=35,MISO=36 |
| RS485 | TX=GPIO17, RX=GPIO18 | TX=GPIO4, RX=GPIO5 |
| DI | GPIO4-11 | GPIO9-16 |
| RGB LED | GPIO38 | GPIO2 |
| ブザー | GPIO46 | GPIO3 |
| Flash/PSRAM | 16MB / 8MB OPI PSRAM | 16MB / SRAM 520KB |
