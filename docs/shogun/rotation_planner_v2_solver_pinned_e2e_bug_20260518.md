# rotation-planner v2: ソルバー pinned 未読 end-to-end 調査 (cmd_586 Wave 4)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1261 / cmd_586 |
| 作成日時 | 2026-05-18T20:12 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象ファイル | Rotation.jsx:169 (5引数→6引数化要) + rotationSolver.js (実装済・呼出未) |
| 報告書範囲 | read-only調査+設計のみ (実装は別Wave) |
| 関連 | subtask_1255 (Wave 2c) + subtask_1259 (Wave 2 暗黙pin) + subtask_1260 (Wave 3 マイグレ) |

---

## §1 エグゼクティブサマリ

**症状**: 殿動作確認3波目で R8効・R9上書き継続 (IMP_6_003 R9=飼料作物入力済→ソルバー結果=飼料用とうもろこし)。pinned_assignments DB投入は成功(Wave 3で14件)だが、ソルバー実行時に**読まれていない**疑い。

**真因**: **★殿仮説②=solver引数経路断裂 確定★** — Rotation.jsx 呼出側で pinned_assignments を**fetch せず・solver引数に渡していない**

**根拠** (Phase別証跡):
- rotationSolver.js constructor は **6引数** `(fields, pastYears, futureYears, crops, constraints, pinnedAssignments=[])` (subtask_1255 で実装済・bundle検証反映確認)
- Rotation.jsx L169 `new RotationSolver(...)` は **5引数のみ**渡し・第6引数 pinnedAssignments **欠落**
- pinnedAssignments デフォルト `[]` で初期化 → pinnedMap 空 → pre-fill されない
- frontend全体で `pinned` / `/api/pinned` / `pinnedApi` grep → **すべて 0件**(fetch経路自体が未実装)

**仮説検証**:
| 仮説 | 判定 | 根拠 |
|---|---|---|
| ①ソルバーAPIがpinned未取得 | 部分肯定 | `rotationApi.optimize` は別経路・本subtask未深堀(別Wave候補) |
| **②solver引数経路断裂** | **確定** | Rotation.jsx L169 5引数渡し・solver constructor 6引数定義 |
| ③DBデータschema差 | 否定 | pinned_assignments yasu R9 9件全件正しく投入(field_id=4 IMP_6_003 crop=飼料作物確認済) |
| ④別盲点 | 部分肯定 | frontend pinned fetch経路 全くなし(②の上位症状) |

**修正案候補** (予断なし整理):
- A: Rotation.jsx に `/api/pinned-assignments` fetch + 6引数化 (約10行)
- B: server-side `/api/rotation/optimize` で pinned 取得 → solver に注入 (大規模)
- C: rotationSolver.js constructor内で fetch (async constructor 問題あり・非推奨)

**殿への質問** (3問以内):
- Q1: Wave 5 起票承認可否?
- Q2: 修正案候補 A/B のどちらを採用するか?(本subtaskは整理のみ・予断なし)
- Q3: `/api/rotation/optimize` server-side 実装の有無確認も Wave 5 に含めるか別subtask分離か?

---

## §2 Phase 1 DB実体スナップショット

### yasu user_id
```
id=6 username=yasu
```

### IMP_6_003 field
```
id=4 name=ishida field_code=IMP_6_003 user_id=6
```

### pinned_assignments yasu R9 (= 2027) ★全9件確認★
| id | user_id | field_id | year | crop | is_active | notes |
|---|---|---|---|---|---|---|
| **6** | 6 | **4 (IMP_6_003)** | 2027 | **飼料作物** | 1 | migrated_from_crop_history_subtask_1260_20260518 |
| 5 | 6 | 5 (IMP_6_004) | 2027 | 飼料作物 | 1 | (同上) |
| 7 | 6 | 6 (IMP_6_005) | 2027 | 飼料作物 | 1 | (同上) |
| 8 | 6 | 7 (IMP_6_006) | 2027 | 飼料作物 | 1 | (同上) |
| 9 | 6 | 8 (IMP_6_007) | 2027 | 飼料作物 | 1 | (同上) |
| 1 | 6 | 18 (IMP_6_017) | 2027 | 長なす | 1 | (同上) |
| 2-4 | 6 | 19-21 | 2027 | 長なす | 1 | (同上) |

★ **IMP_6_003 R9=飼料作物 が pinned_assignments に正しく投入されている** (id=6 record)

### crop_history yasu R9 (=2027) との一致確認
- field_id=4 year=2027 crop=飼料作物 (id=26 crop_history)
- → pinned_assignments と crop_history は完全一致

→ **DB側はWave 3で完全に正しい** ・データschema差ではない

---

## §3 Phase 2 最適化API endpoint特定

### Rotation.jsx の最適化実行経路
```javascript
// Rotation.jsx L163-178 runOptimizationJS (JSソルバー)
const runOptimizationJS = async () => {
    const solverFields = prepareFields();
    const solverConstraints = prepareConstraints();
    const solver = new RotationSolver(           // ★L169 5引数渡し★
      solverFields,
      pastYears,
      futureYearsList,
      crops,
      solverConstraints
      // ← 第6引数 pinnedAssignments 欠落 ★真因★
    );
    const { plan, score, errors } = solver.solve({ maxIterations: 2000 });
    ...
};

// Rotation.jsx L226 (API経由ソルバー・別経路)
const response = await rotationApi.optimize(requestData);
// → lib/api.js:474 api.post('/api/rotation/optimize', data)
```

### server-side `/api/rotation/optimize` endpoint
- api/routers/ 全件 grep → `@router.(post|get).*(optimize|solve|rotation)` の検出なし
- → **server-side ソルバー endpoint 未実装** か **別ファイル**(grep miss)の可能性
- response の `solverUsed: 'OR-Tools'` は API response field 経由・APIが存在する場合の挙動

(注: 別Wave/別subtaskで server-side 確認推奨・本subtaskでは JS経路の真因②に集中)

### frontend で pinned_assignments 利用箇所
```bash
grep -rnE "/api/pinned|pinned_assignments|pinnedApi" frontend/app/src/
→ 0 件 (完全欠落)
```

→ **frontend は pinned_assignments を全く参照していない**

---

## §4 Phase 3 実装精読+bundle検証

### rotationSolver.js (subtask_1255実装済・反映済)

#### constructor (L57-78)
```javascript
constructor(fields, pastYears, futureYears, crops, constraints, pinnedAssignments = []) {
    this.fields = fields;
    this.pastYears = pastYears;
    this.futureYears = futureYears;
    this.allYears = [...pastYears, ...futureYears];
    this.crops = crops;
    this.constraints = constraints;
    this.pinnedAssignments = pinnedAssignments;
    this.errors = [];
    this.forbiddenSet = new Set(
      constraints.forbiddenTransitions.map(([from, to]) => `${from}->${to}`)
    );
    // pinned lookup を事前構築 (cmd_584 subtask_1255 ソルバー組込み)
    this.pinnedMap = new Map();
    for (const pin of pinnedAssignments) {       // ← 空配列なら何もしない
      const fieldIdx = fields.findIndex((f) => f.id === pin.field_id);
      if (fieldIdx >= 0) {
        this.pinnedMap.set(`${fieldIdx},${pin.year}`, pin.crop);
      }
    }
}
```

#### generateInitialSolution (L268-285)
```javascript
generateInitialSolution() {
    const plan = {};
    // cmd_584 subtask_1255: pinned を plan に pre-fill
    for (const [key, crop] of this.pinnedMap) {  // ← pinnedMap 空なら何もしない
      plan[key] = crop;
    }
    for (const year of this.futureYears) {
      const fieldIndices = shuffle([...Array(this.fields.length).keys()]);
      for (const fieldIdx of fieldIndices) {
        // pinned はスキップ (既に plan に格納済・cmd_584 subtask_1255)
        if (this.pinnedMap.has(`${fieldIdx},${year}`)) continue;  // ← pinnedMap 空なら全 fieldIdx 計算
        let validCrops = this.getValidCrops(fieldIdx, year, plan);
        ...
    }
    return plan;
}
```

### bundle検証
- 新bundle: `index-Da77EjTb.js` (subtask_1259後の build)
- `grep -oE "pinned[A-Za-z]*"` → `pinnedAssignments / pinnedMap` の両方検出
- subtask_1255 修正反映確証 ✓

### Rotation.jsx 呼出側
```javascript
// L169-176
const solver = new RotationSolver(
  solverFields,           // 1
  pastYears,              // 2
  futureYearsList,        // 3
  crops,                  // 4
  solverConstraints       // 5
  // pinnedAssignments    ← 6引数目 欠落 ★★★真因★★★
);
```

→ **6引数定義 vs 5引数渡し**・JS のデフォルト引数で `pinnedAssignments=[]` → pinnedMap 空のまま solver 動作

---

## §5 真因特定 (殿仮説①〜④検証・根拠付き)

### ★②solver引数経路断裂 確定★

**証拠連鎖**:
1. DB: pinned_assignments yasu R9=2027 9件 (IMP_6_003 飼料作物含む) 正しく投入 (§2)
2. rotationSolver.js: constructor 6引数定義 + pinnedMap 初期化 + pre-fill 正しく実装 (§4)
3. bundle: pinnedAssignments + pinnedMap 検出 = 実装反映確証 (§4)
4. **Rotation.jsx L169: 5引数渡し・第6引数 pinnedAssignments 欠落 (§4)** ★真因核心★
5. frontend全体: pinned/api/pinned/pinnedApi grep **0件** (fetch経路自体が未実装)

### 殿仮説検証
| 仮説 | 判定 | 根拠 |
|---|---|---|
| ①ソルバーAPIがpinned未取得 | 部分肯定 | `/api/rotation/optimize` server-side 経路未調査(本subtask対象外・別Wave候補)・JSソルバー経路は②で確定 |
| **②solver引数経路断裂** | **確定** | Rotation.jsx L169 5引数渡し・solver constructor 6引数定義・pinnedMap 空のまま動作 |
| ③DBデータschema差 | 否定 | pinned_assignments yasu R9 9件全件正しく投入(field_id=4 IMP_6_003 crop=飼料作物 完全一致) |
| ④別盲点 | 部分肯定 | frontend pinned fetch経路 全くなし(②の上位症状・実装欠落範囲が予想より広い) |

### subtask_1255 の取り扱い
- subtask_1255 は **rotationSolver.js のみ修正** で実装完了とされた
- 設計書§2.D の「呼出側(Rotation.jsx)」記述は**実装漏れ**
- subtask_1259 (暗黙pin POST書込) + subtask_1260 (既存マイグレ) で DB側 は完全だが・**呼出側 frontend実装が欠落**したまま end-to-end フローが断裂

---

## §6 修正案 (最小変更+rollback容易性・予断なし整理)

### 案A: Rotation.jsx に pinned fetch + 6引数化 (推奨候補・最小変更)

```javascript
// Rotation.jsx (新規 useEffect or runOptimizationJS 内)
const [pinnedAssignments, setPinnedAssignments] = useState([]);

useEffect(() => {
  const loadPinned = async () => {
    try {
      // lib/api.js に pinnedApi 追加要 or 直接 fetch
      const res = await api.get('/api/pinned-assignments?active_only=true');
      setPinnedAssignments(res.data || []);
    } catch (e) {
      console.warn('pinned_assignments取得失敗(空配列でfallback):', e);
      setPinnedAssignments([]);
    }
  };
  loadPinned();
}, []);

// L169 6引数化
const solver = new RotationSolver(
  solverFields, pastYears, futureYearsList, crops, solverConstraints,
  pinnedAssignments    // ← 第6引数追加
);
```

**長所**: 設計書§2.D 通り・rotationSolver.js は無変更・JSソルバー経路対応
**短所**: lib/api.js にも pinnedApi 追加要 (約5行)・別Wave で実装

### 案B: server-side `/api/rotation/optimize` で pinned取得+solver注入

server-side endpoint が**実在するか未確認**・存在すれば API 内で:
```python
@router.post("/api/rotation/optimize")
def optimize(req, current_user):
    pinned = list_pinned_for_user(current_user["id"])
    # solver に pinned 注入
    ...
```
**長所**: client-side 単純化・server-side 一元管理
**短所**: server-side 存在不明・実装規模大(L4軍師判断要)

### 案C: rotationSolver.js constructor内で fetch (非推奨)

constructor を async にする → JS のクラス constructor は async 不可・factory pattern等の複雑化必要
**短所**: アーキテクチャ複雑化・推奨せず

### Rollback容易性
- 案A: Rotation.jsx 修正のみ → git revert 1コミットで戻せる(rotationSolver.js は無変更)
- 案B: server-side 修正 + frontend 変更 → 多ファイル変更・revert 複雑
- 案C: アーキテクチャ変更 → revert 困難

---

## §7 殿への質問 (3問以内・予断なし整理)

| # | 質問 |
|---|---|
| **Q1** | Wave 5 起票承認可否? (修正実装は別subtask) |
| **Q2** | 修正案候補 **A** (Rotation.jsx 6引数化・最小変更) vs **B** (server-side `/api/rotation/optimize` 改修) のどちらを採用するか? |
| **Q3** | `/api/rotation/optimize` server-side 実装の有無確認(grep 0件・存在不明)も Wave 5 に含めるか・別subtask分離か? |

### 補足: end-to-end データフロー俯瞰

```
[殿入力]→ Fields.jsx (POST /api/fields/{id}/history)
   ↓ (subtask_1259 暗黙pin)
[Backend] → crop_history INSERT + pinned_assignments INSERT OR REPLACE
   ↓ DB
[pinned_assignments] yasu R9 9件 ★Wave 3完成・正しく投入★
   ↓
[Frontend 最適化実行] → Rotation.jsx:169 new RotationSolver(...) ← 5引数 ★断裂★
   ↓ pinnedMap 空
[Solver] generateInitialSolution → R9 自由計算 → 飼料用とうもろこし返却
   ↓
[UI表示] R9 列 = 飼料用とうもろこし (殿手動入力 飼料作物 と不一致)
```

---

## 付録: 実行コマンド一覧 (read-only)

```bash
# Phase 1 DB SELECT
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM users WHERE username='yasu';"
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM fields WHERE field_code LIKE '%IMP_6_003%';"
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM pinned_assignments WHERE user_id=6 AND CAST(year AS INTEGER)=2027;"
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM crop_history WHERE field_id IN (...);"

# Phase 2 API endpoint特定
sudo -u webapp grep -rnE "@router\.(post|get).*(optimize|solve|rotation)" api/routers/
sudo -u webapp grep -rnE "api/optimize|api/solve|/optimize|rotationApi\." frontend/app/src/
sudo -u webapp grep -nE "optimize|solve|rotationApi" frontend/app/src/lib/api.js

# Phase 3 implementation+bundle
sudo -u webapp sed -n "55,80p" frontend/app/src/lib/rotationSolver.js
sudo -u webapp sed -n "268,285p" frontend/app/src/lib/rotationSolver.js
sudo -u webapp grep -nE "pinned" frontend/app/src/lib/rotationSolver.js
sudo -u webapp grep -nE "RotationSolver|new Rotation|rotationApi" frontend/app/src/pages/Rotation.jsx
curl -s http://127.0.0.1/assets/${NEW_BUNDLE} | grep -oE "pinned[A-Za-z]*" | sort -u
sudo -u webapp sed -n "160,185p" frontend/app/src/pages/Rotation.jsx
sudo -u webapp grep -rnE "/api/pinned|pinned_assignments|pinnedApi" frontend/app/src/
```

書き込み・サービス操作・ファイル変更は一切なし。

---

(cmd_586 Wave 4 真因②確定・修正案 A/B 整理・Wave 5実装は殿確認後)
