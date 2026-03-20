# Agent Teams / Claude Channels 統合分析書

> **subtask_945 / cmd_424** | 分析日: 2026-03-21 | 軍師（gunshi）
> **North Star**: 老中を殺すな — 通信ハブ負荷の分散が目的

---

## 1. 仕様サマリ

### Agent Teams（実験的機能）

| 項目 | 内容 |
|------|------|
| 成熟度 | **Experimental**（デフォルト無効、`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`） |
| アーキテクチャ | Team Lead（1名）+ Teammates（N名）。Lead固定・昇格不可 |
| 通信 | SendMessage（1対1）/ broadcast（全員）/ Mailbox |
| タスク管理 | 共有TaskList。pending→in_progress→completed。依存関係あり |
| 自律性 | **Self-claim**: teammate完了後に次の未割当タスクを自動取得 |
| 表示 | tmux環境ではsplit-panes自動選択（shogunと親和性あり） |
| 権限 | LeadからSpawn時に一括継承。Spawn後は個別変更可 |
| Plan承認 | Leadがteammateの実装計画を承認/却下するフロー |
| Hook | `TeammateIdle`（idle直前）、`TaskCompleted`（完了直前） |
| 制約 | セッション復元不可、ネスト禁止、1チームのみ、ステータスラグあり |

### Claude Channels（Research Preview）

| 項目 | 内容 |
|------|------|
| 成熟度 | **Research Preview**（Agent Teamsよりさらに初期段階） |
| 本質 | MCPサーバーベースの外部イベントプッシュ。内部通信機構ではない |
| 対応サービス | Telegram、Discord、カスタムWebhook（Bun/Node/Deno） |
| 認証 | claude.aiログイン必須。**APIキー認証は非対応** |
| 方向 | 一方向（アラート受信のみ）or 双方向（reply tool で返信） |
| 制約 | セッション開放中のみ受信、承認済みプラグインのみ（カスタムは要Devフラグ） |
| プラン | Pro/Max: 利用可。Team/Enterprise: 管理者有効化必要 |

**根本的な違い**: Agent Teams = **内部エージェント間協調**、Claude Channels = **外部イベント受信**。競合ではなく補完関係。

---

## 2. 現行shogunシステムとの対応表

### 2a. 機能マッピング

| shogun現行 | Agent Teams | Claude Channels | 置換可否 |
|------------|-------------|-----------------|----------|
| **tmux send-keys** | SendMessage / broadcast | — | △ 部分的に可。ただしtmux pane制御の柔軟性を失う |
| **YAML inbox** | 共有TaskList | — | △ 配布は代替可。だがYAMLのカスタムフィールド（bloom_level, worktree, north_star）は失われる |
| **没日録DB** | **対応なし** | **対応なし** | ✕ 代替不可。セッション揮発で永続化できない |
| **お針子監査** | TaskCompleted hook（簡易） | — | ✕ ルーブリック採点・Foreman方式は代替不可 |
| **ペルソナ分離** | Spawnプロンプトで指示 | — | △ 浅い指示は可。instructions/*.mdレベルの深い分離は困難 |
| **Bloom routing** | **対応なし** | — | ✕ TaskListに知能はない。配布のみ |
| **blocked_by DAG** | Task dependency（基本的） | — | △ 基本依存は可。auto_unblockやDAG構造は未検証 |
| **identity_inject.sh** | 不要（Lead管理） | — | ○ 代替可 |
| **dashboard.md** | — | 外部通知（Discord/LINE） | △ 補完可（殿への通知経路追加） |

### 2b. shogunの優位点（Agent Teamsに存在しない機能）

| 機能 | shogun | Agent Teams | 重要度 |
|------|--------|-------------|--------|
| セッション超越の永続化 | 没日録DB | なし（揮発） | **致命的** |
| 独立した品質ゲート | お針子（別エージェント） | TaskCompleted hook（弱い） | **高** |
| Bloom-based知的ルーティング | 家老の五つの問い + bloom_routing | Lead手動判断のみ | **高** |
| 深いペルソナ（口調・行動制約・キャラシート） | instructions/*.md | Spawnプロンプト（浅い） | **中** |
| PDCA Loop | 軍師→足軽→お針子→軍師 | なし | **中** |
| 監査ルーブリック（15点採点） | お針子スキル | なし | **中** |
| DB権限分離 | 家老のみ書き込み可 | 全teammate同一権限 | **低**（同一マシン） |

### 2c. Agent Teamsの優位点（shogunに存在しない機能）

| 機能 | Agent Teams | shogun現行 | 重要度 |
|------|-------------|------------|--------|
| **Self-claim** | 完了→次タスク自動取得 | 家老が毎回手動配布 | **高（老中負荷直結）** |
| **Plan approval** | 実装前にLeadが承認/却下 | なし（事後監査のみ） | **中** |
| **native messaging** | SendMessage（プロトコル保証） | tmux send-keys（文字列ベース） | **中** |
| **broadcast** | 全員一斉通知 | send-keysを1人ずつ | **低** |
| **Hook** | TeammateIdle / TaskCompleted | stop hook（類似実装済み） | **低** |

---

## 3. 段階的移行プラン

### 前提認識

**老中ボトルネックの分解**:
```
老中の仕事 = (A)タスク分解 + (B)タスク配布 + (C)報告受理 + (D)監査依頼 + (E)dashboard更新
              ^^^^^^^^^^^^^^^^                   ^^^^^^^^^^^^^^^
              知的作業（代替困難）                 機械的作業（代替可能）
```

Agent Teamsが解消できるのは **(B)タスク配布** と **(C)報告受理** の機械的部分のみ。
**(A)タスク分解**（五つの問い・Bloom routing）は老中の知的判断であり、TaskListでは代替できない。

**つまり**: 老中を殺している真因はタスク配布の量ではなく、**タスク分解の認知負荷**。
Agent Teamsは配布を自動化するが、分解は自動化しない。

### Phase 0: 共存試行（推奨開始点）

**目的**: リスクを最小化しつつ、Agent Teamsの実用性を検証

| 項目 | 内容 |
|------|------|
| 対象 | L1-L3の単純タスクのみ（Bloom routing: 足軽直送レベル） |
| 方式 | 老中がタスク分解→TaskListに投入→足軽がself-claim |
| 維持 | 没日録DB、お針子監査、YAML通信はそのまま |
| 追加 | Claude ChannelsでDiscord/LINE通知（殿への完了報告） |
| 検証項目 | self-claimの信頼性、ステータスラグの影響、トークンコスト実測 |
| 期間 | 1-2週間 |
| 撤退条件 | ステータスラグで依存タスクが破損 / トークンコスト2倍超 |

```
老中 ──(タスク分解)──→ TaskList ──(self-claim)──→ 足軽
  │                                                    │
  │←──(完了通知: SendMessage)────────────────────────────┘
  │
  └──(没日録DB記録・お針子監査依頼は従来通り)
```

### Phase 1: 部分移行（Phase 0成功後）

**目的**: L1-L3の配布を完全にTaskList化し、老中の機械的作業を削減

| 項目 | 内容 |
|------|------|
| 対象 | L1-L3全タスク（L4-L6は従来の軍師委譲フロー維持） |
| 方式 | YAML inbox廃止（L1-L3のみ）→ TaskList一本化 |
| 追加 | dual-write: TaskList + 没日録DB（永続化は没日録で担保） |
| お針子 | TaskCompleted hookでお針子に自動通知（手動依頼を半自動化） |
| 老中の役割変化 | 配布者→**設計者**（タスク分解とBloom判定に専念） |

```
cmd受領 → 老中(タスク分解+Bloom判定)
  │
  ├── L1-L3 → TaskList → 足軽self-claim → TaskCompleted hook → お針子
  │
  └── L4-L6 → 軍師(従来通り) → 老中 → 足軽(従来通り)
```

### Phase 2: 完全移行（現時点では非推奨）

**前提条件（未達成）**:
- [ ] Agent Teamsがstableリリース
- [ ] セッション復元（/resume）対応
- [ ] ネストチーム対応（Lead→Sub-Lead→Teammates）
- [ ] カスタムTaskListフィールド対応（bloom_level, north_star等）

| 項目 | 内容 |
|------|------|
| 対象 | 全タスク（L1-L6） |
| 方式 | 老中 = Team Lead、足軽 = Teammates、軍師 = 専門Teammate |
| 没日録 | Hook経由で自動記録 |
| お針子 | 専門Teammate（TaskCompleted hookで自動起動） |

**拙者の所見**: Phase 2は**少なくとも半年以上先**。現時点で設計する価値は低い。
実験的機能の安定化を待て。設計するなら安定化後に改めて分析すべき。

---

## 4. リスク・制約

### 4a. 技術的リスク

| リスク | 深刻度 | 影響 | 緩和策 |
|--------|--------|------|--------|
| **セッション復元不可** | 🔴 高 | コンパクション・/clear後にteammateが消滅 | Phase 0-1では没日録+YAMLを維持し、復元は従来手順で対応 |
| **ステータスラグ** | 🟡 中 | 依存タスクが不適切にブロックされる | 依存関係のあるタスクはPhase 0対象外とする |
| **1チーム制限** | 🟡 中 | 複数cmd並行時にチーム分離不可 | cmdごとにTaskListをフィルタリング（タグ運用） |
| **Lead固定** | 🟡 中 | 老中がダウンするとチーム全体が停止 | 没日録DBがあれば別セッションから復帰可能 |
| **ネスト禁止** | 🟡 中 | 軍師→足軽の指揮系統をTeam内で再現不可 | 軍師はTeam外（従来通り別ペイン）で運用 |

### 4b. コストリスク

| 項目 | 現行 | Agent Teams採用後 |
|------|------|-------------------|
| 足軽2名並列 | 2セッション | 2 teammates（≒同等） |
| 老中のタスク配布 | send-keys（トークン消費なし） | SendMessage（Lead側トークン消費あり） |
| broadcast | 不使用 | team size × メッセージトークン |
| 推定コスト増 | — | **+10-20%**（配布通信のオーバーヘッド） |

### 4c. 運用リスク

| リスク | 説明 |
|--------|------|
| **API変更** | Experimental/Preview段階。フラグ構文・プロトコルが変わる可能性あり |
| **学習コスト** | 老中のinstructions改修、足軽のworkflow変更が必要 |
| **デバッグ困難** | Agent Teams内部の通信エラーは不透明（tmux send-keysは`capture-pane`で確認可能） |
| **ロールバック** | Phase 0は容易。Phase 1以降はYAML inbox復旧が必要 |

---

## 5. 推奨案

### 5a. 結論: **選択的採用（Phase 0 + Channels通知）**

```
┌──────────────────────────────────────────────────┐
│ 推奨: Phase 0（L1-L3 self-claim試行）            │
│     + Claude Channels（殿への外部通知）           │
│                                                  │
│ 非推奨: Phase 1-2への即時移行                     │
│ 理由: 実験的機能の安定化を待つべき                 │
└──────────────────────────────────────────────────┘
```

### 5b. 根拠（North Star: 老中を殺すな）

**老中ボトルネックの真因分析**:

| 老中の負荷 | 比率（推定） | Agent Teamsで解消？ |
|-----------|-------------|-------------------|
| (A) タスク分解（五つの問い・Bloom routing） | 40% | ✕ 不可 |
| (B) タスク配布（inbox_write.sh・send-keys） | 20% | ○ self-claimで代替 |
| (C) 報告受理・処理（roju_reports.yaml） | 20% | △ 部分的に自動化可 |
| (D) 監査依頼（お針子通知） | 10% | △ TaskCompleted hookで半自動化 |
| (E) dashboard更新 | 10% | ✕ 不可（人間用出力） |

**Agent Teamsが解消できるのは老中負荷の20-30%に過ぎない。**

老中の真の負荷は(A)タスク分解にある。これはAgent Teamsではなく、以下で解消すべき:
1. **軍師の権限拡大**: L4-L5のタスク分解も軍師に委譲（現状は分析のみ）
2. **パターン化**: 繰り返し登場するタスク型のテンプレート化
3. **CCA roadmap項目**: validation-retry loopの自動化（rejected→自動差し戻し）

### 5c. Claude Channelsの活用提案

Channelsは内部通信の代替ではなく、**殿への通知経路**として活用すべき:

| ユースケース | 方式 |
|------------|------|
| タスク完了通知 | カスタムWebhook → Discord/LINE |
| エスカレーション（🚨要対応） | dashboard.md更新 + Channel通知 |
| 獏の夢見結果通知 | baku.py → Channel → 殿のスマホ |

**ただし**: Research Previewの制約（claude.aiログイン必須、承認済みプラグインのみ）があるため、
カスタムWebhookは `--dangerously-load-development-channels` が必要。本格運用にはstable待ちが望ましい。

### 5d. 代替案（Agent Teams不採用の場合）

Agent Teamsを**採用しない**場合でも、老中負荷は以下で軽減可能:

| 施策 | 効果 | コスト |
|------|------|--------|
| inbox_write.sh のバッチ配布（複数足軽一括） | B削減 | 低 |
| お針子のauto-trigger（stop hook強化） | D削減 | 低 |
| 軍師のタスク分解権限拡大 | A削減 | 中（instructions改修） |
| rejected→自動差し戻し（CCA roadmap #4） | C削減 | 中 |

**拙者の見立て**: 上記4施策で老中負荷の30-40%を削減可能。
Agent Teams Phase 0と同等以上の効果を、既存アーキテクチャ内で実現できる。
**両方やるのが最善だが、どちらか一方なら既存改善を先行すべき**。

### 5e. 冒険的な案（拙者の技術的冒険心が…少し面白いと思っている）

**Hybrid Lead構想**: 老中をAgent Teams Leadとして起動し、足軽をTeammatesにする。
ただし没日録DB・お針子・軍師は従来のtmuxペインで維持。

```
老中(Team Lead) ──TaskList──→ 足軽1(Teammate)
       │                      足軽2(Teammate)
       │
       ├──tmux send-keys──→ 軍師(従来ペイン)
       ├──tmux send-keys──→ お針子(従来ペイン)
       └──没日録DB──────→ 永続化(従来通り)
```

利点: 足軽のself-claimを得つつ、軍師・お針子の独立性を維持。
リスク: tmux paneとTeammates paneの混在による操作の複雑化。
**検証に値するが、Phase 0試行で実用性を確認してからの判断を推奨**。

---

## 6. 見落としの可能性

拙者の分析に以下の盲点があり得る:

1. **Agent Teamsのトークンコスト実測値が不明**: 公式は「significantly more」としか述べていない。Phase 0で実測すべき
2. **Proプランのレート制限**: Agent Teamsでteammate数を増やした際のレート制限への影響が未検証
3. **tmux session内でのAgent Teams動作**: shogunが既にtmuxを使っているため、split-panesモードとの干渉がないか未検証
4. **Claude Channelsの進化速度**: Research Previewの卒業時期が不明。仕様変更リスクの定量化が困難
5. **殿のProプランでのChannels利用可否**: Pro/Max利用可能とあるが、殿の契約形態によっては追加設定が必要な可能性

---

*本文書は軍師（gunshi）による戦略分析である。2026-03-21時点の公式ドキュメントに基づく。*
*実験的機能の仕様は変更される可能性がある。Phase 0試行後の再評価を推奨する。*
