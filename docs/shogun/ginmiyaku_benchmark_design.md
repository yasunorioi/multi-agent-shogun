# 勘定吟味役モデル最適化 ベンチマーク設計メモ

> **作成**: subtask_1101 / cmd_500 Wave2  
> **参照**: memory/systrade_crucix_setup.md, memory/finance_temperature_theory.md  
> **前提**: MBP M4 Pro 48GB / ollama ローカル推論

---

## 1. 現行モデル: qwen2.5:32b の性能特性

### スペック

| 項目 | 値 |
|------|-----|
| モデル | qwen2.5:32b (Q4_K_M相当, ~19GB) |
| ホスト | MBP M4 Pro 48GB RAM |
| 推論エンジン | ollama |
| 用途 | kenshu板のコード品質レビュー、PASS/FAIL判定支援 |
| temperature | 0.4〜0.7（レビュー種別により可変） |

### 強み

- 日本語コードコメント対応（Japanese-English混在コードに強い）
- 32Bパラメータによる広い文脈理解
- YAML/Pythonの構造理解が安定
- 19GBメモリでMBP 48GBの約40%使用 → Crucixと同居可能

### 弱み（初回運用で判明）

- 「設計意図の妥当性」判断が薄い（コード構文は正しいが、なぜこの設計か？への批評が弱い）
- 長いdiff（500行超）でコンテキスト散漫
- kenshu_gate判定（PASS/FAIL/CONDITIONALの3値）の一貫性にばらつき

---

## 2. 比較候補モデル

### 2-1. qwen3系（リリース待ち）

| 項目 | 予測 |
|------|------|
| モデルサイズ | 32B相当予想 |
| 期待改善点 | Reasoning強化、日本語精度向上 |
| 同居制約 | qwen2.5:32bと入れ替え（同等メモリ） |
| テスト方法 | リリース後に同一subtaskで比較 |

> **方針**: qwen3リリース後、下記ベンチマーク手順で即テスト。qwen2.5から無停止移行可能か確認。

### 2-2. gpt-oss-fin-thinking（NRI 21B MoE）

| 項目 | 値 |
|------|-----|
| モデル | gpt-oss-20b-Ja-Fin-Thinking (Q8_0, 21GB) |
| Modelfile | `~/models/Modelfile.fin-thinking2` |
| temperature設定 | 0.6（現行Crucix用） |
| 専門性 | 金融特化。コード品質レビューはgeneral-purposeより弱い可能性 |
| 優位性 | 投資・Finance文書の設計レビューには適合度高い |

**Crucix同居制約**: gpt-oss-fin-thinkingはCrucixがcron稼働中（`*/30 * * * *`）に使用中。
kenshu_gate判定はcron非稼働の間隙（29分以内）を使う設計 → **片方ずつ動く前提**。

### 2-3. llama3系（将来候補）

- llama3.1:70b (Q4_K_M ~40GB) → MBP 48GBでギリギリ。Crucix同居不可
- llama3.2:3b → 軽量だが品質不足の懸念
- **現時点では候補外**。メモリ制約により優先度低。

---

## 3. ベンチマーク項目

### 3-1. レビュー品質

| 評価軸 | 計測方法 | 目標値 |
|--------|---------|:------:|
| バグ検出率 | 意図的に埋め込んだバグN個 / 検出数 | ≥ 80% |
| 誤検知率 | false positive数 / 総指摘数 | ≤ 15% |
| 設計適合性スコア | 人間ゴールドスタンダードとの比較(1-5点) | ≥ 3.5 |
| PASS/FAIL一貫性 | 同一diffを3回実行 → 判定一致率 | ≥ 90% |

### 3-2. 応答速度

| メトリクス | 計測方法 |
|-----------|---------|
| Time to first token (TTFT) | `curl` + `time` コマンド |
| 総応答時間 | 500行diffへの全文レビュー |
| throughput (tokens/sec) | ollama `/api/generate` の `eval_duration` |

**目標**: 足軽がkenshu POSTしてから2F通知→勘定吟味役レビュー完了まで **5分以内**。

### 3-3. メモリ使用量

```bash
# 計測コマンド
watch -n1 "ollama ps && vm_stat | grep 'Pages active'"
```

| モデル | 予測メモリ | Crucix同居可否 |
|--------|:---------:|:-------------:|
| qwen2.5:32b | ~19GB | ✅ 可（合計~25GB） |
| gpt-oss-fin-thinking | ~21GB | ✅ 可（合計~27GB） |
| llama3.1:70b | ~40GB | ❌ 不可 |

### 3-4. Crucixとの同居安定性

```bash
# Crucix cron + ollama kenshu-review 同時稼働テスト
# 1. cron_ideas.sh を手動起動（Crucix稼働状態）
# 2. 同時に kanjou_auto_review.sh を実行
# 3. 両方の完了時間・エラー率を計測
```

---

## 4. テスト方法: 同一subtaskでの多モデル比較

### テストデータ設計

```
test_subtasks/
  bench_easy.diff      # 明確なバグ1件（変数名typo）
  bench_medium.diff    # 設計問題1件（循環参照）
  bench_hard.diff      # 微妙なセキュリティ問題（SQLi）
  bench_architecture.diff  # アーキテクチャ違反（レイヤー跨ぎ）
```

### 評価フロー

```
1. 同一diffをqwen2.5/gpt-oss-fin/qwen3(リリース後)に投入
2. 各モデルのレビュー結果をkenshu板に投稿（FROM=kanjou_ginmiyaku）
3. 人間（殿 or 老中）がゴールドスタンダードと比較採点
4. 没日録DBのaudit_historyテーブルに記録
```

```bash
# 評価記録コマンド（botsunichiroku.py audit record 拡張予定）
python3 scripts/botsunichiroku.py audit record \
  --subtask-id bench_001 \
  --attempt 1 \
  --score 85 \
  --verdict PASS \
  --failure-category "false_positive" \
  --findings-summary "qwen2.5:32b レビュー品質評価" \
  --worker kanjou_ginmiyaku_qwen25
```

---

## 5. Crucixとの同居制約の詳細設計

### 同居スケジュール

```
00 30 * * * → Crucix cron稼働（gpt-oss-fin-thinking）約2〜5分
kenshu_auto.py → Crucix非稼働期間に自動実行（ギャップ25分）
```

### 競合回避設計

```python
# scripts/kanjou_auto_review.sh（案）

# Crucix稼働確認
if ollama ps | grep -q "gpt-oss"; then
    # Crucix稼働中 → 待機
    echo "Crucix稼働中。kenshuレビュー待機。"
    exit 0  # 次回のcronで再試行
fi

# 勘定吟味役モデル起動
ollama run kanjou-ginmiyaku << EOF
...レビュープロンプト...
EOF
```

> **F004適合**: ポーリングループ禁止。cron trigger（イベント駆動の一種）で実行。
> `while true; do sleep 60; done` は使わない。

---

## 6. 移行判断基準

| 条件 | アクション |
|------|----------|
| qwen3リリース + bench_hardスコア > qwen2.5 | qwen2.5→qwen3に移行 |
| gpt-oss-fin が設計レビューで優位 | Finance文書専用に gpt-oss-fin を使い分け |
| 応答時間 > 10分 | context長を削減（num_ctx 4096に下げる） |
| Crucix同居でOOM | Crucixを優先・勘定吟味役はオフピーク限定に変更 |

---

## 7. 実装優先度

| タスク | 優先度 | 備考 |
|--------|:------:|------|
| ベンチテストデータ作成（bench_*.diff）| **高** | 比較の基準が必要 |
| kanjou_auto_review.sh Crucix同居対応 | **高** | 競合avoidance |
| qwen3リリース後の比較テスト | **中** | リリース待ち |
| audit_historyモデル別記録拡張 | **中** | `--worker` フィールドで代替可 |
| llama3.1:70b テスト | **低** | MBP 48GB制約で現実的でない |
