# wireguard-peer-adder

WireGuardサーバーに新しいピアを追加する手順を自動化するスキル。鍵生成→サーバー設定追記→クライアント設定生成→QRコード生成までを一括で行う。

## メタデータ

| 項目 | 値 |
|------|-----|
| Skill ID | wireguard-peer-adder |
| Category | Network / VPN |
| Version | 1.0.0 |
| Created | 2026-02-07 |
| Platform | Linux (Ubuntu/Debian) |

## Overview

WireGuardサーバーに新規ピア（クライアント）を追加する際、以下の手順を自動化する：

1. クライアント用の秘密鍵・公開鍵・事前共有鍵を生成
2. サーバー側の wg0.conf に [Peer] セクションを追記
3. クライアント用の .conf ファイルを生成
4. QRコード生成（スマートフォン用）
5. WireGuardインターフェースをリロード

## Use Cases

### 1. 新しいデバイスのVPN参加

リモートワーカーの新端末や、IoTデバイスをVPNネットワークに追加する際に使用。

### 2. 複数ピアの一括追加

複数のクライアントを連続して追加する際、手作業ミスを防止。

### 3. スマートフォンのVPN設定

QRコード生成により、WireGuardモバイルアプリでの設定をワンスキャンで完了。

## Skill Input

| パラメータ | 必須 | 説明 | デフォルト |
|-----------|------|------|-----------|
| `PEER_NAME` | Yes | ピアの識別名（例: `laptop-taro`, `phone-hanako`） | - |
| `SERVER_WG_CONF` | No | サーバー側WireGuard設定ファイルパス | `/etc/wireguard/wg0.conf` |
| `SERVER_PUBLIC_KEY` | Yes | サーバーの公開鍵 | - |
| `SERVER_ENDPOINT` | Yes | サーバーのエンドポイント（例: `vpn.example.com:51820`） | - |
| `CLIENT_ADDRESS` | Yes | クライアントに割り当てるVPN内IPアドレス（例: `10.0.0.10/32`） | - |
| `DNS_SERVERS` | No | クライアント用DNSサーバー | `1.1.1.1, 8.8.8.8` |
| `ALLOWED_IPS` | No | クライアントがルーティングするIP範囲 | `0.0.0.0/0, ::/0` |
| `OUTPUT_DIR` | No | 生成ファイルの出力先ディレクトリ | `/etc/wireguard/clients/` |

## Generated Output

### ディレクトリ構造

```
/etc/wireguard/clients/{PEER_NAME}/
├── privatekey          # クライアント秘密鍵（600）
├── publickey           # クライアント公開鍵
├── presharedkey        # 事前共有鍵（600）
├── {PEER_NAME}.conf    # クライアント設定ファイル
└── {PEER_NAME}.png     # QRコード画像
```

### クライアント設定ファイル（生成例）

```ini
[Interface]
# Peer: laptop-taro
PrivateKey = <client_private_key>
Address = 10.0.0.10/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = <server_public_key>
PresharedKey = <preshared_key>
Endpoint = vpn.example.com:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

## Implementation

### 前提条件の確認

```bash
# WireGuardがインストールされているか
which wg || { echo "ERROR: wg not found. Install wireguard-tools"; exit 1; }

# qrencodeがインストールされているか（QRコード生成用）
which qrencode || { echo "WARNING: qrencode not found. QR generation will be skipped"; }

# root権限の確認
[ "$(id -u)" -eq 0 ] || { echo "ERROR: This script must be run as root (sudo)"; exit 1; }
```

### STEP 1: 鍵の生成

```bash
PEER_NAME="laptop-taro"
OUTPUT_DIR="/etc/wireguard/clients/${PEER_NAME}"

# 出力ディレクトリ作成
mkdir -p "${OUTPUT_DIR}"
chmod 700 "${OUTPUT_DIR}"

# 秘密鍵の生成
wg genkey | tee "${OUTPUT_DIR}/privatekey" | wg pubkey > "${OUTPUT_DIR}/publickey"
wg genpsk > "${OUTPUT_DIR}/presharedkey"

# パーミッション設定（秘密鍵・事前共有鍵は所有者のみ読み取り可）
chmod 600 "${OUTPUT_DIR}/privatekey" "${OUTPUT_DIR}/presharedkey"

# 鍵を変数に格納
CLIENT_PRIVATE_KEY=$(cat "${OUTPUT_DIR}/privatekey")
CLIENT_PUBLIC_KEY=$(cat "${OUTPUT_DIR}/publickey")
PRESHARED_KEY=$(cat "${OUTPUT_DIR}/presharedkey")

echo "Client Public Key: ${CLIENT_PUBLIC_KEY}"
```

### STEP 2: サーバー設定に [Peer] を追記

```bash
SERVER_WG_CONF="/etc/wireguard/wg0.conf"
CLIENT_ADDRESS="10.0.0.10/32"

# バックアップ作成
cp "${SERVER_WG_CONF}" "${SERVER_WG_CONF}.bak.$(date +%Y%m%d%H%M%S)"

# [Peer] セクションを追記
cat >> "${SERVER_WG_CONF}" << EOF

# Peer: ${PEER_NAME} (added $(date +%Y-%m-%d))
[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
PresharedKey = ${PRESHARED_KEY}
AllowedIPs = ${CLIENT_ADDRESS}
EOF

echo "Server config updated: ${SERVER_WG_CONF}"
```

### STEP 3: クライアント設定ファイルの生成

```bash
SERVER_PUBLIC_KEY="<your_server_public_key>"
SERVER_ENDPOINT="vpn.example.com:51820"
DNS_SERVERS="1.1.1.1, 8.8.8.8"
ALLOWED_IPS="0.0.0.0/0, ::/0"

cat > "${OUTPUT_DIR}/${PEER_NAME}.conf" << EOF
[Interface]
# Peer: ${PEER_NAME}
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${DNS_SERVERS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
PresharedKey = ${PRESHARED_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = ${ALLOWED_IPS}
PersistentKeepalive = 25
EOF

chmod 600 "${OUTPUT_DIR}/${PEER_NAME}.conf"
echo "Client config created: ${OUTPUT_DIR}/${PEER_NAME}.conf"
```

### STEP 4: QRコード生成

```bash
if command -v qrencode &> /dev/null; then
    qrencode -t png -o "${OUTPUT_DIR}/${PEER_NAME}.png" < "${OUTPUT_DIR}/${PEER_NAME}.conf"
    echo "QR code saved: ${OUTPUT_DIR}/${PEER_NAME}.png"

    # ターミナルにもQRコードを表示（UTF-8）
    qrencode -t ansiutf8 < "${OUTPUT_DIR}/${PEER_NAME}.conf"
else
    echo "WARNING: qrencode not installed. Skipping QR generation."
    echo "Install: sudo apt install qrencode"
fi
```

### STEP 5: WireGuardインターフェースのリロード

```bash
# 方法1: wg syncconf（ダウンタイムなし、推奨）
wg syncconf wg0 <(wg-quick strip wg0)
echo "WireGuard interface reloaded (syncconf)"

# 方法2: インターフェース再起動（syncconfが使えない場合）
# wg-quick down wg0 && wg-quick up wg0
# echo "WireGuard interface restarted"

# ピア一覧で追加を確認
wg show wg0 peers
```

### 一括スクリプト（全STEP統合）

```bash
#!/bin/bash
set -euo pipefail

# ===== 設定 =====
PEER_NAME="${1:?Usage: $0 <peer_name> <client_ip> [server_endpoint]}"
CLIENT_ADDRESS="${2:?Usage: $0 <peer_name> <client_ip> [server_endpoint]}"
SERVER_ENDPOINT="${3:-vpn.example.com:51820}"
SERVER_WG_CONF="/etc/wireguard/wg0.conf"
OUTPUT_DIR="/etc/wireguard/clients/${PEER_NAME}"
DNS_SERVERS="1.1.1.1, 8.8.8.8"
ALLOWED_IPS="0.0.0.0/0, ::/0"

# ===== 前提条件チェック =====
[ "$(id -u)" -eq 0 ] || { echo "ERROR: Run as root"; exit 1; }
command -v wg &> /dev/null || { echo "ERROR: wg not found"; exit 1; }

# サーバー公開鍵を取得
SERVER_PUBLIC_KEY=$(wg show wg0 public-key)

# ===== 鍵生成 =====
mkdir -p "${OUTPUT_DIR}" && chmod 700 "${OUTPUT_DIR}"
wg genkey | tee "${OUTPUT_DIR}/privatekey" | wg pubkey > "${OUTPUT_DIR}/publickey"
wg genpsk > "${OUTPUT_DIR}/presharedkey"
chmod 600 "${OUTPUT_DIR}/privatekey" "${OUTPUT_DIR}/presharedkey"

CLIENT_PRIVATE_KEY=$(cat "${OUTPUT_DIR}/privatekey")
CLIENT_PUBLIC_KEY=$(cat "${OUTPUT_DIR}/publickey")
PRESHARED_KEY=$(cat "${OUTPUT_DIR}/presharedkey")

# ===== サーバー設定追記 =====
cp "${SERVER_WG_CONF}" "${SERVER_WG_CONF}.bak.$(date +%Y%m%d%H%M%S)"
cat >> "${SERVER_WG_CONF}" << EOF

# Peer: ${PEER_NAME} (added $(date +%Y-%m-%d))
[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
PresharedKey = ${PRESHARED_KEY}
AllowedIPs = ${CLIENT_ADDRESS}
EOF

# ===== クライアント設定生成 =====
cat > "${OUTPUT_DIR}/${PEER_NAME}.conf" << EOF
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${DNS_SERVERS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
PresharedKey = ${PRESHARED_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = ${ALLOWED_IPS}
PersistentKeepalive = 25
EOF
chmod 600 "${OUTPUT_DIR}/${PEER_NAME}.conf"

# ===== QRコード生成 =====
if command -v qrencode &> /dev/null; then
    qrencode -t png -o "${OUTPUT_DIR}/${PEER_NAME}.png" < "${OUTPUT_DIR}/${PEER_NAME}.conf"
    qrencode -t ansiutf8 < "${OUTPUT_DIR}/${PEER_NAME}.conf"
fi

# ===== リロード =====
wg syncconf wg0 <(wg-quick strip wg0)

echo ""
echo "===== Peer Added Successfully ====="
echo "Peer Name:    ${PEER_NAME}"
echo "Client IP:    ${CLIENT_ADDRESS}"
echo "Public Key:   ${CLIENT_PUBLIC_KEY}"
echo "Config File:  ${OUTPUT_DIR}/${PEER_NAME}.conf"
echo "===================================="
```

## セキュリティ注意事項

| 項目 | 対策 |
|------|------|
| 秘密鍵のパーミッション | `chmod 600`（所有者のみ読み取り） |
| 出力ディレクトリ | `chmod 700`（所有者のみアクセス） |
| 設定ファイルの転送 | SCP/USBメモリ等のセキュアな方法で転送。メール/チャット禁止 |
| バックアップの扱い | `.bak` ファイルにも秘密鍵が含まれる。不要になったら削除 |
| QRコードの扱い | 設定ファイル全文（秘密鍵含む）がエンコードされている。撮影後は画像を削除 |
| git管理 | `/etc/wireguard/` 配下は絶対にgit追跡しない |

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `wg syncconf` がエラー | 設定ファイルの構文エラー | `wg-quick strip wg0` で確認 |
| ピアが接続できない | AllowedIPsの重複 | 他ピアとのIP被りを確認 |
| ハンドシェイク失敗 | エンドポイント/ポートの問題 | `wg show wg0` でlatest handshakeを確認 |
| QRコードが読めない | ターミナル幅不足 | PNG版を使用するか、ターミナルを広げる |

## 関連スキル

- `wireguard-client-config-generator`: クライアント側設定ファイル生成（sudo不要）
- `iot-system-spec-generator`: IoTデバイスのVPN接続設計
