---
description: >
  Generates Node-RED error detection and alert notification flows.
  Includes LWT offline detection, heartbeat timeout, threshold alerts, notification suppression.
  Use when: "error alert flow", "異常検知フロー", "Node-RED alert", "Node-REDアラート",
  "LWT detection", "LWT検知", "heartbeat monitor", "threshold alert", "アラート疲れ防止".
  Do NOT use for: timer/scheduler flows (use nodered-timer-flow-generator) or Node-RED setup (use nodered-setup-guide).
argument-hint: "[--house-id h1] [--nodes sensor01,drainage01] [--notify line|slack]"
---
# nodered-error-alert-flow-generator

Node-RED異常検知・通知フローを自動生成するスキル。
LWT検知、heartbeat監視、閾値超過、通知抑制ロジックを含む。

## 概要

IoTシステムにおける異常検知から通知までの一連のNode-REDフローを生成する。

**主な機能**:
- LWT（Last Will and Testament）によるノードオフライン検知
- Heartbeat監視によるタイムアウト検知
- センサー値の閾値超過検知
- 通知抑制ロジック（アラート疲れ防止）
- SQLiteログ保存
- LINE Notify連携

## 使用方法

```
/nodered-error-alert-flow-generator [オプション]
```

### オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--house-id` | ハウスID | h1 |
| `--nodes` | 監視対象ノード（カンマ区切り） | sensor01,drainage01 |
| `--broker` | MQTTブローカー | localhost:1883 |
| `--line-token` | LINE Notifyトークン | 環境変数から |
| `--db-path` | SQLiteパス | /data/greenhouse.db |
| `--night-mode` | 夜間抑制有効 | true |

---

## 1. 対応する異常検知パターン

### 1.1 LWT（Last Will and Testament）検知

**概要**: MQTTブローカーがノードの切断を検知し、自動的にofflineメッセージをpublishする。

**トピック**: `greenhouse/{house_id}/node/{node_id}/status`

**ペイロード**:
- `"offline"`: ノード切断
- `"online"`: ノード接続

**Node-REDフロー**:
```
[mqtt in] → [switch] → [function] → [LINE notify]
           offline?    重複排除
                       通知文生成
                           │
                           └→ [sqlite out]
```

**検知条件**:
- MQTTブローカーがノードとの接続断を検知
- ノード側がwill_setで設定したLWTメッセージが自動publish

### 1.2 Heartbeat監視

**概要**: ノードが定期的に送信するheartbeatが一定時間途切れた場合に異常と判定。

**トピック**: `greenhouse/{house_id}/node/{node_id}/heartbeat`

**ペイロード例**:
```json
{
  "timestamp": 1707184800,
  "uptime": 3600,
  "free_memory": 45000
}
```

**タイムアウト条件**:
- 120秒間heartbeatを受信しない場合

**Node-REDフロー**:
```
[mqtt in] → [function]        [inject] → [function]
heartbeat受信  最終受信時刻保存   30秒毎     タイムアウトチェック
                                              │
                                              └→ [LINE notify]
```

### 1.3 閾値超過検知

**概要**: センサー値が設定された閾値を超えた場合に異常と判定。

**監視対象**:
| センサー | トピック | 低閾値 | 高閾値 | 単位 |
|---------|---------|--------|--------|------|
| 温度 | `greenhouse/+/sensors/temperature` | 5 | 40 | ℃ |
| 湿度 | `greenhouse/+/sensors/humidity` | 30 | 95 | % |
| CO2 | `greenhouse/+/sensors/co2` | - | 3000 | ppm |

**Node-REDフロー**:
```
[mqtt in] → [function] → [switch] → [function] → [LINE notify]
センサー値     閾値チェック   異常あり?   通知文生成
                                            │
                                            └→ [sqlite out]
```

---

## 2. 通知抑制ロジック

アラート疲れを防ぐため、以下の通知抑制機能を実装。

### 2.1 重複排除

**目的**: 同一異常の連続通知を防止

**実装**:
```javascript
// 重複排除（5分以内の同一異常は無視）
const key = `${errorType}_${houseId}_${nodeId}`;
const lastAlert = flow.get(key) || 0;
const now = Date.now();

if (now - lastAlert < 5 * 60 * 1000) {
    node.warn(`重複排除: ${key}`);
    return null;
}
flow.set(key, now);
```

**パラメータ**:
- 抑制時間: 5分（設定可能）

### 2.2 エスカレーション

**目的**: 継続する異常に対して通知間隔を徐々に延長

**実装**:
```javascript
// エスカレーション間隔（分）: 0, 5, 15, 30, 60
const intervals = [0, 5, 15, 30, 60];
const escKey = `escalation_${houseId}_${nodeId}_${errorType}`;
const state = flow.get(escKey) || { count: 0, lastNotify: 0 };

const index = Math.min(state.count, intervals.length - 1);
const interval = intervals[index] * 60 * 1000;

if (state.count > 0 && (now - state.lastNotify) < interval) {
    return null; // 抑制中
}

state.count++;
state.lastNotify = now;
flow.set(escKey, state);
```

**エスカレーションスケジュール**:
| 回数 | 間隔 |
|------|------|
| 1回目 | 即時 |
| 2回目 | 5分後 |
| 3回目 | 15分後 |
| 4回目 | 30分後 |
| 5回目以降 | 60分毎 |

### 2.3 夜間通知抑制

**目的**: 深夜の不要な通知を抑制

**実装**:
```javascript
// 夜間チェック（22:00-06:00は高重要度のみ通知）
const hour = new Date().getHours();
const isNight = hour >= 22 || hour < 6;
const isHighSeverity = (severity === 'high');

if (isNight && !isHighSeverity) {
    node.warn(`夜間のため通知スキップ: ${errorType}`);
    return null;
}
```

**設定**:
- 夜間開始: 22:00
- 夜間終了: 06:00
- 夜間通知: 高重要度のみ

### 2.4 集約通知

**目的**: 中重要度の異常をまとめて通知

**実装**:
```javascript
// 集約バッファに追加
let pending = flow.get('pending_medium_alerts') || [];
pending.push({
    house_id: houseId,
    node_id: nodeId,
    type: errorType,
    message: message,
    timestamp: Date.now()
});
flow.set('pending_medium_alerts', pending);

// 1時間毎にinjectノードからトリガー → まとめて送信
```

**送信タイミング**: 1時間毎（設定可能）

---

## 3. フローテンプレート（Node-RED JSON）

### 3.1 完全なフロー構成

```json
[
    {
        "id": "error_alert_tab",
        "type": "tab",
        "label": "異常検知・通知フロー"
    }
]
```

### 3.2 LWT検知フロー

```json
[
    {
        "id": "mqtt_lwt_in",
        "type": "mqtt in",
        "name": "LWT受信",
        "topic": "greenhouse/+/node/+/status",
        "qos": "1",
        "broker": "mqtt_broker",
        "wires": [["lwt_check_offline"]]
    },
    {
        "id": "lwt_check_offline",
        "type": "switch",
        "name": "offline/online?",
        "property": "payload",
        "rules": [
            {"t": "eq", "v": "offline", "vt": "str"},
            {"t": "eq", "v": "online", "vt": "str"}
        ],
        "outputs": 2,
        "wires": [["lwt_offline_handler"], ["lwt_online_handler"]]
    },
    {
        "id": "lwt_offline_handler",
        "type": "function",
        "name": "オフライン処理",
        "func": "const parts = msg.topic.split('/');\nconst houseId = parts[1];\nconst nodeId = parts[3];\n\n// 重複排除（5分間）\nconst key = `offline_${houseId}_${nodeId}`;\nconst lastAlert = flow.get(key) || 0;\nconst now = Date.now();\n\nif (now - lastAlert < 5 * 60 * 1000) {\n    return null;\n}\nflow.set(key, now);\n\nconst timestamp = new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'});\nmsg.lineMessage = `🚨 ノード離脱\\nハウス: ${houseId}\\nノード: ${nodeId}\\n時刻: ${timestamp}`;\n\nmsg.error_log = {\n    timestamp: Math.floor(Date.now() / 1000),\n    house_id: houseId,\n    node_id: nodeId,\n    error_type: 'node_offline',\n    severity: 'high',\n    message: 'Node went offline'\n};\n\nreturn msg;",
        "wires": [["line_notify", "sqlite_log"]]
    }
]
```

### 3.3 Heartbeat監視フロー

```json
[
    {
        "id": "mqtt_heartbeat_in",
        "type": "mqtt in",
        "name": "heartbeat受信",
        "topic": "greenhouse/+/node/+/heartbeat",
        "qos": "0",
        "datatype": "json",
        "broker": "mqtt_broker",
        "wires": [["heartbeat_tracker"]]
    },
    {
        "id": "heartbeat_tracker",
        "type": "function",
        "name": "heartbeat追跡",
        "func": "const parts = msg.topic.split('/');\nconst houseId = parts[1];\nconst nodeId = parts[3];\nconst key = `hb_${houseId}_${nodeId}`;\n\nflow.set(key, Date.now());\n\n// エスカレーションリセット\nconst escKey = `escalation_${houseId}_${nodeId}_heartbeat_timeout`;\nflow.set(escKey, null);\n\nreturn null;",
        "wires": [[]]
    },
    {
        "id": "heartbeat_check_inject",
        "type": "inject",
        "name": "30秒毎チェック",
        "repeat": "30",
        "once": true,
        "onceDelay": "60",
        "wires": [["heartbeat_timeout_check"]]
    },
    {
        "id": "heartbeat_timeout_check",
        "type": "function",
        "name": "タイムアウトチェック",
        "func": "const nodes = global.get('monitored_nodes') || [\n    {house_id: 'h1', node_id: 'sensor01'}\n];\n\nconst now = Date.now();\nconst TIMEOUT_MS = 120 * 1000;\nconst alerts = [];\n\nfor (const node of nodes) {\n    const key = `hb_${node.house_id}_${node.node_id}`;\n    const lastHb = flow.get(key);\n    \n    if (!lastHb) continue;\n    \n    if (now - lastHb > TIMEOUT_MS) {\n        // エスカレーション管理\n        const escKey = `escalation_${node.house_id}_${node.node_id}_heartbeat_timeout`;\n        const state = flow.get(escKey) || { count: 0, lastNotify: 0 };\n        \n        const intervals = [0, 5, 15, 30, 60];\n        const index = Math.min(state.count, intervals.length - 1);\n        const interval = intervals[index] * 60 * 1000;\n        \n        if (state.count > 0 && (now - state.lastNotify) < interval) {\n            continue;\n        }\n        \n        state.count++;\n        state.lastNotify = now;\n        flow.set(escKey, state);\n        \n        alerts.push({\n            house_id: node.house_id,\n            node_id: node.node_id,\n            elapsed_sec: Math.floor((now - lastHb) / 1000)\n        });\n    }\n}\n\nif (alerts.length === 0) return null;\n\nconst timestamp = new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'});\nlet message = `🚨 heartbeatタイムアウト\\n時刻: ${timestamp}\\n\\n`;\n\nfor (const a of alerts) {\n    message += `- ${a.house_id}/${a.node_id} (${a.elapsed_sec}秒無応答)\\n`;\n}\n\nmsg.lineMessage = message;\nreturn msg;",
        "wires": [["line_notify"]]
    }
]
```

### 3.4 閾値超過検知フロー

```json
[
    {
        "id": "mqtt_sensor_in",
        "type": "mqtt in",
        "name": "センサー値",
        "topic": "greenhouse/+/sensors/+",
        "qos": "0",
        "datatype": "json",
        "broker": "mqtt_broker",
        "wires": [["threshold_check"]]
    },
    {
        "id": "threshold_check",
        "type": "function",
        "name": "閾値チェック",
        "func": "const parts = msg.topic.split('/');\nconst houseId = parts[1];\nconst sensor = parts[3];\nconst value = msg.payload.value;\n\nif (value === undefined) return null;\n\nconst thresholds = global.get('thresholds') || {\n    temperature: { low: 5, high: 40, unit: '℃' },\n    humidity: { low: 30, high: 95, unit: '%' },\n    co2: { high: 3000, unit: 'ppm' }\n};\n\nconst t = thresholds[sensor];\nif (!t) return null;\n\nlet errorType = null;\nlet threshold = null;\n\nif (t.low !== undefined && value < t.low) {\n    errorType = `low_${sensor}`;\n    threshold = t.low;\n} else if (t.high !== undefined && value > t.high) {\n    errorType = `high_${sensor}`;\n    threshold = t.high;\n} else {\n    // 正常範囲、エスカレーションリセット\n    const escKey = `escalation_${houseId}_${sensor}`;\n    flow.set(escKey, null);\n    return null;\n}\n\n// エスカレーション管理\nconst escKey = `escalation_${houseId}_${sensor}`;\nconst state = flow.get(escKey) || { count: 0, lastNotify: 0 };\nconst now = Date.now();\n\nconst intervals = [0, 5, 15, 30, 60];\nconst index = Math.min(state.count, intervals.length - 1);\nconst interval = intervals[index] * 60 * 1000;\n\nif (state.count > 0 && (now - state.lastNotify) < interval) {\n    return null;\n}\n\nstate.count++;\nstate.lastNotify = now;\nflow.set(escKey, state);\n\n// 夜間チェック\nconst hour = new Date().getHours();\nconst isNight = hour >= 22 || hour < 6;\nconst isHighSeverity = (sensor === 'temperature');\n\nif (isNight && !isHighSeverity) {\n    return null;\n}\n\nconst timestamp = new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'});\nconst icon = errorType.startsWith('high') ? '🔥' : '🥶';\n\nmsg.lineMessage = `${icon} ${errorType}\\nハウス: ${houseId}\\n現在値: ${value}${t.unit}\\n閾値: ${threshold}${t.unit}\\n時刻: ${timestamp}`;\n\nreturn msg;",
        "wires": [["line_notify", "sqlite_log"]]
    }
]
```

### 3.5 LINE通知ノード

```json
[
    {
        "id": "line_notify",
        "type": "http request",
        "name": "LINE Notify",
        "method": "POST",
        "url": "https://notify-api.line.me/api/notify",
        "payload": "message={{lineMessage}}",
        "payloadType": "str",
        "headers": [
            {"key": "Authorization", "value": "Bearer ${LINE_TOKEN}"},
            {"key": "Content-Type", "value": "application/x-www-form-urlencoded"}
        ],
        "wires": [[]]
    }
]
```

### 3.6 SQLiteログ保存ノード

```json
[
    {
        "id": "sqlite_log",
        "type": "function",
        "name": "SQLite INSERT準備",
        "func": "if (!msg.error_log) return null;\n\nconst e = msg.error_log;\nmsg.topic = `INSERT INTO error_log (timestamp, house_id, node_id, error_type, severity, message) VALUES (${e.timestamp}, '${e.house_id}', ${e.node_id ? \"'\" + e.node_id + \"'\" : 'NULL'}, '${e.error_type}', '${e.severity}', '${e.message}')`;\n\nreturn msg;",
        "wires": [["sqlite_out"]]
    },
    {
        "id": "sqlite_out",
        "type": "sqlite",
        "name": "異常ログ保存",
        "mydb": "sqlite_db",
        "sqlquery": "msg.topic",
        "wires": [[]]
    }
]
```

---

## 4. SQLiteスキーマ

```sql
CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    house_id TEXT NOT NULL,
    node_id TEXT,
    error_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT,
    sensor TEXT,
    value REAL,
    threshold REAL,
    notified INTEGER DEFAULT 0,
    acknowledged INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_error_log_timestamp ON error_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_error_log_type ON error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_error_log_severity ON error_log(severity);
```

---

## 5. 使用例

### 5.1 基本的な使用

```
/nodered-error-alert-flow-generator --house-id h1 --nodes sensor01,drainage01
```

**生成されるフロー**:
- LWT検知フロー
- Heartbeat監視フロー（30秒毎チェック、120秒タイムアウト）
- 閾値超過検知フロー（温度、湿度、CO2）
- LINE通知フロー
- SQLiteログ保存フロー

### 5.2 カスタム閾値

```
/nodered-error-alert-flow-generator --thresholds '{"temperature":{"low":10,"high":35}}'
```

### 5.3 夜間抑制なし

```
/nodered-error-alert-flow-generator --night-mode false
```

### 5.4 複数ハウス対応

```
/nodered-error-alert-flow-generator --house-id h1,h2,h3
```

---

## 6. 設定パラメータ

### 6.1 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `LINE_NOTIFY_TOKEN` | LINE Notifyトークン | - |
| `MQTT_BROKER` | MQTTブローカーアドレス | localhost |
| `MQTT_PORT` | MQTTポート | 1883 |
| `SQLITE_PATH` | SQLiteデータベースパス | /data/greenhouse.db |

### 6.2 通知抑制パラメータ

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| `duplicate_suppress_minutes` | 重複排除時間（分） | 5 |
| `escalation_intervals` | エスカレーション間隔（分） | [0, 5, 15, 30, 60] |
| `night_start` | 夜間開始時刻 | 22:00 |
| `night_end` | 夜間終了時刻 | 06:00 |
| `aggregate_interval_minutes` | 集約通知間隔（分） | 60 |

### 6.3 監視パラメータ

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| `heartbeat_check_interval` | heartbeatチェック間隔（秒） | 30 |
| `heartbeat_timeout` | heartbeatタイムアウト（秒） | 120 |

---

## 7. トラブルシューティング

### 7.1 通知が来ない

1. LINE Notifyトークンを確認
2. MQTTブローカー接続を確認
3. Node-REDデバッグノードでメッセージ確認

### 7.2 通知が多すぎる

1. 重複排除時間を延長（`duplicate_suppress_minutes`）
2. エスカレーション間隔を延長
3. 夜間抑制を有効化

### 7.3 heartbeatタイムアウトが頻発

1. ノードのheartbeat間隔を確認（60秒推奨）
2. タイムアウト閾値を延長（120秒→180秒）
3. ネットワーク安定性を確認

---

## 8. 関連スキル

- **circuitpython-sensor-mqtt-builder**: ノード側MQTT実装
- **ha-integration-designer**: Home Assistant連携
- **nodered-timeslot-generator**: タイマーフロー生成

---

## 参考リンク

- [Node-RED公式ドキュメント](https://nodered.org/docs/)
- [LINE Notify API](https://notify-bot.line.me/doc/ja/)
- [node-red-node-sqlite](https://flows.nodered.org/node/node-red-node-sqlite)
- [MQTT LWT解説](https://www.hivemq.com/blog/mqtt-essentials-part-9-last-will-and-testament/)
