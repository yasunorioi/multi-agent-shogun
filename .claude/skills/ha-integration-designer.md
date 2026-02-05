# Home Assistant Integration Designer

Home Assistant + 外部デバイス統合設計ドキュメントを自動生成するスキル。

## 概要

外部デバイス（UniPi/EVOK、Modbus機器、RS485機器、MQTTデバイス等）をHome Assistantに統合するための設計ドキュメントを自動生成する。統合方式の比較、設定ファイル例、動作確認手順、トラブルシューティングを含む包括的な設計書を作成。

## 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- Home Assistantにデバイスを統合したい
- HAと外部機器の連携設計
- Modbus/RS485機器をHAに接続
- IoTデバイスのHA統合方法を比較検討

## 入力パラメータ

### デバイス種類

| デバイス種類 | プロトコル | 統合パターン |
|-------------|-----------|-------------|
| UniPi/EVOK | WebSocket/REST | Node-RED経由推奨 |
| Modbus RTU | RS485 | HA Modbus Integration |
| Modbus TCP | Ethernet | HA Modbus Integration |
| 汎用MQTT | MQTT | HA MQTT Integration |
| REST APIデバイス | HTTP | RESTful/command_line |
| Zigbee機器 | Zigbee | ZHA/Zigbee2MQTT |
| Z-Wave機器 | Z-Wave | Z-Wave JS |

### 統合方式

| 方式 | リアルタイム性 | 設定容易さ | 備考 |
|------|--------------|-----------|------|
| 公式Integration | ◎ | ◎ | あれば最優先 |
| MQTT経由 | ◎ | ○ | 柔軟、MQTTブリッジ必要 |
| REST経由 | △ | ○ | ポーリング、遅延あり |
| Node-RED経由 | ◎ | ○ | 複雑ロジック対応 |
| Modbus直接 | ○ | △ | レジスタ設定必要 |

### 機能要件

| 要件 | 説明 |
|------|------|
| センサー読み取り | 温度、湿度、電力等の取得 |
| リレー/スイッチ制御 | ON/OFF制御 |
| 状態監視 | デバイス死活監視 |
| アラート通知 | 異常値検知時の通知 |
| ログ記録 | データの長期保存 |

## 出力形式

生成するドキュメント構成：

```
HOMEASSISTANT_{DEVICE}_INTEGRATION.md
├── 1. 統合方法の比較
│   ├── 比較表
│   └── 各方式の詳細
├── 2. 推奨構成
│   ├── 選定理由
│   └── アーキテクチャ図（ASCII）
├── 3. 設定ファイル例
│   ├── configuration.yaml
│   ├── デバイス固有設定
│   └── Node-REDフロー（必要時）
├── 4. 動作確認手順
│   ├── 前提条件
│   ├── Step by Step
│   └── チェックリスト
├── 5. トラブルシューティング
│   ├── よくある問題
│   └── ログ確認方法
└── 6. 将来の拡張
```

## サンプル出力

### Modbusデバイス（温調器）統合設計

---

# Home Assistant + Modbus温調器 統合設計書

> **Version**: 1.0.0
> **デバイス**: Modbus RTU 温調器（RS485接続）
> **生成スキル**: ha-integration-designer

---

## 1. 統合方法の比較

### 1.1 比較表

| 方式 | リアルタイム性 | 設定容易さ | 安定性 | 推奨度 |
|------|--------------|-----------|--------|--------|
| **a) HA Modbus Integration** | ○ | △ | ◎ | **◎ 推奨** |
| **b) MQTT Bridge経由** | ◎ | ○ | ○ | ○ |
| **c) Node-RED経由** | ◎ | ○ | ○ | ○ |

### 1.2 各方式の詳細

#### a) HA Modbus Integration（推奨）

Home Assistant公式のModbus Integrationを使用。

**利点**:
- 公式サポート、ドキュメント充実
- YAMLのみで設定完結
- ポーリング間隔を細かく制御

**欠点**:
- レジスタアドレス設定が必要
- 複雑な演算はAutomationで対応

#### b) MQTT Bridge経由

Modbus→MQTT変換を行い、HAのMQTT Integrationで接続。

**利点**:
- 複数システムからデータ参照可能
- 変換ロジックを柔軟に実装

**欠点**:
- 追加のブリッジソフトウェアが必要
- 構成が複雑化

#### c) Node-RED経由

Node-REDのModbusノードで読み取り、HAに送信。

**利点**:
- 複雑な演算・変換が可能
- 他のデータソースと統合しやすい

**欠点**:
- Node-REDの管理が追加

---

## 2. 推奨構成

### 2.1 選定理由

**HA Modbus Integration（方式a）** を推奨。

| 観点 | 理由 |
|------|------|
| **安定性** | 公式Integration、長期サポート |
| **設定容易さ** | configuration.yamlのみ |
| **保守性** | HAアップデートで自動対応 |
| **リソース** | 追加プロセス不要 |

### 2.2 アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────┐
│                 Home Assistant + Modbus 統合構成                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Raspberry Pi / PC                             │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Home Assistant                          │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │  │
│  │  │   Modbus     │  │   Entities   │  │  Automations │     │  │
│  │  │ Integration  │  │  (sensors,   │  │  (alerts,    │     │  │
│  │  │              │  │   switches)  │  │   control)   │     │  │
│  │  └──────┬───────┘  └──────────────┘  └──────────────┘     │  │
│  │         │                                                  │  │
│  └─────────┼──────────────────────────────────────────────────┘  │
│            │                                                     │
│  ┌─────────▼───────────────────────────────────────────────────┐│
│  │              USB-RS485 アダプタ (/dev/ttyUSB0)               ││
│  └─────────────────────────────────┬───────────────────────────┘│
│                                    │                             │
└────────────────────────────────────┼─────────────────────────────┘
                                     │ RS485 (A+/B-)
                     ┌───────────────┴───────────────┐
                     │                               │
              ┌──────▼──────┐                 ┌──────▼──────┐
              │  温調器 #1   │                 │  温調器 #2   │
              │  Addr: 1    │                 │  Addr: 2    │
              │             │                 │             │
              │ ┌─────────┐ │                 │ ┌─────────┐ │
              │ │Temp: 25℃│ │                 │ │Temp: 23℃│ │
              │ │Set:  28℃│ │                 │ │Set:  26℃│ │
              │ └─────────┘ │                 │ └─────────┘ │
              └─────────────┘                 └─────────────┘
```

---

## 3. 設定ファイル例

### 3.1 configuration.yaml

```yaml
# Home Assistant Modbus Configuration
# Device: Temperature Controller (Modbus RTU)

modbus:
  - name: temperature_controllers
    type: serial
    port: /dev/ttyUSB0
    baudrate: 9600
    bytesize: 8
    parity: N
    stopbits: 1
    timeout: 3

    sensors:
      # 温調器 #1 - 現在温度（レジスタ 100）
      - name: "Controller 1 Temperature"
        unique_id: "modbus_ctrl1_temp"
        slave: 1
        address: 100
        input_type: holding
        data_type: int16
        scale: 0.1
        precision: 1
        unit_of_measurement: "°C"
        device_class: temperature
        scan_interval: 10

      # 温調器 #1 - 設定温度（レジスタ 101）
      - name: "Controller 1 Setpoint"
        unique_id: "modbus_ctrl1_setpoint"
        slave: 1
        address: 101
        input_type: holding
        data_type: int16
        scale: 0.1
        precision: 1
        unit_of_measurement: "°C"
        scan_interval: 30

      # 温調器 #2 - 現在温度
      - name: "Controller 2 Temperature"
        unique_id: "modbus_ctrl2_temp"
        slave: 2
        address: 100
        input_type: holding
        data_type: int16
        scale: 0.1
        precision: 1
        unit_of_measurement: "°C"
        device_class: temperature
        scan_interval: 10

    # 設定温度の書き込み（Number Entity）
    climates:
      - name: "Controller 1"
        unique_id: "modbus_ctrl1_climate"
        slave: 1
        target_temp_register: 101
        current_temp_register: 100
        data_type: int16
        scale: 0.1
        precision: 1
        temp_step: 0.5
        min_temp: 10
        max_temp: 40
```

### 3.2 アラート設定（automations.yaml）

```yaml
# 高温アラート
- alias: "Modbus High Temperature Alert"
  id: modbus_high_temp_alert
  trigger:
    - platform: numeric_state
      entity_id: sensor.controller_1_temperature
      above: 35
      for:
        minutes: 5
  action:
    - service: notify.mobile_app
      data:
        title: "高温警報"
        message: "温調器1: {{ states('sensor.controller_1_temperature') }}°C"
    - service: persistent_notification.create
      data:
        title: "高温警報"
        message: "温調器1の温度が35°Cを超えました"

# 通信エラーアラート
- alias: "Modbus Communication Error"
  id: modbus_comm_error
  trigger:
    - platform: state
      entity_id: sensor.controller_1_temperature
      to: "unavailable"
      for:
        minutes: 2
  action:
    - service: notify.mobile_app
      data:
        title: "通信エラー"
        message: "温調器1との通信が途絶しました"
```

---

## 4. 動作確認手順

### 4.1 前提条件

- Home Assistant インストール済み
- USB-RS485 アダプタ接続済み
- 温調器の通信設定（ボーレート、アドレス）確認済み

### 4.2 確認手順

#### Step 1: シリアルポート確認

```bash
# USBデバイス確認
ls -la /dev/ttyUSB*

# シリアルポート権限確認
sudo usermod -aG dialout homeassistant
```

#### Step 2: Modbus通信テスト（mbpoll使用）

```bash
# mbpollインストール
sudo apt install mbpoll

# レジスタ読み取りテスト
mbpoll -a 1 -b 9600 -P none -t 4 -r 100 -c 2 /dev/ttyUSB0

# 期待出力:
# [100]:  250  (= 25.0°C)
# [101]:  280  (= 28.0°C setpoint)
```

#### Step 3: Home Assistant設定反映

```bash
# 設定チェック
ha core check

# 再起動
ha core restart
```

#### Step 4: エンティティ確認

1. Home Assistant → Settings → Devices & Services
2. Modbus Integration を確認
3. Developer Tools → States でエンティティ値を確認

### 4.3 確認チェックリスト

| # | 項目 | 確認方法 | 期待結果 |
|---|------|---------|---------|
| 1 | シリアルポート | `ls /dev/ttyUSB*` | デバイス表示 |
| 2 | Modbus通信 | `mbpoll` コマンド | レジスタ値取得 |
| 3 | HA設定 | `ha core check` | エラーなし |
| 4 | センサー値 | Developer Tools | 温度値表示 |
| 5 | アラート | 閾値超過テスト | 通知受信 |

---

## 5. トラブルシューティング

### 5.1 よくある問題

#### 問題1: センサーが "unavailable" になる

**原因候補**:
- シリアルポートのパス誤り
- ボーレート不一致
- スレーブアドレス誤り
- 配線（A+/B-極性反転）

**確認手順**:
```bash
# シリアルポート確認
dmesg | grep tty

# Modbusテスト
mbpoll -a 1 -b 9600 -P none -t 4 -r 100 /dev/ttyUSB0
```

#### 問題2: 値が異常（桁違い等）

**原因候補**:
- scale設定誤り
- data_type誤り（int16 vs uint16）
- レジスタアドレス誤り

**確認**:
- デバイスのマニュアルでレジスタ仕様確認
- 生の値をmbpollで確認してscale計算

#### 問題3: 書き込みができない

**原因候補**:
- デバイスが書き込み禁止モード
- Function Code不一致
- レジスタが読み取り専用

**確認**:
```bash
# 書き込みテスト（値280 = 28.0°C）
mbpoll -a 1 -b 9600 -P none -t 4 -r 101 /dev/ttyUSB0 280
```

### 5.2 ログ確認

```bash
# Home Assistantログ
ha core logs | grep -i modbus

# 詳細ログ有効化（configuration.yaml）
logger:
  default: info
  logs:
    pymodbus: debug
    homeassistant.components.modbus: debug
```

### 5.3 Modbus レジスタタイプ対応表

| HA input_type | Modbus Function | 用途 |
|---------------|-----------------|------|
| holding | FC03 (Read), FC06/16 (Write) | 読み書き可能レジスタ |
| input | FC04 | 読み取り専用レジスタ |
| coil | FC01 (Read), FC05 (Write) | ビット単位ON/OFF |
| discrete_input | FC02 | 読み取り専用ビット |

---

## 6. 将来の拡張

### 6.1 複数デバイス対応

```yaml
modbus:
  - name: line_1
    port: /dev/ttyUSB0
    # ...

  - name: line_2
    port: /dev/ttyUSB1
    # ...
```

### 6.2 InfluxDB連携

```yaml
influxdb:
  host: localhost
  include:
    entities:
      - sensor.controller_1_temperature
      - sensor.controller_2_temperature
```

---

**Document End**

---

## 構成パターン

### 1. 公式Integration優先パターン

```
[デバイス] ─直接─► [HA Integration] ─► [Home Assistant]
```

対象: Modbus、Zigbee、Z-Wave、KNX等
利点: シンプル、公式サポート

### 2. MQTT経由パターン

```
[デバイス] ─► [MQTT Bridge] ─► [Mosquitto] ─► [HA MQTT] ─► [Home Assistant]
```

対象: カスタムプロトコル、複数システム共有
利点: 柔軟性、マルチクライアント対応

### 3. Node-RED経由パターン

```
[デバイス] ─► [Node-RED] ─► [HA API/MQTT] ─► [Home Assistant]
```

対象: 複雑なロジック、データ変換が必要
利点: 演算、フィルタリング、統合処理

### 4. ハイブリッドパターン

```
[UniPi] ──WebSocket──► [Node-RED] ──┐
                                    ├─► [Home Assistant]
[Pico] ──MQTT──► [Mosquitto] ───────┘
```

対象: 複数種類のデバイスを統合
利点: デバイス特性に応じた最適な連携方式

## 使用例

```
User: 電力計（Modbus RTU）をHome Assistantに接続したい
Assistant: [このスキルを使用してModbus統合設計書を生成]

User: HAにRS485機器を統合する方法を比較検討したい
Assistant: [このスキルを使用して統合方式比較表を生成]

User: UniPiとPicoの両方をHAに統合したい
Assistant: [このスキルを使用してハイブリッドパターン設計書を生成]

User: Zigbee温度センサーをHA連携したい
Assistant: [このスキルを使用してZHA/Zigbee2MQTT比較と設定例を生成]
```
