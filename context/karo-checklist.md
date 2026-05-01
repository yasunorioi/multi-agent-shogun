# 家老 確認チェックリスト

**関連cmd**: cmd_573 (S3) / cmd_571 §4 P1三層 / **作成日**: 2026-05-02

---

## 1. 「ファイル/機構未存在」と判定する前の必須手順

> 「ls で見つからない → 未存在」は **即席チェック禁止**。以下を全項確認してから「未存在」と告知せよ。

| # | 確認コマンド | 説明 |
|---|---|---|
| 1 | `find . -name "*.py" \| xargs grep -l <キーワード>` | サブディレクトリ含む全横断検索 |
| 2 | `bash scripts/karo_check.sh exists <キーワード>` | 第三層ツール（机上確認の機械化）|
| 3 | `git log --all --oneline \| grep -i <キーワード>` | commit履歴でキーワード照会 |
| 4 | `git log --diff-filter=D --name-only --pretty=format: \| grep <pattern>` | 削除されたファイルを追跡 |
| 5 | `python3 scripts/botsunichiroku.py cmd show <cmd_id>` | 起源cmdの設計書・成果物確認 |
| 6 | 軍師に独立検証依頼 | 同じ情報源を参照していない第三者確認 |

**これら全てをPASSしてから「未存在」と殿へ告知せよ。**

---

## 2. grep経由確認テンプレ集

### 2.1 ファイル検索（全サブディレクトリ横断）

```bash
# キーワードでPythonファイル横断
find scripts -name "*.py" | xargs grep -l "crystallize"

# ファイル名パターンで検索（scripts/botsu/含む）
find . -name "*crystall*" -not -path "./.git/*"

# 特定ディレクトリ配下の全ファイル
find scripts -type f -name "*.py" -o -name "*.sh" | head -30
```

### 2.2 削除ファイル追跡

```bash
# 削除されたファイル一覧
git log --diff-filter=D --name-only --pretty=format: | sort -u

# 特定パターンのファイルが削除された時点のcommit
git log --diff-filter=D --name-only --oneline | grep -A1 "botsu"
```

### 2.3 機構・モジュール存在確認

```bash
# Pythonモジュールの実際のimport可否
python3 -c "import scripts.botsu.crystallize; print('OK')"

# シンボル（関数・クラス）の存在確認
grep -r "def crystallize_cmd" scripts/

# 設計書に記載されたパスの実在確認
bash scripts/karo_check.sh path scripts/botsu/crystallize.py
```

### 2.4 commit/変更追跡

```bash
# 特定ファイルの変更履歴
git log --oneline -- scripts/botsu/crystallize.py

# 特定commitで変更されたファイル
git show --name-only <commit_hash>

# 直近commitの内容確認
git log --oneline -5
```

---

## 3. 殿への進言前チェックリスト

進言・報告・指示を出す前に以下を確認せよ：

- [ ] **表面検索だけで判断していないか**（`ls` 1回ではなく、`find` + `grep` + `git log` の三段確認済みか）
- [ ] **scripts/botsu/ サブディレクトリを見落としていないか**（`ls scripts/` では `scripts/botsu/` 配下は表示されない）
- [ ] **git管理外ファイルを除外していないか**（`.gitignore` 対象ファイルは `git ls-files` では見えない）
- [ ] **軍師の独立検証を受けたか**（同じ情報源を参照している同士では盲点を発見できない）
- [ ] **`bash scripts/karo_check.sh exists <キーワード>` を実行したか**（機械的確認で誤判定を排除）

---

## 4. cmd_570 教訓（必読）

> **cmd_570 実在性調査**（`docs/shogun/crystallize_v2_existence_audit_20260501.md`）で発覚した即席チェック失敗事例。

### 4.1 何が起きたか

- 家老が `ls scripts/crystallize*` で表面検索のみを実施
- `scripts/botsu/` サブディレクトリを見落とし
- 結果: `scripts/botsu/crystallize.py` が存在するにも関わらず「未存在」と判定

### 4.2 根本原因

| 原因 | 詳細 |
|---|---|
| `ls` のスコープ誤認 | `ls scripts/` は `scripts/` 直下のみ。`scripts/botsu/` 配下は表示しない |
| サブディレクトリ構造への油断 | `botsu/` が実装の隠し場所として機能（cmd_517での設計判断）|
| 機械的確認の欠如 | `find` / `grep` ではなく目視・記憶依存の判断 |

### 4.3 教訓

> **「見えない = 存在しない」ではない。必ず `find` + `git log` で確認せよ。**

再発防止三層（軍師設計書 §4.3 より）:
1. **第一層**: Memory MCP system-rules（既追加済・家老セッション開始時に復元）
2. **第二層**: 本ファイル（context/karo-checklist.md）— 確認手順の文書化
3. **第三層**: `scripts/karo_check.sh` — 機械化による誤判定排除

---

## 5. 権限マトリクス参照（§12.8）

>>1-10 各レスの主筆者・承認権限については設計書 §12.8 を参照せよ：
`docs/shogun/crystallize_v2_doc_design_20260502.md` §12.8

| 層 | レス | 主筆者 | 承認 |
|---|---|---|---|
| 安定層 | >>1 概要 | 殿/家老 | **殿（必須）** |
| 構造層 | >>2-4 | 軍師 | 家老（任意） |
| 運用層 | >>5-9 | お針子/軍師/家老 | なし |
| 安定層 | >>10 用語集 | 家老 | 軍師（任意） |

---

*作成: 足軽2(ashigaru2) | cmd_573 S3 | subtask_1209 | 2026-05-02*
