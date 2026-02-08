# Phase 2: Home Assistant アドオン導入手順

**作成日**: 2026-02-06
**対象**: Raspberry Pi 4 + UniPi 1.1
**Home Assistant OS バージョン**: 2026.2.0

## 概要

本ドキュメントは、Phase 1で構築したHome Assistant OSに、農業IoT制御に必要な3つのアドオンを導入する手順を記載する。

殿ご自身で実施いただく作業は **★殿の操作★** で明示する。

## 前提条件

以下が完了していることを確認してください：

- [ ] Phase 1が完了している
- [ ] Home Assistant OSが起動している
- [ ] Webインターフェース（`http://homeassistant.local:8123`）にアクセスできる
- [ ] 管理者アカウントでログインできる

## 導入するアドオン一覧

| アドオン | 用途 | 必須度 | Phase 3以降での役割 |
|---------|------|--------|-------------------|
| **Mosquitto broker** | MQTTブローカー | 必須 | Pico/W5500からのセンサーデータ受信 |
| **Node-RED** | フロー制御エンジン | 必須 | 農業制御ロジックの実装 |
| **File Editor** | 設定ファイル編集 | 推奨 | configuration.yaml等の編集 |

## アドオンストアへのアクセス

### ★殿の操作★ Step 1: アドオンストアを開く

1. **Home Assistantダッシュボードにログイン**

   ブラウザで `http://homeassistant.local:8123` にアクセス

2. **左側メニューから「Settings」をクリック**

3. **「Add-ons」をクリック**

4. **右下の「ADD-ON STORE」ボタンをクリック**

   → アドオンストアが表示される

## 1. Mosquitto broker インストール

### 概要

**Mosquitto broker** は、MQTT（Message Queuing Telemetry Transport）プロトコルのブローカーです。

- IoTデバイス（W5500-EVB-Pico-PoE等）からセンサーデータを受信
- Home Assistantとデバイス間の双方向通信を実現
- 軽量で信頼性が高い

### ★殿の操作★ インストール手順

#### Step 1: アドオンを検索

1. アドオンストアの検索ボックスに「**Mosquitto**」と入力

2. **「Mosquitto broker」** が表示される → クリック

#### Step 2: インストール実行

1. 「INSTALL」ボタンをクリック

2. インストール進行中... （1〜3分程度）

3. 「Successfully installed add-on」と表示されたら完了

#### Step 3: 起動設定

1. 「Configuration」タブをクリック

2. **以下のオプションを有効化**:
   - [x] **Start on boot** （起動時に自動起動）
   - [x] **Watchdog** （異常終了時に自動再起動）

3. 「SAVE」ボタンをクリック

#### Step 4: 起動

1. 「Info」タブに戻る

2. 「START」ボタンをクリック

3. ステータスが **「Running」** になればOK

### 初期設定（MQTT ユーザー作成）

Phase 3でIoTデバイスを接続する際に必要なMQTTユーザーを作成します。

#### ★殿の操作★ ユーザー作成手順

1. **Home Assistantの「Settings」→「People」→「Users」タブをクリック**

2. **右下の「ADD USER」ボタンをクリック**

3. **ユーザー情報を入力**:
   - **Name**: mqtt_user（または任意）
   - **Username**: mqtt_user
   - **Password**: 強固なパスワード（Phase 3でIoTデバイスに設定）
   - [x] **Can only log in from the local network** （ローカルネットワークのみ）
   - [x] **Allow person to use Home Assistant** のチェックを **外す** （MQTTのみに使用）

4. 「CREATE」ボタンをクリック

5. **メモ**: `Username` と `Password` をPhase 3で使用するため記録しておく

### 動作確認（Phase 3以降で実施）

MQTT動作確認は、Phase 3でIoTデバイスを接続した際に行います。

## 2. Node-RED インストール

### 概要

**Node-RED** は、フローベースのプログラミングツールです。

- ドラッグ&ドロップでロジックを構築
- センサーデータの加工・判断・アクション実行
- Home AssistantとMQTTを連携

農業制御ロジック（例: 温度が30℃を超えたら換気扇ON）を実装します。

### ★殿の操作★ インストール手順

#### Step 1: アドオンを検索

1. アドオンストアの検索ボックスに「**Node-RED**」と入力

2. **「Node-RED」** が表示される → クリック

#### Step 2: インストール実行

1. 「INSTALL」ボタンをクリック

2. インストール進行中... （2〜5分程度、Node.jsパッケージをダウンロード）

3. 「Successfully installed add-on」と表示されたら完了

#### Step 3: 起動設定

1. 「Configuration」タブをクリック

2. **以下のYAML設定を確認**:

   ```yaml
   credential_secret: ""  # 空のままでOK（初回起動時に自動生成）
   http_node:
     username: ""
     password: ""
   http_static:
     username: ""
     password: ""
   ssl: false
   certfile: fullchain.pem
   keyfile: privkey.pem
   require_ssl: false
   system_packages: []
   npm_packages: []
   init_commands: []
   ```

   **重要**: Phase 3でHome Assistantノード（node-red-contrib-home-assistant-websocket）をインストールするため、現時点では `npm_packages` は空のままでOK。

3. **以下のオプションを有効化**:
   - [x] **Start on boot**
   - [x] **Watchdog**

4. 「SAVE」ボタンをクリック

#### Step 4: 起動

1. 「Info」タブに戻る

2. 「START」ボタンをクリック

3. ステータスが **「Running」** になればOK

### Node-REDエディタにアクセス

#### ★殿の操作★ エディタを開く

1. **ブラウザで以下のURLにアクセス**:

   ```
   http://homeassistant.local:1880
   ```

   または

   ```
   http://<Raspberry PiのIPアドレス>:1880
   ```

2. **Node-REDエディタが表示される**

   - 左側: ノードパレット（利用可能な機能）
   - 中央: フローキャンバス（ドラッグ&ドロップでロジックを構築）
   - 右側: デバッグ情報、設定

3. **テストフローを作成**（動作確認）:

   1. 左側パレットから「**inject**」ノードをキャンバスにドラッグ
   2. 左側パレットから「**debug**」ノードをキャンバスにドラッグ
   3. inject ノードの右端をドラッグして debug ノードの左端に接続
   4. 右上の「Deploy」ボタンをクリック
   5. inject ノードの左側の **ボタンをクリック**
   6. 右側の「debug」タブに `timestamp` が表示されればOK

4. **Phase 3で実施すること**:
   - Home Assistantノード（node-red-contrib-home-assistant-websocket）のインストール
   - センサーデータ受信フローの構築
   - 制御ロジックの実装

### 初期設定（パスワード保護：推奨）

Node-REDエディタに外部からアクセスされないよう、パスワード保護を設定します。

#### ★殿の操作★ パスワード設定（オプションだが推奨）

**注**: Phase 2の時点では、ローカルネットワーク内のみで使用するため、パスワード設定はオプションです。外部公開する場合は必須です。

パスワード設定を行う場合は、Phase 3で「SSH & Web Terminal」アドオンをインストール後、`/config/.node-red/settings.js` を編集します。詳細はPhase 3の手順書に記載します。

## 3. File Editor インストール

### 概要

**File Editor** は、Home Assistantの設定ファイルをブラウザから編集できるツールです。

- `configuration.yaml` の編集
- `automations.yaml` の編集
- スクリプト、センサー定義の編集

SSH接続せずに設定変更ができるため便利です。

**代替選択肢**: より高機能な **Studio Code Server** もあります（VSCodeのブラウザ版）。初心者には File Editor が軽量で使いやすいです。

### ★殿の操作★ インストール手順

#### Step 1: アドオンを検索

1. アドオンストアの検索ボックスに「**File Editor**」と入力

2. **「File editor」** が表示される → クリック

   **補足**: Studio Code Serverを使いたい場合は「Studio Code Server」を検索してください。

#### Step 2: インストール実行

1. 「INSTALL」ボタンをクリック

2. インストール進行中... （1〜2分程度）

3. 「Successfully installed add-on」と表示されたら完了

#### Step 3: 起動設定

1. 「Configuration」タブをクリック

2. **以下のオプションを有効化**:
   - [x] **Start on boot**
   - [x] **Watchdog**
   - [x] **Show in sidebar** （左側メニューに表示）

3. 「SAVE」ボタンをクリック

#### Step 4: 起動

1. 「Info」タブに戻る

2. 「START」ボタンをクリック

3. ステータスが **「Running」** になればOK

### File Editorを使ってみる

#### ★殿の操作★ 設定ファイル編集確認

1. **左側メニューに「File editor」アイコンが表示される** → クリック

2. **File Editorが開く**

   - 左側: ファイルツリー（`/config/` 配下）
   - 右側: エディタ

3. **`configuration.yaml` を開く**

   - 左側ツリーから `configuration.yaml` をクリック
   - エディタに内容が表示される

4. **確認のみ（編集不要）**

   ```yaml
   # Loads default set of integrations. Do not remove.
   default_config:

   # Load frontend themes from the themes folder
   frontend:
     themes: !include_dir_merge_named themes

   automation: !include automations.yaml
   script: !include scripts.yaml
   scene: !include scenes.yaml
   ```

5. **編集せずに閉じる**（動作確認のみ）

## Phase 2 完了確認チェックリスト

### アドオンインストール確認

- [ ] **Mosquitto broker** がインストールされ、Running状態になっている
- [ ] MQTT用のユーザー（mqtt_user）が作成されている
- [ ] **Node-RED** がインストールされ、Running状態になっている
- [ ] Node-REDエディタ（`http://homeassistant.local:1880`）にアクセスできる
- [ ] **File Editor** がインストールされ、Running状態になっている
- [ ] File Editorで `configuration.yaml` を開けることを確認した

### ★殿の確認作業★（Phase 2完了チェック）

以下を確認し、全てOKであればPhase 2完了です：

| 確認項目 | 期待結果 | 判定 |
|---------|---------|------|
| Mosquitto broker ステータス | Running | ☐ OK / ☐ NG |
| MQTT ユーザー作成 | mqtt_user が存在 | ☐ OK / ☐ NG |
| Node-RED ステータス | Running | ☐ OK / ☐ NG |
| Node-RED エディタアクセス | `http://homeassistant.local:1880` が開く | ☐ OK / ☐ NG |
| Node-RED テストフロー | injectボタンでdebug出力される | ☐ OK / ☐ NG |
| File Editor ステータス | Running | ☐ OK / ☐ NG |
| File Editor 動作確認 | `configuration.yaml` が開ける | ☐ OK / ☐ NG |

**Phase 2 完了！次はPhase 3（UniPi 1.1統合・センサー接続）に進みます。**

## トラブルシューティング

### 問題1: アドオンのインストールが失敗する

**症状**: 「Failed to install add-on」エラーが表示される

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| インターネット接続不良 | LANケーブル接続確認、ルーター再起動 |
| DNSサーバーの問題 | `設定 > システム > ネットワーク` でDNSを手動設定（例: 8.8.8.8） |
| ストレージ容量不足 | `設定 > システム > ストレージ` で空き容量確認、32GB以上推奨 |
| Dockerイメージのダウンロード失敗 | Raspberry Piを再起動後、再インストール |

### 問題2: Mosquitto broker が起動しない

**症状**: START をクリックしても Running にならない

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| ポート1883が既に使用中 | 他のMQTTブローカーが動作していないか確認 |
| 設定ファイルのエラー | アドオンを一度アンインストールして再インストール |
| ログ確認 | アドオンの「Log」タブでエラーメッセージを確認 |

### 問題3: Node-RED エディタにアクセスできない

**症状**: `http://homeassistant.local:1880` が開かない

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| Node-REDが起動していない | アドオンのステータスを確認、STARTボタンをクリック |
| ポート1880がブロックされている | ファイアウォール設定を確認、ローカルネットワークなら通常は問題なし |
| mDNSが動作していない | `http://<IPアドレス>:1880` で直接アクセス |
| 初回起動が完了していない | 2〜3分待機してから再アクセス |

### 問題4: File Editor で保存できない

**症状**: 設定ファイルを編集して保存しようとするとエラーが出る

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| 構文エラー（YAMLのインデント等） | YAML構文を確認、インデントはスペース2つ |
| ファイルの権限がない | File Editorを再起動、または Studio Code Server を試す |
| ディスク容量不足 | `設定 > システム > ストレージ` で空き容量確認 |

### 問題5: MQTT ユーザーでログインできない（Phase 3以降）

**症状**: IoTデバイスからMQTT接続しようとするとエラーが出る

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| ユーザー名/パスワードが間違っている | `設定 > People > Users` でmqtt_userの設定を再確認 |
| MQTTユーザーに権限がない | ユーザー作成時に「Can only log in from the local network」がONになっているか確認 |
| Mosquitto brokerが起動していない | アドオンのステータスを確認 |

### ログの確認方法

アドオンで問題が発生した場合、ログを確認することで原因を特定できます。

#### ★殿の操作★ ログ確認手順

1. **「Settings」→「Add-ons」**

2. **問題が発生しているアドオンをクリック**

3. **「Log」タブをクリック**

4. **エラーメッセージを確認**

   - 赤色の「ERROR」行がないか確認
   - エラーメッセージをコピーして検索すると解決策が見つかることが多い

5. **ログをリフレッシュ**: 右上の「Refresh」ボタンで最新ログを表示

## 参考資料

### 公式ドキュメント

- [Home Assistant - Add-ons](https://www.home-assistant.io/addons/)
- [Mosquitto broker Add-on](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md)
- [Node-RED Add-on](https://github.com/hassio-addons/addon-node-red/blob/main/node-red/DOCS.md)
- [File Editor Add-on](https://github.com/home-assistant/addons/blob/master/configurator/DOCS.md)

### MQTT関連

- [MQTT - Wikipedia](https://en.wikipedia.org/wiki/MQTT)
- [Mosquitto - Eclipse Foundation](https://mosquitto.org/)

### Node-RED関連

- [Node-RED 公式サイト](https://nodered.org/)
- [Node-RED - Getting Started](https://nodered.org/docs/getting-started/)
- [node-red-contrib-home-assistant-websocket](https://zachowj.github.io/node-red-contrib-home-assistant-websocket/)

### コミュニティ

- [Home Assistant Community Forum - Add-ons](https://community.home-assistant.io/c/third-party/hassio-addons/57)

---

## 次のステップ

Phase 2が完了したら、Phase 3（UniPi 1.1統合・センサー接続）に進みます。

**Phase 3で実施すること**:
- SSH & Web Terminal アドオンのインストール（ACT LED制御テスト用）
- UniPi 1.1 の物理接続
- UniPi統合（EVOK）のセットアップ
- センサー（温度・湿度・CO2等）の設定
- Node-REDでのセンサーデータ受信フロー構築
- アクチュエーター（リレー・バルブ等）の制御テスト
