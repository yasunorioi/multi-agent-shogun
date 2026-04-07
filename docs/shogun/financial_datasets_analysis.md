# financial-datasets MCP Server 分析 — 日米間影響分析への適用評価

> **Version**: 1.0 | **Date**: 2026-04-07
> **Author**: 軍師（将軍直接指令）
> **対象**: https://github.com/financial-datasets/mcp-server
> **API提供元**: financialdatasets.ai

---

## 総合評価

| 項目 | スコア |
|------|:------:|
| **総合評価** | **4 / 10** |
| **Go/No-Go** | **Conditional No-Go（現時点では導入不要）** |

**一言**: 米国株の財務データAPIとしては良質だが、日本市場カバレッジが致命的に不足。殿の「日米間影響分析」という主目的に対しては片翼飛行。既存ツール(Crucix+YFinance)の方がカバレッジ広く、月額ゼロ。

---

## 1. データカバレッジ評価

### 1.1 全体像

| 項目 | 内容 |
|------|------|
| ティッカー数 | 17,325+ |
| 履歴深度 | 30年+(Pro以上)、3年(Developer) |
| 対象市場 | **米国のみ（SEC管轄）** |
| 更新頻度 | リアルタイム(価格)、四半期(財務) |

### 1.2 提供エンドポイント（server.py実読）

| エンドポイント | 内容 | 日米分析での価値 |
|--------------|------|:---------------:|
| `get_income_statements` | 損益計算書(annual/quarterly/ttm) | ◎ 米国側 |
| `get_balance_sheets` | 貸借対照表 | ◎ 米国側 |
| `get_cash_flow_statements` | CF計算書 | ◎ 米国側 |
| `get_current_stock_price` | 現在株価(snapshot) | ○ |
| `get_historical_stock_prices` | 過去株価(min/hour/day/week/month) | ○ |
| `get_company_news` | 企業ニュース | △ |
| `get_sec_filings` | SEC提出書類(10-K/10-Q/8-K等) | ◎ ADR限定 |
| crypto系 × 4 | 暗号通貨価格 | ✕ 無関係 |

### 1.3 日本市場カバレッジ — 致命的ギャップ

**実機検証結果:**
- `ticker=TM`（トヨタADR）→ 401 Unauthorized（APIキー必要だがティッカー自体は認識）
- `ticker=7203.T`（TSE形式）→ **400 Bad Request（フォーマット自体が非対応）**

**結論**: TSEティッカー形式は完全非対応。日本株はADR銘柄のみ。

**ADR経由でアクセス可能な日本企業（推定20-30社）:**

| ADR | 日本企業 | セクター |
|-----|---------|---------|
| TM | トヨタ | 自動車 |
| SONY | ソニー | エレクトロニクス |
| HMC | ホンダ | 自動車 |
| MUFG | 三菱UFJ | 金融 |
| SMFG | 三井住友FG | 金融 |
| NMR | 野村HD | 金融 |
| IX | ORIX | 金融 |

→ **日本企業4,000社中の20-30社（0.5-0.75%）。セクターも偏在（自動車・金融に集中）。**
→ 殿の関心セクター（半導体・素材・ゼネコン・住設）はほぼカバーされない。

---

## 2. 日米クロスアナリシスへの適用性

### 2.1 可能なユースケース（3件+）

**UC-1: ADR Premium/Discount監視**
- 本API（TM米国価格）+ YFinance（7203.T TSE価格）→ ADR裁定機会検出
- temperature: t=0（価格差は事実）
- **評価**: ○ だがYFinance単独で両方取れる。本APIの独自価値は低い

**UC-2: SEC 20-F Filing分析（ADR日本企業の英語開示）**
- 日本企業が米国SECに提出する20-F（年次報告書）には日本事業のリスク開示あり
- 英語で構造化されており、LLM解析に向いている
- Crucixの28ソースにSEC Filingは含まれていない → **独自の補完価値あり**
- **評価**: ◎ これが本APIの最大の差別化ポイント

**UC-3: 米国セクター財務→日本関連企業影響推定**
- 米国半導体(INTC/NVDA/AMD)のcapex変動 → 日本の装置メーカー(東エレク/ディスコ等)への受注予測
- CF計算書のcapex/R&D推移を時系列でLassoモデルの説明変数に
- **評価**: ◎ だし日本側データは別途EDINETdb/YFinanceで調達する必要あり

**UC-4: 米国企業ニュースからの日本影響シグナル検出**
- `get_company_news(ticker="AAPL")` → サプライチェーン言及をNLP抽出 → 日本サプライヤー影響
- hookトリガー三層モデルのL2(ニュース・イベント)層に位置
- **評価**: △ Crucix GDELT/RSS の方がカバレッジ広い

**UC-5: daily_risk.pyファクター拡張**
- 米国個別企業の財務健全性指標（current ratio, debt/equity等）を算出
- daily_risk.pyのLayer B composite_alertの補助ファクターとして投入
- **評価**: ○ だがdaily_risk.pyは指数・コモディティベースでミクロ不要

### 2.2 不可能なユースケース（重要な制約）

| やりたいこと | なぜ不可能か |
|-------------|-------------|
| 日本国内セクター比較 | TSEティッカー非対応 |
| 殿の対象国(タイ/ベトナム等)市場分析 | アジア市場完全非対応 |
| 為替影響の直接分析 | FX/マクロデータなし(FRED等が必要) |
| 日本企業の四半期決算比較 | TSE非対応。EDINETdb/YFinanceが必要 |

---

## 3. 既存ツールとの統合評価

### 3.1 役割分担マトリクス

| データソース | 米国株 | 日本株 | アジア | マクロ | 月額 | 現状 |
|-------------|:-----:|:-----:|:-----:|:-----:|:----:|------|
| **financial-datasets** | ◎ | △(ADRのみ) | ✕ | ✕ | **$200+** | 未導入 |
| Crucix(28ソース) | ○ | ○(YFinance) | △ | ◎(FRED/OECD) | ¥0 | 稼働中 |
| YFinance | ◎ | ◎ | ○ | △ | ¥0 | Crucix内 |
| EDINETdb(MCP) | ✕ | ◎(有報) | ✕ | ✕ | ¥0 | 導入済み |
| daily_risk.py | — | — | — | ◎(指数) | ¥0 | 稼働中 |

### 3.2 個別ツールとの関係

**Crucix（MBP cron30分、28ソースOSINT）:**
- Crucixは既にYFinance経由で米国株価格を取得している
- financial-datasetsの独自価値: **構造化された財務諸表**(income/BS/CF)とSEC Filing
- 重複: 株価、ニュース。補完: 財務諸表、SEC Filing

**Dexter（DCF分析エンジン）:**
- DexterはDCFバリュエーションに財務諸表データを必要とする
- financial-datasetsは米国企業のDCF入力データ供給源として**直接的に補完**
- ただし殿のDexterは日本企業分析にも使うはず → 日本側はEDINETdb

**獏（baku.py）:**
- 獏の入力パイプラインとして company_news エンドポイントは使えるが、
  GDELTの方がカバレッジ広い。SEC Filingの定期監視(20-F)は価値あり

**systrade Lasso/カーネル法:**
- 財務諸表数値（売上成長率、利益率変動、capex/売上比率等）はファクター候補
- ただしsystradeのOOS R²=-0.18問題（月次マクロでは過学習）は個別企業データでも同じリスク

---

## 4. 殿の投資仮説との整合

### 4.1 「棍棒で殴れるファンダメンタルズ」（t=0）

| データ種別 | temperature | 棍棒適格 |
|-----------|:-----------:|:--------:|
| 財務諸表(income/BS/CF) | t=0（監査済み事実） | ◎ |
| SEC Filing(10-K/20-F) | t=0（法定開示） | ◎ |
| 株価(current/historical) | t=0（市場事実） | ◎ |
| 企業ニュース | t>0（ナラティブ） | △ |

→ 本APIのデータは**大部分がt=0**。棍棒原則と合致。
→ ただし棍棒を振る対象が米国企業に限定される。

### 4.2 アジアインフラ×オルタナティブデータ仮説

**ギャップ**: 本APIが埋めるのは「米国側の受益企業の財務データ」のみ。
殿の仮説サプライチェーン:
```
インフラ計画(ODA/ADB) → 沿線地価 → 建材需要 → 日本企業受益
                                                    ↑ ここだけカバー(ADRのみ)
```
→ サプライチェーンの上流（インフラ計画・現地データ）は一切カバーされない。

### 4.3 月額ゼロ精神との両立

| プラン | 月額 | 殿の許容度 |
|-------|:----:|:---------:|
| Pay-as-you-go | $0.01-$0.10/req | △（使った分だけだが単価高い） |
| Developer | $200/mo | ✕（月額忌避の典型） |
| Pro | $2,000/mo | ✕✕ |

→ **月額忌避原則に正面衝突。** Pay-as-you-goでも使用量に応じて課金が発生。
→ YFinance(無料)+EDINETdb(無料)で同等以上のカバレッジが得られる現状では正当化困難。

---

## 5. 導入判断: Conditional No-Go

### 5.1 判定根拠

| 基準 | 評価 | 理由 |
|------|:----:|------|
| 主目的適合(日米分析) | **✕** | 日本側がADR 20-30社のみ。片翼飛行 |
| 既存ツール代替不可性 | **△** | SEC Filingのみ独自価値。他は既存ツールで代替可 |
| 月額ゼロ精神 | **✕** | 最安$200/mo。Pay-as-you-goも従量課金 |
| 導入コスト | **◎** | MCP設定15分。技術的障壁なし |
| API依存リスク | **△** | MIT License。だがデータソースはAPIに依存 |

### 5.2 Conditional — 以下の条件で再評価

1. **殿がDexterで米国企業DCF分析を本格化**した場合
   → Dexter入力パイプラインとして financial-datasets の構造化財務諸表が価値を持つ
   → その場合もPay-as-you-go利用に限定し、月額プランは避ける

2. **SEC 20-F Filing分析**のユースケースが具体化した場合
   → ADR日本企業の英語開示をLLMで定期監視 → Crucixにない独自情報
   → SEC EDGAR直接アクセス（無料）で代替可能かも先に検証すべき

3. **無料枠の存在が確認**された場合
   → server.pyでAPIキーがoptional(`if api_key := ...`)な実装 → 一部エンドポイントは無料かもしれない
   → 要実機テスト（APIキーなしでどこまで取れるか）

### 5.3 現時点での推奨アクション

| # | アクション | 優先度 | 理由 |
|---|-----------|:------:|------|
| 1 | **導入しない** | — | 月額忌避+日本カバレッジ不足 |
| 2 | SEC EDGAR直接アクセス調査 | 低 | 20-F Filingが無料で取れるなら本API不要 |
| 3 | Dexter本格化時に再評価 | 棚上げ | Dexter側の需要が明確になってから |
| 4 | APIキーなしテスト | 低 | 無料枠の有無確認（好奇心レベル） |

---

## 6. 代替手段との比較

殿の日米間影響分析に対して、**既に手元にあるツール**で十分な理由:

```
日本側データ:
  EDINETdb(MCP) → 有価証券報告書(4,000社) ← 無料、導入済み
  YFinance       → TSE全銘柄価格+財務 ← 無料、Crucix内稼働中

米国側データ:
  YFinance       → NYSE/NASDAQ全銘柄価格+財務 ← 無料、Crucix内稼働中
  FRED(via Crucix) → マクロ指標 ← 無料、稼働中
  OECD(via Crucix) → 国際統計 ← 無料、稼働中

クロス分析:
  daily_risk.py  → 日次リスクダッシュボード ← 無料、稼働中
  Crucix         → 28ソースOSINT ← 無料(ローカルLLM)、cron稼働中
  獏(baku.py)    → 夢見+リサーチ ← 無料、稼働中

唯一のギャップ:
  SEC Filing構造化データ → SEC EDGAR直接アクセスで代替検証推奨
```

---

## 関連ドキュメント

| 文書 | 内容 |
|------|------|
| Memory: systrade_asia_thesis | アジアインフラ×投資仮説 |
| Memory: systrade_crucix_setup | Crucix+gpt-oss構成 |
| Memory: finance_temperature_theory | daily_risk.py温度理論 |
| context/finance-triggers.md | 金融hookトリガー設計(§12含む) |
| docs/shogun/dexter_analysis.md | Dexter DCF分析評価 |
| docs/shogun/systrade_phase0_plan.md | systrade Phase 0計画 |
