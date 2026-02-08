# 本家 v3.0.0 統合分析レポート

> **作成日**: 2026-02-08
> **作成者**: 部屋子1（heyago1）— Wave1レポート3本の統合
> **対象リポジトリ**: yohey-w/multi-agent-shogun v3.0.0
> **入力レポート**:
> - tmp_v3_build_system.md（heyago1: ビルドシステム分析）
> - tmp_v3_instructions.md（heyago2: instructions構造分析）
> - tmp_v3_agents.md（heyago3: エージェント起動・CLI選択分析）

---

## 分析観点1: ビルドシステムの仕組み

### 全体像

本家v3.0.0は「1つの正本（CLAUDE.md）から4種類のCLI対応ファイルを自動生成する」ビルドシステムを採用している。

```
                  ┌── instructions/roles/{role}_role.md ──┐
                  │                                       │
YAML Front Matter ┤   instructions/common/protocol.md     ├─→ instructions/generated/{cli}-{role}.md
(既存.mdから抽出)  │   instructions/common/task_flow.md     │     （12ファイル = 3ロール × 4CLI）
                  │   instructions/common/forbidden.md     │
                  └── instructions/cli_specific/{cli}.md ──┘

CLAUDE.md ──sed置換──→ AGENTS.md (Codex)
                    → .github/copilot-instructions.md (Copilot)
                    → agents/default/system.md + agent.yaml (Kimi)
```

### 結合方法の詳細

`scripts/build_instructions.sh` が以下の順序でファイルを連結する:

| 順序 | ソース | 内容 | 例 |
|------|--------|------|-----|
| 1 | YAML Front Matter | 既存instructions/{role}.mdから抽出。なければversion:3.0を自動生成 | `role: ashigaru` |
| 2 | `instructions/roles/{role}_role.md` | ロール固有の役割定義・権限・行動指針 | 足軽の報告フォーマット等 |
| 3 | `instructions/common/protocol.md` | 全ロール共通の通信プロトコル | mailbox system, send-keysルール |
| 4 | `instructions/common/task_flow.md` | 全ロール共通のタスクフロー | タスク受取→実行→報告の流れ |
| 5 | `instructions/common/forbidden_actions.md` | 全ロール共通の禁止事項 | F001〜F005相当 |
| 6 | `instructions/cli_specific/{cli}_tools.md` | CLI固有のツール説明 | Claude: Memory MCP, Task tool等 |

**結合方法**: `cat` による単純連結（各セクション間に空行挿入）

### CLI自動読込ファイル生成

CLAUDE.mdを正本として、`sed` 一括置換で各CLI用ファイルを生成:

| 生成物 | 対象CLI | 主な置換 |
|--------|---------|---------|
| `AGENTS.md` | Codex | CLAUDE.md→AGENTS.md, ~/.claude/→~/.codex/, Claude Code→Codex CLI |
| `.github/copilot-instructions.md` | Copilot | 同様のパス・名称置換 |
| `agents/default/system.md` + `agent.yaml` | Kimi K2 | 同様 + agent.yaml（モデル・ツール定義）自動生成 |

### 設計哲学

- **Single Source of Truth**: CLAUDE.mdを唯一の正本とし、他CLIは派生物
- **3層モジュール化**: roles（ロール固有）+ common（共通）+ cli_specific（CLI固有）
- **静的生成**: generated/はGit管理下。再生成はスクリプト実行が必要

### 我々との構成比較

| 項目 | 本家 v3.0.0 | 我々 v2.0 |
|------|-----------|---------|
| 指示書 | モジュール結合（3層） | 単一ファイル（直接編集） |
| ビルドステップ | あり（build_instructions.sh） | なし |
| CLI対応 | 4CLI（Claude/Codex/Copilot/Kimi） | Claude Code専用 |
| ロール数 | 3（shogun/karo/ashigaru） | 5（+midaidokoro/ohariko） |
| 生成ファイル数 | 12+3（指示書+自動読込） | 0（全て手動管理） |

---

## 分析観点2: 大奥ロール追加に必要な変更

本家v3.0.0に我々の大奥ロール（ohariko, midaidokoro, heyago）を追加するために必要な変更箇所を分析する。

### 2.1 影響範囲一覧

#### (A) lib/cli_adapter.sh（5箇所）

| 関数 | 変更内容 | 工数 |
|------|---------|------|
| `get_cli_type()` | 変更不要（agent_idベースで動的取得のため） | — |
| `build_cli_command()` | 変更不要（get_cli_type結果で分岐のため） | — |
| `get_instruction_file()` | ロール判定に `midaidokoro`, `ohariko`, `heyago*` を追加 | 小 |
| `validate_cli_availability()` | 変更不要 | — |
| `get_agent_model()` | デフォルトモデルに新ロールを追加 | 小 |

**get_instruction_file の修正例**:
```bash
case "$agent_id" in
    shogun)       role="shogun" ;;
    karo*)        role="karo" ;;       # karo, karo-roju
    midaidokoro)  role="midaidokoro" ;; # 新規
    ashigaru*)    role="ashigaru" ;;
    heyago*)      role="heyago" ;;     # 新規（部屋子）
    ohariko)      role="ohariko" ;;    # 新規
    *)            return 1 ;;
esac
```

**get_agent_model の修正例**:
```bash
case "$agent_id" in
    shogun|karo*|midaidokoro) echo "opus" ;;
    ashigaru[1-4])            echo "sonnet" ;;
    ashigaru[5-8]|heyago*)    echo "opus" ;;
    ohariko)                  echo "sonnet" ;;
    *)                        echo "sonnet" ;;
esac
```

#### (B) scripts/build_instructions.sh（3箇所）

| 変更箇所 | 内容 | 工数 |
|---------|------|------|
| ロール固有ファイル | `instructions/roles/midaidokoro_role.md`, `heyago_role.md`, `ohariko_role.md` を新規作成 | 中 |
| ビルド対象追加 | `build_instruction_file` 呼び出しを新ロール分追加（12行→24行） | 小 |
| CLI自動読込 | sed置換に新instructionsパスを追加 | 小 |

**ビルド対象追加例**:
```bash
# 既存3ロール × 4CLI = 12ファイル
build_instruction_file "claude" "shogun" "shogun.md"
# ...

# 新規3ロール × 4CLI = 12ファイル追加（合計24ファイル）
build_instruction_file "claude" "midaidokoro" "midaidokoro.md"
build_instruction_file "claude" "heyago" "heyago.md"
build_instruction_file "claude" "ohariko" "ohariko.md"
build_instruction_file "codex" "midaidokoro" "codex-midaidokoro.md"
# ...以下同様
```

#### (C) instructions/ ディレクトリ（新規ファイル6つ）

```
instructions/
├── roles/
│   ├── midaidokoro_role.md   # 新規: 御台所の役割定義
│   ├── heyago_role.md        # 新規: 部屋子の役割定義
│   └── ohariko_role.md       # 新規: お針子の役割定義
├── common/
│   ├── protocol.md           # 修正: ookuセッション通信ルール追加
│   ├── task_flow.md          # 修正: 部屋子の報告フロー追加
│   └── forbidden_actions.md  # 修正: お針子の権限制約追加
└── cli_specific/
    └── （変更不要: CLI固有でなくロール固有のため）
```

#### (D) shutsujin_departure.sh（大規模変更）

| 変更箇所 | 内容 | 工数 |
|---------|------|------|
| セッション構成 | ookuセッション（5ペイン）の作成ロジック追加 | 大 |
| エージェント起動 | midaidokoro, heyago1-3, ohariko の起動コマンド追加 | 中 |
| inbox_watcher | 新エージェント分のwatcher起動追加 | 中 |
| pane変数設定 | @agent_id, @agent_cli の設定追加 | 小 |

#### (E) CLAUDE.md / AGENTS.md

| 変更箇所 | 内容 | 工数 |
|---------|------|------|
| 階層構造図 | 2家老体制+お針子の図を追加 | 小 |
| ペイン対応表 | ookuセッションのペイン定義を追加 | 小 |
| 通信プロトコル | 部屋子→御台所、お針子→家老のルール追加 | 中 |
| 復帰手順 | 部屋子・お針子用の復帰手順追加 | 中 |

### 2.2 工数見積もり

| カテゴリ | ファイル数 | 工数 |
|---------|----------|------|
| 新規ロール指示書 | 3ファイル | 1日 |
| cli_adapter.sh修正 | 1ファイル | 2時間 |
| build_instructions.sh修正 | 1ファイル | 2時間 |
| common/*.md修正 | 3ファイル | 半日 |
| shutsujin_departure.sh修正 | 1ファイル | 1日 |
| CLAUDE.md修正 | 1ファイル | 半日 |
| テスト | — | 1日 |
| **合計** | **10ファイル** | **4日** |

### 2.3 推奨アプローチ

**PRに含めるべき最小スコープ**:
1. `instructions/roles/` に3ロール追加
2. `lib/cli_adapter.sh` のロール判定修正
3. `scripts/build_instructions.sh` のビルド対象追加
4. `CLAUDE.md` に階層構造・ペイン対応表の追加

**PRに含めるべきでないもの**:
- 没日録DB（設計思想が異なる。本家はYAML運用）
- 3セッション構成（本家の2セッション構成を前提としたdiff最小化のため）
- お針子のツンデレ口調（本家ユーザーに混乱を招く）

---

## 分析観点3: 通信プロトコルの差異

### 3.1 方式比較

```
【本家: inbox方式】
送信側 → inbox_write.sh → queue/inbox/{agent}.yaml に書き込み
                                     ↓
                            inbox_watcher.sh (inotifywait)
                                     ↓
                            tmux send-keys 'inboxN' (件数のみ)
                                     ↓
受信側 → inbox読み込みプロトコル → queue/inbox/{agent}.yaml からメッセージ取得

【我々: send-keys方式】
送信側 → tmux send-keys -t {pane} 'メッセージ本文'   ← 1回目
       → tmux send-keys -t {pane} Enter              ← 2回目
                                     ↓
受信側 → Claude Codeがプロンプトとして直接受信
```

### 3.2 詳細比較

| 比較項目 | 本家（inbox） | 我々（send-keys） |
|---------|-------------|-----------------|
| **永続性** | ✅ YAMLファイルに永続化 | ❌ tmuxバッファのみ（揮発） |
| **通信ロスト耐性** | ✅ 高い（ファイルに残る） | ⚠️ 到達確認プロトコルで補完 |
| **busy時の挙動** | ✅ nudge（`inboxN`）のみ送信 | ⚠️ リトライ（最大3回、10秒間隔） |
| **メッセージ長制限** | ✅ なし（ファイル書き込み） | ⚠️ send-keysの実用的上限あり |
| **リアルタイム性** | ⚠️ inotifywait遅延（~1秒） | ✅ 即時 |
| **実装の単純さ** | ❌ 中間スクリプト2本必要 | ✅ tmuxコマンドのみ |
| **依存ソフトウェア** | inotifywait（inotify-tools） | tmux（既存） |
| **割り込み制御** | ✅ 短いnudgeで最小化 | ⚠️ 長いメッセージが入力中に割り込む可能性 |
| **Multi-CLI対応** | ✅ CLI種別別入力方式切替 | ❌ Claude Code専用 |
| **監査証跡** | ✅ YAMLファイルに履歴残る | ❌ 揮発（没日録DBで補完） |

### 3.3 本家inbox方式の詳細

```bash
# inbox_write.sh の使い方
bash scripts/inbox_write.sh <recipient> "<message>" <cmd_id> <sender>
# 例: bash scripts/inbox_write.sh karo "タスク完了" cmd_100 ashigaru1

# inbox_watcher.sh の動作
1. inotifywait で queue/inbox/{agent}.yaml を監視
2. 変更検知 → 未読メッセージ件数カウント
3. tmux send-keys -t {pane} "inbox{N}" (件数のみ。本文は送らない)
4. 受信側がinboxプロトコルでYAMLからメッセージ取得
```

**設計意図**:
- 本文をsend-keysで送らないことで、入力中のテキスト破壊を防止
- ファイルに永続化することで、再起動時も未読メッセージを保持
- CLI種別に応じてnudge方法を切替可能

### 3.4 我々のsend-keys方式の補完策

我々はsend-keys方式の弱点を以下で補完している:

| 弱点 | 補完策 | 実装場所 |
|------|--------|---------|
| 通信ロスト | 到達確認プロトコル（capture-pane + リトライ） | instructions/ashigaru.md |
| busy時割り込み | idle判定（❯表示チェック）→ sleep 10リトライ | instructions/ashigaru.md |
| Enter解釈問題 | 2回分割送信（メッセージ→Enter） | CLAUDE.md |
| 揮発性 | 没日録DB（report add）で永続化 | scripts/botsunichiroku.py |
| 割り込み防止 | 家老→将軍はdashboard.md更新のみ（send-keys禁止） | CLAUDE.md |

### 3.5 移行判断

**結論: 現状維持（send-keys方式を継続）**

**理由**:
1. **補完策が機能している**: 到達確認プロトコルと没日録DBの組み合わせで、実運用上の問題は最小限
2. **実装コストが高い**: inbox方式への移行は全エージェントの通信コード変更が必要
3. **依存追加を避ける**: inotify-toolsの追加インストールが必要
4. **没日録DBが代替**: メッセージの永続化は没日録DBが担っており、YAMLファイルでの二重管理は不要

**将来的に再検討すべきトリガー**:
- 通信ロストが頻発する場合
- Codex/Kimi等の別CLIを混在運用する場合
- エージェント数が15名以上に増加する場合

---

## 分析観点4: 本家への貢献で小PRとして切り出せる部分

### 4.1 PR候補一覧

#### PR-A: audit CLI サブコマンド（即座にPR可能）

**スコープ**: `scripts/botsunichiroku.py` の audit サブコマンド + subtask list フィルタ

**含めるもの**:
- `subtask list --needs-audit` フィルタ
- `subtask list --audit-status` フィルタ
- `subtask update --needs-audit / --audit-status` オプション
- DBスキーマに `needs_audit`, `audit_status` カラム追加

**含めないもの**:
- お針子エージェント自体（ロール・指示書は含めない）
- ツンデレ口調
- ookuセッション構成

**工数**: 半日
**PR規模**: ~200行
**本家へのメリット**: 品質管理フローの基盤を提供

---

#### PR-B: 没日録DB CLI の基本機能（中規模）

**スコープ**: `scripts/botsunichiroku.py` + `data/botsunichiroku.db` スキーマ

**含めるもの**:
- cmd / subtask / report のCRUD操作
- wave管理（subtaskのwave割当・フィルタ）
- worker割当（subtask list --worker）
- SQLite DBスキーマ定義

**含めないもの**:
- 大奥固有フィールド（assigned_by: ooku 等）
- お針子固有機能（先行割当）

**工数**: 1日
**PR規模**: ~800行
**本家へのメリット**: YAML通信からDB管理への移行パスを提供

**注意**: 本家がYAML運用を継続している場合、設計思想の不一致で受け入れられない可能性あり。事前にIssueで方向性を確認すべし。

---

#### PR-C: get_instruction_file のロール拡張（最小PR）

**スコープ**: `lib/cli_adapter.sh` の `get_instruction_file()` 関数修正

**含めるもの**:
- `midaidokoro`, `heyago*`, `ohariko` のロール判定追加
- `get_agent_model()` のデフォルトモデル追加

**含めないもの**:
- 実際のinstructionsファイル（roles/midaidokoro_role.md 等）
- ビルドスクリプトの変更
- CLAUDE.mdの変更

**工数**: 2時間
**PR規模**: ~30行
**本家へのメリット**: 将来のロール拡張に対応した前方互換性

**注意**: 実際のinstructionsファイルがなければ意味がないため、PR-DとセットでPRすべし。

---

#### PR-D: 大奥ロールの指示書（feature/ooku-tokugawa）

**スコープ**: 新ロール3種の指示書 + CLAUDE.md/AGENTS.md修正

**含めるもの**:
- `instructions/roles/midaidokoro_role.md` — 御台所（内部システム担当家老）
- `instructions/roles/heyago_role.md` — 部屋子（御台所配下の実働部隊）
- `instructions/roles/ohariko_role.md` — お針子（監査・先行割当）
- `instructions/common/protocol.md` に ookuセッション通信ルール追加
- `CLAUDE.md` の階層構造図・ペイン対応表更新

**含めないもの**:
- 没日録DB（本家はYAML運用）
- shutsujin_departure.sh のookuセッション起動（大規模変更になるため別PR）
- ツンデレ口調の強制（本家ユーザーの混乱防止。オプションとして提案）

**工数**: 2日
**PR規模**: ~500行
**本家へのメリット**: 2家老体制による役割分担の選択肢を提供

**注意**: 既存PR #17（feature/ooku-tokugawa）の範囲。現在の差分が大きいため、PR-A〜Cを先に出して小さく取り込んでもらう戦略が有効。

---

### 4.2 PR戦略の推奨順序

```
PR-A: audit CLI (即座にPR可能、最小スコープ)
  ↓
PR-C + PR-D: ロール拡張 + 大奥指示書 (セットでPR)
  ↓
PR-B: 没日録DB (Issueで方向性確認後)
```

**理由**:
1. **PR-Aが最もリスクが低い**: 既存機能の拡張のみで、設計思想の衝突がない
2. **PR-C+Dは本家のロール拡張**: マルチCLI基盤の上に新ロールを追加する形で、本家の設計に沿っている
3. **PR-Bは設計思想の確認が必要**: YAML→DB移行は本家の方向性次第

### 4.3 PRに含めるべきでないもの（private fork独自機能）

| 機能 | 理由 |
|------|------|
| 没日録DBのooku固有フィールド | 本家はYAML運用 |
| 3セッション構成のshutsuijn | 本家の2セッション構成との差異が大きすぎる |
| ツンデレ口調（お針子） | 殿の勅命であり本家の方針と異なる |
| Memory MCPの農業IoT知見 | プロジェクト固有 |
| /clear最適化の3段階復帰 | 本家は統一手順を選択済み |

---

## 付録A: 4CLI比較マトリクス

| 機能 | Claude Code | Codex | Copilot | Kimi |
|------|------------|-------|---------|------|
| **Memory MCP** | ✅ 組み込み | ⚠️ 設定で追加 | ❌ 無し | ⚠️ 設定で追加 |
| **Task tool** | ✅ 外部プロセス | ❌ 無し | ⚠️ /delegate | ✅ Agent Swarm |
| **Skills** | ✅ Skill tool | ❌ | ❌ | ✅ /skill + /flow |
| **/clear** | ✅ | ⚠️ /new | ❌ /compact | ❌ /compact |
| **tmux統合** | ✅ 実証済み | ⚠️ --no-alt-screen | ⚠️ 未検証 | ✅ 実証済み |
| **自動読込** | CLAUDE.md | AGENTS.md | copilot-instructions.md | AGENTS.md + /init |
| **Agent並列** | 8並列実証 | 制限あり | Premium制限 | 100並列（公称） |
| **Prompt cache** | 90%割引 | 75%割引 | 不明 | 不明 |

## 付録B: ファイルサイズ・トークン比較

| 分類 | ファイル | サイズ | トークン推定 |
|------|---------|-------|------------|
| 最小 | generated/ashigaru.md (Claude) | 16KB | ~3,700 |
| 中間 | generated/codex-ashigaru.md | 22KB | ~5,200 |
| 最大 | generated/kimi-karo.md | 33KB | ~7,800 |
| 我々 | instructions/ashigaru.md | ~20KB | ~4,700 |

**トークン効率の観点**:
- 本家のClaude版ashigaru.md（16KB）は我々のashigaru.md（20KB）より小さい
- 理由: 本家は共通部分をcommon/に分離し、必要最小限のみ結合
- 我々は部屋子モード等の条件分岐を1ファイルに含めているため肥大化

## 付録C: 我々の独自機能一覧

| 機能 | 本家にあるか | 概要 |
|------|------------|------|
| 2家老体制（老中+御台所） | ❌ | 外部PJ/内部システムの役割分担 |
| 部屋子（heyago） | ❌ | 御台所配下の調査実働部隊 |
| お針子（ohariko） | ❌ | 監査・予測・先行割当の特殊エージェント |
| 没日録DB（SQLite） | ❌ | YAML通信に代わる永続データストア |
| 3セッション構成 | ❌ | shogun/multiagent/ooku |
| /clear最適化 | ❌ | 状況別3段階復帰（セッション開始/コンパクション/clear） |
| 到達確認プロトコル | ❌ | send-keys後のcapture-pane+リトライ |
| context/{project}.md | ❌ | プロジェクト固有の技術知見を足軽に提供 |

---

**報告者**: 部屋子1（heyago1）
**分析完了日時**: 2026-02-08
