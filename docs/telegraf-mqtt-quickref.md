# Telegraf MQTT Consumer Quick Reference

## Configuration Snippet: Minimal vs Full

### Minimal (Fast Start)
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["agriha/+/sensor/DS18B20"]
  data_format = "json"
  qos = 1
  persistent_session = true
  client_id = "telegraf_agriha"
```

### Full (Production)
```toml
[[inputs.mqtt_consumer]]
  # Connection
  servers = ["tcp://mosquitto:1883"]
  client_id = "telegraf_agriha_main"
  connection_timeout = "30s"
  keepalive = 10
  ping_timeout = "5s"

  # Topics
  topics = [
    "agriha/+/sensor/DS18B20",
    "agriha/farm/weather/misol",
    "agriha/+/relay/state",
    "agriha/+/di/+",
    "agriha/daemon/status"
  ]

  # Data Parsing
  data_format = "json"
  json_query = ""
  tag_keys = ["device_id", "device_type", "model", "status"]
  json_string_fields = ["firmware_version", "device_model", "status_code"]

  # Topic Parsing
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/sensor/metric"
    measurement = "sensor"
    tags = ["house_id", "metric"]

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/_/weather/station"
    measurement = "weather"
    tags = "station"

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/relay/state"
    measurement = "relay"
    tags = "house_id"

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/di/circuit"
    measurement = "di"
    tags = ["house_id", "circuit"]

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/daemon/status"
    measurement = "daemon"
    tags = []

  topic_tag = ""

  # Reliability
  qos = 1
  persistent_session = true
  max_undelivered_messages = 1000
```

---

## Wildcard Patterns Cheat Sheet

| Pattern | Matches | Example |
|---------|---------|---------|
| `agriha/h01/sensor/DS18B20` | Exact topic | Single house, single sensor |
| `agriha/+/sensor/DS18B20` | One segment varies | All houses' DS18B20 sensors |
| `agriha/h01/di/+` | Last segment varies | All channels of h01 digital inputs |
| `agriha/+/sensor/+` | Two segments vary | All houses' all sensors |
| `agriha/+/di/#` | Multi-level varies | All houses' all di topics (and subtopics) |
| `agriha/#` | Everything under agriha | All agriha topics |

---

## Topic Parsing Pattern Examples

### Before (Without Topic Parsing)
```
measurement,topic="agriha/h01/sensor/DS18B20" value=22.5
```

### After (With Topic Parsing)
```
sensor,house_id=h01,metric=DS18B20 value=22.5
```

### Pattern Syntax
```
Pattern:  agriha/house_id/sensor/metric
Actual:   agriha/h01/sensor/DS18B20
          ^^^^^^ ^^^ ^^^^^^ ^^^^^^^^
          └─────┬─────┘ └──────┬──────┘
                │             │
            Match static   Extract to tags
            "agriha"       house_id=h01
            "sensor"       metric=DS18B20
```

---

## JSON Parsing Examples

### Simple Flat JSON
```json
{"value": 22.5, "unit": "celsius"}
```

**Config:**
```toml
data_format = "json"
```

**Output:**
```
measurement value=22.5,unit="celsius"
```

### JSON with Tags
```json
{"value": 22.5, "device_id": "DS001", "location": "greenhouse"}
```

**Config:**
```toml
data_format = "json"
tag_keys = ["device_id", "location"]
```

**Output:**
```
measurement,device_id=DS001,location=greenhouse value=22.5
```

### Nested JSON (Use json_query)
```json
{
  "data": {
    "temperature": 22.5,
    "humidity": 65
  }
}
```

**Config:**
```toml
data_format = "json"
json_query = "data"
```

**Output:**
```
measurement temperature=22.5,humidity=65
```

### String Fields (Prevent Number Conversion)
```json
{"version": "1.2.3", "status": "200"}
```

**Config:**
```toml
data_format = "json"
json_string_fields = ["version", "status"]
```

**Output:**
```
measurement version="1.2.3",status="200"
```

---

## QoS Decision Tree

```
Is this critical data? (Relay activation, pump start, alarm)
├─ YES → QoS 2 (Exactly Once)
│         [Slower but guaranteed single delivery]
└─ NO → Is occasional data loss acceptable?
        ├─ YES → QoS 0 (At Most Once)
        │        [Fastest, fire-and-forget, may lose]
        └─ NO → QoS 1 (At Least Once)
               [Recommended for sensors - some duplicates ok]
               [Enable persistent_session for recovery]
```

---

## Common Configuration Patterns

### Pattern 1: Single House, Multiple Sensors
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["house/h01/+/+"]  # All sensors in h01

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "house/house_id/sensor_type/metric"
    measurement = "sensor"
    tags = ["house_id", "sensor_type", "metric"]
```

### Pattern 2: Multiple Houses, Same Sensor Types
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "agriha/+/sensor/temperature",
    "agriha/+/sensor/humidity",
    "agriha/+/relay/state"
  ]

  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "agriha/house_id/sensor/metric"
    measurement = "sensor"
    tags = ["house_id", "metric"]
```

### Pattern 3: Multiple MQTT Servers
```toml
# Server 1: Local sensors
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["local/+/+/+"]

# Server 2: Remote weather API
[[inputs.mqtt_consumer]]
  servers = ["tcp://weather-api:1883"]
  topics = ["weather/global/+"]
```

### Pattern 4: Different Parsing Rules per Topic
```toml
# JSON topics
[[inputs.mqtt_consumer]]
  topics = ["sensor/+/data"]
  data_format = "json"

# InfluxDB line protocol topics
[[inputs.mqtt_consumer]]
  topics = ["influx/+/write"]
  data_format = "influx"
```

---

## Troubleshooting Checklist

| Symptom | Check | Fix |
|---------|-------|-----|
| No metrics | Topics subscribe? | `telegraf --debug \| grep mqtt` |
| No metrics | JSON valid? | `echo '$payload' \| jq .` |
| Wrong tags | Topic pattern match? | Verify segment count and case |
| Memory growing | Output working? | `curl http://influxdb:8086/health` |
| Duplicates | QoS 1? | Expected; use dedup in query |
| No auth | Credentials? | Add `username` and `password` |
| TLS error | Cert path? | Verify `tls_ca`, `tls_cert`, `tls_key` |

---

## Testing Commands

```bash
# 1. Validate syntax
telegraf --config telegraf.conf --test

# 2. Start with debug output
telegraf --config telegraf.conf --debug

# 3. Send test message
mosquitto_pub -h mosquitto -t "agriha/h01/sensor/DS18B20" \
  -m '{"value": 22.5}'

# 4. Subscribe and watch
mosquitto_sub -h mosquitto -t "agriha/#" -v

# 5. Query InfluxDB
influx query 'from(bucket:"agriculture") |> range(start: -10m)'
```

---

## Performance Tuning

### For High Frequency (>100 msg/sec)
```toml
[agent]
  interval = "1s"               # Quick collection cycles
  metric_batch_size = 5000      # Larger batches
  metric_buffer_limit = 50000   # More buffer

[[inputs.mqtt_consumer]]
  max_undelivered_messages = 5000
  qos = 0                       # Less overhead
```

### For Low Frequency (<1 msg/sec)
```toml
[agent]
  interval = "30s"

[[inputs.mqtt_consumer]]
  max_undelivered_messages = 100
  qos = 1
  persistent_session = true     # Important for reliable delivery
```

### For Bandwidth-Constrained (Slow Network)
```toml
[agent]
  metric_batch_size = 100       # Smaller batches
  flush_interval = "30s"        # Less frequent writes

[[inputs.mqtt_consumer]]
  max_undelivered_messages = 50
  qos = 0                       # Accept some loss
  keepalive = 60                # Longer keep-alive
```

---

## Tag Cardinality Warning

High cardinality = many unique tag value combinations = database performance issues

**Bad (High Cardinality):**
```toml
tag_keys = ["timestamp", "raw_payload", "device_serial_number"]
# Creates millions of unique tag combinations
```

**Good (Low Cardinality):**
```toml
tag_keys = ["device_id", "house_id", "sensor_type"]
# Creates predictable, limited tag combinations
```

---

## Example Output Queries

### Flux (InfluxDB 2.x)
```sql
# Last 24 hours of sensor data
from(bucket:"agriculture")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "sensor" and r.house_id == "h01")

# Average temperature by hour
from(bucket:"agriculture")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "sensor" and r.metric == "DS18B20")
  |> aggregateWindow(every: 1h, fn: mean)
```

### InfluxQL (InfluxDB 1.x)
```sql
-- Last 24 hours of sensor data
SELECT * FROM sensor WHERE house_id = 'h01' AND time > now() - 24h

-- Average temperature by hour
SELECT MEAN(value)
FROM sensor
WHERE metric = 'DS18B20'
  AND time > now() - 7d
GROUP BY time(1h), house_id
```

---

## Environment-Specific Configs

### Development (localhost)
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://localhost:1883"]
  client_id = "telegraf_dev"
```

### Staging (Internal Network)
```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto-staging:1883"]
  client_id = "telegraf_staging"
  username = "telegraf_staging"
  password = "staging_password"
```

### Production (Secure)
```toml
[[inputs.mqtt_consumer]]
  servers = ["ssl://mosquitto-prod:8883"]
  client_id = "telegraf_prod"
  username = "telegraf_prod"
  password = "$MQTT_PASSWORD"  # Use environment variable
  tls_ca = "/etc/telegraf/ca.crt"
  tls_cert = "/etc/telegraf/client.crt"
  tls_key = "/etc/telegraf/client.key"
```

---

**Version:** 1.0
**Last Updated:** 2026-02-21
**Quick Links:** [Full Guide](telegraf-mqtt-consumer-research.md) | [Testing](telegraf-mqtt-testing-guide.md) | [Config Example](telegraf-agriha-mqtt.conf)
