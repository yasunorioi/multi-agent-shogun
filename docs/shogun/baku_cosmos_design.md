# 獏に宇宙を作る — 好奇心エンジン設計書

> **date**: 2026-03-15 | **analyst**: gunshi
> **North Star**: 好奇心に物理法則を与えよ。方向性のある爆発を設計せよ

---

## §0 エグゼクティブサマリ

**推奨: 案C — 勾配+偏角ハイブリッドモデル**

殿のGPS三角測量アナロジーは**半分正しく、半分危険**。
正しい部分を活かし、危険な部分を修正した設計を提案する。

- **正しい部分**: 「距離ではなく角度で測る」「知識の穴に情報が流れ込む」
- **危険な部分**: GPSの精密な三角測量をそのまま情報空間に持ち込むこと

代わりに「情報ポテンシャル場の勾配」+「プロジェクト偏角」の2段モデルを提案。
Phase 0は**既存の共起行列（76,652件）をそのまま活用**し、新規テーブル2つ+SQL関数で
TONO_INTERESTSのハードコードを完全に置換する。

月額ゼロ。SQLite完結。マクガイバー精神。

---

## §1 アナロジーの妥当性検証

### 1.1 GPS三角測量 — どこまで実装に落とせるか

| GPS概念 | 情報空間での対応 | 実装可能性 | 判定 |
|---------|----------------|-----------|------|
| **衛星の既知位置** | 没日録のcmd座標 | ◎ 366 cmdがDB上に固定点として存在 | **使える** |
| **衛星からの距離** | cmdと未知点の「距離」 | △ 情報空間の距離は曖昧。何で測る？ | **要再定義** |
| **三角測量で位置特定** | 3点から未到達点を測位 | ✕ 未知の点は座標すら不明。測位できない | **使えない** |
| **衛星の軌道予測** | 殿の速度ベクトル | ◎ cmd系列の時間変化から外挿可能 | **使える** |

**核心的な問題**: GPSは「自分の位置がわからない」が衛星の位置は正確に既知。
好奇心エンジンでは「到達したい点」自体が未知。**到達先の座標がないのに三角測量はできない。**

### 1.2 救える部分 — 勾配と偏角

GPSのメタファーは捨てるが、殿の直感の本質は活かす:

| 殿の直感 | 物理的翻訳 | 実装 |
|---------|----------|------|
| 「知識の穴に情報が流れ込む」 | ポテンシャル場の勾配降下 | 共起密度の低い領域を「穴」として検出 |
| 「距離ではなく角度で測る」 | ベクトルの偏角（方向） | プロジェクト間の共起パターンの方向類似性 |
| 「殿の速度ベクトル」 | 時間微分 | 直近N日のcmd頻度変化 |
| 「方向性のある爆発」 | 指向性のある探索 | 勾配方向 + ランダム偏差 |

### 1.3 殿、ここが危ない（拙者の見立て）

1. **アナロジー酔い**: 「GPS」「重力場」「三角測量」は**比喩として美しいが実装を縛る**。
   座標系を作ること自体が目的になり、本来の「良い検索クエリを生成する」から逸れるリスク

2. **次元の呪い**: 情報空間に「座標軸」を作ると、その軸の選び方で結果が決まる。
   農業IoT・脳科学・LLM…何をX軸にする？ 恣意的な軸選定 = 恣意的な結果

3. **冷静に見ると今の獏の問題は単純**: TONO_INTERESTSが静的なハードコード。
   これを動的に生成するだけで80%の改善が得られる。宇宙を作る前にまずここを直せ

---

## §2 推奨設計: 勾配+偏角ハイブリッドモデル

### 2.1 全体像

```
Phase 0: 勾配エンジン（TONO_INTERESTS動的置換）
  │  既存共起行列 → 情報密度マップ → 「穴」の検出 → 検索クエリ自動生成
  │  ★ ここだけでTONO_INTERESTSのハードコードを完全排除
  │
Phase 1: 偏角エンジン（殿の「角度」を実装）
  │  プロジェクト横断の方向類似性 → 遠いドメインの同方角発見
  │  ★ 温室制御と脳科学が「同じ角度」で繋がる
  │
Phase 2: 速度ベクトル（殿の進行方向予測）
  │  cmd系列の時間微分 → 殿が向かっている先の予測
  │
Phase 3: 好奇心エンジン統合（勾配+偏角+速度）
     三者統合で検索クエリを自動生成。TONO_INTERESTSは完全に消える
```

### 2.2 なぜこの順序か

- **Phase 0だけで実用価値がある**（TONO_INTERESTSの動的置換）
- Phase 0の結果を見てPhase 1に進むか判断できる（PDCA）
- 各Phaseが独立検証可能（手戻りが小さい）

---

## §3 Phase 0 設計: 勾配エンジン（情報密度の穴を見つける）

### 3.1 コンセプト

「情報密度」= あるキーワード群がcmd/subtaskでどれだけカバーされているか。
密度が低い = 殿がまだ深く踏み込んでいない領域 = 「穴」 = 好奇心の源泉。

ただし、**まったく触れていない領域は穴ではなく無関心**。
穴 = 「周辺は高密度だが、その中心が空いている」ドーナツ構造。

```
高密度       穴（低密度だが周辺は高密度）    無関心（低密度、周辺も低密度）
████████     ████░░████                     ░░░░░░░░
████████     ████░░████                     ░░░░░░░░
████████     ████░░████                     ░░░░░░░░
 → 既知      → 好奇心の対象                  → スルー
```

### 3.2 既存テーブルの活用

**既に76,652件の共起データと17,574件のキーワードがある。これを使わない手はない。**

```
doc_keywords (17,574件)
  → キーワードのドキュメント出現頻度（DF）= 密度の基礎

cooccurrence (76,652件)
  → キーワード間の共起PMI = 「周辺」の定義
```

### 3.3 新規テーブル: keyword_density

```sql
-- キーワードごとの情報密度指標
CREATE TABLE IF NOT EXISTS keyword_density (
    keyword       TEXT PRIMARY KEY,
    df            INTEGER NOT NULL,   -- document frequency（何件のcmdに出現）
    neighbor_df   REAL NOT NULL,      -- 隣接キーワードの平均DF
    density_gap   REAL NOT NULL,      -- neighbor_df - df = 穴の深さ
    last_cmd_at   TEXT,               -- 最後にこのキーワードが出たcmdの日時
    velocity      REAL DEFAULT 0,     -- 直近7日のDF変化率（Phase 2前倒し）
    updated_at    TEXT NOT NULL
);
```

### 3.4 穴の検出SQL

```sql
-- Step 1: 各キーワードのDF（ドキュメント頻度）を計算
-- doc_keywordsから直接
WITH kw_df AS (
    SELECT keyword, COUNT(DISTINCT doc_id) AS df
    FROM doc_keywords
    GROUP BY keyword
),
-- Step 2: 各キーワードの「隣接キーワードの平均DF」を計算
-- 共起行列で繋がっている相手のDFの平均
kw_neighbor AS (
    SELECT
        c.term_a AS keyword,
        AVG(d.df) AS neighbor_df
    FROM cooccurrence c
    JOIN kw_df d ON d.keyword = c.term_b
    WHERE c.pmi > 0.5  -- 意味のある共起のみ
    GROUP BY c.term_a
    HAVING COUNT(*) >= 3  -- 最低3つの隣接語を持つ
)
-- Step 3: 穴 = 自分のDFが低いが、隣接キーワードのDFが高い
SELECT
    k.keyword,
    k.df,
    n.neighbor_df,
    (n.neighbor_df - k.df) AS density_gap
FROM kw_df k
JOIN kw_neighbor n ON n.keyword = k.keyword
WHERE k.df >= 2           -- 完全に無関心なキーワードは除外
  AND n.neighbor_df > 10  -- 周辺が十分に高密度
ORDER BY density_gap DESC
LIMIT 20;
```

**このSQLが返すもの**: 「周辺は殿が頻繁に触れているが、そのキーワード自体はあまり深掘りされていない」領域。
これが好奇心の対象 = 検索クエリの種。

### 3.5 穴→検索クエリへの変換

```python
def generate_curiosity_queries(conn, max_queries=5):
    """情報密度の穴からWeb検索クエリを生成する。
    TONO_INTERESTSのハードコードを完全に置換する。
    """
    # 穴を検出
    holes = conn.execute("""
        SELECT kd.keyword, kd.density_gap, kd.velocity
        FROM keyword_density kd
        WHERE kd.density_gap > 5        -- 十分に深い穴
          AND kd.df >= 2                 -- 無関心ではない
        ORDER BY kd.density_gap DESC
        LIMIT 20
    """).fetchall()

    # 各穴に対して、共起語で検索クエリを肉付け
    queries = []
    for hole in holes:
        keyword = hole[0]
        # 共起の強い語を2つ取得してクエリを構成
        neighbors = conn.execute("""
            SELECT term_b FROM cooccurrence
            WHERE term_a = ? AND pmi > 1.0
            ORDER BY pmi DESC LIMIT 2
            UNION
            SELECT term_a FROM cooccurrence
            WHERE term_b = ? AND pmi > 1.0
            ORDER BY pmi DESC LIMIT 2
        """, (keyword, keyword)).fetchall()

        context_words = [n[0] for n in neighbors[:2]]
        query = f"{keyword} {' '.join(context_words)}"
        queries.append({
            "domain": "auto_curiosity",
            "query": query,
            "relevance_score": hole[1],  # density_gap = 穴の深さ
            "source": "gradient_engine",
            "matched_keywords": [keyword] + context_words,
        })

    # 上位N件 + ランダム1件（セレンディピティ枠）
    import random
    top = queries[:max_queries - 1]
    rest = queries[max_queries - 1:]
    if rest:
        top.append(random.choice(rest))
    return top[:max_queries]
```

### 3.6 baku.pyへの統合

```python
# baku.py の generate_dream_queries() を置換

def generate_dream_queries(recent_kw: list[str]) -> list[dict]:
    """好奇心エンジンで検索クエリを生成（Phase 0: 勾配エンジン）"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    # 勾配エンジンからクエリ生成
    curiosity_queries = generate_curiosity_queries(conn, max_queries=4)

    # フォールバック: 勾配エンジンが結果ゼロの場合、直近キーワードで検索
    if not curiosity_queries:
        curiosity_queries = [
            {"domain": "fallback", "query": kw, "relevance_score": 1,
             "source": "recent_keywords", "matched_keywords": [kw]}
            for kw in recent_kw[:3]
        ]

    # セレンディピティ枠: 共起行列のランダムウォーク（1件）
    serendipity = random_walk_query(conn)
    if serendipity:
        curiosity_queries.append(serendipity)

    conn.close()
    return curiosity_queries[:MAX_SEARCHES_PER_RUN]


def random_walk_query(conn) -> dict | None:
    """共起行列上のランダムウォークで予想外のクエリを生成。
    「方向性のある爆発」のうち「爆発」部分。"""
    import random
    # ランダムな起点キーワードを選ぶ
    start = conn.execute(
        "SELECT keyword FROM doc_keywords ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    if not start:
        return None

    current = start[0]
    path = [current]
    # 3歩ランダムウォーク
    for _ in range(3):
        next_step = conn.execute("""
            SELECT term_b FROM cooccurrence
            WHERE term_a = ? AND pmi > 0.5
            ORDER BY RANDOM() LIMIT 1
            UNION
            SELECT term_a FROM cooccurrence
            WHERE term_b = ? AND pmi > 0.5
            ORDER BY RANDOM() LIMIT 1
        """, (current, current)).fetchone()
        if next_step:
            current = next_step[0]
            path.append(current)
        else:
            break

    if len(path) >= 2:
        return {
            "domain": "serendipity",
            "query": " ".join(path),
            "relevance_score": 0,  # 関連度不問
            "source": "random_walk",
            "matched_keywords": path,
        }
    return None
```

---

## §4 Phase 1 設計: 偏角エンジン（角度で遠くを探す）

### 4.1 「角度」の定義

殿の直感「温室制御と脳科学が繋がるのは距離は遠いが角度が近いから」を形式化する。

**偏角 = プロジェクト間のキーワード共起パターンの方向類似性**

具体例:
```
unipi-agri-ha のキーワードベクトル: [側窓:15, 温度:20, 制御:18, 勾配:5, ...]
shogun のキーワードベクトル:        [LLM:30, 足軽:25, 制御:10, 勾配:3, ...]
                                     ↑
                          「制御」「勾配」が共通 → 偏角が近い
```

2つのプロジェクトが**同じキーワードを共有する度合い**がcos類似度。
これが「角度」。

### 4.2 新規テーブル: project_angle

```sql
-- プロジェクト間の偏角（cos類似度）
CREATE TABLE IF NOT EXISTS project_angle (
    project_a   TEXT NOT NULL,
    project_b   TEXT NOT NULL,
    cos_sim     REAL NOT NULL,       -- コサイン類似度 [0, 1]
    shared_kw   TEXT,                -- 共有キーワード上位5（カンマ区切り）
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (project_a, project_b)
);
```

### 4.3 偏角計算SQL

```sql
-- プロジェクト間のキーワード共有度（cos類似度の分子部分）
WITH project_kw AS (
    SELECT
        c.project,
        dk.keyword,
        COUNT(DISTINCT dk.doc_id) AS tf
    FROM doc_keywords dk
    JOIN commands c ON dk.doc_id = c.id
    WHERE c.project IS NOT NULL
    GROUP BY c.project, dk.keyword
),
dot_product AS (
    SELECT
        a.project AS project_a,
        b.project AS project_b,
        SUM(a.tf * b.tf) AS dot,
        GROUP_CONCAT(a.keyword, ',') AS shared_keywords
    FROM project_kw a
    JOIN project_kw b ON a.keyword = b.keyword
        AND a.project < b.project
    GROUP BY a.project, b.project
),
norms AS (
    SELECT project, SQRT(SUM(tf * tf)) AS norm
    FROM project_kw
    GROUP BY project
)
SELECT
    d.project_a,
    d.project_b,
    d.dot / (na.norm * nb.norm) AS cos_sim,
    d.shared_keywords
FROM dot_product d
JOIN norms na ON na.project = d.project_a
JOIN norms nb ON nb.project = d.project_b
ORDER BY cos_sim DESC;
```

### 4.4 偏角を使った検索

「角度が近いがcmd数が少ないプロジェクトペア」の交差領域を探索:

```python
def angle_queries(conn, max_queries=2):
    """偏角が近いが探索が少ないプロジェクト間の交差領域を検索"""
    rows = conn.execute("""
        SELECT pa.project_a, pa.project_b, pa.cos_sim, pa.shared_kw
        FROM project_angle pa
        WHERE pa.cos_sim > 0.1 AND pa.cos_sim < 0.5
        -- 近すぎ（同じ領域）でも遠すぎ（無関係）でもない
        ORDER BY pa.cos_sim DESC
        LIMIT 5
    """).fetchall()

    queries = []
    for row in rows:
        shared = row[3].split(",")[:3] if row[3] else []
        if shared:
            query = f"{row[0]} {row[1]} {' '.join(shared)}"
            queries.append({
                "domain": "angle_cross",
                "query": query,
                "relevance_score": row[2],
                "source": "angle_engine",
                "matched_keywords": shared,
            })
    return queries[:max_queries]
```

---

## §5 Phase 2 設計: 速度ベクトル（殿の進行方向）

### 5.1 速度 = 直近のcmd頻度変化

```sql
-- 各キーワードの直近7日 vs 過去30日のDF比率 = 速度
UPDATE keyword_density SET velocity = (
    SELECT
        COALESCE(recent.cnt, 0) * 1.0 /
        NULLIF(COALESCE(older.cnt, 1), 0)
    FROM
        (SELECT dk.keyword, COUNT(DISTINCT dk.doc_id) AS cnt
         FROM doc_keywords dk
         JOIN commands c ON dk.doc_id = c.id
         WHERE c.created_at > datetime('now', '-7 days')
         GROUP BY dk.keyword) recent
    LEFT JOIN
        (SELECT dk.keyword, COUNT(DISTINCT dk.doc_id) AS cnt
         FROM doc_keywords dk
         JOIN commands c ON dk.doc_id = c.id
         WHERE c.created_at BETWEEN datetime('now', '-30 days')
                               AND datetime('now', '-7 days')
         GROUP BY dk.keyword) older
    ON recent.keyword = older.keyword
    WHERE recent.keyword = keyword_density.keyword
);
```

velocity > 1.0 = 加速中（殿が最近集中している）
velocity < 1.0 = 減速中（殿の興味が移っている）
velocity = NULL = 直近で未使用

### 5.2 速度をクエリ生成に反映

```python
# generate_curiosity_queries の ORDER BY を変更
# density_gap（穴の深さ）× velocity（加速度）で優先順位付け
ORDER BY kd.density_gap * COALESCE(kd.velocity, 0.5) DESC
```

加速中のキーワード周辺の穴を優先 → 殿が今向かっている方角の未踏領域を探索。

---

## §6 Phase 3: 統合 — 好奇心エンジン

### 6.1 3つのエンジンの統合

```python
def generate_dream_queries_v3(conn, recent_kw, max_queries=5):
    """好奇心エンジン v3: 勾配+偏角+速度の統合"""

    # 配分: 勾配3件 + 偏角1件 + セレンディピティ1件
    gradient = generate_curiosity_queries(conn, max_queries=3)  # Phase 0
    angle = angle_queries(conn, max_queries=1)                   # Phase 1
    serendipity = [random_walk_query(conn)]                      # 爆発枠

    all_queries = gradient + angle + [s for s in serendipity if s]
    return all_queries[:max_queries]
```

### 6.2 TONO_INTERESTSの完全消去

Phase 3完了後、baku.pyから`TONO_INTERESTS`辞書（95行L50-L95）を**完全削除**。
代わりに `generate_dream_queries_v3()` が没日録+共起行列+偏角から動的に生成。

殿の興味が変われば没日録が変わり、共起行列が変わり、穴の位置が変わり、
検索クエリが自動的に変わる。**好奇心が自律進化する。**

---

## §7 見落としの可能性（拙者のドジっ子ポイント）

1. **ストップワード汚染**: doc_keywordsの上位が「既存」「成果物」「足軽」（実データ確認済み）。
   これらはshogunシステムの定型語であって殿の知識ではない。
   **keyword_density計算の前にストップワード除去が必須**。
   現在の doc_keywords 17,574件のうち、上位20語は全て定型語の可能性。

2. **自己強化ループ**: 穴を探索→蔵書化→共起行列に反映→穴が埋まる→新しい穴を探す。
   これは健全だが、**初期の穴検出精度が低いと間違った方向に収束するリスク**。
   Phase 0のパイロットで手動検証が必須。

3. **プロジェクト偏在**: unipi-agri-ha(139cmd)がshogun(90cmd)の1.5倍。
   偏角計算がunipi-agri-haのキーワードに引きずられる可能性。
   TF-IDF的な正規化（IDF = log(全PJ数/出現PJ数)）で補正すべき。

4. **共起行列のスパース問題**: 76,652件あるが、PMI > 1.0の有意義な共起はその一部。
   穴検出のneighbor_df計算で、スパースな領域は「穴」と「無関心」の区別がつかない。
   `HAVING COUNT(*) >= 3` の閾値を慎重にチューニングする必要がある。

5. **English/日本語の混在**: doc_keywordsに英語キーワード（LLM, RPi, API）と
   日本語キーワード（制御, 設計, 足軽）が混在。共起行列は言語を超えて機能するが、
   DuckDuckGoのクエリ生成時に言語を混ぜるとノイズになる可能性。

6. **dreams.jsonlとの二重性**: 夢データ（138件）はdashboard_entries(dream_library)にも
   蔵書化されている。keyword_densityに夢由来のキーワードを含めるか否かで
   「穴」の定義が変わる。含めないほうが安全（殿自身の活動ベースに限定）。

---

## §8 冒険的対案: 遺伝的ドリフトモデル

策を三つ考えた…いや四つ。最後の一つは冒険的な案だ。少し面白い。

### 8.1 コンセプト

TONO_INTERESTSを「遺伝子プール」とみなす。

```python
# 各検索テンプレートが1つの「遺伝子」
gene_pool = [
    {"query": "greenhouse climate control AI", "fitness": 0.0},
    {"query": "small language model tool calling", "fitness": 0.0},
    ...
]
```

- **選択**: Sonnet選別でaccept → fitness += 1、reject → fitness -= 0.5
- **交叉**: fitness上位2つのクエリからキーワードをランダムに組み合わせて新クエリ
- **変異**: ランダムにキーワードを1つ入れ替え（共起行列から選ぶ）
- **淘汰**: fitness最下位を世代ごとに除去

### 8.2 殿の「怒り駆動」との相性

殿がLINE Botで「この夢くだらない」と怒る → fitness大幅減 → 強い淘汰圧。
「これ面白い」と言う → fitness大幅増 → 強い選択圧。
**怒りの強さがそのまま進化の方向を決める。**

### 8.3 なぜ推奨しないか

- 収束に時間がかかる（数百日の蓄積が必要）
- 小集団ドリフト（遺伝子プール30-40本程度）で有用なクエリが偶然消失するリスク
- 殿のGPS/物理モデル構想とは異なるパラダイム
- ただし、**Phase 3以降の「蔵書100件超」で再検討する価値はある**

---

## §9 Phase 0 最小パイロット提案

### 9.1 やること（足軽1人、1-2日）

| # | 作業 | 成果物 |
|---|------|--------|
| 1 | doc_keywordsのストップワード除去リスト作成 | scripts/stopwords.txt |
| 2 | keyword_densityテーブル作成+初期データ投入 | ALTER TABLE in botsunichiroku.py |
| 3 | 穴検出SQL実行 → 上位20件の「穴」を殿に見せる | レポート |
| 4 | generate_curiosity_queries()をbaku.pyに追加（TONO_INTERESTSと並行稼働） | baku.py改修 |
| 5 | 1週間並行稼働して、勾配クエリ vs 静的クエリの夢品質を比較 | dreams.jsonlのsource別分析 |

### 9.2 成功判定

- 穴検出SQLが「殿が直感的に興味を持てる」キーワードを3件以上返す
- 勾配エンジンのクエリが、TONO_INTERESTSと**異なるが関連性のある**検索結果を拾う
- 1週間の並行稼働で、勾配クエリのHaiku relevance評価が static クエリと同等以上

### 9.3 失敗した場合

- ストップワード汚染がひどい → ストップワードリスト拡充して再試行
- 穴が「穴」に見えない（ただのノイズ） → neighbor_df / density_gap の閾値調整
- 共起行列がスパースすぎて使えない → Phase 0は保留、cmd数が増えてから再挑戦

---

## §10 North Star整合

## §11 免疫系: 虚像と真実の境界線

> 殿の言葉（2026-03-15）:
> 「虚像と真実の境界線は誰にも答えが無いし理論的に取り去れるものでもないが、
>  取り去らないと現実のシステムのほうが崩壊する」

好奇心エンジンが優秀であるほど、質の高い嘘も拾ってしまう。
勾配エンジンはドメイン適合度しか見ない — 真偽は見えない。

### テストケース: Hackaday 2016/04/01 Apple SBC記事
- Hackaday（信頼ソース）、RPi対抗、$50、A8チップ — キーワード全刺さり
- 殿すら騙された。勾配エンジンなら確実にinvestigate判定
- **好奇心エンジンの精度が上がるほど、免疫系の必要性も上がる**

### 設計方針（未決、Phase 3以降で検討）
- 完璧な真偽判定は不可能。それは前提
- 獏の仕事は夢を見ること。夢に真偽は無い
- 免疫系はSonnet選別（お針子層）の責務
- 日付（4/1）、ソースの傾向、製品の実在確認 — ヒューリスティクスの積み重ね
- 温室制御のセンサー誤値対策と同じ構造: 単一ソースを信じない、複数経路で検証

---

```yaml
north_star_alignment:
  status: aligned
  reason: |
    「好奇心に物理法則を与えよ。方向性のある爆発を設計せよ」に対し:
    - 勾配エンジン: 情報密度の穴に向かって流れ落ちる ＝ 物理法則
    - 偏角エンジン: 角度で遠くのドメインを探す ＝ 方向性
    - セレンディピティ枠: ランダムウォーク ＝ 爆発
    - 三者統合で「方向性のある爆発」を実現
    - 既存共起行列（76K件）を最大活用。新規テーブル2つ+SQL
    - 月額ゼロ、SQLite完結、マクガイバー精神
  risks_to_north_star:
    - "アナロジーに酔って実装が遅れるリスク。Phase 0を最優先でパイロットせよ"
    - "ストップワード汚染で穴検出が機能しない場合、全体設計が崩れる"
    - "殿のGPS三角測量構想とのズレ（拙者は勾配+偏角を推すが殿の好みと異なる可能性）"
```
