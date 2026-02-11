# IoT Design Document Generator - Skill Definition

**Skill ID**: `iot-design-doc-generator`
**Category**: Documentation / IoT
**Version**: 1.0.0
**Created**: 2026-02-06
**Invocation**: `/iot-design-doc-generator` or `/iot-doc`

---

## Overview

This skill generates standardized design documents for IoT sensor/actuator nodes. It follows an 8-section structure covering all aspects from hardware to Home Assistant integration.

**Use Cases:**
- New IoT node design documentation
- Standardizing existing project documentation
- Rapid prototyping documentation
- Knowledge transfer and handoff

---

## Input Parameters

When invoking this skill, provide the following information:

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `project_name` | Project name (Japanese/English) | ミニ気象ステーション |
| `project_id` | Short identifier | mini-weather-station |
| `sensors` | List of sensors with models | SCD41, VEML6075 |
| `board` | Main controller board | W5500-EVB-Pico-PoE |

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `actuators` | List of actuators | None |
| `protocol` | Communication protocol | MQTT |
| `house_id` | Greenhouse/house identifier | h1 |
| `language` | Output language | ja |
| `power_source` | Power method | PoE |

---

## Output Format (8 Sections)

The generated document follows this structure:

### Section 1: 概要・目的 (Overview)

```markdown
## 1. 概要・目的

### ユースケース
- [Primary use case]
- [Secondary use case]

### 測定項目
| 項目 | センサー | 用途 |
|------|---------|------|
| {item} | {sensor} | {purpose} |
```

### Section 2: システム構成図 (Architecture)

```markdown
## 2. システム構成図

### 全体構成
```
┌─────────────────────────────────────────┐
│  {project_name}                          │
│  ┌──────────────┐    ┌──────────────┐   │
│  │  {sensor_1}  │──▶ │  {board}     │   │
│  │  {sensor_2}  │    │              │   │
│  └──────────────┘    └──────┬───────┘   │
└─────────────────────────────┼───────────┘
                              │ {protocol}
                              ▼
                    ┌─────────────────┐
                    │  MQTT Broker    │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │  Home Assistant │
                    └─────────────────┘
```

### データフロー
[Sensor → MCU → MQTT → HA flow diagram]
```

### Section 3: ハードウェア (Hardware)

```markdown
## 3. ハードウェア

### 部品リスト
| カテゴリ | 品名 | 型番 | 入手先 | 単価 | 備考 |
|---------|------|------|--------|------|------|
| メインボード | {board} | {model} | {source} | ¥{price} | {notes} |
| センサー | {sensor} | {model} | {source} | ¥{price} | {notes} |

**概算コスト**: ¥{total}

### 配線・接続
```
{board}
├── I2C0 SDA（GP4）
│   ├── {sensor_1}（{i2c_addr_1}）
│   └── {sensor_2}（{i2c_addr_2}）
├── I2C0 SCL（GP5）
└── Ethernet PoE
```
```

### Section 4: ソフトウェア (Software)

```markdown
## 4. ソフトウェア

### ファームウェア概要（CircuitPython）

#### 主要ライブラリ
- `adafruit_wiznet5k`: Ethernet通信
- `adafruit_minimqtt`: MQTTクライアント
- `adafruit_{sensor_lib}`: センサードライバ

#### 処理フロー
```python
# メインループ疑似コード
while True:
    # センサー読み取り
    data = read_sensors()

    # MQTT送信
    mqtt_client.publish(TOPIC_SENSOR, json.dumps(data))

    # 間隔待機
    time.sleep(INTERVAL)
```

### サンプルコード
[Full code example with comments]
```

### Section 5: MQTTトピック設計 (MQTT Topics)

```markdown
## 5. MQTTトピック設計

### トピック構造
```
greenhouse/
├── {house_id}/
│   ├── sensors/
│   │   └── {sensor_type}     # センサーデータ
│   ├── actuators/
│   │   └── {actuator_type}/
│   │       ├── set           # 制御コマンド
│   │       └── state         # 状態フィードバック
│   └── node/
│       └── {node_id}/
│           └── status        # ノード状態
```

### ペイロード例
```json
{
  "{measurement_1}": {value},
  "{measurement_2}": {value},
  "timestamp": "{iso_timestamp}"
}
```
```

### Section 6: Home Assistant連携 (HA Integration)

```markdown
## 6. Home Assistant連携

### MQTT Discovery
```python
discovery_config = {
    "name": "{friendly_name}",
    "state_topic": "{topic}",
    "value_template": "{{ value_json.{field} }}",
    "unit_of_measurement": "{unit}",
    "device_class": "{class}",
    "unique_id": "{unique_id}",
    "device": {
        "identifiers": ["{device_id}"],
        "name": "{device_name}",
        "manufacturer": "DIY"
    }
}
```

### 自動化例
```yaml
automation:
  - alias: "{automation_name}"
    trigger:
      - platform: numeric_state
        entity_id: sensor.{entity}
        above: {threshold}
    action:
      - service: notify.{notifier}
        data:
          message: "{alert_message}"
```

### ダッシュボードカード
```yaml
type: entities
title: {project_name}
entities:
  - entity: sensor.{entity_1}
  - entity: sensor.{entity_2}
```
```

### Section 7: 実装手順 (Implementation)

```markdown
## 7. 実装手順

### Phase 1: ハードウェア組立
1. {board}の準備
2. センサー接続
3. 筐体組み込み（必要な場合）

### Phase 2: ファームウェアセットアップ
1. CircuitPython書き込み
2. ライブラリコピー
3. code.py配置・設定

### Phase 3: MQTT設定
1. ブローカー接続確認
2. トピック動作確認

### Phase 4: Home Assistant連携
1. MQTT Discovery確認
2. エンティティ命名
3. ダッシュボード追加

### Phase 5: 動作確認
1. センサー値確認
2. 通知テスト
3. 長期動作確認
```

### Section 8: 将来拡張案 (Future Enhancements)

```markdown
## 8. 将来拡張案

### {enhancement_1}
[Description and implementation approach]

### {enhancement_2}
[Description and implementation approach]

### 参考リンク
- [{reference_1}]({url_1})
- [{reference_2}]({url_2})
```

---

## Template Generation Rules

### Sensor-Specific Templates

| Sensor Type | Default Library | I2C Address | Measurements |
|-------------|-----------------|-------------|--------------|
| SCD41 | adafruit_scd4x | 0x62 | CO2, temp, humidity |
| SHT40 | adafruit_sht4x | 0x44 | temp, humidity |
| BMP280 | adafruit_bmp280 | 0x76/0x77 | pressure, temp |
| VEML6075 | adafruit_veml6075 | 0x10 | UV index |
| BH1750 | adafruit_bh1750 | 0x23 | lux |

### Board-Specific Templates

| Board | Firmware | Network | Power | Features |
|-------|----------|---------|-------|----------|
| W5500-EVB-Pico-PoE | CircuitPython | Ethernet | PoE | Industrial |
| Pico 2 W | CircuitPython | WiFi | USB/Battery | Compact |
| ESP32-CAM | Arduino | WiFi | USB | Camera |

### MQTT Topic Patterns

```
# Sensor data
greenhouse/{house}/sensors/{sensor_type}

# Actuator control
greenhouse/{house}/actuators/{actuator_type}/set
greenhouse/{house}/actuators/{actuator_type}/state

# Node status
greenhouse/{house}/node/{node_id}/status
```

---

## Usage Examples

### Example 1: Basic Sensor Node

```
User: /iot-design-doc-generator
      プロジェクト: 温湿度モニター
      センサー: SHT40
      ボード: W5500-EVB-Pico-PoE
```

**Output**: Complete design document with:
- Temperature/humidity monitoring overview
- Simple architecture diagram
- SHT40 + W5500-EVB-Pico-PoE hardware list
- CircuitPython firmware with adafruit_sht4x
- MQTT topics for temp/humidity
- HA sensor entities
- 5-phase implementation steps
- Future enhancements (alerts, logging)

### Example 2: Multi-Sensor Node

```
User: /iot-design-doc-generator
      プロジェクト: ハウス環境モニター
      センサー: SCD41, BH1750, VEML6075
      ボード: W5500-EVB-Pico-PoE
      ハウスID: h2
```

**Output**: Complete design document with:
- Multi-parameter monitoring overview
- Complex architecture with I2C hub consideration
- Multiple sensor hardware list with I2C addresses
- Firmware handling multiple sensors
- MQTT topics for CO2, temp, humidity, lux, UV
- HA dashboard with multiple cards
- I2C scan verification in implementation
- Future: threshold alerts, trend analysis

### Example 3: Actuator Node

```
User: /iot-design-doc-generator
      プロジェクト: 換気制御
      センサー: SHT40
      アクチュエータ: 換気扇リレー
      ボード: Pico 2 W
```

**Output**: Complete design document with:
- Ventilation control overview
- Sensor + actuator architecture
- Relay wiring and flyback diode
- Control logic (threshold-based)
- MQTT topics for both sensor and actuator
- HA switch entity + automation
- Safety considerations
- Future: PID control, scheduling

---

## Document Quality Checklist

The generated document must include:

- [ ] Clear project purpose and use cases
- [ ] ASCII architecture diagram
- [ ] Complete parts list with prices
- [ ] Wiring diagram
- [ ] Working code example
- [ ] MQTT topic structure
- [ ] HA configuration snippets
- [ ] Step-by-step implementation
- [ ] At least 2 future enhancement ideas
- [ ] References section

---

## Related Skills

- `sensor-driver-generator`: Generate sensor driver code
- `pico-wifi-mqtt-template`: WiFi MQTT firmware template
- `homeassistant-agri-starter`: HA integration patterns
- `agri-iot-board-design-template`: PCB design guide

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-06 | Initial release |

---

**Skill Author**: Arsprout Analysis Team
**License**: MIT
