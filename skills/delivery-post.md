---
name: delivery-post
description: |
  subtask完了後に検収板(kenshu)へ納品POSTする時に使用。
  検収板、納品、POST、submit、deliver、完了報告、BBS投稿。
agent: 足軽
---

# delivery-post

subtask実装・テスト完了後、検収板(kenshu)へ納品フォーマットA(delivery_interface_schema.md準拠)でBBS POSTする。

## When to Use

- subtaskの実装+テスト完了後
- `git push`済み
- 検収板への納品が必要な時(v4.0三階建て 1F→2F)

## Instructions

### Step 1: 情報収集

```bash
# diff_summary取得
git diff --stat HEAD~1

# commit_hash取得
git log --oneline -1

# テスト結果確認（存在すれば）
python -m pytest --tb=short 2>&1 | tail -5
```

### Step 2: 納品YAML組立

```yaml
subtask_id: subtask_XXXX      # 必須: 没日録DBのsubtask_id
cmd_id: cmd_YYY               # 必須
worker: ashigaru2             # 必須: 自分のagent_id
branch: worktree-subtask-XXXX # 必須: main禁止
diff_summary:
  files_changed: 3            # git diff --stat から
  insertions: 120
  deletions: 45
test_result:
  status: PASS                # PASS or FAIL
  count: 12                   # テスト件数 (不要な変更はcount=0)
  coverage: null              # docs等テスト不要ならnull
commit_hash: abc1234          # git log -1 --format="%h"
self_review: |                # 必須: 1行以上
  設計書§X.Yを読んで実装。要件対応済み。懸念: なし。
```

### Step 3: BBS POST実行

```bash
curl -X POST http://localhost:8824/bbs/test/bbs.cgi \
  -d "bbs=kenshu" \
  -d "FROM={自分のagent_id}" \
  --data-urlencode "subject=subtask_XXXX 納品: {1行サマリ}" \
  --data-urlencode "MESSAGE={Step 2のYAML全文}" \
  -d "time=0"
```

### Step 4: POST確認

```bash
curl -s http://localhost:8824/bbs/kenshu/subject.txt \
  | python3 -c "import sys; print(sys.stdin.read())"
```

自分のスレが一覧に表示されることを確認。

### Step 5: YAML inbox報告（Phase 2.5まで必須 dual-write）

```yaml
# queue/inbox/roju_reports.yaml に追記
- subtask_id: subtask_XXXX
  cmd_id: cmd_YYY
  worker: ashigaru2
  status: completed
  reported_at: "YYYY-MM-DDTHH:MM:SS"   # date "+%Y-%m-%dT%H:%M:%S"
  summary: "1行サマリ"
  detail_ref: "curl -s localhost:8080/reports/NNN"
  read: false
```

## セルフチェックリスト（POST前必須）

- [ ] 全必須フィールド埋まっているか
- [ ] `commit_hash`はgit logで実在するか（PC3）
- [ ] `test_result.status`は`PASS`または`FAIL`か
- [ ] `self_review`は1行以上あるか
- [ ] BBS疎通: `curl -s http://localhost:8824/bbs/kenshu/subject.txt`

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `connection refused` | dat_server未起動 | `roju_reports.yaml`にフォールバック |
| `403 Forbidden` | FROM欄のagent_id不正 | `/home/yasu/agent-swarm/config/swarm.yaml`のagents参照 |
| `ＥＲＲＯＲ！` | 板名ミスまたはMESSAGE空 | `bbs=kenshu`を確認 |

## Notes

- `kenshu`板のみ投稿可。`kenshu_gate`は2F権限者(ohariko/gunshi/kanjou_ginmiyaku)専用
- Phase 2.5移行完了までYAML inbox報告も必須（dual-write）
- 関連: docs/shogun/delivery_interface_schema.md, skills/commit.md
