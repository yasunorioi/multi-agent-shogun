# karo-kenshu.md — 検収・kenshu_gate操作手順

v4.0三階建て Phase 2/3: 老中による検収板(kenshu)読取・2F合議トリガー・kenshu_gate判定・判定後処理の全手順。

---

## Phase 3 フロー図（自動化）

```
足軽がkenshu板にPOST（Format A）
  │
  ▼ notify.py が自動検知 → 2Fメンバー(お針子/軍師)にsend-keys自動通知
  │
  ▼ 2F合議（kenshu板レスで自由議論）
  │
  ▼ kenshu_auto.py gate → kenshu_gate板に判定投稿 + scribe自動実行（DB書き戻し）
  │
  ├─ PASS  → git merge worktree-subtask-XXXX → git push fork main
  └─ FAIL  → herald自動実行（任務板通知 + severity分岐）
```

> **Phase 2との差分**: 老中の手動send-keys・手動scribe・手動heraldが `kenshu_auto.py` に置き換わる。
> フォールバックとして手動手順は引き続き有効。

---

## 検収板(kenshu)読取

```bash
# スレ一覧（足軽が納品したスレを確認）
curl -s http://localhost:8824/bbs/kenshu/subject.txt

# スレ内容取得（thread_idはsubject.txtのDAT名から拡張子除去）
curl -s http://localhost:8824/bbs/kenshu/dat/{thread_id}.dat \
  | python3 -c "
import sys
data = sys.stdin.buffer.read()
try: text = data.decode('cp932')
except: text = data.decode('utf-8', errors='replace')
for i, line in enumerate(text.strip().split('\n'), 1):
    fields = line.split('<>')
    body = fields[3].replace('<br>', '\n') if len(fields) > 3 else ''
    print(f'[{i}] {body[:300]}')
"
```

納品フォーマットA(delivery_interface_schema.md)で記載された以下フィールドを確認:
- `subtask_id` / `cmd_id` / `worker` / `branch`
- `diff_summary` / `test_result` / `commit_hash` / `self_review`

---

## 2F合議トリガー

### 自動トリガー（Phase 3標準 / notify.py稼働時）

```bash
python3 scripts/kenshu_auto.py trigger --thread {thread_id}
```

notify.pyがkenshu板を監視し、新着スレを検知した時点で自動発火する。
老中が明示的に呼ぶ必要があるのはフォールバック時のみ。

### フォールバック（手動 / notify.py不通時）

```bash
# お針子(ooku:agents.1)にsend-keys（2回に分ける）
tmux send-keys -t ooku:agents.1 '老中より: kenshu {thread_id} に納品あり。合議を頼む。'
tmux send-keys -t ooku:agents.1 Enter

# 軍師(ooku:agents.0)にsend-keys（2回に分ける）
tmux send-keys -t ooku:agents.0 '老中より: kenshu {thread_id} に納品あり。合議を頼む。'
tmux send-keys -t ooku:agents.0 Enter

# 勘定吟味役 外部監査（review）実行
python3 scripts/kanjou_ginmiyaku.py review --thread {thread_id} --board kenshu
```

**Bloom別ファストトラック（L1-L3）**: 2F合議スキップ。老中スポットチェックのみで step 9.7 へ。

---

## kenshu_gate判定投稿

合議結果を踏まえ、老中が kenshu_gate 板に判定を投稿する（Format B準拠）。

```bash
curl -X POST http://localhost:8824/bbs/test/bbs.cgi \
  -d "bbs=kenshu_gate" \
  -d "FROM=roju" \
  --data-urlencode "subject=subtask_XXXX 判定" \
  --data-urlencode "MESSAGE=subtask_id: subtask_XXXX
cmd_id: cmd_YYY
verdict: PASS
severity: S3
reviewers:
  - ohariko
  - gunshi
minimum_reviews: 2
summary: 全要件充足。テストPASS。懸念なし。
findings: []
tiebreaker: null" \
  -d "time=0"
```

| verdict | severity目安 |
|---------|------------|
| PASS | 省略可 |
| CONDITIONAL | S3(Minor) |
| FAIL | S3(Minor)/S2(Major)/S1(Critical) |

---

## 判定後処理

### scribe実行（DB書き戻し）

```bash
python3 scripts/kanjou_ginmiyaku.py scribe --thread {kenshu_gate_thread_id}
```

没日録DBにaudit recordを投入する。kenshu_gate thread_idはsubject.txtで確認。

### PASS → git merge

```bash
# worktreeブランチをmainにマージ
git merge worktree-subtask-XXXX

# マージ後worktree削除
git worktree remove /tmp/worktree-subtask-XXXX

# fork push
git push fork main
```

### FAIL → herald確認

```bash
python3 scripts/kanjou_ginmiyaku.py herald --thread {kenshu_gate_thread_id}
```

- S3: 任務板にリジェクト通知POST → 足軽に差し戻し
- S2: リジェクト通知 + search連携（類似パターン提示）
- S1: CRITICAL警告 → 老中が直接対処

---

## kenshu_auto.py 利用手順（Phase 3）

`scripts/kenshu_auto.py` は検収フローの自動化CLI。trigger/status/gate の3サブコマンドを持つ。

### trigger — 2F合議トリガー発火

```bash
python3 scripts/kenshu_auto.py trigger --thread {kenshu_thread_id}
```

- kenshu板の指定スレを読み取り、お針子・軍師にsend-keys自動通知
- 勘定吟味役のreviewも自動起動
- notify.py稼働中は自動検知のため手動呼出し不要

### status — レビュー状況確認

```bash
python3 scripts/kenshu_auto.py status --thread {kenshu_thread_id}
```

- kenshu板スレのレス数・参加者・合議進捗を表示
- gate実行前の確認に使う

### gate — 判定投稿 + scribe + herald 一括実行

```bash
# PASS判定
python3 scripts/kenshu_auto.py gate \
  --thread {kenshu_thread_id} \
  --subtask subtask_XXXX \
  --cmd cmd_YYY \
  --verdict PASS

# FAIL判定（severity必須）
python3 scripts/kenshu_auto.py gate \
  --thread {kenshu_thread_id} \
  --subtask subtask_XXXX \
  --cmd cmd_YYY \
  --verdict FAIL \
  --severity S3
```

gate コマンドは以下を一括実行する:
1. kenshu_gate板に判定投稿（Format B）
2. 勘定吟味役 scribe 実行（没日録DB書き戻し）
3. FAIL時: herald 実行（任務板通知 + severity分岐）

| verdict | severity | gateの動作 |
|---------|---------|-----------|
| PASS | — | kenshu_gate POST + scribe |
| CONDITIONAL | S3/S4 | kenshu_gate POST + scribe |
| FAIL | S1-S3 | kenshu_gate POST + scribe + herald |

---

## worktreeブランチ管理

```bash
# 一覧確認
git worktree list

# 作成（足軽が1F実装用に作る場合の参考）
git worktree add /tmp/worktree-subtask-XXXX -b worktree-subtask-XXXX

# マージ後削除
git worktree remove /tmp/worktree-subtask-XXXX

# 強制削除（ファイルが残っている場合）
git worktree remove --force /tmp/worktree-subtask-XXXX
git branch -d worktree-subtask-XXXX
```

---

## デュアルモード監視手順（Phase 2.5）

Phase 2.5では老中が **YAML inbox** と **BBS板** の両方を監視する。

### 老中の監視役割

| チャネル | 監視内容 | アクション |
|---------|---------|-----------|
| YAML inbox (`roju_reports.yaml`) | 足軽の完了報告 (`status: completed`) | `read: false` エントリを確認 |
| BBS kenshu板 | 新着スレ（足軽の納品POST） | step 9.5〜9.9 の検収フロー起動 |
| kenshu_gate板 | 合議結果の判定投稿 | PASS→マージ / FAIL→herald |

### kenshu板の新着確認（定期実施）

```bash
# kenshu板スレ一覧 — 未処理のスレを探す
curl -s http://localhost:8824/bbs/kenshu/subject.txt
```

未処理スレの判定基準:
- kenshu_gate板に対応するsubtask_idの判定投稿がない
- roju_reports.yaml に対応する `read: true` エントリがない

### 突合確認（YAML vs BBS）

移行期は足軽がYAML報告とBBS POSTの**両方**を実施しているかを確認せよ。

```bash
# BBS確認: kenshuに納品スレがあるか
curl -s http://localhost:8824/bbs/kenshu/subject.txt | grep "subtask_XXXX"

# YAML確認: roju_reports.yamlに報告エントリがあるか
grep "subtask_XXXX" queue/inbox/roju_reports.yaml
```

| 状態 | 対処 |
|------|------|
| YAML◯ + BBS◯ | 正常。step 9.5〜9.9 を進める |
| YAML◯ + BBS✕ | 足軽にkenshu POST再実行を指示（BBS不通時は例外） |
| YAML✕ + BBS◯ | 足軽にroju_reports.yaml報告を指示 |
| YAML✕ + BBS✕ | 足軽にsend-keys通知して確認 |

---

## 関連ドキュメント

- `docs/shogun/delivery_interface_schema.md` — Format A/B仕様
- `docs/shogun/v4_three_story_architecture.md §2.1` — 合議フロー
- `docs/shogun/v4_three_story_architecture.md §6` — Phase 2.5デュアルモード
- `scripts/kanjou_ginmiyaku.py` — review/scribe/herald/search
