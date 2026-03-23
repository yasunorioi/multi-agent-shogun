#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# bench_ronin.sh — MBP城 ollama qwen3:70b(Q4_K_M) ベンチマーク
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   bash scripts/bench_ronin.sh [--model qwen3:70b] [--output results.yaml]
#   bash scripts/bench_ronin.sh --test speed          # 推論速度のみ
#   bash scripts/bench_ronin.sh --test tool           # tool calling精度のみ
#   bash scripts/bench_ronin.sh --test yaml           # YAML通信のみ
#   bash scripts/bench_ronin.sh --test context        # コンテキスト長のみ
#   bash scripts/bench_ronin.sh --test practical      # 実タスクのみ
#   bash scripts/bench_ronin.sh --all                 # 全テスト（デフォルト）
#
# テスト項目:
#   1. speed    — 推論速度 (tok/s): eval_count/eval_duration から算出
#   2. tool     — tool calling精度: 5種類のtool定義でJSON返却率を計測
#   3. yaml     — YAML通信: shogun inbox形式のYAML読み書き精度
#   4. context  — コンテキスト長: 段階的プロンプト拡張で劣化点特定
#   5. practical— 実タスク: 没日録サンプルデータの要約タスク
#
# 出力:
#   - JSON/YAML形式で stdout に出力
#   - --output 指定時はファイルに保存
#   - 没日録 report として記録可能な形式
#
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── デフォルト設定 ────────────────────────────────────────────────────────────
MODEL="${BENCH_MODEL:-qwen3:70b}"
OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"
OUTPUT_FILE=""
RUN_TEST="all"

# ── 引数パース ────────────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --model)    MODEL="$2";      shift 2 ;;
        --output)   OUTPUT_FILE="$2"; shift 2 ;;
        --test)     RUN_TEST="$2";   shift 2 ;;
        --all)      RUN_TEST="all";  shift ;;
        --help|-h)
            sed -n '2,30p' "${BASH_SOURCE[0]}" | grep '^#' | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ── 前提チェック ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[bench_ronin] ERROR: python3 が必要です。" >&2
    exit 1
fi

if ! curl -sf "${OLLAMA_BASE}/api/tags" &>/dev/null; then
    echo "[bench_ronin] ERROR: ollama が起動していません (${OLLAMA_BASE})" >&2
    echo "  起動: ollama serve" >&2
    echo "  または: bash scripts/launch_mbp.sh" >&2
    exit 1
fi

# モデル存在確認
TAGS=$(curl -sf "${OLLAMA_BASE}/api/tags")
MODEL_BASE="${MODEL%%:*}"  # qwen3:70b → qwen3
if ! echo "$TAGS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
names = [m['name'] for m in data.get('models', [])]
# 完全一致 or ベース名一致
import sys
model = sys.argv[1] if len(sys.argv) > 1 else ''
matched = any('${MODEL}' in n or '${MODEL_BASE}' in n for n in names)
sys.exit(0 if matched else 1)
" 2>/dev/null; then
    echo "[bench_ronin] ERROR: モデル '${MODEL}' がpullされていません。" >&2
    echo "  pullコマンド: ollama pull ${MODEL}" >&2
    echo "  ※ qwen3:70bは約40GB。pull後に再実行してください。" >&2
    exit 1
fi

echo "[bench_ronin] モデル: ${MODEL} | ベース: ${OLLAMA_BASE}"
echo "[bench_ronin] テスト: ${RUN_TEST}"
echo ""

# ── Pythonメインベンチマーク ───────────────────────────────────────────────────
exec python3 - "${MODEL}" "${OLLAMA_BASE}" "${RUN_TEST}" "${OUTPUT_FILE}" <<'PYEOF'
#!/usr/bin/env python3
"""bench_ronin — qwen3:70b ベンチマークエンジン"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any


# ── 引数 ─────────────────────────────────────────────────────────────────────
MODEL       = sys.argv[1] if len(sys.argv) > 1 else "qwen3:70b"
OLLAMA_BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:11434"
RUN_TEST    = sys.argv[3] if len(sys.argv) > 3 else "all"
OUTPUT_FILE = sys.argv[4] if len(sys.argv) > 4 else ""


# ── API呼び出しユーティリティ ─────────────────────────────────────────────────

def call_generate(prompt: str, num_predict: int = 300, timeout: int = 120) -> dict:
    """ollama /api/generate を呼び出す（stream=False）"""
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.1,
        },
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def call_chat(messages: list[dict], tools: list[dict] | None = None,
              num_predict: int = 300, timeout: int = 120) -> dict:
    """ollama /api/chat を呼び出す（stream=False）"""
    body: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "temperature": 0.0,
        },
    }
    if tools:
        body["tools"] = tools
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def tps_from_resp(resp: dict, key: str = "eval") -> float:
    """eval_count / eval_duration(ns) → tok/s"""
    count    = resp.get(f"{key}_count", 0)
    duration = resp.get(f"{key}_duration", 0)  # nanoseconds
    if count == 0 or duration == 0:
        return 0.0
    return round(count / (duration / 1e9), 2)


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ── テスト1: 推論速度 ─────────────────────────────────────────────────────────

def test_speed() -> dict:
    print("[1/5] 推論速度テスト (tok/s)...")

    prompts = [
        ("短文", "日本の四季について3文で説明してください。", 100),
        ("中文", "機械学習とディープラーニングの違いを200文字程度で説明してください。", 250),
        ("長文", (
            "以下のトピックについて、それぞれ2〜3文で解説してください:\n"
            "1. トランスフォーマーアーキテクチャの仕組み\n"
            "2. 量子コンピューティングの現状\n"
            "3. マルチエージェントシステムの利点\n"
            "4. ゼロショット学習の定義\n"
        ), 400),
    ]

    results = []
    for label, prompt, num_predict in prompts:
        log(f"  [{label}] 実行中...")
        t0 = time.time()
        try:
            resp = call_generate(prompt, num_predict=num_predict, timeout=180)
            elapsed = round(time.time() - t0, 2)
            gen_tps    = tps_from_resp(resp, "eval")
            prompt_tps = tps_from_resp(resp, "prompt_eval")
            gen_tokens = resp.get("eval_count", 0)
            results.append({
                "label": label,
                "prompt_tokens": resp.get("prompt_eval_count", 0),
                "generated_tokens": gen_tokens,
                "prompt_eval_tps": prompt_tps,
                "generation_tps": gen_tps,
                "elapsed_sec": elapsed,
                "status": "ok",
            })
            log(f"  [{label}] {gen_tps} tok/s ({gen_tokens} tokens, {elapsed}s)")
        except Exception as e:
            results.append({"label": label, "status": "error", "error": str(e)})
            log(f"  [{label}] エラー: {e}")

    avg_tps = [r["generation_tps"] for r in results if r.get("status") == "ok"]
    avg = round(sum(avg_tps) / len(avg_tps), 2) if avg_tps else 0.0
    log(f"  平均生成速度: {avg} tok/s")

    return {"test": "speed", "status": "ok", "avg_generation_tps": avg, "details": results}


# ── テスト2: tool calling 精度 ────────────────────────────────────────────────

TOOLS_DEF = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "指定した都市の現在の天気を取得する",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "都市名（例: Tokyo）"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "データベースからレコードを検索する",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "検索キーワード"},
                    "limit": {"type": "integer", "description": "最大件数", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "新しいタスクを作成してキューに追加する",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "worker": {"type": "string"},
                },
                "required": ["title", "priority"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "指定したエージェントに通知を送る",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "送信先エージェントID"},
                    "message": {"type": "string", "description": "通知本文"},
                },
                "required": ["agent", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_metrics",
            "description": "数値リストから統計指標（平均・最大・最小・標準偏差）を計算する",
            "parameters": {
                "type": "object",
                "properties": {
                    "values": {"type": "array", "items": {"type": "number"}},
                    "metric": {"type": "string", "enum": ["mean", "max", "min", "stddev", "all"]},
                },
                "required": ["values", "metric"],
            },
        },
    },
]

TOOL_CASES = [
    ("get_weather",      "東京の今日の天気を摂氏で教えてください。",                              "get_weather"),
    ("search_database",  "没日録DBからsubtask_952に関するレコードを最大5件検索してください。",     "search_database"),
    ("create_task",      "タスク「ベンチマーク実行」を優先度highでashigaru2に作成してください。",  "create_task"),
    ("send_notification","ashigaru1に「ベンチ完了」と通知してください。",                         "send_notification"),
    ("calculate_metrics","[1.5, 2.3, 4.1, 3.8, 2.9]の平均と最大値を計算してください。",           "calculate_metrics"),
]


def test_tool_calling() -> dict:
    print("[2/5] tool calling精度テスト...")

    results = []
    correct = 0

    for tool_name, user_msg, expected_fn in TOOL_CASES:
        log(f"  [{tool_name}] テスト中...")
        try:
            resp = call_chat(
                messages=[{"role": "user", "content": user_msg}],
                tools=TOOLS_DEF,
                num_predict=200,
                timeout=120,
            )
            msg = resp.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            called_fn = None
            valid_json = False
            if tool_calls:
                tc = tool_calls[0]
                called_fn = tc.get("function", {}).get("name", "")
                args = tc.get("function", {}).get("arguments", {})
                # argumentsがdict or JSON文字列か確認
                if isinstance(args, dict):
                    valid_json = True
                elif isinstance(args, str):
                    try:
                        json.loads(args)
                        valid_json = True
                    except json.JSONDecodeError:
                        valid_json = False

            match = (called_fn == expected_fn) and valid_json
            if match:
                correct += 1

            results.append({
                "case": tool_name,
                "expected": expected_fn,
                "called": called_fn,
                "valid_json": valid_json,
                "match": match,
                "status": "ok",
            })
            log(f"  [{tool_name}] {'✓' if match else '✗'} called={called_fn} json={valid_json}")

        except Exception as e:
            results.append({"case": tool_name, "status": "error", "error": str(e)})
            log(f"  [{tool_name}] エラー: {e}")

    total = len(TOOL_CASES)
    accuracy = round(correct / total * 100, 1)
    log(f"  正答率: {correct}/{total} ({accuracy}%)")

    return {
        "test": "tool_calling",
        "status": "ok",
        "accuracy_pct": accuracy,
        "correct": correct,
        "total": total,
        "details": results,
    }


# ── テスト3: YAML通信精度 ─────────────────────────────────────────────────────

YAML_CASES = [
    (
        "yaml_generate",
        (
            "以下のフォーマットに従ったYAMLを生成してください。\n"
            "フォーマット:\n"
            "```yaml\n"
            "reports:\n"
            "- subtask_id: subtask_XXX\n"
            "  worker: ashigaru1\n"
            "  status: completed\n"
            "  summary: 作業内容の要約\n"
            "```\n\n"
            "内容: subtask_001、足軽1が実装完了、DBマイグレーションを実施した。\n"
            "YAMLのコードブロックのみを出力してください。```yaml と ``` で囲んでください。"
        ),
        ["subtask_id", "worker", "status", "summary"],
    ),
    (
        "yaml_parse_and_answer",
        (
            "以下のYAMLを読んで、status: completedのsubtask_idを全て列挙してください。\n\n"
            "```yaml\n"
            "tasks:\n"
            "- subtask_id: subtask_001\n"
            "  status: completed\n"
            "  worker: ashigaru1\n"
            "- subtask_id: subtask_002\n"
            "  status: in_progress\n"
            "  worker: ashigaru2\n"
            "- subtask_id: subtask_003\n"
            "  status: completed\n"
            "  worker: ashigaru1\n"
            "- subtask_id: subtask_004\n"
            "  status: assigned\n"
            "  worker: ashigaru2\n"
            "```\n\n"
            "completedのsubtask_idのみをリスト形式で答えてください。"
        ),
        ["subtask_001", "subtask_003"],
    ),
]


def test_yaml_communication() -> dict:
    print("[3/5] YAML通信精度テスト...")

    results = []
    correct = 0

    for case_name, prompt, expected_keys in YAML_CASES:
        log(f"  [{case_name}] テスト中...")
        try:
            resp = call_generate(prompt, num_predict=300, timeout=120)
            output = resp.get("response", "")

            # 期待キーが出力に含まれるか確認
            matches = [k for k in expected_keys if k in output]
            all_match = len(matches) == len(expected_keys)
            if all_match:
                correct += 1

            results.append({
                "case": case_name,
                "expected_keys": expected_keys,
                "matched_keys": matches,
                "all_match": all_match,
                "output_preview": output[:200].replace("\n", "↵"),
                "status": "ok",
            })
            log(f"  [{case_name}] {'✓' if all_match else '✗'} matched={len(matches)}/{len(expected_keys)}")

        except Exception as e:
            results.append({"case": case_name, "status": "error", "error": str(e)})
            log(f"  [{case_name}] エラー: {e}")

    total = len(YAML_CASES)
    accuracy = round(correct / total * 100, 1)
    log(f"  正答率: {correct}/{total} ({accuracy}%)")

    return {
        "test": "yaml_communication",
        "status": "ok",
        "accuracy_pct": accuracy,
        "correct": correct,
        "total": total,
        "details": results,
    }


# ── テスト4: コンテキスト長 ───────────────────────────────────────────────────

def _make_long_prompt(target_tokens: int) -> str:
    """指定トークン数に近いプロンプトを生成（1トークン ≈ 1.5文字で近似）"""
    unit = (
        "足軽システムはtmuxとClaude Codeを組み合わせたマルチエージェント並列開発基盤です。"
        "戦国軍制モチーフの階層構造により、将軍・老中・足軽・軍師・お針子が役割分担して作業します。"
    )
    chars_needed = int(target_tokens * 1.5)
    reps = max(1, chars_needed // len(unit))
    base = unit * reps
    question = "\n\n上記のシステムの主な特徴を3点に絞って箇条書きで説明してください。"
    return base[:chars_needed] + question


def test_context_length() -> dict:
    print("[4/5] コンテキスト長テスト...")

    # 段階的トークン数（概算）
    levels = [
        ("512",   512,   100),
        ("1024",  1024,  100),
        ("2048",  2048,  150),
        ("4096",  4096,  150),
        ("8192",  8192,  200),
    ]

    results = []
    degraded_at = None

    for label, tokens, num_predict in levels:
        log(f"  [{label}トークン] テスト中...")
        prompt = _make_long_prompt(tokens)
        try:
            t0 = time.time()
            resp = call_generate(prompt, num_predict=num_predict, timeout=240)
            elapsed = round(time.time() - t0, 2)
            output = resp.get("response", "")
            gen_tps = tps_from_resp(resp, "eval")
            prompt_tokens = resp.get("prompt_eval_count", 0)

            # 品質評価: 箇条書き（・、1.、- 等）が含まれるか
            has_bullet = any(c in output for c in ["・", "•", "1.", "2.", "3.", "-", "①", "②"])
            # 出力が短すぎないか（最低50文字）
            sufficient = len(output.strip()) >= 50

            quality_ok = has_bullet and sufficient
            if not quality_ok and degraded_at is None:
                degraded_at = label

            results.append({
                "context_level": label,
                "prompt_tokens_actual": prompt_tokens,
                "generated_tokens": resp.get("eval_count", 0),
                "generation_tps": gen_tps,
                "elapsed_sec": elapsed,
                "output_len_chars": len(output),
                "has_bullet": has_bullet,
                "quality_ok": quality_ok,
                "status": "ok",
            })
            log(f"  [{label}] tps={gen_tps} quality={'✓' if quality_ok else '✗'} len={len(output)}chars")

        except Exception as e:
            results.append({"context_level": label, "status": "error", "error": str(e)})
            log(f"  [{label}] エラー: {e}")
            if degraded_at is None:
                degraded_at = label

    log(f"  品質劣化点: {degraded_at or 'なし（全レベルOK）'}")

    return {
        "test": "context_length",
        "status": "ok",
        "degraded_at_tokens": degraded_at,
        "details": results,
    }


# ── テスト5: 実タスク ─────────────────────────────────────────────────────────

SAMPLE_BOTSUNICHIROKU = """
# 没日録 サンプルデータ

## コマンド一覧 (最新5件)

| cmd_id  | command                        | status   | project            |
|---------|--------------------------------|----------|--------------------|
| cmd_434 | MBP城構築+ベンチマーク         | pending  | multi-agent-shogun |
| cmd_431 | instructions 2ch板ルール追加   | done     | multi-agent-shogun |
| cmd_428 | 2ch板拡張+論議スレ機能         | done     | multi-agent-shogun |
| cmd_427 | Browse Use調査                 | done     | multi-agent-shogun |
| cmd_426 | 軍師権限拡大+老中負荷軽減      | done     | multi-agent-shogun |

## 最近完了したsubtask (subtask_951〜960)

- subtask_951: 2ch板3板追加 (senryaku/houkoku/ofure) — ashigaru1 — completed
- subtask_952: zatsudan板+thread_replies+CLI — ashigaru2 — completed
- subtask_956: instructions 2ch板投稿ルール追加 — ashigaru2 — completed
- subtask_959: launch_mbp.sh 作成 — ashigaru2 — completed
- subtask_960: bench_ronin.sh 作成 — ashigaru2 — in_progress

## エージェント稼働状況

- ashigaru1: idle（subtask_961 待ち）
- ashigaru2: active（subtask_960 実行中）
- gunshi: idle
- ohariko: idle
"""

PRACTICAL_CASES = [
    (
        "summarize",
        (
            "以下の没日録データを読んで、3行以内で現在のシステム状況を要約してください。\n\n"
            + SAMPLE_BOTSUNICHIROKU
        ),
        ["cmd_", "subtask_", "ashigaru"],  # 関連キーワードが含まれるか
    ),
    (
        "extract_completed",
        (
            "以下の没日録データから、status が completed または done のコマンド(cmd_id)を全て抽出してください。\n\n"
            + SAMPLE_BOTSUNICHIROKU
            + "\n\ncmd_idのリストのみを出力してください。"
        ),
        ["cmd_431", "cmd_428", "cmd_427", "cmd_426"],
    ),
    (
        "next_action",
        (
            "以下の没日録データを見て、次に優先すべきアクションを1つ提案してください。\n\n"
            + SAMPLE_BOTSUNICHIROKU
        ),
        ["cmd_434", "subtask_960", "bench", "ベンチ"],
    ),
]


def test_practical() -> dict:
    print("[5/5] 実タスクテスト（没日録データ処理）...")

    results = []
    correct = 0

    for case_name, prompt, expected_keys in PRACTICAL_CASES:
        log(f"  [{case_name}] テスト中...")
        try:
            resp = call_generate(prompt, num_predict=400, timeout=180)
            output = resp.get("response", "")
            gen_tps = tps_from_resp(resp, "eval")

            # 期待キーワードのうち1つ以上が含まれるか（実タスクは柔軟評価）
            matches = [k for k in expected_keys if k in output]
            any_match = len(matches) >= 1
            if any_match:
                correct += 1

            results.append({
                "case": case_name,
                "expected_keywords": expected_keys,
                "matched_keywords": matches,
                "pass": any_match,
                "generation_tps": gen_tps,
                "output_preview": output[:300].replace("\n", "↵"),
                "status": "ok",
            })
            log(f"  [{case_name}] {'✓' if any_match else '✗'} matched={len(matches)}/{len(expected_keys)} tps={gen_tps}")

        except Exception as e:
            results.append({"case": case_name, "status": "error", "error": str(e)})
            log(f"  [{case_name}] エラー: {e}")

    total = len(PRACTICAL_CASES)
    accuracy = round(correct / total * 100, 1)
    log(f"  正答率: {correct}/{total} ({accuracy}%)")

    return {
        "test": "practical",
        "status": "ok",
        "accuracy_pct": accuracy,
        "correct": correct,
        "total": total,
        "details": results,
    }


# ── 結果集計・出力 ────────────────────────────────────────────────────────────

def build_report(results: list[dict], elapsed_total: float) -> dict:
    """没日録 report 形式で結果を集計する"""
    summary_parts = []
    for r in results:
        t = r["test"]
        if t == "speed":
            summary_parts.append(f"速度:{r['avg_generation_tps']}tok/s")
        elif t == "tool_calling":
            summary_parts.append(f"tool:{r['accuracy_pct']}%")
        elif t == "yaml_communication":
            summary_parts.append(f"yaml:{r['accuracy_pct']}%")
        elif t == "context_length":
            deg = r.get("degraded_at_tokens") or "OK"
            summary_parts.append(f"ctx劣化:{deg}")
        elif t == "practical":
            summary_parts.append(f"実タスク:{r['accuracy_pct']}%")

    return {
        "report_type": "benchmark",
        "model": MODEL,
        "ollama_base": OLLAMA_BASE,
        "run_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_total_sec": round(elapsed_total, 1),
        "summary": " | ".join(summary_parts),
        "results": results,
    }


def dump_yaml(data: dict, indent: int = 0) -> str:
    """シンプルなYAMLシリアライザ（PyYAML不要）"""
    lines = []
    pad = "  " * indent
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            lines.append(dump_yaml(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{pad}{k}:")
            for item in v:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        prefix = f"{pad}  - " if first else f"{pad}    "
                        first = False
                        if isinstance(iv, (dict, list)):
                            lines.append(f"{prefix}{ik}: <nested>")
                        else:
                            lines.append(f"{prefix}{ik}: {iv}")
                else:
                    lines.append(f"{pad}  - {item}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{pad}{k}: |")
            for line in v.split("\n"):
                lines.append(f"{pad}  {line}")
        else:
            lines.append(f"{pad}{k}: {v}")
    return "\n".join(lines)


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    test_map = {
        "speed":    test_speed,
        "tool":     test_tool_calling,
        "yaml":     test_yaml_communication,
        "context":  test_context_length,
        "practical": test_practical,
    }

    if RUN_TEST == "all":
        run_keys = list(test_map.keys())
    elif RUN_TEST in test_map:
        run_keys = [RUN_TEST]
    else:
        print(f"ERROR: 不明なテスト '{RUN_TEST}'。利用可能: {list(test_map.keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"[bench_ronin] 開始: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}")
    print(f"[bench_ronin] model={MODEL}  tests={run_keys}")
    print("")

    t_start = time.time()
    results = []
    for key in run_keys:
        try:
            r = test_map[key]()
            results.append(r)
        except Exception as e:
            results.append({"test": key, "status": "error", "error": str(e)})
            print(f"  [{key}] 致命的エラー: {e}", file=sys.stderr)
        print("")

    elapsed_total = time.time() - t_start
    report = build_report(results, elapsed_total)

    # ── 出力 ──────────────────────────────────────────────────────────────────
    print("=" * 60)
    print("[bench_ronin] 結果サマリー")
    print("=" * 60)
    print(f"  モデル  : {MODEL}")
    print(f"  実行時間: {report['elapsed_total_sec']}秒")
    print(f"  サマリー: {report['summary']}")
    print("")

    output_json = json.dumps(report, ensure_ascii=False, indent=2)

    if OUTPUT_FILE:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"[bench_ronin] 結果を保存: {OUTPUT_FILE}")
    else:
        print("--- JSON出力 ---")
        print(output_json)

    # 没日録 report 向け1行サマリーを stderr に出力（inbox_write.sh で使用可）
    print(f"\n[REPORT_SUMMARY] model={MODEL} {report['summary']} elapsed={report['elapsed_total_sec']}s",
          file=sys.stderr)


if __name__ == "__main__":
    main()

PYEOF
