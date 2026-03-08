---
name: agriha-deploy
description: |
  uecs-llm (AgriHA) をRPi (unipi@10.10.0.10) にデプロイする。
  git pull + setup.sh再実行 + systemctl restart のワークフロー。
  RPiデプロイ指示を受けた足軽が使用。コミット済みコードをRPi本番環境へ反映する。
trigger: |
  - RPiデプロイ指示を受けた時（cmd種別がdeploy相当）
  - setup.sh変更後にRPiへ反映が必要な時
  - /etc/agriha/ 配下のファイル追加・変更後
target_path: /home/yasu/uecs-llm
needs_audit: false
output_format: report
arguments:
  - $COMMIT_HASH   # デプロイするコミットハッシュ
  - $CMD_ID        # 対応するcmd ID
  - $SUBTASK_ID    # 対応するsubtask ID
agent_type: 足軽
---

# agriha-deploy（AgriHA RPiデプロイ）

## Purpose

uecs-llm の変更をRPi本番環境（unipi@10.10.0.10）へ反映する。
`git push` 後にRPi側で `git pull + setup.sh + systemctl restart` を実行する
一連の手順をスキル化。デプロイ漏れ・手順ミスを防ぐ。

## Context

- **対象リポジトリ**: `/home/yasu/uecs-llm`（ローカル）、 `/opt/agriha`（RPi）
- **RPi接続**: `ssh unipi@10.10.0.10`
- **サービス**: `agriha-ui`（uvicorn, ポート8501）
- **設定ディレクトリ**: `/etc/agriha/`（owner: agriha:agriha 755）
- **前提条件**: ローカルでコミット・`git push origin main` 済み
- **エージェント**: 足軽1（ashigaru1）が実行

## Instructions

### Step 1: ローカルでコミット・プッシュ確認

```bash
cd /home/yasu/uecs-llm
git log --oneline -3
git push origin main 2>&1
```

- プッシュ成功を確認してから次へ進む
- 失敗時はリモートとのconflictを解消してから再実行

### Step 2: RPi git pull

```bash
ssh unipi@10.10.0.10 'cd /opt/agriha && sudo git pull origin main 2>&1'
```

- Fast-forward が表示されることを確認
- 変更ファイル一覧を目視確認

### Step 3: setup.sh 再実行

```bash
ssh unipi@10.10.0.10 'cd /opt/agriha && sudo bash setup.sh 2>&1'
```

- 各ステップの `→ ファイル名 コピー` / `→ 既存 → スキップ` を確認
- エラーが出た場合は原因を調査してから再実行

### Step 4: サービス再起動・確認

```bash
ssh unipi@10.10.0.10 'sudo systemctl restart agriha-ui && sleep 3 && systemctl is-active agriha-ui'
```

- `active` が返ることを確認
- `failed` の場合: `journalctl -u agriha-ui --no-pager -n 30` でログ確認

### Step 5: 配置ファイル確認（必要に応じて）

```bash
ssh unipi@10.10.0.10 'ls -la /etc/agriha/'
```

- 新規追加したファイルが `agriha:agriha 664` で存在することを確認

### Step 6: 報告

`queue/inbox/roju_reports.yaml` に記入して老中へ send-keys:

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
    RPiデプロイ完了。git pull + setup.sh + systemctl restart。
    agriha-ui: active ✓
  worker: ashigaru1
```

```bash
tmux send-keys -t multiagent:agents.0 '【足軽1より報告】$CMD_ID/$SUBTASK_ID完了。RPiデプロイ完了。$COMMIT_HASH。roju_reports.yaml確認されたし。'
tmux send-keys -t multiagent:agents.0 Enter
```

## Notes

- `setup.sh` は `set -euo pipefail` 付きのため、エラーで即中断する
- `/etc/agriha/` は既存ファイルを上書きしない設計（農家の手動編集を保護）
- `api.env` は root 所有のため setup.sh では変更しない（意図的）
- `unipi_daemon.yaml` はハードウェア設定のため root:agriha 640 を維持
- pip install が `ProtocolError` で Warning を出すことがあるが完了すれば問題なし
- RPiとSSH接続できない場合: ネットワーク疎通確認 `ping 10.10.0.10`

## Changelog

| Version | Date       | Author    | Notes                                  |
|---------|------------|-----------|----------------------------------------|
| 1.0     | 2026-03-08 | ashigaru1 | 初版（cmd_356〜357のデプロイ経験より） |
