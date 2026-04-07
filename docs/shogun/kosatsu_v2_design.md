# 高札v2 設計書: 連想記憶+リサーチエンジン

> **Version**: 1.0 | **subtask_882 / cmd_397** | 2026-03-12
> **設計方針**: 殿の壁打ち確定済み（cmd_397）を忠実に反映。マクガイバー精神。

---

## §1 概要・思想

### 背景: 人間の脳がやっていること

人間の脳は無意識下で以下を並列実行している:

| 脳の機能 | 内容 | 現行shogunでの対応 | ギャップ |
|----------|------|-------------------|---------|
| **メタ認知** | 記憶の危機を自覚し外部記憶に書き出す | Memory MCP, 没日録DB | LLMは自発的にメモを取れない |
| **レム睡眠** | 寝ている間に記憶を整理・統合する | なし | 知識の自動整理機構がない |
| **連想検索** | 無意識下で並列に関連記憶を検索し続ける | 高札v1 `/search` | 聞かれないと動かない（受動的） |
| **内外統合** | 内部記憶と外部記憶（ググる）を区別しない | 個別ツール（Web, X） | 統合されていない |

### 問題の核心

高札v1は「聞かれたら答える受動的な辞書」。人間の脳のように**頼まれなくても勝手に関連知識を引っ張ってくる能動的な記憶エンジン**になっていない。

### 高札v2のコンセプト

```
高札v1: 辞書（聞かれたら答える）
    ↓
高札v2: 連想記憶+リサーチエンジン（イベントが起きたら勝手に動く）
```

**設計哲学**: 殿が常々言う「実時間で延々と回せるチート」をイベント駆動で再現する。ポーリングではなく、cmdやsubtaskの登録という**明確なイベント**に反応して動く。

### v1→v2の関係

| 観点 | v1 | v2 |
|------|----|----|
| 起動契機 | 手動API呼び出し | **イベント駆動**（cmd add後に自動） |
| 検索範囲 | 没日録DB内部のみ | 内部（没日録）**+ 外部（Web/X）** |
| 出力 | 検索結果リスト | **構造化ブリーフィング**（related_knowledge） |
| 失敗知識 | 検索可能だが能動的でない | **pitfalls自動抽出**（audit失敗・rework履歴） |
| 外部リサーチ | なし | Web検索 + X検索（x-researchスキル） |

---

## §2 イベントトリガー設計

### トリガー一覧

| # | イベント | 発動タイミング | 目的 |
|---|---------|-------------|------|
| T1 | **cmd登録** | `botsunichiroku.py cmd add` 直後 | 類似事例+外部リサーチを自動添付 |
| T2 | **subtask開始** | subtask status → assigned/in_progress | 過去の落とし穴・失敗パターンを添付 |
| T3 | **audit完了** | audit結果がPOSTされた時 | 失敗パターンを知識DBに蓄積 |
| T4 | **PJ登録** | 新プロジェクト追加時 | 関連技術の最新動向をリサーチ |

### 実装方式: CLIフック

```
botsunichiroku.py cmd add "..."
    │
    ├── 1. DBに書き込み（既存処理）
    │
    └── 2. curl -s -X POST http://localhost:8080/enrich \     ← 追加
           -d '{"cmd_id":"cmd_397","text":"..."}'  &          ← 非同期（&でバックグラウンド）
```

**方式の選定理由**:
- botsunichiroku.py 末尾に `curl &` を1行追加するだけ。最小変更
- `&` でバックグラウンド実行 → cmd addの応答速度に影響なし
- 高札コンテナ側で非同期処理するため、CLIは即座に返る

### 各トリガーの実装箇所

| トリガー | 実装箇所 | 変更量 |
|---------|---------|--------|
| T1 cmd登録 | `botsunichiroku.py` cmd add サブコマンド末尾 | +3行 |
| T2 subtask開始 | `botsunichiroku.py` subtask update サブコマンド末尾 | +5行（status判定付き） |
| T3 audit完了 | 高札v1 `POST /audit` エンドポイント内部 | +5行 |
| T4 PJ登録 | 手動（頻度が低いため自動化不要） | 0行 |

---

## §3 内部検索（連想記憶）設計

### 既存資産の活用

高札v1にはすでに以下が存在する:

- **FTS5インデックス** (`search_index.db`): MeCab形態素解析済み。commands/subtasks/reports/dashboard全データ
- **`/search`**: FTS5 MATCHクエリ
- **`/search/similar`**: subtask_idから類似タスクを自動検索
- **`build_index.py`**: コンテナ起動時にインデックス再構築（冪等）

→ **v2では新規FTS5テーブルは作らない。既存インデックスをそのまま活用する。**

### /enrich の内部検索フロー

```
入力: cmd summary + details テキスト
    │
    ▼ Step 1: MeCab名詞抽出（extract_nouns）
    │   「uecs-llm 複数農家対応 WireGuard 設計書」
    │   → ["uecs", "llm", "農家", "WireGuard", "設計書"]
    │
    ▼ Step 2: FTS5 OR検索（既存search_index）
    │   MATCH '"農家" OR "WireGuard" OR "設計書"'
    │   → 類似cmd/subtask/report一覧（rank順）
    │
    ▼ Step 3: pitfalls抽出（専用クエリ）
    │   status IN ('blocked','rework') OR audit_status = 'done' でフィルタ
    │   → 過去の失敗・差し戻し事例を抽出
    │
    ▼ Step 4: 構造化出力
        → related_knowledge YAML
```

### pitfalls抽出クエリ（新規）

```sql
-- 失敗・差し戻しパターンの抽出
SELECT s.id, s.parent_cmd, s.description, s.status,
       r.summary AS report_summary
FROM subtasks s
LEFT JOIN reports r ON r.task_id = s.id
WHERE s.status IN ('blocked', 'cancelled')
   OR s.audit_status IS NOT NULL
   AND s.description LIKE '%' || ? || '%'
ORDER BY s.completed_at DESC
LIMIT 5;
```

加えて、FTS5でpitfallsも検索する:

```sql
-- FTS5で失敗パターン検索
SELECT source_id, snippet, rank
FROM search_index
WHERE search_index MATCH ?
  AND status IN ('blocked', 'rework', 'error')
ORDER BY rank
LIMIT 5;
```

### インデックス更新タイミング

現行: コンテナ起動時のみ（`build_index.py`）
→ v2追加: **T3 audit完了時にインクリメンタル更新**

```python
# 新規レコードのみ追加（全再構築ではない）
INSERT INTO search_index (source_type, source_id, ..., content)
VALUES ('report', ?, ..., ?);
```

ただし、FTS5のインクリメンタル更新は`search_index.db`がコンテナ内にあるため、コンテナ再起動なしで可能。build_index.pyの全再構築は日次cronまたは手動で実行する運用でも十分（没日録の更新頻度は1日数十件レベル）。

---

## §4 外部検索（リサーチエンジン）設計

### 検索ソース

| ソース | ツール | 費用 | 制約 |
|--------|--------|------|------|
| **Web検索** | WebSearch（Claude Code内蔵） | 無料（Claude API内） | Agentツール経由 |
| **X検索** | x-research スキル（bun run x-search.ts） | X API従量課金（既存契約） | 直近7日間のみ |

### 外部検索の発動条件

**全cmdで外部検索を回すのは過剰。** 以下の条件で発動を制御する:

| 条件 | 判定方法 | 例 |
|------|---------|-----|
| **新技術キーワード** | 内部検索のヒット数が少ない（≤2件） | 初めて扱うライブラリ名 |
| **明示的リサーチ指示** | cmd detailsに「リサーチ」「調査」を含む | cmd_397のようなタスク |
| **新PJ登録** | T4トリガー | 新規プロジェクト |

→ Phase 0では外部検索を**手動トリガーのみ**とし、Phase 1で条件自動判定を追加。

### X検索の統合

```bash
# /enrich内部から呼び出す
cd ~/.claude/skills/x-research
source ~/.config/env/global.env
bun run x-search.ts search "$KEYWORDS" --quick --json 2>/dev/null
```

`--quick`オプション: 1ページ・10件・1時間キャッシュ・コスト最小。

### リサーチ結果の蓄積

外部検索結果は**没日録のdashboard_entriesテーブルに蓄積**する:

```python
# 蓄積フォーマット
dashboard_entry = {
    "cmd_id": "cmd_397",
    "section": "research",        # 新セクション名
    "content": "WireGuard multi-site: NATホールパンチング問題...",
    "status": "auto_enriched",
    "tags": "web,wireguard,multi-tenant"
}
```

→ 次回の内部検索でFTS5インデックスに載り、蓄積知識として再利用される。
→ 人間で言う「ググった結果を覚えておく」に相当。

---

## §5 統合出力フォーマット

### related_knowledge YAML

/enrich APIのレスポンスを以下の形式で返す:

```yaml
related_knowledge:
  cmd_id: cmd_397
  enriched_at: "2026-03-12T00:30:00"

  internal:                           # 内部検索結果（没日録DB）
    - source_type: command
      source_id: cmd_303
      relevance: "channel_map外部設定化。農家ごとの設定分離の先例"
      score: -8.5                     # FTS5 rank（負値、小さいほど関連度高）
    - source_type: subtask
      source_id: subtask_529
      relevance: "LFM2.5モデル移行設計書。設計書作成パターンの先例"
      score: -7.2

  external:                           # 外部検索結果（Web/X）
    - source: web
      title: "Multi-tenant IoT Architecture Best Practices"
      summary: "テナント分離にはネットワーク層+アプリ層の二重分離が推奨..."
      url: "https://..."
    - source: x
      author: "@dev_example"
      text: "WireGuard multi-site: persistent keepaliveは25s推奨..."
      likes: 42

  pitfalls:                           # 過去の失敗パターン
    - source_id: subtask_852
      pattern: "別リポにcommitした事故。git remote -v確認必須"
      severity: high
    - source_id: "cmd_284-300"
      pattern: "ハルシネーション事例。実在確認を怠った"
      severity: critical
    - source_id: subtask_805
      pattern: "ashigaru6コミット漏れ。inbox descriptionに明記が必要"
      severity: medium

  meta:
    internal_hits: 12                 # 内部検索ヒット数
    external_searched: true           # 外部検索実行したか
    processing_time_ms: 850           # 処理時間
```

### 出力の利用者

| 利用者 | 利用方法 |
|--------|---------|
| **家老** | cmd登録後にrelated_knowledgeを参照し、subtask分解の参考にする |
| **足軽** | subtask inboxのcontextとしてpitfallsが添付される |
| **軍師** | 分析タスクのコンテキストとしてinternal/externalを参照 |
| **お針子** | 監査時にpitfallsの再発チェック |

---

## §6 高札APIの拡張設計

### 新規エンドポイント

| # | Method | Path | 説明 |
|---|--------|------|------|
| 1 | **POST** | `/enrich` | メイン。テキストを受け取り、related_knowledgeを返す |
| 2 | **GET** | `/enrich/{cmd_id}` | キャッシュ済みの結果を取得 |
| 3 | **POST** | `/enrich/external` | 外部検索のみを手動トリガー |

### POST /enrich

```python
class EnrichRequest(BaseModel):
    cmd_id: str                    # 対象cmd ID
    text: str                      # summary + details テキスト
    include_external: bool = False  # 外部検索を含めるか（Phase 0ではデフォルトFalse）

class EnrichResponse(BaseModel):
    cmd_id: str
    enriched_at: str
    internal: list[dict]
    external: list[dict]
    pitfalls: list[dict]
    meta: dict
```

### 処理フロー

```
POST /enrich
    │
    ▼ 1. MeCab名詞抽出
    │
    ▼ 2. FTS5内部検索（同期、<100ms）
    │
    ▼ 3. pitfalls抽出（同期、<50ms）
    │
    ├── include_external=False → 4a. 即座にレスポンス返却
    │
    └── include_external=True  → 4b. 外部検索（subprocess、タイムアウト30s）
                                      → レスポンス返却
```

### 非同期設計の判断

**案A: 完全非同期（job_id方式）**
- POST → 即座にjob_id返却 → GET /enrich/{job_id} でポーリング
- 問題: ポーリング禁止に抵触

**案B: 同期+タイムアウト**（★推奨）
- 内部検索は同期（<100ms）。外部検索はsubprocess+30sタイムアウト
- タイムアウト時は内部結果のみ返却、外部結果は空
- シンプル。マクガイバー精神に合致

**案C: Fire-and-forget + キャッシュ**（冒険案）
- POST → 内部結果を即座に返却
- 外部検索はバックグラウンドで実行し、結果をdashboard_entriesに蓄積
- 次回のGET /enrich/{cmd_id} で外部結果込みを取得
- 利点: 呼び出し側を一切ブロックしない
- 欠点: 初回は外部結果が空

→ **Phase 0は案B（同期+タイムアウト）で開始。** 外部検索の需要が見えたらPhase 1で案Cに移行。

### キャッシュ設計

```python
# dashboard_entriesテーブルを流用
# section="enrich_cache", content=JSON(related_knowledge)
# cmd_id でキャッシュキー

# キャッシュヒット: GET /enrich/{cmd_id} でdashboard_entriesから取得
# キャッシュミス: POST /enrich で生成→dashboard_entriesに保存→返却
```

dashboard_entriesテーブル流用の理由:
- 新テーブル追加不要
- FTS5インデックスにも自動で載る（build_index.pyがdashboard_entriesを読む）
- 既存のGET /dashboard APIでも参照可能

---

## §7 家老・足軽ワークフローへの統合

### 家老のワークフロー変更

```
【Before】
家老: cmd add → subtask分解 → 足軽に配布

【After】
家老: cmd add → (自動)/enrich呼び出し → related_knowledge確認
      → subtask分解時にpitfallsを参考 → 足軽に配布（pitfalls添付）
```

### 具体的な統合ポイント

#### 1. botsunichiroku.py cmd add 末尾

```python
# cmd add 完了後に自動enrich
import subprocess
subprocess.Popen(
    ["curl", "-s", "-X", "POST", "http://localhost:8080/enrich",
     "-H", "Content-Type: application/json",
     "-d", json.dumps({"cmd_id": cmd_id, "text": f"{command} {details}"})],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

#### 2. 家老のsubtask配布テンプレート

```yaml
# 足軽inbox YAML（拡張）
- subtask_id: subtask_XXX
  description: |
    ...
  pitfalls:                          # /enrichから自動添付
    - "subtask_852: git remote -v確認必須"
    - "ashigaru6コミット漏れ注意"
  related_cmds:                      # /enrichから自動添付
    - cmd_303: "channel_map外部設定化の先例"
```

#### 3. 軍師の分析タスクへの統合

軍師のタスクYAMLに `context_files` として `/enrich/{cmd_id}` を含めることで、分析開始前にrelated_knowledgeを参照できる。

### 段階的な浸透

Phase 0では家老が手動でrelated_knowledgeを確認し、有用と判断したらinboxに添付する。
Phase 1で家老のkaro-workflow.mdに自動参照を標準フローとして記載。

---

## §8 段階的導入計画

### Phase 0: 内部検索のみ（最小動作）

**目標**: FTS5連想検索が `/enrich` で自動動作する

| # | タスク | 変更対象 | 工数目安 |
|---|--------|---------|---------|
| 0-1 | `/enrich` エンドポイント追加 | `tools/kousatsu/main.py` | +80行 |
| 0-2 | pitfalls抽出クエリ追加 | `tools/kousatsu/main.py` | +30行 |
| 0-3 | キャッシュ（dashboard_entries流用） | `tools/kousatsu/main.py` | +20行 |
| 0-4 | `GET /enrich/{cmd_id}` 追加 | `tools/kousatsu/main.py` | +15行 |
| 0-5 | `botsunichiroku.py` cmd add フック | `scripts/botsunichiroku.py` | +5行 |
| 0-6 | Dockerコンテナ再ビルド | `tools/kousatsu/` | コマンド1つ |
| 0-7 | テスト（test_search.pyに追加） | `tools/kousatsu/test_search.py` | +50行 |

**完了基準**: `cmd add` すると自動的に `/enrich` が呼ばれ、`GET /enrich/{cmd_id}` で結果を取得できる

### Phase 1: 外部検索統合

**目標**: Web+X検索結果がrelated_knowledgeに含まれる

| # | タスク | 変更対象 |
|---|--------|---------|
| 1-1 | x-researchスキルのCLI呼び出し統合 | `tools/kousatsu/main.py` |
| 1-2 | Web検索統合（subprocess→curl） | `tools/kousatsu/main.py` |
| 1-3 | 外部検索結果のdashboard_entries蓄積 | `tools/kousatsu/main.py` |
| 1-4 | `include_external=True` の自動判定ロジック | `tools/kousatsu/main.py` |
| 1-5 | subtask assignedトリガー（T2） | `scripts/botsunichiroku.py` |

**完了基準**: 内部検索ヒット≤2件のcmdで自動的にWeb/X検索が実行される

### Phase 2: 知識蓄積サイクル

**目標**: リサーチ結果が蓄積され、次回の連想検索で再利用される

| # | タスク | 変更対象 |
|---|--------|---------|
| 2-1 | audit完了時のインクリメンタルインデックス更新（T3） | `tools/kousatsu/main.py` |
| 2-2 | 失敗パターンの自動分類・タグ付け | `tools/kousatsu/main.py` |
| 2-3 | build_index.py の差分更新モード追加 | `tools/kousatsu/build_index.py` |

**完了基準**: audit失敗→蓄積→次のcmdでpitfallsに自動出現

### Phase 3: 夢見機能（冒険案・殿の判断事項）

```
「レム睡眠的整理」をcronで再現。日次で没日録全体をFTS5クロス相関し、
非自明な関連（異なるPJ間の類似パターン）を発見する。

例: 温室制御の三層構造(爆発/ガムテ/知恵) ↔ shogunの三層構造(緊急停止/ルール/LLM)
    → 「構造的類似性あり。設計パターンの共有可能」

cron 0 3 * * * docker exec kousatsu python3 /app/dream.py
→ 結果をdashboard_entries section="dream" に蓄積
```

**注意**: これはポーリングではなくcron（タイマーイベント）。ただし、必要性が見えるまで実装しない。殿の判断を仰ぐ。

---

## §9 既存高札v1との互換性

### 変更なしのエンドポイント（14本全て）

| エンドポイント | 影響 |
|-------------|------|
| GET /search | **変更なし** |
| GET /search/similar | **変更なし** |
| GET /check/orphans | **変更なし** |
| GET /check/coverage | **変更なし** |
| GET /audit/history | **変更なし** |
| GET /worker/stats | **変更なし** |
| GET /health | **変更なし**（v2情報を追加してもよい） |
| POST /reports | **変更なし** |
| POST /audit | T3トリガー追加（既存動作に影響なし） |
| GET /reports/{id} | **変更なし** |
| GET /audit/{id} | **変更なし** |
| POST /dashboard | **変更なし** |
| GET /dashboard | **変更なし** |
| GET /docs/{cat}/{file} | **変更なし** |

### 追加のみ（3本）

| エンドポイント | 新規 |
|-------------|------|
| POST /enrich | **新規追加** |
| GET /enrich/{cmd_id} | **新規追加** |
| POST /enrich/external | **新規追加** |

### データ互換性

- FTS5スキーマ（search_index）: **変更なし**
- 没日録DBスキーマ: **変更なし**
- dashboard_entriesテーブル: section="enrich_cache" / section="research" を追加利用するが、既存セクションに影響なし
- Docker volume mount: **変更なし**

### 後方互換性の保証

v2機能を一切使わなくても、v1として完全に動作する。`/enrich` を呼ばなければv1と同一動作。

---

## 付録A: 脳科学アナロジー対応表

| 脳の機能 | 高札v2の対応 | 実装 |
|----------|-------------|------|
| 海馬（短期記憶→長期記憶） | cmd add → FTS5インデックス | build_index.py |
| 大脳皮質（連想検索） | 名詞抽出 → FTS5 MATCH | /enrich 内部検索 |
| 前頭前皮質（メタ認知） | pitfalls自動抽出 | 失敗パターンクエリ |
| レム睡眠（記憶統合） | 夢見機能（Phase 3） | dream.py（cron） |
| 外部記憶（ググる） | Web/X検索 | /enrich 外部検索 |
| 扁桃体（感情記憶=痛い記憶） | severity: critical の pitfalls | audit失敗・ハルシネーション履歴 |

## 付録B: 全体アーキテクチャ図

```
┌─────────────────────────────────────────────────────────┐
│                    家老ワークフロー                        │
│                                                          │
│  cmd add ─→ botsunichiroku.py ─→ 没日録DB               │
│      │                              │                    │
│      └─→ curl POST /enrich ─────────┼─→ 高札v2コンテナ   │
│                                     │   ┌──────────────┐ │
│                                     │   │ MeCab名詞抽出 │ │
│                                     │   │      ↓       │ │
│  ┌───────────────────┐              │   │ FTS5内部検索  │ │
│  │ search_index.db   │←─build_index─┘   │      ↓       │ │
│  │ (FTS5)            │←─────────────────│ pitfalls抽出  │ │
│  └───────────────────┘              ┌───│      ↓       │ │
│                                     │   │ 外部検索(opt) │ │
│  ┌───────────────────┐              │   │      ↓       │ │
│  │ x-research        │←─subprocess──┘   │ related_     │ │
│  │ (bun + X API)     │                  │ knowledge    │ │
│  └───────────────────┘                  └──────────────┘ │
│                                                          │
│  家老: GET /enrich/{cmd_id} → subtask分解の参考に         │
│  足軽: inbox.yaml に pitfalls 添付                        │
│  軍師: context_files に /enrich 参照                      │
└─────────────────────────────────────────────────────────┘
```

## 付録C: 殿の判断事項

| # | 判断事項 | 選択肢 | 軍師の推奨 |
|---|---------|--------|-----------|
| 1 | Phase 3「夢見機能」の実装可否 | 実装する / 棚上げ | 棚上げ（Phase 0-2の成果を見てから判断） |
| 2 | 外部検索のコスト上限 | X API月額予算 | 既存契約範囲内（--quick固定で1検索≈$0.01以下） |
| 3 | /enrichの自動実行範囲 | 全cmd / priority:high以上のみ | 全cmd（内部検索のみならコストゼロ） |
| 4 | pitfalls添付先 | inbox YAML / 高札参照リンクのみ | inbox YAMLに直接埋め込み（足軽が参照しやすい） |
