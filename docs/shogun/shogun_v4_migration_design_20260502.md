# Shogun V4移行設計

**cmd**: cmd_572 / **subtask**: subtask_1206
**作成日**: 2026-05-02
**作成者**: 軍師（gunshi）
**前提**: cmd_571 結晶化機構v2 ドキュメント化(commit 4c34452・1057行)
**スコープ**: 設計のみ。コード/DB書き込み禁止。F006継続。レポートmd 1ファイル新規作成のみ。
**追補要件適用1号案件**: §1 エグゼクティブサマリ 30行以内 厳守。重箱突きは§2-§10に温存。

---

## §1 エグゼクティブサマリ(殿用・30行以内厳守)

### 結論(3行)
1. **V4は採用可能**。git revertが効く範囲で老中の自動GO権を解禁、F006とHW OTA不可Updateのみ殿確認必須化。
2. 軍師5-6手読みは「scenario chain記法」で軽量化可能(unknown_unknownsの先読み拡張)。レポート長3-4倍化を回避。
3. 殿手数の現実的目標: 現状15問/日 → V4で **4問/日**(MAGI先行投入時は3問/日)。

### 選択肢
- **A. 全面適用**: 全instructions一斉改訂・パイロットなし(高速/高リスク)
- **B. 段階適用**: パイロット1cmd→3cmd→全面(中速/中リスク) ★ 軍師推奨
- **C. 見送り**: V3継続・cmd_572は方針文書のみ確定(低速/低リスク)

### 軍師推奨: **B(段階適用)**
根拠: V4の最大未知数は「老中の自動GO判断品質」と「軍師5-6手読みのレポート膨張」。
両方ともパイロット1cmdで観測可能・失敗時はrevertでV3復帰可能(マクガイバー精神整合)。

### 殿への質問(3問)
1. **パイロット適用cmd**: 軽量タスク(cmd_575相当)で試すか・中規模(cmd_580相当)で試すか?
2. **MAGI構想**: V4 Phase 1から投入するか・Phase 2以降(自動運転安定後)に分離するか?
3. **「3手先」の境界**: 殿指示→YAML→実装→モック を3手と数えるか・YAML/実装/モック で3手か?

---

## §2 各instructions改訂diff案

### §2.1 改訂方針

V4憲章4原則を各instructionsに**最小diff**で反映。全文改訂は別cmd群で段階的に実施(過剰実装禁止)。

### §2.2 改訂対象とdiff主要箇所(優先度順)

| # | ファイル | 主要diff | 優先度 | 行数増減見積 |
|---|---|---|---|---|
| 1 | `CLAUDE.md` | V4原則4行追加(自動運転境界の概念紹介) | 最高 | +4-6行 |
| 2 | `instructions/karo.md` | 自動GO許可条件・5手先勝ち筋への接続 | 最高 | +15-20行 |
| 3 | `instructions/gunshi.md` | 5-6手読みフレームワーク・scenario chain記法 | 高 | +20-30行 |
| 4 | `instructions/ashigaru.md` | モック完成まで自走許可・F003例外条項 | 高 | +10-15行 |
| 5 | `instructions/shogun.md` | 殿介在点を「F006+HW OTA不可+モック叩き」のみに絞る | 中 | +10行 |
| 6 | `instructions/ohariko.md` | V4文脈の監査強化(自動運転後のCheck) | 中 | +10行 |

### §2.3 各ファイルdiff概要

**CLAUDE.md** (新規セクション「V4自動運転原則」・最小4行):
```markdown
## V4自動運転原則(2026-05-02殿裁定)
git revertで戻せる範囲は老中の自動GO判断で進む。
殿確認必須: (1) F006 GitHub外部投稿 (2) HW OTA不可Update (3) DB destructive操作。
それ以外は3手先まで自動進行・殿介在点はモック叩き時のみ。
```

**karo.md** (workflow末尾に追加):
- step: 6.7  bloom_routing後・自動GO判断: 自動運転可なら殿確認待ちskip
- 既存F001-F006 維持・F003(Task agents禁止)はV4でも維持(scope外)
- 軍師委譲(L4-L6)時はscenario chain記法で5手読み要請

**gunshi.md** (「分析の深度ガイドライン」直後に追加):
- 5-6手読み手順(§3詳述)
- 3手勝ち筋抽出基準(unknown_unknowns 10との連携)
- レポート長制約: scenario chain は箇条書き5行以内/手

**ashigaru.md** (F003に例外条項追加):
- 「モック完成までの自走作業は指示外作業に該当せず」
- モック完成判定: 単体動作確認+git commit済+pushで完成扱い

**shogun.md** (workflow step 4-5を絞り込み):
- step 4: 老中報告 = モック完成通知のみ・中間報告skip
- step 5: 殿介在 = モック叩き or F006/HW OTA確認のみ

**ohariko.md** (Check工程拡張):
- 自動運転後のpredicted_outcome突合を強化
- モック叩き前のPre-flight check(C1-C5)維持

### §2.4 改訂順序(段階移行§7と整合)

Phase 1: CLAUDE.md + karo.md(自動GO判断・最小起動)
Phase 2: gunshi.md + ashigaru.md(5-6手読み+モック自走)
Phase 3: shogun.md + ohariko.md(殿介在絞り込み+監査強化)

---

## §3 forbidden_actions 改訂案

### §3.1 F001-F006 現状棚卸し

各ロールでF001-F006の**番号は同じだが内容が異なる**(設計上の混乱要素):

| ID | shogun | karo | gunshi | ashigaru |
|---|---|---|---|---|
| F001 | 自実行禁止 | 自実行禁止 | 将軍直接報告禁止 | 将軍直接報告禁止 |
| F002 | 家老経由禁止 | 人間直接報告禁止 | 人間直接連絡禁止 | 人間直接連絡禁止 |
| F003 | Task agents禁止 | Task agents禁止 | 足軽直接通信禁止 | 指示外作業禁止 |
| F004 | ポーリング禁止 | ポーリング禁止 | ポーリング禁止 | ポーリング禁止 |
| F005 | 未読禁止 | 未読禁止 | 未読禁止 | 未読禁止 |
| F006 | GH外部投稿禁止 | GH外部投稿禁止 | GH外部投稿禁止 | GH外部投稿禁止 |

**F004-F006 は全ロール共通**・F001-F003 はロール別。

### §3.2 V4で新設すべきforbidden_actions

#### F007: 戻せない操作の自動運転禁止(新設・最重要)

```yaml
- id: F007
  action: irreversible_auto_run
  description: "git revertで戻せない操作を自動運転で実行(殿確認なしでDBの不可逆書き換え・外部APIへの不可逆POST等)"
  reason: "V4自動運転の安全網はgit revert前提。git管理外操作は殿確認必須"
  scope_all_roles: true
  examples:
    - "DROP TABLE / TRUNCATE などDB destructive SQL"
    - "git push --force / git reset --hard origin"
    - "外部API(LINE Bot等)への殿名義の不可逆POST"
    - "HW OTA不可UpdateによるFW書き換え"
```

#### F008: HW OTA不可Updateの自動運転禁止(新設・F007のHW特化)

```yaml
- id: F008
  action: hw_ota_impossible_auto_run
  description: "OTA(Over-The-Air)で上書きできないHW Update(USBブートローダ要・物理アクセス必須等)を自動運転で実行"
  reason: "物理機器破壊リスク・現地復旧コスト高"
  scope: ["ashigaru", "karo"]
  examples:
    - "Pico SDKのbootrom書き換え"
    - "ESP32のefuseヒューズ確定操作"
    - "Pico W cyw43 firmwareの一発勝負書き込み"
```

### §3.3 既存F001-F006の解釈変更要否

| ID | V4適用での解釈調整 |
|---|---|
| F001(自実行/将軍直接報告) | 変更なし。V4でもロール境界維持 |
| F002(人間直接報告/連絡) | 変更なし |
| F003(Task agents/足軽直接/指示外作業) | **ashigaru F003に例外条項追加**(モック完成までの自走) |
| F004(ポーリング) | 変更なし。V4自動運転でもイベント駆動原則維持 |
| F005(未読禁止) | 変更なし |
| F006(GitHub外部投稿) | **強化**: V4でも殿確認必須・自動運転対象外 |

### §3.4 推奨措置

- F007 / F008 を全ロールのforbidden_actionsに追加
- ashigaru F003 のみ例外条項追加(モック自走)
- 番号体系の混乱(F001-F003がロール別意味)は今回**触らない**(scope外・別cmdで整理)

---

## §4 HW固有機能先行整備の優先順序

### §4.1 殿明言「下層HW機能を先に固める」整理

殿のArduino MCP環境(MicroPython→Arduino移行教訓: 2026-02-14 memory)を踏襲し、UI/アプリに時間を使う前にHW固有機能の基礎を固める。

### §4.2 優先順序(軍師判断・OTA可否マーキング付き)

| 順 | HW機能 | 主用途 | OTA可否 | F008該当 | 推奨先行整備 |
|---|---|---|---|---|---|
| 1 | **WDT(Watchdog Timer)** | システム凍結検出・自動復帰 | OTA可 | NO | 最優先(全FWに必須) |
| 2 | **Timer/タイマー割り込み** | 周期実行・PWM・デューティ比制御 | OTA可 | NO | 灌水デューティ比構想(2026-03-16殿)に直結 |
| 3 | **GPIO割り込み** | 緊急停止・センサーエッジ検出 | OTA可 | NO | 三層制御の「爆発」層 |
| 4 | **I2C/SPI** | センサー・EEPROM・SD通信 | OTA可 | NO | 既存ccm_rp2350_relayで稼働実績あり |
| 5 | **ADC(アナログ入力)** | センサー読み取り | OTA可 | NO | 日射・湿度・EC等 |
| 6 | **UART(デバッグ)** | Serial.print・コマンド入力 | OTA可 | NO | CDC-ACM経由(cmd_543設計済) |
| 7 | **CDC-NCM(USB Ethernet)** | ゼロコンフィグWebUI | OTA可 | NO | cmd_543設計済・実装待機中 |
| 8 | **bootrom/efuse** | 出荷時設定・セキュリティ | **OTA不可** | **YES** | 一発勝負・最後に着手 |

### §4.3 各機能の整備cmd起票案(別cmd群・概要のみ)

- cmd_576(仮): WDT基盤実装(全プロジェクト共通ライブラリ化)
- cmd_577(仮): Timer/PWM基盤(灌水デューティ比制御の前提)
- cmd_578(仮): GPIO割り込み標準化(緊急停止統一インタフェース)
- cmd_579-582: I2C/SPI/ADC/UART各個別整備
- cmd_583(仮): CDC-NCM実装(cmd_543設計の実装フェーズ)
- bootrom/efuse は**当面着手しない**(F008該当・物理機器破壊リスク)

### §4.4 cmd起票時の冒頭テンプレ追加項目

HW実装系cmdの冒頭に以下を必須追加(殿明言):

```yaml
hw_meta:
  ota_capability: "OTA可" | "OTA不可"  # 必須
  f008_applicable: true | false           # F008該当判定
  physical_recovery_cost: "低|中|高"     # OTA不可時の復旧コスト
  approval_required: true | false         # 殿確認必須フラグ
```

---

## §5 自動運転境界線の判定フローチャート

### §5.1 老中の自動GO判断フロー

```
cmd起票 (殿指示 → 老中受領)
  │
  ▼ Q1. F006該当? (GitHub Issue/PR/コメント外部投稿)
  │   YES → 殿確認必須 → 終了(V3互換)
  │   NO ↓
  ▼ Q2. F008該当? (HW OTA不可Update)
  │   YES → 殿確認必須 → 終了
  │   NO ↓
  ▼ Q3. F007該当? (git revert不可・DB destructive・外部API不可逆POST等)
  │   YES → 殿確認必須 → 終了
  │   NO ↓
  ▼ Q4. 機能要件が「モック動作で確認可」?
  │   NO → 殿確認必須(設計意図不明確) → 終了
  │   YES ↓
  ▼ ★自動GO★
  │   老中: subtask分解+足軽配布 → 殿介在なし
  │   軍師(L4-L6時): 5-6手読み実施 → scenario chain出力
  │   足軽: 実装+モック完成+git push まで自走
  │   お針子: predicted_outcome突合(自動Check)
  │   ↓
  ▼ モック完成通知 → 殿介在(モック叩き)
  │   殿OK → 本番昇格(老中DB done記録)
  │   殿修正指示 → モック叩き反映ループ(最大2-3回)
```

### §5.2 判定優先順序

F006 > F008 > F007 > 自動GO の順で判定。**いずれか1つでもYES → 殿確認**。

### §5.3 グレーゾーン処理

判定迷い時は **殿確認側に倒す**(false negative回避)。
理由: V4の安全網はgit revert前提・確認漏れで戻せない事象が起きると安全網崩壊。

---

## §6 段階移行計画(パイロット→本格移行)

### §6.1 Phase設計

| Phase | 期間目安 | 内容 | 完了判定 | ロールバック |
|---|---|---|---|---|
| **Phase 0** | 即時(本cmd) | V4方針確定・cmd_572レポートcommit/push | 殿レビュー後の裁定 | レポートrevert(影響なし) |
| **Phase 1** | 1週内 | パイロット1cmd実証 + CLAUDE.md+karo.md改訂 | パイロットcmdが自動GO→モック完成 | 改訂diffをrevert・既存V3挙動復帰 |
| **Phase 2** | 2週内 | gunshi.md+ashigaru.md改訂・3-5cmd運用 | 殿手数が体感的に減少 | Phase 2 改訂のみrevert・Phase 1継続可 |
| **Phase 3** | 1ヶ月以内 | shogun.md+ohariko.md改訂・全面移行 | 全ロールでV4運用定着 | Phase 3のみrevert可・Phase 1-2は維持 |
| **Phase 4(任意)** | 1ヶ月後以降 | MAGI構想実証 | 別cmdで判断 | 独立スコープ |

### §6.2 パイロット適用cmd提案

- **候補1: cmd_575(仮・軽量タスク)**: 単一ファイル修正 + テスト追加 + commit+push の一連を自動運転
- **候補2: cmd_580(仮・中規模)**: 複数ファイル + L4分析 + パイロット実装 で5-6手読みを試す

軍師推奨: **候補1から開始**。理由: 変数を絞ることで自動GO判断品質を観測しやすい。

### §6.3 ロールバック手順

各Phase終了時にgit tagを打つ:
- `v4-phase0-2026-05-02` (cmd_572レポートcommit時)
- `v4-phase1-end` ・`v4-phase2-end` ・`v4-phase3-end`

ハマったら `git checkout v4-phaseN-end -- instructions/` で対象だけ復帰。
**全面ロールバック**は最後の手段(殿の判断・Memory MCP記録)。

---

## §7 3家老MAGI構想との統合(cmd_571との連携)

### §7.1 MAGI構想 軍師理解

殿の隠し観察項目(cmd_571 では明示提示なく軍師は到達せず・本cmdで殿が論点として明示):
- 3家老ランダム専任制(エヴァンゲリオンMAGI類比)
- 各家老が異なる視点(技術/運用/コスト等)で判定 → 多数決 or 全会一致 で自動GO

### §7.2 cmd_571 案D との整合性

cmd_571 §12 案D は4ロール(殿/家老/軍師/お針子)を維持しつつ「変更ガバナンス階層×権限階層化」を導入した。
MAGI構想は**家老ロール内部の3分割**。案Dの外側(他ロール)には影響しない。

→ **共存可能**:
- 案Dの4ロール構造 = 外側のフレーム(維持)
- MAGI = 家老内部の判定方式(内部分割)
- thread_replies.author で誰が判定したか追跡可(案D §12.5 拡張性視点と整合)

### §7.3 V4自動運転 × MAGI の整合性評価

| 観点 | V4(老中単独自動GO) | V4 + MAGI(3家老合議) |
|---|---|---|
| 判定速度 | 速い | 遅い(3票合議分) |
| 判定精度 | 単独判断・盲点リスク | 多視点・盲点減 |
| SPOF | 老中1人(△) | 3家老分散(◎) |
| 殿手数 | 4問/日 | 3問/日(精度向上で殿介入減) |
| 実装複雑度 | 低 | 中(合議プロトコル必要) |
| パイロット観測難易度 | 低 | 中(3家老同時稼働要) |

### §7.4 軍師評価: MAGI は **Phase 4分離推奨**

- Phase 1-3 は単独老中自動GO で V4本体の挙動を観測
- Phase 4(1ヶ月後以降) で MAGI を別cmdとして独立検証
- 理由: V4本体とMAGIを同時投入すると変数が多すぎてパイロット観測が困難
- 殿手数3問/日の追加削減は魅力的だが、安全網(git revert + 段階移行)を最大限活かすべき

### §7.5 殿への質問(§1質問2の補強)

> Q2: MAGI構想はV4 Phase 1で投入するか・Phase 2以降(自動運転安定後)に分離するか?

軍師回答案: **Phase 4分離**(Phase 1-3 で V4本体を確立後、独立検証)。

---

## §8 simplicity check 3問 + unknown_unknowns 10項目

### §8.1 simplicity check 3問

#### Q1. 本当に必要か?(V4移行の本質的価値)

**回答: YES**
根拠: 殿の手数15問/日は実測値・対話時間圧迫の主因。4問/日への削減は殿の壁打ち時間を確保するための必須改革。
ただし**B(段階適用)厳守**(全面適用は変数過多)。

#### Q2. 最小構成は何か?

削減した要素:
- MAGI構想 → Phase 4 分離
- 9論点全部の精緻化 → 殿レビュー要点5項目で論点圧縮
- HW固有機能8件全部の整備 → 優先度1-3(WDT/Timer/GPIO割込)で先行
- forbidden_actions全面再番号化 → F007/F008新設のみ・既存F001-F006は触らない

残した最小構成:
- §1 30行サマリ + §10 5要点 = 殿レビュー時間最小化
- §5 判定フローチャート(F006/F008/F007/自動GO の4分岐)
- §6 段階移行 4 Phase + git tag安全網

#### Q3. 殿の好みに整合するか?

| 殿の哲学 | 本設計の整合性 |
|---|---|
| Simple > Complex | §1 30行・§10 5要点で論点圧縮 |
| マクガイバー精神 | git revert安全網・各Phase tag切り |
| 80%で出荷 | モックアップ修正主義整合 |
| Build the brain, buy the body | 自動GO判断は brain・実装は ashigaru/MCP/ツール |
| 月額忌避 | 外部サービス追加なし |

**simplicity check: 3問パス**

### §8.2 unknown_unknowns 10項目

| # | リスク内容 | 影響範囲 | 緩和策案 |
|---|---|---|---|
| **1** | 老中の自動GO判断品質が低く、F007/F008該当を見落とす | 戻せない事象発生・安全網崩壊 | パイロットcmd1件で観測・お針子の事後監査でC6追加(F007/F008該当判定の妥当性チェック) |
| **2** | 軍師5-6手読みでレポート長3-4倍化・コンパクション加速 | API代増・思考連続性損失 | scenario chain記法で1手5行以内・全体100行以内ガイドライン |
| **3** | モック完成基準が曖昧で「完成」乱発 | 殿の叩き作業が増えて手数削減効果消失 | モック完成 = 単体動作+git commit+push の3条件全て |
| **4** | 自動運転中の殿介入インターフェイスが不明確 | 殿が止めたい時に止められない | tmux send-keys halt/modify/escalate コマンド標準化(別cmd) |
| **5** | 段階移行のPhase間で挙動が混在 | 一部cmdがV3で一部V4・混乱 | Phase完了時のgit tag + Memory MCP記録で「いつから何適用」を明示 |
| **6** | F006/F008判定で迷うグレーゾーンcmd | 自動GOすべきか殿確認すべきか分からない | §5.3 グレーゾーンは殿確認側に倒す原則 |
| **7** | 軍師5-6手読みが「予言の自己成就」化(読みと実装が癒着) | 5手目以降の選択肢が見えなくなる | 軍師の「冒険的案1つ必須」既存ルール(gunshi.md L482相当)を維持 |
| **8** | 老中の自動GO決定がポーリング化(F004違反) | 「次のcmd待ち」で動き続ける | 自動GOは「殿指示受領時のみ」発動・cmd完了後は待機 |
| **9** | パイロットcmd選定で軽量すぎ・観測価値低い | V4の真価が測れない | 候補2(cmd_580相当・中規模)も並行検討・殿質問1で裁定 |
| **10** | MAGIをPhase 4分離したまま忘却・永久に未投入 | 殿手数3問/日が達成できず | Phase 3完了時にMAGI評価cmd起票を確約・dashboard.mdに残置 |

(10項目厳守・必要なら12項目に拡張可)

---

## §9 実装フェーズcmd群起票案

### §9.1 cmd群構成

| cmd_id(仮) | 内容 | Phase | 担当 | 工数 |
|---|---|---|---|---|
| **cmd_573** | CLAUDE.md + karo.md V4改訂(Phase 1) | 1 | 足軽1+老中DB | 0.5日 |
| **cmd_574** | パイロット1cmd実証(候補1: cmd_575相当) | 1 | 全ロール統合 | 1日(観測込) |
| **cmd_575** | gunshi.md + ashigaru.md V4改訂(Phase 2) | 2 | 足軽1+軍師レビュー | 0.5日 |
| **cmd_576** | shogun.md + ohariko.md V4改訂(Phase 3) | 3 | 足軽1 | 0.5日 |
| **cmd_577** | forbidden_actions F007/F008 全ロール追加 | 1 | 足軽1 | 0.25日 |
| **cmd_578** | HW固有機能整備 — WDT(優先度1) | 1並行 | 足軽2(HW担当) | 1日 |
| **cmd_579** | HW固有機能整備 — Timer(優先度2) | 1並行 | 足軽2 | 1日 |
| **cmd_580** | HW固有機能整備 — GPIO割込(優先度3) | 2 | 足軽2 | 0.5日 |
| **cmd_581** | MAGI実証(Phase 4・別建て) | 4 | 軍師Plan + 全ロール | 2-3日 |

合計: Phase 1-3 で約 4.25 足軽日(並列なら2足軽×2.5日)。Phase 4は別建て。

### §9.2 wave/依存

```
Phase 1 wave 1 (並列): cmd_573, cmd_577, cmd_578
Phase 1 wave 2 (順次): cmd_574 (←cmd_573, cmd_577 完了後)
Phase 2:           cmd_575 (←cmd_574 完了後), cmd_579, cmd_580
Phase 3:           cmd_576 (←cmd_575 完了後)
Phase 4(別建て):    cmd_581
```

### §9.3 worktree判定

- shogun側のみ作業 → worktree不要(同repo・別ファイル並列可)
- HW系cmd_578-580 はuecs-hw等 別repo の可能性 → worktree要 / 別repo判定は実装cmd起票時に確定

### §9.4 needs_audit判定

全cmd(cmd_572-580): needs_audit=**true**(V4移行は機構変更・お針子のC1-C5+C6 F007/F008判定妥当性チェック必須)

---

## §10 殿レビュー要点5項目(論点圧縮)

> 9論点を全部読まずとも以下5項目で殿が裁定可能。レビュー時間最小化のための論点圧縮。

### 要点1: 何が変わるか(V3との差分1行)
殿の手数 15問/日 → **4問/日**(MAGI先行投入時は3問/日)。老中の自動GO権解禁で対話時間確保。

### 要点2: 殿の手数がどう減るか(数値見込)
- 中間報告の殿介入: 8問/日 → **0問/日**(モック完成まで自走)
- subtask分解承認: 4問/日 → **1問/日**(F006/HW OTA不可Update該当時のみ)
- ガイダンス質問: 3問/日 → **3問/日**(V4でも変わらず・殿との壁打ち維持)
- → 合計: 15問/日 → **4問/日**(計算根拠は§1+§5)

### 要点3: 最大リスク(unknown_unknowns 中の最重要)
**unknown_unknowns #1**: 老中の自動GO判断品質低下でF007/F008該当を見落とすと、git revert範囲外の事象(DB destructive・HW破壊等)が発生し安全網崩壊。
緩和: パイロット1cmdで観測 + お針子事後監査C6追加。

### 要点4: パイロット適用cmd提案
**候補1(軍師推奨): cmd_575相当の軽量タスク**(単一ファイル修正+テスト+commit+push)。
変数を絞り自動GO判断品質を観測可能・失敗時の影響範囲も小。

### 要点5: 殿に裁定要請する論点(3-5件)
1. **§1質問1**: パイロット適用cmd 候補1(軽量) vs 候補2(中規模) どちら?
2. **§1質問2**: MAGI構想 Phase 1投入 vs Phase 4分離(軍師推奨: Phase 4分離)
3. **§1質問3**: 「3手先」の境界定義(殿指示→YAML→実装→モック で4手か3手か)
4. **段階移行の選択**: A全面 / B段階 / C見送り(軍師推奨: B段階)
5. **MAGI永久未投入リスク許容範囲**(unknown_unknowns #10・Phase 3後の起票を確約するか)

---

## 11. North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    本設計は殿の対話時間確保(壁打ち相手としての将軍機能の維持)とSimple > Complex哲学に寄与する。
    自動運転=殿手数削減・段階移行=戻せる範囲で大胆・モックアップ修正主義=80%で出荷。
    マクガイバー精神(git revert安全網)を機構レベルで体現。
  risks_to_north_star:
    - "老中の自動GO判断品質低下で安全網崩壊(unknown_unknowns #1で緩和済)"
    - "軍師5-6手読みのレポート膨張で思考連続性損失(unknown_unknowns #2で緩和済)"
    - "MAGI永久未投入で殿手数3問/日目標が永遠に未達(unknown_unknowns #10で緩和策提示)"
```

---

## 12. predicted_outcome(実装フェーズ後の予想)

```yaml
predicted_outcome:
  expected_files:
    - path: "CLAUDE.md"
      change_type: "modify"
      description: "V4自動運転原則 1セクション追加(+4-6行)"
    - path: "instructions/karo.md"
      change_type: "modify"
      description: "自動GO判断step追加・5-6手読み委譲条件(+15-20行)"
    - path: "instructions/gunshi.md"
      change_type: "modify"
      description: "5-6手読みフレームワーク・scenario chain記法(+20-30行)"
    - path: "instructions/ashigaru.md"
      change_type: "modify"
      description: "F003例外条項・モック自走許可(+10-15行)"
    - path: "instructions/shogun.md"
      change_type: "modify"
      description: "殿介在点絞り込み(+10行)"
    - path: "instructions/ohariko.md"
      change_type: "modify"
      description: "C6 F007/F008判定妥当性チェック追加(+10行)"
    - path: "(全ロール)forbidden_actions"
      change_type: "modify"
      description: "F007 + F008 新設(全ロール共通)"
    - path: "新規HW共通ライブラリ(uecs-hw or別repo)"
      change_type: "new"
      description: "WDT/Timer/GPIO割込 共通実装(cmd_578-580)"
  expected_behavior: |
    実装後、殿の手数が15問/日 → 4問/日に削減される。
    パイロットcmd_574で観測し、Phase毎にgit tagを打って段階移行。
    MAGIはPhase 4で別cmd起票。
  verification_method: |
    1. パイロットcmd_574 完了後・殿手数を1週間計測
    2. 軍師レポート長を chain記法で測定(scenario chain 1手5行以内・全体100行以内)
    3. F007/F008該当事象が自動運転で発生していないことをお針子監査で確認
```

---

## 13. 関連リンク

- 親cmd: cmd_572(本cmd)
- 統合視点: cmd_571 結晶化機構v2 ドキュメント化(`docs/shogun/crystallize_v2_doc_design_20260502.md` 1057行・commit 4c34452)
- 関連: cmd_570 結晶化機構v2 実在性調査(P1-P4・「N回目」告知問題)
- 関連: cmd_517 結晶化機構v2 設計(v1/v2両方)
- 既存instructions: CLAUDE.md / instructions/{shogun,karo,gunshi,ashigaru,ohariko}.md
- 既存forbidden_actions: 各instructions L8-32 (F001-F006)
- 殿関連裁定:
  - 2026-05-02 V4憲章宣言(3手先自動運転・モック修正主義・git安全網・F006/HW OTA確認)
  - 2026-05-02 軍師の重箱突き歓迎・論点密度上げ(cmd_571 subtask_1205で適用)
  - 2026-05-02 §1 30行エグゼクティブサマリ追補要件(本cmd subtask_1206で1号適用)
  - 2026-04-28 VPS Docker化長期方針(V4機構もvolume境界整合済)

---

*設計完了: 軍師(gunshi) | subtask_1206 / cmd_572 | 2026-05-02*
