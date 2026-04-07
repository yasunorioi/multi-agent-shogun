# subtask_829 統合テスト エビデンス

**提出者**: ashigaru1
**提出日時**: 2026-03-13T22:26:36
**差し戻し理由**: お針子監査却下（audit score 6/15）— 成果物エビデンス不在
**再提出タスク**: subtask_889 / cmd_370

---

## 1. bloom_router.sh 全関数テスト実行ログ

```
実行コマンド: bash lib/bloom_router.sh test

=== bloom_router.sh テスト ===
[get_capability_tier]
  PASS: opus→6 (=6)
  PASS: sonnet→4 (=4)
  PASS: haiku→2 (=2)
[get_recommended_model]
  PASS: L1→sonnet (=claude-sonnet-4-6)
  PASS: L3→sonnet (=claude-sonnet-4-6)
  PASS: L4→sonnet (=claude-sonnet-4-6)
  PASS: L5→sonnet (=claude-sonnet-4-6)
  PASS: L6→opus (=claude-opus-4-6)
[get_bloom_routing]
  PASS: routing=off (=off)
[needs_model_switch]
  PASS: opus+L6→no (=no)
  PASS: sonnet+L4→no (=no)
  PASS: sonnet+L6→yes (=yes)
  PASS: haiku+L3→yes (=yes)
  PASS: haiku+L1→no (=no)
[validate_gunshi_analysis]
  PASS: valid yaml→valid (=valid)
  PASS: invalid yaml→error (=error)

=== 結果: PASS=16 FAIL=0 ===
```

**判定: 全16テスト PASS ✅**

---

## 2. gunshi_analysis.yaml バリデーション結果

```
実行コマンド:
  source lib/bloom_router.sh
  validate_gunshi_analysis queue/inbox/gunshi_analysis.yaml

出力: valid
exit_code: 0
```

**検証対象**: `queue/inbox/gunshi_analysis.yaml`
- `task_id`: subtask_887 ✅
- `analysis.bloom_level`: 5 ✅
- `analysis.recommended_model`: claude-sonnet-4-6 ✅

**判定: valid ✅**

---

## 3. 通信フロー確認記録

### 軍師 → 家老（一方向分析YAML）

```
ファイル: queue/inbox/gunshi_analysis.yaml
task_id: subtask_887
cmd_id: cmd_397
timestamp: "2026-03-12T10:55:00"
analysis:
  bloom_level: 5
  recommended_model: claude-sonnet-4-6
  confidence: 0.92
```

フロー:
```
軍師（ooku:agents.0）
  → gunshi_analysis.yaml に分析結果を書き込み
  → 家老（multiagent:agents.0）が読み取り
  → 家老が足軽にタスク割当（ashigaru{N}.yaml）
```

### 足軽 → 老中（報告YAML）

```
ファイル: queue/inbox/roju_reports.yaml（subtask_888 完了報告例）
subtask_id: subtask_888
summary: shutsujin_departure.sh の ccusage→獏(baku)全箇所書き換え完了（11箇所）
worker: ashigaru1
detail_ref: curl -s localhost:8080/reports/854
```

フロー:
```
足軽1（multiagent:agents.1）
  1. 高札API POST /reports → report_id取得
  2. roju_reports.yaml に summary + detail_ref を追記
  3. tmux send-keys -t multiagent:agents.0（2回に分けて送信）
  4. 到達確認（capture-pane）
```

---

## 4. PDCAドライラン記録

`gunshi_analysis.yaml` に明示記録:
```yaml
pdca_needed: false
```

**判定**: PDCAドライラン不要。軍師が subtask_887 分析時に判定済み。

---

## 5. 設定確認（config/settings.yaml）

```yaml
bloom_routing: "off"
capability_tiers:
  claude-opus-4-6:   max_bloom: 6
  claude-sonnet-4-6: max_bloom: 4
  claude-haiku-4-5:  max_bloom: 2
bloom_model_preference:
  L1-L3: [claude-sonnet-4-6, claude-haiku-4-5]
  L4-L5: [claude-sonnet-4-6, claude-opus-4-6]
  L6:    [claude-opus-4-6]
```

テスト結果はこの設定と完全一致している。

---

## 総括

| 要件 | 結果 |
|------|------|
| bloom_router.sh 全関数テスト | PASS 16/16 ✅ |
| gunshi_analysis.yaml validate | valid ✅ |
| 通信フロー確認記録 | YAML送受信実例記録済み ✅ |
| PDCAドライラン | pdca_needed: false（不要）✅ |
| コミット + push | 本コミットにて実施 ✅ |
