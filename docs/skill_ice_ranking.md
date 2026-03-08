# スキル候補 ICE ランキング

> **作成**: cmd_363 / subtask_803
> **日付**: 2026-03-08
> **手法**: ICE (Impact x Confidence x Ease) — 各1-5点、積でスコア算出

## スコアリング基準

| 軸 | 1点 | 3点 | 5点 |
|---|---|---|---|
| **Impact** | 特定場面のみ有用 | 複数PJで効果あり | 全PJ・全エージェントに波及 |
| **Confidence** | 技術的不確実性高い | 前例あり実現可能 | 既に手順確立・実証済み |
| **Ease** | 3subtask以上 | 2subtask | 1subtask以下 |

## 総合ランキング

| 順位 | スキル名 | I | C | E | ICE | 分類 |
|---:|---|:---:|:---:|:---:|---:|---|
| 1 | systemd-service-installer | 4 | 5 | 4 | **80** | 即実装 |
| 2 | python-default-arg-mock-trap | 3 | 5 | 5 | **75** | 即実装 |
| 3 | local-llm-ollama-nosudo-install | 3 | 5 | 5 | **75** | 即実装 |
| 4 | ollama-tool-calling-loop | 5 | 4 | 3 | **60** | 即実装 |
| 5 | asyncio-daemon-graceful-shutdown | 3 | 5 | 4 | **60** | 即実装 |
| 6 | ollama-nosudo-install-v2 | 2 | 5 | 5 | **50** | 次スプリント |
| 7 | llm-model-migration-design-doc | 3 | 4 | 4 | **48** | 次スプリント |
| 8 | llama-server-async-client | 4 | 4 | 3 | **48** | 次スプリント |
| 9 | qwen3-thinking-tc-test | 3 | 4 | 4 | **48** | 次スプリント |
| 10 | local-llm-bench-auto-table | 4 | 4 | 3 | **48** | 次スプリント |
| 11 | actuator-safety-constraint-analyzer | 3 | 3 | 3 | **27** | 次スプリント |
| 12 | yaml-to-llm-tool-generator | 4 | 3 | 2 | **24** | 次スプリント |
| 13 | ds18b20-sysfs-driver + weather-protocol-parser | 2 | 4 | 3 | **24** | 保留 |
| 14 | cross-doc-consistency-checker | 4 | 3 | 2 | **24** | 保留 |
| 15 | gpiod-v2-asyncio-edge-detection | 2 | 3 | 3 | **18** | 保留 |
| 16 | iot-actuator-safety-design-template | 3 | 2 | 2 | **12** | 保留 |
| 17 | pid-scale-annotator | 2 | 2 | 2 | **8** | 保留 |

## 即実装（上位5件）— 次スプリントで着手

### 1. systemd-service-installer (ICE: 80)
- **出典**: 足軽3号 (subtask_532)
- **内容**: systemd .service生成+install.shスクリプト
- **根拠**: デプロイのたびに手動で.serviceファイルを書いている。テンプレート化すれば全PJで即効果。技術的に確立済み（ExecStart/User/Restart等のパターンは定型）。1subtaskで完了可能。

### 2. python-default-arg-mock-trap (ICE: 75)
- **出典**: 足軽3号 (subtask_657)
- **内容**: Pythonデフォルト引数import時評価→module変数パッチ不可→関数パッチが正解パターン
- **根拠**: テストで繰り返しハマるパターン。ドキュメント化だけで即効果。全Pythonプロジェクトに適用可能。工数ゼロに近い（知見ドキュメントのみ）。

### 3. local-llm-ollama-nosudo-install (ICE: 75)
- **出典**: 足軽1号 (subtask_626)
- **内容**: ollamaをsudo不要でインストール(wget+tar.zst展開)する手法
- **根拠**: RPiデプロイで毎回必要。手順は既に確立済み。ドキュメント化のみで完了。
- **備考**: ollama-nosudo-install-v2 (subtask_634) と重複。統合してスキル化推奨。

### 4. ollama-tool-calling-loop (ICE: 60)
- **出典**: 足軽2号 (subtask_580)
- **内容**: Ollama/OpenAI互換tool callingループ+MAX_TOOL_ROUNDS制御+run_in_executor
- **根拠**: ローカルLLM TC運用の核心パターン。uecs-llm forecast_engineで既に実装済みの知見を汎用化。Impact最高（全LLMプロジェクトに波及）。2subtaskで実現可能。

### 5. asyncio-daemon-graceful-shutdown (ICE: 60)
- **出典**: 足軽1号 (subtask_533)
- **内容**: asyncioデーモンのSIGTERM/SIGINT+task cancel+subprocess停止
- **根拠**: unipi-daemon/agriha等のデーモンプロセスで共通必要。パターンは確立済み。1subtaskで実装可能。

## 次スプリント（中位7件）— 優先度中

### 6. ollama-nosudo-install-v2 (ICE: 50)
- **備考**: #3 local-llm-ollama-nosudo-install と統合推奨。単独では重複のためImpact低め。

### 7. llm-model-migration-design-doc (ICE: 48)
- モデル切替時の設計書改訂パターン。テンプレート化は容易だが利用頻度はモデルリリース依存。

### 8. llama-server-async-client (ICE: 48)
- llama-server subprocess管理+httpx asyncクライアント。ローカルLLM基盤として重要だが2subtask必要。

### 9. qwen3-thinking-tc-test (ICE: 48)
- Qwen3 thinking mode対応TCテスト手順。ベンチマーク改善に有用。手順ドキュメント化は容易。

### 10. local-llm-bench-auto-table (ICE: 48)
- 全モデル比較表自動集計。モデル選定効率化に高価値だが実装に2subtask必要。

### 11. actuator-safety-constraint-analyzer (ICE: 27)
- YAML定義の安全制約分類マトリクス。IoT特化だがshogun全体への波及は限定的。

### 12. yaml-to-llm-tool-generator (ICE: 24)
- YAML→Pydantic→MCP/OpenAI/Claude互換ツール定義自動構築。高価値だが複数API互換の実装が重い。

## 保留（下位5件）— 当面不要 or 実現困難

### 13. ds18b20-sysfs-driver + weather-protocol-parser (ICE: 24)
- ハードウェアテスト特化。unipi-daemon以外で使う場面が少ない。

### 14. cross-doc-consistency-checker (ICE: 24)
- 設計書間整合性チェック。Impact高いが自然言語解析の精度保証が困難。3subtask以上。

### 15. gpiod-v2-asyncio-edge-detection (ICE: 18)
- GPIO特化。gpiod v2はまだ普及途上で適用場面が限定的。

### 16. iot-actuator-safety-design-template (ICE: 12)
- #5 actuator-safety + #12 yaml-to-llm-tool-generator の複合。依存が多く単独スキル化困難。

### 17. pid-scale-annotator (ICE: 8)
- PIDゲインのスケール差異検出。適用範囲が極めて狭い。精度保証も困難。

## 統合推奨

| 統合対象 | 統合後スキル名 | 理由 |
|---|---|---|
| #3 + #6 | **ollama-nosudo-installer** | 同一手順の重複。1つに統合 |
| #4 + #8 | **local-llm-tc-runtime** | tool calling loop + llama-server clientは一体運用 |
| #9 + #10 | **local-llm-bench-suite** | thinkingテスト + ベンチ自動化は同一ワークフロー |
