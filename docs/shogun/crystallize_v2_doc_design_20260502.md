# 結晶化機構v2 ドキュメント化(>>1-10テンプレ)+P1+P3+P4 設計

**cmd**: cmd_571 / **subtask**: subtask_1204(初版) + **subtask_1205(補足追補)**
**作成日**: 2026-05-02 (subtask_1204) / 追補 2026-05-02 (subtask_1205)
**作成者**: 軍師（gunshi）
**前提**: cmd_570 実在性調査(`docs/shogun/crystallize_v2_existence_audit_20260501.md`) を真と扱う
**親思想**: cmd_517 結晶化機構v2(commit 244b2af, 既に16+2スレ稼働中)
**ステータス**: 設計案（実装は本cmd終了後・別cmdで足軽担当）
**スコープ**: 設計のみ。コード/DB書き込み禁止。F006継続。
**追補(subtask_1205)**: §11(OSI 7層類比)+§12(権限管理 案D推奨)を末尾追加。既存§1-§10は無変更・整合上「## 11/12/13」を「§13/§14/§15」へrenumber。

---

## 0. 総括（殿用Executive Summary）

| 設計判断 | 結論 |
|---------|------|
| §1 >>1-10 テンプレ仕様 | **>>1-5 必須・>>6-10 任意余白**。MD/Mermaid採用、文字数無制限の自由を活かしつつ過剰テンプレ化を回避 |
| §2 後付け移行 | **既存cmd_XXXスレには触らない**。プロジェクト構造ドキュメント専用スレ`thread_id="project_{name}"`を別途新設し、そこに>>1-10を載せる |
| §3 crystallize.py修正diff | 既存`crystallize_cmd()`は無変更。新規関数2本(`init_project_template/update_template_reply`)+CLIサブコマンド追加 |
| §4 P1実装位置 | (b)+(c)+(d)三層**: Memory MCP(済)+context/karo-checklist.md+scripts/karo_check.sh |
| §5 P3実施タイミング | **本cmd内では実施しない**(設計フェーズ・DB/ファイル書込禁止のため)。実装cmdに作業項目として明記 |
| §6 P4 needs_audit自動判定 | **キーワード+パス監視ハイブリッド**。老中側で割当時に自動付与(お針子側ではなく老中側で実装) |
| §7 N回目告知廃止 | Memory MCP system-rulesに記録+自然減衰+違反検出時お針子フラグ。**既存報告は履歴価値ありで保持** |
| §8 Viewer接続点 | テンプレデータはthread_replies格納で済むため新規volume不要。Markdownレンダリングは**Viewer側責務**(server側プレーン返却) |
| §9 simplicity check | 3問パス。**>>1-5基本+>>6-10オプション**で最小化済 |
| §10 unknown_unknowns | **12項目**(必須10超え)。最大リスク=`thread_replies`がINSERT-onlyで「>>1-10更新可」要件と衝突 |
| **§11 OSI 7層類比(追補)** | 殿草案の重箱突き: L2=>>1配置妥当性低い・「OSI類比」と「変更ガバナンス階層」の二軸混在を分離。**>>1-10は全てL7アプリ層**(媒体非依存性宣言) |
| **§12 権限管理(追補)** | 殿の重箱突き: 現行§1.2は既に4ロール分散済(殿/家老/軍師/お針子)。**案D=変更ガバナンス階層×権限階層化** を軍師推奨(>>1のみ殿承認必須・運用層は承認不要) |
| 付録 実装cmd起票案 | cmd_572(仮)・足軽2名×1.5日(並列)・wave3段+blocked_by構成。**§11/§12 影響=増減なし**(概念追補のみ・実装範囲不変) |

---

## §1 >>1-10 テンプレ仕様

### §1.1 設計の核心

殿裁定「2ch仕様縛り解放」を活かし、各レス(reply)を**プロジェクト構造ドキュメントの固定セクション**として運用する。
`thread_replies.body` は SQLite TEXT(無制限)・LF許容・MD埋め込み可なので、形式の自由は既に担保されている。

ただし**過剰テンプレ化禁止**(殿好み: Simple > Complex)。>>1-5を必須、>>6-10は「埋めなくてもよい余白」とする。

### §1.2 レス毎仕様

| レス | 内容 | 主筆者 | 更新タイミング | データ形式 | 必須/任意 |
|---|---|---|---|---|---|
| **>>1** | プロジェクト概要・存在理由・North Star | 殿/家老 | プロジェクト発足時/方針変更時 | Markdown 1-2段落 | 必須 |
| **>>2** | アーキテクチャ図 | 軍師 | 構造変更時(エージェント追加・板新設等) | Mermaid(推奨) / ASCII(fallback) | 必須 |
| **>>3** | 主要構成要素一覧(没日録/高札/結晶化等の役割定義) | 軍師 | 構成要素追加・削除時 | Markdownテーブル | 必須 |
| **>>4** | データフロー(誰が誰に書く・読む・通知経路) | 軍師 | 通信プロトコル変更時 | Markdown箇条書き or Mermaid sequenceDiagram | 必須 |
| **>>5** | 既知の癖・地雷(GL.iNet教訓型) | 殿/軍師/お針子 | インシデント発生時 | Markdown箇条書き(原因/影響/回避策) | 必須 |
| **>>6** | 重要ファイルパス索引 | 家老 | 構造変更時 | Markdown箇条書き | 任意 |
| **>>7** | 環境変数・設定値一覧 | 軍師/家老 | 設定追加時 | Markdownテーブル | 任意 |
| **>>8** | 主要メトリクス・ヘルスチェック観点 | お針子 | 監視項目追加時 | Markdown箇条書き | 任意 |
| **>>9** | 外部接続点(API・MCP・URL) | 軍師 | 接続点追加時 | Markdownテーブル | 任意 |
| **>>10** | 用語集・命名由来 | 殿/家老 | 新概念導入時 | Markdownテーブル | 任意 |
| **>>11+** | (本テンプレスレでは)構造変更履歴・改訂メモ。**cmd完遂結晶化レスは別スレ** | 任意 | 随時 | 自由 | - |

### §1.3 >>6-10 余白の使い方ガイドライン

- **「該当なし」レスを敢えて投稿しない**。空白のままで良い。
- 後発で必要になったら埋める。**全部埋めることが目的ではない**。
- 投稿しても1-3行で十分。長文化したらdocs/配下のmdに分離してリンク貼る(軍師既存ルール踏襲)。

### §1.4 「cmd完遂結晶化スレ」との分離

**重要**: 既存の`thread_id="cmd_XXX"`は**1cmd=1スレ・>>1-5テンプレ**(問い/結果/変更点/学び/関連)で確定済(commit 244b2af)。
今回の>>1-10は**プロジェクト構造ドキュメント専用スレ**として、別の thread_id 名前空間で切る。

**新規 thread_id 命名規則案**:
```
thread_id = "project_{project_name}"
例: project_shogun, project_hardware, project_tooling
```

これにより:
- crystals板内に2種類のスレが並存: `project_*`(プロジェクト構造) + `cmd_*`(cmd完遂)
- 既存16スレ(cmd_XXX)は触らない → §2で後付け不要を確定

---

## §2 後付け移行可否+方針

### §2.1 既存16スレへの>>1-10後付け追加 — **不可・不要**

**技術的不可性**:
`agent-swarm/server/dat_server.py:46`の`do_reply_add()`は`thread_replies`への**INSERT-only**(UPDATE/DELETEエンドポイント無し)。
既存スレcmd_XXXは既に>>1-5(cmd完遂テンプレ)が埋まっており、その**前に**>>0系列を挿入することは AUTO_INCREMENT id 順序上不可能。

論理的不要性:
- §1.4の通り`cmd_XXX`スレは「1cmd完遂記録」として目的が明確で、プロジェクト構造ドキュメントとは別責務
- 既存スレを書き換えると履歴の一貫性が失われる(殿のappend-only思想と矛盾)

### §2.2 推奨方針 — **新規`project_{name}`スレで実施**

| 項目 | 内容 |
|---|---|
| 既存16スレ(cmd_XXX) | **完全に維持・触らない** |
| 新規スレ(project_*) | プロジェクト発足時・本機構導入時に**手動初期化** |
| 初期化対象 | shogun / hardware / tooling(既存目次MD3つに対応) |
| 埋める順序 | >>1(殿/家老起草)→>>2-4(軍師)→>>5(運用蓄積)→>>6-10(随時) |
| 既存目次MD `agent-swarm/crystals/{project}.md` との関係 | **共存**。MD目次=cmd完遂索引、project_*スレ=構造ドキュメント。役割分離 |

### §2.3 thread_replies テーブルへの影響評価

**スキーマ変更不要**:
```sql
-- 現状(変更なし)
CREATE TABLE thread_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    board TEXT NOT NULL DEFAULT 'general',
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    posted_at TEXT NOT NULL
)
```

`project_shogun`等は単なる新規 thread_id として既存スキーマで動く。
**衝突回避**: cmd_XXX 命名規則と project_* 命名規則は接頭辞で完全分離 → 衝突なし。

### §2.4 「>>1-10更新可」要件と INSERT-only 制約の矛盾(重要)

殿裁定: 「>>1-10は**更新可**」
現状実装: thread_replies は INSERT-only (UPDATE/DELETE非対応)

**解決選択肢**:

| 案 | 概要 | 利点 | 欠点 | 評価 |
|---|---|---|---|---|
| (A) `dat_server`に PATCH エンドポイント追加 | reply_no指定でUPDATE | 真の更新が可能 | append-only思想と矛盾、MR大 | △ |
| (B) 「最新版優先」方式 — 同テンプレを再投稿し、Viewerが最新の>>N相当を表示 | INSERT-only維持 | append-only思想保持・履歴も追える | reply_noが>>11以降に流れる、Viewer側で「>>1相当の最新」抽出ロジックが要る | ◎ **推奨** |
| (C) スレを切り直し | 古いproject_shogun_v1廃→ project_shogun_v2を新設 | 単純 | 履歴が分断、MD目次が壊れる | × |

**推奨 (B)**:
- thread_replies に追加カラム不要(SQLite既存で運用)
- `body`先頭に魔法行`<!-- TEMPLATE:N -->` (例: `<!-- TEMPLATE:1 -->`) を入れて、reply_noではなくテンプレ番号を本文側に持つ
- Viewer/取得API側で「同`thread_id`内で同`<!-- TEMPLATE:N -->`の最新posted_atを優先表示」
- 履歴は thread_replies に全保存される(append-only思想保持)
- 利点: agent-swarm 改修最小(server側はプレーンに返すだけ、論理は呼び出し側=shogun + Viewer)

---

## §3 結晶化v2 修正diff案 — `scripts/botsu/crystallize.py`

### §3.1 既存`crystallize_cmd()`への影響 — **無変更**

cmd_update(status=done)時の挙動は完全に維持(>>1-5を cmd_XXX スレに連投、目次MDにappend)。
今回のテンプレ機構は**完全に追加機能**として実装する。

### §3.2 新規関数案

`scripts/botsu/crystallize.py` 末尾に以下を追加(行数: 既存234行 → 推定330行・約100行増):

```python
# ====== プロジェクトテンプレ機構(cmd_571追加) ======

TEMPLATE_REPLY_DEFINITIONS = {
    1: ("project_overview", "プロジェクト概要"),
    2: ("architecture",     "アーキテクチャ図"),
    3: ("components",       "主要構成要素"),
    4: ("data_flow",        "データフロー"),
    5: ("gotchas",          "既知の癖・地雷"),
    6: ("file_index",       "重要ファイルパス索引"),
    7: ("env_vars",         "環境変数・設定値"),
    8: ("metrics",          "メトリクス・ヘルスチェック"),
    9: ("external_links",   "外部接続点"),
    10:("glossary",         "用語集・命名由来"),
}

def init_project_template(project: str, scaffolds: dict[int, str] | None = None) -> dict:
    """`project_{project}` スレを初期化。
    scaffolds: {1: ">>1本文", 2: ">>2本文", ...} 任意指定。未指定キーはplaceholder投稿
    冪等性: 既存>>1-10があれば skip(既存判定は <!-- TEMPLATE:N --> マジック行で行う)
    """
    thread_id = f"project_{project}"
    board = _env("SWARM_BOARD", "crystals")
    scaffolds = scaffolds or {}

    existing = _existing_template_nums(thread_id, board)
    posted = []
    for n, (slug, label) in TEMPLATE_REPLY_DEFINITIONS.items():
        if n in existing:
            continue
        body = scaffolds.get(n) or f"<!-- TEMPLATE:{n} -->\n>>{n} {label}\n(未記入)"
        if "<!-- TEMPLATE:" not in body:
            body = f"<!-- TEMPLATE:{n} -->\n{body}"
        ok = _swarm_post_python(thread_id, board, [body]) or _swarm_post_http(thread_id, board, [body])
        if ok:
            posted.append(n)
    return {"thread_id": thread_id, "posted": posted}


def update_template_reply(project: str, reply_no: int, body: str) -> dict:
    """テンプレレスを更新(実態は新規INSERT・最新版優先方式)。"""
    if reply_no not in TEMPLATE_REPLY_DEFINITIONS:
        return {"updated": False, "reason": "invalid_reply_no"}
    thread_id = f"project_{project}"
    board = _env("SWARM_BOARD", "crystals")
    if "<!-- TEMPLATE:" not in body:
        body = f"<!-- TEMPLATE:{reply_no} -->\n{body}"
    ok = _swarm_post_python(thread_id, board, [body]) or _swarm_post_http(thread_id, board, [body])
    return {"updated": ok, "thread_id": thread_id, "reply_no": reply_no}


def _existing_template_nums(thread_id: str, board: str) -> set[int]:
    """thread_replies から `<!-- TEMPLATE:N -->` を持つレスの N を抽出。"""
    db_path = _env("SWARM_DB", "/home/yasu/agent-swarm/data/swarm.db")
    if not os.path.exists(db_path):
        return set()
    import re
    nums = set()
    try:
        conn = sqlite3.connect(db_path)
        try:
            for (body,) in conn.execute(
                "SELECT body FROM thread_replies WHERE thread_id=? AND board=?",
                (thread_id, board),
            ):
                m = re.search(r"<!-- TEMPLATE:(\d+) -->", body or "")
                if m:
                    nums.add(int(m.group(1)))
        finally:
            conn.close()
    except Exception:
        pass
    return nums
```

### §3.3 `scripts/botsu/cmd.py` への CLI サブコマンド追加(任意)

`cmd_update`本体は無変更。新規`crystallize`サブコマンド配下に`project init/update`を切る:

```bash
# 例: 初期化
python3 scripts/botsunichiroku.py crystallize project init shogun \
  --scaffold-from docs/shogun/project_shogun_scaffold.md

# 例: >>2 アーキ図のみ更新
python3 scripts/botsunichiroku.py crystallize project update shogun 2 \
  --body-from docs/shogun/architecture.mmd
```

設計判断: **CLIは必須ではない**。`init_project_template()`をPythonから呼ぶだけで初期化可。CLIは利便性のために実装cmdで判断(殿/家老の運用次第)。

### §3.4 自動初期化の有無

**推奨: 自動化しない**(殿好み: Simple > Complex / マクガイバー精神)。

- スレ作成は殿/家老の**手動コマンド実行**で行う
- 「プロジェクト発足時」は人間が認識するイベント → 自動検出より明示的指示が安全
- 自動化すると config/projects.yaml 変更検知などの追加機構が必要になり過剰実装

### §3.5 テスト追加範囲

- `tests/test_crystallize_template.py` (新規・約80行)
  - `test_init_project_template_idempotent`: 2回呼んでも重複INSERTしない
  - `test_update_template_reply_appends_new_record`: INSERT-only動作の確認
  - `test_existing_template_nums_extraction`: マジック行抽出
  - 既存`tests/test_crystallize.py`は無変更(cmd完遂機構への影響なし)

---

## §4 P1(grep経由確認テンプレ)実装位置

### §4.1 P1の目的

家老の「ファイル未存在」誤判定再発防止(cmd_570で発覚)。
`find scripts -name "crystall*"`等を**実行する手順**を、家老が必ず使うフロー上に置く。

### §4.2 4選択肢の評価

| ID | 案 | 利点 | 欠点 | 評価 |
|---|---|---|---|---|
| (a) `instructions/karo.md`直接追記 | フロー文書に直接記載・即読み込み | 1373→199行圧縮方針に逆行・本文肥大化 | △ |
| (b) `context/karo-checklist.md`専用ファイル | 集中管理・検索可・他チェックリストとも統合可 | コンパクション後再読み込みが必要 | ◎ |
| (c) `scripts/karo_check.sh`実行ツール | 機械化・誤判定が物理的に消える | 「ツール忘れ」リスク・bash運用の保守 | ◎ |
| (d) Memory MCP system-rules | エージェント横断で再利用可・既追加済(2026-05-01老中) | Memory読み込みが必須・ルール多数化で霞む | ○ |

### §4.3 推奨 — **(b)+(c)+(d) 三層**

単独採用ではなく**三層防御**:

```
[ 第一層: (d) Memory MCP system-rules ]  ← 既追加済(老中)・キャッチオール
   │
   ▼
[ 第二層: (b) context/karo-checklist.md ]  ← 文書化された確認手順
   │
   ▼
[ 第三層: (c) scripts/karo_check.sh ]  ← 機械化(コマンド実行で誤判定排除)
```

#### 第二層: `context/karo-checklist.md`

新規ファイル(約30-50行)。家老の「ファイル/機構実在判定」フローに組み込む確認チェックリスト。

```markdown
# 家老 確認チェックリスト

## 「ファイル/機構未存在」と判定する前の必須手順

1. [ ] `find scripts -name "*.py" | xargs grep -l <キーワード>` でサブディレクトリ含む横断確認
2. [ ] `git log --all --oneline | grep <キーワード>` でcommit履歴確認
3. [ ] `python3 scripts/botsunichiroku.py cmd show cmd_XXX` で起源cmd照会
4. [ ] 軍師に**本当に未存在か**確認依頼を出す(独立検証)

これらを全てPASSしてから「未存在」と告知せよ。
```

#### 第三層: `scripts/karo_check.sh`

新規ファイル(約20-30行)。`bash scripts/karo_check.sh exists <keyword>` で機械的に判定:

```bash
#!/usr/bin/env bash
# karo_check.sh — 家老の「ファイル未存在」誤判定防止ツール
# 使用: bash scripts/karo_check.sh exists <keyword>
case "$1" in
  exists)
    keyword="$2"
    echo "## scripts/ 全サブディレクトリ横断検索"
    find scripts -name "*.py" 2>/dev/null | xargs grep -l "$keyword" 2>/dev/null || echo "(ヒットなし)"
    echo "## git history"
    git log --all --oneline | grep -i "$keyword" || echo "(ヒットなし)"
    ;;
  *)
    echo "Usage: $0 exists <keyword>" >&2; exit 1;;
esac
```

### §4.4 トレードオフ判断

- **(b)単独**: 機械化されず再発リスク残る
- **(c)単独**: 「ツール存在を忘れる」可能性
- **(d)単独**: Memory読み込みが家老セッションで毎回保証されない
- **三層**: 各層が補完的。コスト=新規ファイル2(checklist.md+karo_check.sh) ≈ 50-80行追加。**過剰ではない**。

---

## §5 P3(cmd_517名称更新+`.env.example`)実施タイミング

### §5.1 本cmd内での実施可否

**実施しない**。理由:
- 本cmdの厳禁事項: 「コード変更/新規ファイル作成禁止」「DB書き込み禁止」
- `cmd update --command`はDB書き込み(commands.command UPDATE)
- `.env.example`編集はファイル変更
- → どちらも本cmd内で実行できない(設計フェーズのみ)

### §5.2 後続実装cmdへの委譲

cmd_572(仮)実装フェーズで足軽担当:

| 作業 | コマンド/操作 | 担当 |
|---|---|---|
| cmd_517 名称更新 | `python3 scripts/botsunichiroku.py cmd update cmd_517 --command "結晶化機構v2(agent-swarm/crystals/*.md目次+DATスレ)"` | 老中(DB書込権限) |
| `.env.example` 追記 | `SHOGUN_CRYSTALS_DIR`の説明コメント追加(現状16行・コメント説明明示なし) | 足軽 |
| `.env.example` 追記 | `SWARM_DAT_URL` / `SWARM_BOARD` / `SWARM_SERVER_PATH` / `SWARM_DB` の用途コメント追加 | 足軽 |
| `.env.example` 追記 | `SHOGUN_CRYSTALS_DISABLE` killスイッチの用途明記 | 足軽 |

### §5.3 範囲限定

- `.env.example`の編集は**コメント追加のみ**(値変更しない)
- 既存の環境変数を消さない・置換しない(後方互換)

### §5.4 タイミング

- 実装cmd(cmd_572仮)の wave 1(他作業と並列可・依存なし)
- 老中によるDB書込は wave 2(他足軽作業の後に実施・並行不要)

---

## §6 P4 お針子監査強化範囲定義

### §6.1 `needs_audit: true` の自動判定 — 老中側で実装

**核心**: 自動判定の実装場所は**お針子側ではなく老中側**(タスク割当時)。
理由: お針子は判定ロジックを持つのではなく、`needs_audit: true`のタスクを「監査する」のが職掌。判定は割当時(老中)が適切。

### §6.2 自動判定ロジック案 — キーワード+パスのハイブリッド

```python
# 老中側の subtask 割当処理に追加(scripts/karo_*.py 実装は別cmd)

CRYSTALLIZE_KEYWORDS = [
    "crystallize", "結晶化", "没日録", "高札",
    "botsunichiroku", "thread_replies", "swarm.db",
]
CRYSTALLIZE_PATHS = [
    "scripts/botsu/",
    "agent-swarm/server/botsu/",
    "agent-swarm/config/swarm.yaml",
    "agent-swarm/crystals/",
]

def needs_audit_auto(subtask: dict) -> bool:
    desc = (subtask.get("description") or "").lower()
    target = subtask.get("target_path") or ""
    expected = subtask.get("expected_files") or []  # 軍師predicted_outcome
    if any(k.lower() in desc for k in CRYSTALLIZE_KEYWORDS):
        return True
    if any(p in target for p in CRYSTALLIZE_PATHS):
        return True
    if any(p in (e.get("path") or "") for p in CRYSTALLIZE_PATHS for e in expected):
        return True
    return False
```

判定優先度:
1. 殿/家老が手動で`needs_audit: true/false`指定 → **手動指定を絶対優先**
2. 上記ロジックで`true`判定 → 自動付与
3. それ以外 → 既定`false`

### §6.3 お針子チェック項目追加(チェックリスト形式)

`instructions/ohariko.md`(or `context/ohariko-checklist.md`)に以下のチェック項目を追加:

| # | 項目 | 確認方法 |
|---|---|---|
| C1 | パス整合性 | 報告に記載された`scripts/botsu/*`パスが`git ls-files`に存在するか |
| C2 | カウント整合性 | 報告中の「N回目稼働」記述があれば`SELECT COUNT(*) FROM thread_replies WHERE board='crystals' GROUP BY thread_id`の実カウントと突合 |
| C3 | 名称ドリフト検出 | `cmds.command`と実装内容(commit message・コードコメント・docstring)の核心キーワードが一致するか |
| C4 | テスト存在チェック | `scripts/botsu/*`修正なら対応する`tests/test_*.py`が存在するか |
| C5 | env変数追記整合 | 新環境変数を導入している場合`.env.example`に追加コメントがあるか |

### §6.4 既存お針子監査ルーブリックとの統合

- お針子の18点ルーブリック(品質15+ポリシー3)に**追加点として組み込まない**(過剰採点化を避ける)
- 代わりに**Pre-flight check**として、ルーブリック採点前に C1-C5 を必須確認
- いずれか1つでも違反 → ルーブリック採点せず**差し戻し**(老中経由)

---

## §7 「N回目」告知廃止(Q2)の周知方法

### §7.1 現状の文化(調査結果)

- `instructions/*.md`に「N回目稼働」を要求する記述は**実は存在しない**
- 老中報告(`queue/inbox/roju_reports.yaml`)・部屋子/足軽報告で**自然発生した報告慣習**
- cmd_570 §5でカウント誤りが顕在化(13回目→実16回目)

### §7.2 廃止の周知3手順

| 手順 | 内容 | 担当 | タイミング |
|---|---|---|---|
| (1) Memory MCP記録 | system-rules に「結晶化N回目告知文化廃止(2026-05-02殿裁定)」を追加 | 老中 | 即時(本cmd終了後) |
| (2) send-keysテンプレ整理 | 老中→足軽完遂送信テンプレから「結晶化N回目稼働」フレーズを除去 | 老中 | 即時 |
| (3) 違反検出 | お針子監査で「N回目」記述を**警告レベル**(差し戻しではなく注意)で検出 | お針子 | 自動・継続的 |

### §7.3 既存roju_reports.yaml中の旧告知 — **保持**

- 過去報告は**履歴価値あり**(cmd_570の遡及検証で活用された実績)
- 削除すると「カウント誤りの原因調査」ができなくなる
- → 保持。ただし**新規報告では使わない**

### §7.4 instructions改訂は不要

- 既存`instructions/*.md`に該当記述はない
- 「廃止する」のは**慣習**であり、文書化された規則ではない
- Memory MCP記録(手順1)で十分・instructions改訂はオーバーキル

---

## §8 agent-swarm Viewer接続点(後続cmd)

### §8.1 Viewer 2層分離との整合性

Viewer(後続cmd予定): swarm.dbをreadしてWeb UIで表示する仕組み。
本機構の>>1-10は**Viewerのヘッダー領域(プロジェクト固定情報)**として表示される想定。

| Viewer要件 | 本機構の対応 |
|---|---|
| project_*スレを「ヘッダーカード」として固定表示 | thread_id接頭辞`project_`で識別可・既存スキーマで対応 |
| MD/Mermaidレンダリング | **Viewer側責務**(server側はプレーン文字列を返す) |
| 「最新版」抽出ロジック(§2.4 (B)案) | Viewer側で`<!-- TEMPLATE:N -->`magic行から最新posted_atのレスを優先 |
| cmd_*スレ(完遂)は別カラム表示 | thread_id接頭辞で分離・スキーマ変更不要 |

### §8.2 dat_server.py への影響

**最小限の改修案**(Viewer実装cmd内で必要に応じて):

| 改修 | 内容 | 必要性 |
|---|---|---|
| `GET /bbs/{board}/threads?prefix=project_` | thread_id接頭辞フィルタAPI | Viewer側のロジックでクライアントフィルタリング可・必須ではない |
| `GET /bbs/{board}/template/{project}` | テンプレ専用便利API(>>N毎の最新版を返す) | Viewer簡素化のためあると良い・必須ではない |
| Markdownレンダリング | server側でやらない(Viewer側) | server側追加不要 |

### §8.3 VPS Docker化時のvolume境界(2026-04-28殿明言整合)

| データ | volume | アクセス |
|---|---|---|
| swarm.db (thread_replies含む) | swarm_db (named volume) | swarm container=RW, shogun=RW(直叩き)/RO(HTTP) |
| crystals/*.md (cmd完遂目次) | crystals (shared volume) | shogun=RW, swarm=RO |
| project_*スレ本文 | swarm.db内に格納 → 新規volume**不要** | 既存swarm_db volume内に納まる |

**結論**: 本機構導入で新規 named volume の追加は不要。既存設計(cmd_517_crystallization_design_v2.md §F)のvolume割当そのままで動作する。

### §8.4 DATスレ形式維持と内部自由設計の境界

- DATスレ**外形**(thread_replies スキーマ): 維持。変更すると agent-swarm の他機能(任務板・雑談板等)が壊れる
- レス**内容**(body): 自由設計。MD/Mermaid/`<!-- TEMPLATE:N -->`magic行など、外部から見れば単なるテキスト
- → **2ch仕様縛り解放は body内部の話**。スキーマレベルでは2ch互換維持(JDim等の既存ビューアでも閲覧可)

---

## §9 simplicity check 3問(必須)

### Q1. 本当に必要か?(>>1-10テンプレ化の本質的価値)

**回答: YES (条件付き)**

根拠:
- コンパクション復帰時、エージェントは`CLAUDE.md`+`instructions/*.md`+`context/*.md`を再読込するが、**プロジェクト構造の俯瞰図**は分散している
- DATスレに固定領域として置くことで、Viewer経由の即時把握が可能(殿の「無限の星空」ビジョンに寄与)
- ただし**>>1-10全部を必須化したら過剰**。>>1-5必須+>>6-10任意で簡素化

懸念事項:
- 既存`agent-swarm/crystals/{project}.md`目次・`context/{project}.md`知見との**重複**(unknown_unknowns #12参照)
- 二重管理になりドリフトする恐れ → 役割分離を明確化(>>1-10=構造、目次MD=cmd索引、context/=実装知見)で回避

### Q2. 最小構成は何か?(削れる要素)

**削減した要素**:

| 削減対象 | 削った理由 |
|---|---|
| 自動初期化(scripts/botsu/crystallize.py 内で全プロジェクト自動スキャン) | 殿好み: マクガイバー精神。手動初期化で十分 |
| >>6-10 必須化 | 過剰テンプレ化禁止(殿明言)。任意余白に降格 |
| `do_reply_add()`の`notify_quiet`新規追加 | 既存`notify=False`(L119)で対応済 |
| `dat_server`への PATCH エンドポイント | INSERT-only維持・最新版優先方式(§2.4 案B)で代替 |
| crystals板スキーマ変更 | 不要・既存スキーマで動く |
| お針子18点ルーブリックへのチェック点追加 | 過剰採点化回避・Pre-flight checkに格下げ |

**残した最小構成**:
- 関数2本(`init_project_template`/`update_template_reply`) + ヘルパ1本(`_existing_template_nums`) ≈ 100行
- magic行`<!-- TEMPLATE:N -->`規約のみ
- 老中側の自動判定ロジック ≈ 20行
- お針子Pre-flight check(C1-C5・チェックリスト形式) ≈ 文書追加のみ
- karo-checklist.md + karo_check.sh ≈ 50-80行

### Q3. 殿の好み(Simple > Complex / Build the brain, buy the body)に整合するか?

**回答: 整合**

| 殿の哲学 | 本設計の整合性 |
|---|---|
| Simple > Complex | >>6-10任意化・自動初期化なし・Pre-flight check化 |
| Build the brain, buy the body | 自前swarm活用(2ch仕様縛り解放を活かしてMD/Mermaid採用)・既存schemaで対応(余分な「buy」なし) |
| マクガイバー精神(ガムテ+爆発) | 手動初期化(スクリプトで叩く・ガムテ)+killスイッチ`SHOGUN_CRYSTALS_DISABLE`(爆発)が継続 |
| 月額忌避・ローカル優先 | 全機構ローカル動作・新規外部サービス依存なし |
| VPS Docker化長期方針 | 新規volume不要・既存設計に納まる |

**simplicity check: 3問パス**

---

## §10 unknown_unknowns(必須10項目以上)

軍師v2必須要件。盲点を**12項目**列挙:

### #1 thread_replies INSERT-only と「>>1-10更新可」要件の矛盾(最大リスク)

- リスク: 「更新可」と裁定されたが現実装は INSERT-only。誤った実装でPATCHエンドポイントを増やすと append-only思想が崩れる
- 影響: append-only前提の他コンポーネント(お針子監査・Viewer表示の整合性)が破綻
- 緩和策: 最新版優先方式(§2.4 案B)で対応・PATCHエンドポイント追加は採用しない

### #2 既存16スレへのテンプレ後付け不可性(設計上既知)

- リスク: 既存16スレ(cmd_555-570)に >>1-10 を後付けできない(物理的に不可)
- 影響: 殿/家老が「全スレに均一テンプレ」を期待していると齟齬
- 緩和策: §2の通り「触らない」方針を明記・project_*スレで別建て

### #3 「>>N更新」のレース条件

- リスク: 軍師・家老・殿が同時に同じ`<!-- TEMPLATE:2 -->`を投稿すると、Viewerが古い方を最新と表示する可能性(posted_at同秒衝突)
- 影響: アーキ図の古いMermaidが表示される事故
- 緩和策: thread_replies.id(AUTOINCREMENT)を二次キーとして「最新版」判定に使用(posted_at同秒なら大きいid優先)

### #4 通知5発(or 10発)爆撃の再発

- リスク: `init_project_template()`で>>1-10一気に投稿すると通知10回発火
- 影響: 老中・足軽・お針子に大量通知 → 既知問題(cmd_517_design_v2 §E-2)
- 緩和策: `notify=False`を継続使用(既存`_swarm_post_python()`で実装済)・HTTPフォールバック時のみ通知発火する点に注意

### #5 「PJ概要」「アーキ図」「データフロー」の三重重複

- リスク: 同内容が `CLAUDE.md` / `dashboard.md` / `context/{project}.md` / `agent-swarm/crystals/{project}.md` / project_*スレに散在
- 影響: ドリフトで「どれが正?」が分からなくなる
- 緩和策: **正データを1箇所に絞る**(PJ概要=`CLAUDE.md`§概要、構造=project_*スレ、cmd索引=目次MD)。役割分離を §1.1 と §8.1 で明記済

### #6 SHOGUN_CRYSTALS_DISABLE時の挙動

- リスク: killスイッチ有効時に`init_project_template()`が呼ばれた場合の挙動が未定義
- 影響: 静かに失敗 vs 例外 で運用が混乱
- 緩和策: `crystallize_cmd()`同様に冒頭でチェック・`{"posted":[],"skipped":True,"reason":"disabled"}`を返す統一仕様

### #7 sys.path競合の二次影響

- リスク: shogun側`scripts/botsu/`と agent-swarm側`server/botsu/`が同名パッケージ。新規関数が増えるたび競合面積が拡大
- 影響: 既知(cmd_517_design_v2 §E-8で対策済)。新関数も同じ`saved=...sys.modules.pop`方式を踏襲必要
- 緩和策: 新規関数も既存`_swarm_post_python()`を必ず経由・直接`from botsu...`を書かないコーディング規約

### #8 VPS移行時のSQLite→PostgreSQL等への変更

- リスク: 殿のVPS Docker化長期方針で将来DB変更があり得る。`<!-- TEMPLATE:N -->`magic行はDB依存だが、`thread_replies.body`スキーマ依存のロジック(`_existing_template_nums`等)が壊れる可能性
- 影響: 新DB移行時に再実装要
- 緩和策: 抽象化レイヤ(`_existing_template_nums`の中だけにSQL閉じ込め)を維持・移行時はそこを書き換えるだけで済む

### #9 自動判定の誤検知(P4)

- リスク: キーワード「結晶化」「没日録」が広範囲に該当 → 大半のタスクが`needs_audit: true`化
- 影響: お針子の負荷増・本来不要な監査が増える
- 緩和策: 監視期間を設けて誤検知率測定 → 必要に応じてキーワードを絞る・例外パターン(NOT条件)を追加

### #10 「テンプレ未記入」レス(`(未記入)`)の蓄積

- リスク: `init_project_template()`が空白プレースホルダで>>1-10を投稿(§3.2 scaffolds未指定時) → DAT上に「(未記入)」レスが大量に並ぶ
- 影響: Viewer表示が見栄え悪い・運用初期で印象不良
- 緩和策: scaffoldsに最低限の文言(殿/家老が起草)を渡す運用ルール・「未記入」プレースホルダ投稿はオプション化(default: 投稿しない・必要時のみ)

### #11 2ch仕様縛り解放の二次影響(文字数無制限)

- リスク: 「文字数無制限」を活かしてMermaid/コード断片を直書き → body長10万字超で `subject.txt` 生成・dat配信パフォーマンス劣化
- 影響: agent-swarm 全体が重くなる
- 緩和策: 軍師既存ルール(長文はdocs/配下mdに分離してリンク・本文は要約3行)を本機構にも適用・>>1-10にも長文制限ガイドライン(レス本文1KB以下推奨)

### #12 cmd_*スレと project_*スレの命名衝突可能性

- リスク: 将来`cmds.id="project_xxx"`を作ってしまうと thread_id衝突
- 影響: project_*スレに cmd完遂レスが混入
- 緩和策: `cmds.id`の命名規則(現状`cmd_<連番>`)を死守・コードレベルで`project_`接頭辞は予約語として禁止(NamedTuple定数で管理)

---

## 付録: 実装フェーズcmd起票案

### A.1 cmd_572(仮): 結晶化機構v2 >>1-10テンプレ化+P1+P3+P4 実装

**親cmd**: cmd_571(本cmd)
**性格**: cmd_558の後続実装(機構拡張)

### A.2 subtask 分解案

| ID | subtask | 担当 | repo | bloom | 推定工数 | wave | blocked_by |
|---|---|---|---|---|---|---|---|
| **S1** | `scripts/botsu/crystallize.py` に`init_project_template/update_template_reply/_existing_template_nums`追加+tests | 足軽1(haiku/sonnet) | shogun | L3 | 半日 | 1 | - |
| **S2** | `scripts/botsunichiroku.py crystallize project init/update` CLIサブコマンド追加 | 足軽1 | shogun | L3 | 0.25日 | 2 | S1 |
| **S3** | `context/karo-checklist.md`新規作成(P1 第二層) | 足軽2(haiku) | shogun | L2 | 0.25日 | 1 | - |
| **S4** | `scripts/karo_check.sh`新規作成(P1 第三層・実行権限付与) | 足軽2 | shogun | L2 | 0.25日 | 1 | - |
| **S5** | `.env.example` コメント追記(P3 — `SHOGUN_CRYSTALS_DIR/SWARM_*`の用途明記) | 足軽2 | shogun | L1 | 0.1日 | 1 | - |
| **S6** | 老中: `cmd update cmd_517 --command`実行で名称更新(P3 DB書込) | 老中(直接) | shogun | L1 | 0.05日 | 2 | S5 |
| **S7** | 老中側 needs_audit 自動判定ロジック実装(P4・キーワード+パス監視) | 足軽1 | shogun(scripts/karo_*.py) | L4 | 0.5日 | 2 | S1 |
| **S8** | お針子 Pre-flight check(C1-C5)文書化(`instructions/ohariko.md`へ追記 or `context/ohariko-checklist.md`新規) | 軍師レビュー → 足軽2実装 | shogun | L3 | 0.25日 | 2 | - |
| **S9** | Memory MCP system-rules に「N回目告知文化廃止(2026-05-02殿裁定)」追加 | 老中 | - | L1 | 0.05日 | 1 | - |
| **S10** | パイロット動作確認: shogun/hardware/tooling 3PJで`init_project_template`実行+目視確認 | 軍師(Plan)→足軽1(Do)→お針子(Check) | swarm.db | L3 | 0.5日 | 3 | S1, S2, S6, S7, S8 |

合計工数: 約**2.5足軽日** (並列なら2足軽×1.25日)

### A.3 wave 構成

```
wave 1 (並列): S1, S3, S4, S5, S9
wave 2 (並列): S2(←S1), S6(←S5), S7(←S1), S8
wave 3 (順次): S10(←wave2全て)
```

### A.4 worker推奨

- **足軽1(haiku/sonnet)**: S1, S2, S7(コード変更主体)
- **足軽2(haiku)**: S3, S4, S5, S8(文書化・bash・MD編集主体)
- **老中**: S6, S9(DB書込・Memory MCP)
- **軍師**: S8レビュー+S10 Plan/Act
- **お針子**: S10 Check

### A.5 worktree判定

- shogun側作業のみ → **worktree不要**(同一repo・別ファイル並列作業可)
- agent-swarm側変更**なし**(Viewerは別cmd) → repo境界でworktree不要

### A.6 PDCA判定

- pdca_needed: **false**
- 理由: 既存`crystallize_cmd()`の挙動を変えない(追加機能のみ)・新規アーキテクチャではない・パイロット要素は S10で完結

### A.7 needs_audit判定

- needs_audit: **true**(機構拡張のため・cmd_570の教訓)
- お針子チェック項目: C1-C5 全項目+ S10パイロット結果の DAT 投稿確認

### A.8 ロールバック手順

- S1: コミット単位でrevert(関数追加のみのため影響範囲限定)
- S6: `cmd update cmd_517 --command "(旧名称)"`で復旧可
- S10失敗時: `python3 -c "import sqlite3; ..."`で`thread_id LIKE 'project_%'`の手動DELETE可(復旧用スクリプトを実装cmd内で用意)

---

## §11. OSI 7層類比による>>1-10階層化(subtask_1205追補)

> **追補背景**: 殿追加観点①(2026-05-02 subtask_1204受領後)。
> 軍師の重箱突き歓迎との殿ご意向に応じ、殿草案を出発点に**精緻化+再解釈**を行う。

### §11.1 殿草案の重箱突き(軍師再解釈)

殿草案(下命文より):

| OSI層 | 役割 | 殿草案 結晶化対応 |
|---|---|---|
| L1 物理層 | 媒体・信号 | DAT形式そのもの(swarm.db thread_replies) |
| L2 データリンク層 | フレーム | (空白) |
| L3 ネットワーク層 | ルーティング | >>2-4 IPv4↔IPv6相当(構造刷新時のみ更新) |
| L4-L5 | 接続管理 | (空白) |
| L5-L7 上位層 | アプリ層 | >>5-10 + >>11+ |
| (※L2位置か?) | (草案揺らぎ) | >>1 プロジェクト概要 |

**軍師重箱突き ① — L2=>>1 配置の妥当性低い**:

OSIのL2(データリンク層)は「同一物理セグメント内のフレーミング・MACアドレス・エラー検出」を担う層であり、**意味論ではなく構造**を扱う。
「プロジェクト概要」は紛れもなくL7アプリケーション層の意味論。殿草案の「L2=>>1」は不整合。

**軍師重箱突き ② — 「>>1-10 を OSI 7層に分割」は二軸混在**:

殿の真意を二軸に分けると以下になる:
- **軸A: OSI類比 = 媒体非依存性のメタファ**
  - 「>>1-10 は全てL7アプリケーション層に位置し、下層(L1-L6)が変わっても意味は不変」を宣言する装置
- **軸B: 殿のL3=>>2-4(構造刷新時のみ更新) = 変更ガバナンス階層**
  - これはOSI層ではなく「>>レスごとに更新頻度の階層がある」という別概念

軍師は**両軸を分離**し、§11.2(軸A)と§11.3(軸B)で別々に整理する。

### §11.2 軸A: OSI 7層 — 媒体非依存性のメタファ(軍師精緻化版)

>>1-10 自体を7層に分割するのではなく、**機構全体を7層に分解**し、>>1-10はL7に置く。

| OSI層 | 結晶化機構の対応物 | 役割 | 差し替え可能性 |
|---|---|---|---|
| **L1 物理層** | swarm.db ファイル(SQLite磁気ディスク格納) | 物理ストレージ | PostgreSQL/MySQL/分散KVS等に差し替え可(unknown_unknowns #8整合) |
| **L2 データリンク層** | thread_replies テーブル schema(id/thread_id/board/author/body/posted_at) | レス単位のフレーミング・author識別 | 列追加・別テーブル化可。既存>>1-10の意味は不変 |
| **L3 ネットワーク層** | thread_id プレフィクス分離(`cmd_*` / `project_*`) | スレ間ルーティング・名前空間分離 | 命名規則変更可・新prefix追加可(`exp_*`等) |
| **L4 トランスポート層** | `_swarm_post_python()` / `_swarm_post_http()` の二系統(Python直叩き+HTTPフォールバック) | 信頼性配送・notify=False抑止 | gRPC/MQ等に差し替え可(関数差し替えで吸収) |
| **L5 セッション層** | swarm.yaml `writers`権限・通知suppression状態 | 書き込みセッション管理 | 認証方式変更可(API key→OAuth等) |
| **L6 プレゼンテーション層** | `<!-- TEMPLATE:N -->` magic行 / Markdown / Mermaid | データ表現・最新版優先方式の論理判定 | 表現規約差し替え可(`<TEMPLATE:N>`等別記法へ) |
| **L7 アプリケーション層** | **>>1-10 各レスの意味論(>>1=概要、>>2=アーキ図…)** | プロジェクト構造ドキュメントとしての意味 | 各レスのスロット定義(`TEMPLATE_REPLY_DEFINITIONS`)が真の上位インタフェース |

**核心宣言**:
> 「**>>1-10 は全てL7に位置する。L1-L6が将来差し替わっても、>>1-10の意味論は変わらない**」
> 既存§10(unknown_unknowns #8 VPS移行時のSQLite→PostgreSQL等)は、この媒体非依存性宣言の具体例。

### §11.3 軸B: 変更ガバナンス階層(殿のL3=>>2-4観点を昇華)

殿草案「>>2-4 = 構造刷新時のみ更新」は OSI ではなく**更新頻度の階層**を表している。軍師はこれを**変更ガバナンス階層**として独立に明文化する。

| 層名 | レス番号 | 更新頻度の典型 | 更新トリガ |
|---|---|---|---|
| **安定層(Foundation)** | >>1, >>10 | 年単位(プロジェクト発足以降ほぼ不変) | プロジェクト方針変更/新概念導入 |
| **構造層(Architecture)** | >>2, >>3, >>4 | 月単位 | エージェント追加/板新設/通信プロトコル変更 |
| **運用層(Operations)** | >>5, >>6, >>7, >>8, >>9 | 週単位 | インシデント/ファイル増減/環境変数追加/メトリクス追加/接続点追加 |

この三層は§12(権限管理)と直結する。**「変更頻度の高い層ほど主筆者を分散」**が軍師の権限設計原則。

### §11.4 層独立性・差し替え可能性・媒体非依存性 設計原則

- **層独立性**: 各>>レスは独立したthread_replies行で他レスのbodyに依存しない。`<!-- TEMPLATE:N -->` magic行で番号自己同定 → 順序入れ替えも理論上可
- **差し替え可能性**: 軸A(L1-L6)の各層を差し替えても上位は不変。例: Mermaid→ASCIIへの>>2差し替えで>>3-4は影響なし
- **媒体非依存性**: §10 unknown_unknowns #8 でPostgreSQL移行時の対応既出 → 抽象化レイヤ(`_existing_template_nums`)にSQL閉じ込め済

### §11.5 既存§との整合更新

| 既存§ | §11追補による補強 |
|---|---|
| §1.2 レス毎仕様表 | 「変更頻度」列の解釈を§11.3で精緻化(レス単位の更新トリガが明確化) |
| §2.4 案B「最新版優先方式」 | §11.2 L6プレゼンテーション層の具体実装として位置づけ整理 |
| §8.1 Viewer接続 | 「Viewerはアプリ層(L7)・dat_serverはセッション層(L5)」と層境界が明確化 |
| §10 unknown_unknowns #8 | 「媒体非依存性宣言の具体例」として§11.2と相互参照 |

§1-§10本文は無変更(殿明示の禁止事項を厳守)。

### §11.6 simplicity check 整合(§11限定)

| Q | 答 |
|---|----|
| OSI類比は過剰設計か? | NO. **概念整理のみ・コード変更不要**。L1-L7の役割分担を文書化するだけで、既存実装は1行も変わらない |
| 7層全て埋める必要があるか? | NO. **媒体非依存性宣言が目的**。実装層は既に存在(L1=swarm.db, L7=>>1-10) |
| 殿の好みに整合するか? | YES. 「Build the brain, buy the body」=「上位層(brain)=不変、下位層(body)=差し替え可」と一致 |

---

## §12. 権限管理 — 各>>レス更新権限の負荷分散論点(subtask_1205追補)

> **追補背景**: 殿追加観点②(2026-05-02)。
> 殿の問い「家老1人運用の負荷評価」に対し、軍師の重箱突き: **現行§1.2案は既に4ロール分散済**。
> 評価軸を「家老単独 vs 分散」ではなく「分散の階層化が適切か」へ組み替える。

### §12.1 現行§1.2案の権限棚卸し(重箱突き起点)

§1.2 レス毎仕様表の「主筆者」列を集計:

| 主筆者 | 担当レス | 数 |
|---|---|---|
| 殿 | >>1, >>5, >>10 (共担) | 3 |
| 家老 | >>1, >>6, >>7, >>10 (共担含む) | 4 |
| 軍師 | >>2, >>3, >>4, >>5, >>7, >>9 (共担含む) | 6 |
| お針子 | >>5, >>8 (共担含む) | 2 |

**重箱突き**: 既に4ロール分散済(殿・家老・軍師・お針子)。「家老1人運用」前提は§1.2と既に齟齬している。
殿の真の問いは「**この分散は適切か・偏りはないか・SPOFはないか**」と再解釈する。

### §12.2 家老1人運用前提の負荷評価(殿明示観点)

仮に家老1人で全>>レスを管理した場合の負荷:

| 観点 | 評価 |
|---|---|
| 更新トリガー頻度(全レス合計) | 月10-15件程度(プロジェクト3つ × 平均月3-5更新)。1人で処理可能な範囲 |
| 専門性ミスマッチ | >>2 アーキ図(軍師の専門)を家老が描くと品質低下 / >>5 地雷(お針子のインシデント観察)を家老が把握しづらい |
| **SPOF(単一障害点)リスク** | **重大**。家老不在(コンパクション中・別作業集中)で>>レス更新が完全停止 |
| ボトルネック | 月10-15更新の調整コスト・優先度判断が家老に集中 |

**結論**: 家老1人運用は**実行可能だが推奨されない**。専門性ミスマッチとSPOFが現実的リスク。

### §12.3 権限分散選択肢評価(案A-D)

#### 案A: 家老1人継続(全レス更新権限を家老に集約)

| 軸 | 評価 |
|---|---|
| simplicity | ◎ 最大限シンプル |
| 専門性 | × 軍師/お針子の専門性活用なし |
| SPOF | × 家老不在で停止 |
| 拡張性 | × 拡張できない構造 |
| 殿好み | × 「Build the brain」の brain が家老1人に偏る |

評価: **不採用**(SPOF重大)

#### 案B: 家老 + 軍師(2ロール)

| 軸 | 評価 |
|---|---|
| simplicity | ○ 2ロールで明快 |
| 専門性 | ○ アーキ系=軍師、運用系=家老 で分担可 |
| SPOF | △ 軍師不在で構造系停止 |
| 拡張性 | △ お針子の監査専門性が活かせない |
| 殿好み | ○ |

評価: **次善**(お針子の>>5地雷・>>8メトリクス専門性が浮く)

#### 案C: 殿+家老+軍師+お針子(4ロール・現行§1.2踏襲)

| 軸 | 評価 |
|---|---|
| simplicity | ○ 4ロールは既存役割と一致(増えない) |
| 専門性 | ◎ 各ロールの職掌と整合 |
| SPOF | ◎ 4ロール分散でSPOFなし |
| 拡張性 | ○ 家老複数化・専門軍師化等の拡張余地あり |
| 殿好み | ○ |

評価: **基本採用**(現行§1.2の方向性は妥当)

#### 案D: 軍師独自案 — 変更ガバナンス階層×権限階層化

§11.3の三層(安定/構造/運用)に対応した権限割当:

| 層 | レス | 主筆者 | 承認者 | 承認の必須性 |
|---|---|---|---|---|
| 安定層(年単位) | >>1 プロジェクト概要 | 殿/家老 | 殿 | **必須**(プロジェクト方針変更は殿裁定事項) |
| 安定層 | >>10 用語集 | 家老 | 軍師(任意) | 任意(用語追加は重要度低) |
| 構造層(月単位) | >>2 アーキ図 | 軍師 | 家老(任意) | 任意 |
| 構造層 | >>3 構成要素 | 軍師 | 家老(任意) | 任意 |
| 構造層 | >>4 データフロー | 軍師 | 家老(任意) | 任意 |
| 運用層(週単位) | >>5 既知の癖・地雷 | お針子/軍師 | (承認不要) | なし |
| 運用層 | >>6 ファイル索引 | 家老 | (承認不要) | なし |
| 運用層 | >>7 環境変数 | 軍師/家老 | (承認不要) | なし |
| 運用層 | >>8 メトリクス | お針子 | (承認不要) | なし |
| 運用層 | >>9 外部接続点 | 軍師 | (承認不要) | なし |

| 軸 | 評価 |
|---|---|
| simplicity | ○ 4ロール維持・「承認任意デフォルト」で過剰承認回避 |
| 専門性 | ◎ 変更頻度に応じた権限階層 |
| SPOF | ◎ 運用層は承認不要・構造層も承認任意 |
| 拡張性 | ◎ 「層」という抽象を新規ロール(複数家老等)に拡張可 |
| 殿好み | ◎ Simple > Complex(承認は基本任意・必須は1箇所のみ) |

評価: **軍師推奨案** ✦

### §12.4 軍師推奨 — **案D採用**(理由)

1. 案Cの「4ロール分散」を継承しつつ、§11.3の変更ガバナンス階層を権限軸に組み込み専門性を最大化
2. 「承認任意デフォルト+>>1のみ殿承認必須」で過剰承認を回避(simplicity check合致)
3. 案Cの均一分散と異なり、**運用層は承認なし**で機動性を確保(週単位更新でも調整コスト最小)
4. 安定層は殿承認必須にすることで、プロジェクト発足時の方針承認を結晶化

### §12.5 拡張性視点 — 3エージェント以上分散運用

将来「複数家老」「専門軍師」「お針子チーム」になった場合の権限拡張:

| 拡張シナリオ | 案D での対応 |
|---|---|
| 家老複数化(担当PJ別) | >>6/>>7担当を「該当PJの家老」に振り分け。`thread_replies.author`カラムで追跡可 |
| 軍師複数化(専門別) | >>2(アーキ専門軍師)・>>3(セキュリティ専門軍師)・>>4(運用専門軍師)に専門分割可 |
| お針子チーム化 | >>5(インシデント担当)・>>8(メトリクス担当)に分割可 |
| 新ロール導入(例: 勘定吟味役) | 新層追加(例: 「監査層」)で吸収可。`<!-- TEMPLATE:N -->` magic行は変えず、`TEMPLATE_REPLY_DEFINITIONS`定数に slug を増やすだけ |

**swarm.yaml 設定への影響**:
crystals板 `writers: ["shogun", "roju", "ohariko", "gunshi"]` は4ロール対応済(変更不要)。新ロール追加時のみ追記。

### §12.6 simplicity check 整合(§12限定)

| Q | 答 |
|---|----|
| 案Dは過剰権限分散か? | NO. **4ロール維持**(増えない)・**承認は基本任意**(>>1殿のみ必須) |
| 階層化は複雑度を上げるか? | NO. §11.3の変更ガバナンス階層を再利用(新規概念導入なし) |
| 殿の好みに整合するか? | YES. 「Simple > Complex」=承認任意デフォルト・「Build the brain, buy the body」=専門性活用 |

### §12.7 既存§との整合更新(§12由来)

| 既存§ | §12追補による補強 |
|---|---|
| §1.2 主筆者列 | §12.3 案Dの「主筆者+承認者+承認必須性」3列に拡張する解釈を提示(本文書換は不要・解釈の追補) |
| §3.2 `init_project_template()` | scaffolds 引数で殿承認必須の>>1を別途検証する余地(任意拡張) |
| §6.3 お針子チェック項目 | C6追加候補: 「>>1更新時に殿承認痕跡(発言履歴 or Memory MCP記録)があるか」(任意・実装cmd判断) |

### §12.8 §11×§12 統合表(参考・運用ガイド)

| レス | OSI(軸A) | ガバナンス層(軸B/§11.3) | 主筆者 | 承認 |
|---|---|---|---|---|
| >>1 | L7 | 安定 | 殿/家老 | 殿(必須) |
| >>2 | L7 | 構造 | 軍師 | 家老(任意) |
| >>3 | L7 | 構造 | 軍師 | 家老(任意) |
| >>4 | L7 | 構造 | 軍師 | 家老(任意) |
| >>5 | L7 | 運用 | お針子/軍師 | なし |
| >>6 | L7 | 運用 | 家老 | なし |
| >>7 | L7 | 運用 | 軍師/家老 | なし |
| >>8 | L7 | 運用 | お針子 | なし |
| >>9 | L7 | 運用 | 軍師 | なし |
| >>10 | L7 | 安定 | 家老 | 軍師(任意) |

>>1-10は全てL7(媒体非依存性宣言)、ガバナンス層と権限は変更頻度に応じて差別化。

---

### §12.9 付録 実装cmd_572起票案の見直し(§11/§12 影響評価)

| 評価軸 | §11(OSI類比)の影響 | §12(権限管理 案D)の影響 |
|---|---|---|
| subtask 数増減 | **増減なし**(概念整理・コード変更不要) | **増減なし**(swarm.yaml writers変更不要・instructions改訂は最小) |
| wave 構造変更 | 不要 | 不要 |
| 足軽人数・工数見積 | 変動なし(2足軽×1.25日並列) | S3(`context/karo-checklist.md`)に「権限マトリクス§12.8参照」リンク追加・S8(お針子checklist)にC6を任意項目追加。**+0.1日程度** |
| worktree判定 | 不要(変動なし) | 不要(変動なし) |

**追補subtask候補(任意・付録扱い)**:

- **S11(任意)**: §11/§12 を `instructions/karo.md` または `context/karo-checklist.md` の付録として参照する1行追加 — **0.1日**(任意・足軽2に統合可)

→ **付録の本文(subtask 10件・wave 3段・足軽2名×1.25日)は変更なし**。S11は「あれば良い」程度・必須化しない(simplicity維持)。

### 付録 simplicity check 統合(§11/§12由来)

| Q | 答 |
|---|----|
| §11/§12 で実装範囲が膨れたか? | NO. 概念整理+権限解釈の追補のみ・既存subtask構成不変 |
| 文書増加は適切か? | YES. >>1-10 設計の自己説明性が向上・将来の拡張時に再利用可 |
| 追補だけで殿要件を満たすか? | YES. §11(OSI類比)+§12(権限管理)+既存§1-§10で完結 |

---

## §13. North Star Alignment

> **subtask_1205注記**: 既存§番号は§11/§12の新規追加に伴い§13/§14/§15へrenumber(本文無変更・整合更新)。
> 殿指示「§番号体系は既存維持」と新§11/§12要請は番号衝突するため、軍師判断で番号衝突回避を優先(本文書換なし)。

```yaml
north_star_alignment:
  status: aligned
  reason: |
    本設計はコンパクション/clear後でもPJ知見をエージェントが即座に取り戻せる状態(殿の「無限の星空」ビジョン)に
    寄与する。プロジェクト構造ドキュメントを永続DAT(thread_replies)に固定することで、
    Viewer経由・grep経由・コンパクション後の各エージェント再起動時に即時把握可能になる。
    過剰テンプレ化を避けることで、殿のSimple > Complex哲学とも整合。
  risks_to_north_star:
    - "二層管理(目次MD+project_*スレ+context/*.md)のドリフトで『どれが正?』が分からなくなる(unknown_unknowns #5で緩和済)"
    - "INSERT-only制約と更新可要件の矛盾を解決しないまま実装すると、append-only思想が崩れる(§2.4 案Bで緩和済)"
    - "自動判定誤検知でお針子過負荷(unknown_unknowns #9で緩和策提示)"
```

---

## §14. predicted_outcome(実装フェーズ後の予想)

```yaml
predicted_outcome:
  expected_files:
    - path: "scripts/botsu/crystallize.py"
      change_type: "modify"
      description: "新規関数3本追加(約100行増・既存234行→約330行)"
    - path: "scripts/botsunichiroku.py"
      change_type: "modify"
      description: "crystallize project init/update サブコマンド追加(約30行増)"
    - path: "context/karo-checklist.md"
      change_type: "new"
      description: "家老ファイル未存在判定前チェックリスト(P1 第二層)"
    - path: "scripts/karo_check.sh"
      change_type: "new"
      description: "家老の機械的存在確認ツール(P1 第三層)"
    - path: ".env.example"
      change_type: "modify"
      description: "SHOGUN_CRYSTALS_DIR等のコメント追記(P3)"
    - path: "tests/test_crystallize_template.py"
      change_type: "new"
      description: "新規関数のユニットテスト約80行"
    - path: "context/ohariko-checklist.md (or instructions/ohariko.md追記)"
      change_type: "new or modify"
      description: "お針子Pre-flight check C1-C5 (P4)"
    - path: "scripts/karo_*.py (老中側コード)"
      change_type: "modify"
      description: "needs_audit自動判定ロジック追加(P4)"
  expected_tests:
    pass_count: 9   # 既存6 + 新規3
    key_assertions:
      - "init_project_template が冪等に動作"
      - "update_template_reply がINSERT-only動作"
      - "magic行抽出が正しい"
  expected_behavior: |
    実装後、`python3 scripts/botsunichiroku.py crystallize project init shogun` で
    swarm.db crystals板に thread_id="project_shogun" の>>1-10レスが生成される。
    Viewer(後続cmd)からヘッダーカードとして表示可能。
    既存cmd_*スレ・目次MD・cmd_update(status=done)挙動は無変更。
  verification_method: |
    1. pytest tests/test_crystallize_template.py で全PASS
    2. 手動: `crystallize project init shogun --dry-run` 動作確認
    3. SQL: `SELECT thread_id, COUNT(*) FROM thread_replies WHERE thread_id LIKE 'project_%' GROUP BY thread_id` で>>1-10件数確認
    4. お針子監査でC1-C5 全PASS
```

---

## §15. 関連リンク

- 親cmd: cmd_571 (本cmd) / cmd_572(仮実装cmd・付録参照)
- 起源: cmd_517 結晶化機構v2(cmd_558実装・commit 244b2af)
- 直前cmd: cmd_570 結晶化機構v2 実在性調査(`docs/shogun/crystallize_v2_existence_audit_20260501.md`)
- 設計v1/v2参照: `docs/shogun/cmd_517_crystallization_design.md` / `cmd_517_crystallization_design_v2.md`
- 既存実装: `scripts/botsu/crystallize.py`(234行) / `scripts/botsu/cmd.py:118-122`
- 既存目次MD: `agent-swarm/crystals/{shogun,hardware,tooling}.md`
- agent-swarm: `server/dat_server.py:184-186` / `server/botsu/reply.py:7`
- 殿関連裁定:
  - 2026-04-28 結晶化v2採用(P2棄却・MD/Mermaid/文字数自由)
  - 2026-04-28 VPS Docker化長期方針
  - 2026-05-01 cmd_570→Q1-Q3裁定(P1+P3+P4採用・N回目廃止・>>1-10テンプレ化)
  - 2026-05-02 「2ch仕様縛り解放」明示
  - 2026-05-02 軍師の重箱突き歓迎・自発思考歓迎・論点密度上げ方針 → §11(OSI類比)/§12(権限管理)追補(subtask_1205)

---

*初版設計: 軍師(gunshi) | subtask_1204 / cmd_571 | 2026-05-02*
*補足追補: 軍師(gunshi) | subtask_1205 / cmd_571 | 2026-05-02 §11(OSI類比)+§12(権限管理 案D推奨)*
