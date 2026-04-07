# お針子 Instructions 改修案：DB CLI 直接書き込み廃止 → YAML Inbox 方式への移行

> **作成日**: 2026-02-08
> **作成者**: ashigaru1
> **目的**: お針子のDB直接書き込みを廃止し、監査結果・先行割当報告をYAML inbox経由で家老に送る

---

## 設計原則

### DB書き込み権限の集約
```
┌─────────────────────────────────────────┐
│ DB書き込み権限は家老のみ               │
│ お針子: DB読み取りのみ                 │
│ 足軽・部屋子: DB権限なし               │
└─────────────────────────────────────────┘
```

- **家老**: 没日録DB（botsunichiroku.db）への読み書き全権
- **お針子**: 没日録DBの読み取りのみ（read系コマンド） + YAML inbox書き込み（監査結果・先行割当報告）
- **足軽・部屋子**: YAML inbox 読み書き（自分のタスク + 報告）、DB権限なし

### お針子の役割変更

| 項目 | 旧仕様（DB直接書き込み） | 新仕様（YAML inbox方式） |
|------|----------------------|----------------------|
| DB読み取り | 全権閲覧（変更なし） | 全権閲覧（変更なし） |
| DB書き込み | report add, subtask update（audit_status） | **廃止** |
| 監査結果報告 | DB直接書き込み | queue/inbox/{karo}_ohariko.yaml に書き込み |
| 先行割当報告 | DB直接書き込み + send-keys | YAML書き込み + send-keys |

---

## 1. 現行 instructions/ohariko.md の DB CLI 直接書き込み箇所一覧

### 1.1 成果物監査ワークフロー（行251-325）

#### 箇所1: audit_status を in_progress に更新（行262-263）
```bash
STEP 2: audit_status を in_progress に更新
  python3 scripts/botsunichiroku.py subtask update subtask_XXX --audit-status in_progress
```

#### 箇所2: 監査結果を report に記録（行283-287）
```bash
STEP 6: 監査結果を報告（reportに記録）
  python3 scripts/botsunichiroku.py report add subtask_XXX ohariko \
    --status done \
    --summary "監査結果: [合格/要修正] - [概要]" \
    --findings '["指摘1", "指摘2"]'
```

#### 箇所3: audit_status を done に更新（行289-290）
```bash
STEP 7: audit_status を done に更新
  python3 scripts/botsunichiroku.py subtask update subtask_XXX --audit-status done
```

#### 箇所4: audit_status = rejected の記述（行302, 308）
```markdown
■ パターン2: 要修正（自明）
  DB: audit_status=rejected, reportのfindingsに理由記載

■ パターン3: 要修正（判断必要）
  DB: audit_status=rejected, reportのfindingsに理由記載
```
※ これらは説明文なので、具体的なコマンド記載なし。書き換え案では「YAML経由で家老がDB更新」と修正する。

### 1.2 先行割当手順（行190-231）

#### 箇所5: 没日録に割当を記録（行203-204）
```markdown
3. タスクYAML（`queue/tasks/ashigaru{N}.yaml`）に割当内容を書き込む
4. 没日録に割当を記録
```
※ 具体的なコマンドは記載されていないが、DB書き込みを示唆している。YAML方式では「家老への報告YAMLに書き込み、家老がDB記録」に変更。

---

## 2. YAML Inbox 方式への書き換え案（Before/After）

### 2.1 新しいファイル構成

#### お針子専用の報告 inbox
```
queue/inbox/
  ├── roju_ohariko.yaml       # 老中へのお針子報告 inbox
  └── ooku_ohariko.yaml       # 御台所へのお針子報告 inbox
```

#### Inbox YAMLフォーマット（お針子監査報告）
```yaml
# queue/inbox/roju_ohariko.yaml
audit_reports:
  - id: audit_report_001
    subtask_id: subtask_294
    timestamp: "2026-02-08T11:30:00"
    result: approved  # approved | rejected_trivial | rejected_judgment
    summary: |
      監査結果: 合格。4観点クリア。品質は及第点よ。
    findings: []
    read: false  # 家老が読んだかフラグ

  - id: audit_report_002
    subtask_id: subtask_296
    timestamp: "2026-02-08T11:40:00"
    result: rejected_trivial
    summary: |
      監査結果: 要修正（自明）。数値不一致（17箇所→15箇所）を検出。
    findings:
      - "194行目: 「17箇所」→「15箇所」に修正が必要"
    read: false

preemptive_assignments:
  - id: preassign_001
    subtask_id: subtask_300
    cmd_id: cmd_128
    worker: ashigaru2
    timestamp: "2026-02-08T12:00:00"
    reason: "idle足軽2名検出、未割当subtaskとの適合を確認"
    read: false
```

### 2.2 各箇所の書き換え案

#### 書き換え1: audit_status を in_progress に更新

**Before**:
```bash
STEP 2: audit_status を in_progress に更新
  python3 scripts/botsunichiroku.py subtask update subtask_XXX --audit-status in_progress
```

**After**:
```bash
STEP 2: 監査開始をYAML報告に記録（省略可）
  # お針子は audit_status を直接更新しない
  # 家老がお針子のYAML報告を読んだ時点で audit_status=in_progress に更新する
  # または、監査完了まで audit_status は pending のまま（簡略版）
```

**説明**: audit_status の in_progress 更新は省略可能。お針子は監査を開始したらすぐに完了まで進むため、中間状態の記録は不要。家老がYAML報告を読んだ時点で結果に応じた status 更新を行う。

---

#### 書き換え2: 監査結果を report に記録

**Before**:
```bash
STEP 6: 監査結果を報告（reportに記録）
  python3 scripts/botsunichiroku.py report add subtask_XXX ohariko \
    --status done \
    --summary "監査結果: [合格/要修正] - [概要]" \
    --findings '["指摘1", "指摘2"]'
```

**After**:
```bash
STEP 6: 監査結果をYAML報告に記録
  # 1. 担当家老の報告inboxパスを決定（subtaskの assigned_by で判定）
  Read queue/inbox/ashigaru{監査対象足軽番号}.yaml
  # → assigned_by: roju なら queue/inbox/roju_ohariko.yaml
  # → assigned_by: ooku なら queue/inbox/ooku_ohariko.yaml

  # 2. お針子報告inboxに監査結果を追記
  Edit queue/inbox/{karo}_ohariko.yaml
  # audit_reports リストの末尾に新規報告を追加:
  # - id: audit_report_XXX  # 既存のaudit_report IDから連番を推測
  #   subtask_id: subtask_XXX
  #   timestamp: "YYYY-MM-DDTHH:MM:SS"  # date "+%Y-%m-%dT%H:%M:%S" で取得
  #   result: approved | rejected_trivial | rejected_judgment
  #   summary: |
  #     監査結果: [合格/要修正（自明）/要修正（要判断）] - [概要]
  #   findings:
  #     - "指摘1"
  #     - "指摘2"
  #   read: false
```

---

#### 書き換え3: audit_status を done に更新

**Before**:
```bash
STEP 7: audit_status を done に更新
  python3 scripts/botsunichiroku.py subtask update subtask_XXX --audit-status done
```

**After**:
```bash
STEP 7: （削除）audit_status は家老が更新する
  # お針子は audit_status を直接更新しない
  # 家老がYAML報告を読んだ時点で以下のように更新:
  #   - result: approved → audit_status=done
  #   - result: rejected_* → audit_status=rejected
```

---

#### 書き換え4: audit_status = rejected の記述

**Before**:
```markdown
■ パターン2: 要修正（自明）
  DB: audit_status=rejected, reportのfindingsに理由記載

■ パターン3: 要修正（判断必要）
  DB: audit_status=rejected, reportのfindingsに理由記載
```

**After**:
```markdown
■ パターン2: 要修正（自明）
  YAML: queue/inbox/{karo}_ohariko.yaml に result=rejected_trivial で記録
  → 家老がYAML読み取り後、DB: audit_status=rejected に更新

■ パターン3: 要修正（判断必要）
  YAML: queue/inbox/{karo}_ohariko.yaml に result=rejected_judgment で記録
  → 家老がYAML読み取り後、DB: audit_status=rejected に更新
```

---

#### 書き換え5: 没日録に割当を記録（先行割当手順）

**Before**:
```markdown
3. タスクYAML（`queue/tasks/ashigaru{N}.yaml`）に割当内容を書き込む
4. 没日録に割当を記録
```

**After**:
```markdown
3. 家老報告inboxに先行割当を記録
   Edit queue/inbox/{karo}_ohariko.yaml
   # preemptive_assignments リストの末尾に追加:
   # - id: preassign_XXX
   #   subtask_id: subtask_YYY
   #   cmd_id: cmd_ZZZ
   #   worker: ashigaru{N}
   #   timestamp: "YYYY-MM-DDTHH:MM:SS"
   #   reason: "idle足軽を検出、未割当subtaskとの適合を確認"
   #   read: false

4. （削除）没日録への直接記録は廃止
   # 家老がYAML報告を読んだ時点で DB: subtask の worker を更新
```

---

## 3. 成果物監査ワークフロー改修版（完全版）

### 改修後のフロー

```
STEP 1: subtask詳細の確認（DB読み取り - 変更なし）
  python3 scripts/botsunichiroku.py subtask show subtask_XXX
  → description, target_path, needs_audit, audit_status, assigned_by を確認

STEP 2: 足軽の報告を確認（DB読み取り - 変更なし）
  python3 scripts/botsunichiroku.py report list --subtask subtask_XXX
  → summary, files_modified を確認

STEP 3: 成果物ファイルを直接読む（Read - 変更なし）
  → report の files_modified から対象ファイルを特定し Read で内容を確認
  → target_path が指定されていればそのディレクトリ配下も確認

STEP 4: 品質チェック（4観点 - 変更なし）
  ┌────────────┬──────────────────────────────────┐
  │ 観点       │ チェック内容                       │
  ├────────────┼──────────────────────────────────┤
  │ 完全性     │ 要求された内容が全て含まれているか   │
  │ 正確性     │ 事実誤認・技術的な間違いがないか     │
  │ 書式       │ フォーマット・命名規則は適切か       │
  │ 一貫性     │ 他のドキュメント・コードとの整合性   │
  └────────────┴──────────────────────────────────┘

STEP 5: 担当家老のお針子報告inboxパスを決定
  # subtaskの assigned_by で判定（STEP 1で確認済み）
  # assigned_by: roju → queue/inbox/roju_ohariko.yaml
  # assigned_by: ooku → queue/inbox/ooku_ohariko.yaml

STEP 6: 監査結果をYAML報告に記録（★ 改修箇所）
  Edit queue/inbox/{karo}_ohariko.yaml
  # audit_reports リストの末尾に新規報告を追加:
  # - id: audit_report_XXX  # 既存IDから連番推測
  #   subtask_id: subtask_XXX
  #   timestamp: "2026-02-08T11:30:00"  # date "+%Y-%m-%dT%H:%M:%S" で取得
  #   result: approved | rejected_trivial | rejected_judgment
  #   summary: |
  #     監査結果: [合格/要修正（自明）/要修正（要判断）] - [概要]
  #   findings:
  #     - "指摘1"
  #     - "指摘2"
  #   read: false

STEP 7: 担当家老に監査結果を報告（send-keys通知）
  → assigned_byで通知先を決定（roju=multiagent:agents.0, ooku=ooku:agents.0）

  ■ パターン1: 合格
    【1回目】tmux send-keys -t {家老ペイン} 'お針子より監査報告。subtask_XXX: 合格。報告YAMLを確認くだされ。'
    【2回目】tmux send-keys -t {家老ペイン} Enter
    → 家老がYAML読み取り → DB: audit_status=done に更新 → 戦果移動・次タスク進行

  ■ パターン2: 要修正（自明）
    【1回目】tmux send-keys -t {家老ペイン} 'お針子より監査報告。subtask_XXX: 要修正（自明）。報告YAMLを確認くだされ。'
    【2回目】tmux send-keys -t {家老ペイン} Enter
    → 家老がYAML読み取り → DB: audit_status=rejected に更新 → 足軽/部屋子に差し戻し修正指示

  ■ パターン3: 要修正（判断必要）
    【1回目】tmux send-keys -t {家老ペイン} 'お針子より監査報告。subtask_XXX: 要修正（要判断）。報告YAMLを確認くだされ。'
    【2回目】tmux send-keys -t {家老ペイン} Enter
    → 家老がYAML読み取り → DB: audit_status=rejected に更新 → dashboard.md「要対応」に記載 → 殿が判断

STEP 8: 次の監査待ち（pending）があるか確認し、あれば連続処理（変更なし）
  python3 scripts/botsunichiroku.py subtask list --json | python3 -c "
  import json, sys
  data = json.load(sys.stdin)
  pending = [s for s in data if s.get('audit_status') == 'pending']
  if pending:
      print(f'NEXT:{pending[0][\"id\"]}')
  else:
      print('EMPTY')
  "
  → NEXT:subtask_YYY の場合: STEP 1 に戻り subtask_YYY の監査を開始
  → EMPTY の場合: 全監査完了。処理を終了しプロンプト待ちになる
```

### 変更点サマリ

| STEP | 旧仕様 | 新仕様 |
|------|--------|--------|
| STEP 1-4 | DB読み取り、ファイル読み取り | 変更なし |
| STEP 5 | （なし） | 担当家老のお針子報告inboxパスを決定 |
| STEP 6 | `python3 scripts/botsunichiroku.py report add ...` | `Edit queue/inbox/{karo}_ohariko.yaml` |
| STEP 7 | send-keys 通知 | send-keys 通知（メッセージを「報告YAMLを確認」に変更） |
| STEP 8 | 変更なし | 変更なし |

---

## 4. 先行割当手順改修版（完全版）

### 改修後のフロー

```
STEP 1: 没日録で idle 足軽/部屋子を特定（DB読み取り - 変更なし）
  python3 scripts/botsunichiroku.py subtask list --status assigned
  # 全足軽の割当状況を確認し、割当なし = idle を特定

STEP 2: 未割当 subtask を特定（DB読み取り - 変更なし）
  python3 scripts/botsunichiroku.py subtask list --status unassigned

STEP 3: 適切なマッチングを判定（変更なし）
  # 足軽1-4: 定型・中程度タスク
  # 足軽5: 高難度タスク
  # 部屋子1-3: 調査・分析タスク

STEP 4: 家老報告inboxに先行割当を記録（★ 改修箇所）
  # 該当subtaskの assigned_by で報告先家老を決定
  Edit queue/inbox/{karo}_ohariko.yaml
  # preemptive_assignments リストの末尾に追加:
  # - id: preassign_XXX  # 既存IDから連番推測
  #   subtask_id: subtask_YYY
  #   cmd_id: cmd_ZZZ
  #   worker: ashigaru{N}
  #   timestamp: "YYYY-MM-DDTHH:MM:SS"  # date "+%Y-%m-%dT%H:%M:%S" で取得
  #   reason: "idle足軽を検出、未割当subtaskとの適合を確認"
  #   read: false

STEP 5: 対象足軽/部屋子に send-keys で起こす（変更なし）
  # 【1回目】YAML参照を指示するメッセージを送る
  tmux send-keys -t {ペイン} 'subtask_YYYの任務がございます。python3 scripts/botsunichiroku.py subtask show subtask_YYY で確認くだされ。'
  # 【2回目】Enterを送る
  tmux send-keys -t {ペイン} Enter

STEP 6: 担当家老に報告（send-keys 通知）
  # assigned_by に基づき通知先を決定（roju=multiagent:agents.0, ooku=ooku:agents.0）
  # 【1回目】
  tmux send-keys -t {家老ペイン} 'お針子より報告。subtask_YYYをashigaru{N}に先行割当。報告YAMLを確認くだされ。'
  # 【2回目】
  tmux send-keys -t {家老ペイン} Enter
  # → 家老がYAML読み取り → DB: subtask の worker を更新
```

### 変更点サマリ

| STEP | 旧仕様 | 新仕様 |
|------|--------|--------|
| STEP 1-3 | DB読み取り、判定 | 変更なし |
| STEP 4 | 「没日録に割当を記録」（DB直接書き込み） | `Edit queue/inbox/{karo}_ohariko.yaml` |
| STEP 5 | send-keys で足軽起動 | 変更なし |
| STEP 6 | send-keys で家老報告 | send-keys（メッセージを「報告YAMLを確認」に変更） |

---

## 5. お針子が使わなくなるコマンド一覧

### 5.1 完全廃止コマンド

以下のコマンドは、YAML Inbox方式への移行後、お針子は**一切使用しない**。

| コマンド | 用途 | 代替手段 |
|---------|------|---------|
| `python3 scripts/botsunichiroku.py subtask update --audit-status` | audit_status 更新 | `Edit queue/inbox/{karo}_ohariko.yaml` → 家老がDB更新 |
| `python3 scripts/botsunichiroku.py report add ... ohariko` | 監査結果記録 | `Edit queue/inbox/{karo}_ohariko.yaml` |

### 5.2 読み取り専用で継続使用するコマンド

以下のコマンドは、DB読み取り専用なので引き続き使用可能。

| コマンド | 用途 | 変更 |
|---------|------|------|
| `python3 scripts/botsunichiroku.py cmd list` | cmd一覧取得 | 変更なし（読み取りのみ） |
| `python3 scripts/botsunichiroku.py subtask list` | subtask一覧取得 | 変更なし（読み取りのみ） |
| `python3 scripts/botsunichiroku.py subtask show` | subtask詳細確認 | 変更なし（読み取りのみ） |
| `python3 scripts/botsunichiroku.py report list` | report一覧取得 | 変更なし（読み取りのみ） |
| `python3 scripts/botsunichiroku.py agent list` | agent状態確認 | 変更なし（読み取りのみ） |

---

## 6. お針子ユーザー観点での検証

### 6.1 主要業務フローの完結性チェック

#### ✅ 成果物監査（合格の場合）

1. **subtask詳細確認**: `python3 scripts/botsunichiroku.py subtask show subtask_XXX`
2. **報告確認**: `python3 scripts/botsunichiroku.py report list --subtask subtask_XXX`
3. **成果物読み取り**: `Read` で対象ファイル確認
4. **品質チェック**: 4観点で評価
5. **監査結果記録**: `Edit queue/inbox/{karo}_ohariko.yaml` → result: approved
6. **家老通知**: send-keys（「報告YAMLを確認くだされ」）

**結論**: DB読み取り + Read + Edit + send-keys で完結。DB書き込み不要。✅

---

#### ✅ 成果物監査（要修正の場合）

1. **subtask詳細確認**: `python3 scripts/botsunichiroku.py subtask show subtask_XXX`
2. **報告確認**: `python3 scripts/botsunichiroku.py report list --subtask subtask_XXX`
3. **成果物読み取り**: `Read` で対象ファイル確認
4. **品質チェック**: 4観点で評価 → 指摘事項を発見
5. **監査結果記録**: `Edit queue/inbox/{karo}_ohariko.yaml` → result: rejected_trivial, findings: ["指摘内容"]
6. **家老通知**: send-keys（「報告YAMLを確認くだされ」）

**結論**: DB読み取り + Read + Edit + send-keys で完結。DB書き込み不要。✅

---

#### ✅ 先行割当（idle足軽 + 未割当subtask）

1. **idle足軽検出**: `python3 scripts/botsunichiroku.py subtask list --status assigned` → 割当なし = idle
2. **未割当subtask検出**: `python3 scripts/botsunichiroku.py subtask list --status unassigned`
3. **マッチング判定**: 足軽の特性とタスク内容を照合
4. **先行割当記録**: `Edit queue/inbox/{karo}_ohariko.yaml` → preemptive_assignments に追記
5. **足軽起動**: send-keys で対象足軽を起こす
6. **家老通知**: send-keys（「報告YAMLを確認くだされ」）

**結論**: DB読み取り + Edit + send-keys で完結。DB書き込み不要。✅

---

### 6.2 エッジケースの検証

#### ケース1: 複数subtaskの監査が連続する場合

**シナリオ**: audit_status=pending のsubtaskが3件ある

**対応**:
1. 1件目の監査完了 → YAML書き込み → send-keys 通知
2. 次のpending検索 → 2件目の監査開始
3. 2件目完了 → YAML書き込み → send-keys 通知
4. 次のpending検索 → 3件目の監査開始
5. 3件目完了 → YAML書き込み → send-keys 通知

**結論**: 各監査ごとに `Edit queue/inbox/{karo}_ohariko.yaml` で audit_reports に追記。DB書き込み不要。✅

---

#### ケース2: 異なる家老配下のsubtaskが混在する場合

**シナリオ**: assigned_by: roju と assigned_by: ooku のsubtaskが両方ある

**対応**:
1. roju配下のsubtask監査 → `Edit queue/inbox/roju_ohariko.yaml` → send-keys to multiagent:agents.0
2. ooku配下のsubtask監査 → `Edit queue/inbox/ooku_ohariko.yaml` → send-keys to ooku:agents.0

**結論**: assigned_by に応じた報告inboxを使い分けるだけ。DB書き込み不要。✅

---

### 6.3 総合結論

**お針子は DB CLI 直接書き込みを廃止し、全業務を完結できる。**

- DB読み取り: `python3 scripts/botsunichiroku.py` の読み取り系コマンド（変更なし）
- 監査結果報告: `Edit queue/inbox/{karo}_ohariko.yaml`
- 先行割当報告: `Edit queue/inbox/{karo}_ohariko.yaml`
- 家老通知: send-keys（「報告YAMLを確認」）

**メリット**:
1. **DB書き込み権限の集約**: 家老のみがDB書き込み可能 → データ整合性向上
2. **権限分離の明確化**: お針子は監査・予測・先行割当のみ、DB管理は家老
3. **トレーサビリティ**: YAML報告が残るため、お針子の判断経緯が追跡可能
4. **エラー回避**: DB CLI実行エラー（パス間違い、引数ミス等）が発生しない

**デメリット**:
1. **家老の負荷増**: YAML報告を読み取り、DBに転記する作業が発生
2. **YAMLフォーマット厳守**: お針子がYAML構文ミスをするとエラー

**推奨**: DB書き込み権限の集約による安全性向上が大きい。YAML方式への移行を推奨する。

---

## 7. 補足: お針子のYAML報告フォーマット詳細

### 7.1 監査報告（audit_reports）

#### result フィールドの種類

| result 値 | 意味 | 家老の対応 |
|----------|------|----------|
| approved | 合格 | audit_status=done, 戦果移動・次タスク進行 |
| rejected_trivial | 要修正（自明） | audit_status=rejected, 足軽/部屋子に差し戻し |
| rejected_judgment | 要修正（判断必要） | audit_status=rejected, dashboard.md「要対応」に記載 |

#### findings フィールドの使い方

- **approved の場合**: findings: [] （空リスト）
- **rejected_* の場合**: findings: ["指摘1", "指摘2", ...] （具体的な指摘事項を列挙）

### 7.2 先行割当報告（preemptive_assignments）

#### reason フィールドの記載内容

- 先行割当の理由を簡潔に記載
- 例: "idle足軽2名検出、未割当subtaskとの適合を確認"
- 例: "滞留cmd_XXXの未割当subtask、足軽5の高難度タスク適性あり"

---

**以上、お針子 instructions 改修案でござる。**
