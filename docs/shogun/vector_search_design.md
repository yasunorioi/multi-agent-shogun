# ベクトル検索（sqlite-vec + Ruri v3）導入設計

> **軍師分析** | 2026-03-24 | North Star: 意味検索で没日録の知見を掘り起こせ。FTS5を壊すな、拡張せよ

---

## 結論（先に述べる）

**導入を推奨する。既存FTS5の横にsqlite-vecベクトルインデックスを追加し、RRFで統合するハイブリッド検索を実装する。**

| 項目 | 判定 | 理由 |
|------|:----:|------|
| sqlite-vec導入 | **やる** | SQLite拡張。DBファイル1本の原則を維持 |
| Ruri v3-310m | **Phase 0で採用** | 日本語特化、CPU動作可、ローカル推論（月額ゼロ） |
| RRF（FTS5+Vec統合） | **やる** | sui-memoryで実績。スコア正規化不要の簡潔な手法 |
| 時間減衰 | **Phase 2で導入** | 没日録はCmd寿命が長いため、最適半減期の検証が必要 |
| agent-swarm展開 | **Phase 1で対応** | 共通モジュール化→両DB対応 |
| 没日録DBスキーマ変更 | **最小限** | vec_index仮想テーブル追加のみ。既存テーブル不変 |

---

## 0. sui-memoryから学ぶ設計思想

### 0.1 sui-memoryの核心的洞察

> **「知性を保存時ではなく検索時に置け」**
> — LLM要約で情報を潰すな。生データを保存し、検索を賢くしろ

| sui-memory | 没日録への適用 |
|-----------|--------------|
| Q&A形式チャンク分割（ルールベース） | source_type別チャンク（cmd/subtask/report/reply） |
| FTS5 trigram + sqlite-vec | FTS5 unicode61(+MeCab) + sqlite-vec |
| RRF fusion (k=60) | 同じ手法を採用 |
| 時間減衰（半減期30日） | source_type別に半減期を調整 |
| 1ファイルSQLite | 没日録DB 1ファイルを維持 |
| 外部依存2つ (sentence-transformers, sqlite-vec) | 同じ2つ |

### 0.2 没日録との違い

| 観点 | sui-memory | 没日録 |
|------|-----------|--------|
| データ構造 | 非構造化（会話ログ） | 構造化（cmd/subtask/report + FTS5済み） |
| データ量 | 7,059チャンク | ~2,500エントリ（FTS5 2,345 + reply 168） |
| チャンク戦略 | Q&A分割（LLMなし） | **既にチャンク済み**（source_type/source_id単位） |
| 検索頻度 | セッション開始時 | エージェントの検索コマンド（5-20回/日） |
| 実行環境 | ローカルPC | **ローカル（没日録）+ VPS（agent-swarm）** |

**没日録の優位性**: FTS5が既に稼働中（2,345エントリ、MeCab分かち書き済み）。チャンク分割も不要。sqlite-vecを追加するだけでハイブリッド検索が実現する。

---

## 1. アーキテクチャ設計（最重要）

### 1.1 没日録DB vs agent-swarm DB

| DB | データ量 | FTS5 | 実行環境 | ベクトル検索 |
|----|---------|:----:|---------|:----------:|
| 没日録DB (16.9MB) | cmd 390 / subtask 777 / report 915 / reply 168 / diary 3 | **済** (2,345行) | ローカル (MBP 48GB / デスクトップ) | **Phase 0** |
| agent-swarm (swarm.db) | reply 7 (新規) | **なし** | VPS (457MB RAM) or ローカル | **Phase 1** |

**判断**: 両方に入れる。ただし優先度は没日録が先（データ量・即効性）。共通モジュールを設計し、両DBで再利用。

### 1.2 テーブル設計

```sql
-- 没日録DBに追加する仮想テーブル（既存テーブル不変）
CREATE VIRTUAL TABLE IF NOT EXISTS vec_index USING vec0(
    source_id TEXT PRIMARY KEY,    -- search_indexのsource_idと同一
    embedding float[1024]          -- Ruri v3-310m: 1024次元
);

-- メタデータテーブル（ベクトル化管理用）
CREATE TABLE IF NOT EXISTS vec_meta (
    source_id   TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,      -- command, subtask, report, reply, diary
    parent_id   TEXT,               -- cmd_id等（フィルタ用）
    project     TEXT,
    created_at  TEXT,               -- 時間減衰計算用
    model_name  TEXT DEFAULT 'cl-nagoya/ruri-v3-310m',
    vectorized_at TEXT              -- ベクトル化日時
);
```

**なぜvec_metaが必要か:**
- sqlite-vecのvec0はベクトルとPKのみ保持。メタデータを格納できない
- 時間減衰計算にcreated_atが必要
- source_typeフィルタ（「reportだけ検索」等）に必要
- 既存search_indexのフィールドと重複するが、JOIN 1回で取得可能

### 1.3 既存FTS5との共存

```
┌─────────────────────────────────────────────────┐
│                 ハイブリッド検索                    │
│                                                   │
│  ┌──────────────┐    ┌──────────────┐            │
│  │ FTS5検索      │    │ ベクトル検索   │            │
│  │ search_index  │    │ vec_index     │            │
│  │ BM25スコア    │    │ コサイン類似度  │            │
│  └──────┬───────┘    └──────┬───────┘            │
│         │                   │                     │
│         └───────┬───────────┘                     │
│                 ▼                                  │
│         RRF Fusion (k=60)                         │
│                 │                                  │
│                 ▼                                  │
│         時間減衰 × RRFスコア                        │
│                 │                                  │
│                 ▼                                  │
│         Top-N結果を返却                            │
└─────────────────────────────────────────────────┘
```

**FTS5は一切変更しない。** vec_indexを横に追加し、検索時にRRFで統合するだけ。FTS5単独検索も引き続き動作する。

### 1.4 RRF実装

```python
def hybrid_search(query: str, top_n: int = 20, k: int = 60,
                  source_type: str | None = None,
                  project: str | None = None) -> list[dict]:
    """FTS5 + ベクトル検索をRRFで統合"""
    conn = get_connection()

    # 1. FTS5検索（BM25スコア順）
    fts_sql = "SELECT source_id, rank FROM search_index WHERE content MATCH ?"
    if source_type:
        fts_sql += f" AND source_type = '{source_type}'"
    fts_results = conn.execute(fts_sql, (fts5_tokenize(query),)).fetchall()

    # 2. ベクトル検索（コサイン類似度順）
    query_vec = embed_text(query)  # Ruri v3でベクトル化
    vec_results = conn.execute(
        "SELECT source_id, distance FROM vec_index"
        " WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (query_vec, top_n * 3),
    ).fetchall()

    # 3. RRF統合
    scores: dict[str, float] = {}
    for rank, row in enumerate(fts_results[:top_n * 3]):
        sid = row["source_id"]
        scores[sid] = scores.get(sid, 0) + 1 / (k + rank + 1)
    for rank, row in enumerate(vec_results):
        sid = row["source_id"]
        scores[sid] = scores.get(sid, 0) + 1 / (k + rank + 1)

    # 4. 時間減衰（Phase 2で有効化）
    # for sid in scores:
    #     age_days = get_age_days(conn, sid)
    #     decay = 0.5 ** (age_days / half_life)
    #     scores[sid] *= decay

    # 5. source_typeフィルタ（指定時）
    if source_type or project:
        meta = {r["source_id"]: r for r in conn.execute(
            "SELECT * FROM vec_meta WHERE source_id IN ({})".format(
                ",".join("?" * len(scores))), list(scores.keys())).fetchall()}
        if source_type:
            scores = {s: v for s, v in scores.items()
                      if meta.get(s, {}).get("source_type") == source_type}
        if project:
            scores = {s: v for s, v in scores.items()
                      if meta.get(s, {}).get("project") == project}

    # 6. Top-Nソート＆返却
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_n]
    results = []
    for sid, score in ranked:
        content = conn.execute(
            "SELECT * FROM search_index WHERE source_id = ?", (sid,)
        ).fetchone()
        if content:
            results.append({**dict(content), "hybrid_score": score})

    conn.close()
    return results
```

### 1.5 チャンク戦略

**没日録は既にチャンク済み。** search_indexの各行が1チャンク:

| source_type | チャンク単位 | 平均文字数 | 件数 |
|-------------|------------|:---------:|:----:|
| command | cmd title + details | ~500 | 390 |
| subtask | description | ~400 | 777 |
| report | summary + findings | ~600 | 915 |
| reply | body | ~200 | 168 |
| diary | summary + body | ~300 | 3 |
| **合計** | | **avg 513** | **~2,345** |

**追加チャンク**: thread_replies（168件）はsearch_indexに未登録のものがある。Phase 0でthread_repliesもベクトル化対象に含める。

---

## 2. モデル選定

### 2.1 候補比較表

| モデル | パラメータ | 次元 | モデルサイズ | メモリ使用 | 日本語性能 | CPU推論/件 |
|--------|:---------:|:----:|:----------:|:---------:|:---------:|:---------:|
| **cl-nagoya/ruri-v3-310m** | 310M | 1024 | ~1.2GB | ~1.5GB | **◎ 最高** | ~200ms |
| intfloat/multilingual-e5-small | 118M | 384 | ~470MB | ~600MB | ○ 良好 | ~80ms |
| intfloat/multilingual-e5-base | 278M | 768 | ~1.1GB | ~1.3GB | ○ 良好 | ~150ms |
| cl-nagoya/ruri-v3-30m | 30M | 256 | ~120MB | ~200MB | △ 中程度 | ~30ms |

### 2.2 推奨: Ruri v3-310m（没日録） + ruri-v3-30m（VPSフォールバック）

**没日録（ローカル実行）**: Ruri v3-310m
- MBP 48GB / デスクトップ: メモリ十分。1.5GB負荷は問題なし
- 日本語特化で没日録の内容（戦国口調含む）に最適
- 殿が「バージョンアップしてでも入れたい」と明言。最高品質を選択

**agent-swarm（VPS実行）**: 要注意
- VPSメモリ: メモリ記録では457MB RAM（さくら512MBプラン相当）
- タスク記載では「4コア/4GB」— **VPSアップグレード予定か確認が必要**
  - 457MB: Ruri v3-310m（1.5GB）は不可能。ruri-v3-30m（200MB）がギリギリ
  - 4GB: Ruri v3-310m は起動可能だが他サービスとの共存が厳しい
- **推奨**: agent-swarm側は Phase 1 で対応。VPSスペック確定後にモデル選定

### 2.3 ベクトル次元数とsqlite-vecの制約

- sqlite-vec: float32ベクトル、次元数制限なし（実用上~4096程度）
- Ruri v3-310m: 1024次元 → sqlite-vecで問題なし
- 1024次元 × float32 × 2,500件 = **約10MB** のインデックスサイズ
- ブルートフォースで~1ms以下（ANN不要。この規模ではHNSW等のオーバーヘッドが逆に遅い）

---

## 3. 実装設計

### 3.1 sqlite-vecのセットアップ

```bash
# インストール
pip install sqlite-vec sentence-transformers

# Python内でのロード
import sqlite_vec
conn = sqlite3.connect("data/botsunichiroku.db")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
```

**注意**: SQLiteのload_extension はデフォルト無効。`enable_load_extension(True)` が必要。没日録CLIの `get_connection()` に追加するか、ベクトル検索時のみ有効化する。

### 3.2 ベクトル化のタイミング

| タイミング | 用途 | 方式 |
|-----------|------|------|
| **バッチ（初回移行）** | 既存2,345件のベクトル化 | `migrate_vec.py` スクリプト |
| **インクリメンタル（書き込み時）** | 新規cmd/subtask/report追加時 | `fts5_upsert` と同時に `vec_upsert` |
| **検索時** | クエリのベクトル化 | `hybrid_search` 内で `embed_text(query)` |

**バッチ移行の見積もり:**
```
2,345件 × 200ms/件 = 469秒 ≈ 8分
（バッチ最適化で2-3分に短縮可能）
```

### 3.3 インクリメンタル更新の設計

```python
# botsu/__init__.py に追加
def vec_upsert(
    conn: sqlite3.Connection,
    source_id: str,
    source_type: str,
    parent_id: str,
    project: str,
    created_at: str,
    raw_text: str,
) -> None:
    """vec_indexにベクトルをupsert。vec_indexが存在しない場合は何もしない。"""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_meta'"
    ).fetchone()
    if not exists:
        return

    embedding = _get_embedding(raw_text)  # Ruri v3
    if embedding is None:
        return

    # vec_index upsert（DELETE+INSERT）
    conn.execute("DELETE FROM vec_index WHERE source_id = ?", (source_id,))
    conn.execute(
        "INSERT INTO vec_index (source_id, embedding) VALUES (?, ?)",
        (source_id, embedding),
    )

    # vec_meta upsert
    conn.execute(
        "INSERT OR REPLACE INTO vec_meta"
        " (source_id, source_type, parent_id, project, created_at, vectorized_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (source_id, source_type, parent_id, project, created_at, now_iso()),
    )


# 遅延ロード（初回呼び出し時にモデルをロード）
_embed_model = None

def _get_embedding(text: str) -> bytes | None:
    """テキストをRuri v3でベクトル化。モデルは遅延ロード。"""
    global _embed_model
    try:
        if _embed_model is None:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("cl-nagoya/ruri-v3-310m")
        vec = _embed_model.encode(text, normalize_embeddings=True)
        import struct
        return struct.pack(f"{len(vec)}f", *vec)
    except Exception:
        return None
```

**遅延ロードの理由:**
- モデルロード: ~10秒（初回のみ）
- 通常のCLI操作（cmd list, subtask update等）でモデルロードを避ける
- ベクトル検索 or 書き込み時にのみロード

### 3.4 既存CLIへの統合

```bash
# 現行（FTS5のみ）
python3 scripts/botsunichiroku.py search "委託業務"
# → FTS5 BM25でキーワード一致検索

# 新（ハイブリッド）
python3 scripts/botsunichiroku.py search "委託業務" --hybrid
# → FTS5 + ベクトル検索のRRF統合結果

python3 scripts/botsunichiroku.py search "農家が困っていること" --hybrid
# → キーワードに一致しなくても意味的に近い結果を返す
#   例: "委託業務モデル設計", "地主と作業者の分離", "出荷管理ロット"

# フィルタオプション
python3 scripts/botsunichiroku.py search "キーワード" --hybrid --type report --project shogun
```

**`--hybrid` フラグ**: デフォルトは従来のFTS5検索（後方互換）。`--hybrid`指定でハイブリッド検索。将来的にデフォルトを切り替え検討。

### 3.5 agent-swarm CLIへの統合

```python
# 共通モジュール: scripts/botsu/vec.py（新規作成）
# 没日録 + agent-swarm の両方から import 可能

class VecSearch:
    def __init__(self, db_path: str, model_name: str = "cl-nagoya/ruri-v3-310m"):
        self.db_path = db_path
        self.model_name = model_name

    def setup(self, conn):
        """vec_index + vec_meta テーブル作成"""
        ...

    def upsert(self, conn, source_id, text, **meta):
        """ベクトルupsert"""
        ...

    def search(self, conn, query, top_n=20, **filters):
        """ベクトル検索"""
        ...

    def hybrid_search(self, conn, query, fts_table="search_index", **kwargs):
        """FTS5 + Vec のRRF統合検索"""
        ...
```

---

## 4. コスト・パフォーマンス試算

### 4.1 データ量

| データ | 件数 | 平均文字数 | ベクトルサイズ |
|--------|:----:|:---------:|:------------:|
| 没日録FTS5 | 2,345 | 513 | 2,345 × 4KB = **9.4MB** |
| thread_replies | 168 | ~200 | 168 × 4KB = **0.7MB** |
| **合計** | **~2,500** | | **~10MB** |

### 4.2 Ruri v3 CPU推論性能

| 環境 | 1件あたり | バッチ(32) | バッチ(128) |
|------|:---------:|:----------:|:-----------:|
| MBP M4 Pro (48GB) | ~100ms | ~50ms/件 | ~30ms/件 |
| デスクトップ (Intel/AMD) | ~200ms | ~100ms/件 | ~60ms/件 |
| VPS 457MB (ruri-v3-30m) | ~100ms | ~50ms/件 | ~30ms/件 |

**初回バッチ移行**: 2,500件 × 100ms/件(バッチ) = **~4分**（MBP）

### 4.3 検索レイテンシ

| 処理 | 時間 |
|------|:----:|
| クエリベクトル化（Ruri v3） | ~100-200ms |
| sqlite-vec検索（2,500件ブルートフォース） | ~1ms |
| FTS5検索 | ~5ms |
| RRF統合 + ソート | ~1ms |
| **合計** | **~110-210ms** |

sui-memoryの実測値（100ms）とほぼ同等。モデルが常駐していれば更に速い。

### 4.4 メモリ使用量

| コンポーネント | メモリ |
|-------------|:-----:|
| Ruri v3-310m モデル | ~1.5GB |
| sentence-transformers + PyTorch | ~500MB |
| sqlite-vec インデックス（10MB） | ~10MB |
| **合計（モデルロード時）** | **~2GB** |
| **合計（非ロード時）** | **~10MB** |

**遅延ロード戦略**: 検索コマンド実行時のみモデルをロード → 検索完了後にプロセス終了 → メモリ解放。常駐プロセスなし。

### 4.5 VPS共存可能性

| VPSスペック | Ruri v3-310m | ruri-v3-30m | e5-small |
|-----------|:------------:|:-----------:|:--------:|
| 457MB (現行) | **不可** | △ swap前提 | △ swap前提 |
| 4GB (アップグレード後) | △ 他サービス圧迫 | **◎** | **◎** |

**殿への確認事項**: VPSスペックの確認。4GBアップグレード予定であればRuri v3-310mも検討可。現行457MBであればruri-v3-30m（256次元、120MB）が現実的。

---

## 5. 移行・導入戦略

### 5.1 Phase分解

#### Phase 0: 没日録にsqlite-vec導入（最小構成）

| subtask | 内容 | 依存 |
|---------|------|------|
| pip install | sqlite-vec + sentence-transformers インストール | なし |
| テーブル作成 | vec_index + vec_meta のDDL | pip install |
| vec.py | 共通ベクトル検索モジュール新規作成 | テーブル作成 |
| migrate_vec.py | 既存FTS5データのバッチベクトル化 | vec.py |
| CLI統合 | `search --hybrid` オプション追加 | migrate_vec.py |

**Phase 0完了時:**
- `python3 scripts/botsunichiroku.py search "農家が困っていること" --hybrid` が動作
- 既存FTS5検索は `--hybrid` なしで従来通り動作
- モデルは遅延ロード（CLIプロセス終了でメモリ解放）

#### Phase 1: agent-swarmに展開 + インクリメンタル更新

| subtask | 内容 | 依存 |
|---------|------|------|
| vec.pyをagent-swarmにコピー | 共通モジュールの再利用 | Phase 0 |
| agent-swarm FTS5導入 | swarm.dbにFTS5テーブル追加 | なし |
| agent-swarm vec導入 | swarm.dbにvec_index追加 | FTS5導入 |
| インクリメンタル更新 | fts5_upsert + vec_upsert を連動 | Phase 0 |

#### Phase 2: 時間減衰 + RRF最適化

| subtask | 内容 | 依存 |
|---------|------|------|
| 時間減衰実装 | source_type別半減期の導入 | Phase 1 |
| RRFパラメータ調整 | k値、top_n、重み付けの最適化 | Phase 0 |
| 性能ベンチマーク | 検索精度・速度の定量評価 | Phase 0 |

### 5.2 時間減衰の設計案（Phase 2）

| source_type | 推奨半減期 | 理由 |
|-------------|:---------:|------|
| command | 90日 | 戦略的意思決定。長期間参照される |
| subtask | 30日 | 戦術的タスク。完了後の参照頻度は低下 |
| report | 45日 | 知見・教訓。中期間参照される |
| reply | 14日 | 会話ログ。鮮度重要 |
| diary | 60日 | 文脈記録。中長期参照 |

sui-memoryの30日一律より、source_type別に調整する方が没日録の特性に合う。ただしPhase 2まで後回し（Phase 0で最適値を実データで検証してから決定）。

### 5.3 既存FTS5検索が壊れないことの保証

1. **`--hybrid` フラグ制御**: デフォルトはFTS5のみ。ハイブリッドはオプトイン
2. **vec_indexが存在しない場合の安全処理**: `vec_upsert` / `hybrid_search` はテーブル不存在時にフォールバック
3. **sqlite-vec未インストール時**: `import sqlite_vec` 失敗時はFTS5のみで動作
4. **ロールバック**: `DROP TABLE vec_index; DROP TABLE vec_meta;` で完全除去。FTS5に影響なし

### 5.4 Wave分解案

| Wave | 内容 | subtask数 |
|------|------|:---------:|
| W1 | pip install + DDL + vec.py共通モジュール | 2 |
| W2 | migrate_vec.py(バッチベクトル化) + CLI統合 | 2 |
| W3 | インクリメンタル更新(fts5_upsert連動) | 1 |
| W4 | agent-swarm展開 | 2 |
| W5 | 時間減衰 + ベンチマーク | 2 |
| **合計** | | **9** |

---

## 6. 見落としの可能性

1. **sentence-transformersのサイズ**: PyTorch + transformersで~2GB のディスク使用。VPSの25GBディスクでは余裕だが、CI等では注意
2. **モデルダウンロード**: 初回に~1.2GBダウンロード。オフライン環境（VPN越し等）では事前準備が必要
3. **MeCabとの共存**: 現行FTS5はMeCab分かち書き済みテキストを保存。ベクトル化はraw textが望ましい（Ruri v3は自前トークナイザ）。FTS5用content（MeCab済み）とベクトル用text（raw）を分ける必要あり
4. **cooccurrenceテーブル（76,652行）のベクトル化**: 現時点では対象外だが、共起関係のベクトル化は将来的にHopfield連想（前回分析のcontext/hopfield_associative.md）との接点がある
5. **embedモデルのバージョン管理**: Ruri v3がアップデートされた場合、全ベクトルの再計算が必要。vec_metaのmodel_nameで追跡
6. **concurrent access**: 複数エージェントが同時にベクトル検索する場合のsqlite-vec拡張のスレッド安全性。WALモードで読み取りは並行可能だが、sqlite-vecの制約を要確認

---

## 7. North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    「意味検索で没日録の知見を掘り起こせ」に直結。
    現行FTS5はキーワード一致のみ。「農家が困っていること」では
    「委託業務モデル」や「地主と作業者の分離」がヒットしない。
    ベクトル検索の追加により意味的に近い知見を掘り起こせる。
    マクガイバー精神: SQLite + Python、外部依存2つのみ、月額ゼロ。
    sui-memoryの実績（7,059チャンク、100ms）が有効性を実証。
  risks_to_north_star:
    - "VPSメモリ不足（457MB）でagent-swarm側の展開が困難"
    - "遅延ロード時の初回10秒待ちがUXを損なう可能性"
    - "MeCab分かち書きとRuri v3トークナイザの不整合"
    - "モデルバージョン更新時の全ベクトル再計算コスト"
```

---

## 付録A: ハイブリッド検索の具体例

```
Query: "農家が困っていること"

--- FTS5のみ（キーワード一致） ---
結果: 0件（「農家」「困」が分かち書きで一致しない可能性）

--- ハイブリッド検索 ---
#1 [cmd_XXX] rotation-planner「委託業務モデル」拡張設計
   hybrid_score: 0.031 (FTS: rank=∞, Vec: rank=2)
   → 意味的に「農家の困りごと」に関連

#2 [subtask_XXX] fields.owner_id（地主）と fields.user_id（作業者）の分離
   hybrid_score: 0.028 (FTS: rank=∞, Vec: rank=5)
   → 「地主≠作業者」問題は農家の困りごとの一つ

#3 [report_XXX] 出荷管理ロット管理システム設計中に委託概念欠落を発見
   hybrid_score: 0.025 (FTS: rank=∞, Vec: rank=8)

#4 [cmd_XXX] ハードウェア方針決定：Pico 2 Wで進める
   hybrid_score: 0.022 (FTS: rank=15, Vec: rank=12)
   → FTS5でもVecでも中程度の一致
```

## 付録B: migrate_vec.py の概要

```python
#!/usr/bin/env python3
"""migrate_vec.py — 既存FTS5データのバッチベクトル化（1回実行）"""

import sqlite3
import sqlite_vec
from sentence_transformers import SentenceTransformer

DB_PATH = "data/botsunichiroku.db"
MODEL = "cl-nagoya/ruri-v3-310m"
BATCH_SIZE = 32

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)

    # テーブル作成
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS vec_index
                    USING vec0(source_id TEXT PRIMARY KEY, embedding float[1024])""")
    conn.execute("""CREATE TABLE IF NOT EXISTS vec_meta (
                    source_id TEXT PRIMARY KEY, source_type TEXT,
                    parent_id TEXT, project TEXT, created_at TEXT,
                    model_name TEXT DEFAULT 'cl-nagoya/ruri-v3-310m',
                    vectorized_at TEXT)""")

    # モデルロード
    model = SentenceTransformer(MODEL)

    # FTS5データ取得（content列はMeCab済みなので、元テーブルからrawテキストを取得）
    rows = conn.execute(
        "SELECT source_type, source_id, parent_id, project, content"
        " FROM search_index"
    ).fetchall()

    # バッチベクトル化
    texts = [r[4] for r in rows]  # content
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_rows = rows[i:i+BATCH_SIZE]
        embeddings = model.encode(batch_texts, normalize_embeddings=True)

        for row, emb in zip(batch_rows, embeddings):
            source_id = row[1]
            vec_bytes = struct.pack(f"{len(emb)}f", *emb)
            conn.execute("INSERT OR REPLACE INTO vec_index VALUES (?, ?)",
                        (source_id, vec_bytes))
            conn.execute("INSERT OR REPLACE INTO vec_meta VALUES (?,?,?,?,?,?,?)",
                        (source_id, row[0], row[2], row[3], None, MODEL, now_iso()))

        conn.commit()
        print(f"  {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")

    print(f"Done: {len(texts)} vectors indexed")

if __name__ == "__main__":
    main()
```

## 付録C: 殿への確認事項

1. **VPSスペック**: 現行457MB RAM → 4GBアップグレード予定はあるか？ agent-swarm側のモデル選定に影響
2. **モデル常駐 vs 遅延ロード**: 検索頻度が高い場合はデーモン化（常駐）が有利。初回10秒待ちは許容可能か？
3. **`--hybrid` デフォルト化のタイミング**: Phase 0ではオプトイン。いつデフォルトに切り替えるか？
4. **MeCab分かち書き問題**: 現行FTS5のcontentはMeCab済み。ベクトル化用にrawテキストを別途保持するか、MeCab済みテキストをそのままベクトル化するか？（後者は精度低下の可能性あり）
