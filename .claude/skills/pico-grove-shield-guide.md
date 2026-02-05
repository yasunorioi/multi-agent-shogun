# Pico Grove Shield 接続ガイド

Raspberry Pi Pico用Grove Shieldの接続ガイド。センサー接続の標準化と、W5500-EVB-Pico-PoEとのスタック構成を解説。

## 概要

Grove Shieldを使用することで、はんだ付けなしでセンサーを接続できる。本スキルは以下を提供：

- Grove Shield のピン配置と仕様
- 各種センサーの接続例（I2C/UART/ADC）
- W5500-EVB-Pico-PoE とのスタック構成
- M5Stack Unitシリーズとの接続
- トラブルシューティング

## 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- Pico に Grove センサーを接続したい
- Grove Shield の使い方を知りたい
- W5500-EVB-Pico-PoE に Grove センサーを追加したい
- M5Stack Unit を Pico で使いたい
- I2C/UART/ADC センサーの接続方法

## 1. 対応Grove Shieldの種類

### Seeed Studio Grove Shield for Pi Pico v1.0

| 項目 | 仕様 |
|------|------|
| サイズ | 56mm × 56mm |
| Grove ポート | I2C×2, UART×2, Digital×3, Analog×3 |
| 追加機能 | SPI×1, SWD Debug |
| 電源切替 | 3.3V / 5V スイッチ |

### 購入先

| ショップ | URL | 備考 |
|---------|-----|------|
| 秋月電子 | https://akizukidenshi.com/ | 「Grove Shield Pico」で検索 |
| スイッチサイエンス | https://www.switch-science.com/ | 在庫あり |
| マルツ | https://www.marutsu.co.jp/ | 取り寄せ |
| Seeed Studio | https://www.seeedstudio.com/Grove-Shield-for-Pi-Pico-v1-0-p-4846.html | 本家 |

### 入手性問題と対策

#### 現状の問題

| 販売店 | 状況 |
|-------|------|
| 秋月電子 | **販売終了** |
| スイッチサイエンス | 在庫限り（要確認） |
| Seeed Studio | 在庫あり（海外発送） |

Grove Shield for Pi Pico は国内での入手性が悪化している。

#### 現在の開発方針

```
【開発フェーズ】
  └── 手持ち在庫で開発継続
      └── 既存在庫を活用してプロトタイプ開発
```

#### 量産フェーズの対策

```
【量産フェーズ】
  └── JLCPCBで自作基板に移行
      ├── Grove Shield代替基板として設計
      ├── 必要なGroveコネクタのみ実装
      │   ├── I2C × 2ポート
      │   ├── ADC × 2ポート
      │   └── 電源切替スイッチ
      └── コスト削減も実現
```

**自作基板のメリット**:
- 入手性の問題を解消
- 必要最小限の機能に絞れる
- 大量発注でコスト削減
- カスタム配置が可能

**参考**: JLCPCBでの基板発注は5枚$2〜程度から可能。

## 2. ピン配置表

### Raspberry Pi Pico GPIO 配置

```
          ┌─────────────────────┐
     GP0 ─┤ 1               40 ├─ VBUS
     GP1 ─┤ 2               39 ├─ VSYS
     GND ─┤ 3               38 ├─ GND
     GP2 ─┤ 4               37 ├─ 3V3_EN
     GP3 ─┤ 5               36 ├─ 3V3(OUT)
     GP4 ─┤ 6  [I2C0 SDA]   35 ├─ ADC_VREF
     GP5 ─┤ 7  [I2C0 SCL]   34 ├─ GP28 [ADC2]
     GND ─┤ 8               33 ├─ GND
     GP6 ─┤ 9  [I2C1 SDA]   32 ├─ GP27 [ADC1]
     GP7 ─┤ 10 [I2C1 SCL]   31 ├─ GP26 [ADC0]
     GP8 ─┤ 11              30 ├─ RUN
     GP9 ─┤ 12              29 ├─ GP22
     GND ─┤ 13              28 ├─ GND
    GP10 ─┤ 14              27 ├─ GP21
    GP11 ─┤ 15              26 ├─ GP20
    GP12 ─┤ 16              25 ├─ GP19
    GP13 ─┤ 17              24 ├─ GP18
     GND ─┤ 18              23 ├─ GND
    GP14 ─┤ 19              22 ├─ GP17
    GP15 ─┤ 20              21 ├─ GP16
          └─────────────────────┘
```

### Grove Shield ポートマッピング

| ポート種別 | Grove端子 | GPIO | 用途 |
|-----------|----------|------|------|
| **I2C0** | I2C | GP4 (SDA), GP5 (SCL) | センサー接続メイン |
| **I2C1** | I2C | GP6 (SDA), GP7 (SCL) | センサー接続サブ |
| **UART0** | UART | GP0 (TX), GP1 (RX) | シリアル通信 |
| **UART1** | UART | GP8 (TX), GP9 (RX) | シリアル通信 |
| **Analog0** | A0 | GP26 (ADC0) | アナログ入力 |
| **Analog1** | A1 | GP27 (ADC1) | アナログ入力 |
| **Analog2** | A2 | GP28 (ADC2) | アナログ入力 |
| **Digital** | D16/D18/D20 | GP16, GP18, GP20 | デジタルI/O |

### Grove コネクタ配線色

| Pin | 色 | 機能 |
|-----|-----|------|
| 1 | 黄 | Signal 1 (SDA/RX/A0/D0) |
| 2 | 白 | Signal 2 (SCL/TX/A1/D1) |
| 3 | 赤 | VCC (3.3V または 5V) |
| 4 | 黒 | GND |

### Grove ケーブル長さバリエーション

#### M5Stack GROVE互換ケーブル（スイッチサイエンス）

長距離I2C配線に最適。P82B96バッファ併用でさらに延長可能。

| 長さ | 型番 | 価格 | URL |
|------|------|------|-----|
| 5cm | A034-A | - | https://www.switch-science.com/products/5212 |
| 10cm | A034-B | - | https://www.switch-science.com/products/5213 |
| 20cm | A034-C | - | https://www.switch-science.com/products/5214 |
| 50cm | A034-E | - | https://www.switch-science.com/products/5215 |
| **100cm** | **A034-D** | **¥550** | **https://www.switch-science.com/products/5216** |
| **200cm** | A034-F | - | https://www.switch-science.com/products/5217 |

**注意**: 長距離（1m以上）でI2C通信する場合は、P82B96等のI2Cバスバッファ併用を推奨。

## 3. I2Cセンサー接続例

### 対応センサーとアドレス

| センサー | 型番 | I2Cアドレス | 測定項目 |
|---------|------|-------------|---------|
| 温湿度 | SHT40 | 0x44 | 温度、湿度 |
| 温湿度 | SHT30 | 0x44 (0x45) | 温度、湿度 |
| CO2 | SCD41 | 0x62 | CO2、温度、湿度 |
| 気圧 | BMP280 | 0x76 (0x77) | 気圧、温度 |
| 気圧 | QMP6988 | 0x70 | 気圧、温度 |
| TVOC | SGP30 | 0x58 | TVOC、eCO2 |

### CircuitPython 接続コード（SHT40）

```python
import time
import board
import busio
import adafruit_sht4x

# I2C初期化（GP4=SDA, GP5=SCL）
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# SHT40センサー初期化
sht = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION

while True:
    temperature, humidity = sht.measurements
    print(f"Temperature: {temperature:.1f}°C")
    print(f"Humidity: {humidity:.1f}%")
    time.sleep(2)
```

### CircuitPython 接続コード（SCD41）

```python
import time
import board
import busio
import adafruit_scd4x

# I2C初期化
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# SCD41センサー初期化
scd = adafruit_scd4x.SCD4X(i2c)
scd.start_periodic_measurement()

while True:
    if scd.data_ready:
        print(f"CO2: {scd.CO2} ppm")
        print(f"Temperature: {scd.temperature:.1f}°C")
        print(f"Humidity: {scd.relative_humidity:.1f}%")
    time.sleep(5)
```

### 複数I2Cセンサーの同時使用

```python
import board
import busio
import adafruit_sht4x
import adafruit_bmp280

# I2Cバスは共有可能（アドレスが異なれば）
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# 複数センサーを同じI2Cバスに接続
sht = adafruit_sht4x.SHT4x(i2c)       # 0x44
bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)  # 0x76

# 両方のセンサーから読み取り
temp, humid = sht.measurements
pressure = bmp.pressure
```

## 4. UARTセンサー接続例

### GPSモジュール接続

```python
import board
import busio
import adafruit_gps

# UART初期化（GP0=TX, GP1=RX）
uart = busio.UART(board.GP0, board.GP1, baudrate=9600)

# GPSモジュール初期化
gps = adafruit_gps.GPS(uart)
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
gps.send_command(b'PMTK220,1000')

while True:
    gps.update()
    if gps.has_fix:
        print(f"Lat: {gps.latitude:.6f}")
        print(f"Lon: {gps.longitude:.6f}")
```

### K30 CO2センサー（UART）

```python
import board
import busio
import time

# UART初期化（9600bps）
uart = busio.UART(board.GP0, board.GP1, baudrate=9600)

# K30読み取りコマンド
CMD_READ_CO2 = bytes([0xFE, 0x44, 0x00, 0x08, 0x02, 0x9F, 0x25])

def read_co2():
    uart.write(CMD_READ_CO2)
    time.sleep(0.1)
    response = uart.read(7)
    if response and len(response) == 7:
        co2 = (response[3] << 8) | response[4]
        return co2
    return None
```

## 5. ADCセンサー接続例

### 土壌水分センサー（アナログ）

```python
import board
import analogio
import time

# ADC初期化（GP26 = A0）
soil_sensor = analogio.AnalogIn(board.GP26)

def get_moisture_percent():
    # 16bit ADC: 0-65535
    raw = soil_sensor.value
    # 乾燥時: ~50000, 湿潤時: ~20000（センサーにより異なる）
    percent = (50000 - raw) / 300
    return max(0, min(100, percent))

while True:
    moisture = get_moisture_percent()
    print(f"Soil Moisture: {moisture:.1f}%")
    time.sleep(5)
```

### 光センサー（アナログ）

```python
import board
import analogio
import time

# ADC初期化（GP27 = A1）
light_sensor = analogio.AnalogIn(board.GP27)

def get_light_level():
    raw = light_sensor.value
    # 0-65535 を 0-100% に変換
    return (raw / 65535) * 100

while True:
    light = get_light_level()
    print(f"Light Level: {light:.1f}%")
    time.sleep(1)
```

## 6. 電源・電圧の注意事項

### 3.3V vs 5V 選択

Grove Shield には電源切替スイッチがある：

| 設定 | 用途 | 注意点 |
|------|------|--------|
| **3.3V** | ほとんどのセンサー | Pico のGPIOは3.3Vトレラント |
| **5V** | 5V専用モジュール | レベル変換が必要な場合あり |

### 電圧互換性チェックリスト

| センサー | 動作電圧 | 推奨設定 |
|---------|---------|---------|
| SHT40/SHT30 | 2.15-5.5V | 3.3V OK |
| SCD41 | 2.4-5.5V | 3.3V OK |
| BMP280 | 1.71-3.6V | **3.3V必須** |
| SGP30 | 1.62-1.98V | **3.3V** (内部LDO) |

### レベル変換が必要なケース

- 5V I2Cモジュール → Pico (3.3V) 接続時
- 5V UART → Pico 接続時

```
5V Module ─┬── R1 (10kΩ) ── Pico GPIO
           │
           └── R2 (20kΩ) ── GND
```

## 7. よくあるトラブルと対処法

### I2Cデバイスが認識されない

**症状**: `I2C device not found` エラー

**対処法**:

1. **アドレススキャン**で確認
```python
import board
import busio

i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

while not i2c.try_lock():
    pass

devices = i2c.scan()
print(f"Found devices: {[hex(d) for d in devices]}")
i2c.unlock()
```

2. **配線確認**: SDA-SDA, SCL-SCL が正しいか
3. **プルアップ抵抗**: Grove Shield には内蔵だが、長配線時は追加が必要
4. **電源**: VCC/GNDが正しく接続されているか

### ADC値が不安定

**症状**: 値が大きく変動する

**対処法**:

1. **移動平均フィルタ**
```python
readings = []
SAMPLES = 10

def read_filtered():
    readings.append(sensor.value)
    if len(readings) > SAMPLES:
        readings.pop(0)
    return sum(readings) // len(readings)
```

2. **デカップリングコンデンサ**: センサー近くに0.1μF追加
3. **配線を短く**: 長いワイヤはノイズを拾いやすい

### UARTデータが文字化け

**症状**: 読み取りデータが意味不明

**対処法**:

1. **ボーレート確認**: センサーの設定と一致しているか
2. **TX/RX逆接続**: Pico TX → センサー RX、Pico RX → センサー TX
3. **GND共通**: 必ずGNDを接続

## 8. W5500-EVB-Pico-PoE + Grove Shield スタック構成

### 構成図

```
┌─────────────────────────────────────┐
│     Grove Shield for Pi Pico       │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐    │
│  │I2C│ │I2C│ │A0 │ │A1 │ │A2 │    │
│  └───┘ └───┘ └───┘ └───┘ └───┘    │
│         Female Headers             │
└──────────────┬──────────────────────┘
               │ スタック接続
┌──────────────┴──────────────────────┐
│      W5500-EVB-Pico-PoE            │
│  ┌─────────┐     ┌────────┐        │
│  │ RP2040  │     │ W5500  │        │
│  └─────────┘     └────────┘        │
│  [PoE給電] ←── RJ45 ──→ [Ethernet] │
└─────────────────────────────────────┘
```

### ピン使用状況（干渉確認済み）

| 使用元 | GPIO | 干渉 |
|-------|------|------|
| **W5500 SPI** | GP16, GP17, GP18, GP19 | - |
| **W5500 制御** | GP20 (RST), GP21 (INT) | - |
| **Grove I2C0** | GP4 (SDA), GP5 (SCL) | なし |
| **Grove I2C1** | GP6 (SDA), GP7 (SCL) | なし |
| **Grove UART0** | GP0 (TX), GP1 (RX) | なし |
| **Grove ADC** | GP26, GP27, GP28 | なし |
| **システム** | GP24 (VBUS), GP25 (LED), GP29 (ADC3) | - |

**結論**: W5500とGrove Shieldは異なるピンを使用するため、**干渉なしで併用可能**。

### 電源供給経路

```
PoE給電 (48V)
    │
    ▼
PoEコンバータ (W5500-EVB-Pico-PoE内蔵)
    │
    ├── 3.3V → RP2040
    │
    └── VSYS (5V相当) → Grove Shield VCC
                            │
                            └── 3.3V/5V切替スイッチ
                                    │
                                    ▼
                                センサーへ
```

### スタック時の注意点

1. **Grove Shield の電源スイッチ**: 3.3V推奨（ほとんどのセンサー対応）
2. **PoE給電能力**: 最大15W程度、センサー数に注意
3. **発熱**: 長時間運用時はエアフロー確保

### CircuitPython での使用例（W5500 + I2Cセンサー）

```python
import board
import busio
import digitalio
import adafruit_sht4x
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket

# W5500 SPI設定
cs = digitalio.DigitalInOut(board.GP17)
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)

# W5500初期化
eth = WIZNET5K(spi, cs)
print(f"IP: {eth.pretty_ip(eth.ip_address)}")

# I2Cセンサー設定（別ピンなので干渉なし）
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
sht = adafruit_sht4x.SHT4x(i2c)

# 両方同時に使用可能
temp, humid = sht.measurements
print(f"Temp: {temp:.1f}°C, Humid: {humid:.1f}%")
```

## 9. M5Stack Unit シリーズとの接続

### M5Stack Unit の利点

- **ケース付き**: IP等級の防塵防水モデルあり
- **Grove端子標準**: そのまま接続可能
- **高品質センサー**: Sensirion、Bosch等の採用
- **ドキュメント充実**: サンプルコード豊富

### 対応Unit一覧

| Unit名 | センサーIC | I2Cアドレス | 測定項目 |
|--------|-----------|-------------|---------|
| ENV III | SHT30 + QMP6988 | 0x44, 0x70 | 温度、湿度、気圧 |
| TVOC/eCO2 | SGP30 | 0x58 | TVOC、eCO2 |
| Light | - | Analog | 照度 |
| Color | TCS3472 | 0x29 | RGB色 |
| ToF | VL53L0X | 0x29 | 距離 |

### Unit ENV III 接続例

```python
import board
import busio
import time
import adafruit_sht4x  # SHT30互換

# I2C初期化
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# SHT30（ENV IIIに内蔵）
# 注: adafruit_sht4xはSHT30とピン互換だが、SHT3x用ライブラリ推奨
import adafruit_sht31d
sht = adafruit_sht31d.SHT31D(i2c)  # address=0x44

# QMP6988は専用ライブラリが必要（または直接I2C通信）
# 参考: https://github.com/m5stack/M5Unit-ENV

while True:
    print(f"Temperature: {sht.temperature:.1f}°C")
    print(f"Humidity: {sht.relative_humidity:.1f}%")
    time.sleep(2)
```

### Unit TVOC/eCO2 (SGP30) 接続例

```python
import board
import busio
import time
import adafruit_sgp30

# I2C初期化
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# SGP30初期化
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)

# キャリブレーション（初回のみ）
sgp.iaq_init()
# 既存のベースライン値があれば設定
# sgp.set_iaq_baseline(eco2_base, tvoc_base)

while True:
    print(f"eCO2: {sgp.eCO2} ppm")
    print(f"TVOC: {sgp.TVOC} ppb")
    time.sleep(1)
```

### Unit Light（アナログ）接続例

```python
import board
import analogio
import time

# アナログ入力（Grove A0 = GP26）
light = analogio.AnalogIn(board.GP26)

def get_lux():
    # 電圧値から照度を概算
    voltage = (light.value / 65535) * 3.3
    # 光センサー特性により変換式は異なる
    lux = voltage * 500  # 概算値
    return lux

while True:
    print(f"Light: {get_lux():.0f} lux (approx)")
    time.sleep(1)
```

### 複数Unit同時接続

```python
import board
import busio
import adafruit_sht31d
import adafruit_sgp30

# I2Cバス共有
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# ENV III (0x44)
sht = adafruit_sht31d.SHT31D(i2c)

# TVOC/eCO2 (0x58)
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)
sgp.iaq_init()

# 湿度補正をSGP30に渡す
while True:
    temp = sht.temperature
    humid = sht.relative_humidity

    # 湿度補正（精度向上）
    sgp.set_iaq_humidity(humid)

    print(f"Temp: {temp:.1f}°C, Humid: {humid:.1f}%")
    print(f"eCO2: {sgp.eCO2} ppm, TVOC: {sgp.TVOC} ppb")
```

## 必要ライブラリ（CircuitPython）

以下をCIRCUITPY/lib/にコピー：

```
lib/
├── adafruit_sht4x.mpy        # SHT40
├── adafruit_sht31d.mpy       # SHT30/SHT31
├── adafruit_scd4x.mpy        # SCD41
├── adafruit_bmp280.mpy       # BMP280
├── adafruit_sgp30.mpy        # SGP30
├── adafruit_gps.mpy          # GPS
├── adafruit_bus_device/      # I2C/SPIヘルパー
│   ├── __init__.mpy
│   ├── i2c_device.mpy
│   └── spi_device.mpy
└── adafruit_wiznet5k/        # W5500 Ethernet
    ├── __init__.mpy
    └── adafruit_wiznet5k_socket.mpy
```

ダウンロード: https://circuitpython.org/libraries

## 参考リンク

- [Grove Shield for Pi Pico - Seeed Studio](https://www.seeedstudio.com/Grove-Shield-for-Pi-Pico-v1-0-p-4846.html)
- [Grove System Wiki](https://wiki.seeedstudio.com/Grove_System/)
- [W5500-EVB-Pico-PoE - WIZnet](https://docs.wiznet.io/Product/Chip/Ethernet/W5500/W5500-EVB-Pico-PoE)
- [M5Stack Unit ENV III](https://docs.m5stack.com/en/unit/envIII)
- [CircuitPython Libraries](https://circuitpython.org/libraries)
- [Adafruit CircuitPython SHT4x](https://learn.adafruit.com/adafruit-sht40-temperature-humidity-sensor/python-circuitpython)
- [Adafruit CircuitPython SCD4x](https://learn.adafruit.com/adafruit-scd-40-and-scd-41/python-circuitpython)
