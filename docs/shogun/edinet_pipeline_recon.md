# EDINET棍棒パイプライン偵察+設計書

> **軍師分析書** | 2026-03-30 | cmd_465 / subtask_1030 | project: systrade
> **North Star**: EDINET API v2直叩きで大量保有報告書×有報XBRLの突合パイプラインを構築せよ

---

## §1 EDINET API v2 仕様調査

### 1a. 金融庁EDINET API v2 vs EDINET DB — 決定的な違い

| 項目 | **金融庁EDINET API v2** | **EDINET DB (Cabocia)** |
|------|-------------------------|------------------------|
| 運営 | 金融庁（政府公共API） | Cabocia株式会社（民間SaaS） |
| データ | **生データ**（XBRL/PDF/ZIP） | **加工済み**（84指標正規化） |
| 大量保有報告書 | **全件取得可能**（XBRL生データ） | 7万件（構造化済み） |
| 有報テキスト | **XBRL Inline原文** | テキスト抽出済み |
| 認証 | Subscription-Key（メール登録で即取得、無料） | Bearer Token（Google認証、Free/Pro） |
| レート制限 | 暗黙（3-5秒間隔推奨、403頻発時リトライ） | 明示（100回/日 Free） |
| 月額 | **¥0（永久無料、政府API）** | ¥0（Free）〜¥29,800 |
| 廃止リスク | **極めて低い**（政府インフラ） | 中（スタートアップ） |
| パース負荷 | **高い**（XBRL自前パースが必要） | 低（JSON API） |
| カバレッジ | **全書類種別**（有報、短信、大量保有、適時開示…） | 有報+短信+大量保有 |

**結論**: EDINET API v2は「生の鉱石」、EDINET DBは「精錬済みインゴット」。
cmd_457で精錬済みインゴット（EDINET DB）の導入は完了した。
今回は**鉱石の直接採掘ルート**を確立する。EDINET DBにないデータ（XBRL生テキスト、変動報告書の詳細、有報前期比テキスト差分）がターゲット。

### 1b. エンドポイント一覧

| API | エンドポイント | 用途 |
|-----|--------------|------|
| **書類一覧** | `https://api.edinet-fsa.go.jp/api/v2/documents.json` | 指定日の全提出書類メタデータ取得 |
| **書類取得** | `https://api.edinet-fsa.go.jp/api/v2/documents/{docID}` | 個別書類のダウンロード |

### 1c. 書類一覧APIパラメータ

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `date` | YYYY-MM-DD | ✅ | 提出日 |
| `type` | int | ✅ | 1=メタデータのみ / 2=メタデータ+書類一覧 |
| `Subscription-Key` | string | ✅ | APIキー |

**レスポンス主要フィールド**:
```
seqNumber, docID, edinetCode, secCode, JCN,
filerName, fundCode, ordinanceCode, formCode,
docTypeCode, docDescription, submitDateTime,
periodStart, periodEnd, xbrlFlag, pdfFlag,
withdrawalStatus, docInfoEditStatus
```

### 1d. 書類取得APIパラメータ

| type値 | 取得内容 |
|--------|---------|
| **1** | **XBRL提出本文+監査報告書**（ZIP） |
| **2** | PDF |
| **3** | 代替書面・添付書類 |
| **4** | 英文XBRL |
| **5** | 英文PDF |

**棍棒パイプラインに必要なのは `type=1`（XBRL ZIP）のみ。**

### 1e. docTypeCode（書類種別コード）— 棍棒対象

| docTypeCode | 書類名 | 棍棒用途 |
|:-----------:|--------|---------|
| **120** | 有価証券報告書 | ファンダメンタルズ変動検知 |
| **130** | 訂正有価証券報告書 | 訂正内容=異常シグナル |
| **140** | 四半期報告書 | 四半期変動追跡 |
| **350** | 大量保有報告書（初回+変動） | **スマートマネー検出（本丸）** |
| **360** | 訂正報告書（大量保有・変動） | 訂正=隠蔽の匂い |

### 1f. 認証方式

```
Subscription-Key はURLパラメータまたはHTTPヘッダーで渡す:
  URL: ?Subscription-Key={KEY}
  Header: Ocp-Apim-Subscription-Key: {KEY}
```

**取得方法**: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html
→ アカウント作成（メールアドレスのみ）→ APIキー即発行 → **完全無料**

### 1g. 制限事項と対策

| 制限 | 詳細 | 対策 |
|------|------|------|
| レート制限 | 暗黙（3-5秒間隔推奨） | `time.sleep(3)` をリクエスト間に挿入 |
| 403エラー | 頻発（特に大量取得時） | 指数バックオフ（3→6→12秒） |
| データ期間 | 過去5年分のみ | 十分（2021-2026）。取得データは必ずローカル保存 |
| 並列制限 | 並列リクエスト非推奨 | シーケンシャル処理+ローカルキャッシュ |
| ZIP展開 | ダウンロード後にZIP展開→XBRL抽出が必要 | edinet-toolsまたはzipfile+xml.etree |

---

## §2 大量保有報告書 XBRLデータ構造

### 2a. 5%ルールの仕組み

上場企業の株式を**5%以上保有**した場合、5営業日以内にEDINETに報告義務。
その後**1%以上の変動**があるたびに変動報告書を提出。

→ 機関投資家の「入り」と「出」がリアルタイムで公開される。**これが棍棒の鉱脈。**

### 2b. XBRLタクソノミ — 主要要素

大量保有報告書のXBRLは**原則拡張なし**（想定外の要素は出現しない）。

| 要素名 | 内容 | 型 |
|--------|------|-----|
| `NameOfIssuer` | 発行者名（対象企業） | string |
| `SecurityCodeOfIssuer` | 証券コード（4桁） | string |
| `Name` | 保有者名（氏名/法人名） | string |
| `IndividualOrCorporation` | 個人/法人区分 | string |
| `TotalNumberOfStocksEtcHeld` | 保有株数 | decimal |
| `HoldingRatioOfShareCertificatesEtc` | **保有割合**（%） | decimal |
| `TotalAmountOfFundingForAcquisition` | 取得資金総額 | decimal |
| `PurposeOfHolding` | 保有目的 | string |

### 2c. コンテキスト構造

XBRLインスタンスは2種類のコンテキスト:
- `FilingDateInstant`: 書類全体の値（報告日、対象企業等）
- `FilingDateInstant_..._Holder{N}Member`: **個別保有者データ**（連名報告時に複数）

→ 連名報告（共同保有）では各保有者が別コンテキストに紐づく。パース時に注意。

### 2d. 変動報告書との構造差分

| 項目 | 大量保有報告書（初回） | 変動報告書 |
|------|---------------------|-----------|
| docTypeCode | 350 | 350（同一コード） |
| 記載内容 | 初回5%超え時点の全データ | **変動分のみ** |
| 前回保有割合 | なし | あり（差分計算可能） |
| 変動理由 | なし | あり（市場買付/ToB/割当等） |

**識別方法**: `docDescription`フィールドで「変更報告書」のテキストを含むか判定。

---

## §3 有価証券報告書 XBRL差分検知

### 3a. 数値変動検知（実現可能性: ◎）

edinet-tools `SecuritiesReport`クラスで構造化取得可能な主要指標:
- `net_sales`（売上高）
- `operating_cash_flow`（営業CF）
- `roe`
- `short_term_loans_payable`（短期借入金）
- `bonds_payable`（社債）

**前期比計算**: 同一企業の2期分を取得 → 差分率 = (当期 - 前期) / 前期
既存edinetdb_drill.pyの棍棒指標9種（CLUB_INDICATORS）と同じロジックを流用可能。

### 3b. テキスト差分検知（実現可能性: △）

有報のテキスト部分（リスク情報、設備投資計画、地域セグメント）の前期比差分:
- XBRL Inlineから当該セクションのテキストを抽出
- 前期テキストとのdiff（difflib.unified_diff）
- 変更箇所のキーワード頻度分析

**課題**: XBRL InlineのHTML構造が企業ごとに異なる。セクション境界の自動検出が難しい。
**現実的な落とし所**: edinet-toolsの`get_text_blocks`相当機能 or EDINET DBの`/text-blocks`エンドポイントを使う方が確実。

→ **Phase 0ではテキスト差分は棚上げ。数値差分に集中する。**

### 3c. XBRL Inlineの扱い

EDINET提出書類はInline XBRL（iXBRL）形式。HTMLの中にXBRLタグが埋め込まれている。
- **数値抽出**: `<ix:nonFraction>` タグから直接取得可能
- **テキスト抽出**: `<ix:nonNumeric>` タグだが、HTML装飾が混在
- **edinet-toolsがiXBRL→構造化データの変換を担う**ため、自前パースは不要

---

## §4 既存OSSライブラリ調査

### 4a. 比較表

| ライブラリ | 最新版 | 最終更新 | 大量保有 | 有報 | XBRL Parse | SQLite親和 | 推奨度 |
|-----------|--------|---------|:--------:|:----:|:----------:|:----------:|:------:|
| **edinet-tools** | **0.4.3** | **2026-03-18** | **◎ LargeHoldingReport** | **◎ SecuritiesReport** | **◎** | **◎** | **★★★** |
| edinet_xbrl (BuffettCode) | 0.2.x | 2023 | ✗ | ◎ | ◎ | ○ | ★★ |
| edinet-python | 0.1.x | 2022 | ✗ | ○ | △ | ○ | ★ |
| arelle | 2.x | 2025 | ◎ | ◎ | ◎ | △(重い) | ★ |
| 自前XML解析 | - | - | ◎ | △ | △ | ◎ | ★★ |

### 4b. 推奨: edinet-tools一択

**決定的な理由**:
1. `LargeHoldingReport`クラスで大量保有報告書をtyped Pythonオブジェクトに自動パース
2. `SecuritiesReport`クラスで有報もカバー
3. EDINET API v2のSubscription-Key認証をネイティブサポート
4. MIT License、Python 3.10+、Pure Python（RPi/ARM対応可能）
5. **2026-03-18更新** — 活発なメンテナンス

```python
import edinet_tools

# 企業検索
toyota = edinet_tools.entity("7203")

# 書類取得+パース
docs = toyota.documents(days=30)
report = docs[0].parse()

if isinstance(report, edinet_tools.LargeHoldingReport):
    print(report.filer_name)       # 保有者名
    print(report.target_company)   # 対象企業
    print(report.ownership_pct)    # 保有割合
    print(report.purpose)          # 保有目的
```

### 4c. 冒険的な案: 自前XMLパーサ

Qiita記事の著者曰く「XBRLを処理するためのライブラリなんていらない、シンプルで高速なXMLパーサを使えばいい」。
大量保有報告書は拡張なしの固定タクソノミなので、`xml.etree.ElementTree`だけで十分パース可能。

**利点**: ゼロ依存、高速、edinet-toolsが将来メンテ停止した場合のフォールバック
**欠点**: 有報パースは複雑すぎて自前は非現実的

→ **edinet-toolsをメインに据え、大量保有報告書パースだけ自前XMLフォールバックを持つ**のが最も堅い構成。

---

## §5 Crucix/獏との接続ポイント

### 5a. baku.pyへの追加方式

現行baku.pyの仕入れフロー:
```
TONO_INTERESTS → DDGクエリ生成 → Web検索
config/baku_sources.yaml → RSS巡回（トウシル等）
```

EDINET API追加の2案:

**案A: baku_sources.yamlに追加（RSS互換ラッパー）**
```yaml
# config/baku_sources.yaml に追加
- name: edinet_tairyohoyu
  display_name: "EDINET 大量保有報告書"
  url: "edinet://large-holding"  # カスタムスキーム
  type: edinet  # 新type追加
  category: finance
  enabled: true
  max_items: 10
```
→ baku.pyに`type: edinet`の分岐を追加。`_fetch_edinet_items()`関数で大量保有報告書を取得。

**案B: 独立スクリプト（edinet_pipeline.py）→ baku.pyの夢として注入**
```
cron(日次) → edinet_pipeline.py → SQLite蓄積
         → 急変検出 → dreams.jsonlに追記
baku.py → dreams.jsonlを読む → 噛み砕きループ
```

**推奨: 案B**。理由:
1. EDINET APIは3-5秒間隔制限がある → baku.pyの毎時実行サイクルとは周期が合わない
2. 大量保有報告書は日次で十分（提出は営業日のみ）
3. 独立スクリプトなら障害分離できる（baku.py巻き添え防止）
4. edinetdb_drill.pyと同じ設計パターン（別スクリプト分離）を踏襲

### 5b. 噛み砕き→Crucix投入のデータフロー

```
edinet_pipeline.py (日次cron)
  │
  ├── §1: 書類一覧API → 大量保有報告書(350)をフィルタ
  │     date=今日, type=2, docTypeCode=350
  │
  ├── §2: 書類取得API → XBRL ZIP → edinet-tools parse
  │     → LargeHoldingReport → filer_name, ownership_pct, purpose
  │
  ├── §3: SQLite蓄積 (data/edinet_holdings.db)
  │     → 保有割合の時系列を蓄積
  │     → 前回比の変動率計算
  │
  ├── §4: 急変検出 (ラプラシアンフィルタ適用)
  │     → |Δ保有割合| > 2% の銘柄を抽出
  │     → edinetdb_drill.pyの棍棒指標と突合
  │
  ├── §5: dreams.jsonl追記 (獏の夢として注入)
  │     → query: "{保有者} {銘柄} 保有割合{変動幅}"
  │     → baku.pyが噛み砕きループで深掘り
  │
  └── §6: agent-swarm finance板投稿 (任意)
        → スマートマネーシグナルを全エージェントに通知
```

### 5c. cron頻度設計

| データソース | 更新頻度 | cron設計 |
|------------|---------|---------|
| 大量保有報告書 | 営業日のみ | **平日18:00 JST**（EDINET反映後） |
| 有報 | 四半期/年次 | **決算発表日+3営業日**（edinet_calendar連動） |
| edinetdb_drill.py | daily_risk DANGER時 | **既存（daily_risk.pyトリガー）** |

→ edinet_pipeline.pyは `0 18 * * 1-5`（平日18時）で十分。

### 5d. Crucix連携

Crucixは30分サイクルでOSINT収集 → trade ideas生成。
edinet_pipeline.pyの出力（急変シグナル）をCrucixの入力に注入:

```
edinet_pipeline.py → data/edinet_signals.json
Crucix cron_ideas.sh → EDINET signals + 既存28ソース → LLM判定
```

**実装**: cron_ideas.sh内でdata/edinet_signals.jsonをプロンプトに含める（~5行追加）。

---

## §6 全体アーキテクチャ設計

### 6a. パイプライン全体図

```
                     金融庁EDINET API v2
                     (政府インフラ、無料)
                            │
                  ┌─────────┴─────────┐
                  │                   │
          書類一覧API            書類取得API
          (documents.json)       (type=1: XBRL ZIP)
                  │                   │
                  ▼                   ▼
     ┌─────────────────┐    ┌─────────────────┐
     │ 日次フィルタ       │    │ ZIP展開 + Parse  │
     │ docTypeCode=     │    │ edinet-tools     │
     │ 120,350          │    │ LargeHoldingReport│
     └────────┬────────┘    │ SecuritiesReport  │
              │              └────────┬────────┘
              │                       │
              ▼                       ▼
     ┌───────────────────────────────────────┐
     │  data/edinet_holdings.db (SQLite)       │
     │  ・holdings: 大量保有の時系列             │
     │  ・financials_raw: 有報XBRL数値         │
     │  ・signals: 急変検出結果                 │
     └───────────────────┬───────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │ 急変検出   │ │ edinetdb │ │ dreams   │
     │ Δ保有割合  │ │ _drill.py│ │ .jsonl   │
     │ > ±2%     │ │ 棍棒突合  │ │ 獏注入   │
     └────┬─────┘ └────┬─────┘ └────┬─────┘
          │            │            │
          ▼            ▼            ▼
     agent-swarm    daily_risk.py  baku.py
     finance板      DANGER深掘り   噛み砕きループ
                                      │
                                      ▼
                                   Crucix
                                   trade ideas
```

### 6b. 既存パイプラインとの統合方針

| 既存 | 役割 | 統合方法 |
|------|------|---------|
| edinetdb_drill.py | EDINET DB棍棒指標（加工済み） | **そのまま維持**。edinet_pipeline.pyの急変銘柄をドリル対象に追加 |
| daily_risk.py | マクロリスク判定 | **触らない**。DANGER時にedinet_pipeline.pyの保有変動データを参照 |
| baku.py | 夢収集+噛み砕き | dreams.jsonlへの注入で連携 |
| Crucix | OSINT trade ideas | edinet_signals.jsonをプロンプト入力に追加 |

**鉄則: 既存の安定稼働スクリプトに手を入れない。新規スクリプトで橋を架ける。**

### 6c. 新規作成ファイル一覧

| ファイル | 用途 | 行数見積 |
|---------|------|---------|
| `scripts/edinet_pipeline.py` | メインパイプライン | ~300行 |
| `data/edinet_holdings.db` | SQLiteストア | (自動生成) |
| `config/edinet_watch.yaml` | 監視対象+閾値設定 | ~50行 |
| `tests/test_edinet_pipeline.py` | ユニットテスト | ~150行 |

### 6d. edinet_pipeline.py 主要関数設計

```python
# scripts/edinet_pipeline.py
def fetch_daily_filings(date: str) -> list[dict]:
    """書類一覧APIから指定日の大量保有+有報を取得"""

def download_xbrl(doc_id: str) -> Path:
    """書類取得API type=1 → ZIP → 展開 → XBRLパス返却"""

def parse_large_holding(xbrl_path: Path) -> dict:
    """edinet-tools LargeHoldingReport → 構造化dict"""

def parse_securities_report(xbrl_path: Path) -> dict:
    """edinet-tools SecuritiesReport → 棍棒指標dict"""

def detect_spikes(db: sqlite3.Connection) -> list[dict]:
    """保有割合の急変検出（ラプラシアンフィルタ）"""

def crossref_drill(spike: dict) -> dict:
    """edinetdb_drill.pyの棍棒指標と突合"""

def inject_dream(spike: dict) -> None:
    """dreams.jsonlに急変シグナルを注入"""

def post_signal(spike: dict) -> None:
    """agent-swarm finance板に投稿"""
```

### 6e. SQLiteスキーマ設計

```sql
-- data/edinet_holdings.db

CREATE TABLE holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL UNIQUE,
    filing_date TEXT NOT NULL,       -- 提出日
    sec_code TEXT,                   -- 証券コード
    issuer_name TEXT,                -- 発行者名
    holder_name TEXT,                -- 保有者名
    holder_type TEXT,                -- 個人/法人
    shares_held INTEGER,             -- 保有株数
    holding_ratio REAL,              -- 保有割合(%)
    purpose TEXT,                    -- 保有目的
    funding_amount REAL,             -- 取得資金
    prev_ratio REAL,                 -- 前回保有割合(算出)
    delta_ratio REAL,                -- 変動幅(算出)
    raw_json TEXT,                   -- edinet-tools出力の生JSON
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_holdings_sec_code ON holdings(sec_code);
CREATE INDEX idx_holdings_filing_date ON holdings(filing_date);
CREATE INDEX idx_holdings_holder ON holdings(holder_name);

CREATE TABLE financials_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL UNIQUE,
    filing_date TEXT NOT NULL,
    sec_code TEXT,
    company_name TEXT,
    fiscal_year TEXT,
    net_sales REAL,
    operating_cf REAL,
    capex REAL,
    fcf REAL,
    roe REAL,
    equity_ratio REAL,
    raw_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_type TEXT NOT NULL,       -- 'holding_spike' | 'financial_change'
    sec_code TEXT,
    description TEXT,
    delta_value REAL,
    severity TEXT,                   -- 'low' | 'medium' | 'high'
    injected_to TEXT,                -- 'dreams' | 'swarm' | 'both'
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## §7 トレードオフ比較

### 7a. OSSライブラリ選定

| 案 | 構成 | 利点 | 欠点 | 推奨 |
|----|------|------|------|:----:|
| **A: edinet-tools** | pip install edinet-tools | 型付きパース、メンテ活発、MIT | 外部依存1つ、Alpha版 | **★★★** |
| B: 自前XML | xml.etree のみ | ゼロ依存、軽量 | 有報パースが地獄 | ★★ |
| C: arelle | 大規模XBRLエンジン | 最も堅牢 | 重すぎる(数百MB)、RPi不向き | ★ |

### 7b. 獏連携方式

| 案 | 構成 | 利点 | 欠点 | 推奨 |
|----|------|------|------|:----:|
| A: baku_sources.yaml統合 | baku.pyに組み込み | 統一管理 | baku.pyのサイクルと合わない | ★★ |
| **B: 独立スクリプト+dreams注入** | 別cron→dreams.jsonl | 障害分離、周期独立 | ファイル2つ | **★★★** |

### 7c. データ蓄積方式

| 案 | 構成 | 利点 | 欠点 | 推奨 |
|----|------|------|------|:----:|
| **A: 専用SQLite** | data/edinet_holdings.db | 独立、FTS5追加可能 | DBが増える | **★★★** |
| B: 没日録DBに統合 | botsunichiroku.db | 一元管理 | スキーマ汚染、権限問題 | ★ |
| C: JSONL蓄積 | data/edinet_holdings.jsonl | 最も軽量 | 集計クエリが遅い | ★★ |

---

## §8 リスク・見落とし分析

### 見落としの可能性

1. **共同保有者の名寄せ**: 同一機関が複数の法人名で報告する場合がある。edinet-toolsがどこまでハンドルするか要確認（実装時に検証）。

2. **報告遅延**: 大量保有報告書は5営業日以内に提出義務だが、遅延提出がある。「提出日」と「実際の取得日」にズレがある。

3. **空売り（ショートポジション）**: 大量保有報告書は買い持ち（ロング）のみ。空売りポジションは別の報告形式（空売り規制）で開示されるが、EDINETの対象外の場合もある。

4. **edinet-tools Alpha版リスク**: 0.4.3はまだAlpha。破壊的変更の可能性。→ `requirements.txt`でバージョン固定+自前XMLフォールバック。

5. **Subscription-Key失効**: 長期未使用で失効する可能性。→ cronジョブ自体が定期利用になるため問題なし。

6. **ZIP内のファイル構造変更**: EDINET側のZIPフォーマット変更。→ edinet-toolsが吸収してくれることを期待。フォールバック用にZIP展開→ファイル探索のロジックも持つ。

---

## North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: >
    EDINET API v2直叩きにより、EDINET DBにないデータ（大量保有報告書の生XBRL、
    有報前期比数値差分）を棍棒パイプラインに追加する。
    殿の投資仮説（アジアインフラ×棍棒ファンダメンタルズ）の「スマートマネー検出」を
    大量保有報告書の保有割合変動から実現する。月額¥0、マクガイバー精神に完全合致。
  risks_to_north_star:
    - "edinet-tools Alpha版の安定性。フォールバック（自前XML）で対処可能"
    - "EDINET APIのレート制限で大量取得時に403連発。キャッシュ+リトライで対処"
    - "共同保有者の名寄せ精度。Phase 1で検証し、必要ならPhase 2で改修"
```

---

*棍棒で殴れるデータは、政府が無料で公開している。掘りに行くだけの話だ。—— 軍師*
