# feature-shogun プロジェクトコンテキスト
最終更新: 2026-01-29

## 基本情報
- **プロジェクトID**: feature-shogun
- **正式名称**: multi-agent-shogun（マルチエージェント将軍）
- **パス**: /mnt/c/tools/feature-shogun
- **GitHub URL**: リポジトリあり（gh コマンドで操作、PR #4 マージ済）
- **ブランチ**: feature/improve-installer（main からの作業ブランチ）

## 概要
Claude Code + tmux を使ったマルチエージェント並列開発基盤。
戦国時代の軍制をモチーフとした階層構造（将軍→家老→足軽）で、
最大8名の足軽が並列にタスクを実行する。YAML ファイルと tmux send-keys による
イベント駆動型通信で連携する。

## 技術スタック
- **シェル**: Bash（first_setup.sh, shutsujin_departure.sh, setup.sh）
- **バッチ**: Windows Batch（install.bat — WSL インストーラー）
- **ターミナルマルチプレクサ**: tmux（セッション管理、ペイン間通信）
- **AI エージェント**: Claude Code CLI（各ペインで独立実行）
- **通信方式**: YAML ファイル + tmux send-keys（イベント駆動、ポーリング禁止）
- **MCP サーバー**: Notion, Playwright, GitHub, Sequential Thinking, Memory
- **設定管理**: YAML（config/settings.yaml, config/projects.yaml）

## 重要な決定事項

### 運用ルール
- **言語**: 戦国風日本語のみ（language: ja）、コード・ドキュメントはプロ品質
- **send-keys 2回分割**: メッセージ送信とEnter送信を必ず別の Bash 呼び出しにする
- **dashboard.md の更新責任**: 家老が一元管理（将軍は読むだけ）
- **下→上への報告**: dashboard.md 更新のみ（send-keys 禁止 — 人間への割り込み防止）
- **上→下への指示**: YAML ファイル書き込み + send-keys で起こす
- **ポーリング禁止**: API 代金節約のためイベント駆動のみ
- **各足軽に専用タスクファイル**: queue/tasks/ashigaru{N}.yaml（他の足軽のファイル読み書き禁止）

### 安定性対策（cmd_012, cmd_016 で確立）
- 足軽→家老への報告は send-keys で通知が義務（2回分割方式）
- 家老は起こされた際に全報告ファイル（ashigaru*_report.yaml）をスキャン（通信ロスト対策）
- コンパクション復帰時は必ず自分の位置（tmux ペイン）を確認してから行動

### 設計済み・承認待ち（cmd_017）
- **奉行（Bugyo）導入**: 足軽8を奉行に転用。家老の責務を「頭脳（家老）」と「手足（奉行）」に分離
- **ACK 機構**: assigned → acknowledged → in_progress → done の4段階ステータス
- **通信ロスト検知**: 60秒後の1回確認、未ACKなら再送/再割当て

### スキル化候補（12件蓄積、承認待ち）
batch-encoding-fixer, encoding-validator, space-in-path-auditor,
installer-ux-simulator, shellscript-code-review, bash-set-e-audit,
idempotency-review, wsl-utf16le-detector, agent-health-monitor,
communication-health-check, agent-health-checker, bat-quality-gate

## ファイル構成
```
feature-shogun/
├── CLAUDE.md                  # システム構成・全エージェント共通ルール
├── README.md / README_ja.md   # プロジェクト説明（英語/日本語）
├── first_setup.sh             # 初回セットアップスクリプト（STEP 1-10）
├── install.bat                # Windows用WSLインストーラー
├── setup.sh                   # 簡易セットアップ
├── shutsujin_departure.sh     # 出陣スクリプト（tmux起動+エージェント配置）
├── dashboard.md               # 人間用ダッシュボード（戦況報告）
├── config/
│   ├── settings.yaml          # 言語・スキル・ログ設定
│   └── projects.yaml          # プロジェクト一覧
├── instructions/
│   ├── shogun.md              # 将軍の指示書
│   ├── karo.md                # 家老の指示書
│   └── ashigaru.md            # 足軽の指示書
├── queue/
│   ├── shogun_to_karo.yaml    # 将軍→家老 指示
│   ├── tasks/ashigaru{N}.yaml # 家老→足軽 タスク割当（各足軽専用）
│   └── reports/               # 足軽→家老 報告
│       └── ashigaru{N}_report.yaml
├── context/                   # プロジェクト固有コンテキスト
├── memory/                    # Memory MCP 用データ
├── status/                    # 全体進捗管理
├── skills/                    # スキル定義
├── templates/                 # テンプレート
├── logs/                      # ログ出力先
└── demo_output/               # デモ出力
```

## tmux セッション構成
```
shogunセッション:     Pane 0 = 将軍
multiagentセッション: Pane 0 = 家老, Pane 1-8 = 足軽1-8
```

## 進行状況（2026-01-29）

### 完了済み（cmd_001〜019）
- [x] cmd_001: スキル保存パス修正
- [x] cmd_002: セットアップスクリプト一括修正
- [x] cmd_003: install.bat 品質検証
- [x] cmd_004: install.bat 要改善修正
- [x] cmd_005: フルシミュレーション検証
- [x] cmd_006: 指示書改善（karo.md, shogun.md）
- [x] cmd_007: 全問題修正（11件 — Critical 3件, High 4件, Medium 4件）
- [x] cmd_008: 修正後再検証（コードレビュー+統合フロー）
- [x] cmd_009: set -e 保護問題2件修正
- [x] cmd_010: 新規観点フルシミュレーション（部分完了 — 通信ロスト発生）
- [x] cmd_011: Memory MCP 自動セットアップ追加
- [x] cmd_012: 通信ロスト対策（ashigaru.md + karo.md 改修）
- [x] cmd_013: cmd_010 検証発見7件修正（install.bat 4件）
- [x] cmd_014: cmd_013 未実行3件修正（first_setup.sh + shutsujin_departure.sh）
- [x] cmd_015: 残2件修正（karo.md スキャンプロトコル + tmux エラーハンドリング）
- [x] cmd_016: マルチエージェントシステム安定性調査（5/8名回答、根本原因3件特定）
- [x] cmd_017: 奉行導入+ACK機構設計（設計完了、承認待ち）
- [x] cmd_018: GitHub Issue #5 調査・回答
- [x] cmd_019: PR #4 レビュー（マージ済）

### 承認待ち
- [ ] 奉行導入設計の承認（cmd_017）
- [ ] スキル化候補12件の承認
- [ ] 最優先改善3件の承認（P-001 ACK機構, P-002 ペイン確認義務化, P-009 連続タスク上限）

## 注意事項

### WSL2 環境固有の問題
- **UTF-16LE 問題**: wsl.exe の出力が UTF-16LE のため、findstr 等でのパースが失敗する。install.bat では `wsl.exe -d Ubuntu -- echo test` + goto方式で解決済み
- **パスのスペース**: 日本語ユーザー名等でスペースが入るパスが頻出。全スクリプトでクォート必須
- **wsl.exe のディストロ指定**: `-e` ではなく `-d Ubuntu` を統一使用

### コンパクション対策
- コンパクション後は必ず自分の位置を tmux で確認してから行動
- Memory MCP にルールが永続化されている（mcp__memory__read_graph で確認可能）
- summary には「役割」「禁止事項」「現在のタスクID」を必ず含める

### set -e 環境
- first_setup.sh は `set -e` 有効。コマンド失敗で即終了するため、if 文や `|| true` で保護が必要
- `((var++))` は var=0 のとき exit code 1 を返す → `$((var + 1))` を使用

### 通信の信頼性（既知の問題）
- tmux send-keys はファイア・アンド・フォーゲット型 — 受信確認がない
- 家老が SPOF（単一障害点）— コンテキスト 0-1% で記憶喪失が発生する
- 活発に働く足軽ほど処理中にsend-keysが届き、通信ロストしやすい構造的問題
- 奉行導入+ACK機構で解決予定（cmd_017 承認待ち）
