# 勘定吟味役（かんじょうぎんみやく）

自動監査ツール — Phase 0-1 実装

## 概要

お針子（Claude Code監査官）の監査業務を補助する軽量ツール。
ルールベースの形式チェック + Qwen2.5-Coder（Ollama経由）による補完検出を行い、
構造化JSON（PreAuditReport）を出力する。

## セットアップ

```bash
pip install -r tools/kanjou/requirements.txt
```

Ollama（オプション・Qwen補完チェック用）:
```bash
ollama pull qwen2.5-coder:1.5b
ollama serve
```

## 使い方

### Phase 0: Ollama疎通確認

```bash
python3 -m tools.kanjou.kanjou_ginmiyaku --phase0
```

### Phase 1: subtask監査

```bash
python3 -m tools.kanjou.kanjou_ginmiyaku --audit subtask_560
```

### テスト実行

```bash
pytest tools/kanjou/test_kanjou.py -v
```

## 出力

JSON形式の `PreAuditReport`:

```json
{
  "subtask_id": "subtask_560",
  "kousatsu_ok": true,
  "format_check": {
    "issues": [],
    "severity": "ok"
  },
  "checklist_check": {
    "coverage_ratio": null,
    "uncovered_items": [],
    "similar_tasks": [],
    "worker_approval_rate": 0.95
  },
  "skill_evaluation": null,
  "pre_verdict": "likely_approved"
}
```

## 設計書

`docs/kanjou_ginmiyaku_design.md` を参照。

## 前提条件

- **Ollama未起動時**: Qwen補完チェックはスキップ（ルールベースのみで動作）
- **高札Docker未起動時**: `kousatsu_ok=false`でフォールバック
- **DB未作成時**: subtask/report情報は空文字列
