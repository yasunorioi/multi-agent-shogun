# Phase 1: Home Assistant OS インストール手順

**作成日**: 2026-02-05
**対象**: Raspberry Pi 4 + UniPi 1.1
**Home Assistant OS バージョン**: 2026.2.0（最新）

## 概要

本ドキュメントは、Raspberry Pi 4にHome Assistant OSをインストールし、初回セットアップを完了させるまでの手順を記載する。

殿ご自身で物理作業（SD書き込み、配線等）を実施いただく部分は **★殿の物理作業★** で明示する。

## 必要機材リスト

| 機材 | 仕様 | 必須/推奨 | 備考 |
|------|------|----------|------|
| **Raspberry Pi 4** | 2GB以上のRAM | 必須 | 4GB/8GBモデル推奨 |
| **microSDカード** | 32GB以上 | 必須 | Class 10以上推奨、高品質メーカー品を推奨 |
| **電源アダプタ** | 5V/3A（USB Type-C） | 必須 | 公式電源または同等品 |
| **LANケーブル** | Cat5e以上 | 強く推奨 | WiFiより有線LANが安定 |
| **SDカードリーダー** | microSD対応 | 必須 | PCへのSD書き込み用 |
| **モニター＋HDMIケーブル** | - | オプション | トラブル時の確認用（通常は不要） |
| **UniPi 1.1** | - | Phase 3で使用 | Phase 1では未接続 |

### 推奨構成

- **Raspberry Pi 4 (4GB)**: 十分な余裕を持って動作
- **SanDisk Extreme 32GB microSDHC**: 高速・高耐久
- **公式電源アダプタ**: 電圧安定性が高い

## Home Assistant OS イメージ取得

### ダウンロード手順

1. **公式サイトにアクセス**

   [Home Assistant - Raspberry Pi](https://www.home-assistant.io/installation/raspberrypi/)

2. **Raspberry Pi 4用イメージを選択**

   ページ内の「Raspberry Pi 4」セクションから以下のいずれかをダウンロード：
   - **64-bit版（推奨）**: `haos_rpi4-64-[version].img.xz`
   - 32-bit版: `haos_rpi4-[version].img.xz`

   **最新バージョン**: 2026.2.0（2026年2月現在）

3. **GitHub Releasesから直接ダウンロード（代替方法）**

   [home-assistant/operating-system Releases](https://github.com/home-assistant/operating-system/releases)

   - 最新のReleaseページを開く
   - Assets セクションから `haos_rpi4-64-[version].img.xz` をダウンロード

### ファイル名の例

```
haos_rpi4-64-2026.2.0.img.xz
```

## SD書き込み手順

### 方法1: Raspberry Pi Imager 使用（推奨）

**Raspberry Pi Imager** は公式の書き込みツールで、最も簡単・確実な方法。

#### ★殿の物理作業★ Step 1: Raspberry Pi Imager インストール

1. 以下のURLにアクセス

   https://www.raspberrypi.com/software/

2. お使いのOS（Windows/macOS/Ubuntu）に対応するインストーラーをダウンロード

3. インストーラーを実行し、Raspberry Pi Imager をインストール

#### ★殿の物理作業★ Step 2: SDカードをPCに挿入

1. microSDカードをSDカードリーダーに挿入
2. SDカードリーダーをPCに接続

#### ★殿の物理作業★ Step 3: イメージ書き込み

1. **Raspberry Pi Imager を起動**

2. **「OSを選ぶ」ボタンをクリック**

3. **「Other specific-purpose OS」 → 「Home assistants and home automation」 → 「Home Assistant」 → 「Raspberry Pi 4 / 400」を選択**

   または

   **「Use custom」を選択し、ダウンロードした `.img.xz` ファイルを指定**

4. **「ストレージを選ぶ」ボタンをクリック**

   - 接続したmicroSDカードを選択
   - ⚠️ **間違えると他のドライブを上書きするので慎重に確認**

5. **「書き込む」ボタンをクリック**

   - 確認ダイアログが表示される → 「はい」をクリック
   - 書き込み開始（5〜10分程度）
   - 「書き込みが完了しました」と表示されたら完了

6. **SDカードを安全に取り出す**

   - Windowsの場合: タスクバーの「ハードウェアの安全な取り外し」
   - macOSの場合: Finder でSDカードを右クリック → 「取り出す」
   - Ubuntuの場合: ファイルマネージャーでアンマウント

### 方法2: Balena Etcher 使用（代替）

Raspberry Pi Imager が使えない場合の代替手段。

1. **Balena Etcher をダウンロード**: https://etcher.balena.io/
2. インストール後、起動
3. 「Flash from file」→ ダウンロードした `.img.xz` を選択
4. 「Select target」→ microSDカードを選択
5. 「Flash!」をクリック
6. 書き込み完了後、SDカードを安全に取り出す

## 初回起動と初期セットアップ

### ★殿の物理作業★ Step 1: Raspberry Pi にSDカードを挿入

1. Raspberry Pi 4 の電源が **オフ** になっていることを確認
2. microSDカードをRaspberry Pi 4のSDカードスロットに挿入
3. LANケーブルをRaspberry Pi 4のEthernetポートに接続
4. LANケーブルの反対側をルーター/スイッチに接続

### ★殿の物理作業★ Step 2: 電源投入

1. USB Type-C 電源アダプタを Raspberry Pi 4 に接続
2. 電源アダプタをコンセントに接続
3. Raspberry Pi 4 の赤色LEDが点灯 → 電源供給OK
4. 緑色LEDが点滅開始 → ブート開始

### Step 3: 起動待ち（重要）

**初回起動は時間がかかります。焦らず待機してください。**

| フェーズ | 所要時間 | 説明 |
|---------|---------|------|
| 初回ブート | 3〜5分 | OSの初期化 |
| Home Assistant 初期セットアップ | 5〜10分 | パッケージのダウンロード・インストール |
| **合計** | **8〜15分** | ネットワーク速度に依存 |

**判定方法**:
- ✅ 緑色LEDが規則的に点滅 → 正常
- ⚠️ 赤色LEDのみ点灯、画面真っ黒 → トラブルシューティング参照
- ⚠️ 15分経過しても何も起こらない → トラブルシューティング参照

### Step 4: Home Assistantへアクセス

**待機時間経過後、PCまたはスマートフォンのブラウザで以下のURLにアクセス:**

```
http://homeassistant.local:8123
```

**アクセスできない場合の代替方法**:

1. **IPアドレスで直接アクセス**

   ルーターの管理画面でRaspberry PiのIPアドレスを確認（例: `192.168.1.100`）

   ```
   http://192.168.1.100:8123
   ```

2. **mDNSが動作していない環境**

   Windowsの場合、Bonjour Servicesのインストールが必要な場合がある

### Step 5: 初期セットアップ（ブラウザ上）

1. **「Welcome to Home Assistant」画面が表示される**

2. **アカウント作成**

   - **名前**: 殿のお名前（例: Yasu）
   - **ユーザー名**: ログインID（例: admin）
   - **パスワード**: 強固なパスワードを設定
   - **パスワード（確認）**: 再入力

   → 「アカウントを作成」ボタンをクリック

3. **ロケーション設定**

   - **家の名前**: 任意（例: 自宅）
   - **位置**: 地図上でピンを配置、または住所入力
   - **タイムゾーン**: 自動検出される（`Asia/Tokyo`）
   - **単位系**: メートル法（デフォルト）

   → 「次へ」ボタンをクリック

4. **デバイス検出**

   ネットワーク上のデバイス（スマートスピーカー、Chromecast等）が自動検出される

   - 必要なものを選択して「設定」
   - 不要な場合は「スキップ」

5. **分析設定**

   - 匿名の使用統計送信の可否を選択
   - 「次へ」をクリック

6. **完了**

   「Home Assistant ダッシュボード」が表示される

   **これでインストール完了です！**

## Phase 1 完了確認チェックリスト

- [ ] Raspberry Pi 4 が起動している（緑LEDが点滅）
- [ ] `http://homeassistant.local:8123` にアクセスできる
- [ ] Home Assistant ダッシュボードが表示される
- [ ] ユーザーアカウントでログインできる

**Phase 1 完了！次はPhase 2（基本設定・アドオンインストール）に進みます。**

## 動作確認テスト（ACT LED制御）

Home Assistant OS が正常にインストールされ、Raspberry Pi 4 が動作していることを確認するため、**ACT LED（緑色LED）** を手動制御してテストします。

### ACT LEDとは

Raspberry Pi 4 には以下の2つのLEDが搭載されています：

- **PWR LED（赤色）**: 電源供給中は常時点灯
- **ACT LED（緑色）**: SDカードアクセス時に点滅（通常はシステムが自動制御）

本テストでは、ACT LEDを **sysfs 経由で手動制御** し、Raspberry Pi 4 のハードウェアとOSが正常に動作していることを確認します。

### 前提条件

- Home Assistant OS が起動している
- SSHまたはコンソールアクセスが可能（Phase 2でSSHアドオンをインストール後に実施）

### ★殿の物理作業★ ACT LED制御テスト

#### Step 1: SSH接続（Phase 2完了後に実施）

Phase 2で「SSH & Web Terminal」アドオンをインストール後、以下の方法でSSH接続します：

```bash
# ターミナル（Ubuntu/macOS）またはPowerShell（Windows）から接続
ssh root@homeassistant.local

# または IPアドレス指定
ssh root@192.168.1.100
```

初回接続時にパスワードが要求されます（アドオン設定で指定したパスワード）。

#### Step 2: ACT LEDの現在の制御モードを確認

```bash
# 現在のトリガー（制御モード）を確認
cat /sys/class/leds/ACT/trigger

# 出力例（デフォルト設定）:
# none kbd-scrolllock kbd-numlock kbd-capslock kbd-kanalock kbd-shiftlock kbd-altgrlock kbd-ctrllock kbd-altlock kbd-shiftllock kbd-shiftrlock kbd-ctrlllock kbd-ctrlrlock [mmc0] heartbeat timer
# [ ] で囲まれているものが現在のモード（通常は mmc0 = SDカードアクセス連動）
```

#### Step 3: 手動制御モードに切り替え

```bash
# trigger を none に設定（手動制御モードに切り替え）
echo none > /sys/class/leds/ACT/trigger

# 確認
cat /sys/class/leds/ACT/trigger
# 出力: [none] kbd-scrolllock kbd-numlock ...
# → [none] になっていればOK
```

#### Step 4: ACT LED点灯テスト

```bash
# LED点灯（brightnessを1に設定）
echo 1 > /sys/class/leds/ACT/brightness

# ★殿の目視確認★
# → Raspberry Pi 4 の基板上の緑色LEDが点灯していることを確認
```

#### Step 5: ACT LED消灯テスト

```bash
# LED消灯（brightnessを0に設定）
echo 0 > /sys/class/leds/ACT/brightness

# ★殿の目視確認★
# → Raspberry Pi 4 の基板上の緑色LEDが消灯していることを確認
```

#### Step 6: 元の設定に戻す

```bash
# trigger を mmc0（SDカードアクセス連動）に戻す
echo mmc0 > /sys/class/leds/ACT/trigger

# 確認
cat /sys/class/leds/ACT/trigger
# 出力: none kbd-scrolllock ... [mmc0] heartbeat timer
# → [mmc0] に戻っていればOK
```

これで、ACT LEDが再びSDカードアクセス時に自動点滅するようになります。

### テスト結果の判定

| テスト項目 | 期待結果 | 判定 |
|-----------|---------|------|
| Step 3: trigger変更 | `[none]` と表示される | OK / NG |
| Step 4: LED点灯 | 緑色LEDが点灯する | OK / NG |
| Step 5: LED消灯 | 緑色LEDが消灯する | OK / NG |
| Step 6: 元の設定に戻す | `[mmc0]` と表示される | OK / NG |

**全てOKであれば、Raspberry Pi 4 のハードウェアとHome Assistant OSが正常に動作しています。**

### トラブルシューティング（ACT LED制御）

| 症状 | 原因 | 対処法 |
|------|------|--------|
| `/sys/class/leds/ACT/` が存在しない | OSバージョンの違い | `/sys/class/leds/led0/` を試す（別名の場合がある） |
| `Permission denied` | 権限不足 | `root`ユーザーで実行しているか確認、`sudo`を使用 |
| LEDが点灯しない | ハードウェア不良 | PWR LED（赤）が点灯していれば電源はOK。別のPi 4で試す |
| 元に戻せない | trigger名の間違い | `cat /sys/class/leds/ACT/trigger` で利用可能なトリガー一覧を確認 |

### 参考: 利用可能なトリガー一覧

```bash
# 利用可能なトリガーモード一覧を表示
cat /sys/class/leds/ACT/trigger

# 主なトリガーモード:
# - none: 手動制御
# - mmc0: SDカードアクセス連動（デフォルト）
# - heartbeat: システム稼働を示すハートビート点滅
# - timer: 周期的な点滅（on/off時間を指定可能）
```

### 補足: Phase 3でのUniPi 1.1リレーテスト

**注**: 殿のご指示により、**UniPi 1.1のリレーテストは明日以降に延期**となりました。

Phase 3では、UniPi 1.1を接続後、以下のテストを実施予定です：
- UniPi 1.1のリレー制御（Home Assistantからのオン/オフ）
- I2Cセンサー読み取り（MCP9808温度センサー等）
- LCD表示制御（LCD1602）

---

## トラブルシューティング

### 問題1: SDカードから起動しない

**症状**: 赤色LEDのみ点灯、緑色LEDが全く点滅しない、画面が真っ黒

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| イメージの書き込み失敗 | SDカードを再度書き込み |
| 不良SDカード | 別のSDカード（高品質メーカー品）を試す |
| 電源不足 | 公式電源アダプタ（5V/3A）を使用 |
| 破損したイメージファイル | イメージを再ダウンロードして書き込み直し |

### 問題2: `homeassistant.local` にアクセスできない

**症状**: ブラウザで `homeassistant.local:8123` を開いても接続できない

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| mDNS未対応 | IPアドレスで直接アクセス（例: `http://192.168.1.100:8123`） |
| 起動未完了 | 15〜20分待機してから再アクセス |
| LANケーブル未接続 | 物理的な接続を確認 |
| ファイアウォール | ポート8123を開放、またはファイアウォールを一時的に無効化 |

**mDNS確認方法（Ubuntu/macOS）**:

```bash
# Raspberry PiがmDNSで応答しているか確認
ping homeassistant.local

# 応答があればOK、タイムアウトならIPアドレスで直接アクセス
```

**IPアドレス確認方法**:

```bash
# ネットワーク内のデバイスをスキャン（nmap使用）
nmap -sn 192.168.1.0/24

# または、ルーターの管理画面でDHCPリースを確認
```

### 問題3: 起動途中でフリーズする

**症状**: 緑LEDが点滅後、突然停止する、または無反応になる

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| 電源不足（USB機器が多い） | USBデバイスを全て外す、電源アダプタを高品質なものに交換 |
| SDカードの書き込み速度不足 | Class 10以上のSDカードを使用 |
| 過熱 | ヒートシンクまたは冷却ファンを追加 |
| メモリ不足 | Raspberry Pi 4 2GB → 4GB/8GBモデルに変更 |

### 問題4: Home Assistantダッシュボードが表示されない

**症状**: ブラウザでアクセスできるが、「Preparing Home Assistant」から進まない

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| 初期セットアップ未完了 | さらに10〜15分待機（特に初回は時間がかかる） |
| ネットワーク接続不良 | LANケーブルの物理的な接続を確認、DHCPが有効か確認 |
| SDカード容量不足 | 32GB以上のSDカードを使用 |

### 問題5: アドオンのインストールが失敗する

**症状**: Phase 2でアドオンをインストールしようとするとエラーが出る

**原因と対処法**:

| 原因 | 対処法 |
|------|--------|
| インターネット接続不良 | LANケーブル、ルーター、ISP接続を確認 |
| ストレージ容量不足 | `設定 > システム > ストレージ` で空き容量確認、不要なファイルを削除 |
| DNS設定の問題 | `設定 > システム > ネットワーク` でDNSサーバーを手動設定（例: 8.8.8.8） |

### 緊急時の完全リセット

上記の対処法で解決しない場合、SDカードを再度書き込み直してクリーンインストールを試す。

## 参考資料

### 公式ドキュメント

- [Home Assistant - Raspberry Pi Installation](https://www.home-assistant.io/installation/raspberrypi/)
- [Home Assistant - General Troubleshooting](https://www.home-assistant.io/docs/troubleshooting_general/)
- [Home Assistant OS Releases](https://github.com/home-assistant/operating-system/releases)

### コミュニティ

- [Home Assistant Community Forum](https://community.home-assistant.io/)
- [HAOS on Raspberry Pi4 not booting - Community Discussion](https://community.home-assistant.io/t/haos-on-raspberry-pi4-not-booting/975383)

### 関連ガイド

- [Installing Home Assistant on Raspberry Pi 4 & 5 – Complete Guide](https://openelab.io/blogs/getting-started/installing-home-assistant-raspberry-pi)
- [Setting up Home Assistant OS on the Raspberry Pi - Pi My Life Up](https://pimylifeup.com/home-assistant-raspberry-pi/)

---

## 次のステップ

Phase 1が完了したら、Phase 2（基本設定・アドオンインストール）に進みます。

**Phase 2で実施すること**:
- File Editor アドオンのインストール
- SSH & Web Terminal のインストール
- MQTT Broker（Mosquitto）のインストール
- バックアップ設定

**Phase 3で実施すること**:
- UniPi 1.1 の物理接続
- UniPi統合のセットアップ
- センサー・アクチュエーターの設定
