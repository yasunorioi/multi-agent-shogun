---
name: skill-name
description: |
  このスキルが何をするか、いつ使うかを具体的に記述。
  例: "uecs-llmをRPiにデプロイする。git pull + setup.sh + systemctl restart のワークフロー。
  RPiデプロイ指示を受けた足軽が使用。"
trigger: |
  スキル発動条件。例:
  - "cmd種別がdeploy"
  - "足軽がRPiデプロイ指示を受けた時"
  - "setup.sh対象ファイル追加時"
target_path: /path/to/project   # 対象プロジェクトパス（省略可）
needs_audit: false               # 監査要否（true=お針子レビュー必要）
output_format: report            # commit / report / yaml / none
arguments:
  - $PROJECT      # プレースホルダ変数の説明
  - $TARGET_FILE
agent_type: 足軽                 # 推奨実行エージェント（足軽/部屋子/お針子）
---

# Skill Name（日本語タイトル）

## Purpose

このスキルが解決する問題・目的を1〜3文で記述。
なぜ繰り返し使えるパターンとしてスキル化したか。

## Context

- **対象リポジトリ**: `$PROJECT`（例: /home/yasu/uecs-llm）
- **対象ファイル**: 必要に応じて列挙
- **前提条件**: SSH接続可能、git管理済み、等
- **エージェント**: 足軽1（ashigaru1）が実行

## Instructions

### Step 1: 事前確認

```bash
# 確認コマンド例
git status
```

- チェック項目1
- チェック項目2

### Step 2: メイン作業

```bash
# 作業コマンド例
git add $TARGET_FILE
git commit -m "fix: $TARGET_FILE 修正"
```

### Step 3: 動作確認

```bash
# 確認コマンド
curl -s http://localhost:8501/ | head -5
```

### Step 4: 報告

`queue/inbox/roju_reports.yaml` に以下を記入して老中へ send-keys:

```yaml
- cmd_id: $CMD_ID
  commit: $COMMIT_HASH
  needs_audit: false
  read: false
  reported_at: 'YYYY-MM-DDTHH:MM:SS'
  skill_candidate: なし
  status: done
  subtask_id: $SUBTASK_ID
  summary: |
    $SUMMARY
  worker: ashigaru1
```

## Notes

- 注意事項1（例: `set -euo pipefail` がある場合、エラーで即中断）
- 注意事項2（例: `/etc/agriha` は root 所有のためsudo必要）
- 失敗時の対処: ...

## Changelog

| Version | Date       | Author    | Notes     |
|---------|------------|-----------|-----------|
| 1.0     | 2026-03-08 | ashigaru1 | 初版作成  |
