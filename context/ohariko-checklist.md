# お針子 Pre-flight チェックリスト（C1-C5）

**関連cmd**: cmd_573 (S8) / cmd_571 §6 P4 / **作成日**: 2026-05-02
**対象**: お針子（ohariko）が監査を開始する前に必ず実施するチェック

> **Pre-flight check の位置づけ**: 18点ルーブリック採点を行う**前**に C1-C5 を実施する。
> 1つでも違反があればルーブリック採点せず**差し戻し（老中経由）**とすること。

---

## C1-C5 チェック項目一覧

| # | 項目 | 確認内容 | 確認方法 | 失敗時の対応 | 関連cmd |
|---|---|---|---|---|---|
| **C1** | パス整合性 | 報告に記載された `scripts/botsu/*` パスが実際に存在するか | `git ls-files <path>` / `bash scripts/karo_check.sh path <path>` | 差し戻し: 「報告パス不在。再確認せよ」| cmd_570 |
| **C2** | カウント整合性 | 報告中の「N回目稼働」等のカウント記述と実DB値が一致するか | `SELECT COUNT(*) FROM thread_replies WHERE board='crystals' GROUP BY thread_id` | 注意: カウント誤りを記録し老中に通知（廃止文化だが過去報告残存は許容） | cmd_570 |
| **C3** | 名称ドリフト検出 | `cmds.command` と実装内容（commit msg / コードコメント / docstring）の核心キーワードが一致するか | `python3 scripts/botsunichiroku.py cmd show <cmd_id>` でcommand確認 → `git log --oneline` と照合 | 差し戻し: 「名称ドリフト検出。cmds.commandと実装の乖離を修正せよ」 | cmd_570 (名称ドリフト事例) |
| **C4** | テスト存在チェック | `scripts/botsu/*` を修正した場合、対応する `tests/test_*.py` が存在するか | `find . -name "test_*.py" \| xargs grep -l <module_name>` | 差し戻し: 「テスト未実装。tests/test_*.py を追加せよ」 | cmd_571 §3.5 |
| **C5** | env変数追記整合 | 新環境変数を導入している場合、`.env.example` に説明コメントが追加されているか | `grep <VAR_NAME> .env.example` | 注意レベル（差し戻しではなく警告）: 「.env.exampleへのコメント追記を推奨」 | cmd_573 S5 |

---

## 各チェック詳細

### C1: パス整合性

**目的**: 足軽報告に記載されたファイルパスが実際にgitリポジトリに存在するかを機械的に確認する。

```bash
# 確認手順
git ls-files <報告記載のパス>
# または
bash scripts/karo_check.sh path <報告記載のパス>
```

**判定基準**:
- `git ls-files` で出力がある → PASS
- 出力なし → FAIL（差し戻し）

**注意**: `.gitignore` 対象ファイルは `git ls-files` では見えない。必要に応じて `ls -la` で補完。

---

### C2: カウント整合性

**目的**: 「結晶化N回目稼働」等のカウント記述（自然発生した報告慣習）が実データと乖離していないかを確認する。

> **文化廃止注記（2026-05-02殿裁定）**: 新規報告ではカウント記述は使わない。
> ただし過去報告のカウント記述は履歴価値があるため削除しない（cmd_570遡及検証で活用済み）。
> 新規報告にカウント記述があれば**警告レベル**（差し戻しではなく注意）。

```bash
# 実DBカウント確認（agent-swarm DB）
python3 - <<'EOF'
import sqlite3
db = "/home/yasu/agent-swarm/data/swarm.db"
conn = sqlite3.connect(db)
for row in conn.execute(
    "SELECT thread_id, COUNT(*) as cnt FROM thread_replies WHERE board='crystals' GROUP BY thread_id"
):
    print(row)
conn.close()
EOF
```

---

### C3: 名称ドリフト検出

**目的**: DB上の `cmds.command` フィールド（コマンド名）と実装の核心キーワードが乖離していないかを確認する。

**cmd_570 名称ドリフト事例**:
- DB: `cmds.command = "結晶化機構v1"` (旧名称)
- 実装: `crystallize.py` が既にv2相当の動作をしている
- → 名前が実態を反映していない「名称ドリフト」

```bash
# 確認手順
python3 scripts/botsunichiroku.py cmd show <cmd_id>
# → command フィールドのキーワードを確認

git log --oneline -10
# → commit messageのキーワードと照合

grep -r "def crystallize" scripts/botsu/
# → 実装のdocstringと照合
```

---

### C4: テスト存在チェック

**目的**: `scripts/botsu/` 配下のPythonファイルを修正した場合に、対応するユニットテストが存在するかを確認する。

```bash
# 修正したモジュール名でテストファイルを検索
find . -name "test_*.py" | xargs grep -l "crystallize" 2>/dev/null

# テスト実行（存在する場合）
python3 -m pytest tests/test_crystallize*.py -v
```

**判定基準**:
- `scripts/botsu/` 以外のみの変更（MD, YAML, sh等） → チェックスキップ可
- `scripts/botsu/*.py` 変更あり + テスト存在 → テスト実行・全PASS を確認
- `scripts/botsu/*.py` 変更あり + テスト不在 → FAIL（差し戻し）

---

### C5: env変数追記整合

**目的**: 新しい環境変数を導入した場合に、`.env.example` に説明コメントが追加されているかを確認する。

```bash
# 新環境変数の存在確認
grep "NEW_VAR_NAME" .env.example
grep "NEW_VAR_NAME" .env.example | grep "^#"  # コメント行の存在確認
```

**判定基準**:
- 新環境変数なし → チェックスキップ
- 新環境変数あり + `.env.example` にコメント追記 → PASS
- 新環境変数あり + `.env.example` にコメントなし → 警告（差し戻しではなく注意レベル）

---

## cmd_570 教訓（お針子視点）

> **cmd_570 実在性調査**（`docs/shogun/crystallize_v2_existence_audit_20260501.md`）で露見した監査の盲点。

### 何が起きたか

- 足軽がコミットハッシュ・ファイルパスを報告 → お針子が**実在確認をスキップ**して合格を出した
- 実際には `scripts/botsu/` 配下のファイルが不在の状態で監査を通過
- **お針子STEP3.5（コミット実在確認）未実施が原因**

### 教訓

| 項目 | 旧手順 | 改善後手順 |
|---|---|---|
| パス確認 | 報告内容を信頼 | **必ず** `git ls-files` で機械的確認 |
| コミット確認 | 省略しがち | `git log --oneline | grep <hash>` 必須 |
| C1-C5 | なし | **監査前 Pre-flight check として必須化** |

### お針子に特有の落とし穴

1. **同じ情報源を参照している**: 足軽と同じ `ls` 結果を見ていると盲点を共有する → `git ls-files` + DB直接確認で独立検証
2. **「はず」で合格出さない**: 「commitがあれば存在するはず」は証拠にならない → 必ず実在確認

---

## Pre-flight check 実施タイムライン

```
監査依頼受信
    │
    ▼ C1: パス整合性確認（git ls-files）
    │
    ▼ C2: カウント整合性確認（DB SQL）
    │  ※ カウント記述がなければスキップ
    │
    ▼ C3: 名称ドリフト確認（cmd show + git log照合）
    │
    ▼ C4: テスト存在確認（scripts/botsu/* 修正時のみ）
    │
    ▼ C5: env変数追記確認（新変数導入時のみ）
    │
    ├─ いずれかFAIL → 差し戻し（老中経由）。ルーブリック採点しない
    │
    └─ 全PASS → 18点ルーブリック採点に進む
```

---

*作成: 足軽2(ashigaru2) | cmd_573 S8 | subtask_1214 | 2026-05-02*
