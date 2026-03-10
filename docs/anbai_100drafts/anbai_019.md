<!-- style: Qiitaテック記事風 | perspective: Iデータ原理主義(数字で殴る) | number: 019 -->

# 数字だけで語る：LLM89%削減の全容（n=32,470）

**はじめに**

感想はいらない。数字を見ろ。

本記事は、某クライアントとの環境制御PJ（NDA第2条：施設詳細非開示）における実証データを、数値に基づいて解説する。主観的評価・感情的記述・曖昧な表現は最小化する。

---

## スペック

```
観測期間: 114日（= 2,736時間 = 164,160分）
サンプリング: 5分間隔
理論サンプル数: 32,832レコード
実測サンプル数: 32,470レコード
欠損: 362レコード（欠損率 1.10%）
NDA締結: 1件
測定変数: 主に温度（℃）
```

---

## 問題の定量化

### 温度分布（全32,470レコード）

```python
# データで見る実態
distribution = {
    "< 16.0℃": {"count": 1461, "pct": 4.50},
    "16.0〜23.0℃": {"count": 11787, "pct": 36.31},
    "23.0〜27.0℃": {"count": 9157, "pct": 28.20},
    "> 27.0℃": {"count": 9448, "pct": 29.10},  # 問題域
}
total = sum(v["count"] for v in distribution.values())
# total = 31853（丸め誤差含む）
```

**問題**: 閾値T=27℃に対し、9,448/32,470 = **29.10%** が「緊急」判定。

### Goodhart's Law の定量的含意

情報エントロピーで指標品質を評価する：

```python
import math

p_critical = 0.291  # 緊急発生確率
p_normal = 1 - p_critical  # = 0.709

# Shannon entropy H(X)
H = -(p_critical * math.log2(p_critical) +
      p_normal   * math.log2(p_normal))
# H = 0.896 bits

# 最大エントロピー（p=0.5の時）= 1.000 bits
efficiency = H / 1.0  # = 0.896 = 89.6%
```

**解釈**: 「緊急」指標のエントロピーが89.6%（最大の89.6%に達している）。これは指標がほぼランダムな情報しか持っていないことを意味する。使い物にならない。

### LLM呼び出しコストの試算

```python
# 初期設計でのLLM呼び出し回数（推定）
calls_per_hour = 1.0  # 毎時1回
hours = 114 * 24  # 2,736時間
total_calls_before = calls_per_hour * hours  # = 2,736回

# 改善後
reduction_rate = 0.89
total_calls_after = total_calls_before * (1 - reduction_rate)
# = 2,736 * 0.11 = 300.96 ≈ 301回

reduction_count = total_calls_before - total_calls_after
# = 2,736 - 301 = 2,435回削減

# コスト換算（API単価を仮に¥50/callとすると）
cost_saving = reduction_count * 50  # = ¥121,750
```

**89%削減 = 推定2,435回削減（114日間で）**

---

## 三層アーキテクチャの数値設計

### 各層の処理割合

```python
layer_allocation = {
    "Layer1_emergency": 0.01,    # 1%（実際の緊急）
    "Layer2_rule_based": 0.98,   # 98%（定常制御）
    "Layer3_llm": 0.01,          # 1%（高度判断）
}
# 合計: 1.00（100%）

# 改善前の実態（問題）
before = {
    "Layer1_emergency": 0.01,
    "Layer2_rule_based": 0.709,  # 通過させていた（not processed）
    "Layer3_llm": 0.291,         # LLM呼び出し（過剰）
}
```

### 削減率の計算

```python
# LLM呼び出し比率
llm_before = 0.291  # 29.1%
llm_after  = 0.291 * 0.11  # = 0.032（89%削減後の推定）

actual_reduction = (llm_before - llm_after) / llm_before
# = (0.291 - 0.032) / 0.291 = 0.89 = 89%
```

---

## 塩分アナロジーの定量版

| 塩分濃度 | 官能スコア(0-10) | LLM呼び出し頻度(回/時) |
|--------|----------------|-------------------|
| 0.0% | 2.1 | 0.00 |
| 0.5% | 7.8 | 0.05 |
| **0.8%** | **9.8（最高）** | **0.11（最適）** |
| 1.5% | 6.2 | 0.50 |
| 2.0% | 3.5 | 1.00（問題域） |
| 5.0% | 0.5 | 1.00超（崩壊） |

**最適LLM頻度 ≈ 0.11回/時（本PJの改善後と一致）**

---

## Simon（1956）の数値的解釈

Satisficing は「十分よい解で止まる」。数値的には：

```python
def is_good_enough(quality_score: float, threshold: float = 0.8) -> bool:
    """
    品質スコアがthresholdを超えたら「十分よい」とみなす。
    デフォルト閾値: 0.8（80%）
    """
    return quality_score >= threshold

# 適用例
before_quality = 0.42  # 29.1%誤発報による品質低下
after_quality  = 0.87  # 三層構造後の品質
# is_good_enough(before_quality) → False → 改善が必要
# is_good_enough(after_quality)  → True  → これで十分
```

---

## 制御ルールについて

制御設定ファイルには現場固有のルールが蓄積されている（詳細はNDA管理下のため数値含め非開示）。

開示可能な数値的事実：
- ルールの起源：クライアントフィードバック（件数：非開示）
- ルール適用率：98%（全処理の）
- ルール精度：「品質向上」（具体的スコアはNDA管理下）

---

## Anbai Curve の数式

$$Q(I) = Q_{max} \cdot e^{-\beta(I - I^*)^2}$$

パラメータ：
- Q_max: 最高品質値（=1.0に正規化）
- I*: Anbai Point（最適投入量）
- β: 曲線の鋭さを制御するパラメータ（β>0）

この二次指数関数はガウシアン形状であり、Anbai Zone の幅と右端崩壊の急峻さを β で制御できる。

具体的なパラメータ値（β, I*）は実証データから推定可能だが、本PJのデータはNDA管理下のため非開示。

---

## まとめ（数値のみ）

| 指標 | Before | After | 変化 |
|------|--------|-------|------|
| 緊急判定率 | 29.1% | 改善（詳細NDA） | ↓ |
| LLM呼び出し頻度 | 1.0回/時 | 0.11回/時 | **-89%** |
| エントロピー効率 | 89.6%（低品質） | 改善 | ↓ |
| 推定削減回数 | — | 2,435回 | — |
| Simon（1956）からの経過 | 70年 | — | — |

**結論**: n=32,470のデータは、三層構造によるLLM89%削減が正当であることを支持する。数字が語る。以上。

---

## 参考文献

- Simon (1956): n≈0の理論的提唱 → 本研究で n=32,470 に拡張
- Goodhart (1975): 指標の罠 → エントロピー89.6%で定量確認
- Shannon (1948): 情報理論 → エントロピー計算に使用
- Shiomi (2026): *Journal of Approximate Science* — n=32,470の実証（NDA）
