# temperature理論 実運用適用設計メモ

> **作成**: subtask_1099 / cmd_500  
> **参照**: docs/shogun/v4_three_story_architecture.md §2.1, memory/finance_temperature_theory.md  
> **前提**: 三階建てアーキテクチャ（v4.0）

---

## 1. 設計原則: 下層(t=0)が上層(t>0)を黙らせる

temperature理論の核心は**決定論的制約**にある。

```
温室三層制御 = Finance三層 = shogun三階建て（同型アーキテクチャ）

3F 本店   t ≈ 0   ←── Layer1: 爆発防止 / daily_risk.py / SIL
2F 合議場 t > 0   ←── Layer3: 知恵 / Crucix / LLM心理分析
1F 支店群 t = 0〜 ←── Layer2: ガムテ修理 / composite_alert
kenshu_gate t = 0 ←── ゲート（完全決定的）
```

**棍棒原則**: `t=0` の判定は議論の余地なし。2F合議がどんな結果を出しても、
kenshu_gate（t=0）の判定は覆らない。老中の裁量余地はゼロ。

---

## 2. 各階のLLM呼び出し temperature推奨値

### 3F: 本店（将軍・老中） — t ≈ 0

| コンポーネント | temperature | 理由 |
|-------------|:-----------:|------|
| 将軍（Claude Code） | 1.0（API固定） | Claude Codeはtemperature指定不可。ただし動作は実質決定論的（ルールに従う） |
| 老中（Claude Code） | 1.0（API固定） | 同上。判断軸はinstructions/YAML規約で固定し、創発を制限 |
| bloom_router | **0** | L1-L3直配布判定は完全決定論的。閾値計算のみ |
| dashboard更新 | **0** | テンプレート出力。ハルシネーション排除 |

> **実用上の注意**: Claude CodeのAPIはtemperature調整不可。
> 代わりに **instructions/YAML規約で入出力を型で締める**ことで決定論的動作を担保する。
> これが1F=「型で締めたI/O」の意味。

### 2F: 合議場（お針子・軍師・勘定吟味役） — t > 0

| コンポーネント | temperature推奨値 | 理由 |
|-------------|:----------------:|------|
| お針子（Claude Code） | 1.0（API固定） | 自由議論OK。多角視点でレビュー |
| 軍師（Claude Code） | 1.0（API固定） | 戦略立案、L4-L6分析。創発前提 |
| 勘定吟味役（ollama） | **0.4〜0.7** | 設定可能。後述§3で詳細 |

> 2Fはハルシネーション前提で使う。複数エージェントの議論により偏りを相殺する設計。
> 1エージェントのハルシネーションは他2エージェントの指摘で検出される。

### 1F: 支店群（足軽） — t = 0〜中

| コンポーネント | temperature推奨値 | 理由 |
|-------------|:----------------:|------|
| 足軽（Claude Code） | 1.0（API固定） | instructionsで締める。実装は型付きI/O |
| Codex足軽 | **0〜0.3** | 設定可能。コード生成は低温で決定論的に |
| worktree内作業 | **0.2** | diffが予測可能なほうがマージ競合が減る |

> **設計意図**: 1Fは「実装の正確性」が求められる。
> Claude Codeは1.0固定だが、YAML inbox（型付きタスク指示）が実質的な温度制御。
> Codex足軽（CLI）ではtemperature設定可能。

### kenshu_gate: ゲート判定 — t = 0（絶対）

```
PASS / FAIL / CONDITIONAL の3値のみ。
t > 0 は禁止。議論の余地なし。
```

| コンポーネント | temperature | 理由 |
|-------------|:-----------:|------|
| kenshu_gate判定 | **0** | 3値判定。誤差ゼロ。 |
| severity判定(S1-S4) | **0** | ルールベース分類。創発不要 |
| scribe（DB書き戻し） | **N/A** | LLM不使用 |

---

## 3. 勘定吟味役のollama呼び出し時temperature設定

### 現行設定（gpt-oss-fin-thinking）

```
# ~/models/Modelfile.fin-thinking2
FROM ./gpt-oss-20b-Ja-Fin-Thinking.Q8_0.gguf
PARAMETER num_ctx 16384
PARAMETER temperature 0.6   ← これが現行値
```

### shogun検収レビューでの推奨設定

```python
# scripts/kanjou_auto_review.sh の呼び出しパラメータ
# 勘定吟味役用 Modelfile（案）

PARAMETER temperature 0.4   # コード品質レビュー: やや決定的
PARAMETER temperature 0.7   # 設計・創造性レビュー: やや自由
PARAMETER temperature 0.0   # PASS/FAIL判定のみ: 完全決定的
```

### temperature設定ガイドライン

| レビュー種別 | 推奨t | 根拠 |
|------------|:----:|------|
| コードバグ検出 | 0.1〜0.3 | 正誤が明確。低温で見逃し減 |
| 設計適合性チェック | 0.4〜0.6 | 創造的解釈が有益な場面あり |
| 戦略的意見・改善提案 | 0.6〜0.8 | 多様な視点が価値。軍師領域 |
| PASS/FAIL最終判定 | **0** | 3値のみ。blurを排除 |

### ollama API呼び出し例

```bash
# kanjou_auto_review.sh での呼び出し
curl -s http://localhost:11434/api/generate \
  -d '{
    "model": "kanjou-ginmiyaku",
    "prompt": "...",
    "stream": false,
    "options": {
      "temperature": 0.4,
      "num_predict": 2048,
      "num_ctx": 8192
    }
  }'
```

> **注意**: thinking系モデル（gpt-oss-fin-thinking）は `temperature` が応答品質に強く影響。
> `t=0` はthinking tokenがほぼ出なくなる。`t=0.4` が「決定的かつ推論あり」のバランス点。

---

## 4. skillsとinstructionsへのtemperature指定組み込み方法

### 現状の制約

Claude Code（将軍・老中・足軽）はtemperature指定不可（API側で固定）。
ただし以下の方法で**実質的な温度制御**が可能:

### 4.1 instructions へのtemperature相当指示

```markdown
# instructions/ashigaru.md に追記する想定

## 実装品質制御（temperature相当）

**低温モード（t=0相当）**: 以下の場合は逸脱を排除し、仕様通りに実装せよ:
- YAMLスキーマ定義済みのフィールド操作
- 既存テストに定義されたインターフェース実装
- kenshu_gate判定（PASS/FAIL/CONDITIONALのみ）

**高温モード（t>0相当）**: 以下の場合は創造的な解決策を探せ:
- 設計メモ・分析文書の作成
- バグの根本原因調査
- context/*.md への知見まとめ
```

### 4.2 skills への temperature ヒント

```markdown
# skills/delivery-post.md に追記する想定

## quality_gate

self_review フィールドは **低温モード（事実の確認のみ）** で記述:
- ✅ 「実装したこと」「テスト結果」「懸念点」のみ
- ❌ 創造的な将来展望、妄想的な改善提案は不要
```

### 4.3 Codex足軽（CLI）のtemperature設定

```bash
# scripts/codex_worker.sh の呼び出しオプション（設計案）
claude --model claude-sonnet-4-6 \
  --output-format stream-json \
  --system-prompt "$(cat instructions/ashigaru.md)" \
  # ※ temperature オプションは現在未サポート。
  # 代替: CODEX_TEMPERATURE env var で将来対応予定
```

### 4.4 将来対応のロードマップ

| Phase | 方法 | 対応可能なエージェント |
|-------|------|---------------------|
| 現在 | instructions文書でt相当指示 | 全エージェント |
| 近未来 | kanjou_ginmiyaku Modelfileで設定 | 勘定吟味役 |
| Phase 4 | Claude API経由でtemperature設定 | 外部APIコール時のみ |
| Phase 4+ | agent別Modelfile管理 | 全ollama系エージェント |

---

## 5. 同型アーキテクチャ対応表（統合ビュー）

三階建てが温室・Financeと同型であることの確認:

| 層 | 温室制御 | Finance | shogun | temperature |
|----|---------|---------|--------|:-----------:|
| 上層 | Layer1: 爆発防止(SIL) | daily_risk.py | 3F本店(老中判断) | **t ≈ 0** |
| 中層 | Layer3: 知恵 | Crucix(t=0.6) | 2F合議場 | **t > 0** |
| 下層 | Layer2: ガムテ修理 | composite_alert | 1F支店群(足軽実装) | **t = 0〜** |
| ゲート | -- | Go/NoGo判定 | kenshu_gate | **t = 0** |

**結論**: 三つのシステムすべてが「下層t=0が上層を制約し、中層t>0が創発する」構造を持つ。
これはPOSIX対応（カーネル=決定的/ユーザ空間=自由）と同型でもある。
