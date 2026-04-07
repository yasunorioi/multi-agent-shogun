# OpenAI API足軽 偵察報告書

> **cmd_467 / subtask_1039** | 軍師分析 | L5 評価 | 2026-03-30
> **先行調査**: cmd_080 (2026-02-07) — Codex CLI下調べ（当時はTypeScript版、GPT-5.3-Codex時代）

---

## §1. Codex CLI 最新仕様（cmd_080差分更新）

### 基本情報

| 項目 | cmd_080時点 (2026-02) | 現在 (2026-03) |
|------|----------------------|----------------|
| 実装言語 | TypeScript (Node.js) | **Rust** (codex-rs) — 完全リライト |
| インストール | `npm i -g @openai/codex` | 同左（npmパッケージは維持） |
| 推奨モデル | GPT-5.3-Codex | **GPT-5.4** (gpt-5-codex) |
| 利用可能モデル | GPT-4o, GPT-5-Codex | GPT-4.1, o3, o4-mini, **GPT-5.4**, GPT-5.4-mini |
| ヘッドレスモード | 未確認 / 不明 | **`codex exec` 完全対応** |
| サブエージェント | なし | **v2 multi-agent** (パスベースアドレッシング) |
| プラグイン | なし | **ファーストクラスサポート** |
| 設定ファイル | 不明 | `~/.codex/config.toml` + `AGENTS.md` |

### インストール・認証

```bash
npm i -g @openai/codex
# 認証方法（3択）
codex login                        # ChatGPT OAuth
codex login --device-auth          # デバイスコードフロー
codex login --with-api-key         # stdin からAPIキー入力
# または環境変数
export CODEX_API_KEY="sk-proj-..."  # CI/自動化向け
```

### 主要CLI引数

| フラグ | 説明 |
|--------|------|
| `--model, -m` | モデル指定（例: `gpt-5.4`, `gpt-4.1`, `o3`） |
| `--full-auto` | `--ask-for-approval on-request` + `--sandbox workspace-write` のショートカット |
| `--ask-for-approval, -a` | `untrusted` / `on-request` / `never` |
| `--sandbox, -s` | `read-only` / `workspace-write` / `danger-full-access` |
| `--yolo` | 全承認・全サンドボックス解除（開発専用） |
| `--cd, -C` | 作業ディレクトリ指定 |
| `--add-dir` | 追加書き込みディレクトリ |
| `--oss` | ローカルOSSモデル（Ollama経由） |
| `--profile, -p` | config.toml のプロファイル選択 |

### `codex exec`（ヘッドレス実行）

```bash
# 基本: 非対話で1タスク実行→終了
codex exec "fix the failing test in utils.py"

# フルオート + JSON出力
codex exec --full-auto --json "update CHANGELOG"

# 結果をファイルに保存
codex exec -o result.md "summarize recent changes"

# セッション再開
codex exec resume --last "continue the migration"
```

| execフラグ | 説明 |
|------------|------|
| `--json` | JSONL イベントストリーム出力 |
| `-o <path>` | 最終メッセージをファイル書き出し |
| `--output-schema` | JSON Schema で出力形式強制 |
| `--ephemeral` | セッションファイル永続化なし |
| `--skip-git-repo-check` | Git リポジトリ外でも実行可 |
| `--full-auto` | workspace書き込み許可 + 承認不要 |

### AGENTS.md（カスタム指示）

- リポジトリ内の任意ディレクトリに配置可能
- Gitルートから現在ディレクトリまでの各階層で検出・結合
- `AGENTS.override.md` が優先
- サイズ上限: 32KiB（`project_doc_max_bytes` で変更可）
- **CLAUDE.md のCodex版**。互換性なし（ファイル名が異なるだけで仕組みは同等）

---

## §2. 代替CLIエージェント比較

### aider

| 項目 | 値 |
|------|-----|
| リポジトリ | github.com/Aider-AI/aider |
| 言語 | Python |
| インストール | `pip install aider-chat` |
| 対応モデル | Claude 3.7 Sonnet, GPT-4o, o3, o3-mini, DeepSeek R1/V3, ローカルモデル |
| ヘッドレス | `aider -m "task" --yes` で完全非対話 |
| ファイル操作 | diff形式でコード編集、自動commit |
| 設定 | `.aider.conf.yml`, `.env`, CLI引数 |

**aider非対話モード詳細:**

```bash
# 単一タスク→終了
aider --message "add docstrings" hello.py --yes

# 環境変数でも可
export AIDER_MESSAGE="fix bugs"
export AIDER_YES=true
aider app.py
```

主要フラグ:
- `--message, -m`: 単一メッセージ送信→処理→終了
- `--message-file, -f`: ファイルからメッセージ読み込み
- `--yes` (`--yes-always`): 全確認を自動承認
- `--no-auto-commits`: 自動commit無効
- `--model`: モデル指定（`--model gpt-4.1` など）
- `--dry-run`: ドライラン

### open-interpreter

| 項目 | 値 |
|------|-----|
| リポジトリ | github.com/openinterpreter/open-interpreter |
| 言語 | Python |
| 対応モデル | OpenAI, Anthropic, ローカル（Ollama等） |
| ヘッドレス | Python API経由で可能（CLIは対話前提） |
| 評価 | **足軽用途には不適**（コーディング特化ではなく汎用タスク向け） |

### 比較総括

| 評価軸 | Codex CLI | aider | open-interpreter |
|--------|:---------:|:-----:|:----------------:|
| ヘッドレス実行 | ◎ (`exec`) | ○ (`-m --yes`) | △ (API経由) |
| ファイル編集 | ◎ (sandbox制御) | ◎ (diff形式) | ○ |
| bash実行 | ◎ (sandbox内) | ○ (制限あり) | ◎ |
| 自動commit | ○ | ◎ (デフォルト) | × |
| 指示注入 | ◎ (AGENTS.md) | ○ (.aider.conf.yml) | △ |
| JSON出力 | ◎ (--json JSONL) | × | × |
| マルチエージェント | ◎ (v2 sub-agents) | × | × |
| OSSモデル対応 | ○ (--oss/Ollama) | ◎ (多数対応) | ◎ |

---

## §3. tmux + send-keys + YAML通信互換性（最重要）

### Codex CLI

| 判定項目 | 評価 | 備考 |
|----------|:----:|------|
| a. tmuxペイン常駐 | ◎ | 対話TUIがtmuxで動作。exec後もシェルに戻る |
| b. send-keysテキスト入力 | ○ | 対話TUIへのsend-keysは可能だが、**`exec`モードの方が確実** |
| c. capture-pane出力取得 | ○ | TUI出力は取得可、exec時は`-o`ファイル出力の方が確実 |
| d. instructions注入 | ◎ | **AGENTS.md** でリポジトリレベル指示注入。ashigaru.md相当を配置可能 |
| e. YAML inbox読み書き | ◎ | ファイルRead/Writeは標準機能 |
| f. bash実行 | ◎ | sandbox設定次第で自由にbash実行可 |
| g. 非対話1コマンド完了 | ◎ | `codex exec --full-auto "task" -o result.txt` で完結 |

**推奨統合パターン（Codex CLI）:**

```bash
# 家老 → Codex足軽 へのタスク投入
TASK=$(python3 -c "import yaml; d=yaml.safe_load(open('queue/inbox/codex_ashigaru.yaml')); print(d[0]['description'])")
cd /target/project
CODEX_API_KEY=$(grep OPEN_AI ~/.config/env/openai.env | cut -d= -f2)
codex exec --full-auto --model gpt-4.1 -o /tmp/codex_result.txt "$TASK"

# 結果をYAML報告に変換
# → roju_reports.yaml にprepend
```

### aider

| 判定項目 | 評価 | 備考 |
|----------|:----:|------|
| a. tmuxペイン常駐 | ○ | 対話モードはtmux動作するが、**`-m`モードが適切** |
| b. send-keysテキスト入力 | △ | 対話モードへのsend-keysは可能だが不安定要素あり |
| c. capture-pane出力取得 | △ | 構造化出力がないため解析困難 |
| d. instructions注入 | △ | `.aider.conf.yml` で一部可能だがAGENTS.md相当の柔軟性なし |
| e. YAML inbox読み書き | ○ | ファイル操作は可能だが、明示的に指示必要 |
| f. bash実行 | △ | シェルコマンド実行は限定的 |
| g. 非対話1コマンド完了 | ○ | `aider -m "task" --yes` で可能 |

### 統合判定サマリ

| 要件 | Codex CLI | aider | open-interpreter |
|------|:---------:|:-----:|:----------------:|
| Must: tmux常駐 | ◎ | ○ | ○ |
| Must: send-keys通信 | ○ | △ | △ |
| Must: ファイルR/W | ◎ | ◎ | ○ |
| Must: bash実行 | ◎ | △ | ◎ |
| Want: instructions注入 | ◎ | △ | × |
| Want: 非対話モード | ◎ | ○ | △ |
| **総合** | **◎ 最有力** | **○ 次点** | **△ 不適** |

---

## §4. コスト試算

### OpenAI APIトークン単価（2026-03時点）

| モデル | Input/1M tok | Output/1M tok | 用途 |
|--------|:------------:|:-------------:|------|
| GPT-4.1 | $2.00 | $8.00 | **足軽推奨**（コスパ最良） |
| o4-mini | $1.10 | $4.40 | 軽量タスク向け |
| o3 | $2.00 | $8.00 | 推論重視タスク |
| GPT-5.4 | $2.50 | $15.00 | Codexデフォルト（高い） |
| GPT-5.4-mini | $0.15 | $0.60 | サブエージェント向け |
| o3-pro | $150.00 | — | 論外 |

### Claude API比較（Anthropic、2026-03時点）

| モデル | Input/1M tok | Output/1M tok | 用途 |
|--------|:------------:|:-------------:|------|
| Haiku 4.5 | $1.00 | $5.00 | 足軽（現行） |
| Sonnet 4.6 | $3.00 | $15.00 | 足軽（重いタスク） |
| Opus 4.6 | $5.00 | $25.00 | 将軍・軍師 |

### 足軽1タスクあたりの概算コスト

典型的な足軽タスク = ファイル修正 + commit程度:
- コンテキスト読み込み: ~5,000 input tokens
- タスク記述 + YAML: ~2,000 input tokens
- コード生成 + 報告: ~3,000 output tokens
- **合計: ~7K input + ~3K output**

| モデル | 1タスク概算 | 月30タスク |
|--------|:----------:|:----------:|
| GPT-4.1 | **$0.038** | **$1.14** |
| o4-mini | $0.021 | $0.63 |
| GPT-5.4 | $0.063 | $1.88 |
| GPT-5.4-mini | $0.003 | $0.08 |
| Claude Haiku 4.5 | $0.025 | $0.75 |
| Claude Sonnet 4.6 | $0.060 | $1.80 |

**注意**: 上記は最小タスクの見積もり。実際のCodex/Claude Codeセッションは:
- ツール呼び出し毎にコンテキスト再送信 → 実質 **10-50倍** のトークン消費
- 足軽1タスクの現実的コスト: **$0.50〜$5.00**（モデル・複雑度依存）
- Codex execの場合、1セッション制限があるためturn数は少ないが、コンテキスト膨張は同様

### 月額上限設定

- OpenAI: ダッシュボードで **Usage Limits** 設定可能（hard limit / soft limit）
- 推奨: hard limit $20/月（実験期間）→ 成功なら $50/月に引き上げ

### Codex CLI のPlus特典

- ChatGPT Plus ($20/月) 加入で Codex CLI に含む利用枠あり
- GPT-5.4-mini は GPT-5.4 の 30% の枠消費
- **殿は既にPlus契約中** → 追加API費用なしで一定量の利用可能

---

## §5. 統合判定 + 実験計画

### Go/NoGo判定基準

| # | 基準 | カテゴリ | Codex CLI判定 |
|---|------|----------|:------------:|
| 1 | tmuxペインに常駐できる | Must | **Go** |
| 2 | send-keysまたはexecでタスク投入できる | Must | **Go** (`exec`推奨) |
| 3 | ファイルRead/Write可能 | Must | **Go** |
| 4 | bash実行可能 | Must | **Go** (sandbox設定要) |
| 5 | カスタム指示注入 | Want | **Go** (AGENTS.md) |
| 6 | 非対話1コマンド完了 | Want | **Go** (`exec`) |
| 7 | JSON構造化出力 | Want | **Go** (`--json`) |
| 8 | コスト月$20以内 | Must | **Go** (GPT-4.1ならタスク次第) |

**総合判定: Go（条件付き）**

条件: `codex exec` モードが実際にshogunワークフローで安定動作するか実験検証が必要。

### 最有力候補: Codex CLI

**選定理由:**
1. `codex exec --full-auto` がshogun足軽の「1タスク→完了→報告」ワークフローに完全合致
2. AGENTS.md で `instructions/ashigaru.md` 相当の指示注入が可能
3. `--json` JSONL出力でラッパースクリプトからの結果解析が容易
4. `-o result.txt` で結果ファイル出力 → YAML報告変換が簡単
5. `--model gpt-4.1` でコスト最適化可能（GPT-5.4デフォルトを回避）
6. OpenAI Plus加入済み → 一定量は追加費用なし

**次点: aider** — Codex CLI が不適の場合のフォールバック。`-m --yes` で非対話実行可能だが、構造化出力・AGENTS.md相当がない。

### 実験計画（Phase 2: 足軽によるPoC実装）

#### Wave 1: 環境構築 + 最小動作確認

**ペイン**: 既存空きペインまたは新規tmuxウィンドウ

```bash
# 1. インストール
npm i -g @openai/codex

# 2. 認証
export CODEX_API_KEY=$(grep OPEN_AI ~/.config/env/openai.env | cut -d'"' -f2)
# 注: openai.envの形式は OPEN_AI="sk-proj-..." なのでcut -d= -f2 or cut -d'"' -f2

# 3. 最小テスト（読み取り専用）
codex exec "list all Python files in the current directory and summarize their purpose"

# 4. 書き込みテスト
codex exec --full-auto --model gpt-4.1 "create a file /tmp/codex_test.txt with 'hello from codex'"
```

想定所要: 15分 / 想定トークン: ~2K ($0.02)

#### Wave 2: AGENTS.md + YAML通信テスト

```bash
# 1. AGENTS.md作成（テスト用）
cat > AGENTS.md << 'EOF'
あなたはshogunシステムの足軽（ashigaru）エージェントである。
タスクが完了したら、結果を /tmp/codex_report.yaml に以下の形式で書き出せ:
  status: done
  summary: |
    (作業内容を1-3行で)
EOF

# 2. YAMLタスク読み→実行→報告テスト
codex exec --full-auto --model gpt-4.1 \
  -o /tmp/codex_result.txt \
  "queue/inbox/codex_test.yaml を読み、descriptionに従って作業し、結果をYAML形式で報告せよ"

# 3. 結果確認
cat /tmp/codex_result.txt
cat /tmp/codex_report.yaml
```

想定所要: 20分 / 想定トークン: ~5K ($0.05)

#### Wave 3: ラッパースクリプト + tmux統合テスト

```bash
# codex_ashigaru_wrapper.sh（構想）
# - inbox YAML からタスク取得
# - codex exec --full-auto --model gpt-4.1 で実行
# - 結果を roju_reports.yaml にprepend
# - send-keys で老中に完了通知

# tmuxペインに配置してsend-keysでタスク投入テスト
tmux send-keys -t target_pane "codex exec --full-auto --model gpt-4.1 'fix the typo in README.md'" Enter
```

想定所要: 30分 / 想定トークン: ~10K ($0.10)

#### Wave 4: aiderフォールバック検証（Codex CLIに問題があった場合のみ）

```bash
pip install aider-chat
export OPENAI_API_KEY=$(grep OPEN_AI ~/.config/env/openai.env | cut -d'"' -f2)
aider --model gpt-4.1 --message "list files" --yes
```

### 実験予算・期間

| 項目 | 値 |
|------|-----|
| 実験期間 | 3日間（Wave 1-3） |
| 予算上限 | $5.00（hard limit設定推奨） |
| 成功基準 | Wave 2 完了 = Go、Wave 3 完了 = 本番投入判断可 |
| 撤退基準 | Wave 1 で exec が安定動作しない → aider検証 → 両方ダメなら解約 |

---

## §6. トレードオフ比較

### 比較1: CLIエージェント選択

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| **A. Codex CLI** | exec非対話◎、AGENTS.md指示注入◎、JSON出力◎、Plus枠活用 | npm依存、OpenAIロックイン、sandbox制約 | **9** |
| B. aider | Python純正、マルチモデル対応◎、自動commit | 構造化出力×、instructions注入△、bash制限 | 6 |
| C. open-interpreter | 汎用性高い、bash自由 | コーディング非特化、非対話モード△、メンテ懸念 | 3 |

### 比較2: 統合方式

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| **A. exec + ラッパースクリプト** | 1タスク完結、結果ファイル確実、パース容易 | ラッパー開発コスト、セッション状態なし | **8** |
| B. TUI + send-keys（Claude Code同等） | 既存パターン踏襲、対話可能 | Codex TUIの挙動未知、send-keys互換性リスク | 5 |
| C. Agents SDK統合 | 公式SDK、型安全 | Python/TS依存、学習コスト大、過剰設計 | 4 |

### 比較3: モデル選択

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| **A. GPT-4.1** | コスパ最良($2/$8)、1M context、十分な能力 | 最新GPT-5.4に劣る | **9** |
| B. o4-mini | 最安($1.1/$4.4) | 推論能力に限界 | 6 |
| C. GPT-5.4 | 最高性能、Codexデフォルト | 高い($2.5/$15)、足軽には過剰 | 5 |

---

## §7. リスク分析

| # | リスク | 影響度 | 対策 |
|---|--------|:------:|------|
| 1 | Codex exec のsandboxがshogunファイル構造と競合 | 高 | `--sandbox workspace-write` + `--add-dir` で書き込みディレクトリ明示指定 |
| 2 | AGENTS.md と CLAUDE.md の二重管理 | 中 | AGENTS.md は最小限（ashigaru口調+報告形式のみ）。詳細はinbox YAMLに記載 |
| 3 | OpenAI API課金爆発 | 高 | hard limit $20/月設定必須。GPT-5.4 → GPT-4.1 に明示変更 |
| 4 | Codex CLIバージョン更新で破壊的変更 | 中 | ラッパースクリプトで吸収。`npm i -g @openai/codex@specific-version` でピン留め |
| 5 | 殿のPlus契約にAPI利用枠が含まれない場合 | 低 | API直課金に切り替え。openai.env のキーでAPI利用可能を確認済み |
| 6 | exec モードでのGitリポジトリ要件 | 低 | `--skip-git-repo-check` で回避可能。ただしshogunはGit管理なので通常不要 |

---

## §8. cmd_080 からの差分サマリ

| 項目 | cmd_080 (2026-02-07) | 今回更新 (2026-03-30) |
|------|---------------------|----------------------|
| 実装 | TypeScript版 | **Rust完全リライト** |
| ヘッドレス | 未確認 → 統合不明 | **`codex exec` で完全対応** |
| 統合判定 | 「中」（不確実性多い） | **「Go（条件付き）」** — exec モードが決定打 |
| コスト | GPT-5.3-Codex単価不明 | **GPT-4.1 $2/$8 で足軽用途に最適** |
| AGENTS.md | 不明 | **CLAUDE.md同等の指示注入機構** |
| サブエージェント | なし | **v2 multi-agent対応** |
| 代替候補 | 比較なし | **aider次点、open-interpreter不適** |
| 実験計画 | なし | **3Wave + 予算$5の最小実験計画策定** |

**結論**: cmd_080 時点の「統合可能性: 中」から、Rust版リライト + `codex exec` 追加により **「Go（条件付き実験）」** に格上げ。最大の変化は非対話ヘッドレス実行の正式サポート。

---

## §9. Codex足軽 × agent-swarm BBS通信設計（subtask_1043 追加偵察）

> **殿裁定**: Codex足軽はtmuxペイン不使用。agent-swarm BBS通信のみで参入。
> 既存足軽はPhase 1デュアルライト据え置き。Codex足軽だけswarm通信のみで先行参入。

### 9.1 通信フロー全体像

```
老中(tmux)
  │
  ▼ bbs.cgi POST (任務板 @codex_ashigaru)
  │
agent-swarm DB (thread_replies INSERT)
  │
  ▼ notify_post() → notify.py
  │
  ├── tmuxエージェント → send_keys（従来通り）
  │
  └── Codex足軽(pane: null) → **notify_exec()** ← NEW
        │
        ▼ codex_worker.sh 起動
        │
        ├── 1. 任務板レス読み取り (cli.py reply list)
        ├── 2. codex exec --full-auto --model gpt-4.1 "タスク"
        ├── 3. 結果を bbs.cgi POST (任務板に報告レス)
        └── 4. ログ保存 → 終了
```

### 9.2 起動方式の比較

| 案 | 方式 | F004遵守 | 信頼性 | 複雑度 | 判定 |
|----|------|:--------:|:------:|:------:|:----:|
| **A. notify_exec フック** | bbs.cgi POST時にnotify.pyがシェルスクリプト起動 | ◎ イベント駆動 | ◎ 書き込み=起動 | 低 | **★推奨** |
| B. cronポーリング | */5 * * * * で未処理チェック | × F004違反 | ○ | 最低 | **却下** |
| C. inotifywait | SQLite DBファイル監視 | ○ イベント駆動 | △ WAL更新検知が不安定 | 中 | 次点 |
| D. systemd path unit | SQLite DBファイルのPathChanged | ○ イベント駆動 | △ inotify同様の制約 | 中 | 次点 |

**案A推奨理由**: bbs.cgiの通知フックは既に`notify_post()`として実装済み。ここに「tmuxペインがないエージェントにはシェル実行で通知」を追加するだけ。新規依存なし。F004完全遵守。

### 9.3 notify.py 拡張設計

現行の notify.py は全エージェントに `send_keys()` でtmux通知。Codex足軽は `pane: null` のため通知が届かない。

**拡張案: `notify_exec` 属性**

```yaml
# config/swarm.yaml — Codex足軽エントリ
agents:
  codex_ashigaru:
    name: "Codex足軽"
    trip: "◆CDX1"
    pane: null                     # tmuxペインなし
    notify_exec: "scripts/codex_worker.sh"  # ← NEW: 書き込み通知時に実行
```

```python
# notify.py 拡張（_notify_ninmu 内）
def _notify_ninmu(thread_id: str, author_id: str, message: str) -> None:
    # ... 既存ロジック ...

    # 老中の@メンション → Codex足軽向け
    if author_id in ("roju", "karo-roju"):
        mentioned = _extract_mentions(message)
        for aid in mentioned:
            if aid != author_id:
                pane = AGENT_PANES.get(aid)
                exec_cmd = NOTIFY_EXEC.get(aid)  # ← NEW
                if pane:
                    send_keys(pane, ...)  # 従来通り
                elif exec_cmd:
                    # tmuxペインなし + notify_exec設定あり → シェル実行
                    exec_notify(exec_cmd, thread_id, board="ninmu",
                                author=author_id, message=message)
```

```python
# notify.py に追加
NOTIFY_EXEC: dict[str, str] = {}  # agents.yaml から読み込み

def exec_notify(cmd: str, thread_id: str, board: str,
                author: str, message: str) -> None:
    """tmuxペインなしエージェント向け: シェルスクリプトを非同期起動。"""
    import os
    env = os.environ.copy()
    env["SWARM_THREAD_ID"] = thread_id
    env["SWARM_BOARD"] = board
    env["SWARM_AUTHOR"] = author
    env["SWARM_MESSAGE"] = message[:2000]
    try:
        subprocess.Popen(
            [cmd],
            env=env,
            stdout=open(f"/tmp/codex_worker_{thread_id}.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 親プロセスから切り離し
        )
    except Exception:
        pass  # ベストエフォート
```

**設計の核心**: `subprocess.Popen` + `start_new_session=True` でdat_serverプロセスから完全に切り離す。codex execの実行時間（数十秒〜数分）がHTTPレスポンスをブロックしない。

### 9.4 codex_worker.sh ラッパースクリプト設計

```bash
#!/usr/bin/env bash
# scripts/codex_worker.sh — Codex足軽ワーカー
# notify_exec から呼び出される。環境変数でコンテキストを受け取る。
#
# 環境変数:
#   SWARM_THREAD_ID — 任務スレッドID
#   SWARM_BOARD     — 板名 (ninmu)
#   SWARM_AUTHOR    — 投稿者 (roju)
#   SWARM_MESSAGE   — 投稿本文（タスク指示）

set -euo pipefail

# ─── 設定 ─────────────────────────────────
CODEX_MODEL="${CODEX_MODEL:-gpt-4.1}"
WORKDIR="${CODEX_WORKDIR:-/home/yasu/multi-agent-shogun}"
LOGDIR="${WORKDIR}/logs/codex"
AGENT_ID="codex_ashigaru"
AGENT_SWARM_DIR="/home/yasu/agent-swarm"

# APIキー読み込み
source_key() {
    local envfile="$HOME/.config/env/openai.env"
    [[ -f "$envfile" ]] && export CODEX_API_KEY=$(grep '^OPEN_AI=' "$envfile" | cut -d'"' -f2)
}

# bbs.cgi POST ヘルパー（cli.py経由）
post_reply() {
    local thread_id="$1" board="$2" body="$3"
    python3 "${AGENT_SWARM_DIR}/server/cli.py" reply add \
        "$thread_id" --agent "$AGENT_ID" --board "$board" --body "$body"
}

# ─── メイン ───────────────────────────────
main() {
    local thread_id="${SWARM_THREAD_ID:?}"
    local board="${SWARM_BOARD:-ninmu}"
    local message="${SWARM_MESSAGE:?}"

    mkdir -p "$LOGDIR"
    local logfile="${LOGDIR}/$(date +%Y%m%d_%H%M%S)_${thread_id}.log"
    exec > "$logfile" 2>&1

    echo "[$(date)] codex_worker start: thread=$thread_id board=$board"

    source_key
    if [[ -z "${CODEX_API_KEY:-}" ]]; then
        post_reply "$thread_id" "$board" \
            "[error] CODEX_API_KEY未設定。~/.config/env/openai.envを確認せよ。"
        exit 1
    fi

    # 着手報告
    post_reply "$thread_id" "$board" \
        "[status: in_progress] ${thread_id} Codex足軽着手。model=${CODEX_MODEL}"

    # タスク抽出（メッセージ本文からタスク指示を取得）
    # @codex_ashigaru 以降のテキストをタスクとして扱う
    local task
    task=$(echo "$message" | sed 's/.*@codex_ashigaru[[:space:]]*//')
    [[ -z "$task" ]] && task="$message"

    # codex exec 実行
    local result_file="/tmp/codex_result_${thread_id}.txt"
    cd "$WORKDIR"

    if codex exec --full-auto --model "$CODEX_MODEL" \
         --ephemeral -o "$result_file" "$task" 2>>"$logfile"; then
        # 成功 → 報告
        local result
        result=$(head -c 2000 "$result_file" 2>/dev/null || echo "(出力なし)")
        post_reply "$thread_id" "$board" \
            "[report] ${thread_id} Codex足軽完了。
${result}"
    else
        # 失敗 → エラー報告
        local exitcode=$?
        post_reply "$thread_id" "$board" \
            "[error] ${thread_id} Codex足軽失敗(exit=${exitcode})。ログ: ${logfile}"
    fi

    rm -f "$result_file"
    echo "[$(date)] codex_worker end: thread=$thread_id"
}

main "$@"
```

**作業ディレクトリ問題**: `WORKDIR` はデフォルトで `multi-agent-shogun`。対象リポジトリが異なる場合（systrade等）は、タスク指示に `--cd /home/yasu/systrade` を含めるか、メッセージ内のパスを解析してcdする。Phase 1では `multi-agent-shogun` 固定で十分。

### 9.5 AGENTS.md 配置設計

```
/home/yasu/multi-agent-shogun/AGENTS.md   ← Codex足軽用（CLAUDE.mdと共存）
```

```markdown
# AGENTS.md — Codex足軽指示書

あなたはshogunシステムのCodex足軽（codex_ashigaru）である。

## 行動規範
- 依頼されたタスクのみ実行せよ。余計な改善をするな
- ファイル修正後は必ず git add + git commit せよ
- commit メッセージは日本語で書け
- 他エージェントのファイル（queue/inbox/他人のYAML）を変更するな
- CLAUDE.md は読むな（Claude Code用であり、あなたの指示書ではない）

## 制約
- 没日録DB (data/botsunichiroku.db) への書き込み禁止
- scripts/ 内の既存スクリプト変更禁止（新規作成は可）
- git push 禁止（老中がレビュー後にpush）
```

**CLAUDE.md と AGENTS.md の共存**: Codex CLIはAGENTS.mdのみ読む。Claude CodeはCLAUDE.mdのみ読む。ファイル名が異なるため干渉なし。

### 9.6 既存swarmインフラとの整合性

| 項目 | 対応 |
|------|------|
| swarm.yaml エントリ | `codex_ashigaru` 追加 (name: Codex足軽, trip: ◆CDX1, pane: null, notify_exec: scripts/codex_worker.sh) |
| BOARD_WRITERS | ninmu: null(全員可) → Codex足軽は自動的に書き込み可 |
| 通知ルーティング | notify.py の `_notify_ninmu` 拡張: `@codex_ashigaru` メンション → `exec_notify()` |
| トリップキー | ◆CDX1 — swarm.yaml で定義。cli.py がtrip生成 |
| cmd_466 swarm_post.py | 影響なし。swarm_post.py はMBP支店用。Codex足軽は直接cli.py経由 |
| flush_pending.py | 影響なし。Codex足軽はローカル実行のためSSH不要 |

### 9.7 Wave 2/3 改訂計画

**元Wave 2（subtask_1041: AGENTS.md + YAML通信テスト）→ swarm通信テストに変更**

#### Wave 2改: codex exec + BBS POST報告テスト

```bash
# Step 1: codex exec 基本動作（subtask_1040で確認済み、省略可）

# Step 2: cli.py 経由でCodex足軽として任務板に投稿テスト
cd /home/yasu/agent-swarm
python3 server/cli.py reply add test_codex_thread \
    --agent codex_ashigaru --board ninmu \
    --body "[test] Codex足軽投稿テスト"
# → 老中ペインにsend-keys通知が届くこと確認

# Step 3: codex exec → 結果取得 → BBS POST の一連フロー手動テスト
export CODEX_API_KEY=$(grep OPEN_AI ~/.config/env/openai.env | cut -d'"' -f2)
codex exec --full-auto --model gpt-4.1 -o /tmp/codex_test_result.txt \
    "echo 'hello from codex' > /tmp/codex_hello.txt"
# → /tmp/codex_test_result.txt を確認
# → 結果を手動でBBS POSTしてフロー確認

# Step 4: AGENTS.md 配置テスト
# AGENTS.md をmulti-agent-shogunに配置
# codex exec がAGENTS.md指示を読み込むか確認
```

**成功基準:**
- cli.py経由でcodex_ashigaruとして任務板投稿成功
- codex exec の結果をBBS POSTで報告できる
- AGENTS.mdの指示をCodexが認識する

#### Wave 3改: swarm全自動ワークフローテスト + Go/NoGo

```bash
# Step 1: notify.py 拡張実装
#   - NOTIFY_EXEC辞書追加
#   - exec_notify()関数追加
#   - _notify_ninmu()内の分岐追加

# Step 2: codex_worker.sh 配置 + 実行権限付与
chmod +x scripts/codex_worker.sh

# Step 3: swarm.yaml にcodex_ashigaru + notify_exec追加

# Step 4: 全自動テスト
# 老中ペインから:
python3 server/cli.py reply add test_codex_auto \
    --agent roju --board ninmu \
    --body "@codex_ashigaru /tmp/codex_autotest.txt に 'auto test passed' と書け"
# → notify_exec → codex_worker.sh → codex exec → BBS POST報告
# → 老中に通知
# → /tmp/codex_autotest.txt が存在すること確認
```

**成功基準:**
- 老中のBBS POST → Codex足軽自動起動 → 作業 → BBS POST報告 の全自動フロー成功
- 所要時間: 投稿〜報告レスまで2分以内
- エラー時のBBS POST報告が機能する

#### Wave 4（追加）: 実戦テスト + コスト検証

```bash
# 実際の簡易タスクをCodex足軽に割り当て
# 例: docs/内の誤字修正、テストファイル追加等
# APIダッシュボードでコスト実測
# Go/NoGo最終判定
```

### 9.8 改訂Wave設計サマリ

| Wave | 内容 | 実施者 | 成果物 |
|:----:|------|--------|--------|
| 1 | Codex CLIインストール+API疎通 | 足軽 | ✅ 完了(subtask_1040) |
| **2改** | codex exec + BBS POST + AGENTS.md テスト | 足軽 | cli.py投稿確認、AGENTS.md認識確認 |
| **3改** | notify.py拡張 + codex_worker.sh + 全自動フロー | 足軽 | notify_exec実装、全自動テスト成功 |
| **4(新)** | 実戦タスク + コスト実測 + Go/NoGo最終判定 | 足軽+家老 | 判定レポート |

### 9.9 トレードオフ比較

#### 比較4: Codex足軽起動方式

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| **A. notify_exec フック** | F004遵守◎、既存notify.pyの自然拡張、即座に起動 | dat_serverプロセスからのfork | **9** |
| B. inotifywait | F004遵守○、専用プロセス | SQLite WAL検知不安定、追加デーモン必要 | 4 |
| C. cron | 実装最小 | **F004違反**、遅延、無駄な起動 | 2 |
| D. systemd path unit | F004遵守○、OS標準 | inotify同様の制約、設定複雑 | 4 |

#### 比較5: 作業ディレクトリ戦略

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| **A. multi-agent-shogun固定** | Phase 1として最小構成 | 他リポ作業不可 | **7** |
| B. タスク指示内--cd指定 | 柔軟 | パース必要、sandbox範囲問題 | 5 |
| C. リポジトリ別AGENTS.md | 各リポに指示配置 | 管理コスト大 | 3 |

### 9.10 リスク分析（追加）

| # | リスク | 影響度 | 対策 |
|---|--------|:------:|------|
| 7 | codex_worker.shが長時間実行→同一タスク二重起動 | 高 | PIDファイル or flockで排他制御 |
| 8 | codex execがsandbox内でcli.py呼び出し不可 | 高 | `--sandbox danger-full-access` or ラッパー内で結果取得→ラッパーがPOST |
| 9 | AGENTS.md と CLAUDE.md の指示矛盾 | 中 | 各CLIは自分のファイルのみ読む。干渉なし |
| 10 | notify_exec のPopen失敗がサイレント | 中 | ログ + 監視板に定期ヘルスチェック |
| 11 | Codex足軽のgit commitが既存ブランチと衝突 | 中 | Codex足軽は専用ブランチで作業 → 老中がmerge |

**リスク#8の詳細**: codex exec は `--full-auto` でも sandbox 内で動く。sandbox内からSSH execやcli.py呼び出しが制約される可能性あり。**対策**: codex exec の結果は `-o result.txt` でファイル出力し、codex_worker.sh（sandbox外）が結果を読んでBBS POSTする。codex exec自体にBBS POST責務を持たせない。

```
codex_worker.sh (sandbox外)
  ├── 着手報告: cli.py reply add (sandbox外)
  ├── codex exec -o result.txt (sandbox内で作業)
  ├── 完了報告: cli.py reply add (sandbox外、result.txt読み込み)
  └── 終了
```

この設計なら sandbox 制約の影響を受けない。
