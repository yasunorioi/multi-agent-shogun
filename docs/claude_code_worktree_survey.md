# Claude Code Worktree Isolation 検証報告書

> **subtask_903 / cmd_410**
> 担当: ashigaru2
> 日時: 2026-03-15T14:18:45
> 情報源: `claude --help` 実出力 + `ToolSearch` 公式ツール仕様 + 実機検証

---

## 概要

Claude Code の Worktree Isolation 機能（`isolation: "worktree"` / `EnterWorktree` / `--worktree`）を公式情報と実機検証で確認した。

---

## 1. Worktree の作成仕組み

### 3種類のWorktree起動方法

| 方法 | 用途 | トリガー |
|------|------|---------|
| `claude --worktree [name]` | メインセッションを新規worktreeで開始 | CLIオプション |
| `EnterWorktree` ツール | セッション中にworktreeへ切り替え | ユーザーが明示的に「worktree」と指定時のみ |
| `isolation: "worktree"` | Subagentを隔離実行 | Agent tool の frontmatter/パラメータ |

### EnterWorktree の公式仕様（ToolSearch取得）

```
条件:
- git リポジトリ内、または WorktreeCreate/WorktreeRemove Hooks が設定済み
- 既存のworktree内にいないこと

作成場所: <repo>/.claude/worktrees/<name>/
ブランチ名: worktree-<name>
ブランチ元: HEAD（現在のブランチの最新コミット）
名前省略時: ランダム名を自動生成
```

### 実機確認結果

```bash
# 実行
EnterWorktree(name: "test-isolation-903")
# → Created worktree at /home/yasu/multi-agent-shogun/.claude/worktrees/test-isolation-903
#    on branch worktree-test-isolation-903

# git worktree list
/home/yasu/multi-agent-shogun                                       73f93c1 [main]
/home/yasu/multi-agent-shogun/.claude/worktrees/test-isolation-903  6d01f64 [worktree-test-isolation-903]
```

- CWD が `/home/yasu/multi-agent-shogun/.claude/worktrees/test-isolation-903/` に切り替わる
- 同一 `.git` を共有（ブランチは独立）

---

## 2. 変更がある場合のWorktreeパスとブランチの返却仕様

### EnterWorktree 成功時レスポンス

```
Created worktree at <絶対パス> on branch <ブランチ名>.
The session is now working in the worktree.
Use ExitWorktree to leave mid-session, or exit the session to be prompted.
```

### ExitWorktree の公式仕様（ToolSearch取得）

```
action: "keep"  → worktreeディレクトリとブランチをディスクに保持
action: "remove" → worktreeディレクトリとブランチを削除

変更ありで remove する場合:
  discard_changes: true が必要（未指定時はエラーで一覧表示 → ユーザー確認後再実行）
```

### セッション終了時の挙動

- セッション終了時、まだworktree内にいる場合 → keep/remove をユーザーに確認
- `isolation: "worktree"` の subagent 終了時 → 変更なし=自動削除、変更あり=パスとブランチを返却

---

## 3. 変更がない場合の自動クリーンアップ

### 実機確認結果

```bash
# テストファイルを削除（変更なし状態）
ExitWorktree(action: "remove")
# → Exited and removed worktree at <path>. Session is now back in <original>.
#    ブランチも自動削除（git branchに worktree-test-isolation-903 なし）
```

- **変更なし + remove** → 即時削除、ユーザー確認不要
- **`isolation: "worktree"` subagent** → 変更なしの場合、subagent終了時に自動クリーンアップ（ユーザーへのプロンプトなし）

---

## 4. 現行 YAML 通信との共存確認

### ⚠️ 重要な制限：.gitignore による影響

このリポジトリの `.gitignore` に以下が設定されている:

```gitignore
.claude/*
queue/inbox/
queue/tasks/
queue/reports/
```

これにより、Claude Codeが作成するworktree（`.claude/worktrees/` 以下）は:
1. **相対パスで `queue/inbox/*.yaml` にアクセス不可**
   - worktreeのCWDは `.claude/worktrees/test-isolation-903/`
   - `queue/` ディレクトリが `.gitignore` で除外されているため、worktreeには存在しない
2. **絶対パスでのアクセスは可能**
   - `Read /home/yasu/multi-agent-shogun/queue/inbox/ashigaru2.yaml` → 読める（実機確認済み）
3. **worktree内での git add が制限される**
   - `.claude/*` ルールにより、worktree内ファイルは `.gitignore` でignoreされる
   - `git add -f` で強制追加は可能

### 実機確認

```
worktree内CWD: /home/yasu/multi-agent-shogun/.claude/worktrees/test-isolation-903/
ls queue/inbox/ → No such file or directory  ✗ 相対パス不可
cat /home/yasu/.../queue/inbox/ashigaru2.yaml → 読める  ✓ 絶対パス可
```

### ファイル空間の独立性

```
worktree の docs/test.md を作成
→ ホストの docs/test.md には存在しない（独立したファイル空間）  ✓
→ inode も異なる  ✓
```

**結論**: worktreeはホストと独立したファイル空間を持つ。ただし同一 `.git` を共有するため、gitの追跡ファイルはブランチの内容が反映される。

---

## 5. send-keys のペイン指定との関係

### 公式情報 + 論理検証

`tmux send-keys` はtmuxのペイン識別子（`multiagent:agents.0` 等）に対して操作を行う。
git worktreeはファイルシステム上の概念であり、tmuxペインとは独立している。

| 確認項目 | 結果 |
|---------|------|
| EnterWorktree後のCWD変更 | worktreeのセッション内のみ（他ペイン不変） |
| send-keys先の指定 | ペインID基準のため影響なし |
| 既存YAML通信プロトコル | 変更不要。絶対パスを使えばworktree内からも送信可 |

**結論**: send-keysと既存YAMLプロトコルはworktreeの影響を受けない。

---

## 6. 足軽の同一ファイル同時編集防止効果

### 検証結果

- worktreeを使うと **各エージェントが独立したファイル空間** で作業できる
- 同一ファイル（例: `context/uecs-llm.md`）を複数エージェントが同時編集する際のコンフリクトを防止可能
- ただし **YAML inbox/reports ファイルは共有ファイルシステム上** にあるため、worktreeによる保護対象外
  - RACE-001（同一ファイル書き込み禁止）は引き続き有効

---

## 7. worktree変更をmainにマージするフロー

### 公式情報に基づくフロー

```bash
# worktreeブランチで作業・コミット
git -C .claude/worktrees/<name>/ add <files>
git -C .claude/worktrees/<name>/ commit -m "..."

# ExitWorktree(action: "keep") でworktreeを保持してセッション復帰
ExitWorktree(action: "keep")

# メインでマージ
git merge worktree-<name>
# または
git rebase worktree-<name>

# 不要になったブランチ削除
git branch -d worktree-<name>
git worktree remove .claude/worktrees/<name>
```

### ⚠️ このリポジトリ特有の注意

- `.gitignore` の `.claude/*` により、worktree内でのファイルは `git add -f` が必要
- または worktreeを `.claude/` 以外に作成する（`git worktree add ../worktree-xxx branchname`）
- コンフリクト時は手動解決が必要（自動マージなし）

---

## 8. Agent tool `isolation: "worktree"` vs 他の方法の比較

| 項目 | `isolation: "worktree"` | `EnterWorktree` ツール | `--worktree` CLIオプション |
|------|------------------------|----------------------|--------------------------|
| 用途 | Subagent 隔離 | セッション中切り替え | セッション開始時 |
| トリガー | Agent tool 呼び出し | ユーザーが明示指定 | CLI起動時 |
| クリーンアップ | 変更なし→自動削除 | `ExitWorktree`で制御 | セッション終了時確認 |
| 変更あり時 | パス・ブランチ返却 | keep/remove 選択 | keep/remove 確認 |
| YAML絶対パス | ✓ アクセス可 | ✓ アクセス可 | ✓ アクセス可 |
| YAML相対パス | ✗ 不可 | ✗ 不可 | ✗ 不可 |

---

## 9. shogunシステムへの適用可能性

### 有効なユースケース

1. **コードファイルの並列編集**: 複数足軽が異なるブランチで独立してコードを修正する場合
2. **実験的変更**: mainに影響を与えず試行錯誤したい場合
3. **大規模リファクタリング**: ブランチを切って安全に作業し、完成後にマージ

### 現行システムとの共存条件

```yaml
# 共存条件
- YAMLアクセス: 絶対パスを使用（相対パスは不可）
- send-keys: 変更不要（tmuxペイン操作はworktree非依存）
- RACE-001: worktreeで解決できるのはコードファイルのみ。YAMLは対象外
- git commit: -f フラグが必要（.gitignore の .claude/* ルールのため）
```

### 推奨: worktreeブランチを `.claude/` 外に作る場合

```bash
# .claude/* gitignoreを回避する代替案
git worktree add /tmp/shogun-worktree-N branchname
# → /tmp/ 以下なら .gitignore の影響なし
```

---

## まとめ

| 調査項目 | 結果 |
|---------|------|
| worktree自動作成条件 | `.claude/worktrees/<name>/` にHEADから作成 |
| 変更あり時の返却 | パス + ブランチ名 + 確認プロンプト |
| 変更なし時 | 自動削除（ブランチも削除） |
| YAML相対パスアクセス | ✗ 不可（.gitignoreで除外のため） |
| YAML絶対パスアクセス | ✓ 可能（実機確認済み） |
| send-keys影響 | なし（tmuxペインはworktree非依存） |
| 同時編集防止 | コードファイルに有効。YAMLは対象外 |
| mainマージ | 手動（git merge/rebase）。.claude/*に注意 |

---

*情報源: `claude --help` 実出力 / `ToolSearch(select:EnterWorktree,ExitWorktree)` / 実機検証 (2026-03-15)*
*外部ブログ等は参照していない*
