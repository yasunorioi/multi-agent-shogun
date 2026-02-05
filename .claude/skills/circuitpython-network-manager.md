# CircuitPython Network Manager

CircuitPython/MicroPython用のネットワーク再接続モジュールを生成するスキル。

## 概要

WiFiまたはEthernet(W5500)接続の自動再接続機能を持つネットワーク管理モジュールを生成する。接続断時のリトライ、ウォッチドッグ連携、状態監視機能を含む。

## 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- WiFi/Ethernet再接続機能
- ネットワーク監視モジュール
- 接続断時の自動復旧
- Pico W / W5500 用ネットワークマネージャー

## 入力パラメータ

| パラメータ | 説明 | デフォルト |
|-----------|------|-----------|
| network_type | wifi / ethernet | wifi |
| mcu | pico_w / esp32 / w5500_evb_pico | pico_w |
| max_retries | 最大リトライ回数 | 5 |
| retry_delay | 初期リトライ間隔(秒) | 2.0 |
| use_dhcp | DHCP使用 | false |
| watchdog_enabled | ウォッチドッグ連携 | true |

## 出力形式

使用可能なPythonモジュール（network_manager.py または wifi_manager.py）を生成。

## サンプル出力

### WiFi版 (Pico W用)

```python
"""
WiFi Manager - Pico W ネットワーク再接続モジュール
CircuitPython用

機能:
- WiFi接続監視
- 切断検知時の自動再接続
- リトライ回数制限（exponential backoff）
- ウォッチドッグタイマー対応
"""

import time
import wifi
import socketpool

try:
    from microcontroller import watchdog as wdt
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class WiFiManager:
    """WiFi接続管理クラス"""

    # デフォルト設定
    DEFAULT_MAX_RETRIES = 5
    DEFAULT_RETRY_DELAY = 2.0
    DEFAULT_BACKOFF_MULTIPLIER = 2.0
    DEFAULT_MAX_DELAY = 60.0

    def __init__(
        self,
        ssid,
        password,
        max_retries=None,
        retry_delay=None,
        enable_watchdog_feed=True,
        log_callback=None,
    ):
        """
        WiFiManager初期化

        Args:
            ssid: WiFi SSID
            password: WiFiパスワード
            max_retries: 最大リトライ回数 (default: 5)
            retry_delay: 初期リトライ間隔(秒) (default: 2.0)
            enable_watchdog_feed: ウォッチドッグフィード有効化 (default: True)
            log_callback: カスタムログ関数 (default: print)
        """
        self._ssid = ssid
        self._password = password
        self._max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self._retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        self._enable_watchdog_feed = enable_watchdog_feed
        self._log = log_callback or print

        self._pool = None
        self._retry_count = 0
        self._connected = False

    def _feed_watchdog(self):
        """ウォッチドッグタイマーをフィード"""
        if self._enable_watchdog_feed and WATCHDOG_AVAILABLE:
            try:
                wdt.feed()
            except Exception:
                pass

    def connect(self):
        """
        WiFi接続を確立

        Returns:
            bool: 接続成功時True
        """
        self._log("[WiFiManager] Connecting...")
        self._feed_watchdog()

        try:
            wifi.radio.connect(self._ssid, self._password)
            self._pool = socketpool.SocketPool(wifi.radio)
            self._connected = True
            self._retry_count = 0
            self._log(f"[WiFiManager] Connected: {wifi.radio.ipv4_address}")
            return True

        except Exception as e:
            self._log(f"[WiFiManager] Connection failed: {e}")
            self._connected = False
            return False

    def reconnect(self):
        """
        自動再接続（リトライ制限付き）

        Returns:
            bool: 再接続成功時True
        """
        self._log("[WiFiManager] Starting reconnection...")
        delay = self._retry_delay

        while self._retry_count < self._max_retries:
            self._retry_count += 1
            self._feed_watchdog()

            self._log(
                f"[WiFiManager] Reconnect attempt {self._retry_count}/{self._max_retries}"
            )

            try:
                # 既存接続をリセット
                try:
                    wifi.radio.enabled = False
                    time.sleep(0.5)
                    wifi.radio.enabled = True
                except Exception:
                    pass

                self._feed_watchdog()

                if self.connect():
                    self._log("[WiFiManager] Reconnection successful")
                    return True

            except Exception as e:
                self._log(f"[WiFiManager] Reconnect error: {e}")

            # 次のリトライまで待機（exponential backoff）
            self._log(f"[WiFiManager] Waiting {delay:.1f}s before next retry...")
            self._wait_with_watchdog(delay)
            delay = min(delay * self.DEFAULT_BACKOFF_MULTIPLIER, self.DEFAULT_MAX_DELAY)

        self._log(
            f"[WiFiManager] Reconnection failed after {self._max_retries} attempts"
        )
        return False

    def _wait_with_watchdog(self, total_seconds):
        """ウォッチドッグをフィードしながら待機"""
        elapsed = 0
        interval = 1.0

        while elapsed < total_seconds:
            wait_time = min(interval, total_seconds - elapsed)
            time.sleep(wait_time)
            elapsed += wait_time
            self._feed_watchdog()

    def is_connected(self):
        """
        接続状態確認

        Returns:
            bool: 接続中True
        """
        if not self._connected:
            return False

        try:
            return wifi.radio.connected
        except Exception:
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

        self._log("[WiFiManager] Connection lost, attempting reconnect...")
        self._connected = False
        return self.reconnect()

    def get_pool(self):
        """SocketPoolを取得"""
        return self._pool

    def get_ip_address(self):
        """IPアドレスを取得"""
        if not self._connected:
            return "0.0.0.0"
        return str(wifi.radio.ipv4_address)

    def get_rssi(self):
        """電波強度を取得"""
        try:
            return wifi.radio.ap_info.rssi
        except Exception:
            return None

    @property
    def max_retries(self):
        return self._max_retries

    @max_retries.setter
    def max_retries(self, value):
        self._max_retries = max(1, int(value))


# ============================================================
# 使用例
# ============================================================
if __name__ == "__main__":
    # 設定
    WIFI_SSID = "YourSSID"
    WIFI_PASSWORD = "YourPassword"

    # WiFiManager初期化
    wifi_mgr = WiFiManager(
        ssid=WIFI_SSID,
        password=WIFI_PASSWORD,
        max_retries=5,
        retry_delay=2.0,
    )

    # 接続
    if wifi_mgr.connect():
        print(f"Connected: {wifi_mgr.get_ip_address()}")
        print(f"RSSI: {wifi_mgr.get_rssi()} dBm")

        # メインループ
        while True:
            # 定期的に接続確認
            if not wifi_mgr.check_and_reconnect():
                print("Network unavailable - entering safe mode")
                break

            # 通常処理
            time.sleep(10)
    else:
        print("Initial connection failed")
```

### Ethernet版 (W5500用)

```python
"""
Network Manager - W5500 ネットワーク再接続モジュール
CircuitPython用 (W5500-EVB-Pico/Pico2対応)

機能:
- ネットワーク接続監視
- 切断検知時の自動再接続
- リトライ回数制限
- ウォッチドッグタイマー対応
"""

import time
import board
import busio
import digitalio

try:
    from microcontroller import watchdog as wdt
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from adafruit_wiznet5k.adafruit_wiznet5k import WIZNET5K


class NetworkManager:
    """W5500ネットワーク接続管理クラス"""

    DEFAULT_MAX_RETRIES = 5
    DEFAULT_RETRY_DELAY = 2.0
    DEFAULT_BACKOFF_MULTIPLIER = 2.0
    DEFAULT_MAX_DELAY = 60.0

    def __init__(
        self,
        ip_address,
        subnet_mask,
        gateway,
        dns_server,
        max_retries=None,
        retry_delay=None,
        use_dhcp=False,
        enable_watchdog_feed=True,
        log_callback=None,
    ):
        """
        NetworkManager初期化

        Args:
            ip_address: IPアドレス (tuple: (192, 168, 1, 100))
            subnet_mask: サブネットマスク (tuple)
            gateway: ゲートウェイ (tuple)
            dns_server: DNSサーバー (tuple)
            max_retries: 最大リトライ回数 (default: 5)
            retry_delay: 初期リトライ間隔(秒) (default: 2.0)
            use_dhcp: DHCP使用フラグ (default: False)
            enable_watchdog_feed: ウォッチドッグフィード有効化 (default: True)
            log_callback: カスタムログ関数 (default: print)
        """
        self._ip_address = ip_address
        self._subnet_mask = subnet_mask
        self._gateway = gateway
        self._dns_server = dns_server
        self._use_dhcp = use_dhcp

        self._max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self._retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        self._enable_watchdog_feed = enable_watchdog_feed
        self._log = log_callback or print

        self._eth = None
        self._spi = None
        self._cs = None
        self._retry_count = 0
        self._connected = False

    def _feed_watchdog(self):
        """ウォッチドッグタイマーをフィード"""
        if self._enable_watchdog_feed and WATCHDOG_AVAILABLE:
            try:
                wdt.feed()
            except Exception:
                pass

    def _init_hardware(self):
        """W5500ハードウェア初期化"""
        # W5500-EVB-Pico2 ピン配置
        self._cs = digitalio.DigitalInOut(board.GP17)
        self._spi = busio.SPI(board.GP18, MOSI=board.GP19, MISO=board.GP16)
        self._log("[NetworkManager] Hardware initialized")

    def _configure_network(self):
        """ネットワーク設定を適用"""
        self._eth = WIZNET5K(self._spi, self._cs, is_dhcp=self._use_dhcp)

        if not self._use_dhcp:
            self._eth.ifconfig = (
                self._ip_address,
                self._subnet_mask,
                self._gateway,
                self._dns_server,
            )

        self._log(f"[NetworkManager] IP: {self._eth.pretty_ip(self._eth.ip_address)}")

    def connect(self):
        """ネットワーク接続を確立"""
        self._log("[NetworkManager] Connecting...")
        self._feed_watchdog()

        try:
            if self._spi is None:
                self._init_hardware()

            self._configure_network()

            if self.is_link_up():
                self._connected = True
                self._retry_count = 0
                self._log("[NetworkManager] Connected successfully")
                return True
            else:
                self._log("[NetworkManager] Link down")
                self._connected = False
                return False

        except Exception as e:
            self._log(f"[NetworkManager] Connection failed: {e}")
            self._connected = False
            return False

    def reconnect(self):
        """自動再接続（リトライ制限付き）"""
        self._log("[NetworkManager] Starting reconnection...")
        delay = self._retry_delay

        while self._retry_count < self._max_retries:
            self._retry_count += 1
            self._feed_watchdog()

            self._log(
                f"[NetworkManager] Reconnect attempt {self._retry_count}/{self._max_retries}"
            )

            try:
                self._reset_hardware()
                time.sleep(0.5)
                self._feed_watchdog()

                if self.connect():
                    return True

            except Exception as e:
                self._log(f"[NetworkManager] Reconnect error: {e}")

            self._wait_with_watchdog(delay)
            delay = min(delay * self.DEFAULT_BACKOFF_MULTIPLIER, self.DEFAULT_MAX_DELAY)

        self._log(f"[NetworkManager] Reconnection failed")
        return False

    def _reset_hardware(self):
        """ハードウェアリセット"""
        if self._spi:
            try:
                self._spi.deinit()
            except Exception:
                pass
        if self._cs:
            try:
                self._cs.deinit()
            except Exception:
                pass

        self._spi = None
        self._cs = None
        self._eth = None
        self._connected = False

    def _wait_with_watchdog(self, total_seconds):
        """ウォッチドッグフィードしながら待機"""
        elapsed = 0
        while elapsed < total_seconds:
            time.sleep(min(1.0, total_seconds - elapsed))
            elapsed += 1.0
            self._feed_watchdog()

    def is_link_up(self):
        """リンク状態確認"""
        if self._eth is None:
            return False
        try:
            return bool(self._eth.link_status)
        except Exception:
            return False

    def is_connected(self):
        """接続状態確認"""
        return self._connected and self.is_link_up()

    def check_and_reconnect(self):
        """接続確認・再接続"""
        self._feed_watchdog()
        if self.is_connected():
            return True
        self._connected = False
        return self.reconnect()

    def get_eth(self):
        """W5500インスタンスを取得"""
        return self._eth

    def get_ip_address(self):
        """IPアドレスを取得"""
        if self._eth is None:
            return "0.0.0.0"
        return self._eth.pretty_ip(self._eth.ip_address)
```

## 生成オプション

### WiFi版生成条件
- Pico W / ESP32 使用時
- ワイヤレス接続が必要な場合

### Ethernet版生成条件
- W5500-EVB-Pico / W5500-EVB-Pico2 使用時
- 有線LAN接続が必要な場合

## 機能一覧

| 機能 | 説明 |
|------|------|
| `connect()` | 初期接続 |
| `reconnect()` | 自動再接続（exponential backoff） |
| `is_connected()` | 接続状態確認 |
| `check_and_reconnect()` | 接続確認・必要時再接続 |
| `get_ip_address()` | IPアドレス取得 |

## MQTT統合版

参考実装: `ethernet_mqtt_manager.py`, `wifi_mqtt_manager.py`

ネットワーク再接続に加えて、MQTT接続管理も統合したい場合は、以下の機能を追加：

### 追加機能
- MQTT接続管理（自動接続、再接続）
- サブスクリプション永続化（再接続時に自動復元）
- メッセージ受信コールバック
- QoS対応（0, 1, 2）
- 状態管理（DISCONNECTED → NETWORK_CONNECTING → NETWORK_CONNECTED → MQTT_CONNECTING → CONNECTED）

### クラス構造（MQTT統合版）

```python
class ConnectionState:
    DISCONNECTED = 0
    NETWORK_CONNECTING = 1
    NETWORK_CONNECTED = 2
    MQTT_CONNECTING = 3
    CONNECTED = 4
    ERROR = 5

class NetworkMqttManager:
    # ネットワーク + MQTT統合管理
    def connect()  # Network → MQTT の順に接続
    def reconnect()  # 両方を自動再接続
    def subscribe(topic, qos=1)  # サブスクリプション（永続化）
    def publish(topic, message, qos=0, retain=False)
    def loop(timeout=1.0)  # MQTTメッセージ処理
    def set_on_message(callback)  # メッセージ受信コールバック
```

MQTT統合版の詳細は参考実装を参照のこと。

## 使用例

```
User: Pico WでWiFi再接続機能が欲しい
Assistant: [WiFi版 network_manager.py を生成]

User: W5500-EVB-Pico2でネットワーク監視モジュールを作って
Assistant: [Ethernet版 network_manager.py を生成]

User: WiFi + MQTT の統合マネージャーが欲しい
Assistant: [WiFi+MQTT統合版 wifi_mqtt_manager.py を生成]
```
