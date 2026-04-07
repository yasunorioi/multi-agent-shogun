# memx-core設計パターン shogun移植可能性リサーチ

> **cmd_366 / subtask_808** | 2026-03-08
> **リポジトリ**: https://github.com/RNA4219/memx-core (MIT License)

## memx-core概要

ローカルLLM/エージェント向け軽量メモリ基盤。4つのSQLiteストア（short/journal/knowledge/archive）でメモの保存・検索・要約・GCを管理。Go実装、シングルバイナリ、10,195行。

### memx-core ↔ shogun コンポーネント対比表

| memx-core | 役割 | shogun相当 | 現在の実装 |
|-----------|------|-----------|-----------|
| `short.db` | 短期メモ・作業中情報 | inbox YAML (Layer 3a) | Python YAML読み書き |
| `journal.db` | 時系列ログ・進捗 | 没日録DB (botsunichiroku.db) | Python CLI (botsunichiroku.py) |
| `knowledge.db` | 知識・定義・手順 | context/*.md + Memory MCP | Markdown + MCP JSON |
| `archive.db` | 退避保管（検索対象外） | queue/archive/ | 手動YAML移動 |
| Gatekeeper | 保存前/出力前の安全チェック | お針子（事後監査） | send-keys + YAML報告 |
| GC | 自動アーカイブ | 手動「直近10件保持」ルール | 家老が手動でYAML削除 |
| ADR | 意思決定履歴 | なし（dashboard.mdに散在） | なし |
| `mem` CLI | シングルバイナリCLI | botsunichiroku.py + worker_ctl.sh + inbox_write.sh | Python + Bash群 |
| HTTP API | REST API | 高札API (localhost:8080) | Docker + Python |

---

## 1. Go統合の実現可能性

### 1.1 シングルバイナリ化の対象

| 現在のコンポーネント | 行数 | Go化の難易度 | 効果 |
|-------------------|------|:-----------:|------|
| botsunichiroku.py | ~800行 | ★★☆ 中 | CLI高速化、依存削減 |
| 高札API (Docker) | ~500行 | ★★☆ 中 | Docker廃止、起動高速化 |
| inbox_write.sh | ~100行 | ★☆☆ 易 | シェル依存削減 |
| worker_ctl.sh | ~200行 | ★★★ 難 | tmux操作はshellが自然 |
| stop_hook_inbox.sh | ~120行 | ★★☆ 中 | YAML解析の堅牢化 |

### 1.2 Claude Code Bashツール→Go CLI呼び出し

- **利点**: `go build` で単一バイナリ。Python venv不要、パス問題なし
- **利点**: 起動時間 Go CLI ~10ms vs Python CLI ~300ms（毎回import処理）
- **利点**: memx-coreの`mem in/out`パターンがそのまま適用可能
  - `shogun cmd add` / `shogun subtask list` / `shogun report add`
- **制約**: Claude CodeのBashツールはstdout/stderrを読むだけなので、Go/Python差はない
- **制約**: tmux send-keys操作はos/execでも可能だが、shellの方が自然

### 1.3 tmux send-keys制御のGo方式

```go
// Go版send-keys（概念コード）
func sendKeys(pane, message string) error {
    cmd := exec.Command("tmux", "send-keys", "-t", pane, message)
    if err := cmd.Run(); err != nil { return err }
    cmd2 := exec.Command("tmux", "send-keys", "-t", pane, "Enter")
    return cmd2.Run()
}
```

技術的には可能だが、tmux操作はshellスクリプトの方がメンテナンスしやすい。

### 1.4 go install一発 vs 現在の構成

| 項目 | 現在 | Go化後 |
|------|------|--------|
| 依存 | Python3 + pyyaml + sqlite3 + bash | Goバイナリ1つ |
| インストール | git clone + 各種設定 | `go install` or バイナリダウンロード |
| 更新 | git pull | バイナリ差し替え |
| 開発 | Python（家老含む全員が読める） | Go（学習コスト あり） |

### 1.5 結論: Go統合

**部分採用を推奨。** 没日録CLI+高札APIをGoシングルバイナリに統合するのが最も効果的。tmux操作系(worker_ctl/send-keys)はshellのまま残す。

- **即効性**: ★★★（Python venv廃止、Docker廃止、起動高速化）
- **リスク**: ★★☆（Go移行の学習コスト、既存CLIとのI/F互換）
- **推奨スコープ**: `shogun` バイナリ = 没日録CLI + 高札API + inbox管理

---

## 2. ADR(Architecture Decision Record)導入

### 2.1 memx-coreのADR方式

- `docs/ADR/` ディレクトリに `ADR-NNNN-slug.md` で管理
- 構造: Status / Date / Context / Decision / Consequences
- `docs/ADR/README.md` に一覧・索引
- 現在3件: 4DB分割(0001)、v1必須エンドポイント(0002)、エラーコード設計(0003)

### 2.2 shogun適用設計

**案A: 高札FTS5検索統合（推奨）**

```
docs/ADR/
├── README.md (索引)
├── ADR-0001-yaml-db-two-layer.md
├── ADR-0002-ohariko-audit-queue.md
├── ADR-0003-blocked-by-dependency.md
└── ADR-0004-context-extraction.md
```

- 高札API `http://localhost:8080/search?q=ADR` で全文検索可能
- 没日録DBに `adr` テーブル追加は不要（Markdownファイルを高札が直接インデックス）
- Git管理対象（意思決定履歴はバージョン管理すべき）

**案B: 没日録DB別テーブル**

- `CREATE TABLE adr (id TEXT PRIMARY KEY, title TEXT, status TEXT, context TEXT, decision TEXT, consequences TEXT, created_at TEXT)`
- CLIから `shogun adr add/list/show`
- メリット: 構造化クエリ可能
- デメリット: Markdown可読性が失われる、没日録DB肥大化

### 2.3 Memory MCPとの棲み分け

| 記憶層 | 内容 | 例 | 寿命 |
|--------|------|-----|------|
| **ADR** | 意思決定の経緯と根拠 | 「なぜYAML+DB二層にしたか」 | 永続（Git管理） |
| **Memory MCP** | 殿の好み・行動原則 | 「シンプル好き」「月額忌避」 | 永続（jsonl） |
| **context/*.md** | PJ固有の技術知見 | 「uecs-llmのセンサー仕様」 | 永続（Git管理外） |

ADRはシステム設計判断、Memory MCPは人的嗜好、contextは技術知見。重複なし。

### 2.4 結論: ADR導入

**案Aを推奨。** `docs/ADR/` にMarkdownで管理し、高札FTS5で検索。1subtaskで導入可能。過去の重要決定（通信プロトコルv2、没日録DB設計、お針子設計等）を遡ってADR化するのに2-3subtask。

---

## 3. 自動GC

### 3.1 memx-coreのGC設計

```
Phase 0: トリガ判定
  └─ soft_limit(1200件) + min_interval(180分) → 条件合致で実行
  └─ hard_limit(2000件) → 即時実行

Phase 3: Archive退避
  └─ access_count=0 + 作成30日以上 → archive.dbに移動
  └─ lineageテーブルに系譜記録（archived_from）
  └─ dry-run対応（--dry-runで影響確認のみ）
```

### 3.2 shogun適用設計

| memx-core | shogun版 | 実装方式 |
|-----------|---------|---------|
| soft_limit(1200件) | 報告YAML 10件超過 | `wc -l` or YAML件数カウント |
| hard_limit(2000件) | 報告YAML 30件超過 | 同上 |
| min_interval(180分) | 家老のタスク処理サイクル | 起こされるたびにチェック |
| access_count=0 | `read: true` かつDB永続化済み | YAMLのreadフィールド |
| archive退避 | YAML削除（DBに永続化済み） | 高札検索で復元可能 |
| dry-run | `--dry-run` でアーカイブ候補表示 | CLI実装 |

**shogun GCスクリプト案（Bash）:**

```bash
# shogun-gc.sh --dry-run
# roju_reports.yaml の read:true かつ DB永続化済みエントリを削除
# 直近10件は保持（現行ルール踏襲）
```

### 3.3 現在の手動ルールとの比較

| 項目 | 現在（手動） | 自動GC後 |
|------|------------|---------|
| トリガ | 家老が手動判断 | 閾値超過で自動実行 |
| 対象判定 | 家老が目視 | read:true + DB永続化済み |
| 実行 | 家老がEdit tool | スクリプト実行 |
| 安全性 | 家老の判断次第 | dry-run + 閾値保護 |
| 頻度 | 不定期（忘れがち） | タスク処理サイクルごと |

### 3.4 結論: 自動GC

**即導入推奨。** `scripts/shogun-gc.sh` として実装。1subtaskで完了。dry-run対応で安全。家老の手動YAML削除負荷を完全自動化できる。

---

## 4. Gatekeeper設計

### 4.1 memx-coreのGatekeeper

```go
// 3段階判定
type GatekeeperDecision struct {
    Decision   string // "allow" | "deny" | "needs_human"
    Reason     string
    Categories []string
}

// 事前チェック（保存前 + 出力前）
GateKindMemoryStore  = "memory_store"   // 保存前
GateKindMemoryOutput = "memory_output"  // 出力前

// 3プロファイル
GateProfileStrict = "STRICT"  // trusted以外はneeds_human
GateProfileNormal = "NORMAL"  // untrustedのみneeds_human
GateProfileDev    = "DEV"     // secret以外はallow
```

**fail-closed設計**: `needs_human` → deny相当として安全側に倒す。

### 4.2 お針子事後監査 + Gatekeeper事前チェック併用

| レイヤー | タイミング | チェック内容 | 判定者 |
|---------|----------|------------|--------|
| **Gatekeeper（事前）** | subtask割当時 | F001-F006禁止事項 | 自動（ルールベース） |
| **お針子（事後）** | subtask完了後 | 成果物品質・設計準拠 | お針子エージェント |

### 4.3 禁止事項のGatekeeper型ルール実装

```yaml
# gatekeeper_rules.yaml
rules:
  - id: F001
    kind: task_assign
    check: "足軽のtarget_pathが自プロジェクト外でないか"
    decision: deny

  - id: F002
    kind: send_keys
    check: "将軍→足軽への直接send-keysでないか"
    decision: deny

  - id: F004
    kind: bash_command
    check: "while true/sleep/watchパターンでないか"
    decision: deny

  - id: F006
    kind: bash_command
    check: "gh issue create/gh pr createでないか"
    decision: deny
```

**実装方式**: stop_hookまたはClaude Code hooksのpre-tool-useフックで、Bashコマンド実行前にルールチェック。

### 4.4 fail-closed設計の適用範囲

| 対象 | fail-closed適用 | 理由 |
|------|:---:|------|
| F006 (GitHub操作) | **Yes** | 外部影響大、取り消し困難 |
| F002 (直接指示) | **Yes** | 指揮系統の根幹 |
| F004 (ポーリング) | No | コスト問題のみ、致命的でない |
| F001 (自己実行) | No | 検出困難、事後監査が現実的 |

### 4.5 結論: Gatekeeper設計

**段階的導入を推奨。** Phase 1: F006(GitHub操作)のstop_hookチェック（既存hook拡張で1subtask）。Phase 2: 他の禁止事項のルールベースチェック。お針子の事後監査と併用し、Gatekeeperは「明確に禁止できるもの」のみ担当。

---

## 5. knowledge昇格パターン

### 5.1 memx-coreの昇格パターン

```
short（短期メモ）
  │ access_count増加 + pinned=true
  ▼
knowledge（永続知識）
  │ scope付与 + working_scope必須
  ▼
archive（退避）← GCで自動移動
```

- short→knowledgeは明示的な昇格操作（`mem in knowledge`）
- knowledge.dbのノートは `working_scope`（プロジェクトスコープ）と `is_pinned`（固定表示）を持つ
- 昇格基準: 繰り返しアクセスされる情報、プロジェクト横断で再利用される知見

### 5.2 shogun版: subtask報告→context蓄積

```
subtask報告（Layer 3a: 報告YAML）
  │ 家老がDB永続化（Layer 3b）
  │ お針子が監査時にパターン検出
  ▼
context/{project}.md（Layer 2: PJ固有知見）
  │ 繰り返し参照される知見を蓄積
  ▼
Memory MCP（Layer 1: 殿の好み・横断知見）
  │ プロジェクト横断の重要知見
  ▼
docs/ADR/（意思決定記録）← 設計判断のみ
```

### 5.3 自動蓄積方式の設計

**トリガ**: お針子監査時に以下のパターンを検出→context/*.md に自動追記

| パターン | 検出方法 | 蓄積先 |
|---------|---------|--------|
| 同一エラーが3回以上 | 高札検索で同一キーワードのreport件数 | context/{project}.md |
| skill_candidateの重複 | dashboard.mdスキル候補との突合 | docs/skill_ice_ranking.md |
| 頻出コマンドパターン | report内のbashコマンド集計 | context/karo-*.md |
| 設計判断の記録 | 「〜を採用」「〜は不採用」パターン | docs/ADR/ |

**実装方式**: お針子の監査ルーブリックに「knowledge昇格候補の検出」項目を追加。お針子が報告YAMLに `knowledge_candidate:` フィールドを追記。家老がcontext/*.mdに反映。

### 5.4 結論: knowledge昇格

**段階的導入を推奨。** Phase 1: お針子の監査ルーブリックに昇格候補検出を追加（0.5subtask）。Phase 2: 家老のcontext/*.md自動追記フロー整備（1subtask）。完全自動化は精度課題があるため、お針子→家老の半自動フローが現実的。

---

## 総合評価

| 項目 | 移植可能性 | 効果 | 工数 | 推奨 |
|------|:---------:|:----:|:----:|:----:|
| 1. Go統合（部分） | ★★★★ | ★★★★ | 3-5 subtask | **次スプリント** |
| 2. ADR導入 | ★★★★★ | ★★★ | 1-3 subtask | **即実装** |
| 3. 自動GC | ★★★★★ | ★★★★ | 1 subtask | **即実装** |
| 4. Gatekeeper | ★★★ | ★★★ | 2-3 subtask | **段階的** |
| 5. knowledge昇格 | ★★★ | ★★ | 1.5 subtask | **段階的** |

### 推奨実施順序

1. **自動GC**（1subtask、即効果、YAML肥大化問題の根本解決）
2. **ADR導入**（1subtask、過去の設計判断をADR化は追加2subtask）
3. **Gatekeeper Phase1**（1subtask、F006のhookチェック）
4. **Go統合設計**（1subtask設計、3subtask実装）
5. **knowledge昇格**（お針子ルーブリック拡張0.5subtask + 家老フロー1subtask）
