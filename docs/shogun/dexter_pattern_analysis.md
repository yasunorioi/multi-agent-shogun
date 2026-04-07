# Dexterパターン分析 — systrade Phase 0-2 反映設計

> **軍師分析書** | 2026-03-26 | cmd_451 / subtask_1001 | project: systrade

---

## §1 分析の目的と前提

### North Star

> 殿の投資仮説（アジアインフラ×GIS×オルタナティブデータ）にDexterパターンがどう寄与するか

前回分析（dexter_analysis.md、7.2/10）で「部分導入推奨。全面依存は不可」と結論済み。
今回は「**何を盗み、何を捨てるか**」を具体的コード設計レベルまで掘り下げる。

### 前提: systradeの現状

```
/home/yasu/systrade/          # 既に稼働中
├── src/systrade/
│   ├── fetch/     (yahoo, worldbank, portwatch, comtrade, mlit)
│   ├── select/    (lasso)
│   ├── predict/   (kernel_ridge)
│   ├── regime/    (hmm)
│   └── viz/       (plots)
├── scripts/
│   ├── daily_risk.py   (920行、4層リスクダッシュボード)
│   ├── risk_alert.py
│   ├── run_pipeline.py
│   ├── walkforward.py
│   └── bootstrap_test.py
└── tests/ (69テスト)
```

**Phase 0-2は実装済み。** daily_risk.pyが稼働し、agent-swarm 2ch BBSへのリスク速報投稿まで動いている。
Phase 3（Dexter統合）の判断材料を提供するのが本分析の位置づけ。

### 実験結果からの教訓（重要）

```
- 月次港湾データ→月次株リターン: 予測力ゼロ（EMH）
- グローバル指標→JPN infra月次: OOS R²=-0.18（過学習確定）
- 方向予測hit rate 57.9% — 弱いシグナルはある
- 戦略転換: リターン予測 → リスク回避アラート
```

**殿は既に「予測で稼ぐ」から「リスクを避ける」に転換している。**
Dexterパターンもこの文脈で評価する。

---

## §2 Dexterアーキテクチャ精読

### 2a. エージェントループ

```
User Query
  ↓
while (iteration < maxIterations=10):
  iteration++
  ├── buildIterationPrompt()
  │     SOUL.md + Scratchpad(tool results) + Skills
  ├── LLM Call
  ├── Response判定:
  │   ├── 直接回答(no tool calls) → 終了
  │   ├── ツール呼び出し → tool-executor実行
  │   └── エラー → 終了
  ├── Scratchpad logging (JSONL)
  └── Context overflow check
        estimatedTokens > CONTEXT_THRESHOLD → 古い結果を除去
```

**特筆点:**
- **計画フェーズが存在しない**: リアクティブに1ステップずつ進む
- **類似クエリ検出**: Jaccard類似度0.7で重複ツール呼び出しを検出（scratchpad.findSimilarQuery）
- **コンテキスト溢れ対応**: 古いtool結果を消去してリトライ（最大2回）
- **ループ検出なし**: maxIter=10のみ。shogunの3層ガードレールと比較して素朴

### 2b. Scratchpad構造

```typescript
// .dexter/scratchpad/{timestamp}_{queryMD5-12char}.jsonl
{
  type: 'init' | 'tool_result' | 'thinking',
  timestamp: string,
  toolName?: string,
  args?: Record<string, unknown>,
  result?: unknown,    // パース済みオブジェクト
  content?: string     // thinking時のテキスト
}
```

**設計判断:**
- JSONL append-only（壊れにくい）
- queryハッシュでファイル分離（クエリ単位の追跡が容易）
- 消去はin-memoryのSetで管理（ファイル自体は不変）→ デバッグ性と運用性の両立

### 2c. ツール制御

```
- canCallTool() / recordToolCall() でツール呼び出し履歴を管理
- findSimilarQuery(): word-overlap Jaccard ≥ 0.7 で類似検出
- TOOLS_REQUIRING_APPROVAL: write_file, edit_file のみ承認制
- session approval: 一度許可すれば同セッション内は全許可
```

### 2d. DCF SKILL.md（8ステップ）

| Step | 内容 | 検証基準 |
|:----:|------|---------|
| 1 | 財務データ収集（5年分） | get_financials, get_market_data |
| 2 | FCF成長率計算 | CAGR計算、15%キャップ、アナリスト突合 |
| 3 | WACC推定 | セクター別テーブル、リスクフリー4%、ERP 5-6% |
| 4 | CF予測（5年） | 年率5%減衰(0.95,0.90...)、ターミナル2.5% |
| 5 | 現在価値計算 | EV→Net Debt控除→1株価値 |
| 6 | 感度分析 | WACC±1% × 成長率3点の3×3マトリクス |
| 7 | サニティチェック | EV乖離30%以内、TV比50-80%、FCF倍率15-25x |
| 8 | 出力 | 仮定表+5年予測+感度+注意事項 |

### 2e. SOUL.md 設計パターン

```markdown
## Identity
"I'm a financial research agent... I think, plan, and learn as I work."
"I'm not a search engine with opinions."

## Investment Philosophy (Buffett/Munger)
- 価格と価値の区別
- Circle of competence
- Margin of safety
- 問題の逆転（inversion）
- メンタルモデル

## Core Drivers
1. Relentless interrogation of data（データへの容赦ない問い）
2. Building instinct（体系構築本能）
3. Technical courage（技術的勇気）
4. Independence（独立判断）
5. Thoroughness as craft（徹底さ=職人技）

## 特異な設計判断: 記憶の放棄
"Each conversation starts fresh" → 記憶がないことを「分析的規律の強制」と再定義
```

---

## §3 盗む/捨てるの仕分け

### 3a. 盗む候補（5パターン）

| # | パターン | Dexterの実装 | systrade適用案 | 優先度 |
|:-:|---------|-------------|---------------|:------:|
| P1 | **Scratchpad JSONL** | append-only、queryハッシュ分離、in-memory消去 | daily_risk.pyの実行ログを構造化JSONL化 | **高** |
| P2 | **DCF SKILL構造** | 8ステップ+サニティチェック3項目+仮定表 | リスクアラート判定スキルをSKILL.md化 | **高** |
| P3 | **類似クエリ検出** | Jaccard ≥ 0.7 | 獏のリサーチ重複排除 | 中 |
| P4 | **コンテキスト溢れ対応** | 古い結果消去+リトライ | 長期パイプライン実行時のメモリ管理 | 低 |
| P5 | **SOUL.md Core Drivers** | 5原則を自然言語でプロンプトに焼く | systrade CLAUDE.mdに投資原則を追記 | **高** |

### 3b. 捨てる候補（4項目）

| # | 要素 | 捨てる理由 |
|:-:|------|-----------|
| D1 | **Financial Datasets API** | 月額ゼロ制約。yfinance+wbgapiで代替済み |
| D2 | **TypeScript/Bun** | Python生態系と異質。再実装コスト > 統合コスト |
| D3 | **WhatsApp Gateway** | 殿はJDim + 2ch BBS。通信レイヤーが完全に異なる |
| D4 | **記憶の放棄思想** | 殿のシステムは没日録=永続記憶。真逆の設計思想 |

### 3c. 保留候補（2項目）

| # | 要素 | 保留理由 |
|:-:|------|---------|
| H1 | **Exa/Tavily Web検索** | 獏(baku.py)が既に担当。ただしExa APIの検索精度は評価する価値あり |
| H2 | **LLM-as-Judge評価** | LangSmithは月額ゼロ制約に抵触。ただしローカル実装でお針子の監査強化に使える |

---

## §4 パターン適用設計（5案のトレードオフ）

### 案A: Scratchpad JSONL導入（推奨 ★）

daily_risk.pyの実行結果を構造化JSONLで記録する。

```python
# src/systrade/scratchpad.py
import json, hashlib, datetime as dt
from pathlib import Path

SCRATCHPAD_DIR = Path("data/processed/scratchpad")

def log_entry(query_hint: str, entry_type: str, data: dict) -> Path:
    """Append a JSONL entry to scratchpad file."""
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    qhash = hashlib.md5(query_hint.encode()).hexdigest()[:12]
    fpath = SCRATCHPAD_DIR / f"{ts}_{qhash}.jsonl"
    entry = {
        "type": entry_type,  # "risk_check" | "fetch" | "alert"
        "timestamp": dt.datetime.now().isoformat(),
        "data": data,
    }
    with open(fpath, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return fpath
```

**利点**: デバッグ容易、没日録DBとの二重記録でも破綻しない、将来ベクトル検索のチャンク元になる
**害点**: ファイル膨張（→ 日次ローテーションで対処）
**スコア**: 9/10

### 案B: リスクアラート SKILL.md化

daily_risk.pyの4層判定ロジックをDexterのDCF SKILL構造で再設計する。

```markdown
# skills/risk_alert/SKILL.md
## Trigger: 日次リスクチェック実行時

### Steps:
1. FRED CSV取得（7日次指標）
2. yfinance取得（Shipping 3、素材4）
3. 月次FRED取得（マクロ4指標）
4. 各指標のシグナル計算（閾値判定）
5. 重み付きスコア集計
6. ラベル判定（SAFE/CAUTION/DANGER）
7. agent-swarm finance板に投稿
8. 検証: バックテスト3大暴落の2/3以上を事前検出

### Validation:
- COVID(2020-02): 事前シグナル検出
- 2022利上げ: 事前シグナル検出
- 2024急落: （部分検出）

### Assumptions:
| 指標 | 閾値(CAUTION) | 閾値(DANGER) | 重み |
|------|:------------:|:-----------:|:----:|
| yield_curve | < 0 | < -0.5 | 3 |
| credit | > 4.5 | > 6.0 | 2 |
| ... | ... | ... | ... |
```

**利点**: ロジックの構造化・再利用性向上、お針子の監査対象として明確化
**害点**: 920行の既存コードをリファクタリングする必要はない（ドキュメントとして並置すれば十分）
**スコア**: 8/10

### 案C: 自己検証ループ（Dexter反復パターンの適用）

Lassoの変数選択に反復検証を追加する。

```python
# src/systrade/select/lasso_verified.py
MAX_ITERATIONS = 5

def verified_select(X, y, min_r2=0.1, max_iter=MAX_ITERATIONS):
    """Lasso変数選択 + 自己検証ループ（Dexterパターン）"""
    for i in range(max_iter):
        result = select_features(X, y)
        # 検証1: R²が最低基準を超えるか
        if result.r2_score < min_r2:
            X = X.drop(columns=[weakest_feature(result)])
            continue
        # 検証2: Walk-Forward OOSで過学習チェック
        oos_r2 = walk_forward_validate(X, y, result)
        if oos_r2 < 0:  # 過学習
            continue
        return result  # 検証OK
    return result  # max_iter到達
```

**利点**: Phase 0の過学習問題（OOS R²=-0.18）への直接的対策
**害点**: 計算コスト増、パラメータチューニングが必要
**スコア**: 7/10

### 案D: SOUL.md → systrade CLAUDE.md強化

殿の投資哲学をDexterのSOUL.md構造でsystrade CLAUDE.mdに焼く。

```markdown
## 殿の投資原則（SOUL）

### Core Drivers
1. 物理の動きは嘘をつかない（鉄道・道路・建材 > ICTユニコーン）
2. 棍棒で殴れる変数のみ使え（Lasso係数非ゼロ = 有効変数）
3. 予測で稼ぐな、リスクを避けろ（magnitude予測断念 → アラート）
4. 月額ゼロ（有料APIは使うな）
5. やってみてから判断（マクガイバー精神）

### Inversion（マンガー式逆転）
「いつ買うか」ではなく「いつ逃げるか」を設計せよ。
daily_risk.pyのスコア0.4以上でDANGER。エクスポージャー削減判断。

### Circle of Competence
- 殴れる領域: アジアインフラ、農業、建材、港湾物流
- 殴れない領域: 暗号資産、バイオテック、SaaS成長株
```

**利点**: OMC Worker投入時に哲学がブレない。Dexterの「SOUL=行動規範の自然言語注入」パターンの直接的転用
**害点**: 既存CLAUDE.mdの改修が必要（軽微）
**スコア**: 8/10

### 案E: 獏(baku.py)にDexterリサーチパターン統合（冒険的案）

獏の好奇心エンジンにDexterの「タスク分解→反復実行→自己検証」ループを組み込む。

```python
# scripts/baku.py に追加
class DexterResearchLoop:
    """Dexterパターンの金融リサーチ自律ループ"""
    MAX_ITER = 5

    def run(self, query: str):
        scratchpad = []
        for i in range(self.MAX_ITER):
            # Step 1: サブクエリ分解（LLM）
            sub_queries = self.decompose(query, scratchpad)
            # Step 2: 各サブクエリを実行（yfinance/FRED/Web）
            for sq in sub_queries:
                result = self.execute_tool(sq)
                scratchpad.append(result)
            # Step 3: 自己検証（十分性判定）
            if self.is_sufficient(query, scratchpad):
                break
        return self.synthesize(query, scratchpad)
```

**利点**: 獏が自律的に金融リサーチを深堀りできるようになる。殿が寝ている間にリサーチが進む
**害点**: LLM API呼び出しコスト増（Haiku使用でも1ループ$0.01程度）、暴走リスク（maxIter必須）、baku.pyの複雑性増大
**スコア**: 6/10（面白いが時期尚早）

### 案の比較表

| 案 | 実装コスト | 既存破壊 | North Star貢献 | リスク | 推奨度 |
|----|:---------:|:-------:|:--------------:|:-----:|:------:|
| A: Scratchpad | 低（1ファイル新規） | なし | ○（知見の構造化蓄積） | 低 | **★★★** |
| B: SKILL.md化 | 低（ドキュメント追加） | なし | ○（監査基準の明確化） | 低 | **★★★** |
| C: 自己検証ループ | 中（lasso拡張） | 低 | ◎（過学習対策直結） | 中 | **★★** |
| D: SOUL.md強化 | 低（CLAUDE.md改修） | 低 | ○（哲学のブレ防止） | 低 | **★★★** |
| E: 獏リサーチ統合 | 高（baku.py大改修） | 中 | △（将来的にはあり） | 高 | **★** |

**推奨: A + B + D を即座に実装（低コスト×高効果）、C を次フェーズで検証、E は保留。**

---

## §5 Phase 0-2への反映提案

### 5a. Phase 0 Lasso: 自己検証パターン適用

現状の問題: OOS R²=-0.18（過学習確定）

Dexterの自己検証ループを参考に、Walk-Forward検証を変数選択パイプラインに組み込む:

```
Lasso選択 → Walk-Forward OOS検証 → R²<0 → 変数削減 → 再選択
                                    → R²≥0 → 採用
```

ただし、殿は既に「magnitude予測断念→リスクアラート」に転換済み。
Lasso自己検証は**リスク指標の選別**に適用するのが現実的:

```python
# daily_risk.pyの指標選択にLasso+自己検証を適用
# → 「殴っても効かない指標」を自動特定
#    例: 2023以降に予測力を失った指標を検出
```

### 5b. 放置運用の自律パイプライン設計

Dexterの「maxIter + scratchpad + 自動終了」パターンを適用:

```
cron (daily)
  ↓
daily_risk.py 実行
  ├── データ取得（FRED/yfinance）
  ├── シグナル計算
  ├── scratchpad.jsonl に記録
  ├── DANGER判定 → agent-swarm finance板に投稿
  └── 自動終了（Dexterの「直接回答→ループ終了」と同じ）
```

**既に daily_risk.py がこのパターンを実質的に実装している。**
追加すべきは scratchpad JSONL化（案A）のみ。

### 5c. リソース制約下の実現可能性

| 制約 | Dexter | systrade | 判定 |
|------|--------|----------|:----:|
| VPS 4GB | Bun + OpenAI API | Python + yfinance | ◎ systrade軽量 |
| 月額ゼロ | Financial Datasets $0.04/req | yfinance/FRED 無料 | ◎ |
| ラズパイ対応 | × (Bun + 大量API) | ○ (Python + CSV) | ◎ |
| Ollama | ○ (プロバイダ切替可) | △ (未統合) | 将来課題 |

### 5d. systrade_phase0_plan.mdとの整合

Phase 0-2計画書の§9で「Phase 3 Dexter統合は殿が実際にPhase 0-2の結果を見てから判断」と記載。

**判定: Phase 0-2の結果は出た。パターンだけ盗んでPhase 3は不要。**

根拠:
1. daily_risk.pyが920行で稼働中。Dexterの機能の70%はPythonで再実装済み
2. Financial Datasets APIはアジア市場カバレッジが不足（前回分析§4b確認済み）
3. 殿はリターン予測を断念し、リスク回避に転換。DCF分析（Dexterの本丸）の優先度が下がった
4. 「パターンを盗む」だけで十分。Dexter自体のfork/統合は投資対効果が合わない

---

## §6 見落としの可能性

拙者の分析には以下の盲点がありうる:

1. **Dexterのcronモジュール**: src/cron/ に定期実行機能がある。daily_risk.pyのcron設計と比較していない。差異があれば知見になる可能性
2. **LLM-as-Judge評価**: DexterのLangSmith連携はコスト問題で捨てたが、ローカル実装（Haiku使用）でリスク判定の精度評価ができる可能性を十分に検討していない
3. **Exa検索API**: 獏のWeb検索より高精度の可能性があるが、月額ゼロ制約との整合を詳細評価していない
4. **案Eの過小評価**: 獏×Dexterリサーチパターンは「殿が寝ている間にリサーチが進む」という戦略的価値があるが、baku.pyの現状の複雑性（宇宙座標系構想）との整合を評価しきれていない

---

## §7 North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    殿の投資仮説（アジアインフラ×ファンダメンタルズ）にDexterのパターンを
    低コストで適用する設計を提示。Phase 0-2の既存成果を壊さず拡張する。
    「パターンだけ盗んでPython再実装」の殿方針に完全合致。
  risks_to_north_star:
    - "案Eの獏統合に走ると、baku.pyの複雑性が爆発しNorth Starから逸脱するリスク"
    - "Dexter的な自律ループをdaily_risk.pyに入れすぎると、放置運用の安定性が損なわれる"
```

---

## §8 総合所見

```
┌──────────────────────────────────────────────────────────────┐
│ Dexterは「設計の教科書」であって「導入すべきツール」ではない。│
│                                                                │
│ 盗むべき3パターン:                                            │
│   1. Scratchpad JSONL（実行ログの構造化）                      │
│   2. SKILL.md（判定ロジックのドキュメント化）                  │
│   3. SOUL.md（投資哲学のプロンプト注入）                       │
│                                                                │
│ Phase 0-2は既に動いている。daily_risk.pyは920行で              │
│ Dexterが16ツールでやることの70%を月額ゼロで実現している。    │
│                                                                │
│ 殿が「いつ逃げるか」に転換した今、DCF分析の優先度は低い。    │
│ パターンだけ盗め。本体は要らない。                            │
└──────────────────────────────────────────────────────────────┘
```

---

*以上。拙者の見立てでは、Dexterの真価は実装ではなく設計思想にある。盗むべきは刀ではなく、刀の鍛え方である。*
