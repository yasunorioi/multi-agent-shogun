# circuitpython-pico-connection-test

Pico系ボードのCircuitPython接続テストを自動化し、USB認識、シリアル通信、ネットワーク機能を包括的に検証するスキル。

## 概要

Raspberry Pi Pico系ボード（Pico, Pico W, Pico 2, W5500-EVB-Pico等）のCircuitPython環境における接続テストを体系的に実施する。手動テスト手順と自動化スクリプトテンプレートを提供し、開発初期段階やトラブルシューティング時に迅速な動作確認を可能にする。

## 使用方法

```
/circuitpython-pico-connection-test [オプション]
```

### オプション

- `--auto`: 自動テストスクリプトを生成
- `--manual`: 手動テスト手順書を出力
- `--board <board-type>`: 対象ボードを指定（pico-w, w5500-evb-pico2 等）
- `--output <format>`: 出力形式（markdown, json）

### 例

```bash
# 自動テストスクリプト生成（W5500-EVB-Pico2用）
/circuitpython-pico-connection-test --auto --board w5500-evb-pico2

# 手動テスト手順書出力（Pico W用）
/circuitpython-pico-connection-test --manual --board pico-w
```

## テスト項目一覧

### 1. ハードウェア検出レイヤー

| テスト項目 | 検証コマンド | 期待結果 |
|-----------|------------|---------|
| **USB認識** | `lsusb` | `Bus XXX Device XXX: ID 2e8a:XXXX` |
| **シリアルポート** | `ls /dev/ttyACM*` | `/dev/ttyACM0` (またはACM1,2...) |
| **デバイスパーミッション** | `ls -l /dev/ttyACM0` | `crw-rw---- 1 root dialout` |

### 2. CircuitPython実行レイヤー

| テスト項目 | REPLコマンド | 期待結果 |
|-----------|-------------|---------|
| **REPL接続** | `Ctrl+C` | `>>>` プロンプト表示 |
| **基本import** | `import board` | エラーなし |
| **ピン一覧** | `dir(board)` | `['GP0', 'GP1', ..., 'LED']` |
| **LED制御** | `led = digitalio.DigitalInOut(board.LED); led.direction = digitalio.Direction.OUTPUT; led.value = True` | LED点灯 |

### 3. ネットワーク機能判別レイヤー

| テスト項目 | REPLコマンド | 成功時 | 失敗時 |
|-----------|-------------|-------|-------|
| **WiFi有無** | `import wifi` | ImportError無し → WiFi搭載 | ImportError → WiFi非搭載 |
| **Ethernet有無** | `'W5K_CS' in dir(board)` | True → W5500搭載 | False → Ethernet非搭載 |

### 4. ネットワーク接続レイヤー（WiFi）

| テスト項目 | REPLコマンド | 期待結果 |
|-----------|-------------|---------|
| **WiFi接続** | `import wifi; wifi.radio.connect(ssid, password)` | True |
| **IP取得** | `wifi.radio.ipv4_address` | `192.168.x.x` |

### 5. ネットワーク接続レイヤー（Ethernet）

| テスト項目 | REPLコマンド | 期待結果 |
|-----------|-------------|---------|
| **W5500初期化** | `from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K; eth = WIZNET5K(...)` | エラーなし |
| **MAC取得** | `eth.mac_address` | `b'\xde\xad\xbe\xef\xfe\xed'` |
| **DHCP IP取得** | `eth.pretty_ip(eth.ip_address)` | `192.168.x.x` |

### 6. 通信プロトコルレイヤー

| テスト項目 | REPLコマンド | 期待結果 |
|-----------|-------------|---------|
| **MQTT接続** | `mqtt.connect()` | 例外なし |
| **MQTT Publish** | `mqtt.publish("test/topic", "message")` | 例外なし |
| **HTTP GET** | `requests.get("http://example.com")` | status_code: 200 |

## 自動テストスクリプトテンプレート

### Python自動テストスクリプト（pyserial使用）

```python
#!/usr/bin/env python3
"""
CircuitPython Pico 接続テスト自動化スクリプト
"""
import serial
import time
import json
import sys
import subprocess
from typing import Dict, Any, Optional

class PicoConnectionTest:
    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.results: Dict[str, Any] = {}

    def test_usb_recognition(self) -> bool:
        """USB認識テスト"""
        print("Step 1: USB recognition test...")
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if '2e8a' in result.stdout:  # Raspberry Pi ベンダーID
            device_line = [line for line in result.stdout.split('\n') if '2e8a' in line]
            self.results['usb'] = {'status': 'OK', 'device': device_line[0] if device_line else 'Unknown'}
            print("  ✅ USB device detected")
            return True
        else:
            self.results['usb'] = {'status': 'FAILED', 'reason': 'No Pico device found'}
            print("  ❌ USB device not found")
            return False

    def test_serial_port(self) -> bool:
        """シリアルポート接続テスト"""
        print("Step 2: Serial port connection test...")
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(1)

            # Ctrl+C でREPLに入る
            self.ser.write(b'\x03')  # Ctrl+C
            time.sleep(0.5)

            # プロンプト確認
            output = self.ser.read_all().decode('utf-8', errors='ignore')
            if '>>>' in output:
                self.results['serial'] = {'status': 'OK', 'port': self.port}
                print("  ✅ REPL connection successful")
                return True
            else:
                self.results['serial'] = {'status': 'WARNING', 'reason': 'REPL prompt not found'}
                print("  ⚠️  Connected but REPL prompt unclear")
                return True
        except Exception as e:
            self.results['serial'] = {'status': 'FAILED', 'reason': str(e)}
            print(f"  ❌ Serial connection failed: {e}")
            return False

    def send_repl_command(self, command: str, wait_time: float = 1.0) -> str:
        """REPLコマンド送信"""
        if not self.ser:
            return ""

        # コマンド送信
        self.ser.write(command.encode('utf-8') + b'\r\n')
        time.sleep(wait_time)

        # 出力読み取り
        output = self.ser.read_all().decode('utf-8', errors='ignore')
        return output

    def test_circuitpython_basic(self) -> bool:
        """CircuitPython基本動作テスト"""
        print("Step 3: CircuitPython basic operation test...")

        # import board テスト
        output = self.send_repl_command("import board")
        if "Traceback" in output or "Error" in output:
            self.results['circuitpython'] = {'status': 'FAILED', 'reason': 'import board failed'}
            print("  ❌ import board failed")
            return False

        # dir(board) でピン一覧取得
        output = self.send_repl_command("dir(board)", wait_time=1.5)

        board_info = {
            'status': 'OK',
            'pins': [],
            'wifi': False,
            'ethernet': False
        }

        if 'GP0' in output or 'LED' in output:
            board_info['pins'] = ['GP0-GP28', 'LED'] if 'GP0' in output else ['LED']
            print("  ✅ CircuitPython operational")

        # WiFi有無判定
        if "'wifi'" in output.lower() or "WIFI" in output:
            board_info['wifi'] = True
            print("  ℹ️  WiFi module detected")

        # Ethernet有無判定
        if 'W5K_CS' in output or 'W5K_SPI' in output:
            board_info['ethernet'] = True
            print("  ℹ️  W5500 Ethernet detected")

        self.results['circuitpython'] = board_info
        return True

    def test_led_control(self) -> bool:
        """LED制御テスト"""
        print("Step 4: LED control test...")

        commands = [
            "import digitalio",
            "led = digitalio.DigitalInOut(board.LED)",
            "led.direction = digitalio.Direction.OUTPUT",
            "led.value = True",
            "led.value = False"
        ]

        for cmd in commands:
            output = self.send_repl_command(cmd, wait_time=0.3)
            if "Traceback" in output or "Error" in output:
                self.results['led'] = {'status': 'FAILED', 'reason': f'Command failed: {cmd}'}
                print(f"  ❌ LED control failed at: {cmd}")
                return False

        self.results['led'] = {'status': 'OK'}
        print("  ✅ LED control successful")
        return True

    def test_network_capability(self) -> Dict[str, bool]:
        """ネットワーク機能テスト"""
        print("Step 5: Network capability test...")

        network_caps = {'wifi': False, 'ethernet': False}

        # WiFi
        output = self.send_repl_command("import wifi", wait_time=0.5)
        if "ImportError" not in output and "Traceback" not in output:
            network_caps['wifi'] = True
            print("  ✅ WiFi module available")
        else:
            print("  ⏭️  WiFi module not available (expected for non-WiFi boards)")

        # Ethernet
        output = self.send_repl_command("'W5K_CS' in dir(board)", wait_time=0.5)
        if "True" in output:
            network_caps['ethernet'] = True
            print("  ✅ W5500 Ethernet available")
        else:
            print("  ⏭️  Ethernet not available (expected for WiFi-only boards)")

        self.results['network'] = network_caps
        return network_caps

    def run_all_tests(self) -> Dict[str, Any]:
        """全テスト実行"""
        print("="*60)
        print("CircuitPython Pico Connection Test")
        print("="*60)

        try:
            # USB認識
            if not self.test_usb_recognition():
                return self.results

            # シリアル接続
            if not self.test_serial_port():
                return self.results

            # CircuitPython基本動作
            self.test_circuitpython_basic()

            # LED制御
            self.test_led_control()

            # ネットワーク機能
            self.test_network_capability()

        except Exception as e:
            self.results['error'] = str(e)
        finally:
            if self.ser:
                self.ser.close()

        print("="*60)
        return self.results

    def print_summary(self):
        """結果サマリ出力"""
        print("\n📊 Test Summary:")
        print(json.dumps(self.results, indent=2))

        # 合格/不合格判定
        failed_tests = [k for k, v in self.results.items()
                       if isinstance(v, dict) and v.get('status') == 'FAILED']

        if failed_tests:
            print(f"\n❌ FAILED: {', '.join(failed_tests)}")
            sys.exit(1)
        else:
            print("\n✅ ALL TESTS PASSED")
            sys.exit(0)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='CircuitPython Pico Connection Test')
    parser.add_argument('--port', default='/dev/ttyACM0', help='Serial port (default: /dev/ttyACM0)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')

    args = parser.parse_args()

    tester = PicoConnectionTest(port=args.port, baudrate=args.baudrate)
    results = tester.run_all_tests()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        tester.print_summary()
```

### 使用例

```bash
# pyserialインストール（初回のみ）
pip install pyserial

# 基本実行
python3 pico_connection_test.py

# ポート指定
python3 pico_connection_test.py --port /dev/ttyACM1

# JSON出力
python3 pico_connection_test.py --json > test_results.json
```

## 手動テスト手順

### 手順1: USB認識確認

```bash
# デバイス認識
lsusb | grep 2e8a

# 期待される出力例
# Bus 007 Device 091: ID 2e8a:109f WIZnet W5500-EVB-Pico2
# または
# Bus 001 Device 015: ID 2e8a:0005 Raspberry Pi Pico W

# シリアルポート確認
ls -l /dev/ttyACM*

# 期待される出力例
# crw-rw---- 1 root dialout 166, 0 Feb 5 11:35 /dev/ttyACM0
```

**判定基準**:
- ✅ `2e8a:XXXX` が表示される
- ✅ `/dev/ttyACM0` (または ACM1) が存在する
- ⚠️ パーミッションが `dialout` グループに設定されている

**トラブルシューティング**:
- デバイスが表示されない → USBケーブル確認（データ転送対応か）、別ポートを試す
- パーミッションエラー → `sudo usermod -aG dialout $USER` 実行後ログアウト/ログイン

### 手順2: REPL接続

```bash
# screen を使用
screen /dev/ttyACM0 115200

# または picocom を使用
picocom /dev/ttyACM0 -b 115200

# または minicom を使用
minicom -D /dev/ttyACM0 -b 115200
```

**操作**:
1. 接続後、`Ctrl+C` でREPLに入る
2. `>>>` プロンプトが表示されればOK
3. `Ctrl+D` でソフトリブート

**screen終了方法**: `Ctrl+A` → `K` → `Y`

### 手順3: CircuitPython基本動作確認

REPLで以下を実行:

```python
# Step 1: board モジュールインポート
import board

# Step 2: 利用可能なピン一覧
dir(board)
# ['GP0', 'GP1', ..., 'GP28', 'LED', 'W5K_CS', ...] が表示される

# Step 3: LED点滅テスト
import digitalio
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# 点灯
led.value = True

# 消灯
led.value = False
```

**判定基準**:
- ✅ `import board` でエラーが出ない
- ✅ `dir(board)` でピン一覧が表示される
- ✅ LED制御コマンドでLEDが点灯/消灯する

### 手順4: ネットワーク機能判別

#### WiFi判別

```python
# WiFiモジュールのインポート試行
import wifi

# 成功 → WiFi搭載ボード（Pico W, Pico 2 W）
# ImportError → WiFi非搭載ボード
```

#### Ethernet判別

```python
# W5500ピンの存在確認
'W5K_CS' in dir(board)

# True → W5500搭載ボード（W5500-EVB-Pico系）
# False → W5500非搭載
```

### 手順5: W5500 Ethernet接続テスト（該当ボードのみ）

```python
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K

# SPI設定（W5500-EVB-Pico/Pico2のピン配置）
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
rst = digitalio.DigitalInOut(board.GP20)

# W5500初期化（DHCP有効）
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)

# MACアドレス確認
print("MAC:", [hex(i) for i in eth.mac_address])

# IP取得確認
print("IP:", eth.pretty_ip(eth.ip_address))
# 期待される出力: IP: 192.168.x.x
```

**判定基準**:
- ✅ MACアドレスが表示される
- ✅ IPアドレスが `192.168.x.x` または `10.x.x.x` 形式で取得できる
- ❌ `0.0.0.0` の場合 → DHCP失敗、LANケーブル接続確認

### 手順6: MQTT接続テスト（該当ボードのみ）

#### WiFi版（Pico W / Pico 2 W）

```python
import wifi
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# WiFi接続（settings.toml必要）
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))
print("IP:", wifi.radio.ipv4_address)

# SocketPool作成
pool = socketpool.SocketPool(wifi.radio)

# MQTT接続
mqtt = MQTT.MQTT(broker="192.168.1.10", port=1883, socket_pool=pool)
mqtt.connect()
mqtt.publish("test/pico", "Hello from Pico W")
mqtt.disconnect()
```

#### Ethernet版（W5500-EVB-Pico系）

```python
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# W5500初期化
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
rst = digitalio.DigitalInOut(board.GP20)
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)
print("IP:", eth.pretty_ip(eth.ip_address))

# SocketPool作成（CircuitPython 10.x方式）
pool = SocketPool(eth)

# MQTT接続
mqtt = MQTT.MQTT(broker="192.168.1.10", port=1883, socket_pool=pool)
mqtt.connect()
print("MQTT Connected!")
mqtt.publish("test/pico/w5500", "Hello from W5500-EVB-Pico2")
mqtt.disconnect()
```

**別ターミナルで受信確認**:

```bash
# Mosquittoクライアントでsubscribe
mosquitto_sub -h 192.168.1.10 -t "test/pico/#" -v

# 期待される出力
# test/pico/w5500 Hello from W5500-EVB-Pico2
```

## トラブルシューティング

### USB認識されない

| 症状 | 原因 | 対処法 |
|------|------|--------|
| `lsusb` に表示されない | USBケーブル不良 | データ転送対応ケーブルに交換 |
| デバイスが認識されない | ドライバ不足（Windows） | Zadig でドライバインストール |
| `/dev/ttyACM0` が存在しない | CircuitPython未書き込み | BOOTSELモードでUF2を書き込む |

### REPL接続できない

| 症状 | 原因 | 対処法 |
|------|------|--------|
| Permission denied | dialoutグループ未所属 | `sudo usermod -aG dialout $USER` → ログアウト/ログイン |
| プロンプトが出ない | code.py実行中 | `Ctrl+C` を複数回押す |
| 文字化け | ボーレート不一致 | 115200 bps を確認 |

### import エラー

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `ImportError: no module named 'wifi'` | WiFi非搭載ボード | 正常（W5500系等） |
| `ImportError: no module named 'adafruit_wiznet5k'` | ライブラリ未インストール | `circup install adafruit_wiznet5k` |
| `ImportError: no module named 'adafruit_minimqtt'` | ライブラリ未インストール | `circup install adafruit_minimqtt` |

### ネットワーク接続失敗

| 症状 | 原因 | 対処法 |
|------|------|--------|
| DHCP IP が 0.0.0.0 | LANケーブル未接続 | ケーブル接続確認、リンクLED点灯確認 |
| WiFi接続失敗 | SSID/パスワード誤り | settings.toml を確認 |
| MQTT接続失敗 | ブローカーアドレス誤り | `ping <broker_ip>` で疎通確認 |
| `ConnectionError` | ファイアウォール | ポート1883を開放 |

### CircuitPython 10.x API変更関連

| 症状 | 原因 | 対処法 |
|------|------|--------|
| `AttributeError: 'module' object has no attribute 'set_socket'` | 旧API使用 | `MQTT.set_socket()` → `MQTT(socket_pool=pool)` に変更 |
| `ImportError: adafruit_wiznet5k_socket` | モジュール名変更 | `adafruit_wiznet5k_socket` → `adafruit_wiznet5k_socketpool` |

## サンプル対話例

### 例1: 自動テスト実行

```
User: /circuitpython-pico-connection-test --auto --board w5500-evb-pico2

Claude: W5500-EVB-Pico2 用の接続テストスクリプトを生成します。

[自動テストスクリプトを出力]

このスクリプトを pico_test.py として保存し、以下のコマンドで実行してください：

```bash
python3 pico_test.py --port /dev/ttyACM0
```

実行すると以下の項目がテストされます：
1. USB認識（lsusb）
2. シリアルポート接続
3. CircuitPython基本動作
4. LED制御
5. W5500 Ethernet機能の有無

テスト結果はコンソールとJSONファイルに出力されます。
```

### 例2: 手動テスト手順出力

```
User: /circuitpython-pico-connection-test --manual --board pico-w

Claude: Raspberry Pi Pico W の手動接続テスト手順を出力します。

[手動テスト手順を出力]

各ステップの実行結果を確認しながら進めてください。
問題が発生した場合は、トラブルシューティングセクションを参照してください。
```

### 例3: 初心者向けガイド

```
User: Pico W を買ったけど動作確認の方法がわからない

Claude: Raspberry Pi Pico W の動作確認を順を追って説明します。

## 最小限の確認手順

### Step 1: CircuitPythonが入っているか確認

1. Pico W をUSB接続
2. 「CIRCUITPY」ドライブが表示されれば → 次へ
3. 表示されない場合 → CircuitPythonをインストール（/pico-setup-wizard参照）

### Step 2: シリアル接続

```bash
screen /dev/ttyACM0 115200
```

画面に何か文字が流れればOK。`Ctrl+C` で `>>>` が出ればREPL接続成功。

### Step 3: LED点滅

REPLで以下を実行：

```python
import board, digitalio
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True  # 点灯
```

ボード上のLEDが点灯すれば完全動作確認完了です！

より詳細なテストは `/circuitpython-pico-connection-test --manual --board pico-w` を実行してください。
```

## 出力ファイル

### テスト結果JSON例

```json
{
  "usb": {
    "status": "OK",
    "device": "Bus 007 Device 091: ID 2e8a:109f WIZnet W5500-EVB-Pico2"
  },
  "serial": {
    "status": "OK",
    "port": "/dev/ttyACM0"
  },
  "circuitpython": {
    "status": "OK",
    "pins": ["GP0-GP28", "LED"],
    "wifi": false,
    "ethernet": true
  },
  "led": {
    "status": "OK"
  },
  "network": {
    "wifi": false,
    "ethernet": true
  }
}
```

### テスト結果Markdown例

```markdown
# CircuitPython Pico Connection Test Result

**Test Date**: 2026-02-05 22:30:00
**Board**: W5500-EVB-Pico2
**Port**: /dev/ttyACM0

## Summary

✅ **ALL TESTS PASSED**

## Test Results

| Test Item | Status | Details |
|-----------|--------|---------|
| USB Recognition | ✅ OK | Bus 007 Device 091: ID 2e8a:109f |
| Serial Port | ✅ OK | /dev/ttyACM0 |
| CircuitPython | ✅ OK | import board successful |
| LED Control | ✅ OK | LED on/off successful |
| WiFi | ⏭️ SKIP | Not available (expected) |
| Ethernet | ✅ OK | W5K_CS detected |

## Board Capabilities

- **Pins**: GP0-GP28, LED
- **WiFi**: ❌ Not available
- **Ethernet**: ✅ W5500 available
```

## 関連スキル

- **pico-setup-wizard**: CircuitPython初期セットアップガイド
- **circuitpython-toml-config**: settings.toml設定ファイル生成
- **pico-wifi-mqtt-template**: WiFi+MQTT統合コード生成
- **circuitpython-network-manager**: ネットワーク接続マネージャー生成
- **i2c-sensor-auto-detector**: I2Cセンサー自動検出スキル

## 注意事項

- **CircuitPython 10.x**: SocketPool API が変更されているため、旧API（`set_socket`）は使用不可
- **pyserial**: 自動テストスクリプト実行には `pip install pyserial` が必要
- **パーミッション**: `/dev/ttyACM*` へのアクセスには `dialout` グループへの所属が必要
- **Ethernet接続**: LANケーブルが接続されていない場合、DHCPで `0.0.0.0` が返される
- **WiFi接続**: `settings.toml` にSSIDとパスワードが設定されていない場合、接続失敗する

## 参考資料

- CircuitPython公式ドキュメント: https://docs.circuitpython.org/
- Adafruit CircuitPython Bundle: https://circuitpython.org/libraries
- pyserial ドキュメント: https://pyserial.readthedocs.io/
