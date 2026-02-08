# Pico W → Node-RED 通信方式比較調査

> **調査者**: 足軽2号
> **タスクID**: subtask_028_pico_nodered_comm
> **日時**: 2026-02-04
> **目的**: Raspberry Pi Pico W と Node-RED 間の最適な通信方式を選定する

---

## 1. 調査対象の通信方式

| 方式 | プロトコル | 主な用途 |
|------|-----------|---------|
| MQTT | TCP/IP (pub/sub) | IoTセンサーデータ収集 |
| HTTP/REST | TCP/IP (req/res) | APIベース通信 |
| WebSocket | TCP/IP (双方向) | リアルタイム通信 |

---

## 2. MQTT方式

### 2.1 概要

MQTT（Message Queuing Telemetry Transport）は軽量なpub/subメッセージングプロトコル。IoTで最も広く使用される。

### 2.2 CircuitPython実装

**ライブラリ**: `adafruit_minimqtt`

```python
# インストール
# circup install adafruit_minimqtt

import wifi
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# WiFi接続
wifi.radio.connect("SSID", "PASSWORD")
pool = socketpool.SocketPool(wifi.radio)

# MQTTクライアント設定
mqtt_client = MQTT.MQTT(
    broker="192.168.1.100",  # Node-RED/Mosquittoのアドレス
    port=1883,
    socket_pool=pool,
)

# コールバック
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")

def on_message(client, topic, message):
    print(f"Received: {topic} = {message}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# 接続・送信
mqtt_client.connect()
mqtt_client.publish("sensors/temperature", "25.5")
mqtt_client.loop()
```

### 2.3 Node-RED側設定

```
[mqtt in] → [function] → [debug]
         ↓
    トピック: sensors/#
    QoS: 1
    ブローカー: localhost:1883
```

### 2.4 トピック設計例

```
farm/
├── sensors/
│   ├── pico001/
│   │   ├── temperature
│   │   ├── humidity
│   │   └── co2
│   └── pico002/
│       └── ...
├── actuators/
│   ├── pico001/
│   │   └── relay
│   └── ...
└── status/
    └── pico001/
        └── online
```

### 2.5 QoS（Quality of Service）

| QoS | 配信保証 | 用途 |
|-----|---------|------|
| 0 | At most once | センサーデータ（欠損許容） |
| 1 | At least once | 重要データ（推奨） |
| 2 | Exactly once | 課金・制御（オーバーヘッド大） |

### 2.6 Pros/Cons

| Pros | Cons |
|------|------|
| ✅ IoT標準プロトコル | ❌ MQTTブローカー必要（Mosquitto等） |
| ✅ 軽量・低帯域 | ❌ 初期設定がやや複雑 |
| ✅ QoSで信頼性確保 | ❌ WiFi切断時の再接続処理必要 |
| ✅ Node-REDとの親和性抜群 | |
| ✅ 双方向通信（制御指示も受信可能） | |
| ✅ 複数クライアント対応 | |

---

## 3. HTTP/REST方式

### 3.1 概要

HTTPリクエスト/レスポンス形式。シンプルで理解しやすい。

### 3.2 CircuitPython実装

**ライブラリ**: `adafruit_requests`

```python
# インストール
# circup install adafruit_requests

import wifi
import socketpool
import ssl
import adafruit_requests

# WiFi接続
wifi.radio.connect("SSID", "PASSWORD")
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# POSTでセンサーデータ送信
url = "http://192.168.1.100:1880/api/sensors"
data = {
    "device_id": "pico001",
    "temperature": 25.5,
    "humidity": 60.0
}

response = requests.post(url, json=data)
print(f"Status: {response.status_code}")
response.close()
```

### 3.3 Node-RED側設定

```
[http in] → [function] → [http response]
    ↓
    Method: POST
    URL: /api/sensors
```

**Functionノード例**:
```javascript
// センサーデータ処理
let data = msg.payload;
msg.payload = {
    device: data.device_id,
    temp: data.temperature,
    humid: data.humidity,
    timestamp: new Date().toISOString()
};
return msg;
```

### 3.4 ポーリング vs Webhook

| 方式 | Pico → Node-RED | Node-RED → Pico |
|------|-----------------|-----------------|
| **ポーリング** | POST定期送信 | Picoが定期GET |
| **Webhook** | POST送信 | 困難（Picoがサーバー化必要） |

**推奨**: Pico側からのPOST送信のみ使用（シンプル）

### 3.5 Pros/Cons

| Pros | Cons |
|------|------|
| ✅ 実装が最もシンプル | ❌ 双方向通信が困難 |
| ✅ 追加サーバー不要 | ❌ ポーリングは非効率 |
| ✅ デバッグ容易（curl等） | ❌ リアルタイム性に欠ける |
| ✅ SSL/TLS対応可能 | ❌ 毎回コネクション確立のオーバーヘッド |

---

## 4. WebSocket方式（参考）

### 4.1 概要

持続的な双方向通信。リアルタイム性が必要な場合に有効。

### 4.2 CircuitPython実装

**ライブラリ**: `adafruit_websocket`（未成熟）

```python
# 注意: CircuitPythonのWebSocketサポートは限定的
# 参考コードのみ

import wifi
import socketpool
# WebSocketライブラリは公式サポートが限定的
```

### 4.3 Node-RED側設定

```
[websocket in] → [function] → [websocket out]
    ↓
    Type: Listen on
    Path: /ws/sensors
```

### 4.4 Pros/Cons

| Pros | Cons |
|------|------|
| ✅ リアルタイム双方向 | ❌ CircuitPythonサポート限定的 |
| ✅ 低レイテンシ | ❌ 実装複雑 |
| | ❌ メモリ消費大 |

**結論**: 現時点ではPico Wでの採用は非推奨

---

## 5. 比較総括

### 5.1 比較表

| 観点 | MQTT | HTTP/REST | WebSocket |
|------|------|-----------|-----------|
| **実装の容易さ** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **信頼性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Node-RED親和性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **双方向通信** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **リソース消費** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **スケーラビリティ** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

### 5.2 既存資産（network_manager.py）の活用

先に作成した `network_manager.py` は **W5500（有線Ethernet）用**。

Pico W（WiFi）の場合:
- `wifi.radio` APIを使用
- 再接続ロジックは流用可能（設計パターン）
- 新規に `wifi_manager.py` を作成推奨

---

## 6. 推奨方式

### 🏆 推奨: MQTT方式

**理由**:

1. **IoT標準** - センサーデータ収集のデファクトスタンダード
2. **Node-REDとの親和性** - mqtt in/outノードで即座に連携可能
3. **双方向通信** - センサーデータ送信 + 制御指示受信の両方に対応
4. **QoSによる信頼性** - データ欠損を防止
5. **スケーラビリティ** - 複数Picoの追加が容易（トピック追加のみ）
6. **将来性** - Home Assistant等との連携も視野に

### 構成案

```
┌─────────────┐      WiFi       ┌─────────────┐
│   Pico W    │ ─── MQTT ────→ │  Mosquitto  │
│  (sensors)  │ ←── MQTT ───── │  (broker)   │
└─────────────┘                 └──────┬──────┘
                                       │
                                       ▼
                                ┌─────────────┐
                                │  Node-RED   │
                                │ (処理/可視化) │
                                └─────────────┘
```

### 次のステップ（提案）

1. **MQTTブローカー準備**: Mosquittoインストール（Node-RED同一マシン可）
2. **Pico W用WiFi/MQTTモジュール作成**: `wifi_mqtt_manager.py`
3. **Node-REDフロー作成**: センサーデータ受信・ダッシュボード表示
4. **動作検証**: 温湿度センサーでE2Eテスト

---

## 7. 補足: MQTTブローカー選択肢

| ブローカー | 特徴 | 推奨度 |
|-----------|------|--------|
| **Mosquitto** | 軽量・標準的 | ⭐⭐⭐⭐⭐ |
| **EMQX** | 高機能・クラスタ対応 | ⭐⭐⭐⭐ |
| **Node-RED内蔵** | aedes-broker | ⭐⭐⭐ |

**推奨**: Mosquitto（apt install mosquitto で即導入可能）

---

## 参考リンク

- [Adafruit MiniMQTT](https://docs.circuitpython.org/projects/minimqtt/en/stable/)
- [Adafruit Requests](https://docs.circuitpython.org/projects/requests/en/latest/)
- [Node-RED MQTT Cookbook](https://cookbook.nodered.org/mqtt/)
- [Mosquitto MQTT Broker](https://mosquitto.org/)
- [Pico W CircuitPython Guide](https://learn.adafruit.com/pico-w-wifi-with-circuitpython)
