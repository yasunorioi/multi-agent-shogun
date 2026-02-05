# CircuitPython Sensor MQTT Builder - Skill Definition

**Skill ID**: `circuitpython-sensor-mqtt-builder`
**Category**: IoT / Firmware Development
**Version**: 1.0.0
**Created**: 2026-02-05
**Platform**: CircuitPython 9.0+ (W5500-EVB-Pico-PoE, Pico 2 W)

---

## Overview

This skill provides a structured workflow for creating I2C sensor drivers and MQTT-integrated firmware for CircuitPython platforms. It automates the process of porting Arduino sensor libraries to CircuitPython, implementing MQTT communication, and creating Home Assistant MQTT Discovery configurations.

---

## Use Cases

- **I2C Sensor Integration**: Porting Arduino drivers (DFRobot, Adafruit, SparkFun) to CircuitPython
- **Temperature/Humidity Sensors**: SHT31, SHT41, DHT22, BME280
- **CO2 Sensors**: SCD30, SCD40, SCD41
- **Environmental Sensors**: BMP280 (pressure), BH1750 (light), TSL2561
- **Liquid Monitoring**: EC sensors, pH sensors, flow sensors
- **Custom I2C Devices**: Any sensor with I2C interface (0x00-0x7F)

---

## Skill Input

When invoked, this skill requires:

### 1. Sensor Specification
- **Model Name**: e.g., "DFRobot SEN0575", "SHT41", "SCD30"
- **I2C Address**: e.g., 0x44, 0x61, 0x76
- **Communication Protocol**: I2C register addresses and commands
- **Data Format**: big-endian, little-endian, float, int
- **Measurement Units**: mm, °C, ppm, lux, etc.

### 2. Arduino Library Reference
- Link to Arduino library (GitHub, official docs)
- Datasheet URL
- Example Arduino code

### 3. Platform Details
- Board type (W5500-EVB-Pico-PoE, Pico 2 W)
- I2C pins (SDA, SCL)
- Network type (Ethernet or WiFi)

### 4. MQTT Integration
- House ID (e.g., "h1", "greenhouse1")
- Topic structure (e.g., `greenhouse/{house_id}/sensor/{type}`)
- Broker IP and port
- Publishing interval (seconds)

---

## Skill Output

The skill generates the following deliverables:

### 1. I2C Sensor Driver (`lib/sensor_name.py`)

```python
# Template structure:
# - I2C register definitions
# - Sensor class with I2CDevice wrapper
# - Read/write methods with error handling
# - Data conversion functions (big-endian, float, etc.)
```

### 2. Main Firmware (`firmware/node_name/code.py`)

```python
# Template structure:
# - Hardware initialization (W5500 or WiFi)
# - I2C sensor initialization
# - MQTT client setup with LWT
# - Main loop with interval-based publishing
# - Home Assistant MQTT Discovery
```

### 3. Configuration File (`firmware/node_name/settings.toml`)

```toml
# Template structure:
# - Device identification
# - Network configuration
# - MQTT broker settings
# - Sensor parameters
# - Timing configuration
```

### 4. Documentation (`firmware/node_name/README.md`)

```markdown
# Template structure:
# - Hardware requirements
# - Wiring diagram
# - Installation procedure
# - Configuration guide
# - Troubleshooting
```

### 5. Design Document (`docs/SENSOR_NAME_MQTT.md`)

```markdown
# Template structure:
# - System architecture
# - MQTT topic design
# - Data flow diagram
# - Error handling strategy
# - Future enhancements
```

---

## Workflow Steps

### Step 1: Analyze Arduino Library

1. **Identify I2C Registers**
   - Extract register addresses from Arduino `.h` files
   - Document read/write operations
   - Note data types (uint8, uint16, float)

2. **Understand Communication Protocol**
   - Command sequences
   - Wait times / delays
   - Endianness (big-endian or little-endian)

3. **Extract Conversion Formulas**
   - Raw data → physical units
   - Calibration factors
   - Scaling constants

**Example (DFRobot SEN0575 Rainfall Sensor)**:
```cpp
// Arduino library analysis
#define REG_RAINFALL 0x06  // 4 bytes, float, big-endian
#define REG_RAW_DATA 0x02  // 4 bytes, uint32, big-endian

float getRainfall() {
    uint8_t buffer[4];
    read_register(REG_RAINFALL, buffer, 4);
    return bytes_to_float_be(buffer);  // big-endian conversion
}
```

### Step 2: Create CircuitPython Driver

```python
# lib/dfrobot_rainfall.py (example)

import time
import struct
from adafruit_bus_device.i2c_device import I2CDevice

# I2C Register Addresses
REG_PID = 0x00
REG_RAINFALL = 0x06
REG_RAW_DATA = 0x02
REG_WORKING_TIME = 0x0E

class DFRobot_RainfallSensor:
    """
    CircuitPython driver for DFRobot SEN0575 rainfall sensor.

    Example:
        import board
        import busio
        from dfrobot_rainfall import DFRobot_RainfallSensor

        i2c = busio.I2C(board.GP5, board.GP4)
        sensor = DFRobot_RainfallSensor(i2c, address=0x1D)

        if sensor.begin():
            rainfall = sensor.get_rainfall()
            print(f"Rainfall: {rainfall} mm")
    """

    def __init__(self, i2c, address=0x1D):
        self.i2c_device = I2CDevice(i2c, address)
        self._address = address

    def begin(self):
        """Initialize sensor and verify connection."""
        try:
            pid = self._read_register_8(REG_PID)
            return pid != 0
        except Exception:
            return False

    def get_rainfall(self):
        """Get total rainfall in mm."""
        return self._read_register_float(REG_RAINFALL)

    def get_raw_data(self):
        """Get raw tip count."""
        return self._read_register_32(REG_RAW_DATA)

    def get_working_time(self):
        """Get sensor working time in hours."""
        return self._read_register_float(REG_WORKING_TIME)

    # I2C Communication Methods (private)

    def _read_register_8(self, reg):
        """Read 8-bit register."""
        buffer = bytearray(1)
        with self.i2c_device as i2c:
            i2c.write_then_read(bytes([reg]), buffer)
        return buffer[0]

    def _read_register_32(self, reg):
        """Read 32-bit register (big-endian)."""
        buffer = bytearray(4)
        with self.i2c_device as i2c:
            i2c.write_then_read(bytes([reg]), buffer)
        return (buffer[0] << 24) | (buffer[1] << 16) | (buffer[2] << 8) | buffer[3]

    def _read_register_float(self, reg):
        """Read 32-bit float register (big-endian)."""
        buffer = bytearray(4)
        with self.i2c_device as i2c:
            i2c.write_then_read(bytes([reg]), buffer)
        return struct.unpack('>f', buffer)[0]  # '>f' = big-endian float
```

**Key Patterns**:
- Use `adafruit_bus_device.i2c_device.I2CDevice` for I2C abstraction
- `with self.i2c_device as i2c:` pattern for automatic locking
- `struct.unpack()` for endianness handling
- Error handling with try-except

### Step 3: Create MQTT Firmware

```python
# firmware/sensor_node/code.py

import board
import busio
import time
import json
import os
from digitalio import DigitalInOut
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# Import sensor driver
import sys
sys.path.append('/lib')
from dfrobot_rainfall import DFRobot_RainfallSensor

# Configuration from settings.toml
HOUSE_ID = os.getenv("HOUSE_ID", "h1")
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.10")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
STATIC_IP = tuple(map(int, os.getenv("STATIC_IP", "192.168.1.70").split(".")))
SUBNET = tuple(map(int, os.getenv("SUBNET", "255.255.255.0").split(".")))
GATEWAY = tuple(map(int, os.getenv("GATEWAY", "192.168.1.1").split(".")))
DNS = tuple(map(int, os.getenv("DNS", "8.8.8.8").split(".")))

# MQTT topics
TOPIC_BASE = f"greenhouse/{HOUSE_ID}/rainfall"
TOPIC_AMOUNT = f"{TOPIC_BASE}/amount"
TOPIC_STATUS = f"{TOPIC_BASE}/status"

# Hardware initialization
print("Initializing W5500 Ethernet...")
cs = DigitalInOut(board.GP17)
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
eth = WIZNET5K(spi, cs, is_dhcp=False)
eth.ifconfig = (STATIC_IP, SUBNET, GATEWAY, DNS)
socket.set_interface(eth)

print("Initializing I2C sensor...")
i2c = busio.I2C(board.GP5, board.GP4)  # SCL, SDA
sensor = DFRobot_RainfallSensor(i2c, address=0x1D)

if not sensor.begin():
    raise RuntimeError("Sensor init failed")

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT (RC: {rc})")
    client.publish(TOPIC_STATUS, "online", retain=True)

def on_disconnect(client, userdata, rc):
    print(f"Disconnected (RC: {rc})")

# MQTT client
mqtt_client = MQTT.MQTT(
    broker=MQTT_BROKER,
    port=MQTT_PORT,
    socket_pool=socket,
    keep_alive=60
)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.will_set(TOPIC_STATUS, "offline", retain=True)

# Connect
mqtt_client.connect()

# Publish Home Assistant Discovery
def publish_ha_discovery():
    config = {
        "name": f"{HOUSE_ID.upper()} Rainfall",
        "state_topic": TOPIC_AMOUNT,
        "unit_of_measurement": "mm",
        "device_class": "precipitation",
        "value_template": "{{ value_json.amount_mm }}",
        "unique_id": f"{HOUSE_ID}_rainfall",
        "device": {
            "identifiers": [f"{HOUSE_ID}_rainfall_sensor"],
            "name": f"{HOUSE_ID.upper()} Rainfall Sensor",
            "model": "DFRobot SEN0575",
            "manufacturer": "DFRobot"
        }
    }
    mqtt_client.publish(f"homeassistant/sensor/{HOUSE_ID}_rainfall/config", json.dumps(config), retain=True)

publish_ha_discovery()

# Main loop
PUBLISH_INTERVAL = 600  # 10 minutes
last_publish = time.monotonic()

while True:
    try:
        mqtt_client.loop()

        if time.monotonic() - last_publish >= PUBLISH_INTERVAL:
            rainfall = sensor.get_rainfall()
            count = sensor.get_raw_data()

            payload = json.dumps({
                "timestamp": time.localtime(),
                "amount_mm": round(rainfall, 2),
                "count": count
            })

            mqtt_client.publish(TOPIC_AMOUNT, payload)
            last_publish = time.monotonic()

        time.sleep(1)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
```

### Step 4: Generate Configuration Files

**settings.toml**:
```toml
# Device identification
HOUSE_ID = "h1"

# Network (Static IP)
STATIC_IP = "192.168.1.70"
SUBNET = "255.255.255.0"
GATEWAY = "192.168.1.1"
DNS = "8.8.8.8"

# MQTT Broker
MQTT_BROKER = "192.168.1.10"
MQTT_PORT = "1883"

# Sensor I2C Address
SENSOR_I2C_ADDR = "0x1D"

# Publish interval (seconds)
PUBLISH_INTERVAL = "600"
```

### Step 5: Write Documentation

**README.md Template**:
```markdown
# Sensor Node - MQTT Version

## Hardware Requirements
- W5500-EVB-Pico-PoE
- [Sensor Name]
- Ethernet cable
- PoE injector (optional)

## Wiring
[ASCII diagram]

## Installation
1. Flash CircuitPython
2. Install libraries
3. Deploy firmware
4. Configure settings.toml

## MQTT Topics
- `greenhouse/{house_id}/sensor/value`
- `greenhouse/{house_id}/sensor/status`

## Home Assistant Integration
Auto-discovered via MQTT Discovery.

## Troubleshooting
[Common issues and solutions]
```

---

## Design Patterns

### 1. I2C Driver Patterns

#### adafruit_bus_device Usage
```python
from adafruit_bus_device.i2c_device import I2CDevice

class SensorDriver:
    def __init__(self, i2c, address):
        self.i2c_device = I2CDevice(i2c, address)

    def read_register(self, reg, length):
        buffer = bytearray(length)
        with self.i2c_device as i2c:  # Auto lock/unlock
            i2c.write_then_read(bytes([reg]), buffer)
        return buffer
```

#### Endianness Handling
```python
import struct

# Big-endian ('>') - most I2C sensors
def read_float_be(buffer):
    return struct.unpack('>f', buffer)[0]

def read_uint16_be(buffer):
    return (buffer[0] << 8) | buffer[1]

# Little-endian ('<')
def read_float_le(buffer):
    return struct.unpack('<f', buffer)[0]
```

### 2. MQTT Patterns

#### Last Will and Testament (LWT)
```python
mqtt_client.will_set(TOPIC_STATUS, "offline", retain=True)
```

#### Retained Status Messages
```python
mqtt_client.publish(TOPIC_STATUS, "online", retain=True)
```

#### Home Assistant MQTT Discovery
```python
config_topic = f"homeassistant/sensor/{unique_id}/config"
config_payload = {
    "name": "Sensor Name",
    "state_topic": "data/topic",
    "unit_of_measurement": "unit",
    "device_class": "temperature",  # or "humidity", "pressure", etc.
    "value_template": "{{ value_json.value }}",
    "unique_id": "unique_sensor_id",
    "device": {
        "identifiers": ["device_id"],
        "name": "Device Name",
        "model": "Model",
        "manufacturer": "Manufacturer"
    }
}
mqtt_client.publish(config_topic, json.dumps(config_payload), retain=True)
```

### 3. Network Patterns

#### W5500 Ethernet (Static IP)
```python
from digitalio import DigitalInOut
from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K
import adafruit_wiznet5k.adafruit_wiznet5k_socket as socket

cs = DigitalInOut(board.GP17)
spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
eth = WIZNET5K(spi, cs, is_dhcp=False)
eth.ifconfig = (STATIC_IP, SUBNET, GATEWAY, DNS)
socket.set_interface(eth)
```

#### WiFi (Pico 2 W)
```python
import wifi
import socketpool

wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
pool = socketpool.SocketPool(wifi.radio)
```

---

## Common Sensor Conversion Patterns

### Temperature Sensors
```python
def celsius_to_fahrenheit(celsius):
    return celsius * 9/5 + 32

def celsius_to_kelvin(celsius):
    return celsius + 273.15
```

### CO2 Sensors
```python
def ppm_to_percent(ppm):
    return ppm / 10000.0
```

### Pressure Sensors
```python
def hpa_to_bar(hpa):
    return hpa / 1000.0

def hpa_to_altitude(hpa, sea_level_hpa=1013.25):
    """Calculate altitude from pressure (meters)."""
    return 44330 * (1 - (hpa / sea_level_hpa) ** (1/5.255))
```

---

## Testing Strategy

### 1. Driver Unit Test
```python
# Test I2C communication
i2c = busio.I2C(board.GP5, board.GP4)
sensor = MySensor(i2c, address=0x44)

assert sensor.begin() == True
value = sensor.read_value()
assert 0 <= value <= 100  # Range check
```

### 2. MQTT Integration Test
```bash
# Subscribe to topic
mosquitto_sub -h 192.168.1.10 -t 'greenhouse/+/sensor/#' -v

# Verify payload structure
# Expected: {"timestamp": "...", "value": 25.5}
```

### 3. Home Assistant Discovery Test
```bash
# Check discovery topic
mosquitto_sub -h 192.168.1.10 -t 'homeassistant/sensor/+/config' -v

# Verify entity appears in HA
```

---

## Skill Invocation Example

**User Request**:
> "Port the Adafruit SCD30 Arduino library to CircuitPython and create MQTT firmware for greenhouse CO2 monitoring."

**Skill Generates**:

1. **lib/scd30.py** - I2C driver with commands: start_measurement(), read_measurement(), set_interval()
2. **firmware/co2_node/code.py** - MQTT publishing every 60s to `greenhouse/h1/co2/ppm`
3. **firmware/co2_node/settings.toml** - Network and MQTT config
4. **firmware/co2_node/README.md** - Wiring (GP4/GP5 I2C), installation steps
5. **docs/SCD30_MQTT.md** - Architecture, calibration procedure, troubleshooting

**Home Assistant Result**:
- Entity: `sensor.h1_co2`
- Unit: `ppm`
- Device Class: `carbon_dioxide`

---

## References

- [CircuitPython I2C Guide](https://learn.adafruit.com/circuitpython-essentials/circuitpython-i2c)
- [adafruit_bus_device Documentation](https://docs.circuitpython.org/projects/busdevice/en/latest/)
- [MQTT Protocol Specification](https://mqtt.org/mqtt-specification/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [W5500-EVB-Pico-PoE Docs](https://docs.wiznet.io/Product/iEthernet/W5500/w5500-evb-pico)

---

## Best Practices

### Code Quality
1. **Type Hints**: Use Python type hints where possible (CircuitPython supports them)
2. **Docstrings**: Document all public methods
3. **Error Handling**: Wrap I2C operations in try-except
4. **Constants**: Define all magic numbers as named constants

### Maintainability
1. **Modular Design**: Separate sensor driver from firmware logic
2. **Configuration**: Use settings.toml for all configurable values
3. **Logging**: Use print() with structured prefixes (`[INFO]`, `[ERROR]`)
4. **Comments**: Explain non-obvious I2C commands with datasheet references

### Performance
1. **Avoid Blocking**: Use `time.sleep()` sparingly in main loop
2. **Sensor Delays**: Respect sensor measurement times (e.g., SCD30 needs 2s)
3. **MQTT Keep-Alive**: Set appropriate keep_alive value (30-120s)

---

**Skill Author**: Arsprout Analysis Team
**Last Updated**: 2026-02-05
**License**: MIT
