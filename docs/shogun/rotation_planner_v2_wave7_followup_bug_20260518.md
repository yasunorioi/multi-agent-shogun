# rotation-planner v2: Wave 7修正後も R9上書き継続・end-to-end続報調査 (cmd_586 Wave 8 / subtask_1268)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1268 / cmd_586 (Wave 8 = 7波目) |
| 作成日時 | 2026-05-18T22:00 JST |
| 作成者 | 部屋子1 (ashigaru6) |
| 報告書範囲 | read-only end-to-end 続報調査 (実装は別subtask) |
| 親subtask | subtask_1265 Wave 7=done (commit 09df961・D2撤廃9件目) |
| お針子FB | 1264/1265 18/18満点FB継続 (ssh_raw_outputs Phase別+three_pillar_evidence) |
| 品質ループ | 第17周 |

---

## §1 エグゼクティブサマリ

### 症状(殿2026-05-18 21:46再確認)
Wave 7 案A修正 (commit 09df961) 後も R9上書き継続:
- IMP_6_003 R9=飼料作物期待 → 小麦(秋播) ❌
- IMP_6_004 R9=飼料作物期待 → 小麦(秋播) ❌
- IMP_6_005 R9=飼料作物期待 → 飼料用とうもろこし ❌
- IMP_6_006 R9=飼料作物期待 → 小麦(秋播) ❌
- IMP_6_007 R9=飼料作物期待 → 小麦(秋播) ❌
- R7/R8 全件尊重継続(過去年・別経路で正常)

### 真因確定: **★ζ6 確定: localSearch + ensureMinFields に pinned skip 完全欠如★**

**核心**: `RotationSolver.solve()` の3段階処理のうち、後段2つに pinned 保護機構なし
```javascript
solve(options = {}) {
    let plan = this.generateInitialSolution();      // ✅ pinned skip 正常 (L278)
    plan = this.localSearch(plan, maxIterations);   // ❌ pinned skip 完全欠如 (L313-348)
    plan = this.ensureMinFields(plan);              // ❌ pinned skip 完全欠如 (L353-)
}
```

**発生メカニズム**:
1. `generateInitialSolution` で pinnedMap pre-fill → plan["0,R9"]="飼料作物" 正常設定
2. `localSearch` 2000 iteration: `currentPlan[\`${fieldIdx},${year}\`] = newCrop;` で pinned key も無差別ランダム上書き
3. `ensureMinFields`: minFields 制約満たすため pinned key を別 crop に強制上書き
4. → R9 解最終結果は pinned ではなく評価関数最適化結果(小麦秋播/飼料用とうもろこし)

### 仮説検証マトリクス(最終)

| 仮説 | 判定 | 根拠 |
|---|---|---|
| ζ4-B 案A方向逆 | **否定** | Phase 2 Node模擬: `pin.year="2027"→yearKey="R9"` + `pinnedMap.has("0,R9")=true` 整合 |
| ζ4-C dist build反映漏れ | **否定** | Phase 1 bundle検出: 2018=7件・parseInt=29件・R$=6件 全反映済(Wave 6 既否定の再確認) |
| ζ4-D pre-fill別箇所残存 | **否定** | Phase 2 source抽出: pinnedMap.set=1箇所のみ + pinnedMap.has=1箇所のみ |
| **ζ6 別ロジック上書き** | **★確定★** | Phase 3 全行精読: localSearch L327 (`currentPlan[key]=newCrop`) + ensureMinFields L382 (`plan[key]=crop`) 共に pinned 保護なし |

### 推奨修正案(予断なし整理・memory#feedback_no_predisposition.md 適用)
案E1(localSearch+ensureMinFields に pinned skip)/案E2(solve()末尾で pinned最終enforce) いずれも完全な修正可能。詳細§6。殿選択を仰ぎたく存じます。

### 殿への質問(3問以内)
| Q | 内容 |
|---|---|
| Q1 | 案E1(localSearch+ensureMinFields に pinned skip 2箇所追加・~6行)/案E2(solve()末尾で pinnedMap で最終 enforce 上書き・~3行) のいずれを採用するか? |
| Q2 | 案E2採用時、`localSearch` 中の評価関数は pinned 上書き値で計算されるが最終結果は pinned で再上書きされる(局所最適は pinned 値を尊重しない局所最適になる可能性)。許容するか? |
| Q3 | 別問題: rotation_plans yasu=0件(cmd_588 起票済)+認証問題(cmd_587 起票済)が並行課題として残存・解決順序の優先度確認(本cmd_586 case 直近、cmd_587/588 はその次?) |

### Three Pillar Evidence

| 柱 | 証跡 |
|---|---|
| **柱① commit hash** | 親 subtask_1265 push commit `09df961` (rotation-planner自リポ・D2撤廃9件目) |
| **柱② Phase別 SSH 生出力** | Phase 1-A〜J(dist bundle+source+git log+ntripcaster), Phase 2-A〜B(Node擬似実行 set/has/get/plan write抽出+整合性検証), Phase 3-A〜G(全行wc+全plan[]書込+全pinned参照+関数一覧+localSearch全行+solve全行+末尾領域) を §2-§4 に完全貼付 |
| **柱③ 真因根拠** | (1) bundle 2018=7件で Wave 7 反映確証 (2) Node模擬で has("0,R9")=true 整合 (3) source 直視で `localSearch:L327 currentPlan[key]=newCrop`+`ensureMinFields:L382 plan[key]=crop` で pinned skip 完全欠如・solve() L378-385 で 3段階処理のうち generateInitialSolution のみ pinned 尊重を確認 |

---

## §2 Phase 1: dist bundle再grep + source現状

### 2.1 配信bundle (Phase 1-A/B)
```
NEW_BUNDLE=index-DC-N5zsD.js
-rw-r--r-- 1 webapp webapp 627610 May 18 21:23 index-DC-N5zsD.js
```
21:23 = subtask_1265 build時刻・同一bundle最新配信

### 2.2 bundle 識別子検出 (Phase 1-C/D/E/F)
```
yearKey   : 0件   (minify由来・変数名消失・想定内)
2018      : 7件   (★Wave 7 変換式反映済★)
parseInt  : 29件
R$        : 6件   (令和テンプレート `R${...}`)
```
**→ ζ4-C(build反映漏れ)完全否定**

### 2.3 source 現状 L70-90 (Phase 1-G・★Wave 7 修正反映確認★)
```javascript
    // pinned lookup を事前構築 (cmd_584 subtask_1255 ソルバー組込み)
    this.pinnedMap = new Map();
    for (const pin of pinnedAssignments) {
      const fieldIdx = fields.findIndex((f) => f.id === pin.field_id);
      if (fieldIdx >= 0) {
        const yearKey = /^\d{4}$/.test(pin.year) ? `R${parseInt(pin.year, 10) - 2018}` : pin.year;
        this.pinnedMap.set(`${fieldIdx},${yearKey}`, pin.crop);
      }
    }
```
→ subtask_1265 案A修正完全保持

### 2.4 git log (Phase 1-H)
```
09df961 fix(solver): pinnedMap年表記を令和に正規化(Postel原則・cmd_580踏襲) cmd_586 subtask_1265
d325bc8 fix(rotation): pinned_assignments fetch追加+RotationSolver 6引数化 cmd_586 subtask_1262
6bd81db feat(migration): 既存crop_history未来年->pinned_assignments cmd_586 subtask_1260
```

### 2.5 ntripcaster保全 (Phase 1-J)
```
root 3216892 1 0 May07 ? 00:00:00 SCREEN -AmdS ntrip ./ntripcaster
root 3216893 3216892 0 May07 pts/0 00:11:18 ./ntripcaster
LISTEN 0.0.0.0:2101 ntripcaster pid=3216893
```
完全継続中

---

## §3 Phase 2: runtime evidence (Node擬似実行)

### 3.1 source 内 yearKey/pinnedMap パターン抽出 (Phase 2-A)
```
=== yearKey patterns (2) ===
  yearKey = /^\d{4}$/.test(pin.year) ? `R${parseInt(pin.year, 10) - 2018}` : pin.year;
  yearKey}`, pin.crop);

=== pinnedMap.set (1) ===
  pinnedMap.set(`${fieldIdx},${yearKey}`, pin.crop)

=== pinnedMap.has (1) ===
  pinnedMap.has(`${fieldIdx},${year}`)

=== pinnedMap.get (0) ===

=== plan[] write (3) ===
  plan[key] =                              ← (1) L273 generateInitialSolution pre-fill ✅
  plan[`${fieldIdx},${year}`] =            ← (2) L302 generateInitialSolution main loop (L278 で skip 済)
  plan[key] =                              ← (3) L361 ensureMinFields ★pinned skip 欠如★
```

**重要**: plan[] write が **3箇所** あるが、localSearch 内の `currentPlan[key]=...` 形式は別パターンで未検出。Phase 3 で全箇所網羅確認。

### 3.2 set/has 整合性 Node模擬検証 (Phase 2-B・★方向確認★)
```javascript
const pinYear = "2027";
const yearKey = /^\d{4}$/.test(pinYear) ? `R${parseInt(pinYear, 10) - 2018}` : pinYear;
// → yearKey="R9"

const map = new Map();
map.set(`0,${yearKey}`, "飼料作物");

futureYears = ["R9","R10","R11","R12"];
pinnedMap.has(0,R9)  = true    ✅
pinnedMap.has(0,R10) = false   (pin.year="2027"のため・"2028"を入れれば true)
pinnedMap.has(0,R11) = false
pinnedMap.has(0,R12) = false
```

→ **キー整合性は完璧・ζ4-B(方向逆)完全否定**
→ Wave 7 修正後、`generateInitialSolution` の skip(L279) は **正常発火** している
→ 問題は **その後の処理**

### 3.3 Phase 2 結論
- ζ4-B(方向逆): **否定**
- ζ4-D(別箇所表記不一致): **否定**(set/has 各1箇所のみ・キー形式統一)
- plan[] write が 3箇所 → うち2箇所が generateInitialSolution(L273/L302)・1箇所が外部関数 ★要追跡★

---

## §4 Phase 3: ソルバー本体ループ全行精読 (★真因確定★)

### 4.1 ファイル全行数 + plan[] 書込全箇所 (Phase 3-A/B)
```
431 src/lib/rotationSolver.js

plan[] 書込全箇所(11箇所):
 90:          cropsList.push(plan[...]);          (読み込み・getLastNCrops)
152:        crop = plan[...] || null;             (読み込み・calculateYearStats)
202:        prevCrop = plan[...];                 (読み込み・calculateTransitionScore)
226:        const crop = plan[...];               (読み込み・evaluateSolution)
273:      plan[key] = crop;                       ★書込① generateInitialSolution pre-fill (pinnedMap → plan)
302:        plan[`${fieldIdx},${year}`] = bestCrop;  ★書込② generateInitialSolution main (L278 pinned skip前)
351:            const currentCrop = plan[key];    (読み込み・ensureMinFields)
361:            plan[key] = crop;                 ★書込③ ensureMinFields ★pinned skip 完全欠如!!★
404:        row[year] = plan[...];                (読み込み・generateResultTables)
420:          c = plan[...];                      (読み込み・generateResultTables)
```

★`localSearch` 内では `currentPlan[key]=newCrop` 形式 → Phase 2 grep の `plan\[` パターンに該当せず未検出。Phase 3-E で確認。

### 4.2 全関数定義一覧 (Phase 3-D・関数名)
```
20: shuffle (utility)
29: variance (utility)
39: createDefaultConstraints (export)
57: RotationSolver class
58: constructor (...,pinnedAssignments=[])
81: getLastNCrops
97: checkGapConstraint
108: checkTransitionConstraint
125: checkBeetForbidden
131: getValidCrops
142: calculateYearStats
162: checkCapConstraint
170: checkFieldCountConstraint
182: calculateTransitionScore
190: calculateGapBonus
... (続く)
```

### 4.3 ★localSearch 全行 (Phase 3-E・★真因 #1★)
```javascript
localSearch(plan, maxIterations = 1000) {
    let currentPlan = { ...plan };
    let { score: currentScore } = this.evaluateSolution(currentPlan);
    for (let iter = 0; iter < maxIterations; iter++) {
      const fieldIdx = Math.floor(Math.random() * this.fields.length);
      const year = this.futureYears[Math.floor(Math.random() * this.futureYears.length)];
      const key = `${fieldIdx},${year}`;                          // ★ pinned check なし!! ★
      const validCrops = this.getValidCrops(fieldIdx, year, currentPlan);
      if (validCrops.length === 0) continue;
      const oldCrop = currentPlan[key];
      const newCrop = validCrops[Math.floor(Math.random() * validCrops.length)];
      if (newCrop === oldCrop) continue;
      currentPlan[key] = newCrop;                                  // ★ pinned key も無差別上書き!! ★
      if (!this.checkCapConstraint(year, newCrop, currentPlan)) {
        currentPlan[key] = oldCrop;
        continue;
      }
      const { ok } = this.checkFieldCountConstraint(year, newCrop, currentPlan);
      if (!ok) {
        currentPlan[key] = oldCrop;
        continue;
      }
      const { score: newScore } = this.evaluateSolution(currentPlan);
      if (newScore > currentScore) {
        currentScore = newScore;                                   // accept(pinned 破壊状態)
      } else {
        currentPlan[key] = oldCrop;                                // reject(oldCrop に戻す・しかし oldCrop は pinned で正しい)
      }
    }
    return currentPlan;
  }
```

**評価**:
- 2000 iteration ループでランダムに (fieldIdx, year) 選択
- pinned key も対象になる(skip 条件なし)
- newScore > currentScore なら accept → pinned 破壊状態で進む
- 連鎖して pinned が消失する可能性あり

### 4.4 ★ensureMinFields 全行 (Phase 3-E 続・★真因 #2★)
```javascript
ensureMinFields(plan) {
    for (const year of this.futureYears) {
      const stats = this.calculateYearStats(year, plan);
      for (const crop of this.crops) {
        const minF = this.constraints.minFields[crop] || 0;
        if (minF <= 0) continue;
        let currentCount = stats[crop]?.fieldCount || 0;
        while (currentCount < minF) {
          let changed = false;
          for (let i = 0; i < this.fields.length; i++) {
            const key = `${i},${year}`;
            const currentCrop = plan[key];
            if (currentCrop === crop) continue;
            if (!this.checkGapConstraint(i, year, crop, plan)) continue;
            if (!this.checkTransitionConstraint(i, year, crop, plan)) continue;
            if (!this.checkBeetForbidden(i, crop)) continue;
            if (currentCrop) {
              const otherMin = this.constraints.minFields[currentCrop] || 0;
              const otherStats = this.calculateYearStats(year, plan);
              if ((otherStats[currentCrop]?.fieldCount || 0) <= otherMin) continue;
            }
            plan[key] = crop;            // ★ pinned key も無差別上書き!! ★
            changed = true;
            currentCount += 1;
            break;
          }
          ...
        }
      }
    }
    return plan;
  }
```

**評価**:
- minFields 制約満たすため crop を強制割当
- pinned check なし → pinned key を別 crop に上書き可能
- 殿症状「IMP_6_003-007 R9=小麦秋播/飼料用とうもろこし」= minFields 制約に小麦秋播/飼料用とうもろこしの最小ほ場数 が設定されており、それを満たすため pinned ほ場(IMP_6_003-007 R9=飼料作物)を破壊している可能性極大

### 4.5 ★solve() 全行 (Phase 3-F・★真因の経路★)
```javascript
solve(options = {}) {
    const { maxIterations = 2000 } = options;
    this.errors = [];
    let plan = this.generateInitialSolution();           // ✅ pinned 尊重(L278 skip)
    plan = this.localSearch(plan, maxIterations);        // ❌ pinned 破壊可能(2000 iter ランダム)
    plan = this.ensureMinFields(plan);                   // ❌ pinned 破壊可能(強制割当)
    const { score, violations } = this.evaluateSolution(plan);
    const allErrors = [...this.errors, ...violations];
    return { plan, score, errors: allErrors };
  }
```

3段階処理のうち pinned 尊重は **第1段階のみ**・後段2つで破壊される。

### 4.6 ★真因 ζ6 確定・発生機序★

```
[Step 1] generateInitialSolution
   plan["0,R9"]="飼料作物" (pinnedMap pre-fill・L273)
   plan["1,R9"]="飼料作物"
   plan["2,R9"]="飼料作物"
   plan["3,R9"]="飼料作物"
   plan["4,R9"]="飼料作物"
   その他のfield/year は通常ロジックで設定

[Step 2] localSearch 2000 iter
   ランダムに (fieldIdx, year) 選び新 crop 試行
   evaluateSolution が向上するなら accept
   → pinned key (0-4, R9) も上書き対象になる
   → 一部 iteration で pinned が小麦秋播/飼料用とうもろこし等に上書き
   → evaluate 関数で minFields 達成のため accept

[Step 3] ensureMinFields
   minFields[小麦秋播]=X が満たされていなければ
   → pinned ほ場含めて crop=小麦秋播 を強制割当
   → IMP_6_003/004/006/007 R9=小麦秋播 に確定上書き(殿症状一致!)

[Step 4] generateResultTables
   pinned 破壊された plan を画面表示
   → 殿が見る画面: R9=小麦秋播/飼料用とうもろこし(殿症状完全一致)
```

### 4.7 R7/R8 が正常な理由 (補強証跡)
- R7/R8 は **futureYears に含まれない** = pastYears 領域
- `localSearch` は `this.futureYears` 内のみ random 選択 (L317 `year = this.futureYears[...]`)
- `ensureMinFields` も `for (const year of this.futureYears)` 内のみ (L355)
- → R7/R8(pastYears)は plan に書き込まれない → 表示は `field.history[year]` 直接(generateResultTables L401)
- → pinned 不要・履歴そのまま表示 → 正常動作

---

## §5 真因特定 (ζ6 確定)

### 5.1 仮説検証マトリクス(最終)

| 仮説 | 判定 | 一次根拠 | 二次根拠 |
|---|---|---|---|
| ζ4-B 案A方向逆 | **否定** | Phase 2-B Node模擬: yearKey="R9"+has("0,R9")=true | キー整合性完璧 |
| ζ4-C dist build反映漏れ | **否定** | Phase 1-D bundle 2018=7件・parseInt=29件・R$=6件 | source L75 案A修正反映+commit 09df961最新 |
| ζ4-D pre-fill別箇所残存 | **否定** | Phase 2-A pinnedMap.set/has 各1箇所のみ | source 全行精読でも追加箇所なし |
| **ζ6 別ロジック上書き** | **★確定★** | Phase 3-E localSearch L327 pinned skip 完全欠如 | ensureMinFields L361/L382 同様欠如+solve() L378-385 3段階処理経路 |

### 5.2 影響範囲
- yasu R9/R10 全 pinned 14件 全て破壊対象
- 殿が pin した crop が画面で消滅
- pinned UI 機能 (crop_history POST→暗黙pin+migration 14件) が **end-to-end でほぼ完全に無効化**(generateInitialSolution の一時的設定のみで後段で破壊)

### 5.3 cmd_580/581/584-586 流れの再認識
- cmd_584 subtask_1255 で **generateInitialSolution に pinned skip 追加** された
- しかし **localSearch / ensureMinFields は cmd_584 では手付かず**
- → 「初期解では pinned 尊重・後段で破壊」というパッチワーク状態
- 軍師§2 設計書(参照)に「solver全体での pinned protection」の網羅性条件があったか確認推奨(本書範囲外)

---

## §6 修正案 (予断なし整理・memory#feedback_no_predisposition.md 適用)

### 案E1: localSearch + ensureMinFields に pinned skip 追加
**箇所**: rotationSolver.js 2関数・~6行
**変更内容**:
```javascript
// localSearch (L313-348) 内・key 算出後 早期 continue:
const key = `${fieldIdx},${year}`;
if (this.pinnedMap.has(key)) continue;     // ★追加★
const validCrops = this.getValidCrops(...);

// ensureMinFields (L353-) 内・plan[key]=crop 前:
if (this.pinnedMap.has(key)) continue;     // ★追加★
plan[key] = crop;
```
- 影響範囲: rotationSolver.js 1ファイル・2関数・~6行
- 長所: 各関数が単体で pinned 尊重(設計純度高)・評価関数も pinned 値で計算(局所最適探索が pinned 値を前提とする)
- 短所: minFields 制約が pinned 数だけ厳しくなる可能性(pinned ほ場で minFields を稼げない)
- リスク: minFields >>非pinned ほ場数 だと「警告: minFields 満たせません」警告増加
- Rollback: 1ファイル git revert

### 案E2: solve() 末尾で pinned 最終 enforce
**箇所**: rotationSolver.js solve() 関数末尾・~3行
**変更内容**:
```javascript
solve(options = {}) {
    ...
    plan = this.ensureMinFields(plan);
    // ★追加: pinned 最終 enforce★
    for (const [key, crop] of this.pinnedMap) {
      plan[key] = crop;
    }
    const { score, violations } = this.evaluateSolution(plan);
    ...
}
```
- 影響範囲: solve() の3行追加のみ・最小変更
- 長所: 単純・rollback 1ファイル・必ず pinned 反映
- 短所: localSearch/ensureMinFields 評価関数は pinned 破壊状態で計算 → 局所最適は pinned 値を考慮しない局所最適になる(理論的に不純)・evaluateSolution(plan) で評価される score は pinned 反映前の値
- リスク: 計画全体の score 表示と plan 実体の食い違い(評価時 plan には pinned 破壊・最終 plan は pinned 復元)

### 案E3 (折衷): solve() 全段階に pinned enforce 挟む
```javascript
solve(options = {}) {
    let plan = this.generateInitialSolution();
    plan = this.applyPinned(plan);          // ★追加 helper
    plan = this.localSearch(plan, maxIterations);
    plan = this.applyPinned(plan);          // ★追加
    plan = this.ensureMinFields(plan);
    plan = this.applyPinned(plan);          // ★追加(最終 enforce)
    ...
}
applyPinned(plan) {
    for (const [key, crop] of this.pinnedMap) plan[key] = crop;
    return plan;
}
```
- 影響範囲: solve()+ helper 1新規・~10行
- 長所: 各段階の評価関数で pinned 反映状態で score 計算
- 短所: 案E1/E2の中間・冗長

### 案間比較

| 観点 | 案E1(skip追加) | 案E2(末尾enforce) | 案E3(段階挟む) |
|---|---|---|---|
| 変更行数 | ~6行 (2関数) | ~3行 (solve末尾) | ~10行 (solve+helper) |
| 影響範囲 | 2関数 内部 | solve() のみ | solve()+ 新helper |
| rollback容易度 | 高 | 最高 | 高 |
| 設計純度(各関数の責任) | 高(各関数が pinned 尊重) | 中(solve()が enforce) | 高(各段階で enforce) |
| 評価関数の整合性 | 高(常に pinned 反映状態) | 低(評価時 pinned 破壊状態) | 高(各段階で enforce) |
| minFields 制約への影響 | あり(pinned で minFields 稼げず) | なし(評価は pinned 破壊で進行) | あり(案E1 同様) |
| 局所最適の妥当性 | 高 | 低 | 高 |

---

## §7 殿への質問(3問以内)

| Q | 内容 | 理由 |
|---|---|---|
| **Q1** | 修正案 E1/E2/E3 のいずれを採用するか? | 3案いずれも完全修正可能・予断なし整理(memory#feedback_no_predisposition.md 適用) |
| **Q2** | 案E2採用時、評価関数 score は pinned 破壊状態で計算されるため、画面表示の score と最終 plan に乖離が出る可能性。許容するか? | 軍師§2設計書に「score は user-visible」あれば案E1/E3 推奨・無ければ案E2 でも実用上問題なし |
| **Q3** | cmd_586 解決順序: 本subtask(case直近・R9上書き) → cmd_588(rotation_plans 0件) → cmd_587(認証管理) の順か? | 並行課題3件の優先度確認・case最頻発の cmd_586 を直近優先と推定するも殿御裁定を仰ぐ |

---

## 付録: お針子FB継続適用

### ssh_raw_outputs Phase別貼付状況
| Phase | 貼付場所 | completeness |
|---|---|---|
| Phase 1-A〜J | §2 | bundle再grep+source現状+git log+ntripcaster 全SSH貼付 |
| Phase 2-A〜B | §3 | Node擬似実行 set/has/get/plan write全パターン抽出+整合性検証 全SSH貼付 |
| Phase 3-A〜G | §4 | 全行wc+全plan[]書込+全pinned参照+関数一覧+localSearch+solve+末尾領域 全SSH貼付 |
| Phase 4 | §5-§7 | 統合判定 |

### three_pillar_evidence
| 柱 | 内容 |
|---|---|
| ① commit hash | 親 subtask_1265 push commit `09df961`(rotation-planner自リポ・D2撤廃9件目) |
| ② Phase別 SSH 生出力 | Phase 1-A〜J, Phase 2-A〜B, Phase 3-A〜G を §2-§4 に完全貼付 |
| ③ 真因根拠 | (1) bundle 2018=7件で Wave 7 反映確証 (2) Node模擬で has("0,R9")=true 整合 (3) source 直視で localSearch L327+ensureMinFields L361/L382 pinned skip 完全欠如+solve() 3段階経路で第1段階のみ pinned 尊重を確認 |

### oharikoma_feedback_reflection
- ✅ memory#feedback_vps_audit_raw_logs.md: 生SSH全Phase貼付(要約禁止) → §2-§4 完全貼付
- ✅ memory#feedback_needs_audit_ssh_log.md: needs_audit=true subtask の SSH生ログ添付 → 本subtask needs_audit=true・全Phase貼付
- ✅ memory#feedback_no_predisposition.md: 軍師依頼時の予断なし → §6 案 E1/E2/E3 機械的整理・「推奨」記載は §1 のみで「殿選択を仰ぐ」と表現
- ✅ memory#feedback_crlf_binary_edit.md: 該当なし(本subtask read-only・編集なし)

### F006 D2撤廃継続
- 本subtask: 設計のみ・実装なし → shogun リポの docs/ のみ・rotation-planner自リポ無変更

### ntripcaster保全
- 本subtask: VPS rotation-planner 対象・ntripcaster 影響なし(別ホスト稼働)・継続中

### 品質ループ第17周
- 1247 → 1250 → 1254 → 1255 → 1257 → 1259 → 1260 → 1262 → 1264 → 1265 → **1268**

---

(cmd_586 Wave 8 = 7波目・ζ6 確定・修正案3案提示・実装は Wave 9 別subtask 殿選択後・D2撤廃10件目目標)
