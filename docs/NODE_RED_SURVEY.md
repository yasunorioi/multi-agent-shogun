# Node-RED プロジェクト現状調査報告書

**調査日**: 2026-02-04
**調査担当**: 足軽1号
**タスクID**: subtask_027_nodered_survey
**親タスク**: cmd_022

---

## 1. 調査結果サマリ

| 項目 | 状況 |
|------|------|
| Node-RED | **未インストール** |
| MQTTブローカー | **未インストール** |
| Node.js | v24.13.0 インストール済み |
| npm | v11.6.2 インストール済み |
| Docker | 利用可能（関連コンテナなし） |

**結論: Node-REDは新規セットアップが必要**

---

## 2. 現在の環境

### 2.1 Node.js環境

```
Node.js: v24.13.0
npm:     v11.6.2
nvm:     インストール済み (/home/yasu/.nvm)
```

Node-REDの動作に十分なバージョン。

### 2.2 確認した場所

| パス | 結果 |
|------|------|
| `~/.node-red` | 存在しない |
| `~/node-red` | 存在しない |
| `which node-red` | 見つからない |
| `npm list -g node-red` | インストールされていない |
| `systemctl status nodered` | サービスなし |

### 2.3 MQTT関連

| 項目 | 結果 |
|------|------|
| `mosquitto` | 未インストール |
| `mosquitto_sub/pub` | 未インストール |
| Docker MQTT | コンテナなし |

---

## 3. Node-RED新規セットアップ手順

### 3.1 Node-REDインストール

```bash
# グローバルインストール
npm install -g node-red

# または、プロジェクトローカル
mkdir ~/node-red && cd ~/node-red
npm init -y
npm install node-red
```

### 3.2 MQTTブローカー（Mosquitto）

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mosquitto mosquitto-clients

# サービス有効化
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 3.3 Docker Compose（推奨）

```yaml
# docker-compose.yml
version: '3'
services:
  node-red:
    image: nodered/node-red:latest
    ports:
      - "1880:1880"
    volumes:
      - ./node-red-data:/data
    environment:
      - TZ=Asia/Tokyo
    restart: unless-stopped

  mosquitto:
    image: eclipse-mosquitto:latest
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
    restart: unless-stopped
```

---

## 4. Pico連携に必要なノード（パレット）

### 4.1 必須ノード

| ノード | 用途 | インストール |
|--------|------|-------------|
| `node-red-contrib-aedes` | MQTTブローカー内蔵 | npm i node-red-contrib-aedes |
| `node-red-dashboard` | Web UI/グラフ | npm i node-red-dashboard |

### 4.2 推奨ノード

| ノード | 用途 | インストール |
|--------|------|-------------|
| `node-red-contrib-ui-svg` | カスタムSVG表示 | npm i node-red-contrib-ui-svg |
| `node-red-node-sqlite` | SQLiteデータ保存 | npm i node-red-node-sqlite |
| `node-red-contrib-influxdb` | InfluxDB連携 | npm i node-red-contrib-influxdb |
| `node-red-contrib-cron-plus` | 高度なスケジューリング | npm i node-red-contrib-cron-plus |

### 4.3 Pico連携オプション

| ノード | 用途 | 備考 |
|--------|------|------|
| `node-red-contrib-serialport` | USB/UART通信 | 有線接続時 |
| `node-red-contrib-modbus` | Modbus通信 | 産業機器連携 |

---

## 5. 推奨アーキテクチャ

### 5.1 シンプル構成（推奨）

```
┌─────────────────┐     MQTT      ┌─────────────────┐
│  Pico W/2 W     │ ←──────────→  │  Node-RED       │
│  (センサー)     │   pub/sub     │  + Dashboard    │
│                 │               │  + Mosquitto    │
│  ・温湿度       │               │                 │
│  ・CO2          │               │  WebUI: :1880   │
│  ・電磁弁       │               │  MQTT:  :1883   │
└─────────────────┘               └─────────────────┘
                                         │
                                         ▼
                                  ┌─────────────────┐
                                  │  ブラウザ       │
                                  │  (ダッシュボード)│
                                  └─────────────────┘
```

### 5.2 MQTT トピック設計案

```
greenhouse/
├── sensor/
│   ├── {house_id}/temperature    # 温度
│   ├── {house_id}/humidity       # 湿度
│   ├── {house_id}/co2           # CO2
│   └── {house_id}/pressure      # 気圧
├── actuator/
│   ├── {house_id}/valve/{id}/state    # バルブ状態
│   └── {house_id}/valve/{id}/command  # バルブ制御
└── status/
    └── {house_id}/online        # オンライン状態
```

### 5.3 Picoファームウェア要件

| 機能 | ライブラリ | 備考 |
|------|-----------|------|
| WiFi | `network` | MicroPython標準 |
| MQTT | `umqtt.simple` | MicroPython標準 |
| JSON | `json` | MicroPython標準 |
| I2C | `machine.I2C` | センサー用 |

```python
# Pico MQTT送信例
from umqtt.simple import MQTTClient
import json

client = MQTTClient("pico-h1-sen", "192.168.x.x")
client.connect()

data = {"temperature": 25.5, "humidity": 65.0}
client.publish("greenhouse/sensor/h1/temperature", json.dumps(data))
```

---

## 6. ArsproutPi/UECS からの移行

### 6.1 比較

| 項目 | ArsproutPi + UECS | Node-RED + MQTT |
|------|-------------------|-----------------|
| プロトコル | UDP マルチキャスト | TCP（MQTT） |
| メッセージ形式 | XML (CCM) | JSON |
| ブローカー | 不要 | 必要（Mosquitto） |
| UI | Angular WebUI | Node-RED Dashboard |
| 制御ロジック | Java（ArsproutPi内） | Node-REDフロー |
| 学習コスト | 高（UECS仕様理解） | 低（ビジュアル） |
| 柔軟性 | 中（ArsproutPi依存） | 高（ノード追加自由） |

### 6.2 移行のメリット

1. **シンプル**: UECS CCM仕様の理解が不要
2. **柔軟**: ノードの追加でカスタマイズ自由
3. **可視化**: ダッシュボードで即座にグラフ化
4. **コミュニティ**: 豊富なサンプルフロー
5. **拡張性**: InfluxDB、Grafana等との連携容易

### 6.3 移行時の注意点

1. MQTTブローカーの冗長性（本番環境）
2. QoS設定（センサーデータの確実な配信）
3. 認証設定（セキュリティ）
4. データ永続化（SQLite or InfluxDB）

---

## 7. 次のステップ（提案）

### Step 1: 環境構築
```bash
# Docker Compose で一括セットアップ
docker compose up -d
```

### Step 2: 基本フロー作成
- MQTT受信ノード設定
- デバッグノードで動作確認
- ダッシュボードゲージ追加

### Step 3: Picoファームウェア開発
- MicroPython MQTT実装
- センサー読み取り＋JSON送信
- 定期送信（10秒間隔）

### Step 4: 制御フロー追加
- 電磁弁ON/OFF制御
- タイマー制御
- 条件分岐（温度閾値など）

---

## 8. 参考リソース

- [Node-RED公式](https://nodered.org/)
- [Node-RED Dashboard](https://flows.nodered.org/node/node-red-dashboard)
- [Eclipse Mosquitto](https://mosquitto.org/)
- [MicroPython umqtt](https://github.com/micropython/micropython-lib/tree/master/micropython/umqtt.simple)

---

**以上、Node-REDプロジェクト現状調査報告終わり。**
