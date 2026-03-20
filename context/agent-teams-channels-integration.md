# Agent Teams / Channels 統合分析

> **調査日**: 2026-03-21
> **調査者**: ashigaru1 (subtask_945 / cmd_424)
> **参照**: context/agent-teams-research.md, context/claude-channels-research.md

---

## 1. エグゼクティブサマリー

| 観点 | 結論 |
|------|------|
| **Agent Teams の位置づけ** | shogunのYAML/没日録は**置き換えない**。特定ユースケースで**補完的に活用**可 |
| **Channels の位置づけ** | 殿→老中の外部通信経路として**先行試験価値が最も高い** |
| **移行の基本方針** | 没日録DB・お針子・ペルソナ分離はshogun固有の優位性。捨てるな |
| **今すぐ試せるもの** | `--channels Telegram` による殿のリモートタスク指示 |
| **実験的制約** | Agent Teams（v2.1.32+）、Channels（v2.1.80+）ともに実験段階。本番前提にするな |

---

## 2. 現行shogunシステムとの対応表

### 2-1. エージェント階層

| shogunロール | ペイン | Agent Teams相当 | 備考 |
|-------------|--------|----------------|------|
| 将軍（shogun） | shogun:main.0 | - | 殿との対話専任。移行対象外 |
| 老中（karo） | multiagent:agents.0 | **Team Lead** | 最も近い対応。タスク調整・合成 |
| 足軽1/2（ashigaru） | agents.1-2 | **Teammates** | 実装担当 |
| 部屋子（ashigaru6） | agents.3 | **Teammates（調査特化）** | 調査特化roleとして対応 |
| 軍師（gunshi） | ooku:agents.0 | - | 戦略分析専任。直接対応なし |
| お針子（ohariko） | ooku:agents.1 | TaskCompleted hook | 事後監査 → 事前ゲートに近似 |
| 殿（人間） | - | - | Channels経由でリモート指示が可能に |

### 2-2. タスク管理

| shogun機構 | 実体 | Agent Teams相当 | 差異 |
|-----------|------|----------------|------|
| `queue/inbox/ashigaru*.yaml` | YAML（揮発） | `~/.claude/tasks/{team}/` | AT側はファイルロックで競合防止済み |
| `status: assigned/in_progress/done` | 3状態 | `pending/in_progress/completed` | 名前が違うだけで等価 |
| `blocked_by` フィールド | 依存関係 | Task dependencies | ATは自動アンブロック機能あり（同等） |
| 没日録DB（SQLite） | **永続化** | **なし** | AT最大の欠如。消えたら終わり |
| 家老のみDB書き込み可 | **権限集約** | Leadが管理 | ATはself-claimあり。権限分離は弱い |
| `request_id` + `detail_ref` | 参照方式 | - | shogun独自の軽量化設計 |

### 2-3. 通信・メッセージング

| shogun機構 | 実体 | Agent Teams相当 | Channels相当 |
|-----------|------|----------------|-------------|
| `tmux send-keys`（2回） | 同期通知 | SendMessage（Mailbox） | - |
| `roju_reports.yaml` | 報告inbox | 共有TaskList + Mailbox | - |
| stop hook（idle検知） | 非同期復帰 | TeammateIdle hook | - |
| 殿がCLIで直接入力 | ローカル操作 | - | **Telegram/Discord → Channels** |
| LINE Bot（温室制御） | 外部通知 | - | Channels（同系統） |
| broadcast不可（個別send-keys） | 非効率 | broadcast機能あり | - |

### 2-4. 品質保証

| shogun機構 | タイミング | Agent Teams相当 | Channels相当 |
|-----------|----------|----------------|-------------|
| お針子 15点ルーブリック | **事後** | TaskCompleted hook | - |
| retry-loop（subtask_939） | **事後→自動再送** | TeammateIdle hook（exit 2） | - |
| 設計書必読ルール（F005） | **事前** | Plan approval | - |
| blocked_by依存チェック | **事前** | Task dependencies | - |
| 没日録audit-history（subtask_942） | **記録** | **なし** | - |

### 2-5. 表示・インフラ

| shogun機構 | 実体 | Agent Teams相当 |
|-----------|------|----------------|
| tmux 3セッション構成 | shogun/multiagent/ooku | split-panes mode（tmux利用） |
| shutsujin_departure.sh | 起動スクリプト | TeamCreate（自然言語） |
| scripts/worker_ctl.sh | 動的起動/停止 | Spawn/Shutdown |
| ペイン直接操作（Shift+Down） | tmux操作 | in-process mode（Shift+Down） |

---

## 3. shogunの優位点（移行不要・維持必須）

以下はAgent Teamsに存在せず、shogunが独自に持つ価値である。**絶対に捨てるな。**

| 優位点 | 理由 | 代替手段なし |
|--------|------|-------------|
| **没日録DB（永続化）** | セッション跨ぎ、コンパクション後も参照可。ATはセッション消滅でタスク情報も消える | ✅ |
| **お針子 15点ルーブリック** | 定量的品質評価。ATのTaskCompletedフックは汎用的で採点基準を持たない | ✅ |
| **ペルソナ分離（行動制約）** | 足軽1の暴走グセ・足軽2の過剰分析など、ロール別の弱点認識が品質に直結 | ✅ |
| **audit-history蓄積** | rejected→修正→合格の経緯DB記録。失敗パターン学習が可能 | ✅ |
| **DB権限集約（家老のみ）** | データ整合性保証。ATはself-claimで足軽がタスクを直接取れる（制御が弱い） | ✅ |
| **コンパクション復帰手順** | 長大セッションの確実な復帰。ATはセッション復元不可 | ✅ |

---

## 4. Agent Teamsで補完できること

現行shogunに**追加価値**をもたらし得る機能。

### 4-1. 今すぐ活用可能

**ファイルロックによる競合防止**
- shogunのRACE-001（同一ファイル書き込み禁止）をAT側に任せられる
- 複数足軽が同一ファイルを編集するリスクが自動排除される

**Plan approval（事前設計書レビュー）**
- 現行: instructions/ashigaru.mdでF005「コンテキスト未読禁止」を人手で強制
- AT: Leadが事前承認するまで実装に入れない（ハード制約）
- shogun流儀: `plan_approval_required: true` フィールドをinbox YAMLに追加し、老中がplan approvalを要求するパターン

**Broadcast通知**
- 現行: 各足軽に個別send-keysが必要（コスト大）
- AT: `broadcast` 1回で全員に届く
- 適用場面: 緊急停止・方針転換・全体連絡

### 4-2. 検討段階（条件付き）

**TeammateIdle hookとshogun stop hookの統合**
```
現行: stop_hook_inbox.sh → idle検知 → YAML通知書き込み → send-keys
AT:  TeammateIdle hook  → exit 2    → フィードバック送信 → Teammate再起動
```
→ AT環境下ではTeammateIdle hookをstop_hook_inbox.shにルーティングする設計が可能。
→ ただし: ATは実験的。stop hookのほうが安定。当面は並存。

**TaskCompleted hookとお針子監査の統合**
```
TaskCompleted hook (exit code 2) → お針子の15点監査スクリプトを呼び出す
→ 不合格なら exit 2 でcompletedをブロック → Teammateに修正指示
```
→ retry-loop（subtask_939実装済み）と相性が良い。
→ 現時点では没日録CLI連携が必要で実装コストが高い。

---

## 5. Channelsで補完できること

### 5-1. 最優先: 殿のリモートタスク指示（Telegram）

**現状の課題**:
- 殿はCLIから直接入力するしかない
- 外出時・農作業中にshogunへ指示できない

**Channelsで解決できること**:
```
殿（スマホのTelegram）→ Channelsサーバー → 老中セッション
                     ← reply tool       ← 老中が返答
```

**実装手順**（既存LINE Botとは別系統）:
```bash
# v2.1.80以上確認
claude --version

# Telegramプラグインインストール
/plugin marketplace add anthropics/claude-plugins-official
/plugin install telegram@claude-plugins-official

# 老中セッションをChannels付きで起動
claude --channels plugin:telegram@claude-plugins-official
```

**shogunの老中セッション（multiagent:agents.0）への統合**:
```bash
# shutsujin_departure.sh の老中起動コマンドに --channels を追加する案
claude --channels plugin:telegram@claude-plugins-official
```

### 5-2. CI/CDイベントのプッシュ

**適用場面**: git push → CI失敗 → 老中に自動通知 → 足軽に修正指示

```bash
# カスタムWebhook（--dangerously-load-development-channels必要）
# CI側でcurl → ローカルMCPサーバー → Claudeセッション
curl -X POST localhost:8788 -d "CI failed: test_coverage dropped below 80%"
```

**制約**: Research Preview中はカスタムチャンネルに `--dangerously-load-development-channels` が必要。

### 5-3. 温室制御LINE BotとChannelsの共存

| 用途 | 推奨手段 | 理由 |
|------|---------|------|
| 温室制御（開けろ/閉めろ） | **LINE Bot継続** | 既存農家に配布済み。変えるな |
| shogun指示（殿限定） | **Telegram Channels** | 殿専用。農家と混在させない |
| CI/CD通知 | **カスタムWebhook** | Telegram/Discordに依存しない |

---

## 6. 移行パス（段階的ロードマップ）

### Phase 1: 今すぐ試せる（コスト低・リスク低）

```
[P1-a] Channels（Telegram）試験導入
  条件: claude --version >= 2.1.80
  作業: プラグインインストール + 老中起動コマンド変更
  価値: 殿のリモート指示が可能に
  リスク: Research Preview。プロトコル変更の可能性あり

[P1-b] Agent Teamsのsplit-pane modeを現行tmux環境で確認
  条件: CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
  作業: settings.jsonに1行追加
  価値: ネイティブsplit-panesの使い勝手確認
  リスク: 実験的。shogunの既存ペイン配置と干渉する可能性
```

### Phase 2: 条件付き導入（中コスト・中リスク）

```
[P2-a] TaskCompleted hook → お針子監査 統合
  条件: AT環境でお針子を起動
  作業: TaskCompleted hookスクリプト作成（お針子CLIを呼び出す）
  価値: 完了時の自動品質ゲート
  前提: 没日録CLIとAT環境の統合テスト

[P2-b] inbox YAMLにplan_approval_requiredフィールド追加
  条件: AT環境
  作業: 老中がplan approvalを使うフローをinstructions/karo.mdに追記
  価値: F005（コンテキスト未読禁止）のハード強制
  前提: AT安定化待ち

[P2-c] broadcast機能の活用
  条件: 複数足軽がAT環境で動作
  作業: 緊急通知フローをbroadcastに切り替え
  価値: 個別send-keys廃止→通信コスト削減
```

### Phase 3: 将来検討（高コスト・高リスク）

```
[P3-a] YAML通信 → 共有TaskList 段階的移行
  課題: 没日録DBの永続化をどう維持するか
  方針: 共有TaskListはL3a（揮発）として使い、L3b（没日録DB）は必ず維持
  注意: ATのセッション復元不可制約が解消されるまで全面移行は不可

[P3-b] 全面Agent Teams化（将軍/老中/足軽をATに統一）
  条件: (1)セッション復元可能になる (2)没日録DB統合 (3)お針子ATへの組み込み
  現時点では: 制約多数。2026年末以降の動向を見て判断
```

---

## 7. 移行の禁止事項

| 禁止 | 理由 |
|------|------|
| 没日録DBをATのタスクリストで代替 | セッション消滅でデータが消える。永続化の概念がない |
| お針子をTaskCompleted hookのみに置き換え | 15点ルーブリックの採点ロジックが失われる |
| Agent Teamsを本番前提にする | 実験的機能。`--experimental` フラグなしに依存するな |
| Channelsを将軍ペインに追加 | 将軍は殿との対話専任。外部イベントで割り込み禁止 |
| 全足軽を同時AT化 | セッション復元不可 + ペルソナ分離が崩れる |

---

## 8. 優先度マトリクス

```
高価値
  │  [Telegram Channels] ← 今すぐ試せる。殿のリモート指示
  │  [TaskCompleted+お針子]← 品質ゲートのハード化
  │
  │  [Plan approval]      ← F005強制。設計フェーズに有効
  │  [broadcast]          ← send-keys置換。通信コスト削減
  │
  │  [全面AT化]           ← 将来。制約解消後
低価値│  [CI/CD Webhook]      ← 便利だが --dangerously フラグ必要
  └──────────────────────────────
     低コスト              高コスト
```

---

## 9. 結論・推奨アクション

### 短期（今週）
1. **`claude --version` を確認**し、Channelsの試験可否を判断（v2.1.80以上必要）
2. **Telegram Channels試験**: 老中セッションに `--channels` を追加し、スマホからタスク指示テスト

### 中期（今月）
3. **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` を設定**し、AT動作をshogun環境で確認
4. **TaskCompleted hookとお針子の統合設計**を軍師に依頼（戦略分析向き）

### 長期（今四半期）
5. ATの安定化・セッション復元可能化を待ちながら、**没日録DB+AT統合設計**を策定
6. Channelsの正式リリース後、shutsujin_departure.shに `--channels` 統合

---

*本文書はcontext/agent-teams-research.md（subtask_943）とcontext/claude-channels-research.md（subtask_944）を統合分析したものである。*
