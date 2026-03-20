# Agent Teams 公式ドキュメント調査

> **調査日**: 2026-03-21
> **調査者**: ashigaru1 (subtask_943 / cmd_424)
> **出典**: https://code.claude.com/docs/en/agent-teams

---

## 1. 概要

Agent Teamsは複数のClaude Codeインスタンスをチームとして協調動作させる機能。
1つのセッションがteam leadとなり、残りのteammateを生成・調整する。

**現状**: 実験的機能（デフォルト無効）

---

## 2. 有効化方法

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` を `1` にセットする。

### settings.json で設定
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### または環境変数で設定
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**必要バージョン**: Claude Code v2.1.32以上（`claude --version` で確認）

---

## 3. アーキテクチャ

| コンポーネント | 役割 |
|--------------|------|
| **Team Lead** | チームを作成・teammates生成・作業調整するメインセッション |
| **Teammates** | 各自独立したコンテキストウィンドウで並列作業するClaude Codeインスタンス |
| **Task List** | 全員が共有するタスクリスト。自律的なclaimが可能 |
| **Mailbox** | エージェント間メッセージングシステム |

**ストレージ**:
- チーム設定: `~/.claude/teams/{team-name}/config.json`
- タスクリスト: `~/.claude/tasks/{team-name}/`

---

## 4. TeamCreate の仕組み

明示的なAPIではなく、**自然言語でLeadに指示する**だけでチームが作られる。

```text
Create an agent team with 3 teammates: one for UX, one for architecture, one as devil's advocate.
```

Claude自身がタスクの複雑さを判断し、チーム生成を提案することもある（ユーザー承認が必要）。

**mate数指定も可能**:
```text
Create a team with 4 teammates. Use Sonnet for each teammate.
```

---

## 5. SendMessage の仕組み

### message（特定mate宛）
```text
Ask the researcher teammate to investigate the authentication module.
```
Leadから特定teammateへ、またはteammateからteammateへ直接送信可能。

### broadcast（全員宛）
```text
Tell all teammates to stop and report current status.
```
全teammateに同時送信。コスト増加に注意（team size × トークン）。

### メッセージ配信
- **自動配信**: テキスト送信後、受信側に自動デリバリー。Leadがポーリング不要。
- **idle通知**: teammate終了時、自動でLeadに通知。
- **直接インタラクション**:
  - in-processモード: `Shift+Down` でterminate循環 → 直接タイプ
  - split-paneモード: ペインをクリックして直接対話

---

## 6. 共有TaskList の仕組み

チーム全体で共有される作業キュー。ファイルロックで競合防止。

### タスク状態
- `pending` → `in_progress` → `completed`

### タスク依存関係
- blocked: 未完了の依存タスクがあるとclaimできない
- 依存タスクが完了すると自動アンブロック（手動操作不要）

### タスク割当方法
1. **Leadが明示的に割当**: `Tell the researcher teammate to take task X`
2. **Self-claim（自律）**: teammate自身が完了後に次の未割当タスクを自動クレーム

### タスク数の目安
- 1teammateあたり5〜6タスクが最適
- 15タスクなら3teammates推奨

---

## 7. 表示モード

| モード | 説明 | 条件 |
|--------|------|------|
| **in-process** | 全teammates同一terminal内。`Shift+Down`で循環 | 任意のterminal |
| **split-panes** | 各teammateが独自ペイン。同時表示可 | tmuxまたはiTerm2必須 |

**デフォルト（`"auto"`）**:
- tmuxセッション内 → split-panes
- それ以外 → in-process

**settings.jsonで上書き**:
```json
{
  "teammateMode": "in-process"
}
```

**shogunとの親和性**: shogunはtmux環境のため、デフォルトでsplit-panes動作する。

---

## 8. Permissions（権限）

- Teammatesは**Leadの権限設定を引き継ぐ**
- Leadが `--dangerously-skip-permissions` で起動 → 全teammates同様
- Spawn後は個別变更可能
- Spawn時に個別設定はできない（一括のみ）

---

## 9. Plan Approval（計画承認）

リスクの高いタスクでは、teammate実装前に計画承認を要求できる。

```text
Spawn an architect teammate. Require plan approval before they make any changes.
```

フロー:
1. Teammate → read-onlyでプランニング
2. → Leadに plan approval request を送信
3. Leadが承認 or 却下（フィードバック付き）
4. 却下 → teammate再プランニング → 再送
5. 承認 → 実装開始

---

## 10. Hooks との連携

| Hook | 発火タイミング | 利用方法 |
|------|--------------|--------|
| `TeammateIdle` | teammateがidle状態になる直前 | exit code 2 でフィードバック送信・継続 |
| `TaskCompleted` | タスクがcompleted状態になる直前 | exit code 2 で完了阻止・フィードバック |

---

## 11. 制約・制限事項

| 制限 | 詳細 |
|------|------|
| **実験的機能** | プロダクション用途には非推奨 |
| **セッション復元不可** | `/resume`・`/rewind` でin-process teammatesは復元されない |
| **タスクステータスラグ** | 完了マークが遅れ、dependent tasksがブロックされることがある |
| **シャットダウン遅延** | 現在のリクエスト/ツール呼出し完了後でないと停止しない |
| **1チームのみ** | 1セッション = 1チーム。複数チーム同時不可 |
| **ネストチーム禁止** | TeammatesがさらにTeammatesを生成できない |
| **Leadは固定** | チーム作成セッションが終生Lead。昇格・移譲不可 |
| **権限はSpawn時確定** | Spawn後個別変更可だが、Spawn時に個別設定不可 |
| **split-panes制限** | VS Code統合terminal・Windows Terminal・Ghosttyでは不使用 |

---

## 12. Proプランでの利用可否

ドキュメントには**プラン別制限の記載なし**。ただし以下の注記あり：

- 「Agent teams use significantly more tokens than a single session」
- トークン消費はtermatesの数に比例
- 「See agent team token costs for usage guidance」（`/en/costs#agent-team-token-costs`）

**結論**: Proプラン固有の制限なし（利用可能と推測）。ただしトークン消費が大幅増加するため、コスト設計に注意が必要。

---

## 13. Subagentsとの比較

| 項目 | Subagents | Agent Teams |
|------|-----------|-------------|
| コンテキスト | 独自ウィンドウ（結果を親に返す） | 独自ウィンドウ（完全独立） |
| 通信 | 親agentのみに報告 | Teammates間で直接メッセージ |
| 調整方式 | 親agentが全管理 | 共有TaskListで自律協調 |
| 適用場面 | 結果だけが必要な集中タスク | 議論・協調が必要な複雑作業 |
| トークンコスト | 低（結果summaryが親に戻る） | 高（各teammateが独立Claudeインスタンス） |

---

## 14. shogunシステムとの関係

### 類似点
- 共有TaskList ≈ shogunの`queue/inbox/`YAML
- Mailbox ≈ shogunの`queue/inbox/roju_reports.yaml`
- Team Lead ≈ 老中（karo）
- Teammates ≈ 足軽（ashigaru）

### 差異・shogunの優位点
- shogunは**没日録DB永続化**（セッション超越）
- shogunは**お針子監査**（品質ゲート）
- shogunは**ペルソナ分離**（役割ベースの口調・行動制約）
- shogunは**DB権限集約**（家老のみ書き込み可）
- shogunは**blocked_by + auto_unblock**（依存関係管理）

### 取り入れ検討の余地
- `TeammateIdle` hook → shogunのstop hookで類似実装済み
- `TaskCompleted` hook → お針子の事後監査で代替可
- Plan approval → 没日録の設計書レビューフローで代替可

---

## 15. ベストプラクティス

1. **チームサイズは3〜5名から始めよ**（それ以上は協調オーバーヘッドが増大）
2. **各タスクは自己完結型に**（1関数・1テストファイル・1レビュー）
3. **同一ファイル編集禁止**（ownershipを分割せよ）
4. **コンテキストはSpawnプロンプトに明記**（Lead会話履歴は引き継がれない）
5. **最初はresearch/reviewから**（並列探索の価値を低リスクで体験）
6. **LeadのみClean upを実行**（Teammatesがやると破損リスク）

---

*本文書は公式ドキュメント（2026-03-21時点）をshogunシステム視点で整理したものである。*
