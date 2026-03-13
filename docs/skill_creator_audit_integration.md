# skill-creator 監査ツール統合設計書

> **cmd**: cmd_281 / subtask_638
> **作成日**: 2026-02-28
> **作成者**: 部屋子1号 (ashigaru6)
> **ステータス**: Phase 2 統合設計書（Wave 1 調査A・B 統合版）
> **入力文書**:
>   - report_id:538 — skill-creator全体解析（部屋子1号 subtask_636）
>   - report_id:539 — 既存監査体制分析（部屋子2号 subtask_637）

---

## §1. エグゼクティブサマリ

### 1.1 目的

skill-creator の評価ツール群（grader / comparator / analyzer / aggregate_benchmark / eval-viewer）を、shogun システムの監査体制（お針子＋勘定吟味役）に統合する。これにより、現在定性的な品質チェックを**定量スコアリング**に進化させ、監査の再現性・客観性・トレーサビリティを飛躍的に向上させる。

### 1.2 期待効果

| 指標 | 現状 | 導入後 | 改善率 |
|------|------|--------|--------|
| 品質判定の再現性 | コンテキスト依存（変動あり） | ルーブリック0-3点×5観点（固定基準） | 大幅向上 |
| 監査結果の粒度 | 3値（approved/rejected_trivial/rejected_judgment） | 4段階+観点別スコア（15点満点） | 4倍 |
| 足軽の弱点可視化 | 合格率のみ | 観点別スコア推移（完全性/正確性/書式/一貫性/横断） | 5倍 |
| 内部vs外部監査の比較 | なし | ブラインド比較+乖離パターン分析 | 新規 |
| 監査品質の経年トレンド | なし | benchmark.json蓄積による統計追跡 | 新規 |

### 1.3 制約

- **マクガイバー精神**: skill-creator丸ごとは使わない。必要な部品だけ抜いて使う
- **既存ワークフロー非破壊**: 3パターン分岐（approved/rejected_trivial/rejected_judgment）は維持
- **DB書き込み権限**: 家老のみ（変更なし）
- **お針子ペルソナ**: ツンデレ維持（殿の勅命）
- **フォールバック保証**: 新ツールがダウンしても現行方式で100%監査可能

---

## §2. 現状の監査フローと課題

### 2.1 お針子ワークフロー全体像（v2.1）

```
STEP 0: 高札ヘルスチェック
  ↓
STEP 1: subtask詳細確認（DB CLI）
STEP 1.5: 類似タスク自動検索（高札API）
STEP 1.7: 担当足軽の監査傾向確認（高札API）
  ↓
STEP 2: 足軽報告確認（DB CLI）
STEP 3: 成果物ファイル直読（Read）
  ↓
STEP 4: 品質チェック（5観点: 完全性・正確性・書式・一貫性・横断一貫性）
STEP 4.5: カバレッジチェック（高札API、cmd全subtask完了時）
  ↓
STEP 5: YAML報告記録（roju_ohariko.yaml）
STEP 6: 老中にsend-keys通知
STEP 8: 次pending確認→連続処理
```

### 2.2 勘定吟味役の3層モデル（設計済み・未実装）

```
Layer 1: 勘定吟味役（CrewAI + Qwen2.5-Coder-1.5B）
  → 情報収集・形式チェック・スコアリング（コスト無料）
Layer 2: お針子（Claude Sonnet 4.6）
  → 意味的判断・最終判定（API課金）
Layer 3: 殿（人間）
  → rejected_judgmentの最終裁定
```

CrewAI Agent構成:
- **FormatChecker**: 命名規則・Markdown構造・必須フィールド形式違反検出
- **ChecklistVerifier**: 指示書全項目カバレッジ確認・比率算出
- **SkillEvaluator**: スキル候補5軸ルーブリックスコアリング（条件付き）

### 2.3 課題5点

#### 課題1: 定量化不足
- 品質チェック5観点が定性的（Yes/No二値のみ、スコアリング基準なし）
- 監査結果が3値のみ（条件付き合格の中間状態がない）
- 足軽の観点別弱点分析不可（合格率のみで観点別の弱点が見えない）
- カバレッジ閾値0.7の根拠不明

#### 課題2: 再現性なし
- お針子の意味的判断がコンテキスト状態で変動
- 横断一貫性の解釈がお針子に委ねられる
- 勘定吟味役のpre_verdict閾値定義が曖昧

#### 課題3: ボトルネック
- お針子コンテキスト消費: 監査1件あたり~3,000-5,000トークン（情報収集STEP1-3が主因）
- シリアル処理: お針子1名→キュー滞留
- 高札API依存: NG時は5観点→4観点に縮退

#### 課題4: 内部vs外部監査の比較手段なし
- お針子（内部監査）と勘定吟味役（外部監査）の判定乖離を検出・分析する仕組みがない

#### 課題5: 監査品質の経年トレンド追跡なし
- 監査の品質が改善しているのか劣化しているのか数値で追えない

---

## §3. skill-creatorツール群の概要

### 3.1 転用対象ツール一覧

skill-creator全18ファイルのうち、監査統合に転用価値の高い7部品を抽出。

| 部品 | 元の役割 | 転用難易度 | 優先度 |
|------|---------|----------|--------|
| **grader.md** | 成果物のexpectations評価 | 低（ほぼそのまま） | ★★★★★ |
| **comparator.md** | 2つの出力のブラインド比較 | 低（ほぼそのまま） | ★★★★★ |
| **analyzer.md** | 差異分析+改善提案生成 | 低（ほぼそのまま） | ★★★★★ |
| **aggregate_benchmark.py** | 複数runの統計集計 | 中（入力スキーマ調整） | ★★★★☆ |
| **eval-viewer** | 結果の可視化HTML+サーバー | 中（テーマ・フィールド調整） | ★★★★☆ |
| **run_loop.py** | eval+improve自動反復 | 高（大幅改修要） | ★★★☆☆ |
| **improve_description.py** | Extended Thinking改善案生成 | 中（プロンプト書換え） | ★★★☆☆ |

### 3.2 grader.mdの処理フロー（転用の核心）

skill-creatorのgraderは7ステップで成果物を評価する:

```
Step 1: Transcript読込
Step 2: Output検証（ファイル存在・内容確認）
Step 3: Assertion評価（expectations[{text, passed, evidence}]）
Step 4: Claims抽出（報告内容の事実検証）
Step 5: User Notes確認
Step 6: Eval批評（assertions自体の品質を評価）
Step 7: 結果書込（grading.json）
```

**核心的特徴**: 表層的合格を排除（ファイル名だけでなく内容も検証）、Eval自体を批評する機能

### 3.3 comparator.mdの処理フロー

```
Step 1: 両Output読込
Step 2: タスク理解
Step 3: Rubric生成（Content: correctness/completeness/accuracy + Structure: organization/formatting/usability）
Step 4: スコアリング（各項目1-5点）
Step 5: Assertion確認
Step 6: Winner決定
Step 7: 結果書込（comparison.json）
```

**核心的特徴**: ブラインド（どちらがどのスキルか知らない）、Content+Structureの2軸評価

### 3.4 主要JSON Schemaの構造

#### grading.json
```json
{
  "expectations": [{"text": "...", "passed": true/false, "evidence": "..."}],
  "summary": {"passed": N, "failed": N, "total": N, "pass_rate": 0.XX},
  "claims": [{"claim": "...", "type": "factual", "verified": true/false, "evidence": "..."}],
  "eval_feedback": {"suggestions": [...], "overall": "..."}
}
```

#### comparison.json
```json
{
  "winner": "A"/"B",
  "rubric": {"A": {"content_score": X, "structure_score": Y, "overall_score": Z}, "B": {...}},
  "output_quality": {"A": {"score": N, "strengths": [...], "weaknesses": [...]}, "B": {...}}
}
```

#### benchmark.json
```json
{
  "metadata": {"skill_name": "...", "timestamp": "..."},
  "runs": [{"eval_id": N, "configuration": "...", "result": {"pass_rate": 0.XX}}],
  "run_summary": {"with_skill": {"pass_rate": {"mean": X, "stddev": Y}}}
}
```

---

## §4. お針子への統合設計

### 4.1 grader方式の導入: STEP 4の5観点をルーブリック化

現行STEP 4の定性的5観点チェックを、grader.mdのexpectations方式に変換する。

#### expectations定義（お針子監査用）

各subtask監査時に、以下の5観点をexpectationsリストとして構成する:

```json
{
  "expectations": [
    {
      "aspect": "completeness",
      "text": "要求された内容が全て含まれている",
      "rubric": {
        "0": "50%未満のカバレッジ",
        "1": "50-70%のカバレッジ",
        "2": "70-90%のカバレッジ",
        "3": "90%以上のカバレッジ"
      }
    },
    {
      "aspect": "accuracy",
      "text": "事実誤認・技術的な間違いがない",
      "rubric": {
        "0": "致命的誤り（動作不能・データ破壊）",
        "1": "重大な誤り（機能不全）",
        "2": "軽微な誤り（動作に影響なし）",
        "3": "誤りなし"
      }
    },
    {
      "aspect": "formatting",
      "text": "フォーマット・命名規則は適切",
      "rubric": {
        "0": "3件以上の書式違反",
        "1": "2件の書式違反",
        "2": "1件の書式違反",
        "3": "違反なし"
      }
    },
    {
      "aspect": "consistency",
      "text": "他のドキュメント・コードとの整合性がある",
      "rubric": {
        "0": "重大な不整合",
        "1": "部分的な不整合",
        "2": "軽微な不整合",
        "3": "完全に整合"
      }
    },
    {
      "aspect": "cross_consistency",
      "text": "類似タスク・過去監査との横断一貫性がある",
      "rubric": {
        "0": "類似タスクと矛盾",
        "1": "部分的な差異あり",
        "2": "概ね一致",
        "3": "完全一致"
      }
    }
  ]
}
```

### 4.2 スコアリング: 5観点×0-3点=15点満点

#### 4段階判定閾値

| 合計スコア | 判定 | YAML result | 家老の対応 |
|-----------|------|------------|----------|
| **≥12点** | 合格 | `approved` | audit_status=done、戦果移動・次タスク進行 |
| **8-11点** | 条件付き合格 | `conditional_approved` | 軽微指摘あり。老中判断で進行可 |
| **5-7点** | 要修正（自明） | `rejected_trivial` | audit_status=rejected、足軽に差し戻し |
| **≤4点** | 要修正（判断必要） | `rejected_judgment` | audit_status=rejected、dashboard要対応 |

**注意**: `conditional_approved`は新設の4段階目。既存の3パターン分岐との後方互換のため、老中は`conditional_approved`を従来の`approved`と同等に扱ってもよい（findings付き合格として処理）。

#### 高札NG時の縮退

横断一貫性（cross_consistency）を除く4観点×0-3点=12点満点で判定:
- ≥10点: approved
- 7-9点: conditional_approved
- 4-6点: rejected_trivial
- ≤3点: rejected_judgment

### 4.3 grading.json互換出力

お針子の監査結果をgrading.json互換フォーマットで保存する。

```json
{
  "subtask_id": "subtask_XXX",
  "auditor": "ohariko",
  "timestamp": "2026-02-28T12:00:00",
  "expectations": [
    {
      "aspect": "completeness",
      "text": "要求された内容が全て含まれている",
      "score": 3,
      "passed": true,
      "evidence": "指示書の6項目全てが報告に含まれている"
    },
    {
      "aspect": "accuracy",
      "text": "事実誤認・技術的な間違いがない",
      "score": 2,
      "passed": true,
      "evidence": "行234のポート番号が8080ではなく8081だが動作に影響なし"
    }
  ],
  "summary": {
    "total_score": 12,
    "max_score": 15,
    "score_rate": 0.80,
    "verdict": "approved",
    "aspects": {
      "completeness": 3,
      "accuracy": 2,
      "formatting": 3,
      "consistency": 2,
      "cross_consistency": 2
    }
  },
  "claims": [
    {
      "claim": "全8ファイルを修正した",
      "type": "factual",
      "verified": true,
      "evidence": "git diff --stat で8ファイルの変更を確認"
    }
  ]
}
```

### 4.4 claims検証: 足軽reportの事実検証

grader.mdのclaims機能を活用し、足軽報告の内容を事実検証する:

1. 足軽報告の`summary`と`notes`から事実主張（claims）を抽出
2. 成果物ファイルの直読（STEP 3）で各claimを検証
3. `verified: false`のclaimがあれば、findingsに`[検証]`プレフィックスで記載

```yaml
findings:
  - "[検証] 足軽報告「全8ファイル修正」→ git diffで確認: 7ファイルのみ。1ファイル未修正"
```

### 4.5 改修後のお針子STEP 4フロー

```
STEP 4（改修後）:
  4a: expectations生成（subtask descriptionから5観点の検証項目を生成）
  4b: 各expectationに0-3点スコアリング + evidence記入
  4c: claims抽出・検証
  4d: 合計スコア算出 → 4段階判定
  4e: grading.json互換出力を生成
  4f: grading.jsonを高札APIにPOST（蓄積用）
```

---

## §5. 勘定吟味役への統合設計

### 5.1 blind comparison: お針子 vs 勘定吟味役

comparator.mdの仕組みを活用し、お針子と勘定吟味役の監査結果をブラインド比較する。

#### 比較フロー

```
同一subtaskに対して:
  ┌─────────────────┐     ┌─────────────────┐
  │ お針子（Layer 2）  │     │ 勘定吟味役（Layer 1）│
  │ grading.json (A) │     │ grading.json (B) │
  └────────┬────────┘     └────────┬────────┘
           │                       │
           ▼                       ▼
  ┌───────────────────────────────────────┐
  │ comparator（ブラインド比較）             │
  │ A/Bのラベルをランダム化                  │
  │ 同一expectations に対する採点比較        │
  │ Content + Structure 2軸評価             │
  └───────────────────┬───────────────────┘
                      │
                      ▼
              comparison.json
```

#### comparison.json出力（監査統合版）

```json
{
  "subtask_id": "subtask_XXX",
  "winner": "A",
  "reasoning": "Aは全5観点でevidenceが具体的。Bは完全性の判断根拠が曖昧",
  "rubric": {
    "A": {
      "content_score": 4.3,
      "structure_score": 4.0,
      "overall_score": 8.3
    },
    "B": {
      "content_score": 3.0,
      "structure_score": 3.7,
      "overall_score": 6.7
    }
  },
  "aspect_divergence": {
    "completeness": {"A": 3, "B": 2, "delta": 1},
    "accuracy": {"A": 2, "B": 2, "delta": 0},
    "formatting": {"A": 3, "B": 3, "delta": 0},
    "consistency": {"A": 2, "B": 1, "delta": 1},
    "cross_consistency": {"A": 2, "B": null, "delta": null}
  }
}
```

### 5.2 analyzer: 乖離パターンの分析

analyzer.mdのPost-hoc Analysis機能を活用し、お針子と勘定吟味役の判定乖離を分析する。

#### 分析対象

| 分析軸 | 内容 |
|--------|------|
| **観点別乖離** | どの観点でスコア差が大きいか（例: 正確性で常に勘定吟味役が甘い） |
| **足軽別乖離** | 特定足軽の成果物で乖離が大きいか |
| **プロジェクト別乖離** | 特定PJで乖離傾向があるか |
| **時系列乖離** | 乖離が収束しているか拡大しているか |

#### analysis.json出力（監査統合版）

```json
{
  "period": "2026-02-01 to 2026-02-28",
  "total_comparisons": 15,
  "agreement_rate": 0.73,
  "winner_distribution": {"ohariko": 8, "ginmiyaku": 4, "tie": 3},
  "divergence_patterns": [
    {
      "pattern": "accuracy_leniency",
      "description": "勘定吟味役は正確性判定が甘い傾向（平均+0.8点）",
      "frequency": 0.6,
      "affected_aspects": ["accuracy"]
    }
  ],
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "rubric_calibration",
      "suggestion": "勘定吟味役の正確性ルーブリックに具体例を追加",
      "expected_impact": "accuracy乖離を0.8→0.3に縮小"
    }
  ]
}
```

### 5.3 精度改善ループ

```
監査実施 → grading.json蓄積 → comparison → analysis
                                                 │
                      ┌──────────────────────────┘
                      ▼
           improvement_suggestions
                      │
                      ▼
           ルーブリック/プロンプト改善
                      │
                      ▼
           次回監査に反映（ループ）
```

---

## §6. eval-viewer統合設計

### 6.1 監査結果の可視化ダッシュボード

eval-viewerのviewer.html（53KB SPA）をベースに、監査専用UIを構築する。

#### 2タブ構成

| タブ | 内容 | 元のviewer機能 |
|------|------|--------------|
| **Audits** | subtask単位の監査結果レビュー | Outputsタブ（per-run feedback） |
| **Benchmark** | 監査品質のトレンド・統計 | Benchmarkタブ（config別stats） |

### 6.2 Auditsタブの機能

```
┌─────────────────────────────────────────────────────┐
│ Audits                                     Benchmark │
├─────────────────────────────────────────────────────┤
│                                                      │
│ subtask_638 (ashigaru6) — cmd_281             ← →   │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Score: 12/15 (80%) — approved                    │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ completeness:  ███████████░ 3/3                  │ │
│ │ accuracy:      ████████░░░ 2/3                   │ │
│ │ formatting:    ███████████░ 3/3                  │ │
│ │ consistency:   ████████░░░ 2/3                   │ │
│ │ cross_consist: ████████░░░ 2/3                   │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ Evidence:                                        │ │
│ │ • completeness: 指示書の6項目全て含まれている      │ │
│ │ • accuracy: 行234のポート番号8081は軽微            │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ Claims:                                          │ │
│ │ ✓ 全8ファイル修正 → verified                     │ │
│ │ ✗ テスト全パス → 1件failing                       │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ ┌ Ohariko vs Ginmiyaku (collapsed) ─────────┐   │ │
│ │ │ Winner: Ohariko (8.3 vs 6.7)               │   │ │
│ │ │ 乖離: consistency(+1), completeness(+1)     │   │ │
│ │ └────────────────────────────────────────────┘   │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ [Feedback]  [Submit]                                 │
└─────────────────────────────────────────────────────┘
```

### 6.3 Benchmarkタブの機能

```
┌─────────────────────────────────────────────────────┐
│ Audits                                     Benchmark │
├─────────────────────────────────────────────────────┤
│                                                      │
│ Overall Quality Trend (last 30 days)                 │
│ ┌──────────────────────────────────────────────────┐ │
│ │ avg_score: 11.2/15 (74.7%)  ▲ +2.1 from prev    │ │
│ │ approval_rate: 73%          ▲ +5% from prev      │ │
│ │ comparison_agreement: 80%                         │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ Per-Worker Stats                                  │ │
│ │  ashigaru1: avg 10.5 (70%) — weakness: accuracy  │ │
│ │  ashigaru2: avg 12.1 (81%) — strength: all       │ │
│ │  ashigaru3: avg 9.8  (65%) — weakness: formatting│ │
│ │  ashigaru6: avg 11.8 (79%) — weakness: consist.  │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ Per-Aspect Trend                                  │ │
│ │  completeness:     2.5 → 2.7 → 2.8 ▲            │ │
│ │  accuracy:         2.1 → 2.0 → 2.3 ▲            │ │
│ │  formatting:       2.3 → 2.5 → 2.6 ▲            │ │
│ │  consistency:      1.9 → 2.1 → 2.2 ▲            │ │
│ │  cross_consistency: 2.0 → 2.1 → 2.0 →           │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ Analyst Notes                                     │ │
│ │ • accuracy観点がシステム全体で最弱               │ │
│ │ • ashigaru3のformatting改善傾向                   │ │
│ └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 6.4 閲覧者と用途

| 閲覧者 | 主な用途 |
|--------|---------|
| **殿** | Benchmarkタブで品質トレンド俯瞰。rejected_judgmentの根拠確認 |
| **老中** | Auditsタブで個別監査結果確認。足軽への差し戻し指示の根拠 |
| **お針子** | Benchmarkタブで自身の判定傾向確認。ルーブリック改善 |

---

## §7. ラッパースクリプト設計

### 7.1 既存スクリプトの流用可否判断

| スクリプト | 流用可否 | 理由 |
|-----------|---------|------|
| aggregate_benchmark.py | **流用（改修あり）** | 入力スキーマをshogun監査用に変換するアダプタ追加 |
| generate_review.py | **流用（改修あり）** | フィールド名・テーマ・データソースの変更 |
| viewer.html | **流用（改修あり）** | Auditsタブのフィールド追加、Benchmarkタブのworker別表示 |
| run_eval.py | **不使用** | skill descriptionトリガーテスト用。監査と無関係 |
| run_loop.py | **不使用（Phase 3で検討）** | 大幅改修が必要。Phase 0-2では不要 |
| improve_description.py | **不使用（Phase 3で検討）** | 監査プロンプト改善に転用可能だが優先度低 |
| quick_validate.py | **不使用** | SKILL.md frontmatter専用 |
| package_skill.py | **不使用** | パッケージング専用 |
| utils.py | **不使用** | SKILL.mdパース専用 |

### 7.2 新規作成が必要なスクリプト

マクガイバー精神に従い、最小限の新規スクリプトに絞る。

#### scripts/audit_grading.py — 監査スコアリングCLI

```
用途: grading.json互換ファイルの生成・蓄積・検索
I/O:
  入力: subtask_id, auditor(ohariko/ginmiyaku), aspects scores, evidence
  出力: data/audit_gradings/{subtask_id}_{auditor}.json
コマンド例:
  python3 scripts/audit_grading.py save --subtask subtask_638 --auditor ohariko \
    --completeness 3 --accuracy 2 --formatting 3 --consistency 2 --cross 2 \
    --evidence-file /tmp/evidence.json
  python3 scripts/audit_grading.py show subtask_638
  python3 scripts/audit_grading.py list --worker ashigaru1 --limit 10
  python3 scripts/audit_grading.py benchmark --period 30d
```

#### scripts/audit_compare.py — ブラインド比較CLI

```
用途: 2つのgrading.jsonを比較しcomparison.jsonを生成
I/O:
  入力: subtask_id（同一subtaskの2つのgrading.jsonを自動検索）
  出力: data/audit_comparisons/{subtask_id}_comparison.json
コマンド例:
  python3 scripts/audit_compare.py run subtask_638
  python3 scripts/audit_compare.py analyze --period 30d
```

#### scripts/audit_viewer.py — 監査ダッシュボードサーバー

```
用途: eval-viewer改修版。監査結果の可視化HTMLサーバー
I/O:
  入力: data/audit_gradings/, data/audit_comparisons/
  出力: HTTP localhost:8082（ポート番号は高札8080, ollama11434と競合回避）
コマンド例:
  python3 scripts/audit_viewer.py serve --port 8082
  python3 scripts/audit_viewer.py static --output docs/audit_report.html
```

### 7.3 ディレクトリ構成

```
data/
  ├── botsunichiroku.db          # 既存: 没日録DB
  ├── audit_gradings/            # 新規: grading.json蓄積
  │   ├── subtask_638_ohariko.json
  │   └── subtask_638_ginmiyaku.json
  └── audit_comparisons/         # 新規: comparison.json蓄積
      └── subtask_638_comparison.json

scripts/
  ├── botsunichiroku.py          # 既存: 没日録CLI
  ├── audit_grading.py           # 新規: スコアリングCLI
  ├── audit_compare.py           # 新規: 比較CLI
  └── audit_viewer.py            # 新規: ダッシュボードサーバー
```

---

## §8. 段階的導入計画

### Phase 0: grader方式のお針子STEP 4導入（最小MVP）

| 項目 | 内容 |
|------|------|
| **目標** | お針子のSTEP 4を0-3点ルーブリック化。grading.json互換出力 |
| **実装内容** | ①5観点ルーブリック定義をohariko.mdに追記 ②scripts/audit_grading.py新規作成 ③お針子STEP 4フロー改修 |
| **完了条件** | 監査3件でスコアリングが正しく動作し、grading.jsonが蓄積される |
| **変更ファイル** | instructions/ohariko.md, scripts/audit_grading.py(新規) |
| **前提条件** | なし |
| **影響範囲** | お針子のSTEP 4のみ。他エージェント・既存フローへの影響なし |
| **フォールバック** | grading.json保存失敗時は従来の3値判定で続行 |

### Phase 1: grading.json蓄積 + aggregate_benchmark導入

| 項目 | 内容 |
|------|------|
| **目標** | 蓄積されたgrading.jsonからベンチマーク統計を算出 |
| **実装内容** | ①aggregate_benchmark.pyをshogun監査用に改修 ②data/audit_gradings/のスキーマ整備 ③足軽別・観点別の統計出力 |
| **完了条件** | grading.json 10件以上でbenchmark.jsonが生成される |
| **変更ファイル** | scripts/audit_grading.py(benchmark機能追加) |
| **前提条件** | Phase 0完了、grading.json 10件以上蓄積 |

### Phase 2: comparator + analyzer導入（勘定吟味役連携）

| 項目 | 内容 |
|------|------|
| **目標** | お針子 vs 勘定吟味役のブラインド比較と乖離分析 |
| **実装内容** | ①scripts/audit_compare.py新規作成 ②勘定吟味役のgrading.json出力対応 ③analysis.json生成 |
| **完了条件** | 同一subtaskの2つのgrading.jsonから比較・分析が自動生成される |
| **変更ファイル** | scripts/audit_compare.py(新規), docs/kanjou_ginmiyaku_design.md(grading.json対応追記) |
| **前提条件** | Phase 1完了、勘定吟味役Phase 2以上が稼働 |

### Phase 3: eval-viewer統合

| 項目 | 内容 |
|------|------|
| **目標** | 監査結果の可視化ダッシュボード |
| **実装内容** | ①eval-viewerのgenerate_review.py + viewer.htmlをfork ②Audits/Benchmarkタブ実装 ③scripts/audit_viewer.py新規作成 |
| **完了条件** | localhost:8082で監査ダッシュボードが閲覧可能 |
| **変更ファイル** | scripts/audit_viewer.py(新規) |
| **前提条件** | Phase 1完了（最低限のgrading.json蓄積） |

### Phase間の依存関係

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2
  │                        │
  │                        ▼
  └──────────────────▶ Phase 3
```

Phase 0は全ての基盤。Phase 2は勘定吟味役の稼働が前提。Phase 3はPhase 1だけでも着手可能。

---

## §9. 既存ワークフローへの影響分析

### 9.1 instructions/ohariko.md の変更箇所

| 箇所 | 変更内容 | Phase |
|------|---------|-------|
| STEP 4 品質チェック | 5観点の定性チェック → 0-3点ルーブリックスコアリング | Phase 0 |
| STEP 4後に4e-4f追加 | grading.json生成 + 高札API POST | Phase 0 |
| 判定基準テーブル | 3パターン → 4段階（conditional_approved追加） | Phase 0 |
| 監査報告フォーマット | summaryにスコア記載（例: 12/15点） | Phase 0 |
| findings プレフィックス | `[検証]` プレフィックス追加（claims検証用） | Phase 0 |
| 高札NG時の縮退ルール | 4観点12点満点の閾値追記 | Phase 0 |

### 9.2 docs/kanjou_ginmiyaku_design.md の変更箇所

| 箇所 | 変更内容 | Phase |
|------|---------|-------|
| §4 Phase 3出力 | PreAuditReport JSON → grading.json互換に変更 | Phase 2 |
| §5 SkillEvaluator | 5軸ルーブリック出力をgrading.jsonのexpectationsに統合 | Phase 2 |
| §6 報告先 | grading.jsonをdata/audit_gradings/にも保存 | Phase 2 |
| §7 新Phase追加 | Phase 4.5: comparator連携追加 | Phase 2 |

### 9.3 没日録DBスキーマ変更の要否

**変更不要**。

理由:
- grading.jsonはファイルシステム（data/audit_gradings/）に蓄積する
- 没日録DBのsubtasksテーブルには既にaudit_statusカラムがあり、新カラム追加は不要
- ベンチマーク統計もファイルシステム（benchmark.json）で管理
- 高札APIに新エンドポイント追加でgrading.jsonの検索・集約を提供する選択肢はあるが、Phase 0-1の範囲外

### 9.4 後方互換性の保証

| 既存機能 | 影響 | 対策 |
|---------|------|------|
| 3パターン分岐 | conditional_approved追加 | 老中は従来approved扱いも可 |
| roju_ohariko.yaml | summaryにスコア追記 | 既存フィールドは変更なし |
| 高札API POST /audit | 変更なし | grading.jsonは別経路で保存 |
| 勘定吟味役PreAuditReport | Phase 2で形式変更 | フォールバック: 従来形式も受付可 |
| お針子のツンデレ口調 | 変更なし | スコアを伝える時もツンデレ（「12点よ。まあ悪くないんじゃない？」） |

---

## 付録A: grading.json 完全スキーマ定義（監査統合版）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuditGrading",
  "type": "object",
  "required": ["subtask_id", "auditor", "timestamp", "expectations", "summary"],
  "properties": {
    "subtask_id": {"type": "string", "pattern": "^subtask_\\d+$"},
    "cmd_id": {"type": "string", "pattern": "^cmd_\\d+$"},
    "worker_id": {"type": "string"},
    "auditor": {"type": "string", "enum": ["ohariko", "ginmiyaku"]},
    "timestamp": {"type": "string", "format": "date-time"},
    "kousatsu_ok": {"type": "boolean"},
    "expectations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["aspect", "text", "score", "passed", "evidence"],
        "properties": {
          "aspect": {"type": "string", "enum": ["completeness", "accuracy", "formatting", "consistency", "cross_consistency"]},
          "text": {"type": "string"},
          "score": {"type": "integer", "minimum": 0, "maximum": 3},
          "passed": {"type": "boolean", "description": "score >= 2 → true"},
          "evidence": {"type": "string"}
        }
      },
      "minItems": 4,
      "maxItems": 5
    },
    "summary": {
      "type": "object",
      "required": ["total_score", "max_score", "score_rate", "verdict"],
      "properties": {
        "total_score": {"type": "integer", "minimum": 0, "maximum": 15},
        "max_score": {"type": "integer", "enum": [12, 15]},
        "score_rate": {"type": "number", "minimum": 0, "maximum": 1},
        "verdict": {"type": "string", "enum": ["approved", "conditional_approved", "rejected_trivial", "rejected_judgment"]},
        "aspects": {
          "type": "object",
          "properties": {
            "completeness": {"type": "integer", "minimum": 0, "maximum": 3},
            "accuracy": {"type": "integer", "minimum": 0, "maximum": 3},
            "formatting": {"type": "integer", "minimum": 0, "maximum": 3},
            "consistency": {"type": "integer", "minimum": 0, "maximum": 3},
            "cross_consistency": {"type": "integer", "minimum": 0, "maximum": 3}
          }
        }
      }
    },
    "claims": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim", "type", "verified", "evidence"],
        "properties": {
          "claim": {"type": "string"},
          "type": {"type": "string", "enum": ["factual", "quantitative", "comparative"]},
          "verified": {"type": "boolean"},
          "evidence": {"type": "string"}
        }
      }
    }
  }
}
```

## 付録B: comparison.json 完全スキーマ定義（監査統合版）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AuditComparison",
  "type": "object",
  "required": ["subtask_id", "winner", "reasoning", "rubric", "aspect_divergence"],
  "properties": {
    "subtask_id": {"type": "string"},
    "timestamp": {"type": "string", "format": "date-time"},
    "winner": {"type": "string", "enum": ["ohariko", "ginmiyaku", "tie"]},
    "reasoning": {"type": "string"},
    "rubric": {
      "type": "object",
      "properties": {
        "ohariko": {
          "type": "object",
          "properties": {
            "content_score": {"type": "number"},
            "structure_score": {"type": "number"},
            "overall_score": {"type": "number"}
          }
        },
        "ginmiyaku": {"$ref": "#/properties/rubric/properties/ohariko"}
      }
    },
    "aspect_divergence": {
      "type": "object",
      "description": "観点別のスコア差分",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "ohariko": {"type": ["integer", "null"]},
          "ginmiyaku": {"type": ["integer", "null"]},
          "delta": {"type": ["integer", "null"]}
        }
      }
    }
  }
}
```
