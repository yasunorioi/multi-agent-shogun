# GitHub全リポジトリ俯瞰調査レポート — arsprout+MQTT 再開前の地ならし

- **cmd**: cmd_593 / **subtask**: subtask_1284
- **worker**: ashigaru6 (部屋子1)
- **取得日時**: 2026-06-02T01:25Z
- **対象アカウント**: yasunorioi
- **方針**: read-only (gh CLI 取得系のみ・F006厳守・書込み系コマンド一切なし)

---

## §1 エグゼクティブサマリ

**全43リポ走査結果の核心3行:**

1. **Open Issue/PR は外部1件のみ。自リポ32件 + fork11件は全てゼロ** — Issue/PR 起因の地ならし作業は不要。唯一の宿題は GLAY-AK2/NTRIP-client-for-Arduino #5 (2026-04-14 提出後 1.5ヶ月放置、上流レビュー待ち) のみ。
2. **直近1ヶ月で arsprout+MQTT 戦線が爆発的に立ち上がり中** — agri-* 4ノード (env/flow/rain/solar) + 共通ベース agri-node-poe-core + サーバ側 (OGMS / Arsprout-RESTAPI / ccm_rp2350_relay) が 2026-05-30〜06-01 にかけて連続push。地ならしより本攻めの段階に近い。
3. **並行戦線が複数走行中**: arsprout+MQTT 系 (15リポ) / rotation-planner 系 (3リポ) / multi-agent-shogun 系 (4リポ) / 古いM5Atom系小物 (10件以上) — 再開時は「全戦線並行」か「arsprout+MQTT 集中」かの戦略判断が必要。

**arsprout+MQTT 再開時の論点(3点):**

- **A. 共通ベースの分岐管理**: agri-node-poe-core を派生4ノード (env/flow/rain/solar) にどう同期するか。git submodule / monorepo / 手動コピーのいずれか。
- **B. サーバ側スタック整理**: Arsprout-RESTAPI / uecs-ccm-mcp / OGMS / ccm_rp2350_relay の役割分担と統合パス。
- **C. LLM制御の位置づけ**: uecs-llm (2026-04-25) が本戦線に合流するか、別軸として進めるか。

**殿への質問3問:**

1. **Q1: 再開時の「最初の1リポ」を decide すべきか？** — アクティブ15リポは多すぎる。優先順位 (PoEノード共通基盤 → センサ4種 → サーバ統合) で良いか。
2. **Q2: GLAY-AK2/NTRIP-client-for-Arduino PR #5 は fork main 直使い (plan B) に切り替えるか？** — 上流マージ待ちで戦線が止まるなら、yasunorioi fork main を本番採用すべき。
3. **Q3: rotation-planner-v2 移行は arsprout+MQTT と並行 or 直列か？** — v1→v2 完了を先に閉じてから arsprout 集中、が見通し良いが、殿の判断を仰ぐ。

---

## §2 リポジトリ一覧 (全43件・最終push降順)

| Pushed | Vis | Name | Type | Lang | Description |
|---|---|---|---|---|---|
| 2026-06-01 | PRIVATE | ccm_rp2350_relay | own | C++ | (no desc) |
| 2026-06-01 | PUBLIC | Arsprout-RESTAPI | own | - | (no desc) |
| 2026-06-01 | PUBLIC | agri-node-poe-core | own | C++ | Shared base for M5Stack ATOM PoE sensor / relay nodes (network + NVS + HTTP UI + MQTT + CCM + mDNS/OTA + LED) |
| 2026-06-01 | PUBLIC | OGMS | own | C++ | Standalone greenhouse relay controller. Waveshare RP2350-ETH-8DI-8RO + UECS-CCM |
| 2026-05-30 | PUBLIC | agri-solar-poe | own | C++ | Pyranometer (M5 ADC Unit V1.1 / ADS1110 + PVSS-03) → MQTT + UECS-CCM InRadiation |
| 2026-05-30 | PUBLIC | agri-flow-poe | own | C | DIGITEN flow meter on M5Stack ATOM PoE → MQTT + UECS-CCM |
| 2026-05-30 | PUBLIC | agri-env-poe | own | C | UECS-CCM/MQTT env sensor (SHT30 + QMP6988 + SCD41) |
| 2026-05-30 | PUBLIC | agri-rain-poe | own | C | M5Stack ATOM PoE rainfall sensor (SEN0575) → MQTT + UECS-CCM |
| 2026-05-23 | PUBLIC | rotation-planner-v2 | own | Python | 輪作計画アプリ v2 — HTMX + FastAPI + Jinja2 で再設計 |
| 2026-05-18 | PUBLIC | ntripcaster | fork | Zig | NTRIP v1 caster (Zig) FKP virtual mountpoint engine, RTCM3/MSM7 |
| 2026-05-18 | PRIVATE | multi-agent-shogun-private | own | Python | (no desc) |
| 2026-05-18 | PUBLIC | rotation-planner | own | Python | (no desc) |
| 2026-05-15 | PUBLIC | NTRIP-client-for-Arduino | fork | C++ | (parent: GLAY-AK2/NTRIP-client-for-Arduino) |
| 2026-05-01 | PUBLIC | uecs-hardwares | own | Python | (no desc) |
| 2026-04-25 | PUBLIC | uecs-llm | own | Python | LLM-based greenhouse environment control with UECS-CCM integration |
| 2026-04-25 | PUBLIC | ntrip-pico | own | C++ | (no desc) |
| 2026-04-23 | PUBLIC | multi-agent-shogun | fork | Python | multi-agent-shogun + 大奥 — Claude Code + tmux マルチエージェント並列開発基盤 |
| 2026-04-01 | PUBLIC | codedb | fork | Zig | Zig code intelligence server and MCP toolset (parent: justrach/codedb) |
| 2026-03-30 | PRIVATE | systrade | own | Python | (no desc) |
| 2026-03-27 | PUBLIC | RotationPlanner-iOS | own | Swift | (no desc) |
| 2026-03-14 | PUBLIC | BF-018A | fork | C++ | JJY Simulator for M5Atom (parent: botanicfields/BF-018A) |
| 2026-03-12 | PUBLIC | claude-skills | own (ARCH) | - | Claude Code skill templates for IoT, agriculture, DevOps |
| 2026-03-12 | PUBLIC | shogun-plugins | own | - | (no desc) |
| 2026-03-11 | PRIVATE | arsprout-llama | own | Jupyter | (no desc) |
| 2026-02-25 | PUBLIC | Hokuren-RTKClient_for-M5Atom | own | C++ | (no desc) |
| 2026-02-19 | PUBLIC | uecs-ccm-mcp | own | Python | (no desc) |
| 2026-02-07 | PRIVATE | arsprout-analysis | own | Python | (no desc) |
| 2026-02-03 | PRIVATE | pico-uecs-sensor | own | Python | (no desc) |
| 2025-09-16 | PUBLIC | uardecs-w55rp20-envsensor | fork | C++ | (parent: shinrinakamura/...) |
| 2025-06-14 | PUBLIC | M5AtomUECS-water_meter | own | C++ | (no desc) |
| 2024-09-06 | PUBLIC | M5Atom-UECS-Sample | own | C++ | (no desc) |
| 2024-09-04 | PUBLIC | M5Unit-ENV_UECS | fork | C++ | M5Stack-UNIT ENV series — SHT30 + QMP6988 |
| 2024-08-11 | PUBLIC | NTRIP-server-for-Arduino | fork (ARCH) | C++ | (parent: GLAY-AK2/...) |
| 2024-07-08 | PUBLIC | ESP32-DCF77_M5Atom | fork | C++ | Hacking the ESP32 (parent: aknik/ESP32) |
| 2024-04-02 | PUBLIC | Unit_ENVIV_M5Atom_mDNS_AsyncWebserver | own | C++ | (no desc) |
| 2023-12-15 | PUBLIC | M5Atom_AcFreqLog | own | C++ | (no desc) |
| 2023-12-15 | PUBLIC | M5AtomU_ds18b20_influxdb | own | C++ | (no desc) |
| 2023-12-15 | PUBLIC | M5Stack_PowerMonitor | fork | C++ | (parent: AmbientDataInc/...) |
| 2023-12-14 | PUBLIC | M5Stick-C_Co2_Speaker | own | C++ | (no desc) |
| 2023-05-22 | PUBLIC | M5Stack_NMEA-fix_off_buzzer | own | C++ | (no desc) |
| 2022-01-29 | PUBLIC | Ambient_ESP8266_lib | fork | C++ | Ambient lib fork |
| 2020-11-12 | PRIVATE | YUN_influxDB-UDP | own | C++ | (no desc) |
| 2020-10-25 | PRIVATE | pptp-ntrip | own | Shell | pptp ntrip server on Raspberry Pi |

**集計:**
- 総数: 43 / own: 32 / fork: 11
- visibility: PUBLIC 35 / PRIVATE 8
- archived: 2 (claude-skills / NTRIP-server-for-Arduino)
- 直近30日 push (≥2026-05-02): **14リポ** (全て arsprout+MQTT 系か agri-* 系か rotation-planner 系)
- 直近90日 push (≥2026-03-04): **23リポ**

---

## §3 Pinned / 主要PJ

殿がプロフィールにpinした5リポ:

| Pinned | Name | Push | Stars | Note |
|---|---|---|---|---|
| 1 | rotation-planner | 2026-05-18 | 0 | 輪作計画アプリ v1 (Python) |
| 2 | M5Atom-UECS-Sample | 2024-09-06 | 0 | M5Atom UECS サンプル (古いがPinned継続) |
| 3 | NTRIP-client-for-Arduino | 2026-05-15 | 2 | GLAY-AK2 fork — RTK/NTRIP系の主力 |
| 4 | Hokuren-RTKClient_for-M5Atom | 2026-02-25 | 0 | 北連RTKクライアント |
| 5 | multi-agent-shogun | 2026-04-23 | 0 | 本基盤 (yohey-w fork) |

**Pinnedからの読み:** 殿の対外的な主力PJは「rotation-planner系 + RTK/NTRIP系 + multi-agent-shogun」。**arsprout+MQTT の agri-* 4ノードは未Pinned** だが直近push活発のため、再開後はPin更新の検討余地あり。

---

## §4 Recently updated (分類別)

### §4.1 arsprout+MQTT 関連 (15リポ)

**サーバ/CCM/REST系 (2026-06-01集中push):**
- **Arsprout-RESTAPI** (06-01) — REST API
- **OGMS** (06-01) — Standalone 温室リレー (Waveshare RP2350-ETH-8DI-8RO + UECS-CCM)
- **ccm_rp2350_relay** (06-01 private) — RP2350 リレー (C++)
- **uecs-ccm-mcp** (02-19) — UECS-CCM の MCP server

**ノード共通基盤:**
- **agri-node-poe-core** (06-01) — M5Stack ATOM PoE 共通ベース (network + NVS + HTTP UI + MQTT + CCM + mDNS/OTA + LED)

**センサノード4種 (2026-05-30〜31 同時push — 派生4兄弟):**
- agri-env-poe — SHT30 + QMP6988 + SCD41 環境センサ
- agri-flow-poe — DIGITEN 流量計
- agri-rain-poe — SEN0575 雨量センサ
- agri-solar-poe — ADS1110 + PVSS-03 日射計 (InRadiation)

**LLM/解析/データ系 (private):**
- uecs-llm (04-25) — LLM-based 環境制御
- arsprout-llama (03-11 private) — Jupyter
- arsprout-analysis (02-07 private) — Python 分析

**過去センサ/HW (古いが系列内):**
- uecs-hardwares (05-01) — HW定義?
- pico-uecs-sensor (02-03 private)
- M5AtomUECS-water_meter (2025-06)
- M5Atom-UECS-Sample (2024-09 Pinned)

### §4.2 NTRIP / RTK / PoE 関連の小物 (5リポ)

- **NTRIP-client-for-Arduino** (05-15 fork Pinned) — **★PR #5 上流レビュー待ち** (後述§5)
- **ntripcaster** (05-18 fork) — Zig製 NTRIP v1 caster
- **Hokuren-RTKClient_for-M5Atom** (02-25 Pinned)
- **ntrip-pico** (04-25) — Pico用 NTRIP
- **uardecs-w55rp20-envsensor** (2025-09 fork) — W5500RP20 環境センサ

### §4.3 rotation-planner 系 (3リポ・並行戦線)

- **rotation-planner** (05-18 Pinned) — v1 Python
- **rotation-planner-v2** (05-23) — v2 HTMX + FastAPI + Jinja2 再設計
- **RotationPlanner-iOS** (03-27) — Swift クライアント

### §4.4 multi-agent-shogun 系 (4リポ)

- **multi-agent-shogun** (04-23 fork Pinned) — 大奥 / yohey-w fork
- **multi-agent-shogun-private** (05-18 private) — 私的派生
- **shogun-plugins** (03-12)
- **claude-skills** (03-12 ARCHIVED) — スキル雛形 (アーカイブ済)

### §4.5 その他 (古いM5Atom系・ツール類)

- **codedb** (04-01 fork) — Zig コード検索 MCP (justrach fork)
- **systrade** (03-30 private) — 株式取引?
- **BF-018A** (03-14 fork) — JJY Simulator (botanicfields fork)
- 2024年以前push の小物 (M5Atom_AcFreqLog / M5Stick-C_Co2_Speaker 等 7件) — メンテモード

---

## §5 未マージPR一覧

### 自リポの Open PR

**0件** (自分の32リポ + fork 11リポ全てゼロ)

### 外部リポへの自分の Open PR

| Repo | # | Title | Created | Updated | Draft |
|---|---|---|---|---|---|
| GLAY-AK2/NTRIP-client-for-Arduino | #5 | fix: NTRIP v2 compatibility + flush() for reliable ESP32 connection | 2026-04-14 | 2026-04-14 | false |

**★唯一の宿題:** PR #5 は提出から1.5ヶ月放置 (updated == created で完全停止)。上流GLAY-AK2のメンテナ動向次第。

### レビュー依頼PR

**0件**

---

## §6 Open Issue一覧

### 自リポの Open Issue

**0件** (全43リポゼロ・fork系は has_issues=false で無効化済)

### 自分が著者の Open Issue (外部リポ)

| Repo | # | Title | Created | 備考 |
|---|---|---|---|---|
| GLAY-AK2/NTRIP-client-for-Arduino | #1 | M5Stack 3G | 2019-09-01 | **★古い (6.7年放置)。クローズ候補** |

### 自分にアサインされた Open Issue

**0件**

---

## §7 要対応事項 (殿が判断すべき事項)

優先度順:

### P0 (即決推奨)

1. **GLAY-AK2/NTRIP-client-for-Arduino Issue #1 (2019年作成・6.7年放置)** — 内容陳腐化の可能性大。Self-close すべきか確認 (※本subtaskでは F006 厳守でクローズせず・殿判断待ち)。

### P1 (戦略判断)

2. **GLAY-AK2/NTRIP-client-for-Arduino PR #5 (1.5ヶ月放置)** — 上流マージ待ちで arsprout/RTK 戦線が止まるなら、yasunorioi fork main を本番採用 (plan B) すべきか。
3. **arsprout+MQTT 再開時の「最初の1リポ」decide** — 15リポ並行は重い。優先順位: agri-node-poe-core (共通) → センサ4種 → サーバ側 (Arsprout-RESTAPI/OGMS/ccm_rp2350_relay) → LLM/解析 (uecs-llm/arsprout-analysis) の順か、殿の判断を仰ぐ。
4. **rotation-planner v1→v2 移行のクロージング** — v1/v2/iOS の3軸並行は分散リスク。v1 を凍結して v2 集中、または v1 → v2 完全移行スケジュールを decide。

### P2 (任意・余力で)

5. **古いM5Atom系小物 (2023-2024 push 7リポ) のアーカイブ判断** — Unit_ENVIV_M5Atom_mDNS_AsyncWebserver / M5Atom_AcFreqLog / M5Stick-C_Co2_Speaker 等。
6. **Pinned更新検討** — arsprout+MQTT 系の中核 (agri-node-poe-core / OGMS / Arsprout-RESTAPI) を Pinned に昇格するか。
7. **description 未記入リポ多数** — 外部から訪れた人向けに主要リポ (rotation-planner-v2 / ccm_rp2350_relay 等) に1行descを追加するか。

---

## §8 後続cmd 候補 (arsprout+MQTT 深掘り調査の準備メモ)

| cmd案 | 内容 | bloom | 推定時間 |
|---|---|---|---|
| **A. arsprout+MQTT 戦線全体図** | agri-node-poe-core + 派生4ノード + サーバ側 (Arsprout-RESTAPI/OGMS/ccm_rp2350_relay/uecs-ccm-mcp/uecs-llm) の依存関係・通信フロー (MQTT/CCM/HTTP/mDNS/OTA) を全可視化 | L3 | 3-4h |
| **B. agri-node-poe-core 共通基盤の同期戦略** | 派生4ノード (env/flow/rain/solar) との同期方法 (submodule / monorepo / copy) を read-only で現状把握 + 提案 | L3 | 2-3h |
| **C. PR #5 上流動向偵察** | GLAY-AK2/NTRIP-client-for-Arduino の他PR/コメント・メンテナ活動頻度を調査し、plan B (fork main 採用) 判断材料を整理 | L2 | 1h |
| **D. rotation-planner v1→v2 移行 gap 分析** | v1 / v2 / iOS の機能差分・データ移行・テスト網羅性 を read-only で棚卸し | L3 | 3-4h |
| **E. 古いM5Atom系小物の棚卸し** | 2024以前push 10リポについて、参照リポ・現役性・依存先を確認しアーカイブ候補リスト化 | L1 | 1h |

**推奨着手順:** A (戦線俯瞰) → B (基盤分離戦略) → C (PR plan B 判断) → D (rotation-planner クロージング) → E (古いリポ整理)

---

## 付録: F006 準拠確認

本subtaskで実行した gh CLI コマンド一覧 (全てread系):

- `gh auth status`
- `gh repo list yasunorioi --limit 200 --json ...`
- `gh api graphql -f query='{user(login:"yasunorioi")...}'` (pinned)
- `gh search prs --author yasunorioi --state open`
- `gh search issues --author yasunorioi --state open`
- `gh search issues --assignee yasunorioi --state open`
- `gh search prs --review-requested yasunorioi --state open`
- `gh api repos/yasunorioi/{repo}` (×43)
- `gh pr list --repo yasunorioi/{repo} --state open` (×20)
- `gh issue list --repo yasunorioi/{repo} --state open` (×20)

**書込み系コマンド (gh issue create / comment / edit / close, gh pr create / comment / merge / close, gh repo create / delete) は一切実行していない。F006抵触ゼロ。**
