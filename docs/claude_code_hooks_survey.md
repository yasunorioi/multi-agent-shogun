# Claude Code Hooks 調査レポート + 1Mコンテキスト検証

> **作成**: subtask_902 / cmd_410
> **作成者**: ashigaru1
> **日付**: 2026-03-15
> **情報源**: 公式ドキュメント（WebFetch by claude-code-guide agent）+ claude --help 実出力 + .claude/settings.json 実ファイル
> ⚠️ 外部ブログ情報は一切使用していない

---

## タスク1: Hooks 調査・検証

### 1-1. 利用可能なHookイベント一覧（公式ドキュメント確認済み）

| イベント名 | 発火タイミング | matcher対応 | 備考 |
|-----------|--------------|:-----------:|------|
| **SessionStart** | セッション開始・再開時 | ✅ | `startup`, `resume`, `clear`, `compact` でマッチ |
| **InstructionsLoaded** | CLAUDE.md / rules/*.md ロード時 | ✅ | |
| **UserPromptSubmit** | ユーザーがプロンプト送信時 | ❌ | 常に発火 |
| **PreToolUse** | ツール実行前 | ✅ | exit 2 でブロック可能 |
| **PermissionRequest** | パーミッションダイアログ表示時 | ✅ | non-interactive(-p)では発火しない |
| **PostToolUse** | ツール実行成功後 | ✅ | undo不可（実行済み） |
| **PostToolUseFailure** | ツール実行失敗後 | ✅ | |
| **Notification** | Claude Codeが通知送信時 | ✅ | `permission_prompt`, `idle_prompt` でマッチ |
| **SubagentStart** | サブエージェント起動時 | ✅ | |
| **SubagentStop** | サブエージェント終了時 | ✅ | |
| **Stop** | Claudeがレスポンス完了時 | ❌ | 常に発火。task completionではなくすべてのStop |
| **TeammateIdle** | Agent Team の teammate がidle時 | ❌ | 常に発火 |
| **TaskCompleted** | タスク完了時 | ❌ | 常に発火 |
| **ConfigChange** | 設定ファイル変更時 | ✅ | `user_settings`, `project_settings`, `policy_settings`, `skills` |
| **WorktreeCreate** | worktree 作成時 | ❌ | stdout に path を返す必須 |
| **WorktreeRemove** | worktree 削除時 | ❌ | |
| **PreCompact** | コンテキストコンパクション前 | ✅ | `manual`, `auto` でマッチ |
| **PostCompact** | コンテキストコンパクション後 | ❌ | |
| **Elicitation** | MCP serverがuser input要求時 | - | |
| **ElicitationResult** | userがMCP elicitationに応答時 | - | |
| **SessionEnd** | セッション終了時 | ✅ | `clear`, `logout`, `other` でマッチ |

**計21イベント**（公式ドキュメント確認済み）

> **現在使用中**: PreToolUse（gatekeeper_f006.sh）、Stop（stop_hook_inbox.sh）

---

### 1-2. HTTP Hooks（type: "http"）の存否確認

**✅ 存在する。公式ドキュメントに完全記載済み。**

#### 設定フォーマット

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:8080/hooks/post-tool-use",
            "headers": {
              "X-Agent-ID": "$AGENT_ID"
            },
            "allowedEnvVars": ["AGENT_ID"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

#### 仕様

- JSON POST リクエストをエンドポイントに送信
- hookのinputをPOST bodyとして送信
- 2xx レスポンスでJSON返却 → 意思決定に使用
- header値は環境変数補間対応（`$VAR_NAME` / `${VAR_NAME}`）
- `allowedEnvVars` に記載した変数のみ解決（セキュリティ制約）
- 接続エラー時はnon-blocking（hookなしと同じ動作）
- timeout: デフォルト10分（秒単位で設定可）

#### 高札API（http://localhost:8080）との直結設定例

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|Edit|Write",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:8080/hooks/post-tool-use",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:8080/hooks/stop",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

> **注意**: 高札API側で `/hooks/*` エンドポイントの実装が必要。現在未実装のため、導入前に高札側の対応が必要。

---

### 1-3. 足軽の報告漏れ防止に使えるHookイベント評価

#### 現状の課題

- Stop hookで inbox 未読検知は実装済み（stop_hook_inbox.sh）
- しかし「報告書を書いたが send-keys を忘れた」ケースは検知できていない

#### 活用できるイベント

| イベント | 用途 | 優先度 |
|---------|------|:------:|
| **Stop** | 既存: レスポンス完了時にinbox未読確認 + 報告漏れ検知 | ✅ 実装済み |
| **TaskCompleted** | タスク完了時に自動報告確認トリガー | ⭐⭐⭐ 高 |
| **SubagentStop** | サブエージェント終了時の成果物確認 | ⭐⭐ 中 |
| **PreCompact** | コンパクション前にinbox状態保存 | ⭐⭐⭐ 高 |
| **PostCompact** | コンパクション後の身元確認・タスク再確認 | ⭐⭐⭐ 高 |
| **SessionStart** | セッション開始時の初期化・身元確認 | ⭐⭐ 中 |

#### 最も有効な追加案: **PreCompact + PostCompact Hook**

```json
"PreCompact": [
  {
    "matcher": "auto",
    "hooks": [
      {
        "type": "command",
        "command": "bash /home/yasu/multi-agent-shogun/scripts/pre_compact_hook.sh",
        "timeout": 10
      }
    ]
  }
]
```

**効果**: コンパクション前にinbox未報告タスクがあればブロック → 報告完了後にコンパクション実行。

---

### 1-4. 現在の .claude/settings.json Hook設定と拡張案

#### 現在の設定（.claude/settings.json 実ファイル確認済み）

```json
"hooks": {
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "bash /home/yasu/multi-agent-shogun/scripts/gatekeeper_f006.sh",
          "timeout": 5
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /home/yasu/multi-agent-shogun/scripts/stop_hook_inbox.sh",
          "timeout": 10
        }
      ]
    }
  ]
}
```

#### 現在の機能

| Hook | 機能 |
|------|------|
| `PreToolUse/Bash` | gatekeeper_f006.sh: GitHub Issue/PR作成禁止チェック（F006）。違反コマンドをブロック |
| `Stop` | stop_hook_inbox.sh: レスポンス完了時にinbox未読確認。未読あればブロックして通知 |

#### 拡張案（優先度順）

**案A: PreCompact Hook追加（優先度: 高）**

コンパクション前にinbox未報告タスクを強制確認。コンパクション後の記憶喪失による報告漏れを防止。

```json
"PreCompact": [
  {
    "matcher": "auto",
    "hooks": [
      {
        "type": "command",
        "command": "bash /home/yasu/multi-agent-shogun/scripts/stop_hook_inbox.sh",
        "timeout": 10
      }
    ]
  }
]
```

> **注**: stop_hook_inbox.sh はコンパクションにも対応可能（再利用推奨）。

**案B: SessionStart Hook追加（優先度: 中）**

セッション開始・コンパクション復帰時に自動で身元確認スクリプトを実行。

```json
"SessionStart": [
  {
    "matcher": "startup|resume|compact",
    "hooks": [
      {
        "type": "command",
        "command": "bash /home/yasu/multi-agent-shogun/scripts/identity_inject.sh",
        "timeout": 10
      }
    ]
  }
]
```

**案C: ConfigChange Hook追加（優先度: 低）**

設定ファイルの無断変更を検知・記録（セキュリティ監査用）。

```json
"ConfigChange": [
  {
    "matcher": "project_settings|user_settings",
    "hooks": [
      {
        "type": "command",
        "command": "bash /home/yasu/multi-agent-shogun/scripts/config_audit.sh",
        "timeout": 5
      }
    ]
  }
]
```

> **注**: config_audit.sh は未実装。导入前に作成が必要。

**案D: HTTP Hooks による高札API連携（優先度: 要検討）**

HTTP type hookで高札APIに直接送信できる。高札API側の `/hooks/*` エンドポイント実装が前提条件。

---

## タスク2: 1Mコンテキスト確認

### 2-1. Opus 4.6の1Mコンテキスト有効性

**公式ドキュメント確認結果: 技術的には利用可能。ただし現セッションでは未設定。**

#### 現セッションの状態

- 現在のモデル: **Sonnet 4.6**（CLAUDE.md 環境セクションより確認）
- `.claude/settings.json` に `"model"` フィールドなし → デフォルト設定で動作
- `~/.claude/settings.json` にも `"model"` フィールドなし

#### 設定方法（公式ドキュメント確認済み）

**方法1: settings.json に追加**

```json
// ~/.claude/settings.json または .claude/settings.json
{
  "model": "opus[1m]"
}
```

**方法2: 環境変数**

```bash
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-6[1m]'
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-4-6[1m]'
```

**方法3: セッション内コマンド（1セッション限り）**

```
/model opus[1m]
```

#### プラン別利用可能性

| Plan | Opus 4.6 + 1M | Sonnet 4.6 + 1M |
|------|:-------------:|:---------------:|
| **Max, Team, Enterprise** | ✅ 標準包含 | 追加利用要求 |
| **Pro** | 追加利用要求 | 追加利用要求 |
| **API / pay-as-you-go** | ✅ Full access | ✅ Full access |

#### 無効化方法

```bash
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1
```

---

### 2-2. 設定変更の要否

| 項目 | 現状 | 必要な変更 |
|------|------|-----------|
| モデル設定 | 未設定（Sonnet 4.6デフォルト） | `"model": "opus[1m]"` を追加 |
| 1Mコンテキスト | 未有効化 | モデル変更と同時に有効化 |

**推奨設定変更**（殿の承認が必要）:

```json
// ~/.claude/settings.json への追加案
{
  "model": "opus[1m]",
  ...（既存設定維持）
}
```

---

### 2-3. コンパクション頻度の見込み

| 項目 | 現状 (Sonnet 4.6) | 1M設定後 (Opus 4.6 [1m]) |
|------|:-----------------:|:------------------------:|
| コンテキスト上限 | 200K tokens | **1,000K tokens (5倍)** |
| コンパクション頻度 | 高い | **大幅削減見込み** |
| 料金 | 標準 | 1M超過分はプレミアムなし（包含プランはsubscription内） |

**見込み**: 1Mコンテキストを設定すれば、現在のコンパクション頻度が **概ね1/5以下**に低下する見込み。長期タスクでのコンテキスト喪失リスクが著しく低減される。

> **注意**: Opus 4.6 は Sonnet 4.6 より応答速度が遅い可能性がある。速度とコンテキスト量のトレードオフを考慮せよ。

---

## まとめ・推奨アクション

### Hooks

| 優先度 | アクション | 工数見積 |
|:------:|-----------|:--------:|
| ⭐⭐⭐ | **PreCompact hookを追加**（stop_hook_inbox.sh 再利用） | 小（設定変更のみ） |
| ⭐⭐ | **SessionStart hookを追加**（identity_inject.sh 活用） | 小（設定変更のみ） |
| ⭐ | HTTP hooks + 高札API `/hooks/*` エンドポイント実装 | 中（高札API側の実装が必要） |

### 1Mコンテキスト

| 優先度 | アクション |
|:------:|-----------|
| ⭐⭐⭐ | `~/.claude/settings.json` に `"model": "opus[1m]"` を追加（殿の承認後） |

---

## 参考: Hook Handler 4種類

| type | 説明 |
|------|------|
| `"command"` | Shell command 実行（現在使用中） |
| `"http"` | HTTP POST to endpoint（今回確認: **存在する**） |
| `"prompt"` | Single-turn Claude evaluation |
| `"agent"` | Multi-turn subagent with tools |

---

*公式ドキュメントのみを情報源とした。外部ブログ情報は使用していない。*
