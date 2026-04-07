# 勘定吟味役 設計リサーチ — お針子ワークフロー分析 + スキル査定基準構造化

> **Version**: 1.0
> **Date**: 2026-02-21
> **cmd**: cmd_252 subtask_558
> **Author**: 部屋子2号（ashigaru7）

---

## §1. お針子監査ワークフロー構造化

### 1.1 監査フロー全体像

```
起動トリガー（イベント駆動、ポーリング禁止F004）
  │
  ├── [T1] 将軍からのsend-keys → 没日録全体監査
  ├── [T2] 新規cmd通知 → 未割当subtask確認・先行割当検討
  ├── [T3] 定期確認指示 → 健全性チェック
  └── [T4] 家老からの監査依頼 → 成果物品質監査
        │
        ▼
  STEP 0: 高札ヘルスチェック
        │
        ├─ OK → 高札API併用モード
        └─ NG → 従来方式フォールバック
              │
              ▼
  STEP 1-6: 品質監査パイプライン（§1.2 詳細）
        │
        ▼
  STEP 8: 次のpending監査確認 → あればSTEP 1に戻る
```

### 1.2 成果物監査ワークフロー — ステップ詳細

| Step | 名称 | 入力 | 処理 | 出力 | 判断基準 |
|------|------|------|------|------|----------|
| **0** | 高札ヘルスチェック | curl /health | HTTP応答確認 | KOUSATSU_OK / KOUSATSU_NG | status == "ok" |
| **1** | subtask詳細確認 | subtask_id | DB CLI: subtask show | description, target_path, needs_audit, audit_status | — (情報収集のみ) |
| **1.5** | 類似タスク検索 ★高札 | subtask_id | /search/similar API | 類似タスクリスト + audit_status | audit_statusで一貫性判断 |
| **1.7** | 監査傾向確認 ★高札 | worker_id | /audit/history API | 合格率・却下傾向 | approval_rate低→重点チェック |
| **2** | 報告確認 | subtask_id | DB CLI: report list | summary, files_modified | — (情報収集のみ) |
| **3** | 成果物直接閲覧 | files_modified | Read ツール | ファイル内容 | — (情報収集のみ) |
| **4** | 品質チェック | 全収集情報 | 5観点評価 | 各観点の合否 | §1.3 参照 |
| **4.5** | カバレッジ ★高札 | cmd_id | /check/coverage API | coverage_ratio | < 0.7 で警告 |
| **5** | YAML報告記録 | 判定結果 | Edit roju_ohariko.yaml | 監査報告エントリ | — (記録のみ) |
| **6** | 老中通知 | 判定 | send-keys 2回 | 通知メッセージ | — (通知のみ) |
| **8** | 次pending確認 | — | DB CLI | NEXT:subtask_id / EMPTY | audit_status == pending |

★高札 = KOUSATSU_OK時のみ実行。NG時はスキップ。

### 1.3 品質チェック5観点

| # | 観点 | チェック内容 | 判断の性質 |
|---|------|-------------|-----------|
| 1 | **完全性** | 要求内容が全て含まれているか | 指示文とのキーワード照合 + 構造理解 |
| 2 | **正確性** | 事実誤認・技術的間違いがないか | ドメイン知識による判断 |
| 3 | **書式** | フォーマット・命名規則は適切か | パターンマッチ（ルールベース可能） |
| 4 | **一貫性** | 他ドキュメント・コードとの整合性 | 既存コードとの差分比較 |
| 5 | **横断一貫性** ★高札 | 類似タスク・傾向との整合性 | 過去事例との比較（高札API） |

### 1.4 判定3パターンの分岐条件

| result | 条件 | 具体例 | 後続処理 |
|--------|------|--------|----------|
| **approved** | 5観点全てに問題なし | コード品質OK + エビデンス充足 | 老中: audit_status=done → 戦果移動 |
| **rejected_trivial** | 自明な修正で解決 | typo, import漏れ, フォーマット崩れ | 老中: audit_status=rejected → 差し戻し |
| **rejected_judgment** | 殿の判断が必要 | 仕様変更, 数値選択, 設計判断 | 老中: dashboard「要対応」→ 殿判断 |

### 1.5 高札API連携ポイント

| Step | API | 用途 | フォールバック |
|------|-----|------|---------------|
| 0 | GET /health | 高札利用可否判定 | — (判定自体が目的) |
| 1.5 | GET /search/similar | 類似タスク自動検索 | スキップ（4観点で監査） |
| 1.7 | GET /audit/history | 担当者の監査傾向 | スキップ |
| 4.5 | GET /check/coverage | 指示vs報告のカバレッジ | スキップ |
| (全体) | GET /check/orphans | 矛盾・放置検出 | DB CLIで手動確認 |

### 1.6 HW関連タスクの追加観点

通常5観点に加え、HW関連タスクでは2観点を追加:

| 追加観点 | チェック内容 | 照合テーブル |
|---------|-------------|-------------|
| **HWエビデンス** | I2Cスキャン/MQTTログ/mpremote ls等のエビデンス有無 | 必須エビデンス表 |
| **HW設定値** | I2Cアドレス/ピン番号等が正値と一致するか | HW設定値照合テーブル（16項目） |

---

## §2. スキル候補査定ルブリック

### 2.1 採用/却下パターンの逆引き分析

dashboard.mdの全32件を分析:
- **採用**: 8件（docker-pytest-runner, frontend-backend-schema-migration, playwright-e2e-scaffold, tech-comparison-reporter, manual-ocr-extractor, manual-merge-summarizer, jupyter-exploratory-analysis, sklearn-timeseries-model, fastapi-linebot-ollama, mcp-server-scaffold-python）
- **却下**: 17件
- **保留**: 4件
- **未裁定**: 7件

### 2.2 採用基準（逆引き）

| 基準 | 重み | 根拠（採用例） |
|------|------|---------------|
| **再利用性** | 高 | 全採用スキルが2回以上の利用場面あり |
| **複雑性閾値** | 高 | 採用スキルは全て200-513行。却下の「単純すぎる」パターンに該当しない |
| **汎用性** | 高 | PJ固有でなく、異なるプロジェクトで再利用可能 |
| **独立性** | 中 | 他スキルに統合されない独自の価値がある |
| **パターン性** | 中 | 手順がテンプレート化可能（毎回異なる構成ではない） |

### 2.3 却下理由パターン

| 却下パターン | 出現数 | 具体例 |
|-------------|--------|--------|
| **単純すぎる** | 3件 | docker-compose-env-parameterize（sed/grepで済む）, sensitive-value-redaction（pre-commitで対応） |
| **PJ固有** | 5件 | csv-sensor-identification（ArSprout固有）, nodered-stage-template-generator（PJ固有） |
| **構成が毎回違う** | 4件 | telegraf-grafana-event-panel-adder, grafana-dashboard-provisioning, multi-source-data-integrator |
| **他スキルに統合** | 3件 | scipy-cross-correlation-analyzer→jupyter統合, sklearn-gbr-gridsearch→sklearn統合 |
| **スコープが狭い** | 2件 | arduino-cli-swd-flash-test（RP2350固有）, open-meteo-data-fetcher（API叩くだけ） |

### 2.4 JSON Schema形式 スキル候補評価ルブリック案

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SkillCandidateEvaluation",
  "type": "object",
  "required": ["skill_name", "proposed_by", "scores", "recommendation"],
  "properties": {
    "skill_name": {
      "type": "string",
      "description": "スキル候補名（kebab-case）"
    },
    "proposed_by": {
      "type": "string",
      "description": "提案元（worker_id + subtask_id）"
    },
    "line_count": {
      "type": "integer",
      "description": "推定行数",
      "minimum": 0
    },
    "scores": {
      "type": "object",
      "required": ["reusability", "complexity", "generality", "independence", "pattern_stability"],
      "properties": {
        "reusability": {
          "type": "integer",
          "minimum": 0, "maximum": 3,
          "description": "再利用性: 0=1回限り, 1=同PJ内2回, 2=PJ跨ぎ2回, 3=汎用(任意PJで有用)"
        },
        "complexity": {
          "type": "integer",
          "minimum": 0, "maximum": 3,
          "description": "複雑性: 0=<50行(trivial), 1=50-150行, 2=150-300行, 3=>300行"
        },
        "generality": {
          "type": "integer",
          "minimum": 0, "maximum": 3,
          "description": "汎用性: 0=特定HW/API固有, 1=特定PJ内, 2=同技術スタック内, 3=技術非依存"
        },
        "independence": {
          "type": "integer",
          "minimum": 0, "maximum": 2,
          "description": "独立性: 0=既存スキルに統合可, 1=部分重複あり, 2=完全独立"
        },
        "pattern_stability": {
          "type": "integer",
          "minimum": 0, "maximum": 2,
          "description": "パターン安定性: 0=毎回構成が異なる, 1=基本パターン+カスタマイズ, 2=テンプレート化可能"
        }
      }
    },
    "total_score": {
      "type": "integer",
      "description": "合計スコア (0-13)",
      "minimum": 0, "maximum": 13
    },
    "auto_judgment": {
      "type": "string",
      "enum": ["auto_reject", "review_needed", "auto_recommend"],
      "description": "自動判定: <=4=auto_reject, 5-8=review_needed, >=9=auto_recommend"
    },
    "rejection_pattern": {
      "type": "string",
      "enum": ["too_simple", "project_specific", "config_varies", "merged_into_other", "scope_too_narrow", "none"],
      "description": "該当する却下パターン（自動検出可能なもの）"
    },
    "recommendation": {
      "type": "string",
      "enum": ["adopt", "reject", "hold", "needs_human"],
      "description": "最終推奨（auto_judgmentを人間がオーバーライド可能）"
    },
    "rationale": {
      "type": "string",
      "description": "判断理由の自然言語説明"
    }
  }
}
```

### 2.5 スコアリング閾値

| 合計スコア | 自動判定 | 説明 |
|-----------|---------|------|
| **0-4** | auto_reject | 再利用性・複雑性・汎用性のいずれかが0で、他も低い |
| **5-8** | review_needed | 人間の判断が必要（境界領域） |
| **9-13** | auto_recommend | 高スコア、採用推奨 |

### 2.6 過去事例への適用検証

| スキル候補 | reuse | complex | general | indep | pattern | **合計** | 自動判定 | 実際の裁定 | **一致** |
|-----------|-------|---------|---------|-------|---------|---------|---------|-----------|---------|
| docker-pytest-runner | 3 | 2 | 3 | 2 | 2 | **12** | auto_recommend | ✅採用 | ✅ |
| manual-ocr-extractor | 2 | 2 | 2 | 2 | 2 | **10** | auto_recommend | ✅採用 | ✅ |
| fastapi-linebot-ollama | 2 | 3 | 2 | 2 | 2 | **11** | auto_recommend | ✅採用 | ✅ |
| docker-compose-env-parameterize | 2 | 0 | 2 | 1 | 2 | **7** | review_needed | ❌却下 | ⚠️ |
| csv-sensor-identification | 0 | 2 | 0 | 2 | 1 | **5** | review_needed | ❌却下 | ⚠️ |
| telegraf-grafana-event-panel | 1 | 2 | 1 | 1 | 0 | **5** | review_needed | ❌却下 | ⚠️ |
| scipy-cross-correlation | 2 | 1 | 2 | 0 | 2 | **7** | review_needed | ❌却下(統合) | ⚠️ |
| arduino-cli-swd-flash-test | 1 | 2 | 0 | 2 | 1 | **6** | review_needed | ❌却下 | ⚠️ |
| open-meteo-data-fetcher | 1 | 0 | 1 | 1 | 2 | **5** | review_needed | ❌却下 | ⚠️ |

**検証結果**: auto_recommend (≥9) は全て採用と一致。review_needed (5-8) は人間判断で却下されたケースが多い。
→ 閾値を「≥9=推奨、5-8=要審査、≤4=却下」で運用するのが妥当。

---

## §3. 自動化可能性マトリクス

### 3.1 監査ワークフロー × 自動化カテゴリ

| Step | 名称 | (A) LFM2.5で自動化 | (B) 大型LLM必要 | (C) 人間必須 |
|------|------|:---:|:---:|:---:|
| 0 | 高札ヘルスチェック | ✅ curl + 応答パース | — | — |
| 1 | subtask詳細確認 | ✅ DB CLI実行 + パース | — | — |
| 1.5 | 類似タスク検索 | ✅ curl + JSONパース | — | — |
| 1.7 | 監査傾向確認 | ✅ curl + 統計判定 | — | — |
| 2 | 報告確認 | ✅ DB CLI + パース | — | — |
| 3 | 成果物直接閲覧 | ✅ ファイル読み込み | — | — |
| 4a | 完全性チェック | ⚠️ キーワード照合は可 | ✅ 意味理解が必要 | — |
| 4b | 正確性チェック | — | ✅ ドメイン知識必要 | ⚠️ HW実機は人間 |
| 4c | 書式チェック | ✅ パターンマッチ | — | — |
| 4d | 一貫性チェック | ⚠️ 差分検出は可 | ✅ 意味的整合性判断 | — |
| 4e | 横断一貫性 | ✅ 高札API結果の照合 | — | — |
| 4.5 | カバレッジ | ✅ curl + ratio判定 | — | — |
| 5 | YAML報告記録 | ✅ テンプレート充填 | — | — |
| 6 | 老中通知 | ✅ send-keys送信 | — | — |
| **判定** | approved/rejected | — | ⚠️ 境界判断 | ✅ rejected_judgment |

### 3.2 スキル候補査定 × 自動化カテゴリ

| 査定項目 | (A) LFM2.5で自動化 | (B) 大型LLM必要 | (C) 人間必須 |
|---------|:---:|:---:|:---:|
| 行数カウント | ✅ wc -l | — | — |
| 命名規則チェック | ✅ regex照合 | — | — |
| 依存関係チェック | ✅ import/require解析 | — | — |
| 類似スキル検出 | ✅ FTS5キーワード検索 | — | — |
| **complexity** スコア | ✅ 行数→スコア変換 | — | — |
| **independence** スコア | ⚠️ キーワード重複検出 | ✅ 意味的重複判断 | — |
| **reusability** スコア | — | ✅ 利用場面の推定 | ⚠️ ビジネス判断 |
| **generality** スコア | ⚠️ 技術キーワードで推定 | ✅ PJ横断性の判断 | — |
| **pattern_stability** | — | ✅ テンプレート化可能性 | — |
| rejection_pattern検出 | ✅ ルールベース | — | — |
| auto_judgment算出 | ✅ スコア合計→閾値判定 | — | — |
| **最終 adopt/reject** | — | — | ✅ 殿の判断 |

### 3.3 自動化率サマリ

| 業務領域 | (A) 自動化可能 | (B) 大型LLM | (C) 人間必須 | 自動化率(A) |
|---------|:---:|:---:|:---:|:---:|
| 監査ワークフロー（情報収集） | 10/15 steps | 0 | 0 | **67%** |
| 監査ワークフロー（品質判定） | 2/5 観点 | 2/5 | 1/5 | **40%** |
| スキル候補査定（スコアリング） | 5/11 項目 | 4/11 | 2/11 | **45%** |
| 全体平均 | — | — | — | **~50%** |

### 3.4 LFM2.5 (1.2B) の適用可能範囲

LFM2.5の能力制約を踏まえた実装可能性:

| 能力 | LFM2.5の実力 | 適用可否 |
|------|-------------|---------|
| JSON出力 | ✅ tool calling実証済み | 構造化レポート出力に使える |
| 日本語理解 | ⚠️ 中国語混入あり（言語混交問題） | system promptで強制。品質は限定的 |
| コード理解 | ❌ 1.2Bでは深いロジック理解不可 | 正確性チェックには不向き |
| パターンマッチ | ✅ チェックリスト照合程度は可能 | 完全性・書式チェックに使える |
| 数値比較 | ✅ 閾値判定は可能 | スコアリング・カバレッジ判定に使える |
| テキスト要約 | ⚠️ 品質にばらつき | 監査サマリ生成は大型LLM推奨 |

---

## §4. 先行割当の自動化分析

### 4.1 先行割当ワークフロー構造化

| Step | 処理 | 入力 | 出力 | 自動化 |
|------|------|------|------|--------|
| 1 | idle足軽検出 | タスクYAML全件 | idle worker リスト | **(A)** grep/parse |
| 2 | 未割当subtask検出 | 没日録DB | unassigned subtask リスト | **(A)** DB CLI |
| 3a | 足軽パフォーマンス確認 | worker_id | stats (top_project, rate) | **(A)** 高札API |
| 3b | 類似タスク完了者確認 | subtask_id | 類似タスク worker リスト | **(A)** 高札API |
| **マッチング** | 最適worker選定 | 3a+3b結果 | 割当先worker_id | **(A)** 優先順位ルール |
| 4 | YAML inbox記録 | 割当結果 | ohariko.yaml更新 | **(A)** テンプレート充填 |
| 5 | 足軽send-keys | worker_id | 起動通知 | **(A)** send-keys |
| 6 | 老中報告 | 割当結果 | 通知メッセージ | **(A)** send-keys |

### 4.2 先行割当の自動化可能性

**結論: 先行割当は90%以上自動化可能**

3条件（idle worker存在 + 未割当subtask存在 + 新規cmd非作成）の全てがルールベースで判定可能。
最適worker選定も高札APIの統計データ + 優先順位ルール（§1 PJ一致+高合格率 > §2 類似タスク経験 > §3 高速完了）で機械的に決定できる。

### 4.3 ワーカー適性判断の自動化

| 判断基準 | データ源 | 自動化 | 備考 |
|---------|---------|--------|------|
| PJ一致 | worker/stats → top_project | **(A)** 文字列一致 | 最も信頼性高い |
| 合格率 | audit/history → approval_rate | **(A)** 数値比較 | 低合格率workerは除外 |
| 完了速度 | worker/stats → avg_completion_hours | **(A)** 数値比較 | 速い=経験豊富 |
| 類似タスク経験 | search/similar → worker_id | **(A)** リスト照合 | |
| **技術スキル適合** | — | **(C)** 人間判断 | 新技術のタスクは判断不可 |

---

## §5. 勘定吟味役が担うべき業務範囲の推奨案

### 5.1 設計思想

勘定吟味役（kanjou ginmiyaku）= LFM2.5 (1.2B) ベースの軽量自動監査エージェント。
お針子（Claude, ツンデレ監査官）の業務のうち、**機械的に判定可能な工程を自動化**し、
お針子をより高度な判断に集中させる。

```
┌─────────────────────────────────────────────────┐
│  勘定吟味役（LFM2.5 1.2B）の守備範囲            │
│                                                   │
│  ■ 情報収集の完全自動化                           │
│    - DB CLI / 高札API の全呼び出し                │
│    - ファイル読み込み                              │
│    - 類似タスク検索・統計取得                      │
│                                                   │
│  ■ 形式チェックの自動化                           │
│    - 書式チェック（パターンマッチ）                │
│    - カバレッジ比率の算出                          │
│    - orphans検出（矛盾・放置）                    │
│    - HW設定値照合（テーブル照合）                  │
│    - MQTTログ値範囲チェック                        │
│                                                   │
│  ■ スキル候補の事前スコアリング                    │
│    - 行数カウント → complexity                    │
│    - 命名規則チェック                              │
│    - 依存関係解析                                  │
│    - 類似スキル検出                                │
│    - rejection_pattern自動判定                     │
│    - auto_judgment算出（合計スコア→閾値）          │
│                                                   │
│  ■ 先行割当の自動化                               │
│    - idle worker検出                               │
│    - 未割当subtask検出                             │
│    - 最適workerマッチング                          │
│    - YAML記録 + send-keys通知                      │
│                                                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  お針子（Claude）に残る業務                       │
│                                                   │
│  ■ 品質の意味的判断                               │
│    - 完全性チェック（意味理解が必要な部分）        │
│    - 正確性チェック（ドメイン知識による判断）      │
│    - 一貫性チェック（意味的整合性）                │
│    - rejected_judgment の判定                      │
│                                                   │
│  ■ 高度な分析                                     │
│    - ボトルネック予測                              │
│    - 新技術タスクの適性判断                        │
│    - スキル候補のreusability/generality評価        │
│                                                   │
│  ■ 最終判定                                       │
│    - approved / rejected の最終判断                │
│    - 監査報告の文面作成（ツンデレ口調含む）        │
│                                                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  殿（人間）に残る判断                             │
│                                                   │
│  ■ rejected_judgment案件の最終裁定                │
│  ■ スキル候補の最終採用/却下判断                  │
│  ■ 優先度の決定                                   │
│  ■ ビジネス判断（コスト/価値/方針）               │
│                                                   │
└─────────────────────────────────────────────────┘
```

### 5.2 勘定吟味役の動作モデル

```
【入力】
  家老からの監査依頼 (send-keys or YAML)
    │
    ▼
【Phase 1: 自動情報収集】（LFM2.5で完全自動化）
  - DB CLIでsubtask詳細/報告取得
  - 高札APIで類似タスク/監査傾向/カバレッジ取得
  - 成果物ファイル読み込み
  - HW設定値照合（該当する場合）
    │
    ▼
【Phase 2: 形式チェック】（LFM2.5で自動化）
  - 書式チェック（命名規則、Markdown構造）
  - 数値範囲チェック
  - 必須フィールド存在確認
  - カバレッジ比率判定
  - rejection_pattern検出（スキル候補の場合）
    │
    ▼
【Phase 3: レポート生成】（LFM2.5で自動化）
  - 収集情報 + 形式チェック結果を構造化JSON出力
  - auto_judgment算出（スキル候補の場合）
  - pre_verdict: "likely_approved" / "needs_review" / "likely_rejected"
    │
    ▼
【Phase 4: お針子に引き渡し】
  - 構造化レポートをお針子のプロンプトに注入
  - お針子は意味的判断のみに集中
  - 最終 approved / rejected / rejected_judgment を決定
```

### 5.3 期待効果

| 指標 | 現状（お針子単独） | 勘定吟味役導入後 |
|------|-------------------|-----------------|
| 監査1件あたりのお針子トークン消費 | ~3,000-5,000 | ~1,000-2,000（情報収集分を削減） |
| 監査1件あたりの時間 | 3-5分 | 1-2分（お針子）+ 数秒（勘定吟味役） |
| 形式チェックの見落とし | 人間レベル | 0（ルールベースなので漏れなし） |
| スキル候補のスクリーニング | 全件お針子が評価 | auto_reject/recommend で半数を自動処理 |
| 先行割当の応答速度 | お針子起動待ち | 即座（常駐デーモン） |

### 5.4 実装上の注意点

1. **LFM2.5の限界を前提とした設計**: 意味的判断は一切させない。構造化データの変換・比較・閾値判定のみ
2. **フォールバック必須**: 勘定吟味役がダウンしてもお針子単独で100%監査可能（現行と同じ）
3. **判断の透明性**: 勘定吟味役の出力は全てJSON構造化。お針子がオーバーライド可能
4. **段階的導入**: Phase 1（情報収集自動化）→ Phase 2（形式チェック）→ Phase 3（スキル査定）→ Phase 4（先行割当）
5. **言語混交問題**: LFM2.5は日本語出力に中国語が混入する既知問題あり。出力はJSON構造化で回避（自然言語生成はさせない）

---

## 参照ドキュメント

| ドキュメント | パス | 関連 |
|------------|------|------|
| お針子指示書 v2.2 | instructions/ohariko.md | §1 ワークフロー全体 |
| ダッシュボード | dashboard.md | §2 スキル候補一覧 |
| 没日録CLI | scripts/botsunichiroku.py | §1 DB操作 |
| 高札API（Docker） | ooku:agents.3 (localhost:8080) | §1 API連携 |
| LFM2.5実測 | uecs-ccm-llama-poc/config/config.example.yaml | §3 モデル能力 |
