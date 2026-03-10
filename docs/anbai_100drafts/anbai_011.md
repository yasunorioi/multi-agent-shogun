<!-- style: Qiitaテック記事風 | perspective: A冷静学術 | number: 011 -->

# LLM呼び出しを89%削減した三層アーキテクチャの設計と「Anbai理論」

**はじめに**

AI制御システムを設計するとき、「どのくらいLLMを使えばいいか」という問いに答えを持っている人は少ない。

本記事では、某クライアントとの環境制御プロジェクト（詳細はNDA）で得た実証知見を基に、過剰最適化の構造的原因と解決策としての三層アーキテクチャを解説する。

---

## TL;DR

- 最初、LLMを毎時呼んでいた → 全体の29.1%が「緊急」判定になった
- 問題の原因は精度不足ではなく**アーキテクチャの設計**だった
- 三層構造（if文→cron→LLM）に変えたら**LLM呼び出し89%削減**
- Herbert Simon（1956）の「satisficing」が70年越しに実証された

---

## 問題：27℃で世界が緊急になった

### データ概要

```
観測期間: 2025年6月〜9月（114日間）
サンプリング: 5分間隔
総データ数: 32,470レコード
観測対象: 某施設の環境データ（NDA）
```

### 初期設定の問題

初期設計では、室内温度T>27℃を「緊急」とし、LLMに即時判断を依頼するロジックを実装した。

```python
# 初期実装（問題あり）
def check_temperature(temp):
    if temp > 27.0:
        return call_llm("緊急: 温度異常。対処法を教えて")
    return "normal"
```

しかし実際の温度分布を確認すると：

| 温度帯 | 割合 |
|--------|------|
| <16℃ | 4.5% |
| 16〜23℃ | 36.3% |
| 23〜27℃ | 28.2% |
| **>27℃（緊急）** | **29.1%** |

**全体の29.1%が「緊急」と判定された。**

これはGoodhart's Lawの典型例だ。「27℃を緊急の閾値に設定した瞬間、27℃は緊急を示す指標として機能しなくなった」。

---

## 原因分析：過剰最適化という構造的問題

### Anbai Curve

成果品質は最適化投入量に対して単調増加しない。ある点（Anbai Point）を超えると逓減する。

```
品質
↑
│         ╭────────╮
│       ╱   Anbai   ╲
│     ╱     Zone     ╲
│   ╱                  ╲___
│ ╱
└────────────────────────→ LLM呼び出し頻度
     ↑                ↑
  Anbai Point    崩壊点
```

「毎時LLMを呼ぶ」は、このカーブの右端に位置していた。

---

## 解決策：三層アーキテクチャ

問題を解決したのは精度向上ではなく、**構造の変更**だった。

### 設計思想

```
Layer 1（if文）: 本当の緊急だけ。絶対に削るな。
Layer 2（cron+ルール）: 日常の99%をここで処理する。
Layer 3（LLM）: 本当に困った時だけ呼ぶ。
```

### 実装イメージ

```python
# 三層構造（改善後）
def control_system(sensor_data):
    # Layer 1: 緊急停止（絶対閾値）
    if sensor_data['critical_param'] > ABSOLUTE_LIMIT:
        emergency_stop()
        notify_immediately()
        return

    # Layer 2: ルールベース（99%はここで解決）
    result = rule_engine.evaluate(sensor_data)
    if result.is_deterministic:
        return apply_rule(result)

    # Layer 3: LLM（本当に判断が難しいときだけ）
    return call_llm(sensor_data)
```

### 制御ルールの源泉

制御設定ファイルには現場固有のルールが蓄積されている（詳細はNDA管理下）。これらはAI技術者が設計したルールではない。クライアントのフィードバック——現場の経験と判断——から生まれたものだ。

```yaml
# 制御ルールの構造（概念図）
rules:
  - id: rule_001
    source: "クライアントフィードバック"
    confidence: high
    # 具体的内容はNDA管理下
```

---

## 結果

| 指標 | Before | After |
|------|--------|-------|
| LLM呼び出し頻度 | 毎時1回 | 約0.11回/時 |
| 削減率 | — | **89%** |
| 緊急判定率 | 29.1% | 改善 |

---

## 学んだこと

### ① 精度より構造

「LLMの性能が高いからもっと使おう」という発想は、「専門家が優秀だから毎日常駐させよう」と同じ。コストと効果のバランスを常に確認せよ。

### ② Goodhart's Lawに気をつけよ

指標が目標になった瞬間、その指標は意味を失う。「緊急率を0%にする」ことを目標にすると、閾値を∞にするだけで達成できてしまう。正しい指標を設計することが先決。

### ③ if文とcronを舐めるな

99%の問題はif文とcronで解ける。シンプルなツールを信頼せよ。LLMは残り1%のために存在する。

---

## 参考文献

- Simon, H.A. (1956). "Rational Choice and the Structure of the Environment." — satisficing 概念の提唱（70年前）
- Goodhart, C.A.E. (1975). "Problems of Monetary Management." — 指標の罠
- Shiomi, A. (2026). "Anbai Theory: A Framework for Optimal Sub-optimality in Complex AI Systems." *Journal of Approximate Science*, 1(1).（NDA締結済みの実証研究）

---

*本記事の実装詳細は守秘義務（NDA）により一部非開示です。設計思想は汎用なので、参考にしていただけます。*
