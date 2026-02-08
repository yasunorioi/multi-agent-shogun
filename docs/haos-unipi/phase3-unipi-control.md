# Phase 3: UniPi 1.1 統合・制御手順

**作成日**: 2026-02-06
**対象**: Raspberry Pi 4 + UniPi 1.1
**Home Assistant OS バージョン**: 2026.2.0

## 概要

本ドキュメントは、Phase 2で構築したHome Assistant環境に、UniPi 1.1拡張基板を統合し、リレー・センサーを制御できるようにする手順を記載する。

殿ご自身で実施いただく作業は **★殿の操作★** で明示する。

## 前提条件

以下が完了していることを確認してください：

- [ ] Phase 1（Home Assistant OS インストール）完了
- [ ] Phase 2（Mosquitto, Node-RED, File Editor導入）完了
- [ ] UniPi 1.1 基板が Raspberry Pi 4 に物理接続済み
- [ ] Raspberry Pi 4 に電源供給されている

### UniPi 1.1 とは

**UniPi 1.1** は、Raspberry Pi用の産業用I/O拡張基板です。

| 機能 | 仕様 |
|------|------|
| リレー出力 | 8ch（電磁弁、ファン等の制御） |
| デジタル入力 | 14ch（スイッチ、センサー入力） |
| アナログ入力 | 2ch（0-10V電圧入力） |
| 1-Wireバス | 1ch（温度センサー DS18B20等） |
| 温度センサー | MCP9808（I2C接続、基板上） |
| GPIO拡張 | MCP23008（I2C接続、リレー制御用） |

### Arsproutでの使用実績

UniPi 1.1は、農業IoTシステム「Arsprout」で採用されており、農業現場での稼働実績があります。

## UniPi 1.1 ハードウェア概要

### I2Cデバイス構成

UniPi 1.1には、以下のI2Cデバイスが搭載されています：

| I2Cアドレス | デバイス | 用途 |
|------------|---------|------|
| **0x20** | MCP23008 | GPIO拡張（リレー制御） |
| **0x18** | MCP9808 | 温度センサー（基板上） |

### リレー配置

**重要**: リレー番号とGPIOピンは**逆順**です。

| リレー番号 | MCP23008 GPIO | ビット値 | 用途例 |
|-----------|---------------|---------|--------|
| Relay 1 | GP7 | 0x80 | 灌水バルブ1 |
| Relay 2 | GP6 | 0x40 | 灌水バルブ2 |
| Relay 3 | GP5 | 0x20 | 灌水バルブ3 |
| Relay 4 | GP4 | 0x10 | 灌水バルブ4 |
| Relay 5 | GP3 | 0x08 | 換気扇 |
| Relay 6 | GP2 | 0x04 | サーキュレータ |
| Relay 7 | GP1 | 0x02 | 暖房機 |
| Relay 8 | GP0 | 0x01 | 予備 |

### 物理接続確認

#### ★殿の物理作業★ UniPi 1.1 接続確認

1. **Raspberry Pi 4の電源をオフにする**

2. **UniPi 1.1基板をRaspberry Pi 4のGPIOヘッダーに接続**

   - 40ピンGPIOヘッダーに、UniPi 1.1をしっかりと差し込む
   - 基板がズレていないか確認

3. **電源を投入**

   - Raspberry Pi 4の電源を入れる
   - Home Assistantが起動するまで待機（2〜3分）

## 制御方法の選択

UniPi 1.1を制御する方法は2つあります：

| 方法 | 難易度 | 推奨度 | 説明 |
|------|--------|--------|------|
| **a) EVOK API経由** | 低 | **◎ 推奨** | UniPi公式のオープンソースAPI。REST/WebSocketで制御。 |
| **b) I2C直接制御** | 高 | △ | I2Cレジスタを直接操作。低レベル制御が必要な場合のみ。 |

### EVOKとは

**EVOK**（Enhanced Virtual Output Kernel）は、UniPi Technology公式のオープンソースAPIです。

**特徴**:
- REST API（HTTP）でリレー・センサーを制御
- WebSocketでリアルタイムイベント受信
- ブラウザから操作可能（WebUI付属）
- Node-REDノードが公式提供

**本手順書では、EVOK API経由での制御を推奨します。**

## 1. SSH & Web Terminal アドオンのインストール

Phase 3では、SSH接続が必要になります。Home Assistant OSにSSH接続するため、「SSH & Web Terminal」アドオンをインストールします。

### ★殿の操作★ SSH & Web Terminal インストール

#### Step 1: アドオンストアを開く

1. Home Assistantダッシュボードにログイン（`http://homeassistant.local:8123`）
2. 左側メニューから「**Settings**」をクリック
3. 「**Add-ons**」をクリック
4. 右下の「**ADD-ON STORE**」ボタンをクリック

#### Step 2: SSH & Web Terminal を検索

1. 検索ボックスに「**Terminal**」と入力
2. 「**Terminal & SSH**」が表示される → クリック

#### Step 3: インストール実行

1. 「**INSTALL**」ボタンをクリック
2. インストール進行中... （1〜2分程度）
3. 「Successfully installed add-on」と表示されたら完了

#### Step 4: 起動設定

1. 「**Configuration**」タブをクリック

2. **パスワード設定**（重要）:

   ```yaml
   ssh:
     username: root
     password: "your-strong-password"  # 強固なパスワードを設定
     authorized_keys: []
     sftp: false
     compatibility_mode: false
     allow_agent_forwarding: false
     allow_remote_port_forwarding: false
     allow_tcp_forwarding: false
   ```

   **重要**: `your-strong-password` を強固なパスワードに変更してください。

3. **以下のオプションを有効化**:
   - [x] **Start on boot**
   - [x] **Show in sidebar**

4. 「**SAVE**」ボタンをクリック

#### Step 5: 起動

1. 「**Info**」タブに戻る
2. 「**START**」ボタンをクリック
3. ステータスが **「Running」** になればOK

### SSH接続テスト

#### ★殿の操作★ SSH接続確認

**方法1: ブラウザから接続（簡単）**

1. Home Assistantの左側メニューに「**Terminal**」アイコンが表示される → クリック
2. ターミナルが開く
3. プロンプト（`#`）が表示されればOK

**方法2: 外部ターミナルから接続（Ubuntu/macOS/Windows）**

```bash
# ターミナル（Ubuntu/macOS）またはPowerShell（Windows）から
ssh root@homeassistant.local

# パスワード入力（設定したパスワード）

# プロンプトが表示されれば接続成功
#
```

または IPアドレス指定:

```bash
ssh root@192.168.1.100  # IPアドレスは環境に応じて変更
```

## 2. I2Cデバイス確認

SSHでHome Assistant OSに接続し、UniPi 1.1のI2Cデバイスが認識されているか確認します。

### ★殿の操作★ I2Cデバイス検出

#### Step 1: SSH接続

前述の方法で、SSH & Web Terminalに接続します。

#### Step 2: I2C有効化確認

Home Assistant OSでは、I2Cはデフォルトで有効化されていますが、念のため確認します。

```bash
# I2Cデバイスが存在するか確認
ls /dev/i2c*

# 出力例:
# /dev/i2c-1
```

`/dev/i2c-1` が表示されればOKです。

#### Step 3: I2Cツールのインストール

Home Assistant OS Container版では、`i2c-tools` がインストールされていない場合があります。

```bash
# i2c-tools がインストールされているか確認
which i2cdetect

# インストールされていない場合
apk add i2c-tools
```

**注**: Home Assistant OS（HAOS）では、`apk` コマンドが使えない場合があります。その場合は、Step 4に進んでください（後述の代替方法を使用）。

#### Step 4: I2Cデバイススキャン

```bash
# I2Cバス1をスキャン
i2cdetect -y 1
```

**期待する出力**:

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- 18 -- -- -- -- -- -- --
20: 20 -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

- **0x18**: MCP9808 温度センサー
- **0x20**: MCP23008 GPIO拡張（リレー制御）

この2つのアドレスが表示されていれば、UniPi 1.1が正常に認識されています。

## 3. EVOKのインストール

UniPi公式のEVOK APIをインストールします。

### EVOKインストール方法の選択

EVOKのインストール方法は2つあります：

| 方法 | 説明 | 推奨度 |
|------|------|--------|
| **a) Dockerコンテナ** | 最も簡単。Home Assistant Containerと共存可能。 | ◎ |
| **b) ネイティブインストール** | Raspberry Pi OSに直接インストール。 | △ |

本手順書では、**Dockerコンテナ版**を推奨します（Home Assistant OSと共存しやすいため）。

### ★殿の操作★ EVOK Dockerコンテナのインストール

#### Step 1: Dockerが利用可能か確認

Home Assistant OSでは、Dockerが既にインストールされています。

```bash
# Docker確認
docker --version

# 出力例:
# Docker version 24.0.7, build afdd53b
```

#### Step 2: EVOK Dockerコンテナを起動

```bash
# EVOK公式Dockerイメージを起動
docker run -d \
  --name evok \
  --restart unless-stopped \
  --privileged \
  --network host \
  -v /etc/evok:/etc/evok \
  unipitechnology/evok:latest
```

**パラメータ説明**:
- `--name evok`: コンテナ名を「evok」に設定
- `--restart unless-stopped`: Raspberry Pi再起動時に自動起動
- `--privileged`: I2Cデバイスへのアクセスに必要
- `--network host`: ホストネットワークを使用（ポート8080で公開）
- `-v /etc/evok:/etc/evok`: 設定ファイルをホストと共有

#### Step 3: EVOK起動確認

```bash
# EVOKコンテナの状態確認
docker ps | grep evok

# 出力例:
# a1b2c3d4e5f6  unipitechnology/evok:latest  "/usr/bin/evok"  Up 10 seconds  evok
```

「Up」と表示されていれば起動成功です。

#### Step 4: EVOKログ確認

```bash
# EVOKのログを表示
docker logs evok

# 正常な出力例:
# INFO:evok:Starting Evok...
# INFO:evok:WebSocket server started on port 8080
# INFO:evok:REST API server started on port 8080
```

エラーが表示されていないか確認してください。

### EVOKのWebUIにアクセス

EVOKには、Webブラウザから操作できるUIが付属しています。

#### ★殿の操作★ EVOK WebUIを開く

1. **ブラウザで以下のURLにアクセス**:

   ```
   http://homeassistant.local:8080
   ```

   または

   ```
   http://192.168.1.100:8080  # IPアドレスは環境に応じて変更
   ```

2. **EVOKのWebUIが表示される**

   - 左側: デバイス一覧（Relays, Digital Inputs, Analog Inputs, 1-Wire等）
   - 右側: 各デバイスの状態・制御ボタン

3. **リレー一覧を確認**

   - 「Relays」セクションに、Relay 1〜8 が表示される
   - 各リレーに「ON」「OFF」ボタンがある

これで、EVOKのインストールは完了です。

## 4. リレー制御テスト

EVOKを使って、リレーを実際に制御してみます。

### ★殿の操作★ リレー制御テスト（WebUI）

#### Step 1: EVOK WebUIでリレーをON

1. EVOK WebUI（`http://homeassistant.local:8080`）を開く
2. 「Relays」セクションで **Relay 1** の「**ON**」ボタンをクリック
3. **リレーのカチッという音を確認**

   - UniPi 1.1基板上のリレーがカチッと音を立ててONになる
   - これはリレーの接点が閉じた音

4. **Relay 1** の「**OFF**」ボタンをクリック
5. 再びカチッという音がして、リレーがOFFになる

**注意**: この段階では、リレーに高電圧機器（電磁弁、ファン等）を接続しないでください。動作確認のみを行います。

#### Step 2: REST APIでリレー制御（SSH）

SSHターミナルから、`curl`コマンドでリレーを制御します。

```bash
# Relay 1の状態を取得
curl http://localhost:8080/rest/relay/1

# 出力例:
# 0  （0=OFF, 1=ON）

# Relay 1をON
curl -X POST http://localhost:8080/rest/relay/1 -d "value=1"

# ★殿の確認★ リレーのカチッという音を確認

# Relay 1の状態を再取得
curl http://localhost:8080/rest/relay/1

# 出力例:
# 1  （ONになっている）

# Relay 1をOFF
curl -X POST http://localhost:8080/rest/relay/1 -d "value=0"

# ★殿の確認★ リレーのカチッという音を確認
```

#### Step 3: JSON形式でのリレー制御

```bash
# JSON形式でリレー状態を取得
curl http://localhost:8080/json/relay/1

# 出力例:
# {"circuit": "1", "value": 0, "pending": false, "mode": "Simple"}

# JSON形式でリレーをON
curl -X POST http://localhost:8080/json/relay/1 \
  -H "Content-Type: application/json" \
  -d '{"value": 1}'

# JSON形式でリレーをOFF
curl -X POST http://localhost:8080/json/relay/1 \
  -H "Content-Type: application/json" \
  -d '{"value": 0}'
```

### リレー制御テストの確認

| テスト項目 | 期待結果 | 判定 |
|-----------|---------|------|
| WebUIでRelay 1 ON | カチッという音 | ☐ OK / ☐ NG |
| WebUIでRelay 1 OFF | カチッという音 | ☐ OK / ☐ NG |
| REST APIでRelay 1 ON | カチッという音 | ☐ OK / ☐ NG |
| REST APIでRelay 1 OFF | カチッという音 | ☐ OK / ☐ NG |

**全てOKであれば、リレー制御は正常に動作しています。**

## 5. 温度センサー（MCP9808）読み取り

UniPi 1.1基板上に搭載されているMCP9808温度センサーの値を読み取ります。

### ★殿の操作★ 温度センサー確認

#### 方法1: EVOK WebUI

1. EVOK WebUI（`http://homeassistant.local:8080`）を開く
2. 「1-Wire」または「Sensors」セクションを確認
3. 温度センサーの値が表示される

**注**: EVOKのバージョンや設定によっては、MCP9808が1-Wireセクションに表示されない場合があります。その場合は、方法2（I2C直接読み取り）を使用してください。

#### 方法2: I2C直接読み取り（SSH）

```bash
# i2cget コマンドでMCP9808から温度を読み取る
# MCP9808のアドレス: 0x18
# 温度レジスタ: 0x05

# 上位バイト読み取り
TEMP_HIGH=$(i2cget -y 1 0x18 0x05)
# 下位バイト読み取り
TEMP_LOW=$(i2cget -y 1 0x18 0x06)

echo "Temperature High: $TEMP_HIGH"
echo "Temperature Low: $TEMP_LOW"

# 温度計算（手動）
# 上位5bitがサインと整数部、下位8bitが小数部
# 詳細はMCP9808データシート参照
```

**簡易確認スクリプト**:

```bash
# temp_read.sh
#!/bin/bash
TEMP_HIGH=$(i2cget -y 1 0x18 0x05)
TEMP_LOW=$(i2cget -y 1 0x06)

# 16進数を10進数に変換
TEMP_HIGH_DEC=$((TEMP_HIGH))
TEMP_LOW_DEC=$((TEMP_LOW))

# 簡易計算（サイン無視）
TEMP=$(awk "BEGIN {print ($TEMP_HIGH_DEC * 16 + $TEMP_LOW_DEC / 16)}")
echo "Temperature: ${TEMP}°C"
```

実行:

```bash
chmod +x temp_read.sh
./temp_read.sh

# 出力例:
# Temperature: 24.5°C
```

## 6. Node-REDからの制御フロー

Phase 2でインストールしたNode-REDから、EVOKを経由してリレーを制御します。

### ★殿の操作★ Node-REDからのリレー制御

#### Step 1: Node-REDエディタを開く

1. ブラウザで `http://homeassistant.local:1880` にアクセス
2. Node-REDエディタが開く

#### Step 2: UniPi公式ノードのインストール

1. 右上の「☰」メニュー → 「Manage palette」をクリック
2. 「Install」タブをクリック
3. 検索ボックスに「**unipi**」と入力
4. 「**@unipitechnology/node-red-contrib-unipi-evok**」を探す
5. 「Install」ボタンをクリック
6. インストール完了後、「Close」をクリック

**注**: インストールには1〜2分かかります。

#### Step 3: HTTP Requestノードでのリレー制御（簡易版）

UniPi公式ノードが使えない場合、HTTP Requestノードで代替できます。

**フロー構成**:

```
[inject] → [http request] → [debug]
```

**手順**:

1. 左側パレットから「**inject**」ノードをキャンバスにドラッグ
2. 左側パレットから「**http request**」ノードをキャンバスにドラッグ
3. 左側パレットから「**debug**」ノードをキャンバスにドラッグ
4. ノードを接続: inject → http request → debug

**http request ノードの設定**:

1. http requestノードをダブルクリック
2. 以下のように設定:
   - **Method**: POST
   - **URL**: `http://localhost:8080/json/relay/1`
   - **Payload**: 「JSON」を選択し、以下を入力:
     ```json
     {"value": 1}
     ```
   - **Return**: 「a parsed JSON object」を選択
3. 「Done」をクリック

**inject ノードの設定**:

1. injectノードをダブルクリック
2. **msg.payload** を「JSON」に変更し、以下を入力:
   ```json
   {"value": 1}
   ```
3. 「Done」をクリック

**デプロイ**:

1. 右上の「**Deploy**」ボタンをクリック
2. injectノードの左側の **ボタンをクリック**
3. **リレーのカチッという音を確認**
4. 右側の「debug」タブに、EVOKからのレスポンスが表示される

#### Step 4: リレーOFFフローの作成

同様に、リレーOFFのフローも作成します。

1. 新しい injectノード → http requestノード → debugノードを配置
2. http requestノードの設定:
   - **URL**: `http://localhost:8080/json/relay/1`
   - **Payload**: `{"value": 0}`
3. Deploy → injectボタンをクリック → リレーOFF確認

### サンプルフロー（温度監視→リレー制御）

温度が30℃を超えたらリレーをON、25℃以下でOFFにする自動制御フローの例です。

**フロー構成**:

```
[inject (定期実行)] → [http request (温度取得)] → [function (閾値判定)] → [http request (リレー制御)]
```

詳細は、Phase 4（農業制御ロジック実装）で取り扱います。

## 7. Home AssistantとNode-REDの連携

Node-REDで制御したリレーを、Home Assistantのダッシュボードに表示します。

### ★殿の操作★ Home Assistantエンティティ作成

#### Step 1: Home AssistantノードをNode-REDにインストール

1. Node-REDエディタで「☰」メニュー → 「Manage palette」
2. 「Install」タブ → 「**node-red-contrib-home-assistant-websocket**」を検索
3. 「Install」ボタンをクリック

#### Step 2: Home Assistant接続設定

1. Node-REDの設定に、Home Assistantサーバー設定を追加
2. **Long-Lived Access Token** を取得:
   - Home Assistant → Profile → Long-Lived Access Tokens → 「CREATE TOKEN」
   - トークン名: `Node-RED`
   - トークンをコピー

3. Node-REDで「events: state」ノードを追加し、サーバー設定にトークンを入力

詳細なHome Assistant連携は、Phase 4で実施します。

## Phase 3 完了確認チェックリスト

### インストール確認

- [ ] SSH & Web Terminal アドオンがRunning状態になっている
- [ ] SSH接続ができる（ブラウザまたは外部ターミナル）
- [ ] I2Cデバイススキャンで 0x18, 0x20 が検出された
- [ ] EVOKコンテナが起動している（`docker ps | grep evok`）
- [ ] EVOK WebUI（`http://homeassistant.local:8080`）にアクセスできる

### リレー制御確認

- [ ] EVOK WebUIでRelay 1をON/OFFできる
- [ ] リレーのカチッという音が確認できる
- [ ] REST APIでリレーをON/OFFできる
- [ ] Node-REDからリレーをON/OFFできる

### センサー確認

- [ ] MCP9808温度センサーの値を読み取れる（EVOK WebUIまたはI2C直接）
- [ ] 温度値が妥当な範囲（15〜30℃程度）である

### ★殿の確認作業★（Phase 3完了チェック）

| 確認項目 | 期待結果 | 判定 |
|---------|---------|------|
| SSH接続 | ターミナルでプロンプト表示 | ☐ OK / ☐ NG |
| I2Cデバイス検出 | 0x18, 0x20 が表示 | ☐ OK / ☐ NG |
| EVOKコンテナ起動 | `docker ps` で evok が Up | ☐ OK / ☐ NG |
| EVOK WebUIアクセス | ブラウザでリレー一覧表示 | ☐ OK / ☐ NG |
| WebUIでリレーON | カチッという音 | ☐ OK / ☐ NG |
| REST APIでリレーON | `curl`コマンドで制御成功 | ☐ OK / ☐ NG |
| Node-REDでリレーON | injectボタンで制御成功 | ☐ OK / ☐ NG |
| 温度センサー読み取り | 温度値が表示される | ☐ OK / ☐ NG |

**Phase 3 完了！次はPhase 4（農業制御ロジック実装）に進みます。**

## トラブルシューティング

### 問題1: I2Cデバイスが検出されない

**症状**: `i2cdetect -y 1` で 0x18, 0x20 が表示されない

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| UniPi 1.1が正しく接続されていない | Raspberry Pi 4の電源をオフにし、UniPi 1.1を再接続 |
| I2Cが有効化されていない | `/boot/config.txt` に `dtparam=i2c_arm=on` を追加し、再起動 |
| ケーブル不良 | GPIOヘッダーの接触不良を確認 |

### 問題2: EVOKコンテナが起動しない

**症状**: `docker ps | grep evok` で何も表示されない

**確認**:

```bash
# EVOKコンテナのログ確認
docker logs evok

# 停止したコンテナを表示
docker ps -a | grep evok
```

**対処法**:

| 原因 | 対処法 |
|------|--------|
| Dockerイメージのダウンロード失敗 | `docker pull unipitechnology/evok:latest` で再ダウンロード |
| ポート8080が既に使用中 | 別のサービス（Nginx等）がポート8080を使用していないか確認 |
| --privileged権限エラー | Dockerコマンドに `--privileged` が含まれているか確認 |

### 問題3: リレーが動作しない（音がしない）

**症状**: EVOK WebUIやREST APIでリレーをONにしても、カチッという音がしない

**確認手順**:

1. **I2C通信確認**:
   ```bash
   # MCP23008に直接書き込み
   i2cset -y 1 0x20 0x00 0x00  # 出力方向設定
   i2cset -y 1 0x20 0x09 0x80  # Relay 1 ON（GP7=0x80）
   ```

   リレーが動作すれば、I2C通信は正常。EVOKの設定を確認。

2. **電源電圧確認**: UniPi 1.1に24V DCが供給されているか確認（リレー駆動に必要）

3. **リレーの物理的故障**: 別のリレー（Relay 2, 3等）で試す

### 問題4: EVOK WebUIにアクセスできない

**症状**: `http://homeassistant.local:8080` が開かない

**確認**:

```bash
# EVOKコンテナが起動しているか
docker ps | grep evok

# ポート8080がリスンしているか
netstat -tlnp | grep 8080
```

**対処法**:

| 原因 | 対処法 |
|------|--------|
| EVOKコンテナが起動していない | `docker start evok` で起動 |
| ファイアウォールがブロック | Home Assistant OSではデフォルトでファイアウォール無効 |
| IPアドレスで直接アクセス | `http://192.168.1.100:8080` で試す |

### 問題5: 温度センサー（MCP9808）が読めない

**症状**: EVOK WebUIに温度センサーが表示されない、またはI2C読み取りでエラー

**確認**:

```bash
# MCP9808のI2Cアドレスを確認
i2cdetect -y 1

# 0x18 が表示されるか確認
```

**対処法**:

| 原因 | 対処法 |
|------|--------|
| I2Cアドレスが競合 | 他のI2Cデバイスと競合していないか確認 |
| MCP9808が搭載されていない | UniPi 1.1のバージョンによっては未搭載の場合あり |
| EVOKの1-Wire設定が有効 | `/etc/evok/evok.conf` でMCP9808の設定を確認 |

### 問題6: Node-REDからリレー制御できない

**症状**: Node-REDのhttp requestノードでエラーが出る

**確認**:

- **URLが正しいか**: `http://localhost:8080/json/relay/1`
- **Payloadが正しいか**: `{"value": 1}`
- **Methodが正しいか**: POST
- **EVOKが起動しているか**: `docker ps | grep evok`

**Node-REDデバッグタブのエラーメッセージを確認してください。**

## 参考資料

### 公式ドキュメント

- [UniPi Technology](https://www.unipi.technology/)
- [EVOK GitHub](https://github.com/UniPiTechnology/evok)
- [EVOK Documentation](https://evok.readthedocs.io/)
- [EVOK API Reference](https://unipitechnology.stoplight.io/docs/evok)
- [Node-RED UniPi ノード](https://flows.nodered.org/node/@unipitechnology/node-red-contrib-unipi-evok)

### Home Assistant関連

- [Home Assistant - SSH & Web Terminal Add-on](https://github.com/hassio-addons/addon-ssh)
- [Node-RED Home Assistant ノード](https://flows.nodered.org/node/node-red-contrib-home-assistant-websocket)

### I2Cデバイス

- [MCP23008 データシート](https://www.microchip.com/wwwproducts/en/MCP23008)
- [MCP9808 データシート](https://www.microchip.com/wwwproducts/en/MCP9808)

### コミュニティ

- [UniPi フォーラム](https://forum.unipi.technology/)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

---

## 次のステップ

Phase 3が完了したら、Phase 4（農業制御ロジック実装）に進みます。

**Phase 4で実施すること**:
- 8時間帯タイマーの実装（Node-RED）
- 温度・湿度に基づく自動制御（VPD制御）
- MQTTでのPico連携（W5500-EVB-Pico-PoE追加時）
- Home Assistantダッシュボードのカスタマイズ
- LINE/Slack通知の設定
- データロギング（InfluxDB + Grafana）
