# Embedded MQTT Tester - Skill Definition

**Skill ID**: `embedded-mqtt-tester`
**Category**: IoT / Testing / Quality Assurance
**Version**: 1.0.0
**Created**: 2026-02-05
**Platform**: CircuitPython 9.0+ / MicroPython (REPL-based devices)

---

## Overview

This skill provides a comprehensive framework for automated MQTT testing on embedded devices via pyserial-controlled REPL. It enables CI/CD integration, headless testing, and result verification for IoT sensor nodes without manual intervention.

**Core Capability**: Execute MQTT publish/subscribe tests on CircuitPython/MicroPython devices by sending REPL commands over serial connection, capturing results, and generating structured test reports.

---

## Use Cases

### 1. Development Workflow
- **Pre-commit Testing**: Verify MQTT functionality before pushing firmware changes
- **Regression Testing**: Ensure new features don't break existing MQTT communication
- **Protocol Validation**: Confirm correct MQTT packet flow (CONNECT, PUBLISH, SUBSCRIBE)

### 2. CI/CD Integration
- **GitHub Actions**: Automated tests on every push/PR
- **Jenkins Pipeline**: Integration testing in hardware-in-the-loop setups
- **Daily Smoke Tests**: Nightly validation of production firmware

### 3. Hardware Validation
- **Pico PoE Nodes**: Test W5500 Ethernet + MQTT stack
- **Pico 2 W Nodes**: Validate WiFi + MQTT communication
- **Multi-device Testing**: Parallel testing of multiple sensor nodes

### 4. Protocol Debugging
- **Connection Issues**: Diagnose MQTT broker connectivity problems
- **Message Verification**: Confirm payload structure and QoS levels
- **Network Stack Testing**: Validate TCP/IP → MQTT layer interactions

---

## Test Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Host PC (Ubuntu/Linux)                                  │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Python Test Script (pyserial)                     │ │
│  │  - REPL command sender                            │ │
│  │  - Result parser                                  │ │
│  │  - Timeout handler                                │ │
│  └──────────────┬────────────────────────────────────┘ │
│                 │ USB Serial                            │
│                 ▼                                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │ CircuitPython Device (Pico/Pico 2 W)              │ │
│  │  - REPL interface                                 │ │
│  │  - MQTT client (adafruit_minimqtt)                │ │
│  │  - Network stack (W5500/WiFi)                     │ │
│  └──────────────┬────────────────────────────────────┘ │
│                 │ Ethernet/WiFi                         │
└─────────────────┼─────────────────────────────────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ MQTT Broker      │
         │ (Mosquitto)      │
         │                  │
         │ - Port 1883      │
         │ - Docker/Local   │
         └────────┬─────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ mosquitto_sub    │
         │ (Verifier)       │
         │                  │
         │ Background proc  │
         └──────────────────┘
```

### Data Flow

1. **Test Script** sends REPL commands via pyserial
2. **Pico Device** executes MQTT operations (connect/publish/subscribe)
3. **Mosquitto Broker** routes messages
4. **Background Subscriber** (`mosquitto_sub`) captures messages
5. **Test Script** verifies results from both REPL output and subscriber logs

---

## Skill Input

When invoked, this skill requires:

| Parameter | Required | Description | Default |
|-----------|:--------:|-------------|---------|
| **device_type** | Yes | `usb` (Pico 2 W), `ethernet` (W5500) | - |
| **test_scenarios** | No | `connection`, `publish`, `subscribe`, `all` | `all` |
| **mqtt_broker** | No | Broker IP address | `192.168.1.10` |
| **mqtt_port** | No | Broker port | `1883` |
| **serial_port** | No | Device serial port | Auto-detect |
| **output_format** | No | `json`, `junit`, `markdown` | `json` |
| **ci_mode** | No | Enable CI-friendly output | `false` |

---

## Skill Output

The skill generates the following deliverables:

### 1. Test Script (`test_mqtt.py`)

Main test automation script with:
- Serial port detection
- REPL command execution
- Result parsing and verification
- Timeout handling
- Multi-scenario orchestration

### 2. Device Test Code (`mqtt_test_fixture.py`)

CircuitPython code deployed to device `/lib/`:
- MQTT test helper functions
- Network initialization
- Subscribe callback handlers
- Structured result output

### 3. Test Configuration (`mqtt_test_config.json`)

```json
{
  "mqtt_broker": "192.168.1.10",
  "mqtt_port": 1883,
  "test_topics": {
    "publish": "test/pico/publish",
    "subscribe": "test/pico/subscribe"
  },
  "timeouts": {
    "connect": 10,
    "publish": 5,
    "subscribe": 15
  }
}
```

### 4. CI/CD Integration Files

- **GitHub Actions**: `.github/workflows/mqtt-test.yml`
- **Docker Compose**: `docker-compose.test.yml` (Mosquitto broker)
- **Makefile**: `make test-mqtt` target

### 5. Documentation (`README_MQTT_TEST.md`)

- Setup instructions
- Usage examples
- Troubleshooting guide
- CI/CD integration steps

---

## Test Script Template

### Python Test Script (pyserial + REPL automation)

```python
#!/usr/bin/env python3
"""
mqtt_test_runner.py - Automated MQTT testing via pyserial REPL

Usage:
    python3 mqtt_test_runner.py --broker 192.168.1.10 --scenario all
"""

import serial
import serial.tools.list_ports
import time
import subprocess
import json
import re
import argparse
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class TestResult:
    """MQTT test result"""
    test_id: str
    name: str
    passed: bool
    duration_ms: int
    message: str
    mqtt_log: Optional[str] = None


class REPLController:
    """CircuitPython REPL controller via pyserial"""

    PICO_VID = "2E8A"  # Raspberry Pi Foundation

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port or self._find_pico_port()
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None

        if not self.port:
            raise RuntimeError("Pico device not found")

    def _find_pico_port(self) -> Optional[str]:
        """Auto-detect Pico serial port"""
        for port in serial.tools.list_ports.comports():
            if port.vid and f"{port.vid:04X}" == self.PICO_VID:
                return port.device
        return None

    def connect(self):
        """Open serial connection"""
        self.serial = serial.Serial(self.port, self.baudrate, timeout=5)
        time.sleep(0.5)
        # Enter REPL
        self.serial.write(b'\x03')  # Ctrl+C (interrupt)
        time.sleep(0.3)
        self.serial.read_all()  # Clear buffer
        print(f"[REPL] Connected to {self.port}")

    def disconnect(self):
        """Close serial connection"""
        if self.serial:
            self.serial.close()

    def execute(self, command: str, timeout: float = 10.0) -> str:
        """Execute REPL command and capture output"""
        if not self.serial:
            raise RuntimeError("Serial not connected")

        # Send command
        self.serial.write(f"{command}\r\n".encode())

        # Read response until prompt or timeout
        start = time.time()
        output = ""

        while time.time() - start < timeout:
            if self.serial.in_waiting:
                chunk = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                output += chunk
                if '>>>' in chunk:  # REPL prompt detected
                    break
            time.sleep(0.1)

        return output

    def soft_reboot(self):
        """Soft reboot device (Ctrl+D)"""
        if self.serial:
            self.serial.write(b'\x04')
            time.sleep(2)
            self.serial.read_all()


class MQTTTestRunner:
    """MQTT test orchestrator"""

    def __init__(self, config: dict):
        self.config = config
        self.repl = REPLController()
        self.results: List[TestResult] = []

    def setup(self):
        """Initialize test environment"""
        self.repl.connect()

        # Import test fixture
        init_code = """
import sys
sys.path.append('/lib')
from mqtt_test_fixture import MQTTTestFixture

test_fixture = MQTTTestFixture(
    broker='{broker}',
    port={port}
)
print('[FIXTURE] Ready')
""".format(**self.config)

        output = self.repl.execute(init_code, timeout=15)

        if '[FIXTURE] Ready' not in output:
            raise RuntimeError(f"Fixture init failed: {output}")

    def teardown(self):
        """Cleanup test environment"""
        self.repl.disconnect()

    def run_test(self, test_id: str, name: str, test_func) -> TestResult:
        """Execute single test"""
        print(f"\n[TEST] {test_id}: {name}")
        start = time.time()

        try:
            result, mqtt_log = test_func()
            passed = True
            message = result
        except Exception as e:
            passed = False
            message = str(e)
            mqtt_log = None

        duration = int((time.time() - start) * 1000)

        test_result = TestResult(
            test_id=test_id,
            name=name,
            passed=passed,
            duration_ms=duration,
            message=message,
            mqtt_log=mqtt_log
        )

        self.results.append(test_result)

        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {test_id}: {message} ({duration}ms)")

        return test_result

    # ========================================
    # Test Scenarios
    # ========================================

    def test_mqtt_connect(self) -> tuple[str, Optional[str]]:
        """MQTT-001: Connection test"""
        output = self.repl.execute("result = test_fixture.test_connect()", timeout=15)

        if 'Connected to MQTT' in output or 'CONNACK' in output:
            return "MQTT connection successful", output
        else:
            raise Exception(f"Connection failed: {output}")

    def test_mqtt_publish(self) -> tuple[str, Optional[str]]:
        """MQTT-002: Publish test"""
        topic = self.config['test_topics']['publish']
        payload = f"Test message {int(time.time())}"

        # Start background subscriber
        sub_process = subprocess.Popen(
            ['mosquitto_sub', '-h', self.config['mqtt_broker'], '-t', topic, '-C', '1'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(1)  # Wait for subscriber to be ready

        # Execute publish from device
        cmd = f"test_fixture.test_publish('{topic}', '{payload}')"
        output = self.repl.execute(cmd, timeout=10)

        # Wait for subscriber result
        try:
            stdout, stderr = sub_process.communicate(timeout=5)
            received = stdout.decode().strip()

            if payload in received:
                return f"Published and verified: {payload[:20]}...", output
            else:
                raise Exception(f"Payload mismatch: expected '{payload}', got '{received}'")

        except subprocess.TimeoutExpired:
            sub_process.kill()
            raise Exception("Subscriber timeout - message not received")

    def test_mqtt_subscribe(self) -> tuple[str, Optional[str]]:
        """MQTT-003: Subscribe test"""
        topic = self.config['test_topics']['subscribe']
        test_payload = f"Subscribe test {int(time.time())}"

        # Start subscribe on device (background)
        cmd = f"test_fixture.test_subscribe_async('{topic}')"
        output = self.repl.execute(cmd, timeout=5)

        time.sleep(2)  # Wait for subscription to be active

        # Publish from host
        subprocess.run(
            ['mosquitto_pub', '-h', self.config['mqtt_broker'], '-t', topic, '-m', test_payload],
            check=True,
            capture_output=True
        )

        time.sleep(2)  # Wait for message to arrive

        # Check result from device
        result = self.repl.execute("test_fixture.get_last_message()", timeout=5)

        if test_payload in result:
            return f"Subscribed and received: {test_payload[:20]}...", result
        else:
            raise Exception(f"Subscribe failed: expected '{test_payload}', got '{result}'")

    def test_mqtt_disconnect(self) -> tuple[str, Optional[str]]:
        """MQTT-004: Disconnect test"""
        output = self.repl.execute("test_fixture.test_disconnect()", timeout=10)

        if 'Disconnected' in output or 'DISCONNECT' in output:
            return "MQTT disconnect successful", output
        else:
            raise Exception(f"Disconnect failed: {output}")

    def run_all_tests(self) -> dict:
        """Execute all test scenarios"""
        start = time.time()

        self.setup()

        self.run_test("MQTT-001", "MQTT Connection", self.test_mqtt_connect)
        self.run_test("MQTT-002", "MQTT Publish", self.test_mqtt_publish)
        self.run_test("MQTT-003", "MQTT Subscribe", self.test_mqtt_subscribe)
        self.run_test("MQTT-004", "MQTT Disconnect", self.test_mqtt_disconnect)

        self.teardown()

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        return {
            "target": "MQTT Protocol Stack",
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "duration_ms": int((time.time() - start) * 1000),
            "results": [asdict(r) for r in self.results]
        }


def main():
    parser = argparse.ArgumentParser(description="MQTT Test Runner")
    parser.add_argument('--broker', default='192.168.1.10', help='MQTT broker IP')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--output', default='test_results.json', help='Output file')
    parser.add_argument('--scenario', default='all', help='Test scenario (all, connection, publish, subscribe)')
    args = parser.parse_args()

    config = {
        'mqtt_broker': args.broker,
        'mqtt_port': args.port,
        'test_topics': {
            'publish': 'test/pico/publish',
            'subscribe': 'test/pico/subscribe'
        }
    }

    runner = MQTTTestRunner(config)
    report = runner.run_all_tests()

    # Print summary
    print("\n" + "=" * 60)
    print(f"MQTT TEST SUMMARY: {report['target']}")
    print("=" * 60)
    print(f"Passed: {report['passed']}/{report['total_tests']}")
    print(f"Duration: {report['duration_ms']}ms")
    print()

    for r in report['results']:
        status = "✓" if r['passed'] else "✗"
        print(f"  {status} {r['test_id']}: {r['name']}")

    # Save JSON report
    with open(args.output, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nResults saved to {args.output}")

    return 0 if report['failed'] == 0 else 1


if __name__ == "__main__":
    exit(main())
```

---

## Device Test Fixture

### CircuitPython Code (`lib/mqtt_test_fixture.py`)

```python
"""
mqtt_test_fixture.py - MQTT test helper for CircuitPython devices

Deploy to device: /lib/mqtt_test_fixture.py
"""

import board
import busio
import time
import json
from digitalio import DigitalInOut

# Network import (adjust based on platform)
try:
    # W5500 Ethernet
    from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
    from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
    NETWORK_TYPE = "W5500"
except ImportError:
    # WiFi (Pico 2 W)
    import wifi
    import socketpool
    NETWORK_TYPE = "WiFi"

import adafruit_minimqtt.adafruit_minimqtt as MQTT


class MQTTTestFixture:
    """MQTT testing helper for CircuitPython"""

    def __init__(self, broker: str, port: int = 1883):
        self.broker = broker
        self.port = port
        self.mqtt_client = None
        self.last_message = None

        # Initialize network
        self._init_network()

    def _init_network(self):
        """Initialize network stack"""
        if NETWORK_TYPE == "W5500":
            # W5500 Ethernet (CircuitPython 10.x SocketPool API)
            cs = DigitalInOut(board.GP17)
            spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
            eth = WIZNET5K(spi, cs, is_dhcp=True)

            self.pool = SocketPool(eth)
            print(f"[NET] W5500 initialized: {eth.pretty_ip(eth.ip_address)}")

        else:
            # WiFi (Pico 2 W)
            # Assumes WiFi already connected (via settings.toml)
            self.pool = socketpool.SocketPool(wifi.radio)
            print(f"[NET] WiFi initialized: {wifi.radio.ipv4_address}")

    def test_connect(self) -> bool:
        """MQTT connection test"""
        try:
            self.mqtt_client = MQTT.MQTT(
                broker=self.broker,
                port=self.port,
                socket_pool=self.pool,
                keep_alive=60
            )

            # Callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message

            self.mqtt_client.connect()
            print("[MQTT] Connected to broker")
            return True

        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")
            return False

    def test_publish(self, topic: str, payload: str) -> bool:
        """MQTT publish test"""
        try:
            if not self.mqtt_client or not self.mqtt_client.is_connected():
                print("[MQTT] Not connected")
                return False

            self.mqtt_client.publish(topic, payload)
            print(f"[MQTT] Published: {topic} -> {payload}")
            return True

        except Exception as e:
            print(f"[MQTT] Publish failed: {e}")
            return False

    def test_subscribe_async(self, topic: str) -> bool:
        """MQTT subscribe test (non-blocking)"""
        try:
            if not self.mqtt_client or not self.mqtt_client.is_connected():
                print("[MQTT] Not connected")
                return False

            self.mqtt_client.subscribe(topic)
            print(f"[MQTT] Subscribed: {topic}")

            # Poll for messages (non-blocking)
            for _ in range(30):  # 3 seconds
                self.mqtt_client.loop(timeout=0.1)
                time.sleep(0.1)

            return True

        except Exception as e:
            print(f"[MQTT] Subscribe failed: {e}")
            return False

    def get_last_message(self) -> str:
        """Get last received message"""
        if self.last_message:
            return f"Received: {self.last_message}"
        else:
            return "No message received"

    def test_disconnect(self) -> bool:
        """MQTT disconnect test"""
        try:
            if self.mqtt_client:
                self.mqtt_client.disconnect()
                print("[MQTT] Disconnected")
            return True

        except Exception as e:
            print(f"[MQTT] Disconnect failed: {e}")
            return False

    # Callbacks

    def _on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] CONNACK received (RC: {rc})")

    def _on_message(self, client, topic, payload):
        self.last_message = payload.decode() if isinstance(payload, bytes) else payload
        print(f"[MQTT] Message: {topic} -> {self.last_message}")
```

---

## CircuitPython 10.x API Compatibility

### Key Changes from 9.x to 10.x

| Component | CircuitPython 9.x | CircuitPython 10.x |
|-----------|-------------------|---------------------|
| **Socket Module** | `adafruit_wiznet5k_socket` | `adafruit_wiznet5k_socketpool` |
| **MQTT Init** | `MQTT.set_socket(socket, eth)` | `MQTT(..., socket_pool=pool)` |
| **SocketPool** | Not used | `SocketPool(eth)` required |

### Migration Example

```python
# ===== CircuitPython 9.x (OLD API) =====
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket

socket.set_interface(eth)
MQTT.set_socket(socket, eth)
mqtt = MQTT.MQTT(broker="...", port=1883)

# ===== CircuitPython 10.x (NEW API) =====
from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool

pool = SocketPool(eth)
mqtt = MQTT.MQTT(broker="...", port=1883, socket_pool=pool)
```

### Version Detection

```python
import sys

def get_circuitpython_version():
    return sys.implementation.version[:2]  # (major, minor)

version = get_circuitpython_version()

if version >= (10, 0):
    # Use SocketPool API
    from adafruit_wiznet5k.adafruit_wiznet5k_socketpool import SocketPool
    pool = SocketPool(eth)
    mqtt = MQTT.MQTT(..., socket_pool=pool)
else:
    # Use legacy socket API
    import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
    socket.set_interface(eth)
    mqtt = MQTT.MQTT(...)
```

---

## mosquitto Integration

### Background Subscriber Pattern

```bash
#!/bin/bash
# mqtt_background_subscriber.sh

BROKER="${MQTT_BROKER:-192.168.1.10}"
TOPIC="${TEST_TOPIC:-test/pico/#}"
OUTPUT_FILE="/tmp/mqtt_test_output.log"

# Clear previous log
> "$OUTPUT_FILE"

# Start background subscriber
mosquitto_sub -h "$BROKER" -t "$TOPIC" -v >> "$OUTPUT_FILE" &
SUB_PID=$!

echo "Subscriber started (PID: $SUB_PID)"
echo "Logging to: $OUTPUT_FILE"

# Wait for test completion (or Ctrl+C)
trap "kill $SUB_PID 2>/dev/null; echo 'Subscriber stopped'" EXIT

wait $SUB_PID
```

### Docker Mosquitto for Testing

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: mqtt-test-broker
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
    networks:
      - test-network

networks:
  test-network:
    driver: bridge
```

```conf
# mosquitto.conf
listener 1883
allow_anonymous true
```

### Verification Commands

```bash
# Start test broker
docker-compose -f docker-compose.test.yml up -d

# Manual publish test
mosquitto_pub -h 192.168.1.10 -t test/pico/manual -m "Hello from host"

# Manual subscribe test
mosquitto_sub -h 192.168.1.10 -t test/pico/# -v

# Check broker logs
docker logs mqtt-test-broker
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/mqtt-test.yml
name: MQTT Integration Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  mqtt-test:
    runs-on: ubuntu-latest

    services:
      mosquitto:
        image: eclipse-mosquitto:2.0
        ports:
          - 1883:1883
        options: >-
          --health-cmd "mosquitto_sub -t test -C 1 -i healthcheck || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 3

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install pyserial pytest
          sudo apt-get update
          sudo apt-get install -y mosquitto-clients

      - name: Connect Pico device
        run: |
          # Wait for USB device
          timeout 30 bash -c 'until lsusb | grep -q "2e8a"; do sleep 1; done'
          echo "Pico device detected"

      - name: Run MQTT tests
        run: |
          python3 test_mqtt.py --broker localhost --output results.json

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: mqtt-test-results
          path: results.json

      - name: Publish test summary
        if: always()
        run: |
          python3 -c "
          import json
          with open('results.json') as f:
              data = json.load(f)
          print(f'MQTT Tests: {data[\"passed\"]}/{data[\"total_tests\"]} passed')
          "
```

### Makefile Integration

```makefile
# Makefile

.PHONY: test-mqtt test-mqtt-docker clean

# Run MQTT tests (requires hardware)
test-mqtt:
	python3 test_mqtt.py --broker 192.168.1.10 --output test_results.json

# Run tests with Docker Mosquitto
test-mqtt-docker:
	docker-compose -f docker-compose.test.yml up -d
	sleep 3
	python3 test_mqtt.py --broker localhost --output test_results.json
	docker-compose -f docker-compose.test.yml down

# Run specific test scenario
test-mqtt-connection:
	python3 test_mqtt.py --scenario connection --broker 192.168.1.10

test-mqtt-publish:
	python3 test_mqtt.py --scenario publish --broker 192.168.1.10

# Clean test artifacts
clean:
	rm -f test_results.json
	rm -f /tmp/mqtt_test_output.log
```

---

## Best Practices

### 1. Serial Communication
- **Buffer Management**: Always clear buffer before sending commands
- **Timeout Handling**: Set appropriate timeouts for each operation
- **Error Recovery**: Implement soft reboot on test failures

### 2. MQTT Testing
- **Unique Payloads**: Use timestamps to ensure message freshness
- **Topic Isolation**: Use test-specific topics to avoid interference
- **Background Subscribers**: Start subscribers before publishing

### 3. Test Reliability
- **Retry Logic**: Retry flaky operations (connection, publish)
- **Health Checks**: Verify broker availability before tests
- **Cleanup**: Always disconnect MQTT clients after tests

### 4. CI/CD
- **Hardware Detection**: Implement robust USB device detection
- **Parallel Testing**: Use test tags to run tests independently
- **Artifact Collection**: Save logs and results for debugging

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Port not found** | Pico not connected | Check USB cable, try different port |
| **REPL timeout** | Device frozen | Soft reboot with Ctrl+D |
| **MQTT connection failed** | Network issue | Verify broker IP, check firewall |
| **Subscribe timeout** | Message not sent | Check mosquitto_pub command, topic spelling |
| **Import error on device** | Missing library | Deploy `mqtt_test_fixture.py` to `/lib/` |

### Debug Commands

```bash
# Check serial ports
ls -la /dev/ttyACM* /dev/ttyUSB*

# Test serial connection
screen /dev/ttyACM0 115200

# Test MQTT broker
mosquitto_pub -h 192.168.1.10 -t test -m "hello"
mosquitto_sub -h 192.168.1.10 -t test -v

# Check MQTT broker logs
docker logs mqtt-test-broker -f
```

---

## References

- [PICO_CONNECTION_TEST.md](/home/yasu/arsprout_analysis/docs/PICO_CONNECTION_TEST.md) - Original test implementation
- [pyserial Documentation](https://pyserial.readthedocs.io/)
- [adafruit_minimqtt API](https://docs.circuitpython.org/projects/minimqtt/en/latest/)
- [Mosquitto Manual](https://mosquitto.org/man/mosquitto-8.html)
- [GitHub Actions Hardware Testing](https://github.blog/2021-08-26-github-actions-update-helping-maintainers-combat-bad-actors/)

---

## Related Skills

- `pico-wifi-mqtt-template`: WiFi+MQTT integrated manager generation
- `iot-auto-test-generator`: General IoT device auto-test framework
- `circuitpython-sensor-mqtt-builder`: Sensor driver + MQTT firmware builder

---

**Skill Author**: Arsprout QA Team
**Last Updated**: 2026-02-05
**License**: MIT
**Tested Platforms**: W5500-EVB-Pico2, Pico 2 W (CircuitPython 10.0.3)
