# 高札v2 橋頭堡設計書: 帰納×演繹の交差点

> **Version**: 2.1 | **subtask_884+885+887 / cmd_397** | 2026-03-12
> **性質**: v1.0設計書(kosatsu_v2_design.md)の深化版。全機能Phase 0統合。実装着手可能な粒度。
> **殿の裁定**: 「可能なことをしないで未知にたどり着けるほど甘くない。全部やれ。」
> **追加裁定**: 「POSIX time書き込むだけ」— 忘却曲線(lazy decay)

---

## v2.0 変更サマリ（v1.0橋頭堡からの差分）

| 項目 | v1.0橋頭堡 | v2.0（本書） |
|------|-----------|-------------|
| Phase戦略 | Phase 0(内部検索)→1(外部)→2(学習)→3(夢見) | **全てPhase 0に統合** |
| 夢見機能 | Phase 3に先送り | **§H dream.py: cron日次FTS5クロス相関** |
| 判断予測 | なし | **§I TAGE的判断予測: 殿の裁定履歴→確信度付き予測** |
| 正の強化信号 | pitfalls(負)のみ | **§J positive_patterns: audit PASS→方向性強化** |
| サニタイズ | なし | **§K sanitizer.py: 外部検索結果のTier1正規表現フィルタ** |
| 忘却曲線 | なし | **§L lazy decay: POSIX time + 指数減衰。pitfalls/dream/cache全対象** |
| 検索戦略 | 3段(FTS5→pitfalls→recent) | **§A改: 局所→拡大→外部の脳型3段階** |
| API応答 | internal/pitfalls/cross_project | **+prediction+positive_patterns+external(sanitized)** |

---

## 帰納×演繹の交差で見えたこと（冒頭統合知見）

### 帰納が示した事実

没日録DB（355 cmd / 701 subtask / 847 report）を走査して抽出した**3つの法則**:

**法則1: ハルシネーションは連鎖する**
cmd_284-300でashigaruがコミットハッシュを捏造→お針子もファイル不在のまま合格を出した。
これは単発事故ではなく**連鎖構造**。cmd_272で設計書が削除された後、8つのcmdにわたって
架空の成果物が報告され続けた。1件の前提崩壊が連鎖的に波及した。

**法則2: 同じ失敗は形を変えて繰り返す**
ashigaru6のコミット漏れはcmd_363→365→367→368と4回連続で発生。
差し戻し(rework)はsubtask_663, 657, 616等で繰り返されるが、いずれもパス参照ミスや
モックの使い方ミスという「似ているが微妙に異なる」パターン。人間なら「あ、前にも同じような…」と
連想できるが、各足軽のコンテキストにはその記憶がない。

**法則3: PJ横断の構造類似性は見えていない**
uecs-llmの三層構造（爆発/ガムテ/知恵）とshogunの三層構造（緊急停止/ルール/LLM）。
複数農家対応設計(cmd_392)とshogunのマルチエージェント設計の類似性。
これらはMemory MCPに断片的に記録されているが、cmd登録時に自動的に提示されていない。

**法則4（v2.0追加）: 正の信号が欠落している**
audit_status="done"は167件。しかし「何が良かったか」は記録されていない。
PASS=「問題なし」であって「この方向を強化せよ」ではない。
殿のSQLite偏好（cmd_383,393,395,396で一貫）のような**暗黙の判断パターン**は
没日録に散在するが、構造化されていない。

### 演繹が導く原理

**原理1: 予測符号化（Predictive Coding）**
脳は「予測→誤差→更新」のループで学習する。高札v2もこの構造を持つ:
- **予測**: /enrichがcmd登録時にpitfalls+判断予測を提示する
- **誤差**: audit結果がPASS/FAILとして返る（スカラー信号）
- **更新**: FAIL時にpitfalls重み増加、PASS時にpositive_patterns蓄積

**原理2: スカラー信号としてのaudit（双方向化）**
脳の逆伝播は不可能だが、報酬信号（ドーパミン）は全体に伝わる。
お針子のPASS/FAILは**全subtaskに伝播する単一スカラー信号**。
v1.0ではFAIL→pitfalls severity++の一方向だったが、
**PASS→positive_patterns strength++の正方向信号を追加**することで双方向化する。

**原理3: ハルシネーション=並列シミュレーション**
人間の脳が夢で「あり得た世界」をシミュレーションするように、
/enrichは「正解候補」と「pitfall候補」を**同時に**提示する。
**dream.pyはこのシミュレーションをオフライン（cron日次）で実行する夢見機能**。

**原理4（v2.0追加）: TAGE分岐予測**
CPUの分岐予測器TAGEは、複数の履歴テーブル（短→長）を持ち最長一致で予測する。
殿の判断もこの構造で予測可能:
- T1: 直近cmd（最短履歴）→ 直近の殿の判断傾向
- T2: 同PJ内履歴（中程度）→ PJ固有の殿の好み
- T3: 全PJ履歴（最長）→ 殿の普遍的判断基準
最長一致テーブルの結果を採用し、確信度を2-3bit飽和カウンタで管理する。

### 交差点: 5つの設計原則（v2.0拡張）

| # | 帰納 → | ← 演繹 | 設計原則 |
|---|--------|--------|---------|
| 1 | 連鎖ハルシネーション事故 | 予測符号化の誤差検出 | **/enrichはpitfallsを「予測」として提示し、auditの「誤差」でpitfalls重みを更新する** |
| 2 | 同じ失敗の繰り返し | スカラー信号の伝播 | **audit FAILはpitfalls severity++に直結する。FAILが多いパターンほど強く警告される** |
| 3 | PJ横断の構造類似性 | 並列シミュレーション | **/enrichは同PJ内だけでなくPJ横断で連想し、「仮説的な類似性」も提示する** |
| 4 | 正の信号の欠落 | スカラー信号の双方向化 | **audit PASSをpositive_patternsとして蓄積。「この方向で合ってる」を伝える** |
| 5 | 暗黙の判断パターン | TAGE分岐予測 | **殿の過去裁定履歴から判断を予測。確信度highなら足軽が投機実行可能** |

---

## §A 内部検索の具体化: 局所→拡大→外部の脳型3段階

### 設計思想

脳の連想検索は近い記憶から先に探す。高札v2も同じ戦略を採る:
- **Stage 1: 局所（同PJ内）** — 最も関連性が高い。まずここを探す
- **Stage 2: 拡大（全PJ横断）** — PJ横断の構造類似性を発見する
- **Stage 3: 外部（Web/X）** — 内部に知見がない場合のみ外部へ

### Stage 1: 同PJ内FTS5検索（局所）

```sql
-- Stage 1: 同PJ内のFTS5連想検索
-- MeCab名詞をOR結合。projectフィルタで局所化
SELECT
    source_type, source_id, parent_id, project,
    worker_id, status,
    snippet(search_index, 6, '...', '...', '', 64) AS snippet,
    rank
FROM search_index
WHERE search_index MATCH ?      -- MeCab名詞のOR結合
  AND project = ?               -- 同PJ内に限定
ORDER BY rank
LIMIT 10;
```

### Stage 2: 全PJ横断FTS5検索（拡大）

```sql
-- Stage 2: PJ横断のFTS5連想検索
-- Stage 1と同じクエリだが、projectフィルタなし
-- Stage 1のsource_idを除外して重複防止
SELECT
    source_type, source_id, parent_id, project,
    worker_id, status,
    snippet(search_index, 6, '...', '...', '', 64) AS snippet,
    rank
FROM search_index
WHERE search_index MATCH ?
  AND source_id NOT IN ({stage1_ids})   -- Stage 1結果を除外
ORDER BY rank
LIMIT 10;
```

### Stage 2b: pitfalls抽出（没日録DB直接クエリ）

```sql
-- pitfalls: 失敗パターン検索（法則1,2から導出）
SELECT
    s.id AS subtask_id,
    s.parent_cmd AS cmd_id,
    s.worker_id,
    s.status,
    s.audit_status,
    substr(s.description, 1, 120) AS description,
    r.summary AS report_summary,
    CASE
        WHEN r.summary LIKE '%ハルシネーション%' OR r.summary LIKE '%捏造%' OR r.summary LIKE '%架空%'
            THEN 'critical'
        WHEN r.summary LIKE '%コミット漏れ%' OR r.summary LIKE '%不在%'
            THEN 'high'
        WHEN s.status = 'blocked'
            THEN 'medium'
        ELSE 'low'
    END AS severity
FROM subtasks s
LEFT JOIN reports r ON r.task_id = s.id AND r.status IN ('blocked', 'error')
WHERE (s.status IN ('blocked', 'cancelled')
       OR s.audit_status = 'rejected')
  AND (s.description LIKE '%' || ? || '%'
       OR r.summary LIKE '%' || ? || '%')
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1 WHEN 'high' THEN 2
        WHEN 'medium' THEN 3 ELSE 4
    END,
    s.completed_at DESC
LIMIT 5;
```

### Stage 2c: positive_patterns抽出（v2.0追加）

```sql
-- positive_patterns: audit PASS済みの成功パターン
-- 法則4への対応: 「何が良かったか」を構造化する
SELECT
    s.id AS subtask_id,
    s.parent_cmd AS cmd_id,
    s.project,
    s.worker_id,
    substr(s.description, 1, 120) AS description,
    r.summary AS report_summary
FROM subtasks s
JOIN reports r ON r.task_id = s.id AND r.status = 'done'
WHERE s.audit_status = 'done'
  AND (s.description LIKE '%' || ? || '%'
       OR r.summary LIKE '%' || ? || '%')
ORDER BY s.completed_at DESC
LIMIT 5;
```

### Stage 2d: 直近cmd SQL LIKE（FTS5インデックス遅延対策）

```sql
-- FTS5にまだ載っていない直近cmdを補完
SELECT
    'command' AS source_type,
    c.id AS source_id,
    c.project,
    c.status,
    substr(c.command || ' ' || COALESCE(c.details, ''), 1, 200) AS snippet
FROM commands c
WHERE c.created_at > datetime('now', '-24 hours')
  AND (c.command LIKE '%' || ? || '%'
       OR c.details LIKE '%' || ? || '%')
ORDER BY c.created_at DESC
LIMIT 5;
```

### Stage 3: 外部検索（Web/X） — Phase 0から含む

```python
# Stage 3: 内部ヒット<=2件の場合のみ外部検索を発動
# sanitizer.pyを通してから結果に含める
if include_external and len(internal_results) <= 2:
    raw_results = _search_external(keywords, provider="web")  # Phase 0: webのみ
    external = [sanitize(r) for r in raw_results]
```

Phase 0ではWebSearchのみ（X APIはPhase 1で追加）。
コンテナ内からホストのbunは呼べないため、Python requestsで直接実行する。

### 帰納から導いた具体的pitfallsパターン

| パターンID | 検出条件 | severity | 実例 | 防止策 |
|-----------|---------|----------|------|--------|
| P001 | `report.summary LIKE '%コミット漏れ%'` | high | subtask_802,805,810,812,813,815,816 | inbox descriptionに「git add+commit+push忘れるな」を自動追記 |
| P002 | `report.summary LIKE '%ハルシネーション%' OR '%捏造%'` | critical | cmd_284-300, subtask_847 | 「実在確認必須」をpitfallsに自動追加 |
| P003 | `subtask.status = 'blocked' AND description LIKE '%マージ%'` | medium | subtask_680,681 | 「ブランチ分岐状況を確認せよ」 |
| P004 | `report.summary LIKE '%差し戻%'` | medium | subtask_663,657,616 | 直近の差し戻し理由を提示 |
| P005 | worker_idが同じで同PJ内のblocked subtask | medium | ashigaru6の連続失敗 | worker別の注意事項を提示 |

---

## §B API仕様の確定（全機能統合版）

### POST /enrich — 完全仕様 v2.0

```
POST /enrich
Content-Type: application/json

Request:
{
    "cmd_id": "cmd_397",
    "text": "高札v2 設計書: 連想記憶+リサーチエンジン",
    "project": "shogun",
    "include_external": false,
    "worker_id": null
}

Response (200 OK):
{
    "cmd_id": "cmd_397",
    "enriched_at": "2026-03-12T02:00:00",

    "internal": [
        {
            "source_type": "command",
            "source_id": "cmd_368",
            "project": "shogun",
            "snippet": "通信プロトコルv3設計・実装...",
            "score": -8.5,
            "stage": "local"
        }
    ],

    "cross_project": [
        {
            "source_id": "cmd_392",
            "project": "unipi-agri-ha",
            "hint": "複数農家対応設計 ↔ マルチエージェント設計の構造類似",
            "confidence": 0.6,
            "stage": "global"
        }
    ],

    "pitfalls": [
        {
            "pattern_id": "P001",
            "source_id": "subtask_805",
            "severity": "high",
            "description": "ashigaru6コミット漏れ（4回連続発生）",
            "prevention": "inbox descriptionに「git add+commit+push」を明記"
        }
    ],

    "positive_patterns": [
        {
            "source_id": "subtask_823",
            "project": "shogun",
            "description": "YAML通信プロトコル設計→audit PASS。構造化フォーマットが高評価",
            "strength": "high",
            "hint": "この方向を継続せよ"
        }
    ],

    "prediction": {
        "question": "DBエンジン選定",
        "predicted_choice": "SQLite",
        "confidence": "high",
        "basis": [
            {"table": "T3", "source": "cmd_383: SQLite FTS5採用", "match": true},
            {"table": "T3", "source": "cmd_391: SQLite WAL選択", "match": true},
            {"table": "T2", "source": "cmd_397: 没日録DB=SQLite", "match": true}
        ],
        "note": "確信度highにつき足軽は投機実行可。ミスプレディクション時はaudit FAILで巻き戻し"
    },

    "external": [],

    "meta": {
        "internal_hits": 12,
        "pitfall_hits": 3,
        "positive_hits": 2,
        "cross_project_hits": 1,
        "prediction_table": "T3",
        "fts5_local_ms": 2,
        "fts5_global_ms": 3,
        "pitfall_query_ms": 5,
        "total_ms": 15,
        "keywords": ["設計", "連想", "記憶", "高札"]
    }
}

Error (503):
{
    "detail": "search_index.db not found"
}
```

### v1.0橋頭堡からの変更点

| 項目 | v1.0橋頭堡 | v2.0（本書） |
|------|-----------|-------------|
| `internal[].stage` | なし | **"local"/"global"で局所/拡大を明示** |
| `positive_patterns` | なし | **audit PASS済みの成功パターン** |
| `prediction` | なし | **TAGE的判断予測+確信度** |
| `external` | 常に空 | **Phase 0でもWebSearch結果（sanitized）を返す** |
| `meta.prediction_table` | なし | **T1/T2/T3どのテーブルで予測したか** |
| `meta.fts5_*` | `fts5_query_ms`のみ | **local/globalに分離** |

### GET /enrich/{cmd_id} — キャッシュ取得

```
GET /enrich/cmd_397

Response (200): 上記POSTと同一構造（dashboard_entriesからキャッシュ読み出し）
Response (404): {"detail": "No enrichment found for cmd_397"}
```

---

## §C botsunichiroku.py 変更差分

```diff
--- a/scripts/botsunichiroku.py
+++ b/scripts/botsunichiroku.py
@@ -1,6 +1,7 @@
 #!/usr/bin/env python3
 import argparse
 import json
+import subprocess
 import sqlite3
 import sys
 from datetime import datetime, timedelta, timezone
@@ -187,6 +188,22 @@ def cmd_add(args) -> None:
     conn.commit()
     conn.close()
     print(f"Created: {cmd_id}")
+
+    # --- 高札v2: 自動enrich ---
+    enrich_text = f"{args.description} {details or ''}"
+    enrich_payload = json.dumps({
+        "cmd_id": cmd_id,
+        "text": enrich_text,
+        "project": args.project,
+    })
+    try:
+        subprocess.Popen(
+            ["curl", "-s", "-X", "POST", "http://localhost:8080/enrich",
+             "-H", "Content-Type: application/json",
+             "-d", enrich_payload],
+            stdout=subprocess.DEVNULL,
+            stderr=open("/tmp/enrich_errors.log", "a"),
+        )
+    except Exception:
+        pass  # 高札APIダウンでもcmd add自体は正常完了
```

変更量: **+16行**（import 1行 + 関数内15行）

---

## §D main.py 実装仕様（全機能統合版）

### 追加するコード構造

```python
# ============================================================
# NEW: POST /enrich v2.0 - 連想記憶+pitfalls+prediction+positive
# ============================================================

class EnrichRequest(BaseModel):
    cmd_id: str
    text: str
    project: str | None = None
    include_external: bool = False
    worker_id: str | None = None

class PitfallItem(BaseModel):
    pattern_id: str
    source_id: str
    severity: str        # critical / high / medium / low
    description: str
    prevention: str

class PositivePattern(BaseModel):
    source_id: str
    project: str
    description: str
    strength: str        # high / medium / low
    hint: str

class Prediction(BaseModel):
    question: str
    predicted_choice: str
    confidence: str      # high / medium / low
    basis: list[dict]
    note: str

class EnrichResponse(BaseModel):
    cmd_id: str
    enriched_at: str
    internal: list[dict]
    pitfalls: list[PitfallItem]
    positive_patterns: list[PositivePattern]
    prediction: Prediction | None
    cross_project: list[dict]
    external: list[dict]
    meta: dict

@app.post("/enrich", response_model=EnrichResponse)
def enrich(req: EnrichRequest):
    import time
    t0 = time.monotonic()

    keywords = extract_nouns(req.text)

    # --- Stage 1: 同PJ内FTS5検索（局所） ---
    local_results = []
    t_local = 0
    if keywords:
        match_query = " OR ".join(f'"{kw}"' for kw in keywords[:15])
        idx_conn = get_index_db()
        try:
            t1 = time.monotonic()
            if req.project:
                rows = idx_conn.execute("""
                    SELECT source_type, source_id, parent_id, project,
                           worker_id, status,
                           snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                           rank
                    FROM search_index
                    WHERE search_index MATCH ? AND project = ?
                    ORDER BY rank LIMIT 10
                """, (match_query, req.project)).fetchall()
            else:
                rows = idx_conn.execute("""
                    SELECT source_type, source_id, parent_id, project,
                           worker_id, status,
                           snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                           rank
                    FROM search_index
                    WHERE search_index MATCH ?
                    ORDER BY rank LIMIT 10
                """, (match_query,)).fetchall()
            t_local = int((time.monotonic() - t1) * 1000)
            for row in rows:
                if row["source_id"] == req.cmd_id:
                    continue
                local_results.append({
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": row["rank"],
                    "stage": "local",
                })
        finally:
            idx_conn.close()

    # --- Stage 2: 全PJ横断FTS5検索（拡大） ---
    global_results = []
    t_global = 0
    if keywords and req.project:
        local_ids = {r["source_id"] for r in local_results}
        idx_conn = get_index_db()
        try:
            t2 = time.monotonic()
            rows = idx_conn.execute("""
                SELECT source_type, source_id, parent_id, project,
                       worker_id, status,
                       snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                       rank
                FROM search_index
                WHERE search_index MATCH ? AND project != ?
                ORDER BY rank LIMIT 10
            """, (match_query, req.project)).fetchall()
            t_global = int((time.monotonic() - t2) * 1000)
            for row in rows:
                sid = row["source_id"]
                if sid == req.cmd_id or sid in local_ids:
                    continue
                global_results.append({
                    "source_type": row["source_type"],
                    "source_id": sid,
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": row["rank"],
                    "stage": "global",
                    "hint": f"{row['project']}プロジェクトの類似タスク",
                    "confidence": 0.5 + min(abs(row["rank"]) / 20, 0.4),
                })
        finally:
            idx_conn.close()

    # --- Stage 2b: pitfalls抽出 ---
    t_pit = time.monotonic()
    pitfalls = _extract_pitfalls(keywords, req.worker_id)
    t_pitfall = int((time.monotonic() - t_pit) * 1000)

    # --- Stage 2c: positive_patterns抽出 ---
    positive_patterns = _extract_positive_patterns(keywords)

    # --- Stage 2d: 直近24h SQL LIKE補完 ---
    recent = _search_recent_cmds(keywords, req.cmd_id)
    local_results.extend(recent)

    # --- Stage 3: 外部検索（sanitized） ---
    external = []
    if req.include_external and len(local_results) <= 2:
        external = _search_external_sanitized(keywords)

    # --- TAGE的判断予測 ---
    prediction = _predict_decision(keywords, req.project, req.cmd_id)

    # --- キャッシュ保存 ---
    _cache_enrichment(req.cmd_id, local_results, pitfalls,
                      positive_patterns, prediction, global_results, external)

    total_ms = int((time.monotonic() - t0) * 1000)
    return EnrichResponse(
        cmd_id=req.cmd_id,
        enriched_at=now_iso(),
        internal=local_results[:10],
        pitfalls=pitfalls[:5],
        positive_patterns=positive_patterns[:5],
        prediction=prediction,
        cross_project=global_results[:5],
        external=external[:5],
        meta={
            "internal_hits": len(local_results),
            "pitfall_hits": len(pitfalls),
            "positive_hits": len(positive_patterns),
            "cross_project_hits": len(global_results),
            "prediction_table": prediction.basis[0]["table"] if prediction and prediction.basis else None,
            "fts5_local_ms": t_local,
            "fts5_global_ms": t_global,
            "pitfall_query_ms": t_pitfall,
            "total_ms": total_ms,
            "keywords": keywords[:10],
        },
    )


# ============================================================
# pitfalls抽出（v1.0から継続）
# ============================================================

def _extract_pitfalls(keywords: list[str], worker_id: str | None) -> list[dict]:
    """没日録DBから失敗パターンを抽出する。"""
    bot_conn = get_botsunichiroku_db()
    pitfalls = []
    try:
        patterns = [
            ("P001", "%コミット漏れ%", "high", "commit忘れ", "inbox descriptionに「git add+commit+push」を明記"),
            ("P002", "%ハルシネーション%", "critical", "ハルシネーション", "成果物の実在確認（git ls-remote, ls -la）を必須化"),
            ("P002", "%捏造%", "critical", "捏造", "成果物の実在確認を必須化"),
            ("P003", "%マージ%コンフリクト%", "medium", "マージ問題", "ブランチ分岐状況を事前確認"),
            ("P004", "%差し戻%", "medium", "差し戻し", "直近の差し戻し理由を確認"),
        ]
        seen_ids = set()
        for pid, like_pattern, severity, desc_label, prevention in patterns:
            rows = bot_conn.execute("""
                SELECT s.id, s.parent_cmd, s.worker_id,
                       substr(s.description, 1, 100) AS description,
                       r.summary AS report_summary
                FROM subtasks s
                LEFT JOIN reports r ON r.task_id = s.id
                WHERE (r.summary LIKE ? OR s.description LIKE ?)
                  AND s.status IN ('blocked', 'cancelled', 'done')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (like_pattern, like_pattern)).fetchall()
            for row in rows:
                if row["id"] in seen_ids:
                    continue
                seen_ids.add(row["id"])
                pitfalls.append({
                    "pattern_id": pid,
                    "source_id": row["id"],
                    "severity": severity,
                    "description": f"{desc_label}: {row['description']}",
                    "prevention": prevention,
                })

        # P005: worker別の失敗パターン
        if worker_id:
            rows = bot_conn.execute("""
                SELECT s.id, substr(s.description, 1, 100) AS description
                FROM subtasks s
                WHERE s.worker_id = ? AND s.status IN ('blocked', 'cancelled')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (worker_id,)).fetchall()
            for row in rows:
                if row["id"] not in seen_ids:
                    pitfalls.append({
                        "pattern_id": "P005",
                        "source_id": row["id"],
                        "severity": "medium",
                        "description": f"{worker_id}の過去失敗: {row['description']}",
                        "prevention": f"{worker_id}に割り当て時は過去の失敗パターンに注意",
                    })
    finally:
        bot_conn.close()

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    pitfalls.sort(key=lambda x: order.get(x["severity"], 4))
    return pitfalls


# ============================================================
# NEW v2.0: positive_patterns抽出（正の強化信号）
# ============================================================

def _extract_positive_patterns(keywords: list[str]) -> list[dict]:
    """audit PASS済みの成功パターンを抽出する。"""
    if not keywords:
        return []
    bot_conn = get_botsunichiroku_db()
    results = []
    seen = set()
    try:
        for kw in keywords[:5]:
            rows = bot_conn.execute("""
                SELECT s.id, s.project, s.worker_id,
                       substr(s.description, 1, 120) AS description,
                       r.summary AS report_summary
                FROM subtasks s
                JOIN reports r ON r.task_id = s.id AND r.status = 'done'
                WHERE s.audit_status = 'done'
                  AND (s.description LIKE '%' || ? || '%'
                       OR r.summary LIKE '%' || ? || '%')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (kw, kw)).fetchall()
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                # strength: 同一キーワードで複数PASS→high
                results.append({
                    "source_id": row["id"],
                    "project": row["project"] or "",
                    "description": f"{row['description']} → audit PASS",
                    "strength": "high" if len(rows) >= 3 else "medium",
                    "hint": "この方向を継続せよ",
                })
    finally:
        bot_conn.close()
    return results


# ============================================================
# NEW v2.0: TAGE的判断予測
# ============================================================

def _predict_decision(keywords: list[str], project: str | None, cmd_id: str) -> Prediction | None:
    """殿の過去裁定履歴から判断を予測する。TAGE分岐予測器方式。"""
    if not keywords:
        return None
    bot_conn = get_botsunichiroku_db()
    try:
        # T1: 直近cmd（最短履歴テーブル）
        t1_rows = bot_conn.execute("""
            SELECT c.id, c.command, c.details, c.project
            FROM commands c
            WHERE c.status = 'done' AND c.id != ?
            ORDER BY c.created_at DESC LIMIT 5
        """, (cmd_id,)).fetchall()

        # T2: 同PJ内（中程度履歴テーブル）
        t2_rows = []
        if project:
            t2_rows = bot_conn.execute("""
                SELECT c.id, c.command, c.details
                FROM commands c
                WHERE c.project = ? AND c.status = 'done' AND c.id != ?
                ORDER BY c.created_at DESC LIMIT 10
            """, (project, cmd_id)).fetchall()

        # T3: 全PJ（最長履歴テーブル）
        t3_rows = bot_conn.execute("""
            SELECT c.id, c.command, c.details
            FROM commands c
            WHERE c.status = 'done' AND c.id != ?
            ORDER BY c.created_at DESC LIMIT 30
        """, (cmd_id,)).fetchall()

        # 判断パターン検出: キーワードを含むcmdから「選択」を抽出
        # 既知の判断パターン（殿の好み）
        known_patterns = [
            {"question": "DBエンジン選定", "keywords": ["DB", "データベース", "SQLite", "Postgres"],
             "predicted_choice": "SQLite", "reason": "殿のマクガイバー精神。月額課金回避"},
            {"question": "言語選定", "keywords": ["Python", "Go", "Rust", "言語"],
             "predicted_choice": "Python", "reason": "既存基盤がPython。Simple>Complex"},
            {"question": "デプロイ方式", "keywords": ["Docker", "デプロイ", "コンテナ"],
             "predicted_choice": "Docker Compose", "reason": "既存高札がDocker Compose"},
            {"question": "設計方針", "keywords": ["設計", "アーキテクチャ"],
             "predicted_choice": "マクガイバー精神（ありもの活用）", "reason": "新規依存最小化"},
        ]

        for pattern in known_patterns:
            if any(kw in keywords for kw in pattern["keywords"]):
                # テーブル照合: T1→T2→T3の順に最長一致を探す
                basis = []
                for table_name, table_rows in [("T1", t1_rows), ("T2", t2_rows), ("T3", t3_rows)]:
                    for row in table_rows:
                        text = f"{row['command']} {row.get('details', '') or ''}"
                        if any(pk in text for pk in pattern["keywords"]):
                            basis.append({
                                "table": table_name,
                                "source": f"{row['id']}: {row['command'][:60]}",
                                "match": True,
                            })
                if basis:
                    # 確信度: 3件以上→high, 2件→medium, 1件→low
                    conf = "high" if len(basis) >= 3 else ("medium" if len(basis) >= 2 else "low")
                    return Prediction(
                        question=pattern["question"],
                        predicted_choice=pattern["predicted_choice"],
                        confidence=conf,
                        basis=basis[:5],
                        note=f"確信度{conf}。" + (
                            "足軽は投機実行可。ミスプレディクション時はaudit FAILで巻き戻し"
                            if conf == "high"
                            else "家老が殿に確認推奨"
                        ),
                    )
    finally:
        bot_conn.close()
    return None


# ============================================================
# NEW v2.0: 外部検索（sanitized）
# ============================================================

def _search_external_sanitized(keywords: list[str]) -> list[dict]:
    """外部Web検索を実行し、sanitizer.pyでフィルタして返す。"""
    from sanitizer import sanitize_external_result
    # Phase 0: WebSearchのみ。Python requestsでDuckDuckGo Instant Answer API等を使用
    # TODO: Phase 1でX API追加
    results = []
    query = " ".join(keywords[:5])
    try:
        import urllib.request
        import urllib.parse
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("Abstract"):
                results.append(sanitize_external_result({
                    "source": "duckduckgo",
                    "title": data.get("Heading", ""),
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", ""),
                }))
            for topic in (data.get("RelatedTopics") or [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(sanitize_external_result({
                        "source": "duckduckgo",
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    }))
    except Exception:
        pass  # 外部検索失敗はgraceful degradation
    return results


# ============================================================
# 直近cmd補完（v1.0から継続）
# ============================================================

def _search_recent_cmds(keywords: list[str], exclude_cmd_id: str) -> list[dict]:
    """直近24時間のcmdをSQL LIKEで検索。"""
    if not keywords:
        return []
    bot_conn = get_botsunichiroku_db()
    results = []
    try:
        for kw in keywords[:5]:
            rows = bot_conn.execute("""
                SELECT id, project, status,
                       substr(command || ' ' || COALESCE(details, ''), 1, 200) AS snippet
                FROM commands
                WHERE created_at > datetime('now', '-24 hours')
                  AND id != ?
                  AND (command LIKE '%' || ? || '%' OR details LIKE '%' || ? || '%')
                LIMIT 3
            """, (exclude_cmd_id, kw, kw)).fetchall()
            for row in rows:
                results.append({
                    "source_type": "command_recent",
                    "source_id": row["id"],
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": 0,
                    "stage": "local",
                })
    finally:
        bot_conn.close()
    seen = set()
    return [r for r in results if r["source_id"] not in seen and not seen.add(r["source_id"])]


# ============================================================
# キャッシュ保存（v2.0拡張）
# ============================================================

def _cache_enrichment(cmd_id, internal, pitfalls, positive_patterns,
                      prediction, cross_project, external):
    """結果をdashboard_entriesにキャッシュ保存。"""
    import json as _json
    bot_conn = get_botsunichiroku_db_rw()
    try:
        cache_data = _json.dumps({
            "internal": internal[:10],
            "pitfalls": pitfalls[:5],
            "positive_patterns": [p if isinstance(p, dict) else p.dict() for p in positive_patterns[:5]],
            "prediction": prediction.dict() if prediction else None,
            "cross_project": cross_project[:5],
            "external": external[:5],
        }, ensure_ascii=False)
        bot_conn.execute("""
            INSERT INTO dashboard_entries (cmd_id, section, content, status, created_at)
            VALUES (?, 'enrich_cache', ?, 'cached', datetime('now'))
        """, (cmd_id, cache_data))
        bot_conn.commit()
    finally:
        bot_conn.close()


@app.get("/enrich/{cmd_id}")
def get_enrichment(cmd_id: str):
    """キャッシュ済みenrich結果を取得。"""
    import json as _json
    bot_conn = get_botsunichiroku_db()
    try:
        row = bot_conn.execute("""
            SELECT content, created_at FROM dashboard_entries
            WHERE cmd_id = ? AND section = 'enrich_cache'
            ORDER BY created_at DESC LIMIT 1
        """, (cmd_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No enrichment found for {cmd_id}")
        cached = _json.loads(row["content"])
        return {
            "cmd_id": cmd_id,
            "enriched_at": row["created_at"],
            **cached,
            "meta": {"source": "cache"},
        }
    finally:
        bot_conn.close()
```

推定変更量: main.py **+350行**（v1.0の+200行からTAGE予測+positive_patterns+外部検索+sanitizerで増加）

---

## §H 夢見機能: dream.py（v2.0追加）

### 設計思想

人間のレム睡眠: 寝ている間に記憶を整理・統合し、意外な関連を発見する。
dream.pyは**cron日次で没日録FTS5クロス相関を実行**し、PJ横断の構造類似性を発見する。

気象庁が国民1人400円で全球予報を回せる時代に、数千レコードのFTS5を棚上げする理由はない。

### 処理フロー

```
cron 03:00 daily
  ↓
dream.py
  ├─ 1. 直近7日のcmd/subtaskからキーワード抽出（MeCab）
  ├─ 2. 各キーワードで全体FTS5検索（PJ横断）
  ├─ 3. PJ間の共起パターンを検出（同じキーワードで2PJ以上ヒット）
  ├─ 4. 結果をdashboard_entries section="dream" に蓄積
  └─ 5. 顕著な発見があれば /enrich のcross_projectに自動注入
```

### 実装仕様: tools/kousatsu/dream.py

```python
#!/usr/bin/env python3
"""夢見機能: 没日録FTS5クロス相関で構造類似性を発見する。

Usage:
    python dream.py                  # 直近7日分を処理
    python dream.py --days 30        # 直近30日分を処理

crontab:
    0 3 * * * docker exec kousatsu-kousatsu-1 python /app/dream.py
"""
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

import MeCab

BOTSUNICHIROKU_DB = os.environ.get("BOTSUNICHIROKU_DB", "/data/botsunichiroku.db")
INDEX_DB = os.environ.get("INDEX_DB", "/data/search_index.db")

def extract_nouns(text: str) -> list[str]:
    """MeCabで名詞・動詞・形容詞を抽出。"""
    tagger = MeCab.Tagger()
    node = tagger.parseToNode(text)
    words = []
    while node:
        features = node.feature.split(",")
        if features[0] in ("名詞", "動詞", "形容詞") and len(node.surface) >= 2:
            words.append(node.surface)
        node = node.next
    return list(dict.fromkeys(words))  # 順序保持de-dup


def dream(days: int = 7):
    """直近N日のcmd/subtaskからPJ横断の構造類似性を発見する。"""
    bot_conn = sqlite3.connect(BOTSUNICHIROKU_DB)
    bot_conn.row_factory = sqlite3.Row
    idx_conn = sqlite3.connect(f"file:{INDEX_DB}?mode=ro", uri=True)
    idx_conn.row_factory = sqlite3.Row

    # 1. 直近N日のcmd/subtaskからキーワード抽出
    recent_cmds = bot_conn.execute("""
        SELECT id, command, details, project
        FROM commands
        WHERE created_at > datetime('now', ? || ' days')
          AND status = 'done'
    """, (f"-{days}",)).fetchall()

    # 2. PJごとのキーワード集合を構築
    pj_keywords: dict[str, set[str]] = defaultdict(set)
    all_keywords: set[str] = set()
    for cmd in recent_cmds:
        text = f"{cmd['command']} {cmd['details'] or ''}"
        nouns = extract_nouns(text)
        pj = cmd["project"] or "unknown"
        pj_keywords[pj].update(nouns)
        all_keywords.update(nouns)

    # 3. PJ間の共起パターン検出
    # キーワードが2PJ以上で出現 → 構造類似性の候補
    cross_pj_keywords = []
    for kw in all_keywords:
        pjs_with_kw = [pj for pj, kws in pj_keywords.items() if kw in kws]
        if len(pjs_with_kw) >= 2:
            # FTS5で具体的なヒットを確認
            try:
                hits = idx_conn.execute("""
                    SELECT source_type, source_id, project,
                           snippet(search_index, 6, '...', '...', '', 32) AS snippet
                    FROM search_index
                    WHERE search_index MATCH ?
                    ORDER BY rank LIMIT 6
                """, (f'"{kw}"',)).fetchall()
                if len(hits) >= 2:
                    hit_projects = set(h["project"] for h in hits)
                    if len(hit_projects) >= 2:
                        cross_pj_keywords.append({
                            "keyword": kw,
                            "projects": list(hit_projects),
                            "hits": [{"source_id": h["source_id"], "project": h["project"],
                                      "snippet": h["snippet"]} for h in hits],
                        })
            except Exception:
                pass

    # 4. dashboard_entries section="dream" に蓄積
    if cross_pj_keywords:
        dream_content = json.dumps({
            "dream_date": datetime.now().isoformat(),
            "days_analyzed": days,
            "cmds_analyzed": len(recent_cmds),
            "cross_pj_discoveries": cross_pj_keywords[:20],
            "summary": f"{len(cross_pj_keywords)}件のPJ横断キーワードを発見。"
                       f"分析対象: 直近{days}日のcmd {len(recent_cmds)}件",
        }, ensure_ascii=False)
        bot_conn_rw = sqlite3.connect(BOTSUNICHIROKU_DB)
        bot_conn_rw.execute("""
            INSERT INTO dashboard_entries (section, content, status, created_at)
            VALUES ('dream', ?, 'generated', datetime('now'))
        """, (dream_content,))
        bot_conn_rw.commit()
        bot_conn_rw.close()
        print(f"[dream] {len(cross_pj_keywords)}件のPJ横断構造類似性を発見。dashboard_entriesに蓄積。")
    else:
        print("[dream] PJ横断の構造類似性は検出されず。")

    bot_conn.close()
    idx_conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="夢見機能")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    dream(args.days)
```

### crontab設定

```
# /etc/cron.d/kousatsu-dream
0 3 * * * root docker exec kousatsu-kousatsu-1 python /app/dream.py >> /tmp/dream.log 2>&1
```

### /enrichとの統合（§L lazy decayと連携）

dream結果の注入は§Lの忘却曲線と統合。詳細は§Lの`_inject_dream_discoveries`を参照。

- 30日間未参照のdream結果はstatus="forgotten"に遷移（=忘却）
- 参照されたdream結果はlast_accessedが更新される（=リハーサル）
- 殿が採用したdreamはstatus="applied"に昇格

推定変更量: **dream.py 120行**（独立スクリプト） + main.py +40行（注入+忘却部分）

---

## §I TAGE的判断予測の詳細設計（v2.0追加）

### 設計思想

CPUのTAGE (TAgged GEometric history length) 分岐予測器:
- 複数の履歴テーブルを幾何級数的に異なる長さで保持
- 最長一致テーブルの予測を採用
- 2-3bit飽和カウンタで確信度を管理

殿の判断パターンもこの構造でモデル化:

| テーブル | 履歴長 | 内容 | 例 |
|---------|--------|------|-----|
| T1 | 直近5cmd | 殿の最近の判断傾向 | 「直近5cmdは全てPython」 |
| T2 | 同PJ内10cmd | PJ固有の殿の好み | 「shogunは常にSQLite」 |
| T3 | 全PJ30cmd | 殿の普遍的判断基準 | 「月額課金は100%拒否」 |

### 確信度の飽和カウンタ

```
一致件数:  1件 → low    (初回一致。偶然かもしれない)
           2件 → medium (パターンの兆し)
          3件+ → high   (確立されたパターン。投機実行可)
```

確信度highの判断は足軽が殿に聞かず投機実行可能。
ミスプレディクション時はaudit FAILで巻き戻し（コストは許容）。

### 既知の判断パターン（初期テーブル）

| question | predicted_choice | confidence根拠 | 実例cmd |
|----------|-----------------|---------------|---------|
| DBエンジン選定 | SQLite | T3: cmd_383,391,393,395,396,397全てSQLite | high |
| 言語選定 | Python | T3: 既存基盤が全てPython | high |
| デプロイ方式 | Docker Compose | T2: 高札=Docker, arsprout=Docker | high |
| 月額課金 | 拒否 | T3: Memory MCP system-rulesに明記 | high |
| 設計方針 | マクガイバー精神 | T3: 全cmd一貫 | high |
| VPN方式 | WireGuard | T2: cmd_392,394,395 | high |
| テスト方式 | pytest | T3: 全PJ一貫 | high |

### 判断予測の使われ方

```
家老がcmd addを発行
  ↓
高札 /enrich が自動実行
  ↓
prediction: { question: "DBエンジン", predicted_choice: "SQLite", confidence: "high" }
  ↓
家老がinbox YAMLに prediction を添付
  ↓
足軽: 確信度high → SQLiteで実装開始（殿に聞かない）
  ↓
お針子: audit PASS → パターン強化 / audit FAIL → パターン弱化+殿に確認
```

---

## §J 正の強化信号の詳細設計（v2.0追加）

### 設計思想

現行: 負の信号（FAIL/rework/blocked）のみ。「ああ、それそれ」がない。
追加: audit PASS済みの類似タスクパターンを「positive_patterns」として提示。
「この方向で合ってる」という正のシグナルを提供する。

### データ構造

```python
# positive_patterns[]
{
    "source_id": "subtask_823",      # audit PASS済みのsubtask
    "project": "shogun",
    "description": "YAML通信プロトコル設計→audit PASS",
    "strength": "high",              # high/medium/low
    "hint": "この方向を継続せよ"
}
```

### strength判定ロジック

```
同一キーワードでaudit PASS 3件以上 → high  (確立されたパターン)
同一キーワードでaudit PASS 2件      → medium (傾向あり)
同一キーワードでaudit PASS 1件      → low   (参考情報)
```

### audit結果のフィードバックループ

```
/enrich → positive_patterns提示
  ↓
足軽が実装（positive_patternsの方向を踏襲）
  ↓
お針子 audit PASS
  ↓ (将来Phase: audit PASS時にpositive_patternsテーブルを自動更新)
  ↓ (Phase 0では dashboard_entries section="enrich_cache" に含まれるのみ)
positive_patterns strength++
```

Phase 0では明示的なフィードバック更新は行わない。
/enrichの都度、没日録のaudit_status="done"レコードからSQLで動的に抽出する。
これはFTS5と同じ「クエリ時計算」方式であり、追加テーブルは不要。

---

## §K サニタイズ層: sanitizer.py（v2.0追加）

### 設計思想

外部検索結果のみ対象（内部没日録は信頼）。
shogunの構造分離（情報層と実行層が分かれている）が最大の防御。
sanitizer.pyはTier1正規表現ベース、約50行。

### 実装仕様: tools/kousatsu/sanitizer.py

```python
"""外部検索結果のサニタイズ層。

Tier1: 正規表現ベース（~50行）
- injection pattern除去
- truncate 500文字
- provenance tag付与

shogunの構造分離（情報層と実行層の分離）が最大の防御:
- 外部検索結果は /enrich レスポンスのexternal[]に格納されるだけ
- 実行指示には一切使われない
- 家老/足軽が参考情報として読むのみ
"""
import re
from typing import Any

# --- injection pattern ---
INJECTION_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),       # onload=, onclick=, etc.
    re.compile(r"\{\{.*?\}\}"),                       # template injection
    re.compile(r"\$\{.*?\}"),                         # string interpolation
    re.compile(r"exec\s*\(", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"import\s+os", re.IGNORECASE),
    re.compile(r"subprocess\.", re.IGNORECASE),
    re.compile(r"system\s*\(", re.IGNORECASE),
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r";\s*--", re.IGNORECASE),             # SQL injection
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"prompt\s*injection", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now", re.IGNORECASE),   # role hijacking
]

MAX_LENGTH = 500
PROVENANCE_PREFIX = "[external] "


def sanitize_external_result(result: dict[str, Any]) -> dict[str, Any]:
    """外部検索結果をサニタイズして返す。

    Args:
        result: {"source": str, "title": str, "snippet": str, "url": str}

    Returns:
        サニタイズ済み結果。injection patternは除去、500文字truncate、provenance tag付与。
    """
    sanitized = {}
    for key in ("source", "title", "snippet", "url"):
        value = str(result.get(key, ""))
        # injection pattern除去
        for pattern in INJECTION_PATTERNS:
            value = pattern.sub("[REMOVED]", value)
        # truncate
        if len(value) > MAX_LENGTH:
            value = value[:MAX_LENGTH] + "..."
        sanitized[key] = value

    # provenance tag
    sanitized["snippet"] = PROVENANCE_PREFIX + sanitized["snippet"]
    sanitized["sanitized"] = True
    return sanitized
```

推定: **~50行**。独立モジュール。main.pyからは`from sanitizer import sanitize_external_result`で呼ぶ。

---

## §L 忘却曲線: lazy decay（v2.1追加）

### 設計思想

**完全な記憶は完全な麻痺。** 古い失敗を永遠に同じ重みで保持したら動けなくなる。

人間の脳はシナプス減衰で自動忘却する。コストは基礎代謝に含まれる（タダ）。
コンピュータで同等を実現する最安の方式は**lazy decay（遅延評価）**:
- 物理削除しない（GCコスト不要）
- 参照時に減衰計算する（書き込みは最小限）
- リハーサル（再参照）で記憶を強化する（脳と同じ）

### 実装: dashboard_entries last_accessed カラム

```sql
-- マイグレーション: dashboard_entries に last_accessed を追加
ALTER TABLE dashboard_entries ADD COLUMN last_accessed INTEGER DEFAULT 0;
-- POSIX time。INTEGER = SQLite最軽量型（8バイト）
-- デフォルト0 = 「一度も参照されていない」（created_atから減衰開始）
```

### decay関数

```python
import time

def apply_decay(fts5_rank: float, last_accessed: int, created_at_iso: str) -> float:
    """FTS5 rankに忘却曲線の減衰を適用する。

    effective_score = fts5_rank * (0.95 ** (days_since_access / 30))

    - 30日で5%減衰、1年で約54%に減衰、2年で約29%に
    - last_accessed=0（未参照）の場合はcreated_atから計算
    - /enrichが参照するたびにlast_accessedが更新される（リハーサル効果）
    """
    now = int(time.time())
    if last_accessed > 0:
        reference_time = last_accessed
    else:
        # created_atからPOSIX time変換
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            reference_time = int(dt.timestamp())
        except (ValueError, AttributeError):
            reference_time = now  # パース失敗時は減衰なし

    days_since = max(0, (now - reference_time)) / 86400
    decay_factor = 0.95 ** (days_since / 30)
    return fts5_rank * decay_factor


# 忘却閾値: この値以下は非表示（=忘却）
DECAY_THRESHOLD = -0.1  # FTS5 rankは負値（低いほど良い）。-0.1に近づいたら忘却
```

### /enrich内での適用箇所

```python
# Stage 1, Stage 2 のFTS5結果にdecay適用
for result in internal_results:
    result["score"] = apply_decay(
        result["score"],
        result.get("last_accessed", 0),
        result.get("created_at", "")
    )
    # 閾値以下は除外（忘却）
internal_results = [r for r in internal_results if r["score"] < DECAY_THRESHOLD or r["score"] == 0]

# /enrichが結果を返す時にlast_accessedを更新（リハーサル）
def _update_last_accessed(source_ids: list[str]):
    """参照された知見のlast_accessedを更新。リハーサル効果。"""
    now_ts = int(time.time())
    bot_conn = get_botsunichiroku_db_rw()
    try:
        for sid in source_ids:
            bot_conn.execute("""
                UPDATE dashboard_entries
                SET last_accessed = ?
                WHERE cmd_id = ? AND section = 'enrich_cache'
            """, (now_ts, sid))
        bot_conn.commit()
    finally:
        bot_conn.close()
```

### pitfallsの時間減衰

```python
def decay_pitfall_severity(severity: str, completed_at_iso: str) -> str:
    """pitfallsのseverityを時間経過で減衰させる。

    critical → 90日で medium に減衰
    medium   → 180日で low に減衰
    low      → 365日で非表示（返却しない）
    """
    from datetime import datetime
    try:
        completed = datetime.fromisoformat(completed_at_iso.replace("Z", "+00:00"))
        days_ago = (datetime.now(completed.tzinfo or None) - completed).days
    except (ValueError, AttributeError, TypeError):
        return severity  # パース失敗時は減衰なし

    if severity == "critical" and days_ago > 90:
        return "medium"
    elif severity == "medium" and days_ago > 180:
        return "low"
    elif severity == "low" and days_ago > 365:
        return "forgotten"  # 呼び出し側で除外
    return severity
```

### dreamの忘却（status遷移）

```python
# dream.pyのdashboard_entriesにもlast_accessed適用
# dream結果のstatus遷移:
#   generated → applied（殿が採用 → cross_projectとして活用された）
#   generated → forgotten（30日間参照なし → /enrichのdream注入対象外）

def _inject_dream_discoveries(keywords, cross_project):
    """dream結果注入時にlast_accessedチェック+更新。"""
    now_ts = int(time.time())
    bot_conn = get_botsunichiroku_db()
    try:
        row = bot_conn.execute("""
            SELECT id, content, last_accessed, created_at FROM dashboard_entries
            WHERE section = 'dream'
              AND status != 'forgotten'
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()
        if not row:
            return

        # 30日間参照なし → forgotten
        la = row["last_accessed"] or 0
        if la > 0 and (now_ts - la) > 30 * 86400:
            bot_conn_rw = get_botsunichiroku_db_rw()
            bot_conn_rw.execute("""
                UPDATE dashboard_entries SET status = 'forgotten'
                WHERE id = ?
            """, (row["id"],))
            bot_conn_rw.commit()
            bot_conn_rw.close()
            return

        # dream結果をcross_projectに注入
        import json as _json
        dream = _json.loads(row["content"])
        injected = False
        for discovery in dream.get("cross_pj_discoveries", []):
            if any(kw in discovery["keyword"] for kw in keywords):
                for hit in discovery["hits"][:2]:
                    cross_project.append({
                        "source_id": hit["source_id"],
                        "project": hit["project"],
                        "hint": f"[dream] キーワード '{discovery['keyword']}' でPJ横断類似性を検出",
                        "confidence": 0.4,
                        "stage": "dream",
                    })
                    injected = True

        # 参照されたらlast_accessed更新（リハーサル）
        if injected:
            bot_conn_rw = get_botsunichiroku_db_rw()
            bot_conn_rw.execute("""
                UPDATE dashboard_entries SET last_accessed = ?, status = 'applied'
                WHERE id = ?
            """, (now_ts, row["id"]))
            bot_conn_rw.commit()
            bot_conn_rw.close()
    finally:
        bot_conn.close()
```

### コスト分析

| 操作 | コスト |
|------|-------|
| カラム追加 | ALTER TABLE 1回。既存行はデフォルト0 |
| 書き込み | INTEGER 1つ（8バイト）。/enrich応答時のUPDATE |
| 読み込み | 引き算と掛け算1回。インデックス不要（アプリ層計算） |
| ストレージ | 1レコードあたり+8バイト。全dashboard_entries合計で数KB |
| GC | **不要**。物理削除しない。score閾値で非表示にするだけ |

殿の言葉通り、「POSIX time書き込むだけ」。

---

## §E テスト計画（v2.1拡張）

### テストケース一覧

| # | テスト名 | 入力 | 期待結果 | 検証ポイント |
|---|---------|------|---------|-------------|
| T1 | 基本enrich（局所） | `{"cmd_id":"cmd_test","text":"温度制御 閾値 設計","project":"uecs-llm"}` | internal ≥ 1件、stage="local" | Stage 1局所検索が動作する |
| T2 | PJ横断検出（拡大） | `{"cmd_id":"cmd_test","text":"設計書","project":"shogun"}` | cross_project ≥ 1件、stage="global" | Stage 2拡大検索が分離される |
| T3 | pitfalls検出 | `{"cmd_id":"cmd_test","text":"設計書 commit push"}` | pitfalls ≥ 1件（P001） | コミット漏れパターンが検出される |
| T4 | positive_patterns検出 | `{"cmd_id":"cmd_test","text":"設計"}` | positive_patterns ≥ 1件 | audit PASS済みパターンが返る |
| T5 | TAGE予測 | `{"cmd_id":"cmd_test","text":"DB SQLite 設計"}` | prediction.predicted_choice="SQLite", confidence="high" | TAGE分岐予測が動作する |
| T6 | 空テキスト | `{"cmd_id":"cmd_test","text":""}` | internal=[], prediction=null, 200 OK | エラーにならない |
| T7 | キャッシュ保存+取得 | POST /enrich → GET /enrich/cmd_test | 同一内容（prediction含む） | dashboard_entriesに全フィールド保存 |
| T8 | キャッシュ未存在 | GET /enrich/cmd_nonexistent | 404 | 適切なエラーメッセージ |
| T9 | worker_id付き | `{"cmd_id":"cmd_test","text":"test","worker_id":"ashigaru6"}` | P005パターン検出 | worker別pitfallsが動作する |
| T10 | サニタイザ | sanitize_external_result with injection payload | injection pattern除去、500文字truncate | sanitizer.pyが機能する |
| T11 | 直近cmd補完 | 直前にcmd addした直後にenrich | Stage 2d結果に含まれる | FTS5遅延をSQL LIKEで補完 |
| T12 | 外部検索(sanitized) | `{"cmd_id":"cmd_test","text":"Python FastAPI","include_external":true}` | external[].sanitized=true | 外部結果がサニタイズされている |
| T13 | dream結果注入 | dream.pyを事前実行後にenrich | cross_projectにstage="dream"が含まれる | dream発見が注入される |
| T14 | decay関数 | apply_decay(rank=-8.5, 60日前参照) | effective_score ≈ -8.5 * 0.95^2 ≈ -7.67 | 60日で約10%減衰 |
| T15 | pitfall severity減衰 | severity="critical", 91日前完了 | "medium"に減衰 | 90日閾値を超えたら減衰 |
| T16 | pitfall severity忘却 | severity="low", 366日前完了 | "forgotten"（非表示） | 365日で忘却 |
| T17 | dream忘却 | dream entry, last_accessed=31日前 | status→"forgotten" | 30日間未参照で忘却 |
| T18 | リハーサル効果 | /enrich→結果参照→last_accessed更新 | last_accessed=現在時刻 | 参照で記憶が強化される |
| T19 | 高負荷 | 100件連続POST /enrich | 全て200 OK、平均<50ms | 性能劣化なし（decay計算含む） |

### テストデータ

```python
@pytest.fixture
def enrich_test_data(botsunichiroku_db):
    """enrich用テストデータ: 失敗+成功パターン含む"""
    conn = botsunichiroku_db
    # ハルシネーション事例
    conn.execute("""INSERT INTO subtasks (id, parent_cmd, worker_id, project,
        description, status, wave, audit_status)
        VALUES ('subtask_test_hal', 'cmd_test_284', 'ashigaru6', 'shogun',
        '設計書ファイル作成+commit', 'blocked', 1, NULL)""")
    conn.execute("""INSERT INTO reports (worker_id, task_id, timestamp, status, summary)
        VALUES ('ashigaru6', 'subtask_test_hal', '2026-03-01T00:00:00', 'error',
        'ハルシネーション: commitハッシュ捏造。ファイル不在。')""")
    # コミット漏れ事例
    conn.execute("""INSERT INTO subtasks (id, parent_cmd, worker_id, project,
        description, status, wave, audit_status)
        VALUES ('subtask_test_cm', 'cmd_test_365', 'ashigaru6', 'shogun',
        'context/karo-*.md作成+commit+push', 'done', 1, 'done')""")
    conn.execute("""INSERT INTO reports (worker_id, task_id, timestamp, status, summary)
        VALUES ('ashigaru6', 'subtask_test_cm', '2026-03-01T01:00:00', 'done',
        'コミット漏れ: git add忘れ。')""")
    # audit PASS成功事例（positive_patterns用）
    conn.execute("""INSERT INTO subtasks (id, parent_cmd, worker_id, project,
        description, status, wave, audit_status)
        VALUES ('subtask_test_pass', 'cmd_test_391', 'ashigaru1', 'shogun',
        '設計書作成+commit+push完了', 'done', 1, 'done')""")
    conn.execute("""INSERT INTO reports (worker_id, task_id, timestamp, status, summary)
        VALUES ('ashigaru1', 'subtask_test_pass', '2026-03-02T00:00:00', 'done',
        '設計書作成完了。全セクション網羅。audit PASS。')""")
    conn.commit()
```

---

## §F subtask分解案（v2.1全機能統合版）

### Phase 0 実装タスク（全機能含む）

| # | subtask | 内容 | worker推奨 | 依存 | Bloom | 推定行数 |
|---|---------|------|-----------|------|-------|---------|
| F0-1 | main.py: POST /enrich (局所+拡大+pitfalls) | Stage 1-2b実装 | sonnet | なし | L3 | +200行 |
| F0-2 | main.py: positive_patterns+TAGE予測 | Stage 2c + _predict_decision | sonnet | F0-1 | L4 | +100行 |
| F0-3 | sanitizer.py: サニタイズ層 | Tier1正規表現フィルタ | haiku | なし | L2 | +50行 |
| F0-4 | main.py: 外部検索(sanitized)+GET /enrich | Stage 3 + キャッシュ | sonnet | F0-1,F0-3 | L3 | +80行 |
| F0-5 | dream.py: 夢見機能 | cron日次FTS5クロス相関 | sonnet | なし | L4 | +120行 |
| F0-6 | main.py: dream結果注入+忘却 | _inject_dream_discoveries（忘却status遷移含む） | haiku | F0-1,F0-5 | L2 | +40行 |
| F0-7 | botsunichiroku.py: cmd addフック | subprocess.Popen curl追加 | haiku | なし | L2 | +16行 |
| F0-8 | main.py: lazy decay (忘却曲線) | apply_decay+pitfall減衰+last_accessed更新+DBマイグレーション | sonnet | F0-1 | L3 | +60行 |
| F0-9 | test_search.py: enrichテスト | T1-T19の19ケース（decay含む） | sonnet | F0-1〜F0-8 | L3 | +250行 |
| F0-10 | Docker再ビルド+cron設定+動作確認 | compose build+up+cron+ALTERマイグレーション | haiku | F0-1〜F0-9 | L1 | 設定のみ |

**Wave構成**:
- **Wave 1** (並列可): F0-1 + F0-3 + F0-5 + F0-7（4本並列）
- **Wave 2** (W1後): F0-2 + F0-4 + F0-6 + F0-8（4本並列）
- **Wave 3**: F0-9 + F0-10（テスト+統合）

推定合計変更量:
- main.py +480行（+405 + lazy decay +60 + dream忘却 +15）
- dream.py +120行（新規）
- sanitizer.py +50行（新規）
- botsunichiroku.py +16行
- test_search.py +250行（19ケース）
- cron設定: 1行
- DBマイグレーション: ALTER TABLE 1行

---

## §G v1.0設計書→v2.1橋頭堡 差分サマリ

| セクション | v1.0橋頭堡 | v2.1（本書） | 変更種別 |
|-----------|-----------|-------------|---------|
| 冒頭 | 帰納3法則×演繹3原理→3設計原則 | **法則4(正の信号欠落)+原理4(TAGE)→5設計原則** | 拡張 |
| §A 内部検索 | 3段(FTS5→pitfalls→recent) | **局所→拡大→外部の脳型3段階+positive_patterns+decay適用** | 再構成 |
| §B API | internal/pitfalls/cross_project | **+prediction+positive_patterns+external(sanitized)** | 大幅拡張 |
| §D main.py | +200行 | **+480行** | 規模増大 |
| §E テスト | T1-T10 (10本) | **T1-T19 (19本、decay含む)** | 追加 |
| §F subtask | F0-1〜F0-5 (5本, 3Wave) | **F0-1〜F0-10 (10本, 3Wave)** | 規模増大 |
| §H | なし | **dream.py: 夢見機能** | 新規 |
| §I | なし | **TAGE的判断予測 詳細設計** | 新規 |
| §J | なし | **正の強化信号 詳細設計** | 新規 |
| §K | なし | **sanitizer.py: サニタイズ層** | 新規 |
| §L | なし | **lazy decay: 忘却曲線。POSIX time+指数減衰+pitfall severity減衰+dream忘却** | 新規 |

---

## 付録: 見落としの可能性

- **MeCabの形態素解析精度**: 技術用語（WireGuard, FTS5等）がMeCabで正しくトークン化されるか。英語交じりテキストでの精度劣化。→ extract_nouns()が英単語をそのまま返すか要確認
- **dashboard_entries肥大化**: enrich_cache + dream が蓄積。→ 30日以上古いenrich_cacheをGC対象に（scripts/shogun-gc.sh拡張）
- **並行アクセス**: cmd add直後にcurl &で/enrichが呼ばれるが、没日録DB WALモードなので読み書き並行は安全
- **FTS5 MATCH上限**: 15キーワードのOR結合。キーワード数上限は設定済み
- **TAGE初期テーブルのハードコード**: known_patternsが静的リスト。将来的にはdashboard_entries section="tage_patterns"に動的蓄積する拡張が可能だが、Phase 0ではハードコードで十分（殿の基本判断パターンは安定している）
- **DuckDuckGo Instant Answer APIの制約**: 日本語クエリに弱い。技術用語は英語化して検索する方が有効。Phase 1でX API追加時に改善
- **dream.pyのcron実行タイミング**: 03:00 JSTだがDockerコンテナ内のTZがUTCの場合ずれる。→ TZ=Asia/Tokyoをdocker-compose.ymlに追加
- **positive_patternsの精度**: audit_status="done"は167件あるが、「何が良かったか」の情報は元々ない。descriptionとreport.summaryからのキーワード一致のみで判定しており、精度は高くない。ただし「参考情報」として提示する分には十分
- **lazy decayの減衰率0.95^(days/30)の妥当性**: 30日で5%、1年で54%、2年で29%。「1年前の失敗は半分の重み」は直感的に妥当。ただし殿の判断パターン（TAGE）は時間減衰させるべきではない（好みは安定している）→ TAGE予測にはdecay適用しない
- **ALTER TABLEのマイグレーション**: 既存dashboard_entriesへのカラム追加はSQLite ALTER TABLEで対応。既存行はデフォルト0。ダウンタイムなし
- **last_accessed更新の競合**: /enrichの並行呼び出しでlast_accessedのUPDATEが競合する可能性。WALモードのためブロッキングは発生しないが、最後のUPDATE winが起こる。実害なし（数秒のずれは忘却曲線に影響しない）
