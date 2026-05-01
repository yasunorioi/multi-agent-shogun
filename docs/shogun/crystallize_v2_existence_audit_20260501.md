# 結晶化機構v2 実在性調査レポート (subtask_1201 / cmd_570)

**作成者**: ashigaru1  
**作成日時**: 2026-05-01T22:52:03  
**調査対象**: commit 244b2af `feat(crystallize): cmd_517 結晶化機構v2`  
**調査方針**: 老中暫定報告に依存せず、一次情報（git/find/grep/pytest）のみで独立検証

---

## §1 結論

**判定: 実在（稼働中） — ハルシネーションではない**

| 検証項目 | 判定 | 根拠 |
|---------|------|------|
| commit 244b2af 実体 | ✅ 実在 | `git show 244b2af --stat` → 4ファイル変更確認 |
| scripts/botsu/crystallize.py | ✅ 実在 | 現HEAD 234行、削除commitなし |
| cmd.py フック | ✅ 実在 | cmd_update('done') → crystallize_cmd() 呼び出し確認 |
| crystals板 DAT | ✅ 実在 | swarm.db thread_replies に crystals板 16スレッド存在 |
| crystals/*.md 目次 | ✅ 実在 | agent-swarm/crystals/{shogun,hardware,tooling}.md 確認 |
| テスト6件PASS | ✅ 確認 | pytest 6 passed in 0.04s |
| 稼働実績 | ✅ 16回 | cmd_555〜cmd_568 まで 16 cmd が結晶化済み |

**ハルシネーション疑惑の真因**: 家老の即席チェックが `scripts/` 直下のみ検索し、`scripts/botsu/` サブディレクトリを見落とした検索ミス。機構自体は完全に稼働している。

**仕様ドリフト（告知内容の誤り）**: 3点の誤記が確認された（§5参照）。機構の実在を否定するものではないが、正確な記述が求められる。

---

## §2 commit 244b2af 実体検査

### ファイル変更リスト

```
$ git show 244b2af --stat
commit 244b2af06ceb688800691132824cc4943c796c37
Author: yasu <bb.folf@gmail.com>
Date:   Wed Apr 29 00:13:20 2026 +0900

    feat(crystallize): cmd_517 結晶化機構v2 (DAT本体+MD目次ハイブリッド)

 .env.example                 |  16 +++
 scripts/botsu/cmd.py         |   8 ++
 scripts/botsu/crystallize.py | 234 +++++++++++++++++++++++++++++++++++++
 tests/test_crystallize.py    | 115 +++++++++++++++++++++
 4 files changed, 373 insertions(+)
```

### crystallize.py 現HEAD行数

```
$ git cat-file -p HEAD:scripts/botsu/crystallize.py | wc -l
234
```

削除commit: なし（`git log --oneline -- scripts/botsu/crystallize.py` → 1件のみ: `244b2af`）

### cmd.py フック箇所（scripts/botsu/cmd.py）

```python
# 行118-122
if args.status == 'done':
    try:
        from botsu.crystallize import crystallize_cmd
        crystallize_cmd(args.cmd_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"crystallize failed: {e}")
```

graceful degradation（失敗時 warning のみ・cmd完了処理を阻害しない）が実装通りに確認された。

---

## §3 scripts/context/swarm.yaml 各実在状況（物理確認結果）

### scripts/botsu/crystallize.py

```
$ ls -la scripts/botsu/crystallize.py
-rw-rw-r-- 1 yasu yasu 7924 Apr 29 00:07 scripts/botsu/crystallize.py
```
✅ 実在（7924バイト、234行）

### agent-swarm/crystals/*.md 目次ファイル

```
$ ls -la /home/yasu/agent-swarm/crystals/
total 20
drwxrwxr-x  2 yasu yasu 4096 Apr 30 11:25 .
drwxrwxr-x 11 yasu yasu 4096 Apr 29 00:04 ..
-rw-rw-r--  1 yasu yasu    0 Apr 29 00:04 .gitkeep
-rw-rw-r--  1 yasu yasu 1008 May  1 21:52 hardware.md
-rw-rw-r--  1 yasu yasu 1254 Apr 29 20:43 shogun.md
-rw-rw-r--  1 yasu yasu 2178 Apr 30 01:39 tooling.md
```

✅ 3つのMD目次ファイル実在（shogun/hardware/tooling 各プロジェクト分）

**注意: 「context/*.md」への追記は設計外**  
crystallize.py の追記先は `${SHOGUN_CRYSTALS_DIR}/{project}.md`（デフォルト `/home/yasu/agent-swarm/crystals/{project}.md`）であり、`multi-agent-shogun/context/*.md` ディレクトリへの書き込みは設計通り行われていない。commit メッセージ「context/*.md自動更新」はv1設計の名残であり、v2実装では `agent-swarm/crystals/*.md` が正の追記先である。

### swarm.yaml crystals板定義

```
$ grep -r "crystals" /home/yasu/agent-swarm/config/swarm.yaml
  crystals:
```
✅ boards に crystals 板が定義済み

### swarm.db DAT実体

```python
# swarm.db の thread_replies テーブル
board    count
-------  -----
crystals   80  # 16スレッド × 5レス(>>1-5)
```
✅ SQLite `thread_replies` テーブルに crystals 板 80行（16スレッド × >>1-5）確認

---

## §4 テスト実行結果

### pytest 実行ログ

```
$ python3 -m pytest tests/test_crystallize.py -v

============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.3, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/yasu/multi-agent-shogun
plugins: typeguard-4.4.2
collecting ... collected 6 items

tests/test_crystallize.py::test_template_generation       PASSED  [ 16%]
tests/test_crystallize.py::test_md_append_new             PASSED  [ 33%]
tests/test_crystallize.py::test_md_append_idempotent      PASSED  [ 50%]
tests/test_crystallize.py::test_disable_kill_switch       PASSED  [ 66%]
tests/test_crystallize.py::test_cmd_not_found             PASSED  [ 83%]
tests/test_crystallize.py::test_dat_existing_skips_post   PASSED  [ 100%]

============================== 6 passed in 0.04s
===============================
```

✅ テスト6件 全PASS（commit 244b2af 報告と一致）

テスト副作用: なし（全テストがモック/temp dir使用、実DB/実DATに書き込まない設計を確認）

---

## §5 遡及検証

### crystals板 全稼働記録（通算カウント）

| 回 | 日付 | cmd_id | project |
|----|------|--------|---------|
| 1 | 2026-04-28 | cmd_555 | tooling |
| 2 | 2026-04-28 | cmd_557 | shogun |
| 3 | 2026-04-28 | cmd_558 | shogun |
| 4 | 2026-04-29 | cmd_552 | tooling |
| 5 | 2026-04-29 | cmd_516 | shogun |
| 6 | 2026-04-29 | cmd_517 | shogun |
| 7 | 2026-04-29 | cmd_559 | tooling |
| 8 | 2026-04-29 | cmd_560 | tooling |
| 9 | 2026-04-29 | cmd_561 | tooling |
| 10 | 2026-04-29 | cmd_562 | tooling |
| 11 | 2026-04-29 | cmd_563 | tooling |
| 12 | 2026-04-29 | cmd_564 | tooling |
| 13 | 2026-04-30 | cmd_565 | hardware |
| 14 | 2026-04-30 | cmd_566 | hardware |
| 15 | 2026-04-30 | cmd_567 | hardware |
| 16 | 2026-05-01 | cmd_568 | hardware |

「稼働告知に虚偽はあったか」→ **機構稼働自体は全て事実**。以下の誤記が判明した：

### 確認された告知誤記（仕様ドリフト）

| 誤記箇所 | 誤った告知 | 正しい内容 | 出所 |
|---------|-----------|-----------|------|
| subtask_1200タスク指示 | 「結晶化13回目稼働」 | crystals板通算**16回目** | ashigaru6.yaml L3467 |
| subtask_1200タスク指示 | 「context/hardware.md に自動追記」 | `agent-swarm/crystals/hardware.md` に追記 | ashigaru6.yaml L3467 |
| subtask_1200タスク指示 | 「scripts/crystallize_v2.py」 | `scripts/botsu/crystallize.py` | ashigaru6.yaml L3467 |
| commit / cmd_517名称 | 「context/*.md自動更新」 | `agent-swarm/crystals/*.md` への追記 | commit 244b2af, cmd詳細 |

**「13回目」の誤りの原因推定**: roju_reports.yaml の稼働カウント記録（「9連続稼働」がcmd_564）を基に、cmd_565/566/567 の3回を加算して 9+4=13 と計算したと思われるが、crystal板通算では5回目から遡及追加されたcmd_516/cmd_517が含まれるため16回目が正しい。

**「context/*.md」誤称の原因**: cmd_517設計書v1ではcontext/ディレクトリへの追記を構想していたが、v2（2026-04-28殿裁定）でagent-swarmのDAT+MD目次方式に変更された。コード・設計書v2は正しいが、cmd名称・commit メッセージにv1の名称が残存した。

---

## §6 再発防止策案

### P1: 検索パス不足によるhide（家老の即席チェック失敗）

**問題**: `find scripts -name "crystall*"` でヒットするにも関わらず、`scripts/botsu/` サブディレクトリを見落とした。

**案**: 家老の「確認コマンド」テンプレートに `find scripts -name "*.py" | xargs grep -l 機能名` のようなgrep経由確認を追加する。

### P2: 告知カウントの誤り（13回目 → 実際は16回目）

**問題**: crystals板のSQLiteを参照せずに手計算した結果、roju_reports記録の「9連続稼働」から誤カウント。

**案**: `botsunichiroku.py cmd show cmd_XXX` の詳細にcrystalas板の通算カウントを自動表示する機能追加（家老が告知する際に使えるコマンドとして）。

### P3: 名称ドリフト（「context/*.md」 vs 実際の追記先）

**問題**: v1→v2設計変更時にcmd名称・commitメッセージが旧称のまま残存。後から機構を参照するエージェントが混乱する。

**案**: 
- cmd_517の `command` フィールドを「結晶化機構v2（agent-swarm/crystals/*.md目次+DATスレ）」に更新依頼（殿・家老判断）
- `.env.example` に `SHOGUN_CRYSTALS_DIR` の説明を追記（現状ではコメントのみ）

### P4: お針子監査の強化

**問題**: subtask_1184（cmd_558実装）の監査で上記誤記が見落とされた（`needs_audit: false` であった可能性）。

**案**: 結晶化機構のような「既存機構への影響を持つ実装」には `needs_audit: true` を必須とし、お針子がパス名・カウント整合性を確認するチェック項目を追加する。

---

*調査実施: ashigaru1 | subtask_1201 / cmd_570 | 2026-05-01T22:52:03*
