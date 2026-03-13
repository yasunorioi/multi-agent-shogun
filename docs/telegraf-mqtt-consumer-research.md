# Telegraf MQTT Consumer Plugin Configuration Guide

## Research Summary (2026-02-21)

This document provides best practices for configuring Telegraf's `mqtt_consumer` input plugin with focus on:
- Multiple MQTT topics with wildcards
- JSON payload parsing
- Topic path extraction to tags
- Measurement naming strategies
- QoS and reliability settings

## 1. Topic Wildcard Support

### Standard MQTT Wildcards

The `mqtt_consumer` plugin supports two types of wildcards:

| Wildcard | Level | Behavior | Example |
|----------|-------|----------|---------|
| `+` | Single-level | Matches exactly one topic segment | `agriha/+/sensor/DS18B20` matches `agriha/h01/sensor/DS18B20` |
| `#` | Multi-level | Matches 0 or more segments (must be last) | `agriha/farm/weather/#` matches all subtopics under weather |

### Example Topics for Your Use Case
```
# Single-level wildcard: subscribe to all houses' DS18B20 sensors
agriha/+/sensor/DS18B20

# Multi-level wildcard: subscribe to all relay topics
agriha/+/relay/#

# Multiple topics in single section
topics = [
  "agriha/+/sensor/DS18B20",
  "agriha/farm/weather/misol",
  "agriha/+/relay/state",
  "agriha/+/di/+",
  "agriha/daemon/status"
]
```

## 2. Topic Parsing: Extract Tags from Topic Path

Topic parsing allows you to extract structured data from the topic hierarchy instead of storing the entire topic path as a tag.

### Syntax
- **Named keys** (e.g., `house_id`, `metric_name`): Extract this segment as a tag or field
- **Underscore `_`**: Ignore this segment (placeholder)
- **Hash `#`**: Variable-length path (multi-segment, use only once per element type)

### Mapping to Line Protocol
```
measurement/tag1/tag2/field

measurement = metric from topic or configured static value
tags = structured data from topic segments
fields = values from payload
```

### Example: DS18B20 Temperature Sensor

**Topic Pattern:**
```
agriha/{house_id}/sensor/DS18B20
```

**Configuration:**
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["agriha/+/sensor/DS18B20"]
  data_format = "json"

  # Topic parsing: extract house_id and use 'temperature' as measurement
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/sensor/metric"
    measurement = "metric"        # DS18B20
    tags = "house_id"             # h01, h02, etc
    # fields would come from JSON payload (not from topic)
```

When receiving `agriha/h01/sensor/DS18B20` with payload `{"value": 22.5}`:
```
DS18B20,house_id=h01 value=22.5
```

### Example: Relay State with Multiple Channels

**Topic Pattern:**
```
agriha/{house_id}/relay/state
```

**Configuration:**
```toml
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/relay/state"
  measurement = "relay"
  tags = "house_id"
```

### Example: Digital Input with Circuit Number

**Topic Pattern:**
```
agriha/{house_id}/di/{circuit}
```

**Configuration:**
```toml
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/di/circuit"
  measurement = "di"
  tags = ["house_id", "circuit"]    # Multiple tags from topic
```

Result with topic `agriha/h01/di/ch1` and payload `{"state": 1}`:
```
di,house_id=h01,circuit=ch1 state=1
```

### Removing the Default Topic Tag

By default, the entire topic is stored as a tag. To disable this:
```toml
topic_tag = ""  # Remove the default topic tag
```

## 3. JSON Payload Parsing

### Configuration Options

| Option | Type | Purpose |
|--------|------|---------|
| `data_format` | string | Set to `"json"` for JSON payloads |
| `json_query` | string | GJSON query to extract specific fields from nested JSON |
| `tag_keys` | array | List of JSON keys to promote to tags (not fields) |
| `json_string_fields` | array | List of JSON keys to keep as strings (not numbers) |

### Simple JSON Parsing

**Configuration:**
```toml
data_format = "json"
tag_keys = ["device_id", "location"]  # These become tags, not fields
```

**Input Payload:**
```json
{
  "value": 22.5,
  "device_id": "DS001",
  "location": "greenhouse",
  "timestamp": 1645350000
}
```

**Output:**
```
measurement,device_id=DS001,location=greenhouse value=22.5,timestamp=1645350000
```

### Using json_query for Nested JSON

When your JSON has nested structures, use `json_query` to extract specific paths.

**Configuration:**
```toml
data_format = "json"
json_query = "data.sensors"    # Extract data.sensors from the payload
tag_keys = ["sensor_type"]
json_string_fields = ["model"]
```

**Input Payload:**
```json
{
  "timestamp": "2026-02-21T12:00:00Z",
  "data": {
    "sensors": [
      {
        "sensor_type": "temperature",
        "model": "DS18B20",
        "value": 22.5
      }
    ]
  }
}
```

**Output:**
```
measurement,sensor_type=temperature model="DS18B20",value=22.5
```

### String Fields (Preventing Numeric Conversion)

By default, numeric-looking values are converted to numbers. Use `json_string_fields` to keep them as strings:

**Configuration:**
```toml
json_string_fields = ["device_id", "model", "firmware_version"]
```

## 4. Measurement Naming Strategies

### Strategy 1: Topic-Derived Measurement (Recommended for Your Use Case)

Use topic parsing to extract the metric name:

```toml
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"
  measurement = "metric"  # DS18B20, HTU21D, etc become measurement names
  tags = "house_id"
```

**Pros:**
- Different sensor types have different measurements
- Clean separation of data types
- Easy to query by sensor type

**Cons:**
- Creates many measurement series if you have diverse sensors
- Requires consistent topic structure

### Strategy 2: Static Measurement with Sensor Tags

Use a fixed measurement name and extract sensor info as tags:

```toml
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"
  measurement = "sensor"      # All go to 'sensor' measurement
  tags = ["house_id", "metric"]
```

Result: `sensor,house_id=h01,metric=DS18B20 value=22.5`

**Pros:**
- Fewer measurement series
- Single query endpoint for all sensors
- Easier to run cross-sensor analytics

**Cons:**
- Less granular data organization

### Strategy 3: Hybrid Approach (Balanced)

Use topic parsing for major categories, static names for others:

```toml
# Sensors always go to 'sensor' measurement
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"
  measurement = "sensor"
  tags = ["house_id", "metric"]

# Relay states always go to 'relay' measurement
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/relay/state"
  measurement = "relay"
  tags = "house_id"

# Digital inputs always go to 'di' measurement
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/di/circuit"
  measurement = "di"
  tags = ["house_id", "circuit"]

# System metrics always go to 'daemon' measurement
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/daemon/status"
  measurement = "daemon"
  tags = []
```

**Result:** Clean, predictable measurements: `sensor`, `relay`, `di`, `daemon`

## 5. Multiple Topics vs Multiple Sections

### Single Section with Multiple Topics (Recommended)

**Advantages:**
- Single MQTT connection (fewer resources)
- All topics use same QoS, JSON parser settings, connection timeout
- Simpler configuration
- Shared client_id for persistent session

**Configuration:**
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "agriha/+/sensor/DS18B20",
    "agriha/farm/weather/misol",
    "agriha/+/relay/state",
    "agriha/+/di/+",
    "agriha/daemon/status"
  ]
  data_format = "json"
  qos = 1
  persistent_session = true
  client_id = "telegraf_agriha_main"

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/sensor/metric"
    measurement = "sensor"
    tags = ["house_id", "metric"]
  # ... more topic parsing rules
```

### Multiple Sections (When Needed)

Create separate `[[inputs.mqtt_consumer]]` sections only when:

1. **Different MQTT servers**
   ```toml
   [[inputs.mqtt_consumer]]
     servers = ["tcp://mqtt-server1:1883"]
     topics = ["farm/+/sensor/#"]

   [[inputs.mqtt_consumer]]
     servers = ["tcp://mqtt-server2:1883"]
     topics = ["house/+/sensor/#"]
   ```

2. **Different data formats for different topics**
   ```toml
   [[inputs.mqtt_consumer]]
     topics = ["agriha/+/sensor/+"]
     data_format = "json"

   [[inputs.mqtt_consumer]]
     topics = ["agriha/daemon/raw"]
     data_format = "line"
   ```

3. **Different QoS requirements**
   ```toml
   [[inputs.mqtt_consumer]]
     topics = ["critical/+/state"]
     qos = 2  # Exactly once

   [[inputs.mqtt_consumer]]
     topics = ["metrics/+/value"]
     qos = 0  # At most once
   ```

4. **Different JSON parsing rules**
   ```toml
   [[inputs.mqtt_consumer]]
     topics = ["sensor/temperature/+"]
     json_query = "temp_data"

   [[inputs.mqtt_consumer]]
     topics = ["weather/+/misol"]
     json_query = "weather_info"
   ```

## 6. Quality of Service (QoS) and Reliability

### QoS Levels

| Level | Name | Guarantee | Use Case |
|-------|------|-----------|----------|
| 0 | At most once | No guarantee | High-frequency metrics (ok to lose some) |
| 1 | At least once | Delivered, may duplicate | Most sensors (temperature, humidity) |
| 2 | Exactly once | Delivered exactly once | Critical state changes (relay activation) |

### Configuration for Reliability

```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]

  # Quality of Service
  qos = 1                           # At least once delivery

  # Persistent Sessions (for QoS 1 or 2)
  persistent_session = true         # Resume undelivered messages on reconnect
  client_id = "telegraf_agriha"     # Stable client ID for session resumption

  # Connection Management
  connection_timeout = "30s"        # Initial connection timeout
  keepalive = 10                    # Keep-alive interval (seconds, min 1)
  ping_timeout = "5s"               # Timeout for ping response

  # Message Buffering
  max_undelivered_messages = 100    # How many messages to buffer (default 1000)
```

### Persistent Session Explanation

When `persistent_session = true`:
1. MQTT broker stores client state using `client_id`
2. If Telegraf disconnects, unacknowledged messages (QoS 1-2) are stored
3. Upon reconnection with same `client_id`, broker resends unacknowledged messages
4. **Important:** Use a **stable, unique** `client_id` across restarts

**Example for multiple Telegraf instances:**
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  persistent_session = true
  client_id = "telegraf_agriha_instance1"  # Change per instance

[[inputs.mqtt_consumer]]
  servers = ["tcp://mqtt-backup:1883"]
  persistent_session = true
  client_id = "telegraf_agriha_instance2"  # Different ID
```

## 7. Concrete Configuration Example for Your Use Case

Here's a complete, production-ready configuration for your agriculture IoT system:

```toml
# ============================================================================
# MQTT Consumer: Agriculture IoT Data Ingestion
# ============================================================================
#
# Topics:
# - agriha/{house_id}/sensor/DS18B20      → Temperature
# - agriha/farm/weather/misol             → Weather (multiple fields)
# - agriha/{house_id}/relay/state         → 8-channel relay states
# - agriha/{house_id}/di/{circuit}        → Digital inputs
# - agriha/daemon/status                  → System status
#
# Features:
# - Topic parsing extracts house_id, circuit, sensor type
# - JSON payload parsing for nested data
# - QoS 1 for reliable delivery with persistent sessions
# - Automatic tag promotion from JSON keys
# ============================================================================

[[inputs.mqtt_consumer]]
  # ---- MQTT Server Configuration ----
  servers = ["tcp://mosquitto:1883"]

  # List of topics to subscribe to (wildcards: + = single level, # = multi-level)
  # Using wildcards reduces configuration needed for multiple houses
  topics = [
    "agriha/+/sensor/DS18B20",     # All houses' temperature sensor
    "agriha/farm/weather/misol",   # Farm weather data
    "agriha/+/relay/state",        # All houses' relay states
    "agriha/+/di/+",               # All houses' digital inputs (all circuits)
    "agriha/daemon/status"         # System daemon status
  ]

  # ---- Data Format Configuration ----
  # All payloads from these topics are JSON
  data_format = "json"

  # For deeply nested JSON, use json_query with GJSON syntax
  # Example: json_query = "data.sensors.0" extracts first sensor from nested data
  # Leave empty to parse entire payload as JSON
  json_query = ""

  # JSON keys that should become tags (not fields)
  # Tags: indexed, queryable, typically IDs or categories
  # Fields: values (numbers, strings), time-series data
  tag_keys = ["device_id", "device_type", "model"]

  # JSON keys that should remain as strings (not converted to numbers)
  # Useful for values that look numeric but should be strings (firmware versions, codes)
  json_string_fields = ["firmware_version", "device_model", "status_code"]

  # ---- Topic Parsing: Extract Structure from Topic Hierarchy ----
  # Syntax: Use segment names for extraction, "_" for ignored segments, "#" for variable-length
  # Result: Topic data becomes tags, not stored as literal topic string

  # Temperature Sensor: agriha/{house_id}/sensor/{metric}
  # Extract house_id as tag, metric name becomes measurement name
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/sensor/metric"
    measurement = "sensor"      # Measurement: temperature sensor
    tags = ["house_id", "metric"]    # Tags: which house, which metric (DS18B20)

  # Weather Station: agriha/farm/weather/misol
  # Static measurement name with source tag
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/_/weather/station"
    measurement = "weather"
    tags = "station"            # station=misol

  # Relay State: agriha/{house_id}/relay/state
  # Extract house_id as tag
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/relay/state"
    measurement = "relay"
    tags = "house_id"

  # Digital Input: agriha/{house_id}/di/{circuit}
  # Extract both house_id and circuit number as tags
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/di/circuit"
    measurement = "di"
    tags = ["house_id", "circuit"]

  # System Daemon: agriha/daemon/status
  # No tag extraction from topic (all data in payload)
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/daemon/status"
    measurement = "daemon"
    tags = []

  # Remove the default topic tag to keep tags clean
  # (Without this, every metric would have "topic=/path/to/topic" tag)
  topic_tag = ""

  # ---- Reliability & Connection Settings ----
  # Quality of Service level:
  # 0 = at most once (fast, may lose messages)
  # 1 = at least once (recommended, may duplicate on reconnect)
  # 2 = exactly once (slower, guaranteed single delivery)
  qos = 1

  # Enable persistent session: resume delivery of unacknowledged messages
  # after reconnection. Critical for QoS 1-2 reliability.
  persistent_session = true

  # Unique client ID for session tracking. Must be stable across Telegraf restarts.
  # Each Telegraf instance should have unique client_id
  client_id = "telegraf_agriha_main"

  # Connection timeout for initial TCP connection
  connection_timeout = "30s"

  # Keep-alive interval: how often to ping broker (prevents idle disconnect)
  # Minimum value: 1 second
  keepalive = 10

  # Timeout for waiting on keep-alive response
  ping_timeout = "5s"

  # Maximum number of unacknowledged messages to buffer in memory
  # Higher = more buffering during network issues, more memory usage
  # Default 1000, reasonable for typical IoT scenarios
  max_undelivered_messages = 100

  # ---- Optional: TLS/SSL Security ----
  # Uncomment if your MQTT broker uses TLS
  # tls_ca = "/etc/telegraf/mosquitto-ca.crt"
  # tls_cert = "/etc/telegraf/telegraf.crt"
  # tls_key = "/etc/telegraf/telegraf.key"
  # insecure_skip_verify = false

  # ---- Optional: Authentication ----
  # Uncomment if your MQTT broker requires username/password
  # username = "telegraf"
  # password = "secure_password_here"
```

## 8. Payload Examples and Expected Output

### Temperature Sensor

**MQTT Topic:** `agriha/h01/sensor/DS18B20`

**JSON Payload:**
```json
{
  "value": 22.5,
  "unit": "celsius",
  "timestamp": 1645350000
}
```

**Output Line Protocol (InfluxDB):**
```
sensor,house_id=h01,metric=DS18B20 value=22.5,unit="celsius",timestamp=1645350000
```

### Weather Station

**MQTT Topic:** `agriha/farm/weather/misol`

**JSON Payload:**
```json
{
  "temperature": 18.5,
  "humidity": 65,
  "wind_speed": 3.2,
  "wind_direction": 245,
  "rain_rate": 0.5
}
```

**Output Line Protocol (InfluxDB):**
```
weather,station=misol temperature=18.5,humidity=65,wind_speed=3.2,wind_direction=245,rain_rate=0.5
```

### Relay State (8-channel)

**MQTT Topic:** `agriha/h02/relay/state`

**JSON Payload:**
```json
{
  "ch1": 1,
  "ch2": 0,
  "ch3": 1,
  "ch4": 0,
  "ch5": 0,
  "ch6": 1,
  "ch7": 0,
  "ch8": 0
}
```

**Output Line Protocol (InfluxDB):**
```
relay,house_id=h02 ch1=1,ch2=0,ch3=1,ch4=0,ch5=0,ch6=1,ch7=0,ch8=0
```

### Digital Input

**MQTT Topic:** `agriha/h01/di/ch5`

**JSON Payload:**
```json
{
  "state": 1,
  "edge": "rising",
  "timestamp": 1645350000
}
```

**Output Line Protocol (InfluxDB):**
```
di,house_id=h01,circuit=ch5 state=1,edge="rising",timestamp=1645350000
```

### System Daemon Status

**MQTT Topic:** `agriha/daemon/status`

**JSON Payload:**
```json
{
  "uptime_seconds": 86400,
  "messages_published": 5432,
  "errors": 0,
  "heap_used_bytes": 524288,
  "version": "1.2.3"
}
```

**Output Line Protocol (InfluxDB):**
```
daemon uptime_seconds=86400,messages_published=5432,errors=0,heap_used_bytes=524288,version="1.2.3"
```

## 9. Troubleshooting Tips

### Issue: Topic Parsing Not Working

**Symptoms:** Topic appears as a tag, not extracted into separate tags

**Solutions:**
1. Verify topic pattern matches exactly (case-sensitive)
   ```
   Topic: "agriha/h01/sensor/DS18B20"
   Pattern: "agriha/house_id/sensor/metric"  # Must match segment count
   ```

2. Check if `topic_tag = ""` is set (removes default topic tag)

3. Verify you're receiving on a topic that matches a `topic_parsing` rule

### Issue: JSON Fields Not Parsed

**Symptoms:** Payload received but not split into fields

**Solutions:**
1. Verify `data_format = "json"` is set
2. Check JSON is valid: use `echo 'payload' | jq .` to validate
3. Use `json_query` if data is nested inside wrapper object

### Issue: Duplicate Messages on Reconnect

**Symptoms:** Same data appears multiple times in database

**Root Cause:** QoS 1 with persistent session - broker correctly re-delivers unacknowledged messages

**Solutions:**
1. Configure InfluxDB to handle duplicates (use unique tag combinations + timestamps)
2. Use deduplication in Telegraf output plugin
3. Accept small duplicates as cost of reliability (QoS 1/2)

### Issue: High Memory Usage

**Symptoms:** Telegraf consumes excessive RAM

**Solutions:**
1. Reduce `max_undelivered_messages` (default 1000)
2. Check if messages are being written to output (lag = high buffer)
3. Verify network connection to MQTT broker is stable
4. Monitor with `telegraf --debug` to see queue depth

## 10. Best Practices Summary

| Practice | Reason |
|----------|--------|
| Use single `[[inputs.mqtt_consumer]]` section with multiple topics | Fewer connections, simpler config |
| Use `+` and `#` wildcards | Reduces config as houses/sensors expand |
| Use topic parsing to extract structure | Cleaner tags, better queryability |
| Set `qos = 1` with `persistent_session = true` | Reliable delivery without messages loss |
| Use stable `client_id` | Enables session resumption |
| Set `topic_tag = ""` | Prevents redundant topic tags in database |
| Keep JSON payloads simple | Easier parsing, fewer GJSON edge cases |
| Use `tag_keys` for IDs, sensor types | Better query performance in InfluxDB |
| Use `json_string_fields` for codes/versions | Prevents unexpected numeric conversion |
| Test with `telegraf --test --config telegraf.conf` | Validate before deployment |

## Sources

- [MQTT Consumer Input Plugin - Telegraf Documentation](https://docs.influxdata.com/telegraf/v1/input-plugins/mqtt_consumer/)
- [MQTT Consumer Input Plugin - GitHub README](https://github.com/influxdata/telegraf/blob/master/plugins/inputs/mqtt_consumer/README.md)
- [MQTT Topic and Payload Parsing with Telegraf - InfluxData Blog](https://www.influxdata.com/blog/mqtt-topic-payload-parsing-telegraf/)
- [InfluxData Community Forums - MQTT Configuration Discussions](https://community.influxdata.com/t/)

---

**Last Updated:** 2026-02-21
**Author:** Claude Code (Research)
**Status:** Ready for production use
