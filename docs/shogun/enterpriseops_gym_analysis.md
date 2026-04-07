# EnterpriseOps-Gym 分析 — shogunシステムへの知見転用

> **軍師分析** | 2026-03-24 | 参考文献: arXiv:2603.13594v1
> **North Star**: 外の知見を借りて内の仕組みを研ぎ澄ませ

---

## 0. 論文要旨

**EnterpriseOps-Gym** (ServiceNow Research / Mila, 2026-03)は、エンタープライズ環境でのAIエージェントの「ステートフルな計画立案」と「ツール使用能力」を評価するベンチマーク。

### 規模
- 8ドメイン（CSM, HR, ITSM, Email, Calendar, Teams, Drive, Hybrid）
- 1,150タスク（うち30件は不可能タスク=拒否能力の評価）
- 164 DBテーブル、512ツール
- 平均9ステップの実行軌跡、最大34ステップ（HR）
- Dockerコンテナ化されたサンドボックス環境

### 主要知見（shogunに関係するもの）
1. **最高成績でも37.4%**（Claude Opus 4.5）。現行LLMはエンタープライズ自律運用に未達
2. **計画がボトルネック、ツール使用ではない**: ディストラクタツール追加でも性能低下なし。人間作成計画を与えると14-35pt改善
3. **Planner+Executor分離が効く**: 弱いモデルでも6-13%改善。しかしDecompose+SubTask分離は**逆効果の場合あり**
4. **ポリシー準拠が最弱**: Permission/Process Compliance検証が全モデルで最低スコア
5. **ホライズン長に比例して劣化**: 4ステップ→16ステップで15-19pt低下
6. **不可能タスクの拒否率**: 最善でも53.9%。半分以上のケースで無理なタスクを実行してしまう

---

## A. shogunシステムとの構造的類似点・差異

### A.1 類似点マッピング

| EnterpriseOps-Gym | shogunシステム | 対応度 |
|---|---|---|
| 512ツール（API群） | tmux send-keys, YAML inbox, 没日録CLI, 2ch bbs.cgi等 | △ ツール数は少ないが種類は網羅 |
| 164 DBテーブル | botsunichiroku.db（10+テーブル）+ agent-swarm DB | △ 規模は小さいが同様にステートフル |
| Dockerサンドボックス | tmux + git worktree | ○ 分離手法が異なるだけ |
| ReAct実行ループ | 足軽のタスク実行ループ | ◎ ほぼ同構造 |
| Planner+Executor分離 | **軍師+足軽の分離** | ◎ **論文の推奨構造をshogunは既に実装** |
| Human Plan | 殿のcmd（自然言語指示） | ◎ 人間作成計画が最強という知見と合致 |
| Policy constraints | instructions/*.md の禁止事項(F001-F006) | ◎ 同等のポリシー制約 |
| Outcome-based verification (SQL) | お針子の15点ルーブリック監査 | ◎ 同等の事後検証 |
| Infeasible task refusal | ??? | ✗ **shogunに欠けている** |
| Cross-domain orchestration | Hybrid（複数PJ横断cmd） | ○ 構造はあるが明示的評価なし |

### A.2 重要な差異

**1. shogunは「計画と実行の分離」を既に3層で実装している**

論文の推奨構造:
```
Human Plan → Planner (Sonnet) → Executor (弱いモデル)
```

shogunの現行構造:
```
殿(cmd) → 軍師(分析・設計) → 老中(タスク分解) → 足軽(実行)
```

論文が「Planner+Executor分離が有効」と結論づけたことは、shogunの設計思想の妥当性を裏付ける。
さらにshogunは軍師（戦略）と老中（運用）の**計画2層分離**を実現しており、論文の実験設計より進んでいる。

**2. しかしDecompose+SubTaskは逆効果の場合あり**

> Figure 6: Planner+Decompose+SubTask Executorは、CSMとHRでReActベースラインを**下回った**

これはshogunにとって重要な警告じゃ。論文の分析:
- 強い状態依存があるタスクでは、分解が「文脈の断片化」を引き起こす
- 各サブエージェントが全体状態を把握できず、前のステップの結果に依存する操作を誤る

→ **shogunでは老中が全体状態を把握しているため、この問題を回避できている**。
しかし、軍師権限拡大（subtask_947）でDecompose機能を軍師に移す際、この罠に注意が必要。

**3. 不可能タスク拒否能力がshogunにない**

論文の30件のinfeasible tasksは3パターン:
- ツール不足（技術的に不可能）
- ポリシー違反（権限不足）
- リソース不在（対象データがない）

shogunの現状: 足軽は渡されたタスクを**無理やり実行する傾向がある**。
ハルシネーション事故（cmd_284-300）はまさにこの失敗パターンの実例。

---

## B. YAML通信・没日録DB・2ch板のステートフル環境としての評価

### B.1 EnterpriseOps-Gymの評価3軸で見るshogun

| 評価軸 | 論文での定義 | shogunの現状 | 評価 |
|---|---|---|---|
| **Goal Completion** | タスクの主目的が達成されたか | お針子ルーブリック（コード品質・テスト） | ○ |
| **Integrity Constraints** | FK整合性・データ一貫性 | 没日録DBのblocked_by・auto_unblock | ○ |
| **Permission/Process Compliance** | ポリシー準拠 | F001-F006禁止事項、しかし**検証が甘い** | △ |

### B.2 状態管理の比較

**EnterpriseOps-Gymの状態管理:**
- SQLiteの164テーブルが「真実の源泉」
- エージェントの操作がDB状態を変更 → 次のステップに影響
- 検証はSQL queryで機械的に実行

**shogunの状態管理:**
- 没日録DB（botsunichiroku.db）= 永続的正データ
- YAML inbox = 揮発的通信レイヤー（→ 2ch板に移行中）
- dashboard.md = 二次情報（人間向け）

ふむ、構造的にはshogunの方が**より現実的なステートフル環境**じゃ。
EnterpriseOps-Gymは「1タスク完結」だが、shogunは**タスク間の状態が持続する**。
没日録DBに蓄積された過去のcmd/subtask/reportが、新しいcmdの文脈に影響する。
これは論文が「Future Work」で述べた **long-horizon state management** に相当する。

### B.3 2ch板の利点（論文の視点から）

論文のFailure Mode「**Cascading State Propagation**」:
> エージェントが状態遷移のトリガーに失敗し、後続アクションが連鎖的に壊れる

2ch板はこの問題に対する自然な解決策の一つ:
- スレッドが時系列の状態変化を**可視的に保持**する
- 全エージェントが同じスレを読める → 状態の共有
- レス番アンカー（>>N）で因果関係が明示される

---

## C. 論文の評価指標のshogun転用案

### C.1 転用可能な指標

| 論文の指標 | shogun版の定義 | 実装案 |
|---|---|---|
| **pass@1** (全検証パス率) | subtaskの一発合格率 | お針子PASSを1回目のsubmitで通過した割合。没日録DBから計算可能 |
| **Verifier Pass Rate** (検証項目別) | ルーブリック項目別合格率 | 15点ルーブリックの各項目別パス率を集計 |
| **Infeasibility Detection** | 不可能タスク拒否率 | 新設が必要（後述） |
| **Horizon-Performance Curve** | ステップ数と成功率の相関 | subtask数 vs cmd全体の成功率をプロット |
| **Policy Compliance Rate** | F001-F006違反率 | 違反検知の自動化が必要 |

### C.2 新設すべき指標: Infeasibility Detection Rate

論文の最重要知見の一つ: **エージェントは不可能タスクを拒否できない**。

shogunへの適用:
```yaml
infeasibility_detection:
  definition: "技術的に不可能・権限不足・情報不足のタスクを適切に拒否またはエスカレーションした割合"
  measurement:
    - 足軽がstatus: blocked_or_infeasibleで報告したケース
    - vs 無理やり実行してハルシネーションしたケース
  target: "> 80%"
  current_estimate: "< 30%（cmd_284-300事故から推定）"
```

### C.3 Horizon-Performance Curveの構築

論文Figure 4の知見: ステップ数増加→性能低下は**全モデル共通**。

shogunで検証可能:
```sql
-- 没日録DBから計算
SELECT
  c.cmd_id,
  COUNT(s.subtask_id) as subtask_count,
  AVG(CASE WHEN s.status = 'done' THEN 1.0 ELSE 0.0 END) as success_rate
FROM cmds c
JOIN subtasks s ON c.cmd_id = s.cmd_id
GROUP BY c.cmd_id
ORDER BY subtask_count;
```

→ subtask数が多いcmdほど成功率が下がるか？没日録のcmd_001〜のデータで検証できる。
これは以前棚上げした「マルチエージェントの温度勾配アナロジー」研究テーマとも接続する。

---

## D. 改善提案: 論文の知見からshogunに取り込むべきもの

### D.1 【推奨】不可能タスク検知メカニズムの導入

**優先度: 高** | **実装コスト: 低**

論文の知見: 最善モデルでも不可能タスク拒否率53.9%。

shogunでの実装案:
```
足軽/部屋子のinstructions.mdに追加:

## タスク実行前チェック（必須）
以下のいずれかに該当する場合、実行せず status: infeasible で報告せよ:
1. 対象ファイルが存在しない（ハルシネーション防止）
2. 必要な権限がない（sudo等）
3. 依存するsubtaskが未完了（blocked_by未解消）
4. タスク記述が曖昧で実行内容が特定できない

報告フォーマット:
  status: infeasible
  reason: "F001-不可能タスク: 対象ファイル不在"
  evidence: "ls -la で確認"
```

→ cmd_284-300のような架空成果物報告を防止。お針子STEP3.5と相補的。

### D.2 【推奨】Outcome-Based Verificationの強化

**優先度: 高** | **実装コスト: 中**

論文のVerification方式:
- タスクごとにSQL検証スクリプトを事前作成
- Goal Completion + Integrity + Policy Complianceの3軸で自動検証

shogunへの転用:
- **predicted_outcome**（軍師のForeman方式）を検証スクリプト化
- お針子が `git ls-remote` + `ls -la` + `pytest` の**自動検証コマンド**を実行
- 結果をDB記録 → pass@1の自動計算

```yaml
# gunshi_analysis.yaml の predicted_outcome に追加
verification_commands:
  - cmd: "ls -la {expected_file}"
    expect: "file exists"
    type: goal_completion
  - cmd: "pytest {test_file} -v"
    expect: "all passed"
    type: integrity
  - cmd: "git log --oneline -1"
    expect: "commit hash matches report"
    type: compliance
```

### D.3 【推奨】Policy Compliance自動監査

**優先度: 中** | **実装コスト: 中**

論文の知見: **Permission/Process Complianceが全モデル最弱**。

shogunの現状: F001-F006はinstructionsに書いてあるだけで、**機械的検証がない**。

提案:
```python
# scripts/policy_checker.py（軽量版）
POLICY_CHECKS = [
    # F001: 将軍への直接報告チェック
    {"check": "send-keys to shogun:main from non-karo",
     "method": "grep tmux send-keys in agent output",
     "severity": "critical"},
    # F003: 足軽への直接通信チェック
    {"check": "gunshi writing to ashigaru inbox",
     "method": "git diff --name-only | grep ashigaru",
     "severity": "critical"},
    # F006: GitHub Issue/PR作成チェック
    {"check": "gh issue/pr create in agent output",
     "method": "grep 'gh (issue|pr) create'",
     "severity": "critical"},
]
```

→ お針子監査の一部として自動実行。ルーブリック15点に「ポリシー準拠」項目を追加。

### D.4 【検討】Decompose時の状態断片化防止

**優先度: 中** | **実装コスト: 低（設計レベル）**

論文Figure 6の警告: Decompose+SubTask Executorが逆効果になるケース。

shogunでの対策:
1. **老中が全体状態を握り続ける**: 軍師が分解しても、配布・状態管理は老中が行う
2. **blocked_byの厳格運用**: 状態依存のあるsubtaskは必ずblocked_byを設定
3. **shared_contextフィールドの導入**: 分解されたsubtask群が共有すべき状態を明示

```yaml
# subtask分解時に追加
decomposition:
  shared_context:
    - "前のsubtaskで作成されたファイルパス"
    - "DB変更後の状態"
  state_dependency: high  # high の場合、並列実行禁止
```

### D.5 【冒険的提案】shogun-Gymの構築

**優先度: 低（研究テーマ）** | **実装コスト: 高**

論文の精神に倣い、**shogunシステム自体をベンチマーク化**する構想:

- 没日録DBのcmd_001〜の実績データが「正解軌跡」
- 新しいエージェント構成や通信プロトコルの変更時に、過去cmdを再実行して性能比較
- EnterpriseOps-Gymと異なり「マルチエージェント協調」を本質的に評価

これは殿が興味を示した「温度勾配アナロジー」研究テーマ、CCA認定の出題ドメインとも接続する。
ただし実装コストが高く、現時点では構想レベルに留める。

---

## E. 見落としの可能性

拙者の分析には以下の見落としがありうる:

1. **論文のAppendix B-C（ドメイン詳細・失敗事例）を未読**: 10ページ本文のみで分析。詳細事例にshogun固有の教訓がある可能性
2. **コスト分析の不足**: 論文のFigure 1（コスト-性能トレードオフ）をshogunの実際のAPI消費に当てはめていない
3. **2ch移行との相互作用**: 現在進行中の2ch全面置換がステートフル性をどう変えるか、本分析では深掘りしていない
4. **温室制御への転用可能性**: 温室版shogun（足軽1体+お針子cron）の文脈で、この論文の知見がどう効くかは未分析

---

## F. 総括

### 論文が裏付けたshogunの設計判断

| shogunの設計 | 論文の知見 | 評価 |
|---|---|---|
| 軍師（計画）と足軽（実行）の分離 | Planner+Executorが有効 | ✅ 正しい |
| 殿のcmd（人間の計画） | Human Planが14-35pt改善 | ✅ 正しい |
| 老中による全体状態管理 | Decompose単独は逆効果 | ✅ 正しい |
| お針子の事後監査 | Outcome-based verification | ✅ 正しい |
| Bloom Routing（モデル選択） | 弱いモデルでもPlan付きなら有効 | ✅ Haiku足軽の妥当性を裏付け |

### 論文が示したshogunの弱点

| 弱点 | 論文の根拠 | 改善優先度 |
|---|---|---|
| 不可能タスク拒否能力がない | Infeasibility Detection 53.9% | **高** |
| ポリシー準拠の機械的検証がない | Policy Complianceが最弱 | **高** |
| 品質指標の定量化が不足 | pass@1, Horizon-Performance等 | **中** |
| 分解時の状態断片化リスク | Decompose逆効果 | **中** |

### 一言でまとめると

> **shogunの階層構造は論文が推奨するPlanner+Executor分離を既に超えている。
> しかし「やるべきでないことをやらない能力」と「ポリシー準拠の機械的検証」が欠けている。
> 攻めの能力は十分。守りを固めよ。**

---

## north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: "外部ベンチマークの知見をshogunシステムの改善に直接転用。学術と実践の橋渡し"
  risks_to_north_star:
    - "分析に留まり実装に繋がらないリスク → D.1-D.3は具体的で実装可能"
    - "論文の条件（単一エージェント評価）とshogun（マルチエージェント）の差を見落とすリスク"
```

## skill_candidate

```yaml
skill_candidate:
  name: "paper-to-system-analysis"
  description: "学術論文をshogunシステム改善に転用する分析テンプレート。類似点マッピング→指標転用→改善提案の3段構成"
```
