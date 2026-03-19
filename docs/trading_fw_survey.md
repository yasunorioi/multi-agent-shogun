# 日米セクターETF自動売買 フレームワーク・取引APIリサーチ

> **調査日**: 2026-03-20 | **調査者**: ashigaru6 (research_001)

---

## 推奨構成

殿の要件（日米セクターETFロングショート、日次リバランス、Python）に最適な組み合わせ:

| レイヤー | 推奨 | 理由 |
|---------|------|------|
| **データ取得** | J-Quants API (日本) + yfinance (米国) | JPX公式で信頼性最高。米国はyfinanceで十分 |
| **バックテスト** | vectorbt → 本格検証は Lean/QuantConnect | 高速パラメータスイープ → イベント駆動精密検証 |
| **ライブ執行(日本)** | kabuステーションAPI (三菱UFJ eスマート証券) | 国内唯一の本格REST API。信用手数料0円 |
| **ライブ執行(米国)** | Interactive Brokers TWS API | グローバル対応、アルゴ注文、日本株もIB経由で可 |
| **リスク管理** | QuantStats + PyPortfolioOpt | パフォーマンス可視化 + ポートフォリオ最適化 |
| **口座** | 三菱UFJ eスマート証券 + IB証券 | 日本株API + 米国株API の二刀流 |

---

## 1. 証券API比較

### 実用的なAPI（個人利用可）

| 証券会社 | API種別 | 信用取引 | 手数料 | 特記 |
|---------|---------|---------|--------|------|
| **三菱UFJ eスマート証券** | REST + WebSocket (PUSH) | 対応（売建2,500+銘柄） | 信用0円 | **最有力**。発注5req/s。Professionalプラン以上で無料 |
| **Interactive Brokers** | TWS API (REST/WebSocket) | 対応（全注文種別+アルゴ） | 固定0.08% (最低JPY 80) | 最も機能豊富。日本株もTSE経由で対応。Pro口座必須 |
| **立花証券 e支店** | REST + WebSocket | 対応（2025年拡充中） | 無料 | kabuステーションの対抗馬。完全無料API |
| **楽天証券** | MarketSpeed II RSS (Excel VBA) | 対応 | - | REST APIではない。Windows+Excel必須。80件/分 |
| **SBI証券** | HyperSBI2 ローカルHTTP | 限定的 | - | 非公式。過剰アクセスでBANリスク |

### APIなし・非対応

| 証券会社 | 状況 |
|---------|------|
| 松井証券 | FX APIのみ。株式APIなし |
| マネックス証券 | TradeStation日本株は2020年終了 |
| GMOクリック証券 | APIなし。自動売買ツール利用は規約で禁止 |
| Alpaca | 米国株のみ。日本株未対応（将来拡大予定） |

---

## 2. フレームワーク比較

| FW | Stars | 日本株 | ライブ | バックテスト | ロングショート適合 | 言語 |
|----|-------|--------|-------|------------|------------------|------|
| **Lean/QuantConnect** | ~10k | IB経由可 | 対応 | 高機能 | **高** | C#/Python |
| **nautilus_trader** | ~2.5k | IB経由可 | 対応 | ナノ秒精度 | **非常に高** | Rust/Python |
| **vectorbt** | ~6.8k | データ次第 | 不可 | **超高速** | リサーチ向き | Python |
| **Backtrader** | ~14k | カスタム可 | 限定的 | イベント駆動 | 中 | Python |
| **Zipline-reloaded** | ~1.6k | カスタム要 | 不可 | コア機能 | バックテストのみ | Python |
| Freqtrade | ~47.8k | **不可** | 対応 | あり | 不適(暗号資産専用) | Python |
| Jesse | ~7.5k | **不可** | 対応 | あり | 不適(暗号資産専用) | Python |
| pybotters | ~800 | **不可** | 対応 | なし | 不適(暗号資産専用) | Python |

### 推奨段階別ツール

| 段階 | 推奨 | 理由 |
|------|------|------|
| リサーチ/高速バックテスト | vectorbt + yfinance/J-Quants | 数千パターンを秒単位でテスト |
| 本格バックテスト | Lean or nautilus_trader | スリッページ・手数料の精密モデリング |
| ライブ執行(日本株) | kabuステーションAPI直接利用 | フレームワーク経由より直接APIが確実 |
| ライブ執行(米国株) | Lean + IB | TSE含むグローバル対応 |

---

## 3. データプロバイダー比較

| プロバイダー | 日本株 | 料金 | TOPIX-17 | 信頼性 | 適合度 |
|-------------|--------|------|----------|--------|--------|
| **J-Quants API** | 対応 | Free～16,500円/月 | 要確認 | **最高**(JPX公式) | **最適** |
| **yfinance** | `.T`銘柄 | 無料 | 取得可 | 不安定(429エラー頻発) | 少数銘柄なら可 |
| **stooq.com** | `.JP`銘柄 | 無料 | 取得可 | 安定 | プロトタイプ向き |
| Alpha Vantage | 対応 | 無料25件/日 | 制約大 | 安定 | 日次運用に不足 |
| Polygon.io | **非対応** | - | - | - | 不可 |
| pandas-datareader | Stooq経由 | 無料 | 可 | メンテ低活動 | 中間ライブラリ |

### TOPIX-17 ETF 銘柄コード一覧（NEXT FUNDS シリーズ）

| コード | 業種 | コード | 業種 |
|--------|------|--------|------|
| 1617 | 食品 | 1626 | 情報通信・サービスその他 |
| 1618 | エネルギー資源 | 1627 | 電力・ガス |
| 1619 | 建設・資材 | 1628 | 運輸・物流 |
| 1620 | 素材・化学 | 1629 | 商社・卸売 |
| 1621 | 医薬品 | 1630 | 小売 |
| 1622 | 自動車・輸送機 | 1631 | 銀行 |
| 1623 | 鉄鋼・非鉄 | 1632 | 金融（除く銀行） |
| 1624 | 機械 | 1633 | 不動産 |
| 1625 | 電機・精密 | | |

---

## 4. リスク管理ライブラリ比較

| ライブラリ | Stars | 状態 | 主要機能 | 推奨度 |
|-----------|-------|------|---------|--------|
| **QuantStats** | ~6.5k | 活発 | パフォーマンス分析・可視化・HTMLティアシート | **推奨** |
| **PyPortfolioOpt** | ~5.3k | 活発 | Efficient Frontier/Black-Litterman/HRP/CVaR | **推奨** |
| **riskfolio-lib** | ~3.7k | 活発 | MVO/CVaR/BL/HRP、24種リスク指標 | 学術的用途にも |
| pyfolio-reloaded | ~576 | 活発 | ポートフォリオ分析ティアシート | 後継fork推奨 |
| empyrical-reloaded | ~99 | 活発 | Sharpe/Sortino等リスク指標計算 | 後継fork推奨 |
| ~~pyfolio~~ | ~5.7k | **死亡** | Quantopian倒産で放置 | 使うな |
| ~~empyrical~~ | ~1.4k | **低活動** | 同上 | 使うな |

---

## 5. 個人トレーダーの自動売買実例

| 事例 | API/FW | 戦略 | 成績 |
|------|--------|------|------|
| AI Deep Kabu (dogwood008) | kabuステーション + backtrader | ML株価予測 | 10ヶ月運用、収益化困難 |
| Kabuto (kokimame) | kabuステーション + **Freqtrade改造** | テクニカル | OSS公開、HyperOpt対応 |
| くじらキャピタル | kabuステーション | 板シミュレーター | プロ向け構成解説 |
| kazuhito00 | kabuステーション | **LLM活用**システムトレード | 週次公開(小規模) |
| J-Stock Auto Planner (reorome) | 独自構成 | テクニカル分析 | **2年平均+9.10%、勝率62.4%** |
| NT1123 | kabuステーション + J-Quants | VWAP乖離率セミ自動 | 東証プライム対象 |

**注目点**: セクターローテーション・ロングショートの自動化事例は公開情報としては**未発見**。機関投資家の領域。

---

## 6. 法規制・税務

### 個人の自動売買: **規制なし**

- 金商法上、個人がPythonで自動売買すること自体に許認可は不要
- HFT登録制（2018年施行）はコロケーション利用が判定基準。kabuステーションAPI経由は**対象外**

### 空売り規制

| 項目 | 内容 |
|------|------|
| アップティックルール | 前日比10%下落銘柄にのみトリガー |
| 個人適用除外 | **1回50単位以下は価格規制対象外** |
| ETF | 株式と同ルール。信用取引可能ETFなら空売り可 |
| 残高報告 | 発行済株式数の0.2%以上で報告義務（個人規模では該当しにくい） |

### 税務処理

| 項目 | 扱い |
|------|------|
| ロング+ショート損益通算 | **同一「上場株式等の譲渡所得」として通算可能** |
| 特定口座 | 信用取引も組入れ可。自動通算される |
| 配当落調整金 | 譲渡所得扱い（配当所得ではない）。売建は譲渡損として計上 |
| 繰越控除 | 3年間繰越可能（確定申告要） |
| 逆日歩 | 流動性の低いETFで発生リスクあり |

---

## 7. 口座開設の選択肢と推奨

### 推奨: 2口座体制

1. **三菱UFJ eスマート証券** — 日本株API自動売買のメイン口座
   - kabuステーションAPI利用にはProfessionalプラン以上が必要（条件クリアで無料）
   - 信用取引手数料0円、売建2,500+銘柄
   - Windows PCでkabuステーション常時起動が必要

2. **Interactive Brokers (IB証券)** — 米国株+グローバルのAPI口座
   - TWS APIで全注文種別+アルゴ注文
   - 日本株もTSE経由で取引可能（日米一元管理の選択肢）
   - 海外ブローカー扱い。確定申告は自己管理

### 代替選択肢

- **立花証券 e支店**: 完全無料API。kabuステーションの対抗馬として注目
- **IB一本化**: 日米両方をIBで管理。ただし海外ブローカーの税務処理が煩雑

---

## 参考リンク

### API・公式
- [kabuステーションAPI](https://kabu.com/company/lp/lp90.html) / [GitHub](https://github.com/kabucom/kabusapi)
- [J-Quants API](https://jpx-jquants.com/) / [Python Client](https://github.com/J-Quants/jquants-api-client-python)
- [Interactive Brokers TWS API](https://www.interactivebrokers.co.jp/)
- [立花証券 e支店 API](https://e-shiten.tachibana-sec.co.jp/)

### フレームワーク
- [Lean/QuantConnect](https://github.com/QuantConnect/Lean)
- [nautilus_trader](https://github.com/nautechsystems/nautilus_trader)
- [vectorbt](https://github.com/polakowo/vectorbt)
- [Backtrader](https://github.com/mementum/backtrader)

### リスク管理
- [QuantStats](https://github.com/ranaroussi/quantstats)
- [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt)
- [riskfolio-lib](https://github.com/dcajasn/Riskfolio-Lib)

### 実例・解説
- [Kabuto (Freqtrade改造)](https://github.com/kokimame/kabuto)
- [AI Deep Kabu](https://qiita.com/dogwood008/items/8e968c0ec6cf618ccb84)
- [PythonでFinTech講座](https://python-fin.tech/automatic-stock-trading-1/)
- [NEXT FUNDS TOPIX-17特集](https://nextfunds.jp/special/tpx17etf/)

### 法規制
- [金融庁 高速取引行為](https://www.fsa.go.jp/common/shinsei/hst/index.html)
- [JPX 空売り規制](https://www.jpx.co.jp/equities/trading/regulations/02.html)
