# ADC Sensor Design Template - Skill Definition

**Skill ID**: `adc-sensor-design-template`
**Category**: Hardware Design / Sensor Integration
**Version**: 2.0.0
**Created**: 2026-02-04
**Updated**: 2026-02-05
**Platform**: CircuitPython (RP2040/RP2350)

---

## Overview

This skill provides a structured template and workflow for designing analog sensor integrations using ADC (Analog-to-Digital Converter) on CircuitPython platforms. It covers voltage-to-physical-quantity conversion formulas, calibration procedures, and implementation patterns.

---

## Use Cases

- **Water Pressure Sensors**: Pressure transducers (0-5V, 4-20mA) for irrigation monitoring
- **Solar Radiation Sensors**: Pyranometers or photodiodes for light intensity measurement
- **Soil Moisture Sensors**: Capacitive sensors for soil water content
- **EC (Electrical Conductivity) Sensors**: For nutrient solution monitoring
- **pH Sensors**: For water quality monitoring
- **Custom Analog Sensors**: Any sensor with 0-3.3V output

---

## Skill Input

When invoked, this skill requires:

1. **Sensor Specification**
   - Sensor model/type
   - Output voltage range (e.g., 0-2V, 0.5-2.5V)
   - Measurement range (e.g., 0-100 kPa, pH 0-14)
   - Power requirements (3.3V or 5V)

2. **Platform Details**
   - Board type (e.g., W5500-EVB-Pico-PoE, Pico 2 W)
   - ADC pin assignment (GP26/ADC0, GP27/ADC1, GP28/ADC2)
   - ADC resolution (default: 16-bit = 0-65535)

3. **Integration Context**
   - Existing firmware (if any)
   - MQTT topic structure
   - Home Assistant entity name

---

## Skill Output

The skill generates:

1. **Voltage-to-Physical-Quantity Conversion Formula**
   - Mathematical equation
   - CircuitPython code implementation
   - Example calculations

2. **ADC Reading Code**
   - Initialization code
   - Sampling and averaging logic
   - Error handling

3. **Calibration Procedure**
   - Step-by-step calibration guide
   - Reference point requirements
   - Calibration value storage (settings.toml)

4. **Documentation**
   - Wiring diagram (ASCII art or description)
   - Pin assignment table
   - Notes on ADC input protection

---

## Design Template

### 1. ADC Basics (CircuitPython / RP2040 / RP2350)

```python
import board
import analogio

# ADC pin mapping
ADC_PINS = {
    "ADC0": board.GP26,
    "ADC1": board.GP27,
    "ADC2": board.GP28,
}

# ADC resolution
ADC_MAX = 65535  # 16-bit ADC (0-65535)
V_REF = 3.3      # Reference voltage (volts)

# Convert ADC reading to voltage
def adc_to_voltage(adc_value):
    """
    Convert ADC reading to voltage.

    Args:
        adc_value: Raw ADC value (0-65535)

    Returns:
        float: Voltage (0-3.3V)
    """
    return (adc_value / ADC_MAX) * V_REF
```

### 2. Sensor-Specific Conversion Formulas

#### Example 1: EC Sensor (0-2V → 0-20 mS/cm)

```python
# Sensor specification
EC_OUTPUT_RANGE = (0.0, 2.0)      # Output voltage range (V)
EC_MEASUREMENT_RANGE = (0.0, 20.0)  # EC range (mS/cm)

def ec_sensor_read(adc_pin):
    """
    Read EC sensor and convert to mS/cm.

    Formula:
        EC (mS/cm) = (ADC_voltage / V_max) × EC_max

    Args:
        adc_pin: ADC pin object (e.g., board.GP26)

    Returns:
        float: EC value (mS/cm)
    """
    adc = analogio.AnalogIn(adc_pin)
    adc_value = adc.value
    voltage = adc_to_voltage(adc_value)

    # Linear conversion
    v_min, v_max = EC_OUTPUT_RANGE
    ec_min, ec_max = EC_MEASUREMENT_RANGE

    ec = ((voltage - v_min) / (v_max - v_min)) * (ec_max - ec_min) + ec_min

    return max(0.0, ec)  # Clamp to non-negative
```

#### Example 2: pH Sensor (0.5-2.5V → pH 0-14)

```python
# Sensor specification
PH_OUTPUT_RANGE = (0.5, 2.5)      # Output voltage range (V)
PH_MEASUREMENT_RANGE = (0.0, 14.0)  # pH range

def ph_sensor_read(adc_pin):
    """
    Read pH sensor and convert to pH value.

    Formula:
        pH = ((ADC_voltage - V_offset) / V_range) × pH_range

    Args:
        adc_pin: ADC pin object (e.g., board.GP27)

    Returns:
        float: pH value (0-14)
    """
    adc = analogio.AnalogIn(adc_pin)
    adc_value = adc.value
    voltage = adc_to_voltage(adc_value)

    # Linear conversion with offset
    v_min, v_max = PH_OUTPUT_RANGE
    ph_min, ph_max = PH_MEASUREMENT_RANGE

    ph = ((voltage - v_min) / (v_max - v_min)) * (ph_max - ph_min) + ph_min

    return max(0.0, min(14.0, ph))  # Clamp to 0-14
```

#### Example 3: Water Pressure Sensor (0-3V → 0-100 kPa)

```python
# Sensor specification
PRESSURE_OUTPUT_RANGE = (0.0, 3.0)      # Output voltage range (V)
PRESSURE_MEASUREMENT_RANGE = (0.0, 100.0)  # Pressure range (kPa)

def pressure_sensor_read(adc_pin, calibration_offset=0.0, calibration_scale=1.0):
    """
    Read water pressure sensor and convert to kPa.

    Formula:
        Pressure (kPa) = ((ADC_voltage / V_max) × P_max) × scale + offset

    Args:
        adc_pin: ADC pin object (e.g., board.GP26)
        calibration_offset: Offset correction (kPa)
        calibration_scale: Scale correction factor

    Returns:
        float: Pressure value (kPa)
    """
    adc = analogio.AnalogIn(adc_pin)
    adc_value = adc.value
    voltage = adc_to_voltage(adc_value)

    # Linear conversion
    v_min, v_max = PRESSURE_OUTPUT_RANGE
    p_min, p_max = PRESSURE_MEASUREMENT_RANGE

    pressure = ((voltage - v_min) / (v_max - v_min)) * (p_max - p_min) + p_min

    # Apply calibration
    pressure = pressure * calibration_scale + calibration_offset

    return max(0.0, pressure)  # Clamp to non-negative
```

### 3. ADC Sampling Best Practices

```python
import time

def adc_read_averaged(adc_pin, samples=10, delay_ms=10):
    """
    Read ADC with averaging to reduce noise.

    Args:
        adc_pin: ADC pin object
        samples: Number of samples to average
        delay_ms: Delay between samples (milliseconds)

    Returns:
        float: Averaged ADC voltage
    """
    adc = analogio.AnalogIn(adc_pin)
    total = 0

    for _ in range(samples):
        total += adc.value
        time.sleep(delay_ms / 1000.0)

    avg_value = total / samples
    return adc_to_voltage(avg_value)
```

### 4. settings.toml Configuration

```toml
# ADC Sensor Configuration

[sensors.adc.ec_sensor]
enabled = true
pin = "ADC0"  # GP26
v_min = 0.0
v_max = 2.0
ec_min = 0.0
ec_max = 20.0
calibration_offset = 0.0
calibration_scale = 1.0

[sensors.adc.ph_sensor]
enabled = true
pin = "ADC1"  # GP27
v_min = 0.5
v_max = 2.5
ph_min = 0.0
ph_max = 14.0
calibration_offset = 0.0

[sensors.adc.pressure_sensor]
enabled = true
pin = "ADC2"  # GP28
v_min = 0.0
v_max = 3.0
pressure_min = 0.0
pressure_max = 100.0
calibration_offset = 0.0
calibration_scale = 1.0
```

---

## Calibration Procedure

### Two-Point Calibration

1. **Preparation**
   - Prepare known reference solutions (e.g., pH 4.0 and pH 7.0)
   - Or use calibrated reference sensor for comparison

2. **Collect Reference Data**
   ```
   Reference Point 1:
   - Known value: 4.0 pH
   - Measured voltage: 1.0 V

   Reference Point 2:
   - Known value: 7.0 pH
   - Measured voltage: 1.75 V
   ```

3. **Calculate Calibration Coefficients**
   ```python
   # Given:
   v1, ph1 = 1.0, 4.0
   v2, ph2 = 1.75, 7.0

   # Calculate slope and offset
   slope = (ph2 - ph1) / (v2 - v1)
   offset = ph1 - slope * v1

   # Calibrated formula
   def calibrated_ph(voltage):
       return slope * voltage + offset
   ```

4. **Update settings.toml**
   ```toml
   [sensors.adc.ph_sensor]
   v_min = 1.0   # Voltage at pH 4.0
   v_max = 1.75  # Voltage at pH 7.0
   ph_min = 4.0
   ph_max = 7.0
   ```

---

## Wiring Guidelines

### ADC Input Protection

```
Sensor Output ──┬──[ 1kΩ ]──┬── ADC Pin (GP26/27/28)
                │            │
                │          ┌─┴─┐
                │          │3.3V│ TVS Diode or Zener
                │          └───┘
                │            │
                └───────────GND
```

### Pin Assignment Table

| ADC Pin | GPIO | Recommended Use | Max Voltage |
|---------|------|-----------------|-------------|
| ADC0    | GP26 | Primary analog sensor | 3.3V |
| ADC1    | GP27 | Secondary analog sensor | 3.3V |
| ADC2    | GP28 | Tertiary analog sensor | 3.3V |

**WARNING**: Exceeding 3.3V on ADC inputs will damage the RP2040/RP2350 chip!

---

## MQTT Integration

### Topic Structure

```
greenhouse/{house_id}/drainage/ec
greenhouse/{house_id}/drainage/ph
greenhouse/{house_id}/water/pressure
```

### Payload Example

```json
{
  "timestamp": "2026-02-05T10:30:00",
  "ec_ms_cm": 12.5,
  "adc_voltage": 1.25,
  "calibration_applied": true
}
```

---

## Home Assistant MQTT Discovery

```python
def publish_ha_discovery_adc_sensor(mqtt_client, house_id, sensor_name, unit):
    """
    Publish Home Assistant MQTT Discovery for ADC sensor.

    Args:
        mqtt_client: MQTT client object
        house_id: House identifier (e.g., "h1")
        sensor_name: Sensor name (e.g., "ec", "ph", "pressure")
        unit: Unit of measurement (e.g., "mS/cm", "pH", "kPa")
    """
    config_topic = f"homeassistant/sensor/{house_id}_{sensor_name}/config"
    state_topic = f"greenhouse/{house_id}/sensor/{sensor_name}"

    config = {
        "name": f"{house_id.upper()} {sensor_name.upper()}",
        "state_topic": state_topic,
        "unit_of_measurement": unit,
        "value_template": "{{ value_json.value }}",
        "unique_id": f"{house_id}_{sensor_name}",
        "device": {
            "identifiers": [f"{house_id}_drainage_node"],
            "name": f"{house_id.upper()} Drainage Node",
            "model": "W5500-EVB-Pico-PoE",
            "manufacturer": "Arsprout"
        }
    }

    import json
    mqtt_client.publish(config_topic, json.dumps(config), retain=True)
```

---

## Common Pitfalls and Solutions

### 1. ADC Noise

**Problem**: Readings fluctuate wildly

**Solutions**:
- Use averaging (10-20 samples)
- Add low-pass filter (capacitor) on sensor output
- Shorten wiring between sensor and ADC pin
- Use shielded cable for long runs

### 2. Voltage Range Mismatch

**Problem**: Sensor outputs 0-5V but ADC expects 0-3.3V

**Solutions**:
- Use voltage divider: `R1=1.7kΩ, R2=3.3kΩ` (5V → 3.3V)
- Use level shifter IC
- Check if sensor has adjustable output range

### 3. Zero Offset Drift

**Problem**: Sensor reads non-zero when no input

**Solutions**:
- Implement calibration_offset in settings.toml
- Perform two-point calibration regularly
- Use sensor with built-in temperature compensation

### 4. Non-Linear Response

**Problem**: Sensor output is not linear

**Solutions**:
- Use lookup table (LUT) for conversion
- Polynomial curve fitting
- Piecewise linear approximation

---

## Example: Complete ADC Sensor Module

```python
# lib/adc_sensors.py

import board
import analogio
import time
from collections import deque

class ADCSensor:
    """Base class for ADC-based sensors."""

    def __init__(self, adc_pin, v_min, v_max, unit_min, unit_max, unit_name):
        self.adc = analogio.AnalogIn(adc_pin)
        self.v_min = v_min
        self.v_max = v_max
        self.unit_min = unit_min
        self.unit_max = unit_max
        self.unit_name = unit_name
        self.calibration_offset = 0.0
        self.calibration_scale = 1.0
        self.samples = deque(maxlen=10)

    def read_voltage(self):
        """Read ADC and convert to voltage."""
        adc_value = self.adc.value
        return (adc_value / 65535.0) * 3.3

    def read_averaged(self, n=10):
        """Read ADC with averaging."""
        total = 0
        for _ in range(n):
            total += self.read_voltage()
            time.sleep(0.01)
        return total / n

    def convert_to_unit(self, voltage):
        """Convert voltage to physical unit."""
        # Linear conversion
        normalized = (voltage - self.v_min) / (self.v_max - self.v_min)
        value = normalized * (self.unit_max - self.unit_min) + self.unit_min

        # Apply calibration
        value = value * self.calibration_scale + self.calibration_offset

        return value

    def read(self):
        """Read sensor and return calibrated value."""
        voltage = self.read_averaged()
        return self.convert_to_unit(voltage)


# Usage
ec_sensor = ADCSensor(
    adc_pin=board.GP26,
    v_min=0.0, v_max=2.0,
    unit_min=0.0, unit_max=20.0,
    unit_name="mS/cm"
)

ec_value = ec_sensor.read()
print(f"EC: {ec_value:.2f} {ec_sensor.unit_name}")
```

---

## Skill Invocation Example

**User Request**:
> "Add a soil moisture sensor (capacitive, 0-3V output, 0-100% range) to ADC1 with MQTT publishing."

**Skill Output**:

1. Conversion formula code
2. settings.toml configuration
3. MQTT topic: `greenhouse/h1/soil/moisture`
4. HA Discovery configuration
5. Wiring diagram for GP27
6. Calibration procedure (dry soil = 0%, saturated soil = 100%)

---

## References

- [RP2040 ADC Specification](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf) - Section 4.9
- [CircuitPython analogio](https://docs.circuitpython.org/en/latest/shared-bindings/analogio/)
- [ADC Noise Reduction Techniques](https://www.analog.com/en/technical-articles/reducing-noise-in-analog-to-digital-converter-applications.html)

---

**Skill Author**: Arsprout Analysis Team
**Last Updated**: 2026-02-05
**License**: MIT

---

## サンプル出力 (Legacy)

```markdown
# 水圧センサー設計書

## 1. センサー仕様

| 項目 | 値 |
|------|-----|
| センサー種類 | 水圧センサー |
| 型番 | (ユーザー指定または汎用) |
| 測定範囲 | 0 - 1.0 MPa |
| 出力形式 | 0.5V - 4.5V (ratiometric) |
| 電源電圧 | 5V DC |
| 精度 | ±0.5% FS |

## 2. 電気仕様

### 出力特性

```
出力電圧 = 0.5V + (圧力 / 最大圧力) × 4.0V
```

| 圧力 (MPa) | 出力電圧 (V) |
|-----------|-------------|
| 0.0 | 0.5 |
| 0.25 | 1.5 |
| 0.50 | 2.5 |
| 0.75 | 3.5 |
| 1.00 | 4.5 |

## 3. ADC接続設計

### マイコン: Raspberry Pi Pico

| 項目 | 値 |
|------|-----|
| ADC分解能 | 12bit (0-4095) |
| 基準電圧 | 3.3V |
| 入力範囲 | 0 - 3.3V |

### 電圧分圧回路（5V → 3.3V変換）

```
センサー出力 (0.5-4.5V)
    │
    ├──[R1: 10kΩ]──┬── ADC入力 (0.33-2.97V)
    │              │
    └──[R2: 20kΩ]──┴── GND
```

分圧比: R2 / (R1 + R2) = 20k / 30k = 0.66

### 変換後の電圧範囲

| 圧力 (MPa) | センサー出力 (V) | ADC入力 (V) | ADC値 |
|-----------|-----------------|-------------|-------|
| 0.0 | 0.5 | 0.33 | 409 |
| 1.0 | 4.5 | 2.97 | 3686 |

## 4. 校正式

### ADC値 → 圧力変換

```python
def adc_to_pressure(adc_value, adc_max=4095, vref=3.3):
    """
    ADC値を圧力(MPa)に変換

    Args:
        adc_value: ADC読み取り値 (0-4095)
        adc_max: ADC最大値
        vref: 基準電圧

    Returns:
        圧力 (MPa)
    """
    # ADC値 → 電圧
    voltage_adc = (adc_value / adc_max) * vref

    # 分圧補正（逆変換）
    voltage_sensor = voltage_adc / 0.66

    # 電圧 → 圧力
    # V = 0.5 + (P / 1.0) * 4.0
    # P = (V - 0.5) / 4.0
    pressure = (voltage_sensor - 0.5) / 4.0

    # 範囲制限
    return max(0.0, min(1.0, pressure))
```

### 校正定数

```python
# 校正パラメータ
VOLTAGE_OFFSET = 0.5      # ゼロ点電圧 (V)
VOLTAGE_SPAN = 4.0        # スパン電圧 (V)
PRESSURE_MAX = 1.0        # 最大圧力 (MPa)
DIVIDER_RATIO = 0.66      # 分圧比
```

## 5. 実装コード例

### CircuitPython版

```python
import board
import analogio
import time

# ADC設定
adc = analogio.AnalogIn(board.A0)

# 校正定数
VOLTAGE_OFFSET = 0.5
VOLTAGE_SPAN = 4.0
PRESSURE_MAX = 1.0
DIVIDER_RATIO = 0.66
VREF = 3.3

def read_pressure():
    """圧力を読み取り (MPa)"""
    # ADC読み取り（16bit）
    adc_value = adc.value

    # 電圧変換
    voltage_adc = (adc_value / 65535) * VREF
    voltage_sensor = voltage_adc / DIVIDER_RATIO

    # 圧力変換
    pressure = (voltage_sensor - VOLTAGE_OFFSET) / VOLTAGE_SPAN * PRESSURE_MAX

    return max(0.0, min(PRESSURE_MAX, pressure))

# メインループ
while True:
    p = read_pressure()
    print(f"Pressure: {p:.3f} MPa")
    time.sleep(1)
```

## 6. 配線図

```
[5V電源]──────────────────┬─── VCC (センサー)
                         │
[水圧センサー]            │
  │                      │
  ├─── Signal ───[10kΩ]──┼───┬─── GP26 (ADC0)
  │                      │   │
  └─── GND ──────────────┴───┴─── GND
                             │
                         [20kΩ]
                             │
                            GND

※ 5V電源はPicoのVSYS or 外部電源
```

## 7. 注意事項

1. **電圧レベル**: センサー出力が3.3Vを超える場合は必ず分圧
2. **ノイズ対策**: ADC入力にコンデンサ(0.1μF)追加推奨
3. **校正**: 実機で2点校正（ゼロ点、スパン）推奨
4. **保護**: 過電圧保護にツェナーダイオード追加検討
```

## 対応センサー種類

| センサー種類 | 典型的な出力 | 備考 |
|-------------|-------------|------|
| 水圧センサー | 0.5-4.5V | 5V電源、ratiometric |
| 土壌水分センサー | 0-3V | 抵抗式、容量式 |
| 日射センサー | 0-1V または 4-20mA | 高精度品は電流出力 |
| 温度センサー (サーミスタ) | 抵抗値変化 | 分圧回路で電圧変換 |
| pH センサー | mV出力 | オペアンプ増幅必要 |

## 使用例

```
User: Pico W で水圧センサー(0-1MPa, 0.5-4.5V出力)を使いたい
Assistant: [このスキルを使用してセンサー設計書を生成]
```
