# 勘定吟味役 アーキテクチャ設計書

> **cmd**: cmd_252 / subtask_559
> **作成日**: 2026-02-21
> **作成者**: 足軽1号 (ashigaru1)
> **ステータス**: Wave2 設計書（Wave1リサーチ統合版）
> **入力文書**:
>   - docs/kanjou_ginmiyaku_research_crewai.md（部屋子1号 subtask_557）
>   - docs/kanjou_ginmiyaku_research_workflow.md（部屋子2号 subtask_558）

---

## §1. エグゼクティブサマリ

### 1.1 勘定吟味役とは

**勘定吟味役（かんじょうぎんみやく）** は、CrewAI フレームワークと Qwen2.5-Coder-1.5B（ローカル LLM）を組み合わせた軽量自動監査エージェントである。お針子（Claude Code、ツンデレ監査官）が担う監査業務のうち、機械的に判定可能な工程を自動化し、お針子をより高度な意味的判断に集中させることを目的とする。

### 1.2 導入目的

| 目的 | 詳細 |
|------|------|
| **お針子のトークン消費削減** | 情報収集・形式チェックをローカル LLM に委譲。監査1件あたりのトークン消費を 50% 削減 |
| **形式チェックの自動化** | ルールベース判定によりチェック漏れを 0 件に |
| **スキル候補の自動スクリーニング** | 5軸ルーブリックによる auto_recommend / auto_reject で半数を自動処理 |
| **先行割当の高速化** | idle worker 検出・最適マッチングを常駐デーモンで即座に処理 |

### 1.3 期待効果（数値目標）

| 指標 | 現状（お針子単独） | 導入後 | 目標 |
|------|-------------------|--------|------|
| 監査1件のお針子トークン消費 | ~3,000-5,000 | ~1,000-2,000 | **50% 削減** |
| 形式チェック見落とし | 人間レベル | 0（ルールベース） | **0件** |
| スキル候補自動処理率 | 0% | ~50% | **50%以上** |
| 先行割当応答速度 | お針子起動待ち | 即座（常駐デーモン） | — |

---

## §2. アーキテクチャ全体像

### 2.1 3層モデル

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: 勘定吟味役（自動・ローカル LLM）                       │
│                                                                   │
│  CrewAI + Qwen2.5-Coder-1.5B (Ollama)                           │
│  役割: 情報収集・形式チェック・スコアリング・レポート生成          │
│  コスト: 無料（ローカル実行）                                     │
│  品質: 中〜低（意味的判断は不可）                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 構造化 JSON レポートを注入
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: お針子（意味的判断・Claude Code Agent）                  │
│                                                                   │
│  Claude Sonnet 4.6                                               │
│  役割: 意味的完全性・正確性・一貫性チェック、最終 approved/rejected │
│  コスト: API 課金                                                 │
│  品質: 高                                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ rejected_judgment のみ上申
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: 殿（最終決裁・人間）                                    │
│                                                                   │
│  役割: rejected_judgment の裁定、スキル採用/却下、優先度決定        │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 システム構成図

```
                         ┌──────────────────────────────┐
  家老 (老中)             │  勘定吟味役プロセス              │
  send-keys 起動          │                                │
  ─────────────────────▶ │  CrewAI Crew                   │
                         │  ┌────────────────────────┐   │
                         │  │ FormatChecker Agent     │   │
                         │  │ ChecklistVerifier Agent │   │
                         │  │ SkillEvaluator Agent    │   │
                         │  └────────────────────────┘   │
                         │          │                     │
                         │          ▼                     │
                         │  ┌──────────────────────────┐ │
  Ollama                 │  │ Qwen2.5-Coder-1.5B       │ │
  localhost:11434 ──────▶│  │ (コード特化小型 LLM)      │ │
                         │  └──────────────────────────┘ │
                         │          │                     │
  没日録 DB              │          ▼                     │
  data/botsunichiroku.db │  ┌──────────────────────────┐ │
  ◀ DBQueryTool ─────── │  │ ツール実行                 │ │
                         │  │ DBQueryTool              │ │
  高札API                 │  │ KousatsuAPITool           │ │
  localhost:8080         │  │ FileReadTool              │ │
  ◀ KousatsuAPITool ────│  └──────────────────────────┘ │
                         │          │                     │
                         │          ▼                     │
                         │  構造化 JSON レポート生成        │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │  お針子 (ohariko)              │
                         │  レポートをプロンプトに注入      │
                         │  意味的判断のみに集中            │
                         │  最終 approved/rejected 決定    │
                         └──────────────────────────────┘
```

### 2.3 LLM 役割分離

| LLM | 担当システム | 用途 | 理由 |
|-----|------------|------|------|
| **Qwen2.5-Coder-1.5B** | 勘定吟味役 | コードレビュー一次スクリーニング | コード特化、同サイズ帯で最高性能 |
| **LFM2.5-1.2B** | uecs-ccm-llama | 温室制御 tool calling | agentic tasks、data extraction に強い |
| **Claude Sonnet 4.6** | お針子 | 意味的判断・最終判定 | 高品質・高コスト |

**LFM2.5 ではなく Qwen2.5-Coder-1.5B を採用する理由**:
- LFM2.5 のコード訓練データは全体の **5%** のみ。Liquid AI 公式がプログラミングタスクを非推奨と明記
- Qwen2.5-Coder-1.5B は同サイズ帯でコード特化。命名規則・フォーマット・チェックリスト照合に優位
- メモリ使用量はほぼ同等（1.2B vs 1.5B）。Pi5 (8GB) でも問題なし
- LFM2.5 は温室制御 (uecs-ccm-llama) に専念させることで役割が明確になる

---

## §3. CrewAI Agent 設計

### 3.1 Agent 定義

#### Agent 1: FormatChecker

```python
from crewai import Agent, LLM

local_llm = LLM(
    model="ollama/qwen2.5-coder:1.5b",
    base_url="http://localhost:11434",
    temperature=0.1,
)

format_checker = Agent(
    role="フォーマット監査官",
    goal="成果物の命名規則・Markdown構造・必須フィールドの形式違反を検出する",
    backstory=(
        "プロジェクト規約の遵守を最重視するレビュアー。"
        "パターンに合わない記述を見逃さない。"
        "出力は必ず JSON 構造で返す。"
    ),
    tools=[FileReadTool(), DBQueryTool()],
    llm=local_llm,
    verbose=True,
    max_iter=5,
)
```

チェック内容:
- subtask_id / cmd_id / worker フィールドの存在と形式
- Markdown 見出しレベルの整合性
- skill_candidate フィールドの存在
- コミットメッセージの prefix（feat:, fix:, docs: 等）
- ファイル名命名規則（snake_case, kebab-case 等）

#### Agent 2: ChecklistVerifier

```python
checklist_verifier = Agent(
    role="チェックリスト照合官",
    goal="subtask の報告内容が指示書の全項目をカバーしているか確認し、カバレッジ比率を算出する",
    backstory=(
        "品質管理の専門家。"
        "指示書に記載された全項目が報告に反映されているか機械的に確認する。"
        "没日録 DB と高札 API を駆使して客観的なデータを収集する。"
    ),
    tools=[FileReadTool(), DBQueryTool(), KousatsuAPITool()],
    llm=local_llm,
    verbose=True,
    max_iter=5,
)
```

チェック内容:
- 没日録 DB から subtask の description を取得し、報告との照合
- 高札 API `/check/coverage` でカバレッジ比率算出（<0.7 で警告）
- 類似タスクの監査履歴確認（`/search/similar`, `/audit/history`）
- HW 関連タスクの場合: I2C スキャン / MQTT ログ等のエビデンス有無確認

#### Agent 3: SkillEvaluator

```python
skill_evaluator = Agent(
    role="スキル候補評価官",
    goal="スキル候補を5軸ルーブリックでスコアリングし、auto_judgment を算出する",
    backstory=(
        "過去の採用・却下事例を熟知した評価専門家。"
        "再利用可能性・複雑性・汎用性・独立性・パターン安定性の5軸で客観評価する。"
        "rejection_pattern を自動検出し、スコアと共に JSON で出力する。"
    ),
    tools=[FileReadTool(), DBQueryTool(), KousatsuAPITool()],
    llm=local_llm,
    verbose=True,
    max_iter=5,
)
```

スキル候補が存在する場合のみ実行（オプション Agent）。

### 3.2 Task 定義

```python
from crewai import Task

# Task 1: フォーマットチェック
format_task = Task(
    description=(
        "subtask_id={subtask_id} の成果物を確認し、以下をチェックせよ。\n"
        "1. YAML報告ファイルの必須フィールド（subtask_id, cmd_id, worker, status, summary, skill_candidate）\n"
        "2. Markdownファイルの見出し構造と命名規則\n"
        "3. コミットメッセージの prefix 形式\n"
        "結果は JSON で返せ: {{issues: [...], severity: 'ok'|'warn'|'error'}}"
    ),
    expected_output="JSON形式のフォーマットチェック結果（issues リストと severity）",
    agent=format_checker,
)

# Task 2: チェックリスト照合
checklist_task = Task(
    description=(
        "subtask_id={subtask_id} の報告が指示書の全項目を網羅しているか確認せよ。\n"
        "1. 没日録DBからsubtaskのdescriptionを取得\n"
        "2. 報告内容との照合（キーワードベース）\n"
        "3. 高札APIでカバレッジ比率を取得\n"
        "4. 担当workerの監査傾向を確認\n"
        "結果はJSON: {{coverage_ratio: float, uncovered_items: [...], pre_verdict: str}}"
    ),
    expected_output="JSON形式のチェックリスト照合結果",
    agent=checklist_verifier,
    context=[format_task],  # Task 1 の結果をコンテキストとして受け取る
)

# Task 3: スキル候補評価（条件付き）
skill_task = Task(
    description=(
        "以下のスキル候補を5軸ルーブリックでスコアリングせよ: {skill_name}\n"
        "- reusability (0-3)\n"
        "- complexity (0-3, 行数ベース)\n"
        "- generality (0-3)\n"
        "- independence (0-2)\n"
        "- pattern_stability (0-2)\n"
        "合計スコアと auto_judgment (≥10=auto_recommend, 5-9=review_needed, ≤4=auto_reject) を算出。\n"
        "rejection_pattern を検出し、JSON で返せ。"
    ),
    expected_output="JSON形式のスキル候補評価結果（SkillCandidateEvaluation スキーマ準拠）",
    agent=skill_evaluator,
    context=[format_task, checklist_task],
)
```

### 3.3 Crew 定義

```python
from crewai import Crew, Process

# スキル候補なしの場合
audit_crew = Crew(
    agents=[format_checker, checklist_verifier],
    tasks=[format_task, checklist_task],
    process=Process.sequential,
    verbose=True,
)

# スキル候補ありの場合
audit_crew_with_skill = Crew(
    agents=[format_checker, checklist_verifier, skill_evaluator],
    tasks=[format_task, checklist_task, skill_task],
    process=Process.sequential,
    verbose=True,
)

# 実行
result = audit_crew.kickoff(inputs={"subtask_id": "subtask_556"})
```

**process: sequential を採用する理由**:
- 一次スクリーニング（FormatChecker）→ 二次照合（ChecklistVerifier）の直列パイプラインに合致
- 前タスクの結果が次タスクのコンテキストに自動注入される
- Hierarchical は manager_llm に高性能 LLM が必要なため不採用

### 3.4 カスタムツール定義

#### DBQueryTool（没日録 DB 読み取り）

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import subprocess

class DBQueryInput(BaseModel):
    command: str = Field(description="botsunichiroku.py に渡すサブコマンド（例: 'subtask show subtask_556'）")

class DBQueryTool(BaseTool):
    name: str = "没日録DBクエリ"
    description: str = "没日録DB (data/botsunichiroku.db) から情報を読み取る（読み取り専用）"
    args_schema: type[BaseModel] = DBQueryInput

    def _run(self, command: str) -> str:
        result = subprocess.run(
            ["python3", "scripts/botsunichiroku.py"] + command.split(),
            capture_output=True, text=True, cwd="/home/yasu/multi-agent-shogun"
        )
        return result.stdout or result.stderr
```

#### KousatsuAPITool（高札 API クライアント）

```python
import httpx

class KousatsuAPITool(BaseTool):
    name: str = "高札API"
    description: str = "高札検索API (http://localhost:8080) でFTS5全文検索・類似タスク検索を行う"

    def _run(self, endpoint: str, params: dict = {}) -> str:
        try:
            r = httpx.get(f"http://localhost:8080{endpoint}", params=params, timeout=5)
            return r.text
        except httpx.ConnectError:
            return '{"error": "高札API接続不可。KOUSATSU_NG モードで継続"}'
```

#### FileReadTool（既存ツール流用）

```python
from crewai_tools import FileReadTool  # pip install crewai-tools
```

---

## §4. 処理パイプライン詳細

### 4.1 4Phase 構成

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 自動情報収集                                           │
│  担当: FormatChecker + ChecklistVerifier（ツール実行のみ）        │
│                                                                   │
│  - DB CLI: subtask show {subtask_id}                             │
│  - DB CLI: report list --subtask {subtask_id}                    │
│  - 高札 API: GET /health（KOUSATSU_OK/NG 判定）                  │
│  - 高札 API: GET /search/similar?subtask_id={id}（OK時のみ）      │
│  - 高札 API: GET /audit/history?worker={worker_id}（OK時のみ）    │
│  - ファイル読み込み: 報告記載の files_modified を全て読む          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 収集情報をコンテキストとして受け渡し
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 形式チェック                                           │
│  担当: FormatChecker                                              │
│                                                                   │
│  ルールベースチェック:                                            │
│  - 必須フィールド存在確認（subtask_id, cmd_id, summary 等）       │
│  - 命名規則（snake_case, kebab-case, prefix 等）                 │
│  - Markdown 見出し構造（§N. 番号付き等）                          │
│  - カバレッジ比率: GET /check/coverage → ratio < 0.7 で警告      │
│  - rejection_pattern 検出（スキル候補の場合）                    │
│                                                                   │
│  Qwen2.5-Coder 判定:                                             │
│  - パターンに当てはまらない軽微な形式違反を補完検出               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: レポート生成                                           │
│  担当: ChecklistVerifier（+ SkillEvaluator、候補ありの場合）      │
│                                                                   │
│  - 収集情報 + 形式チェック結果を構造化 JSON で出力               │
│  - auto_judgment 算出（スキル候補の場合: スコア合計→閾値判定）    │
│  - pre_verdict: "likely_approved" / "needs_review" / "likely_rejected" │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 構造化 JSON レポート
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: お針子への引き渡し                                     │
│                                                                   │
│  - 構造化 JSON レポートをお針子のプロンプトに注入               │
│  - お針子は情報収集済みの状態から意味的判断のみに集中            │
│  - 最終判定: approved / rejected / rejected_judgment を決定      │
│  - roju_ohariko.yaml に監査報告を記録                            │
│  - 老中に send-keys 通知                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 入出力 JSON Schema

#### Phase 1-2 出力（PreAuditReport）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PreAuditReport",
  "type": "object",
  "required": ["subtask_id", "format_check", "checklist_check", "pre_verdict"],
  "properties": {
    "subtask_id": { "type": "string" },
    "kousatsu_ok": { "type": "boolean", "description": "高札API接続可否" },
    "format_check": {
      "type": "object",
      "properties": {
        "issues": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "field": { "type": "string" },
              "problem": { "type": "string" },
              "severity": { "enum": ["warn", "error"] }
            }
          }
        },
        "severity": { "enum": ["ok", "warn", "error"] }
      }
    },
    "checklist_check": {
      "type": "object",
      "properties": {
        "coverage_ratio": { "type": "number", "minimum": 0, "maximum": 1 },
        "uncovered_items": { "type": "array", "items": { "type": "string" } },
        "similar_tasks": { "type": "array" },
        "worker_approval_rate": { "type": "number" }
      }
    },
    "skill_evaluation": {
      "type": "object",
      "description": "スキル候補ありの場合のみ",
      "$ref": "#/definitions/SkillCandidateEvaluation"
    },
    "pre_verdict": {
      "type": "string",
      "enum": ["likely_approved", "needs_review", "likely_rejected"]
    }
  }
}
```

#### Phase 4 入力（お針子プロンプト注入形式）

```
【勘定吟味役事前レポート】
subtask_id: {subtask_id}
高札API: {kousatsu_ok ? "利用可" : "利用不可（フォールバック）"}

■ 形式チェック結果: {severity}
{issues があれば一覧}

■ チェックリストカバレッジ: {coverage_ratio * 100:.0f}%
未言及項目: {uncovered_items}

■ スキル候補評価: {auto_judgment} (スコア: {total_score}/13)

■ 事前判定: {pre_verdict}

上記を参考に、意味的判断を実施せよ。
```

---

## §5. スキル候補査定基準

### 5.1 5軸ルーブリック

| 軸 | 配点 | 0点 | 1点 | 2点 | 3点 |
|----|------|-----|-----|-----|-----|
| **再利用性** | 0-3 | 1回限り | 同PJ内2回 | PJ跨ぎ2回 | 汎用（任意PJで有用） |
| **複雑性** | 0-3 | <50行（trivial） | 50-150行 | 150-300行 | >300行 |
| **汎用性** | 0-3 | 特定HW/API固有 | 特定PJ内 | 同技術スタック内 | 技術非依存 |
| **独立性** | 0-2 | 既存スキルに統合可 | 部分重複あり | 完全独立 | — |
| **パターン安定性** | 0-2 | 毎回構成が異なる | 基本パターン+カスタマイズ | テンプレート化可能 | — |
| **合計** | **0-13** | | | | |

### 5.2 JSON Schema（SkillCandidateEvaluation）

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
      "minimum": 0
    },
    "scores": {
      "type": "object",
      "required": ["reusability", "complexity", "generality", "independence", "pattern_stability"],
      "properties": {
        "reusability": { "type": "integer", "minimum": 0, "maximum": 3 },
        "complexity": { "type": "integer", "minimum": 0, "maximum": 3 },
        "generality": { "type": "integer", "minimum": 0, "maximum": 3 },
        "independence": { "type": "integer", "minimum": 0, "maximum": 2 },
        "pattern_stability": { "type": "integer", "minimum": 0, "maximum": 2 }
      }
    },
    "total_score": { "type": "integer", "minimum": 0, "maximum": 13 },
    "auto_judgment": {
      "type": "string",
      "enum": ["auto_reject", "needs_review", "auto_recommend"]
    },
    "rejection_pattern": {
      "type": "string",
      "enum": ["too_simple", "project_specific", "config_varies", "merged_into_other", "scope_too_narrow", "none"]
    },
    "recommendation": {
      "type": "string",
      "enum": ["adopt", "reject", "hold", "needs_human"]
    },
    "rationale": { "type": "string" }
  }
}
```

### 5.3 自動判定閾値

| 合計スコア | auto_judgment | 処理 |
|-----------|--------------|------|
| **≥ 10** | `auto_recommend` | 採用推奨として老中に報告。殿の最終判断を仰ぐ |
| **5 - 9** | `needs_review` | お針子が意味的評価を実施 |
| **≤ 4** | `auto_reject` | 却下推奨として老中に報告。殿の最終判断を仰ぐ |

### 5.4 rejection_pattern 一覧（自動検出可能）

| パターン | 検出方法 | 根拠（過去事例） |
|---------|---------|----------------|
| `too_simple` | line_count < 50 または complexity=0 | docker-compose-env-parameterize、sensitive-value-redaction |
| `project_specific` | generality=0（特定HW/API固有キーワードを含む） | csv-sensor-identification（ArSprout固有）、nodered-stage-template-generator |
| `config_varies` | pattern_stability=0 | telegraf-grafana-event-panel-adder、grafana-dashboard-provisioning |
| `merged_into_other` | 類似スキル検索で既存スキルとの高い類似度 | scipy-cross-correlation-analyzer→jupyter統合 |
| `scope_too_narrow` | generality=0 かつ independence=2（独立だが用途が限定的） | arduino-cli-swd-flash-test（RP2350固有） |
| `none` | 上記いずれにも該当しない | — |

### 5.5 過去事例への適用検証結果

| スキル候補 | reuse | complex | general | indep | pattern | **合計** | 自動判定 | 実際の裁定 | 一致 |
|-----------|-------|---------|---------|-------|---------|---------|---------|-----------|------|
| docker-pytest-runner | 3 | 2 | 3 | 2 | 2 | **12** | auto_recommend | ✅採用 | ✅ |
| manual-ocr-extractor | 2 | 2 | 2 | 2 | 2 | **10** | auto_recommend | ✅採用 | ✅ |
| fastapi-linebot-ollama | 2 | 3 | 2 | 2 | 2 | **11** | auto_recommend | ✅採用 | ✅ |
| docker-compose-env-parameterize | 2 | 0 | 2 | 1 | 2 | **7** | needs_review | ❌却下 | ⚠️ |
| arduino-cli-swd-flash-test | 1 | 2 | 0 | 2 | 1 | **6** | needs_review | ❌却下 | ⚠️ |

**考察**: auto_recommend (≥10) は採用と 100% 一致。needs_review (5-9) は人間が却下する場合が多く、ルーブリックの閾値は概ね妥当。

---

## §6. shogun 通信プロトコル統合

### 6.1 起動トリガー

**イベント駆動方式を採用（ポーリング禁止 F004 準拠）**

```
家老が以下の条件で勘定吟味役を起動:
  1. needs_audit=true の subtask が完了報告を受け取った時
  2. send-keys で勘定吟味役プロセスに監査依頼を送信
```

```bash
# 家老が勘定吟味役を起動する手順
# 【1回目】 監査対象 subtask_id をメッセージで送信
tmux send-keys -t ooku:agents.3 'audit subtask_556'
# 【2回目】 Enter を送信
tmux send-keys -t ooku:agents.3 Enter
```

### 6.2 報告先

**既存のお針子報告経路を利用**:

```
勘定吟味役の事前レポート
  → 構造化 JSON をお針子のプロンプトに注入
  → お針子が最終判定
  → roju_ohariko.yaml に監査報告を記録（既存経路と同じ）
  → send-keys で老中に通知
```

報告形式は現行の roju_ohariko.yaml 監査報告フォーマットを変更しない（後方互換）。

### 6.3 フォールバック設計

**勘定吟味役がダウンしてもお針子単独で 100% 監査可能**。

```
┌─────────────────────────────────────────┐
│  判定フロー                              │
│                                         │
│  START                                  │
│    │                                    │
│    ├─ 勘定吟味役が起動中? ──── No ──▶  お針子が単独監査（現行方式） │
│    │                                    │
│    ├─ Yes                               │
│    │    │                               │
│    │    ▼                               │
│    │  事前レポート生成（Phase 1-3）      │
│    │    │                               │
│    │    ├─ 失敗/タイムアウト ──▶ お針子が単独監査（現行方式）  │
│    │    │                               │
│    │    └─ 成功 ──▶ お針子に注入 ──▶ 最終判定  │
│                                         │
└─────────────────────────────────────────┘
```

### 6.4 tmux ペイン配置（殿の判断待ち）

現在の ookuセッション構成:

```
ookuセッション（4ペイン）
  Pane 0: ashigaru6（部屋子1）
  Pane 1: ashigaru7（部屋子2）
  Pane 2: ohariko（お針子）
  Pane 3: namazu（鯰）← 現在 Docker コンテナ、FTS5+MeCab 検索 API
```

**選択肢A: 鯰(ooku:agents.3)を転用**

| 観点 | 評価 |
|------|------|
| メリット | 新規ペイン不要。既存の4ペイン構成を維持 |
| デメリット | 高札API（鯰）と勘定吟味役が同一ペインを共有。起動衝突リスク |
| 前提条件 | 鯰の役割を「勘定吟味役 + 検索API」として統合 |

**選択肢B: 新ペインを追加**

| 観点 | 評価 |
|------|------|
| メリット | 役割が明確に分離。鯰との衝突なし |
| デメリット | ooku セッションが5ペインに拡張。CLAUDE.md の構成記載を更新必要 |
| 前提条件 | `tmux new-window` or `split-window` で追加ペイン作成 |

→ **殿の判断待ち（§9.1 参照）**

---

## §7. 段階的導入ロードマップ

### 7.1 Phase 構成（CrewAI 研究 §5.5 採用）

```
Phase 0 ────▶ Phase 1 ────▶ Phase 2 ────▶ Phase 3 ────▶ Phase 4
  Hello          Format        Checklist      Hybrid        CI/CD
  World          Checker       Verifier       Claude API    Integration
  確認           単体           DB連携          二次判定        自動化
```

### 7.2 Phase 詳細

| Phase | 名称 | 内容 | 完了条件 | 前提条件 | 見積工数 |
|-------|------|------|---------|---------|---------|
| **Phase 0** | Hello World | Ollama に Qwen2.5-Coder-1.5B をインストール。CrewAI で単純なテキスト処理を確認 | `ollama run qwen2.5-coder:1.5b` が動作し、CrewAI から呼び出せる | vx2.local または nipogi.local（殿の判断待ち §9.2） | 0.5日 |
| **Phase 1** | FormatChecker 単体 | FormatChecker Agent を実装。subtask 報告の形式チェックを自動化 | subtask 報告5件で形式チェックが正しく動作 | Phase 0 完了、チェックリスト YAML 定義 | 1日 |
| **Phase 2** | ChecklistVerifier + DB 連携 | ChecklistVerifier Agent を追加。DBQueryTool・KousatsuAPITool を実装 | 没日録 DB からの情報収集と照合が自動化される | Phase 1 完了、DBQueryTool 実装 | 1.5日 |
| **Phase 3** | ハイブリッド Claude API | SkillEvaluator Agent を追加。Phase 3: Claude API 二次判定を統合 | スキル候補の自動スクリーニングが動作する | Phase 2 完了、Claude API キー設定（§9.3） | 1日 |
| **Phase 4** | CI/CD 統合 | shogun 通信プロトコルと完全統合。家老 → 勘定吟味役 → お針子の自動パイプライン | 家老の send-keys で勘定吟味役が起動し、お針子に結果を渡せる | Phase 3 完了、tmux ペイン設定（§9.1） | 1日 |

---

## §8. リスクと制約

### 8.1 Qwen2.5-Coder の日本語制限

| リスク | 詳細 | 対策 |
|--------|------|------|
| 日本語出力品質 | 中国語が混入する可能性（LFM2.5 で確認済みの言語混交問題） | 出力を JSON 構造化に限定。自然言語生成はさせない。system prompt で「JSON のみで返せ」を強制 |
| 意味理解の限界 | 1.5B では深い意味的判断は不可 | 意味的判断はお針子に委譲。勘定吟味役はパターンマッチと数値計算のみ担当 |

### 8.2 Pi5 / nipogi のリソース競合

| リスク | 詳細 | 対策 |
|--------|------|------|
| OOM（メモリ不足） | Pi5 (8GB): Qwen2.5-Coder-1.5B は ~1GB。他モデルとの共存で圧迫 | 7B 以上は vx2.local で実行。Pi5 は 1.5B-3B に留める |
| CPU 競合 | 複数モデルが同時実行された場合の推論速度低下 | 監査と温室制御の時間帯分離（監査は深夜・早朝バッチ）または Ollama のモデル優先度設定 |

### 8.3 温室制御 LLM との共存

| リスク | 詳細 | 対策 |
|--------|------|------|
| Ollama モデル競合 | uecs-ccm-llama と勘定吟味役が同時に Ollama を使用 | LFM2.5（温室制御）と Qwen2.5-Coder（勘定吟味役）は別モデル。Ollama は逐次処理なので競合は軽微。監視が必要 |
| llama-server との分離 | uecs-ccm-llama は llama-server（port 8081）を使用。CrewAI は Ollama（port 11434）を使用 | 設計上すでに分離済み。ポート競合なし |

### 8.4 判断の透明性

| リスク | 詳細 | 対策 |
|--------|------|------|
| 勘定吟味役の判断が不透明 | ローカル LLM の判断根拠が追えない | 全出力を JSON 構造化。お針子がオーバーライド可能な設計 |
| CrewAI LiteLLM バグ | base_url が無視されて Ollama デフォルトに接続するバグ | `model="ollama/qwen2.5-coder:1.5b"` と `base_url` の両方を指定。または `OPENAI_API_BASE` 環境変数で回避 |

---

## §9. 未決事項（殿に伺いが必要な項目）

### 9.1 tmux ペイン配置

**質問**: 勘定吟味役のプロセスをどのペインで動かすか？

- **選択肢A**: 鯰(ooku:agents.3)を転用 → 鯰の FTS5 API とプロセスを統合
- **選択肢B**: ooku セッションに新規ペインを追加 → 役割分離、ペイン数が増加

**影響**: CLAUDE.md のセッション構成記載、ワーカー起動スクリプト（scripts/worker_ctl.sh）の更新範囲

### 9.2 Phase 0 の実施環境

**質問**: Qwen2.5-Coder-1.5B を最初にどの環境でテストするか？

- **vx2.local**: 高性能（CPU 多コア）。推論速度 ~8 tok/s
- **nipogi.local**: 通常運用環境。Pi5 と同等のリソース

**影響**: Phase 0 の完了時間と、本番環境移行時の追加作業量

### 9.3 Claude API 予算上限（Phase 3 ハイブリッド）

**質問**: Phase 3 のハイブリッド構成（Claude API 二次判定）における月次 API 予算上限をいくらに設定するか？

現状の試算:
- お針子による監査: 1件あたり ~3,000-5,000 トークン
- 勘定吟味役導入後: ~1,000-2,000 トークン（情報収集分を削減）
- Phase 3 ハイブリッド: 二次判定が必要な件数×追加コスト

→ **Phase 2 完了時点でトークン消費実績を計測し、Phase 3 予算を決定することを推奨**

---

## 付録: 変更対象ファイル一覧

| ファイル | 変更内容 | Phase |
|---------|---------|-------|
| CLAUDE.md | tmux セッション構成（勘定吟味役ペイン追加） | Phase 4 |
| scripts/worker_ctl.sh | 勘定吟味役の起動/停止サポート | Phase 4 |
| instructions/ohariko.md | 事前レポート受け取り手順の追記 | Phase 4 |
| scripts/kanjou_ginmiyaku.py | 勘定吟味役メインプロセス（新規） | Phase 1-4 |
| requirements_kanjou.txt | crewai, crewai-tools, ollama 等（新規） | Phase 0 |
