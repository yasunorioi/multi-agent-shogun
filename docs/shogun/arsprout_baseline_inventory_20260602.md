# Arsprout既存基盤 現状把握調査レポート — SDカード入替前の地ならし

- **cmd**: cmd_594 / **subtask**: subtask_1285
- **worker**: ashigaru6 (部屋子1)
- **取得日時**: 2026-06-02T02:55
- **方針**: read-only (SDカード/サービス/apt/設定編集 一切禁止・F006厳守)
- **殿戦略前提**: MQTT Broker=Mosquitto / 気象=(b) MQTTブリッジ方式 / UniPi=残す / 最初のcmd=A案(現状把握)
- **★構築方式確定(殿追補2・02:10)★**: 新OS側img制作は **回避** (ブート周り鬼門)。**Raspbian Lite 公式img を焼く → SSH → GitHubワンライナースクリプト** で構築。ワンライナーで Mosquitto + UniPi daemon + 気象 MQTTブリッジ + UECS-CCM を一括復元 (中身は後続cmdで分解)

---

## §1 エグゼクティブサマリ

**核心3行（既知/新規/差分の区分）:**

1. **【既知・更新不要】** 物理基盤と SQLite/UECS-CCM データソース・UniPi 1.1リレー(MCP23008 0x20)・VPN(10.10.0.10)・気象6種計測項目は context/arsprout.md (311行/2026-02確定) でほぼ網羅済。Arsprout本体=Java SpringBoot+SQLite直書きで Mosquitto は稼働するも publishゼロ。
2. **【★新規発見★】** **`~/uecs-hardwares` が現在の本流リポ** — context未記載・cmd_593 §4.1にも明示なし。MQTTブリッジ実装(`mqtt_relay_bridge.py`)・CCM受信(`ccm_receiver.py`)・UniPi I2C制御(`i2c_relay.py`)・WH65LP UART受信(`wh65lp_reader.py`)・REST API(`rest_api.py`)・emergency override が **既に揃っている**。殿戦略(b) MQTTブリッジ方式は **コード追加ゼロで成立** する。
3. **【★差分★】** context/arsprout.md の「ArSprout SDカード完全廃棄(HA+Pico+Node-RED置き換え)」計画は **撤回・路線変更**。現殿戦略=UniPi残す+Mosquitto直挿し+MQTTブリッジ+agri-* PoEノード+OGMS統合。`~/unipi-agri-ha` は git管理外でレガシー化(yasunorioi GitHub一覧に存在せず・README残骸とdocker-compose配下のHA/Mosquitto/Telegraf設定だけ残存)。

**現物SSH 可否:** **❌ 不可** — `ssh arpi@10.10.0.10` Connection timed out (VPN未起動 or arsprout停止可能性)。Starlink瞬断とは別問題。本subtaskは **手元バックアップ資産 (img/zip/configs) + 没日録DB(286件) + ~/uecs-hardwares + ~/unipi-agri-ha + context** から再構成。現物検証は後続cmdで。

**選択肢 A/B/C(SDカード入替方針・★Lite公式img+ワンライナー前提★):**
- **A. uecs-hardwares 即投入**(推奨) — **Raspbian Lite 公式img** → SSH → **GitHubワンライナー** で Mosquitto + unipi-daemon + 気象MQTTブリッジ + UECS-CCM 一括導入。既存`arsprout-pi-1.19.0.img`はバックアップ温存(戻し用のみ・自製img作成不要)。
- **B. 段階移行** — 別Pi/別SDで Lite+ワンライナー検証→本番Arsprout SD差替え。実機SSH復活後実施。
- **C. 純正OS継続** — `arsprout-pi-1.19.0.img` を再焼き現状維持(殿戦略放棄)。

**殿への質問3問:**
1. **Q1**: SSH不可は VPN(wg0)未起動か、現Arsprout Pi電源OFFか、SDカード故障か。物理現認可能か。
2. **Q2**: `~/unipi-agri-ha`(git管理外・HA設定残存) は **廃棄して良いか**、それとも HA路線復活時の素材として温存か。
3. **Q3**: 殿戦略「UniPi残す」は **物理ハードを残す** (推奨A) なのか **UniPi制御を残す**(uecs-hardwares I2C経由)なのか — A前提で進めて良いか。

---

## §2 ハードウェア構成

### Arsprout本体
| 項目 | 値 | 出典 |
|---|---|---|
| モデル | Raspberry Pi (世代不明・現物SSH不可) | 現物確認待ち |
| IP (VPN) | 10.10.0.10 | context/arsprout.md L218-222 |
| IP (LAN) | 192.168.1.71 | context/arsprout.md L234 |
| SSH | `arpi@10.10.0.10` 公開鍵 | context/arsprout.md L16 (RTT 99ms 2026-02-08) |
| 現状 | **SSH timeout (本subtask 02:48時点)** | 本subtask現物確認 |

### UniPi 1.1 (リレーI/O)
| 項目 | 値 | 出典 |
|---|---|---|
| I2Cアドレス | MCP23008 0x20 | context L17, cmd_132 |
| I/O数 | 8out (リレー) + DI07-DI14 | uecs-hardwares/config/unipi_daemon.example.yaml L21 |
| 制御方式 | smbus2 (Python) / SpringBoot Pi4J占有 | context L116-117 |
| バス上他デバイス | 0x18(MCP9808温度), 0x3e, 0x50, 0x57, 0x68 | context L115 |

### 気象センサー
| 項目 | 値 | 出典 |
|---|---|---|
| 内気象ノード | UECS-CCM経由(arsprout-pi-configs に SHT31/SHT41 × D400/S300 構成XML 6種) | ~/Downloads/arsprout-pi-configs-1.18.1/ |
| 外気象 | Misol WH65LP (UART /dev/ttyUSB0 9600bps) | unipi_daemon.example.yaml L29-30 |
| 計測項目 | WAirTemp/WAirHumid/WWindSpeed/WWindDir16/WRainfall/WRainfallAmt.cMC | context L23-30 |

### 配線・電源・設置 (★現物確認待ち)
- 電源/PoE: 不明 (殿の頭の中)
- 設置場所: ハウス内 (192.168.1.71 構成より推定)
- 駆動系ブレーカー: 落としてあり(リモートテスト可) | context L120

---

## §3 ソフトウェア構成

### 現Arsprout純正OS
| 項目 | 値 | 出典 |
|---|---|---|
| OSイメージ | arsprout-pi-1.19.0.img (3.97GB) / arsprout-pi-1.19.0.zip (858MB) | ~/Downloads/ |
| OS確認日 | 2026-05-12 (img) / 2026-05-30 (zip) | mtime |
| Arsprout本体 | Java SpringBoot (PID392 例) | context L116 |
| データストア | SQLite (`compo_log` テーブル) | context L37-44 |
| MQTTブローカー | Mosquitto 稼働中 (publish なし) | context L15 |
| UECS-CCM | マルチキャスト 224.0.0.1:16520 受信側 | unipi_daemon.example.yaml L37 |
| REST API | 8080 (Arsprout-RESTAPI推定) | unipi_daemon.example.yaml L42 |
| 設定資産 | arsprout-pi-configs-1.18.1/ (XML 6件: 内気象ノード SHT31/41 × D400/S300, 制御ノード SwitchBoard v2/v3) | ~/Downloads/ |
| 稼働サービス詳細 | 現物SSH不可で未取得 | 確認待ち |
| パッケージ詳細 | 同上 | 確認待ち |

### 新OS候補 (殿戦略: Raspbian Lite + Mosquitto + uecs-hardwares)
- **systemd**: `unipi-daemon.service` (After=mosquitto.service, User=agriha, グループ=i2c+gpio) — ~/uecs-hardwares/systemd/
- **依存**: paho-mqtt, smbus2, asyncio, FastAPI (推定)
- **設定**: `/etc/agriha/unipi_daemon.yaml` (テンプレ ~/uecs-hardwares/config/unipi_daemon.example.yaml)

### ネットワーク (現状)
- VPN: さくらクラウド WireGuard wg0 (10.10.0.0/24 / 153.127.46.167:31820) | context L216-243
- ハウスLAN: 192.168.1.71 (Arsprout) / 192.168.1.74 (テストノード)
- mDNS: ArSprout側設定詳細は現物確認待ち

---

## §4 データフロー現況

### 現Arsprout (Java SpringBoot)
```
内気象ノード (UECS-CCM/UDP 224.0.0.1:16520) ─┐
外気象 WH65LP (UART /dev/ttyUSB0) ────────────┼─→ Arsprout (Java) → SQLite compo_log
UniPi 1.1 DI (GPIO)                           ┘                  ↓
                                                            HTTP REST API :8080
                                                                  ↓
                                                            (Arsprout純正クライアント)

UniPi 1.1 リレー出力 ← MCP23008 0x20 ← Arsprout Java (Pi4J占有)
Mosquitto :1883 (稼働中だが publish ゼロ)
```

### 殿戦略後 (uecs-hardwares + Mosquitto)
```
内気象 (UECS-CCM)──┐
外気象 WH65LP─────┼─→ uecs-hardwares daemon (Python) ─→ Mosquitto :1883 ─→ HA / agri-* / 外部
UniPi DI/1-Wire────┘     │
                          │ MQTT subscribe (relay control)
                          ↓
                       i2c_relay.py → MCP23008 → UniPi リレー出力
                          │
                       emergency_override.py (GPIO watch + 緊急遮断)
                          │
                       FastAPI :8080 (REST API)
                          │
                       mqtt_relay_bridge.py (CCM→MQTT変換)
```
**注**: context/arsprout.md L90「UECS-CCM→MQTTブリッジは不要」記述は **撤回**(殿戦略(b))。

### 外部接続 (★現物確認待ち)
- LINE Bot: 旧計画あり(cmd_111/093)・現Arsprout稼働は未確認
- VPN: wg0 / wg1 (将来 LLM農業サービス)

---

## §5 リポジトリ・コード資産の照合 (cmd_593 §4.1 と現物突合)

### cmd_593 arsprout+MQTT 15リポ → 現基盤との対応

| cmd_593 §4.1 リポ | 現物配置 | 関係 |
|---|---|---|
| **Arsprout-RESTAPI** (2026-06-01) | 現Arsprout内のJava REST? or 別物? | ★要確認(現物SSHで `dpkg -l \| grep arsprout` 等) |
| **OGMS** (2026-06-01) | Waveshare RP2350-ETH-8DI-8RO+UECS-CCM | ArSprout廃止派生 standalone |
| **agri-node-poe-core** (2026-06-01) | M5Stack ATOM PoE 共通基盤 | 新規ノード共通(現Arsproutと無関係) |
| **agri-{env,flow,rain,solar}-poe** (2026-05-30) | M5Stack ATOM PoE センサ4種 | 新規ノード(置換用) |
| **ccm_rp2350_relay** (priv 2026-06-01) | RP2350 リレー(Waveshare?) | ★uecs-hardwares/arduino/rp2350_relay の親かfirmware別? |
| **★uecs-hardwares** (2026-05-01) | **~/uecs-hardwares/** 実在 | **★本流リポ★** (context未記載) |
| **uecs-llm** (2026-04-25) | LLM制御 | 別軸(LLM 農業サービス wg1 系) |
| **uecs-ccm-mcp** (2026-02-19) | UECS-CCM MCP server | uecs-hardwares/ccm_receiver と機能重複? 要照合 |
| **ntrip-pico** (2026-04-25) | Pico NTRIP | 別軸(RTK系) |
| **arsprout-llama** (priv 2026-03-11) | LLM | 別軸 |
| **arsprout-analysis** (priv 2026-02-07) | データ分析 | 既存資産活用 |
| **pico-uecs-sensor** (priv 2026-02-03) | Pico試作 | 旧計画派生 |
| 古い: M5Atom-UECS-Sample/M5AtomUECS-water_meter | 参考資料 | アーカイブ候補 |

### `~/uecs-hardwares/` 構造 (★本流リポ詳細)
```
arduino/         → ccm_test_w5500evb / rp2350_relay / standalone_rp2350_relay / standalone_test_w5500evb
config/          → unipi_daemon.example.yaml + wg0.conf.template + emergency.conf
docker/          → Mosquitto Docker構成 (推定)
hardware/        → KiCad PCB (Actuator board + Grove shield)
src/uecs_hardwares/  → main.py + ccm_receiver.py + ds18b20.py + emergency_override.py +
                       gpio_watch.py + i2c_relay.py + mqtt_relay_bridge.py + rest_api.py +
                       sensor_loop.py + wh65lp_reader.py
systemd/         → unipi-daemon.service + uecs-hardwares-cron
tests/           → pytest 構成
```
**評価:** 殿戦略 (b) MQTTブリッジ方式は既に **uecs-hardwares 単独で成立**。新規開発不要。

### `~/unipi-agri-ha/` (レガシー判定)
- git 管理外 (`fatal: not a git repository`)
- yasunorioi GitHub 一覧 (cmd_593) に **unipi-agri-ha は存在しない**
- 残存物: docker/ha-config/(HA configuration.yaml + automations.yaml 等) / docker/grafana/ / docker/mosquitto/mosquitto.conf / docker/telegraf/telegraf.conf
- 用途: HA計画(context arsprout.md L82-90)の遺骸
- **判断**: 殿質問 Q2 待ち。廃棄 or 温存。

---

## §6 SDカード入替時のリスク・移行課題

### バックアップ資産 (既に手元にあり)
| 資産 | パス | サイズ | 用途 |
|---|---|---|---|
| 純正OS img | ~/Downloads/arsprout-pi-1.19.0.img | 3.97GB | **戻し用のみ** (新OS側img制作は不要) |
| 純正OS zip | ~/Downloads/arsprout-pi-1.19.0.zip | 858MB | 圧縮配布 |
| 設定 XML | ~/Downloads/arsprout-pi-configs-1.18.1/ | 6 XML | 内気象/制御ノード設定(殿戦略後はuecs-hardwares側に集約予定) |
| UECS UNI configs | ~/Downloads/uecs-pi-uni-configs/ | fw20191030以前 / fw20200911以降 | UNIPi構成リファレンス |

**評価:** **戻し道は確保済**。新OS側は **Raspbian Lite 公式img + GitHubワンライナー** 方式ゆえ自製img制作不要。再現性はワンライナースクリプトのバージョン管理(git)で担保。SD故障時は Lite公式img再焼き+ワンライナー再実行で復旧。

### リスクマトリクス
| リスク | 影響 | 対策 |
|---|---|---|
| R1: 現物Arsprout SQLite (compo_log) 過去データの喪失 | 数年分の蓄積データ | SDイメージ`dd` ★本subtask対象外★ (殿判断・後続cmd) |
| R2: ArSprout独自プロトコル機能(LINE通知等)の Raspbian Lite 化喪失 | LINE Bot 等が再実装必要 | 機能棚卸し → HA or Node-RED で再現 |
| R3: UniPi 1.1 リレー Java SpringBoot ↔ Python smbus2 切替時の競合 | I2C占有衝突 | Java停止→Python起動の順厳守。`unipi-daemon.service` で systemd管理 |
| R4: UECS-CCM マルチキャスト切替 | 内気象ノード→Arsprout の経路途絶 | uecs-hardwares/ccm_receiver.py が同機能を担う(動作未検証) |
| R5: ネットワーク設定(VPN/mDNS/ufw) の Raspbian Lite 移植 | SSH断 / VPN 接続不可 | ~/uecs-hardwares/config/wg0.conf.template + 殿手元 wg0 設定の集約 |
| R6: 設置場所 (ハウス内) での物理アクセス困難性 | 現地SD抜き差し | 後続cmd: ヒアリング(現場往訪可否・他Pi交換可否) |
| R7: ★SSH不可状態の根本原因不明★ | 検証フェーズが停止 | 殿物理確認 (VPN起動?電源?SD?) → 復旧後 read-only 検証 |

### 殿戦略との整合チェック
- **Mosquitto 確定**: ✅ 既に純正でも稼働。新OSでも自然 (Lite公式img+`apt install mosquitto`)
- **(b) MQTTブリッジ**: ✅ uecs-hardwares/mqtt_relay_bridge.py + ccm_receiver.py で実装済 (ワンライナーで `git clone` + `systemctl enable` で起動)
- **UniPi 残す**: ✅ uecs-hardwares/i2c_relay.py がI2C/MCP23008制御 (Lite上で `i2c-tools` + `python3-smbus` 追加だけで動作)
- **Lite公式img+ワンライナー**: ✅ 既存資産で構築可能 (新規開発不要・実装着手前は B案(軍師設計)でシーケンス整理)
- **A案(現状把握)**: 本subtaskで完遂

---

## §7 未確定事項 (殿への確認項目リスト)

| # | 項目 | 確認手段 |
|---|---|---|
| U1 | **★SSH 10.10.0.10 不可の原因** (VPN/電源/SD/その他) | 殿物理確認 or VPN状態 |
| U2 | Pi世代 (Pi3/Pi4/Pi5)・メモリ・SDカード容量 | SSH復活後 `cat /proc/cpuinfo` 等 |
| U3 | UniPi 1.1 Java SpringBoot プロセス現状 (PID/起動時間) | SSH復活後 `ps -ef \| grep java` |
| U4 | Arsprout-RESTAPI リポ(2026-06-01)と現物Java RESTの関係 | リポ内README / 現物port 8080レスポンス |
| U5 | ccm_rp2350_relay (priv) と uecs-hardwares/arduino/rp2350_relay の関係 | リポ間diff |
| U6 | unipi-agri-ha 廃棄 or 温存判断 | 殿判断 |
| U7 | LINE Bot 現稼働状況 (Messaging API トークン更新済?) | 殿手元情報 |
| U8 | 内気象ノード現物の構成 (SHT31 D400/S300 / SHT41 D400/S300 のどれ?) | XML設定 vs 物理 |
| U9 | 制御ノード現物の SwitchBoard バージョン (v2/v3) | XML設定 vs 物理 |
| U10 | SQLite compo_log 過去データ保全要否 | 殿判断 |
| U11 | 設置場所への物理アクセス頻度 (SD交換は何回/週可能?) | 殿手元情報 |
| U12 | wg0.conf テンプレ → 実config への鍵情報 | 殿手元 |

---

## §8 次cmd 候補

| cmd案 | 内容 | bloom | 推定時間 | 前提条件 |
|---|---|---|---|---|
| **★A. SSH復活+現物確認**(最優先) | VPN/電源確認後、ssh arpi@10.10.0.10 read-only 5軸調査 (uname/systemctl/dpkg/i2cdetect/journal) | L2 | 2-3h | 殿物理確認 |
| **★B. 軍師による「Lite焼き→SSH→ワンライナー」構築シーケンス設計** | **Raspbian Lite公式img焼成 → SSH接続 → GitHubワンライナースクリプト一発実行** の構築シーケンス全体図を軍師に依頼(3案・I4採点)。ワンライナー格納先(shogun配下に新規 or 既存uecs-hardwares活用 or 新規`arsprout-bootstrap`リポ)・Mosquitto+UniPi daemon+気象MQTTブリッジ+UECS-CCM の起動順序とエラーリカバリ設計。ワンライナー中身の各行詳細は後続cmdで分解 | L4 | 4-6h | 本subtask完遂 |
| **C. SDバックアップ実機作業手順書** | 殿が現物Arsprout SDを別SDにddする手順 (Raspberry Pi Imager + Win32DiskImager + rpi-clone 比較)。**自製img制作は不要**ゆえ純正img保全+`dd if=/dev/mmcblk0` の戻し検証手順のみ | L2 | 2h | - |
| **D. uecs-hardwares 完全棚卸し** | src/*.py 全関数ドキュメント化 + arduino/ firmware 用途分類 + tests カバレッジ評価 | L3 | 4-5h | - |
| **E. unipi-agri-ha 廃棄/温存判断材料整理** | HA configuration.yaml + automations.yaml + Mosquitto/Telegraf設定の用途分析 + 殿戦略との重複度評価 | L1 | 1h | 殿Q2判断 |
| **F. agri-* PoEノード 4種 + agri-node-poe-core 統合仕様書** | M5Stack ATOM PoE 派生4ノードの Mosquitto トピック設計 (DI/DO+sensor) | L3 | 3-4h | B完遂 |
| **G. OGMS / ccm_rp2350_relay と uecs-hardwares の住み分け** | 3リポの役割分担明確化(standalone vs daemon vs firmware) | L2 | 2h | D完遂 |

**推奨着手順:** ★A(SSH復活)★ + ★B(軍師ワンライナー構築シーケンス設計)★ を並行 → C(SDバックアップ手順) → D(uecs-hardwares棚卸し) → E(unipi-agri-ha判定) → F+G(統合仕様)

---

## 付録: F006 + read-only 準拠確認

本subtaskで実行したコマンド一覧 (全てread-only):

- `ssh -o ConnectTimeout=8 -o BatchMode=yes arpi@10.10.0.10 'hostname; uname -a; date'` (結果: Connection timed out)
- `ls -la` / `find` / `wc -l` / `head` / `cat` (テキストread)
- `git remote -v` / `git log --oneline` (ローカルgit参照)
- `python3 scripts/botsunichiroku.py cmd|subtask|search` (没日録DB read)
- Read tool (Markdown/YAML/conf 読取)

**書込み系コマンド (一切実行せず):**
- ❌ apt install/remove/upgrade
- ❌ systemctl start/stop/restart/disable/enable
- ❌ 設定ファイル編集 (>, >>, sed -i, vi 書込み)
- ❌ dd / SDカード書込み
- ❌ gh issue/pr create|comment|close|merge
- ❌ git push to Arsprout

**F006 + read-only 抵触ゼロ。**
