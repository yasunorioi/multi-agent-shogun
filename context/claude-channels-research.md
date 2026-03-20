# Claude Channels 調査レポート

> subtask_944 / cmd_424 | 調査日: 2026-03-21 | 担当: ashigaru2

## 概要

Claude Channels は **Claude Code の機能**（claude.ai web版ではない）。
MCPサーバーをベースに、外部イベント（チャットメッセージ・CI結果・Webhook等）をClaudeのセッションにプッシュできる仕組み。
現在 **Research Preview** 段階（2026-03-21時点）。

---

## 1. 仕組み（MCPベースの外部イベントプッシュ）

```
外部サービス（Telegram/Discord/Webhook等）
        ↓
ローカルチャンネルサーバー（MCPサーバー）
        ↓ stdio
Claude Code セッション
        ↓（双方向の場合）
reply tool → 外部サービスへ返信
```

**技術的な核心**:
- チャンネル = MCP サーバー（`@modelcontextprotocol/sdk` を使用）
- Claude Code がサブプロセスとして spawn し、stdio 経由で通信
- `capabilities.experimental['claude/channel']` を宣言することでチャンネルとして登録
- イベントは `notifications/claude/channel` メソッドで送信
- Claude のコンテキストに `<channel source="xxx">` タグとして届く

**一方向 vs 双方向**:
- 一方向: アラート・CI結果等、Claudeが受けて作業するのみ
- 双方向: Claudeが reply tool で送り返せる（チャットブリッジ）

---

## 2. 対応サービス

| サービス | 状態 | 必要なもの |
|---------|------|-----------|
| **Telegram** | Research Preview 含む | BotFather でbot作成 → トークン → `/plugin install telegram@claude-plugins-official` |
| **Discord** | Research Preview 含む | Developer Portal でbot作成 → トークン → `/plugin install discord@claude-plugins-official` |
| **Fakechat** | デモ用（localhost） | 外部サービス不要。localhost:8787 でチャットUI |
| **カスタムWebhook** | 自作可能（要Development flag） | MCP SDK + Bun/Node/Deno |

**インストール手順（共通）**:
```bash
# プラグインマーケット追加（必要時）
/plugin marketplace add anthropics/claude-plugins-official

# プラグインインストール
/plugin install telegram@claude-plugins-official
# または
/plugin install discord@claude-plugins-official

# チャンネル有効化して起動
claude --channels plugin:telegram@claude-plugins-official
# 複数同時: スペース区切りで指定可
claude --channels plugin:telegram@claude-plugins-official plugin:discord@claude-plugins-official
```

---

## 3. 制約・制限事項

### 認証要件
- **claude.ai ログイン必須**
- Console API キー認証: **非対応**
- API キー認証: **非対応**

### バージョン要件
- Claude Code **v2.1.80 以上**が必要

### Research Preview の制約
- `--channels` は Anthropic が管理する **承認済みallowlist のプラグインのみ** 受け付ける
- カスタムチャンネル（自作）は `--dangerously-load-development-channels` フラグが必要
- allowlist に追加するには公式マーケットプレイスへの申請 + セキュリティレビューが必要
- Preview 中はフラグ構文やプロトコルが変わる可能性あり

### セッション依存
- イベントはセッションが開いている間のみ届く
- 常時稼働には background process / persistent terminal が必要

### セキュリティ
- 各チャンネルは **送信者 allowlist** を持つ（ペアリングで登録）
- allowlist に未登録の送信者はサイレントに破棄
- `.mcp.json` に登録するだけでは不十分。`--channels` で明示的に有効化が必要
- カスタムチャンネルは **送信者 ID でゲート** 必須（ルーム/チャンネル ID ではなく個人 ID）

---

## 4. プランごとの利用可否

| プラン | デフォルト | 利用方法 |
|--------|----------|---------|
| **Pro / Max**（組織なし） | **利用可能** | セッションごとに `--channels` で opt-in |
| **Team** | **無効**（デフォルト） | 管理者が明示的に有効化が必要 |
| **Enterprise** | **無効**（デフォルト） | 管理者が明示的に有効化が必要 |

**Team/Enterprise の有効化方法**:
- `claude.ai → Admin settings → Claude Code → Channels` で有効化
- または managed settings に `channelsEnabled: true` を設定

> **つまり殿（Pro/Maxプラン）の場合**: `--channels` フラグをつけて起動するだけで利用可能。管理者操作不要。

---

## 5. カスタムチャンネルの作り方（最小構成）

```typescript
// webhook.ts（Bun ランタイム）
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'

const mcp = new Server(
  { name: 'webhook', version: '0.0.1' },
  {
    capabilities: { experimental: { 'claude/channel': {} } },
    instructions: 'イベントは <channel source="webhook"> として届く。',
  },
)

await mcp.connect(new StdioServerTransport())

// HTTP で受けてClaudeにプッシュ
Bun.serve({
  port: 8788,
  hostname: '127.0.0.1',
  async fetch(req) {
    const body = await req.text()
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: {
        content: body,
        meta: { path: new URL(req.url).pathname },
      },
    })
    return new Response('ok')
  },
})
```

テスト方法:
```bash
claude --dangerously-load-development-channels server:webhook
# 別ターミナル
curl -X POST localhost:8788 -d "build failed on main"
```

---

## 6. 関連機能（参考）

| 機能 | 概要 |
|------|------|
| **Remote Control** | 端末からではなくスマホ等でローカルセッションを操作 |
| **Scheduled tasks** | プッシュではなくタイマーポーリング |
| **MCP** | チャンネルの基盤プロトコル |
| **Plugins** | チャンネルをパッケージ化して共有可能にする仕組み |

---

## 参考URL

- [Claude Channels 公式ドキュメント](https://code.claude.com/docs/en/channels)
- [Channels Reference（カスタム構築）](https://code.claude.com/docs/en/channels-reference)
- [公式プラグインリポジトリ](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins)
