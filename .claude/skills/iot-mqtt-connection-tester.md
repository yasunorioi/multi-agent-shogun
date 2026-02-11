# IoT MQTT Connection Tester - Skill Definition

**Skill ID**: `iot-mqtt-connection-tester`
**Category**: IoT / Testing / MQTT
**Version**: 1.0.0
**Created**: 2026-02-07
**Platform**: Linux (Ubuntu 22.04+), Python 3.10+, paho-mqtt

---

## Overview

IoTデバイスとMQTTブローカー間の接続テストを自動化するスキル。
paho-mqttを使用し、接続・Publish・Subscribe・QoS・LWT（Last Will and Testament）の検証を行う。
テスト結果はJSON/YAMLで構造化出力し、CI/CDパイプラインにも組み込み可能。

**Core Capability**: MQTTブローカーへの接続確認、メッセージ送受信の検証、接続品質の定量評価を自動実行する。

---

## Use Cases

### 1. デバイス導入時の受け入れテスト
- 新規IoTデバイスのMQTT接続確認
- ブローカー設定の正当性検証
- ネットワーク疎通確認（TCP + MQTT層）

### 2. 運用監視
- 定期的な接続ヘルスチェック
- ブローカー負荷時の接続品質測定
- メッセージ配信遅延の計測

### 3. 障害切り分け
- デバイス側 vs ブローカー側の障害特定
- ネットワーク経路の問題診断
- 認証・ACL設定の検証

### 4. CI/CDパイプライン統合
- ファームウェア更新後のMQTT回帰テスト
- ブローカー設定変更後の互換性テスト
- 自動テストスイートへの組み込み

---

## Skill Input

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| `broker_host` | string | （必須） | MQTTブローカーのホスト名/IP |
| `broker_port` | int | `1883` | MQTTポート |
| `client_id` | string | `iot-tester-{timestamp}` | クライアントID |
| `username` | string | `None` | 認証ユーザー名（オプション） |
| `password` | string | `None` | 認証パスワード（オプション） |
| `topic_prefix` | string | `test/iot` | テストトピックのプレフィックス |
| `qos` | int | `1` | テストで使用するQoSレベル (0/1/2) |
| `timeout` | int | `10` | 各テストのタイムアウト（秒） |
| `tls_enabled` | bool | `False` | TLS接続の使用 |

---

## Generated Output

### テストスクリプト: `iot_mqtt_connection_test.py`

```python
#!/usr/bin/env python3
"""
IoT MQTT Connection Tester
paho-mqttによるMQTTブローカー接続テスト自動化。

Usage:
    python3 iot_mqtt_connection_test.py --broker 192.168.15.14
    python3 iot_mqtt_connection_test.py --broker 192.168.15.14 --port 8883 --tls
    python3 iot_mqtt_connection_test.py --broker 192.168.15.14 --user admin --pass secret
"""

import argparse
import json
import sys
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt


class MQTTConnectionTester:
    """MQTT接続テスト自動化クラス"""

    def __init__(self, broker: str, port: int = 1883,
                 client_id: str = None, timeout: int = 10):
        self.broker = broker
        self.port = port
        self.client_id = client_id or f"iot-tester-{int(time.time())}"
        self.timeout = timeout
        self.results = []
        self._received_messages = []
        self._connected = threading.Event()
        self._message_received = threading.Event()

    def test_tcp_connection(self) -> bool:
        """TCP接続テスト（MQTTの前段確認）"""
        import socket
        try:
            sock = socket.create_connection(
                (self.broker, self.port), timeout=self.timeout
            )
            sock.close()
            self._record("tcp_connection", True, f"{self.broker}:{self.port} reachable")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self._record("tcp_connection", False, str(e))
            return False

    def test_mqtt_connect(self, username: str = None,
                          password: str = None,
                          tls: bool = False) -> bool:
        """MQTT CONNECT/CONNACKテスト"""
        client = mqtt.Client(
            client_id=self.client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        if username:
            client.username_pw_set(username, password)
        if tls:
            client.tls_set()

        connect_result = {"rc": -1}

        def on_connect(client, userdata, flags, reason_code, properties):
            connect_result["rc"] = reason_code.value if hasattr(reason_code, 'value') else int(reason_code)
            self._connected.set()

        client.on_connect = on_connect

        try:
            client.connect(self.broker, self.port, keepalive=self.timeout)
            client.loop_start()

            if self._connected.wait(timeout=self.timeout):
                ok = connect_result["rc"] == 0
                detail = f"CONNACK rc={connect_result['rc']}"
                if not ok:
                    detail += f" ({self._rc_to_string(connect_result['rc'])})"
            else:
                ok = False
                detail = f"Connection timeout ({self.timeout}s)"

            client.disconnect()
            client.loop_stop()
            self._record("mqtt_connect", ok, detail)
            return ok

        except Exception as e:
            self._record("mqtt_connect", False, str(e))
            return False

    def test_mqtt_publish(self, topic: str = "test/iot/pub",
                          qos: int = 1) -> bool:
        """MQTT Publishテスト"""
        client = mqtt.Client(
            client_id=f"{self.client_id}-pub",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        try:
            client.connect(self.broker, self.port, keepalive=self.timeout)
            client.loop_start()
            time.sleep(0.5)

            payload = json.dumps({
                "test": True,
                "timestamp": datetime.now().isoformat(),
                "client_id": self.client_id,
            })

            info = client.publish(topic, payload, qos=qos)
            info.wait_for_publish(timeout=self.timeout)
            ok = info.is_published()

            client.disconnect()
            client.loop_stop()

            self._record("mqtt_publish", ok,
                         f"topic={topic}, qos={qos}, mid={info.mid}")
            return ok

        except Exception as e:
            self._record("mqtt_publish", False, str(e))
            return False

    def test_mqtt_subscribe(self, topic: str = "test/iot/sub",
                            qos: int = 1) -> bool:
        """MQTT Subscribe + メッセージ受信テスト"""
        client = mqtt.Client(
            client_id=f"{self.client_id}-sub",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._message_received.clear()

        def on_message(client, userdata, msg):
            self._received_messages.append({
                "topic": msg.topic,
                "payload": msg.payload.decode("utf-8", errors="replace"),
                "qos": msg.qos,
            })
            self._message_received.set()

        client.on_message = on_message

        try:
            client.connect(self.broker, self.port, keepalive=self.timeout)
            client.subscribe(topic, qos=qos)
            client.loop_start()

            # テストメッセージをPublish
            pub_client = mqtt.Client(
                client_id=f"{self.client_id}-sub-pub",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
            pub_client.connect(self.broker, self.port)
            pub_client.publish(topic, json.dumps({"test_sub": True}), qos=qos)
            pub_client.disconnect()

            ok = self._message_received.wait(timeout=self.timeout)

            client.disconnect()
            client.loop_stop()

            detail = f"topic={topic}, received={len(self._received_messages)} msgs"
            self._record("mqtt_subscribe", ok, detail)
            return ok

        except Exception as e:
            self._record("mqtt_subscribe", False, str(e))
            return False

    def test_mqtt_roundtrip_latency(self, topic: str = "test/iot/latency",
                                    iterations: int = 5) -> bool:
        """MQTT往復遅延計測"""
        client = mqtt.Client(
            client_id=f"{self.client_id}-lat",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        latencies = []
        recv_event = threading.Event()

        def on_message(client, userdata, msg):
            recv_event.set()

        client.on_message = on_message

        try:
            client.connect(self.broker, self.port, keepalive=self.timeout)
            client.subscribe(topic, qos=0)
            client.loop_start()
            time.sleep(0.5)

            for i in range(iterations):
                recv_event.clear()
                start = time.monotonic()
                client.publish(topic, f"ping-{i}", qos=0)
                if recv_event.wait(timeout=self.timeout):
                    latencies.append((time.monotonic() - start) * 1000)
                time.sleep(0.1)

            client.disconnect()
            client.loop_stop()

            if latencies:
                avg = sum(latencies) / len(latencies)
                ok = avg < 1000  # 1秒未満なら合格
                detail = (f"avg={avg:.1f}ms, min={min(latencies):.1f}ms, "
                          f"max={max(latencies):.1f}ms, samples={len(latencies)}/{iterations}")
            else:
                ok = False
                detail = "No responses received"

            self._record("mqtt_roundtrip_latency", ok, detail)
            return ok

        except Exception as e:
            self._record("mqtt_roundtrip_latency", False, str(e))
            return False

    def test_mqtt_lwt(self, topic: str = "test/iot/lwt") -> bool:
        """LWT（Last Will and Testament）設定テスト"""
        client = mqtt.Client(
            client_id=f"{self.client_id}-lwt",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        try:
            client.will_set(topic, payload="device_offline", qos=1, retain=True)
            client.connect(self.broker, self.port, keepalive=self.timeout)
            client.loop_start()
            time.sleep(0.5)

            # LWT設定付きで接続成功 = テスト合格
            # （実際のLWT発火は異常切断時のみ）
            client.disconnect()
            client.loop_stop()

            self._record("mqtt_lwt_setup", True, f"LWT set on {topic}")
            return True

        except Exception as e:
            self._record("mqtt_lwt_setup", False, str(e))
            return False

    def _record(self, test_name: str, passed: bool, detail: str):
        """テスト結果記録"""
        self.results.append({
            "test": test_name,
            "passed": passed,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        })

    @staticmethod
    def _rc_to_string(rc: int) -> str:
        """MQTT RCコードの文字列表現"""
        codes = {
            0: "Connection Accepted",
            1: "Unacceptable Protocol Version",
            2: "Identifier Rejected",
            3: "Server Unavailable",
            4: "Bad Username/Password",
            5: "Not Authorized",
        }
        return codes.get(rc, f"Unknown ({rc})")

    def run_all(self, topic_prefix: str = "test/iot",
                qos: int = 1,
                username: str = None,
                password: str = None,
                tls: bool = False) -> dict:
        """全テスト実行"""
        print(f"=== IoT MQTT Connection Test ===")
        print(f"Broker: {self.broker}:{self.port}")
        print(f"Client ID: {self.client_id}")
        print(f"QoS: {qos}, TLS: {tls}")
        print()

        # Step 1: TCP接続
        if not self.test_tcp_connection():
            return self._summary()

        # Step 2: MQTT接続
        if not self.test_mqtt_connect(username, password, tls):
            return self._summary()

        # Step 3: Publish
        self.test_mqtt_publish(f"{topic_prefix}/pub", qos)

        # Step 4: Subscribe
        self.test_mqtt_subscribe(f"{topic_prefix}/sub", qos)

        # Step 5: 往復遅延
        self.test_mqtt_roundtrip_latency(f"{topic_prefix}/latency")

        # Step 6: LWT設定
        self.test_mqtt_lwt(f"{topic_prefix}/lwt")

        return self._summary()

    def _summary(self) -> dict:
        """結果サマリ"""
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        overall = "PASS" if passed == total else "FAIL"
        print(f"\n=== Results: {passed}/{total} {overall} ===")
        for r in self.results:
            status = "✅" if r["passed"] else "❌"
            print(f"  {status} {r['test']}: {r['detail'][:80]}")

        return {
            "overall": overall,
            "passed": passed,
            "total": total,
            "broker": f"{self.broker}:{self.port}",
            "results": self.results,
        }


def main():
    parser = argparse.ArgumentParser(description="IoT MQTT Connection Tester")
    parser.add_argument("--broker", required=True, help="MQTT broker host/IP")
    parser.add_argument("--port", type=int, default=1883, help="MQTT port")
    parser.add_argument("--client-id", default=None, help="Client ID")
    parser.add_argument("--user", default=None, help="Username")
    parser.add_argument("--password", default=None, help="Password")
    parser.add_argument("--topic-prefix", default="test/iot", help="Topic prefix")
    parser.add_argument("--qos", type=int, default=1, choices=[0, 1, 2], help="QoS level")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout (sec)")
    parser.add_argument("--tls", action="store_true", help="Enable TLS")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    tester = MQTTConnectionTester(args.broker, args.port, args.client_id, args.timeout)
    result = tester.run_all(
        topic_prefix=args.topic_prefix,
        qos=args.qos,
        username=args.user,
        password=args.password,
        tls=args.tls,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
```

---

## Test Matrix

| テスト | 確認内容 | 合格条件 |
|--------|---------|---------|
| TCP接続 | ブローカーへのTCPリーチ | ポート到達可能 |
| MQTT接続 | CONNECT/CONNACK | RC=0 |
| Publish | メッセージ送信 | is_published()=True |
| Subscribe | メッセージ受信 | タイムアウト内に1件以上受信 |
| 往復遅延 | Pub→Sub遅延 | 平均1000ms未満 |
| LWT設定 | Last Will設定 | 接続成功 |

---

## Dependencies

| パッケージ | バージョン | 用途 |
|-----------|----------|------|
| `paho-mqtt` | 2.0+ | MQTTクライアント |

### インストール

```bash
pip install paho-mqtt
```

---

## Troubleshooting

| 症状 | 原因 | 対処 |
|------|------|------|
| TCP接続失敗 | ブローカー未起動/ファイアウォール | `netstat -tlnp \| grep 1883` 確認 |
| RC=4 (Bad Username/Password) | 認証情報誤り | `--user` `--password` を確認 |
| RC=5 (Not Authorized) | ACL設定 | ブローカーのACL設定を確認 |
| Subscribe受信なし | トピック不一致/QoS問題 | `mosquitto_sub -t '#' -v` で全トピック確認 |
| 高遅延 (>500ms) | ネットワーク負荷/ブローカー過負荷 | ブローカーのリソース確認 |
