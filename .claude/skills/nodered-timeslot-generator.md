# Node-RED 8時間帯タイマー設定生成スキル

農業用8時間帯タイマー設定をNode-REDフロー形式で生成する。
変温管理、日出/日入連動の時間帯制御に対応。

---

## 1. 概要

### 1.1 目的

施設園芸で使用される「8時間帯制御」をNode-REDで実装するためのフロー・設定を自動生成する。

### 1.2 8時間帯制御とは

1日を8つの時間帯に分割し、各時間帯で異なる目標値（温度、湿度等）を設定する制御方式。

| # | 時間帯 | 開始基準 | 農業的意義 |
|---|--------|----------|-----------|
| 1 | 夜間前半 | 日入 | 呼吸抑制期 - 日中の光合成産物を消費しない |
| 2 | 夜間後半 | 日入+4h | 低温管理期 - 徒長防止、花芽分化促進 |
| 3 | 明け方 | 日出-2h | 最低温度期 - 1日の最低温度を維持 |
| 4 | 早朝 | 日出 | 暖房開始期 - 光合成開始に合わせて加温 |
| 5 | 午前 | 日出+2h | 光合成活発期 - 最も活発な光合成 |
| 6 | 真昼 | 南中-2h | 高温管理期 - CO2施用効果大 |
| 7 | 午後 | 南中+2h | 転流促進期 - 同化産物を果実へ転流 |
| 8 | 夕方 | 日入-2h | 暖房停止準備 - 徐々に温度を下げる |

### 1.3 日出・日入連動

時間帯の境界は固定時刻ではなく、日出・日入時刻に連動して毎日変化する。
季節による日長の変化に自動対応。

---

## 2. 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- 8時間帯タイマーの設定
- 農業用変温制御の実装
- 日出/日入連動タイマー
- Node-REDで時間帯制御

### 2.1 入力パラメータ

```yaml
# 基本設定
location:
  latitude: 35.6762    # 緯度（東京）
  longitude: 139.6503  # 経度

# 時間帯設定（8時間帯）
timeslots:
  - slot: 1
    name: "夜間前半"
    start_type: "sunset"
    start_offset: 0      # 分
    targets:
      temperature: 22
      humidity: 70

  - slot: 2
    name: "夜間後半"
    start_type: "sunset"
    start_offset: 240    # 日入+4時間
    targets:
      temperature: 20
      humidity: 75

  - slot: 3
    name: "明け方"
    start_type: "sunrise"
    start_offset: -120   # 日出-2時間
    targets:
      temperature: 18
      humidity: 80

  - slot: 4
    name: "早朝"
    start_type: "sunrise"
    start_offset: 0
    targets:
      temperature: 22
      humidity: 70

  - slot: 5
    name: "午前"
    start_type: "sunrise"
    start_offset: 120    # 日出+2時間
    targets:
      temperature: 26
      humidity: 65

  - slot: 6
    name: "真昼"
    start_type: "solar_noon"
    start_offset: -120   # 南中-2時間
    targets:
      temperature: 28
      humidity: 60

  - slot: 7
    name: "午後"
    start_type: "solar_noon"
    start_offset: 120    # 南中+2時間
    targets:
      temperature: 26
      humidity: 65

  - slot: 8
    name: "夕方"
    start_type: "sunset"
    start_offset: -120   # 日入-2時間
    targets:
      temperature: 24
      humidity: 70
```

### 2.2 出力形式

- Node-REDフローJSON
- sun-positionノード設定
- SQLite連携用SQLスキーマ
- 時間帯判定用functionノード

---

## 3. 必要ノード（インストール）

```bash
cd ~/.node-red

# スケジューラ
npm install node-red-contrib-cron-plus

# 太陽位置計算
npm install node-red-contrib-sun-position

# SQLite（タイマー設定永続化）
npm install node-red-node-sqlite

# Dashboard（UI）
npm install node-red-dashboard

# Node-RED再起動
node-red-restart
```

---

## 4. Node-REDフロー設計

### 4.1 アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Node-RED 8時間帯タイマーシステム                          │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │   SQLite DB     │
                         │ (timeslots)     │
                         └────────┬────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ 日出/日入計算 │       │ 時間帯判定    │       │   管理UI      │
│ (毎日0:00)    │       │ (毎分実行)    │       │ (Dashboard)   │
│ sun-position  │       │               │       │               │
└───────┬───────┘       └───────┬───────┘       └───────────────┘
        │                       │
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│  sun_times    │       │   switch      │
│  テーブル更新 │       │ (slot 1-8)    │
└───────────────┘       └───────┬───────┘
                                │
                ┌───────┬───────┼───────┬───────┐
                ▼       ▼       ▼       ▼       ▼
            ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
            │Slot1 ││Slot2 ││ ... ││Slot7 ││Slot8 │
            │目標値││目標値││     ││目標値││目標値│
            └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘
               └───────┴───────┴───────┴───────┘
                               │
                               ▼
                       ┌───────────────┐
                       │  MQTT送信     │
                       │ (目標値)      │
                       └───────────────┘
```

### 4.2 フロー構成

```
[1分毎inject]
      │
      ▼
[sun-position] ─── 日出/日入/南中時刻取得
      │
      ▼
[時間帯判定function] ─── msg.timeslot = 1-8
      │
      ▼
[switch分岐] ─┬─ 時間帯1 → [目標値1設定] ──┐
              ├─ 時間帯2 → [目標値2設定] ──┤
              ├─ ...                       │
              └─ 時間帯8 → [目標値8設定] ──┤
                                           │
                                           ▼
                                    [MQTT送信]
                                    [ログ記録]
```

---

## 5. 日出/日入計算フロー（sun-position使用）

### 5.1 毎日0時に実行するフロー

```json
[
    {
        "id": "cron_daily_sun",
        "type": "cronplus",
        "name": "毎日0時",
        "outputField": "payload",
        "timeZone": "Asia/Tokyo",
        "options": [
            {
                "name": "daily",
                "topic": "",
                "payloadType": "default",
                "expression": "0 0 * * *"
            }
        ],
        "x": 130,
        "y": 100,
        "wires": [["sun_position_node"]]
    },
    {
        "id": "sun_position_node",
        "type": "sun-position",
        "name": "太陽位置計算",
        "lat": "35.6762",
        "lon": "139.6503",
        "x": 310,
        "y": 100,
        "wires": [["format_sun_times"]]
    },
    {
        "id": "format_sun_times",
        "type": "function",
        "name": "整形・SQL生成",
        "func": "const s = msg.payload;\nconst today = new Date().toISOString().split('T')[0];\nconst sunrise = s.sunriseStart.toTimeString().split(' ')[0];\nconst sunset = s.sunsetEnd.toTimeString().split(' ')[0];\nconst solarNoon = s.solarNoon.toTimeString().split(' ')[0];\n\nmsg.topic = `INSERT OR REPLACE INTO sun_times (date, sunrise, sunset, solar_noon, latitude, longitude) VALUES ('${today}', '${sunrise}', '${sunset}', '${solarNoon}', 35.6762, 139.6503)`;\n\nreturn msg;",
        "outputs": 1,
        "x": 500,
        "y": 100,
        "wires": [["sqlite_sun"]]
    },
    {
        "id": "sqlite_sun",
        "type": "sqlite",
        "name": "sun_times保存",
        "mydb": "timer_db",
        "sqlquery": "msg.topic",
        "x": 690,
        "y": 100,
        "wires": [[]]
    }
]
```

---

## 6. 時間帯判定フロー

### 6.1 毎分実行フロー

```json
[
    {
        "id": "timeslot_inject",
        "type": "inject",
        "name": "1分毎",
        "repeat": "60",
        "crontab": "",
        "once": true,
        "onceDelay": "1",
        "x": 130,
        "y": 200,
        "wires": [["get_sun_times"]]
    },
    {
        "id": "get_sun_times",
        "type": "sqlite",
        "name": "sun_times取得",
        "mydb": "timer_db",
        "sqlquery": "fixed",
        "sql": "SELECT * FROM sun_times WHERE date = date('now', 'localtime') LIMIT 1",
        "x": 310,
        "y": 200,
        "wires": [["get_timeslots"]]
    },
    {
        "id": "get_timeslots",
        "type": "sqlite",
        "name": "timeslots取得",
        "mydb": "timer_db",
        "sqlquery": "fixed",
        "sql": "SELECT * FROM timeslots WHERE enabled = 1 ORDER BY slot_number",
        "x": 490,
        "y": 200,
        "wires": [["calc_timeslot"]]
    },
    {
        "id": "calc_timeslot",
        "type": "function",
        "name": "時間帯判定",
        "func": "/* 下記の時間帯判定コード */",
        "x": 670,
        "y": 200,
        "wires": [["timeslot_switch"]]
    }
]
```

### 6.2 時間帯判定 functionノード

```javascript
// 8時間帯判定（日出/日入/南中連動）
const now = new Date();
const sunData = msg.payload[0]; // sun_times
const timeslots = msg.timeslots; // SQLiteから取得した時間帯設定

if (!sunData) {
    node.error("sun_times not found");
    return null;
}

// sun_timesから時刻をパース
function parseTime(timeStr) {
    const [h, m, s] = timeStr.split(':').map(Number);
    const d = new Date();
    d.setHours(h, m, s || 0, 0);
    return d;
}

const sunrise = parseTime(sunData.sunrise);
const sunset = parseTime(sunData.sunset);
const solarNoon = parseTime(sunData.solar_noon);

// オフセットを適用した実際の開始時刻を計算
function getSlotStartTime(slot) {
    let baseTime;
    switch (slot.start_type) {
        case 'sunrise':
            baseTime = new Date(sunrise);
            break;
        case 'sunset':
            baseTime = new Date(sunset);
            break;
        case 'solar_noon':
            baseTime = new Date(solarNoon);
            break;
        case 'fixed':
            return parseTime(slot.start_time);
        default:
            return parseTime('00:00:00');
    }
    return new Date(baseTime.getTime() + slot.start_offset * 60000);
}

// 全スロットの開始時刻を計算
const slotTimes = timeslots.map(slot => ({
    ...slot,
    actualStart: getSlotStartTime(slot)
})).sort((a, b) => a.actualStart - b.actualStart);

// 現在の時間帯を判定
let currentSlot = slotTimes[slotTimes.length - 1]; // デフォルトは最後のスロット
for (let i = 0; i < slotTimes.length; i++) {
    const nextIdx = (i + 1) % slotTimes.length;
    const start = slotTimes[i].actualStart;
    const end = slotTimes[nextIdx].actualStart;

    // 日をまたぐ場合の処理
    if (end < start) {
        if (now >= start || now < end) {
            currentSlot = slotTimes[i];
            break;
        }
    } else {
        if (now >= start && now < end) {
            currentSlot = slotTimes[i];
            break;
        }
    }
}

msg.timeslot = currentSlot.slot_number;
msg.timeslotName = currentSlot.slot_name;
msg.targetTemp = currentSlot.target_temp;
msg.targetHumidity = currentSlot.target_humidity;
msg.targetCO2 = currentSlot.target_co2;
msg.payload = {
    slot: currentSlot.slot_number,
    name: currentSlot.slot_name,
    start: currentSlot.actualStart.toTimeString().slice(0, 5),
    targets: {
        temperature: currentSlot.target_temp,
        humidity: currentSlot.target_humidity,
        co2: currentSlot.target_co2
    }
};

return msg;
```

---

## 7. 完全なフローJSON（エクスポート用）

### 7.1 8時間帯タイマー基本フロー

```json
[
    {
        "id": "timeslot_flow",
        "type": "tab",
        "label": "8時間帯タイマー",
        "disabled": false
    },
    {
        "id": "inject_1min",
        "type": "inject",
        "z": "timeslot_flow",
        "name": "1分毎",
        "props": [{"p": "payload"}],
        "repeat": "60",
        "crontab": "",
        "once": true,
        "onceDelay": "5",
        "topic": "",
        "x": 130,
        "y": 100,
        "wires": [["sun_calc"]]
    },
    {
        "id": "sun_calc",
        "type": "sun-position",
        "z": "timeslot_flow",
        "name": "日出/日入計算",
        "lat": "35.6762",
        "lon": "139.6503",
        "x": 310,
        "y": 100,
        "wires": [["timeslot_judge"]]
    },
    {
        "id": "timeslot_judge",
        "type": "function",
        "z": "timeslot_flow",
        "name": "時間帯判定",
        "func": "const now = new Date();\nconst s = msg.payload;\n\nconst sunrise = s.sunriseStart;\nconst sunset = s.sunsetEnd;\nconst solarNoon = s.solarNoon;\n\n// 8時間帯定義\nconst slots = [\n    { slot: 1, name: '夜間前半', base: sunset, offset: 0, temp: 22 },\n    { slot: 2, name: '夜間後半', base: sunset, offset: 240, temp: 20 },\n    { slot: 3, name: '明け方', base: sunrise, offset: -120, temp: 18 },\n    { slot: 4, name: '早朝', base: sunrise, offset: 0, temp: 22 },\n    { slot: 5, name: '午前', base: sunrise, offset: 120, temp: 26 },\n    { slot: 6, name: '真昼', base: solarNoon, offset: -120, temp: 28 },\n    { slot: 7, name: '午後', base: solarNoon, offset: 120, temp: 26 },\n    { slot: 8, name: '夕方', base: sunset, offset: -120, temp: 24 }\n];\n\n// 各スロットの実際の開始時刻を計算\nconst slotTimes = slots.map(s => ({\n    ...s,\n    start: new Date(s.base.getTime() + s.offset * 60000)\n})).sort((a, b) => a.start - b.start);\n\n// 現在の時間帯を判定\nlet current = slotTimes[0];\nfor (const slot of slotTimes) {\n    if (now >= slot.start) {\n        current = slot;\n    }\n}\n\nmsg.timeslot = current.slot;\nmsg.timeslotName = current.name;\nmsg.targetTemp = current.temp;\nmsg.payload = {\n    slot: current.slot,\n    name: current.name,\n    target_temp: current.temp,\n    start: current.start.toTimeString().slice(0, 5)\n};\n\nreturn msg;",
        "outputs": 1,
        "x": 510,
        "y": 100,
        "wires": [["timeslot_switch", "debug_slot"]]
    },
    {
        "id": "timeslot_switch",
        "type": "switch",
        "z": "timeslot_flow",
        "name": "時間帯分岐",
        "property": "timeslot",
        "propertyType": "msg",
        "rules": [
            {"t": "eq", "v": "1", "vt": "num"},
            {"t": "eq", "v": "2", "vt": "num"},
            {"t": "eq", "v": "3", "vt": "num"},
            {"t": "eq", "v": "4", "vt": "num"},
            {"t": "eq", "v": "5", "vt": "num"},
            {"t": "eq", "v": "6", "vt": "num"},
            {"t": "eq", "v": "7", "vt": "num"},
            {"t": "eq", "v": "8", "vt": "num"}
        ],
        "checkall": "true",
        "repair": false,
        "x": 710,
        "y": 100,
        "wires": [
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"],
            ["mqtt_target"]
        ]
    },
    {
        "id": "mqtt_target",
        "type": "mqtt out",
        "z": "timeslot_flow",
        "name": "目標値送信",
        "topic": "farm/control/target",
        "qos": "1",
        "retain": "true",
        "broker": "mqtt_broker",
        "x": 910,
        "y": 100,
        "wires": []
    },
    {
        "id": "debug_slot",
        "type": "debug",
        "z": "timeslot_flow",
        "name": "時間帯デバッグ",
        "active": true,
        "tosidebar": true,
        "console": false,
        "complete": "payload",
        "x": 720,
        "y": 200,
        "wires": []
    }
]
```

---

## 8. 目標値設定テンプレート

### 8.1 トマト栽培用（夏期）

```yaml
# トマト夏期設定
crop: tomato
season: summer
timeslots:
  - slot: 1  # 夜間前半（呼吸抑制）
    temp: 22
    humid: 70
    co2: 400
    note: "日中の光合成産物を消費しないよう、やや高めの温度"

  - slot: 2  # 夜間後半（低温管理）
    temp: 20
    humid: 75
    co2: 400
    note: "徒長防止、花芽分化促進"

  - slot: 3  # 明け方（最低温度）
    temp: 18
    humid: 80
    co2: 400
    note: "1日の最低温度維持"

  - slot: 4  # 早朝（暖房開始）
    temp: 22
    humid: 70
    co2: 600
    note: "光合成開始に合わせて加温・CO2施用開始"

  - slot: 5  # 午前（光合成活発）
    temp: 26
    humid: 65
    co2: 1000
    note: "最も光合成が活発、CO2施用効果大"

  - slot: 6  # 真昼（高温管理）
    temp: 28
    humid: 60
    co2: 800
    note: "高温ストレス回避しつつ光合成維持"

  - slot: 7  # 午後（転流促進）
    temp: 26
    humid: 65
    co2: 600
    note: "同化産物を果実へ転流促進"

  - slot: 8  # 夕方（暖房停止準備）
    temp: 24
    humid: 70
    co2: 400
    note: "徐々に温度を下げ、夜間管理へ移行"
```

### 8.2 イチゴ栽培用（冬期）

```yaml
# イチゴ冬期設定
crop: strawberry
season: winter
timeslots:
  - slot: 1  # 夜間前半
    temp: 10
    humid: 85
    co2: 400

  - slot: 2  # 夜間後半
    temp: 8
    humid: 90
    co2: 400

  - slot: 3  # 明け方
    temp: 6
    humid: 90
    co2: 400

  - slot: 4  # 早朝
    temp: 12
    humid: 80
    co2: 600

  - slot: 5  # 午前
    temp: 18
    humid: 70
    co2: 800

  - slot: 6  # 真昼
    temp: 20
    humid: 65
    co2: 800

  - slot: 7  # 午後
    temp: 18
    humid: 70
    co2: 600

  - slot: 8  # 夕方
    temp: 14
    humid: 75
    co2: 400
```

---

## 9. SQLiteスキーマ（タイマー設定永続化）

```sql
-- timeslotsテーブル
CREATE TABLE IF NOT EXISTS timeslots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,           -- 設定名（例: 夏期設定）
    slot_number     INTEGER NOT NULL CHECK (slot_number BETWEEN 1 AND 8),
    slot_name       TEXT,                    -- 時間帯名（例: 夜間前半）

    -- 開始時刻設定
    start_type      TEXT NOT NULL DEFAULT 'fixed',
    start_time      TEXT,                    -- HH:MM (fixed時)
    start_offset    INTEGER DEFAULT 0,       -- 分単位オフセット

    -- 目標値
    target_temp     REAL,                    -- 目標温度（℃）
    target_humidity REAL,                    -- 目標湿度（%）
    target_co2      INTEGER,                 -- 目標CO2（ppm）

    -- 有効/無効
    enabled         INTEGER DEFAULT 1,
    description     TEXT,
    created_at      TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT DEFAULT (datetime('now', 'localtime')),

    UNIQUE (name, slot_number)
);
```

---

## 10. 注意事項

### 10.1 日出/日入計算の精度

- sun-positionノードは高精度（±1分以内）
- 簡易計算式使用時は±2分程度の誤差あり

### 10.2 タイムゾーン

- Node-REDサーバーのタイムゾーン設定を確認
- `Asia/Tokyo` (UTC+9) を前提

### 10.3 季節変動

- 冬至/夏至で日出時刻は約3時間変動
- 日出/日入連動により自動対応

### 10.4 時間帯境界でのチャタリング防止

- 1分間隔での判定でヒステリシスを確保
- 必要に応じて判定間隔を調整

---

## 11. 関連スキル

- [iot-timer-db-generator](./iot-timer-db-generator.md) - タイマーDB スキーマ生成
- [docker-compose-generator](./docker-compose-generator.md) - Node-RED環境構築

---

## 12. 参考資料

- node-red-contrib-cron-plus: https://flows.nodered.org/node/node-red-contrib-cron-plus
- node-red-contrib-sun-position: https://flows.nodered.org/node/node-red-contrib-sun-position
- suncalc: https://github.com/mourner/suncalc
- 施設園芸の環境制御: https://www.naro.affrc.go.jp/

---

**Skill Version**: 2.0.0
**Created**: 2026-02-05
**Updated**: 2026-02-05 - 農業的意義追加、sun-position連携強化
