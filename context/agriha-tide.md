# TiDE × agriha 温室制御予測層 設計書

> **Version**: 1.0 draft | **Author**: 軍師 | **Date**: 2026-04-02
> **Task**: subtask_1054 (cmd_473) | **Status**: 分析完了

## 1. 背景と課題

### 1.1 現行三層構造の「先読み」ギャップ

```
Layer 1: 爆発（emergency_guard.sh）
  └ 閾値超過で即時全窓全開/全閉。if文+LINE curl
Layer 2: ガムテ（rule_engine.py, cron 10分）
  └ rules.yaml＋変温管理5時間帯＋外気温ベース窓開度テーブル
Layer 3: 知恵（rule_compiler.py, on-demand）
  └ LLMがrules.yamlを矛盾なく再生成。リアルタイム実行ではない
```

**問題**: Layer 2は「今の温度が閾値を超えたか」しか見ない。
「30分後に27℃を超える」と予測して先に窓を開ける能力がない。

殿の過去裁定（2026-03-07）:
> 小型LLMに温度勾配計算や未来予測をさせるのは無理。
> rule_engineで計算してLLMに渡す方式(案B)を採用。
> 計算はガムテ(rule_engine)、判断だけ知恵(LLM)。

→ **TiDEはまさにこの「計算」を担う部品**。LLMでもルールでもない、
学習済みMLPモデルによる時系列予測。殿裁定の案Bと完全に整合する。

### 1.2 TiDEとは何か

| 項目 | 値 |
|------|-----|
| 正式名 | Time-series Dense Encoder (Google Research, 2023) |
| 論文 | arXiv:2304.08424 |
| アーキテクチャ | MLP encoder-decoder（Transformerではない） |
| パラメータ数 | ~1.3M（small）～ ~2.6M（default） |
| メモリ | ~5MB（small）～ ~10MB（default） |
| フレームワーク | TensorFlow 2.10 |
| 推論速度 | Transformer系の5-10倍高速 |
| 共変量サポート | ✅ 未来の既知共変量（天気予報）をネイティブ対応 |
| リポジトリ | google-research/google-research/tide/ |

**農業制御への適合理由:**
- MLPのみ → RPi4での推論が現実的（TFLite/ONNX変換可）
- 共変量 → Open-Meteo天気予報を「未来の既知入力」として自然に注入
- 軽量 → cron実行で十分、デーモン化不要
- オフライン → 学習済みモデルさえあればAPI不要（マクガイバー精神合致）

## 2. 三層構造における位置づけ

### 2.1 案の比較

| 案 | 位置 | 概要 | 利点 | 欠点 |
|----|------|------|------|------|
| **A: Layer 2補強** | ガムテ層の一部 | TiDE予測→rule_engineが読んで先行制御 | 三層構造を壊さない。シンプル | rule_engineのif文に予測を組み込む改修が必要 |
| **B: Layer 3復活** | 知恵層 | 旧forecast_engine.pyの後継としてTiDE予測→LLM判断 | LLMが予測を見て高度な判断可 | 1時間予報方式の復活=v5で廃止した設計への回帰 |
| **C: Layer 2.5新設** | 独立層 | TiDE独立cron→JSON出力→L2とL3両方が参照 | 柔軟 | 層が増える=複雑化。三層思想に反する |
| **D: ONNX RPi直接** | Layer 2内蔵 | TFLite/ONNXでrule_engine.pyに直接組み込み | 最速・最シンプル | TF依存排除の工数。rule_engine.pyが肥大化 |

### 2.2 推奨: 案A（Layer 2補強）

**根拠:**

1. **三層原則「下層が上層を黙らせる」を維持**
   - TiDE予測はLayer 2の「計算」として位置づく
   - Layer 1（爆発）はTiDE予測に関係なく発動する
   - Layer 3（知恵）はrule_compiler実行時に予測結果を参照できる（副次的利益）

2. **殿裁定の案Bと完全合致**
   - 「rule_engineで計算してLLMに渡す」→ TiDEがrule_engineの計算を強化
   - LLMに予測させるのではなく、MLPモデルが予測を出す

3. **マクガイバー精神**
   - 学習はvx2(Ryzen5)で一回やればいい。RPi4には推論だけ
   - 学習済みモデルファイル1つ（~5-10MB）をRPiにコピーすれば動く
   - オフラインで完結（Open-Meteo予報はあれば使う、なくても過去パターンで推論可能）

4. **既存コードへの影響最小**
   - rule_engine.pyに「予測JSONを読んで先行制御する」分岐を追加するだけ
   - forecast_engine.py, rule_compiler.pyは変更不要

### 2.3 データフロー設計

```
                    ┌─────────────────────────────┐
                    │   Open-Meteo API (無料)      │
                    │   気温/湿度/日射/降水予報     │
                    └──────────┬──────────────────┘
                               │ (取得できなければスキップ)
                               ▼
┌──────────────┐    ┌─────────────────────────────┐
│ sensor_log   │───→│   tide_forecaster.py        │
│ (SQLite)     │    │   cron 10分 or 30分          │
│ 温度/湿度/   │    │                             │
│ CO2/日射/    │    │ 1. sensor_logから直近N時間読込│
│ 外気温/風速  │    │ 2. Open-Meteo共変量取得      │
│              │    │ 3. TiDE推論(TFLite/ONNX)    │
└──────────────┘    │ 4. 予測JSON出力              │
                    └──────────┬──────────────────┘
                               │
                               ▼
                    ┌─────────────────────────────┐
                    │ /var/lib/agriha/             │
                    │   tide_forecast.json         │
                    │   {                          │
                    │     "generated_at": "...",   │
                    │     "horizon_hours": 3,      │
                    │     "predictions": {         │
                    │       "temp_inside": [...],  │
                    │       "humidity": [...],     │
                    │       "co2": [...]           │
                    │     },                       │
                    │     "alerts": [              │
                    │       "30分後に27℃超過予測"   │
                    │     ]                        │
                    │   }                          │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                    ▼
          ┌──────────────┐    ┌──────────────────┐
          │ rule_engine  │    │ rule_compiler    │
          │ (Layer 2)    │    │ (Layer 3)        │
          │              │    │                  │
          │ 予測を読んで │    │ 週次レビュー時に │
          │ 先行制御判断 │    │ 予測精度を参照   │
          └──────────────┘    └──────────────────┘
```

## 3. 技術設計

### 3.1 センサーデータ蓄積（Phase 0 — 最優先）

**現状の問題**: センサーデータの時系列ログが存在しない。
sensor_loop.pyはMQTTにpublishするが、永続化されていない。
control_log.dbはLLM判断ログのみ（sensor_snapshotは判断時点の断片）。

**対策: sensor_logger.py 新規作成**

```python
# MQTT subscriber → SQLite time-series logger
# agriha/{house_id}/sensor/DS18B20     → 内気温
# agriha/farm/weather/misol            → 外気温/湿度/風速/降雨/日射
# UECS CCM                            → 内気温/湿度/CO2
#
# テーブル: sensor_log
# |timestamp|source|metric|value|
# |2026-04-02T08:00:00|ccm|temp_inside|23.5|
# |2026-04-02T08:00:00|misol|temp_outside|12.3|
# |2026-04-02T08:00:00|ccm|humidity|72.1|
# |2026-04-02T08:00:00|ccm|co2|410|
# |2026-04-02T08:00:00|misol|solar_radiation|0.45|
```

DB: `/var/lib/agriha/sensor_log.db`
ログ間隔: MQTT受信そのまま（~10秒間隔）。TiDE学習時に1時間平均にリサンプル。

**必要蓄積期間**: 最低6ヶ月（1シーズン）。理想は1年。
→ **今すぐ始めれば2026年10月に最低限、2027年4月に1年分確保**。

### 3.2 Open-Meteo連携

現行: Visual Crossing API（有料、forecast_engine.pyで使用→deprecated）
新規: **Open-Meteo** (無料、APIキー不要)

```
# Open-Meteo Forecast API（無料・APIキー不要）
GET https://api.open-meteo.com/v1/forecast
  ?latitude=42.888&longitude=141.603
  &hourly=temperature_2m,relative_humidity_2m,
          shortwave_radiation,precipitation,wind_speed_10m
  &forecast_days=2
  &timezone=Asia/Tokyo
```

**TiDEへの入力方法:**
- Open-Meteo予報 → `num_cov_cols`（未来の既知数値共変量）として投入
- 取得できない場合（オフライン） → 直近の気象パターンで外挿 or 共変量なしで推論
  （TiDEは共変量なしでも動作する。精度は落ちるがゼロではない）

### 3.3 TiDE学習パイプライン（vx2 Ryzen5で実行）

```bash
# 1. sensor_log.dbからCSVエクスポート（1時間平均にリサンプル）
python3 tools/export_sensor_csv.py \
  --db /var/lib/agriha/sensor_log.db \
  --output data/sensor_hourly.csv \
  --resample 1h

# 2. Open-Meteo過去データをCSVにマージ（共変量）
python3 tools/fetch_openmeteo_history.py \
  --start 2026-04-01 --end 2026-10-01 \
  --output data/weather_hourly.csv

# 3. TiDE学習（vx2上で実行、GPUなしでOK）
python3 tools/train_tide.py \
  --sensor data/sensor_hourly.csv \
  --weather data/weather_hourly.csv \
  --output models/agriha_tide_v1/ \
  --pred_len 6 \        # 6時間先まで予測
  --lookback 48          # 直近48時間の入力
```

**モデル設定（推奨）:**

| パラメータ | 値 | 理由 |
|-----------|-----|------|
| hidden_dims | 128 | RPi4推論を考慮して小さめ |
| num_encoder_layers | 2 | デフォルト。過学習防止 |
| pred_len | 6 | 6時間先（制御に十分な予見） |
| lookback | 48 | 直近2日間のパターン参照 |
| batch_size | 32 | vx2のメモリで余裕 |
| epochs | 100 | early stoppingで調整 |

### 3.4 推論デプロイ（RPi4）

**選択肢:**

| 方式 | サイズ | 依存 | 推論時間(est.) | オフライン |
|------|--------|------|---------------|-----------|
| TFLite | ~2MB | tflite-runtime (pip) | ~50ms | ✅ |
| ONNX Runtime | ~5MB | onnxruntime (pip) | ~30ms | ✅ |
| SavedModel | ~10MB | tensorflow (500MB+) | ~100ms | ✅ |

**推奨: TFLite**
- tflite-runtimeはarm64で~5MB。tensorflowの500MB+をRPi4に入れずに済む
- 推論のみならこれで十分。マクガイバー精神に合致
- ONNX Runtimeも良い候補だが、TFLite→ONNX変換より直接TFLite変換の方が素直

### 3.5 tide_forecaster.py 設計

```python
"""tide_forecaster.py — Layer 2 予測補強モジュール

cron 10分毎に実行。TiDEモデルでN時間先のハウス内環境を予測し、
/var/lib/agriha/tide_forecast.json に出力する。

rule_engine.pyがこのJSONを読んで先行制御に使う。
"""

# 入力:
#   1. sensor_log.db: 直近48時間のセンサーデータ
#   2. Open-Meteo API: 向こう48時間の天気予報（取得失敗時はスキップ）
#   3. models/agriha_tide.tflite: 学習済みTiDEモデル
#
# 出力:
#   /var/lib/agriha/tide_forecast.json
#
# tide_forecast.json schema:
# {
#   "generated_at": "2026-04-02T08:30:00+09:00",
#   "model_version": "agriha_tide_v1",
#   "horizon_hours": 6,
#   "interval_minutes": 60,
#   "predictions": {
#     "temp_inside":  [24.1, 25.3, 26.8, 27.2, 26.5, 24.8],
#     "humidity":     [72, 68, 65, 63, 67, 74],
#     "co2":          [420, 380, 350, 340, 360, 410]
#   },
#   "alerts": [
#     {
#       "metric": "temp_inside",
#       "threshold": 27.0,
#       "predicted_breach_at": "2026-04-02T11:30:00+09:00",
#       "lead_time_min": 180,
#       "message": "3時間後に室温27℃超過予測"
#     }
#   ],
#   "confidence": 0.78,
#   "covariates_available": true
# }
```

### 3.6 rule_engine.py 改修（最小差分）

```python
# rule_engine.py に追加する関数（10行程度）

def load_tide_forecast(
    path: str = "/var/lib/agriha/tide_forecast.json",
    max_age_min: int = 30
) -> dict | None:
    """TiDE予測JSONを読む。古すぎれば無視。"""
    try:
        data = json.loads(Path(path).read_text())
        gen = datetime.fromisoformat(data["generated_at"])
        if (datetime.now(_JST) - gen).total_seconds() > max_age_min * 60:
            return None  # 予測が古い → 使わない
        return data
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None

# 既存の制御ロジック内で:
# forecast = load_tide_forecast()
# if forecast and any(a["metric"] == "temp_inside" for a in forecast.get("alerts", [])):
#     # 閾値超過が予測されている → 先行換気開始
```

### 3.7 forecast_engine.py(§3.7)との関係

| 項目 | forecast_engine.py (v4, deprecated) | tide_forecaster.py (新規) |
|------|-------------------------------------|--------------------------|
| 予測方式 | LLM (Claude Haiku/NullClaw) | TiDE (学習済みMLP) |
| 実行頻度 | cron 1時間毎 | cron 10-30分毎 |
| 入力 | センサー+Visual Crossing+判断履歴 | sensor_log+Open-Meteo |
| 出力 | current_plan.json (アクション計画) | tide_forecast.json (予測値のみ) |
| 判断 | LLMが制御アクションまで決定 | 予測のみ。判断はrule_engineが行う |
| コスト | API課金 or NullClawリソース | ゼロ（学習済みモデル推論のみ） |
| オフライン | NullClawなら可 | 完全オフライン可 |

**決定的な違い**: forecast_engine.pyは「予測+判断」を一体化していた（LLMが制御を決める）。
tide_forecaster.pyは「予測だけ」を出す。判断はrule_engine.pyの責務。
→ **三層原則に忠実。計算と判断の分離**。

## 4. 実装フェーズ

### Phase 0: センサーログ基盤（即着手可、足軽1名・半日）
- sensor_logger.py: MQTT subscriber → sensor_log.db
- systemdサービス化（RPi4上で常時稼働）
- **これがないとPhase 1以降が全て止まる。最優先。**

### Phase 1: データ蓄積期間（6ヶ月放置）
- sensor_logger.pyを動かしてデータを貯める
- 並行: Open-Meteo過去データ取得ツール作成（足軽1名・半日）
- 並行: ArSprout 2025実績データがCSVで取れるなら先行学習に使える

### Phase 2: TiDE PoC（vx2で学習、足軽1名・1日）
- export_sensor_csv.py: sensor_log.db → CSV変換
- train_tide.py: TiDE学習スクリプト
- eval_tide.py: 予測精度評価（RMSE, MAE, threshold breach detection rate）
- **PDCA候補**: 予測精度が実用レベルに達するか検証が必要

### Phase 3: RPi4デプロイ（足軽1名・半日）
- TFLite変換
- tide_forecaster.py: 推論cron
- rule_engine.py改修: 予測JSON読み込み+先行制御分岐

### Phase 4: 運用+改善（継続）
- 予測精度モニタリング
- 季節変化時のモデル再学習（シーズン終了後）
- rule_compiler.pyのレビュー時にTiDE精度情報を参照する拡張（任意）

## 5. リスクと見落としの可能性

| リスク | 影響 | 対策 |
|--------|------|------|
| センサーデータ6ヶ月は長すぎて待てない | Phase 2開始が2026年10月以降に | ArSprout過去データで先行PoC。または合成データで構造検証 |
| TFLite ARM64互換性 | RPi4で動かない可能性 | tflite-runtime ARM64 wheelは公式提供あり。事前検証をPhase 0に含める |
| Open-Meteo API信頼性 | 天気予報が取れない時の精度低下 | 共変量なし推論のフォールバック実装。TiDEは共変量optional |
| TF 2.10の保守性 | 将来のPython/OS更新で壊れる | ONNX変換を代替パスとして確保 |
| ハウス容積・品種変更 | 学習データが無効化 | transfer learning or 再学習パイプライン |
| **予測が外れた時の先行制御暴走** | 窓を開けすぎ/閉めすぎ | **Layer 1が黙らせる**。TiDE予測は「提案」、最終判断はrule_engine閾値 |

## 6. 冒険的な案: TiDE + 生育ステージ推定

殿の仮説（Memory MCP記録）:
> 灌水量/日射比の移動平均 ≈ 蒸散係数 ≈ 葉面積プロキシ ≈ ステージ進行

TiDEの共変量に生育ステージ推定値を組み込めば、ステージ別の温度予測が可能になる。
sensor_logger.pyに灌水ログ（relay ON/OFF + duration）を追加すれば、
1年後に「灌水量/日射比 → ステージ → 温度目標」の連鎖予測ができる可能性がある。

**…少し冒険的だが面白い。** ただし排水センサー(SEN0575)のデータが前提。
Phase 4以降の拡張候補として記録しておく。
