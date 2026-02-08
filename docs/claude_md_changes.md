# CLAUDE.md 改修案: 通信プロトコルv2対応

> **作成日**: 2026-02-08
> **対象**: CLAUDE.md
> **目的**: 通信プロトコルv2（第1層=YAML inbox方式、第2層=DB永続）への移行案

---

## (1) 通信プロトコルセクションの全面改修案

### 現行版（169-205行）

```markdown
## 通信プロトコル

### イベント駆動通信（YAML + send-keys）
- ポーリング禁止（API代金節約のため）
- 指示・報告内容はYAMLファイルに書く
- 通知は tmux send-keys で相手を起こす（必ず Enter を使用、C-m 禁止）
- **send-keys は必ず2回のBash呼び出しに分けよ**（1回で書くとEnterが正しく解釈されない）：
  ```bash
  # 【1回目】メッセージを送る（老中の例）
  tmux send-keys -t multiagent:agents.0 'メッセージ内容'
  # 【2回目】Enterを送る
  tmux send-keys -t multiagent:agents.0 Enter
  ```
- **ペイン対応表（3セッション構成）**:
  - **multiagentセッション**: 老中=`multiagent:agents.0`, 足軽N=`multiagent:agents.{N}`（足軽1=agents.1, ..., 足軽5=agents.5）
  - **ookuセッション**: 御台所=`ooku:agents.0`, 部屋子N=`ooku:agents.{N}`（部屋子1=ooku:agents.1, 部屋子2=ooku:agents.2, 部屋子3=ooku:agents.3）, お針子=`ooku:agents.4`

### 報告の流れ（割り込み防止設計）
- **足軽→家老**: 報告YAML記入 + send-keys で家老を起こす（**必須**）
- **部屋子→御台所**: 報告YAML記入 + send-keys で御台所を起こす（**必須**）
- **家老→将軍/殿**: dashboard.md 更新のみ（send-keys **禁止**）
- **家老→お針子**: 監査依頼のみ（needs_audit=1のsubtask完了時、send-keys で起こす）
- **お針子→家老**: send-keys（監査結果・先行割当通知。通知先はsubtaskのassigned_byで判定）
- **上→下への指示**: YAML + send-keys で起こす
- 理由: 殿（人間）の入力中に割り込みが発生するのを防ぐ。足軽→家老は同じtmuxセッション内のため割り込みリスクなし
```

**問題点**:
- 「指示・報告内容はYAMLファイルに書く」と記載されているが、実際には没日録DB（SQLite）に直接書き込む方式に移行済み
- 「報告YAML記入」の記述が現状と矛盾（実際は `python3 scripts/botsunichiroku.py report add` でDB書き込み）
- YAML通信の具体的なファイルパス（inbox/outbox）が記載されていない

---

### 改修案（通信プロトコルv2対応）

```markdown
## 通信プロトコル

### 二層通信モデル

shogunシステムは、**第1層（YAML通信）** と **第2層（DB永続化）** の二層モデルで通信を管理する：

```
第1層: YAML通信（inbox/outbox方式）
  └─ 進行中タスク・報告の一時ストレージ
  └─ 人間が読みやすい（デバッグ容易）
  └─ Git管理可能

第2層: DB永続化（没日録DB）
  └─ 完了済みタスク・報告の永続ストレージ
  └─ 検索・集計が容易（SQLクエリ）
  └─ 家老がアーカイブを管理
```

---

### イベント駆動通信（YAML inbox/outbox + send-keys）

#### 基本原則

- **ポーリング禁止**（API代金節約のため）
- **指示・報告内容はYAMLファイル（inbox/outbox）に書く**
- **通知は tmux send-keys で相手を起こす**（必ず Enter を使用、C-m 禁止）
- **send-keys は必ず2回のBash呼び出しに分けよ**（1回で書くとEnterが正しく解釈されない）：
  ```bash
  # 【1回目】メッセージを送る（老中の例）
  tmux send-keys -t multiagent:agents.0 'メッセージ内容'
  # 【2回目】Enterを送る
  tmux send-keys -t multiagent:agents.0 Enter
  ```

#### ペイン対応表（3セッション構成）

- **multiagentセッション**: 老中=`multiagent:agents.0`, 足軽N=`multiagent:agents.{N}`（足軽1=agents.1, ..., 足軽5=agents.5）
- **ookuセッション**: 御台所=`ooku:agents.0`, 部屋子N=`ooku:agents.{N}`（部屋子1=ooku:agents.1, 部屋子2=ooku:agents.2, 部屋子3=ooku:agents.3）, お針子=`ooku:agents.4`

---

### YAML inbox/outbox ファイル構成

#### inbox（タスク割当）

家老が足軽/部屋子にタスクを割り当てる際に使用：

```
queue/inbox/ashigaru1.yaml       # 足軽1への指示キュー
queue/inbox/ashigaru2.yaml       # 足軽2への指示キュー
...
queue/inbox/ashigaru8.yaml       # 部屋子3（ashigaru8）への指示キュー
queue/inbox/ohariko.yaml         # お針子への監査依頼キュー
```

**inbox YAMLフォーマット例**:

```yaml
- subtask_id: subtask_295
  cmd_id: cmd_127
  worker: ashigaru2
  status: assigned  # assigned / in_progress / done
  description: "【家老instructions+CLAUDE.md改修案】..."
  project: shogun
  target_path: /home/yasu/multi-agent-shogun
  wave: 1
  needs_audit: true
  assigned_at: 2026-02-08T10:59:49
```

#### outbox（報告）

足軽/部屋子/お針子が家老に報告する際に使用：

```
queue/outbox/ashigaru1_report.yaml   # 足軽1からの報告キュー
queue/outbox/ashigaru2_report.yaml   # 足軽2からの報告キュー
...
queue/outbox/ashigaru8_report.yaml   # 部屋子3からの報告キュー
queue/outbox/ohariko_report.yaml     # お針子からの報告キュー
```

**outbox YAMLフォーマット例**:

```yaml
- report_id: report_001
  subtask_id: subtask_295
  worker: ashigaru2
  status: done  # done / failed / blocked
  summary: "タスク完了。2ファイル作成。"
  skill_name: ""
  skill_desc: ""
  reported_at: 2026-02-08T12:30:00
```

---

### 通信フロー: 家老 → 足軽（タスク割当）

```
家老がタスク分解
  │
  ▼ queue/inbox/ashigaru2.yaml にタスク書き込み（YAML append）
  │   status: assigned
  │   subtask_id: subtask_295
  │   description: "..."
  │
  ▼ tmux send-keys で足軽2を起こす（2回に分ける）
  │   【1回目】tmux send-keys -t multiagent:agents.2 'queue/inbox/ashigaru2.yaml を確認し、status: assigned のタスクを実行せよ。'
  │   【2回目】tmux send-keys -t multiagent:agents.2 Enter
  │
  ▼ 足軽2が queue/inbox/ashigaru2.yaml を読み込み
  │   - status: assigned のエントリを探す
  │   - 自分のworkerフィールドが ashigaru2 か確認
  │
  ▼ タスク開始時、inbox YAML の status を in_progress に更新
  │
  ▼ 作業実行
```

---

### 通信フロー: 足軽 → 家老（報告）

```
足軽2がタスク完了
  │
  ▼ queue/outbox/ashigaru2_report.yaml に報告書き込み（YAML append）
  │   report_id: report_001
  │   subtask_id: subtask_295
  │   worker: ashigaru2
  │   status: done
  │   summary: "タスク完了。..."
  │   reported_at: 2026-02-08T12:30:00
  │
  ▼ tmux send-keys で家老を起こす（2回に分ける）
  │   assigned_by フィールドで報告先家老を判定:
  │   - assigned_by: roju → multiagent:agents.0（老中）
  │   - assigned_by: ooku → ooku:agents.0（御台所）
  │   - 未指定 → multiagent:agents.0（デフォルト: 老中）
  │
  │   【1回目】tmux send-keys -t multiagent:agents.0 'ashigaru2、任務完了でござる。outbox を確認されよ。'
  │   【2回目】tmux send-keys -t multiagent:agents.0 Enter
  │
  ▼ 家老が queue/outbox/*.yaml を全スキャン
  │   - ashigaru1_report.yaml, ashigaru2_report.yaml, ..., ashigaru8_report.yaml, ohariko_report.yaml
  │   - 各YAMLから未処理の報告（inbox側の status: in_progress）を探す
  │
  ▼ 家老が inbox YAML の該当 subtask の status を done に更新
  │
  ▼ 家老が dashboard.md を更新（戦果セクション）
  │
  ▼ 【アーカイブ】家老が完了タスクを没日録DBに永続化
  │   python3 scripts/botsunichiroku.py subtask archive subtask_295
  │   python3 scripts/botsunichiroku.py report archive report_001
  │   → DBに INSERT
  │   → inbox/outbox YAML から削除
```

---

### 通信フロー: 家老 → お針子（監査依頼）

```
家老が足軽からの完了報告を受信
  │
  ▼ inbox YAML の該当 subtask の needs_audit を確認
  │
  ▼ needs_audit: true なら、queue/inbox/ohariko.yaml に監査依頼書き込み
  │   audit_id: audit_001
  │   subtask_id: subtask_295
  │   status: pending  # pending / in_progress / done
  │   requested_at: 2026-02-08T12:30:00
  │
  ▼ お針子が空いているか確認
  │   queue/inbox/ohariko.yaml を読み込み
  │   → status: in_progress のエントリがないか確認
  │
  ▼ IDLE の場合のみ send-keys でお針子を起こす
  │   【1回目】tmux send-keys -t ooku:agents.4 'inbox を確認し、status: pending の監査依頼を実行せよ。'
  │   【2回目】tmux send-keys -t ooku:agents.4 Enter
  │
  ▼ お針子が queue/inbox/ohariko.yaml を読み込み、status: pending を探す
  │   → 該当エントリの status を in_progress に更新
  │
  ▼ お針子が対象 subtask の inbox YAML を読み込み、監査実施
  │
  ▼ 監査完了後、queue/outbox/ohariko_report.yaml に結果書き込み
  │   audit_id: audit_001
  │   subtask_id: subtask_295
  │   status: done  # done / rejected
  │   findings: "合格 / 要修正（自明）: typo / 要修正（判断必要）: 仕様"
  │   reported_at: 2026-02-08T12:45:00
  │
  ▼ send-keys で家老を起こす
  │   通知先はsubtaskのassigned_byで判定（roju=multiagent:agents.0, ooku=ooku:agents.0）
  │
  ▼ 家老が queue/outbox/ohariko_report.yaml を読み込み、次処理へ
  │   - 合格 → 通常の完了処理
  │   - 要修正（自明）→ 足軽に修正タスク再割当
  │   - 要修正（判断必要）→ dashboard.md「要対応」に記載
  │
  ▼ 【アーカイブ】家老が完了監査を没日録DBに永続化
  │   queue/inbox/ohariko.yaml の該当エントリを削除
  │   queue/outbox/ohariko_report.yaml の該当エントリを削除
```

---

### 報告の流れ（割り込み防止設計）

- **足軽→家老**: outbox YAML記入 + send-keys で家老を起こす（**必須**）
- **部屋子→御台所**: outbox YAML記入 + send-keys で御台所を起こす（**必須**）
- **家老→将軍/殿**: dashboard.md 更新のみ（send-keys **禁止**）
- **家老→お針子**: inbox YAML記入 + send-keys で起こす（監査依頼のみ）
- **お針子→家老**: outbox YAML記入 + send-keys（監査結果・先行割当通知。通知先はsubtaskのassigned_byで判定）
- **上→下への指示**: inbox YAML記入 + send-keys で起こす
- 理由: 殿（人間）の入力中に割り込みが発生するのを防ぐ。足軽→家老は同じtmuxセッション内のため割り込みリスクなし

---

### お針子の通信経路（v2）

- お針子→家老: outbox YAML記入 + send-keys（監査結果通知・先行割当通知）
  - 通知先はsubtaskのassigned_byで判定（roju=multiagent:agents.0, midaidokoro=ooku:agents.0）
- お針子→将軍: send-keys **禁止**（dashboard.md経由。家老と同じ方式）
- お針子→足軽/部屋子: inbox YAML記入 + send-keys（先行割当のみ）
- お針子の制約: 新規cmd作成不可、既存cmdの未割当subtask割当のみ
- 監査結果の3パターン分岐:
  - [合格] → 家老に通知 → 家老が進行中→戦果に移動
  - [要修正(自明)] → 家老に通知 → 家老が差し戻し
  - [要修正(判断必要)] → 家老に通知 → 家老がdashboard要対応記載 → 殿判断

---

### 通信ロスト対策（未処理報告スキャン）

家老は起こされた際、必ず全 outbox YAML をスキャンせよ：

```bash
# 全outbox YAMLをスキャン
for file in queue/outbox/*.yaml; do
  # 各YAMLから未処理の報告を抽出
  # （inbox側の status: in_progress のsubtaskに対応する報告）
  cat "$file"
done
```

**なぜ全スキャンが必要か**:
- 足軽が報告をoutbox YAMLに書き込んだ後、send-keys が届かないことがある
- 家老が処理中だと、Enter がパーミッション確認等に消費される
- 報告YAML自体は正しく書き込まれているので、スキャンすれば発見できる
```

---

### 改修案の検証結果（家老観点）

| 観点 | 現行（DB直接） | 改修案（YAML inbox/outbox） | 判定 |
|------|---------------|---------------------------|------|
| **実装コスト** | 低 | 高（YAML読み書き+アーカイブ処理） | ❌ 改修案は実装コストが大幅に増加 |
| **運用負担** | 低 | 高（YAML + DB の二重管理） | ❌ 改修案は運用負担が大幅に増加 |
| **デバッグ容易性** | 中 | 高（YAMLを cat で読める） | ✅ 改修案が優位 |
| **並行安全性** | 高 | 中（ファイル競合リスク） | ⚠️ 改修案は排他制御が必要 |
| **通信ロスト対策** | 高 | 中（全outbox YAMLスキャン必要） | ⚠️ 改修案は効率が劣る |
| **スキャン効率** | 高 | 低（8ファイル個別読み込み） | ❌ 改修案は効率が劣る |

**総合判定**: ❌ **改修案は実装・運用コストが高く、効率で劣る**

---

## (2) /clear復帰フロー改修案

### 現行版（57-101行）

```markdown
## /clear後の復帰手順（足軽専用）

/clear を受けた足軽は、以下の手順で最小コストで復帰せよ。
この手順は CLAUDE.md（自動読み込み）のみで完結する。instructions/ashigaru.md は初回復帰時には読まなくてよい（2タスク目以降で必要なら読む）。

> **セッション開始・コンパクション復帰との違い**:
> - **セッション開始**: 白紙状態。Memory MCP + instructions + YAML を全て読む（フルロード）
> - **コンパクション復帰**: summaryが残っている。正データから再確認
> - **/clear後**: 白紙状態だが、最小限の読み込みで復帰可能（ライトロード）

### /clear後の復帰フロー（~5,000トークンで復帰）

```
/clear実行
  │
  ▼ CLAUDE.md 自動読み込み（本セクションを認識）
  │
  ▼ Step 1: 自分のIDを確認
  │   tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'
  │   → 出力例: ashigaru3 → 自分は足軽3（数字部分が番号）
  │
  ▼ Step 2: Memory MCP 読み込み（~700トークン）
  │   ToolSearch("select:mcp__memory__read_graph")
  │   mcp__memory__read_graph()
  │   → 殿の好み・ルール・教訓を復元
  │   ※ 失敗時もStep 3以降を続行せよ（タスク実行は可能。殿の好みは一時的に不明になるのみ）
  │
  ▼ Step 3: 自分の割当タスク確認（~800トークン）
  │   python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned
  │   → 割当があれば: python3 scripts/botsunichiroku.py subtask show SUBTASK_ID で詳細確認
  │   → 割当なしなら: 次の指示を待つ
  │   → assigned_by フィールドで報告先家老を確認（roju=multiagent:agents.0, ooku=ooku:agents.0）
  │
  ▼ Step 4: プロジェクト固有コンテキストの読み込み（条件必須）
  │   タスクYAMLに project フィールドがある場合 → context/{project}.md を必ず読む
  │   タスクYAMLに target_path がある場合 → 対象ファイルを読む
  │   ※ projectフィールドがなければスキップ可
  │
  ▼ 作業開始
```

### /clear復帰の禁止事項
- instructions/ashigaru.md を読む必要はない（コスト節約。2タスク目以降で必要なら読む）
- ポーリング禁止（F004）、人間への直接連絡禁止（F002）は引き続き有効
- /clear前のタスクの記憶は消えている。タスクYAMLだけを信頼せよ
```

**問題点**:
- Step 3 で「python3 scripts/botsunichiroku.py subtask list」と記載されているが、通信プロトコルv2では inbox YAML から読み込む方式に変更
- Step 4 で「タスクYAML」と記載されているが、実際には inbox YAML を指す（用語の統一が必要）

---

### 改修案（通信プロトコルv2対応）

```markdown
## /clear後の復帰手順（足軽専用）

/clear を受けた足軽は、以下の手順で最小コストで復帰せよ。
この手順は CLAUDE.md（自動読み込み）のみで完結する。instructions/ashigaru.md は初回復帰時には読まなくてよい（2タスク目以降で必要なら読む）。

> **セッション開始・コンパクション復帰との違い**:
> - **セッション開始**: 白紙状態。Memory MCP + instructions + inbox YAML を全て読む（フルロード）
> - **コンパクション復帰**: summaryが残っている。正データから再確認
> - **/clear後**: 白紙状態だが、最小限の読み込みで復帰可能（ライトロード）

### /clear後の復帰フロー（~5,000トークンで復帰）

```
/clear実行
  │
  ▼ CLAUDE.md 自動読み込み（本セクションを認識）
  │
  ▼ Step 1: 自分のIDを確認
  │   tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'
  │   → 出力例: ashigaru3 → 自分は足軽3（数字部分が番号）
  │
  ▼ Step 2: Memory MCP 読み込み（~700トークン）
  │   ToolSearch("select:mcp__memory__read_graph")
  │   mcp__memory__read_graph()
  │   → 殿の好み・ルール・教訓を復元
  │   ※ 失敗時もStep 3以降を続行せよ（タスク実行は可能。殿の好みは一時的に不明になるのみ）
  │
  ▼ Step 3: 自分の割当タスク確認（~800トークン）
  │   【変更点】inbox YAML から読み込み
  │   cat queue/inbox/ashigaru{N}.yaml
  │   → status: assigned のエントリを探す
  │   → 自分の worker フィールドが ashigaru{N} か確認
  │   → 割当があれば: 該当エントリの subtask_id, description, project, target_path を確認
  │   → 割当なしなら: 次の指示を待つ
  │   → assigned_by フィールドで報告先家老を確認（roju=multiagent:agents.0, ooku=ooku:agents.0）
  │
  ▼ Step 4: プロジェクト固有コンテキストの読み込み（条件必須）
  │   inbox YAMLの該当エントリに project フィールドがある場合 → context/{project}.md を必ず読む
  │   inbox YAMLの該当エントリに target_path がある場合 → 対象ファイルを読む
  │   ※ projectフィールドがなければスキップ可
  │
  ▼ 作業開始
```

### /clear復帰の禁止事項
- instructions/ashigaru.md を読む必要はない（コスト節約。2タスク目以降で必要なら読む）
- ポーリング禁止（F004）、人間への直接連絡禁止（F002）は引き続き有効
- /clear前のタスクの記憶は消えている。inbox YAML だけを信頼せよ
```

---

### 改修箇所の差分

| 項目 | 現行 | 改修案 |
|------|------|--------|
| **Step 3: タスク確認** | `python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned` | `cat queue/inbox/ashigaru{N}.yaml` + status: assigned のエントリを探す |
| **Step 4: 用語** | 「タスクYAMLに project フィールド」 | 「inbox YAMLの該当エントリに project フィールド」 |
| **禁止事項の用語** | 「タスクYAMLだけを信頼せよ」 | 「inbox YAML だけを信頼せよ」 |

---

## (3) コンテキスト保持の四層モデルの更新案

### 現行版（103-134行）

```markdown
## コンテキスト保持の四層モデル

```
Layer 1: Memory MCP（永続・セッション跨ぎ）
  └─ 殿の好み・ルール、プロジェクト横断知見
  └─ 保存条件: ①gitに書けない/未反映 ②毎回必要 ③非冗長

Layer 2: Project（永続・プロジェクト固有）
  └─ config/projects.yaml: プロジェクト一覧・ステータス（軽量、頻繁に参照）
  └─ projects/<id>.yaml: プロジェクト詳細（重量、必要時のみ。Git管理外・機密情報含む）
  └─ context/{project}.md: PJ固有の技術知見・注意事項（足軽が参照する要約情報）

Layer 3: 没日録DB（永続・SQLite）
  └─ data/botsunichiroku.db — cmd, subtask, report の正データ源
  └─ CLI: python3 scripts/botsunichiroku.py

Layer 4: Session（揮発・コンテキスト内）
  └─ CLAUDE.md（自動読み込み）, instructions/*.md
  └─ /clearで全消失、コンパクションでsummary化
```

### 各レイヤーの参照者

| レイヤー | 将軍 | 家老 | 足軽/部屋子 | お針子 |
|---------|------|------|------------|--------|
| Layer 1: Memory MCP | read_graph | read_graph | read_graph（セッション開始時・/clear復帰時） | read_graph |
| Layer 2: config/projects.yaml | プロジェクト一覧確認 | タスク割当時に参照 | 参照しない | 参照しない |
| Layer 2: projects/<id>.yaml | プロジェクト全体像把握 | タスク分解時に参照 | 参照しない | 参照しない |
| Layer 2: context/{project}.md | 参照しない | 参照しない | タスクにproject指定時に読む | 参照しない |
| Layer 3: 没日録DB | cmd/subtask参照 | cmd/subtask/report全権 | 自分の割当subtaskのみ | **全権閲覧** |
| Layer 3: 没日録DB | 参照可 | 参照可 | 参照しない | **全権閲覧** |
| Layer 4: Session | instructions/shogun.md | instructions/karo.md | instructions/ashigaru.md | instructions/ohariko.md |
```

**問題点**:
- Layer 3（没日録DB）が「正データ源」と記載されているが、通信プロトコルv2では進行中タスクは inbox/outbox YAML で管理される
- Layer 4 に inbox/outbox YAML の記載がない

---

### 改修案（通信プロトコルv2対応）

```markdown
## コンテキスト保持の四層モデル（通信プロトコルv2）

```
Layer 1: Memory MCP（永続・セッション跨ぎ）
  └─ 殿の好み・ルール、プロジェクト横断知見
  └─ 保存条件: ①gitに書けない/未反映 ②毎回必要 ③非冗長

Layer 2: Project（永続・プロジェクト固有）
  └─ config/projects.yaml: プロジェクト一覧・ステータス（軽量、頻繁に参照）
  └─ projects/<id>.yaml: プロジェクト詳細（重量、必要時のみ。Git管理外・機密情報含む）
  └─ context/{project}.md: PJ固有の技術知見・注意事項（足軽が参照する要約情報）

Layer 3a: YAML通信（揮発・進行中タスク）
  └─ queue/inbox/*.yaml: タスク割当キュー（家老→足軽/部屋子/お針子）
  └─ queue/outbox/*_report.yaml: 報告キュー（足軽/部屋子/お針子→家老）
  └─ queue/shogun_to_karo.yaml: 将軍→家老の指示キュー
  └─ 進行中タスクのみ保持、完了後はLayer 3bにアーカイブされる

Layer 3b: 没日録DB（永続・完了済みタスク）
  └─ data/botsunichiroku.db — 完了済みcmd, subtask, report の永続ストレージ
  └─ CLI: python3 scripts/botsunichiroku.py
  └─ 家老がLayer 3aから手動でアーカイブ

Layer 4: Session（揮発・コンテキスト内）
  └─ CLAUDE.md（自動読み込み）, instructions/*.md
  └─ /clearで全消失、コンパクションでsummary化
```

**重要**: 通信プロトコルv2では、**進行中タスクはLayer 3a（YAML通信）**、**完了済みタスクはLayer 3b（没日録DB）** で管理される二層構造となる。

### 各レイヤーの参照者（通信プロトコルv2）

| レイヤー | 将軍 | 家老 | 足軽/部屋子 | お針子 |
|---------|------|------|------------|--------|
| Layer 1: Memory MCP | read_graph | read_graph | read_graph（セッション開始時・/clear復帰時） | read_graph |
| Layer 2: config/projects.yaml | プロジェクト一覧確認 | タスク割当時に参照 | 参照しない | 参照しない |
| Layer 2: projects/<id>.yaml | プロジェクト全体像把握 | タスク分解時に参照 | 参照しない | 参照しない |
| Layer 2: context/{project}.md | 参照しない | 参照しない | inbox YAMLのproject指定時に読む | 参照しない |
| **Layer 3a: inbox YAML** | 参照可 | **読み書き全権** | **自分のinboxのみ読み込み** | **inbox読み込み・outbox書き込み** |
| **Layer 3a: outbox YAML** | 参照可 | **読み込み全権（全スキャン）** | **自分のoutboxのみ書き込み** | **outbox書き込み** |
| Layer 3b: 没日録DB | cmd/subtask参照 | **アーカイブ全権** | 参照しない | **全権閲覧** |
| Layer 4: Session | instructions/shogun.md | instructions/karo.md | instructions/ashigaru.md | instructions/ohariko.md |

**注意**:
- 足軽/部屋子は **自分の inbox/outbox YAML のみ** 読み書き可能
- 家老は **全 inbox/outbox YAML** を読み書き可能
- お針子は **全 inbox/outbox YAML** を閲覧可能（先行割当のため）
```

---

## (4) ファイル構成セクションの更新案

### 現行版（206-218行）

```markdown
### ファイル構成
```
config/projects.yaml              # プロジェクト一覧（サマリのみ）
projects/<id>.yaml                # 各プロジェクトの詳細情報
status/master_status.yaml         # 全体進捗
queue/shogun_to_karo.yaml         # アーカイブ済み（queue/archive/）。新規cmdは没日録DB経由
queue/tasks/ashigaru{N}.yaml      # 廃止。subtaskは没日録DB（python3 scripts/botsunichiroku.py subtask）で管理
queue/reports/ashigaru{N}_report.yaml  # 廃止。reportは没日録DB（python3 scripts/botsunichiroku.py report）で管理
data/botsunichiroku.db            # 没日録（SQLite DB）- cmd/subtask/reportの正データ源
scripts/botsunichiroku.py         # 没日録CLI（python3 scripts/botsunichiroku.py cmd list 等）
dashboard.md                      # 人間用ダッシュボード
```
> **移行完了**: YAML通信から没日録DB（SQLite）への移行完了。全タスク・報告はDBで管理。
```

**問題点**:
- 「移行完了」と記載されているが、通信プロトコルv2では再びYAML通信に戻る
- inbox/outbox YAML の記載がない

---

### 改修案（通信プロトコルv2対応）

```markdown
### ファイル構成（通信プロトコルv2）

```
config/projects.yaml              # プロジェクト一覧（サマリのみ）
projects/<id>.yaml                # 各プロジェクトの詳細情報
status/master_status.yaml         # 全体進捗
queue/shogun_to_karo.yaml         # 将軍→家老の指示キュー（YAML通信）
queue/inbox/ashigaru1.yaml        # 家老→足軽1のタスク割当キュー（YAML通信）
queue/inbox/ashigaru2.yaml        # 家老→足軽2のタスク割当キュー（YAML通信）
...
queue/inbox/ashigaru8.yaml        # 家老→部屋子3のタスク割当キュー（YAML通信）
queue/inbox/ohariko.yaml          # 家老→お針子の監査依頼キュー（YAML通信）
queue/outbox/ashigaru1_report.yaml  # 足軽1→家老の報告キュー（YAML通信）
queue/outbox/ashigaru2_report.yaml  # 足軽2→家老の報告キュー（YAML通信）
...
queue/outbox/ashigaru8_report.yaml  # 部屋子3→家老の報告キュー（YAML通信）
queue/outbox/ohariko_report.yaml    # お針子→家老の報告キュー（YAML通信）
data/botsunichiroku.db            # 没日録（SQLite DB）- 完了済みcmd/subtask/reportの永続ストレージ
scripts/botsunichiroku.py         # 没日録CLI（アーカイブ管理: python3 scripts/botsunichiroku.py subtask archive 等）
dashboard.md                      # 人間用ダッシュボード
```

> **通信プロトコルv2**: 進行中タスクは inbox/outbox YAML で管理、完了済みタスクは没日録DBに永続化。
> 家老がYAMLからDBへのアーカイブを管理する二層構造。

### ファイルの役割（通信プロトコルv2）

| ファイル | 役割 | 管理者 | 保持期間 |
|---------|------|--------|---------|
| queue/shogun_to_karo.yaml | 将軍→家老の指示キュー | 将軍（書き込み）、家老（読み込み+status更新） | cmd完了までYAMLで保持 → 完了後DB |
| queue/inbox/ashigaru{N}.yaml | 家老→足軽のタスク割当 | 家老（書き込み+status更新）、足軽（読み込み） | subtask完了までYAMLで保持 → 完了後DB |
| queue/outbox/ashigaru{N}_report.yaml | 足軽→家老の報告 | 足軽（書き込み）、家老（読み込み） | 報告確認後、即座にDB → YAML削除 |
| queue/inbox/ohariko.yaml | 家老→お針子の監査依頼 | 家老（書き込み）、お針子（読み込み+status更新） | 監査完了までYAMLで保持 → 完了後削除 |
| queue/outbox/ohariko_report.yaml | お針子→家老の監査結果 | お針子（書き込み）、家老（読み込み） | 報告確認後、即座に削除 |
| data/botsunichiroku.db | 完了済みタスク・報告の永続ストレージ | 家老（アーカイブ書き込み）、全員（読み込み可） | 永続 |
```

---

## 総合評価: CLAUDE.md改修案の実現可能性

### 改修箇所の一覧

| セクション | 改修内容 | 影響範囲 |
|-----------|---------|---------|
| **(1) 通信プロトコル** | 全面改修（YAML inbox/outbox方式） | 全エージェント |
| **(2) /clear復帰フロー** | Step 3の読み込み方法変更（DB → inbox YAML） | 足軽/部屋子 |
| **(3) 四層モデル** | Layer 3を3a（YAML）と3b（DB）に分離 | 全エージェント |
| **(4) ファイル構成** | inbox/outbox YAML追加、説明更新 | 全エージェント |

### 家老観点での総合判定

| 観点 | 評価 | 理由 |
|------|------|------|
| **実装コスト** | ❌ 非常に高 | CLAUDE.md全面改修 + instructions/*.md全面改修 + 全エージェントの動作変更 |
| **運用負担** | ❌ 非常に高 | YAML + DB の二重管理、家老がアーカイブを手動管理 |
| **デバッグ容易性** | ✅ 向上 | YAMLを cat で読める、Git管理可能 |
| **並行安全性** | ⚠️ 中 | ファイル競合リスク、排他制御の追加実装が必要 |
| **通信ロスト対策** | ⚠️ 中 | 全outbox YAMLスキャンが必要、現行のDB方式より効率が劣る |
| **原子性保証** | ❌ 困難 | YAML削除とDB書き込みの間に失敗した場合、二重登録のリスク |

### 最終判定

**❌ CLAUDE.md改修案（通信プロトコルv2）は実現コストが非常に高く、運用負担が大幅に増加する。現行のDB直接方式を維持することを推奨する。**

---

## 推奨事項

家老として、以下を上様に進言する：

### 推奨案: 現行のDB直接方式を維持 + デバッグ容易性向上の最小改修

**代替案A: 没日録DBダンプコマンドの追加**

```bash
# 進行中タスクをYAML形式でダンプ（デバッグ用）
python3 scripts/botsunichiroku.py subtask list --status assigned --format yaml > /tmp/assigned_tasks.yaml

# 完了済み報告をYAML形式でダンプ（デバッグ用）
python3 scripts/botsunichiroku.py report list --format yaml > /tmp/reports.yaml
```

**メリット**:
- デバッグ時にYAML形式で確認可能
- 現行のDB方式を維持（実装コスト最小）
- Git管理したい場合は定期的にダンプして commit

**実装コスト**: 低（CLIに `--format yaml` オプション追加のみ）

---

**代替案B: 没日録DBのWeb UIダッシュボード**

```bash
# 軽量WebサーバーでDB内容をブラウザ表示
python3 scripts/botsunichiroku_web.py
# → http://localhost:5000 でアクセス
# → 進行中タスク、完了済み報告、監査状況をGUIで確認
```

**メリット**:
- 人間が読みやすいGUI
- 現行のDB方式を維持
- デバッグ時にブラウザで確認可能

**実装コスト**: 中（Flask + SQLite連携の軽量Webアプリ）

---

### CLAUDE.md の最小改修（用語統一のみ）

通信プロトコルv2を実装しない場合でも、以下の最小改修を推奨する：

1. **通信プロトコルセクション（169-205行）**:
   - 「指示・報告内容はYAMLファイルに書く」→ 「指示・報告内容は没日録DBに書く」
   - 「報告YAML記入」→ 「report add コマンドでDB書き込み」

2. **ファイル構成セクション（206-218行）**:
   - 「アーカイブ済み」「廃止」の記述を削除
   - 「移行完了」の記述を残す

3. **/clear復帰フロー（57-101行）**:
   - 「タスクYAML」→ 「没日録DB」
   - 用語を統一

4. **四層モデル（103-134行）**:
   - Layer 3の説明を明確化
   - 「正データ源」を強調

---

## 次ステップ: 殿のご判断を仰ぐ

- **A案**: 現行のDB直接方式を維持 + 代替案A（ダンプコマンド）実装 + CLAUDE.md最小改修（用語統一）
- **B案**: 現行のDB直接方式を維持 + 代替案B（Web UI）実装 + CLAUDE.md最小改修（用語統一）
- **C案**: 通信プロトコルv2（YAML inbox方式）の実装を強行 + CLAUDE.md全面改修

---

**以上、家老（足軽2号代理）より申し上げる。**

---

# 補足: DB書き込み権限の集約（2026-02-08追記）

> **追記日**: 2026-02-08
> **追記者**: ashigaru1
> **理由**: 将軍の補足指示「お針子のDB直接書き込み廃止、DB書き込み権限は家老のみに集約」に対応

## 概要

将軍の補足指示により、以下の設計原則が確定した：

```
┌─────────────────────────────────────────┐
│ DB書き込み権限は家老のみ               │
│ お針子: DB読み取りのみ                 │
│ 足軽・部屋子: DB権限なし               │
└─────────────────────────────────────────┘
```

この原則をCLAUDE.mdに明記する改修案を提示する。

---

## CLAUDE.mdへの追加セクション

### 追加位置

「通信プロトコル」セクション（現行169-205行）の直後、または「ファイル構成」セクション（現行206-218行）の直前に以下のセクションを挿入する。

---

## DB書き込み権限の集約

### 設計原則

```
┌─────────────────────────────────────────┐
│ DB書き込み権限は家老のみ               │
│ お針子: DB読み取りのみ                 │
│ 足軽・部屋子: DB権限なし               │
└─────────────────────────────────────────┘
```

### エージェント別の権限

| エージェント | DB読み取り | DB書き込み | YAML inbox操作 |
|------------|----------|----------|--------------|
| 将軍 | 可（cmd list等） | 可（cmd add） | 可（cmd指示） |
| 家老 | 可（全権） | **可（全権）** | 可（全権） |
| 足軽/部屋子 | 不可 | **不可** | 可（自分のタスク + 報告） |
| お針子 | 可（全権閲覧） | **不可** | 可（監査結果・先行割当報告） |

### 理由

1. **データ整合性の確保**: 複数エージェントがDB直接書き込みを行うと、競合・不整合のリスクが高まる
2. **権限分離の明確化**: 家老のみがDB管理責任を負い、他エージェントは通信プロトコル経由で連携
3. **監査トレーサビリティ**: YAML inboxに報告が残るため、誰が何を報告したか追跡可能
4. **エラー回避**: DB CLI実行エラー（パス間違い、引数ミス等）を足軽・お針子で発生させない

### YAML Inbox方式の通信フロー

#### 足軽の報告フロー

```
足軽がタスク完了
  │
  ▼ 報告をYAML inboxに書き込み
  │   Edit queue/inbox/{karo}_reports.yaml
  │   → reports リストに新規報告を追記（read: false）
  │
  ▼ send-keys で家老に通知
  │   tmux send-keys -t {家老ペイン} 'ashigaru{N}、任務完了でござる。報告書を確認されよ。'
  │   tmux send-keys -t {家老ペイン} Enter
  │
  ▼ 家老が報告YAML読み取り
  │   Read queue/inbox/{自分}_reports.yaml
  │   → read: false の報告を抽出
  │
  ▼ 家老がDBに記録
  │   python3 scripts/botsunichiroku.py report add {subtask_id} {worker} --status done --summary "..."
  │   python3 scripts/botsunichiroku.py subtask update {subtask_id} --status done
  │
  ▼ 家老がYAMLの read フラグを更新
  │   Edit queue/inbox/{自分}_reports.yaml
  │   → 該当報告の read: false → read: true
  │
  ▼ 完了
```

#### お針子の監査報告フロー

```
お針子が監査完了
  │
  ▼ 監査結果をYAML inboxに書き込み
  │   Edit queue/inbox/{karo}_ohariko.yaml
  │   → audit_reports リストに新規報告を追記（result: approved | rejected_trivial | rejected_judgment）
  │
  ▼ send-keys で家老に通知
  │   tmux send-keys -t {家老ペイン} 'お針子より監査報告。subtask_XXX: 合格。報告YAMLを確認くだされ。'
  │   tmux send-keys -t {家老ペイン} Enter
  │
  ▼ 家老が報告YAML読み取り
  │   Read queue/inbox/{自分}_ohariko.yaml
  │   → read: false の監査報告を抽出
  │
  ▼ 家老がDBに記録
  │   python3 scripts/botsunichiroku.py report add {subtask_id} ohariko --status done --summary "..." --findings "..."
  │   python3 scripts/botsunichiroku.py subtask update {subtask_id} --audit-status done (または rejected)
  │
  ▼ 家老がYAMLの read フラグを更新
  │   Edit queue/inbox/{自分}_ohariko.yaml
  │   → 該当報告の read: false → read: true
  │
  ▼ 監査結果に応じた後続処理
  │   ■ approved → 戦果移動・次タスク進行
  │   ■ rejected_trivial → 足軽/部屋子に差し戻し
  │   ■ rejected_judgment → dashboard.md「要対応」に記載
  │
  ▼ 完了
```

---

## ファイル構成の更新

### 新規追加ファイル

```
queue/inbox/
  ├── ashigaru1.yaml          # 足軽1のタスク inbox
  ├── ashigaru2.yaml          # 足軽2のタスク inbox
  ├── ...
  ├── ashigaru8.yaml          # 部屋子3のタスク inbox
  ├── roju_reports.yaml       # 老中への足軽報告 inbox
  ├── ooku_reports.yaml       # 御台所への部屋子報告 inbox
  ├── roju_ohariko.yaml       # 老中へのお針子報告 inbox
  └── ooku_ohariko.yaml       # 御台所へのお針子報告 inbox
```

### ファイル構成セクションの改修案

**Before**:
```
### ファイル構成
config/projects.yaml              # プロジェクト一覧（サマリのみ）
projects/<id>.yaml                # 各プロジェクトの詳細情報
status/master_status.yaml         # 全体進捗
queue/shogun_to_karo.yaml         # アーカイブ済み（queue/archive/）。新規cmdは没日録DB経由
queue/tasks/ashigaru{N}.yaml      # 廃止。subtaskは没日録DB（python3 scripts/botsunichiroku.py subtask）で管理
queue/reports/ashigaru{N}_report.yaml  # 廃止。reportは没日録DB（python3 scripts/botsunichiroku.py report）で管理
data/botsunichiroku.db            # 没日録（SQLite DB）- cmd/subtask/reportの正データ源
scripts/botsunichiroku.py         # 没日録CLI（python3 scripts/botsunichiroku.py cmd list 等）
dashboard.md                      # 人間用ダッシュボード
```

**After**:
```
### ファイル構成
config/projects.yaml              # プロジェクト一覧（サマリのみ）
projects/<id>.yaml                # 各プロジェクトの詳細情報
status/master_status.yaml         # 全体進捗
queue/shogun_to_karo.yaml         # アーカイブ済み（queue/archive/）。新規cmdは没日録DB経由
queue/inbox/ashigaru{N}.yaml      # 足軽/部屋子のタスク inbox（家老→足軽の指示）
queue/inbox/{karo}_reports.yaml   # 家老への足軽報告 inbox（足軽→家老の報告）
queue/inbox/{karo}_ohariko.yaml   # 家老へのお針子報告 inbox（お針子→家老の監査結果・先行割当報告）
data/botsunichiroku.db            # 没日録（SQLite DB）- cmd/subtask/reportの正データ源（家老のみ書き込み可）
scripts/botsunichiroku.py         # 没日録CLI（python3 scripts/botsunichiroku.py cmd list 等）
dashboard.md                      # 人間用ダッシュボード
```

---

## /clear後の復帰手順の改修

### 現行フロー（DB CLI版）

**Step 3の改修前**:
```
▼ Step 3: 自分の割当タスク確認（~800トークン）
│   python3 scripts/botsunichiroku.py subtask list --worker ashigaru{N} --status assigned
│   → 割当があれば: python3 scripts/botsunichiroku.py subtask show SUBTASK_ID で詳細確認
│   → 割当なしなら: 次の指示を待つ
│   → assigned_by フィールドで報告先家老を確認（roju=multiagent:agents.0, ooku=ooku:agents.0）
```

### 改修後フロー（YAML Inbox版）

**Step 3の改修後**:
```
▼ Step 3: 自分の割当タスク確認（~600トークン）
│   Read queue/inbox/ashigaru{N}.yaml
│   → tasks リストの中から status: assigned を探す
│   → 割当があれば: 同じYAML内の description, notes, target_path, project, assigned_by を確認
│   → 割当なしなら: 次の指示を待つ
│   → assigned_by フィールドで報告先家老を確認（roju=roju_reports.yaml, ooku=ooku_reports.yaml）
```

**変更点**:
- DB CLI不要 → YAML inbox読み取りのみ
- トークン削減: ~800 → ~600（DB CLI実行オーバーヘッドなし）
- 報告先の記載を修正（roju_reports.yaml, ooku_reports.yaml）

---

## 将軍の必須行動セクションの改修

### 「3. 報告の確認」の改修案

**Before**:
```
### 3. 報告の確認
- 足軽の報告は没日録DBで管理: `python3 scripts/botsunichiroku.py report list --worker ashigaru{N}`
- 家老からの報告待ちの際はこれを確認
```

**After**:
```
### 3. 報告の確認
- 足軽の報告は家老が処理（queue/inbox/{karo}_reports.yaml → DB記録）
- 家老からの報告待ちの際は dashboard.md または没日録DB（`python3 scripts/botsunichiroku.py report list --worker ashigaru{N}`）を確認
- お針子の監査報告も家老が処理（queue/inbox/{karo}_ohariko.yaml → DB記録）
```

---

## 移行の影響範囲サマリ

### 改修対象ファイル

| ファイル | 改修内容 |
|---------|---------|
| CLAUDE.md | 「DB書き込み権限の集約」セクション追加、ファイル構成更新、/clear復帰フロー改修 |
| instructions/ashigaru.md | DB CLI → YAML inbox方式への全面書き換え（docs/ashigaru_instructions_changes.md 参照） |
| instructions/karo.md | 足軽・お針子報告のYAML受信処理追加（docs/karo_instructions_changes.md 補足セクション参照） |
| instructions/ohariko.md | DB CLI直接書き込み廃止、YAML inbox方式への書き換え（docs/ohariko_instructions_changes.md 参照） |

### 新規作成ファイル

| ファイル | 内容 |
|---------|------|
| queue/inbox/ashigaru{N}.yaml | 足軽/部屋子のタスク inbox（N=1～8） |
| queue/inbox/roju_reports.yaml | 老中への足軽報告 inbox |
| queue/inbox/ooku_reports.yaml | 御台所への部屋子報告 inbox |
| queue/inbox/roju_ohariko.yaml | 老中へのお針子報告 inbox |
| queue/inbox/ooku_ohariko.yaml | 御台所へのお針子報告 inbox |

---

## 移行手順（将軍承認後）

### Phase 1: ファイル準備
1. queue/inbox/ ディレクトリ作成
2. inbox YAMLテンプレート作成（ashigaru1～8.yaml, roju_reports.yaml, ooku_reports.yaml, roju_ohariko.yaml, ooku_ohariko.yaml）

### Phase 2: instructions改修
1. instructions/ashigaru.md 改修（docs/ashigaru_instructions_changes.md 反映）
2. instructions/karo.md 改修（docs/karo_instructions_changes.md 補足反映）
3. instructions/ohariko.md 改修（docs/ohariko_instructions_changes.md 反映）
4. CLAUDE.md 改修（本補足セクションの内容を反映）

### Phase 3: パイロット運用
1. 足軽1名（ashigaru1）でYAML inbox方式のテスト
2. お針子1件の監査報告でYAML inbox方式のテスト
3. 問題なければ全エージェントに展開

### Phase 4: 全面展開
1. 全足軽・部屋子をYAML inbox方式に移行
2. お針子の全監査報告をYAML inbox方式に移行
3. 家老のYAML報告処理フローを確立
4. 運用開始

---

## メリット・デメリット

### メリット

1. **DB書き込み権限の集約**: 家老のみがDB書き込み → データ整合性向上
2. **トレーサビリティ**: YAML inboxに報告が残るため、追跡・監査が容易
3. **エラー回避**: 足軽・お針子がDB CLI実行エラーを起こさない
4. **権限分離の明確化**: 家老=DB管理、足軽・お針子=通信プロトコル

### デメリット

1. **家老の負荷増**: YAML報告読み取り → DB記録の作業が発生（~700トークン/報告）
2. **レイテンシ増**: 足軽/お針子 → 家老 → DB の3ステップ（旧: 直接DBの1ステップ）
3. **実装コスト**: instructions改修、inbox YAML作成、パイロット運用等

---

## 推奨事項

将軍の補足指示「お針子のDB直接書き込み廃止、DB書き込み権限は家老のみに集約」に従い、以下を推奨する：

1. **YAML Inbox方式の全面採用**: 足軽・お針子の両方でYAML inbox方式を採用
2. **家老の責務拡大**: YAML報告読み取り → DB記録を家老の標準業務とする
3. **段階的移行**: パイロット運用で動作確認後、全エージェントに展開

**理由**: DB書き込み権限の集約により、データ整合性・トレーサビリティが大幅に向上する。家老の負荷増はあるが、システム全体の安全性・保守性向上のメリットが大きい。

---

**以上、将軍の補足指示に対応したCLAUDE.md改修案（補足セクション）でござる。**
