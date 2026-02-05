# pico-setup-wizard

Pico系ボードのCircuitPythonセットアップを対話形式でガイドするスキル。

## 概要

Raspberry Pi Pico W / Pico 2 W / W5500-EVB-Pico等のCircuitPythonセットアップを
ステップバイステップで案内する。ボード種類に応じた適切なUF2ファイル、
必要ライブラリ、設定テンプレートを提示する。

## 使用方法

```
/pico-setup-wizard [ボード種類]
```

ボード種類を省略した場合は対話形式で選択を促す。

### 例

```
/pico-setup-wizard pico-w
/pico-setup-wizard pico2-w
/pico-setup-wizard w5500-evb-pico
```

## 対応ボード一覧

| ボードID | 正式名称 | 接続方式 | 特徴 |
|----------|----------|----------|------|
| `pico-w` | Raspberry Pi Pico W | WiFi (CYW43439) | 標準的なWiFi対応Pico |
| `pico2-w` | Raspberry Pi Pico 2 W | WiFi (CYW43439) | RP2350搭載、高速版 |
| `w5500-evb-pico` | W5500-EVB-Pico | 有線Ethernet (W5500) | WIZnet製、有線安定接続 |
| `w5500-evb-pico2` | W5500-EVB-Pico2 | 有線Ethernet (W5500) | RP2350搭載、有線版 |
| `pico` | Raspberry Pi Pico | なし | 無線なし（USB接続のみ） |
| `pico2` | Raspberry Pi Pico 2 | なし | RP2350搭載、無線なし |

## 出力形式

### 1. セットアップ手順書

ボード種類に応じた手順を出力：

```markdown
# {ボード名} CircuitPython セットアップ手順

## Step 1: CircuitPython UF2 のダウンロード

**ダウンロードURL**: {URL}
**バージョン**: 9.x.x（最新安定版推奨）

## Step 2: BOOTSEL モードでの書き込み

1. ボードのBOOTSELボタンを押しながらUSB接続
2. 「RPI-RP2」ドライブが表示される
3. ダウンロードした .uf2 ファイルをドラッグ＆ドロップ
4. 自動的に再起動し「CIRCUITPY」ドライブが表示される

## Step 3: 必要ライブラリのインストール

{ライブラリ一覧}

## Step 4: settings.toml の配置

{設定テンプレート}

## Step 5: 動作確認

{チェックリスト}
```

### 2. 必要ライブラリ一覧

ボード・用途に応じたライブラリを提示：

#### Pico W / Pico 2 W（WiFi）

| ライブラリ | 用途 | 必須 |
|-----------|------|------|
| adafruit_requests | HTTP通信 | Yes |
| adafruit_connection_manager | 接続管理 | Yes |
| adafruit_minimqtt | MQTT通信 | Yes（MQTT使用時） |
| adafruit_ntp | 時刻同期 | Optional |
| adafruit_sht4x | SHT40センサー | Optional |
| adafruit_bmp280 | BMP280センサー | Optional |
| adafruit_scd4x | SCD41センサー | Optional |

#### W5500-EVB-Pico（有線Ethernet）

| ライブラリ | 用途 | 必須 |
|-----------|------|------|
| adafruit_wiznet5k | W5500ドライバ | Yes |
| adafruit_requests | HTTP通信 | Yes |
| adafruit_connection_manager | 接続管理 | Yes |
| adafruit_minimqtt | MQTT通信 | Yes（MQTT使用時） |
| adafruit_ntp | 時刻同期 | Optional |

### 3. settings.toml テンプレート

#### Pico W / Pico 2 W 用

```toml
# ============================================================
# CircuitPython WiFi 設定ファイル
# ============================================================
# CIRCUITPY ルートに settings.toml として配置

# ------------------------------------------------------------
# WiFi 設定（必須）
# ------------------------------------------------------------
CIRCUITPY_WIFI_SSID = "your-ssid"
CIRCUITPY_WIFI_PASSWORD = "your-password"

# ------------------------------------------------------------
# Web Workflow 設定（オプション）
# ------------------------------------------------------------
# CIRCUITPY_WEB_API_PORT = 80
# CIRCUITPY_WEB_API_PASSWORD = "your-api-password"

# ------------------------------------------------------------
# MQTT 設定
# ------------------------------------------------------------
[mqtt]
broker = "192.168.1.100"
port = 1883
client_id = "pico-w-01"
# username = ""
# password = ""

# ------------------------------------------------------------
# アプリケーション設定
# ------------------------------------------------------------
[app]
node_id = "pico-h1-sen"
publish_interval = 30
```

#### W5500-EVB-Pico 用

```toml
# ============================================================
# CircuitPython Ethernet 設定ファイル
# ============================================================
# CIRCUITPY ルートに settings.toml として配置

# ------------------------------------------------------------
# ネットワーク設定
# ------------------------------------------------------------
[network]
use_dhcp = false
static_ip = "192.168.1.100"
subnet = "255.255.255.0"
gateway = "192.168.1.1"
dns = "8.8.8.8"

# ------------------------------------------------------------
# MQTT 設定
# ------------------------------------------------------------
[mqtt]
broker = "192.168.1.10"
port = 1883
client_id = "w5500-pico-01"

# ------------------------------------------------------------
# UECS 設定（農業用）
# ------------------------------------------------------------
[uecs]
multicast_address = "224.0.0.1"
port = 16520
room = 1
region = 11
order = 1
priority = 15

# ------------------------------------------------------------
# アプリケーション設定
# ------------------------------------------------------------
[app]
node_id = "pico-h1-uecs"
publish_interval = 30
```

### 4. 動作確認チェックリスト

```markdown
## 動作確認チェックリスト

### 基本確認
- [ ] CIRCUITPYドライブが認識される
- [ ] code.py を配置すると自動実行される
- [ ] シリアルコンソール（REPL）に接続できる
- [ ] Ctrl+C で REPL に入れる

### WiFi確認（Pico W / Pico 2 W）
- [ ] WiFi APに接続できる
- [ ] IPアドレスが取得できる
- [ ] pingに応答する（可能な環境のみ）

### Ethernet確認（W5500-EVB-Pico）
- [ ] リンクLEDが点灯する
- [ ] IPアドレスが設定される
- [ ] pingに応答する

### MQTT確認
- [ ] MQTTブローカーに接続できる
- [ ] トピックにpublishできる
- [ ] subscribeでメッセージを受信できる

### センサー確認
- [ ] I2Cバスでセンサーが検出される
- [ ] センサー値が正常に読み取れる
```

## UF2ダウンロードURL

| ボード | CircuitPython公式ページ |
|--------|------------------------|
| Pico W | https://circuitpython.org/board/raspberry_pi_pico_w/ |
| Pico 2 W | https://circuitpython.org/board/raspberry_pi_pico2_w/ |
| W5500-EVB-Pico | https://circuitpython.org/board/wiznet_w5500_evb_pico/ |
| W5500-EVB-Pico2 | https://circuitpython.org/board/wiznet_w5500_evb_pico2/ |
| Pico | https://circuitpython.org/board/raspberry_pi_pico/ |
| Pico 2 | https://circuitpython.org/board/raspberry_pi_pico2/ |

**Bundle（ライブラリ一式）**: https://circuitpython.org/libraries

## BOOTSELモード詳細手順

### 方法1: ボタン押しながら接続

1. USBケーブルを外した状態で準備
2. ボード上の**BOOTSEL**ボタンを押し続ける
3. ボタンを押したままUSBケーブルを接続
4. 「RPI-RP2」または「RP2350」ドライブが表示されたらボタンを離す

### 方法2: 接続中にリセット

1. USBケーブルを接続したまま
2. **BOOTSEL**ボタンを押し続ける
3. **RUN/RESET**ボタンを押して離す（ない場合はUSB抜き差し）
4. 「RPI-RP2」ドライブが表示されたらBOOTSELを離す

### トラブルシューティング

| 症状 | 対処法 |
|------|--------|
| ドライブが表示されない | 別のUSBケーブルを試す（データ転送対応か確認） |
| CIRCUITPYが表示されない | UF2が正しく書き込まれたか確認、再度BOOTSELモードで書き込み |
| 書き込み中にエラー | ドライブを安全に取り外してから再試行 |

## サンプル対話例

### 例1: Pico W セットアップ（引数指定）

```
User: /pico-setup-wizard pico-w

Claude: # Raspberry Pi Pico W CircuitPython セットアップ手順

## Step 1: CircuitPython UF2 のダウンロード

**ダウンロードURL**: https://circuitpython.org/board/raspberry_pi_pico_w/
**推奨バージョン**: 9.x.x（最新安定版）

ページから「DOWNLOAD .UF2 NOW」をクリックしてください。

## Step 2: BOOTSEL モードでの書き込み

1. Pico WのBOOTSELボタン（白い小さなボタン）を押しながらUSB接続
2. 「RPI-RP2」ドライブがPCに表示される
3. ダウンロードした .uf2 ファイルをドラッグ＆ドロップ
4. 数秒後に自動再起動し「CIRCUITPY」ドライブが表示

## Step 3: 必要ライブラリのインストール

Bundle から以下をCIRCUITPY/libにコピー：
- adafruit_requests.mpy
- adafruit_connection_manager.mpy
- adafruit_minimqtt/ (フォルダごと)

Bundle: https://circuitpython.org/libraries

## Step 4: settings.toml の作成

CIRCUITPYルートに settings.toml を作成：

[WiFi設定テンプレートを出力]

## Step 5: 動作確認

[チェックリストを出力]
```

### 例2: 対話形式でボード選択

```
User: /pico-setup-wizard

Claude: Pico系ボードのセットアップを開始します。

どのボードをセットアップしますか？

1. **pico-w** - Raspberry Pi Pico W（WiFi）
2. **pico2-w** - Raspberry Pi Pico 2 W（WiFi、RP2350）
3. **w5500-evb-pico** - W5500-EVB-Pico（有線Ethernet）
4. **w5500-evb-pico2** - W5500-EVB-Pico2（有線、RP2350）
5. **pico** - Raspberry Pi Pico（無線なし）
6. **pico2** - Raspberry Pi Pico 2（無線なし）

番号またはボードIDを入力してください。

User: 3

Claude: W5500-EVB-Pico のセットアップを開始します。

[W5500-EVB-Pico用のセットアップ手順を出力]
```

### 例3: センサー用途を指定

```
User: /pico-setup-wizard pico-w --sensors sht40,bmp280

Claude: Raspberry Pi Pico W + センサー（SHT40, BMP280）構成でセットアップします。

## 追加で必要なライブラリ

- adafruit_sht4x.mpy
- adafruit_bmp280.mpy
- adafruit_bus_device/ (フォルダごと)
- adafruit_register/ (フォルダごと)

## I2C接続

| センサー | アドレス | 接続ピン |
|---------|---------|---------|
| SHT40 | 0x44 | GP4(SDA), GP5(SCL) |
| BMP280 | 0x76/0x77 | GP4(SDA), GP5(SCL) |

[以下、セットアップ手順を出力]
```

## 関連スキル

- **circuitpython-toml-config**: settings.toml読み込みモジュール生成
- **pico-wifi-mqtt-template**: WiFi+MQTT統合マネージャー生成
- **env-derived-values-calculator**: 温湿度から飽差等を計算

## 注意事項

- CircuitPythonのバージョンとライブラリバンドルのバージョンは合わせること
- Pico 2 / Pico 2 W はRP2350搭載のため、専用のUF2が必要
- W5500系はSPI接続のため、ピン設定に注意
