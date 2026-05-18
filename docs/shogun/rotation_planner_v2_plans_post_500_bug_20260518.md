# rotation-planner v2: POST /api/plans 500 バグ調査 (cmd_585 Wave 1)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1256 / cmd_585 |
| 作成日時 | 2026-05-18T17:35 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象ファイル | api/routers/plans.py:80 + rotation_planner/common/db_access.py:621 |
| 報告書範囲 | read-only調査+設計のみ (実装は別subtask) |

---

## §1 エグゼクティブサマリ

**症状**: 殿が輪作計画画面で「最適化実行→計画名→保存」押下時 `POST /api/plans` → **500 Internal Server Error**

**真因**: **新仮説 δ = API/Repository キーワード引数名 mismatch** 確定
- `plans.py:80` で `PlanRepository.create_plan(user_id=..., plan_data={...})` と呼出
- `db_access.py:621` 関数定義は `def create_plan(user_id: int, data: Dict)` ← 引数名 **`data`**
- 結果: `TypeError: PlanRepository.create_plan() got an unexpected keyword argument 'plan_data'`

**殿仮説検証**:
- α schema不整合: **否定** (rotation_plans / plan_details schema 健全)
- β rotation_plans テーブル不存在: **否定** (テーブル存在確認)
- γ その他: **該当・新仮説δで具体化**

**推奨修正案A** (最小変更・1行):
```python
# plans.py:80
plan_id = PlanRepository.create_plan(
    user_id=current_user["id"],
    data={                    # ← plan_data から data に変更
        ...
    }
)
```

**殿への質問** (3問以内):
- Q1: 案A承認可否?(plans.py L80 `plan_data=` → `data=` 1行変更)
- Q2: upstream PR要否(D2撤廃継続中・rotation-planner自リポ)?
- Q3: 他router/Repository で同種の引数名不一致が無いか別subtaskで検証要?

---

## §2 Phase 1 journalctl スタックトレース

### 500 Error 発生時刻と request
```
May 18 17:25:41 ik1-421-42663 uvicorn[4088765]: INFO:     202.212.203.231:0 - "POST /api/plans HTTP/1.0" 500 Internal Server Error
May 18 17:29:13 ik1-421-42663 uvicorn[4088765]: INFO:     202.212.203.231:0 - "POST /api/plans HTTP/1.0" 500 Internal Server Error
```
※ 殿が複数回試行・両回とも同じエラー再現

### スタックトレース末尾 (核心)
```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  ...(starlette/fastapi middleware stack 省略)
  File "/var/www/rotation-planner-v2/app/api/routers/plans.py", line 79, in create_plan
    plan_id = PlanRepository.create_plan(
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: PlanRepository.create_plan() got an unexpected keyword argument 'plan_data'
```

→ `plans.py:79` の `PlanRepository.create_plan(...)` 呼出時の keyword argument 不一致

---

## §3 Phase 2 plans.py 実装 + db_access.py + schema 突合

### plans.py:77-89 (POST /api/plans 実装)
```python
@router.post("/api/plans", response_model=PlanResponse, status_code=201)
def create_plan(plan: PlanCreate, current_user: Dict = Depends(get_current_user)):
    plan_id = PlanRepository.create_plan(
        user_id=current_user["id"],
        plan_data={                    # ★★★ "plan_data" として呼出 ★★★
            "name": plan.name,
            "start_year": plan.start_year,
            "end_year": plan.end_year,
            "details": plan.details
        }
    )
    created = require_found(PlanRepository.get_plan(plan_id), "輪作計画")
    return PlanResponse(**created)
```

### db_access.py:621- (PlanRepository.create_plan 定義)
```python
def create_plan(user_id: int, data: Dict[str, Any]) -> int:    # ★★★ 引数名は "data" ★★★
    """
    輪作計画を作成

    Args:
        user_id: ユーザーID
        data: 計画データ
            - name: 計画名（必須）
            - start_year: 開始年（必須）
            - end_year: 終了年（必須）
            - constraints: 制約設定（dict）
            - details: 計画詳細リスト [{field_id, year, crop}, ...]

    Returns:
        作成された計画のID
    """
    try:
        with get_db() as conn:
            constraints_json = json.dumps(data.get('constraints', {}), ensure_ascii=False)
            metadata_json = json.dumps(data.get('metadata', {}), ensure_ascii=False)
            cursor = conn.execute("""
                INSERT INTO rotation_plans (user_id, name, start_year, end_year,
                                           constraints_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, data['name'], data['start_year'], data['end_year'],
                constraints_json, metadata_json
            ))
            plan_id = cursor.lastrowid

            for detail in data.get('details', []):
                conn.execute("""
                    INSERT INTO plan_details (plan_id, field_id, year, crop)
                    VALUES (?, ?, ?, ?)
                """, ...)
```

→ Repository 側は `data` を期待・API側は `plan_data` で呼出 → 不一致

### Schema (健全)
```sql
CREATE TABLE rotation_plans (
    id, user_id, name, start_year TEXT, end_year TEXT,
    constraints_json TEXT, metadata_json TEXT,
    created_at, updated_at
);

CREATE TABLE plan_details (
    id, plan_id, field_id, year TEXT, crop TEXT, created_at,
    UNIQUE(plan_id, field_id, year)
);
```
→ INSERT SQL と schema は完全整合・schema問題ではない

---

## §4 真因特定 (新仮説δ確定)

| 仮説 | 判定 | 根拠 |
|---|---|---|
| α schema不整合 | **否定** | rotation_plans/plan_details schema は健全・INSERT SQL と一致 |
| β rotation_plans テーブル不存在 | **否定** | `.schema rotation_plans` で存在確認 |
| γ FK violation | **否定** (該当エラー無し) | スタックトレースは TypeError であり SQL層に到達せず |
| **δ API/Repository キーワード引数名 mismatch** | **確定** | `plan_data=` (API) vs `data` (Repository 定義) |
| ε Pydantic validation | 否定 (該当エラー無し) | 422ではなく500・Pydantic通過後の関数呼出失敗 |

### 発生メカニズム
1. ユーザー (殿) が `POST /api/plans` を送信
2. FastAPI が `PlanCreate` Pydantic schema で validation 成功 (→ plan オブジェクト)
3. `plans.py:79-86 create_plan` が呼ばれる
4. `PlanRepository.create_plan(user_id=..., plan_data={...})` 呼出
5. **Python 関数定義が `plan_data` 引数を受け付けない** → `TypeError`
6. FastAPI が 500 Internal Server Error を返却
7. **SQL層には到達せず・DBには何も記録されない**

### 影響範囲
- POST /api/plans のみ (他の GET/PUT/DELETE は別関数で影響なし)
- 殿の「最適化実行→保存」操作が **完全にブロック**
- データ整合性影響: なし (SQL未実行のため)

---

## §5 修正案 (最小変更+rollback)

### 案A (推奨・1行・最小変更)
`plans.py:80` の `plan_data` を `data` に変更:
```python
plan_id = PlanRepository.create_plan(
    user_id=current_user["id"],
    data={                       # ← plan_data から data に変更
        "name": plan.name,
        "start_year": plan.start_year,
        "end_year": plan.end_year,
        "details": plan.details
    }
)
```

**長所**: 単一行変更・rollback容易 (1行 git revert)
**短所**: なし

### 案B (positional argument)
```python
plan_id = PlanRepository.create_plan(
    current_user["id"],
    {
        "name": plan.name,
        ...
    }
)
```
**長所**: 引数名独立
**短所**: 可読性低・案Aより冗長

### 案C (Repository 側を `plan_data` に統一)
db_access.py L621 の `def create_plan(user_id, data)` を `def create_plan(user_id, plan_data)` に変更。
**長所**: API命名と統一
**短所**: PlanRepository を他箇所から呼ぶ場所があれば影響波及 (要grep)

### 推奨: **案A** (plans.py L80 `plan_data=` → `data=` 1行変更)

### Rollback
```bash
# 案A実装後の rollback
sudo -u webapp git diff frontend/.../plans.py  # 変更確認
git revert <commit-hash> && git push origin main
```

### 並行性検証 (cmd_584 への影響)
- 本 bug は cmd_584 (pinned_assignments) と**完全独立**・cmd_584の Wave 2a-2c の変更箇所 (DB+pinned_assignments.py+rotationSolver.js) には影響しない
- plans.py は cmd_584 で **無変更**・bugは PlanRepository 統合時の歴史的問題 (cmd_577 v2移行時か)

---

## §6 殿への質問 (3問以内)

| # | 質問 |
|---|---|
| **Q1** | 案A承認可否?(plans.py L80 `plan_data={...}` → `data={...}` 1行変更) |
| **Q2** | upstream PR要否(D2撤廃継続中・cmd_580 1247→cmd_581 1250→cmd_584 1254→1255 連続push実績あり) |
| **Q3** | 他router/Repository で同種の引数名不一致が無いか・別subtask (例 cmd_586) で全API/Repository ペア突合検証要? |

### 補足
- 本bug は **歴史的問題** (cmd_577 Gradio→FastAPI 移行時の引数名命名未統一が起源と推定・git logで起源特定可)
- cmd_584 (pinned_assignments) では Repository pattern 採用せず router 内 SQL直書きで実装 → 同種問題発生せず

---

## 付録: 実行コマンド一覧 (read-only)

```bash
# Phase 1 journalctl
sudo journalctl -u rotation-planner-v2.service --since "1 hour ago" --no-pager | tail -50
sudo journalctl -u rotation-planner-v2.service --since "1 hour ago" --no-pager | grep -B 5 -A 30 -E "ERROR|Traceback|500"

# Phase 2 plans.py+db_access.py+schema
sudo -u webapp sed -n "70,100p" .../api/routers/plans.py
sudo -u webapp grep -rn "class PlanRepository\|def create_plan" .../rotation_planner/
sudo -u webapp sed -n "621,660p" .../rotation_planner/common/db_access.py
sudo -u webapp sqlite3 $DB ".schema rotation_plans"
sudo -u webapp sqlite3 $DB ".schema plan_details"
```

書き込み・サービス操作・ファイル変更は一切なし。

---

(cmd_585 Wave 1 真因δ確定・案A推奨・実装は別subtask起票判断)
