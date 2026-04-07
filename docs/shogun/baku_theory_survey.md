# 獏宇宙論・理論基盤サーベイ

> **date**: 2026-03-15 | **analyst**: ashigaru6（部屋子）
> **task**: subtask_901 (cmd_409) | **status**: complete

---

## 殿の直感 × 既存理論 対応表（エグゼクティブサマリ）

| # | 殿の直感 | 最も近い既存理論 | 一致度 | 境界条件（壊れるとき） |
|---|---------|----------------|--------|---------------------|
| 1 | 情報は高きから低きへ流れる | Friston自由エネルギー原理 + 情報採餌理論 | ◎ | エージェントが世界モデルを持たない場合は勾配が定義不能 |
| 2 | 距離ではなく角度で測る | TDA + コサイン類似度 + Hopfield連想記憶 | ○ | 次元数が極端に高い/低いと角度の意味が崩壊 |
| 3 | 偏微分方程式で局所的に解ける | 熱拡散方程式 + グラフ拡散カーネル | ◎ | グラフが非連結（孤立ノード）なら拡散しない |
| 4 | 方向性のある爆発 | Lévy flight + Bayesian最適化 + 有向探索 | ◎ | 資源が均一分布のとき方向性の優位が消える |
| 5 | 誤差空間が狭い | 多様体仮説 + 知識空間理論 | ◎ | 興味が広すぎると内在次元が膨張し古典手法が破綻 |

---

## §1 「情報は高きから低きへ流れる」

### 1.1 Fristonの自由エネルギー原理（Free Energy Principle）

- **著者**: Karl Friston (2006〜)
- **出典**: Friston, K. "The free-energy principle: a unified brain theory?" *Nature Reviews Neuroscience*, 2010
- **核心**: 生物は「予測誤差（サプライズ）」を最小化するよう行動する。知識の穴 = 予測誤差が高い領域 = 自由エネルギーが高い。エージェントは自由エネルギーを下げる方向に動く → **情報が高きから低きへ流れる、と同値**
- **能動推論（Active Inference）**: 予測誤差を下げる方法は2つ — (a)知覚を更新する（学習）、(b)行動で環境を変える（探索）。好奇心は「認識的価値（epistemic value）」として定式化され、**不確実性が高い領域への探索衝動**を生む
- **殿の直感との対応**: 「知識の穴に情報が流れ込む」= 自由エネルギー勾配に沿った降下。設計書§3の「穴検出 = density_gapが大きい領域」は自由エネルギーが高い領域の近似

### 1.2 Shannon情報理論

- **著者**: Claude Shannon (1948)
- **出典**: Shannon, C. "A Mathematical Theory of Communication", *Bell System Technical Journal*, 1948
- **核心**: 情報量 = 驚き（surprise） = -log P(x)。確率が低い事象ほど情報量が高い
- **エントロピー**: H = -Σ p(x) log p(x)。知識の穴 = 高エントロピー領域 = 不確実性が高い
- **殿の直感との対応**: 情報が「流れる」のは、エントロピー差が駆動力。熱力学の第二法則と同構造

### 1.3 情報採餌理論（Information Foraging Theory）

- **著者**: Peter Pirolli & Stuart Card (1999, Xerox PARC)
- **出典**: Pirolli, P. & Card, S. "Information Foraging", *Psychological Review*, 1999
- **核心**: 人間の情報探索行動は動物の採餌行動と同じ最適化問題。**情報の匂い（information scent）** の勾配に沿って移動する
- **殿の直感との対応**: 「高きから低きへ」の「高き」= 情報の匂いが強い方向。設計書の共起行列PMI値がまさに「匂い」の定量化

### 1.4 境界条件（直感が壊れるとき）

- エージェントが世界モデルを持たない場合（完全な無知）→ 勾配が定義できない → ランダム探索しかない
- 自由エネルギー最小化は**局所最適に陥る**リスク（確認バイアスと同構造）
- 設計書§3のフォールバック（直近キーワード検索）はこの境界条件への対処として妥当

---

## §2 「距離ではなく角度で測る」

### 2.1 コサイン類似度とTDA

- **TDA（位相的データ解析）**: 高次元データの「形状」を捉える。距離よりも位相的特徴（穴、ループ、連結成分）が本質
- **出典**: Edelsbrunner, H. & Harer, J. "Persistent Homology — a Survey", *Contemporary Mathematics*, 2008
- **核心**: パーシステントホモロジーは「スケールに依存しない構造」を検出。距離の絶対値ではなく、**構造的な関係性**（穴が存在するか、連結しているか）が重要
- **殿の直感との対応**: 「温室制御と脳科学が距離は遠いが角度が近い」= 位相的に同じ構造を持つ。設計書§4の偏角エンジン（cos類似度）はTDAの簡易近似

### 2.2 Hopfieldネットワークのエネルギー地形

- **著者**: John Hopfield (1982, 2024年ノーベル物理学賞)
- **核心**: 連想記憶はエネルギー地形のアトラクター。類似パターンは同じ盆地に落ちる。「距離」ではなく「同じ盆地にいるかどうか」が想起の鍵
- **殿の直感との対応**: 設計書Phase 0の共起行列はHopfieldの重み行列と構造的に同値。Phase 0-Aプロトタイプで既に実装されている

### 2.3 境界条件

- 次元数が極端に高い場合、全てのベクトルが直交に近づく（次元の呪い） → 角度の差が消える
- 次元数が極端に低い（2-3次元）場合、角度の分解能が粗すぎて区別できない
- 設計書§7.2の「自己強化ループ」リスクはこの境界条件に関連。初期の角度計算精度が低いと収束方向を誤る

---

## §3 「偏微分方程式で局所的に解ける」

### 3.1 熱拡散方程式（Heat Equation）

- **数式**: ∂u/∂t = α∇²u（温度u、拡散係数α、ラプラシアン∇²）
- **核心**: 全体の温度分布が不明でも、**隣接点との差分（勾配）だけで局所的に温度変化を計算できる**。まさに殿の直感そのもの
- **情報空間への応用**: グラフ上の拡散カーネル（Graph Diffusion Kernel）。ノード間の情報伝播を熱拡散でモデル化
- **出典**: Kondor, R. & Lafferty, J. "Diffusion Kernels on Graphs and Other Discrete Structures", *ICML*, 2002

### 3.2 グラフ拡散と情報伝播

- SNSの情報拡散モデルで熱拡散方程式が直接使われている（Li et al., 2022, Information Sciences）
- **グラフ拡散カーネル**: K = exp(-βL)（Lはグラフラプラシアン、βは拡散時間）
- 設計書§3の「隣接キーワードの平均DF」はグラフラプラシアンの離散近似

### 3.3 殿の直感が「正しい」理論的根拠

- **ガウスの定理の離散版**: 離散グラフ上では、ノードの情報密度変化 = 隣接ノードとの密度差の総和
- 設計書§3.4の穴検出SQL（neighbor_df - df = density_gap）は**離散ラプラシアンそのもの**
- 全体の地図（全キーワードの完全な関係性）がなくても、共起行列で定義された「隣接」だけで穴を検出できる

### 3.4 境界条件

- グラフが非連結の場合（孤立したキーワードクラスタ）、拡散が到達しない
- 設計書§7.4の「共起行列のスパース問題」がまさにこの境界条件
- `HAVING COUNT(*) >= 3` の閾値は連結性の保証に必要

---

## §4 「方向性のある爆発」

### 4.1 Lévy flight（レヴィ飛行）

- **出典**: Viswanathan, G.M. et al. "Optimizing the success of random searches", *Nature*, 1999
- **核心**: 短い移動を多数 + 稀に長距離ジャンプ。ステップ長がべき乗分布 P(l) ∝ l^(-μ)
- **最適探索**: 資源がまばらで位置不明のとき、μ≈2（逆二乗則）のLévy walkが最適
- **殿の直感との対応**: 「方向性のある爆発」= Lévy flightの長距離ジャンプ。設計書のセレンディピティ枠（ランダムウォーク3歩）はLévy的な探索

### 4.2 Bayesian最適化の獲得関数

- **Expected Improvement (EI)**: 現在の最良値からの改善期待値を最大化。不確実性が高い領域も探索
- **出典**: Mockus, J. "Bayesian Approach to Global Optimization", 1989
- **核心**: EI = 利用（高い予測値）+ 探索（高い不確実性）のバランスを**自動的に**制御
- **殿の直感との対応**: 「好奇心にはコンパスが要る」= 獲得関数がコンパス。ξパラメータが探索の「方向性」を決める

### 4.3 有向探索 vs ランダム探索（Wilson et al., 2014）

- **出典**: Wilson, R.C. et al. "Humans use directed and random exploration to solve the explore-exploit dilemma", *Journal of Experimental Psychology*, 2014
- **核心**: 人間は2種類の探索を**併用**する — (a)情報ボーナスによる有向探索、(b)ノイズによるランダム探索
- **殿の直感との対応**: 設計書の「勾配エンジン（有向）+ セレンディピティ枠（ランダム）」はこの二重構造と一致

### 4.4 Schmidhuberの圧縮進歩理論

- **著者**: Jürgen Schmidhuber (2008)
- **出典**: Schmidhuber, J. "Driven by Compression Progress", *Anticipatory Behavior in Adaptive Learning Systems*, 2009
- **核心**: 好奇心 = 圧縮進歩の一階微分。「学習曲線の傾きが急な方向」に向かう。既に完全に圧縮できるデータ（退屈）も、まったく圧縮できないデータ（ノイズ）も回避
- **殿の直感との対応**: 「無秩序な探索は自然破壊」= ノイズを追いかけても圧縮進歩ゼロ。方向性 = 圧縮進歩が最大の方角

### 4.5 Pathak ICM（Intrinsic Curiosity Module）

- **著者**: Pathak, D. et al. (2017, UC Berkeley)
- **出典**: Pathak et al. "Curiosity-driven Exploration by Self-Supervised Prediction", *ICML*, 2017
- **核心**: 内部報酬 = 次状態の予測誤差。特徴空間で予測誤差を計算し、制御不能なノイズを排除
- **殿の直感との対応**: 設計書§3.1の「穴 vs 無関心」の区別と同じ発想。ノイズ（無関心）は予測誤差が高くても好奇心の対象にしない

### 4.6 境界条件

- 資源が均一分布のとき、方向性の優位が消える（ブラウン運動で十分）
- 殿の知識空間は明確に偏在しているので、この境界条件には当たらない

---

## §5 「誤差空間が狭い」

### 5.1 多様体仮説（Manifold Hypothesis）

- **核心**: 高次元データは実際には低次元多様体上に存在する
- **実例**: ImageNet画像は150,528次元だが、内在次元は26〜43（Pope et al., ICLR 2021）
- **出典**: Pope, P. et al. "The Intrinsic Dimension of Images and Its Relevance to Learning", *ICLR*, 2021
- **殿の直感との対応**: 「個人の知識空間は低次元」= 多様体仮説そのもの。殿の興味は農業IoT・LLM制御・マルチエージェント等の数軸に集約される

### 5.2 知識空間理論（Knowledge Space Theory）

- **著者**: Jean-Paul Doignon & Jean-Claude Falmagne (1985)
- **出典**: Doignon & Falmagne, "Knowledge Spaces", Springer, 1999
- **核心**: 知識は前提関係で構造化される。全てのサブセットが知識状態ではなく、**前提関係で許容される状態のみ**が存在。これにより知識空間の実効次元は大幅に縮小
- **殿の直感との対応**: 「だから古典数理で十分」= 知識空間の実効次元が低いなら、SQLiteの共起行列+コサイン類似度で十分。ニューラルネットや高次元埋め込みは不要

### 5.3 内在次元推定

- 手法: k近傍法（Facco et al., 2017）、PCA、MLE
- **出典**: Facco, E. et al. "Estimating the intrinsic dimension of datasets by a minimal neighborhood information", *Scientific Reports*, 2017
- **実用的示唆**: 設計書Phase 0の共起行列（76,652件, 17,574キーワード）の内在次元を推定すれば、殿の知識空間が本当に低次元かを検証可能

### 5.4 境界条件

- 興味が爆発的に広がると内在次元が膨張 → 古典手法が破綻
- ただし殿のMemory MCPの観察数（~60件）からみて、現時点では低次元に収まる
- 設計書§8の遺伝的ドリフトモデルは、蔵書100件超（= 次元膨張後）のフォールバック

---

## §6 理論同士の関係性マップ

```
【同じことを別の言葉で言っている理論群】

Friston自由エネルギー ←→ Shannon エントロピー ←→ 熱力学第二法則
  │ 予測誤差最小化          情報量=驚き            エントロピー増大
  │    ↕                      ↕                       ↕
  │ 同値：全てF = E - TS の変形（自由エネルギー = 内部エネルギー - 温度×エントロピー）
  │
  ├── 能動推論 ←→ Bayesian最適化（獲得関数）←→ 情報採餌理論
  │     認識的価値    Expected Improvement        情報の匂い
  │     「不確実性が高い方へ」が共通原理
  │
  ├── Schmidhuber圧縮進歩 ←→ Pathak ICM
  │     圧縮進歩率最大化       予測誤差（特徴空間）
  │     「学習が進む方向」vs「ノイズ」の区別が共通
  │
  ├── Lévy flight ←→ 有向+ランダム探索（Wilson 2014）
  │     長距離ジャンプ     ランダム探索成分
  │     短距離クラスタ     有向探索成分
  │
  └── 熱拡散方程式 ←→ グラフラプラシアン ←→ 設計書§3穴検出SQL
        ∂u/∂t = α∇²u    離散ラプラシアン     neighbor_df - df

【独立した視点を提供する理論】

多様体仮説 ——— 「なぜ古典手法で十分か」の根拠
知識空間理論 ——— 「前提関係が次元を圧縮する」メカニズム
TDA ——— 「形状で空間を捉える」= 距離依存しない
Hopfield ——— 「共起行列 = 重み行列」の理論的根拠
```

---

## §7 設計書への示唆

| 設計書の要素 | 理論的根拠 | 強化すべき点 |
|------------|----------|------------|
| density_gap（§3.4） | 離散ラプラシアン（熱拡散方程式） | 理論的に正当。閾値は連結性保証の観点で設定 |
| cos類似度（§4） | TDA + 多様体仮説 | 高次元で角度が潰れるリスク → TF-IDF正規化で対処（§7.3） |
| ランダムウォーク（§3.6） | Lévy flight | 現在の3歩は短い。Lévy的べき分布で歩数を可変にすると探索効率向上 |
| TONO_INTERESTS置換 | Friston能動推論 | density_gap = 自由エネルギーの近似。理論的に妥当 |
| セレンディピティ枠 | Wilson有向+ランダム探索 | 1/5枠は人間の実験結果と整合 |
| 穴 vs 無関心の区別（§3.1） | Pathak ICM | 「制御不能なノイズの排除」と同じ設計思想 |
| 遺伝的ドリフト（§8） | 進化的計算 | 小集団ドリフトの問題は理論通り。蔵書100件超で再検討が妥当 |

---

## §8 追加で検討すべき理論（調査中に発見）

1. **Landauerの原理**: 情報消去に最低 kBT ln(2) の熱が必要 → 「知識を忘れる」にもコストがある。獏の蔵書GCルールの理論的根拠になりうる
2. **Maxwell's Demon**: 情報を使ってエントロピーを下げる存在 → 獏そのもの。没日録から情報を取り出して殿の知識のエントロピーを下げる
3. **情報場理論（IFT, Enßlin 2009〜）**: ベイズ推論を場の理論として定式化。共起行列を「場」として扱う理論的枠組み

---

Sources:
- [Free energy principle - Wikipedia](https://en.wikipedia.org/wiki/Free_energy_principle)
- [Exploration, novelty, surprise, and free energy minimization (Frontiers, 2013)](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2013.00710/full)
- [Active Inference and Learning (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5167251/)
- [Shannon Holes, Black Holes, and Knowledge (MDPI)](https://www.mdpi.com/2673-9585/4/3/19)
- [How Shannon's Entropy Quantifies Information (Quanta)](https://www.quantamagazine.org/how-claude-shannons-concept-of-entropy-quantifies-information-20220906/)
- [Schmidhuber - Driven by Compression Progress (arXiv)](https://arxiv.org/abs/0812.4360)
- [Pathak - Curiosity-driven Exploration (ICML 2017)](https://pathak22.github.io/noreward-rl/resources/icml17.pdf)
- [Lévy flight foraging hypothesis - Wikipedia](https://en.wikipedia.org/wiki/L%C3%A9vy_flight_foraging_hypothesis)
- [Optimal foraging: Lévy walks (J. Theoretical Biology)](https://www.sciencedirect.com/science/article/abs/pii/S0022519314003051)
- [Topological Data Analysis (Frontiers, 2021)](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2021.667963/full)
- [Information Foraging Theory (NN/g)](https://www.nngroup.com/articles/information-foraging/)
- [Pirolli - Information Foraging (ResearchGate)](https://www.researchgate.net/profile/Peter-Pirolli/publication/229101074_Information_Foraging/links/02bfe50f098acc0ea8000000/Information-Foraging.pdf)
- [Maxwell's demon - Wikipedia](https://en.wikipedia.org/wiki/Maxwell's_demon)
- [Information: From Maxwell's demon to Landauer's eraser (Physics Today)](https://physicstoday.aip.org/features/information-from-maxwells-demon-to-landauers-eraser)
- [Bayesian Optimization (Distill.pub)](https://distill.pub/2020/bayesian-optimization/)
- [Exploration Strategies in Deep RL (Lil'Log)](https://lilianweng.github.io/posts/2020-06-07-exploration-drl/)
- [Wilson et al. - Directed and Random Exploration (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5635655/)
- [Intrinsic Dimension of Images (ICLR 2021)](https://openreview.net/pdf?id=XJk19XzGq2J)
- [Intrinsic Dimension Estimation (Nature Scientific Reports)](https://www.nature.com/articles/s41598-017-11873-y)
- [Knowledge Space Theory - Wikipedia](https://en.wikipedia.org/wiki/Knowledge_space)
- [Hopfield network - Wikipedia](https://en.wikipedia.org/wiki/Hopfield_network)
- [Graph Diffusion Kernels (Oxford)](https://www.blopig.com/blog/2019/02/kernel-methods-are-a-hot-topic-in-network-feature-analysis/)
- [Information Field Theory (arXiv)](https://arxiv.org/pdf/2508.17269)
