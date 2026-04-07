# git worktree活用による足軽並列作業の衝突回避設計

> **軍師分析** | 2026-03-18 | North Star: 衝突ゼロで並列作業。既存アーキテクチャを壊さず最小変更で最大効果

---

## 1. 現状の問題

複数足軽が同一リポジトリの `main` ブランチで並列作業すると、同一ファイルの同時編集で衝突する。
現行の `RACE-001`（同一ファイル書き込み禁止）はルールによる回避であり、ファイルシステムレベルの分離ではない。

---

## 2. Claude Code worktree機能の仕様（実機検証済み）

### 2.1 三種の起動方法

| 方法 | 用途 | トリガー |
|------|------|---------|
| `claude --worktree <name>` | セッション開始時に新規worktreeで起動 | CLIオプション |
| `EnterWorktree(name)` | セッション中にworktreeへ切り替え | ツール呼び出し |
| `isolation: "worktree"` | Agent toolのsubagentを隔離実行 | Agentパラメータ |

### 2.2 作成場所と挙動

- **場所**: `<repo>/.claude/worktrees/<name>/`
- **ブランチ**: `worktree-<name>`（HEADから分岐）
- **クリーンアップ**: 変更なし→自動削除、変更あり→keep/remove選択
- **制約**: worktree内にいる状態では二重にworktree作成不可

### 2.3 shogunとの互換性における重大な制約

**制約1: gitignoreファイルがworktreeに存在しない**

`.gitignore` で除外されたディレクトリ/ファイルはworktreeにコピーされない:

| カテゴリ | パス | worktree内 | 影響 |
|---------|------|:----------:|------|
| 没日録DB | `data/botsunichiroku.db` | **不在** | スクリプトがDB参照不可 |
| YAML通信 | `queue/inbox/*.yaml` | **不在** | タスク確認・報告記録不可 |
| コンテキスト | `context/*.md` | **不在** | プロジェクト知見参照不可 |
| 設定 | `config/settings.yaml` | **不在** | 言語設定等参照不可 |
| ダッシュボード | `dashboard.md` | **不在** | — |
| コード/スクリプト | `scripts/*.py` | **存在** | ✓ 正常動作 |
| 指示書 | `instructions/*.md` | **存在** | ✓ 正常動作 |
| テンプレート | `templates/*.yaml` | **存在** | ✓ 正常動作 |

**制約2: PROJECT_ROOT解決の問題**

`scripts/botsu/__init__.py` の `PROJECT_ROOT` は `Path(__file__).resolve().parent.parent` で解決される。
worktree内でスクリプトを実行すると、PROJECT_ROOTがworktreeルートを指し、`data/botsunichiroku.db` が見つからない。

**制約3: `.claude/*` gitignoreとworktree内git操作**

実機検証で `.claude/worktrees/` 内での `git add` に `-f` フラグが必要と報告あり。
ただしworktree自身のルートからの相対パスでは問題ないはず（追加検証推奨）。

---

## 3. 設計案比較

### 案A: EnterWorktree（Claude Code組み込み）

足軽がタスク開始時に `EnterWorktree` でworktreeに入り、完了時に `ExitWorktree(keep)` で抜ける。

```
足軽: inbox読む(絶対パス) → EnterWorktree("subtask-XXX")
    → CWDがworktreeに移動
    → コード編集（worktree内の相対パスでOK）
    → DB/YAML操作は絶対パスで本体リポジトリを参照
    → git commit（worktreeブランチに）
    → ExitWorktree(action: "keep")
    → 報告（絶対パスでYAML記録）→ send-keys
```

| 利点 | 欠点 |
|------|------|
| Claude Code統合（自動クリーンアップ） | CWD変更でスクリプト実行に影響 |
| 追加スクリプト不要 | `git add -f` が必要な可能性 |
| subagent `isolation: "worktree"` と同じ仕組み | worktree内にいる間は二重作成不可 |

### 案B: 手動worktree管理（superpowers方式）

`.worktrees/` ディレクトリにworktreeを作成、スクリプトで管理。

```
家老: git worktree add .worktrees/subtask-XXX -b subtask-XXX
    → inbox YAMLに worktree_path を記載
足軽: CWDを .worktrees/subtask-XXX/ に変更
    → 作業 → commit → 報告
家老: git merge subtask-XXX → git worktree remove .worktrees/subtask-XXX
```

| 利点 | 欠点 |
|------|------|
| 完全な制御権 | 追加スクリプトが必要 |
| `.claude/*` gitignore問題を回避 | 手動クリーンアップ |
| CWD外から `-C` オプションで操作可 | Claude Codeのworktree機能と二重管理 |

### 案C: CWD変更なし・絶対パス方式

足軽はCWDを変えず、worktreeのファイルを絶対パスで編集。

```
家老: git worktree add .worktrees/subtask-XXX -b subtask-XXX
足軽: CWDはメインリポジトリのまま
    → Read/Edit で .worktrees/subtask-XXX/scripts/foo.py を絶対パス操作
    → DB/YAML はそのまま相対パスで操作
    → git -C .worktrees/subtask-XXX/ add && commit
```

| 利点 | 欠点 |
|------|------|
| CWD変更なし（既存フロー影響ゼロ） | 全ファイルパスが冗長 |
| DB/YAML参照に変更不要 | Glob/Grep等のツールがworktreeを対象にしにくい |
| スクリプト修正不要 | 足軽の認知負荷が高い |

### 案D: ハイブリッド条件発動（推奨）

衝突リスクがある場合のみworktreeを使用。それ以外は現行通り。

```
家老: タスク分解時に衝突リスクを判定
    → 衝突リスクあり: inbox YAMLに worktree: true を追加
    → 衝突リスクなし: 従来通り（worktreeなし）
足軽: worktree: true なら EnterWorktree → 作業 → ExitWorktree
    → worktree: false/省略なら 従来通り
```

| 利点 | 欠点 |
|------|------|
| 必要な時だけコスト支払い | 家老の判断負荷 |
| 既存フロー影響を最小化 | worktree有無で足軽の動作が分岐 |
| シンプルなタスクはオーバーヘッドなし | 判断ミスで衝突が残る可能性 |

### 案E: 常時per-ashigaru worktree（冒険的）

各足軽に永続的な専用worktreeを割り当て、常にそこで作業。

```
shutsujin起動時: git worktree add .worktrees/ashigaru1 -b ashigaru1-work
足軽1: 常に .worktrees/ashigaru1/ で作業
タスク完了時: 家老がmain にマージ → git rebase main ashigaru1-work
```

| 利点 | 欠点 |
|------|------|
| 衝突ゼロの完全保証 | worktreeが常にmainから乖離 |
| タスクごとのセットアップ不要 | rebase/merge頻度が高い |
| 予測可能な環境 | コンフリクト解決が頻発する恐れ |
| 足軽の思考が単純化 | worktreeが古くなると大量コンフリクト |

---

## 4. 推奨案: D（ハイブリッド条件発動）+ A（EnterWorktree）メカニズム

### 4.1 推奨理由

1. **マクガイバー精神**: 問題がない場所にworktreeのコストを払わない
2. **既存アーキテクチャ温存**: tmux + YAML通信を壊さない
3. **最小変更**: 足軽instructionsへの追記は約20行、家老のタスクYAMLにフィールド1つ
4. **Claude Code組み込み活用**: EnterWorktree/ExitWorktreeで自動管理

### 4.2 衝突リスク判定基準（家老用）

| 条件 | worktree | 理由 |
|------|:--------:|------|
| 2名以上の足軽が同一プロジェクトの同一ディレクトリを編集 | **要** | ファイル衝突リスク高 |
| 足軽が既存コードを大規模リファクタリング | **要** | mainへの影響が広範 |
| 足軽が新規ファイルを別々のディレクトリに作成 | 不要 | 衝突なし |
| 1名の足軽のみ作業中（他はidle） | 不要 | 並列なし |
| ドキュメント・設計書のみの作業 | 不要 | docs/は各自別ファイル |

### 4.3 全体フロー

```
【タスク分解時（家老）】
1. subtask分解
2. 並列投入する足軽の作業対象ファイルを確認
3. 重複あり → inbox YAMLに worktree: true + worktree_name: "subtask-XXX"
4. 重複なし → 従来通り（worktreeフィールド省略）

【作業開始時（足軽）】
1. Read inbox YAML（絶対パス: /home/yasu/multi-agent-shogun/queue/inbox/ashigaru{N}.yaml）
2. worktree: true の場合:
   a. EnterWorktree(name: タスクYAMLの worktree_name)
   b. 「worktreeに入った。SHOGUN_ROOT=/home/yasu/multi-agent-shogun」と認識
3. worktree: false/省略 → 従来通り

【作業中（足軽）】
- コードファイル: 相対パスで編集（worktree内）
- YAML/DB/context: 絶対パスで参照
  - Read ${SHOGUN_ROOT}/queue/inbox/ashigaru{N}.yaml
  - python3 ${SHOGUN_ROOT}/scripts/botsunichiroku.py ...
  - Read ${SHOGUN_ROOT}/context/{project}.md
- git操作: 通常通り（worktreeブランチにcommit）

【作業完了時（足軽）】
1. worktreeブランチにcommit + push private
2. ExitWorktree(action: "keep")  ← worktreeとブランチを保持
3. 報告をroju_reports.yamlに記録（絶対パス）
4. send-keysで家老に通知

【監査（お針子）】← worktreeブランチ上で監査
- git diff main..worktree-subtask-XXX で変更差分を確認
- テスト実行はworktreeディレクトリで実行

【マージ（家老）】← 監査PASSの場合
1. git merge worktree-subtask-XXX（fast-forward推奨）
2. コンフリクト発生時 → 手動解決 or 足軽に差し戻し
3. git worktree remove .claude/worktrees/subtask-XXX
4. git branch -d worktree-subtask-XXX
5. git push private main
```

### 4.4 SHOGUN_ROOT環境変数

worktree内からメインリポジトリのリソースにアクセスするため、環境変数を導入:

```bash
# shutsujin_departure.sh または .bashrc に追加
export SHOGUN_ROOT=/home/yasu/multi-agent-shogun
```

足軽がworktree内にいるかどうかに関わらず、以下のパスで運用データにアクセス:

```bash
# YAML inbox
${SHOGUN_ROOT}/queue/inbox/ashigaru{N}.yaml

# 没日録
python3 ${SHOGUN_ROOT}/scripts/botsunichiroku.py ...

# コンテキスト
${SHOGUN_ROOT}/context/{project}.md

# 設定
${SHOGUN_ROOT}/config/settings.yaml
```

**スクリプト側の対応（任意・将来）**:
```python
# scripts/botsu/__init__.py に1行追加
SHOGUN_ROOT = Path(os.environ.get("SHOGUN_ROOT", str(PROJECT_ROOT)))
DB_PATH = SHOGUN_ROOT / "data" / "botsunichiroku.db"
```

> ただし現状、足軽がworktree内からスクリプトを直接実行することは稀。
> 絶対パスで `python3 ${SHOGUN_ROOT}/scripts/botsunichiroku.py` と呼べば不要。
> 将来の安全策として記録しておく。

### 4.5 identity_inject.sh の互換性

`identity_inject.sh` は `SCRIPT_DIR` を `$(dirname "${BASH_SOURCE[0]}")/..` で解決する。

- **worktreeなし**: 問題なし（従来通り）
- **worktree内で実行**: SCRIPT_DIRがworktreeルートを指す → `queue/inbox/` が不在
- **対策**: worktree内からは `bash ${SHOGUN_ROOT}/scripts/identity_inject.sh` で呼ぶ、
  または `SCRIPT_DIR` を `SHOGUN_ROOT` でオーバーライド:

```bash
# identity_inject.sh 冒頭に1行追加
SCRIPT_DIR="${__STOP_HOOK_SCRIPT_DIR:-${SHOGUN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"
```

この変更で `SHOGUN_ROOT` が設定されていればそちらを優先し、未設定なら従来の自動検出にフォールバック。

### 4.6 inbox YAMLフォーマット拡張

```yaml
# queue/inbox/ashigaru{N}.yaml のタスクに追加
tasks:
- subtask_id: subtask_XXX
  cmd_id: cmd_YYY
  status: assigned
  description: |
    ■ 実装: ...
  worktree: true                        # ← 新規フィールド
  worktree_name: "subtask-XXX"          # ← 新規フィールド（EnterWorktreeのname引数）
  project: shogun
  assigned_by: roju
```

### 4.7 マージ時のコンフリクト対処

```
コンフリクト発生時:
1. 家老がコンフリクト内容を確認
2. 単純な場合 → 家老がgit mergeで解決（例: 両方の変更を採用）
3. 複雑な場合 → 足軽に差し戻し（inbox YAMLに merge_conflict: true + 対象ファイル一覧）
4. 足軽がworktreeで修正 → recommit → 家老が再マージ
```

### 4.8 お針子の監査フロー

```
案1: worktreeブランチ上で監査（推奨）
  - git diff main..worktree-subtask-XXX で差分を取得
  - worktreeディレクトリでテスト実行
  - mainへのマージ前に品質担保

案2: マージ後に監査
  - 従来通りmain上で監査
  - 問題発見時のrevertが面倒
  → 非推奨
```

---

## 5. .gitignore に `.worktrees/` を追加する必要性

案Bを採用する場合は `.worktrees/` を `.gitignore` に追加する必要がある。
推奨案D+Aでは `.claude/worktrees/` を使用するため、既存の `.claude/*` ルールでカバー済み。

→ **追加不要**

---

## 6. 足軽instructions変更案（差分）

```markdown
## worktreeモード（条件発動）

タスクYAMLに `worktree: true` がある場合、以下の手順で作業せよ。

### 作業開始
1. `EnterWorktree(name: タスクYAMLのworktree_name)` を実行
2. CWDがworktreeに移動したことを確認
3. 以降、コードファイルは相対パスで編集可能

### 運用データアクセス（SHOGUN_ROOT経由）
worktree内からは以下を絶対パスで参照:
- inbox: `/home/yasu/multi-agent-shogun/queue/inbox/ashigaru{N}.yaml`
- 報告: `/home/yasu/multi-agent-shogun/queue/inbox/roju_reports.yaml`
- DB: `python3 /home/yasu/multi-agent-shogun/scripts/botsunichiroku.py ...`
- context: `/home/yasu/multi-agent-shogun/context/{project}.md`

### 作業完了
1. worktreeブランチにgit commit（通常通り）
2. `ExitWorktree(action: "keep")` — worktreeを保持して抜ける
3. 報告記録 + send-keys（従来通り）

### 注意
- worktree内で `queue/` や `data/` を探すな（存在しない）
- `git add -f` が必要な場合がある（`.claude/*` gitignoreの影響）
- worktreeなしのタスクは従来通り（この手順は不要）
```

---

## 7. 家老instructions変更案（差分）

```markdown
## worktree判定（タスク分解時）

並列投入する足軽の作業対象ファイルが重複する場合:
1. inbox YAMLに `worktree: true` と `worktree_name: "subtask-XXX"` を追加
2. 足軽にworktreeモードで作業させる

完了報告受領後（監査PASS後）:
1. `git merge worktree-subtask-XXX`
2. コンフリクト時は手動解決 or 足軽に差し戻し
3. `git worktree remove .claude/worktrees/subtask-XXX`
4. `git branch -d worktree-subtask-XXX`
```

---

## 8. 見落としの可能性

拙者の分析には以下の盲点がありうる:

1. **`.claude/worktrees/` 内での `git add` 問題**: 実機検証で問題が報告されているが、原因の切り分けが不十分。worktree自身のルートからの相対パスでは問題ないはずだが、追加検証が必要
2. **worktreeブランチのpush**: `git push private` でworktreeブランチをpushする際のリモート設定。private リモートに対して `git push private worktree-subtask-XXX` が必要
3. **お針子のworktreeアクセス**: お針子はookuセッション（別tmuxセッション）にいる。worktreeディレクトリへのアクセスは絶対パスで可能だが、テスト実行時のCWD問題
4. **長期worktree放置**: ExitWorktree(keep)後にマージが遅れると、worktreeがmainから乖離。定期的なクリーンアップcronが必要かもしれない
5. **Claude Code `--worktree` CLIオプションとの干渉**: 将来shutsujinが `claude --worktree` で足軽を起動する場合、EnterWorktreeとの二重worktreeが問題になる可能性

---

## 9. 実装フェーズ案（足軽向けsubtask分解）

### Wave 1: 基盤整備（並列可）

| subtask | 内容 | 担当 | 依存 |
|---------|------|------|------|
| A | `SHOGUN_ROOT` 環境変数を `shutsujin_departure.sh` に追加 | 足軽1 | なし |
| B | `identity_inject.sh` の `SCRIPT_DIR` フォールバック修正（1行） | 足軽1 | なし |
| C | `scripts/botsu/__init__.py` に `SHOGUN_ROOT` フォールバック追加（1行） | 足軽2 | なし |

### Wave 2: 指示書更新（Wave 1完了後）

| subtask | 内容 | 担当 | 依存 |
|---------|------|------|------|
| D | `instructions/ashigaru.md` にworktreeモードセクション追加 | 足軽1 | A,B |
| E | `instructions/karo.md` にworktree判定セクション追加 | 足軽2 | A |

### Wave 3: 統合テスト（Wave 2完了後）

| subtask | 内容 | 担当 | 依存 |
|---------|------|------|------|
| F | 実際にworktreeを作成し、足軽フローを手動テスト | 足軽1 | D,E |
| G | worktreeマージ→お針子監査フローのテスト | 足軽2 | F |

---

## 10. North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    衝突ゼロの並列作業を、既存のtmux+YAML通信を温存したまま実現する。
    ハイブリッド条件発動により、不要なオーバーヘッドを避けつつ
    衝突リスクがある場面では確実にファイルシステムレベルで分離する。
  risks_to_north_star:
    - "家老の衝突リスク判定が不正確だと、worktreeなしで衝突が発生する"
    - ".claude/worktrees/ 内の git add 問題が想定以上に深刻な場合、案Bへの切り替えが必要"
    - "worktree放置によるブランチ乖離が蓄積すると、マージコスト増大"
```
