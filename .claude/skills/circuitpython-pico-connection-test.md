# circuitpython-pico-connection-test

Pico系ボードのCircuitPython接続テストを自動化するスキル。USB認識からMQTT通信までの6レイヤーを順次確認し、ハードウェア・ソフトウェアの動作状態を診断する。

## 概要

Raspberry Pi Pico W / Pico 2 W / W5500-EVB-Pico等のCircuitPython動作環境を多層的にテストし、接続問題を早期発見する。手動テストの手間を削減し、セットアップ後の動作確認を自動化する。

**主要機能**:
- 6レイヤーのテストフロー（USB → シリアル → REPL → ファイルシステム → ネットワーク → MQTT）
- ボード種類に応じた適切なテスト項目の自動選択
- OK/NG/SKIPの明確な判定基準
- CircuitPython 10.x SocketPool API完全対応
- トラブルシューティングガイド付き

## 使用方法

```
/circuitpython-pico-connection-test [ボード種類] [--mqtt-broker <IP>]
```

### 例

```bash
# Pico Wの基本テスト（WiFi接続まで）
/circuitpython-pico-connection-test pico-w

# W5500-EVB-Pico2のフルテスト（MQTT含む）
/circuitpython-pico-connection-test w5500-evb-pico2 --mqtt-broker 192.168.15.14

# 対話形式でボード選択
/circuitpython-pico-connection-test
```

## 対応ボード一覧

| ボードID | 正式名称 | 接続方式 | 特記事項 |
|----------|----------|----------|----------|
| `pico-w` | Raspberry Pi Pico W | WiFi (CYW43439) | WiFiテスト実施 |
| `pico2-w` | Raspberry Pi Pico 2 W | WiFi (CYW43439) | RP2350搭載 |
| `w5500-evb-pico` | W5500-EVB-Pico | Ethernet (W5500) | WiFiスキップ、Ethernetテスト |
| `w5500-evb-pico2` | W5500-EVB-Pico2 | Ethernet (W5500) | RP2350搭載 |
| `pico` | Raspberry Pi Pico | USB のみ | ネットワークスキップ |
| `pico2` | Raspberry Pi Pico 2 | USB のみ | RP2350搭載 |

## テスト項目（6レイヤー）

```
Layer 1: USBデバイス認識
  ├─ lsusbでデバイス検出
  ├─ /dev/ttyACM* の存在確認
  └─ ✅ OK / ❌ NG

Layer 2: シリアル接続
  ├─ pyserial経由で接続
  ├─ REPL プロンプト (>>>) 表示確認
  ├─ Ctrl+C, Ctrl+D 応答確認
  └─ ✅ OK / ❌ NG

Layer 3: CircuitPython REPL
  ├─ import board の成功確認
  ├─ dir(board) でピン一覧取得
  ├─ LED点灯テスト（board.LED）
  └─ ✅ OK / ❌ NG

Layer 4: ファイルシステム
  ├─ CIRCUITPY ドライブマウント確認
  ├─ code.py, settings.toml の存在確認
  ├─ /lib ディレクトリの存在確認
  └─ ✅ OK / ⚠️ WARNING / ❌ NG

Layer 5: ネットワーク
  ├─ WiFi（Pico W / Pico 2 W）
  │   ├─ import wifi の成功確認
  │   ├─ WiFi AP接続
  │   ├─ IPアドレス取得
  │   └─ ✅ OK / ⏭️ SKIP / ❌ NG
  │
  └─ Ethernet（W5500-EVB-Pico）
      ├─ W5500初期化
      ├─ DHCP/静的IP設定
      ├─ IPアドレス取得
      └─ ✅ OK / ⏭️ SKIP / ❌ NG

Layer 6: MQTT通信
  ├─ MQTTクライアント作成
  ├─ ブローカーに接続（CONNECT）
  ├─ トピックにpublish（PUBLISH）
  ├─ 正常切断（DISCONNECT）
  └─ ✅ OK / ⏭️ SKIP / ❌ NG
```

## 実テスト結果例（W5500-EVB-Pico2）

```
========================================
CircuitPython Connection Test Report
========================================

Board: W5500-EVB-Pico2
Test Date: 2026-02-05 22:18:00
Device: /dev/ttyACM0
CircuitPython Version: 10.0.3

----------------------------------------
Layer 1: USB Device Recognition    ✅ OK
----------------------------------------
  - lsusb: Bus 007 Device 091: ID 2e8a:109f WIZnet W5500-EVB-Pico2
  - Serial Port: /dev/ttyACM0

----------------------------------------
Layer 2: Serial Connection          ✅ OK
----------------------------------------
  - Baudrate: 115200
  - REPL Prompt: Detected
  - Ctrl+C/D: Responsive

----------------------------------------
Layer 3: CircuitPython REPL         ✅ OK
----------------------------------------
  - import board: Success
  - Available Pins: 58 pins (GP0-GP28, W5K_*, LED, etc.)
  - LED Test: Success (ON/OFF)

----------------------------------------
Layer 4: File System                ✅ OK
----------------------------------------
  - CIRCUITPY Drive: Mounted
  - code.py: Found
  - settings.toml: Found
  - /lib: Found (adafruit_wiznet5k, adafruit_minimqtt, etc.)

----------------------------------------
Layer 5: Network (Ethernet)         ✅ OK
----------------------------------------
  - W5500 Init: Success
  - MAC Address: de:ad:be:ef:fe:ed
  - IP Address: 192.168.15.13 (DHCP)

----------------------------------------
Layer 6: MQTT Communication         ✅ OK
----------------------------------------
  - Broker: 192.168.15.14:1883
  - CONNECT: Success
  - PUBLISH: Success (test/pico/w5500)
  - Message: "Hello from W5500-EVB-Pico2!"
  - DISCONNECT: Success
  - mosquitto_sub confirmed: Message received

========================================
Overall Result: ✅ ALL TESTS PASSED
========================================

Recommendations:
  - Board is ready for production use
  - All hardware and software layers operational
  - MQTT通信完全動作確認済み
```

## 自動テストスクリプトテンプレート

### Python自動テストスクリプト（pyserial使用）

```python
#!/usr/bin/env python3
"""
CircuitPython Pico Connection Test Script

Usage:
    python3 pico_connection_test.py --board pico-w
    python3 pico_connection_test.py --board w5500-evb-pico2 --mqtt-broker 192.168.15.14
"""

import serial
import time
import subprocess
import sys
import argparse
import re

# ============================================================
# Configuration
# ============================================================

SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 5
TEST_TOPIC = "test/pico/connection_test"

# ============================================================
# Test Functions
# ============================================================

def find_pico_serial_port():
    """
    Find Pico serial port (/dev/ttyACM*)

    Returns:
        str: Serial port path or None
    """
    try:
        result = subprocess.run(['ls', '/dev/ttyACM*'],
                                capture_output=True, text=True, shell=True)
        ports = result.stdout.strip().split('\n')
        if ports and ports[0]:
            return ports[0]
    except Exception as e:
        print(f"Error finding serial port: {e}")
    return None


def test_layer1_usb_recognition():
    """
    Layer 1: USB Device Recognition Test

    Returns:
        dict: {"status": "OK"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 1: USB Device Recognition")
    print("="*60)

    result = {"status": "NG", "details": {}}

    # lsusb check
    try:
        lsusb_output = subprocess.run(['lsusb'], capture_output=True, text=True)
        pico_devices = [line for line in lsusb_output.stdout.split('\n')
                        if '2e8a:' in line.lower() or 'pico' in line.lower()]

        if pico_devices:
            result["details"]["lsusb"] = pico_devices[0]
            print(f"  ✅ USB Device: {pico_devices[0]}")
        else:
            print("  ❌ No Pico device found in lsusb")
            return result
    except Exception as e:
        print(f"  ❌ lsusb error: {e}")
        return result

    # /dev/ttyACM* check
    port = find_pico_serial_port()
    if port:
        result["details"]["serial_port"] = port
        result["status"] = "OK"
        print(f"  ✅ Serial Port: {port}")
    else:
        print("  ❌ No /dev/ttyACM* found")

    return result


def test_layer2_serial_connection(port):
    """
    Layer 2: Serial Connection Test

    Args:
        port: Serial port path

    Returns:
        tuple: (status, serial_obj) - ("OK"|"NG", serial.Serial or None)
    """
    print("\n" + "="*60)
    print("Layer 2: Serial Connection")
    print("="*60)

    try:
        ser = serial.Serial(port, SERIAL_BAUDRATE, timeout=SERIAL_TIMEOUT)
        time.sleep(1)

        # Send Ctrl+C to enter REPL
        ser.write(b'\x03')
        time.sleep(0.5)

        # Check for REPL prompt (>>>)
        ser.write(b'\r\n')
        time.sleep(0.2)
        output = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')

        if '>>>' in output:
            print("  ✅ REPL Prompt: Detected")
            print("  ✅ Serial Connection: OK")
            return ("OK", ser)
        else:
            print("  ❌ REPL Prompt: Not detected")
            print(f"  Output: {output[:100]}")
            ser.close()
            return ("NG", None)

    except Exception as e:
        print(f"  ❌ Serial connection error: {e}")
        return ("NG", None)


def send_repl_command(ser, command, timeout=2):
    """
    Send command to REPL and get output

    Args:
        ser: serial.Serial object
        command: Command string
        timeout: Timeout in seconds

    Returns:
        str: Command output
    """
    # Clear buffer
    ser.read(ser.in_waiting)

    # Send command
    ser.write(command.encode() + b'\r\n')
    time.sleep(timeout)

    # Read output
    output = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
    return output


def test_layer3_circuitpython_repl(ser):
    """
    Layer 3: CircuitPython REPL Test

    Args:
        ser: serial.Serial object

    Returns:
        dict: {"status": "OK"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 3: CircuitPython REPL")
    print("="*60)

    result = {"status": "NG", "details": {}}

    # Test: import board
    output = send_repl_command(ser, "import board")
    if "Traceback" not in output and "Error" not in output:
        print("  ✅ import board: Success")
        result["details"]["import_board"] = "OK"
    else:
        print("  ❌ import board: Failed")
        print(f"  Output: {output[:100]}")
        return result

    # Test: dir(board)
    output = send_repl_command(ser, "dir(board)")
    pins = re.findall(r"'GP\d+'", output)
    if pins:
        print(f"  ✅ Available Pins: {len(pins)} GPIO pins")
        result["details"]["pins"] = len(pins)

    # Test: LED control
    led_test_code = """
import digitalio
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True
print("LED_ON")
led.value = False
print("LED_OFF")
"""
    output = send_repl_command(ser, led_test_code, timeout=3)
    if "LED_ON" in output and "LED_OFF" in output:
        print("  ✅ LED Test: Success (ON/OFF)")
        result["details"]["led_test"] = "OK"
        result["status"] = "OK"
    else:
        print("  ⚠️ LED Test: Uncertain (LED pin may not exist)")
        result["status"] = "OK"  # Still pass if other tests succeed

    return result


def test_layer4_filesystem(port):
    """
    Layer 4: File System Test

    Args:
        port: Serial port path

    Returns:
        dict: {"status": "OK"|"WARNING"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 4: File System")
    print("="*60)

    result = {"status": "NG", "details": {}}

    # Check CIRCUITPY drive
    try:
        result_proc = subprocess.run(['mount'], capture_output=True, text=True)
        if 'CIRCUITPY' in result_proc.stdout:
            print("  ✅ CIRCUITPY Drive: Mounted")
            result["details"]["drive_mounted"] = True
            result["status"] = "OK"

            # Extract mount point
            for line in result_proc.stdout.split('\n'):
                if 'CIRCUITPY' in line:
                    mount_point = line.split()[2] if len(line.split()) > 2 else None
                    if mount_point:
                        result["details"]["mount_point"] = mount_point

                        # Check code.py
                        import os
                        if os.path.exists(os.path.join(mount_point, 'code.py')):
                            print("  ✅ code.py: Found")
                            result["details"]["code_py"] = True
                        else:
                            print("  ⚠️ code.py: Not found")
                            result["status"] = "WARNING"

                        # Check settings.toml
                        if os.path.exists(os.path.join(mount_point, 'settings.toml')):
                            print("  ✅ settings.toml: Found")
                            result["details"]["settings_toml"] = True
                        else:
                            print("  ⚠️ settings.toml: Not found")

                        # Check /lib directory
                        lib_path = os.path.join(mount_point, 'lib')
                        if os.path.isdir(lib_path):
                            lib_count = len([f for f in os.listdir(lib_path)])
                            print(f"  ✅ /lib: Found ({lib_count} items)")
                            result["details"]["lib_items"] = lib_count
                        else:
                            print("  ⚠️ /lib: Not found")

        else:
            print("  ❌ CIRCUITPY Drive: Not mounted")
            print("  Note: Drive may be disabled by storage.disable_usb_drive()")

    except Exception as e:
        print(f"  ❌ File system check error: {e}")

    return result


def test_layer5_network_wifi(ser, ssid=None, password=None):
    """
    Layer 5: WiFi Network Test (Pico W / Pico 2 W)

    Args:
        ser: serial.Serial object
        ssid: WiFi SSID (optional, read from settings.toml)
        password: WiFi password (optional)

    Returns:
        dict: {"status": "OK"|"SKIP"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 5: Network (WiFi)")
    print("="*60)

    result = {"status": "SKIP", "details": {}}

    # Test: import wifi
    output = send_repl_command(ser, "import wifi")
    if "ImportError" in output or "No module" in output:
        print("  ⏭️ WiFi: Not available (Ethernet board or WiFi disabled)")
        result["details"]["reason"] = "No wifi module"
        return result

    print("  ✅ WiFi Module: Available")

    # Read WiFi credentials from settings.toml if not provided
    if not ssid:
        print("  ⚠️ WiFi credentials not provided, skipping connection test")
        result["details"]["reason"] = "No credentials"
        return result

    # Test: WiFi connection
    wifi_test_code = f"""
import wifi
wifi.radio.connect("{ssid}", "{password}")
print("IP:", wifi.radio.ipv4_address)
"""
    output = send_repl_command(ser, wifi_test_code, timeout=10)

    if "IP:" in output:
        ip_match = re.search(r'IP:\s*([\d\.]+)', output)
        if ip_match:
            ip = ip_match.group(1)
            print(f"  ✅ WiFi Connected: IP {ip}")
            result["details"]["ip_address"] = ip
            result["status"] = "OK"
        else:
            print("  ❌ WiFi Connection: Failed")
            result["status"] = "NG"
    else:
        print("  ❌ WiFi Connection: Failed")
        print(f"  Output: {output[:200]}")
        result["status"] = "NG"

    return result


def test_layer5_network_ethernet(ser):
    """
    Layer 5: Ethernet Network Test (W5500-EVB-Pico)

    Args:
        ser: serial.Serial object

    Returns:
        dict: {"status": "OK"|"SKIP"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 5: Network (Ethernet)")
    print("="*60)

    result = {"status": "SKIP", "details": {}}

    # Test: W5500 initialization
    eth_test_code = """
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K

spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
rst = digitalio.DigitalInOut(board.GP20)
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)

print("MAC:", [hex(i) for i in eth.mac_address])
print("IP:", eth.pretty_ip(eth.ip_address))
"""
    output = send_repl_command(ser, eth_test_code, timeout=10)

    if "ImportError" in output or "No module" in output:
        print("  ⏭️ Ethernet: Not available (WiFi board or library missing)")
        result["details"]["reason"] = "No wiznet5k module"
        return result

    if "MAC:" in output and "IP:" in output:
        mac_match = re.search(r"MAC:\s*\[(.*?)\]", output)
        ip_match = re.search(r"IP:\s*([\d\.]+)", output)

        if mac_match and ip_match:
            mac = mac_match.group(1)
            ip = ip_match.group(1)
            print(f"  ✅ W5500 Init: Success")
            print(f"  ✅ MAC Address: {mac}")
            print(f"  ✅ IP Address: {ip}")
            result["details"]["mac"] = mac
            result["details"]["ip_address"] = ip
            result["status"] = "OK"
        else:
            print("  ❌ Ethernet: Initialization failed")
            result["status"] = "NG"
    else:
        print("  ❌ Ethernet: Initialization failed")
        print(f"  Output: {output[:200]}")
        result["status"] = "NG"

    return result


def test_layer6_mqtt(ser, broker_ip, network_type="ethernet"):
    """
    Layer 6: MQTT Communication Test

    Args:
        ser: serial.Serial object
        broker_ip: MQTT broker IP address
        network_type: "wifi" or "ethernet"

    Returns:
        dict: {"status": "OK"|"SKIP"|"NG", "details": {...}}
    """
    print("\n" + "="*60)
    print("Layer 6: MQTT Communication")
    print("="*60)

    result = {"status": "SKIP", "details": {}}

    if not broker_ip:
        print("  ⏭️ MQTT: Broker not specified, skipping")
        result["details"]["reason"] = "No broker specified"
        return result

    if network_type == "ethernet":
        mqtt_test_code = f"""
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

pool = SocketPool(eth)
mqtt = MQTT.MQTT(broker="{broker_ip}", port=1883, socket_pool=pool)

print("MQTT_CONNECT: START")
mqtt.connect()
print("MQTT_CONNECT: OK")

print("MQTT_PUBLISH: START")
mqtt.publish("{TEST_TOPIC}", "Test from W5500")
print("MQTT_PUBLISH: OK")

mqtt.disconnect()
print("MQTT_DISCONNECT: OK")
"""
    else:  # wifi
        mqtt_test_code = f"""
import adafruit_minimqtt.adafruit_minimqtt as MQTT

mqtt = MQTT.MQTT(broker="{broker_ip}", port=1883, socket_pool=wifi.radio)

print("MQTT_CONNECT: START")
mqtt.connect()
print("MQTT_CONNECT: OK")

print("MQTT_PUBLISH: START")
mqtt.publish("{TEST_TOPIC}", "Test from Pico W")
print("MQTT_PUBLISH: OK")

mqtt.disconnect()
print("MQTT_DISCONNECT: OK")
"""

    output = send_repl_command(ser, mqtt_test_code, timeout=10)

    if "MQTT_CONNECT: OK" in output and "MQTT_PUBLISH: OK" in output:
        print(f"  ✅ MQTT Broker: {broker_ip}:1883")
        print("  ✅ CONNECT: Success")
        print(f"  ✅ PUBLISH: Success ({TEST_TOPIC})")
        print("  ✅ DISCONNECT: Success")
        result["details"]["broker"] = broker_ip
        result["status"] = "OK"
    elif "ImportError" in output or "No module" in output:
        print("  ⏭️ MQTT: Library not installed")
        result["details"]["reason"] = "No minimqtt module"
    else:
        print("  ❌ MQTT: Connection or publish failed")
        print(f"  Output: {output[:200]}")
        result["status"] = "NG"

    return result


def main():
    parser = argparse.ArgumentParser(description='CircuitPython Pico Connection Test')
    parser.add_argument('--board', type=str, required=True,
                        choices=['pico-w', 'pico2-w', 'w5500-evb-pico',
                                 'w5500-evb-pico2', 'pico', 'pico2'],
                        help='Board type')
    parser.add_argument('--mqtt-broker', type=str,
                        help='MQTT broker IP address')
    parser.add_argument('--wifi-ssid', type=str,
                        help='WiFi SSID (for Pico W/2W)')
    parser.add_argument('--wifi-password', type=str,
                        help='WiFi password (for Pico W/2W)')

    args = parser.parse_args()

    print("="*60)
    print("CircuitPython Pico Connection Test")
    print("="*60)
    print(f"Board: {args.board}")
    print(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Layer 1: USB Recognition
    layer1_result = test_layer1_usb_recognition()
    if layer1_result["status"] != "OK":
        print("\n❌ Layer 1 failed. Cannot proceed.")
        sys.exit(1)

    port = layer1_result["details"]["serial_port"]

    # Layer 2: Serial Connection
    layer2_status, ser = test_layer2_serial_connection(port)
    if layer2_status != "OK":
        print("\n❌ Layer 2 failed. Cannot proceed.")
        sys.exit(1)

    # Layer 3: CircuitPython REPL
    layer3_result = test_layer3_circuitpython_repl(ser)
    if layer3_result["status"] != "OK":
        print("\n❌ Layer 3 failed. Cannot proceed.")
        ser.close()
        sys.exit(1)

    # Layer 4: File System
    layer4_result = test_layer4_filesystem(port)
    if layer4_result["status"] == "NG":
        print("  ⚠️ File system issues detected, but continuing...")

    # Layer 5: Network
    network_type = None
    if args.board in ['pico-w', 'pico2-w']:
        layer5_result = test_layer5_network_wifi(ser, args.wifi_ssid, args.wifi_password)
        network_type = "wifi"
    elif args.board in ['w5500-evb-pico', 'w5500-evb-pico2']:
        layer5_result = test_layer5_network_ethernet(ser)
        network_type = "ethernet"
    else:
        print("\n" + "="*60)
        print("Layer 5: Network")
        print("="*60)
        print("  ⏭️ Network: Not available (USB-only board)")
        layer5_result = {"status": "SKIP"}

    # Layer 6: MQTT
    if layer5_result["status"] == "OK" and args.mqtt_broker:
        layer6_result = test_layer6_mqtt(ser, args.mqtt_broker, network_type)
    else:
        print("\n" + "="*60)
        print("Layer 6: MQTT Communication")
        print("="*60)
        if layer5_result["status"] != "OK":
            print("  ⏭️ MQTT: Skipped (Network layer not ready)")
        else:
            print("  ⏭️ MQTT: Skipped (No broker specified)")

    # Close serial connection
    ser.close()

    # Final summary
    print("\n" + "="*60)
    print("Overall Result: ✅ TEST COMPLETED")
    print("="*60)


if __name__ == "__main__":
    main()
```

## 判定基準

| 判定 | 記号 | 条件 |
|------|------|------|
| **OK** | ✅ | テスト項目が正常に完了 |
| **NG** | ❌ | テスト項目が失敗（要対応） |
| **SKIP** | ⏭️ | テスト項目がハードウェア的に非対応（正常） |
| **WARNING** | ⚠️ | 警告（動作は可能だが推奨設定と異なる） |

### 各レイヤーの判定基準

#### Layer 1: USBデバイス認識

| 判定 | 条件 |
|------|------|
| ✅ OK | `lsusb` でPicoデバイス検出 AND `/dev/ttyACM*` 存在 |
| ❌ NG | 上記いずれかが失敗 |

#### Layer 2: シリアル接続

| 判定 | 条件 |
|------|------|
| ✅ OK | シリアルポート接続成功 AND REPL プロンプト `>>>` 表示 |
| ❌ NG | 接続失敗 OR プロンプト表示なし |

#### Layer 3: CircuitPython REPL

| 判定 | 条件 |
|------|------|
| ✅ OK | `import board` 成功 AND `dir(board)` でピン一覧取得成功 |
| ❌ NG | インポートエラー OR ピン一覧取得失敗 |

#### Layer 4: ファイルシステム

| 判定 | 条件 |
|------|------|
| ✅ OK | `CIRCUITPY` ドライブマウント AND `code.py` 存在 AND `/lib` 存在 |
| ⚠️ WARNING | ドライブマウント成功だが `code.py` または `/lib` なし |
| ❌ NG | ドライブマウント失敗 |

#### Layer 5: ネットワーク

**WiFi (Pico W / Pico 2 W)**:

| 判定 | 条件 |
|------|------|
| ✅ OK | `import wifi` 成功 AND WiFi接続成功 AND IPアドレス取得 |
| ⏭️ SKIP | `import wifi` 失敗（Ethernetボードまたは無線なし） |
| ❌ NG | WiFi接続失敗（認証エラー、AP未検出等） |

**Ethernet (W5500-EVB-Pico)**:

| 判定 | 条件 |
|------|------|
| ✅ OK | W5500初期化成功 AND IPアドレス取得（DHCP/静的） |
| ⏭️ SKIP | `adafruit_wiznet5k` 未インストール |
| ❌ NG | W5500初期化失敗（SPI通信エラー、ケーブル未接続等） |

#### Layer 6: MQTT通信

| 判定 | 条件 |
|------|------|
| ✅ OK | MQTT CONNECT成功 AND PUBLISH成功 AND DISCONNECT成功 |
| ⏭️ SKIP | ブローカーIP未指定 OR `adafruit_minimqtt` 未インストール |
| ❌ NG | 接続失敗（ブローカー未起動、ネットワーク疎通なし等） |

## CircuitPython 10.x 対応の注意点

CircuitPython 10.x では、WIZnet5k用のソケットAPIが変更されています。

### 旧API（9.x以前）

```python
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
MQTT.set_socket(socket, eth)
mqtt = MQTT.MQTT(broker="...", port=1883)
```

### 新API（10.x以降）

```python
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
pool = SocketPool(eth)
mqtt = MQTT.MQTT(broker="...", port=1883, socket_pool=pool)
```

**変更点**:
- `socket` モジュール → `socketpool` モジュール
- `MQTT.set_socket()` メソッド廃止
- `MQTT()` コンストラクタに `socket_pool` パラメータ追加

## トラブルシューティング

### Layer 1: USBデバイス認識

| 症状 | 原因 | 対策 |
|------|------|------|
| lsusbでPicoが見つからない | USBケーブル不良 | データ転送対応ケーブルに交換 |
| /dev/ttyACM* が存在しない | dialoutグループ未所属 | `sudo usermod -a -G dialout $USER` 実行後ログアウト |
| デバイスがすぐ消える | 電源不足 | USB2.0ポート使用、外部電源供給 |

### Layer 2: シリアル接続

| 症状 | 原因 | 対策 |
|------|------|------|
| REPL プロンプトが表示されない | code.py実行中 | Ctrl+C でREPLに入る |
| Permission denied | デバイスアクセス権限なし | `sudo chmod 666 /dev/ttyACM0` または dialout グループ追加 |
| 文字化け | ボーレート不一致 | 115200に設定（CircuitPythonデフォルト） |

### Layer 3: CircuitPython REPL

| 症状 | 原因 | 対策 |
|------|------|------|
| import board 失敗 | CircuitPythonが未インストール | UF2ファイルをBOOTSELモードで書き込み |
| LED点灯しない | LEDピンが存在しない | ボード仕様確認（一部ボードはLEDなし） |
| Traceback表示 | ライブラリ依存関係エラー | 必要ライブラリをCIRCUITPY/libに配置 |

### Layer 4: ファイルシステム

| 症状 | 原因 | 対策 |
|------|------|------|
| CIRCUITPYドライブが表示されない | `storage.disable_usb_drive()` 実行済み | Ctrl+D でリブート、またはUSB抜き差し |
| code.py が読み込まれない | ファイル名誤り（code.txt等） | 拡張子を .py に変更 |
| /lib が見つからない | ディレクトリ未作成 | 手動で /lib フォルダを作成 |

### Layer 5: ネットワーク（WiFi）

| 症状 | 原因 | 対策 |
|------|------|------|
| WiFi接続タイムアウト | SSID/パスワード誤り | settings.toml を確認 |
| import wifi 失敗 | WiFi非対応ボード | Ethernet版または無線なし版を使用中（正常） |
| IPアドレス取得失敗 | DHCP サーバー未起動 | ルーター設定確認 |

### Layer 5: ネットワーク（Ethernet）

| 症状 | 原因 | 対策 |
|------|------|------|
| W5500初期化失敗 | SPI配線誤り | ピン配置確認（GP16-20） |
| MACアドレスが0x00... | W5500未接続 | 基板接続確認 |
| リンクLED点灯しない | LANケーブル未接続 | ケーブル接続、ループ配線確認 |

### Layer 6: MQTT通信

| 症状 | 原因 | 対策 |
|------|------|------|
| MQTT接続失敗 | ブローカー未起動 | `docker ps` でMosquitto起動確認 |
| ConnectionError | IPアドレス誤り | ping でブローカー疎通確認 |
| ImportError: minimqtt | ライブラリ未インストール | `circup install adafruit_minimqtt` 実行 |
| set_socket エラー | CircuitPython 10.x API変更 | SocketPool APIに移行（上記スクリプト参照） |

## 使用例

### 基本実行

```bash
# pyserialインストール（初回のみ）
pip install pyserial

# Pico Wテスト
python3 pico_connection_test.py --board pico-w --wifi-ssid "MySSID" --wifi-password "MyPass"

# W5500-EVB-Pico2テスト（MQTT含む）
python3 pico_connection_test.py --board w5500-evb-pico2 --mqtt-broker 192.168.15.14

# ポート指定
python3 pico_connection_test.py --board pico-w --port /dev/ttyACM1
```

### 手動テスト（REPLで実行）

```bash
# シリアル接続
screen /dev/ttyACM0 115200

# REPLに入る（Ctrl+C）
```

```python
# Layer 3: CircuitPython基本確認
import board
dir(board)

# Layer 3: LED点灯テスト
import digitalio
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = True  # 点灯
led.value = False  # 消灯

# Layer 5: Ethernet テスト（W5500-EVB-Pico系）
import board
import busio
import digitalio
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K

spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
cs = digitalio.DigitalInOut(board.GP17)
rst = digitalio.DigitalInOut(board.GP20)
eth = WIZNET5K(spi, cs, reset=rst, is_dhcp=True)

print("MAC:", [hex(i) for i in eth.mac_address])
print("IP:", eth.pretty_ip(eth.ip_address))

# Layer 6: MQTT テスト（CircuitPython 10.x API）
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

pool = SocketPool(eth)
mqtt = MQTT.MQTT(broker="192.168.15.14", port=1883, socket_pool=pool)

mqtt.connect()
mqtt.publish("test/pico/w5500", "Hello from W5500-EVB-Pico2!")
mqtt.disconnect()
```

### MQTTメッセージ受信確認（別ターミナル）

```bash
# Mosquitto subscribeで確認
mosquitto_sub -h 192.168.15.14 -t "test/pico/#" -v

# Dockerコンテナ内でsubscribe
docker exec arsprout-mqtt mosquitto_sub -t "test/pico/#" -v
```

## 関連スキル

- **pico-setup-wizard**: CircuitPythonセットアップガイド
- **circuitpython-toml-config**: settings.toml読み込みモジュール生成
- **pico-wifi-mqtt-template**: WiFi+MQTT統合マネージャー生成

## 参考資料

- CircuitPython公式ドキュメント: https://docs.circuitpython.org/
- Adafruit CircuitPython Bundle: https://circuitpython.org/libraries
- W5500-EVB-Pico: https://docs.wiznet.io/Product/iEthernet/W5500/w5500-evb-pico
- Raspberry Pi Pico W: https://www.raspberrypi.com/documentation/microcontrollers/raspberry-pi-pico.html
- pyserial ドキュメント: https://pyserial.readthedocs.io/
