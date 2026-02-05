# W5500 Ethernet Connection Test

W5500イーサネットコントローラー搭載デバイスの接続テスト支援スキル。

## 概要

W5500-EVB-Pico/Pico2 などのW5500イーサネットコントローラー搭載デバイスで、SPI初期化、DHCP/静的IP設定、ネットワーク疎通確認を行うテストコードを生成する。CircuitPython 10.x の新API（SocketPool方式）に対応。

## 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- W5500の接続テスト
- W5500イーサネット初期化確認
- DHCP動作テスト
- W5500-EVB-Pico のネットワーク設定確認
- CircuitPython 10.x 対応のW5500コード

## 前提条件

| 項目 | 要件 |
|------|------|
| ハードウェア | W5500-EVB-Pico / W5500-EVB-Pico2 |
| CircuitPython | 10.0.0 以降推奨（SocketPool対応） |
| ライブラリ | adafruit_wiznet5k |
| 接続 | LANケーブル接続済み |
| 環境 | DHCP対応ルーター または 静的IP設定 |

## テストシナリオ

### 1. ハードウェア認識テスト
```python
"""
W5500-EVB-Pico2 認識確認
"""
import board

# W5K_* ピンの存在確認
print("W5500 pins available:")
print(f"  SPI: {hasattr(board, 'W5K_SPI')}")
print(f"  CS:  {hasattr(board, 'W5K_CS')}")
print(f"  RST: {hasattr(board, 'W5K_RST')}")
print(f"  INT: {hasattr(board, 'W5K_INT')}")
print(f"  MISO: {hasattr(board, 'W5K_MISO')}")
print(f"  MOSI: {hasattr(board, 'W5K_MOSI')}")
print(f"  SCK: {hasattr(board, 'W5K_SCK')}")
```

**期待結果**:
- すべて `True` であればW5500対応ボード

### 2. SPI初期化テスト
```python
"""
W5500 SPI初期化と基本動作確認
"""
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K

# SPI設定（W5500-EVB-Pico/Pico2 標準ピン配置）
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
rst = digitalio.DigitalInOut(board.GP20)

# W5500初期化（DHCP有効）
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)

# MACアドレス確認
print("MAC:", [hex(i) for i in eth.mac_address])
```

**期待結果**:
```
MAC: ['0xde', '0xad', '0xbe', '0xef', '0xfe', '0xed']
```
（実際のMACアドレスはデバイスごとに異なる場合あり）

**ピン配置（W5500-EVB-Pico/Pico2）**:
| 信号 | GPIOピン | 説明 |
|------|----------|------|
| SCK  | GP18 | SPI Clock |
| MOSI | GP19 | SPI Master Out Slave In |
| MISO | GP16 | SPI Master In Slave Out |
| CS   | GP17 | Chip Select |
| RST  | GP20 | Reset |
| INT  | GP21 | Interrupt（オプション） |

### 3. DHCP IP取得テスト
```python
"""
DHCP経由でIPアドレスを取得
"""
# SPI初期化（前述の手順）
# ...

# DHCP有効で初期化
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)

# IP取得確認（数秒かかる場合あり）
import time
time.sleep(2)

print("IP Address:", eth.pretty_ip(eth.ip_address))
print("Link Status:", eth.link_status)
```

**期待結果**:
```
IP Address: 192.168.x.x
Link Status: True
```

**注意**: DHCPサーバーがない環境では `0.0.0.0` が表示される。その場合は静的IP設定を使用すること。

### 4. 静的IP設定テスト（DHCP失敗時の代替）
```python
"""
静的IPアドレスの設定
"""
# W5500初期化（DHCP無効）
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=False)

# 静的IP設定
eth.ifconfig = (
    (192, 168, 1, 100),  # IP Address
    (255, 255, 255, 0),  # Subnet Mask
    (192, 168, 1, 1),    # Gateway
    (8, 8, 8, 8)         # DNS Server
)

print("IP Address:", eth.pretty_ip(eth.ip_address))
```

**期待結果**:
```
IP Address: 192.168.1.100
```

### 5. CircuitPython 10.x SocketPool対応テスト
```python
"""
CircuitPython 10.x 新API（SocketPool）の動作確認
"""
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

# W5500初期化（前述）
# eth = WIZNET5K(...)

# SocketPool作成（CircuitPython 10.x方式）
pool = SocketPool(eth)

print("SocketPool created:", pool)
print("Type:", type(pool))
```

**期待結果**:
```
SocketPool created: <SocketPool object at 0x...>
Type: <class 'adafruit_wiznet5k.adafruit_wiznet5k_socketpool.SocketPool'>
```

### 6. TCP接続テスト（HTTP GET例）
```python
"""
TCP接続による疎通確認
HTTP GETリクエスト例（adafruit_requests使用）
"""
import adafruit_requests
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

# W5500 + SocketPool初期化
# ...

# Requestsライブラリ初期化（CircuitPython 10.x方式）
requests = adafruit_requests.Session(pool)

# HTTP GET テスト
response = requests.get("http://wifitest.adafruit.com/testwifi/index.html")
print("Status:", response.status_code)
print("Content (first 100 chars):", response.text[:100])
response.close()
```

**期待結果**:
```
Status: 200
Content (first 100 chars): <!DOCTYPE html>...
```

**注意**: `adafruit_requests` ライブラリが必要。circupでインストール可能。

### 7. MQTT接続テスト（オプション）
```python
"""
MQTTブローカーへの接続テスト
"""
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

# W5500 + SocketPool初期化
# ...

# MQTTクライアント作成（CircuitPython 10.x方式）
mqtt = MQTT.MQTT(
    broker="192.168.1.10",  # MQTTブローカーのIPアドレス
    port=1883,
    socket_pool=pool,
)

# 接続試行
try:
    mqtt.connect()
    print("MQTT Connected!")

    # テストメッセージ送信
    mqtt.publish("test/w5500", "Hello from W5500!")
    print("Message published")

    mqtt.disconnect()
    print("MQTT Disconnected")
except Exception as e:
    print(f"MQTT Error: {e}")
```

**期待結果**:
```
MQTT Connected!
Message published
MQTT Disconnected
```

## ライブラリ依存関係

### circupによるインストール
```bash
# circupのインストール（Ubuntu/Debian）
pip install circup --break-system-packages

# CIRCUITPY ドライブにライブラリをインストール
circup install adafruit_wiznet5k
circup install adafruit_minimqtt  # MQTT使用時
circup install adafruit_requests  # HTTP使用時
```

### 手動インストール
1. [CircuitPython Library Bundle](https://circuitpython.org/libraries) をダウンロード
2. 以下をCIRCUITPY/lib/にコピー:
   - `adafruit_wiznet5k/` （ディレクトリごと）
   - `adafruit_minimqtt/` （MQTT使用時）
   - `adafruit_requests.mpy` （HTTP使用時）
   - `adafruit_connection_manager.mpy` （依存関係）
   - `adafruit_ticks.mpy` （依存関係）

## トラブルシューティング

### Link LEDが点灯しない
| 原因 | 対処法 |
|------|--------|
| LANケーブル未接続 | LANケーブル接続確認 |
| ケーブル不良 | 別のケーブルで試行 |
| スイッチ/ルーターの問題 | 別のポートで試行 |

```python
# リンク状態確認
print("Link Status:", eth.link_status)
# False の場合は物理層の問題
```

### DHCP取得失敗（IP: 0.0.0.0）
| 原因 | 対処法 |
|------|--------|
| DHCPサーバーなし | 静的IP設定を使用 |
| DHCP待機時間不足 | time.sleep(3) で待機時間を延長 |
| ネットワークセグメント不一致 | ルーター設定確認 |

```python
# DHCP取得時間を延ばす
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)
time.sleep(3)  # DHCP応答待ち
print("IP:", eth.pretty_ip(eth.ip_address))
```

### SPI通信エラー
```python
# エラー例: "No response from WIZnet5k"
```

| 原因 | 対処法 |
|------|--------|
| ピン配置誤り | GP16-20の配線確認 |
| CSピンの衝突 | 他のSPIデバイスとCS共有していないか確認 |
| 電源不足 | USB電源を5V 2A以上のものに変更 |

```python
# ハードウェアリセット試行
rst.value = False
time.sleep(0.1)
rst.value = True
time.sleep(0.5)
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)
```

### ImportError: adafruit_wiznet5k_socket
```
ImportError: No module named 'adafruit_wiznet5k.adafruit_wiznet5k_socket'
```

**原因**: CircuitPython 10.x では `adafruit_wiznet5k_socket` が廃止され、`adafruit_wiznet5k_socketpool` に変更された。

**対処**:
```python
# ❌ 旧API（9.x以前）
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
MQTT.set_socket(socket, eth)

# ✅ 新API（10.x以降）
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
pool = SocketPool(eth)
mqtt = MQTT.MQTT(broker="...", socket_pool=pool)
```

## CircuitPython 10.x API変更まとめ

| 項目 | CircuitPython 9.x | CircuitPython 10.x |
|------|-------------------|-------------------|
| モジュール名 | `adafruit_wiznet5k_socket` | `adafruit_wiznet5k_socketpool` |
| 初期化方法 | `MQTT.set_socket(socket, eth)` | `pool = SocketPool(eth)` |
| MQTT初期化 | `MQTT.MQTT(broker=...)` | `MQTT.MQTT(broker=..., socket_pool=pool)` |
| Requests初期化 | `adafruit_requests.set_socket(socket, eth)` | `requests = adafruit_requests.Session(pool)` |

**推奨**: 新規プロジェクトでは必ずCircuitPython 10.x APIを使用すること。

## 完全な接続テストスクリプト

```python
"""
W5500-EVB-Pico2 完全接続テスト
CircuitPython 10.x 対応
"""
import board
import busio
import digitalio
import time
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

print("=" * 50)
print("W5500 Ethernet Connection Test")
print("=" * 50)

# Step 1: Hardware Check
print("\n[1/6] Hardware Check...")
try:
    assert hasattr(board, 'GP16'), "GP16 (MISO) not found"
    assert hasattr(board, 'GP17'), "GP17 (CS) not found"
    assert hasattr(board, 'GP18'), "GP18 (SCK) not found"
    assert hasattr(board, 'GP19'), "GP19 (MOSI) not found"
    assert hasattr(board, 'GP20'), "GP20 (RST) not found"
    print("✅ Hardware pins OK")
except AssertionError as e:
    print(f"❌ {e}")
    raise

# Step 2: SPI Initialization
print("\n[2/6] SPI Initialization...")
try:
    spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
    cs = digitalio.DigitalInOut(board.GP17)
    rst = digitalio.DigitalInOut(board.GP20)
    print("✅ SPI initialized")
except Exception as e:
    print(f"❌ SPI init failed: {e}")
    raise

# Step 3: W5500 Initialization
print("\n[3/6] W5500 Initialization...")
try:
    eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)
    print(f"✅ W5500 initialized")
    print(f"   MAC: {':'.join([f'{b:02x}' for b in eth.mac_address])}")
except Exception as e:
    print(f"❌ W5500 init failed: {e}")
    raise

# Step 4: Link Status Check
print("\n[4/6] Link Status Check...")
time.sleep(1)
if eth.link_status:
    print("✅ Ethernet link UP")
else:
    print("❌ Ethernet link DOWN")
    print("   → Check LAN cable connection")
    raise RuntimeError("Link down")

# Step 5: DHCP IP Acquisition
print("\n[5/6] DHCP IP Acquisition...")
time.sleep(2)  # DHCP待機
ip = eth.pretty_ip(eth.ip_address)
if ip != "0.0.0.0":
    print(f"✅ IP Address: {ip}")
else:
    print("❌ DHCP failed (IP: 0.0.0.0)")
    print("   → Use static IP configuration")
    raise RuntimeError("DHCP failed")

# Step 6: SocketPool Creation (CircuitPython 10.x)
print("\n[6/6] SocketPool Creation...")
try:
    pool = SocketPool(eth)
    print(f"✅ SocketPool created")
    print(f"   Type: {type(pool).__name__}")
except Exception as e:
    print(f"❌ SocketPool creation failed: {e}")
    raise

# Test Complete
print("\n" + "=" * 50)
print("✅ All tests passed!")
print("=" * 50)
print(f"\nDevice is ready for network communication.")
print(f"IP Address: {ip}")
print(f"Link Status: UP")
print(f"\nNext steps:")
print("  - HTTP communication: circup install adafruit_requests")
print("  - MQTT communication: circup install adafruit_minimqtt")
```

## 実行方法

### REPLで手動実行
```bash
# シリアル接続
screen /dev/ttyACM0 115200

# REPLに入る（Ctrl+C）
>>> import board
>>> # テストコードを入力...
```

### code.pyとして自動実行
1. 上記スクリプトを `code.py` として CIRCUITPY ドライブに保存
2. Picoがリセットされると自動実行される
3. シリアルコンソールで結果を確認

### Pythonスクリプトから自動テスト
```python
import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
time.sleep(1)

# Ctrl+C でREPLに入る
ser.write(b'\x03')
time.sleep(0.5)

# テストコード実行
test_code = """
import board
# ... テストコード ...
"""
ser.write(test_code.encode())
ser.write(b'\r\n')

# 結果読み取り
while True:
    line = ser.readline()
    if line:
        print(line.decode('utf-8', errors='ignore'), end='')
```

## 関連スキル

- `circuitpython-network-manager`: W5500用ネットワーク再接続マネージャー
- `circuitpython-sensor-mqtt-builder`: センサーデータのMQTT送信実装
- `iot-comm-comparison`: IoT通信プロトコル比較

## 参考資料

- [Adafruit WIZnet5k Library Documentation](https://docs.circuitpython.org/projects/wiznet5k/en/latest/)
- [W5500-EVB-Pico Hardware Manual](https://docs.wiznet.io/Product/iEthernet/W5500/w5500-evb-pico)
- [CircuitPython 10.x Migration Guide](https://docs.circuitpython.org/en/latest/docs/design_guide.html)
