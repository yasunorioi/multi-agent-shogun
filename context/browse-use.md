# Claude Code ブラウザ自動操作 調査レポート

> subtask_950 / cmd_427 | 調査日: 2026-03-21 | 担当: ashigaru2

## TL;DR（殿向け要約）

「Browse Use」という単一機能は存在しない。Claude Code のブラウザ自動操作手段は**3種類**ある。
うち「**Claude in Chrome**」（Chrome拡張連携）が最も高機能で、ログイン済みサイトへのアクセスが可能。
既存の MCP Playwright と用途が被るが役割分担は明確。

---

## 1. 正式名称・定義

| 機能名 | 正式名称 | 状態 |
|--------|---------|------|
| ブラウザ連携 | **Claude in Chrome（Chrome integration）** | Beta（2026-03-21時点） |
| 拡張機能 | Claude in Chrome extension | Chrome Web Store 公開済み |
| CLIフラグ | `--chrome` / スラッシュコマンド `/chrome` | v2.0.73以上 |

> ⚠️ 「Browse Use」は非公式表現。公式ドキュメントでの名称は **"Chrome integration"** または **"Claude in Chrome"**。

---

## 2. 仕組み・有効化方法

```
Claude Code CLI (--chrome フラグ)
        ↓ Native Messaging
Chrome拡張機能 (Claude in Chrome)
        ↓ Chrome Extension API
ブラウザ（Chrome / Edge）
        ↓
既存タブ・ログイン済みセッションをそのまま操作
```

**有効化手順**:
```bash
# セッション単位で有効化
claude --chrome

# セッション中に有効化
/chrome

# デフォルト有効化（常時ロードによりコンテキスト消費増に注意）
/chrome → "Enabled by default" を選択
```

**必要要件**:
- Chrome または Edge（Brave/Arc/WSL 非対応）
- Claude in Chrome 拡張機能 v1.0.36以上
- Claude Code v2.0.73以上
- Anthropic 直接プラン（Pro/Max/Team/Enterprise）

---

## 3. できること

| カテゴリ | 具体的な操作 |
|---------|------------|
| **ライブデバッグ** | コンソールエラー・DOM状態の直接読み取り→コード修正 |
| **デザイン確認** | Figmaモックを元にUIを実装→ブラウザで視覚検証 |
| **Webアプリテスト** | フォームバリデーション・ビジュアルリグレッション・ユーザーフロー確認 |
| **認証済みサイト** | Google Docs・Gmail・Notion等、**ログイン済みの任意サイト**をAPI不要で操作 |
| **データ抽出** | Webページから構造化データを取得してCSV等に保存 |
| **タスク自動化** | データ入力・フォーム入力・複数サイト横断ワークフロー |
| **セッション録画** | ブラウザ操作をGIFとして記録・保存 |

**重要な特徴**: ブラウザの**既存ログインセッションを共有**するため、OAuth設定等不要。
ログインページやCAPTCHAに当たった場合は**手動対応を要求して停止**する。

---

## 4. 制約・制限事項

| 項目 | 内容 |
|------|------|
| **プラン** | Pro/Max/Team/Enterprise のみ。Bedrock/Vertex AI/Foundry 経由では**利用不可** |
| **ブラウザ** | Chrome・Edge のみ（Brave/Arc/WSL 非対応） |
| **認証** | claude.ai ログイン必須（API キー認証不可） |
| **コンテキスト** | ブラウザツールが常時ロードされると約18,000トークン消費（9%） |
| **CAPTCHA/ログイン画面** | 自動突破不可。手動対応が必要 |
| **状態** | Beta段階。APIや挙動が変わる可能性あり |
| **JavaScript ダイアログ** | alert/confirm/prompt でブロック → 手動で閉じる必要あり |

---

## 5. 既存ツールとの棲み分け

| ツール | 方式 | セッション共有 | JS実行 | コンテキスト消費 | 主な用途 |
|--------|------|:---:|:---:|:---:|---------|
| **WebFetch** | HTTP GET | ✗ | ✗ | 低 | 公開ページのHTML取得 |
| **WebSearch** | 検索API | ✗ | ✗ | 低 | キーワード検索 |
| **MCP Playwright** | CDP（新規ブラウザ） | ✗ | ✓ | 13.7k tokens (6.8%) | テスト自動化・スクリーンショット |
| **Claude in Chrome** | Chrome拡張API（既存ブラウザ） | **✓** | ✓ | 18.0k tokens (9.0%) | ログイン済みサイト操作・デバッグ |

### 使い分けの指針

```
公開URLのテキスト取得だけ → WebFetch
検索クエリ → WebSearch
認証不要のテスト自動化・スクリーンショット → MCP Playwright（コンテキスト節約）
ログイン必要なサイト操作（Gmail/Notion/社内ツール等） → Claude in Chrome
ローカル開発のデバッグ（コンソールログ確認） → Claude in Chrome
```

---

## 6. shogunシステムでのユースケース

### 適合する場面

| ユースケース | ツール選択 | 理由 |
|------------|-----------|------|
| **技術調査（公開ドキュメント）** | WebFetch / WebSearch | 認証不要 → Claude in Chrome は過剰 |
| **X/Twitter補完** | WebSearch（X Research スキル） | APIベースで十分 |
| **農業情報収集（公開サイト）** | WebFetch | HTML取得で対応可 |
| **獏の夢見リサーチ** | WebSearch → WebFetch | 公開情報なので不要 |
| **GitHub（認証が必要な操作）** | gh CLI > Claude in Chrome | gh CLIが正規ルート |
| **農業系閉鎖ネットワーク管理画面** | **Claude in Chrome** | ログイン必須サイト操作に最適 |
| **ローカル開発のUI確認** | **Claude in Chrome** | localhost へのデバッグに強い |

### shogunシステムでの推奨方針

1. **通常の調査タスク**: WebSearch → WebFetch の順で対応（コスト低）
2. **JS描画が必要な場合**: MCP Playwright（既に導入済み）
3. **ログイン済みサービス操作が必要な場合のみ**: Claude in Chrome を使用
4. **Claude in Chrome はデフォルト無効のまま**（コンテキスト消費9%は高コスト）

---

## 7. MCP Playwright との競合整理

両者は同一用途に使えるが、2026年現在の推奨：

- **MCP Playwright**: テスト自動化・ヘッドレス実行・コンテキスト節約
- **Claude in Chrome**: 既存セッション利用・デバッグ・認証済みサービス操作

> 一部のケースでは「Playwright CLI」（MCPではなくCLIツールとして使う）が最もトークン効率が良い（MCPより4倍省トークン）という知見もあり。

---

## 参考URL

- [Claude Code with Chrome 公式ドキュメント](https://code.claude.com/docs/en/chrome)
- [Claude in Chrome 使い始めガイド](https://support.anthropic.com/en/articles/12012173-getting-started-with-claude-for-chrome)
- [Claude in Chrome ニュース](https://www.anthropic.com/news/piloting-claude-in-chrome)
