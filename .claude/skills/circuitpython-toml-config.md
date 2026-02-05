# circuitpython-toml-config

CircuitPython向けTOML設定読み込みモジュールを生成するスキル。

## 概要

settings.tomlから設定を読み込み、型安全なConfigクラスとして提供するモジュールを自動生成する。
CircuitPython 9.x以降のtomllib対応、古いバージョン用のadafruit_tomlフォールバック付き。

## 使用方法

```
/circuitpython-toml-config [設定セクション名...]
```

### 例

```
/circuitpython-toml-config network uecs sensors debug
```

## 入力パラメータ

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| セクション名 | Yes | TOMLのセクション名（スペース区切りで複数可） |

### 標準セクション

| セクション | 説明 | デフォルト項目 |
|-----------|------|---------------|
| network | ネットワーク設定 | use_dhcp, static_ip, subnet, gateway, dns |
| uecs | UECS設定 | multicast_address, port, room, region, order, priority |
| sensors | センサー設定 | read_interval, enabled(サブセクション) |
| debug | デバッグ設定 | verbose, print_xml |

## 出力形式

2つのファイルを生成：

1. `settings_template.toml` - 設定テンプレート
2. `lib/config_loader.py` - 設定読み込みモジュール

## サンプル出力

### settings_template.toml

```toml
# ============================================================
# CircuitPython 設定ファイル
# ============================================================
# このファイルを settings.toml にリネームして使用
# CIRCUITPY ルートに配置すること

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
# UECS設定
# ------------------------------------------------------------
[uecs]
multicast_address = "224.0.0.1"
port = 16520
room = 1
region = 11
order = 1
priority = 15

# ------------------------------------------------------------
# センサー設定
# ------------------------------------------------------------
[sensors]
read_interval = 10

[sensors.enabled]
sht40 = true
bmp280 = true
scd41 = true

# ------------------------------------------------------------
# デバッグ設定
# ------------------------------------------------------------
[debug]
verbose = false
print_xml = false
```

### lib/config_loader.py

```python
"""
TOML設定読み込みモジュール

settings.toml から設定を読み込み、Config オブジェクトとして提供する。
CircuitPython 9.x 以降対応。

使用例:
    from lib.config_loader import load_config_safe
    config = load_config_safe()
    print(config.network.static_ip)
"""

# CircuitPython の tomllib を使用
try:
    import tomllib
except ImportError:
    try:
        import adafruit_toml as tomllib
    except ImportError:
        tomllib = None


class NetworkConfig:
    """ネットワーク設定"""
    def __init__(self, data: dict):
        self.use_dhcp = data.get("use_dhcp", False)
        self.static_ip = data.get("static_ip", "192.168.1.100")
        self.subnet = data.get("subnet", "255.255.255.0")
        self.gateway = data.get("gateway", "192.168.1.1")
        self.dns = data.get("dns", "8.8.8.8")

    def get_ip_tuple(self, ip_str: str) -> tuple:
        """IP文字列をタプルに変換"""
        return tuple(int(x) for x in ip_str.split("."))

    @property
    def static_ip_tuple(self) -> tuple:
        return self.get_ip_tuple(self.static_ip)

    @property
    def subnet_tuple(self) -> tuple:
        return self.get_ip_tuple(self.subnet)

    @property
    def gateway_tuple(self) -> tuple:
        return self.get_ip_tuple(self.gateway)

    @property
    def dns_tuple(self) -> tuple:
        return self.get_ip_tuple(self.dns)


class UecsConfig:
    """UECS設定"""
    def __init__(self, data: dict):
        self.multicast_address = data.get("multicast_address", "224.0.0.1")
        self.port = data.get("port", 16520)
        self.room = data.get("room", 1)
        self.region = data.get("region", 11)
        self.order = data.get("order", 1)
        self.priority = data.get("priority", 15)


class SensorEnabledConfig:
    """センサー有効/無効設定"""
    def __init__(self, data: dict):
        self.sht40 = data.get("sht40", True)
        self.bmp280 = data.get("bmp280", True)
        self.scd41 = data.get("scd41", True)


class SensorsConfig:
    """センサー設定"""
    def __init__(self, data: dict):
        self.read_interval = data.get("read_interval", 10)
        self.enabled = SensorEnabledConfig(data.get("enabled", {}))


class DebugConfig:
    """デバッグ設定"""
    def __init__(self, data: dict):
        self.verbose = data.get("verbose", False)
        self.print_xml = data.get("print_xml", False)


class Config:
    """設定全体を管理するクラス"""
    def __init__(self, data: dict):
        self.network = NetworkConfig(data.get("network", {}))
        self.uecs = UecsConfig(data.get("uecs", {}))
        self.sensors = SensorsConfig(data.get("sensors", {}))
        self.debug = DebugConfig(data.get("debug", {}))

    def __repr__(self):
        return (
            f"Config(\n"
            f"  network: ip={self.network.static_ip}, dhcp={self.network.use_dhcp}\n"
            f"  uecs: room={self.uecs.room}, region={self.uecs.region}\n"
            f"  sensors: interval={self.sensors.read_interval}s\n"
            f")"
        )


def load_config(config_path: str = "/settings.toml") -> Config:
    """
    設定ファイルを読み込んで Config オブジェクトを返す

    Args:
        config_path: 設定ファイルのパス

    Returns:
        Config: 設定オブジェクト
    """
    if tomllib is None:
        raise RuntimeError(
            "tomllib not available. "
            "CircuitPython 9.x or adafruit_toml required."
        )

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        print(f"[Config] Loaded: {config_path}")
        return Config(data)
    except OSError:
        print(f"[Config] Warning: {config_path} not found, using defaults")
        return Config({})


def load_config_safe(config_path: str = "/settings.toml") -> Config:
    """
    設定ファイルを安全に読み込む（エラー時はデフォルト値を使用）
    """
    try:
        return load_config(config_path)
    except Exception as e:
        print(f"[Config] Error loading config: {e}")
        print("[Config] Using default values")
        return Config({})
```

## 特徴

- **tomllibフォールバック**: CircuitPython 9.x標準のtomllibを使用、古いバージョンではadafruit_tomlにフォールバック
- **型安全なConfigクラス**: 各セクションを専用クラスで管理
- **デフォルト値**: 設定ファイルがなくてもデフォルト値で動作
- **IPタプル変換**: IP文字列をW5500等が要求するタプル形式に変換するプロパティ
- **安全な読み込み**: load_config_safe()でエラー時もデフォルト値で継続

## 使用例

```python
# code.py での使用例
from lib.config_loader import load_config_safe

config = load_config_safe()

# ネットワーク設定
if config.network.use_dhcp:
    eth = WIZNET5K(spi, cs, is_dhcp=True)
else:
    eth = WIZNET5K(spi, cs, is_dhcp=False)
    eth.ifconfig = (
        config.network.static_ip_tuple,
        config.network.subnet_tuple,
        config.network.gateway_tuple,
        config.network.dns_tuple
    )

# UECS設定
uecs_sender = UecsSender(
    eth,
    room=config.uecs.room,
    region=config.uecs.region,
    order=config.uecs.order
)

# センサー有効/無効
if config.sensors.enabled.sht40:
    init_sht40(i2c)
```

## 関連スキル

- env-derived-values-calculator: 温湿度から飽差等を計算
