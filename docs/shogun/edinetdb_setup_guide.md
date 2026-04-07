# EDINET DB APIキー取得 & MCP設定手順

> **対象**: 上様（殿）| 所要時間: 約5分 | cmd_457 / subtask_1017

---

## Step 1: APIキー取得（2分）

1. ブラウザで https://edinetdb.jp にアクセス
2. 右上「ログイン」→ **Googleアカウントで認証**（クレカ不要）
3. ダッシュボード → 「APIキー」セクション → キーをコピー
   - 形式: `edb_xxxxxxxxxxxx`
   - Free枠: **100回/日・3,000回/月・¥0**

---

## Step 2: 環境変数に登録（1分）

```bash
echo 'export EDINETDB_API_KEY="edb_ここにキーを貼る"' >> ~/.bashrc
source ~/.bashrc
```

RPi・VPS にも同様に設定すること（SSH接続後に実行）。

---

## Step 3: 動作確認（1分）

```bash
curl -s "https://edinetdb.jp/v1/status" && echo "OK"
curl -H "Authorization: Bearer $EDINETDB_API_KEY" "https://edinetdb.jp/v1/companies/7203"
```

トヨタ（7203）の財務データが返れば完了。

---

## Step 4: Claude Code の MCP を有効化

設定済み（足軽が`.mcp.json`と`settings.local.json`に追記済み）。
`source ~/.bashrc` 後に Claude Code を **再起動** すれば `edinetdb_*` ツールが使用可能になる。

確認コマンド:
```bash
echo $EDINETDB_API_KEY  # edb_... が表示されればOK
```

---

## 利用可能ツール（MCP経由・22種）

| 主要ツール | 機能 |
|-----------|------|
| `search_companies` | 企業名・証券コードで検索 |
| `get_financials` | 6年分財務時系列（売上・CF・設備投資等） |
| `screen_companies` | 97指標マルチ条件スクリーニング |
| `get_shareholders` | 大量保有報告書（スマートマネー検出） |
| `get_analysis` | AI財務健全性スコア |

詳細: `docs/shogun/edinetdb_survey.md`（軍師分析書）参照。

---

*Free枠(100回/日)で daily_risk.py + 獏 + 探索的分析の合計~60回/日をカバー可能。月額¥0維持。*
