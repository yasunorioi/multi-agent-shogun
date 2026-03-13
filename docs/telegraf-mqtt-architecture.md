# Telegraf MQTT Architecture Diagrams & Configuration Matrix

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGRICULTURE IoT SYSTEM                           │
└─────────────────────────────────────────────────────────────────────────┘

                          SENSOR TIER (Distributed)
                          ══════════════════════════
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  House h01   │  │  House h02   │  │  House h03   │  │   Farm       │
│              │  │              │  │              │  │   Weather    │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │
│ │Temp Sens │ │  │ │Temp Sens │ │  │ │Temp Sens │ │  │ │Misol     │ │
│ │(DS18B20) │ │  │ │(DS18B20) │ │  │ │(DS18B20) │ │  │ │Station   │ │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │
│              │  │              │  │              │  │              │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │              │
│ │8Ch Relay │ │  │ │8Ch Relay │ │  │ │8Ch Relay │ │  │              │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │              │
│              │  │              │  │              │  │              │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │  │              │
│ │8Ch DI    │ │  │ │8Ch DI    │ │  │ │8Ch DI    │ │  │              │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │                │
        └──────────────────┼──────────────────┼────────────────┘
                           │ MQTT Publish    │
                           │ (JSON Payload)  │
                           ▼
                    ┌──────────────┐
                    │  Mosquitto   │
                    │ MQTT Broker  │
                    │ tcp:// :1883 │
                    └──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │ Subscribe to:    │                  │
        │ - agriha/+/...   │ MQTT Wildcards   │
        │ - agriha/farm/...|                  │
        │ - agriha/daemon/ │                  │
        ▼                  ▼                  ▼

              INTEGRATION & PROCESSING TIER
              ════════════════════════════════
        ┌──────────────────────────────────┐
        │  Telegraf MQTT Consumer Plugin   │
        ├──────────────────────────────────┤
        │ Topics: [multiple with wildcards]│
        │ QoS: 1 (At Least Once)           │
        │ Data Format: JSON                │
        ├──────────────────────────────────┤
        │ Topic Parsing:                   │
        │ - agriha/{h_id}/sensor/{metric}  │
        │   → tags: house_id, metric       │
        │                                  │
        │ - agriha/{h_id}/di/{circuit}     │
        │   → tags: house_id, circuit      │
        │                                  │
        │ - agriha/farm/weather/misol      │
        │   → tags: station                │
        │                                  │
        │ JSON Parsing:                    │
        │ - json_query: (empty)            │
        │ - tag_keys: [device_id, ...]     │
        │ - json_string_fields: [version]  │
        └──────────────────────────────────┘
                           │
                    Write Metrics
                   (InfluxDB Line
                    Protocol)
                           │
                           ▼
        ┌──────────────────────────────────┐
        │    InfluxDB v2.x Time-Series DB  │
        ├──────────────────────────────────┤
        │ Bucket: agriculture              │
        │                                  │
        │ Measurements:                    │
        │ - sensor (temperature)           │
        │ - weather (wind, rain, humid)    │
        │ - relay (relay states)           │
        │ - di (digital inputs)            │
        │ - daemon (system metrics)        │
        │                                  │
        │ Tags: house_id, circuit, metric..│
        │ Fields: value, temp, humidity...  │
        └──────────────────────────────────┘
                           │
                    Query/Analyze
                           │
                    ┌──────┴──────┐
                    ▼             ▼
            ┌──────────────┐ ┌──────────────┐
            │ Dashboards   │ │ Applications │
            │ (Grafana)    │ │ (API calls)  │
            │ (custom UI)  │ │              │
            └──────────────┘ └──────────────┘
```

---

## Data Flow Diagram: Single Message Example

```
IoT Device (h01 temperature sensor)
         │
         │ MQTT Publish
         │ Topic: agriha/h01/sensor/DS18B20
         │ Payload: {"value": 22.5, "device_id": "DS001"}
         │
         ▼
    Mosquitto Broker
         │
         │ Telegraf Subscribed
         │ (via wildcard: agriha/+/sensor/DS18B20)
         │
         ▼
    Telegraf mqtt_consumer Plugin
         │
         ├─ Topic Parsing:
         │  ├─ Topic Pattern: agriha/house_id/sensor/metric
         │  ├─ Actual Topic: agriha/h01/sensor/DS18B20
         │  └─ Extract Tags: house_id=h01, metric=DS18B20
         │
         ├─ JSON Parsing:
         │  ├─ Payload: {"value": 22.5, "device_id": "DS001"}
         │  ├─ Field: value=22.5
         │  └─ Tag: device_id=DS001 (from tag_keys)
         │
         └─ Combine:
            measurement = "sensor" (from topic_parsing)
            tags = {house_id=h01, metric=DS18B20, device_id=DS001}
            fields = {value=22.5}
            timestamp = now()
         │
         ▼
    InfluxDB Line Protocol
    ┌────────────────────────────────────────────────────────────────┐
    │ sensor,house_id=h01,metric=DS18B20,device_id=DS001 \           │
    │ value=22.5 1645350000000000000                                │
    └────────────────────────────────────────────────────────────────┘
         │
         ▼
    InfluxDB Write
         │
         ▼
    Query: SELECT * FROM sensor WHERE house_id='h01' AND time > now()-1h
         │
         ▼
    Dashboard/Application
```

---

## Topic Mapping & Parsing Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TOPIC → TAG MAPPING MATRIX                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────┬──────────────────────┬──────────────────┐
│ MQTT Topic Pattern               │ Topic Parsing Rule   │ Result Tags      │
├──────────────────────────────────┼──────────────────────┼──────────────────┤
│ agriha/{house_id}/sensor/        │ agriha/house_id/     │ house_id         │
│ {metric}                         │ sensor/metric        │ metric           │
│                                  │ → sensor             │ measurement:     │
│ Example:                         │ measurement          │ sensor           │
│ agriha/h01/sensor/DS18B20        │ = "sensor"           │                  │
│                                  │ tags = [house_id,    │ Example:         │
│                                  │         metric]      │ h01, DS18B20     │
├──────────────────────────────────┼──────────────────────┼──────────────────┤
│ agriha/farm/weather/misol        │ agriha/_/weather/    │ station          │
│                                  │ station              │ measurement:     │
│ (fixed location)                 │ → weather            │ weather          │
│                                  │ measurement          │                  │
│                                  │ = "weather"          │ Example:         │
│                                  │ tags = "station"     │ misol            │
├──────────────────────────────────┼──────────────────────┼──────────────────┤
│ agriha/{house_id}/relay/state    │ agriha/house_id/     │ house_id         │
│                                  │ relay/state          │ measurement:     │
│ Example:                         │ → relay              │ relay            │
│ agriha/h02/relay/state           │ measurement          │                  │
│                                  │ = "relay"            │ Example:         │
│                                  │ tags = "house_id"    │ h02              │
├──────────────────────────────────┼──────────────────────┼──────────────────┤
│ agriha/{house_id}/di/{circuit}   │ agriha/house_id/     │ house_id         │
│                                  │ di/circuit           │ circuit          │
│ Example:                         │ → di                 │ measurement:     │
│ agriha/h01/di/ch5                │ measurement          │ di               │
│                                  │ = "di"               │                  │
│                                  │ tags = [house_id,    │ Example:         │
│                                  │         circuit]     │ h01, ch5         │
├──────────────────────────────────┼──────────────────────┼──────────────────┤
│ agriha/daemon/status             │ agriha/daemon/       │ (none)           │
│                                  │ status               │ measurement:     │
│ (no tags from topic)             │ → daemon             │ daemon           │
│                                  │ measurement          │                  │
│                                  │ = "daemon"           │ Example:         │
│                                  │ tags = []            │ (no topic tags)  │
└──────────────────────────────────┴──────────────────────┴──────────────────┘

Key:
{variable} = Topic segment extracted and assigned a name
_          = Topic segment ignored (placeholder)
→          = Configuration arrow (what rule matches)
```

---

## JSON Parsing Scenarios Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    JSON PAYLOAD PARSING SCENARIOS                           │
└─────────────────────────────────────────────────────────────────────────────┘

Scenario 1: Simple Flat JSON
─────────────────────────────

Input Payload:
{"value": 22.5, "unit": "celsius", "battery": 85}

Configuration:
data_format = "json"
json_query = ""
tag_keys = []
json_string_fields = []

Result:
measurement value=22.5,unit="celsius",battery=85


Scenario 2: JSON with Tag Keys
────────────────────────────────

Input Payload:
{"value": 22.5, "device_id": "DS001", "location": "greenhouse"}

Configuration:
data_format = "json"
tag_keys = ["device_id", "location"]

Result:
measurement,device_id=DS001,location=greenhouse value=22.5


Scenario 3: Nested JSON (extract with json_query)
──────────────────────────────────────────────────

Input Payload:
{
  "metadata": {"timestamp": 1645350000},
  "data": {
    "sensors": [
      {"type": "temperature", "value": 22.5},
      {"type": "humidity", "value": 65}
    ]
  }
}

Configuration (for first sensor):
data_format = "json"
json_query = "data.sensors.0"
tag_keys = ["type"]

Result:
measurement,type=temperature value=22.5


Scenario 4: String Fields (Prevent Number Conversion)
──────────────────────────────────────────────────────

Input Payload:
{"version": "1.2.3", "serial": "001234", "status": "200"}

Configuration:
data_format = "json"
json_string_fields = ["version", "serial", "status"]

Result (Correct):
measurement version="1.2.3",serial="001234",status="200"

Without json_string_fields:
measurement version=1.2,serial=1234,status=200  ← WRONG! Truncated to numbers


Scenario 5: Complex Multi-Field Sensor
───────────────────────────────────────

Input Payload:
{
  "temperature": 18.5,
  "humidity": 65,
  "wind_speed": 3.2,
  "wind_direction": 245,
  "rain_rate": 0.5,
  "device_id": "MISOL001",
  "location": "farm",
  "uptime": 86400
}

Configuration:
data_format = "json"
tag_keys = ["device_id", "location"]
json_string_fields = []

Result:
measurement,device_id=MISOL001,location=farm \
  temperature=18.5,humidity=65,wind_speed=3.2,wind_direction=245,rain_rate=0.5,uptime=86400
```

---

## Configuration Decision Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  WHEN TO USE WHICH CONFIGURATION                           │
└─────────────────────────────────────────────────────────────────────────────┘

Decision: Single vs Multiple [[inputs.mqtt_consumer]] Sections
════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│ ✓ USE SINGLE SECTION if:                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ • All topics from SAME MQTT broker                                         │
│ • All topics use SAME QoS level                                            │
│ • All topics use SAME data format (JSON)                                   │
│ • All topics have SAME JSON structure/parsing rules                        │
│ • You want to minimize MQTT connections                                    │
│                                                                             │
│ ADVANTAGES:                                                                │
│ • Single MQTT connection                                                   │
│ • Simpler configuration                                                    │
│ • Fewer resources                                                          │
│ • All topics get same reliable delivery (persistent session)               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ✓ USE MULTIPLE SECTIONS if:                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Topics from DIFFERENT MQTT brokers                                       │
│ • Topics require DIFFERENT QoS levels                                      │
│ • Topics have DIFFERENT data formats (JSON vs InfluxDB line protocol)      │
│ • Topics need DIFFERENT JSON parsing rules (different json_query paths)    │
│ • You need different output settings per section                           │
│                                                                             │
│ ADVANTAGES:                                                                │
│ • Fine-grained control per topic group                                     │
│ • Mix QoS 0 (fast, lossy) with QoS 2 (slow, guaranteed)                    │
│ • Different data formats in same Telegraf instance                         │
│ • Separate monitoring/troubleshooting per section                          │
│                                                                             │
│ TRADE-OFFS:                                                                │
│ • Multiple MQTT connections                                               │
│ • More complex configuration                                               │
│ • Higher resource usage                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

RECOMMENDED: Single section for agriha (agriculture) system
┌─────────────────────────────────────────────────────────────────────────────┐
│ [[inputs.mqtt_consumer]]                                                    │
│   servers = ["tcp://mosquitto:1883"]                                        │
│   topics = [                                                                │
│     "agriha/+/sensor/DS18B20",                                              │
│     "agriha/farm/weather/misol",                                            │
│     "agriha/+/relay/state",                                                 │
│     "agriha/+/di/+",                                                        │
│     "agriha/daemon/status"                                                  │
│   ]                                                                         │
│   data_format = "json"                                                      │
│   qos = 1                                                                   │
│   persistent_session = true                                                │
│   # ... all in one section                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## QoS Selection Guide

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          QoS SELECTION FLOWCHART                            │
└─────────────────────────────────────────────────────────────────────────────┘

START: What is the importance of this metric?
  │
  ├─→ CRITICAL (system state, must never lose)
  │   │
  │   └─→ QoS 2 (Exactly Once)
  │       │
  │       • Broker guarantees single delivery
  │       • Slower (3-way handshake)
  │       • Use with: Relay activation, pump state, alarms
  │       • Enable: persistent_session = true
  │
  ├─→ IMPORTANT (sensor reading, occasional loss is bad)
  │   │
  │   └─→ QoS 1 (At Least Once) ⭐ RECOMMENDED
  │       │
  │       • Broker guarantees delivery
  │       • May see duplicates on reconnect
  │       • Medium speed
  │       • Use with: Temperature, humidity, weather
  │       • Enable: persistent_session = true
  │       • Handle duplicates: Dedup in queries or InfluxDB
  │
  └─→ OPTIONAL (metrics are frequent, ok to lose some)
      │
      └─→ QoS 0 (At Most Once)
          │
          • Fire-and-forget, fastest
          • No ACK required
          • May lose messages
          • Use with: High-frequency metrics (1/sec), ok to lose 5%
          • persistent_session = false (has no effect)


RECOMMENDED for AGRIHA:
┌──────────────────────────────┐
│ qos = 1                      │
│ persistent_session = true    │
│                              │
│ • Reliable for sensors       │
│ • Recovers from interruptions│
│ • Acceptable duplicates      │
└──────────────────────────────┘
```

---

## Topic Structure Evolution

```
How the topic structure can evolve over time:

Generation 1 (Simple):
├─ agriha/h01/temperature
├─ agriha/h01/humidity
└─ agriha/h02/temperature

Generation 2 (Typed):
├─ agriha/h01/sensor/DS18B20
├─ agriha/h01/sensor/HTU21D
├─ agriha/h02/sensor/DS18B20
└─ agriha/farm/weather/misol

Generation 3 (Expanded):
├─ agriha/h01/sensor/DS18B20
├─ agriha/h01/relay/state
├─ agriha/h01/di/ch1
├─ agriha/h01/di/ch2
└─ agriha/farm/weather/misol

Generation 4 (Hierarchical):
├─ agriha/h01/sensor/DS18B20/greenhouse
├─ agriha/h01/sensor/DS18B20/outdoor
├─ agriha/h01/relay/irrigation/state
├─ agriha/h01/relay/heating/state
├─ agriha/h01/di/pump_outlet/pressure
├─ agriha/h01/di/water_level/tank1
└─ agriha/farm/weather/misol

Telegraf Configuration Adapts:
────────────────────────────

Gen 1-3: Topic patterns are exact matches
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric"

Gen 4: Can use variable-length with # (multi-level wildcard)
(Note: topic_parsing doesn't support # in pattern yet)
Workaround: Use separate topic_parsing rules for each depth
[[inputs.mqtt_consumer.topic_parsing]]
  topic = "agriha/house_id/sensor/metric/location"
  measurement = "sensor"
  tags = ["house_id", "metric", "location"]

OR match topics before they vary too much:
topics = [
  "agriha/+/sensor/+",      # All sensors (both with/without location)
  "agriha/+/relay/+",       # All relays
]
```

---

## Performance Expectations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXPECTED PERFORMANCE METRICS                           │
└─────────────────────────────────────────────────────────────────────────────┘

Message Rate Performance:

┌──────────────┬───────────────────┬──────────────────┬────────────────────┐
│ Rate (msg/s) │ QoS | Persistent   │ Memory Usage     │ CPU Load (Telegraf)│
├──────────────┼───────────────────┼──────────────────┼────────────────────┤
│ 1-10         │ 1   | yes          │ ~50-100 MB       │ <5%                │
│ 10-100       │ 1   | yes          │ ~100-200 MB      │ 5-10%              │
│ 100-1000     │ 1   | yes          │ ~200-500 MB      │ 10-30%             │
│ 1000+        │ 0   | no           │ ~100-200 MB      │ 20-50%             │
├──────────────┼───────────────────┼──────────────────┼────────────────────┤
│ With 50+ tags│ 1   | yes          │ +50-100 MB       │ +5-10%             │
│ Large JSON   │ 1   | yes          │ +100-500 MB      │ +5-15%             │
│ (64KB/msg)   │     |               │ (depends on msg) │                    │
└──────────────┴───────────────────┴──────────────────┴────────────────────┘

Latency (message receive → InfluxDB write):

QoS 0: ~100-500ms (fastest, may lose)
QoS 1: ~500-1000ms (with ACK overhead)
QoS 2: ~1000-2000ms (3-way handshake)
JSON parse overhead: +10-50ms (depends on JSON size/complexity)
Topic parsing: +1-5ms (very fast)
InfluxDB write: +50-500ms (depends on network, DB load)

Throughput:

Single MQTT connection can handle:
  - 1000+ topics with wildcards
  - 1000+ message/sec
  - 16KB average JSON payloads
  - Without degradation

Bottlenecks (in order of likelihood):
1. InfluxDB write latency (network, disk I/O)
2. MQTT broker capacity (QoS 2 with many clients)
3. JSON parsing (very large payloads, complex queries)
4. Telegraf output buffering (metric_batch_size too small)
```

---

## Scaling Considerations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCALING STRATEGIES                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Scenario 1: More Houses (10 → 100)
───────────────────────────────────

BEFORE (10 houses):
[[inputs.mqtt_consumer]]
  topics = ["agriha/+/sensor/DS18B20", ...]  # Wildcards handle all

AFTER (100 houses):
SAME CONFIGURATION WORKS!
The wildcard "+" already handles any number of houses
  • No changes needed
  • Same MQTT connection
  • Same Telegraf instance
  • Scales horizontally if needed (multiple Telegraf instances)


Scenario 2: More Sensor Types (1 → 10)
───────────────────────────────────────

BEFORE (DS18B20 only):
[[inputs.mqtt_consumer]]
  topics = ["agriha/+/sensor/DS18B20"]

AFTER (10 sensor types):
[[inputs.mqtt_consumer]]
  topics = [
    "agriha/+/sensor/DS18B20",
    "agriha/+/sensor/HTU21D",
    "agriha/+/sensor/BMP280",
    # ... etc
  ]

Or use wildcard:
[[inputs.mqtt_consumer]]
  topics = ["agriha/+/sensor/+"]  # Matches all sensor types


Scenario 3: High Message Rate (100 → 10,000 msg/sec)
──────────────────────────────────────────────────────

Single Telegraf Instance:
  Max sustainable: ~1000-2000 msg/sec (QoS 1)

If exceeding: Deploy multiple Telegraf instances

Config:
  Instance 1:
    topics = ["agriha/h01/+/+", "agriha/h02/+/+"]
    client_id = "telegraf_instance_1"

  Instance 2:
    topics = ["agriha/h03/+/+", "agriha/h04/+/+"]
    client_id = "telegraf_instance_2"

  Each writes to same InfluxDB bucket (no coordination needed)


Scenario 4: Multiple Locations (Farm A → Farm A + Farm B + Farm C)
──────────────────────────────────────────────────────────────────

Single MQTT Broker (local):
[[inputs.mqtt_consumer]]
  topics = ["agriha/+/+/+"]  # Matches all

If adding second farm (different MQTT broker):
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = ["agriha/+/+/+"]    # Farm A

[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto2:1883"]    # Different broker
  topics = ["orchard/+/+/+"]   # Farm B
  client_id = "telegraf_farm_b"

Both write to same InfluxDB with different tag values:
  agriha metrics: region=farm_a (from global_tags)
  orchard metrics: region=farm_b (from global_tags)
```

---

## Failure Recovery Scenarios

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FAILURE SCENARIOS & RECOVERY                             │
└─────────────────────────────────────────────────────────────────────────────┘

Scenario 1: Network Interruption (Telegraf ↔ MQTT Broker)
─────────────────────────────────────────────────────────

Timeline:
  T=0s:   Connection established, subscribing to topics
  T=5s:   Network down (e.g., router restart)
  T=10s:  Telegraf detects timeout (from keepalive ping)
  T=15s:  Telegraf reconnects (automatic)
  T=20s:  Persistent session active, undelivered messages redelivered
  T=25s:  Normal operation resumed

Recovery Configuration:
[[inputs.mqtt_consumer]]
  connection_timeout = "30s"    # Timeout for initial connect
  keepalive = 10                # Detect disconnect within 20s
  ping_timeout = "5s"           # Wait 5s for ping response
  persistent_session = true     # Resume undelivered messages
  client_id = "telegraf_agriha" # Stable ID (same across restarts)


Scenario 2: MQTT Broker Restart
───────────────────────────────

Timeline:
  T=0s:   Broker shutting down
  T=1s:   Telegraf disconnects (automatic)
  T=10s:  Broker comes back online
  T=15s:  Telegraf reconnects (via keepalive detection)
  T=20s:  Persistent session restores undelivered messages

Messages Published During Outage:
  - MQTT devices publish to offline broker (broker queues or drops)
  - When broker comes back: devices resend (depends on device QoS)
  - Telegraf resumes normal operation


Scenario 3: InfluxDB Write Failure
──────────────────────────────────

Timeline:
  T=0s:   InfluxDB network down or service restart
  T=5s:   Telegraf buffers metrics (metric_buffer_limit = 10000)
  T=30s:  Buffer fills up, metrics may be dropped (configurable)
  T=40s:  InfluxDB comes back online
  T=45s:  Telegraf resumes writing (fresh metrics only)

Lost Data:
  ✗ Metrics published while InfluxDB was down are lost
  ✓ MQTT broker still has them (persistent_session with QoS 1-2)
  ⚠ Cannot recover from MQTT broker: would require application-level retry

Mitigation:
  • Increase metric_buffer_limit if you expect long InfluxDB outages
  • Monitor InfluxDB health: curl http://influxdb:8086/health
  • Use multiple MQTT consumers → multiple InfluxDB clients (redundancy)


Scenario 4: Telegraf Crash & Restart
────────────────────────────────────

Timeline:
  T=0s:   Telegraf running normally
  T=10s:  Out-of-memory crash (OOM) or manual restart
  T=15s:  Telegraf process exits
  T=20s:  Systemd/supervisor restarts Telegraf
  T=25s:  Telegraf reconnects to MQTT broker
  T=30s:  Persistent session resumes (if client_id hasn't changed)

Message Recovery:
  ✓ QoS 1 + persistent_session: Broker resends undelivered messages
  ✓ Should be automatic, no data loss

Configuration:
[[inputs.mqtt_consumer]]
  persistent_session = true
  client_id = "telegraf_agriha"  # MUST BE STABLE (same after restart!)

⚠ WARNING: If you change client_id after crash, session is lost!


Recovery Checklist:
───────────────────
After any outage:

1. Verify MQTT broker status:
   mosquitto_sub -h mosquitto -t '$SYS/#' -v

2. Verify Telegraf connectivity:
   telegraf --config telegraf.conf --debug 2>&1 | grep mqtt

3. Check InfluxDB:
   curl http://influxdb:8086/health

4. Query for data gaps:
   from(bucket:"agriculture")
     |> range(start: -1h)
     |> group(columns: ["_measurement"])
     |> last()

5. Manual re-publish if needed:
   mosquitto_pub -t agriha/h01/sensor/DS18B20 -m '{"value":22.5}'
```

---

**Diagrams & matrices last updated:** 2026-02-21
**Version:** 1.0
