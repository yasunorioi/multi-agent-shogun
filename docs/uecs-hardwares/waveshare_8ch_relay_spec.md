# Waveshare Industrial 8ch Relay Module 仕様書 + FW設計案

> **Product**: ESP32-S3-ETH-8DI-8RO
> **Author**: ashigaru6 (subtask_1071 / cmd_489)
> **Date**: 2026-04-05
> **Status**: デバイス未購入。公式ドキュメント+コミュニティ情報に基づく先行設計

---

## 1. 製品概要

| 項目 | 値 |
|------|-----|
| 正式名称 | ESP32-S3-ETH-8DI-8RO |
| MCU | ESP32-S3-WROOM-1U-N16R8 (16MB Flash / 8MB PSRAM Octal SPI) |
| リレー | 8ch (1NO+1NC / ch) |
| デジタル入力 | 8ch (フォトカプラ絶縁) |
| 電源 | DC 7~36V (スクリュー端子) / USB-C 5V |
| 寸法 | 175 x 90 x 40 mm |
| 取付 | DINレール |
| 価格 | ~$44.99 (標準版) / ~$49.99 (PoE版) |

### 公式リソース

| リソース | URL |
|---------|-----|
| Wiki | https://www.waveshare.com/wiki/ESP32-S3-ETH-8DI-8RO |
| 製品ページ | https://www.waveshare.com/esp32-s3-eth-8di-8ro.htm |
| ESPHome | https://devices.esphome.io/devices/waveshare-esp32-s3-eth-8di-8ro/ |

### 製品バリエーション

| モデル | Ethernet | 絶縁通信 |
|-------|----------|---------|
| ESP32-S3-ETH-8DI-8RO | 標準RJ45 | RS485 |
| ESP32-S3-POE-ETH-8DI-8RO | PoE (802.3af) | RS485 |
| ESP32-S3-ETH-8DI-8RO-C | 標準RJ45 | CAN |

---

## 2. リレー制御方式

### **I2C GPIO エキスパンダ (TCA9554PWR)** — GPIO直接制御ではない

リレーはESP32-S3のGPIOに直結されていない。TCA9554PWR I2Cエキスパンダ経由で制御する。

- **I2Cバス**: SDA=GPIO42, SCL=GPIO41
- **TCA9554 アドレス**: 0x20

### GPIO → リレーチャンネル対応表

| リレーCH | TCA9554ピン | I2Cビット | 制御方法 |
|:--------:|:-----------:|:---------:|---------|
| Relay 1 | EXIO1 | Bit 0 | Wire.write(0x20, bit0) |
| Relay 2 | EXIO2 | Bit 1 | Wire.write(0x20, bit1) |
| Relay 3 | EXIO3 | Bit 2 | Wire.write(0x20, bit2) |
| Relay 4 | EXIO4 | Bit 3 | Wire.write(0x20, bit3) |
| Relay 5 | EXIO5 | Bit 4 | Wire.write(0x20, bit4) |
| Relay 6 | EXIO6 | Bit 5 | Wire.write(0x20, bit5) |
| Relay 7 | EXIO7 | Bit 6 | Wire.write(0x20, bit6) |
| Relay 8 | EXIO8 | Bit 7 | Wire.write(0x20, bit7) |

### リレースペック

| 項目 | 値 |
|------|-----|
| 接点形式 | 1NO + 1NC / ch |
| 最大開閉 (AC) | 10A @ 250VAC |
| 最大開閉 (DC) | 10A @ 30VDC |
| 絶縁 | フォトカプラ絶縁 |
| 端子 | スクリュー端子 (COM, NO, NC / ch) |

---

## 3. 全GPIOマップ

### デジタル入力 (8ch, フォトカプラ絶縁, アクティブLOW)

| 入力CH | ESP32-S3 GPIO | 入力電圧範囲 |
|:------:|:------------:|:----------:|
| DI1 | GPIO4 | 5~36V |
| DI2 | GPIO5 | 5~36V |
| DI3 | GPIO6 | 5~36V |
| DI4 | GPIO7 | 5~36V |
| DI5 | GPIO8 | 5~36V |
| DI6 | GPIO9 | 5~36V |
| DI7 | GPIO10 | 5~36V |
| DI8 | GPIO11 | 5~36V |

### I2C (TCA9554 + RTC)

| 機能 | GPIO |
|------|:----:|
| SDA | GPIO42 |
| SCL | GPIO41 |

### Ethernet W5500 (SPI)

| 機能 | GPIO |
|------|:----:|
| CS | GPIO16 |
| INT | GPIO12 |
| SCLK | GPIO15 |
| MISO | GPIO14 |
| MOSI | GPIO13 |

### RS485 (絶縁, TVS保護)

| 機能 | GPIO |
|------|:----:|
| TX | GPIO17 |
| RX | GPIO18 |

### TF/SDカード

| 機能 | GPIO |
|------|:----:|
| MISO | GPIO45 |
| MOSI | GPIO47 |
| SCLK | GPIO48 |

### その他ペリフェラル

| 機能 | GPIO |
|------|:----:|
| WS2812 RGB LED | GPIO38 |
| ブザー | GPIO46 |
| BOOTボタン | GPIO0 |

### オンボードRTC

- **PCF85063ATL** (I2C, GPIO41/42共有)
- バッテリーヘッダ付き（タイマー/スケジュール制御用）

---

## 4. 通信インターフェース

| I/F | 詳細 |
|-----|------|
| USB Type-C | 電源供給 + ファームウェア書込み + シリアル通信 |
| WiFi | 2.4GHz 802.11 b/g/n (ESP32-S3内蔵) |
| Bluetooth | Bluetooth 5, BLE (ESP32-S3内蔵) |
| Ethernet | W5500 SPI接続, 10/100Mbps RJ45 |
| RS485 | 絶縁, TVS+サージ/ESD保護, 120Ω終端(ジャンパ切替) |
| Modbus RTU | RS485経由 (デフォルト38400 8E1) |

### LED インジケータ

| LED | 色 | 機能 |
|-----|-----|------|
| PWR | 赤 | 電源 |
| TXD | 緑 | RS485送信 |
| RXD | 青 | RS485受信 |
| RGB | WS2812 | プログラマブル (GPIO38) |

---

## 5. ESP32-S3 Arduino対応状況

### ボード設定 (Arduino IDE)

```
Board Manager URL: https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
Board: "ESP32S3 Dev Module"
USB CDC On Boot: "Enabled"
Flash Size: "16MB (128Mb)"
PSRAM: "OPI PSRAM"
Upload Speed: "921600"
```

### GPIO特殊制約 (strapping pins)

| GPIO | 制約 | 本ボードでの用途 |
|------|------|---------------|
| GPIO0 | BOOTモード選択 | BOOTボタン (問題なし) |
| GPIO45 | VDD_SPI電圧選択 | SDカードMISO (起動後は使用可) |
| GPIO46 | ROM出力制御 | ブザー (起動後は使用可) |
| GPIO48 | — | SDカードSCLK |

**注意**: GPIO45/46はstrapping pinだが、起動後は通常のGPIOとして使用可能。ブート中にSDカードやブザーが接続されていても、内部プルダウンにより正常起動する（Waveshare設計で考慮済み）。

### 必要ライブラリ

| ライブラリ | 用途 | 備考 |
|-----------|------|------|
| Wire | I2C (TCA9554制御) | arduino-esp32標準 |
| PubSubClient | MQTT | 2.8+ |
| ArduinoJson | JSONシリアライズ | 7.x |
| LittleFS | 設定ファイル保存 | ESP32対応版 |

### WiFi + MQTT動作実績

- ESP32-S3のWiFi+PubSubClientは多数の実績あり
- solar_node.ino (Pico 2 W) のコードパターンをほぼそのまま移植可能
- ESP32-S3固有: `WiFi.mode(WIFI_STA)` → `WiFi.begin()` で同一

### Watchdog (ESP32-S3)

Pico 2 Wの `hardware/watchdog.h` は使用不可。ESP32-S3では以下のAPIを使用:

```cpp
#include <esp_task_wdt.h>

// HW WDT初期化 (ESP-IDF API)
esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 30000,  // 30秒
    .idle_core_mask = 0,
    .trigger_panic = true
};
esp_task_wdt_init(&wdt_config);
esp_task_wdt_add(NULL);  // 現タスクを監視対象に追加

// メインループ内でフィード
esp_task_wdt_reset();
```

---

## 6. FW設計案: waveshare_relay_node

### 6.1 アーキテクチャ概要

```
┌─────────────────────────────────────────┐
│ waveshare_relay_node.ino                │
│                                         │
│  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │ WiFi    │  │ MQTT     │  │ HA     │ │
│  │ Manager │  │ Client   │  │ Disc.  │ │
│  └────┬────┘  └────┬─────┘  └───┬────┘ │
│       │            │             │      │
│       └────────────┼─────────────┘      │
│                    │                    │
│  ┌─────────────────┴──────────────────┐ │
│  │ TCA9554 Relay Controller (I2C)     │ │
│  │ addr=0x20, SDA=42, SCL=41         │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ LittleFS │  │ Watchdog │  │ DI    │ │
│  │ Config   │  │ 3-Tier   │  │ 8ch   │ │
│  └──────────┘  └──────────┘  └───────┘ │
└─────────────────────────────────────────┘
```

### 6.2 MQTTトピック設計

mqtt_relay_bridge.py のトピック構造に準拠:

#### Subscribe (QoS=1)

```
agriha/{house_id}/relay/{ch}/set
```

ペイロード:
```json
{"value": 1, "duration_sec": 180, "reason": "irrigation_zone_1"}
```

- `value`: 0=OFF, 1=ON
- `duration_sec`: >0で自動OFF (mqtt_relay_bridge.py互換)
- `reason`: 操作理由 (ログ用)

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

#### デジタル入力状態 (追加トピック)

```
agriha/{house_id}/di/state
```

ペイロード:
```json
{
  "di1": 0, "di2": 1, "di3": 0, "di4": 0,
  "di5": 0, "di6": 0, "di7": 0, "di8": 0,
  "ts": 1740000000
}
```

#### ファームウェアバージョン (retained)

```
agriha/{node_id}/version
```

### 6.3 HA MQTT Auto Discovery

solar_node.ino の `publishHADiscovery()` パターンを踏襲。

#### リレーエンティティ (8ch)

HAの `switch` ドメインで登録:

```json
{
  "name": "Relay CH1",
  "stat_t": "agriha/h2/relay/state",
  "cmd_t": "agriha/h2/relay/1/set",
  "val_tpl": "{{ value_json.ch1 }}",
  "pl_on": "{\"value\":1}",
  "pl_off": "{\"value\":0}",
  "stat_on": 1,
  "stat_off": 0,
  "uniq_id": "waveshare_relay_01_ch1",
  "dev": {
    "identifiers": ["waveshare_relay_01"],
    "name": "Waveshare Relay H2",
    "model": "ESP32-S3-ETH-8DI-8RO",
    "manufacturer": "Waveshare",
    "sw_version": "1.0.0"
  }
}
```

Discovery topic: `homeassistant/switch/waveshare_relay_01_ch1/config`

#### デジタル入力エンティティ (8ch)

HAの `binary_sensor` ドメインで登録:

```json
{
  "name": "DI1",
  "stat_t": "agriha/h2/di/state",
  "val_tpl": "{{ value_json.di1 }}",
  "pl_on": 1,
  "pl_off": 0,
  "uniq_id": "waveshare_relay_01_di1",
  "dev_cla": "power",
  "dev": { ... }
}
```

Discovery topic: `homeassistant/binary_sensor/waveshare_relay_01_di1/config`

### 6.4 Watchdog 3段構え

| Tier | 方式 | タイムアウト | トリガー条件 |
|------|------|:----------:|------------|
| Tier 1 | HW WDT (esp_task_wdt) | 30秒 | loop()がフリーズ |
| Tier 2 | SW WDT (自前実装) | 15秒×3miss=45秒 | メインロジック停止 |
| Tier 3 | 定期リブート | 10分 | 長期安定性 (solar_node.ino踏襲) |

#### Tier 1: HW WDT (ESP32-S3)

```cpp
#include <esp_task_wdt.h>

void setupHwWdt() {
    esp_task_wdt_config_t config = {
        .timeout_ms = 30000,
        .idle_core_mask = 0,
        .trigger_panic = true
    };
    esp_task_wdt_init(&config);
    esp_task_wdt_add(NULL);
}

// loop()内: esp_task_wdt_reset();
```

#### Tier 2: SW WDT (sw_watchdog.h 移植)

sw_watchdog.h の概念を ESP32-S3 に移植。Pico の `repeating_timer` → ESP32 の `Ticker` に置換:

```cpp
#include <Ticker.h>
Ticker swWdtTicker;

volatile bool swWdtFlag = false;
volatile int swWdtMissCount = 0;
const int SWD_CHECK_MS = 5000;
const int SWD_MISS_THRESHOLD = 3;

void swWdtCallback() {
    if (swWdtFlag) {
        swWdtFlag = false;
        swWdtMissCount = 0;
    } else {
        swWdtMissCount++;
        if (swWdtMissCount >= SWD_MISS_THRESHOLD) {
            ESP.restart();
        }
    }
}

void swWdtStart() { swWdtTicker.attach_ms(SWD_CHECK_MS, swWdtCallback); }
void swWdtFeed()  { swWdtFlag = true; }
```

#### Tier 3: 定期リブート

```cpp
const unsigned long REBOOT_INTERVAL = 600000; // 10分 (solar_node.ino踏襲)

// loop()内:
if (millis() >= REBOOT_INTERVAL) {
    rebootWithReason("periodic_10min_reboot");
}
```

### 6.5 LittleFS config.json

```json
{
  "wifi_ssid": "aterm-03e34d-a",
  "wifi_password": "xxxxxxxx",
  "mqtt_broker": "192.168.15.14",
  "mqtt_port": 1883,
  "house_id": "h2",
  "node_id": "waveshare_relay_01",
  "sensor_interval": 10
}
```

- solar_node.ino の `loadConfig()` / `saveConfig()` パターンを流用
- `house_id`: 2棟目ハウスなので `h2`
- `sensor_interval`: DI状態のポーリング間隔(秒)

### 6.6 安全設計

| 項目 | 方針 | 実装 |
|------|------|------|
| 起動時 | **全リレーOFF** | setup()でTCA9554の出力レジスタを0x00に初期化 |
| 通信断 | **フェイルセーフ** | MQTT接続失敗3回連続でリブート (solar_node.ino踏襲) |
| duration超過 | 自動OFF | タイマーで指定秒後にリレーOFF (mqtt_relay_bridge.py互換) |
| I2C障害 | リブート | TCA9554応答なし→リブート |
| 電源断→復帰 | 全OFF | setup()で必ず全OFFから開始 |

#### 起動時全OFF (重要)

```cpp
void initRelaysOff() {
    Wire.beginTransmission(0x20);  // TCA9554
    Wire.write(0x01);              // Output register
    Wire.write(0x00);              // All OFF
    Wire.endTransmission();

    Wire.beginTransmission(0x20);
    Wire.write(0x03);              // Configuration register
    Wire.write(0x00);              // All pins as output
    Wire.endTransmission();
}
```

### 6.7 TCA9554 リレー制御関数

```cpp
const uint8_t TCA9554_ADDR = 0x20;
const uint8_t TCA9554_OUTPUT_REG = 0x01;
const uint8_t TCA9554_CONFIG_REG = 0x03;

uint8_t relayState = 0x00;  // 現在のリレー状態

void setRelay(uint8_t ch, bool on) {
    if (ch < 1 || ch > 8) return;
    uint8_t bit = ch - 1;

    if (on) {
        relayState |= (1 << bit);
    } else {
        relayState &= ~(1 << bit);
    }

    Wire.beginTransmission(TCA9554_ADDR);
    Wire.write(TCA9554_OUTPUT_REG);
    Wire.write(relayState);
    Wire.endTransmission();
}

uint8_t getRelayState() {
    return relayState;
}
```

---

## 7. 既存システムとの対応関係

| 項目 | 1棟目 (UniPi) | 2棟目 (Waveshare) |
|------|-------------|------------------|
| HW | UniPi Neuron + MCP23008 | ESP32-S3 + TCA9554 |
| 制御I/F | I2C (MCP23008) | I2C (TCA9554) |
| MQTT Bridge | mqtt_relay_bridge.py (Python) | waveshare_relay_node.ino (Arduino) |
| Subscribe | agriha/{hid}/relay/{ch}/set | 同一 |
| Publish | agriha/{hid}/relay/state | 同一 |
| ペイロード | {"ch1":0,...,"ts":N} | 同一 + node_id, uptime |
| house_id | h1 (h01) | h2 |
| HA Discovery | なし (Python側) | あり (FW内蔵) |

**互換性**: MQTTトピック・ペイロード構造が同一のため、上位のLLM制御層 (uecs-llm) は house_id の切替のみで両棟を制御可能。

---

## 8. 実装時の注意事項

1. **I2Cアドレス競合**: TCA9554(0x20)とRTC PCF85063(0x51)は別アドレスなので共存可能
2. **W5500 SPI**: 本FWではEthernet未使用(WiFi接続)。将来的にEthernet対応する場合はSPIバス共有に注意
3. **PSRAM**: 8MB搭載だがリレー制御FWでは不要。JSONバッファは通常RAMで十分
4. **OTA**: arduino-esp32のOTA機能は利用可能だが、Pico 2 W同様に初期実装では見送り推奨
5. **RS485/Modbus**: 将来のUECS CCM連携で使用する可能性あり。GPIO17/18を予約
