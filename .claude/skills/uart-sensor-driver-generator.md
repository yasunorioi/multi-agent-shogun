# uart-sensor-driver-generator

UARTセンサードライバ（Python）一括生成スキル。センサー仕様からドライバ・サービス・systemdユニットを自動生成する。

## 概要

UART接続のセンサー（CO2、温湿度、気圧等）向けのPythonドライバを生成する。Modbus RTU対応、MQTT連携、systemdサービス化まで一貫して作成する。

**対象プラットフォーム**: Raspberry Pi（Python 3.x）
**通信方式**: UART (RS-232/RS-485)、Modbus RTU
**用途**: IoTセンサーノード開発

## 使用方法

```
/uart-sensor-driver-generator \
  --sensor-name "SensorModel" \
  --protocol "modbus" \
  --baudrate 9600 \
  --output-dir "/path/to/output"
```

### 必須パラメータ

- `--sensor-name`: センサー名（例: "CDM7160", "K30", "BME280"）
- `--protocol`: 通信プロトコル（"modbus", "custom", "ascii"）
- `--output-dir`: 出力先ディレクトリ

### オプションパラメータ

- `--baudrate`: ボーレート（デフォルト: 9600）
- `--data-format`: データフォーマット（デフォルト: "8N1"）
- `--mqtt-topic`: MQTTトピック（デフォルト: "sensors/{sensor_name}"）
- `--service-name`: systemdサービス名（デフォルト: "uart_{sensor_name}_reader"）

## 生成される成果物

### 1. センサードライバ (`lib/{sensor_name}.py`)

```python
"""
{SensorName} UART Sensor Driver

Hardware:
    - Sensor: {SensorName}
    - Interface: UART ({baudrate}bps, {data_format})
    - Measurement: {measurement_type}

Usage:
    from lib.{sensor_name} import {SensorClass}

    sensor = {SensorClass}('/dev/ttyAMA0')
    value = sensor.read()
    print(f"Reading: {value}")
    sensor.close()
"""

import serial
import time
import struct
from typing import Optional

class {SensorClass}Error(Exception):
    """センサーエラー"""
    pass

class {SensorClass}:
    """
    {SensorName} UARTセンサードライバ
    """

    BAUDRATE = {baudrate}
    BYTESIZE = serial.EIGHTBITS
    PARITY = serial.PARITY_NONE
    STOPBITS = serial.STOPBITS_ONE
    TIMEOUT = 1.0

    def __init__(self, port: str, baudrate: int = BAUDRATE, timeout: float = TIMEOUT):
        self.port = port
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=self.BYTESIZE,
            parity=self.PARITY,
            stopbits=self.STOPBITS,
            timeout=timeout
        )
        time.sleep(0.5)

    def read(self) -> Optional[float]:
        """センサー値を読み取る"""
        # Protocol-specific implementation
        pass

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

**生成内容**:
- シリアルポート初期化
- プロトコル別通信実装
  - Modbus RTU: CRC-16計算、Function Code対応
  - カスタムプロトコル: コマンド/応答パーサー
  - ASCIIプロトコル: 改行区切りテキスト
- エラーハンドリング
- コンテキストマネージャー対応
- テストコード

### 2. MQTTサービス (`services/{service_name}.py`)

```python
#!/usr/bin/env python3
"""
{SensorName} UART Reader Service

定期的にセンサーを読み取り、MQTTブローカーにpublishする。

Configuration: /etc/arsprout/{service_name}.yaml
"""

import sys
import yaml
import json
import logging
from pathlib import Path
import paho.mqtt.client as mqtt

# センサードライバをインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.{sensor_name} import {SensorClass}, {SensorClass}Error

class {ServiceClass}:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.sensor = None
        self.mqtt_client = None
        self.running = False

    def run(self):
        self._init_sensor()
        self._init_mqtt()

        interval = self.config.get('sensor', {}).get('interval', 10)

        self.running = True
        while self.running:
            value = self.sensor.read()
            if value is not None:
                self._publish(value)
            time.sleep(interval)
```

**生成内容**:
- YAML設定ファイル読み込み
- センサー初期化・読み取り
- MQTT接続管理・自動再接続
- 構造化ロギング
- エラー復旧機能

### 3. systemdユニット (`services/{service_name}.service`)

```ini
[Unit]
Description={SensorName} UART Sensor Reader Service
After=network.target mosquitto.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 {output_dir}/services/{service_name}.py --config /etc/arsprout/{service_name}.yaml
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 4. 設定ファイルテンプレート (`config/{service_name}.yaml`)

```yaml
sensor:
  type: "{sensor_name}"
  port: "/dev/ttyAMA0"
  interval: 10  # 読み取り間隔（秒）

mqtt:
  broker: "192.168.1.100"
  port: 1883
  username: null
  password: null
  topic: "{mqtt_topic}"
  qos: 1
  client_id: "{service_name}"
```

## プロトコル別実装

### Modbus RTU

```python
def _calculate_crc(self, data: bytes) -> int:
    """Modbus CRC-16計算"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def _build_read_command(self, register: int, count: int = 1) -> bytes:
    """Read Input Registers (Function Code 0x04)"""
    data = struct.pack('>BBHH',
                      0xFE,  # Device address (Any)
                      0x04,  # Function code
                      register,
                      count)
    crc = self._calculate_crc(data)
    return data + struct.pack('<H', crc)
```

### カスタムプロトコル

```python
def _send_command(self, command: bytes) -> bytes:
    """コマンド送信と応答受信"""
    self.serial.reset_input_buffer()
    self.serial.write(command)
    self.serial.flush()
    time.sleep(0.1)
    response = self.serial.read(self.RESPONSE_SIZE)
    return response

def _validate_checksum(self, data: bytes) -> bool:
    """チェックサム検証"""
    calculated = sum(data[:-1]) & 0xFF
    received = data[-1]
    return calculated == received
```

### ASCIIプロトコル

```python
def read(self) -> Optional[float]:
    """改行区切りASCII応答を読み取る"""
    line = self.serial.readline().decode('ascii').strip()
    try:
        return float(line)
    except ValueError:
        raise {SensorClass}Error(f"Invalid response: {line}")
```

## 実装例

### CDM7160 CO2センサー（カスタムプロトコル）

```bash
/uart-sensor-driver-generator \
  --sensor-name "CDM7160" \
  --protocol "custom" \
  --baudrate 9600 \
  --measurement "CO2" \
  --unit "ppm" \
  --range "0-5000" \
  --command "0x11 0x01 0x01 0xED" \
  --response-size 5 \
  --output-dir "/home/user/project"
```

**生成ファイル**:
- `lib/cdm7160.py` (6.5KB)
- `services/uart_cdm7160_reader.py` (9.2KB)
- `services/uart_cdm7160_reader.service` (787B)
- `config/uart_cdm7160_reader.yaml` (350B)

### K30 CO2センサー（Modbus RTU）

```bash
/uart-sensor-driver-generator \
  --sensor-name "K30" \
  --protocol "modbus" \
  --baudrate 9600 \
  --register 0x0003 \
  --measurement "CO2" \
  --unit "ppm" \
  --output-dir "/home/user/project"
```

**生成ファイル**:
- `lib/k30.py` (7.8KB)
- `services/uart_k30_reader.py` (9.2KB)
- `services/uart_k30_reader.service` (787B)
- `config/uart_k30_reader.yaml` (350B)

## インストール・デプロイ

### 1. ドライバのインストール

```bash
# 依存パッケージ
pip install pyserial paho-mqtt pyyaml

# ドライバをプロジェクトに配置
cp lib/{sensor_name}.py /path/to/project/lib/
```

### 2. サービスの設定

```bash
# 設定ファイルをコピー
sudo cp config/{service_name}.yaml /etc/arsprout/
sudo nano /etc/arsprout/{service_name}.yaml  # 環境に合わせて編集
```

### 3. systemdサービスの有効化

```bash
# サービスファイルをインストール
sudo cp services/{service_name}.service /etc/systemd/system/
sudo systemctl daemon-reload

# サービスを有効化・起動
sudo systemctl enable {service_name}
sudo systemctl start {service_name}

# ログ確認
sudo journalctl -u {service_name} -f
```

### 4. 動作確認

```bash
# ドライバの単体テスト
python lib/{sensor_name}.py /dev/ttyAMA0

# サービスの状態確認
sudo systemctl status {service_name}

# MQTT購読でデータ確認
mosquitto_sub -h 192.168.1.100 -t "sensors/#"
```

## 対応プロトコル

| プロトコル | 用途 | 実装機能 |
|-----------|------|----------|
| Modbus RTU | 産業用センサー（CO2、温湿度、圧力等） | CRC-16検証、Function Code 0x04対応 |
| カスタム | メーカー独自プロトコル | コマンド/応答パーサー、チェックサム検証 |
| ASCII | シンプルなセンサー | 改行区切りテキスト、数値パース |

## 生成時間・コスト削減効果

- **手動実装**: 約30分（ドライバ+サービス+systemd）
- **スキル使用**: 約5分（パラメータ指定のみ）
- **削減率**: 83%

## 参考実装

- `/home/yasu/arsprout_analysis/lib/cdm7160.py` - Figaro CDM7160（カスタムプロトコル）
- `/home/yasu/arsprout_analysis/lib/k30.py` - Senseair K30（Modbus RTU）
- `/home/yasu/arsprout_analysis/services/uart_co2_reader.py` - MQTTサービス実装

## 制限事項

- Python 3.x専用（CircuitPythonには非対応）
- UART通信のみ（I2C/SPIは別スキル）
- MQTTはpaho-mqtt使用（minimqttは非対応）

## 関連スキル

- `i2c-sensor-driver-generator` - I2Cセンサードライバ生成
- `circuitpython-project-initializer` - CircuitPythonプロジェクト初期化
