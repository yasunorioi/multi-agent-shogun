# uecs-llm 複数農家対応 設計書

> **Version**: 1.0 | **subtask_868 / cmd_392** | 2026-03-11
> **設計方針**: 壁打ち確定済み（/tmp/cmd_392.txt）を正確に反映

---

## §1 概要・目的

### 背景

uecs-llm（arsprout-llama）は現在、殿の単一ハウスを対象とした環境制御＋LLMチャットシステムとして稼働中。複数農家への展開にあたり、以下を実現する。

### 目的

1. **複数農家のRPiを1台のMBPで集約管理**する
2. **農家はLINE Botに話しかけるだけ**で自分のハウスを制御できる
3. **制御判断は全てエッジ（各農家のRPi）**で行い、MBPはルーターに徹する
4. **農家の導入操作は2ステップ**（QR追加 + Base64貼付）に抑える

### 設計哲学

- **マクガイバー精神**: シンプル・ローコスト。既存ツール（WireGuard, LINE Messaging API, Streamlit）を組み合わせる
- **月額忌避**: VPSは既存のWebhookリレーのみ。新規月額サービスなし
- **農家ファースト**: 技術知識不要。2ステップで運用開始

---

## §2 アーキテクチャ

### 全体構成図

```
                         ┌─────────────────────────────────────────┐
                         │              Internet                    │
                         └────────┬──────────────┬─────────────────┘
                                  │              │
                           ┌──────▼──────┐  ┌───▼───┐
                           │ LINE Platform│  │  VPS  │
                           │  (Webhook)   │  │(relay)│
                           └──────┬───────┘  └───┬───┘
                                  │              │
                                  └──────┬───────┘
                                         │ Webhook POST
                                         │ (HTTPS→殿用WG 10.10.0.x)
                                         ▼
                              ┌──────────────────────┐
                              │    MBP               │
                              │  ┌────────────────┐  │
                              │  │  LINE Bot本体   │  │
                              │  │ (ルーター機能)  │  │
                              │  │                 │  │
                              │  │ userID→農家特定 │  │
                              │  │ WG経由で転送    │  │
                              │  └────────────────┘  │
                              │  ┌────────────────┐  │
                              │  │ wg-farmers      │  │
                              │  │ WG Server       │  │
                              │  │ 10.20.0.1/24    │  │
                              │  └────────────────┘  │
                              └───┬──────┬──────┬────┘
                  農家用WG VPN    │      │      │
                 ┌────────────────┤      │      ├────────────────┐
                 ▼                ▼      │      ▼                ▼
    ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
    │ 農家A RPi      │  │ 農家B RPi      │  │ 農家C RPi      │
    │ 10.20.0.10     │  │ 10.20.0.20     │  │ 10.20.0.30     │
    │                │  │                │  │                │
    │ agriha_chat.py │  │ agriha_chat.py │  │ agriha_chat.py │
    │ nullclaw/Haiku │  │ nullclaw/Haiku │  │ nullclaw/Haiku │
    │ system_prompt   │  │ system_prompt   │  │ system_prompt   │
    │ UniPi API      │  │ UniPi API      │  │ UniPi API      │
    └────────────────┘  └────────────────┘  └────────────────┘
         ↕ 直結              ↕ 直結              ↕ 直結
    [UniPi Neuron]     [UniPi Neuron]     [UniPi Neuron]
    (ハウスA制御)       (ハウスB制御)       (ハウスC制御)
```

### 設計原則

| 原則 | 説明 |
|------|------|
| **エッジ分散** | 制御判断は各RPiのnullclaw/Haikuが行う。MBPは判断しない |
| **MBP中央** | LINE Bot + WGサーバ + メッセージルーティングのみ |
| **channel_map不要** | 各RPiのsystem_prompt.txtにリレーch情報が全て記載済み。農家が自分で編集。MBPは転送するだけなので同期不要 |

### 殿のアクセス経路

```
殿のMac → ローカルLAN → MBP → SSH経由 → 各農家RPi
（殿の既存WG 10.10.0.x は農家用WGとは完全分離）
```

---

## §3 ネットワーク設計

### IPアドレス体系

| ネットワーク | CIDR | 用途 | 備考 |
|------------|------|------|------|
| 殿の既存WG | 10.10.0.0/24 | 殿の開発・管理用 | **変更なし・触らない** |
| 農家用WG | 10.20.0.0/24 | 農家RPi ↔ MBP通信 | **新規作成** |

### 農家用WG アドレス割り当て

| ホスト | IPアドレス | 備考 |
|--------|-----------|------|
| MBP（WGサーバ） | 10.20.0.1 | 全農家RPiのピア |
| 農家A RPi | 10.20.0.10 | |
| 農家B RPi | 10.20.0.20 | |
| 農家C RPi | 10.20.0.30 | |
| ... | 10.20.0.N0 | N=農家番号 |

### WGサーバ設定（MBP側: /etc/wireguard/wg-farmers.conf）

```ini
[Interface]
Address = 10.20.0.1/24
ListenPort = 51821          # 既存WGの51820とは別ポート
PrivateKey = <MBP_PRIVATE_KEY>

# 農家ごとにPeerセクションを追加（farmers_secrets.yamlから自動生成）
[Peer]
# farmer_id: farmer_a
PublicKey = <FARMER_A_PUBLIC_KEY>
AllowedIPs = 10.20.0.10/32

[Peer]
# farmer_id: farmer_b
PublicKey = <FARMER_B_PUBLIC_KEY>
AllowedIPs = 10.20.0.20/32
```

### VPS → MBP の経路

```
LINE Platform → Webhook → VPS (HTTPS受信)
  → VPS nginx → MBP の殿用WG IP (10.10.0.x):5000 に転送
  → MBP LINE Bot がメッセージ処理
```

VPSと MBPはすでに殿の管理用WG (10.10.0.0/24) で接続済み。VPS nginx の `proxy_pass` はこの既存トンネルを利用する。**farmers WG (10.20.0.x) に VPS を混ぜる必要はない**（農家→VPS経路が開いて分離が崩れるため）。新規月額コストなし。

### MBP の WGインターフェース構成

MBP は2つの WGインターフェースを持つ:

| インターフェース | 役割 | IPアドレス体系 |
|---------------|------|-------------|
| 殿の既存WG（wg0等） | 殿の管理用・VPS←→MBP通信経路 | 10.10.0.0/24（既存） |
| wg-farmers（新規） | 農家用WGサーバ | 10.20.0.0/24（新規） |

> ⚠️ VPSの nginx `proxy_pass` は `http://10.10.0.{MBP_WG_IP}:5000/webhook` とする。`10.20.0.1` を指定してはいけない（VPSはfarmers WGに参加しないため到達不能）。

### 分離の理由

- 殿の管理用WG（10.10.0.x）と農家用WG（10.20.0.x）を同一ネットワークにすると、農家RPiから殿のネットワークにアクセス可能になる
- CIDRが異なるため**ルーティングレベルで完全分離**
- MBPは両方のWGインターフェースを持つが、農家→MBP間の通信制御は **AllowedIPs** で行う（`AllowedIPs = 10.20.0.1/32` により農家RPi同士の直接通信は不可）

---

## §4 LINE Bot設計

### 役割: ルーターに徹する

MBPのLINE Botは**メッセージルーター**であり、制御判断は一切行わない。

```
LINE Bot の処理フロー:

1. Webhook受信（LINE Platform → VPS → MBP）
2. event.source.userId を取得
3. farmers_secrets.yaml を参照し userId → farmer_id を特定
4. farmer_id → rpi_host（WG IP）を farmers.yaml から取得
5. HTTP POST で RPi の agriha_chat.py に転送
   POST http://10.20.0.{N}:8501/api/chat
   Body: {"message": "側窓開けて", "user_id": "..."}
6. RPi からの応答を受信
7. LINE reply API で農家に返信
```

### メッセージルーター（MBP側: linebot/router.py 新規作成）

```python
# linebot/router.py（概要）

import yaml
from flask import Flask, request

app = Flask(__name__)

def load_farmers():
    """farmers.yaml + farmers_secrets.yaml を読み込み"""
    with open("config/farmers.yaml") as f:
        farmers = yaml.safe_load(f)
    with open("config/farmers_secrets.yaml") as f:
        secrets = yaml.safe_load(f)
    return farmers, secrets

def resolve_farmer(user_id, secrets):
    """LINE userID → farmer_id を特定"""
    for fid, sec in secrets["farmers"].items():
        if sec["line_user_id"] == user_id:
            return fid
    return None

@app.route("/webhook", methods=["POST"])
def webhook():
    # 1. LINE eventからuserIdを取得
    # 2. resolve_farmer() で農家特定
    # 3. farmers.yaml から rpi_host を取得
    # 4. HTTP POST → RPi agriha_chat.py
    # 5. 応答をLINE reply APIで返信
    ...
```

### 未登録ユーザーの処理

```
userId が farmers_secrets.yaml に存在しない場合:
  → LINE返信: 「登録されていないユーザーです。管理者にお問い合わせください。」
  → ログに記録（不正アクセス検知用）
```

### follow event（友達追加時）の処理

```
1. follow event 受信
2. userId を自動取得
3. 仮登録として farmers_secrets.yaml に追記（pending状態）
4. MBP側でWGキーペア自動生成
5. 設定情報をBase64エンコード
6. LINE返信:
   「登録ありがとうございます！以下の設定コードをRPiのWeb画面に貼り付けてください。」
   + Base64ブロック
```

---

## §5 農家オンボーディングフロー

### 農家がやること（2ステップだけ）

```
Step 1: スマホでQRコードを読み、LINE Botを友達追加
Step 2: Botから届いたBase64設定コードをRPi Web UIに貼り付け
```

### 全体フロー（詳細）

```
┌─────────────────────────────────────────────────────────────────┐
│ 前提: RPiは setup.sh 済み。Web UI (agriha_chat.py :8501) 稼働中 │
└─────────────────────────────────────────────────────────────────┘

[農家]                    [LINE Bot / MBP]              [RPi]
  │                            │                          │
  │  1. QRスキャン              │                          │
  │  ──(友達追加)──────────────>│                          │
  │                            │                          │
  │                            │ 2. follow event受信       │
  │                            │    userId取得             │
  │                            │    ※キーペア生成はしない  │
  │                            │    farmers_secrets.yaml   │
  │                            │    にpending追記          │
  │                            │    (公開鍵は後で受け取る)  │
  │                            │                          │
  │  3. LINE返信受信            │                          │
  │  「設定コードをRPiに貼ってね」│                          │
  │  + Base64ブロック           │                          │
  │  (サーバ公開鍵+EP+割当IPのみ│                          │
  │   秘密鍵は含めない)         │                          │
  │                            │                          │
  │  4. RPi Web UIにアクセス    │                          │
  │  ──(ブラウザ)────────────────────────────────────────>│
  │                            │                          │
  │  5. Base64を貼り付け        │                          │
  │  ──(フォーム送信)──────────────────────────────────>│
  │                            │                   6. デコード
  │                            │                   RPiがローカルで
  │                            │                   WGキーペア生成
  │                            │                   wg-farmers-client.conf
  │                            │                   生成+wg-quick up
  │                            │                   公開鍵をMBPにPOST通知
  │                            │                          │
  │                            │<── 7. RPi公開鍵受信 ─────│
  │                            │    wg-farmers.conf更新    │
  │                            │<──── 8. WG疎通確認 ──────│
  │                            │                          │
  │  9. LINE通知                │                          │
  │  「接続完了！使えます」     │                          │
  │                            │    pendingをactiveに更新  │
  │                            │                          │
  └────────────────────────────┴──────────────────────────┘
```

### Base64ブロックの中身

```yaml
# MBPが生成するBase64の中身（デコード後）
# ⚠️ wg_client_private_key は含めない — RPiがローカル生成
---
farmer_id: farmer_a
wg_server_public_key: <MBP_PUBLIC_KEY>
wg_server_endpoint: <VPS_IP>:51821    # VPSのUDP 51821はMBPのwg-farmersにルーティング済み
wg_client_ip: 10.20.0.10/32
api_endpoint: http://10.20.0.1:5000
```

RPi側はこれをデコードし、**自身で `wg genkey` を実行**してローカルにキーペアを生成。
取得したサーバ公開鍵・エンドポイント・割当IPと組み合わせて `wg-farmers-client.conf` を生成し、WGを起動する。
起動後、RPiの公開鍵を `POST /api/register_pubkey` でMBPに送信してPeer登録を完了させる。

---

## §6 RPi側変更

### 変更対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/setup.sh` | WGクライアント設定の自動適用を追加 |
| `services/agriha-chat/agriha_chat.py` | Web UI設定画面追加 + チャットAPI追加 |
| `config/system_prompt.txt` | 変更なし（農家が自分で編集） |

### setup.sh 拡張

```bash
#!/bin/bash
# 既存のsetup処理（apt install, pip install等）
# ...

# --- 複数農家対応 追加分 ---
# WireGuard インストール（未導入の場合）
if ! command -v wg &>/dev/null; then
    sudo apt install -y wireguard
fi

# WGクライアント用ディレクトリ準備
sudo mkdir -p /etc/wireguard

echo "=== setup完了 ==="
echo "Web UI: http://$(hostname -I | awk '{print $1}'):8501"
echo "→ 設定画面でBase64コードを貼り付けてください"
```

### agriha_chat.py Web UI設定画面

既存のStreamlit UIに設定タブを追加。

```python
# services/agriha-chat/agriha_chat.py（設定画面追加部分）

import streamlit as st
import base64, yaml, subprocess

# タブ構成
tab_chat, tab_settings = st.tabs(["💬 チャット", "⚙️ 設定"])

with tab_settings:
    st.header("農家登録設定")

    # LINE Bot QRコード表示
    st.image("static/line_bot_qr.png", caption="Step 1: このQRでBot友達追加")

    # Base64貼り付けフォーム
    b64_input = st.text_area("Step 2: Botから届いた設定コードを貼り付け")

    if st.button("登録"):
        try:
            decoded = base64.b64decode(b64_input)
            config = yaml.safe_load(decoded)
            # RPiローカルでWGキーペア生成（秘密鍵はLINE経由で受け取らない）
            private_key = subprocess.check_output(["wg", "genkey"]).decode().strip()
            public_key = subprocess.check_output(
                ["wg", "pubkey"], input=private_key.encode()
            ).decode().strip()
            # WG設定ファイル生成
            wg_conf = f"""[Interface]
PrivateKey = {private_key}
Address = {config['wg_client_ip']}

[Peer]
PublicKey = {config['wg_server_public_key']}
Endpoint = {config['wg_server_endpoint']}
AllowedIPs = 10.20.0.1/32
PersistentKeepalive = 25
"""
            with open("/etc/wireguard/wg-farmers-client.conf", "w") as f:
                f.write(wg_conf)
            subprocess.run(["sudo", "wg-quick", "up", "wg-farmers-client"], check=True)
            # WG永続化: リブート後も自動起動
            subprocess.run(
                ["sudo", "systemctl", "enable", "wg-quick@wg-farmers-client"], check=True
            )
            # MBPに公開鍵を送信してPeer登録
            import requests
            requests.post(
                f"{config['api_endpoint']}/api/register_pubkey",
                json={"farmer_id": config["farmer_id"], "public_key": public_key},
                timeout=10,
            )
            st.success("✅ 接続完了！チャットタブから使えます")
        except Exception as e:
            st.error(f"❌ 設定エラー: {e}")
```

### チャットAPI（RPi側）

MBPのルーターから直接呼ばれるAPIエンドポイント。

```python
# services/agriha-chat/agriha_chat.py（API追加部分）

from flask import Flask, request, jsonify
import threading

# Streamlitとは別スレッドでFlask APIを起動
api = Flask(__name__)

@api.route("/api/chat", methods=["POST"])
def chat_api():
    """MBPルーターからのメッセージを受け取り、nullclaw/Haikuで処理して返す"""
    data = request.json
    message = data.get("message", "")
    # 既存のagriha_chat処理を呼び出し
    response = process_chat(message)  # nullclaw/Haiku経由
    return jsonify({"response": response})

def start_api():
    api.run(host="0.0.0.0", port=8502)  # Streamlitの8501とは別ポート

# メインで別スレッド起動
threading.Thread(target=start_api, daemon=True).start()
```

> ⚠️ **注意**: StreamlitとFlaskを同一プロセス内で `threading.Thread` により同居させる構成は簡便だが不安定になる場合がある。将来的には Flask APIを別 systemd ユニット（`agriha-api.service`）に分離することを推奨。

---

## §7 MBP側構成

### 移設対象

現在VPSで動作しているLINE Bot本体をMBPに移設する。

| コンポーネント | 移設元 | 移設先 |
|-------------|--------|--------|
| LINE Bot (linebot/app.py) | VPS | MBP |
| メッセージルーター (linebot/router.py) | 新規 | MBP |
| WGサーバ (wg-farmers) | 新規 | MBP |
| farmers.yaml | 新規 | MBP |
| farmers_secrets.yaml | 新規 | MBP |

### MBP の WGインターフェース（再掲）

MBPは2つのWGインターフェースを持つ（§3参照）:

| インターフェース | 役割 |
|---------------|------|
| 殿の既存WG（wg0等・10.10.0.x） | VPS←→MBP の Webhook転送経路 |
| wg-farmers（新規・10.20.0.1） | 農家RPi ←→ MBP の通信用WGサーバ |

### VPSに残るもの

- Webhook受信 → **殿の既存WG (10.10.0.x) 経由** でMBP:5000に転送（nginx reverse proxy）
- VPSのnginx設定例:

```nginx
# /etc/nginx/sites-available/linebot-relay
server {
    listen 443 ssl;
    server_name <VPS_DOMAIN>;

    location /webhook {
        # proxy_pass先はMBPの殿用WG IP（10.10.0.x）を使用
        # ⚠️ 10.20.0.1（farmers WG）は指定しない — VPSはfarmers WGに参加しないため到達不能
        proxy_pass http://10.10.0.{MBP_IP}:5000/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### MBP ディレクトリ構成

```
arsprout-llama/          # リポジトリルート（MBP上）
├── linebot/
│   ├── app.py           # LINE Bot本体（VPSから移設）
│   ├── router.py        # メッセージルーター（新規）
│   ├── onboarding.py    # follow event処理・Base64生成（新規）
│   └── requirements.txt
├── config/
│   ├── farmers.yaml             # 農家マスタ（git管理）
│   └── farmers_secrets.yaml     # 秘密情報（.gitignore）
└── scripts/
    ├── wg_farmer_setup.sh       # 農家用WGサーバ初期設定
    └── gen_farmer_config.sh     # 農家追加時のWG設定生成
```

### WGサーバ起動

```bash
# MBPでの初期設定
sudo wg-quick up wg-farmers

# 起動確認
sudo wg show wg-farmers
```

---

## §8 秘密情報管理

### 二層分離方式

| ファイル | 内容 | Git管理 | 機密レベル |
|---------|------|---------|----------|
| `config/farmers.yaml` | 農家マスタ（id, name, rpi_host, 設定パス） | ✅ git管理 | 低 |
| `config/farmers_secrets.yaml` | 秘密情報（line_user_id, wg_public_key, wg_ip） | ❌ .gitignore | **高** |

### farmers.yaml（git管理）

```yaml
# config/farmers.yaml
farmers:
  farmer_a:
    name: "田中農園"
    rpi_host: "10.20.0.10"
    rpi_chat_port: 8502
    system_prompt_path: "/home/pi/arsprout-llama/config/system_prompt.txt"
    status: active        # active / pending / disabled
    registered_at: "2026-04-01"

  farmer_b:
    name: "鈴木ファーム"
    rpi_host: "10.20.0.20"
    rpi_chat_port: 8502
    system_prompt_path: "/home/pi/arsprout-llama/config/system_prompt.txt"
    status: pending
    registered_at: "2026-04-15"
```

### farmers_secrets.yaml（.gitignore、Base64エンコード）

```yaml
# config/farmers_secrets.yaml
# ⚠️ このファイルはgit管理しない。.gitignoreに登録済み
# ⚠️ wg_client_private_key は保持しない — 秘密鍵はRPiローカルのみ。再セットアップ時は再生成。
farmers:
  farmer_a:
    line_user_id: "U1234567890abcdef"
    wg_public_key: "aBcDeFgHiJkLmNoPqRsTuVwXyZ="  # RPiから受け取った公開鍵
    wg_ip: "10.20.0.10"

  farmer_b:
    line_user_id: "Uabcdef1234567890"
    wg_public_key: "zYxWvUtSrQpOnMlKjIhGfEdCbA="
    wg_ip: "10.20.0.20"
```

### 秘密鍵の保持ルール

| 鍵の種類 | 保持場所 | 備考 |
|---------|---------|------|
| MBP WGサーバ秘密鍵 | MBP `/etc/wireguard/wg-farmers.conf` | MBPローカルのみ |
| 農家RPi WGクライアント秘密鍵 | RPi `/etc/wireguard/wg-farmers-client.conf` | **RPiローカルのみ**。バックアップ不要。再セットアップ時は `wg genkey` で再生成し、MBPのPeer公開鍵を更新する。 |
| LINE Channel Secret / Token | MBP 環境変数 or `.env` | git管理しない |

> ⚠️ 農家RPiのWGクライアント秘密鍵をMBP側に保存しない。LINE経由で秘密鍵を送付することも禁止（LINEはE2E暗号化なし。秘密鍵が平文でLINE Platformサーバを通過する）。

---

## §9 既存機能との互換性

### 現行v4 単一農家モード

現在の構成:
```
殿のスマホ → LINE → VPS LINE Bot → RPi agriha_chat.py → UniPi制御
```

### 互換性方針

| 項目 | 現行v4 | 複数農家対応後 | 互換性 |
|------|--------|-------------|--------|
| RPi agriha_chat.py | チャットUI | チャットUI + 設定画面 + API | ✅ 上位互換 |
| system_prompt.txt | 農家が編集 | 農家が編集（変更なし） | ✅ 完全互換 |
| UniPi制御 | RPiローカル | RPiローカル（変更なし） | ✅ 完全互換 |
| LINE Bot | VPSで動作 | MBPに移設 | ⚠️ 移設作業必要 |
| WireGuard | 殿の管理用のみ | 殿の管理用 + 農家用 | ✅ 別インターフェース |

### MBP 可用性リスク

LINE BotをMBPに移設することで、**MBPのスリープ・再起動時に全農家のLINE Botが停止する**リスクがある（VPS運用時にはなかった問題）。

対策:

```bash
# macOS スリープ抑止（常時稼働）
sudo pmset -a sleep 0 disksleep 0

# または caffeinate をバックグラウンド常駐
caffeinate -dimsu &
```

Phase 0移行時のダウンタイム手順（Webhook URL切替・LINE Messaging API設定変更等）を事前に計画すること。

### Phase 0（殿のみ）での互換性

Phase 0では殿が唯一の農家として登録される。

```yaml
# config/farmers.yaml（Phase 0）
farmers:
  tono:
    name: "殿"
    rpi_host: "10.20.0.10"    # 殿のRPi
    rpi_chat_port: 8502
    status: active
```

殿の既存WG（10.10.0.x）はそのまま。農家用WG（10.20.0.x）に殿のRPiも追加登録。二重接続だが問題なし（経路が異なるだけ）。

---

## §10 段階的導入計画

### Phase 0: 殿のみ（現行環境を新構成に移行）

**目標**: 既存機能を壊さず新アーキテクチャに移行

| # | タスク | 成果物 |
|---|--------|--------|
| 0-1 | MBPに農家用WGサーバ構築 | `/etc/wireguard/wg-farmers.conf` |
| 0-2 | LINE BotをVPS→MBPに移設 | `linebot/app.py` + `linebot/router.py` |
| 0-3 | VPS nginx設定変更（MBPへの転送） | nginx設定 |
| 0-4 | farmers.yaml / farmers_secrets.yaml 作成（殿のみ） | `config/farmers*.yaml` |
| 0-5 | 殿のRPiにWGクライアント追加 | `wg-farmers-client.conf` |
| 0-6 | RPi agriha_chat.py にチャットAPI追加 | `/api/chat` エンドポイント |
| 0-7 | E2Eテスト: LINE → MBP → RPi → UniPi → LINE返信 | 動作確認 |

**完了基準**: 殿がLINEで「側窓開けて」→ 応答が返る

### Phase 1: テスト農家1名

**目標**: オンボーディングフローの検証

| # | タスク | 成果物 |
|---|--------|--------|
| 1-1 | RPi setup.sh にWG自動設定を追加 | `scripts/setup.sh` 更新 |
| 1-2 | agriha_chat.py に設定画面（Web UI）追加 | Streamlit設定タブ |
| 1-3 | follow event処理 + Base64生成 | `linebot/onboarding.py` |
| 1-4 | テスト農家のRPiをセットアップ | 実機テスト |
| 1-5 | テスト農家にQR+Base64の2ステップを実施 | オンボーディング検証 |
| 1-6 | テスト農家がLINEで制御できることを確認 | E2Eテスト |

**完了基準**: テスト農家がQR+Base64の2ステップだけで運用開始

### Phase 2: 本格展開

**目標**: 複数農家の同時運用

| # | タスク | 成果物 |
|---|--------|--------|
| 2-1 | 農家追加スクリプトの整備 | `scripts/gen_farmer_config.sh` |
| 2-2 | 農家管理画面（MBP側、オプション） | 管理Webページ |
| 2-3 | 監視・アラート（農家RPiのWG疎通チェック） | cron + LINE通知 |
| 2-4 | 本番農家のオンボーディング | 実運用 |

**完了基準**: 3名以上の農家が同時にLINEから制御可能

---

## 付録A: 制御の流れ（シーケンス詳細）

```
農家「側窓開けて」
  │
  ▼ LINE Platform
  │
  ▼ Webhook POST → VPS (HTTPS)
  │
  ▼ VPS nginx → WG経由 → MBP:5000
  │
  ▼ MBP linebot/router.py
  │   1. event.source.userId 取得
  │   2. farmers_secrets.yaml 参照 → farmer_id 特定
  │   3. farmers.yaml 参照 → rpi_host = 10.20.0.10
  │
  ▼ HTTP POST → http://10.20.0.10:8502/api/chat
  │   Body: {"message": "側窓開けて"}
  │
  ▼ RPi agriha_chat.py
  │   1. system_prompt.txt 読み込み済み（ch情報含む）
  │   2. nullclaw/Haiku に問い合わせ
  │   3. 「ch5をONにします」→ UniPi API実行
  │   4. 結果を返す
  │
  ▼ MBP router.py が応答受信
  │
  ▼ LINE reply API → 農家のスマホ
  │   「側窓を開けました（ch5 ON）」
```

---

## 付録B: ファイル変更一覧

| ファイル | 操作 | 説明 |
|---------|------|------|
| `linebot/router.py` | 新規 | メッセージルーター |
| `linebot/onboarding.py` | 新規 | follow event + Base64生成 |
| `linebot/app.py` | 移設+改修 | VPS→MBP移設、router統合 |
| `config/farmers.yaml` | 新規 | 農家マスタ |
| `config/farmers_secrets.yaml` | 新規 | 秘密情報（.gitignore） |
| `scripts/wg_farmer_setup.sh` | 新規 | MBP WGサーバ初期設定 |
| `scripts/gen_farmer_config.sh` | 新規 | 農家追加スクリプト |
| `scripts/setup.sh` | 改修 | WGクライアント自動設定追加 |
| `services/agriha-chat/agriha_chat.py` | 改修 | 設定画面 + チャットAPI追加 |
| `.gitignore` | 改修 | `config/farmers_secrets.yaml` 追加 |
