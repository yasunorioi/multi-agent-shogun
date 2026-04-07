# 2ch型統合基盤の論理検証 — 没日録×高札×2ch DAT×獏の統合設計

> **軍師分析** | 2026-03-18 | North Star: 3つのシステムを統合して1つにせよ。ただし論理破綻があるなら正直に言え

---

## 結論（先に述べる）

**部分的に採用。ただし「2chスレッド型にスキーマを統合」は論理破綻あり。正しい分離線は別にある。**

| 構想の要素 | 判定 | 理由 |
|-----------|:----:|------|
| 没日録DBにFTS5を統合 | **やる** | Docker撤廃の最大効果。search_index.dbを没日録DB内に移設 |
| Docker（高札v1）撤廃 | **やる** | SQLite + CLIで全機能再現可能 |
| 2ch DAT表示レイヤー | **やる** | 閲覧・人間理解用のビュー。スキーマ変更不要 |
| CMD=スレッド/subtask=レス のスキーマ統合 | **やらない** | 構造化データを非構造化テキストに潰す退化（後述） |
| 獏の夢をスレ化 | **やる（表示のみ）** | dreams.jsonl → 2ch DAT形式でレンダリング |
| tripコード認証 | **やらない** | 全エージェント同一マシン。コスト>効果 |

---

## 1. 論理整合性の検証（最重要）

### 1.1 CMD↔スレッドの1:1対応

**対応自体は成立する。** commands テーブル（376件）の各行が1スレッド、>>1にcmd詳細を記載。

しかし、**スレッド化する意味が薄い:**

```
現行: SELECT * FROM commands WHERE id = 'cmd_397'
  → 構造化データ（status, project, priority, assigned_karo）が即座に取得可能

2ch型: >>1 から cmd_397 のテキストを読み、status等はメタデータとして解析
  → 同じ情報を得るのに追加の解析コストが発生
```

### 1.2 subtaskの二重性問題（核心の論理破綻）

subtasksテーブルの各行は以下の構造化フィールドを持つ:

```
id, parent_cmd, worker_id, project, description, target_path,
status, wave, notes, assigned_at, completed_at,
needs_audit, audit_status, blocked_by
```

**これらは「レス」ではない。** レスは時系列テキストであり、以下を持たない:
- **状態遷移** (assigned → in_progress → done)
- **ワーカー割当** (worker_id)
- **依存関係DAG** (blocked_by)
- **波番号** (wave)
- **監査状態** (needs_audit, audit_status)

2ch型に落とすと2つのどちらかが起きる:

**パターンA: 構造化データをレス本文に埋め込む**
```
>>234
名前：足軽1 ◆trip
status: in_progress
wave: 2
blocked_by: >>230, >>231
---
■ 実装: scripts/foo.py の修正
```

→ 人間は読める。しかしCLI（`subtask list --status assigned --worker ashigaru1`）が動作するには、全レスを解析して構造化データを抽出するパーサーが必要。**現行のSQLクエリが全滅する。**

**パターンB: レスとは別に構造化テーブルを保持する**
```
threads テーブル + posts テーブル（2ch型）
  ＋ subtasks テーブル（構造化データ、現行維持）
  → 二重管理。どちらが正？同期はどうする？
```

→ **これは統合ではなく複雑化。**

### 1.3 blocked_byのDAG構造と>>アンカー

現行: `blocked_by: "subtask_363,subtask_364,subtask_365,subtask_367"`（104件に設定済み）

>>アンカーで表現する場合:
```
>>363が完了するまでこのレスは実行不可
```

**問題**: >>アンカーは「参照」であって「依存」ではない。2chの>>は「このレスに返信している」を意味し、「このレスが完了するまでブロック」という意味論を持たない。意味論を別途定義する必要があり、それは2chの仕組みに乗せるのではなく**独自のフィールド**を追加することに等しい。

→ **DAG構造はリレーショナルモデルの方が自然に表現できる。**

### 1.4 既存CLIコマンド体系の維持

没日録CLIは28個のサブコマンドを持ち、全てSQLクエリでデータを取得:

```bash
subtask list --status assigned --worker ashigaru1
report list --subtask subtask_890 --json
cmd show cmd_397
audit list --all
```

2ch型スキーマでこれらを維持するには:
- 全サブコマンドの内部SQLを書き換え
- thread/post テーブルのスキーマに合わせたクエリ再設計
- status等のフィルタリングはpost本文のLIKE検索 or 別カラム追加

→ **CLI互換性のためにフィールドを追加するなら、それは現行テーブルと同じ構造になる。**

### 1.5 判定: 構造化データ→スレッド型は退化

| 観点 | 現行（リレーショナル） | 2ch型（スレッド/レス） |
|------|---------------------|---------------------|
| 状態管理 | WHERE status = 'assigned' | レス本文を解析 or 別カラム |
| 依存関係 | blocked_by カラム + auto_unblock | >>アンカー + 独自パーサー |
| ワーカー割当 | worker_id カラム | 名前欄 or 別カラム |
| 集計 | COUNT(*) GROUP BY | 全レス走査 |
| FTS5検索 | ✓（追加可能） | ✓ |

**リレーショナルモデルは構造化データの管理に最適化されている。スレッド型は非構造化テキストの蓄積に最適化されている。没日録のデータは前者に属する。**

---

## 2. スレッド分類設計

### 2.1 表示レイヤーとしての2ch型（推奨）

スキーマ統合はしないが、**表示レイヤーとして2ch DAT形式を生成する**のは優れたアイデア:

```python
# botsunichiroku_2ch.py — 没日録データを2ch DAT形式でレンダリング
def render_cmd_as_thread(cmd_id):
    """CMDをスレッドとして表示"""
    cmd = get_cmd(cmd_id)  # 既存SQLで取得
    subtasks = get_subtasks(cmd_id)
    reports = get_reports_for_cmd(cmd_id)

    # >>1 = CMD本体
    print(f"1 名前：{cmd.assigned_karo} ◆karo {cmd.timestamp}")
    print(f"  [{cmd.project}] {cmd.command}")
    print(f"  status: {cmd.status} priority: {cmd.priority}")

    # >>2~ = subtasks（時系列順）
    for i, st in enumerate(subtasks, 2):
        worker_name = st.worker_id or "未割当"
        print(f"\n{i} 名前：{worker_name} ◆{worker_name[:4]} {st.assigned_at}")
        print(f"  [{st.status}] {st.description[:80]}")
        if st.blocked_by:
            refs = ", ".join(f">>{x}" for x in st.blocked_by.split(","))
            print(f"  blocked_by: {refs}")
```

これなら:
- **スキーマ変更ゼロ**
- **既存CLI完全互換**
- **人間が読んで楽しい2ch表示**
- **獏の夢もスレとしてレンダリング可能**

### 2.2 スレッド分類案（表示レイヤー用）

| 板 | 内容 | データソース |
|----|------|------------|
| **管理板** | CMD単位のスレッド | commands + subtasks + reports |
| **夢見板** | 獏の夢スレ（日次まとめ） | data/dreams.jsonl |
| **書庫板** | docs索引スレ | doc_keywords + ファイル一覧 |
| **日記板** | エージェント日記 | diary_entries |
| **監査板** | 監査結果スレ | subtasks WHERE needs_audit=1 |

### 2.3 dat落ち（アーカイブ）

現行のarchiveコマンド（`botsunichiroku.py archive --days 7`）がそのまま「dat落ち」に対応:
- status=archived の CMD → dat落ちスレッドとして表示を薄くする
- 表示レイヤーの問題であり、データ削除は不要

---

## 3. 高札機能の吸収可能性

### 3.1 現行高札v1の機能一覧

```
Docker (python:3.11-slim + MeCab + FastAPI + uvicorn)
├── main.py (1,474行, 16エンドポイント)
├── build_index.py (183行)
├── search_index.db (FTS5, コンテナ内)
└── 没日録DB (volume mount, 読み取り専用)
```

| エンドポイント | 代替可能性 | 代替手段 |
|-------------|:----------:|---------|
| GET /search | ✓ | 没日録DB内FTS5 + CLIコマンド |
| GET /search/similar | ✓ | CLIコマンド |
| GET /check/orphans | ✓ | SQLクエリ → CLIコマンド |
| GET /check/coverage | ✓ | SQLクエリ → CLIコマンド |
| GET /audit/history | ✓ | 既存 `audit list` |
| GET /worker/stats | ✓ | SQLクエリ → CLIコマンド |
| GET /health | 不要 | Docker不要なら不要 |
| POST /reports | ✓ | 既存 `report add` |
| POST /audit | ✓ | 既存 `subtask update --audit-status` |
| GET /reports/{id} | ✓ | 既存 `report list --subtask` |
| POST /dashboard | ✓ | 既存 `dashboard add` |
| GET /dashboard | ✓ | 既存 `dashboard list` |
| GET /docs/{cat}/{file} | ✓ | `cat docs/{cat}/{file}` |
| GET /audit/{subtask_id} | ✓ | SQLクエリ |
| POST /enrich (v2) | ✓ | CLIコマンド新設 |
| GET /enrich/{cmd_id} (v2) | ✓ | CLIコマンド新設 |

**16エンドポイント全てがCLIコマンドで代替可能。**

### 3.2 Docker撤廃の前提条件

| 条件 | 現状 | 対応 |
|------|------|------|
| MeCab | Docker内にインストール | ホストに `apt install mecab libmecab-dev mecab-ipadic-utf8` |
| FTS5 | search_index.db (コンテナ内) | 没日録DB内にFTS5テーブル追加 |
| FastAPI | HTTP API提供 | CLIコマンドに置換 |
| concurrent access | uvicorn が処理 | SQLite WAL + CLIの直接アクセス |

**MeCabは殿の環境にaptで入る（殿はaptパッケージなら即座にインストールしてくれる）。**

### 3.3 高札v2橋頭堡設計との関係

橋頭堡設計書は以下の機能を計画:
- FTS5 + lazy decay（忘却曲線）
- TAGE的判断予測
- 夢見機能（dream.py: cronでFTS5クロス相関）
- positive_patterns（正の強化信号）
- sanitizer.py（外部検索結果フィルタ）

**これらは全てSQLite + Python CLIで実装可能。** Docker/FastAPIに依存する部分はない。

むしろ、Docker撤廃により:
- FTS5が没日録DBと同一ファイルになり、トランザクション整合性が向上
- build_index.py の全再構築が不要に（没日録への書き込み時にFTS5も同時更新）
- 足軽が `curl localhost:8080` する代わりに `python3 scripts/botsunichiroku.py search` で直接検索

### 3.4 REST APIが必要な場面

**残る可能性:**
- 足軽の報告で `curl -s -X POST http://localhost:8080/reports` を使用中
  → `python3 scripts/botsunichiroku.py report add` に置換可
- 家老が `curl -s --get http://localhost:8080/search` で検索
  → `python3 scripts/botsunichiroku.py search` に置換可
- docs配信: `GET /docs/{cat}/{file}`
  → `cat` or `Read` ツールで直接アクセス

**結論: REST APIは全て不要。** CLIに統一できる。

---

## 4. 権限・認証設計

### 4.1 tripコードの検証

2chのtripコード: `名前#パスワード` → `名前 ◆ハッシュ`

shogunでの想定用途:
- 管理職者スレは将軍・老中のみ書き込み可
- 足軽の成りすまし防止

**現実:**
- 全エージェントが同一マシン、同一ユーザー（yasu）で実行
- tmux paneの `@agent_id` で身元が確定（設定は shutsujin が行い、足軽は変更不可）
- YAML inboxの分離で既に権限は実現済み（ashigaru1はashigaru2のinboxを操作しない）
- 没日録DBへの書き込み権限は家老のみ（CLAUDEmdのルール + instructionsで制御）

**tripコードは飾り。** 実際のアクセス制御は既に存在する。

### 4.2 推奨: 表示レイヤーにのみtripを使用

```python
TRIPS = {
    "shogun": "◆SHGN",
    "karo-roju": "◆ROJU",
    "ashigaru1": "◆ASH1",
    "ashigaru2": "◆ASH2",
    "ashigaru6": "◆HYG6",
    "gunshi": "◆GNSH",
    "ohariko": "◆OHRK",
    "baku": "◆BAKU",
}
```

表示時にagent_idからtripを生成するだけ。認証ロジックは不要。

---

## 5. 既存データ移行

### 5.1 推奨: 移行不要（閲覧レイヤー方式）

**スキーマを変えないので、データ移行は発生しない。**

必要なのは:
1. **FTS5テーブルの追加**: 没日録DBに `search_index` FTS5テーブルを新設
2. **FTS5データの初期投入**: 既存の build_index.py のロジックを流用
3. **2ch DATレンダリングスクリプト**: `botsunichiroku_2ch.py` を新規作成

```sql
-- 没日録DBに追加するFTS5テーブル
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    source_type,    -- 'command', 'subtask', 'report', 'dashboard', 'diary'
    source_id,
    content,
    tokenize='unicode61'  -- MeCab分かち書き済みテキストを投入
);
```

### 5.2 FTS5への初期データ投入

```python
# migrate_fts5.py（1回実行）
# 既存 build_index.py のロジックを没日録DB内に移植
def populate_fts5(conn):
    # commands
    for cmd in conn.execute("SELECT id, command, details FROM commands"):
        tokenized = mecab_tokenize(f"{cmd[1]} {cmd[2] or ''}")
        conn.execute("INSERT INTO search_index VALUES (?, ?, ?)",
                     ("command", cmd[0], tokenized))
    # subtasks, reports, dashboard_entries, diary_entries も同様
```

### 5.3 インクリメンタル更新

没日録CLIの各書き込みサブコマンドの末尾にFTS5更新を追加:

```python
# botsu/cmd.py の cmd_add() 末尾に追加
conn.execute("INSERT INTO search_index VALUES (?, ?, ?)",
             ("command", cmd_id, mecab_tokenize(f"{command} {details}")))
```

→ build_index.py の全再構築が不要になる。

---

## 6. コスト・リスク分析

### 6.1 統合のメリット

| メリット | 定量効果 |
|---------|---------|
| Docker撤廃 | Dockerfile + docker-compose.yml + コンテナ管理が不要 |
| コード削減 | main.py (1,474行) の大部分が不要。CLIに集約 |
| FTS5統合 | search_index.db (別ファイル) → 没日録DB内（トランザクション整合性向上） |
| 検索統一 | `curl localhost:8080/search` → `python3 scripts/botsunichiroku.py search` |
| 起動時間短縮 | Docker起動+build_index不要 |
| 依存削減 | FastAPI, uvicorn 不要（ホストのMeCabのみ追加） |
| 2ch表示 | 人間可読性の大幅向上。ねらー口調で楽しい |

### 6.2 統合のリスク

| リスク | 深刻度 | 対策 |
|--------|:------:|------|
| FTS5移行でデータ不整合 | 中 | migrate_fts5.py を冪等に設計 |
| MeCabホストインストールの失敗 | 低 | apt install は殿の環境で実績あり |
| 足軽のcurlコマンドがCI/CDで使われている | 低 | 高札API使用箇所を全検索→置換 |
| FTS5の同時書き込みロック | 低 | WALモードで対応。現行も1エージェント1タスクの制約あり |
| 高札v2橋頭堡の設計が無駄になる | なし | 橋頭堡の設計思想（enrich, pitfalls, lazy decay）はCLI版でも完全に有効 |

### 6.3 「やらない」という選択肢

現行のまま（Docker高札 + 没日録DB + 2ch DATなし）でも動作に問題はない。

**やらない場合のコスト:**
- Docker起動・管理コストが継続
- FTS5インデックスの同期問題（build_index.py の全再構築が定期的に必要）
- 検索がHTTP経由（Dockerコンテナ起動が前提）

**やらない場合でも、2ch DAT表示レイヤーだけは独立して追加可能。** これは設計書の判断で最も低リスク。

### 6.4 実装規模見積もり

| Wave | 内容 | 工数（subtask数） |
|------|------|:----------------:|
| W1 | FTS5テーブル追加 + migrate_fts5.py | 2 |
| W2 | 没日録CLIにsearchサブコマンド追加 | 2 |
| W3 | 没日録CLIの各書き込みにFTS5インクリメンタル更新追加 | 3 |
| W4 | 足軽/家老のcurlコマンドをCLI呼び出しに置換 | 2 |
| W5 | botsunichiroku_2ch.py（2ch DAT表示レイヤー） | 2 |
| W6 | Docker停止・クリーンアップ | 1 |
| W7 | 統合テスト | 2 |
| **合計** | | **14** |

---

## 7. 推奨設計: 三層分離アーキテクチャ

**正しい分離線は「2ch vs リレーショナル」ではなく「保存 vs 検索 vs 表示」。**

```
┌─────────────────────────────────────────────┐
│             表示レイヤー（View）               │
│  botsunichiroku_2ch.py                       │
│  ├── CMD → スレッド表示                       │
│  ├── subtask/report → レス表示                │
│  ├── 獏の夢 → 夢見板                         │
│  ├── diary → 日記板                          │
│  └── tripコード表示（◆ROJU, ◆ASH1...）       │
├─────────────────────────────────────────────┤
│             検索レイヤー（Search）             │
│  FTS5 search_index テーブル（没日録DB内）      │
│  ├── 全文検索: botsunichiroku.py search       │
│  ├── enrich: botsunichiroku.py enrich         │
│  ├── pitfalls抽出                             │
│  └── lazy decay / TAGE（橋頭堡v2設計を継承）   │
├─────────────────────────────────────────────┤
│             保存レイヤー（Storage）             │
│  没日録DB (botsunichiroku.db) — 現行スキーマ   │
│  ├── commands (376)                           │
│  ├── subtasks (730)                           │
│  ├── reports (873)                            │
│  ├── dashboard_entries (278)                  │
│  ├── diary_entries                            │
│  ├── cooccurrence (76,652)                    │
│  ├── doc_keywords (17,574)                    │
│  ├── agents, counters, kenchi                 │
│  └── search_index (FTS5, 新設)                │
└─────────────────────────────────────────────┘
```

**この設計なら:**
- 保存レイヤーは現行のまま（CLIコマンド体系完全互換）
- 検索レイヤーはFTS5を没日録DB内に統合（Docker撤廃）
- 表示レイヤーとして2ch DATを追加（楽しい + 人間可読性向上）
- 各レイヤーは独立して変更可能

---

## 8. 見落としの可能性

1. **高札APIを外部から呼んでいるケースの見落とし**: shogunシステム以外（例: uecs-llmのLINE Bot等）から高札APIを叩いている可能性。調査が必要
2. **FTS5とMeCabのトークナイズ精度**: ホスト版MeCabとDocker版でバージョン差がある場合、検索結果に差が出る
3. **cooccurrenceテーブル（76,652行）とFTS5の関係**: build_cooccurrence.py が高札APIに依存しているか未確認
4. **高札v2のenrich機能の非同期性**: 高札v1ではFastAPIの非同期処理（async/await）が使えたが、CLI版では同期処理になる。enrichの処理時間が長い場合のUX低下
5. **お針子の監査時のcurl呼び出し**: お針子のinstructionsに高札API直接呼び出しが組み込まれている可能性

---

## 9. North Star Alignment

```yaml
north_star_alignment:
  status: aligned（部分的に）
  reason: |
    「3つのシステムを1つに」の精神は三層分離設計で達成。
    SQLite 1本（没日録DB）に保存+検索を統合し、Docker撤廃。
    2ch DAT表示レイヤーは楽しさと可読性を追加。
    ただしスキーマ統合（CMD=スレッド型）には論理破綻がある。
    構造化データはリレーショナルモデルで保持すべき。
  risks_to_north_star:
    - "統合範囲を誤ると既存CLI体系が崩壊する"
    - "Docker撤廃を急いで移行バグを出すと復旧コスト大"
    - "2ch表示の楽しさに引きずられてスキーマ変更に踏み込むリスク"
```

---

## 付録A: 2ch DAT表示のサンプル出力

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【管理板】cmd_397 — 高札v2 橋頭堡設計
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1 名前：老中 ◆ROJU 2026/03/12(木) 00:15:00
  [shogun] 高札v2 橋頭堡設計: 帰納×演繹の交差点
  priority: high | status: in_progress
  ───────────────

2 名前：部屋子1 ◆HYG6 2026/03/12(木) 01:20:00
  [subtask_882] 高札v2設計書作成（前半: §1-§6）
  status: done | wave: 1
  ───────────────

3 名前：足軽2 ◆ASH2 2026/03/12(木) 01:20:00
  [subtask_883] 高札v2設計書作成（後半: §7-付録）
  status: done | wave: 1
  blocked_by: >>2
  ───────────────

4 名前：足軽2 ◆ASH2 2026/03/12(木) 03:45:00
  [report] subtask_883 完了。橋頭堡設計書v2.0をdocs/shogun/に出力。
  commit: abc1234 push済み
  ───────────────

5 名前：お針子 ◆OHRK 2026/03/12(木) 04:00:00
  [audit] subtask_882 監査完了。15点中13点。
  べ、別にあなたのために監査したんじゃないんだからね！
```

---

## 付録B: 高札API → CLI置換対応表

| 高札API | CLI置換 | 備考 |
|---------|---------|------|
| `curl localhost:8080/search?q=XXX` | `python3 scripts/botsunichiroku.py search XXX` | 新設 |
| `curl localhost:8080/search/similar?subtask_id=XXX` | `python3 scripts/botsunichiroku.py search --similar XXX` | 新設 |
| `curl -X POST localhost:8080/reports -d '{...}'` | `python3 scripts/botsunichiroku.py report add ...` | 既存 |
| `curl localhost:8080/reports/42` | `python3 scripts/botsunichiroku.py report list --subtask XXX` | 既存 |
| `curl localhost:8080/check/orphans` | `python3 scripts/botsunichiroku.py check orphans` | 新設 |
| `curl localhost:8080/check/coverage` | `python3 scripts/botsunichiroku.py check coverage` | 新設 |
| `curl localhost:8080/enrich -d '{...}'` | `python3 scripts/botsunichiroku.py search --enrich CMD_ID` | 新設（`search`サブコマンドに統合） |
| `curl -X POST localhost:8080/audit -d '{...}'` | `python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --audit-status done` | 既存 |
| `curl localhost:8080/audit/subtask_XXX` | `python3 scripts/botsunichiroku.py audit list --subtask subtask_XXX` | 既存 |
| `curl localhost:8080/docs/context/karo-*.md` | `cat context/karo-*.md` or `Read` | 直接アクセス |
