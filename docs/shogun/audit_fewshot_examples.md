# 監査事例 few-shot examples（severity calibration用）

> subtask_935 成果物。お針子SKILL.md Step 5 への組み込み素材。
> 抽出元: queue/inbox/roju_ohariko.yaml（audit_requests）

---

## 事例A — 14/15 approved（合格）

**subtask**: subtask_786 | **cmd**: cmd_349 | **worker**: ashigaru1

**スコア内訳（推定）**:
| カテゴリ | 点 | 理由 |
|---------|:--:|------|
| correctness | 3 | 温度段階・ch番号・緊急停止ライン全て殿指定と完全一致 |
| code_quality | 3 | rule_engineとの整合性が旧版より向上、コード構造良好 |
| completeness | 3 | 要件の全実装確認済み |
| no_regressions | 3 | commit acb9056実在確認、origin/main push確認 |
| tests | 2 | テスト自体は通過、軽微な懸念1点減 |
| **合計** | **14** | |

**お針子summary（原文）**:
> ルール2ピタゴラスイッチ方式書き換え完全実装。温度段階・ch番号・緊急停止ライン全て基本ルールと一致。rule_engineとの整合性も旧版より向上。

**お針子findings（要約）**:
- commit acb9056実在確認、origin/main push確認
- 温度段階(25/26/26.5/27℃)が殿指定と完全一致
- ch5/ch6=南側窓・ch7/ch8=北側窓がハウス環境設定と完全一致
- 緊急停止ライン(27℃超/16℃未満)を基本ルールと逐語的に整合

**なぜこの点数か**:
設計書通りの実装で要件を完全に満たし、コミット・pushも確認済み。コードの美しさより「動作し要件を満たす」が基準。tests 2点は軽微な懸念による1点減で、根本的問題はなし。典型的な合格例。

---

## 事例B — 11/15 rejected_trivial（要修正・自明）

**subtask**: subtask_755 | **cmd**: cmd_327 | **worker**: ashigaru1

**スコア内訳（推定）**:
| カテゴリ | 点 | 理由 |
|---------|:--:|------|
| correctness | 3 | SDK差し替え・TOOLS定義・messages形式・finish_reason全て正確 |
| code_quality | 2 | 空行重複1箇所（機能影響なし）、軽微な書式違反 |
| completeness | 2 | anthropic importゼロ確認・後方互換確保、ただし軽微な未整理あり |
| no_regressions | 2 | pytest 455件全PASS、forecast_engine単体53件PASS |
| tests | 2 | テスト自体は全PASS、品質面の軽微な懸念 |
| **合計** | **11** | |

**お針子summary（原文）**:
> forecast_engine OpenAI SDK互換化。Anthropic SDK→OpenAI SDKへの全面差し替え完了。TOOLS定義(type:function形式)、messages形式(system→messages[0], role:tool)、finish_reason(tool_calls/stop)全て正確。後方互換性(anthropic_clientエイリアス+claudeキーマージ)も確保。テスト455件全PASS(forecast_engine単体53件含む)。src/内のanthropic import残存なし。書式のみ軽微減点(空行重複1箇所)。

**お針子findings（要約）**:
- commit aca910a 実在、pytest 455 passed
- src/内 anthropic import 残存ゼロ
- forecast_engine.py L731付近に連続空行1箇所（機能影響なし）

**なぜこの点数か**:
要件は満たしており動作も正常。ただし書式の軽微な問題(空行重複)が複数カテゴリに波及して減点。修正箇所は明確で、空行削除のみで再提出可能な「自明な修正ケース」。correctness は3点満点を維持。

---

## 事例C — 6/15 rejected_judgment（要修正・要判断）

**subtask**: subtask_829 | **cmd**: cmd_370 | **worker**: ashigaru1

**スコア内訳（推定）**:
| カテゴリ | 点 | 理由 |
|---------|:--:|------|
| correctness | 2 | bloom_router.sh 16件PASSはお針子実機確認済み、実装自体は機能 |
| code_quality | 2 | コード品質は問題なし、しかし成果物証跡ゼロ |
| completeness | 1 | gunshi_analysis検証/通信フロー/PDCAドライランのエビデンスなし |
| no_regressions | 1 | 専用コミットなし、報告書なし |
| tests | 0 | 統合テスト完了の証跡ゼロ（報告書・コミット・ログ全て不在） |
| **合計** | **6** | |

**お針子summary（原文）**:
> 要修正・自明(6/15): 統合テスト完了報告書なし・コミットなし。bloom_router.sh 16件PASSはお針子実機確認済みだが、gunshi_analysis検証/通信フロー/PDCAドライランのエビデンスがゼロ。

**お針子findings（要約）**:
- report がDBに1件も存在しない（report addコマンド未実行）
- 専用コミットなし（2026-03-08 19:14〜20:05の間に統合テストコミット不在）
- bloom_router.sh 16件PASS: お針子が実機確認 → 実装自体は機能
- gunshi_analysis検証/通信フロー/PDCAドライランの実施有無が不明

**なぜこの点数か**:
実装自体（bloom_router.sh）は動作しているが、成果物の証跡（コミット・report add・ログ）が全て欠落。「動いたかもしれないが証明できない」ケース。単純なコード修正では解決不可で、エビデンス再整備が必要。completeness/no_regressions/testsが低点の典型。

---

## 抽出メタデータ

- 抽出日: 2026-03-18
- 抽出元: queue/inbox/roju_ohariko.yaml[audit_requests]
- score分布: 0×1, 6×1, 9×2, 10×2, 11×7, 12×4, 13×21, 14×13, 15×5（計56件）
- 選定基準: 高(>=14)・中(10-12)・低(<=7)の代表例 各1件
