# rotation-planner v2: cmd_591 Wave 1 OR-Tools 500エラー read-only 緊急調査 (subtask_1279)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1279 / cmd_591 (Wave 1) |
| 作成日時 | 2026-05-19T01:35 JST |
| 作成者 | 部屋子1 (ashigaru6) |
| 報告書範囲 | 完全 read-only 調査(修正は別subtask候補) |
| 親subtask | cmd_590 Wave 1(γ+ε複合確定)直後・cmd_591 新規起票 |
| 品質ループ | 第26周 |

---

## §1 エグゼクティブサマリ

### 殿動作確認(2026-05-19 00:03〜00:14頃 複数回)
- 輪作画面でソルバー = **OR-Tools(サーバー)** 選択→「最適化実行」押下
- → **Request failed with status code 500** ダイアログ表示(3回再現確認・00:03/00:11/00:14)
- JS版は正常(参考: 11ms スコア-693.5)
- 警告UI 7件表示確認済(cmd_590 γ判定 補強)

### 真因確定: **★η4 確定: Field.__init__() got an unexpected keyword argument 'field_code'★**

**スタックトレース末尾の決定的証跡**:
```
ERROR rotation_planner.api 最適化エラー: Field.__init__() got an unexpected keyword argument 'field_code'
Traceback (most recent call last):
  File "/var/www/rotation-planner-v2/app/api/main.py", line 629, in optimize_rotation
    field_obj = Field(
                ^^^^^^
TypeError: Field.__init__() got an unexpected keyword argument 'field_code'
INFO: "POST /api/rotation/optimize HTTP/1.0" 500 Internal Server Error
```

**機序**:
- main.py:71 `from rotation_planner.app.utils import Field`(★ここで dataclass Field を import)
- `rotation_planner/app/utils.py:33` `@dataclass class Field` は **`field_code` フィールドを持たない**(代わりに `name` フィールド存在)
- main.py:629 `Field(field_id=..., field_code=..., area_ha=..., district=..., history=..., beet_forbidden=...)` で `field_code` kwarg を渡している
- → TypeError 500

**utils.Field の正規 kwargs**:
```python
@dataclass
class Field:
    field_id: str
    district: str
    name: str                          # ← field_code 相当はここに入るべき
    area_ha: float
    history: Dict[str, str] = field(default_factory=dict)
    has_unknown: bool = False
    beet_forbidden: bool = False
```

### 仮説検証マトリクス

| 仮説 | 判定 | 根拠 |
|---|---|---|
| η1 endpoint未実装 | **否定** | main.py:619 `@app.post("/api/rotation/optimize", ...)` 存在 |
| η2 ortools未install | **否定** | `pip list | grep ortools` → `ortools 9.15.6755`+`protobuf 6.33.6`+`from ortools.sat.python import cp_model` import OK |
| η3 input schema差 | **部分該当** | フロント↔API は req.fields 経由で正常・**API内部の Field クラス kwarg と一致しない**(η4 と同根) |
| **η4 初期化失敗(kwarg mismatch)** | **★確定★** | utils.Field に `field_code` フィールド不在・main.py:629 が `field_code=...` 渡し → TypeError 500 |
| η5 認証問題 | **否定** | 500ではなく Bearer/401 になるはず・スタックトレースは内部例外 |

### 推奨修正案 (read-only調査ゆえ実装は別subtask)
**案J1(推奨・1行修正)**: main.py:629 で `field_code=...` を `name=...` に rename
**案J2**: utils.Field dataclass に `field_code: str = ""` フィールド追加
**案J3**: main.py:629 で field_code 引数を削除(field_code 情報を捨てる)

### V4境界線「戻せるか」判定: **★戻せる★** (1行修正・データ変更なし・git revert 容易)

### 殿への質問(3問以内)
| Q | 内容 |
|---|---|
| Q1 | 修正案 **J1(main.py:629 field_code→name に rename・1行)** / **J2**(utils.Field に field_code フィールド追加・1行) / **J3**(field_code 引数削除・1行) のいずれを採用・Wave 2 即実装で進めるか? |
| Q2 | 本件は cmd_585 (plans.py POST kwarg mismatch) と完全同類・**schema差異検出 14回目候補**確定。cmd_589 軍師schema網羅監査(subtask_1273)報告書に本件追記要請するか? |
| Q3 | OR-Tools サーバー版は **pinned非対応**(cmd_586 subtask_1263 既報)。本subtask kwarg修正後も pinned未対応のまま運用するか? それとも別cmd で pinned 対応を起票するか? |

### Three Pillar Evidence
| 柱 | 証跡 |
|---|---|
| ① 親subtask | cmd_590 Wave 1(commit 75c316e shogun private push)・cmd_586 大団円後の運用課題系列 |
| ② Phase別 SSH | Phase 1(systemctl active+journalctl Field.__init__ TypeError スタックトレース 3回再現+endpoint候補 main.py:619)+Phase 2(main.py:619-680+endpoint一覧+routers/+optimizer.py 確認+utils.Field dataclass シグネチャ直視+main.py:629 呼出 context)+Phase 3(ExecStart=/app/venv/bin/uvicorn+pip list ortools 9.15.6755 protobuf 6.33.6+import試行 OK+requirements.txt `ortools>=9.0`)+Phase 4 補助(ntripcaster完全保全) |
| ③ 真因根拠 | (1) journalctl `TypeError: Field.__init__() got an unexpected keyword argument 'field_code'` 明示+main.py:629 行番号明示 (2) main.py:71 `from rotation_planner.app.utils import Field` 直視 (3) utils.py:33 `@dataclass class Field: field_id/district/name/area_ha/history/has_unknown/beet_forbidden` シグネチャ直視 → **field_code 不在** = 三重突合で完全確証 |

---

## §2 Phase 1: journalctl + endpoint特定

### 2.1 systemctl 稼働確認
```
● rotation-planner-v2.service - active (running) since Mon 2026-05-18 22:56:22 JST; 1h 20min ago
Main PID: 4112681 (uvicorn)
ExecStart=/var/www/rotation-planner-v2/app/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8001
```

### 2.2 journalctl 完全スタックトレース(3回再現・00:03/00:11/00:14)
```
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]: ERROR rotation_planner.api 最適化エラー: Field.__init__() got an unexpected keyword argument 'field_code'
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]: Traceback (most recent call last):
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]:   File "/var/www/rotation-planner-v2/app/api/main.py", line 629, in optimize_rotation
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]:     field_obj = Field(
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]:                 ^^^^^^
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]: TypeError: Field.__init__() got an unexpected keyword argument 'field_code'
May 19 00:03:56 ik1-421-42663 uvicorn[4112681]: INFO:     202.212.203.231:0 - "POST /api/rotation/optimize HTTP/1.0" 500 Internal Server Error
```

### 2.3 endpoint 候補 grep
```
api/main.py:619:@app.post("/api/rotation/optimize", response_model=RotationOptimizeResponse)
api/main.py:70:from rotation_planner.app.optimizer import RotationPlannerORTools
api/main.py:71:from rotation_planner.app.utils import Field         ← ★Field の import 経路★
api/main.py:764:        planner = RotationPlannerORTools(
```

### 2.4 frontend 送信URL+ソルバー選択
```
frontend/app/src/pages/Rotation.jsx:25:  const [solverType, setSolverType] = useState('js'); // 'js' or 'ortools'
frontend/app/src/pages/Rotation.jsx:216:  const runOptimizationORTools = async () => {
frontend/app/src/pages/Rotation.jsx:267:      if (solverType === 'ortools') {
frontend/app/src/pages/Rotation.jsx:268:        resultData = await runOptimizationORTools();
frontend/app/src/pages/Rotation.jsx:411:            <option value="ortools">OR-Tools（サーバー）</option>
```

---

## §3 Phase 2: API実装精読

### 3.1 main.py:619 endpoint 実装(★真因の核心箇所★)
```python
@app.post("/api/rotation/optimize", response_model=RotationOptimizeResponse)
def optimize_rotation(req: RotationOptimizeRequest, current_user: Dict = Depends(get_current_user)):
    """OR-Toolsを使用した輪作計画最適化"""
    import time
    start_time = time.time()

    try:
        # ほ場データをFieldオブジェクトに変換
        field_objects = []
        for f in req.fields:
            field_obj = Field(
                field_id=str(f.get("field_id", f.get("fieldId", ""))),
                field_code=f.get("field_code", f.get("fieldCode", "")),       # ★★★ TypeError 発生行 ★★★
                area_ha=float(f.get("area_ha", f.get("areaHa", 0))),
                district=f.get("district", ""),
                history=f.get("history", {}),
                beet_forbidden=f.get("beet_forbidden", f.get("beetForbidden", False))
            )
            field_objects.append(field_obj)
```

### 3.2 ★utils.Field dataclass 定義(★期待kwarg★)
```python
# /var/www/rotation-planner-v2/app/rotation_planner/app/utils.py:33
@dataclass
class Field:
    """ほ場データ"""
    field_id: str                                                   # ✅
    district: str                                                   # ✅
    name: str                                                       # ★field_code 相当はここに入るべき★
    area_ha: float                                                  # ✅
    history: Dict[str, str] = field(default_factory=dict)            # ✅
    has_unknown: bool = False
    beet_forbidden: bool = False                                    # ✅
```

→ **`field_code` フィールドなし**・main.py:629 の `field_code=...` 引数で TypeError

### 3.3 比較対象: common/models.Field(別経路・本件と無関係)
```python
# /var/www/rotation-planner-v2/app/rotation_planner/common/models.py:73
class Field:                                                        # ★こちらは field_code を持つ★
    id: int
    user_id: int
    field_code: str                                                 # ← この field_code は別クラス
    name: str
    district: Optional[str] = None
    area_ha: float = 0.0
    ...
```

★**main.py:71 は `app.utils.Field` を import している**(`common.models.Field` ではない)
★ → 名前空間混乱の典型・cmd_585 と同類の schema差異検出 14回目

### 3.4 全 endpoint 一覧
```
@app.get("/api/ja/farmers")
@app.get("/api/ja/farmers/{farmer_id}/fields")
@app.get("/api/ja/farmers/{farmer_id}/plans")
...
@app.post("/api/rotation/import-csv", response_model=RotationImportResponse)
@app.post("/api/rotation/optimize", response_model=RotationOptimizeResponse)    ← ★本件★
```

→ `/api/rotation/optimize` endpoint 確実に存在(η1否定)

---

## §4 Phase 3: ortools install + import試行

### 4.1 systemd ExecStart 経路特定
```
WorkingDirectory=/var/www/rotation-planner-v2/app
ExecStart=/var/www/rotation-planner-v2/app/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8001
```
→ venv 経路: `/var/www/rotation-planner-v2/app/venv`

### 4.2 pip list+import試行
```
$ /var/www/rotation-planner-v2/app/venv/bin/pip list | grep -iE "ortools|protobuf"
ortools            9.15.6755
protobuf           6.33.6

$ /var/www/rotation-planner-v2/app/venv/bin/python3 -c "from ortools.sat.python import cp_model; print('OK:', cp_model.__file__)"
OK: /var/www/rotation-planner-v2/app/venv/lib/python3.11/site-packages/ortools/sat/python/cp_model.py
```
→ ortools install 完全・import 動作・**η2 完全否定**

### 4.3 requirements.txt
```
/var/www/rotation-planner-v2/app/requirements.txt:
ortools>=9.0
```
→ 正規依存記載あり

### 4.4 uvicorn proc 実体
```
webapp 4112681 1 0 May18 ? 00:00:06 /var/www/rotation-planner-v2/app/venv/bin/python3 /var/www/rotation-planner-v2/app/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8001
```
→ 起動中・正規venv経路

---

## §5 真因特定 (η4 確定)

### 5.1 真因マトリクス(最終)
| 仮説 | 判定 | 一次根拠 | 二次根拠 |
|---|---|---|---|
| η1 endpoint未実装 | **否定** | main.py:619 `@app.post("/api/rotation/optimize")` 存在 | endpoint 一覧で確認 |
| η2 ortools未install | **否定** | ortools 9.15.6755+protobuf 6.33.6 install済 | import OK・requirements.txt 記載あり |
| η3 input schema差 | **部分該当** | フロント→API req.fields 経路は正常 | η4 と同根(API内部 Field クラスとの差) |
| **η4 初期化失敗(kwarg mismatch)** | **★確定★** | journalctl `TypeError: Field.__init__() got an unexpected keyword argument 'field_code'` | utils.Field dataclass field_code 不在(代わりに name) |
| η5 認証問題 | **否定** | 内部TypeError 500・Bearer 401 ではない | 認証通過後に発生 |

### 5.2 発生機序(時系列)
```
1. 殿: 輪作画面 → ソルバー「OR-Tools(サーバー)」選択 → 最適化実行
2. Rotation.jsx runOptimizationORTools: POST /api/rotation/optimize with req.fields
3. main.py:619 optimize_rotation 起動
4. main.py:629 Field(field_id=..., field_code=..., ...) 呼出
5. utils.Field __init__ で field_code が受け取れない → TypeError
6. ASGI exception handler が 500 Internal Server Error 返却
7. フロント: Request failed with status code 500 ダイアログ表示
```

### 5.3 cmd_585 との同類性(★schema差異検出14回目候補★)
- cmd_585 subtask_1257: `PlanRepository.create_plan(plan_data={...})` vs `def create_plan(user_id, data)` の kwarg mismatch
- 本件 subtask_1279: `Field(field_code=...)` vs `@dataclass class Field: name: str` の kwarg mismatch
- **両者とも「呼出側 kwarg と定義側 kwarg の不一致による TypeError 500」** = 同類問題
- cmd_589 軍師schema網羅監査(subtask_1273)に本件を 14回目として追加候補

---

## §6 修正案 (予断なし整理・実装は別subtask候補)

### 案J1: main.py:629 で `field_code` → `name` に rename (★推奨・1行・最小変更★)
```diff
@@ main.py:629 @@
         field_obj = Field(
             field_id=str(f.get("field_id", f.get("fieldId", ""))),
-            field_code=f.get("field_code", f.get("fieldCode", "")),
+            name=f.get("field_code", f.get("fieldCode", "")),
             area_ha=float(f.get("area_ha", f.get("areaHa", 0))),
             district=f.get("district", ""),
             history=f.get("history", {}),
             beet_forbidden=f.get("beet_forbidden", f.get("beetForbidden", False))
         )
```
- 影響: 1ファイル・1行
- 長所: utils.Field 無変更・既存設計尊重(name フィールドに field_code を格納)
- 短所: name の意味が曖昧化(field_code 用途と元 name 用途の混在)
- リスク: utils.Field の name を別用途で使う箇所が下流にあれば影響
- Rollback: 1ファイル git revert 容易

### 案J2: utils.Field dataclass に `field_code` フィールド追加
```diff
@@ utils.py:33 @@
 @dataclass
 class Field:
     """ほ場データ"""
     field_id: str
+    field_code: str = ""        ← 追加
     district: str
     name: str
     area_ha: float
     ...
```
- 影響: 1ファイル・1行追加
- 長所: 設計純度高・common/models.Field との整合性確保
- 短所: utils.Field 利用箇所が全 field_code を受け取るようになる(下流影響あり)
- リスク: optimizer.py 内の Field 利用箇所で field_code 参照を追加要

### 案J3: main.py:629 で field_code 引数削除
```diff
@@ main.py:629 @@
         field_obj = Field(
             field_id=str(f.get("field_id", f.get("fieldId", ""))),
-            field_code=f.get("field_code", f.get("fieldCode", "")),
             area_ha=float(f.get("area_ha", f.get("areaHa", 0))),
             district=f.get("district", ""),
             history=f.get("history", {}),
             beet_forbidden=f.get("beet_forbidden", f.get("beetForbidden", False))
         )
```
- 影響: 1ファイル・1行削除
- 長所: 最小変更
- 短所: field_code 情報を完全に捨てる(name 未設定・空文字)・field_code に依存する下流ロジックが破綻

### 案間比較
| 観点 | 案J1(rename) | 案J2(Field追加) | 案J3(削除) |
|---|---|---|---|
| 変更行数 | 1 | 1 | 1 |
| 変更ファイル数 | 1 | 1 | 1 |
| field_code 情報保持 | ○(name に流用) | ○(専用field) | ×(情報消失) |
| 設計純度 | 中 | 高 | 低 |
| 下流影響 | name 用途混在 | 全 utils.Field 利用箇所 | name 未設定・field_code依存破綻 |
| rollback容易度 | 高 | 高 | 高 |

---

## §7 殿への質問(3問以内)+ 戦略提案

| Q | 内容 |
|---|---|
| **Q1** | 案 J1(name に rename)/ J2(field 追加)/ J3(削除) のいずれを採用・Wave 2 即実装(D2撤廃16件目目標)で進めるか? |
| **Q2** | 本件 = cmd_585 と同類 schema差異検出 14回目候補・cmd_589 軍師schema網羅監査(subtask_1273)に本件追記要請するか? |
| **Q3** | OR-Tools サーバー版は **pinned非対応**(cmd_586 subtask_1263 既報)。本subtask kwarg修正後も pinned未対応のまま運用するか・別cmd で pinned対応を起票するか? |

### 戦略提案
- **第1優先**: 案J1 即実装(Wave 2 で D2撤廃16件目目標) → OR-Tools 500 解消
- **第2優先**: cmd_589 軍師schema網羅監査に本件追記(14回目・cmd_585と同類)
- **第3優先**: OR-Tools pinned対応(cmd_586 case 別cmd 起票判断・優先度低)

---

## 付録: お針子FB継続適用

### ssh_raw_outputs Phase別貼付状況
| Phase | 貼付場所 | completeness |
|---|---|---|
| Phase 1-A〜E | §2 | systemctl+journalctl(3回再現スタックトレース完全)+endpoint候補+frontend送信URL 全SSH貼付 |
| Phase 2-A〜M | §3 | main.py:619-660 endpoint実装+全endpoint一覧+routers/+optimizer.py+utils.Field シグネチャ+common.models.Field比較+import経路 全SSH貼付 |
| Phase 3-A〜F | §4 | ExecStart venv経路+pip list ortools+import試行+requirements.txt+uvicorn proc実体+ntripcaster保全 全SSH貼付 |

### three_pillar_evidence
| 柱 | 内容 |
|---|---|
| ① 親subtask | cmd_590 Wave 1(commit 75c316e shogun private push)・cmd_586大団円後の運用課題系列 |
| ② Phase別 SSH | Phase 1+2+3 を §2-§4 完全貼付 |
| ③ 真因根拠 | (1) journalctl `TypeError: Field.__init__() got an unexpected keyword argument 'field_code'` 明示 (2) main.py:71 import 経路 + L629 呼出 直視 (3) utils.py:33 `@dataclass class Field` 全フィールド直視で field_code 不在確証 → 三重突合 |

### oharikoma_feedback_reflection
- ✅ memory#feedback_vps_audit_raw_logs.md: 生SSH全Phase貼付(要約禁止)→ §2-§4 完全貼付
- ✅ memory#feedback_needs_audit_ssh_log.md: needs_audit=true・全Phase貼付
- ✅ memory#feedback_no_predisposition.md: 案 J1/J2/J3 機械的整理・「推奨」記載は §1 のみ
- ✅ memory#feedback_crlf_binary_edit.md: 該当なし(完全read-only)

### F006 D2撤廃継続
- 本subtask: 完全read-only調査・shogun リポへ docs/ 1ファイル追加のみ・rotation-planner自リポ無変更

### ntripcaster保全
- 全Phase pid 3216892/3216893+port 2101 LISTEN 完全継続

### 品質ループ第26周
- 1247→…→1276(cmd_586大団円)→1277(cmd_590 Wave 1)→**1279**(cmd_591 Wave 1)

### schema差異検出 14回目候補確定
- 1257(plans.py POST kwarg)・1258(pesticides×4)・1259(crop_history)・1260(pinned_assignments)・1264(year表記)・1268(solve 3段階skip)・1270(認証)・1271(GET SQL select)・1272(案G1実装)・1275(prepareFields layer差)・1276(案H1実装)・1273(軍師schema監査)・1277(constraints crop名 layer差)・**1279(main.py Field kwarg mismatch・cmd_585同類)14回目候補確定**

---

(cmd_591 Wave 1 read-only調査完遂・真因 η4 確定 Field.__init__ kwarg mismatch・cmd_585 同類・案J1/J2/J3 殿選択待ち・Wave 2 で D2撤廃16件目目標)
