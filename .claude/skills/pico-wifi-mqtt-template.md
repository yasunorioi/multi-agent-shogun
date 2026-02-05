# pico-wifi-mqtt-template

Raspberry Pi Pico W用WiFi+MQTT統合マネージャーのテンプレートを生成するスキル。

## 概要

IoTセンサーノード開発で必要となるWiFi接続管理とMQTT通信を統合したマネージャーモジュールを自動生成する。
CircuitPython/MicroPython両対応。自動再接続、exponential backoff、ウォッチドッグ対応。

## 使用方法

```
/pico-wifi-mqtt-template [プラットフォーム] [オプション...]
```

### 例

```
/pico-wifi-mqtt-template circuitpython
/pico-wifi-mqtt-template micropython --qos 1 --retain
```

## 入力パラメータ

| パラメータ | 必須 | 説明 | デフォルト |
|-----------|------|------|-----------|
| プラットフォーム | No | circuitpython / micropython | circuitpython |
| --qos | No | MQTT QoSレベル (0, 1) | 0 |
| --retain | No | MQTT retain フラグ | false |
| --keepalive | No | MQTT keepalive秒 | 60 |
| --watchdog | No | ウォッチドッグ有効化 | true |

## 出力形式

2つのファイルを生成：

1. `lib/wifi_mqtt_manager.py` - WiFi+MQTT統合マネージャー
2. `settings_wifi_mqtt.toml` - 設定テンプレート

## サンプル出力

### settings_wifi_mqtt.toml

```toml
# ============================================================
# Pico W WiFi + MQTT 設定ファイル
# ============================================================

# ------------------------------------------------------------
# WiFi設定
# ------------------------------------------------------------
[wifi]
ssid = "YOUR_SSID"
password = "YOUR_PASSWORD"
# 接続タイムアウト（秒）
connect_timeout = 30
# 再接続試行回数
max_retries = 5
# 初期リトライ間隔（秒）
retry_delay = 2.0

# ------------------------------------------------------------
# MQTT設定
# ------------------------------------------------------------
[mqtt]
broker = "192.168.1.100"
port = 1883
# クライアントID（空の場合は自動生成）
client_id = ""
# 認証（不要な場合は空）
username = ""
password = ""
# QoSレベル (0 or 1)
qos = 0
# keepalive秒
keepalive = 60
# retain フラグ
retain = false

# トピック設定
[mqtt.topics]
# 送信トピックのプレフィックス
publish_prefix = "sensor/pico"
# 受信トピック（制御用）
subscribe = ["control/pico/#"]

# ------------------------------------------------------------
# 動作設定
# ------------------------------------------------------------
[behavior]
# センサー読み取り間隔（秒）
sensor_interval = 10
# ウォッチドッグ有効化
watchdog_enabled = true
# ウォッチドッグタイムアウト（秒）
watchdog_timeout = 30
```

### lib/wifi_mqtt_manager.py (CircuitPython版)

```python
"""
WiFi + MQTT 統合マネージャー for Pico W (CircuitPython)

機能:
- WiFi自動接続・再接続
- MQTT接続・再接続
- exponential backoff
- ウォッチドッグタイマー対応
- 状態コールバック

使用例:
    from lib.wifi_mqtt_manager import WiFiMQTTManager

    def on_message(topic, payload):
        print(f"Received: {topic} -> {payload}")

    manager = WiFiMQTTManager(
        wifi_ssid="YOUR_SSID",
        wifi_password="YOUR_PASSWORD",
        mqtt_broker="192.168.1.100",
        on_message=on_message
    )

    if manager.connect():
        manager.publish("sensor/temp", "25.5")
"""

import time
import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT

try:
    from microcontroller import watchdog as wdt
    from watchdog import WatchDogMode
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class WiFiMQTTManager:
    """WiFi + MQTT 統合マネージャー"""

    # デフォルト設定
    DEFAULT_WIFI_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_RETRY_DELAY = 2.0
    DEFAULT_BACKOFF_MULTIPLIER = 2.0
    DEFAULT_MAX_DELAY = 60.0
    DEFAULT_MQTT_PORT = 1883
    DEFAULT_KEEPALIVE = 60

    # 状態定数
    STATE_DISCONNECTED = 0
    STATE_WIFI_CONNECTING = 1
    STATE_WIFI_CONNECTED = 2
    STATE_MQTT_CONNECTING = 3
    STATE_CONNECTED = 4
    STATE_ERROR = -1

    def __init__(
        self,
        wifi_ssid,
        wifi_password,
        mqtt_broker,
        mqtt_port=None,
        mqtt_client_id=None,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_qos=0,
        mqtt_keepalive=None,
        wifi_timeout=None,
        max_retries=None,
        retry_delay=None,
        on_connect=None,
        on_disconnect=None,
        on_message=None,
        on_state_change=None,
        enable_watchdog=True,
        watchdog_timeout=30,
        log_callback=None,
    ):
        """
        WiFiMQTTManager初期化

        Args:
            wifi_ssid: WiFi SSID
            wifi_password: WiFiパスワード
            mqtt_broker: MQTTブローカーアドレス
            mqtt_port: MQTTポート (default: 1883)
            mqtt_client_id: MQTTクライアントID (default: 自動生成)
            mqtt_username: MQTT認証ユーザー名
            mqtt_password: MQTT認証パスワード
            mqtt_qos: MQTT QoS (0 or 1)
            mqtt_keepalive: MQTT keepalive秒
            wifi_timeout: WiFi接続タイムアウト秒
            max_retries: 最大リトライ回数
            retry_delay: 初期リトライ間隔秒
            on_connect: 接続時コールバック
            on_disconnect: 切断時コールバック
            on_message: メッセージ受信コールバック (topic, payload)
            on_state_change: 状態変化コールバック (new_state)
            enable_watchdog: ウォッチドッグ有効化
            watchdog_timeout: ウォッチドッグタイムアウト秒
            log_callback: ログ出力関数
        """
        # WiFi設定
        self._wifi_ssid = wifi_ssid
        self._wifi_password = wifi_password
        self._wifi_timeout = wifi_timeout or self.DEFAULT_WIFI_TIMEOUT

        # MQTT設定
        self._mqtt_broker = mqtt_broker
        self._mqtt_port = mqtt_port or self.DEFAULT_MQTT_PORT
        self._mqtt_client_id = mqtt_client_id or self._generate_client_id()
        self._mqtt_username = mqtt_username
        self._mqtt_password = mqtt_password
        self._mqtt_qos = mqtt_qos
        self._mqtt_keepalive = mqtt_keepalive or self.DEFAULT_KEEPALIVE

        # リトライ設定
        self._max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self._retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY

        # コールバック
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_message = on_message
        self._on_state_change = on_state_change

        # ウォッチドッグ
        self._enable_watchdog = enable_watchdog and WATCHDOG_AVAILABLE
        self._watchdog_timeout = watchdog_timeout

        # ログ
        self._log = log_callback or print

        # 内部状態
        self._state = self.STATE_DISCONNECTED
        self._mqtt_client = None
        self._pool = None
        self._retry_count = 0
        self._subscriptions = []

    def _generate_client_id(self):
        """ユニークなクライアントIDを生成"""
        import microcontroller
        uid = microcontroller.cpu.uid
        return f"pico_{uid[-4:].hex()}"

    def _set_state(self, new_state):
        """状態を更新し、コールバックを呼び出す"""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._log(f"[WiFiMQTT] State: {old_state} -> {new_state}")
            if self._on_state_change:
                self._on_state_change(new_state)

    def _feed_watchdog(self):
        """ウォッチドッグをフィード"""
        if self._enable_watchdog:
            try:
                wdt.feed()
            except Exception:
                pass

    def _setup_watchdog(self):
        """ウォッチドッグを設定"""
        if self._enable_watchdog:
            try:
                wdt.timeout = self._watchdog_timeout
                wdt.mode = WatchDogMode.RESET
                self._log(f"[WiFiMQTT] Watchdog enabled: {self._watchdog_timeout}s")
            except Exception as e:
                self._log(f"[WiFiMQTT] Watchdog setup failed: {e}")

    def _wait_with_watchdog(self, seconds):
        """ウォッチドッグをフィードしながら待機"""
        elapsed = 0
        interval = 1.0
        while elapsed < seconds:
            wait = min(interval, seconds - elapsed)
            time.sleep(wait)
            elapsed += wait
            self._feed_watchdog()

    # ========================================
    # WiFi接続
    # ========================================

    def _connect_wifi(self):
        """WiFi接続"""
        self._set_state(self.STATE_WIFI_CONNECTING)
        self._log(f"[WiFiMQTT] Connecting to WiFi: {self._wifi_ssid}")
        self._feed_watchdog()

        try:
            wifi.radio.connect(
                self._wifi_ssid,
                self._wifi_password,
                timeout=self._wifi_timeout
            )
            ip = wifi.radio.ipv4_address
            self._log(f"[WiFiMQTT] WiFi connected: {ip}")
            self._set_state(self.STATE_WIFI_CONNECTED)

            # ソケットプール作成
            self._pool = socketpool.SocketPool(wifi.radio)
            return True

        except Exception as e:
            self._log(f"[WiFiMQTT] WiFi connection failed: {e}")
            self._set_state(self.STATE_ERROR)
            return False

    def _is_wifi_connected(self):
        """WiFi接続状態を確認"""
        return wifi.radio.ipv4_address is not None

    # ========================================
    # MQTT接続
    # ========================================

    def _connect_mqtt(self):
        """MQTT接続"""
        self._set_state(self.STATE_MQTT_CONNECTING)
        self._log(f"[WiFiMQTT] Connecting to MQTT: {self._mqtt_broker}:{self._mqtt_port}")
        self._feed_watchdog()

        try:
            # MQTTクライアント作成
            self._mqtt_client = MQTT.MQTT(
                broker=self._mqtt_broker,
                port=self._mqtt_port,
                client_id=self._mqtt_client_id,
                username=self._mqtt_username,
                password=self._mqtt_password,
                socket_pool=self._pool,
                ssl_context=ssl.create_default_context(),
                keep_alive=self._mqtt_keepalive,
            )

            # コールバック設定
            self._mqtt_client.on_connect = self._mqtt_on_connect
            self._mqtt_client.on_disconnect = self._mqtt_on_disconnect
            self._mqtt_client.on_message = self._mqtt_on_message

            # 接続
            self._mqtt_client.connect()
            self._set_state(self.STATE_CONNECTED)

            # 既存のサブスクリプションを復元
            for topic in self._subscriptions:
                self._mqtt_client.subscribe(topic, self._mqtt_qos)
                self._log(f"[WiFiMQTT] Resubscribed: {topic}")

            return True

        except Exception as e:
            self._log(f"[WiFiMQTT] MQTT connection failed: {e}")
            self._set_state(self.STATE_ERROR)
            return False

    def _mqtt_on_connect(self, client, userdata, flags, rc):
        """MQTT接続時コールバック"""
        self._log(f"[WiFiMQTT] MQTT connected (rc={rc})")
        if self._on_connect:
            self._on_connect()

    def _mqtt_on_disconnect(self, client, userdata, rc):
        """MQTT切断時コールバック"""
        self._log(f"[WiFiMQTT] MQTT disconnected (rc={rc})")
        self._set_state(self.STATE_WIFI_CONNECTED)
        if self._on_disconnect:
            self._on_disconnect()

    def _mqtt_on_message(self, client, topic, payload):
        """MQTTメッセージ受信コールバック"""
        self._log(f"[WiFiMQTT] Message: {topic} -> {payload}")
        if self._on_message:
            self._on_message(topic, payload)

    # ========================================
    # 公開API
    # ========================================

    def connect(self):
        """
        WiFi + MQTT 接続を確立

        Returns:
            bool: 接続成功時True
        """
        self._setup_watchdog()
        self._retry_count = 0

        # WiFi接続
        if not self._connect_wifi():
            return False

        # MQTT接続
        if not self._connect_mqtt():
            return False

        return True

    def reconnect(self):
        """
        自動再接続（exponential backoff）

        Returns:
            bool: 再接続成功時True
        """
        delay = self._retry_delay

        while self._retry_count < self._max_retries:
            self._retry_count += 1
            self._feed_watchdog()
            self._log(f"[WiFiMQTT] Reconnect attempt {self._retry_count}/{self._max_retries}")

            # WiFi確認
            if not self._is_wifi_connected():
                if not self._connect_wifi():
                    self._wait_with_watchdog(delay)
                    delay = min(delay * self.DEFAULT_BACKOFF_MULTIPLIER, self.DEFAULT_MAX_DELAY)
                    continue

            # MQTT接続
            if self._connect_mqtt():
                self._retry_count = 0
                return True

            self._wait_with_watchdog(delay)
            delay = min(delay * self.DEFAULT_BACKOFF_MULTIPLIER, self.DEFAULT_MAX_DELAY)

        self._log(f"[WiFiMQTT] Reconnection failed after {self._max_retries} attempts")
        return False

    def check_and_reconnect(self):
        """
        接続状態を確認し、必要なら再接続

        Returns:
            bool: 接続中（または再接続成功）ならTrue
        """
        self._feed_watchdog()

        if self.is_connected():
            return True

        self._log("[WiFiMQTT] Connection lost, attempting reconnect...")
        return self.reconnect()

    def is_connected(self):
        """
        接続状態を確認

        Returns:
            bool: WiFi+MQTT両方接続中ならTrue
        """
        return (
            self._state == self.STATE_CONNECTED
            and self._is_wifi_connected()
            and self._mqtt_client is not None
            and self._mqtt_client.is_connected()
        )

    def publish(self, topic, payload, retain=False):
        """
        MQTTメッセージを送信

        Args:
            topic: トピック
            payload: ペイロード（文字列）
            retain: retain フラグ

        Returns:
            bool: 送信成功時True
        """
        if not self.is_connected():
            self._log("[WiFiMQTT] Cannot publish: not connected")
            return False

        try:
            self._mqtt_client.publish(topic, payload, retain=retain, qos=self._mqtt_qos)
            return True
        except Exception as e:
            self._log(f"[WiFiMQTT] Publish failed: {e}")
            return False

    def subscribe(self, topic):
        """
        トピックを購読

        Args:
            topic: 購読トピック
        """
        if topic not in self._subscriptions:
            self._subscriptions.append(topic)

        if self.is_connected():
            try:
                self._mqtt_client.subscribe(topic, self._mqtt_qos)
                self._log(f"[WiFiMQTT] Subscribed: {topic}")
            except Exception as e:
                self._log(f"[WiFiMQTT] Subscribe failed: {e}")

    def loop(self, timeout=0.1):
        """
        MQTTループ処理（定期的に呼び出す）

        Args:
            timeout: タイムアウト秒
        """
        self._feed_watchdog()

        if not self.is_connected():
            return

        try:
            self._mqtt_client.loop(timeout)
        except Exception as e:
            self._log(f"[WiFiMQTT] Loop error: {e}")
            self._set_state(self.STATE_ERROR)

    def disconnect(self):
        """切断"""
        if self._mqtt_client:
            try:
                self._mqtt_client.disconnect()
            except Exception:
                pass
        self._set_state(self.STATE_DISCONNECTED)

    @property
    def state(self):
        """現在の状態"""
        return self._state

    @property
    def ip_address(self):
        """IPアドレス"""
        if self._is_wifi_connected():
            return str(wifi.radio.ipv4_address)
        return "0.0.0.0"


# ============================================================
# 使用例
# ============================================================
if __name__ == "__main__":
    def on_message(topic, payload):
        print(f"Received: {topic} -> {payload}")

    def on_connect():
        print("Connected!")

    manager = WiFiMQTTManager(
        wifi_ssid="YOUR_SSID",
        wifi_password="YOUR_PASSWORD",
        mqtt_broker="192.168.1.100",
        on_connect=on_connect,
        on_message=on_message,
    )

    if manager.connect():
        manager.subscribe("control/#")

        while True:
            manager.loop()

            if not manager.check_and_reconnect():
                print("Connection failed - entering safe mode")
                break

            # センサー読み取り・送信
            manager.publish("sensor/temp", "25.5")
            time.sleep(10)
```

## 機能詳細

### 1. 自動接続フロー

```
初期化
  ↓
WiFi接続（タイムアウト付き）
  ↓ 成功
ソケットプール作成
  ↓
MQTT接続
  ↓ 成功
サブスクリプション復元
  ↓
STATE_CONNECTED
```

### 2. 再接続（exponential backoff）

```
接続断検知
  ↓
リトライ1: 2秒待機
  ↓ 失敗
リトライ2: 4秒待機
  ↓ 失敗
リトライ3: 8秒待機
  ↓ 失敗
リトライ4: 16秒待機
  ↓ 失敗
リトライ5: 32秒待機
  ↓ 失敗
最大リトライ到達 → エラー状態
```

### 3. 状態遷移

| 状態 | 値 | 説明 |
|------|---|------|
| DISCONNECTED | 0 | 切断状態 |
| WIFI_CONNECTING | 1 | WiFi接続中 |
| WIFI_CONNECTED | 2 | WiFi接続完了 |
| MQTT_CONNECTING | 3 | MQTT接続中 |
| CONNECTED | 4 | 完全接続 |
| ERROR | -1 | エラー状態 |

### 4. ウォッチドッグ対応

- 長時間のブロッキング処理中も定期的にフィード
- 接続失敗時のハング防止
- 設定可能なタイムアウト

## コールバック

| コールバック | 引数 | 説明 |
|-------------|------|------|
| on_connect | なし | MQTT接続完了時 |
| on_disconnect | なし | MQTT切断時 |
| on_message | topic, payload | メッセージ受信時 |
| on_state_change | new_state | 状態変化時 |

## 使用例（センサーノード）

```python
from lib.wifi_mqtt_manager import WiFiMQTTManager
from lib.config_loader import load_config_safe
import adafruit_sht4x

# 設定読み込み
config = load_config_safe()

# センサー初期化
sht = adafruit_sht4x.SHT4x(i2c)

# コールバック定義
def on_message(topic, payload):
    if topic == "control/interval":
        global interval
        interval = int(payload)

# マネージャー初期化
manager = WiFiMQTTManager(
    wifi_ssid=config.wifi.ssid,
    wifi_password=config.wifi.password,
    mqtt_broker=config.mqtt.broker,
    mqtt_port=config.mqtt.port,
    on_message=on_message,
)

# 接続
if manager.connect():
    manager.subscribe("control/#")

    while True:
        manager.loop()

        if not manager.check_and_reconnect():
            break

        # センサー読み取り・送信
        temp, humid = sht.measurements
        manager.publish(f"sensor/{manager.ip_address}/temp", f"{temp:.1f}")
        manager.publish(f"sensor/{manager.ip_address}/humid", f"{humid:.1f}")

        time.sleep(config.behavior.sensor_interval)
```

## 関連スキル

- circuitpython-toml-config: 設定ファイル読み込み
- env-derived-values-calculator: 飽差等の計算
