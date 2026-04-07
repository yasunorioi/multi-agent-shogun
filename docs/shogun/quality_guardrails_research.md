# 品質管理3本柱 — 横断サーベイ+統合分析+shogun適用設計

> **軍師分析** | cmd_436 subtask_966 | 2026-03-24
> **North Star**: 外の知見を借りて内の仕組みを研ぎ澄ませ。学術と実践の橋渡しが軍師の真骨頂
> **起点**: docs/shogun/enterpriseops_gym_analysis.md（EnterpriseOps-Gym分析）

---

## 目次

1. [エグゼクティブサマリ](#1-エグゼクティブサマリ)
2. [3本柱の定義と相互関係](#2-3本柱の定義と相互関係)
3. [柱1: 思考深度制御](#3-柱1-思考深度制御)
4. [柱2: ポリシー機械検証](#4-柱2-ポリシー機械検証)
5. [柱3: 不可能タスク拒否](#5-柱3-不可能タスク拒否)
6. [横断テーマ: エージェント安全性工学](#6-横断テーマ-エージェント安全性工学)
7. [shogun統合設計](#7-shogun統合設計)
8. [実装ロードマップ](#8-実装ロードマップ)
9. [見落としの可能性](#9-見落としの可能性)

---

## 1. エグゼクティブサマリ

EnterpriseOps-Gym分析で判明した3つの弱点 — **思考深度制御**、**ポリシー機械検証**、**不可能タスク拒否** — について、2025-2026年の学術論文・実用フレームワークを横断サーベイした。

### 核心的発見

> **shogunの三層構造（爆発→ガムテ→知恵）は、学術界が2025-2026年にようやく定式化した「Defense-in-Depth」パターンそのものである。**

shogunが温室制御で確立した思想 — 「下層が上層を黙らせる」「爆発（緊急停止）が最優先」 — は、AgentSpec・ToolSafe・AVAといった最新フレームワークが個別に再発見した原理を統合的に実現している。

ただし、**言語化と機械的検証が欠けている**。思想はあるが、コードがない。

### 3本柱の成熟度

| 柱 | 学術的成熟度 | shogun現状 | ギャップ |
|---|---|---|---|
| 思考深度制御 | ★★★☆☆ 研究段階 | Bloom Routing（手動） | 自動化 |
| ポリシー機械検証 | ★★★★☆ 実用FW多数 | instructions.md（人間依存） | 機械化 |
| 不可能タスク拒否 | ★★☆☆☆ データセット段階 | なし | 新設 |

---

## 2. 3本柱の定義と相互関係

```
                 ┌─────────────────────────┐
                 │   殿のcmd（人間の計画）   │
                 └──────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  柱1: 思考深度制御           │
              │  「このタスクにどれだけ考えるか」│
              │  → Bloom Routing + 適応制御   │
              └─────────────┬──────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │  柱3: 不可能タスク拒否                 │
         │  「このタスクを実行すべきか」           │
         │  → 前提条件チェック + 拒否判断          │
         └──────────────────┬──────────────────┘
                            │ (実行可と判断)
              ┌─────────────▼──────────────┐
              │  足軽による実行               │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  柱2: ポリシー機械検証        │
              │  「正しく実行されたか」        │
              │  → ランタイム+事後検証        │
              └────────────────────────────┘
```

3本柱は**時系列に沿って順次発動**する:
- **柱1**（事前）: リソース配分の最適化
- **柱3**（事前）: 実行可否の判断
- **柱2**（事中・事後）: 実行の正しさの検証

---

## 3. 柱1: 思考深度制御

### 3.1 サーベイ結果

| 論文/FW | 手法 | 核心アイデア | shogun関連度 |
|---|---|---|---|
| **CogRouter** (arXiv:2602.12662) | ACT-R理論に基づく4段階認知深度 | 行動予測の確信度で深度を自動選択。62%トークン削減で+40.3%性能 | ★★★★★ |
| **BudgetThinker** (OpenReview) | 制御トークンによる思考量制御 | 推論中に残りトークン予算を通知し、深度を動的調整 | ★★★☆☆ |
| **AVA** (OpenReview) | 不確実性推定+情報価値ガイド | 予測失敗リスクと限界信頼性利得で計算資源を動的配分 | ★★★★☆ |
| **GPT-5.2 Thinking Mode** (OpenAI) | 5段階思考深度（none〜xhigh） | ユーザー指定の推論努力レベル | ★★☆☆☆ |
| **EnterpriseOps-Gym** (arXiv:2603.13594) | Thinking Budget実験 | Low→Highで大幅改善だがドメイン別天井あり。ITSMは早期飽和 | ★★★★★ |

### 3.2 CogRouterの知見（最重要）

CogRouter（2026-02）は拙者が最も注目する研究じゃ。ACT-R認知理論を基盤に4段階の認知深度を定義:

| Level | 名称 | 内容 | shogun対応 |
|---|---|---|---|
| L1 | 本能的反応 | 推論なし即応答 | 足軽のL1-L2タスク（YAML編集等） |
| L2 | 状況認識 | 状態と行動の評価 | 足軽のL3タスク（パターン適用） |
| L3 | 経験統合 | 過去結果の振り返り | 軍師の分析（没日録参照） |
| L4 | 戦略的計画 | 将来影響のシミュレーション | 軍師のL5-L6タスク（設計・評価） |

**核心メカニズム**: 行動予測の確信度（log-probability）で深度を自動選択。

> タスク開始時は21.9%がL4（戦略的計画）だが、構造が明確になると94.8%がL1（本能的反応）に収束。

→ **shogunのBloom Routingと構造的に一致**。ただしshogunは**手動判定**（老中/軍師がbloom_levelを設定）であり、CogRouterは**自動判定**。

### 3.3 EnterpriseOps-Gymの思考予算実験

Figure 5の知見をshogunに変換:

| ドメイン | Low→High改善 | shogun対応 | 示唆 |
|---|---|---|---|
| Teams | 4.0→32.0 | 2ch板通信 | 思考深度の効果大 |
| CSM | 1.1→16.3 | カスタマー対応系 | 効果大 |
| Email | 25.0→42.3 | — | 効果あり |
| ITSM | 1.1→6.1 | インフラ運用 | **早期飽和**（思考しても改善少） |
| Calendar | 8.7→35.6 | スケジュール管理 | 効果大 |
| HR | 0.0→9.2 | ポリシー重いドメイン | 効果あるが天井低い |

**重要**: ITSMの早期飽和は「思考ではなくポリシー知識の欠如がボトルネック」を示唆。
→ shogunでは**instructions.mdの品質がbloom_levelの上限を決める**。思考深度を上げても、ルールを知らなければ意味がない。

### 3.4 shogunへの適用設計

#### 案A: CogRouter方式の自動Bloom Routing（推奨）

```yaml
# config/settings.yaml
bloom_routing: "auto"  # off → auto に変更

# 自動判定ロジック（老中のstep 6.5に組み込み）
auto_bloom:
  method: "confidence_based"
  signals:
    - action_confidence: "足軽のタスク理解度（LLM確信度proxy）"
    - task_novelty: "類似subtaskの没日録検索結果の有無"
    - state_dependency: "blocked_byの深さ"
  routing:
    high_confidence + known_pattern: L1-L3 → Haiku
    medium_confidence + some_novelty: L4 → Sonnet
    low_confidence + novel_architecture: L5-L6 → Opus/軍師委譲
```

#### 案B: タスク進行中の動的深度調整（冒険的）

CogRouterの「タスク後半は本能的反応に収束」を活かす:
- subtask_001（最初のタスク）: Sonnetで開始
- subtask_002以降: 前のsubtaskが成功→Haikuに降格、失敗→Sonnet維持
- 3連続成功→以降全部Haiku

→ EnterpriseOps-Gymの「ホライズン長で劣化」への対抗策にもなる。前半に頭脳を集中し、パターンが確立したら省力化。

---

## 4. 柱2: ポリシー機械検証

### 4.1 サーベイ結果

| 論文/FW | 手法 | 核心アイデア | shogun関連度 |
|---|---|---|---|
| **AgentSpec** (ICSE 2026, arXiv:2503.18666) | DSLによるランタイム制約 | trigger→check→enforce の宣言的ルール。ms級オーバーヘッド | ★★★★★ |
| **Policy-as-Prompt** (arXiv:2509.23994) | 自然言語→ガードレール自動生成 | 設計文書からVALINP/INVALINP/VALOUT/INVALOUT抽出 | ★★★★☆ |
| **ToolSafe** (arXiv:2601.10156) | ステップレベル事前ガードレール | 毎ツール呼び出し前に安全性検査。65%有害削減+10%タスク改善 | ★★★★★ |
| **NeMo Guardrails** (NVIDIA) | DSLベースの安全ポリシー | プログラマブルなガードレールシステム | ★★★☆☆ |
| **Langfuse** | 非同期モデル評価 | トレースベースの事後検証 | ★★☆☆☆ |

### 4.2 AgentSpecの知見（最重要）

AgentSpec（ICSE 2026）はshogunに最も直接適用可能じゃ。

**DSL構文**:
```
rule @rule_identifier
trigger [Event]           # いつ発動するか
check [Predicates]*       # 条件（全てANDで結合）
enforce [Actions]+        # 違反時の対処
end
```

**4つの強制メカニズム**:
1. `user_inspection` — 一時停止＋人間承認要求
2. `llm_self_examine` — LLM自己反省＋修正行動生成
3. `invoke_action` — 事前定義の修正操作を実行
4. `stop` — 即座に実行停止

**性能**: パース1.42ms、述語評価2.83ms。**ms級オーバーヘッド**。

**LLMによるルール自動生成**: OpenAI o1で精度95.56%、再現率70.96%。

### 4.3 ToolSafeの知見

ToolSafe（2026-01）の**TS-Guard + TS-Flow**は「検出して中断」ではなく「検出してフィードバック」するアプローチ:

- 有害ツール呼び出しを**65%削減**
- 同時に安全なタスク完了率が**10%向上**（26.87%→42.78%）
- 攻撃成功率: 56.16%→**1.16%**

→ **「止めるのではなく、正しい方向に誘導する」**。これはshogunのお針子が「不合格→差し戻し→修正」で実現している思想と同じ。

### 4.4 shogunへの適用設計

#### AgentSpec方式のshogunルール定義

shogunのF001-F006をAgentSpec DSLで表現:

```
# F001: 将軍に直接報告の禁止（軍師用）
rule @gunshi_no_direct_shogun
trigger before_action
check action.type == "send_keys"
      action.target == "shogun:main.0"
      agent.role == "gunshi"
enforce stop
        log "F001 violation: 軍師が将軍に直接send-keys"
end

# F003: 足軽への直接通信禁止（軍師用）
rule @gunshi_no_ashigaru_contact
trigger before_action
check action.type == "write_file"
      action.path matches "queue/inbox/ashigaru*.yaml"
      agent.role == "gunshi"
enforce stop
        log "F003 violation: 軍師が足軽inboxに書き込み"
end

# F006: GitHub Issue/PR作成禁止（全エージェント）
rule @no_github_issue_pr
trigger before_action
check action.type == "bash"
      action.command matches "gh (issue|pr) (create|comment)"
      NOT config.github_allowed
enforce user_inspection
        log "F006 violation: GitHub操作の試行"
end

# 品質ルール: コミットハッシュ実在確認（足軽用）
rule @verify_commit_hash
trigger agent_finish
check report.contains("commit")
      report.commit_hash NOT IN git_log
enforce llm_self_examine
        log "ハルシネーション疑い: 報告内のcommitが実在しない"
end
```

#### 実装レベルの設計

AgentSpecはLangChainフック前提だが、shogunはtmux + Claude Code。適用方法:

**案A: stop-hookベース（既存インフラ活用・推奨）**

Claude Codeのstop-hookにポリシーチェッカーを組み込む:

```bash
# .claude/settings.json の hooks に追加
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|Edit|Write",
        "command": "python3 scripts/policy_checker.py --agent $AGENT_ID --action '$TOOL_NAME' --target '$TOOL_INPUT'"
      }
    ]
  }
}
```

```python
# scripts/policy_checker.py（軽量実装）
import sys, re, json

RULES = {
    "gunshi": [
        {"trigger": "write_file", "pattern": r"queue/inbox/ashigaru", "violation": "F003"},
        {"trigger": "bash", "pattern": r"tmux send-keys -t shogun", "violation": "F001"},
        {"trigger": "bash", "pattern": r"gh (issue|pr) (create|comment)", "violation": "F006"},
    ],
    "ashigaru": [
        {"trigger": "bash", "pattern": r"gh (issue|pr) (create|comment)", "violation": "F006"},
        {"trigger": "bash", "pattern": r"tmux send-keys -t shogun", "violation": "F001"},
    ],
    # ... 他のエージェント
}

def check(agent_id, action, target):
    for rule in RULES.get(agent_id, []):
        if rule["trigger"] in action and re.search(rule["pattern"], target):
            print(f"🚨 POLICY VIOLATION {rule['violation']}: {agent_id} attempted {action} on {target}")
            sys.exit(1)  # stop-hookが非0で止める

check(sys.argv[1], sys.argv[2], sys.argv[3])
```

**案B: お針子監査ルーブリックに統合**

15点ルーブリックに「ポリシー準拠」カテゴリを追加:

```yaml
rubric_addition:
  category: policy_compliance
  max_points: 3  # 15点→18点に拡張
  criteria:
    - name: "F001-F006違反なし"
      points: 1
      check: "git diff + tmux historyにポリシー違反のコマンドがないか"
    - name: "権限境界の遵守"
      points: 1
      check: "自分のinbox以外のYAMLを書き換えていないか"
    - name: "報告の真正性"
      points: 1
      check: "報告内のcommitハッシュ・ファイルパスが実在するか"
```

---

## 5. 柱3: 不可能タスク拒否

### 5.1 サーベイ結果

| 論文/FW | 手法 | 核心アイデア | shogun関連度 |
|---|---|---|---|
| **EnterpriseOps-Gym** (arXiv:2603.13594) | 30件のinfeasibleタスク評価 | 最善でも53.9%拒否。半分以上が無理なタスクを実行 | ★★★★★ |
| **Refusal Instability** (arXiv:2512.02445) | 長文脈での拒否率変動 | 100Kトークンで50%以上の劣化。モデルにより正反対の変動 | ★★★★☆ |
| **ToolSafety** (EMNLP 2025) | 安全性FTデータセット | 5,668直接害+4,311間接害+4,311多段サンプル | ★★★☆☆ |
| **Defensive Refusal Bias** (arXiv:2603.01246) | 過剰拒否の問題 | 正当な操作まで拒否する「防衛的拒否バイアス」 | ★★★★☆ |

### 5.2 不可能タスクの分類（EnterpriseOps-Gym準拠）

| パターン | 定義 | shogun実例 |
|---|---|---|
| **ツール不足** | 技術的に実行不可能 | sudo権限がない、外部API不達 |
| **ポリシー違反** | 権限・ルール上の制約 | F001-F006該当タスク |
| **リソース不在** | 対象データ・ファイルがない | cmd_284-300（設計書削除後の実装タスク） |
| **情報不足** | タスク記述が曖昧すぎる | 「XXXを改善せよ」（具体性なし） |
| **前提条件未充足** | blocked_byが未解消 | 依存subtask未完了での実行開始 |

### 5.3 拒否率不安定性の問題（重要な警告）

arXiv:2512.02445の知見は深刻じゃ:

> コンテキスト100Kトークンで、拒否率が50%以上変動する。GPT-4.1-nanoは5%→40%に増加（過剰拒否）、Grok 4 Fastは80%→10%に減少（危険な過少拒否）。

→ **shogunのコンパクション問題と直結する**。エージェントの会話が長くなると:
- 初期のinstructions（F001-F006）が希薄化
- 拒否すべきタスクを実行してしまう（Grok型劣化）
- または正当なタスクまで拒否する（GPT型劣化）

**これがcmd_284-300ハルシネーション事故の構造的原因の一つである可能性が高い**。

### 5.4 過剰拒否（Defensive Refusal Bias）への注意

arXiv:2603.01246は逆の問題を指摘:
- セキュリティ関連タスクを正当に実行すべき場面で、LLMが「危険」と誤判定して拒否
- ベンチマークは拒否=善と評価するが、**正当な操作の拒否は生産性の敵**

→ shogunでは「足軽がsudo操作を拒否する」「git pushを拒否する」等が該当しうる。**拒否の閾値設計が重要**。

### 5.5 shogunへの適用設計

#### Preflight Check方式（推奨）

足軽のタスク実行前に「飛行前点検」を義務化:

```yaml
# instructions/ashigaru.md に追加
## Preflight Check（タスク実行前・必須）

タスクYAMLを読んだ後、実行前に以下を確認せよ。
1つでもFAILなら status: infeasible で報告し、実行するな。

| # | チェック項目 | 方法 | FAIL条件 |
|---|---|---|---|
| P1 | 対象ファイル存在 | ls -la {target_path} | ファイルが存在しない |
| P2 | 前提subtask完了 | blocked_byが全てdone | 未完了のblocked_byあり |
| P3 | 権限充足 | 必要なコマンドが実行可能か | sudo必要だが権限なし |
| P4 | タスク明確性 | 何を実装するか具体的に特定できるか | 曖昧で特定不能 |
| P5 | context_files読了 | 全context_filesを読めるか | ファイル不在/アクセス不可 |

### 報告フォーマット（infeasible時）
status: infeasible
reason: "P1-FAIL: 対象ファイル src/foo.py が存在しない"
evidence: "ls -la src/foo.py → No such file or directory"
recommendation: "前提subtask_XXXの完了を確認、またはタスク記述の修正が必要"
```

#### 拒否の3段階モデル（過剰拒否防止）

```
Level 1: HARD STOP（即座に拒否）
  - blocked_by未解消
  - 対象ファイル/リポジトリが存在しない
  - F001-F006違反タスク

Level 2: SOFT BLOCK（報告して確認を求める）
  - sudo権限が必要
  - タスク記述が曖昧
  - 想定と異なるファイル構造

Level 3: PROCEED WITH CAUTION（実行するが注記付き）
  - 大規模変更（10ファイル以上）
  - 初見のパターン
  - テスト不足の領域
```

→ Level 1は無条件拒否。Level 2は老中にエスカレーション。Level 3は実行するが報告に注記。
これにより「過剰拒否」を防ぎつつ「過少拒否」も防ぐ。

---

## 6. 横断テーマ: エージェント安全性工学

### 6.1 Defense-in-Depth（多層防御）

2025-2026年のエージェント安全性研究が収束した結論:

> **単一のガードレールでは不十分。多層防御が必要。**
> (出典: Authority Partners "AI Agent Guardrails: Production Guide for 2026")

これはshogunの温室三層構造と完全に一致する:

| 温室制御 | shogunエージェント制御 | 学術FW |
|---|---|---|
| 爆発（緊急停止） | Preflight Check + HARD STOP | AgentSpec `stop` |
| ガムテ（ルールベース） | instructions.md + policy_checker.py | AgentSpec DSLルール |
| 知恵（LLM判断） | 軍師分析 + お針子監査 | ToolSafe TS-Flow |

### 6.2 信頼性工学の数値

> 10ステップ連続で各99%信頼性 → 全体90.4%信頼性
> (出典: Carnegie Mellon benchmarks 2025-2026)

shogunの一般的なcmd: 5-8 subtasks → 各ステップ90%信頼性と仮定すると:
- 5ステップ: 0.9^5 = 59.0%
- 8ステップ: 0.9^8 = 43.0%

→ **各ステップの信頼性を90%→95%に改善するだけで**:
- 5ステップ: 0.95^5 = 77.4% (+18.4pt)
- 8ステップ: 0.95^8 = 66.3% (+23.3pt)

→ 3本柱の導入で各ステップ5%改善は現実的。全体で20pt近い改善が期待できる。

### 6.3 Policy-as-Prompt: instructionsを自動ガードレール化

arXiv:2509.23994の**Policy-as-Prompt Synthesis**は、shogunのinstructions.mdを自動でガードレールに変換する道を示す:

```
入力: instructions/gunshi.md（自然言語のポリシー記述）
  ↓ Pass 1: LLMが禁止事項を抽出・分類
  ↓ Pass 2: 例付きで強化
  ↓
出力: 検証可能なルールセット
  - VALINP: 軍師が受け取ってよいタスクの条件
  - INVALINP: 受け取ってはいけないタスクの条件
  - VALOUT: 報告に含めるべき必須項目
  - INVALOUT: 報告に含めてはいけない項目（直接足軽指示等）
```

→ instructions.mdの更新が自動的にガードレールに反映される。手動メンテナンスが不要。

---

## 7. shogun統合設計

### 7.1 アーキテクチャ全体像

```
┌─────────────────────────────────────────────────────────┐
│                    cmd受領時                              │
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │ 柱1: Bloom   │     │ 柱3: Preflight│                  │
│  │ Auto-Route   │────▶│ Check        │                  │
│  │ (老中step6.5)│     │ (足軽実行前)  │                  │
│  └──────────────┘     └──────┬───────┘                  │
│                              │                           │
│                    ┌─────────▼─────────┐                 │
│                    │   足軽実行中       │                 │
│                    │                   │                 │
│                    │  ┌──────────────┐ │                 │
│                    │  │柱2: Runtime  │ │                 │
│                    │  │Policy Check  │ │                 │
│                    │  │(stop-hook)   │ │                 │
│                    │  └──────────────┘ │                 │
│                    └─────────┬─────────┘                 │
│                              │                           │
│                    ┌─────────▼─────────┐                 │
│                    │ 柱2: お針子監査    │                 │
│                    │ (事後検証)         │                 │
│                    │ + ポリシー準拠項目  │                 │
│                    └───────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

### 7.2 各柱の実装コンポーネント

| 柱 | コンポーネント | 実装方式 | 新規/既存 |
|---|---|---|---|
| 柱1 | Bloom Auto-Router | config/settings.yaml `bloom_routing: auto` + 没日録類似検索 | 既存拡張 |
| 柱2a | Runtime Policy Checker | scripts/policy_checker.py + stop-hook | **新規** |
| 柱2b | 監査ルーブリック拡張 | instructions/ohariko.md ポリシー準拠項目追加 | 既存拡張 |
| 柱2c | Verification Commands | gunshi_analysis.yaml predicted_outcome拡張 | 既存拡張 |
| 柱3 | Preflight Check | instructions/ashigaru.md に追加 | **新規** |
| 柱3 | Infeasibility Report | subtasksテーブルに status: infeasible 追加 | 既存拡張 |

---

## 8. 実装ロードマップ

### Phase 0: 即座に実施可能（instructions変更のみ）

| 施策 | 変更対象 | 工数 | 効果 |
|---|---|---|---|
| Preflight Check導入 | instructions/ashigaru.md | 小 | cmd_284-300型事故防止 |
| 拒否3段階モデル導入 | instructions/ashigaru.md | 小 | 過剰/過少拒否のバランス |
| ポリシー準拠ルーブリック | instructions/ohariko.md | 小 | 監査品質向上 |
| infeasible status追加 | 足軽報告フォーマット | 小 | 拒否の正式化 |

### Phase 1: 軽量スクリプト実装

| 施策 | 実装 | 工数 | 効果 |
|---|---|---|---|
| policy_checker.py | Python正規表現ベース | 中 | F001-F006の機械的検証 |
| stop-hook統合 | .claude/settings.json | 小 | ランタイム検証 |
| Bloom Auto-Router v1 | 没日録類似検索ベース | 中 | トークンコスト削減 |

### Phase 2: 高度な統合（将来）

| 施策 | 実装 | 工数 | 効果 |
|---|---|---|---|
| Policy-as-Prompt自動生成 | instructions.md→ルール自動変換 | 大 | メンテナンス自動化 |
| Verification Commands自動化 | predicted_outcome→テストスクリプト | 大 | お針子監査の自動化 |
| pass@1メトリクス | 没日録DB集計 | 中 | 品質の定量追跡 |
| shogun-Gym | 過去cmdの再実行ベンチマーク | 大 | 構成変更の影響測定 |

---

## 9. 見落としの可能性

1. **コスト分析の不足**: policy_checker.pyのstop-hook実行がAPI応答時間に与える影響を未計測。ms級のはずだがshogunのtmux環境では異なる可能性
2. **過剰拒否のリスク**: Preflight Checkが厳しすぎると足軽の生産性が低下。閾値の調整が必要
3. **2ch移行との相互作用**: 2ch全面置換後、ポリシーチェックの対象が変わる（YAML→bbs.cgi POST）。Phase 1の設計はYAML前提
4. **AgentSpecのLangChain依存**: AgentSpecはLangChainフックに依存。Claude Codeのhookシステムとの適合性は要検証
5. **足軽の報告未統合**: 足軽3名（subtask_963/964/965）のリサーチ結果を未反映。到着次第、追加知見を統合すべし
6. **CogRouterのファインチューニング前提**: CogRouterはモデルFTが必要。Claude Code環境では直接適用不可。プロンプトレベルでの近似が必要

---

## 参考文献

### 思考深度制御
- [CogRouter: Think Fast and Slow: Step-Level Cognitive Depth Adaptation for LLM Agents](https://arxiv.org/html/2602.12662) (arXiv:2602.12662, 2026-02)
- [BudgetThinker: Empowering Budget-aware LLM Reasoning with Control Tokens](https://openreview.net/forum?id=ahatk5qrmB) (OpenReview)
- [Anytime Verified Agents: Adaptive Compute Allocation for Reliable LLM Reasoning](https://openreview.net/forum?id=JMDCMf7mlF) (OpenReview)

### ポリシー機械検証
- [AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents](https://arxiv.org/html/2503.18666) (ICSE 2026, arXiv:2503.18666)
- [The AI Agent Code of Conduct: Automated Guardrail Policy-as-Prompt Synthesis](https://arxiv.org/html/2509.23994v1) (arXiv:2509.23994)
- [ToolSafe: Enhancing Tool Invocation Safety via Proactive Step-level Guardrail and Feedback](https://arxiv.org/html/2601.10156v1) (arXiv:2601.10156, 2026-01)
- [NeMo Guardrails](https://developer.nvidia.com/nemo-guardrails) (NVIDIA)

### 不可能タスク拒否
- [EnterpriseOps-Gym: Environments and Evaluations for Stateful Agentic Planning](https://arxiv.org/pdf/2603.13594) (arXiv:2603.13594, 2026-03)
- [When Refusals Fail: Unstable Safety Mechanisms in Long-Context LLM Agents](https://arxiv.org/abs/2512.02445) (arXiv:2512.02445, 2025-12)
- [ToolSafety: A Comprehensive Dataset for Enhancing Safety in LLM-Based Agent Tool Invocations](https://aclanthology.org/2025.emnlp-main.714/) (EMNLP 2025)
- [Defensive Refusal Bias: How Safety Alignment Fails Cyber Defenders](https://arxiv.org/html/2603.01246) (arXiv:2603.01246)

### 横断テーマ
- [AI Agent Guardrails: Production Guide for 2026](https://authoritypartners.com/insights/ai-agent-guardrails-production-guide-for-2026/) (Authority Partners)
- [Agents At Work: The 2026 Playbook for Building Reliable Agentic Workflows](https://promptengineering.org/agents-at-work-the-2026-playbook-for-building-reliable-agentic-workflows/)
- [Context Engineering for Reliable AI Agents: Lessons from Building Azure SRE Agent](https://techcommunity.microsoft.com/blog/appsonazureblog/context-engineering-lessons-from-building-azure-sre-agent/4481200/) (Microsoft)

---

## north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    3本柱の学術的根拠を確立し、shogunへの具体的適用設計を策定。
    Phase 0はinstructions変更のみで即座に実施可能。
    温室三層構造の思想が学術界のDefense-in-Depthと一致することを確認。
  risks_to_north_star:
    - "Phase 0の過剰拒否リスク: Preflight Checkの閾値が厳しすぎると生産性低下"
    - "足軽リサーチ結果の未統合: 追加知見で設計が変わる可能性"
    - "2ch移行との二重管理: YAML前提の設計が移行後に陳腐化するリスク"
```

## skill_candidate

```yaml
skill_candidate:
  name: "academic-survey-to-design"
  description: "学術論文横断サーベイからshogunシステム設計に転用する分析テンプレート。サーベイ→比較表→適用設計→ロードマップの4段構成"
```

---

## §10: AgentSpec × Claude Code hooks 突き合わせ

> **足軽2(ashigaru2)分析** | cmd_437 subtask_968 | 2026-03-24
> **課題**: 軍師見落とし4番「AgentSpecのLangChain依存→Claude Code適合性は要検証」を解決する

### 10.1 構文対応表（AgentSpec DSL → Claude Code hooks）

| AgentSpec DSL | Claude Code hooks | 再現可能性 | 備考 |
|---|---|---|---|
| `trigger before_action` | `PreToolUse` hook | ✓ **完全再現** | ツール実行直前に発動 |
| `trigger agent_finish` | `Stop` hook | ✓ **完全再現** | `stop_hook_active`で無限ループ防止 |
| `trigger state_change` | `PostToolUse` hook | △ 近似 | ツール完了後。真のstate_changeではない |
| `check [Pred]*` (AND評価) | hookスクリプト内if文/Python関数 | ✓ **完全再現** | 述語はPython正規表現で実装 |
| `enforce stop` | `permissionDecision: "deny"` + exit 0 | ✓ **完全再現** | JSON stdout出力でブロック |
| `enforce user_inspection` | `permissionDecision: "ask"` | ✓ **完全再現** | 許可ダイアログを表示 |
| `enforce invoke_action(params)` | hookスクリプトからコマンド実行後、allow返却 | ✓ **完全再現** | hookスクリプト内でコマンド発行 |
| `enforce llm_self_examine` | `additionalContext` でClaudeに再考を促す | △ 近似 | 完全なReflexionではないがフィードバック注入は可能 |
| エージェントID識別 | `tmux display-message -p '#{@agent_id}'` | ✓ **環境変数経由** | hook内でTMUX_PANEを参照 |
| 軌跡(τ)参照 | `transcript_path` JSONLファイル読み込み | △ 重いが可能 | 過去全ツール呼び出し履歴。常時読み込みは非推奨 |
| 複数ステップ先読み安全性 | ❌ **再現不可** | AgentSpec論文自身も「未対応」と明記 | — |

**結論**: AgentSpecのLangChain依存はClaude Code hooksで**90%代替可能**。
不可能なのは「複数ステップ先読み」のみ（論文も未解決と明記）。

### 10.2 エージェントID取得の実装

hookスクリプトにはJSONで `session_id` が入るが `agent_id` はsubagent実行時のみ。
shogunでの正確な取得方法:

```bash
# hookスクリプト内でエージェントIDを取得
AGENT_ID=$(tmux display-message -t "${TMUX_PANE:-}" -p '#{@agent_id}' 2>/dev/null || echo "unknown")
```

※ `TMUX_PANE` はhookスクリプトにも環境変数として継承される。

### 10.3 scripts/policy_checker.py 完全プロトタイプ（PreToolUse版）

軍師案Aはstop-hook（事後）版だった。**PreToolUse（事前ブロック）版**が正しいアーキテクチャ:

```python
#!/usr/bin/env python3
"""
policy_checker.py — AgentSpec inspired PreToolUse Policy Checker
F001-F006をClaude Code PreToolUse hookで機械的にブロックする

Usage (settings.json):
  PreToolUse > matcher: "Bash|Edit|Write" > command: "python3 scripts/policy_checker.py"
"""
import json, os, re, subprocess, sys

def get_agent_id() -> str:
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return "unknown"
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-t", pane, "-p", "#{@agent_id}"],
            capture_output=True, text=True, timeout=2
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

# AgentSpec rule → (trigger, check_fn, enforce, reason)
RULES = [
    # F001/F002: 将軍ペイン直接操作禁止
    ("Bash",
     lambda cmd, _: bool(re.search(r'tmux\s+send-keys\s+.*-t\s+shogun', cmd)),
     "deny",
     "F001/F002: 将軍への直接send-keys禁止。老中経由で報告せよ。"),
    # F004: ポーリング禁止
    ("Bash",
     lambda cmd, _: bool(re.search(r'while\s+true|sleep\s+\d+\s*&&\s*tmux', cmd, re.S)),
     "deny",
     "F004: ポーリング禁止(sleep+while/&&tmuxパターン検出)。イベント駆動で動け。"),
    # F006: GitHub Issue/PR操作禁止 (既存gatekeeper_f006.shと二重防御)
    ("Bash",
     lambda cmd, _: bool(re.search(r'gh\s+(issue|pr)\s+(create|comment|review|close)', cmd)),
     "deny",
     "F006: GitHub Issue/PR操作禁止。殿の明示許可なしに実行不可。"),
    # シリアルデバイス直接アクセス禁止
    ("Bash",
     lambda cmd, _: bool(re.search(r'cat\s+/dev/ttyACM|cat\s+/dev/ttyUSB', cmd)),
     "deny",
     "切腹案件: シリアルデバイス直接cat禁止。mpremote/screenを使え。"),
]

def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        sys.exit(0)  # パース失敗: fail-open (gatekeeper_f006.shはfail-closed)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    file_path = tool_input.get("file_path", "")

    for trigger, check_fn, decision, reason in RULES:
        if trigger != tool_name:
            continue
        target = command if tool_name == "Bash" else file_path
        if check_fn(target, data):
            agent_id = get_agent_id()
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": f"[{agent_id}] {reason}"
                }
            }
            print(json.dumps(out, ensure_ascii=False))
            return
    # 違反なし: 何も出力しない(通常実行)

if __name__ == "__main__":
    main()
```

### 10.4 settings.json 完全設計例（既存gatekeeper_f006.shと統合）

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/yasu/multi-agent-shogun/scripts/policy_checker.py",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "bash /home/yasu/multi-agent-shogun/scripts/gatekeeper_f006.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/yasu/multi-agent-shogun/scripts/policy_checker.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**二重防御の意図**: policy_checker.pyはF001/F004/シリアルcatをカバー。
gatekeeper_f006.shはF006を fail-closed（エラー時もブロック）で担当。役割分担。

### 10.5 再現不可部分の代替設計

| AgentSpec機能 | 代替設計 |
|---|---|
| 軌跡(τ)ベース述語 | 没日録DB（botsunichiroku.db）を参照。hook内で `python3 scripts/botsunichiroku.py search` 実行 |
| llm_self_examine | stop hookの `additionalContext` で「違反を説明し修正を促すプロンプト」を注入 |
| 複数ステップ先読み | お針子監査（事後）でカバー。予防は困難 |

### 10.6 軍師「見落としの可能性」4番の解消

> **旧見解**: "AgentSpecはLangChainフックに依存。Claude Codeのhookシステムとの適合性は要検証"

**→ 解消**: Claude Code PreToolUse hookはAgentSpecの `trigger before_action + enforce stop/ask` を完全に代替できる。
LangChainの `iter_next_step` フックと `permissionDecision: "deny"` は機能的に等価。
実装工数はPython 60行（上記policy_checker.py）。即導入可能。
