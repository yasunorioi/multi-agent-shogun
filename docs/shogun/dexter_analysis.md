# Dexter（金融リサーチエージェント）設計分析

> **軍師分析書** | 2026-03-25 | 殿勅命 | project: systrade

---

## §1 概要

[Dexter](https://github.com/virattt/dexter) — TypeScript/Bun製の自律金融リサーチエージェント。
18.5k stars / 2.3k forks / MIT License。最新リリース v2026.3.18。

**一言**: バフェット/マンガーの投資哲学をSOUL.mdに注入し、Financial Datasets APIで財務データを取得、DCF分析まで自動実行する「考えるリサーチャー」。

---

## §2 アーキテクチャ分析

### 2a. コア構造

```
User Query
  ↓
Agent Loop (max 10 iterations)
  ├─ buildIterationPrompt()  ← SOUL.md + Scratchpad + Tool Results
  ├─ LLM Call (OpenAI/Anthropic/etc.)
  ├─ Tool Execution (AgentToolExecutor)
  │   ├─ finance/  (16ツール: DCF, SEC, insider trades, screener...)
  │   ├─ search/   (Exa, Tavily, Perplexity, X-Search)
  │   ├─ browser/  (Webブラウジング)
  │   ├─ memory/   (ベクトル検索ベースの永続記憶)
  │   └─ filesystem/ (ファイル操作)
  ├─ Scratchpad Logging (JSONL)
  └─ Termination Check (直接応答 or maxIter到達)
```

### 2b. 特筆すべき設計判断

| 設計要素 | Dexterの選択 | 評価 |
|----------|-------------|------|
| **計画と実行の分離** | 分離なし（リアクティブ） | △ 単純だが複雑タスクに弱い |
| **ループ検出** | 明示的なし（maxIter=10のみ） | △ 素朴すぎる |
| **記憶** | ベクトル検索（embedding+chunker+indexer） | ○ セッション超え記憶あり |
| **Scratchpad** | JSONL append-only ログ | ◎ 監査可能・デバッグ容易 |
| **ツール制限** | 同一ツール3回/類似クエリ閾値0.7 | ○ 暴走防止の最低限 |
| **コンテキスト管理** | overflow検出→古いtool結果を削除→リトライ | ○ 実用的 |
| **SOUL.md** | 投資哲学＋行動原則を自然言語で注入 | ◎ shogunのinstructions相当 |
| **SKILL.md** | DCFスキルに8ステップ手順+検証チェック | ◎ shogunのスキルと同設計思想 |

### 2c. 強み

1. **SOUL.md の設計が秀逸**
   - 「検索エンジンではない。考えるリサーチャーだ」という自己定義
   - バフェット/マンガーの原則を5つのCore Driverに変換
   - 「セッション継続性がないことが新鮮な目を強制する」——没日録の逆アプローチだが一理ある

2. **DCF SKILLの構造化**
   - 8ステップの明確なワークフロー（データ収集→成長率計算→WACC→感度分析→検証）
   - セクター別WACC表を`.md`で持つ（LLMが直接参照可能）
   - サニティチェック3項目（EV乖離30%以内、Terminal Value比率50-80%、FCF倍率15-25x）

3. **Scratchpad = 没日録の近似**
   - JSONL形式でツール呼び出し全記録
   - クエリハッシュで関連ログを紐付け
   - コンテキスト溢れ時は古い結果だけ消去、ファイルは保全

### 2d. 弱み

1. **計画フェーズが存在しない**
   - EnterpriseOps-Gym論文が示した通り、Planner+Executor分離で6-13%改善が見込める
   - 複合クエリ（「A社とB社のDCF比較→セクター横断分析」）で迷走リスク

2. **ループ検出が素朴**
   - maxIter=10とJaccard類似度のみ。shogunのquality_guardrails_design_v2で設計した3層ガードレールと比較すると防御が薄い

3. **セッション継続性の放棄**
   - SOUL.mdは「記憶がないことが美徳」と主張するが、systrade案件のように長期追跡が必要な場合は致命的
   - memory/モジュール（ベクトル検索）は存在するが、デフォルトの設計思想と矛盾

4. **LLMプロバイダ依存**
   - OpenAIがデフォルト（Anthropic/Google/xAI/Ollamaも対応）
   - shogunはClaude専用設計のため、プロバイダ切替のオーバーヘッドは不要だが、Claude非対応のリスクは低い

---

## §3 shogunシステムとの設計パターン比較

| 概念 | shogun | Dexter | 対応度 |
|------|--------|--------|:------:|
| **人格注入** | instructions/*.md | SOUL.md | ◎ 同一思想 |
| **スキル定義** | .claude/skills/*.md | skills/dcf/SKILL.md | ◎ 同一思想 |
| **作業ログ** | 没日録DB (SQLite) | Scratchpad (JSONL) | ○ 目的同一、実装差異 |
| **記憶** | Memory MCP + 没日録 | memory/ (ベクトル検索) | ○ |
| **階層構造** | 将軍→老中→軍師/足軽 | 単体エージェント | × Dexter単独 |
| **ポリシー遵守** | F001-F006 + hooks | 暗黙（SOUL.mdの価値観のみ） | × shogunが上 |
| **品質検証** | お針子18点ルーブリック | DCFサニティチェック3項目 | △ 領域特化 |
| **通信** | YAML + send-keys | なし（単体） | × |
| **ツール制御** | PreToolUse hooks | requestToolApproval + maxIter | △ |
| **Web検索** | 獏(baku.py) | Exa/Tavily/Perplexity/X-Search | ◎ Dexterが豊富 |

### 設計思想の合流点

**SOUL.md ≒ instructions/gunshi.md**。どちらも「エージェントの魂を自然言語で定義する」アプローチ。
Dexterのバフェット/マンガー原則は、shogunの戦国軍制と同じく**ドメイン知識をプロンプトに焼く**手法。

**SKILL.md ≒ .claude/skills/*.md**。どちらもタスク実行の手順書をMarkdownで定義し、エージェントが参照する。
DexterのDCF 8ステップは、shogunの`/audit` 18点ルーブリックと同じ構造化手法。

---

## §4 systrade_asia_thesis.md との適合性

### 4a. 直接使える部分

| systrade要件 | Dexterの対応 | 適合度 |
|-------------|-------------|:------:|
| ファンダメンタルズ分析 | finance/fundamentals.ts, key-ratios.ts | ◎ |
| DCF分析 | skills/dcf/ (8ステップ+WACC表) | ◎ |
| SEC Filing分析 | filings.ts, read-filings.ts | ○ (米国のみ) |
| インサイダー取引監視 | insider_trades.ts | ○ (米国のみ) |
| ニュース集約 | news.ts | ○ |
| 株価スクリーニング | screen-stocks.ts | ○ |
| X/Twitter検索 | x-search.ts | ◎ (リアルタイム情報) |

### 4b. 不足する部分（systrade戦略との乖離）

| systrade要件 | Dexterの状態 | 対策 |
|-------------|-------------|------|
| **アジア市場対応** | Financial Datasets APIは米国中心（17,325+ティッカー≒主に米国） | 別データソース必要 |
| **GIS/インフラ分析** | 未対応 | QGIS+獏の領域 |
| **ODA/ADB/JICA入札情報** | 未対応 | WebSearchで代替可能 |
| **衛星画像分析** | 未対応 | 別ツール必要 |
| **建材・セメント・鉄鋼** | アジア上場企業のカバレッジ不明 | 要検証 |
| **日本企業（TOTO、ダイキン等）** | 東証ティッカー対応不明 | 要検証 |

### 4c. 適合性評価

**結論: 部分的に有用。ただしsystrade戦略の本丸（アジアインフラ）にはそのまま使えない。**

殿の戦略は「棍棒で殴れるファンダメンタルズ」——DexterのDCF分析は棍棒そのものだが、殴る対象（アジア市場）にリーチできない。米国株の参考分析ツールとしては即戦力。

---

## §5 コスト・制約分析

### 5a. API料金

| API | 最低コスト | 殿の制約との関係 |
|-----|-----------|----------------|
| **Financial Datasets API** | Pay-as-you-go可（$0.01-$0.10/リクエスト） | △ 月額ゼロ違反だが従量制は許容範囲か |
| **OpenAI API** | 従量制 | × shogunはClaude専用。Anthropic APIに切替可 |
| **Exa Search** | 従量制 | △ 獏(baku.py)で代替可能 |
| **Tavily** | Free tier 1000回/月 | ○ |
| **Perplexity API** | 従量制 | △ |

### 5b. 月額ゼロ制約との整合

**Financial Datasets APIのPay-as-you-go**は月額ゼロの精神に合致する（使った分だけ）。
ただし、earnings取得$0.00、株価$0.01、財務諸表$0.04と安価。
DCF分析1回で概算$0.30-$0.50程度（10-15リクエスト）。

### 5c. 技術的制約

| 制約 | 影響 | 対処 |
|------|------|------|
| **Bun依存** | shogunはNode.js/Python環境。Bunインストール必要 | `curl -fsSL https://bun.sh/install \| bash` で追加可 |
| **TypeScript** | shogunのPython/Bashツールチェインと異質 | 独立プロセスとして実行可能 |
| **OpenAIデフォルト** | Anthropic対応あり（プロバイダ切替可） | 環境変数でClaude切替 |
| **米国市場中心** | アジア市場データ不足 | 別データソース併用 |

---

## §6 shogunとの統合案

### 6a. 案1: 獏の下位ツールとして統合（推奨）

```
獏(baku.py) ─── systrade_research カテゴリ
  ├─ X/Twitter検索（既存）
  ├─ Web検索（既存）
  └─ Dexter呼び出し（新規）
      ├─ DCF分析
      ├─ 財務データ取得
      └─ スクリーニング
```

**利点**: 獏の好奇心エンジンがリサーチカテゴリに応じてDexterを起動。軍師は獏の結果を分析。既存の階層を壊さない。

**実装**: `baku.py` に `dexter_query()` 関数を追加。subprocess で `bun run src/cli.ts` を呼び出し、Scratchpadの結果をパースして没日録に記録。

### 6b. 案2: 軍師の直接ツールとして統合

```
軍師(gunshi) ─── Dexter CLI呼び出し
  ├─ 「A社のDCF分析を実行せよ」→ dexter "run DCF for AAPL"
  └─ 結果を分析書に統合
```

**利点**: 軍師が直接制御。レイテンシ低減。
**欠点**: 軍師の権限拡大が必要。F003（足軽直接通信禁止）の精神に抵触する可能性。

### 6c. 案3: agent-swarm連携（将来）

```
agent-swarm (2ch BBS)
  └─ #systrade板 にDexterボットを配置
      ├─ 足軽がスレッドで「$AAPL DCF」と書き込み
      └─ Dexterがレスで分析結果を返信
```

**利点**: 2ch互換CGIの通信基盤に乗る。非同期。
**欠点**: agent-swarm自体がまだ開発中。

### 6d. 統合案評価

| 案 | 実装コスト | 既存構造への影響 | 推奨度 |
|----|-----------|----------------|:------:|
| 案1: 獏統合 | 低（baku.pyに関数追加） | なし | ◎ |
| 案2: 軍師直接 | 中（権限設計必要） | 中 | ○ |
| 案3: agent-swarm | 高（前提が未完成） | なし | △（将来） |

---

## §7 Dexterから盗むべき設計パターン

### 7a. SOUL.md → instructions強化

DexterのSOUL.mdの「Core Drivers」概念をshogunに取り入れる余地あり:

| Dexter Core Driver | shogun対応 | 導入価値 |
|-------------------|-----------|---------|
| Relentless curiosity | 獏に実装済み | — |
| Building instinct | 軍師の設計能力 | — |
| Technical courage | 明示されていない | ○ 足軽instructionsに追加可 |
| Independence | 明示されていない | ○ 軍師の独立判断を後押し |
| Thoroughness as craft | お針子ルーブリック | — |

### 7b. DCF SKILL.md → スキル設計テンプレート

DexterのDCF SKILL.mdの構造（8ステップ+検証チェック+前提値表）は、shogunのスキル設計テンプレートとして優秀:

```markdown
## Skill: [名前]
### Trigger: [発火条件]
### Steps:
1. データ収集（具体的なクエリ列挙）
2-7. 処理ステップ（計算式・閾値を明記）
8. 検証（サニティチェック項目）
### Assumptions: [前提値の表]
### Validation: [結果の妥当性チェック]
```

### 7c. Scratchpad のJSONL形式

没日録DBはSQLiteだが、デバッグ用のJSONLログは別途導入する価値あり。
特に`query_hash`による関連ログ紐付けは、没日録のcmd_id体系と相補的。

---

## §8 総合評価

### 軍師の所見

```
┌─────────────────────────────────────────────────────┐
│ Dexter = 優秀な単騎の侍。だが軍団戦には向かない。  │
│                                                       │
│ 殿のsystrade戦略は「アジアインフラの構造変化を       │
│ 棍棒で殴る」正攻法。Dexterの棍棒（DCF分析）は       │
│ 優秀だが、殴る対象（アジア市場）へのリーチが不足。  │
│                                                       │
│ 導入するなら獏の下位ツールとして。全面依存は危険。   │
│ 設計パターン（SOUL.md, SKILL.md構造）は盗む価値大。 │
└─────────────────────────────────────────────────────┘
```

### スコアカード

| 評価項目 | 点数 | 備考 |
|----------|:----:|------|
| アーキテクチャ設計 | 7/10 | SOUL.md/Scratchpad秀逸、計画フェーズ欠如 |
| systrade適合性 | 5/10 | 米国株◎、アジア市場× |
| shogun統合容易性 | 7/10 | CLI呼び出しで独立運用可、Bun依存が唯一の壁 |
| コスト | 8/10 | Pay-as-you-go、DCF1回$0.50以下 |
| 盗むべき設計 | 9/10 | SOUL.md/SKILL.md/Scratchpadの3点セット |
| **総合** | **7.2/10** | **部分導入推奨。全面依存は不可。** |

### 推奨アクション

1. **即座**: DexterのSOUL.md/SKILL.md設計パターンをshogunスキルテンプレートに反映
2. **短期**: 獏(baku.py)にDexter CLI呼び出し関数を追加（米国株DCF分析用）
3. **中期**: Financial Datasets APIのアジア市場カバレッジを検証。不足ならYahoo Finance API/Alpha Vantage等で補完
4. **判断保留**: agent-swarm連携は2ch CGI基盤の完成を待つ

---

## §9 付録: Financial Datasets API料金表

| エンドポイント | 料金/リクエスト |
|---------------|:---------------:|
| Earnings | $0.00 |
| Stock Prices | $0.01 |
| Crypto Prices | $0.01 |
| Interest Rates | $0.01 |
| Search (10 filters) | $0.01 |
| Financial Metrics | $0.02 |
| Insider Trades | $0.02 |
| News | $0.02 |
| SEC Filings | $0.02 |
| Financial Statements (individual) | $0.04 |
| All Financial Statements (bundle) | $0.10 |

月額プラン: Developer $200/月、Pro $2,000/月、Enterprise カスタム

---

*以上、軍師の分析を終える。殿の棍棒にふさわしい道具か否か、最終判断は殿に委ねる。*
