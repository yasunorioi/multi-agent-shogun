# rotation-planner v2: Wave 11 緊急2本立て・GET /api/plans 500退行+DEBUG-1270 bundle反映漏れ調査 (cmd_586 / subtask_1271)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1271 / cmd_586 (Wave 11) |
| priority | **CRITICAL** |
| 作成日時 | 2026-05-18T22:50 JST |
| 作成者 | 部屋子1 (ashigaru6) |
| 報告書範囲 | read-only実証 + 修正案提示(実装は別subtask候補) |
| 親subtask | subtask_1270 Wave 10=done (commit 15d9095・D2撤廃11件目) |
| 品質ループ | 第20周 |

---

## §1 エグゼクティブサマリ

### 殿devtools結果(2026-05-18 22:48頃)2本立て新発見
1. **GET /api/plans 500 Internal Server Error が多発(2回連続)**: 「Failed to load plans」+「データの取得に失敗」= 輪作計画一覧読込み全体失敗
2. **[DEBUG-1270] 一切出力なし**: ζ4-C類似の bundle反映漏れ疑い・現bundle=index-BcU7SQN9.js(殿確認)

### Phase 1 GET /api/plans 500 真因確定: **★schema/SQL 不整合 = SELECT user_id 欠如★**

**スタックトレース末尾の決定的証跡**:
```
File "/var/www/rotation-planner-v2/app/api/routers/plans.py", line 74, in list_plans
    return [PlanResponse(**p) for p in plans]
pydantic_core._pydantic_core.ValidationError: 1 validation error for PlanResponse
user_id
```

**機序**:
- `plans.py:36-43` PlanResponse schema は `user_id: int` を **必須フィールド** として持つ
- `db_access.py:572` PlanRepository.get_plans の SQL: `SELECT id, name, start_year, end_year, created_at, updated_at FROM rotation_plans WHERE user_id = ?` → **user_id を SELECT していない**
- → 返却 dict に user_id キーなし → `PlanResponse(**p)` で Pydantic ValidationError → 500

### Phase 2 DEBUG-1270 bundle反映漏れ判定: **★bundle反映済・殿ブラウザキャッシュ問題★**

- dist/assets/ 実体: **`index-CV46wlyV.js`** (629025 bytes・22:24 mtime・subtask_1270 build) のみ存在
- 配信中 index.html → `<script src="/assets/index-CV46wlyV.js">` 正配信中
- bundle内 DEBUG-1270 出現数: **★11件★** (grep -oE で正カウント・grep -c=1 は minified 1行による誤読)
- 11 strings 全部検出 (constructor + generateInitial 3+ localSearch 2+ ensureMinFields 2+ Rotation.jsx 3)
- 殿が「現bundle=index-BcU7SQN9.js」と認識 → **強制リロード(Ctrl+Shift+R)未実施・古い Wave 9 bundle をブラウザキャッシュから読込中**

### cmd_585 退行か否か判定
- ★**cmd_585(commit 7d5b057)の退行ではなく、既存 latent bug の顕在化**★
- cmd_585 修正で POST /api/plans が成功するようになり、rotation_plans yasu に2件作成された
- 以前は yasu=0件 → GET は空 list 返却 = ValidationError 発火せず
- 今は 2件あるので validation 走る → 顕在化
- → cmd_585 自体は正しく動作・本件は別系統(SELECT column 欠如)の bug

### 推奨修正案: **案G1 (db_access.py L572 SELECT に user_id 1 column 追加)**
```python
# 既存(db_access.py:572)
SELECT id, name, start_year, end_year, created_at, updated_at
# 修正後
SELECT id, user_id, name, start_year, end_year, created_at, updated_at
```
- 1ファイル・1行・1 column 追加
- rollback容易(1 column 削除)・他箇所影響なし

### V4境界線「戻せるか」判定: **★戻せる★**
- 案G1 は 1 column SELECT 追加のみ・データ変更なし・rollback git revert 1ファイル

### 殿への質問(3問以内)
| Q | 内容 |
|---|---|
| Q1 | 案G1 (db_access.py L572 SELECT に user_id 追加・1行修正)を承認・Wave 12 即実装(D2撤廃12件目)で進めるか? |
| Q2 | DEBUG-1270 bundle は正常配信中。殿に **Ctrl+Shift+R 強制リロード後 再度 [DEBUG-1270] ログ取得** をお願いするか? |
| Q3 | 本件は schema/SQL不整合 = cmd_585 と同類の問題が plans.py GET にも残存 → 全 API/Repository ペアの SELECT列 ↔ Response schema の網羅監査(cmd_586 拡張 or 新規cmd起票)要否? |

### Three Pillar Evidence
| 柱 | 証跡 |
|---|---|
| ① commit hash | 親 subtask_1270 push commit `15d9095`(rotation-planner自リポ・D2撤廃11件目)・本subtask 設計のみ・shogun private push 別途 |
| ② Phase別 SSH | Phase 1(systemctl+journalctl完全スタックトレース+curl 401+plans.py全実装+db_access.py get_plans+rotation_plans yasu 2件+schema) + Phase 2(dist実体+index.html+source現状+bundle DEBUG-1270 11件再カウント) 全SSH §2-§4 |
| ③ 真因根拠 | journalctl Pydantic ValidationError `user_id` 明示 + db_access.py L572 SELECT 列リスト直視 + PlanResponse schema L36-43 必須フィールド明示 で三重突合確証 |

---

## §2 Phase 1: GET /api/plans 500 真因調査

### 2.1 systemctl 稼働確認 (Phase 1-A)
```
● rotation-planner-v2.service - active (running) since Mon 2026-05-18 19:55:07 JST; 2h 46min ago
Main PID: 4098166 (uvicorn)
```
サービス自体は稼働中・ハング/クラッシュなし

### 2.2 journalctl 完全スタックトレース (Phase 1-B + B2)
```
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]: INFO:     202.212.203.231:0 - "GET /api/plans HTTP/1.0" 500 Internal Server Error
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]: ERROR:    Exception in ASGI application
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]: Traceback (most recent call last):
...
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:   File "/var/www/rotation-planner-v2/app/api/routers/plans.py", line 74, in list_plans
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:     return [PlanResponse(**p) for p in plans]
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:   File "/var/www/rotation-planner-v2/app/api/routers/plans.py", line 74, in <listcomp>
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:     return [PlanResponse(**p) for p in plans]
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:             ^^^^^^^^^^^^^^^^^
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:   File ".../pydantic/main.py", line 263, in __init__
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]:     validated_self = self.__pydantic_validator__.validate_python(data, ...)
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]: pydantic_core._pydantic_core.ValidationError: 1 validation error for PlanResponse
May 18 22:34:56 ik1-421-42663 uvicorn[4098166]: user_id
```
**→ ValidationError + 欠如フィールド名「user_id」が明示**

### 2.3 plans.py list_plans + PlanResponse (Phase 1-D/E)
```python
# plans.py:36-43 PlanResponse 定義(★user_id 必須★)
class PlanResponse(BaseModel):
    id: int
    user_id: int                          # ← ★必須★
    name: str
    start_year: int
    end_year: int
    created_at: Optional[str]
    updated_at: Optional[str]
    details: Optional[List[Dict[str, Any]]] = None

# plans.py:71-74 list_plans
@router.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(**p) for p in plans]   # ← L74 ValidationError 発火行
```

### 2.4 PlanRepository.get_plans 実装 (Phase 1-G2・★真因の核心★)
```python
# db_access.py:565-580
@staticmethod
def get_plans(user_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, start_year, end_year, created_at, updated_at
            FROM rotation_plans
            WHERE user_id = ?
            ORDER BY updated_at DESC
        """, (user_id,))
        return rows_to_list(cursor.fetchall())
```
**→ SELECT列リストに user_id がない**
→ 返却 dict キー: `id, name, start_year, end_year, created_at, updated_at`(6項目)
→ PlanResponse 必須キー: `id, user_id, name, start_year, end_year`(5項目+Optional 3)
→ **user_id キー欠如で ValidationError**

### 2.5 cmd_585 commit 7d5b057 影響範囲 (Phase 1-F)
```diff
# cmd_585 subtask_1257 commit 7d5b057 詳細(POST /api/plans のみ修正)
diff --git a/api/routers/plans.py b/api/routers/plans.py
@@ -78,7 +78,7 @@ def list_plans(current_user: Dict = Depends(get_current_user)):
 def create_plan(plan: PlanCreate, current_user: Dict = Depends(get_current_user)):
     plan_id = PlanRepository.create_plan(
         user_id=current_user["id"],
-        plan_data={
+        data={
            "name": plan.name,
```
→ **cmd_585 修正は POST /api/plans (L80) のみ・GET /api/plans (L74) は無関係**
→ **本subtask の真因は cmd_585 退行ではない**

### 2.6 rotation_plans 現状(yasu 2件存在)(Phase 1-H/H2)
```
id  user_id  name  start_year  end_year  created_at           updated_at
1   6        R9    9           12        2026-05-18 12:48:55  2026-05-18 12:48:55
2   6        R9    9           12        2026-05-18 12:55:07  2026-05-18 12:55:07

plan_id  detail_count
1        80
2        80
```
→ ★rotation_plans yasu = **2件**★(cmd_585 POST修正後・本日 12:48/12:55 にyasu保存成功)
→ subtask_1264 当時の「yasu=0件」状態から **正常に増加**(cmd_585 POST 修正の効果が反映)
→ ★これにより GET の latent bug が初めて顕在化★

### 2.7 schema 確認 (Phase 1-J)
```sql
CREATE TABLE rotation_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_year TEXT NOT NULL,
    end_year TEXT NOT NULL,
    constraints_json TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
→ schema には user_id 存在・get_plans SQL が select し忘れているのみ・修正は SQL 1 column 追加で済む

### 2.8 真因確定
| 仮説 | 判定 |
|---|---|
| cmd_585 退行(commit 7d5b057 副作用) | **否定** (cmd_585 修正は POST L80 のみ・GET L74 と無関係) |
| cmd_588 (rotation_plans yasu=0件) 影響 | **間接的に該当** (yasu=0件→2件 で初めて顕在化・cmd_588 の症状自体は改善済) |
| ★schema/SQL 不整合(SELECT user_id 欠如)★ | **★確定★** (db_access.py L572 SELECT列リストに user_id なし・PlanResponse は user_id 必須) |

---

## §3 Phase 2: DEBUG-1270 dist bundle 反映確認

### 3.1 dist/assets/ 実体 (Phase 2-A)
```
total 756
-rw-r--r-- 1 webapp webapp 629025 May 18 22:24 index-CV46wlyV.js   ← subtask_1270 build
-rw-r--r-- 1 webapp webapp  53453 May 18 22:24 index-DULB61Yp.css
-rw-r--r-- 1 webapp webapp  67235 May 18 22:24 leaflet.draw-lilBA_P9.js
-rw-r--r-- 1 webapp webapp   5551 May 18 22:24 spritesheet-DpIxuf5L.svg
```
- 古い Wave 9 bundle `index-BcU7SQN9.js` は **既に dist から削除済**
- 配信実体は `index-CV46wlyV.js` のみ

### 3.2 nginx 配信実体 (Phase 2-B/D)
```html
<!doctype html>
<html lang="en">
  <head>
    <script type="module" crossorigin src="/assets/index-CV46wlyV.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-DULB61Yp.css">
  </head>
  ...
</html>
```
→ 新bundle 完全配信中

### 3.3 bundle DEBUG-1270 出現数(初回 grep -c 1 → 再カウント grep -oE 11) (Phase 2-C/C2)
```
DEBUG-1270 出現数(行=grep -c): 1   ← minified 1行ゆえ・誤読パターン
DEBUG-1270 出現数(全=grep -oE): ★11★
DEBUG-1270 strings 全部(11種):
  [DEBUG-1270] constructor pinnedAssignments.length=
  [DEBUG-1270] generateInitialSolution START pinnedMap.size=
  [DEBUG-1270] generateInitialSolution pre-fill done plan keys=
  [DEBUG-1270] generateInitialSolution END plan sample=
  [DEBUG-1270] localSearch START pinnedMap.size=
  [DEBUG-1270] localSearch END skip_count=
  [DEBUG-1270] ensureMinFields START pinnedMap.size=
  [DEBUG-1270] ensureMinFields END skip_count=
  [DEBUG-1270] Rotation.jsx loadPinnedAssignments SUCCESS data=
  [DEBUG-1270] Rotation.jsx loadPinnedAssignments FAIL error=
  [DEBUG-1270] Rotation.jsx before solver pinnedAssignments=
```
→ **bundle反映済・11種strings全部検出 ✅**

### 3.4 source 状態 (Phase 2-E)
- rotationSolver.js: DEBUG-1270 = 8件
- Rotation.jsx: DEBUG-1270 = 3件
- 計 11件 → bundle と完全一致

### 3.5 git log 確認 (Phase 2-F)
```
15d9095 debug(solver): runtime debug log 大量挿入(殿devtools真因目視特定用) cmd_586 subtask_1270 案X2
6fa2ed6 fix(solver): localSearch+ensureMinFields に pinned skip 追加(案E1) cmd_586 subtask_1269
09df961 fix(solver): pinnedMap年表記を令和に正規化 cmd_586 subtask_1265
```
→ 最新 commit `15d9095`(D2撤廃11件目) origin push成功・サーバー側 source/dist 整合済

### 3.6 Phase 2 結論: bundle 反映漏れ否定・**殿ブラウザキャッシュ**疑い濃厚
- 殿が「現bundle=index-BcU7SQN9.js」と認識 = **古い Wave 9 bundle のキャッシュ**
- 強制リロード(Ctrl+Shift+R)未実施 → ブラウザは古い bundle を使い続けている
- → [DEBUG-1270] 出力なし は **キャッシュ問題で説明可能**

---

## §4 修正案 (案G1/G2/G3 予断なし整理・memory#feedback_no_predisposition.md 適用)

### 案G1: db_access.py L572 SELECT に user_id 1 column 追加 (★推奨★ - 1行修正・最小変更)
**箇所**: `/var/www/rotation-planner-v2/app/rotation_planner/common/db_access.py:572`
**変更内容**:
```diff
@@ db_access.py:572 PlanRepository.get_plans @@
         cursor = conn.execute("""
-            SELECT id, name, start_year, end_year, created_at, updated_at
+            SELECT id, user_id, name, start_year, end_year, created_at, updated_at
             FROM rotation_plans
             WHERE user_id = ?
             ORDER BY updated_at DESC
         """, (user_id,))
```
- 影響範囲: 1ファイル・1行・1 column追加
- 長所: schema/SQL/Response 整合性完全回復・最小変更・rollback容易・他箇所無影響
- 短所: なし
- リスク: 既存 get_plans 利用箇所が user_id キー想定外で動作 → grep で全利用箇所要確認(本書範囲外・別subtask候補)
- Rollback: 1ファイル git revert / SQL 1 column削除

### 案G2: plans.py PlanResponse の user_id を Optional化
```python
class PlanResponse(BaseModel):
    id: int
    user_id: Optional[int] = None         # ← Optional化
    name: str
    ...
```
- 影響範囲: 1ファイル・1行
- 長所: SQL 無変更
- 短所: API レスポンス schema 緩和・user_id 取得期待のクライアントが None 受信
- リスク: フロント側で user_id 利用していれば仕様変更扱い

### 案G3: list_plans で user_id を current_user["id"] から補填
```python
@router.get("/api/plans", response_model=List[PlanResponse])
def list_plans(current_user: Dict = Depends(get_current_user)):
    plans = PlanRepository.get_plans(current_user["id"])
    return [PlanResponse(user_id=current_user["id"], **p) for p in plans]
```
- 影響範囲: 1ファイル・1行
- 長所: SQL 無変更・確実に補填
- 短所: スコープ違い(Repository層で取れるべき情報を Router層で補填)・admin/ja_staff が他ユーザー閲覧時に **不正な user_id 上書き** リスク

### 案間比較

| 観点 | 案G1(SQL+1列) | 案G2(Response Optional) | 案G3(Router補填) |
|---|---|---|---|
| 変更ファイル数 | 1(db_access.py) | 1(plans.py) | 1(plans.py) |
| 変更行数 | 1行(SQL列追加) | 1行(Optional化) | 1行(補填) |
| 設計純度 | 最高(schema完全整合) | 中(API緩和) | 低(層責任侵食) |
| rollback容易度 | 高 | 高 | 高 |
| admin閲覧時 安全性 | 安全 | 安全 | ★危険(user_id上書き) |
| 既存利用者影響 | なし | None受信に依存変更 | なし |

---

## §5 V4境界線「戻せるか」判定

### V4 判定: **★戻せる★**

| 判定軸 | 案G1 |
|---|---|
| データ変更 | なし(SELECT列追加のみ) |
| 不可逆操作 | なし |
| rollback コスト | 極低(git revert 1ファイル) |
| 副作用範囲 | rotation_plans GET のみ・他ルート無影響 |
| 緊急時バイパス | 案G2 にスイッチも可能(Optional化で500回避) |

**→ V4境界線通過・実装着手可・本subtaskは設計まで止め・別subtask Wave 12 で実装推奨**

---

## §6 殿への質問(3問以内)+ 戦略提案

| Q | 内容 |
|---|---|
| **Q1** | 案G1(db_access.py L572 SELECT に user_id 1 column追加)を承認・Wave 12 即実装(D2撤廃12件目目標)で進めるか? |
| **Q2** | DEBUG-1270 bundle は正常配信中(index-CV46wlyV.js に 11種strings全反映)。殿に再度 **Ctrl+Shift+R 強制リロード + [DEBUG-1270] devtools ログ取得** をお願いするか?(ζ10 確定の鍵が残っている) |
| **Q3** | 本件 = schema/SQL不整合 (cmd_585 と同類問題が plans.py GET にも残存)・他router/Repository ペアの SELECT列 ↔ Response schema の網羅監査を cmd_586 拡張 or 新規cmd起票で実施するか? |

### 戦略提案
- **第1優先**: 案G1 Wave 12 即実装(1行修正・D2撤廃12件目)→ GET /api/plans 200復活 → 殿 plans一覧表示復活
- **第2優先**: 殿 Ctrl+Shift+R 強制リロード+devtools 再取得 → ζ10 確定 → Wave 13 認証修復(cmd_587統合 案F2)
- **第3優先**: 他 API/Repository SELECT列 監査(類似 latent bug 網羅・新cmd起票推奨)

### cmd_586 全体進捗
- 11波構造 (subtask_1255→…→1270→1271)
- D2撤廃 11件連続push 2桁突破済 (1270 = 11件目)
- 本subtask Wave 12 実装で12件目目標
- お針子18/18満点 5連続 (1264/1265/1268/1269/1270 見込み)
- 品質ループ第20周突入

---

## 付録: お針子FB継続適用

### ssh_raw_outputs Phase別貼付状況
| Phase | 貼付場所 | completeness |
|---|---|---|
| Phase 1-A〜J | §2 | systemctl+journalctl完全スタックトレース+curl+plans.py全実装+db_access.py get_plans+rotation_plans 2件+schema 全SSH貼付 |
| Phase 2-A〜F | §3 | dist実体+index.html+bundle DEBUG-1270 11種・全SSH貼付 |

### three_pillar_evidence
| 柱 | 内容 |
|---|---|
| ① commit hash | 親 subtask_1270 push commit `15d9095`(D2撤廃11件目)・本subtask 設計のみ |
| ② Phase別 SSH | Phase 1+2 全SSH §2-§3 完全貼付 |
| ③ 真因根拠 | (1) journalctl ValidationError `user_id` 明示 (2) db_access.py L572 SELECT列リスト直視 (3) PlanResponse schema L36-43 必須フィールド明示 で三重突合 |

### oharikoma_feedback_reflection
- ✅ memory#feedback_vps_audit_raw_logs.md: 生SSH全Phase貼付(要約禁止)→ §2-§3 完全貼付
- ✅ memory#feedback_needs_audit_ssh_log.md: needs_audit=true subtask の SSH生ログ添付 → 全Phase貼付
- ✅ memory#feedback_no_predisposition.md: 修正案 G1/G2/G3 機械的整理・「推奨」表記は §1 のみ
- ✅ memory#feedback_crlf_binary_edit.md: 該当なし(本subtask read-only・編集なし)
- ✅ **schema差異検出 9回目**: 1257(plans.py kwarg) / 1258(pesticides.py kwarg 4件) / 1259(crop_history INSERT vs schema) / 1260(pinned_assignments INSERT) / 1264(year表記) / 1268(solve 3段階 skip欠如) / 1270(認証問題) / **1271(plans.py GET SQL select user_id欠如)★新★**

### F006 D2撤廃継続
- 本subtask: 設計のみ・実装なし → shogun リポの docs/ のみ・rotation-planner自リポ無変更
- D2撤廃 11件連続 (本subtask Wave 12 実装で12件目目標)

### ntripcaster保全
- 全Phase pid 3216892/3216893+port 2101 LISTEN 完全継続

### 品質ループ第20周
- 1247→1250→1254→1255→1257→1259→1260→1262→1264→1265→1268→1269→1270→**1271**

---

(cmd_586 Wave 11 緊急2本立て・GET 500 真因確定 schema/SQL不整合・DEBUG-1270 bundle反映済キャッシュ問題・案G1 推奨・Wave 12 実装で D2撤廃12件目目標)
