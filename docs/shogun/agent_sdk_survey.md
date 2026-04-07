# Claude Agent SDK リサーチ — 獏宇宙論との統合可能性調査

> **date**: 2026-03-15 | **analyst**: ashigaru6（部屋子）
> **task**: subtask_904 (cmd_411) | **status**: complete

---

## エグゼクティブサマリ

| 判定項目 | 結論 |
|---------|------|
| Agent SDKで獏を再設計すべきか | **No（現時点）** — 過剰。直API（anthropic SDK）で十分 |
| 好奇心エンジンにAgent SDKが活きる場面 | Phase 3統合後、ツール連鎖が複雑化したときに再検討 |
| 推奨アーキテクチャ | **案B: anthropic SDK + カスタムツール関数（自前ループ）** |
| コスト影響 | Agent SDK自体は追加課金なし。ただしAgent Loopのオーバーヘッド（思考トークン）が増える |

---

## §1 Agent SDKの概要・設計思想

### 1.1 正体

- `pip install claude-agent-sdk`（PyPI: claude-agent-sdk）
- Claude Codeと同じエージェントループ・ツール群・コンテキスト管理をPython/TypeScriptから利用可能にしたもの
- 内部的にClaude Code CLIをバンドル。別途インストール不要

### 1.2 2つのAPI

| API | 用途 | ツール対応 | 適合場面 |
|-----|------|----------|---------|
| `query()` | 軽量テキスト生成 | **なし** | 単発の質問応答、パイプライン内の1ステップ |
| `ClaudeSDKClient` | フル機能エージェント | **あり**（組込+カスタム+MCP） | 自律的タスク実行、ファイル操作、コード編集 |

### 1.3 設計思想

- **Agent Loop**: プロンプト → Claude推論 → ツール呼び出し → 結果観察 → 繰り返し → 完了
- **自動コンテキスト管理**: コンパクション・長時間実行の制御を自動化
- **Hooks**: PreToolUse / PostToolUse / Stop でツール実行を制御・監視可能
- **セッション永続化**: session_idで会話を再開可能

---

## §2 Python SDKの具体的API

### 2.1 query()（軽量版）

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async for msg in query(
    prompt="この検索結果を要約して",
    options=ClaudeAgentOptions(model="claude-haiku-4-5-20251001")
):
    # msg から TextBlock を抽出
    pass
```

- ツール不可。単純なテキスト生成のみ
- **現行baku.pyのinterpret_dream()置き換え候補**（ただしメリット薄い、後述）

### 2.2 ClaudeSDKClient（フル版）

```python
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    tool, create_sdk_mcp_server
)

@tool("search_db", "没日録DBを検索", {"query": str})
async def search_db(args):
    # SQLite検索ロジック
    conn = sqlite3.connect(DB_PATH)
    results = conn.execute("SELECT ...", (args["query"],)).fetchall()
    return {"content": [{"type": "text", "text": str(results)}]}

server = create_sdk_mcp_server(
    name="baku-tools",
    version="1.0.0",
    tools=[search_db]
)

async with ClaudeSDKClient(
    ClaudeAgentOptions(
        model="claude-haiku-4-5-20251001",
        allowed_tools=["search_db", "Read"],
        max_turns=5,
    ),
) as client:
    async for msg in client.query("好奇心の穴を探して検索クエリを生成して"):
        process(msg)
```

### 2.3 カスタムツール定義

- `@tool` デコレータでPython関数をツール化
- `create_sdk_mcp_server()` でインプロセスMCPサーバーとして登録
- **別プロセス不要**。同一Pythonプロセス内でMCPが動く
- 型安全、デバッグ容易

---

## §3 cronデーモンとの相性

### 3.1 現行の獏

```
crontab: 0 7 * * * cd /home/yasu/multi-agent-shogun && python3 scripts/baku.py --once
```

- 純粋なPythonスクリプト。起動→実行→終了
- DuckDuckGo検索 + Haiku API直叩き + SQLite読み書き
- 依存: `openai`（OpenAI互換エンドポイント経由）

### 3.2 Agent SDK + cron

```bash
# CLIモード（-p フラグでヘッドレス実行）
0 7 * * * claude -p "好奇心エンジンを実行して夢を5件探せ" --allowedTools "Read,Bash(python3:*)"
```

- **可能だが重い**: Agent SDKはClaude Code CLIをバンドル → 起動オーバーヘッドあり
- エージェントループの思考トークン（推論過程）が追加コスト
- **単純なcronジョブには過剰**

### 3.3 判定

| 項目 | 現行（直API） | Agent SDK |
|------|-------------|-----------|
| 起動速度 | ◎ 即時 | △ CLI起動+初期化 |
| cron相性 | ◎ 完全 | ○ 可能だが重い |
| 依存 | openai（軽量） | claude-agent-sdk（CLIバンドル） |
| 制御の精度 | ◎ 全て自前コード | △ Agent Loopに委ねる |

**結論**: cronデーモンとしてはAgent SDK不向き。現行の直API方式が最適。

---

## §4 SQLite統合

### 4.1 カスタムツールとして登録可能

```python
@tool("query_cooccurrence", "共起行列から穴を検出", {"min_gap": float})
async def query_cooccurrence(args):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    holes = conn.execute(HOLE_DETECTION_SQL, (args["min_gap"],)).fetchall()
    conn.close()
    return {"content": [{"type": "text", "text": json.dumps(holes)}]}

@tool("save_dream", "夢をdreams.jsonlに保存", {"dream": dict})
async def save_dream_tool(args):
    # ...
```

- **技術的に完全に可能**
- ただし、SQLiteの読み書きをClaude（LLM）に委ねる意味があるかが問題
- 現行baku.pyはSQLite操作を**Pythonコードで直接制御** → 決定論的・高速・コスト0

### 4.2 判定

| 操作 | 直接Python | Agent SDKツール経由 |
|------|-----------|-------------------|
| 共起行列読み取り | ◎ SQL直実行 | △ LLMがツール呼び出し→SQL実行→結果解釈 |
| 夢の保存 | ◎ JSONL追記 | ✕ 過剰（LLMに保存判断させる意味なし） |
| 穴検出SQL | ◎ 決定論的 | △ 同じSQLをLLM経由で実行するだけ |
| 検索クエリ生成 | △ テンプレ+ルール | **◎ LLMの創造性が活きる** |

**結論**: SQLite操作自体はAgent SDKツール化不要。LLMが価値を発揮するのは**検索クエリ生成と夢解釈のみ**。

---

## §5 獏再設計案 — 3つのアーキテクチャ比較

### 案A: Agent SDK全面採用（非推奨）

```
cron → claude-agent-sdk ClaudeSDKClient
         ├─ カスタムツール: query_db, search_ddg, save_dream
         ├─ Agent Loop が全てを制御
         └─ Claudeが自律的に穴を探し、検索し、保存
```

- **メリット**: コード量最小。Claudeに全て委ねる
- **デメリット**:
  - 思考トークンのコスト増（Agent Loopの推論過程で数千トークン消費）
  - 決定論的であるべき処理（SQL、ファイルI/O）をLLMに委ねる不合理
  - デバッグ困難。Agent Loopの中身はブラックボックス
  - **月額ゼロ原則に反する**（Agent Loop自体のトークン消費が増大）

### 案B: anthropic SDK + カスタムツール関数（推奨）

```
cron → baku.py（Python）
         ├─ Phase 0-2: Pythonコード直実行（SQL, 穴検出, 共起行列）
         ├─ Phase 3: anthropic SDK で Haiku 呼び出し
         │    └─ 検索クエリ生成 + 夢解釈（LLMの価値がある箇所のみ）
         ├─ DuckDuckGo検索: urllib直叩き（現行通り）
         └─ SQLite: sqlite3モジュール直叩き（現行通り）
```

- **メリット**:
  - 現行baku.pyの構造を維持。段階的にPhase 0-3を追加可能
  - LLMコストは検索クエリ生成+夢解釈のみ（現行と同等）
  - 決定論的処理は確実にPythonで実行
  - デバッグ容易。全ての処理が可視
  - **openai SDK（現行）→ anthropic SDK への移行は任意**（OpenAI互換が使える限り不要）
- **デメリット**: Agent SDKの自動コンテキスト管理・セッション再開機能は使えない（獏には不要）

### 案C: ハイブリッド（将来検討）

```
cron → baku.py（Python）
         ├─ Phase 0-2: Pythonコード直実行
         └─ Phase 3統合時:
              claude-agent-sdk query() で検索クエリ生成
              （ツール不要な軽量呼び出し）
```

- Phase 3で複数エンジン（勾配+偏角+速度）の統合判断が複雑化した場合のみ
- `query()` は軽量でtools不要。interpret_dream()の置き換えに使える
- ただし現行のOpenAI互換エンドポイントで同じことができるため優先度低

---

## §6 コスト比較

### 6.1 API料金

Agent SDK自体は**追加課金なし**。裏で使うAPI（Haiku/Sonnet/Opus）の通常料金のみ。

| モデル | Input/1M tokens | Output/1M tokens |
|--------|:-:|:-:|
| Haiku 4.5 | $1.00 | $5.00 |
| Sonnet 4.6 | $3.00 | $15.00 |
| Opus 4.6 | $5.00 | $25.00 |

### 6.2 現行baku.pyのコスト構造

| 処理 | モデル | 1回あたりトークン | 1日コスト（概算） |
|------|--------|:--:|:--:|
| interpret_dream() × 5件 | Haiku | ~500 in + ~200 out × 5 | ~$0.0075 |
| sonnet_selection() × 1回 | Sonnet | ~2000 in + ~500 out | ~$0.0135 |
| **合計** | | | **~$0.02/日 ≈ $0.6/月** |

### 6.3 Agent SDK採用時の追加コスト

| 追加コスト要因 | 概算 |
|--------------|------|
| Agent Loopの推論トークン（思考過程） | +1000〜3000 tokens/回 |
| ツール呼び出しのラウンドトリップ | +500〜1000 tokens/ツール |
| **1日あたり追加** | **+$0.01〜0.03** |

**結論**: Agent SDKは月額+$0.3〜0.9の追加。獏のような定型cronジョブでは費用対効果が低い。

---

## §7 好奇心エンジン実装スケッチ（Agent SDK使用時）

### もしAgent SDKで実装するなら（参考設計）

```python
#!/usr/bin/env python3
"""baku_v2.py — Agent SDK版（参考実装。推奨は案B）"""

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    tool, create_sdk_mcp_server
)
import sqlite3, json

DB_PATH = "data/botsunichiroku.db"

# --- カスタムツール定義 ---

@tool("detect_holes", "共起行列から情報密度の穴を検出する", {
    "min_gap": {"type": "number", "description": "最小density_gap閾値"},
    "limit": {"type": "integer", "description": "返す穴の最大数"}
})
async def detect_holes(args):
    """Phase 0: 勾配エンジン — 穴検出"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    sql = """
    WITH kw_df AS (
        SELECT keyword, COUNT(DISTINCT doc_id) AS df
        FROM doc_keywords GROUP BY keyword
    ),
    kw_neighbor AS (
        SELECT c.term_a AS keyword, AVG(d.df) AS neighbor_df
        FROM cooccurrence c
        JOIN kw_df d ON d.keyword = c.term_b
        WHERE c.pmi > 0.5
        GROUP BY c.term_a HAVING COUNT(*) >= 3
    )
    SELECT k.keyword, k.df, n.neighbor_df,
           (n.neighbor_df - k.df) AS density_gap
    FROM kw_df k JOIN kw_neighbor n ON n.keyword = k.keyword
    WHERE k.df >= 2 AND n.neighbor_df > 10
      AND (n.neighbor_df - k.df) > ?
    ORDER BY density_gap DESC LIMIT ?
    """
    rows = conn.execute(sql, (args["min_gap"], args["limit"])).fetchall()
    conn.close()
    return {"content": [{"type": "text", "text": json.dumps(
        [{"keyword": r[0], "df": r[1], "neighbor_df": r[2], "gap": r[3]} for r in rows]
    )}]}

@tool("search_web", "DuckDuckGoでWeb検索", {"query": str})
async def search_web(args):
    """外部検索（DuckDuckGo Lite）"""
    result = search_ddg(args["query"])  # 既存関数を流用
    return {"content": [{"type": "text", "text": result or "(結果なし)"}]}

@tool("save_to_library", "蔵書化（dashboard_entriesに保存）", {
    "title": str, "summary": str, "tags": list
})
async def save_to_library(args):
    """蔵書化ツール"""
    # ... SQLite INSERT ...
    return {"content": [{"type": "text", "text": "蔵書化完了"}]}

# --- エージェント起動 ---

server = create_sdk_mcp_server(
    name="baku-curiosity-engine",
    version="0.1.0",
    tools=[detect_holes, search_web, save_to_library]
)

SYSTEM_PROMPT = """あなたは獏（baku）— 好奇心エンジンです。
1. detect_holes ツールで情報密度の穴を見つけてください
2. 穴のキーワードから検索クエリを生成し、search_web で検索
3. 結果を評価し、蔵書に値するものを save_to_library で保存
殿は農業IoT・LLMエッジ推論・マルチエージェントシステムを手がけています。"""

async def main():
    async with ClaudeSDKClient(
        ClaudeAgentOptions(
            model="claude-haiku-4-5-20251001",
            system_prompt=SYSTEM_PROMPT,
            allowed_tools=["detect_holes", "search_web", "save_to_library"],
            max_turns=10,
        ),
    ) as client:
        async for msg in client.query("今日の好奇心探索を実行してください"):
            if hasattr(msg, "total_cost_usd"):
                print(f"コスト: ${msg.total_cost_usd:.4f}")
```

### この設計の問題点

1. **Haiku にAgent Loopは荷が重い** — ツール選択・ループ制御はSonnet以上が推奨。Haikuでは判断ミスが頻発する可能性
2. **決定論的な処理をLLMに委ねている** — 穴検出SQLの実行タイミングや引数をLLMが決める必然性がない
3. **1日1回のcronに対してAgent Loopのオーバーヘッドが大きい**
4. **デバッグ困難** — Agent Loopの中でどのツールがどの順で呼ばれたか追跡しにくい

---

## §8 推奨アーキテクチャ（案B詳細）

```
┌─────────────────────────────────────────┐
│  baku.py（Python直実行）                   │
│                                          │
│  ┌──────────────────┐                    │
│  │ Phase 0: 勾配エンジン │  ← SQLite直実行    │
│  │ (generate_curiosity_ │  ← 決定論的        │
│  │  queries())         │                   │
│  └────────┬─────────┘                    │
│           ↓                              │
│  ┌──────────────────┐                    │
│  │ DuckDuckGo検索     │  ← urllib直叩き     │
│  └────────┬─────────┘                    │
│           ↓                              │
│  ┌──────────────────┐                    │
│  │ Haiku: 夢解釈      │  ← anthropic API   │
│  │ (interpret_dream()) │  ← LLMが価値ある箇所 │
│  └────────┬─────────┘                    │
│           ↓                              │
│  ┌──────────────────┐                    │
│  │ Sonnet: 選別+蔵書化 │  ← 日次バッチのみ   │
│  │ (sonnet_selection())│                   │
│  └──────────────────┘                    │
│                                          │
│  【変更点】                                │
│  ・TONO_INTERESTS → generate_curiosity_   │
│    queries() に段階的に置換               │
│  ・openai SDK → そのまま維持              │
│    （OpenAI互換で動いている限り変更不要）    │
│  ・Agent SDKは導入しない                   │
└─────────────────────────────────────────┘
```

### 8.1 なぜopenai SDK→anthropic SDK移行も不要か

- 現行baku.pyは `from openai import OpenAI` + `ANTHROPIC_BASE_URL/v1` でHaiku/Sonnet呼び出し
- Anthropic公式がOpenAI SDK互換エンドポイントを提供済み
- 動いているものを変える理由がない（マクガイバー精神）

### 8.2 Agent SDKを再検討すべきタイミング

1. **Phase 3統合後**に検索クエリ生成の判断ロジックが複雑化した場合
2. **蔵書100件超**で遺伝的ドリフトモデル（§8設計書）を導入する場合
3. **獏をClaude Code外の独立デーモン**として動かす必要が出た場合（現状は不要）
4. **MCP統合**で外部ツール（Notion, Playwright等）を獏に使わせたい場合

---

## §9 まとめ

| 質問 | 回答 |
|------|------|
| Agent SDKで獏を作り直すべき？ | **No**。現行baku.py + 好奇心エンジン段階追加が最適 |
| Agent SDKの技術的メリットは？ | ツール自動管理、セッション永続、コンテキスト圧縮。だが獏には不要 |
| 月額ゼロは維持可能？ | 直API維持なら◎。Agent SDK採用でも料金自体は同じだが思考トークン増 |
| いつ再検討？ | Phase 3統合後 or 蔵書100件超 or MCP統合需要発生時 |
| 殿の「SQLite完結」原則との整合 | 案Bで完全整合。案AはSQLiteをLLM経由にする不合理あり |

---

Sources:
- [Agent SDK overview - Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Agent SDK reference - Python](https://platform.claude.com/docs/en/agent-sdk/python)
- [Custom Tools - Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/custom-tools)
- [How the agent loop works](https://platform.claude.com/docs/en/agent-sdk/agent-loop)
- [Intercept and control agent behavior with hooks](https://platform.claude.com/docs/en/agent-sdk/hooks)
- [Quickstart - Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/quickstart)
- [Connect to external tools with MCP](https://platform.claude.com/docs/en/agent-sdk/mcp)
- [Track cost and usage](https://platform.claude.com/docs/en/agent-sdk/cost-tracking)
- [Pricing - Claude API Docs](https://platform.claude.com/docs/en/about-claude/pricing)
- [claude-agent-sdk · PyPI](https://pypi.org/project/claude-agent-sdk/)
- [GitHub - anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python)
- [Run Claude Code programmatically (headless)](https://code.claude.com/docs/en/headless)
- [Building agents with the Claude Agent SDK | Anthropic](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Plugins in the SDK](https://platform.claude.com/docs/en/agent-sdk/plugins)
