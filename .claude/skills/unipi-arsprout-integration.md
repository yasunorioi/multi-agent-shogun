# UniPi Arsprout ハードウェア流用ガイド

Arsproutで使用されているUniPi基板をそのまま流用し、
Home Assistant / Node-RED / 自作システムで制御するための完全ガイド。

---

## 重要性

**本プロジェクトの重要なセールスポイント**

| メリット | 説明 |
|---------|------|
| HW製造リスク回避 | 自前で基板製造・在庫を抱えない |
| 移行障壁の低減 | 既存Arsproutユーザーがそのまま移行可能 |
| 実績あるHW | 農業現場で稼働実績のある堅牢な基板 |
| オープンAPI | EVOK APIで自由に制御可能 |

---

## 1. UniPi 1 ハードウェア仕様

### 1.1 基板概要

| 項目 | 仕様 |
|------|------|
| 製品名 | UniPi 1.1 |
| フォームファクタ | Raspberry Pi HAT互換 |
| 対応RPi | Raspberry Pi Model B rev2（推奨）、Pi 3/4（一部制限あり） |
| 電源 | 24V DC または Raspberry Pi経由5V |

### 1.2 I/O構成

| I/O種別 | 数量 | 用途 |
|---------|------|------|
| リレー出力 | 8ch | 電磁弁、ファン等の制御 |
| デジタル入力 | 14ch | スイッチ、センサー入力 |
| アナログ入力 | 2ch | 0-10V電圧入力 |
| 1-Wireバス | 1ch | 温度センサー（DS18B20等） |

### 1.3 リレーピン配置（MCP23008）

**重要**: リレー番号とGPIOは**逆順**

| リレー番号 | MCP23008 GPIO | I2Cアドレス | ビット値 |
|-----------|---------------|-------------|---------|
| Relay 1 | GP7 | 0x20 | 0x80 |
| Relay 2 | GP6 | 0x20 | 0x40 |
| Relay 3 | GP5 | 0x20 | 0x20 |
| Relay 4 | GP4 | 0x20 | 0x10 |
| Relay 5 | GP3 | 0x20 | 0x08 |
| Relay 6 | GP2 | 0x20 | 0x04 |
| Relay 7 | GP1 | 0x20 | 0x02 |
| Relay 8 | GP0 | 0x20 | 0x01 |

### 1.4 MCP23008レジスタ

| レジスタ | アドレス | 用途 |
|---------|---------|------|
| IODIR | 0x00 | 入出力方向（0=出力） |
| GPIO | 0x09 | 出力値 |
| OLAT | 0x0A | 出力ラッチ |

---

## 2. EVOK API 完全リファレンス

### 2.1 概要

EVOKは UniPi公式のオープンソースAPI。
複数のプロトコルで I/O制御が可能。

| プロトコル | ポート | 用途 |
|-----------|--------|------|
| REST WebForms | 80 | シンプルなHTTPアクセス |
| REST JSON | 80 | JSON形式レスポンス |
| WebSocket | 8080 | リアルタイム双方向通信 |
| JSON-RPC | 80 | バッチ処理向け |

### 2.2 REST API（WebForms）

#### 全状態取得
```bash
curl http://[IP]/rest/all
```

#### リレー状態取得
```bash
# UniPi 1.1 形式
curl http://[IP]/rest/relay/1

# レスポンス例
1
```

#### リレー制御
```bash
# リレー1をON
curl -X POST http://[IP]/rest/relay/1 -d "value=1"

# リレー1をOFF
curl -X POST http://[IP]/rest/relay/1 -d "value=0"
```

#### デジタル入力取得
```bash
curl http://[IP]/rest/di/1
```

#### アナログ入力取得
```bash
curl http://[IP]/rest/ai/1
```

### 2.3 REST API（JSON）

#### 全状態取得（JSON）
```bash
curl http://[IP]/json/all
```

#### リレー状態取得（JSON）
```bash
curl http://[IP]/json/relay/1

# レスポンス例
{
  "circuit": "1",
  "value": 1,
  "pending": false,
  "mode": "Simple"
}
```

#### リレー制御（JSON）
```bash
curl -X POST http://[IP]/json/relay/1 \
  -H "Content-Type: application/json" \
  -d '{"value": 1}'
```

### 2.4 WebSocket API

#### 接続
```javascript
const ws = new WebSocket('ws://[IP]:8080/ws');

ws.onopen = () => {
  console.log('Connected to EVOK');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

#### コマンド形式
```json
// リレー制御
{"cmd": "set", "dev": "relay", "circuit": "1", "value": "1"}

// 状態取得
{"cmd": "get", "dev": "relay", "circuit": "1"}

// 全状態監視
{"cmd": "all"}
```

#### イベント受信例
```json
{
  "dev": "relay",
  "circuit": "1",
  "value": 1,
  "pending": false
}
```

### 2.5 JSON-RPC API

```bash
curl -X POST http://[IP]/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "relay_set",
    "params": {"circuit": "1", "value": 1}
  }'
```

---

## 3. 実装例

### 3.1 Python（requests使用）

```python
import requests

EVOK_URL = "http://192.168.1.100"

def get_relay_state(relay_num):
    """リレー状態を取得"""
    resp = requests.get(f"{EVOK_URL}/json/relay/{relay_num}")
    return resp.json()

def set_relay(relay_num, value):
    """リレーをON/OFF"""
    resp = requests.post(
        f"{EVOK_URL}/json/relay/{relay_num}",
        json={"value": value}
    )
    return resp.json()

def get_all_status():
    """全I/O状態を取得"""
    resp = requests.get(f"{EVOK_URL}/json/all")
    return resp.json()

# 使用例
if __name__ == "__main__":
    # リレー1をON
    set_relay(1, 1)

    # 状態確認
    state = get_relay_state(1)
    print(f"Relay 1: {'ON' if state['value'] else 'OFF'}")

    # リレー1をOFF
    set_relay(1, 0)
```

### 3.2 Python（WebSocket使用）

```python
import asyncio
import websockets
import json

EVOK_WS = "ws://192.168.1.100:8080/ws"

async def control_relay():
    async with websockets.connect(EVOK_WS) as ws:
        # 全状態監視開始
        await ws.send(json.dumps({"cmd": "all"}))

        # リレー1をON
        await ws.send(json.dumps({
            "cmd": "set",
            "dev": "relay",
            "circuit": "1",
            "value": "1"
        }))

        # イベント受信
        while True:
            message = await ws.recv()
            data = json.parse(message)
            print(f"Event: {data}")

asyncio.run(control_relay())
```

### 3.3 curl コマンド集

```bash
# === 状態取得 ===
# 全状態
curl http://192.168.1.100/json/all

# リレー1状態
curl http://192.168.1.100/json/relay/1

# デジタル入力1
curl http://192.168.1.100/json/di/1

# アナログ入力1
curl http://192.168.1.100/json/ai/1

# 1-Wire温度センサー
curl http://192.168.1.100/json/temp/1

# === リレー制御 ===
# リレー1 ON
curl -X POST http://192.168.1.100/json/relay/1 -H "Content-Type: application/json" -d '{"value":1}'

# リレー1 OFF
curl -X POST http://192.168.1.100/json/relay/1 -H "Content-Type: application/json" -d '{"value":0}'

# === 複数リレー一括制御 ===
# リレー1,2,3をON
for i in 1 2 3; do
  curl -X POST http://192.168.1.100/json/relay/$i -H "Content-Type: application/json" -d '{"value":1}'
done
```

### 3.4 Node-RED実装

#### 公式ノードのインストール
```bash
cd ~/.node-red
npm install @unipitechnology/node-red-contrib-unipi-evok
```

#### HTTPリクエストでの実装
```json
[
    {
        "id": "relay_on",
        "type": "http request",
        "name": "Relay ON",
        "method": "POST",
        "url": "http://192.168.1.100/json/relay/{{relay_num}}",
        "payload": "{\"value\": 1}",
        "payloadType": "json"
    },
    {
        "id": "relay_off",
        "type": "http request",
        "name": "Relay OFF",
        "method": "POST",
        "url": "http://192.168.1.100/json/relay/{{relay_num}}",
        "payload": "{\"value\": 0}",
        "payloadType": "json"
    }
]
```

#### WebSocket監視フロー
```json
[
    {
        "id": "evok_ws",
        "type": "websocket in",
        "name": "EVOK Events",
        "server": "",
        "client": "evok_ws_client"
    },
    {
        "id": "evok_ws_client",
        "type": "websocket-client",
        "path": "ws://192.168.1.100:8080/ws"
    },
    {
        "id": "parse_event",
        "type": "json",
        "name": "Parse JSON"
    },
    {
        "id": "switch_by_dev",
        "type": "switch",
        "name": "Device Type",
        "property": "payload.dev",
        "rules": [
            {"t": "eq", "v": "relay"},
            {"t": "eq", "v": "di"},
            {"t": "eq", "v": "ai"}
        ]
    }
]
```

---

## 4. Arsproutでの使用方法

### 4.1 Arsprout リレー割当（標準構成）

| リレー番号 | Arsprout用途 | CCM識別子 |
|-----------|-------------|-----------|
| Relay 1 | 灌水バルブ1 | Irriopr |
| Relay 2 | 灌水バルブ2 | Irriopr |
| Relay 3 | 灌水バルブ3 | Irriopr |
| Relay 4 | 灌水バルブ4 | Irriopr |
| Relay 5 | 換気扇 | VenFanopr |
| Relay 6 | サーキュレータ | CirVertFanopr |
| Relay 7 | 暖房機 | AirHeatBurnopr |
| Relay 8 | 予備 | - |

### 4.2 移行時の対応表

| Arsprout制御 | EVOK API | MQTTトピック例 |
|-------------|----------|---------------|
| 灌水ON | `POST /json/relay/1 {"value":1}` | `farm/actuators/valve1/cmd` |
| 灌水OFF | `POST /json/relay/1 {"value":0}` | `farm/actuators/valve1/cmd` |
| 換気扇ON | `POST /json/relay/5 {"value":1}` | `farm/actuators/fan/cmd` |
| サーキュON | `POST /json/relay/6 {"value":1}` | `farm/actuators/circulator/cmd` |

### 4.3 MQTT-EVOKブリッジ

```python
# mqtt_evok_bridge.py
import paho.mqtt.client as mqtt
import requests

EVOK_URL = "http://localhost"
MQTT_BROKER = "localhost"

# リレーマッピング
RELAY_MAP = {
    "farm/actuators/valve1/cmd": 1,
    "farm/actuators/valve2/cmd": 2,
    "farm/actuators/valve3/cmd": 3,
    "farm/actuators/valve4/cmd": 4,
    "farm/actuators/fan/cmd": 5,
    "farm/actuators/circulator/cmd": 6,
    "farm/actuators/heater/cmd": 7,
}

def on_message(client, userdata, msg):
    topic = msg.topic
    value = int(msg.payload.decode())

    if topic in RELAY_MAP:
        relay_num = RELAY_MAP[topic]
        requests.post(
            f"{EVOK_URL}/json/relay/{relay_num}",
            json={"value": value}
        )

client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER)

for topic in RELAY_MAP:
    client.subscribe(topic)

client.loop_forever()
```

---

## 5. Home Assistant設定例

### 5.1 REST API統合

```yaml
# configuration.yaml

# リレーをスイッチとして設定
switch:
  - platform: rest
    name: "灌水バルブ1"
    resource: http://192.168.1.100/json/relay/1
    body_on: '{"value": 1}'
    body_off: '{"value": 0}'
    is_on_template: "{{ value_json.value == 1 }}"
    headers:
      Content-Type: application/json

  - platform: rest
    name: "灌水バルブ2"
    resource: http://192.168.1.100/json/relay/2
    body_on: '{"value": 1}'
    body_off: '{"value": 0}'
    is_on_template: "{{ value_json.value == 1 }}"
    headers:
      Content-Type: application/json

  - platform: rest
    name: "換気扇"
    resource: http://192.168.1.100/json/relay/5
    body_on: '{"value": 1}'
    body_off: '{"value": 0}'
    is_on_template: "{{ value_json.value == 1 }}"
    headers:
      Content-Type: application/json

# デジタル入力をセンサーとして設定
sensor:
  - platform: rest
    name: "ドア開閉"
    resource: http://192.168.1.100/json/di/1
    value_template: "{{ 'Open' if value_json.value == 1 else 'Closed' }}"
    scan_interval: 5

# アナログ入力
  - platform: rest
    name: "水圧センサー"
    resource: http://192.168.1.100/json/ai/1
    value_template: "{{ value_json.value | round(2) }}"
    unit_of_measurement: "V"
    scan_interval: 10
```

### 5.2 unipi-control（MQTT統合）

```bash
# インストール
pip install unipi-control

# 起動
unipi-control --mqtt-host localhost --mqtt-port 1883
```

Home Assistant MQTT Discovery対応で自動認識。

### 5.3 カスタム統合（ha-unipi-neuron）

```bash
# HACS経由でインストール
# https://github.com/marko2276/ha-unipi-neuron
```

WebSocket直接接続で高速レスポンス。

---

## 6. 直接I2C制御

### 6.1 Python（smbus使用）

```python
import smbus
import time

# I2Cバス
bus = smbus.SMBus(1)
MCP23008_ADDR = 0x20

# レジスタ
IODIR = 0x00
GPIO = 0x09

# 初期化（全ピン出力）
bus.write_byte_data(MCP23008_ADDR, IODIR, 0x00)

def set_relay(relay_num, value):
    """
    リレーを制御
    relay_num: 1-8
    value: 0=OFF, 1=ON
    """
    # リレー番号からビット位置を計算（逆順）
    bit = 1 << (8 - relay_num)

    # 現在の状態を読み取り
    current = bus.read_byte_data(MCP23008_ADDR, GPIO)

    if value:
        new_value = current | bit
    else:
        new_value = current & ~bit

    bus.write_byte_data(MCP23008_ADDR, GPIO, new_value)

def get_relay(relay_num):
    """リレー状態を取得"""
    bit = 1 << (8 - relay_num)
    current = bus.read_byte_data(MCP23008_ADDR, GPIO)
    return 1 if current & bit else 0

# 使用例
set_relay(1, 1)  # Relay 1 ON
time.sleep(1)
set_relay(1, 0)  # Relay 1 OFF
```

### 6.2 CircuitPython（MCP23008ライブラリ）

```python
import board
import busio
from adafruit_mcp230xx.mcp23008 import MCP23008
import digitalio

# I2C初期化
i2c = busio.I2C(board.SCL, board.SDA)
mcp = MCP23008(i2c, address=0x20)

# リレーピン設定（逆順に注意）
relay_pins = [
    mcp.get_pin(7),  # Relay 1
    mcp.get_pin(6),  # Relay 2
    mcp.get_pin(5),  # Relay 3
    mcp.get_pin(4),  # Relay 4
    mcp.get_pin(3),  # Relay 5
    mcp.get_pin(2),  # Relay 6
    mcp.get_pin(1),  # Relay 7
    mcp.get_pin(0),  # Relay 8
]

# 出力設定
for pin in relay_pins:
    pin.direction = digitalio.Direction.OUTPUT

def set_relay(relay_num, value):
    """リレー制御（1-8）"""
    relay_pins[relay_num - 1].value = value

# 使用例
set_relay(1, True)   # Relay 1 ON
set_relay(1, False)  # Relay 1 OFF
```

### 6.3 i2csetコマンド（テスト用）

```bash
# I2Cデバイス検出
i2cdetect -y 1

# 出力方向設定
i2cset -y 1 0x20 0x00 0x00

# Relay 1 ON (GP7 = 0x80)
i2cset -y 1 0x20 0x09 0x80

# Relay 1 OFF
i2cset -y 1 0x20 0x09 0x00

# 全リレーON
i2cset -y 1 0x20 0x09 0xFF

# 全リレーOFF
i2cset -y 1 0x20 0x09 0x00
```

---

## 7. 他基板との比較

### 7.1 UniPiを選ぶ理由

| 観点 | UniPi | 汎用リレーボード | 自作基板 |
|------|-------|----------------|---------|
| **オープンAPI** | ✅ EVOK（OSS） | ❌ 独自/なし | ❌ 要開発 |
| **Raspberry Pi HAT** | ✅ 標準対応 | △ 一部のみ | ❌ 要設計 |
| **農業実績** | ✅ Arsprout採用 | ❌ なし | ❌ なし |
| **サポート** | ✅ フォーラムあり | △ メーカー依存 | ❌ 自己責任 |
| **入手性** | ✅ 通販で購入可 | ✅ Amazon等 | ❌ 製造必要 |
| **信頼性** | ✅ 産業用品質 | △ ホビー向け | △ 設計次第 |

### 7.2 UniPi製品ラインナップ

| 製品 | 特徴 | 用途 |
|------|------|------|
| **UniPi 1.1** | Arsprout採用 | 小規模、既存移行 |
| **Neuron S103** | DINレール対応 | 産業用途 |
| **Neuron M203** | 拡張I/O | 中規模システム |
| **Gate** | ゲートウェイ機能 | 複数拠点統合 |

### 7.3 代替検討時の注意

UniPi以外を検討する場合、以下を確認:
- I2Cアドレスが同じか（MCP23008: 0x20）
- リレー配置が同じか（逆順配線）
- EVOKと互換のAPIがあるか

---

## 8. トラブルシューティング

### 8.1 I2C通信エラー

**症状**: `i2cdetect`でデバイスが見えない

```bash
# I2C有効化確認
sudo raspi-config
# Interface Options > I2C > Enable

# デバイス確認
i2cdetect -y 1
# 0x20 が表示されるはず
```

**対策**:
- I2Cケーブル接続確認
- 電源電圧確認（3.3V/5V）
- 他のI2Cデバイスとのアドレス競合確認

### 8.2 EVOK接続エラー

**症状**: REST APIがタイムアウト

```bash
# EVOKサービス確認
sudo systemctl status evok

# 再起動
sudo systemctl restart evok

# ログ確認
journalctl -u evok -f
```

### 8.3 リレーが動作しない

**確認手順**:
1. I2C通信確認: `i2cdetect -y 1`
2. 直接制御テスト: `i2cset -y 1 0x20 0x09 0xFF`
3. リレークリック音の確認
4. 電源電圧確認（24V DC）

### 8.4 WebSocket切断

**症状**: WebSocket接続が頻繁に切れる

```javascript
// 再接続ロジック
function connect() {
    ws = new WebSocket('ws://192.168.1.100:8080/ws');
    ws.onclose = () => {
        setTimeout(connect, 5000);  // 5秒後に再接続
    };
}
```

### 8.5 RPi互換性問題

**UniPi 1.1 は RPi Model B rev2向け設計**

新しいRaspberry Pi（3/4/5）で使用時:
- P5ヘッダーの DI 13/14 は使用不可
- I2C_0 バスは使用不可
- I2C_1 バス（GPIO 2/3）は使用可能

---

## 9. 参考リンク

### 公式
- [UniPi Technology](https://www.unipi.technology/)
- [EVOK GitHub](https://github.com/UniPiTechnology/evok)
- [EVOK ドキュメント](https://evok.readthedocs.io/)
- [API仕様（Stoplight）](https://unipitechnology.stoplight.io/docs/evok)
- [UniPi フォーラム](https://forum.unipi.technology/)

### コミュニティ
- [unipi-mqtt](https://github.com/matthijsberg/unipi-mqtt) - MQTT統合
- [unipi-control](https://pypi.org/project/unipi-control/) - PyPIパッケージ
- [ha-unipi-neuron](https://github.com/marko2276/ha-unipi-neuron) - Home Assistant統合

### 技術資料
- [UniPi 1.1 技術マニュアル](https://cdn-reichelt.de/documents/datenblatt/A300/RB_UNIPI_MANUAL.pdf)
- [MCP23008 データシート](https://www.microchip.com/wwwproducts/en/MCP23008)
- [Adafruit MCP230xx ガイド](https://learn.adafruit.com/using-mcp23008-mcp23017-with-circuitpython/)

---

**作成日**: 2026-02-05
**作成者**: 足軽1号
**parent_cmd**: cmd_036
