# LINE Notify実装ガイド

> **Version**: 1.0.0
> **作成日**: 2026-02-06
> **対象**: Arsprout農業IoTシステム
> **関連**: LINE_INTEGRATION_GUIDE.md, ERROR_HANDLING_DESIGN.md

---

## 1. 概要

本ドキュメントは、ArsproutシステムにLINE Notify機能を実装するための実践的な手順書です。
基本的なテキスト通知の送信機能を、Node-REDフローとして提供します。

### 実装範囲

本ドキュメントでカバーする内容:
- ✅ LINE Notifyトークンの取得
- ✅ Node-REDフローのインポート
- ✅ 基本的なテキスト通知の送信
- ✅ エラーハンドリング（認証エラー、レート制限）

今後の拡張（別途実装予定）:
- ⏳ 画像付き通知
- ⏳ エラーアラート自動送信フロー（別フロー: error_alert_flow.json）
- ⏳ 通知抑制・エスカレーション

---

## 2. LINE Notifyトークンの取得

### 2.1 事前準備

- LINEアカウント（スマホアプリでログイン済み）
- Webブラウザ

### 2.2 トークン発行手順

1. **LINE Notify公式サイトにアクセス**
   ```
   https://notify-bot.line.me/ja/
   ```

2. **ログイン**
   - 右上の「ログイン」ボタンをクリック
   - LINEアカウントでログイン

3. **マイページを開く**
   - 右上のアカウント名 → 「マイページ」

4. **トークンを発行**
   - 「トークンを発行する」ボタンをクリック
   - トークン名を入力（例: `温室アラート` または `Arsprout通知`）
   - 通知を送信するトークルームを選択:
     - **個人で受け取る場合**: 「1:1でLINE Notifyから通知を受け取る」
     - **グループで受け取る場合**: 対象のグループを選択
   - 「発行する」ボタンをクリック

5. **トークンをコピー**
   - 発行されたトークンが表示される（例: `AbCdEfGhIjKlMnOpQrStUvWxYz1234567890`）
   - **重要**: このトークンは再表示できません。必ずコピーして安全な場所に保存してください
   - コピーしたら「閉じる」

### 2.3 トークンの管理

#### セキュリティのベストプラクティス

- ✅ トークンはGitにコミットしない（`.gitignore`に追加）
- ✅ 定期的にトークンをローテーション（3-6ヶ月毎）
- ✅ 不要になったトークンは削除（LINE Notifyマイページから）
- ❌ トークンをSlack・メールで共有しない

#### トークン保存場所の推奨

```
/config/.env            # 環境変数ファイル（Git管理外）
または
Node-REDのグローバル変数  # 設定ファイルに保存
```

---

## 3. Node-REDフローのインポート

### 3.1 フローファイルの場所

```
/home/yasu/arsprout_analysis/nodered/flows/line_notify_flow.json
```

### 3.2 インポート手順

1. **Node-REDを起動**
   ```bash
   # Dockerの場合
   docker-compose up -d nodered

   # または直接起動
   node-red
   ```

2. **Webインターフェースを開く**
   ```
   http://localhost:1880
   ```
   （またはRaspberry PiのIPアドレス: `http://192.168.1.10:1880`）

3. **フローをインポート**
   - 右上のハンバーガーメニュー ☰ をクリック
   - 「読み込み」（Import）→ 「クリップボード」（Clipboard）
   - 「ファイルを選択」をクリック
   - `/home/yasu/arsprout_analysis/nodered/flows/line_notify_flow.json` を選択
   - 「読み込み」（Import）ボタンをクリック

4. **フローが追加される**
   - 新しいタブ「LINE Notify 送信フロー」が作成される
   - ノードが配置された状態で表示される

5. **デプロイ**
   - 右上の「デプロイ」（Deploy）ボタンをクリック

---

## 4. トークンの設定

### 4.1 方法1: トークン設定ノードを使用（簡単）

1. **「【初期設定】トークン設定」injectノードの右の三角ボタンをダブルクリック**
2. **「グローバル変数にトークンを設定」functionノードをダブルクリック**
3. **コードを編集**
   ```javascript
   // ============================================
   // ⚠️ ここにLINE Notifyトークンを入力してください
   // ============================================
   const LINE_NOTIFY_TOKEN = 'YOUR_LINE_NOTIFY_TOKEN_HERE';
   ```
   ↓
   ```javascript
   const LINE_NOTIFY_TOKEN = 'AbCdEfGhIjKlMnOpQrStUvWxYz1234567890';
   ```
4. **「完了」（Done）をクリック**
5. **「デプロイ」をクリック**
6. **「【初期設定】トークン設定」の左側のボタンをクリック**
7. **デバッグウィンドウで「トークンを設定しました」と表示されることを確認**

### 4.2 方法2: settings.jsで設定（推奨・本番環境）

Node-REDの設定ファイルでグローバル変数を定義します。

1. **settings.jsを編集**
   ```bash
   nano ~/.node-red/settings.js
   ```

2. **`functionGlobalContext`セクションに追加**
   ```javascript
   functionGlobalContext: {
       // 既存の設定...

       // LINE Notify設定
       line_notify_token: process.env.LINE_NOTIFY_TOKEN || "YOUR_TOKEN_HERE"
   },
   ```

3. **環境変数を設定（オプション）**
   ```bash
   # ~/.bashrc または ~/.profile に追加
   export LINE_NOTIFY_TOKEN="AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
   ```

4. **Node-REDを再起動**
   ```bash
   # Dockerの場合
   docker-compose restart nodered

   # または
   sudo systemctl restart nodered
   ```

### 4.3 方法3: グローバルコンテキストで直接設定

1. **Node-REDのWebUI右上の「☰」→「コンテキストデータ」（Context Data）**
2. **「グローバル」（Global）タブ**
3. **「追加」（Add）ボタン**
4. **キー**: `line_notify_token`
5. **値**: `AbCdEfGhIjKlMnOpQrStUvWxYz1234567890`（取得したトークン）
6. **「保存」（Save）**

---

## 5. テスト方法

### 5.1 基本的なテスト

1. **「テスト送信（シンプル）」ボタンをクリック**
   - Injectノードの左側のボタン（タイムスタンプアイコン）をクリック

2. **LINEアプリを開く**
   - 数秒以内に通知が届くことを確認
   - 通知内容: 「テストメッセージ: Node-REDから送信」

3. **デバッグウィンドウで結果を確認**
   - 右側のデバッグタブを開く
   - 以下のような結果が表示される:
     ```json
     {
       "success": true,
       "message": "LINE通知を送信しました",
       "response": {
         "status": 200,
         "message": "ok"
       }
     }
     ```

### 5.2 アラート形式のテスト

1. **「テスト送信（アラート形式）」ボタンをクリック**
2. **LINEで以下のような通知を確認**:
   ```
   🚨 高温警報
   ハウス: h1
   温度: 42.5℃（閾値: 40℃）
   時刻: 2026-02-06 14:30:25
   ```

### 5.3 複数行メッセージのテスト

1. **「テスト送信（複数行）」ボタンをクリック**
2. **LINEで日次レポート形式の通知を確認**

---

## 6. トラブルシューティング

### 6.1 通知が届かない

#### 症状: ボタンを押しても何も届かない

**原因1: トークンが設定されていない**
- デバッグウィンドウで「LINE Notifyトークンが設定されていません」というエラーを確認
- 解決: 「4. トークンの設定」を実施

**原因2: トークンが無効**
- デバッグウィンドウで「HTTP 401エラー」または「認証エラー」を確認
- 解決: LINE Notifyでトークンを再発行し、設定し直す

**原因3: レート制限**
- デバッグウィンドウで「HTTP 429エラー」または「レート制限」を確認
- LINE Notifyの制限: 1時間に1000通まで
- 解決: しばらく待ってから再試行

### 6.2 エラーコード一覧

| HTTPステータス | 意味 | 対処方法 |
|--------------|------|---------|
| 200 | 成功 | - |
| 400 | リクエスト不正 | メッセージフォーマットを確認 |
| 401 | 認証エラー | トークンを確認・再発行 |
| 429 | レート制限 | 送信頻度を下げる（1時間待つ） |
| 500 | LINE側サーバーエラー | しばらく待ってから再試行 |

### 6.3 デバッグ方法

#### ステップ1: ノードのステータスを確認

各ノードの下に表示されるステータスメッセージ:
- 🔵 青い点 + "送信中...": HTTP リクエスト実行中
- 🟢 緑の点 + "送信成功": 正常に送信完了
- 🔴 赤い輪 + "認証エラー": トークンが無効
- 🟡 黄色い輪 + "レート制限": 送信頻度超過

#### ステップ2: デバッグウィンドウを確認

右側のデバッグタブで詳細なログを確認:
- `msg.payload`: 送信結果（success/error）
- `msg.statusCode`: HTTPステータスコード
- `msg.error`: エラーメッセージ（存在する場合）

#### ステップ3: グローバル変数を確認

Node-RED関数ノードで以下を実行:
```javascript
const token = global.get('line_notify_token');
node.warn(`トークン: ${token ? token.substring(0, 10) + '...' : '未設定'}`);
```

---

## 7. 他のフローからの呼び出し方法

### 7.1 基本的な呼び出し

他のフローから「LINE送信（メッセージ整形）」ノードに接続してメッセージを送信できます。

```javascript
// 他のフローのfunctionノードで
msg.payload = "送信したいメッセージ";
return msg;
```

### 7.2 テンプレートを使った動的メッセージ

```javascript
// センサーデータをLINE通知
const temp = msg.payload.temperature;
const humid = msg.payload.humidity;
const houseId = msg.payload.house_id;

msg.payload = `🌡️ センサーデータ
ハウス: ${houseId}
温度: ${temp}℃
湿度: ${humid}%
時刻: ${new Date().toLocaleString('ja-JP')}`;

return msg;
```

### 7.3 条件付き送信

```javascript
// 閾値超過時のみ送信
const temp = msg.payload.temperature;
const threshold = 40;

if (temp > threshold) {
    msg.payload = `🚨 高温警報
温度: ${temp}℃（閾値: ${threshold}℃）
時刻: ${new Date().toLocaleString('ja-JP')}`;
    return msg;
} else {
    // 閾値以下の場合は送信しない
    return null;
}
```

### 7.4 エラー通知の例

```javascript
// ノードオフライン検知時
const nodeId = msg.topic.split('/')[3];
const houseId = msg.topic.split('/')[1];

msg.payload = `📡 ノードオフライン
ハウス: ${houseId}
ノード: ${nodeId}
時刻: ${new Date().toLocaleString('ja-JP')}

確認が必要です。`;

return msg;
```

---

## 8. 設定ファイルの構造

### 8.1 推奨ディレクトリ構造

```
/home/yasu/arsprout_analysis/
├── nodered/
│   ├── flows/
│   │   ├── line_notify_flow.json        # 本フロー
│   │   └── error_alert_flow.json        # 別フロー（足軽3が作成）
│   └── settings.js
├── config/
│   ├── .env                             # 環境変数（Git管理外）
│   └── notification.yaml                # 通知設定
└── docs/
    ├── LINE_INTEGRATION_GUIDE.md
    ├── ERROR_HANDLING_DESIGN.md
    └── LINE_IMPLEMENTATION.md           # 本ドキュメント
```

### 8.2 環境変数ファイル（.env）

```bash
# /home/yasu/arsprout_analysis/config/.env
# Git管理外（.gitignoreに追加済み）

# LINE Notify設定
LINE_NOTIFY_TOKEN=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890

# その他の設定
HOUSE_ID=h1
NODE_RED_PORT=1880
```

---

## 9. パフォーマンスとレート制限

### 9.1 LINE Notifyの制限

| 項目 | 制限 |
|------|------|
| 1時間あたりの送信数 | 1000通 |
| 1メッセージの最大文字数 | 1000文字 |
| 画像サイズ | 1MB以下（JPEG, PNG） |

### 9.2 推奨運用

- **通常のセンサーデータ**: 通知不要、ダッシュボードで確認
- **閾値超過（重要）**: 即時通知、重複排除5分
- **閾値超過（中程度）**: 1時間毎に集約通知
- **日次レポート**: 1日1回

### 9.3 重複排除の実装（推奨）

エラーアラートフロー（別フロー）で実装予定:
```javascript
// 同一異常は5分間再通知しない
const key = `last_alert_${alertType}`;
const lastTime = flow.get(key) || 0;
const now = Date.now();

if (now - lastTime < 5 * 60 * 1000) {
    // 重複、送信しない
    return null;
}

flow.set(key, now);
return msg; // 送信
```

---

## 10. セキュリティベストプラクティス

### 10.1 トークン管理

- ✅ トークンは環境変数またはNode-RED設定ファイルで管理
- ✅ `.gitignore`にトークンファイルを追加
- ✅ 定期的にトークンをローテーション
- ❌ ハードコードしない
- ❌ Slackやメールで共有しない

### 10.2 アクセス制限

- Node-REDのWebUIに認証を設定（settings.js）:
  ```javascript
  adminAuth: {
      type: "credentials",
      users: [{
          username: "admin",
          password: "$2b$08$...",  // bcrypt hash
          permissions: "*"
      }]
  }
  ```

### 10.3 ネットワークセキュリティ

- Node-REDはローカルネットワークからのみアクセス可能に設定
- 外部公開する場合はリバースプロキシ（nginx）+ HTTPS

---

## 11. 今後の拡張予定

### 11.1 画像付き通知（Phase 2）

LINE Notify APIは画像の添付に対応しています。今後、以下を実装予定:
- Grafanaのグラフを画像として送信
- カメラ画像の添付（ハウス内の状況確認）

### 11.2 エラーアラート自動送信フロー（別フロー）

足軽3が `error_alert_flow.json` として実装予定:
- MQTTトピック監視（error, status）
- 閾値チェック（温度、湿度、CO2）
- 通知抑制（重複排除、エスカレーション）
- SQLiteログ保存

### 11.3 LINE Messaging API（双方向通信）

将来的にリモート制御が必要な場合、LINE Messaging APIに移行:
- クイックリプライ（選択ボタン）
- Webhook受信（ユーザーの返信を受け取る）
- リモートアクション（遮光カーテン閉、ミスト噴霧ON等）

---

## 12. 参考資料

### 12.1 公式ドキュメント

- [LINE Notify公式](https://notify-bot.line.me/ja/)
- [LINE Notify API仕様](https://notify-bot.line.me/doc/ja/)
- [Node-RED公式](https://nodered.org/)

### 12.2 関連ドキュメント

- [LINE_INTEGRATION_GUIDE.md](../arsprout_analysis/docs/LINE_INTEGRATION_GUIDE.md) - LINE連携の全体設計
- [ERROR_HANDLING_DESIGN.md](../arsprout_analysis/docs/ERROR_HANDLING_DESIGN.md) - 異常系設計書
- [SYSTEM_SPEC_v1.md](../arsprout_analysis/docs/SYSTEM_SPEC_v1.md) - システム仕様書

### 12.3 サンプルコード

本フロー（line_notify_flow.json）のfunction nodeを参照してください。

---

## 13. チェックリスト

### 導入時チェックリスト

- [ ] LINE Notifyトークンを取得
- [ ] Node-REDにフローをインポート
- [ ] トークンをグローバル変数に設定
- [ ] テスト送信を実行
- [ ] LINEアプリで通知を確認
- [ ] エラーハンドリングをテスト（無効なトークンで試す）

### 本番運用前チェックリスト

- [ ] トークンをGit管理外のファイルに移動
- [ ] `.gitignore`に環境変数ファイルを追加
- [ ] Node-REDのWebUIに認証を設定
- [ ] ネットワークアクセス制限を設定
- [ ] バックアップ手順を確認
- [ ] 監視・ログ設定を確認

---

## 付録A: よくある質問（FAQ）

### Q1: トークンを忘れた場合は？

A: LINE Notifyマイページで該当トークンを削除し、新しいトークンを発行してください。古いトークンは無効化されます。

### Q2: グループに通知を送りたい

A: トークン発行時に通知先としてグループを選択してください。既存のトークンは個人宛て/グループ宛ての変更ができないため、再発行が必要です。

### Q3: 複数のハウスで別々に通知したい

A: ハウス毎に別のトークンを発行し、グローバル変数を `line_notify_token_h1`, `line_notify_token_h2` のように分けて管理してください。

### Q4: 画像を送信したい

A: 現在のフローは基本的なテキスト送信のみ対応しています。画像送信は別途実装予定です。

### Q5: 送信失敗時に自動リトライしたい

A: 現在のフローはリトライ機能がありません。エラーアラートフロー（別フロー）で実装予定です。

---

## 付録B: 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2026-02-06 | 1.0.0 | 初版作成（基本的なLINE Notify送信フロー） |

---

**Document End**
