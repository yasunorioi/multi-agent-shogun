# 勘定吟味役 技術調査: CrewAI + LFM2.5 コードレビュー能力評価

> **subtask**: subtask_557 (cmd_252)
> **作成日**: 2026-02-21
> **作成者**: 部屋子1号 (ashigaru6)
> **ステータス**: Wave1a リサーチ成果物

---

## §1: CrewAI アーキテクチャ概要

### 1.1 フレームワークの位置づけ

CrewAI はマルチエージェント協調のためのオープンソース Python フレームワーク。
各エージェントに役割(role)・目標(goal)・背景(backstory)を定義し、
複数エージェントが協調してタスクを遂行する。

GitHub: https://github.com/crewAIInc/crewAI
ドキュメント: https://docs.crewai.com/

### 1.2 3層構造

```
┌──────────────────────────────────────────┐
│  Crew（チーム全体）                        │
│  ┌─────────────────────────────────────┐ │
│  │  Agent 1: Code Reviewer             │ │
│  │  role: "コードレビュアー"              │ │
│  │  goal: "品質問題の検出"               │ │
│  │  backstory: "10年のPython経験..."     │ │
│  │  tools: [FileReadTool, GrepTool]    │ │
│  │  llm: LLM("ollama/lfm2.5:1.2b")    │ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │  Agent 2: Security Auditor          │ │
│  │  role: "セキュリティ監査官"            │ │
│  │  goal: "脆弱性の検出"                │ │
│  │  tools: [FileReadTool]              │ │
│  │  llm: LLM("claude-3.5-sonnet")     │ │
│  └─────────────────────────────────────┘ │
│                                          │
│  ┌─────────────────────────────────────┐ │
│  │  Task 1: 命名規則チェック             │ │
│  │  → Agent 1 が実行                    │ │
│  │  expected_output: "違反一覧"          │ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │  Task 2: セキュリティ検査             │ │
│  │  → Agent 2 が実行                    │ │
│  │  context: [Task 1]  # 依存           │ │
│  └─────────────────────────────────────┘ │
│                                          │
│  process: sequential | hierarchical      │
│  memory: True                            │
└──────────────────────────────────────────┘
```

### 1.3 Agent 定義

```python
from crewai import Agent, LLM

reviewer = Agent(
    role="コードレビュアー",
    goal="Pythonコードの品質問題を検出し、改善提案を出す",
    backstory="10年のPython開発経験を持つシニアエンジニア。PEP8準拠とクリーンコードを重視する。",
    tools=[FileReadTool(), GrepTool()],
    llm=LLM(model="ollama/lfm2.5:1.2b", base_url="http://localhost:11434"),
    verbose=True,
    memory=True,
)
```

主要パラメータ:

| パラメータ | 説明 | 必須 |
|-----------|------|------|
| `role` | エージェントの役割（短い文字列） | 必須 |
| `goal` | 達成目標 | 必須 |
| `backstory` | 背景・専門性（プロンプトに注入される） | 必須 |
| `tools` | 使用可能なツールのリスト | 任意 |
| `llm` | 使用する LLM（エージェントごとに異なるモデル可） | 任意 |
| `verbose` | 詳細ログ出力 | 任意 |
| `memory` | メモリ使用の有無 | 任意 |
| `allow_delegation` | 他のエージェントへのタスク委任を許可 | 任意 |
| `max_iter` | 最大反復回数（無限ループ防止） | 任意 |

### 1.4 Task 定義

```python
from crewai import Task

review_task = Task(
    description="以下のPythonファイルのコード品質をレビューせよ: {file_path}",
    expected_output="問題点のリスト（行番号、問題内容、修正提案）",
    agent=reviewer,
    context=[],  # 他タスクの出力を参照可能
)
```

主要パラメータ:

| パラメータ | 説明 |
|-----------|------|
| `description` | タスク内容（テンプレート変数 `{var}` 使用可能） |
| `expected_output` | 期待する出力形式（LLMの出力ガイドになる） |
| `agent` | 担当エージェント |
| `context` | 依存タスクのリスト（出力がコンテキストとして渡される） |
| `output_file` | 結果をファイルに書き出す |
| `human_input` | 人間の確認を要求 |

### 1.5 Crew 実行モード

#### Sequential（逐次実行）

```python
crew = Crew(
    agents=[reviewer, auditor],
    tasks=[review_task, audit_task],
    process=Process.sequential,
    verbose=True,
)
result = crew.kickoff()
```

タスクが定義順に1つずつ実行される。前のタスクの出力が次のタスクのコンテキストに自動注入される。
**勘定吟味役に適する**: 一次スクリーニング → 二次判定 のパイプラインに合致。

#### Hierarchical（階層実行）

```python
crew = Crew(
    agents=[reviewer, auditor],
    tasks=[review_task, audit_task],
    process=Process.hierarchical,
    manager_llm=LLM(model="claude-3.5-sonnet"),
)
```

マネージャーエージェントがタスクの委任・結果の検証を行う。
`manager_llm` または `manager_agent` の指定が必須。
**注意**: マネージャーに高性能 LLM が必要（1.2B では厳しい）。

### 1.6 ツール定義

#### @tool デコレータ方式

```python
from crewai.tools import tool

@tool("ファイル読み取り")
def read_file(file_path: str) -> str:
    """指定パスのファイル内容を返す"""
    with open(file_path) as f:
        return f.read()
```

関数名がツール名、docstring がツール説明として自動認識される。

#### BaseTool 継承方式

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class FileReadInput(BaseModel):
    file_path: str = Field(description="読み取るファイルのパス")

class FileReadTool(BaseTool):
    name: str = "ファイル読み取り"
    description: str = "指定パスのファイル内容を返す"
    args_schema: type[BaseModel] = FileReadInput

    def _run(self, file_path: str) -> str:
        with open(file_path) as f:
            return f.read()
```

#### 既存ツール

CrewAI は FileReadTool、DirectorySearchTool、GithubSearchTool 等の
既存ツールを提供。`pip install crewai-tools` で追加インストール。

### 1.7 メモリシステム

CrewAI は4種のメモリを提供:

| メモリ種別 | ストレージ | 用途 |
|-----------|-----------|------|
| Short-term Memory | ChromaDB (RAG) | 現在のセッションのコンテキスト保持 |
| Long-term Memory | SQLite3 | セッション間のタスク結果・学習の永続化 |
| Entity Memory | ChromaDB (RAG) | 人名・概念・プロジェクト等のエンティティ情報 |
| Contextual Memory | 上記の統合 | Short-term + Long-term の統合参照 |

```python
crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,  # 全メモリを有効化
    embedder={
        "provider": "ollama",
        "config": {"model": "nomic-embed-text"},
    },
)
```

**注意**: デフォルトは OpenAI embeddings を使用。ローカル運用では Ollama 等の
ローカル embedder を指定する必要がある。

---

## §2: ローカル LLM 接続方式

### 2.1 接続方式の比較

| 方式 | 接続先 | CrewAI設定 | 利点 | 欠点 |
|------|--------|-----------|------|------|
| **Ollama** | localhost:11434 | `model="ollama/model_name"` | 公式サポート、簡単 | Ollama必須 |
| **OpenAI互換API** | 任意のURL | `model="openai/model_name"` + `base_url` | llama-server直結可 | LiteLLMのバグあり |
| **LiteLLM Proxy** | localhost:4000 | LiteLLMプロキシ経由 | 複数モデル管理 | 別プロセス必要 |

### 2.2 Ollama 方式（推奨）

```python
from crewai import LLM

llm = LLM(
    model="ollama/lfm2.5:1.2b",
    base_url="http://localhost:11434",
    temperature=0.1,
)
```

Ollama に LFM2.5 の GGUF をインポートする手順:

```bash
# 1. Modelfile を作成
cat > Modelfile << 'EOF'
FROM ./models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
TEMPLATE """{{ .System }}{{ .Prompt }}"""
PARAMETER temperature 0.1
PARAMETER num_ctx 4096
EOF

# 2. Ollama にインポート
ollama create lfm2.5:1.2b -f Modelfile

# 3. 確認
ollama list
```

### 2.3 OpenAI 互換 API 方式（llama-server 直結）

```python
llm = LLM(
    model="openai/lfm2.5",
    base_url="http://localhost:8081/v1",
    api_key="dummy",  # llama-server は認証不要だがパラメータ必須
)
```

llama-server が OpenAI 互換 `/v1/chat/completions` エンドポイントを提供するため、
CrewAI の LiteLLM 経由で直結可能。

**既知の問題**:
- LiteLLM が `base_url` を無視して Ollama デフォルト (localhost:11434) に接続するバグが報告されている
- CrewAI v1.3.0+ で修正が進んでいるが、`OPENAI_API_BASE` 環境変数による設定が確実

```python
import os
os.environ["OPENAI_API_BASE"] = "http://localhost:8081/v1"
os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["OPENAI_MODEL_NAME"] = "lfm2.5"
```

### 2.4 推奨構成: Ollama + llama-server 併用

```
                     ┌─── CrewAI Agent (一次スクリーニング)
                     │     model="ollama/lfm2.5:1.2b"
Ollama ──────────────┤
  localhost:11434    │
                     └─── uecs-ccm-llama (温室制御)
                           ※ 同一モデルを共有

llama-server ────────── uecs-ccm-llama (tool calling 用)
  localhost:8081          ※ --jinja フラグ必須
```

**注意**: Ollama と llama-server で同じ GGUF モデルを二重にメモリに載せないよう、
CrewAI 側は Ollama 経由に統一し、llama-server は uecs-ccm-llama 専用にする。

---

## §3: LFM2.5 コードレビュー能力評価

### 3.1 LFM2.5-1.2B の特性

| 項目 | 値 |
|------|-----|
| パラメータ数 | 1.2B |
| アーキテクチャ | Liquid Foundation Model（SSM ハイブリッド） |
| 訓練データ | 10T トークン（英語75%、多言語20%、**コード5%**） |
| コンテキスト長 | 32,768 トークン（推奨 4,096） |
| 推論速度 (vx2.local) | ~47 tok/s (CPU, 6スレッド) |
| 推論速度 (Pi5) | ~10 tok/s (CPU, 4スレッド) |
| GGUF量子化 | Q4_K_M |

Liquid AI 公式の注意書き:
> **プログラミングスキルを要するタスクやナレッジ集約タスクへの使用は非推奨**

### 3.2 得意な領域（1.2B でも実用可能）

| カテゴリ | 具体例 | 理由 |
|---------|--------|------|
| **パターンマッチ** | 命名規則違反（snake_case/CamelCase混在）検出 | 単純な正規表現的判断。コンテキスト不要 |
| **フォーマットチェック** | インデント不整合、行長超過、末尾空白 | 表面的パターン。5%のコード訓練で十分 |
| **チェックリスト照合** | docstring の有無、型ヒントの有無、import 順序 | Yes/No 判定。構造理解は最小限 |
| **定型的コメント生成** | 「この関数に docstring がありません」等 | テンプレート生成。創造性不要 |
| **差分サマリ** | git diff の要約（追加行数、変更箇所の概要） | テキスト要約。コード理解は浅くてOK |

### 3.3 苦手な領域（1.2B では困難）

| カテゴリ | 具体例 | 理由 |
|---------|--------|------|
| **ロジック理解** | 条件分岐の漏れ、境界値の誤り | 実行パスの追跡に深い推論が必要 |
| **設計判断** | 「この抽象化は過剰」「責務分離が不十分」 | ドメイン知識+設計原則の複合判断 |
| **セキュリティ脆弱性** | SQLインジェクション、パストラバーサル | コンテキスト依存。攻撃ベクトルの推論が必要 |
| **クロスファイル依存** | import 先の変更が呼び出し元に影響 | 複数ファイルの同時理解が必要 |
| **リファクタリング提案** | 「この3箇所を共通関数に抽出すべき」 | パターン認識+最適な抽象化の判断 |
| **非自明なバグ検出** | 競合状態、メモリリーク、非同期の deadlock | 実行時挙動の推論が必要 |

### 3.4 代替モデルの比較

| モデル | サイズ | コード能力 | コスト | 推論速度(Pi5) | 備考 |
|--------|--------|-----------|--------|-------------|------|
| **LFM2.5-1.2B** | 1.2B | 低 | 無料 | ~10 tok/s | 現有。コード訓練5% |
| **Qwen2.5-Coder-1.5B** | 1.5B | 中 | 無料 | ~8 tok/s | コード特化。同サイズ帯で最強 |
| **Qwen3-Coder-Next-3B** | 3B | 高 | 無料 | ~4 tok/s | SWE-Bench で 10-20x 大モデルに匹敵 |
| **Qwen2.5-Coder-7B** | 7B | 高 | 無料 | ~2 tok/s | コード特化中型。Pi5でギリギリ |
| **Claude 3.5 Sonnet** | 非公開 | 最高 | API課金 | N/A (クラウド) | 設計判断・セキュリティに強い |

### 3.5 ハイブリッド案（推奨）

```
┌────────────────────────┐
│  一次スクリーニング       │
│  LFM2.5 or Qwen-Coder  │
│  ローカル・無料・高速     │
│                          │
│  チェック内容:            │
│  - 命名規則               │
│  - フォーマット            │
│  - docstring/型ヒント有無  │
│  - 変更量サマリ            │
│  - チェックリスト照合       │
└──────────┬───────────────┘
           │ 問題あり or 重要ファイル
           ▼
┌────────────────────────┐
│  二次判定               │
│  Claude API (Sonnet)   │
│  クラウド・高品質・有料   │
│                          │
│  チェック内容:            │
│  - ロジック正当性          │
│  - セキュリティ脆弱性      │
│  - 設計判断               │
│  - リファクタリング提案     │
└──────────────────────────┘
```

**コスト最適化**: 全ファイルを Claude に投げるのではなく、
一次スクリーニングで「問題なし」と判定されたファイルはスキップ。
Claude API のトークン消費を 50-80% 削減可能（推定）。

---

## §4: 既存活用事例サマリ

### 4.1 CrewAI 公式: PR レビューデモ

**リポジトリ**: https://github.com/crewAIInc/demo-pull-request-review

構成:
- **Quick Review Assistant**: コード変更の初期評価（概要・影響範囲）
- **Code Review Expert**: 詳細レビュー（品質問題・改善提案）

フロー:
1. GitHub PR の変更ファイルを取得
2. Quick Review → 概要生成
3. Code Review Expert → 詳細レビューレポート生成
4. レビューコメントを PR に投稿

### 4.2 Ionio: LLM Agent for Code Reviews

**リポジトリ**: https://github.com/Ionio-io/LLM-agent-for-code-reviews

CrewAI + LangChain を使用。GitHub API 経由でリポジトリ構造を取得し、
ファイルごとにレビュー → 変更提案を生成。

### 4.3 Jenkins + CrewAI + Claude 3.5 Sonnet

**出典**: Medium (@ingeniero.agustin)

エンタープライズ構成:
- Jenkins が新規 PR を検出 → CrewAI パイプラインを起動
- Code-Reviewer Agent: 各ファイルの diff を分析
- Comment-Publisher Agent: レビュー結果を検証し、高品質なコメントのみ PR に投稿
- Docker コンテナ内で実行（CI/CD 統合）

### 4.4 農業 IoT / 組込みシステムでの事例

**直接的な事例は確認できず**。
ただし CrewAI の「エージェントごとに異なる LLM」を指定可能な機能は、
エッジデバイス（Pi5 ローカル LLM）+ クラウド API のハイブリッド構成に適している。

---

## §5: 勘定吟味役への適用可能性

### 5.1 現在のお針子と勘定吟味役の役割分担

```
┌──────────────────────┐  ┌──────────────────────┐
│  お針子 (ohariko)     │  │  勘定吟味役            │
│  Claude Code Agent    │  │  CrewAI + ローカルLLM  │
│                        │  │                        │
│  責務:                 │  │  責務:                 │
│  - DB全権閲覧          │  │  - 定型監査の自動化     │
│  - 没日録の監査         │  │  - コードレビュー一次   │
│  - 先行割当            │  │  - チェックリスト照合   │
│  - 老中への報告         │  │  - 差分サマリ生成      │
│                        │  │                        │
│  LLM: Claude Sonnet   │  │  LLM: LFM2.5 or Qwen  │
│  コスト: API課金       │  │  コスト: 無料（ローカル）│
│  品質: 高              │  │  品質: 中〜低          │
└──────────────────────┘  └──────────────────────┘
```

### 5.2 推奨構成案

#### 構成A: Ollama + CrewAI Sequential（最小構成）

```python
from crewai import Agent, Task, Crew, Process, LLM

# ローカルLLM（一次スクリーニング用）
local_llm = LLM(
    model="ollama/qwen2.5-coder:1.5b",  # コード特化小型モデル推奨
    base_url="http://localhost:11434",
    temperature=0.1,
)

# Agent 1: フォーマットチェッカー
format_checker = Agent(
    role="フォーマットチェッカー",
    goal="Python コードの命名規則・フォーマット違反を検出する",
    backstory="PEP8 準拠とプロジェクト規約の遵守を重視するレビュアー",
    tools=[FileReadTool()],
    llm=local_llm,
)

# Agent 2: チェックリスト監査官
checklist_auditor = Agent(
    role="チェックリスト監査官",
    goal="subtask の報告内容がチェックリストの全項目をカバーしているか確認する",
    backstory="品質管理の専門家。漏れを許さない。",
    tools=[FileReadTool(), DBQueryTool()],  # 没日録DB検索用カスタムツール
    llm=local_llm,
)

# Task 1: フォーマットチェック
format_task = Task(
    description="以下のファイルの命名規則・フォーマットをチェックせよ: {file_path}",
    expected_output="違反箇所のリスト（行番号、問題、修正案）。問題なければ'OK'",
    agent=format_checker,
)

# Task 2: チェックリスト照合
checklist_task = Task(
    description="subtask {subtask_id} の報告が指示の全項目を網羅しているか確認せよ",
    expected_output="網羅率(%)と未言及項目のリスト",
    agent=checklist_auditor,
    context=[format_task],
)

# Crew: 逐次実行
crew = Crew(
    agents=[format_checker, checklist_auditor],
    tasks=[format_task, checklist_task],
    process=Process.sequential,
    verbose=True,
)
```

#### 構成B: ハイブリッド（ローカル一次 + Claude 二次）

```python
# 一次: ローカル LLM
local_llm = LLM(model="ollama/qwen2.5-coder:1.5b", ...)

# 二次: Claude API（重要ファイルのみ）
cloud_llm = LLM(model="claude-3-5-sonnet-20241022", api_key=os.environ["ANTHROPIC_API_KEY"])

# Agent: ローカル一次スクリーニング
screener = Agent(role="一次スクリーナー", llm=local_llm, ...)

# Agent: Claude 二次判定
deep_reviewer = Agent(role="深層レビュアー", llm=cloud_llm, ...)

# Crew: 一次 → 二次（問題ありの場合のみ）
crew = Crew(
    agents=[screener, deep_reviewer],
    tasks=[screening_task, deep_review_task],
    process=Process.sequential,
)
```

### 5.3 カスタムツール（勘定吟味役用）

勘定吟味役に必要なカスタムツール:

| ツール名 | 機能 | 実装方式 |
|---------|------|---------|
| `DBQueryTool` | 没日録DB (SQLite) への読み取りクエリ | BaseTool継承 |
| `FileReadTool` | ソースコードの読み取り | 既存ツール流用 |
| `DiffTool` | git diff の取得 | @tool デコレータ |
| `ChecklistTool` | チェックリストYAML の読み込みと照合 | BaseTool継承 |
| `NamazuSearchTool` | 鯰API (FTS5検索) の呼び出し | @tool デコレータ |

### 5.4 制約・リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| LFM2.5 のコード理解力不足 | 誤検出/見逃しが多い | Qwen2.5-Coder に切り替え or ハイブリッド |
| CrewAI の LiteLLM バグ | 接続先が意図通りにならない | 環境変数方式で回避 |
| メモリの OpenAI 依存 | ローカル運用で embedder 設定が必要 | Ollama nomic-embed-text を指定 |
| Pi5 のメモリ制約 (8GB) | Qwen-7B + Ollama で OOM | 1.5B-3B に留める。7B は vx2.local で |
| 温室制御 LLM との競合 | uecs-ccm-llama と GPU/CPU リソース競合 | Ollama 共有 or 時間帯分離 |

### 5.5 段階的導入ロードマップ

| Phase | 内容 | 前提条件 |
|-------|------|---------|
| **Phase 0** | Ollama に Qwen2.5-Coder-1.5B をインストール、CrewAI で Hello World | vx2.local or nipogi.local |
| **Phase 1** | フォーマットチェック Agent 単体で subtask 出力を検査 | チェックリスト YAML 定義 |
| **Phase 2** | チェックリスト照合 Agent 追加（没日録DB検索ツール） | DBQueryTool 実装 |
| **Phase 3** | Claude API 二次判定の統合（ハイブリッド構成） | API キー設定 |
| **Phase 4** | CI/CD 統合（git push → 自動レビュー → 結果を inbox YAML に書き込み） | shogun通信プロトコル統合 |

### 5.6 LFM2.5 vs Qwen2.5-Coder の選定

**結論: 勘定吟味役には Qwen2.5-Coder-1.5B を推奨**。

理由:
1. LFM2.5 はコード訓練が全体の 5% のみ。公式が「プログラミングタスクは非推奨」と明記
2. Qwen2.5-Coder-1.5B は同サイズ帯でコード特化。SWE-Bench 等のベンチマークで優位
3. メモリ使用量はほぼ同等（1.2B vs 1.5B）。Pi5 でも問題なし
4. LFM2.5 は uecs-ccm-llama（温室制御）に専念させる。役割分離が明確

LFM2.5 の温室制御適性（agentic tasks, data extraction, tool calling）と
Qwen2.5-Coder のコード適性は相補的。両方を Ollama に載せて使い分ける。

---

## 参考文献

- [CrewAI Documentation](https://docs.crewai.com/en/introduction)
- [CrewAI GitHub](https://github.com/crewAIInc/crewAI)
- [CrewAI LLM Connections](https://docs.crewai.com/en/learn/llm-connections)
- [CrewAI Memory](https://docs.crewai.com/en/concepts/memory)
- [CrewAI PR Review Demo](https://github.com/crewAIInc/demo-pull-request-review)
- [Ionio LLM Agent for Code Reviews](https://github.com/Ionio-io/LLM-agent-for-code-reviews)
- [LFM2 Technical Report](https://arxiv.org/abs/2511.23404)
- [LFM2-1.2B (Hugging Face)](https://huggingface.co/LiquidAI/LFM2-1.2B)
- [Qwen3-Coder-Next](https://qwen.ai/blog?id=qwen3-coder-next)
- [CrewAI + Jenkins + Claude PR Review](https://medium.com/@ingeniero.agustin/automating-pull-request-code-reviews-with-crewai-docker-jenkins-claude-3-5-sonnet-35a9ace52ce1)
- [CrewAI Framework 2025 Review](https://latenode.com/blog/ai-frameworks-technical-infrastructure/crewai-framework/crewai-framework-2025-complete-review-of-the-open-source-multi-agent-ai-platform)
- [Small LLM Benchmarks (distillabs)](https://www.distillabs.ai/blog/we-benchmarked-12-small-language-models-across-8-tasks-to-find-the-best-base-model-for-fine-tuning)
