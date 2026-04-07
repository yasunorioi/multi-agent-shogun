# TurboQuant MBP ollama高速化 偵察報告書

> **cmd_468 / subtask_1047+1048** | 軍師分析 | L5 評価 | 2026-03-30
> ~~**判定: Wait** — llama.cpp本流未マージ、ollama未対応。~~ → **§9で判定見直し: Go（条件付き）**
> **判定: Go（条件付き）** — turboquant_plus v1 Complete + llama-server直接実行でCrucix接続可（改修3行）

---

## §1. TurboQuantとは何か（致命的な誤解の訂正）

### 重要: KVキャッシュ圧縮であり、モデル重み量子化ではない

| 項目 | TurboQuant | 通常のGGUF量子化(Q4_K_M等) |
|------|-----------|---------------------------|
| 圧縮対象 | **推論時のKVキャッシュ（VRAM上）** | **モデルの重みパラメータ（ファイル）** |
| 適用タイミング | 推論中（ランタイム） | モデル変換時（事前処理） |
| ファイルサイズ | **変わらない** | 小さくなる |
| メモリ効果 | 長コンテキスト時のVRAM消費削減 | モデルロード時のメモリ削減 |
| 速度効果 | 長コンテキスト時のデコード高速化 | モデルロード高速化 |

**「22GB→4GB」は誤り。** TurboQuantを適用しても:
- GGUFファイルサイズ: **22GB のまま**
- モデルロードメモリ: **22GB のまま**
- KVキャッシュ（推論時の追加メモリ）: FP16比 **3.8〜6.4倍圧縮**

つまり、gpt-oss-fin-thinking 22GBモデルは22GBのまま。恩恵は**長文推論時のKVキャッシュメモリ削減**。

### 論文情報

- **タイトル**: TurboQuant: Online Vector Quantization of Key-Value Caches
- **著者**: Google Research (Zandieh et al.)
- **発表**: ICLR 2026 (2026-04-23〜25 正式発表予定)
- **手法**: ランダム化アダマール変換 + Lloyd-Max スカラー量子化
- **圧縮率**: TQ2(2bit, 6.4x) / TQ3(3bit, 4.6x) / TQ4(4bit, 3.8x) — いずれもFP16比

---

## §2. llama.cpp 実装状況

### 本流(ggml-org/llama.cpp): 未マージ

| ステータス | 詳細 |
|-----------|------|
| Issue | [#20977](https://github.com/ggml-org/llama.cpp/issues/20977) Feature Request |
| Discussion | [#20969](https://github.com/ggml-org/llama.cpp/discussions/20969) 活発な議論 |
| マージ状態 | **未マージ。Q3 2026ロードマップ** |
| 公式コード | Google未公開。ICLR 2026発表後に期待 |

### コミュニティフォーク一覧

| フォーク | Metal対応 | 完成度 | URL |
|---------|:---------:|:------:|-----|
| **TheTom/turboquant_plus** | **◎** | 高 | [GitHub](https://github.com/TheTom/turboquant_plus) |
| TheTom/llama-cpp-turboquant | ◎ | 中 | [GitHub](https://github.com/TheTom/llama-cpp-turboquant) |
| Aaryan-Kapoor/llama.cpp (tq3_0) | × (CPU only) | 低 | [GitHub](https://github.com/Aaryan-Kapoor/llama.cpp/tree/turboquant-tq3_0) |
| spiritbuun/llama-cpp-turboquant-cuda | × (CUDA only) | 中 | [GitHub](https://github.com/spiritbuun/llama-cpp-turboquant-cuda) |
| ikawrakow/ik_llama.cpp #1509 | × (CPU only) | 中 | [GitHub](https://github.com/ikawrakow/ik_llama.cpp/issues/1509) |

**最有力**: `turboquant_plus` — Apple Silicon Metal対応、turbo2/3/4全対応、ベンチマーク実績あり。

---

## §3. 0xSero/turboquant (vLLM統合)

vLLM版TurboQuantは**CUDA前提**。Apple Silicon非対応。

| 判定項目 | 評価 |
|----------|:----:|
| Apple Silicon対応 | **×** — vLLMはCUDA/ROCmのみ |
| MBPで動作 | **NoGo** |
| 根拠 | vLLMはGPUサーバ向け。Metal未対応。MBP M4 Proでは動作不可 |

---

## §4. gpt-oss-fin-thinking への適用可能性

### モデルアーキテクチャ

gpt-oss-fin-thinkingはNRI(野村総研)によるgpt-oss-20bの金融ファインチューン。ベースアーキテクチャ:

| 項目 | 値 |
|------|-----|
| ベースモデル | OpenAI gpt-oss-20b |
| アーキテクチャ | Transformer + **MoE** (32 experts, Top-4 routing) |
| 総パラメータ | 21B (アクティブ 3.6B/token) |
| レイヤー数 | 24 |
| Attention | **GQA** (Grouped Multi-Query Attention, group size 8) |
| 位置エンコーディング | RoPE |
| 活性化関数 | SwiGLU |
| コンテキスト長 | 128K (ネイティブ) |
| 現在の量子化 | **Q8_0** (GGUF, 22GB) |
| 重み量子化 | MoE層はMXFP4 (4.25bit/param) |

### TurboQuant互換性

| 項目 | 判定 | 備考 |
|------|:----:|------|
| GQA対応 | ◎ | TurboQuantはattention head単位。GQA互換 |
| MoE対応 | ◎ | KVキャッシュ圧縮はMoE/Dense関係なく適用可能 |
| RoPE互換 | ◎ | 位置エンコーディングはKVキャッシュ前段。干渉なし |
| Q8_0 GGUF読み込み | ◎ | TurboQuantは推論時適用。既存GGUF変更不要 |
| **K/V非対称リスク** | **要注意** | Q8_0はまだ安全だが、MoEモデルのK精度劣化報告あり |

### K/V非対称問題（重大な知見）

TurboQuantの最大の罠: **KとVで必要な精度が異なる**。

- K(key)は精度要求が高い → q8_0推奨
- V(value)は圧縮耐性が高い → turbo3/turbo4で可
- **対称圧縮(turbo3/turbo3)は低bit重みモデルで破綻する報告あり**
  - Qwen2.5-7B Q4_K_M: PPL 6.6 → **3556** (壊滅)

gpt-oss-fin-thinkingはQ8_0なので比較的安全だが、**必ず非対称設定で開始すべき**:

```
--cache-type-k q8_0 --cache-type-v turbo4   # 最安全
--cache-type-k q8_0 --cache-type-v turbo3   # 圧縮優先
```

### 既存TQ3 GGUF公開状況

HuggingFaceで `gpt-oss-fin-thinking TQ3` `turboquant` 検索: **該当なし**。
TurboQuantはGGUFファイル自体を変えるものではないため、TQ3_0量子化済みGGUFという概念は存在しない。

### TurboQuant適用時のメモリ推定

gpt-oss-fin-thinking Q8_0 (22GB) + KVキャッシュ:

| コンテキスト長 | KV FP16 | KV turbo4 | KV turbo3 | 節約量 |
|:-----------:|:-------:|:---------:|:---------:|:------:|
| 4K | ~0.5GB | ~0.13GB | ~0.11GB | ~0.4GB |
| 16K | ~2.0GB | ~0.53GB | ~0.43GB | ~1.6GB |
| 32K | ~4.0GB | ~1.05GB | ~0.87GB | ~3.1GB |
| 128K | ~16.0GB | ~4.2GB | ~3.5GB | ~12.5GB |

**MBP 48GB での意味**: モデル22GB + KVキャッシュ。FP16だと32Kで26GB、128Kで38GB。
TurboQuant(turbo3)なら128Kで25.5GB — **128Kコンテキストが実用範囲に入る**。

これは速度改善ではなく**コンテキスト長の壁を突破する恩恵**。

---

## §5. Go/Wait/NoGo 判定

### 判定基準と結果

| # | 基準 | 判定 | 根拠 |
|---|------|:----:|------|
| 1 | llama.cpp本流にマージ済みか | **×** | Q3 2026ロードマップ。未マージ |
| 2 | ollamaに降りているか | **×** | llama.cppマージ後に対応予定 |
| 3 | forkで動作実績あるか | **○** | turboquant_plus: M系Metal動作確認済み |
| 4 | 既存GGUFをそのまま使えるか | **○** | ランタイム適用。GGUF変更不要 |
| 5 | Crucixパイプラインを壊さないか | **×** | ollama非対応のため、llama-server直接利用が必要 |
| 6 | コンテキスト長延伸効果があるか | **◎** | 128Kが実用範囲に入る |
| 7 | 速度改善効果があるか | **△** | 短コンテキストでは効果薄。長コンテキストで改善 |

### 総合判定: **Wait**

```
 Go    — 今すぐ試せる        → 該当しない
[Wait] — 条件が揃えば試せる  → ★ これ
 NoGo  — 見込みなし          → 該当しない
```

**Wait理由**:
1. **ollama未対応**が最大の障壁。現在のCrucix cronは `ollama /api/generate` を使用。TurboQuantを使うには `llama-server --cache-type-v turbo3` に切り替えが必要で、Crucixパイプラインの書き換えが発生する
2. **forkビルドは技術的に可能**だが、本流マージ前のfork追従は保守コストが高い
3. **恩恵が限定的**: 現在のCrucix用途（短プロンプト→短回答）ではKVキャッシュは小さく、TurboQuantの効果はほぼない。恩恵が出るのは**16K+の長コンテキスト**利用時

**Wait解除条件**:
- **条件A**: llama.cpp本流にTurboQuantマージ → ollamaに降りる → `ollama run --cache-type-v turbo3` が使える（**Q3 2026見込み、あと3-4ヶ月**）
- **条件B**: 長コンテキスト利用ニーズが発生（EDINET有報全文解析等）→ 恩恵が明確になる

### 「今すぐ試したい」場合の代替案

forkビルドで**実験だけ**は可能:

```bash
# MBPでturboquant_plusをビルド
git clone https://github.com/TheTom/turboquant_plus.git
cd turboquant_plus
cmake -B build -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

# llama-serverで起動（ollamaを経由しない）
./build/bin/llama-server \
  -m ~/models/gpt-oss-fin-thinking-Q8_0.gguf \
  --cache-type-k q8_0 --cache-type-v turbo3 \
  -c 32768 --port 8081
# → http://localhost:8081/v1/chat/completions

# ベンチマーク
./build/bin/llama-perplexity -m model.gguf --cache-type-v turbo3
```

ただし:
- Crucix cronとは別系統（ollama APIではなくOpenAI互換API）
- 実験後に元のollama運用に戻すのは容易
- **殿がやる場合15分、足軽にやらせる場合1-2時間**

---

## §6. トレードオフ比較

### 比較1: TurboQuant導入タイミング

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| A. 今すぐforkビルド | 実験データ取得可、先行者利益 | fork保守コスト、Crucix書き換え、本流マージで二度手間 | 4 |
| **B. Q3 2026のollama統合待ち** | ゼロコスト、Crucix変更なし、安定 | 3-4ヶ月待ち | **8** |
| C. 見送り(NoGo) | コストゼロ | 128K利用の選択肢を失う | 5 |

### 比較2: 長コンテキスト対応戦略

| 案 | 利点 | 欠点 | スコア |
|----|------|------|:------:|
| A. TurboQuant (Wait) | KVキャッシュ圧縮で128K実用化 | ollama未対応 | 7 |
| **B. 現状維持(16K)** | 変更なし、Crucix安定 | 長文解析不可 | **7** |
| C. モデル軽量化(Q4_K_M) | 22GB→8GB、KV含め余裕 | 品質劣化リスク（金融LLMには致命的） | 3 |

---

## §7. リスク分析

| # | リスク | 影響度 | 対策 |
|---|--------|:------:|------|
| 1 | K/V非対称問題でMoEモデル品質劣化 | 高 | 必ず `q8_0-K + turbo-V` 非対称設定。対称turbo3/turbo3は禁止 |
| 2 | forkビルドが本流マージ時に互換性喪失 | 中 | Wait判定でfork利用を避ける |
| 3 | ollama統合がQ3 2026より遅延 | 低 | 影響なし（現状で運用可能） |
| 4 | gpt-oss-fin-thinkingのMoE構造とTQ相性問題 | 中 | 本流マージ後のコミュニティ検証結果を待つ |
| 5 | 「22GB→4GB」の期待と実態の乖離 | 低 | 本報告書で訂正済み。KVキャッシュ圧縮であると周知 |

---

## §8. 推奨アクション（subtask_1047時点）

~~1. **即座**: 何もしない。Wait判定。~~
~~2. **Q3 2026(7-9月)**: llama.cpp本流マージを監視~~

**↓ subtask_1048で判定見直し。§9以降を参照。**

**監視対象**:
- [ggml-org/llama.cpp #20977](https://github.com/ggml-org/llama.cpp/issues/20977) — Feature Request
- [ggml-org/llama.cpp Discussion #20969](https://github.com/ggml-org/llama.cpp/discussions/20969) — 実装議論
- [ollama/ollama #15051](https://github.com/ollama/ollama/issues/15051) — ollama TurboQuant Issue

---

## §9. 追加偵察: TheTom/turboquant_plus 詳細調査（subtask_1048）

> **判定見直し: Wait → Go（条件付き）**
> turboquant_plus v1 Complete + Metal kernel + MoE検証済み + llama-server OpenAI互換API

### 9.1 turboquant_plus リポジトリ詳細

| 項目 | 値 |
|------|-----|
| リポ | [TheTom/turboquant_plus](https://github.com/TheTom/turboquant_plus) |
| Stars | **672** |
| ステータス | **v1 Complete, Speed Optimized, Community-Tested** |
| ライセンス | MIT（llama.cpp準拠） |
| テスト | 141 tests pass |
| Metal kernel | turbo2/turbo3/turbo4 全対応。世代別自動最適化（M1-M4: 4-mag LUT、M5: 専用パス） |
| Sparse V | Attention-gated dequant（softmax < 1e-6 をスキップ、+22.8% decode速度@32K） |

### 9.2 ベンチマーク（公式README）

**品質（wikitext-2, 512 context, PPL）:**

| キャッシュ設定 | PPL | vs q8_0 |
|---------------|:---:|:-------:|
| q8_0 (baseline) | 6.112 | — |
| **turbo4** | **6.125** | **+0.23%** |
| **turbo3** | **6.176** | **+1.06%** |
| turbo2 | 6.507 | +6.48% |

**速度（M5 Max, Qwen3.5-35B-A3B MoE decode）:**

| キャッシュ設定 | tok/s | vs q8_0 |
|---------------|:-----:|:-------:|
| q8_0 | 68.2 | 1.00x |
| **turbo4** | **63.7** | **0.93x** |
| turbo3 | 53.3 | 0.78x |

**長コンテキスト（32K, wikitext-103）:**

| 設定 | 効果 |
|------|------|
| turbo3 + Sparse V | decode +22.8%、PPL変化なし(Δ=0.0000) |

### 9.3 K/V対称 vs 非対称の安全性再評価

**前回の懸念**: 「対称turbo3/turbo3はMoEモデルで破綻リスク」

**再評価結果**:

| モデル | 重み量子化 | 対称turbo3/turbo3 | 非対称q8_0-K/turbo-V | 結論 |
|--------|:---------:|:-----------------:|:-------------------:|------|
| Qwen2.5-7B | **Q4_K_M** | PPL 3556 (壊滅) | PPL +1% (安全) | 低bit重みで対称は危険 |
| Qwen3.5-35B-A3B **MoE** | Q8_0 | PPL +1.06% (安全) | PPL +0.23% (最安全) | **Q8_0なら対称でも安全** |

**結論**: 前回の壊滅報告は**Q4_K_M（低bit重み量子化）固有の問題**。gpt-oss-fin-thinkingは**Q8_0**であり、対称turbo3/turbo3でもPPL劣化+1%で安全。ただし最安全は非対称turbo4-K/turbo4-V。

**推奨設定**:

```
# 安全優先（品質劣化+0.23%）
--cache-type-k turbo4 --cache-type-v turbo4

# 圧縮優先（品質劣化+1.06%）
--cache-type-k turbo3 --cache-type-v turbo3
```

金融LLMは精度重視 → **turbo4/turbo4 推奨**。

### 9.4 ollama統合可否（3パターン評価）

| パターン | 方式 | 判定 | 理由 |
|----------|------|:----:|------|
| A. ollamaバックエンド差し替え | turboquant_plus版llama.cppでollamaをリビルド | **×** | ollamaはGo独自エンジン移行中。llama.cpp単純差し替え不可 |
| B. Modelfile指定 | `PARAMETER cache_type turbo3` | **×** | ollamaにcache_typeパラメータなし |
| **C. llama-server直接起動** | ollama停止 → llama-server起動 → 同ポートで提供 | **◎** | **OpenAI互換API提供。最小改修で接続可** |

**結論: パターンC一択。ollama統合は不要。llama-serverに乗り換える。**

### 9.5 Crucix接続の最小改修設計

**現状（ollama）:**

```
Crucix cron_ideas.sh
  → curl http://localhost:11434/api/generate
    POST { "model": "gpt-oss-fin-thinking", "raw": true, "prompt": "...<|channel|>final<|message|>..." }
  ← { "response": "..." } (streaming NDJSON)
```

**改修後（llama-server）:**

```
llama-server (port 11434 or 8081)
  → curl http://localhost:8081/completion
    POST { "prompt": "...<|channel|>final<|message|>...", "temperature": 0.6, "n_predict": 4096 }
  ← { "content": "..." } (single JSON)
```

**差分**:

| 項目 | ollama /api/generate | llama-server /completion |
|------|---------------------|------------------------|
| URL | `localhost:11434/api/generate` | `localhost:8081/completion` |
| リクエスト | `{"model":"...", "raw":true, "prompt":"..."}` | `{"prompt":"...", "temperature":0.6}` |
| レスポンス | streaming NDJSON `{"response":"..."}` | single JSON `{"content":"..."}` |
| 変更量 | — | **curlコマンド3行変更** |

**cron_ideas.sh の改修イメージ**:

```bash
# Before (ollama)
RESPONSE=$(curl -s http://localhost:11434/api/generate \
  -d "{\"model\":\"gpt-oss-fin-thinking\",\"raw\":true,\"prompt\":\"$PROMPT\"}" \
  | jq -r '.response // empty' | tr -d '\n')

# After (llama-server)
RESPONSE=$(curl -s http://localhost:8081/completion \
  -d "{\"prompt\":\"$PROMPT\",\"temperature\":0.6,\"n_predict\":4096}" \
  | jq -r '.content // empty')
```

**改修規模: 3-5行。破壊的変更なし。ロールバックは`ollama serve`再起動のみ。**

### 9.6 MBP即時実験手順（Go判定時）

```bash
# ═══ Step 1: turboquant_plus ビルド (5分) ═══
cd ~
git clone https://github.com/TheTom/llama-cpp-turboquant.git
cd llama-cpp-turboquant
git checkout feature/turboquant-kv-cache
cmake -B build -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)

# ═══ Step 2: ollama停止 (10秒) ═══
# Crucix cronを一時停止
crontab -l > /tmp/crontab_backup.txt
crontab -r  # 全cron停止（安全のため）
launchctl stop com.ollama.ollama 2>/dev/null  # ollamaサービス停止
# または
pkill ollama

# ═══ Step 3: llama-server起動 (30秒) ═══
# gpt-oss-fin-thinking GGUFのパスを確認
GGUF_PATH=$(find ~/.ollama/models -name "*.gguf" -path "*fin-thinking*" | head -1)
# 見つからない場合: ollama show gpt-oss-fin-thinking --modelfile で確認

./build/bin/llama-server \
  -m "$GGUF_PATH" \
  -ngl 99 -c 16384 -fa \
  --cache-type-k turbo4 --cache-type-v turbo4 \
  --host 127.0.0.1 --port 8081

# ═══ Step 4: 動作確認 (1分) ═══
# テスト1: 基本応答
curl -s http://localhost:8081/completion \
  -d '{"prompt":"日経平均株価について簡潔に説明せよ。","temperature":0.6,"n_predict":200}' \
  | jq '.content'

# テスト2: gpt-oss thinking format（Crucix互換）
curl -s http://localhost:8081/completion \
  -d '{"prompt":"<|channel|>final<|message|>以下のデータを分析せよ: USD/JPY 150.23","temperature":0.6,"n_predict":500}' \
  | jq '.content'

# テスト3: メモリ確認
# Activity Monitor → llama-server のメモリ使用量確認
# 期待値: ~22GB (モデル) + 最小KVキャッシュ

# ═══ Step 5: ベンチマーク (5分) ═══
./build/bin/llama-perplexity \
  -m "$GGUF_PATH" -ngl 99 -fa \
  --cache-type-k turbo4 --cache-type-v turbo4 \
  -c 2048

# ═══ Step 6: ロールバック (10秒) ═══
# llama-serverを停止 (Ctrl+C)
# ollama再起動
ollama serve &
# cron復元
crontab /tmp/crontab_backup.txt
```

**所要時間: 約15分（ビルド5分 + テスト10分）**

### 9.7 ollama GGUFファイルの所在

ollamaはGGUFを独自ディレクトリに保存:

```bash
# macOS
~/.ollama/models/blobs/
# ファイル名はsha256ハッシュ。元のGGUFファイル名はない

# 確認方法
ollama show gpt-oss-fin-thinking --modelfile
# → FROM /path/to/blob が表示される
```

llama-serverにはこのblobパスをそのまま渡せる。

### 9.8 長期運用設計（実験成功後）

| 項目 | ollama運用（現行） | llama-server運用（移行後） |
|------|-------------------|--------------------------|
| 起動 | `ollama serve` (launchd) | `llama-server ...` (launchd plist) |
| モデル管理 | `ollama pull/show` | GGUF手動管理 |
| API | `/api/generate` (独自) | `/completion` + `/v1/chat/completions` (OpenAI互換) |
| KVキャッシュ | FP16固定 | **turbo4/turbo3選択可** |
| コンテキスト | Modelfile指定 | `-c` フラグ |
| GPU offload | 自動 | `-ngl 99` |

**launchd plist案（実験成功後に作成）:**

```xml
<!-- ~/Library/LaunchAgents/com.systrade.llama-server.plist -->
<plist version="1.0">
<dict>
  <key>Label</key><string>com.systrade.llama-server</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/llama-server</string>
    <string>-m</string><string>/path/to/model.gguf</string>
    <string>-ngl</string><string>99</string>
    <string>-c</string><string>16384</string>
    <string>-fa</string>
    <string>--cache-type-k</string><string>turbo4</string>
    <string>--cache-type-v</string><string>turbo4</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8081</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
```

### 9.9 Go/Wait/NoGo判定見直し

| # | 判定基準 | subtask_1047 | **subtask_1048** | 変化理由 |
|---|---------|:----------:|:----------------:|---------|
| 1 | llama.cpp本流マージ済み | × | × (変化なし) | — |
| 2 | ollama対応 | × | × (変化なし) | — |
| 3 | **forkで本番動作実績** | ○ | **◎** | v1 Complete, 672 stars, 141 tests, MoE検証済み |
| 4 | 既存GGUF利用可 | ○ | ◎ (変化なし) | — |
| 5 | **Crucixパイプライン接続** | × | **◎** | llama-server /completion API、**改修3-5行** |
| 6 | コンテキスト延伸 | ◎ | ◎ (変化なし) | — |
| 7 | **品質劣化許容範囲** | △(不明) | **◎** | turbo4: +0.23%, turbo3: +1.06% 検証済み |
| 8 | **MoE安全性** | △(懸念) | **◎** | Qwen3.5-35B-A3B MoE Q8_0で検証済み |

### 総合判定: **Go（条件付き）**

```
 前回: Wait  — ollama統合待ち
 今回: [Go]  — llama-server直接実行で即時利用可能 ★
```

**Go条件**:
1. MBPでturboquant_plusビルドが成功すること（M4 Proは検証対象内）
2. gpt-oss-fin-thinking Q8_0 GGUFでllama-serverが正常起動すること
3. `/completion` APIでCrucix互換の応答が返ること

**Wait→Go変更の決定的理由**:
1. Crucix接続がcurl 3行変更で済むことが判明（ollama統合不要）
2. turboquant_plus v1 Completeで品質・安定性が検証済み
3. MoE + Q8_0での対称turbo4/turbo4がPPL +0.23%で安全と確認
4. ロールバックが`ollama serve`再起動のみで即座に可能

### 9.10 リスク分析（追加）

| # | リスク | 影響度 | 対策 |
|---|--------|:------:|------|
| 8 | turboquant_plus forkの保守停滞 | 中 | llama.cpp本流マージ(Q3 2026)後に正式版に移行。forkは実験期間のみ |
| 9 | ollama GGUFのblob形式が非標準 | 低 | `ollama show --modelfile`でパス取得可。そのままllama-serverに渡せる |
| 10 | cron停止忘れでollama/llama-server競合 | 中 | 実験手順にcron停止を明記。ポート番号をずらす(8081)ことでも回避可 |
| 11 | M4 ProがM5 Maxと異なるMetal挙動 | 低 | turboquant_plusはM1-M5自動検出。M4は4-mag LUTパス使用 |
| 12 | gpt-oss-fin-thinking固有のchat template非互換 | 中 | `<\|channel\|>final` formatはraw promptなので/completionに直接渡せる |

### 9.11 推奨アクション（改訂）

1. **即座**: 殿がMBPで §9.6 の実験手順を実行（15分）
2. **実験成功時**: Crucix cron_ideas.sh の3行改修（§9.5）
3. **安定確認後**: launchd plistでllama-server自動起動化（§9.8）
4. **Q3 2026**: llama.cpp本流マージ時にfork→正式版に切り替え
5. **ollama完全廃止は不要**: 他モデル利用時はollamaを別ポートで併用可
