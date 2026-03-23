# 2ch互換CGI全面置換設計 — 通信レイヤーの2ch化

> **軍師分析** | 2026-03-23 | North Star: 通信レイヤーを2chに統一せよ。没日録スキーマは壊すな。殿がJDimだけで全てを把握できる世界を設計せよ

---

## 結論（先に述べる）

**全面置換を推奨する。YAML inbox通信を thread_replies テーブル（2chスレ書き込み）に完全移行する。**

| 置換対象 | 判定 | 理由 |
|---------|:----:|------|
| YAML inbox → 2chスレ（任務板） | **やる** | SQLite WAL > YAMLファイル。原子的書き込み、排他制御、JDim閲覧 |
| shogun_to_karo.yaml → 殿がJDimからスレ立て | **やる** | bbs.cgi→send-keysフックが既に稼働 |
| roju_reports.yaml → 足軽がスレにレス | **やる** | 報告の流れが自然（スレ内で対話完結） |
| dashboard.md → 管理板固定スレ | **段階的** | Phase 1は並行運用、Phase 2で統合 |
| roju_ohariko.yaml → 監査板スレ | **やる** | 監査→差し戻し→再監査がスレ上で追跡可能 |
| 没日録DBスキーマ | **変更なし** | 前回分析の結論を踏襲。構造化データはDB |
| 没日録CLI | **変更なし** | cmd/subtask/report の全CLIコマンドは維持 |

---

## 0. 設計原理 — 三層分離の深化

前回分析で確立した三層分離（保存/検索/表示）に、今回「通信」レイヤーを追加する:

```
┌──────────────────────────────────────────────┐
│             通信レイヤー（Message）  ← NEW      │
│  thread_replies テーブル（bbs.cgi POST）        │
│  ├── 任務板: タスク指示・完了報告               │
│  ├── 監査板: 監査依頼・結果                     │
│  ├── 軍師板: 戦略分析依頼・報告                 │
│  └── 雑談板: 対話・御触（既存）                 │
├──────────────────────────────────────────────┤
│             表示レイヤー（View）                 │
│  dat_server.py + botsunichiroku_2ch.py         │
│  ├── 管理板: CMD/subtask構造化ビュー（DB生成）   │
│  ├── 日記板・夢見板                             │
│  └── JDim が統一UI                             │
├──────────────────────────────────────────────┤
│             検索レイヤー（Search）               │
│  FTS5 search_index（没日録DB内）                │
├──────────────────────────────────────────────┤
│             保存レイヤー（Storage）              │
│  没日録DB — 現行スキーマ不変                     │
│  commands / subtasks / reports / etc.           │
└──────────────────────────────────────────────┘
```

**核心的洞察**: YAML inboxは「通信」と「保存」を1ファイルで兼ねていた。これを分離する:
- **通信** → thread_replies（2chスレ）— 人間が読める、JDim閲覧可能
- **保存** → 没日録DB（既存テーブル）— 構造化クエリ、CLI互換

---

## 1. YAML inbox → 2chスレ置換の設計（最重要）

### 1.1 現行フロー vs 新フロー

**現行:**
```
老中 → Edit ashigaru1.yaml → send-keys "タスク割り当てた"
足軽 → Read ashigaru1.yaml → 作業 → Edit roju_reports.yaml → send-keys "完了報告"
老中 → Read roju_reports.yaml → 処理
```

**問題点:**
- YAMLファイルの同時編集でデータ破損リスク（足軽が読んでいる間に老中が書く）
- YAMLが肥大化（定期的なGCが必要。shogun-gc.sh）
- 殿からはYAMLの中身が見えない（JDimで閲覧不可）
- 報告の`read: false/true`フラグ管理が煩雑

**新フロー:**
```
老中 → bbs.cgi POST (任務板/cmd_XXX) → [自動] send-keys通知
足軽 → スレ読み(reply list) → 作業 → bbs.cgi POST (完了報告) → [自動] send-keys通知
老中 → スレ読み → DB更新
```

**利点:**
- SQLite WAL: 原子的INSERT、読み書き並行可能
- send-keys通知が bbs.cgi に組み込み済み（二重管理不要）
- 殿がJDimで全通信を閲覧可能
- GC不要（thread_repliesは1000レスでdat落ち。自然な寿命管理）

### 1.2 YAML通信の何を2chに移し、何をDB/YAMLに残すか

| 現行の情報 | 移行先 | 理由 |
|-----------|--------|------|
| タスク指示テキスト（description） | **thread_replies** | 人間可読。JDim閲覧 |
| 完了報告テキスト（summary） | **thread_replies** | 対話の一部として自然 |
| context_files, target_path | **thread_replies body** | 指示テキストに含める |
| bloom_level, needs_audit | **没日録DB subtasks** | 構造化メタデータ |
| status (assigned/done) | **没日録DB subtasks** | CLIクエリの正データ |
| wave, blocked_by | **没日録DB subtasks** | DAG構造はDB |
| skill_candidate | **thread_replies** | 老中への提案テキスト |
| detail_ref | **thread_replies** | 参照ポインタ |
| read: true/false | **廃止** | スレ上でレス番号で既読管理（JDim標準機能） |

**原則**: 「人間が読む文章」→ thread_replies、「機械がクエリするフィールド」→ 没日録DB

### 1.3 任務板スレッドの構造

**スレ粒度: CMD単位（1 CMD = 1スレ）**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【任務板】cmd_435 — 2ch通信レイヤー全面置換
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1 名前：老中 ◆ROJU 2026/03/23(日) 14:00:00
  [cmd_435] 2ch通信レイヤー全面置換
  priority: high | project: shogun
  ───────────────
  タスク詳細はこのスレで配布する。

2 名前：老中 ◆ROJU 2026/03/23(日) 14:05:00
  [subtask_961] @ashigaru1 ■ 実装: bbs.cgiに任務板書き込み権限追加
  bloom: L2 | wave: 1 | needs_audit: true
  target: scripts/botsu/nich.py, scripts/dat_server.py
  ───
  WRITABLE_BOARDS拡張 + BOARD_WRITERS権限マトリクス実装。
  context: docs/shogun/2ch_workflow_design.md §3

3 名前：老中 ◆ROJU 2026/03/23(日) 14:05:00
  [subtask_962] @ashigaru2 ■ 実装: 通知ルーティング拡張
  bloom: L3 | wave: 1 | needs_audit: true
  target: scripts/dat_server.py
  ───
  _notify_thread → _notify_by_board に改修。@メンション解析。
  context: docs/shogun/2ch_workflow_design.md §3.3

4 名前：足軽1 ◆ASH1 2026/03/23(日) 16:00:00
  [report] subtask_961 完了。WRITABLE_BOARDS拡張+BOARD_WRITERS実装。
  commit: abc1234 push済み。
  テスト: curl -s -X POST ... で任務板書き込み確認OK。

5 名前：お針子 ◆OHRK 2026/03/23(日) 16:30:00
  [audit] subtask_961 監査完了。13/15点。PASS。
  べ、別にあなたのために監査したんじゃないんだからね！
```

### 1.4 status管理 — 没日録DBが正、スレは通知

**Status のライフサイクル:**

```
[DB] subtask add → status: assigned
  ↓ 同時に
[2ch] 老中が任務板スレにレス "[subtask_XXX] @agent ■ タスク内容"

[2ch] 足軽がレス "[status: in_progress] subtask_XXX 着手"
  ↓ 老中がスレ読み → DB更新
[DB] subtask update → status: in_progress

[2ch] 足軽がレス "[report] subtask_XXX 完了。summary..."
  ↓ 老中がスレ読み → DB更新
[DB] subtask update → status: done
[DB] report add → 構造化報告データ
```

**重要**: 足軽は没日録DBへの書き込み権限がない。足軽のstatus更新はスレへのレス投稿のみ。老中がスレを読んでDB側を更新する（現行のYAML→DB更新と同じ責任分担）。

### 1.5 足軽のinbox読み込み方式

**現行:**
```bash
# 足軽が自分のinboxを読む
Read queue/inbox/ashigaru1.yaml → status: assigned のタスクを探す
```

**新方式:**
```bash
# 足軽が任務板で自分宛のタスクを検索
python3 scripts/botsunichiroku.py reply list-for @ashigaru1 --board ninmu --unread
# または
python3 scripts/botsunichiroku_2ch.py --board ninmu --grep "@ashigaru1"
```

**CLI追加案:**
```python
# botsunichiroku.py に追加
# reply list-for <agent> --board <board>
# → thread_replies WHERE board = ? AND body LIKE '%@agent%' ORDER BY id DESC
```

これにより足軽は自分宛のタスクをCLIで一覧取得できる。JDimでも任務板を開けば全タスクが見える。

---

## 2. dashboard.md → 管理板固定スレ設計

### 2.1 現行dashboard.mdの構造

```markdown
# Dashboard
## 🚨 要対応（殿の判断待ち）
## 進行中 (CMD)
## 今日の戦果
## 足軽の稼働状況
```

### 2.2 固定スレ方式（推奨）

**kanri板（管理板）に「dashboard」スレッドを作成。**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【管理板】dashboard — 今日の戦況
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

42 名前：老中 ◆ROJU 2026/03/23(日) 18:00:00
  [dashboard update]

  ■ 🚨 要対応
  - PDCAエスカレーション: subtask_950（3回FAIL）

  ■ 進行中
  | CMD | 内容 | 状態 |
  | cmd_434 | 浪人ベンチマーク | subtask_959,960 完了 |
  | cmd_435 | 2ch通信置換 | 設計中 |

  ■ 足軽稼働
  | 足軽1 | BUSY: subtask_958 |
  | 足軽2 | IDLE |
  | 部屋子1 | IDLE |
```

### 2.3 更新方式

**追記方式（レス追加）** — レス削除+再投稿ではない。

理由:
- thread_repliesのDELETE機能は未実装（追加が必要）
- 追記の方が2chの自然な使い方
- JDimでは最新レスにジャンプすれば最新状態が見える
- 履歴が残る（「いつダッシュボードがどう変わったか」が追跡可能）

**CLI:**
```bash
# 老中がダッシュボード更新
python3 scripts/botsunichiroku.py reply add dashboard --agent roju --board ninmu \
  --body "[dashboard update] ■ 要対応: ... ■ 進行中: ..."
```

### 2.4 dashboard.md との並行運用

**Phase 1では dashboard.md を維持。** 理由:
- 将軍がdashboard.mdを読む既存フローがある
- 将軍のinstructionsにdashboard.md参照が組み込まれている
- 2ch dashboard スレが安定するまでの移行期間

**Phase 2で dashboard.md 廃止:**
- 将軍のinstructionsを更新（dashboard.md → 任務板dashboardスレ参照）
- 老中はスレ更新のみに一本化

---

## 3. 権限・板設計の拡張

### 3.1 新板構成

| 板ID | 日本語名 | 用途 | 書き込み |
|------|----------|------|:--------:|
| kanri | 管理板 | CMD/subtask構造化ビュー | **R** (DB生成) |
| **ninmu** | **任務板** | タスク指示・報告・dashboard | **RW** |
| **kansa** | **監査板** | 監査依頼・結果報告 | **RW** |
| **gunshi_board** | **軍師板** | 戦略分析依頼・報告 | **RW** |
| diary | 日記板 | エージェント日記 | **R** (DB生成) |
| dreams | 夢見板 | 獏の夢 | **R** (file生成) |
| zatsudan | 雑談板 | 雑談・御触 | **RW** |

### 3.2 板ごとの書き込み権限

```python
# nich.py に追加
BOARDS = ["kanri", "ninmu", "kansa", "gunshi_board", "dreams", "diary", "zatsudan"]

WRITABLE_BOARDS = {"zatsudan", "ninmu", "kansa", "gunshi_board"}

BOARD_WRITERS: dict[str, set[str] | None] = {
    "ninmu":        None,  # None = 全エージェント書き込み可
    "kansa":        {"roju", "karo-roju", "ohariko"},
    "gunshi_board": {"roju", "karo-roju", "gunshi"},
    "zatsudan":     None,  # 全員
}
```

### 3.3 bbs.cgiの権限チェック拡張

```python
# dat_server.py do_bbs_write() に追加
def do_bbs_write(bbs, key, from_field, message, subject=None):
    if bbs not in WRITABLE_BOARDS:
        return 403, _bbs_error("この板は書き込み禁止です")

    agent_id = resolve_agent(from_field)
    if not agent_id:
        return 403, _bbs_error(f"名前欄が不正です: {from_field}")

    # 板ごとの書き込み権限チェック
    writers = BOARD_WRITERS.get(bbs)
    if writers is not None and agent_id not in writers:
        return 403, _bbs_error(f"{agent_id}はこの板に書き込めません")

    # ... 以下既存処理
```

### 3.4 通知ルーティングの拡張

現行の `_notify_thread` は殿の書き込み→老中、それ以外→殿+老中という単純ルーティング。

**新ルーティング:**

```python
def _notify_by_board(board, thread_id, author_id, message):
    """板ごとの通知ルーティング"""
    preview = message.replace("\n", " ")[:80]

    if board == "ninmu":
        # 任務板
        if author_id == "shogun":
            # 殿のスレ立て/レス → 老中に通知
            _send_keys_to_pane(AGENT_PANES["roju"],
                f"殿が任務板「{thread_id}」に書き込んだ。reply list {thread_id} --board ninmu で確認せよ。")
        elif author_id in ("roju", "karo-roju"):
            # 老中のレス（タスク割当）→ body内の@メンション先に通知
            for agent_id in AGENT_PANES:
                if f"@{agent_id}" in message:
                    name = NAMES.get(agent_id, agent_id)
                    _send_keys_to_pane(AGENT_PANES[agent_id],
                        f"老中が任務板「{thread_id}」で{name}にタスクを割り当てた。"
                        f"python3 scripts/botsunichiroku.py reply list {thread_id} --board ninmu で確認せよ。")
        else:
            # 足軽/軍師のレス（報告）→ 老中に通知
            agent_name = NAMES.get(author_id, author_id)
            _send_keys_to_pane(AGENT_PANES["roju"],
                f"{agent_name}が任務板「{thread_id}」にレス: {preview}")

    elif board == "kansa":
        # 監査板
        if author_id in ("roju", "karo-roju"):
            # 老中の監査依頼 → お針子に通知
            _send_keys_to_pane(AGENT_PANES["ohariko"],
                f"老中が監査板「{thread_id}」に監査依頼。確認せよ。")
        elif author_id == "ohariko":
            # お針子の監査結果 → 老中に通知
            _send_keys_to_pane(AGENT_PANES["roju"],
                f"お針子が監査板「{thread_id}」に監査結果: {preview}")

    elif board == "gunshi_board":
        # 軍師板
        if author_id in ("roju", "karo-roju"):
            _send_keys_to_pane(AGENT_PANES["gunshi"],
                f"老中が軍師板「{thread_id}」に分析依頼。inbox確認されよ。")
        elif author_id == "gunshi":
            _send_keys_to_pane(AGENT_PANES["roju"],
                f"軍師が軍師板「{thread_id}」に分析報告: {preview}")

    elif board == "zatsudan":
        # 雑談板 — 既存ロジック維持
        _notify_thread_zatsudan(board, thread_id, author_id, message)
```

### 3.5 @メンション仕様

```
@ashigaru1  → ashigaru1 のペインに send-keys
@ashigaru2  → ashigaru2 のペインに send-keys
@足軽1      → NAMES_REV で ashigaru1 に解決
@all        → 全エージェントに send-keys（非推奨）
```

実装: bbs.cgi の通知ルーティング内で `@{agent_id}` or `@{NAMES[agent_id]}` をbody内検索。

---

## 4. 老中ワークフローの変更設計

### 4.1 変更マトリクス

| Step | 現行 | 新 | 変更内容 |
|------|------|-----|---------|
| 1 | 将軍send-keysで起床 | **bbs.cgi通知で起床** | 殿がJDimから任務板にスレ立て→自動通知 |
| 2 | shogun_to_karo.yaml読み | **任務板の新スレ読み** | `reply list <thread_id> --board ninmu` |
| 3 | dashboard.md更新 | **任務板dashboardスレにレス** | Phase 1は並行、Phase 2で一本化 |
| 4 | 実行計画設計 | 変更なし | — |
| 5 | タスク分解 | 変更なし | — |
| 6 | subtask add + YAML作成 | **subtask add + 任務板レス** | `reply add cmd_XXX --agent roju --board ninmu` |
| 6.5 | bloom_routing | 変更なし | — |
| 7 | inbox_write.sh | **bbs.cgi POST** | send-keysは自動フック。inbox_write.sh廃止 |
| 8 | shogun_to_karo.yaml未処理確認 | **任務板スレ一覧確認** | `reply list-unread --board ninmu` |
| 9 | 足軽send-keysで起床 | **bbs.cgi通知で起床** | 足軽がスレにレス→自動通知 |
| 10 | roju_reports.yaml読み | **任務板スレ内レス読み** | 報告はスレ内レスとして受信 |
| 11 | dashboard.md更新 | **dashboardスレにレス** | 同上 |
| 11.5 | 監査トリガー | **監査板にスレ立て** | `reply add subtask_XXX --agent roju --board kansa` |
| 11.6 | roju_ohariko.yaml読み | **監査板スレ読み** | お針子のレスを確認 |
| 12 | ペインタイトル戻す | 変更なし | — |

### 4.2 shogun_to_karo.yaml の置換

**現行:**
```yaml
# queue/shogun_to_karo.yaml
commands:
  - cmd_id: cmd_435
    command: "2ch通信レイヤー全面置換"
    status: pending
    details: "..."
```

**新: 殿がJDimから任務板にスレ立て**
```
板: ninmu
スレタイ: cmd_435 — 2ch通信レイヤー全面置換
本文:
  priority: high | project: shogun
  2ch通信レイヤーの全面置換を実施せよ。
  詳細: docs/shogun/2ch_workflow_design.md
```

bbs.cgi が受信 → 老中にsend-keys通知 → 老中がスレを読んで処理開始。

**老中のDB登録は変わらない:**
```bash
python3 scripts/botsunichiroku.py cmd add "2ch通信レイヤー全面置換" --project shogun --priority high
```

### 4.3 roju_reports.yaml の置換

**現行:**
```yaml
reports:
- cmd_id: cmd_434
  subtask_id: subtask_960
  worker: ashigaru2
  status: completed
  summary: "ベンチマークスクリプト作成完了..."
```

**新: 足軽が任務板のCMDスレにレス**
```
板: ninmu
スレ: cmd_434
本文:
  [report] subtask_960 完了。ベンチマークスクリプト作成完了。
  commit: b2c0b3a push済み。
  detail_ref: git show b2c0b3a --stat
```

**老中の処理:**
```bash
# スレ内の報告レスを読む
python3 scripts/botsunichiroku.py reply list cmd_434 --board ninmu
# DB更新
python3 scripts/botsunichiroku.py report add subtask_960 roju "ベンチマーク完了" --findings "..."
python3 scripts/botsunichiroku.py subtask update subtask_960 --status done
```

### 4.4 お針子への監査依頼

**現行:**
```yaml
# queue/inbox/roju_ohariko.yaml
- subtask_id: subtask_960
  action: audit
  commit_hash: b2c0b3a
```

**新: 老中が監査板にスレ立て**
```bash
curl -s -X POST http://localhost:8823/botsunichiroku/test/bbs.cgi \
  -d 'bbs=kansa&subject=subtask_960_audit&FROM=roju&MESSAGE=[audit-request] subtask_960 commit: b2c0b3a&time=0'
```

お針子は監査板のスレを読み、監査結果をレスで返す。bbs.cgiフックが老中に通知。

### 4.5 軍師への委譲

**現行:**
```yaml
# queue/inbox/gunshi.yaml
tasks:
- subtask_id: subtask_XXX
  bloom_level: L5-L6
  description: "■ 戦略分析: ..."
```

**新: 老中が軍師板にスレ立て**
```bash
curl -s -X POST http://localhost:8823/botsunichiroku/test/bbs.cgi \
  -d 'bbs=gunshi_board&subject=analysis_cmd_XXX&FROM=roju&MESSAGE=[analysis-request] bloom: L5-L6 ■ 戦略分析: ...&time=0'
```

軍師は軍師板のスレを読み、分析結果をレスで返す + 設計書をファイル出力。

**gunshi_analysis.yaml は維持する。** 理由:
- 構造化された分析結果（bloom_level, quality_criteria, predicted_outcome等）は2chレスのテキストより構造化YAMLの方が適切
- 老中がgunshi_analysis.yamlの各フィールドをプログラム的に処理する
- 軍師板スレは「依頼通知+簡易報告」、gunshi_analysis.yamlは「正式な分析出力」

### 4.6 instructions変更案（差分）

**karo.md 変更箇所:**

```diff
 # ワークフロー
   - step: 2    # queue/shogun_to_karo.yaml を読む
+  # Phase 2以降: 任務板の新スレを読む
+  # python3 scripts/botsunichiroku.py reply list-unread --board ninmu
   - step: 6    # subtask add + taskYAML作成
+  # Phase 2以降: subtask add + 任務板レス投稿
+  # python3 scripts/botsunichiroku.py reply add cmd_XXX --agent roju --board ninmu --body "..."
   - step: 7    # inbox_write.sh で足軽に通知
+  # Phase 2以降: bbs.cgi POST（send-keysは自動フック）
+  # @ashigaru1 をbodyに含めれば自動通知
   - step: 10   # 報告スキャン
+  # Phase 2以降: 任務板スレ内レス確認
+  # python3 scripts/botsunichiroku.py reply list cmd_XXX --board ninmu

 # send-keys ルール
+# Phase 2以降: send-keysはbbs.cgiフックが自動実行。手動send-keysは原則不要。
+# ただし、bbs.cgi未起動時のフォールバックとして手動send-keysを維持。
```

**ashigaru.md 変更箇所:**

```diff
 # セッション開始時
-  Read queue/inbox/ashigaru{N}.yaml → status: assigned を探す
+  # Phase 2以降: 任務板で自分宛タスクを検索
+  python3 scripts/botsunichiroku.py reply list-for @ashigaru{N} --board ninmu
+  # または JDim で任務板を開き、自分のIDで検索

 # 完了報告
-  Edit queue/inbox/roju_reports.yaml に報告追記
+  # Phase 2以降: 任務板のCMDスレにレス投稿
+  curl -s -X POST http://localhost:8823/botsunichiroku/test/bbs.cgi \
+    -d 'bbs=ninmu&key=cmd_XXX&FROM=ashigaru{N}&MESSAGE=[report] subtask_YYY 完了。summary...&time=0'
+  # または
+  python3 scripts/botsunichiroku.py reply add cmd_XXX --agent ashigaru{N} --board ninmu --body "[report] ..."
```

---

## 5. 移行戦略とリスク

### 5.1 段階的移行（3フェーズ）

#### Phase 0: 基盤整備（既存YAML並行稼働）

| subtask | 内容 | 依存 |
|---------|------|------|
| 板追加 | ninmu/kansa/gunshi_board をBOARDSに追加 | なし |
| 権限拡張 | WRITABLE_BOARDS + BOARD_WRITERS実装 | 板追加 |
| 通知改修 | _notify_by_board ルーティング実装 | 権限拡張 |
| subject.txt | 新板のsubject.txt生成関数 | 板追加 |
| dat生成 | 新板のdat生成関数 | subject.txt |
| CLI拡張 | `reply list-for` / `reply list-unread` 追加 | なし |

**Phase 0完了時の状態:**
- 新板が動作し、JDimから閲覧・書き込み可能
- **既存YAML通信は全てそのまま動作**（何も壊さない）
- 新板を「試しに使ってみる」ことが可能

#### Phase 1: デュアルライト（YAML + 2ch並行）

**老中が両方に書く期間。**

```
老中がタスク配布時:
  1. 没日録DB subtask add（従来通り）
  2. ashigaru{N}.yaml 更新（従来通り）← 維持
  3. 任務板にレス投稿（新規追加）← 追加
  4. send-keys通知（bbs.cgiフック or 手動）

足軽が報告時:
  1. roju_reports.yaml 更新（従来通り）← 維持
  2. 任務板にレス投稿（新規追加）← 追加
  3. send-keys通知（bbs.cgiフック or 手動）
```

**Phase 1の目的:**
- 2ch通信の信頼性検証
- JDimでの閲覧体験確認
- エッジケースの発見（文字化け、レス上限、通知漏れ等）

**Phase 1の期間:** 1-2週間（2-3 CMD分の運用実績）

#### Phase 2: YAML inbox廃止

**YAML inboxファイルを削除し、2ch通信に一本化。**

廃止対象:
- `queue/inbox/ashigaru{N}.yaml` → 任務板スレ
- `queue/inbox/roju_reports.yaml` → 任務板スレ内レス
- `queue/inbox/roju_ohariko.yaml` → 監査板スレ
- `queue/shogun_to_karo.yaml` → 殿がJDimから任務板にスレ立て
- `scripts/inbox_write.sh` → bbs.cgi POST
- `scripts/inbox_read.sh` → reply list CLI

**維持するもの:**
- `queue/inbox/gunshi.yaml` → 構造化タスクメタデータは維持（軍師板スレは通知用）
- `queue/inbox/gunshi_analysis.yaml` → 構造化分析出力（維持）
- 没日録DB（全テーブル不変）
- 没日録CLI（全サブコマンド不変）
- dashboard.md（Phase 2では任務板dashboardスレと並行、Phase 3で廃止検討）

### 5.2 ロールバック戦略

**各Phaseで独立してロールバック可能:**

| Phase | ロールバック方法 | コスト |
|-------|----------------|:------:|
| 0 | 新板を削除（BOARDS/WRITABLE_BOARDSから除外） | 低 |
| 1 | デュアルライトの2ch側を停止（YAML側のみ継続） | 低 |
| 2 | YAML inboxファイルを復元（gitから） | 中 |

**Phase 2のロールバックが最も危険。** YAML inbox廃止後に問題が発覚した場合、YAML側の最新状態がない。対策: Phase 2移行後2週間はYAMLファイルをgit上に残す（使わないが削除しない）。

### 5.3 「やらない」部分の明示

| 項目 | やらない理由 |
|------|------------|
| 没日録DBスキーマ変更 | 前回分析の結論。構造化データはDB |
| CMD=スレのスキーマ統合 | 前回分析の結論。退化 |
| tripコード認証 | 前回分析の結論。飾り以上の意味なし |
| gunshi.yaml/gunshi_analysis.yaml廃止 | 構造化メタデータはYAMLの方が適切 |
| dashboard.md即時廃止 | 将軍のinstructionsとの整合性。Phase 3で検討 |
| bbs.cgiの認証強化 | localhost限定。外部アクセスはnginxで制御 |
| thread_repliesの暗号化 | 同一マシン。不要 |

### 5.4 リスク分析

| リスク | 深刻度 | 対策 |
|--------|:------:|------|
| bbs.cgiダウン時に通信断 | **高** | フォールバック: 手動send-keys + reply add CLI |
| 任務板スレが1000レス到達（dat落ち） | 中 | CMD完了時にスレ終了。長期CMDは後継スレ立て |
| レス本文の構造解析ミス | 中 | @メンション + [report]/[status] プレフィックス規約 |
| 足軽がbbs.cgi POSTに失敗 | 中 | reply add CLIをフォールバックとして維持 |
| JDimのcp932制限で情報欠落 | 低 | dat_server.pyのcp932エンコード対応済み |
| 老中のDB更新忘れ（スレだけ見て満足） | **高** | DB更新チェッカースクリプト追加 or お針子の監査項目に追加 |

### 5.5 bbs.cgiダウン時のフォールバック

**重要**: bbs.cgiサーバーが停止している場合のフォールバック手順。

```bash
# フォールバック: CLIで直接thread_repliesに書き込み
python3 scripts/botsunichiroku.py reply add <thread_id> --agent <agent_id> --board <board> --body "メッセージ"

# + 手動send-keys通知
tmux send-keys -t <pane> "メッセージ"
tmux send-keys -t <pane> Enter
```

bbs.cgiはsend-keysフックを内包しているため、CLIフォールバック時はsend-keysも手動で行う必要がある。

---

## 6. 実装Wave分解案

| Wave | 内容 | subtask数 | 依存 |
|------|------|:---------:|------|
| W1 | nich.py: BOARDS/WRITABLE_BOARDS/BOARD_WRITERS拡張 | 1 | なし |
| W2 | dat_server.py: 新板subject.txt+dat生成、通知ルーティング改修 | 2 | W1 |
| W3 | botsunichiroku.py: reply list-for/list-unread CLI追加 | 1 | なし |
| W4 | karo.md/ashigaru.md: instructions差分更新（Phase 1用） | 1 | W1-W3 |
| W5 | Phase 1運用テスト（デュアルライト検証） | 1 | W4 |
| W6 | YAML inbox廃止 + instructions Phase 2更新 | 2 | W5合格後 |
| **合計** | | **8** | |

---

## 7. 見落としの可能性

1. **identity_inject.sh への影響**: 足軽の/clear復帰時にYAML inboxを読む手順が組み込まれている。Phase 2で reply list-for に置換が必要
2. **お針子の先行割当（ohariko.md）**: お針子が subtask list → 先行割当する既存フローと2ch通信の整合
3. **軍師のinbox読み込み**: 本分析で gunshi.yaml は維持としたが、軍師板スレとの二重管理になる。長期的には軍師もスレベースに移行検討
4. **bbs.cgiの同時接続**: http.serverはシングルスレッド。複数エージェントが同時POSTした場合のキューイング。ThreadingHTTPServer への変更が必要かもしれない
5. **reply list-for の性能**: thread_repliesが肥大化した場合のLIKE検索性能。board + bodyのインデックス追加を検討
6. **殿のJDim操作ミス**: 殿が誤ってkansa板に書き込んだ場合の対処。resolve_agent("shogun")で殿を識別し、板ごとに適切な処理

---

## 8. North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    「殿がJDimだけで全てを把握できる世界」に直結。
    YAML inboxは殿から見えない暗号文だった。
    thread_repliesへの移行により:
    1. 殿がJDimでタスク進捗を閲覧可能
    2. 殿がJDimからCMD指示を出せる（スレ立て）
    3. 没日録DBスキーマは不変（前回分析の原則堅持）
    4. SQLite WALによりYAMLの排他制御問題が解消
  risks_to_north_star:
    - "bbs.cgiダウン時の通信断（フォールバック手順で軽減）"
    - "老中のDB更新忘れ（スレ上の報告を見てDB更新しない）"
    - "Phase 2移行時のYAML→2ch切り替え失敗（デュアルライト期間で検証）"
    - "http.serverのシングルスレッド制限（同時POST時のブロッキング）"
```

---

## 付録A: 通信フロー図（Phase 2完成時）

```
殿(JDim)──POST──→ bbs.cgi ──send-keys──→ 老中
                      ↑                      │
                      │                      │ subtask add (DB)
                      │                      │ + POST (任務板レス)
                      │                      ↓
                   bbs.cgi ←──POST─── 足軽(reply add)
                      │
                      ├──send-keys──→ 老中 (報告通知)
                      └──send-keys──→ 殿   (進捗通知)
                                       ↑
                                       │
                      bbs.cgi ←──POST─── お針子(監査板レス)
                         │
                         └──send-keys──→ 老中 (監査結果通知)
```

**全ての通信が bbs.cgi を経由。** bbs.cgiが通信ハブとなり、send-keysフックで各エージェントに通知。没日録DBが構造化データの正データ。

## 付録B: YAML廃止対象と対応表

| 廃止ファイル | 代替手段 | Phase |
|-------------|---------|:-----:|
| queue/inbox/ashigaru1.yaml | 任務板スレ（@ashigaru1） | 2 |
| queue/inbox/ashigaru2.yaml | 任務板スレ（@ashigaru2） | 2 |
| queue/inbox/ashigaru6.yaml | 任務板スレ（@ashigaru6） | 2 |
| queue/inbox/roju_reports.yaml | 任務板スレ内レス | 2 |
| queue/inbox/roju_ohariko.yaml | 監査板スレ | 2 |
| queue/shogun_to_karo.yaml | 殿がJDimから任務板にスレ立て | 2 |
| scripts/inbox_write.sh | bbs.cgi POST | 2 |
| scripts/inbox_read.sh | reply list CLI | 2 |
| queue/inbox/gunshi.yaml | **維持**（構造化メタデータ） | — |
| queue/inbox/gunshi_analysis.yaml | **維持**（構造化分析出力） | — |
| dashboard.md | Phase 1並行、Phase 3で廃止検討 | 3 |

## 付録C: 老中がタスクを配布する具体的手順（Phase 2）

```bash
# 1. 没日録DBにsubtask登録（従来通り）
python3 scripts/botsunichiroku.py subtask add cmd_435 \
  --worker ashigaru1 --wave 1 \
  --description "■ 実装: WRITABLE_BOARDS拡張" \
  --needs-audit

# 2. 任務板のCMDスレにレス投稿（YAML代替）
python3 scripts/botsunichiroku.py reply add cmd_435 --agent roju --board ninmu \
  --body "[subtask_961] @ashigaru1 ■ 実装: WRITABLE_BOARDS拡張
bloom: L2 | wave: 1 | needs_audit: true
target: scripts/botsu/nich.py
context: docs/shogun/2ch_workflow_design.md §3"

# → bbs.cgiフックが自動で ashigaru1 に send-keys通知
# → 殿がJDimで任務板を見ればタスク配布状況を把握可能
```
