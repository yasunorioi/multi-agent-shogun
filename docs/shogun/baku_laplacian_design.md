# 獏（baku.py）改修設計 — ラプラシアンフィルタ＋深掘りループ＋systrade共通パターン

> **軍師分析書** | 2026-03-27 | cmd_455 / subtask_1010 | project: shogun

---

## §1 ラプラシアンフィルタの獏への適用設計

### 1a. 問題の定式化

画像処理におけるラプラシアンフィルタは「二次微分＝変化の変化」を検出する。
獏の情報パイプラインに翻訳すると:

```
情報の一次微分 = 今回収集 - 前回収集（差分）
情報の二次微分 = 今回の差分 - 前回の差分（差分の差分 = エッジ検出）
```

**目的**: 「みんな知っている平坦な情報」を捨て、「急に変化した尖った情報」だけを深掘りキューに投入する。

### 1b. 現行baku.pyのフロー分析

```
get_recent_keywords(7d)
  ↓
generate_dream_queries(recent_kw)  ← TONO_INTERESTS × DB keyword
  ↓
search_ddg() + search_kousatsu()   ← Web + 内部検索
  ↓
interpret_dream(Haiku)              ← relevance判定 (high/medium/low/none)
  ↓
save_dream(JSONL)                   ← dreams.jsonl に追記
  ↓
[朝7時] run_daily_batch()
  ├── sonnet_selection()            ← Sonnet一括選別
  ├── save_to_dream_library()       ← 没日録DB蔵書化
  └── finance_deepdive()            ← FRED/WB自動検証
```

**現行の問題点**:
1. **差分概念がない**: 毎回全テンプレート（~80件）からMAX_SEARCHES_PER_RUN=5件を選び、DDG検索する。前回の結果との差分を見ていない
2. **6時間重複チェックは同一クエリのスキップのみ**: 「同じクエリを投げない」だけで、「結果が変わったかどうか」は見ていない
3. **Haiku解釈のrelevanceは静的判断**: dream単体の関連度であり、前回との変化量ではない
4. **蔵書化フィルタは品質フィルタ**: Sonnet選別は「知見として使えるか」であり「変化が尖っているか」ではない

### 1c. フック点（挿入ポイント）

```
フック点A: generate_dream_queries() → search実行の間
  場所: dream_once() L812付近
  目的: 「前回と同じ検索結果を返しそうなクエリ」を事前に間引く
  方法: 前回結果のhash保存 → hash一致なら skip
  コスト: hash比較のみ、API呼び出しゼロ

フック点B: search結果取得 → interpret_dream()の間
  場所: dream_once() L827-833付近
  目的: 検索結果の「変化量」を計算し、閾値以下なら解釈をスキップ
  方法: 前回同一クエリ結果とのJaccard/edit distance → delta_score算出
  コスト: ローカル計算のみ

フック点C: interpret_dream()の出力 → save_dream()の間
  場所: dream_once() L836付近
  目的: Haiku解釈に「前回との差分コンテキスト」を注入
  方法: interpret_dream()のuser_msgに「前回の同一ドメイン解釈」を付加
  コスト: Haiku APIトークン微増（+200token程度）

フック点D: run_daily_batch() → sonnet_selection()の間
  場所: run_daily_batch() L504付近
  目的: delta_scoreで事前フィルタし、Sonnet選別のコストを削減
  方法: candidates中のdelta_score > 閾値のみSonnet送り
  コスト: Sonnet API呼び出し削減（コスト節約）
```

### 1d. 推奨: 二段フィルタ設計

```
┌──────────────────────────────────────────────────────┐
│ Stage 1: Content Hash Filter (フック点A)             │
│   前回結果のSHA256先頭16文字を保存                    │
│   hash一致 → skip（検索すらしない）                   │
│   hash不一致 or 初回 → 検索実行                      │
│   ストレージ: data/baku_content_hash.json            │
│   コスト: ゼロ                                       │
├──────────────────────────────────────────────────────┤
│ Stage 2: Delta Score Filter (フック点B)              │
│   前回同一クエリ結果とのJaccard類似度を計算           │
│   jaccard < 0.3（大きく変化）→ high_delta            │
│   0.3 ≤ jaccard < 0.7 → medium_delta                │
│   jaccard ≥ 0.7（ほぼ同じ）→ low_delta → skip       │
│   dream_entryに "delta_score" フィールド追加          │
│   コスト: ローカル計算のみ                            │
└──────────────────────────────────────────────────────┘
                        ↓
              interpret_dream() → 通常フロー
              （high_delta のみ Haiku 解釈に進む）
```

**Jaccard閾値0.7の根拠**: cmd_451のDexterパターン分析で「Jaccard 0.7で類似検出」を確認済み。同じ閾値を逆用する（0.7以上は変化なし＝捨て）。

### 1e. データ構造

```python
# data/baku_content_hash.json
{
  "query_hash_md5_12": {
    "last_hash": "sha256_16chars",
    "last_result": "前回検索結果スニペット（先頭300文字）",
    "last_checked": "2026-03-27T08:00:00",
    "check_count": 5,
    "delta_history": [0.1, 0.8, 0.2, ...]  # 直近10回のdelta推移
  }
}
```

`delta_history` を保持することで、将来的に**二次微分（delta of delta）**の計算が可能になる。
これが本来の「ラプラシアンフィルタ」——変化量自体の変化を検出する仕組みの布石。

### 1f. コスト影響

| 指標 | 現行 | Stage 1適用後 | Stage 1+2適用後 |
|------|------|-------------|----------------|
| DDG検索/回 | 5件 | 2-3件（推定40%削減） | 2-3件 |
| Haiku API呼び出し/回 | 5件 | 5件 | 1-2件（推定60%削減） |
| Sonnet選別候補/日 | 全件 | 全件 | high_delta のみ |
| 月額APIコスト | ~$0.8 | ~$0.5 | ~$0.3 |

殿の「月額$1以内」制約を余裕で満たしつつ、情報の質を向上させる。

---

## §2 深掘りループ（Dexterパターン適用）

### 2a. Dexterの自己検証ループ（cmd_451分析結果より）

```
Dexter: while (iteration < maxIterations=10):
  ├── ツール呼び出し → 結果取得
  ├── 「十分か？」判定（LLMに委ねる）
  │   ├── 十分 → 直接回答（ループ終了）
  │   └── 不十分 → 次のツール呼び出し
  └── Jaccard 0.7 で類似クエリ検出 → 同じ質問の繰り返し防止
```

### 2b. 獏への適用: 「噛み砕きループ」

現行の獏には「仕入れ → 品定め → 蔵書化」はあるが、**「噛み砕く」フェーズがない**。
Dexterパターンを適用して、high_delta情報に対する深掘りループを設計する。

```
┌─────────────────────────────────────────────────┐
│  噛み砕きループ (chew_loop)                       │
│                                                  │
│  入力: high_delta な dream_entry                  │
│  max_iterations: 3（Dexterの10は過剰。コスト制約） │
│                                                  │
│  while iteration < 3:                            │
│    ├── DDG追加検索（関連キーワード展開）          │
│    ├── 没日録DB検索（内部知見との突合）           │
│    ├── Haiku判定: 「これで殿に報告できるか？」    │
│    │   ├── "sufficient" → ループ終了             │
│    │   └── "need_more" + 次のクエリ提案          │
│    └── 類似チェック（前iterationとJaccard > 0.7   │
│          → 収束判定 → 強制終了）                  │
│                                                  │
│  出力: enriched_dream（追加情報付き）             │
└─────────────────────────────────────────────────┘
```

### 2c. 収束判定基準（convergence criterion）

Dexterは「LLMがツール呼び出しを止めたら終了」という暗黙の収束判定。
獏では明示的な3条件を設計する:

1. **Haiku自己判定**: `"sufficient"` を返せば終了（Dexterと同じ）
2. **Jaccard収束**: 前回iterationの結果とJaccard ≥ 0.7 → 新情報なし → 終了
3. **max_iterations到達**: 3回で強制終了（Haiku 3回 × ~300token = ~$0.001）

**Dexterとの差分と理由**:
- maxIter=3（Dexterは10）: APIコスト制約。月$1以内を死守
- Jaccard収束追加: Dexterにはない。「同じ情報をぐるぐる」を早期検出
- ツール呼び出しなし: Dexterはファイル操作・API実行あり。獏はWeb検索+DB検索のみ

### 2d. 噛み砕きの入口条件

全てのdreamに対して深掘りループを回すとコスト爆発する。入口条件:

```python
def should_chew(dream_entry: dict) -> bool:
    """深掘りループに投入するかの判定"""
    # 条件1: delta_scoreがhigh（§1のラプラシアンフィルタ通過）
    if dream_entry.get("delta_score", 0) < 0.5:
        return False
    # 条件2: Haiku解釈でaction=investigate
    action = dream_entry.get("interpretation", {}).get("action")
    if action != "investigate":
        return False
    # 条件3: 殿の重点ドメイン（systrade_research, system_design）を優先
    priority_domains = {"systrade_research", "system_design", "agriculture_iot"}
    if dream_entry.get("domain") not in priority_domains:
        return False
    return True
```

### 2e. 噛み砕き結果の構造

```python
{
    # 元のdream_entryフィールドはそのまま
    "chew_result": {
        "iterations": 2,
        "convergence_reason": "haiku_sufficient",  # or "jaccard_converged", "max_iter"
        "additional_sources": [
            {"query": "expanded query 1", "result": "..."},
            {"query": "expanded query 2", "result": "..."},
        ],
        "internal_connections": ["cmd_451: Dexterパターン", "cmd_420: daily_risk.py"],
        "chewed_insight": "噛み砕いた知見（Haikuが最終iterationで生成）",
        "chewed_at": "2026-03-27T08:05:00",
    }
}
```

---

## §3 出力設計

### 3a. 現行のデータフロー

```
dreams.jsonl (生の夢、JSONL追記)
  ↓ [Sonnet選別]
dashboard_entries.dream_library (没日録DB、蔵書化)
  ↓ [Finance系のみ]
data/finance_deepdive.md (Markdownレポート)
  + agent-swarm finance板投稿
```

### 3b. 噛み砕き結果の配置先

**案A: dreams.jsonlに追記（推奨 ★★★）**
- `chew_result` フィールドを dream_entry に付加して save_dream()
- 既存のload_recent_dreams()、load_dreams_days() がそのまま使える
- run_daily_batch() で蔵書化対象にchew済みdreamが自動で含まれる
- **理由**: 既存パイプラインに乗せるのが最も低コスト

**案B: 別ファイル data/chewed_dreams.jsonl**
- 噛み砕き結果だけを分離保存
- load関数を別途作成する必要あり
- 蔵書化パイプラインへの接続にコード追加が必要
- **理由**: 分離すると管理が面倒。dreams.jsonlが既に整理されている

**案C: 没日録DB直接INSERT**
- 噛み砕き完了時点で即蔵書化
- Sonnet選別をスキップ（既にHaikuで十分噛み砕いている）
- **理由**: 過剰最適化。Sonnet選別の二重チェックは品質担保として残すべき

### 3c. 2chスレ連携

噛み砕き結果のうち特に価値の高いもの（Sonnet accept + chew済み）は:
1. `generate_digest()` で週次まとめスレに自動反映（既存フロー）
2. Finance系は `post_finance_report()` で相場板に投稿（既存フロー）
3. **新規**: high_delta + chew完了のdreamは即時投稿（リアルタイム速報）

即時投稿は `_post_reply()` の既存インフラをそのまま使える。

### 3d. docs/静的配信との連携

cmd_453で追加された `dat_server.py /docs/` エンドポイントとの連携:
- 週次ダイジェストの蓄積版を `docs/baku/weekly_YYYYMMDD.md` に静的保存
- finance_deepdive.mdはdata/に現行保存 → docs/finance/に移行可能
- **ただし優先度低**: まずはラプラシアンフィルタ+噛み砕きの基本機能を先行

---

## §4 systradeとの共通パターン抽出

### 4a. daily_risk.py のシグナル検出パターン

```python
# daily_risk.py の構造
SCORE_WEIGHTS = {
    "yield_curve": 3,  "credit": 2,  "oil": 2,
    "energy_sec": 2,   "shipping": 2, "vix": 1,
    "usd": 1,          "nikkei": 1,
}

# 各シグナルの計算: z-score → 閾値判定 → 0.0-1.0スコア
# 例: oil
#   z = (current - mean) / std
#   signal = clip((z - threshold) / (max_threshold - threshold), 0, 1)
#
# weighted_score = Σ (signal_i × weight_i) / MAX_SCORE
# label: SAFE < 0.25, CAUTION < 0.4, DANGER ≥ 0.4
```

### 4b. 獏のエッジ検出パターン

```python
# §1で設計したbaku laplacian filter
# delta_score = 1 - jaccard(current_result, previous_result)
# delta_history = [d1, d2, d3, ...]
#
# high_delta: delta_score > 0.5
# medium_delta: 0.3 ≤ delta_score < 0.5
# low_delta: delta_score < 0.3 → skip
```

### 4c. 共通の抽象構造

両者を並べると、同じパターンが浮かび上がる:

```
[daily_risk.py]                    [baku laplacian]
──────────────────────────────────────────────────
入力: FRED/yfinance 時系列データ    入力: DDG検索結果テキスト
信号: z-score（平均からの乖離）     信号: delta_score（前回からの変化量）
重み: SCORE_WEIGHTS（手動設定）     重み: ドメイン優先度（暗黙）
閾値: SAFE/CAUTION/DANGER          閾値: low/medium/high_delta
出力: リスクラベル + スコア          出力: skip/interpret/chew判定
```

**共通パターン = 「スカラーシグナル → 閾値判定 → アクション選択」**

### 4d. 共通モジュール化の可否

**結論: 共通モジュール化しない（★推奨）**

理由:
1. **入力型が根本的に異なる**: daily_risk.pyはpd.Series（数値時系列）、bakuはstr（テキスト）
2. **z-score計算とJaccard計算は共有できない**: 数値の標準偏差とテキストの集合類似度は別物
3. **抽象化のROEが低い**: 共通化して得られるコード削減 < 抽象化レイヤーの複雑性増加
4. **殿のマクガイバー精神に反する**: 「3行の類似コードを抽象化するな」

**ただし設計哲学は共有する**:
- 両システムとも「スカラーシグナル → 閾値 → アクション」の三段構造を守る
- SCORE_WEIGHTSのような重み辞書パターンは獏にも適用可能（将来的にドメイン重み付け）
- 閾値の命名規則（SAFE/CAUTION/DANGER ↔ low/medium/high_delta）を統一

### 4e. scratchpad.pyの横展開

cmd_451で実装されたsystradeのscratchpad.py（JSONL追記ログ）は獏にも適用できる:

```python
# baku側でも同じパターンを使う
from systrade.scratchpad import log_entry  # ← リポジトリ跨ぎは不可

# 代替: baku自身にスクラッチパッドを持たせる
# data/baku_scratchpad/{domain_hash}.jsonl
# → ドメイン別に検索結果の変遷を記録
# → delta_historyの永続化に使える
```

**実装方針**: scratchpad.pyの「queryハッシュでファイル分離 + JSONL追記」パターンを
baku側にも独立実装する（3関数、~40行）。リポジトリ間依存は作らない。

---

## §5 トレードオフ比較

### 5a. 実装案比較

| 案 | 内容 | コスト | 効果 | リスク | 推奨 |
|-----|------|--------|------|--------|------|
| **A: Content Hash Filter のみ** | Stage 1だけ実装 | 極小（hash計算） | DDG検索40%削減 | 低 | ★★★ |
| **B: A + Delta Score Filter** | Stage 1+2 | 小（Jaccard計算追加） | Haiku API 60%削減 | 低 | ★★★ |
| **C: B + 噛み砕きループ** | A+B+chew_loop | 中（Haiku追加3回/件） | 知見の質が飛躍的向上 | 中（APIコスト増） | ★★ |
| **D: C + systrade共通モジュール** | フル統合 | 大（リポジトリ間連携） | 理論的整合性 | 高（複雑性爆発） | ★ |
| **E: C + 2chリアルタイム速報** | C+即時投稿 | 小（既存インフラ流用） | 情報の即時性向上 | 低 | ★★ |

### 5b. 推奨ロードマップ

```
Phase 0 (即実装可): A + B（ラプラシアンフィルタ基本機能）
  → baku.pyに ~100行追加
  → テスト: 既存フロー破壊なし確認 + delta_score計算テスト

Phase 1 (次フェーズ): C（噛み砕きループ）
  → chew_loop() ~80行追加
  → テスト: コスト制約（月$1以内）内でのイテレーション回数検証

Phase 2 (将来): E（即時投稿）
  → _post_reply()流用で ~20行追加
  → Phase 1安定後に追加
```

Phase Dは非推奨。共通モジュール化は設計哲学の共有にとどめ、コード統合はしない。

---

## §6 リスクと見落としの可能性

### 6a. 技術リスク

1. **DDG結果の不安定性**: DDG Liteの出力HTMLは安定していない。hashが毎回変わる「偽変化」が起きる可能性
   - 対策: HTML全体ではなくsnippetテキストのみをhash対象にする（現行の抽出済みテキスト）

2. **Jaccard類似度の限界**: 語順が変わっただけで類似度が下がる
   - 対策: word-level Jaccardではなく、trigram Jaccardを使う（語順の影響を低減）

3. **噛み砕きループの暴走**: Haikuが常に"need_more"を返し続ける
   - 対策: max_iterations=3 の強制停止 + Jaccard収束検出

### 6b. コストリスク

4. **Haiku API呼び出し増**: 噛み砕きループで1 dream あたり最大3回追加
   - 対策: should_chew() の入口フィルタで対象を絞る。priority_domainsのみ
   - 最悪ケース推定: 5 dreams/日 × 3 iter × 300token × $0.25/1M = $0.001/日 = $0.03/月

5. **data/baku_content_hash.json の肥大化**: クエリ数 ~80 × ハッシュデータ → 問題なし（数KB）

### 6c. 見落としの可能性

6. **「ゆっくり変化する重要情報」の取りこぼし**: ラプラシアンフィルタは急変を検出するが、
   じわじわ変化する重要トレンド（例: 東南アジア不動産市場の漸進的変化）を見逃す
   - 対策: delta_historyの移動平均を月次で確認する「定期健診」機能（Phase 2以降）

7. **ドメイン間の相互作用**: あるドメインのhigh_deltaが別ドメインに波及する効果
   - 対策: generate_digest()のクロスドメイン関連ネタ検出（既存機能）がこれを補う

---

## §7 North Star 整合確認

| 観点 | 判定 |
|------|------|
| マクガイバー精神（最小コスト） | ✅ Phase 0はAPI呼び出し削減方向。コスト減 |
| 月額ゼロ志向 | ✅ 月$0.3に圧縮可能。DDG=無料、FRED=無料 |
| 殿の「噛み砕いて栄養にする」方針 | ✅ chew_loopが直接対応 |
| 既存69テスト回帰なし | ✅ systradeは無関係。baku.pyに既存テストなし |
| RPi/VPS放置運用 | ✅ daemon_loop()の構造に変更なし |
| Dexterパターン「盗む」 | ✅ Jaccard類似度検出、自己検証ループ、Scratchpad追記を適用 |

---

## §8 推奨アクション

1. **Phase 0を即時実行可能**: Content Hash + Delta Score Filter（~100行追加、テスト容易）
2. **Phase 1は Phase 0安定後**: 噛み砕きループ（~80行追加、コスト検証必要）
3. **共通モジュール化はしない**: 設計哲学の共有にとどめる
4. **scratchpadパターンはbaku独立実装**: リポジトリ間依存を作らない
5. **2ch即時投稿はPhase 2**: 既存インフラ流用で低コスト追加可能

---

*盗むべきは刀ではなく、刀の研ぎ方。—— cmd_451分析の結論はここでも生きている。*
