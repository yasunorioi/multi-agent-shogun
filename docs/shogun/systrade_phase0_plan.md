# systrade Phase 0-2 OMC絨毯爆撃 実装計画書

> **軍師分析書** | 2026-03-26 | 殿勅命 | project: systrade

---

## §1 作戦概要

### 目的
カーネル法×systrade統合分析（docs/shogun/kernel_systrade_analysis.md）で策定したPhase 0-2を、OMC（oh-my-claudecode）の絨毯爆撃で一気に実装する。

### 作戦名: **関ヶ原（棍棒の陣）**

```
Phase 0: Lasso変数選択 ────── 「棍棒を選ぶ」  ← 即日着手
Phase 1: カーネルリッジ回帰 ── 「棍棒で殴る」  ← Phase 0完了後
Phase 2: HMMレジーム検出 ──── 「戦場を読む」  ← Phase 1完了後
Phase 3: Dexter統合 ────────── 「弾を補給する」← 判断保留
```

### OMC投入戦力

| Phase | Worker数 | モデル | 爆撃パターン |
|:-----:|:--------:|:------:|:-----------:|
| 0 | 5体 | sonnet×4 + haiku×1 | 並列 |
| 1 | 3体 | sonnet×2 + haiku×1 | 並列 |
| 2 | 3体 | sonnet×2 + haiku×1 | 並列 |
| 検品 | 各Phase後1体 | opus×1 | 逐次 |

---

## §2 リポジトリ構成案

systradeリポジトリは **未存在**。shogun管理下に新規作成する。

```
/home/yasu/systrade/
├── README.md                    # プロジェクト概要
├── pyproject.toml               # uv/pip依存管理
├── .python-version              # 3.11+
├── CLAUDE.md                    # OMC worker向け指示書
│
├── data/
│   ├── raw/                     # 生データ（gitignore）
│   │   ├── yahoo/               # Yahoo Finance CSV
│   │   ├── worldbank/           # World Bank API JSON
│   │   └── mlit/                # 国交省地価公示CSV
│   ├── processed/               # 前処理済み（gitignore）
│   └── sample/                  # テスト用サンプル（git管理）
│       ├── sample_stocks.csv    # 10銘柄×100日のダミーデータ
│       └── sample_features.csv  # 10変数×100サンプルのダミーデータ
│
├── src/
│   └── systrade/
│       ├── __init__.py
│       ├── fetch/               # Phase 0: データ取得
│       │   ├── __init__.py
│       │   ├── yahoo.py         # Yahoo Finance取得
│       │   ├── worldbank.py     # World Bank API取得
│       │   └── mlit.py          # 国交省地価公示パーサー
│       ├── select/              # Phase 0: 変数選択
│       │   ├── __init__.py
│       │   └── lasso.py         # LassoCV変数選択
│       ├── predict/             # Phase 1: 非線形予測
│       │   ├── __init__.py
│       │   └── kernel_ridge.py  # カーネルリッジ回帰
│       ├── regime/              # Phase 2: レジーム検出
│       │   ├── __init__.py
│       │   └── hmm.py           # GaussianHMM
│       └── viz/                 # 可視化
│           ├── __init__.py
│           └── plots.py         # matplotlib係数プロット
│
├── tests/
│   ├── conftest.py              # pytest fixtures
│   ├── test_fetch.py
│   ├── test_lasso.py
│   ├── test_kernel.py
│   ├── test_hmm.py
│   └── test_viz.py
│
├── notebooks/                   # 探索用（git管理外）
│   └── .gitkeep
│
└── scripts/
    └── run_pipeline.py          # Phase 0-2一気通貫実行
```

### .gitignore

```
data/raw/
data/processed/
notebooks/*.ipynb
__pycache__/
*.egg-info/
.venv/
```

### pyproject.toml 依存関係

```toml
[project]
name = "systrade"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "yfinance>=0.2",          # Yahoo Finance API（無料）
    "wbgapi>=1.0",            # World Bank API（無料）
    "scikit-learn>=1.4",      # LassoCV, KernelRidge
    "hmmlearn>=0.3",          # GaussianHMM
    "pandas>=2.0",
    "numpy>=1.26",
    "matplotlib>=3.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]
```

---

## §3 Phase 0: Lasso変数選択（棍棒を選ぶ）

### 3a. OMCタスク分解

| # | Worker | モデル | タスク | 出力ファイル | 爆発半径 |
|:-:|:------:|:------:|--------|------------|:--------:|
| 0-1 | explore | haiku | リポジトリ初期化。ディレクトリ構成+pyproject.toml+CLAUDE.md作成 | 複数ファイル（scaffold） | 低 |
| 0-2 | executor | sonnet | `src/systrade/fetch/yahoo.py` — yfinanceでアジアインフラ関連銘柄の日次データ取得 | 1ファイル | 低 |
| 0-3 | executor | sonnet | `src/systrade/fetch/worldbank.py` — wbgapiでODA/FDI/建設許可/セメント消費量等の指標取得 | 1ファイル | 低 |
| 0-4 | executor | sonnet | `src/systrade/select/lasso.py` — LassoCV変数選択パイプライン | 1ファイル | 低 |
| 0-5 | executor | sonnet | `src/systrade/viz/plots.py` — Lasso係数プロット+選択変数ハイライト | 1ファイル | 低 |

### 3b. 依存関係

```
0-1 (scaffold) ──→ 0-2, 0-3, 0-4, 0-5 は並列
                     ↓ 全完了後
              テスト+検品（逐次）
```

### 3c. OMCコマンド雛形

#### Worker 0-1: Scaffold

```bash
omc team 1:claude:executor "
systradeリポジトリを /home/yasu/systrade/ に新規作成せよ。

【ディレクトリ構成】
（§2の構成をそのまま貼る）

【pyproject.toml】
（§2のtomlをそのまま貼る）

【CLAUDE.md】以下の内容で作成:
# systrade
アジアインフラ×ファンダメンタルズ投資の定量分析パイプライン。
## 鉄則
- 月額ゼロ。有料APIは使うな。yfinance, wbgapi, 国交省CSVのみ
- 1関数1責務。scikit-learnのfit/predict/transformパターンに従え
- テストはdata/sample/のダミーデータで動くこと
- 殿の哲学:「棍棒で殴れる変数」= Lassoで係数が非ゼロになる変数のみ使え
## 言語
Python 3.11+。型ヒント必須。docstringはGoogle style

【data/sample/】
sample_stocks.csv: 10銘柄×100日の日次リターン（numpy.random.seedで再現可能なダミー）
sample_features.csv: 10変数×100サンプルのダミー特徴量
"
```

#### Worker 0-2: Yahoo Finance取得

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/fetch/yahoo.py を作成せよ。

【仕様】
- yfinanceでアジアインフラ関連銘柄の日次株価を取得する関数
- fetch_stock_data(tickers: list[str], start: str, end: str) -> pd.DataFrame
- デフォルトティッカー: タイ(SCC.BK, SCCC.BK), マレーシア(YTLP.KL), フィリピン(HLCM.PS), 日本(1801.T TOTO, 6367.T ダイキン, 5401.T 日本製鉄)
- リターン列を自動計算（日次log return）
- エラーハンドリング: ティッカーが見つからない場合はwarningしてスキップ
- レート制限: time.sleep(0.5) を各リクエスト間に挿入

【テスト】
tests/test_fetch.py も作成。data/sample/sample_stocks.csv を使ったunit testを含める。
yfinanceのモックは不要（sample CSVで代替テスト可能にする設計にせよ）。

【制約】
月額ゼロ。yfinanceは無料。有料APIは絶対に使うな。
"
```

#### Worker 0-3: World Bank取得

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/fetch/worldbank.py を作成せよ。

【仕様】
- wbgapiでマクロ指標を取得する関数
- fetch_indicators(countries: list[str], indicators: dict[str,str], start_year: int, end_year: int) -> pd.DataFrame
- デフォルト国: THA, MYS, PHL, VNM, NPL, JPN
- デフォルト指標:
  NY.GDP.MKTP.KD.ZG  GDP成長率
  NE.GDI.FTOT.ZS     固定資本形成/GDP
  BX.KLT.DINV.WD.GD.ZS FDI流入/GDP
  IS.SHP.GOOD.TU      コンテナ取扱量
  DT.ODA.ODAT.GN.ZS   ODA/GNI比率
  SP.POP.GROW          人口増加率
  SP.URB.GROW          都市人口増加率
- 欠損値処理: 前方補完(ffill) + 後方補完(bfill)

【テスト】
tests/test_fetch.py に追記。data/sample/sample_features.csv を使ったunit test。

【制約】
wbgapiは無料。World Bank Open Data APIキー不要。
"
```

#### Worker 0-4: Lasso変数選択

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/select/lasso.py を作成せよ。

【仕様】
- LassoCVで株価リターンの説明変数を自動選択する関数
- select_features(X: pd.DataFrame, y: pd.Series, cv: int = 5) -> LassoResult
- LassoResult = NamedTuple(selected_features: list[str], coefficients: dict[str,float], alpha: float, r2_score: float)
- 前処理: StandardScaler で標準化（スケール差でLassoが歪むのを防止）
- 交差検証でalphaを自動選択（LassoCV）
- 非ゼロ係数の変数名と係数値を返す
- 補助関数: summarize(result: LassoResult) -> str  人間が読める要約文

【殿の哲学をコードに焼け】
# 棍棒で殴れる変数 = 係数が非ゼロの変数
# 係数が0 = 殴っても効かない変数。自動消去。
# Lasso正則化は殿の投資哲学の数学的表現である。

【テスト】
tests/test_lasso.py を作成。
- sample_features.csv + ランダムターゲットでfit/predictが動くこと
- 明らかに無関係な変数（ランダムノイズ列）が選択されないこと
- selected_featuresが空でないこと

【制約】
scikit-learn LassoCVのみ使用。追加ライブラリ禁止。
"
```

#### Worker 0-5: 可視化

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/viz/plots.py を作成せよ。

【仕様】
- Lasso係数をプロットする関数
- plot_lasso_coefficients(result: LassoResult, save_path: str | None = None) -> matplotlib.figure.Figure
  - 横軸: 変数名、縦軸: 係数値
  - 非ゼロ係数を赤、ゼロ係数をグレーで色分け
  - タイトル: 'Lasso Feature Selection (α={alpha:.4f}, R²={r2:.3f})'
- plot_feature_importance(result: LassoResult, save_path: str | None = None) -> matplotlib.figure.Figure
  - 係数の絶対値でソートした横棒グラフ（非ゼロのみ）
  - タイトル: '棍棒で殴れる変数 Top N'

【テスト】
tests/test_viz.py を作成。
- Figure オブジェクトが返ることを確認
- save_path指定時にファイルが生成されることを確認（tmpdir使用）

【制約】
matplotlib のみ。plotly等は使うな。
"
```

### 3d. Phase 0 検品（お針子観点）

```bash
omc team 1:claude:critic "
/home/yasu/systrade/ のPhase 0成果物を検品せよ。

【検品項目】
1. pyproject.toml の依存関係に有料ライブラリが混入していないか（月額ゼロ違反）
2. 全テストが pytest で通るか（pytest tests/ -v）
3. lasso.py: LassoCVのcv値がハードコードされていないか（引数で変更可能か）
4. lasso.py: StandardScalerが適用されているか（スケール差によるLasso歪み防止）
5. fetch/yahoo.py: レート制限(sleep)が入っているか
6. fetch/worldbank.py: 欠損値処理が実装されているか
7. viz/plots.py: 非ゼロ/ゼロの色分けが正しく動作するか
8. CLAUDE.md: 殿の哲学（棍棒で殴れる変数）が記載されているか
9. data/sample/: テスト用ダミーデータが再現可能か（seed固定）
10. 型ヒントが全関数に付いているか
"
```

---

## §4 Phase 1: カーネルリッジ回帰（棍棒で殴る）

### 4a. OMCタスク分解

| # | Worker | モデル | タスク | 出力ファイル |
|:-:|:------:|:------:|--------|------------|
| 1-1 | executor | sonnet | `src/systrade/predict/kernel_ridge.py` — KernelRidge回帰パイプライン | 1ファイル |
| 1-2 | executor | sonnet | `src/systrade/fetch/mlit.py` — 国交省地価公示CSVパーサー | 1ファイル |
| 1-3 | explore | haiku | `tests/test_kernel.py` + `tests/test_fetch.py`追記 | 2ファイル |

### 4b. OMCコマンド雛形

#### Worker 1-1: カーネルリッジ回帰

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/predict/kernel_ridge.py を作成せよ。

【仕様】
- scikit-learn KernelRidgeで非線形予測を行う関数
- fit_kernel_ridge(X: pd.DataFrame, y: pd.Series, kernel: str = 'rbf', alpha: float = 0.1, gamma: float = 0.01) -> KernelRidgeResult
- KernelRidgeResult = NamedTuple(model: KernelRidge, r2_train: float, r2_cv: float, best_params: dict)
- GridSearchCV でalpha, gammaの最適値を探索（小さいグリッドでよい）
  - alpha: [0.01, 0.1, 1.0, 10.0]
  - gamma: [0.001, 0.01, 0.1, 1.0]
- predict(model, X_new) -> pd.Series  予測関数
- transfer_predict(model, X_source_domain, X_target_domain) -> pd.Series
  - 日本(source)で学習 → アジア(target)に適用する転移関数
  - 注意: ドメインシフトの警告を出す（R²が0.3以下なら warning）

【用途】
日本の新幹線沿線地価データで学習し、タイMRT/ベトナムメトロの沿線地価を予測する。
カーネルリッジ回帰は少量データの非線形予測に最適（Ide-Yairi 2010）。

【制約】
scikit-learn KernelRidge + GridSearchCV のみ。
"
```

#### Worker 1-2: 国交省地価公示パーサー

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/fetch/mlit.py を作成せよ。

【仕様】
- 国土交通省 地価公示/地価調査のCSVをパースする関数
- parse_land_price(csv_path: str) -> pd.DataFrame
  - 列: year, prefecture, city, address, land_price_per_sqm, lat, lon, land_use, nearest_station, station_distance_m
- filter_hsr_corridor(df: pd.DataFrame, line_name: str, buffer_km: float = 5.0) -> pd.DataFrame
  - 新幹線路線名で絞り込み（東海道/山陽/九州/北海道）
  - 路線からbuffer_km以内の地点を抽出
  - 注: 路線座標はハードコードの代表点リスト（API不要）

【データソース】
国交省地価公示: https://www.land.mlit.go.jp/webland/download.html
CSV形式。Shift-JIS→UTF-8変換が必要。

【テスト】
data/sample/ にダミーCSV（5行）を追加してテスト。

【制約】
pandasのみ。GIS系ライブラリ(geopandas等)は使うな。距離計算はhaversine公式を自前実装。
"
```

### 4c. Phase 1 検品観点

1. KernelRidgeのGridSearchCVが正しく動作するか
2. transfer_predictでドメインシフト警告が出るか（R²<0.3で warning）
3. mlit.py: Shift-JIS→UTF-8変換が正しいか
4. mlit.py: haversine距離計算が正確か（東京→大阪で約400kmになるか）
5. 全テストがpytest通過するか

---

## §5 Phase 2: HMMレジーム検出（戦場を読む）

### 5a. OMCタスク分解

| # | Worker | モデル | タスク | 出力ファイル |
|:-:|:------:|:------:|--------|------------|
| 2-1 | executor | sonnet | `src/systrade/regime/hmm.py` — GaussianHMMレジーム検出 | 1ファイル |
| 2-2 | executor | sonnet | `scripts/run_pipeline.py` — Phase 0-2一気通貫スクリプト | 1ファイル |
| 2-3 | explore | haiku | `tests/test_hmm.py` + 統合テスト | 2ファイル |

### 5b. OMCコマンド雛形

#### Worker 2-1: HMMレジーム検出

```bash
omc team 1:claude:executor "
/home/yasu/systrade/src/systrade/regime/hmm.py を作成せよ。

【仕様】
- hmmlearn GaussianHMMで市場レジームを検出する関数
- detect_regimes(returns: pd.Series, n_regimes: int = 3, n_iter: int = 100) -> RegimeResult
- RegimeResult = NamedTuple(regimes: pd.Series, transition_matrix: np.ndarray, means: np.ndarray, variances: np.ndarray, regime_labels: dict[int, str])
- レジームの自動ラベリング:
  - 平均リターン最大 → 'trend_up'（上昇トレンド）
  - 分散最大 → 'volatile'（暴落/調整）
  - それ以外 → 'range'（レンジ相場）
- current_regime(result: RegimeResult) -> str  最新のレジームを返す
- plot_regimes(returns: pd.Series, result: RegimeResult, save_path: str | None = None) -> Figure
  - 株価チャートの背景をレジームで色分け（緑=trend_up, 黄=range, 赤=volatile）

【用途】
GA適合度関数(fit3)の「トレンド/レンジ相場自動切替」をHMMで実装する。
SLDSの考え方（Ide-Yairi 2010 §3.1）に基づく。

【制約】
hmmlearn GaussianHMM のみ。PyMC等のベイズライブラリは使うな。
"
```

#### Worker 2-2: 統合パイプライン

```bash
omc team 1:claude:executor "
/home/yasu/systrade/scripts/run_pipeline.py を作成せよ。

【仕様】
- Phase 0-2を一気通貫で実行するCLIスクリプト
- argparse で以下のサブコマンド:
  - fetch: データ取得（yahoo + worldbank）
  - select: Lasso変数選択
  - predict: カーネルリッジ回帰
  - regime: HMMレジーム検出
  - all: 全Phase実行
- 各ステップの結果をdata/processed/に保存（pickle + CSV）
- ログ出力: logging.INFO レベルで進捗表示
- --dry-run: データ取得をスキップしてsampleデータで実行

【使用例】
python scripts/run_pipeline.py all --dry-run     # サンプルデータで全Phase
python scripts/run_pipeline.py fetch              # データ取得のみ
python scripts/run_pipeline.py select --output results/  # 変数選択+結果出力

【制約】
標準ライブラリ + 既存のsrc/systrade/ モジュールのみ使用。
"
```

### 5c. Phase 2 検品観点

1. HMMのfit/predictがsample dataで動くか
2. レジーム自動ラベリングが正しいか（平均リターン/分散の大小関係）
3. transition_matrixの行和が1.0になるか
4. run_pipeline.py --dry-run が全Phase通過するか
5. 全テストがpytest通過するか

---

## §6 OMC投入スケジュール

### 6a. 実行順序

```
Day 1 午前: Phase 0 絨毯爆撃
  │
  ├─ [0-1] scaffold ──────→ 完了待ち（5分）
  │
  ├─ [0-2] yahoo.py   ─┐
  ├─ [0-3] worldbank.py ├─→ 並列実行（各10-15分）
  ├─ [0-4] lasso.py    ─┤
  └─ [0-5] plots.py   ─┘
  │
  ├─ [検品] critic ────────→ 逐次（10分）
  ├─ [修正] 検品不合格分を再投入
  │
Day 1 午後: Phase 1 絨毯爆撃
  │
  ├─ [1-1] kernel_ridge.py ─┐
  ├─ [1-2] mlit.py          ├→ 並列（各10-15分）
  └─ [1-3] tests            ─┘
  │
  ├─ [検品] critic
  │
Day 2 午前: Phase 2 絨毯爆撃
  │
  ├─ [2-1] hmm.py          ─┐
  ├─ [2-2] run_pipeline.py  ├→ 並列（各10-15分）
  └─ [2-3] tests            ─┘
  │
  ├─ [検品] critic
  ├─ [統合テスト] pytest + run_pipeline.py --dry-run
  │
Day 2 午後: 軍師レビュー + 殿への報告
```

### 6b. 見積もり

| 項目 | 見積もり |
|------|---------|
| OMC Worker 総数 | 11体 + 検品3体 = 14体 |
| 所要時間 | 実働2日（並列実行で圧縮） |
| コスト | OMC利用料のみ（データAPI月額ゼロ） |
| 生成コード量 | 約800-1000行（テスト含む） |
| ファイル数 | 約20ファイル |

---

## §7 CLAUDE.md（OMC Worker向け指示書）

```markdown
# systrade

アジアインフラ×ファンダメンタルズ投資の定量分析パイプライン。

## 殿の哲学

「棍棒で殴れるファンダメンタルズ」—— ICTのユニコーン探しではなく、
物理の動き（鉄道・道路・建材）が嘘をつかない領域で棍棒を振る。

Lasso正則化の係数が0になる変数 = 殴っても効かない変数。自動消去。
これが殿の投資哲学の数学的表現である。

## 鉄則

1. **月額ゼロ**: 有料APIは使うな。yfinance, wbgapi, 国交省CSVのみ
2. **1関数1責務**: scikit-learnのfit/predict/transformパターンに従え
3. **テスト必須**: data/sample/のダミーデータで動くこと。外部API不要で動くテストを書け
4. **型ヒント必須**: Python 3.11+。全関数にtype hints。Google style docstring
5. **結果はNamedTuple**: 辞書ではなくNamedTupleで返せ。属性アクセスで可読性確保
6. **過剰実装禁止**: 依頼された1ファイルだけ作れ。他のファイルに手を出すな

## 依存ライブラリ

- yfinance: Yahoo Finance（無料）
- wbgapi: World Bank API（無料）
- scikit-learn: LassoCV, KernelRidge, GridSearchCV
- hmmlearn: GaussianHMM
- pandas, numpy, matplotlib

## テスト

pytest tests/ -v で全テスト通過すること。
外部APIに依存するテストは書くな。data/sample/ のダミーデータを使え。
```

---

## §8 お針子検品の統合チェックリスト

### Phase横断の検品観点

| # | チェック項目 | Phase | 重要度 |
|:-:|------------|:-----:|:------:|
| Q1 | 有料APIが混入していないか | 全Phase | **致命** |
| Q2 | 全テストがpytest通過するか | 全Phase | **致命** |
| Q3 | 型ヒントが全関数に付いているか | 全Phase | 高 |
| Q4 | NamedTupleで結果を返しているか | 全Phase | 中 |
| Q5 | StandardScalerがLasso前に適用されているか | Phase 0 | **致命** |
| Q6 | LassoCVのcvが引数で変更可能か | Phase 0 | 中 |
| Q7 | yfinanceにsleepが入っているか | Phase 0 | 高 |
| Q8 | KernelRidgeのGridSearchCVが動作するか | Phase 1 | 高 |
| Q9 | ドメインシフト警告(R²<0.3)が実装されているか | Phase 1 | 中 |
| Q10 | HMM遷移行列の行和が1.0か | Phase 2 | 高 |
| Q11 | レジーム自動ラベリングのロジックが正しいか | Phase 2 | 高 |
| Q12 | run_pipeline.py --dry-run が全Phase通過するか | Phase 2 | **致命** |

### お針子向け検品コマンド

```bash
# Phase 0 検品
cd /home/yasu/systrade && pip install -e ".[dev]" && pytest tests/ -v

# Phase 1 検品
pytest tests/test_kernel.py tests/test_fetch.py -v

# Phase 2 検品（統合テスト含む）
pytest tests/ -v && python scripts/run_pipeline.py all --dry-run
```

---

## §9 Phase 3 Dexter統合の判断

### 判断基準

| 条件 | Phase 3着手 | Phase 0-2で止める |
|------|:----------:|:-----------------:|
| Phase 0-2の結果が実用的 | - | ◎ まず使ってみる |
| アジア市場データが不足 | ◎ Dexter(米国株)で補完 | - |
| DCF分析が必要な段階 | ◎ | - |
| 月額コストが問題 | - | ◎ Dexter API有料 |

### 軍師の判断

**Phase 0-2で十分。Phase 3は殿が実際にPhase 0-2の結果を見てから判断。**

理由:
1. Phase 0-2は月額ゼロで完結する
2. Dexterは米国市場中心であり、アジアインフラ戦略の本丸には直接貢献しない
3. 「使ってみてから判断」がマクガイバー精神に合致
4. Dexter統合はPhase 0-2のパイプラインが安定してからでも遅くない

---

## §10 総合評価

### 軍師の所見

```
┌──────────────────────────────────────────────────────────┐
│ OMC 14体で2日。これは絨毯爆撃ではなく精密爆撃である。     │
│                                                            │
│ 各Workerの爆発半径は「1ファイル」に限定。                  │
│ 全弾がscikit-learn 35行以内の小さなモジュール。            │
│ お針子が1発でも不発弾を見つければ再投入。                  │
│                                                            │
│ Phase 0のLasso 20行が動いた瞬間、                          │
│ 殿の「棍棒で殴れる変数」が数値として目の前に並ぶ。        │
│ それが本作戦の戦略的価値である。                            │
└──────────────────────────────────────────────────────────┘
```

---

*以上。14体の精密爆撃で棍棒を鍛え上げる。殿の号令を待つ。*
