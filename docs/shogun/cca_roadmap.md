# CCA知見に基づくshogunシステム改善ロードマップ

> **軍師分析** | 2026-03-18 | Bloom L5（評価）
> **North Star**: 公式の知恵を借りて、最小の変更で最大のシステム改善を。老中を殺すな

---

## 1. 問題の本質 — 老中過負荷の因数分解

CCA Domain 1の核心: **コーディネーターの分解ミスが最大の失敗原因**。
shogunの老中は現在、以下の7責務を1エージェントで担う:

| # | 責務 | 負荷 | CCA対応概念 |
|---|------|:----:|------------|
| R1 | タスク分解（Bloom判定+subtask設計） | **最重** | attention dilution |
| R2 | 足軽割当（inbox YAML書き込み+send-keys） | 中 | hub-and-spoke routing |
| R3 | 報告受理（roju_reports.yaml読み+検証） | 重 | tool result trimming |
| R4 | 監査依頼（お針子キュー管理） | 中 | validation-retry loop |
| R5 | dashboard更新（dashboard.md書き換え） | 軽 | scratchpad files |
| R6 | 没日録DB操作（全権） | 軽 | — |
| R7 | rejected時の再割当・判断 | **重** | error propagation |

**構造的洞察**: R1（分解品質）の劣化は下流全てを汚染する。だが「老中を分割する」のは過剰手術。
**正解**: R3・R4・R7の自動化で老中の認知負荷を削り、R1に集中させる。

---

## 1.1 外部事例による裏付け — 月商300万SaaS完全ソロ運用

> 出典: [Claude Codeで月商300万SaaSを完全ソロ運用](https://zenn.dev/nnze/articles/e3f648e335a947)

Next.js + Supabase + StripeのSaaSを1人でClaude Code運用。エラー検知→AI分析→PR生成→人間承認の自動パイプラインを構築。

**shogunロードマップへの4つの示唆**:

| # | 事例の知見 | shogunへの適用 | 該当候補 |
|---|-----------|--------------|---------|
| 1 | エラー→AI分析→PR→人間承認の自動パイプライン | お針子rejected→足軽修正→再監査の自動ループと同構造 | **④ retry-loop** |
| 2 | 「コードがダサくても気にしない」= 動作優先 | 殿の「動けば合格」= correctness 3点の条件を厳しくしすぎない | **⑤ calibration** |
| 3 | 人間介入はセキュリティレビュー+マージ承認のみ | 老中介入をrejected_judgment+エスカレーションのみに限定 | **④ retry-loop** |
| 4 | 無限ループ時のみ手綱 | retry上限2回 → エスカレーションのフェイルセーフ | **④ retry-loop** |

**設計への反映**:
- ④ retry-loopの**Wave順序を据え置き（Wave 10）**。事例は「自動化は正しい方向」を裏付けるが、この事例は単一エージェント運用であり、マルチエージェント間の自動ループは**判定精度（⑤）が前提**という構造的制約は変わらない
- ⑤ calibrationのfew-shot例に**「動けば合格」基準を明示的に組み込む** — correctnessカテゴリで「コードの美しさは減点対象外」と明記
- ⑦ notifyの優先度を**再確認** — 事例の「自動監視ボットがログを丸抱えしてエージェントに送信」は、shogunのnotify.py（外部への状況発信）と方向が一致

## 1.2 外部事例による裏付け — 42エージェント本番運用フレームワーク

> 出典: [Agent Skill Bus](https://github.com/ShunsukeHayashi/agent-skill-bus) — 42エージェント日次27タスク平均スループット、JSONL通信基盤

**アーキテクチャの類似性**: JONLファイルベース非同期通信、DAG依存管理、フレームワーク非依存設計。shogunのYAML通信+blocked_by+tmux構成と驚くほど共通する設計判断。

**shogunロードマップへの5つの示唆**:

| # | Agent Skill Busの知見 | shogunの現状 | 適用判定 |
|---|----------------------|-------------|---------|
| 1 | **Silent Skill Degradation検知**: スコア追跡+週次15%低下アラート | MCP/API壊れても気づかない（盲点） | **⑧新規候補** |
| 2 | **ファイルロック**: `affectedFiles`+TTL付きロック+`active-locks.jsonl` | worktree設計で上位レベル解決 | ⑥に統合検討 |
| 3 | **7ステップ自己改善ループ**: OBSERVE→ANALYZE→DIAGNOSE→PROPOSE→EVALUATE→APPLY→RECORD | お針子監査は3ステップ（差分確認→採点→報告）| ④に構造化ヒント |
| 4 | **DAGトポロジカル自動実行**: `dependsOn`解決後に自動dispatch | blocked_byは手動（老中がR2で管理） | **将来検討** |
| 5 | **Knowledge Watcher 3Tier**: 毎回/日次/週次の階層的外部変更検知 | 獏の夢見（内部連想）のみ。外部変更検知なし | **将来検討** |

### 各示唆の詳細判定

**示唆1 — Silent Skill Degradation → ⑧新規候補として追加**

shogunの盲点。以下が「静かに壊れる」リスクを持つ:
- Memory MCP（mcp__memory__*） — サーバープロセス停止で全エージェントの永続記憶が消失
- 高札API（localhost:8080） — Dockerコンテナ停止で16エンドポイント全滅
- Notion MCP — API key失効でproject管理が不能に
- inbox_write.sh — YAMLフォーマット破損で通信断絶

ただし**42エージェント規模のスコア追跡は過剰**。shogunは5-7エージェント。
→ **最小実装**: 老中のセッション開始時にヘルスチェックスクリプトを実行（MCP応答、高札ping、inbox YAML整合性）

**示唆2 — ファイルロック → ⑥worktreeで上位解決済み**

Agent Skill Busのファイルロックは「同一ディレクトリで複数エージェントが同一ファイルを編集する」問題への解。
shogunのworktree設計は「そもそも別ディレクトリで作業する」ため、ファイルレベルのロックは不要。

ただし**worktree対象外ファイル**（gitignored: queue/inbox/*.yaml, data/botsunichiroku.db）には衝突リスクが残る。
→ **現状の対策で十分**: inbox_write.shの追記方式 + 没日録DBは老中のみ書き込み権限（権限マトリクスで制御済み）

**示唆3 — 7ステップ自己改善 → ④retry-loopの設計補強**

現行の④設計（rejected→足軽修正→再監査）は実質3ステップ:
```
OBSERVE(お針子採点) → APPLY(足軽修正) → OBSERVE(再監査)
```

Agent Skill Busの7ステップから**DIAGNOSEとRECORD**を取り込むべき:
```
OBSERVE(お針子採点) → DIAGNOSE(失敗原因分類) → APPLY(足軽修正) → RECORD(没日録に学習記録)
```

- **DIAGNOSE追加**: お針子のfindingsに「失敗カテゴリ」を必須化（prompt不足/要件誤解/技術的誤り/回帰）
- **RECORD追加**: rejected→修正→合格の経緯を没日録DBに記録し、同種エラーの再発率を追跡可能に

**示唆4 — DAGトポロジカル自動実行 → 将来検討**

現状: 老中がblocked_byを見て手動でsubtask投入順を制御（R2責務）。
Agent Skill Busの自動dispatch（依存解決後に自動開始）は老中R2の自動化に直結するが:
- shogunの足軽はtmux paneに常駐しており、「自動dispatch」= send-keysの自動発火
- 足軽のpane空き状況の判定が必要（idle検知）
- 実装コストが高い（老中のワークフローエンジン化）

→ **現時点ではやらない**。Wave 8-10完了後、老中過負荷が残る場合に再評価。

**示唆5 — Knowledge Watcher 3Tier → 将来検討**

獏（baku.py）は「内部の連想・夢見」。Knowledge Watcherは「外部変更の検知」。相補的だが別物。
shogunでの適用先:
- Tier 1（毎回）: MCP応答チェック → ⑧のヘルスチェックと重複
- Tier 2（日次）: Claude Code/MCP仕様変更の検知 → 有用だが獏の拡張で対応可能
- Tier 3（週次）: Anthropic API変更・新機能リリース → 獏のWeb検索で既にカバー

→ **現時点ではやらない**。獏の夢見機能拡張（高札v2 dream.py）で段階的にカバー。

---

## 2. 優先度マトリクス

### 2.1 効果 × コスト 配置図

```
        効果
  High ┃ ③trimming    ④retry-loop   ①hub-spoke
       ┃              ⑥worktree
       ┃──────────────────────────────────────
  Med  ┃ ⑧healthchk   ⑤calibration
       ┃
       ┃──────────────────────────────────────
  Low  ┃ ②rules
       ┃ ⑦notify
       ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
         Low Cost      Med Cost      High Cost
```

### 2.2 個別評価

| # | 改善候補 | 効果 | コスト | 老中負荷削減 | 判定 |
|---|---------|:----:|:-----:|:-----------:|:----:|
| ① | hub-and-spoke純化 | High | **High** | ◎（根治） | **やらない** |
| ② | path-specific rules | Low | Low | △ | **後回し** |
| ③ | tool result trimming | High | **Low** | ○（R3軽減） | **やる** |
| ④ | validation-retry loop | High | Med | ◎（R4+R7自動化） | **やる** |
| ⑤ | severity calibration | Med | Med | ○（間接:誤判定減） | **やる** |
| ⑥ | worktree実装 | High | Med | ○（衝突割込み減） | **やる** |
| ⑦ | 通知システム | Low | Low | △ | **やる（軽量）** |
| ⑧ | ヘルスチェック（劣化検知） | Med | Low | ○（障害早期発見） | **やる** |

---

## 3. 各候補の詳細所見

### ① hub-and-spoke純化 → **やらない**

**理由**: shogunのhub-and-spoke構造はCCA推奨パターン**そのもの**。問題は「パターンの不採用」ではなく「ハブの過負荷」。

CCA Domain 1が警告するのは:
- サブエージェント間の直接通信 → shogunは既に禁止（YAML通信+send-keys制御）
- コーディネーターの分解ミス → これは老中のR1品質問題

**老中を2エージェントに分割する案の却下理由**:
1. 分割した2エージェント間の状態同期が新たな複雑性を生む
2. 没日録DBの全権操作を2エージェントに渡すとRACE条件が発生
3. 現行のtmux 4ペイン（老中+足軽2+部屋子1）を拡張するとペイン管理が爆発
4. 老中のcontext/karo-*.md分割は既に実施済み — これ以上の構造変更は過剰手術

**代わりにやること**: ②③④⑤⑥で老中のR3・R4・R7を自動化し、R1（タスク分解）に認知リソースを集中させる。
これがCCAの「注意希薄化(attention dilution)問題」への正しい解。

---

### ② path-specific rules → **後回し**

**理由**: ROIが低い。現行のinstructions/*.md + CLAUDE.md階層で十分機能している。

**CCAが推奨する具体例と現状の対比**:

| CCA推奨 | shogun現状 | gap |
|---------|-----------|-----|
| `**/*.test.tsx` でテスト規約 | テストファイルが少ない（pytest中心） | gapなし |
| ディレクトリ別ルール | instructions/*.md + context/*.md | 同等機能 |
| `@import` でルール参照 | 未使用 | 低優先 |

**実施する場合の候補（将来）**:
- `.claude/rules/scripts.md` (glob: `scripts/**/*.py`): `PROJECT_ROOT`参照ルール、DB_PATH解決方式
- `.claude/rules/instructions.md` (glob: `instructions/**/*.md`): 指示書フォーマット統一

**判定**: worktree導入後にPROJECT_ROOT問題が顕在化したら再検討。現時点では不要。

---

### ③ tool result trimming → **やる（Wave 8）**

**現状の問題**:
- 足軽の報告ルール「50行→3行summary」は`instructions/ashigaru.md`に記載済み
- しかし**老中側に受信時トリム機構がない** — 長文報告がそのまま老中のコンテキストに注入される
- roju_reports.yamlの報告フォーマットにsummary長の構造的制約がない

**CCA Domain 5の処方箋**: `tool result trimming — 40フィールド中5つだけ必要ならトリムせよ`

**実装案**:
1. **roju_reports.yaml スキーマ強制**: `summary`フィールドを**最大80文字**に制限（フォーマットバリデーション）
2. **detail_ref方式の徹底**: 詳細は没日録DBに格納し、summaryにはDB参照コマンドのみ記載
3. **inbox_write.sh にバリデーション追加**: 80文字超のsummaryは切り詰め+警告

**効果**: 老中のR3（報告受理）の認知負荷を直接削減。コンパクション耐性も向上。
**コスト**: inbox_write.sh に10行程度の追加。最も安い改善。

**subtask分解案（2件）**:
- S1: inbox_write.sh にsummary長バリデーション追加
- S2: context/karo-yaml-format.md に受信時トリムルール追記

---

### ④ validation-retry loop → **やる（Wave 9）**

**現状の問題（実例）**:
- お針子がrejected → 老中が手動で足軽に再割当（R7負荷）
- subtask_925→928の事例: 手動やり直しで老中が3回介入

**CCA Domain 4の処方箋**: `validation-retry loop — 監査rejected時の修正→再監査フロー`

**設計案 — DIAGNOSE+RECORD強化型エスカレーション**:

> Agent Skill Busの7ステップ自己改善ループ(OBSERVE→ANALYZE→DIAGNOSE→PROPOSE→EVALUATE→APPLY→RECORD)から
> shogunに不足していた**DIAGNOSE**（失敗原因分類）と**RECORD**（学習記録）を取り込む。

```
お針子 rejected_trivial (10-12点)
  │
  ▼ OBSERVE: お針子が採点（既存フロー）
  │
  ▼ DIAGNOSE: findingsに失敗カテゴリを付与（新規）
  │   カテゴリ: prompt不足 / 要件誤解 / 技術的誤り / 回帰 / フォーマット不備
  │
  ▼ APPLY: 足軽に修正指示をsend-keys（findingsをそのまま渡す）
  │         老中にはcc通知のみ（介入不要）
  │
  ▼ 足軽が修正 → お針子が再監査（自動ループ、最大2回）
  │
  ▼ RECORD: 結果を没日録DBに記録（rejected→修正→合格の経緯）（新規）
  │   → 同種エラーの再発率追跡が可能に
  │
  ▼ 2回rejected → 老中にエスカレーション（R7発動）

お針子 rejected_judgment (9点以下)
  │
  ▼ 即座に老中にエスカレーション（自動ループ禁止）
  │  理由: 根本的問題は足軽だけでは解決できない
```

**DIAGNOSE/RECORDの効果**: 単なるretry-loopではなく、失敗パターンの蓄積による予防的改善。
「なぜ失敗したか」のカテゴリ分布が可視化され、instructions改善やfew-shot例の追加判断材料になる。

**CCAのエスカレーション判定基準との整合**:
- 有効トリガー: 進展不能（2回rejected） → ◎
- 無効トリガー: 自己申告confidence → ✗（お針子のスコアは客観的）

**安全弁**（CCA + 外部事例の知見を統合）:
- `rejected_trivial`のみ自動ループ対象（typo修正レベル）
- `rejected_judgment`は**必ず老中を経由**（設計判断が必要）— 外部事例の「人間介入はセキュリティレビュー+マージ承認のみ」に相当
- ループ回数上限2回（無限ループ防止）— 外部事例の「無限ループ時のみ手綱」を構造化した閾値
- 老中へのcc通知は全件（visibility確保）
- **スコア悪化検知**: 再監査でスコアが前回より下がった場合、残り回数に関わらず即エスカレーション（修正が逆効果のケース）

**依存**: ⑤severity calibrationが先行すべき（判定精度が低いまま自動ループは危険）

**subtask分解案（3件）**:
- S1: お針子instructions にretry-loop手順追加（rejected_trivialのみ足軽に直接send-keys）
- S2: context/karo-audit.md にエスカレーション条件・cc通知ルール追記
- S3: inbox_write.sh にretry_count追跡フィールド追加

---

### ⑤ severity calibration → **やる（Wave 9）**

**現状の強みと弱み**:

| 既存資産 | 状態 |
|---------|------|
| 15点ルーブリック（5カテゴリ×3点） | ✓ SKILL.md に定義済み |
| よくある言い訳テーブル | ✓ ohariko.md に実装済み |
| 殿の判断基準4項目 | ✓ SKILL.md に記載済み |
| **few-shot examples** | **✗ 未実装** |
| **severity境界のコード例** | **✗ 未実装** |

**CCA Domain 4の処方箋**: `few-shot examples (2-4件) が最高レバレッジ技法 — 曖昧ケースの判断理由を含めよ`

**実装案**:
- SKILL.md の Step 5（ルーブリック採点）に **3件のfew-shot examples** を追加:
  1. **14/15 合格例**: 典型的な実装タスク。全カテゴリ3点、tests のみ2点（テストにwarning）。code_qualityは「動いている+読める」で3点 — **コードの美しさ・設計の洗練は減点対象外**
  2. **11/15 rejected_trivial例**: 要件は満たすがcode_quality 2点 + completeness 2点。修正箇所が明確
  3. **7/15 rejected_judgment例**: 要件未達。correctness 1点 + no_regressions 1点。根本的再実装が必要

- 各例に「**なぜこの点数か**」の判断理由を含める（CCA推奨: 曖昧ケースの判断理由）
- **「動けば合格」原則の明文化**: correctnessカテゴリの3点基準に「コードの美しさ・アーキテクチャの洗練は評価対象外。動作し、要件を満たし、既存を壊さなければ3点」と注記（外部事例: 月商300万SaaSの「完成したコードがどれだけダサくても絶対に気にしない」と同方向）

**過剰仕様化リスクの制御**:
- 例は3件に限定（CCA推奨の2-4件の中間値）
- 例はshogunの実際のsubtask（過去の監査事例）から抽出
- ルーブリック本体は変更しない（例の追加のみ）

**効果**: 監査精度向上 → 誤rejected減 → 老中のR7介入機会減。④retry-loopの前提条件。

**subtask分解案（2件）**:
- S1: 過去の監査事例から3件の代表例を抽出（没日録DBのaudit_status検索）
- S2: SKILL.md Step 5 にfew-shot examples セクション追加

---

### ⑥ worktree実装 → **やる（Wave 9）**

**設計済み**: `docs/shogun/worktree_design.md`（Hybrid D + EnterWorktree A方式、3Wave/7subtask）

**CCA知見による追加検証**:

| CCA観点 | 設計との整合 | 追加修正要否 |
|---------|:-----------:|:-----------:|
| サブエージェントはコーディネーターのコンテキストを共有しない | ✓ worktree分離 | 不要 |
| fork_session: 共有ベースラインから独立ブランチ | ✓ SHOGUN_ROOT共有+ブランチ分離 | 不要 |
| parallel spawning: 複数タスクを1レスポンスで並列実行 | ✓ 足軽2名並列 | 不要 |
| PostToolUseフック: ツール結果正規化 | △ worktree CWD正規化は未設計 | **要検討** |

**追加修正1件**: SHOGUN_ROOT未設定時のPostToolUse的フォールバック
- `scripts/botsu/__init__.py` の `PROJECT_ROOT` 解決にSHOGUN_ROOT env varフォールバックを追加
- これはworktree_design.md Wave 1 subtask_1 に既に含まれている

**判定**: 設計完了済み。CCA追加修正は軽微。Wave 9で⑤と並行実施可能。

---

### ⑦ 通知システム → **やる（Wave 8）**

**Plan存在**: `~/.claude/plans/radiant-dancing-snail.md`（ntfy/Discord/Slack/MQTT 4バックエンド）

**CCA知見との接点**: 低い。通知はCCA 5ドメインのいずれにも直接対応しない。

**やる理由**:
1. 実装コストが極めて低い（1ファイル新規 + 既存2行追加）
2. Plan完成済みで設計不要
3. 老中のdashboard更新（R5）を外部から確認可能に — 人間（殿）の待ち時間削減
4. 他6件と**完全に独立** — 並列実装可能

**追加コスト**: ntfy.sh は無料。セルフホストも可能。月額ゼロ。

**subtask分解案（2件）**:
- S1: scripts/notify.py 新規作成（Plan通り）
- S2: scripts/botsunichiroku.py に_try_notify追加

### ⑧ ヘルスチェック（Silent Skill Degradation検知） → **やる（Wave 8）**

> Agent Skill Busの「スキルの静かな劣化検知」から着想。42エージェント規模のスコア追跡は過剰だが、
> shogunの「壊れても気づかない」盲点は実在する。

**shogunの「静かに壊れる」リスク一覧**:

| コンポーネント | 壊れ方 | 影響範囲 | 現状の検知 |
|--------------|--------|---------|-----------|
| Memory MCP | サーバープロセス停止 | 全エージェントの永続記憶消失 | **なし** |
| 高札API (localhost:8080) | Dockerコンテナ停止 | 16エンドポイント全滅 | **なし** |
| Notion MCP | API key失効 | project管理不能 | **なし** |
| inbox YAML | フォーマット破損 | エージェント間通信断絶 | **なし** |
| 没日録DB | ファイル破損/ロック | 全データ消失 | **なし** |

**実装案 — 最小ヘルスチェックスクリプト `scripts/healthcheck.sh`**:

```bash
#!/bin/bash
# 老中セッション開始時 or identity_inject.sh から呼び出し
# 各コンポーネントの生存確認。異常時は警告表示のみ（ブロックしない）

CHECKS=0; FAILS=0

# 1. Memory MCP応答確認
# 2. 高札API ping (curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
# 3. inbox YAML構文チェック (python3 -c "import yaml; yaml.safe_load(open(...))")
# 4. 没日録DB整合性 (sqlite3 data/botsunichiroku.db "PRAGMA integrity_check")

echo "HealthCheck: $((CHECKS-FAILS))/$CHECKS passed"
# FAILS > 0 → 警告色で表示（作業は続行可能）
```

**Agent Skill Busとの差分**:
- Agent Skill Bus: スコア追跡+15%低下アラート+自動修復 → **過剰**（42エージェント向け）
- shogun: 起動時バイナリチェック+警告表示 → **最小**（5-7エージェント向け）

**コスト**: 1スクリプト新規（30行程度）。identity_inject.shに1行追加。

**subtask分解案（2件）**:
- S1: scripts/healthcheck.sh 新規作成（4コンポーネントチェック）
- S2: scripts/identity_inject.sh にhealthcheck呼び出し追加

---

## 4. 依存関係グラフ

```
  ⑤ severity calibration ──→ ④ validation-retry loop（DIAGNOSE+RECORD強化）
                                    │
                                    ▼
                              老中R4+R7自動化

  ⑥ worktree ──→（独立、並列可能）

  ③ trimming ──→（独立、即実施可能）

  ⑦ notify ──→（独立、即実施可能）

  ⑧ healthcheck ──→（独立、即実施可能。③⑦と並列）

  ② rules ──→ ⑥ worktree後に再検討

  ① hub-spoke ──→ ③④⑤⑥⑧の効果測定後に再評価

  [将来] DAG自動dispatch ──→ Wave 8-10完了後に再評価
  [将来] Knowledge Watcher ──→ 獏の夢見拡張で段階的カバー
```

**クリティカルパス**: ⑤ → ④（severity calibrationが不正確なまま自動retry-loopを回すと、正しい成果物を不当にrejectedし続ける危険）

---

## 5. Wave分解案

### Wave 8（即実施 — Quick Wins）

| # | subtask | 改善候補 | 並列可能 | 工数目安 |
|---|---------|---------|:--------:|---------|
| 1 | inbox_write.sh summary長バリデーション | ③trimming | ✓ | 軽（10行） |
| 2 | karo-yaml-format.md 受信時トリムルール | ③trimming | ✓ | 軽（文書） |
| 3 | scripts/notify.py 新規作成 | ⑦notify | ✓ | 中（Plan通り） |
| 4 | botsunichiroku.py _try_notify追加 | ⑦notify | S3後 | 軽（2行） |
| 5 | scripts/healthcheck.sh 新規作成 | ⑧healthchk | ✓ | 軽（30行） |
| 6 | identity_inject.sh にhealthcheck呼び出し追加 | ⑧healthchk | S5後 | 軽（1行） |

**Wave 8の効果**: 老中R3軽減 + 人間の外部監視可能化 + 静かな障害の早期発見。リスクゼロ。

### Wave 9（コア改善 — 並列2系統）

| # | subtask | 改善候補 | 依存 | 工数目安 |
|---|---------|---------|------|---------|
| 7 | 過去監査事例3件抽出 | ⑤calibration | なし | 軽（DB検索） |
| 8 | SKILL.md few-shot examples追加 | ⑤calibration | S7後 | 中（文書） |
| 9 | worktree Wave 1（SHOGUN_ROOT + botsu修正） | ⑥worktree | なし | 中 |
| 10 | worktree Wave 2（ashigaru instructions） | ⑥worktree | S9後 | 中 |

**Wave 9の効果**: 監査精度向上 + 衝突ゼロ並列作業。④retry-loopの前提条件充足。

### Wave 10（自動化 — ⑤完了が前提）

| # | subtask | 改善候補 | 依存 | 工数目安 |
|---|---------|---------|------|---------|
| 11 | お針子instructions retry-loop手順追加（DIAGNOSE付き） | ④retry | Wave 9完了 | 中 |
| 12 | karo-audit.md エスカレーション条件追記 | ④retry | S11と並列 | 軽 |
| 13 | inbox_write.sh retry_count + failure_category追跡 | ④retry | S11と並列 | 軽 |
| 14 | 没日録CLIにaudit-history記録機能追加（RECORD） | ④retry | S11後 | 中 |

**Wave 10の効果**: 老中R4+R7の自動化 + 失敗パターン蓄積による予防的改善。最大のkaro負荷削減。

### 再評価ポイント（Wave 10完了後）

| 候補 | 再評価条件 |
|------|-----------|
| ① hub-spoke | Wave 8-10完了後、老中過負荷が解消されたか測定。解消されていれば不要 |
| ② rules | worktree導入後にPROJECT_ROOT問題が頻発するなら実施 |
| DAG自動dispatch | Wave 10完了後、老中R2（手動依存解決）が主要ボトルネックなら実施 |
| Knowledge Watcher | 獏の夢見拡張（高札v2 dream.py）で段階的にカバー。単独実装は不要 |

---

## 6. 総括 — 「老中を殺すな」への回答

**やらない**: ① hub-and-spoke純化（過剰手術。原因は構造ではなく認知負荷）
**後回し**: ② path-specific rules（ROI不足）、DAG自動dispatch（実装コスト高）、Knowledge Watcher（獏で代替）
**やる（3 Wave / 8候補中6件採用）**:
- Wave 8: ③ trimming + ⑦ notify + ⑧ healthcheck（即効・低リスク・6subtask）
- Wave 9: ⑤ calibration + ⑥ worktree（コア改善・並列可能・4subtask）
- Wave 10: ④ retry-loop + DIAGNOSE/RECORD（最大効果・⑤が前提・4subtask）

**追加コスト**: ゼロ（全てローカル実装、外部サービス課金なし）

**老中負荷の期待削減**:
- Wave 8後: R3（報告受理）の認知負荷 **-30%**、静かな障害の検知率 **0% → 80%**
- Wave 9後: 衝突割込み **-80%**、誤rejected **-50%**
- Wave 10後: R4+R7（監査管理+再割当） **-70%**（rejected_trivialの手動介入がゼロに）+ 失敗パターン蓄積による予防的改善

**外部事例との整合**:
- 月商300万SaaSソロ運用: 「エラー→AI修正→人間承認」= ④retry-loop + ⑤calibrationの方向性を裏付け
- 42エージェントAgent Skill Bus: 「静かな劣化検知」= ⑧healthcheck、「DIAGNOSE+RECORD」= ④の設計補強

> ふむ、この戦場の構造を見るに……老中殿の過負荷は「役割の設計」ではなく「雑務の堆積」が原因でござる。
> 大手術（hub-spoke再構築）は刃を研ぐ前に鞘を壊すようなもの。
> まずは研ぎ石（trimming）と油（notify）と目付（healthcheck）で手入れし、
> 次に新しい足場（worktree）と目利きの精度（calibration）を整え、
> 最後に自動の返し技（retry-loop）を仕込む — しかも今度は「なぜ負けたか」を記録する返し技だ。
> 三段の構えで、老中殿の注意力を「分解の一刀」に集中させるのが上策と心得まする。
>
> 42人の足軽を動かす他家の知恵も、300万石の一人大名の知恵も、
> 煎じ詰めれば同じことを言っておる — 「人間は判断だけに集中せよ」と。
