# Telegraf MQTT Consumer Testing & Troubleshooting Guide

## Quick Reference: Testing Workflow

### 1. Validate Configuration Syntax
```bash
# Check configuration for errors (without starting Telegraf)
telegraf --config telegraf-agriha-mqtt.conf --test

# Expected output shows parsed metrics, NOT written to database
# Good sign: Metrics appear with correct field/tag structure
```

### 2. Start Telegraf in Foreground (Easy Debugging)
```bash
# Run with debug logging to see every MQTT message
telegraf --config telegraf-agriha-mqtt.conf --debug

# Watch for:
# - "Subscribed to topic: agriha/..."
# - "Parsing message: ..." with field counts
# - Any parse errors or connection issues
```

### 3. Send Test Messages from Another Terminal
```bash
# Publish temperature sensor reading
mosquitto_pub -h mosquitto -t "agriha/h01/sensor/DS18B20" \
  -m '{"value": 22.5, "unit": "celsius", "timestamp": 1645350000}'

# Publish weather data
mosquitto_pub -h mosquitto -t "agriha/farm/weather/misol" \
  -m '{"temperature": 18.5, "humidity": 65, "wind_speed": 3.2, "wind_direction": 245, "rain_rate": 0.5}'

# Publish relay state (8-channel)
mosquitto_pub -h mosquitto -t "agriha/h02/relay/state" \
  -m '{"ch1": 1, "ch2": 0, "ch3": 1, "ch4": 0, "ch5": 0, "ch6": 1, "ch7": 0, "ch8": 0}'

# Publish digital input
mosquitto_pub -h mosquitto -t "agriha/h01/di/ch5" \
  -m '{"state": 1, "edge": "rising", "timestamp": 1645350000}'

# Publish daemon status
mosquitto_pub -h mosquitto -t "agriha/daemon/status" \
  -m '{"uptime_seconds": 86400, "messages_published": 5432, "errors": 0, "heap_used_bytes": 524288, "version": "1.2.3"}'
```

### 4. Monitor Telegraf Output
Watch the terminal running Telegraf and verify:
- Messages are received: `[mqtt_consumer] ... topic=agriha/...`
- JSON parsed correctly: field counts match payload
- Topic parsing works: tags show `house_id=h01`, `metric=DS18B20` (not full topic)

### 5. Verify Data in InfluxDB
```bash
# Connect to InfluxDB CLI
influx

# List buckets
buckets

# List measurements in agriculture bucket
from(bucket:"agriculture")
  |> range(start: -1h)
  |> group(columns: ["_measurement"])
  |> distinct(column: "_measurement")

# Query sensor data for last hour
from(bucket:"agriculture")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor")

# Query specific house
from(bucket:"agriculture")
  |> range(start: -1h)
  |> filter(fn: (r) => r.house_id == "h01")
```

---

## Detailed Troubleshooting

### Problem: Telegraf Connects but Receives No Messages

**Symptoms:**
- Telegraf starts without errors
- MQTT broker shows connected
- But no metrics appear in InfluxDB
- Log shows: "Connected to MQTT broker" but no "parsing message" lines

**Root Causes & Solutions:**

#### 1. Wrong Topic Pattern
```bash
# Check what topics are actually being published
mosquitto_sub -h mosquitto -t '#' -v &

# Compare with telegraf.conf topics list
# Topics must match exactly (case-sensitive)
```

**Example Problem:**
```toml
# telegraf.conf
topics = ["agriha/+/sensor/DS18B20"]

# Actual MQTT messages published to:
"agriha/h01/Sensor/DS18B20"  # ❌ Capital S - won't match!
```

#### 2. Wildcard Misuse
```toml
# Wrong: Missing wildcard level
topics = ["agriha/sensor/DS18B20"]  # ❌ Missing house_id segment

# Correct: Use wildcard for variable segment
topics = ["agriha/+/sensor/DS18B20"]  # ✓

# Wrong: # must be last
topics = ["agriha/#/relay/state"]  # ❌ Can't have segments after #

# Correct: Use + for individual segments
topics = ["agriha/+/relay/+"]  # ✓
```

#### 3. Broker Authentication Issues
```bash
# Test MQTT connection manually
mosquitto_sub -h mosquitto -p 1883 -t 'agriha/#' -u username -P password -v

# If this fails, check credentials:
```

**Fix in telegraf.conf:**
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  username = "correct_username"
  password = "correct_password"
  # Verify these match broker configuration
```

#### 4. Protocol/Port Mismatch
```toml
# Common mistakes:
servers = ["http://mosquitto:1883"]   # ❌ Wrong protocol
servers = ["mqtt://mosquitto:8883"]   # ❌ Wrong port for unencrypted
servers = ["tcp://mosquitto:1883"]    # ✓ Correct for unencrypted
servers = ["ssl://mosquitto:8883"]    # ✓ Correct for TLS

protocol = "tcp"  # Match the scheme above
```

---

### Problem: JSON Parsing Fails

**Symptoms:**
- Metrics not appearing in database
- Log shows: `[mqtt_consumer] ... unable to parse message`
- Error mentions JSON parsing

**Root Causes & Solutions:**

#### 1. Invalid JSON Payload
```bash
# Test JSON validity
echo '{"value": 22.5, "status": "ok"' | jq .
# Error: parse error (missing closing brace)

# Correct JSON
echo '{"value": 22.5, "status": "ok"}' | jq .
# Success
```

**Fix:** Validate JSON before publishing to MQTT:
```python
# Python example
import json
payload = {"value": 22.5, "unit": "celsius"}
json_str = json.dumps(payload)  # This ensures valid JSON
mqtt_client.publish(topic, json_str)
```

#### 2. Wrong data_format Setting
```toml
# If payload is JSON but this is missing:
# ❌ data_format = "influx"  # Expects InfluxDB line protocol

# Fix:
# ✓ data_format = "json"    # Parse as JSON
```

#### 3. json_query Points to Wrong Path
```json
{
  "data": {
    "sensors": [
      {"value": 22.5}
    ]
  }
}
```

```toml
# Wrong: Points to array, not object
json_query = "data.sensors"      # ❌ This is an array!

# Correct: Point to the object
json_query = "data.sensors.0"    # ✓ First element
# OR if you have multiple sensors, handle differently
```

#### 4. Numeric Values Converted Unexpectedly
```json
{"firmware_version": "1.2.3"}
```

**Problem:** Might be converted to numeric if field contains numbers

**Fix:** Use `json_string_fields`:
```toml
json_string_fields = ["firmware_version", "device_model"]
```

**Before (wrong):**
```
measurement firmware_version=1.2 value=5  # Truncated to number!
```

**After (correct):**
```
measurement firmware_version="1.2.3" value=5
```

---

### Problem: Topic Parsing Not Working

**Symptoms:**
- Topic appears as literal tag: `topic="agriha/h01/sensor/DS18B20"`
- Topic parsing rules are in config but ignored
- Tags should be `house_id=h01, metric=DS18B20` but aren't

**Root Causes & Solutions:**

#### 1. Topic Pattern Doesn't Match
```toml
# Configuration
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"
  measurement = "sensor"
  tags = ["house_id", "metric"]

# Actual MQTT topic received
"agriha/h01/sensor/DS18B20/extra"  # ❌ Extra segment!
# Pattern expects 4 segments, but topic has 5
```

**Fix:** Make sure segment count matches:
```toml
# For variable-length topics, use # (multi-level wildcard)
# But topic_parsing doesn't support # in the pattern yet
# Workaround: Use separate topic_parsing rules for each length

# For 4-segment topics
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"
  ...

# For 5-segment topics (if they exist)
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric/extra"
  ...
```

#### 2. Case Sensitivity
```toml
# Configuration (lowercase)
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"

# Actual topic (uppercase)
"agriha/h01/Sensor/DS18B20"  # ❌ "Sensor" != "sensor"
```

**Fix:** Match case exactly:
```toml
topic = "agriha/house_id/Sensor/metric"
```

#### 3. Wrong Segment Name
```toml
# Configuration uses underscore for ignored segment
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/relay/state"
  # But actual topic is:
  # "agriha/h01/relay/state"

# If topic structure is different, pattern won't match
```

**Verify match manually:**
```
Pattern:      agriha  /  house_id  /  relay  /  state
Actual topic: agriha  /  h01       /  relay  /  state
              ✓         ✓           ✓         ✓
              Match!
```

#### 4. Default topic_tag Not Removed
```toml
# Without removing default tag:
# Output: measurement,topic="agriha/h01/sensor/DS18B20",house_id=h01,metric=DS18B20

# Add this to remove redundant topic tag:
topic_tag = ""

# Output: measurement,house_id=h01,metric=DS18B20
```

---

### Problem: Duplicate Messages Appearing in Database

**Symptoms:**
- Same metric appears multiple times
- Timestamps are identical or very close
- Happens after Telegraf restarts or network hiccups

**Root Cause:**
QoS 1 with persistent sessions re-delivers unacknowledged messages. This is **correct behavior**, not a bug.

**Solutions:**

#### 1. Accept as Normal Behavior
QoS 1 trades occasional duplicates for guaranteed delivery. This is the right tradeoff for sensor data.

**Note in your monitoring/alerting:**
```sql
-- InfluxQL: Handle duplicates by taking latest value
SELECT last("value")
FROM sensor
GROUP BY time(1m), *
```

#### 2. Deduplicate at Application Layer
```python
# In your time-series analysis
import pandas as pd
df = df.drop_duplicates(subset=['timestamp', 'measurement', 'house_id'], keep='last')
```

#### 3. Use Deduplication in Telegraf
```toml
# Telegraf input filters (advanced)
[[inputs.mqtt_consumer]]
  # ... config ...

# Stagger broker message delivery to different instances
client_id = "telegraf_instance_1"  # Unique per instance
```

---

### Problem: High Memory Usage / Messages Buffering

**Symptoms:**
- Telegraf RAM usage grows over time
- `max_undelivered_messages` not helping
- Performance degrades

**Root Causes & Solutions:**

#### 1. Slow Output to InfluxDB
```bash
# Check if InfluxDB is slow/unreachable
curl -v http://influxdb:8086/health

# If response is slow or fails:
# - Network latency issues
# - InfluxDB overloaded
# - Disk I/O bottleneck
```

**Fix:**
```toml
[[inputs.mqtt_consumer]]
  # Reduce buffer size to fail fast if output is slow
  max_undelivered_messages = 100

# OR increase InfluxDB capacity:
# - Add RAM to InfluxDB server
# - Optimize database schema
# - Reduce metric cardinality
```

#### 2. Too Many Unacknowledged Messages
```toml
[[inputs.mqtt_consumer]]
  qos = 1
  persistent_session = true

  # If broker is slow to ACK:
  max_undelivered_messages = 1000  # Too high for slow networks!

# Fix: Reduce for slower networks
  max_undelivered_messages = 100   # More conservative
```

#### 3. Message Burst
```bash
# Monitor message rate
mosquitto_sub -h mosquitto -t 'agriha/#' -v | wc -l

# If rate is 1000+ messages/second, consider:
# - Aggregating sensors (send once per 10s instead of 1s)
# - Adding output buffering
# - Increasing batch_size in [agent]
```

**Fix in telegraf.conf:**
```toml
[agent]
  interval = "30s"              # Less frequent collection
  metric_batch_size = 5000      # Larger batches
  metric_buffer_limit = 50000   # Higher buffer
```

---

## Test Data: Complete MQTT Payload Examples

### Example 1: Temperature Sensor with Metadata
```bash
mosquitto_pub -h mosquitto \
  -t "agriha/h01/sensor/DS18B20" \
  -m '{
    "value": 22.5,
    "unit": "celsius",
    "device_id": "DS001",
    "device_type": "temperature",
    "model": "DS18B20",
    "battery_level": 85,
    "rssi": -52,
    "timestamp": 1645350000
  }'
```

**Expected InfluxDB Output:**
```
sensor,house_id=h01,metric=DS18B20,device_id=DS001,device_type=temperature,model=DS18B20 \
  value=22.5,battery_level=85,rssi=-52,timestamp=1645350000
```

### Example 2: Weather Station (Multiple Fields)
```bash
mosquitto_pub -h mosquitto \
  -t "agriha/farm/weather/misol" \
  -m '{
    "temperature": 18.5,
    "humidity": 65,
    "wind_speed": 3.2,
    "wind_direction": 245,
    "rain_rate": 0.5,
    "pressure": 1013.25,
    "timestamp": 1645350000
  }'
```

**Expected InfluxDB Output:**
```
weather,station=misol \
  temperature=18.5,humidity=65,wind_speed=3.2,wind_direction=245,rain_rate=0.5,pressure=1013.25,timestamp=1645350000
```

### Example 3: Relay State (8-channel with state change log)
```bash
mosquitto_pub -h mosquitto \
  -t "agriha/h02/relay/state" \
  -m '{
    "ch1": 1,
    "ch2": 0,
    "ch3": 1,
    "ch4": 0,
    "ch5": 0,
    "ch6": 1,
    "ch7": 0,
    "ch8": 0,
    "last_change": "ch1_on",
    "uptime": 86400,
    "timestamp": 1645350000
  }'
```

**Expected InfluxDB Output:**
```
relay,house_id=h02 \
  ch1=1,ch2=0,ch3=1,ch4=0,ch5=0,ch6=1,ch7=0,ch8=0,uptime=86400,timestamp=1645350000,last_change="ch1_on"
```

### Example 4: Digital Input with Edge Detection
```bash
mosquitto_pub -h mosquitto \
  -t "agriha/h01/di/ch5" \
  -m '{
    "state": 1,
    "edge": "rising",
    "debounce_ms": 50,
    "timestamp": 1645350000,
    "circuit_name": "pump_outlet_pressure"
  }'
```

**Expected InfluxDB Output:**
```
di,house_id=h01,circuit=ch5 \
  state=1,debounce_ms=50,timestamp=1645350000,circuit_name="pump_outlet_pressure",edge="rising"
```

### Example 5: System Daemon Status
```bash
mosquitto_pub -h mosquitto \
  -t "agriha/daemon/status" \
  -m '{
    "uptime_seconds": 86400,
    "messages_published": 5432,
    "errors": 0,
    "heap_used_bytes": 524288,
    "version": "1.2.3",
    "cpu_percent": 12.5,
    "timestamp": 1645350000
  }'
```

**Expected InfluxDB Output:**
```
daemon \
  uptime_seconds=86400,messages_published=5432,errors=0,heap_used_bytes=524288,cpu_percent=12.5,timestamp=1645350000,version="1.2.3"
```

---

## Monitoring Telegraf Health

### Key Metrics to Watch

```bash
# View Telegraf internal metrics (if enabled)
from(bucket:"telegraf_system")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "internal_write")
  |> group(columns: ["_field"])
```

**Watch for:**
- `internal_write.influxdb_write_errors` → Should be 0
- `internal_gather.internal_gather_errors` → Should be 0
- `mqtt_consumer_messages_received` → Should grow over time
- `mqtt_consumer_publish_errors` → Should be 0 (or minimal)

### Telegraf Startup Checklist

```bash
# 1. Verify configuration
telegraf --config telegraf-agriha-mqtt.conf --test

# 2. Start Telegraf
systemctl start telegraf

# 3. Check systemd status
systemctl status telegraf
journalctl -u telegraf -f --lines=50

# 4. Verify MQTT connection
telegraf --config telegraf-agriha-mqtt.conf --debug 2>&1 | grep -i mqtt

# 5. Send test message and observe Telegraf debug output
mosquitto_pub -h mosquitto -t "agriha/h01/sensor/DS18B20" -m '{"value": 22.5}'

# 6. Query InfluxDB
influx query 'from(bucket:"agriculture") |> range(start: -10m) |> tail(n: 10)'
```

---

## InfluxQL Query Examples

### Query All Sensor Data for One House (Last Hour)
```sql
SELECT * FROM sensor WHERE house_id = 'h01' AND time > now() - 1h
```

### Average Temperature by House (Last Day)
```sql
SELECT MEAN(value)
FROM sensor
WHERE metric = 'DS18B20'
  AND time > now() - 24h
GROUP BY time(10m), house_id
```

### Relay State Changes (Last 24 Hours)
```sql
SELECT *
FROM relay
WHERE time > now() - 24h
  AND (ch1 != ch1_prev)  -- State change detection
ORDER BY time DESC
```

### System Uptime Trend
```sql
SELECT uptime_seconds
FROM daemon
WHERE time > now() - 7d
GROUP BY time(1h)
```

---

## References

- [Telegraf MQTT Consumer Plugin Documentation](https://docs.influxdata.com/telegraf/v1/input-plugins/mqtt_consumer/)
- [MQTT Topic Parsing with Telegraf](https://www.influxdata.com/blog/mqtt-topic-payload-parsing-telegraf/)
- [InfluxDB Query Language](https://docs.influxdata.com/influxdb/v2/query-data/influxql/)
- [mosquitto_pub/sub Manual](https://mosquitto.org/man/mosquitto_pub-1.html)

---

**Last Updated:** 2026-02-21
**Version:** 1.0
