# 獏×部屋子×お針子 夢見自動解釈パイプライン設計書

> **subtask_id**: subtask_895 | **cmd_id**: cmd_405 | **date**: 2026-03-14
> **North Star**: 夢を蔵書に変える。広く拾い、賢く選び、安く回す

---

## §0 エグゼクティブサマリ

**推奨: 案B — baku.py内から直接Haiku APIを叩く。部屋子ペイン不要。**

- トリガー: baku.pyのdream_once()内でHaiku APIを直接呼び出し（重複排除後）
- 選別: Sonnet層はcron日次バッチ（dream.pyサマリ生成と統合）
- 蔵書化: 没日録DBのdashboard_entries（section="dream_library"）に蓄積
- 月額コスト: **$1.44（全件Haiku）〜 $3.06（+50% Sonnet選別）**
- 重複排除適用時: **$0.42/月**（31/106=70.8%が重複）
- $8予算に対して**大幅な余裕**あり

---

## §1 トリガー機構の設計判断（最重要）

### 3案の比較

| | 案A: send-keys部屋子 | **案B: baku.py直接API** | 案C: cronバッチ |
|---|---|---|---|
| 仕組み | baku→tmux send-keys→部屋子ペイン | baku.py内でHaiku API直叩き | 別cronで定期的に未処理夢をバッチ |
| コスト/件 | Claude Code料金（高い） | Haiku API直接（$0.002/件） | Haiku API直接（同左） |
| ペイン占有 | 部屋子ペインを占有 | なし（baku.pyプロセス内） | なし |
| 実装複雑性 | 中（send-keys+YAML通信） | **低**（httpx 1関数追加） | 中（別スクリプト+状態管理） |
| レイテンシ | 分単位（ペイン起動待ち） | 秒（API直叩き） | 時間単位（次cron実行まで） |
| 既存整合 | shogunの通信プロトコル準拠 | **forecast_engine.pyと同パターン** | dream.pyと統合可能 |
| リスク | ペイン不在時に失敗 | API key管理が必要 | バッチ遅延 |

### 判定: **案B推奨**

**根拠:**
1. **コスト**: Claude Code経由（案A）は1件あたりの料金がAPI直叩き（案B）の数倍〜十数倍。月720件では差が大きい
2. **既存パターン**: forecast_engine.pyが既にOpenAI SDK互換でHaiku APIを叩いている。同じパターンを踏襲すれば実装コスト最小
3. **ペイン占有なし**: 部屋子ペインは他タスクに使える。獏の夢解釈に占有するのは勿体無い
4. **マクガイバー精神**: 最もシンプルな構成。baku.py内に関数1つ追加するだけ

### 案Bの実装設計

```python
# baku.py に追加する interpret_dream() 関数

import httpx

HAIKU_BASE_URL = os.getenv("HAIKU_BASE_URL", "https://api.anthropic.com")
HAIKU_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-5-20251001"

async def interpret_dream(dream: dict, context_snippet: str = "") -> dict | None:
    """Haiku APIで夢を解釈する。API key未設定時はスキップ。"""
    if not HAIKU_API_KEY:
        return None  # NullClawモード: 解釈なし

    system_prompt = """あなたは獏に取り憑かれた部屋子でございます。
夢うつつの中、ネットの海から拾い上げた情報を、
殿のお仕事に役立つかどうか、ぼんやりと判断いたします。

以下の観点で夢を解釈してくださいませ:
1. relevance: 殿の現在のプロジェクトとの関連度 (high/medium/low/none)
2. connection: 既存の蔵書・知見との接続点
3. insight: この夢から得られる知見（あれば）
4. action: 推奨アクション (archive/investigate/ignore)

JSON形式で出力してください。"""

    user_msg = f"""## 夢データ
ドメイン: {dream.get('domain', '?')}
クエリ: {dream.get('query', '?')}
外部検索結果: {dream.get('external_result', '')[:400]}

## 直近の殿のお仕事（参考）
{context_snippet[:500]}"""

    try:
        # OpenAI SDK互換パターン（forecast_engine.pyと同じ）
        from openai import OpenAI
        client = OpenAI(
            base_url=f"{HAIKU_BASE_URL}/v1",
            api_key=HAIKU_API_KEY,
        )
        response = client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        result_text = response.choices[0].message.content
        # JSONパース試行
        import re as _re
        json_match = _re.search(r'\{.*\}', result_text, _re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"raw_interpretation": result_text}
    except Exception as e:
        print(f"  WARN: 夢解釈失敗: {e}", file=sys.stderr)
        return None
```

### 重複排除の組み込み

```python
def dream_once(manual_topic=None):
    # ... 既存の検索処理 ...

    for q in queries:
        # 検索実行
        external = search_ddg(q["query"])
        internal = search_kousatsu(q["query"])

        dream_entry = { ... }  # 既存の夢エントリ生成

        # ★ 重複排除: 6時間以内に同じクエリの解釈済み夢があればスキップ
        if q["query"] not in recent_interpreted_queries:
            # Haiku解釈
            context = get_recent_cmd_summary()  # 直近cmdサマリ
            interpretation = interpret_dream(dream_entry, context)
            if interpretation:
                dream_entry["interpretation"] = interpretation
                dream_entry["status"] = "interpreted"
                dream_entry["interpreted_at"] = datetime.now().isoformat()

        save_dream(dream_entry)
```

---

## §2 部屋子の夢解釈（Haiku層）

### 2.1 入力設計

| 要素 | トークン数（概算） | 内容 |
|------|----------------|------|
| system_prompt | ~200 tok | 獏に取り憑かれた部屋子の口調+判定基準 |
| 夢データ | ~300 tok | domain, query, external_result(400字切り詰め) |
| コンテキスト | ~500 tok | 直近7日のcmdタイトル一覧（get_recent_keywords()の出力を再利用） |
| **合計入力** | **~1,000 tok** | |
| 出力 | ~300 tok | JSON: relevance, connection, insight, action |

### 2.2 蔵書コンテキストの渡し方

**推奨: 直近cmdタイトル一覧（軽量・動的）**

全context/*.mdを渡すのはトークン過剰（数千〜数万トークン）。
baku.pyが既に持っているget_recent_keywords()の出力（直近7日のcmdキーワード上位20）を
文字列化して渡す。Haikuは「このキーワード群と夢の関連性」を判定するだけでよい。

```python
def get_recent_cmd_summary() -> str:
    """直近7日のcmdタイトル一覧を返す（コンテキスト注入用）"""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    rows = conn.execute(
        "SELECT id, command, project FROM commands "
        "WHERE created_at > ? ORDER BY created_at DESC LIMIT 15",
        (cutoff,),
    ).fetchall()
    conn.close()
    return "\n".join(f"- [{r[2]}] {r[0]}: {r[1]}" for r in rows)
```

### 2.3 出力フォーマット

```json
{
  "relevance": "high",
  "connection": "cmd_399(RPi5エッジLLM)と直接関連。蒸留の具体的手法が含まれる",
  "insight": "QLoRA fine-tuningが1B-3Bモデルで実用的な精度を達成している知見",
  "action": "archive",
  "tags": ["llm_edge", "distillation", "rpi5"]
}
```

| actionの値 | 意味 | 後続処理 |
|-----------|------|---------|
| `archive` | 蔵書化候補 | Sonnet選別へ |
| `investigate` | 深掘り調査推奨 | Sonnet選別へ（優先度高） |
| `ignore` | 殿のお仕事に無関係 | ここで終了 |

### 2.4 system_promptの設計（獏が取り憑いた部屋子の口調）

```
あなたは獏に取り憑かれた部屋子でございます。
夢うつつの中、ネットの海から拾い上げた情報を、
殿のお仕事に役立つかどうか、ぼんやりと判断いたします。

殿は農業IoT・LLMエッジ推論・マルチエージェントシステムを手がけておられます。
月額忌避・マクガイバー精神（シンプル・ローコスト）がお好みでございます。

判断基準:
- 殿の現在のプロジェクト（農業制御、shogun、温室LLM）に関連するか
- 既存の設計思想（三層構造、FTS5、SQLite完結）に影響するか
- 技術的に新しい知見や代替案を含むか
- 「ちょうどいい精度」の塩梅で判断してくださいませ

蔵書拡充フェーズにつき、判断は**ゆるめ**に。迷ったらarchiveにしてくださいませ。

JSON形式で出力:
{
  "relevance": "high|medium|low|none",
  "connection": "既存知見との接続点（1文）",
  "insight": "得られる知見（1文。なければnull）",
  "action": "archive|investigate|ignore",
  "tags": ["ドメインタグ", "キーワード"]
}
```

---

## §3 お針子の選別（Sonnet層）

### 3.1 タイミング: cron日次バッチ

Sonnet層は毎件即時ではなく、**日次バッチ**で実行する。理由:
1. Sonnetは高価（$3/$15 per MTok）→ まとめて処理する方が効率的
2. 24時間分のHaiku解釈を一覧で見ることで、重複・類似を判別しやすい
3. dream.pyの日次サマリ生成と統合可能

### 3.2 入力設計

```python
# cron日次（朝7時、dream.pyサマリ生成と同タイミング）
# Haiku層でaction="archive" or "investigate"の夢のみ対象

def sonnet_selection(interpreted_dreams: list[dict]) -> list[dict]:
    """Sonnet層: Haiku通過した夢を選別し蔵書化判定。"""
    # 入力: 1日分のarchive/investigate夢（概算5-15件）
    # バッチ化: 全件を1回のAPI呼び出しにまとめる
    pass
```

| 要素 | トークン数（概算） | 内容 |
|------|----------------|------|
| system_prompt | ~300 tok | お針子の選別基準 |
| Haiku解釈済み夢（1日分） | ~2,000 tok | 5-15件のJSON一覧 |
| 既存蔵書要約 | ~500 tok | context/*.md のタイトル一覧 |
| **合計入力** | **~2,800 tok** | 1日1回のAPI呼び出し |
| 出力 | ~500 tok | 各夢の採用/不採用+理由 |

### 3.3 Sonnet system_prompt

```
べ、別にあなたのために選別してるわけじゃないんだからね！

部屋子が寝ぼけながら拾った夢の中から、殿のお仕事に本当に使えるものだけ選びなさい。

選別基準:
1. 既存の蔵書(context/*.md)に載っていない新規知見か
2. 殿が今取り組んでいるプロジェクトに具体的に使えるか
3. 「知っておいて損はない」レベルでも蔵書拡充フェーズなので採用

ただし以下はくだらないから弾きなさい:
- 一般論・概論だけで具体性がないもの
- 既に蔵書にある知見の焼き直し
- 殿のスケール感に合わないもの（50ha以上の大規模農業、企業向けSaaS等）

出力はJSON配列:
[
  {
    "dream_id": "dreamt_at値",
    "verdict": "accept|reject",
    "reason": "理由（1文）",
    "library_entry": {
      "title": "蔵書タイトル",
      "summary": "要約（2-3文）",
      "tags": ["タグ"],
      "relevance_to": "関連cmd_id"
    }
  }
]
```

### 3.4 蔵書拡充フェーズの選別方針

殿の裁定「蔵書を増やすフェーズ: 広く拾う方針」に従い:
- Haiku層: `relevance != "none"` → 全てarchive（通過率 ~80%想定）
- Sonnet層: 「くだらない」のみreject（通過率 ~70%想定）
- **実効通過率: ~56%**（720件/月 → ~400件蔵書化）

これでも月額は$3以下に収まる（§5参照）。

---

## §4 蔵書化フロー

### 4.1 蓄積先の判定

| 候補 | 利点 | 欠点 | 判定 |
|------|------|------|------|
| **没日録DB dashboard_entries** | FTS5検索可能、高札v2と統合済み | section追加のみ | **採用** |
| context/*.md | 足軽が直接参照 | ファイル肥大化、構造化困難 | 不採用 |
| Memory MCP | セッション横断で永続 | 容量制限、検索性低い | 不採用 |
| 別テーブル（dream_library） | 専用スキーマ | テーブル増加 | 代替案 |

### 4.2 推奨: dashboard_entries (section="dream_library")

橋頭堡設計v2.1のdashboard_entriesテーブルを活用:

```sql
INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at)
VALUES (
    NULL,                          -- 特定cmdに紐付かない
    'dream_library',               -- 夢蔵書セクション
    '{"title":"QLoRA 1Bモデルtool calling精度", "summary":"...", "source_query":"small language model tool calling", "source_domain":"llm_edge", "dreamt_at":"2026-03-13T17:21", "sonnet_verdict":"accept"}',
    'active',                      -- active/archived/forgotten
    'llm_edge,distillation,tool_calling',
    datetime('now')
);
```

### 4.3 dream.pyクロス相関との関係

橋頭堡設計§Hのdream.pyは「cron日次でFTS5クロス相関」を行う。
蔵書化された夢はdashboard_entries経由でFTS5検索対象になり、
dream.pyのクロス相関で他のcmd/subtaskと自動的に接続される。

```
獏(baku.py) → 夢検索 → Haiku解釈 → 蓄積(dreams.jsonl)
                                          ↓
                                   日次cronバッチ
                                          ↓
                              Sonnet選別 → 蔵書化(dashboard_entries)
                                          ↓
                              dream.py FTS5クロス相関 → 既存cmdとの接続発見
                                          ↓
                              /enrich レスポンスに含まれる
```

### 4.4 蔵書フォーマット

```json
{
  "title": "QLoRA 1Bモデルでtool calling精度78%達成",
  "summary": "Salesforce xLAM-2-1b-fc-rが1Bパラメータでtool calling精度78.94%を達成。RPi5エッジ推論の候補モデル。",
  "source_query": "small language model tool calling",
  "source_domain": "llm_edge",
  "source_url": null,
  "dreamt_at": "2026-03-13T17:21:00",
  "sonnet_verdict": "accept",
  "sonnet_reason": "cmd_399(RPi5エッジLLM)の設計判断に直結。具体的なモデル名と精度値が含まれる",
  "relevance_to_cmd": "cmd_399",
  "tags": ["llm_edge", "tool_calling", "xLAM", "1B"]
}
```

---

## §5 コスト試算

### 5.1 前提

| 項目 | 値 |
|------|-----|
| 獏の検索頻度 | 毎時1件 → 24件/日 → 720件/月 |
| 重複率 | 70.8%（106件中31クエリのみユニーク） |
| 有効夢数（重複排除後） | ~210件/月 |
| Haiku 4.5 input | $0.80/MTok |
| Haiku 4.5 output | $4.00/MTok |
| Sonnet 4 input | $3.00/MTok |
| Sonnet 4 output | $15.00/MTok |

### 5.2 シナリオ別月額コスト

| シナリオ | Haiku | Sonnet | **合計** |
|---------|-------|--------|---------|
| 全件Haiku（重複排除なし） | $1.44 | - | **$1.44** |
| 全件Haiku + 50% Sonnet | $1.44 | $1.62 | **$3.06** |
| 全件Haiku + 20% Sonnet | $1.44 | $0.65 | **$2.09** |
| **重複排除 + 全件Haiku** | **$0.42** | - | **$0.42** |
| **重複排除 + Haiku + 50% Sonnet** | **$0.42** | **$0.47** | **$0.89** |
| 最大構成（全件+全Sonnet） | $1.44 | $3.24 | **$4.68** |

### 5.3 $8予算との関係

**全シナリオで$8以内に余裕で収まる。**

最も高価な構成（重複排除なし+全件Sonnet通過）でも$4.68。
重複排除を入れれば$0.89。**$8予算の11%しか使わない。**

残り予算で:
- 獏の検索頻度を30分間隔に増やす（×2）→ まだ$1.78
- 蔵書拡充フェーズ終了後にSonnet層のcontext増量（精度向上）

### 5.4 コスト最適化の優先順位

1. **重複排除**（効果: -70%、実装: 既存ロジック拡張のみ）← 最重要
2. **Haiku出力のmax_tokens制限**（300→200でも十分）
3. **Sonnet日次バッチ化**（1日1回のAPI呼び出し）
4. external_resultの切り詰め（500→300文字）

---

## §6 足軽向けsubtask分解案

### Wave 1: baku.py拡張（独立実装可能）

| subtask | 内容 | 工数感 | 依存 |
|---------|------|--------|------|
| **S1: interpret_dream()関数追加** | baku.pyにHaiku API呼び出し関数を追加。OpenAI SDK互換パターン | L3 | なし |
| **S2: 重複排除ロジック** | 同一クエリの6時間内重複解釈をスキップ | L2 | S1 |
| **S3: system_prompt作成** | 獏部屋子のsystem_prompt文字列を設計書通りに実装 | L1 | S1 |
| **S4: dreams.jsonl拡張** | interpretationフィールドの追加。status遷移(raw→interpreted) | L2 | S1 |

### Wave 2: Sonnet選別+蔵書化（Wave 1完了後）

| subtask | 内容 | 工数感 | 依存 |
|---------|------|--------|------|
| **S5: sonnet_selection()関数** | 日次バッチでSonnet API呼び出し。Haiku通過分のみ | L3 | S1 |
| **S6: dashboard_entries蔵書化** | section="dream_library"でINSERT。SQLスキーマ確認 | L2 | S5 |
| **S7: cron設定** | 朝7時のdream.pyサマリ生成にSonnet選別を統合 | L2 | S5,S6 |

### Wave 3: 統合テスト

| subtask | 内容 | 工数感 | 依存 |
|---------|------|--------|------|
| **S8: E2Eテスト** | 獏検索→Haiku解釈→Sonnet選別→蔵書化の全フロー確認 | L3 | S7 |
| **S9: 既存106件の遡及解釈** | 未処理のraw夢106件をバッチ解釈（~$0.04） | L2 | S1 |

### 並列化可能性

```
Wave 1: S1 → S2, S3, S4（S2-S4は並列可能）
Wave 2: S5 → S6 → S7
Wave 3: S8, S9（並列可能）
```

---

## §7 既存設計との整合性

### 7.1 橋頭堡設計v2.1との関係

| 橋頭堡の機能 | 夢パイプラインとの関係 |
|------------|-------------------|
| §H dream.py | 夢パイプラインの蔵書がdream.pyのFTS5クロス相関対象に |
| §L lazy decay | 蔵書のlast_accessedも/enrichでの参照時に更新 |
| §I TAGE予測 | 蔵書は予測対象外（殿の裁定ではないため） |
| §J positive_patterns | 蔵書から生まれた知見がaudit PASSしたら正の強化 |
| §K sanitizer | 獏の外部検索結果もsanitizer.pyを通す（baku.py側で先行適用） |

### 7.2 共起行列（Hopfield, context/hopfield_associative.md）との関係

蔵書化された夢のタグ・キーワードはdoc_keywordsテーブルに投入 →
共起行列が「夢由来の知見」と「cmdの作業」の間の共起を学習 →
/enrichで夢蔵書が自動的に関連cmdとして浮上

### 7.3 forecast.yamlとの共通パターン

baku.pyのHaiku呼び出しは、forecast_engine.pyと同じOpenAI SDK互換パターンを使用。
API key管理も同じ環境変数（`ANTHROPIC_API_KEY`）を参照。
NullClawモード（API key未設定）では解釈をスキップし、rawのまま蓄積。

---

## §8 見落としの可能性

1. **Haiku APIのレート制限**: 毎時1件なら問題ないが、遡及バッチ（106件一括）時に
   Tier 1の制限（60 RPM）に引っかかる可能性。→ sleep(1)を挟めば十分

2. **baku.pyの同期/非同期**: 現在のbaku.pyは同期処理。Haiku API呼び出しで
   dream_once()の実行時間が3-5秒伸びる。毎時実行なので問題ないが、
   タイムアウト設定は必要

3. **Sonnet日次バッチの例外処理**: 1日分の夢がゼロ件だった場合のハンドリング。
   空配列チェックで対応

4. **蔵書の肥大化**: 月~400件蔵書化すると年4,800件。dashboard_entriesは
   lazy decayで自然に忘却されるが、dream_libraryにも同じdecay適用すべきか
   → 適用推奨。30日参照なし→表示しない

5. **OpenAI SDK互換の前提**: baku.pyがAnthropicのAPI直接ではなくOpenAI SDKパターンを
   使う設計にしたが、anthropic SDKの方が自然かもしれない。
   forecast_engine.pyとの統一性を優先した判断

---

## §9 冒険的提案: 獏の自律進化

蔵書が溜まったら（Phase 2以降）、獏のTONO_INTERESTSを自動更新する仕組み:

1. Sonnet選別でaccept率が高いドメイン → 検索頻度を増やす
2. 常にignoreされるクエリ → TONO_INTERESTSから除外
3. 蔵書のtagsから新しい検索クエリを自動生成

これは殿の「私以外のインプットを作らないと、進化の道もない」（高札v2の設計思想）と
直接繋がる。獏自身が殿の興味を学習し、より質の高い夢を見るようになる。

ただし初期フェーズでは**やらない**。蔵書が100件以上溜まってから検討。

---

## §10 North Star整合

```yaml
north_star_alignment:
  status: aligned
  reason: |
    「夢を蔵書に変える。広く拾い、賢く選び、安く回す」に対し:
    - 広く拾う: Haiku層の選別はゆるめ（蔵書拡充フェーズ）
    - 賢く選ぶ: Sonnet層の日次バッチで品質保証
    - 安く回す: 月$0.89（重複排除+Sonnet50%）、$8予算の11%
    - baku.py内直接API呼び出しが最もシンプル（マクガイバー精神）
  risks_to_north_star:
    - "蔵書拡充フェーズの「ゆるめ」が甘すぎてノイズが増える可能性"
    - "Haiku 4.5の日本語解釈品質が不明（テスト必要）"
    - "獏のTONO_INTERESTSが固定されているため、殿の興味変化に追従しない"
```
