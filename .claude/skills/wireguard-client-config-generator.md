# wireguard-client-config-generator

WireGuardクライアント設定ファイル（.conf）をsudo不要で生成するスキル。サーバー情報とクライアントパラメータを入力し、即座に使える設定ファイルを出力する。

## メタデータ

| 項目 | 値 |
|------|-----|
| Skill ID | wireguard-client-config-generator |
| Category | Network / VPN |
| Version | 1.0.0 |
| Created | 2026-02-07 |
| Platform | Linux / macOS / Windows |

## Overview

WireGuardクライアント設定ファイルの生成に特化したスキル。サーバー側への追記は行わず、クライアント側の `.conf` ファイル生成のみを担当する。sudo権限不要で実行可能。

主な機能：
- Interface セクション（秘密鍵、アドレス、DNS）の生成
- Peer セクション（サーバー公開鍵、エンドポイント、AllowedIPs）の生成
- Split Tunnel / Full Tunnel の切り替え
- 複数プロファイル（自宅/オフィス/モバイル）の一括生成

## Use Cases

### 1. リモートワーカーの初期設定

新しい従業員にVPN設定ファイルを配布する際、個別のパラメータを入力して生成。

### 2. Split Tunnel構成

VPN経由で社内ネットワークのみアクセスし、一般インターネットは直接接続するSplit Tunnel設定。

### 3. 複数環境のプロファイル管理

自宅VPN・オフィスVPN・クラウドVPNなど複数の接続先プロファイルを一括生成。

### 4. IoTデバイスのVPN設定

Raspberry PiやPicoなどのIoTデバイス用の軽量VPN設定を生成。

## Skill Input

| パラメータ | 必須 | 説明 | デフォルト |
|-----------|------|------|-----------|
| `PROFILE_NAME` | Yes | プロファイル名（例: `home-vpn`, `office-vpn`） | - |
| `CLIENT_PRIVATE_KEY` | Yes* | クライアント秘密鍵（未指定時は自動生成） | 自動生成 |
| `CLIENT_ADDRESS` | Yes | クライアントのVPN内IPアドレス（例: `10.0.0.10/32`） | - |
| `SERVER_PUBLIC_KEY` | Yes | サーバーの公開鍵 | - |
| `SERVER_ENDPOINT` | Yes | サーバーのエンドポイント（例: `vpn.example.com:51820`） | - |
| `DNS_SERVERS` | No | DNS サーバー | `1.1.1.1, 8.8.8.8` |
| `ALLOWED_IPS` | No | ルーティング対象IP範囲 | `0.0.0.0/0, ::/0`（Full Tunnel） |
| `TUNNEL_MODE` | No | `full` or `split` | `full` |
| `SPLIT_NETWORKS` | No | Split Tunnel時のネットワーク | `10.0.0.0/24, 192.168.0.0/16` |
| `MTU` | No | MTU値 | 未指定（WireGuardデフォルト） |
| `PERSISTENT_KEEPALIVE` | No | キープアライブ間隔（秒） | `25` |
| `OUTPUT_DIR` | No | 出力先ディレクトリ | `./wireguard-configs/` |

## Generated Output

### 設定ファイル構造

```
./wireguard-configs/
├── home-vpn.conf           # Full Tunnel設定
├── office-vpn.conf         # Split Tunnel設定
└── keys/
    ├── home-vpn.key        # 秘密鍵（自動生成時）
    └── office-vpn.key      # 秘密鍵（自動生成時）
```

### Full Tunnel設定ファイル（生成例）

```ini
[Interface]
# Profile: home-vpn
# Generated: 2026-02-07
PrivateKey = <client_private_key>
Address = 10.0.0.10/32
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = <server_public_key>
Endpoint = vpn.example.com:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

### Split Tunnel設定ファイル（生成例）

```ini
[Interface]
# Profile: office-vpn (Split Tunnel)
# Generated: 2026-02-07
PrivateKey = <client_private_key>
Address = 10.0.0.10/32
# DNS is not set for split tunnel (use system DNS)

[Peer]
PublicKey = <server_public_key>
Endpoint = office-vpn.example.com:51820
AllowedIPs = 10.0.0.0/24, 192.168.1.0/24
PersistentKeepalive = 25
```

## Implementation

### 鍵の生成（sudo不要）

```bash
PROFILE_NAME="home-vpn"
OUTPUT_DIR="./wireguard-configs"
KEYS_DIR="${OUTPUT_DIR}/keys"

mkdir -p "${KEYS_DIR}"
chmod 700 "${KEYS_DIR}"

# wg コマンドによる鍵生成（sudo不要）
CLIENT_PRIVATE_KEY=$(wg genkey)
CLIENT_PUBLIC_KEY=$(echo "${CLIENT_PRIVATE_KEY}" | wg pubkey)

# 秘密鍵をファイルに保存
echo "${CLIENT_PRIVATE_KEY}" > "${KEYS_DIR}/${PROFILE_NAME}.key"
chmod 600 "${KEYS_DIR}/${PROFILE_NAME}.key"

echo "Client Public Key: ${CLIENT_PUBLIC_KEY}"
echo "(この公開鍵をサーバー管理者に渡してください)"
```

### Full Tunnel設定の生成

```bash
SERVER_PUBLIC_KEY="<server_public_key>"
SERVER_ENDPOINT="vpn.example.com:51820"
CLIENT_ADDRESS="10.0.0.10/32"
DNS_SERVERS="1.1.1.1, 8.8.8.8"

cat > "${OUTPUT_DIR}/${PROFILE_NAME}.conf" << EOF
[Interface]
# Profile: ${PROFILE_NAME}
# Generated: $(date +%Y-%m-%d)
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${DNS_SERVERS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF

chmod 600 "${OUTPUT_DIR}/${PROFILE_NAME}.conf"
echo "Config created: ${OUTPUT_DIR}/${PROFILE_NAME}.conf"
```

### Split Tunnel設定の生成

```bash
SPLIT_NETWORKS="10.0.0.0/24, 192.168.1.0/24"

cat > "${OUTPUT_DIR}/${PROFILE_NAME}-split.conf" << EOF
[Interface]
# Profile: ${PROFILE_NAME} (Split Tunnel)
# Generated: $(date +%Y-%m-%d)
# Note: DNS is not set (split tunnel uses system DNS)
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = ${SPLIT_NETWORKS}
PersistentKeepalive = 25
EOF

chmod 600 "${OUTPUT_DIR}/${PROFILE_NAME}-split.conf"
echo "Split tunnel config created: ${OUTPUT_DIR}/${PROFILE_NAME}-split.conf"
```

### MTU指定時の設定

```bash
# MTUを指定する場合（VPN over VPN、モバイル回線等で必要）
MTU=1380

cat > "${OUTPUT_DIR}/${PROFILE_NAME}.conf" << EOF
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${DNS_SERVERS}
MTU = ${MTU}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
```

### PresharedKey付き設定（より高いセキュリティ）

```bash
# 事前共有鍵の生成（sudo不要）
PRESHARED_KEY=$(wg genpsk)

cat > "${OUTPUT_DIR}/${PROFILE_NAME}.conf" << EOF
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${DNS_SERVERS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
PresharedKey = ${PRESHARED_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
EOF
```

### 一括生成スクリプト（複数プロファイル）

```bash
#!/bin/bash
set -euo pipefail

# ===== 設定 =====
OUTPUT_DIR="./wireguard-configs"
KEYS_DIR="${OUTPUT_DIR}/keys"
mkdir -p "${KEYS_DIR}" && chmod 700 "${KEYS_DIR}"

# ===== プロファイル定義 =====
# 形式: "PROFILE_NAME|CLIENT_ADDRESS|SERVER_ENDPOINT|SERVER_PUBKEY|MODE|ALLOWED_IPS"
PROFILES=(
    "home-vpn|10.0.0.10/32|home.example.com:51820|<home_server_pubkey>|full|"
    "office-vpn|10.1.0.10/32|office.example.com:51820|<office_server_pubkey>|split|10.1.0.0/24,172.16.0.0/12"
    "cloud-vpn|10.2.0.10/32|cloud.example.com:51820|<cloud_server_pubkey>|full|"
)

for profile_def in "${PROFILES[@]}"; do
    IFS='|' read -r NAME ADDR ENDPOINT PUBKEY MODE NETWORKS <<< "${profile_def}"

    # 鍵生成
    PRIVKEY=$(wg genkey)
    PUBKEY_CLIENT=$(echo "${PRIVKEY}" | wg pubkey)
    echo "${PRIVKEY}" > "${KEYS_DIR}/${NAME}.key"
    chmod 600 "${KEYS_DIR}/${NAME}.key"

    # AllowedIPs決定
    if [ "${MODE}" = "split" ] && [ -n "${NETWORKS}" ]; then
        ALLOWED="${NETWORKS// /}"
        DNS_LINE=""
    else
        ALLOWED="0.0.0.0/0, ::/0"
        DNS_LINE="DNS = 1.1.1.1, 8.8.8.8"
    fi

    # 設定ファイル生成
    {
        echo "[Interface]"
        echo "# Profile: ${NAME} (${MODE} tunnel)"
        echo "# Generated: $(date +%Y-%m-%d)"
        echo "PrivateKey = ${PRIVKEY}"
        echo "Address = ${ADDR}"
        [ -n "${DNS_LINE}" ] && echo "${DNS_LINE}"
        echo ""
        echo "[Peer]"
        echo "PublicKey = ${PUBKEY}"
        echo "Endpoint = ${ENDPOINT}"
        echo "AllowedIPs = ${ALLOWED}"
        echo "PersistentKeepalive = 25"
    } > "${OUTPUT_DIR}/${NAME}.conf"
    chmod 600 "${OUTPUT_DIR}/${NAME}.conf"

    echo "[OK] ${NAME}: ${ADDR} (${MODE}) -> Public Key: ${PUBKEY_CLIENT}"
done

echo ""
echo "All configs generated in: ${OUTPUT_DIR}/"
echo "Share the public keys above with each server administrator."
```

## 各プラットフォームでの設定ファイル適用方法

### Linux

```bash
# 設定ファイルをコピー
sudo cp home-vpn.conf /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf

# 接続
sudo wg-quick up wg0

# 自動起動
sudo systemctl enable wg-quick@wg0
```

### macOS（WireGuard.app）

1. App Storeから WireGuard をインストール
2. アプリを起動 → 「Import tunnel(s) from file」
3. 生成した `.conf` ファイルを選択
4. 「Activate」で接続

### Windows（WireGuard.app）

1. wireguard.com から WireGuard をダウンロード・インストール
2. アプリを起動 → 「Import tunnel(s) from file」
3. 生成した `.conf` ファイルを選択
4. 「Activate」で接続

### iOS / Android（WireGuard App）

1. WireGuard アプリをインストール
2. `qrencode -t ansiutf8 < home-vpn.conf` でQRコードを表示
3. アプリの「+」→「Create from QR code」でスキャン

## セキュリティ注意事項

| 項目 | 対策 |
|------|------|
| 秘密鍵の保護 | `chmod 600` で所有者のみ読み取り可。パスワードマネージャーでの管理を推奨 |
| 設定ファイルの転送 | SCP、暗号化USBメモリ、パスワード付きZIPで転送。メール/Slack禁止 |
| git追跡の防止 | `.gitignore` に `*.conf`, `*.key`, `wireguard-configs/` を追加 |
| 不要ファイルの削除 | 転送完了後、生成元マシンの設定ファイルを `shred -u` で安全削除 |
| PresharedKey | 量子コンピュータ耐性のため追加を推奨 |

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `wg genkey` が見つからない | wireguard-tools 未インストール | `sudo apt install wireguard-tools` |
| 接続後インターネットに出られない | サーバー側でIP転送/NAT未設定 | サーバーの `PostUp`/`PostDown` iptables確認 |
| DNS解決できない | DNS設定の問題 | `resolvectl status` で確認。DNS行を修正 |
| Split Tunnel で社内のみ繋がらない | AllowedIPs が不足 | 社内ネットワークの全セグメントを追加 |
| MTU関連のタイムアウト | MTU値が大きすぎる | `MTU = 1280` から試す |

## 関連スキル

- `wireguard-peer-adder`: サーバー側ピア追加自動化（sudo必要）
- `iot-system-spec-generator`: IoTデバイスのネットワーク設計
