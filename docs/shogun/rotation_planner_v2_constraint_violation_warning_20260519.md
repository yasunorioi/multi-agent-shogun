# rotation-planner v2: cmd_590 Wave 1 制約違反検出+警告未表示バグ read-only 調査 (subtask_1277)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1277 / cmd_590 (Wave 1) |
| 作成日時 | 2026-05-19T01:15 JST |
| 作成者 | 部屋子1 (ashigaru6) |
| 報告書範囲 | 完全 read-only 調査(修正は別subtask候補) |
| 親subtask | (cmd_586 close 大団円・cmd_590 新規起票) |
| 品質ループ | 第25周 |

---

## §1 エグゼクティブサマリ

### 殿動作確認(2026-05-19 00:55頃)
殿が作物別制約設定を入力→「制約設定を保存しました」表示後、最適化実行結果で**違反多発・警告未表示**:
- 小麦(秋播) R9=**17.0ha** (殿期待7ha・+10超過・R9だけ薄赤UI)
- 飼料用とうもろこし R7=**7.5ha** (殿期待4ha・+3.5超過・警告なし)
- 小麦(秋播) R8=**7.5ha** (殿期待7ha・+0.5超過・警告なし)
- 飼料作物 R7-R11 多数=**0.0ha** (殿期待最小2ha・警告なし)

### 真因マトリクス(最終確定)

| 仮説 | 判定 | 核心根拠 |
|---|---|---|
| α 伝達経路漏れ(DB→ソルバー) | **否定** | user_constraints schema 正常+ /api/constraints GET/PUT 正常+prepareConstraints 正常 |
| β solver制約評価未組込 | **部分否定** | checkCapConstraint+checkFieldCountConstraint+evaluateSolution 全実装あり |
| **γ 警告UI部分実装** | **★確定★** | summary-table 描画(Rotation.jsx L590-650)に **違反ハイライトロジック完全欠如**・R9薄赤は計画表 `future-year` クラスの偶然 |
| δ pinned強制副作用 | **否定** | pinned skip は forEach先頭・制約評価無影響 |
| **ε 作物名表記揺れ(新真因)** | **★確定★** | DB constraints に「春小麦 cap=7」(殿入力)+「**小麦(春播)cap=0**」(別エントリ)・ソルバー出力「小麦(秋播)」は cap=0 → 制約なし扱い → 17ha 上書き可 |

### 推奨修正案 (read-only調査ゆえ実装は別subtask)
- **案I1**: 作物名統一(春小麦↔小麦(春播) 等の alias 定義)
- **案I2**: prepareConstraints で 0値も cropCaps に登録(明示 0 を制約として扱う)
- **案I3**: summary-table セルに違反ハイライト追加(視認性向上・γ対応)
- **案I4**: 警告UI を目立つ位置に固定表示(γ対応・UI設計改修)

### 殿への質問(3問以内)
| Q | 内容 |
|---|---|
| Q1 | 真因マトリクス確認: α否定 / β部分否定 / **γ確定**(summary-tableハイライト欠如) / δ否定 / **ε作物名表記揺れ確定**(殿入力データ「小麦(春播)/(秋播)/だいず cap=0」が真の上書き原因)で良いか? |
| Q2 | ε(作物名表記揺れ)の根本解消方針: (a)DB cleanup(殿が cap=0 行を削除) / (b)案I1 alias定義(春小麦↔小麦(春播) 統一) / (c)案I2 prepareConstraints 0値登録(cap=0 も制約として扱う・実質「禁止作物」表現) のいずれを採用? |
| Q3 | γ(警告UI) 改善別subtask: 案I3(summary-tableハイライト) + 案I4(警告固定表示) を Wave 2 として軍師 L4-L6 設計依頼するか? |

### Three Pillar Evidence
| 柱 | 証跡 |
|---|---|
| ① 親subtask | cmd_586 close 大団円(15 subtask+15 commit+D2撤廃15件連続push 2桁突破)・本subtask 設計のみ shogun リポへの docs/ 1ファイル追加候補 |
| ② Phase別 SSH | Phase 1(DB user_constraints schema+データ+API+Repository 全SSH)+Phase 2(rotationSolver.js全 check/evaluate関数+prepareConstraints+generateInitial main loop+localSearch 全SSH)+Phase 3(警告UI実装範囲・summary-table描画・componentsカバー範囲 全SSH)+Phase 4(pinned/制約交差点・ntripcaster) |
| ③ 真因根拠 | (1) DB user_constraints データに 「春小麦/秋小麦/大豆/てんさい/飼料作物/飼料用とうもろこし」+ 別エントリ「小麦(春播)/小麦(秋播)/だいず cap=0 min=0」 (2) prepareConstraints の `if (row.cap_ha && row.cap_ha > 0)` フィルタで 0値はスキップ・cropCaps 空 (3) checkCapConstraint で `cap == null || cap === 0` なら true 返却=制約なし扱い (4) summary-table 描画 L590-650 に違反ハイライトロジック完全欠如 |

---

## §2 Phase 1: DB+API+Repository 制約伝達経路追跡

### 2.1 user_constraints テーブル存在確認 (Phase 1-A/B)
```
crop_constraints / crop_history / crop_master / crop_polygons / user_constraints / user_crops

CREATE TABLE user_constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    constraints_json TEXT NOT NULL,
    forbidden_transitions TEXT,
    preferred_transitions TEXT,
    main_crops TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);
```

### 2.2 ★yasu(user_id=6) 制約データ★ (Phase 1-C・★真因 ε の決定的証跡★)
```json
[
  {"crop": "春小麦",          "min_ha": 4, "cap_ha": 7,  "min_gap_years": 4, "min_fields": 1, "max_fields": 1},
  {"crop": "秋小麦",          "min_ha": 4, "cap_ha": 7,  "min_gap_years": 4, "min_fields": 1, "max_fields": 1},
  {"crop": "大豆",            "min_ha": 4, "cap_ha": 10, "min_gap_years": 4, "min_fields": 1, "max_fields": 1},
  {"crop": "デントコーン",    "min_ha": 5, "cap_ha": 4,  "min_gap_years": 0, "min_fields": 0, "max_fields": 5},
  {"crop": "てんさい",        "min_ha": 3, "cap_ha": 7,  "min_gap_years": 4, "min_fields": 1, "max_fields": 3},
  {"crop": "馬鈴薯",          "min_ha": 0, "cap_ha": 0,  ...},
  {"crop": "飼料作物",        "min_ha": 0, "cap_ha": 2,  ...},
  {"crop": "飼料用とうもろこし","min_ha": 2, "cap_ha": 4,  ...},
  ★{"crop": "小麦(春播)",      "min_ha": 0, "cap_ha": 0, ...}★   ← 殿が別エントリで cap=0 登録
  ★{"crop": "小麦(秋播)",      "min_ha": 0, "cap_ha": 0, ...}★   ← 殿が別エントリで cap=0 登録
  ★{"crop": "だいず",          "min_ha": 0, "cap_ha": 0, ...}★   ← 殿が別エントリで cap=0 登録
]
```

★**ε仮説 確定の核心**★:
- 殿は「春小麦 cap=7」「秋小麦 cap=7」「大豆 cap=10」を入力済
- しかし**別エントリ**で「小麦(春播)」「小麦(秋播)」「だいず」を **cap=0 で登録**(これらは画面上 ソルバー結果として表示される作物名・殿が後から重複登録した形跡)
- ソルバーは内部で「小麦(秋播)」を生成・cropCaps["小麦(秋播)"] = 0 → 制約なし扱い → 17ha 上書き可
- 「秋小麦 cap=7」設定は cropCaps["秋小麦"] にあるが、ソルバー出力は「小麦(秋播)」なので **キー不一致**

### 2.3 /api/constraints GET/PUT 実装(plans.py L137-170)
```python
@router.get("/api/constraints", response_model=ConstraintsResponse)
def get_constraints(current_user: Dict = Depends(get_current_user)):
    data = UserConstraintsRepository.get_constraints(current_user["id"])
    if not data:
        return ConstraintsResponse(constraints=[], ...)
    return ConstraintsResponse(
        constraints=data.get("constraints", []),
        forbidden_transitions=data.get("forbidden_transitions", ""),
        preferred_transitions=data.get("preferred_transitions", ""),
        main_crops=data.get("main_crops", "")
    )

@router.put("/api/constraints", response_model=ConstraintsResponse)
def update_constraints(req: ConstraintsUpdate, current_user: Dict = Depends(get_current_user)):
    UserConstraintsRepository.save_constraints(user_id=current_user["id"], ...)
```
→ API 正常実装

### 2.4 UserConstraintsRepository (db_access.py L1905-1935)
```python
class UserConstraintsRepository:
    @staticmethod
    def get_constraints(user_id: int) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM user_constraints WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get('constraints_json'):
                data['constraints'] = json.loads(data['constraints_json'])
            else:
                data['constraints'] = []
            return data
```
→ Repository 正常実装・JSON parse でリスト化

### 2.5 α判定: **否定** (DB→API→Repository 全経路正常)

---

## §3 Phase 2: Rotation.jsx → solver 制約評価ロジック精読

### 3.1 prepareConstraints (Rotation.jsx L124-143・★0値フィルタの問題箇所★)
```javascript
const prepareConstraints = () => {
    if (!constraints || !constraints.constraints || constraints.constraints.length === 0) {
      return createDefaultConstraints();
    }

    const c = createDefaultConstraints();

    // 制約テーブルから
    for (const row of constraints.constraints) {
      const crop = row.crop;
      if (!crop) continue;

      if (row.min_ha && row.min_ha > 0) c.cropMins[crop] = row.min_ha;     // ← ★0値スキップ★
      if (row.cap_ha && row.cap_ha > 0) c.cropCaps[crop] = row.cap_ha;     // ← ★0値スキップ★
      if (row.min_gap_years && row.min_gap_years > 0) c.minGapYears[crop] = row.min_gap_years;
      if (row.min_fields && row.min_fields > 0) c.minFields[crop] = row.min_fields;
      if (row.max_fields && row.max_fields > 0) c.maxFields[crop] = row.max_fields;
    }
    ...
};
```

→ 「小麦(秋播) cap=0」エントリは `cap_ha > 0` false で スキップ → cropCaps["小麦(秋播)"] **未設定**
→ checkCapConstraint で `cap == null` → true 返却 = **制約なし扱い**

### 3.2 createDefaultConstraints (rotationSolver.js L39-52)
```javascript
export function createDefaultConstraints() {
  return {
    cropMins: {},          // 全crop 空・「小麦(秋播)」は未設定
    cropCaps: {},          // 全crop 空・「小麦(秋播)」は未設定
    minGapYears: {},
    minFields: {},
    maxFields: {},
    forbiddenTransitions: [],
    preferredTransitions: {},
    mainCrops: [],
    unknownMode: 'ignore'
  };
}
```

### 3.3 ★checkCapConstraint (rotationSolver.js L165-171・★制約なし扱いの実体★)
```javascript
checkCapConstraint(year, crop, plan, additionalHa = 0) {
    const cap = this.constraints.cropCaps[crop];
    if (cap == null || cap === 0) return true;                              // ← ★cap 未設定/0 なら 制約なし★
    const stats = this.calculateYearStats(year, plan);
    const currentHa = stats[crop]?.totalHa || 0;
    return currentHa + additionalHa <= cap;
}
```

→ cropCaps["小麦(秋播)"] = undefined → `cap == null` true → **制約なし**返却 → 17ha 上書き可

### 3.4 checkFieldCountConstraint (rotationSolver.js L173-183)
```javascript
checkFieldCountConstraint(year, crop, plan, adding = false) {
    const minF = this.constraints.minFields[crop] || 0;
    const maxF = this.constraints.maxFields[crop];
    const stats = this.calculateYearStats(year, plan);
    let currentCount = stats[crop]?.fieldCount || 0;
    if (adding) currentCount += 1;
    if (maxF != null && currentCount > maxF) {
      return { ok: false, message: `${crop}のほ場数が上限(${maxF})を超えます` };
    }
    return { ok: true, message: '' };
}
```
→ maxF 設定があれば動作・「小麦(秋播)」は maxFields 未設定→無制約

### 3.5 ★evaluateSolution violations 検出 (rotationSolver.js L213-256・実装あり)
```javascript
evaluateSolution(plan) {
    let score = 0;
    const violations = [];
    ...
    for (const year of this.futureYears) {
      const stats = yearStats[year];
      for (const crop of this.crops) {
        const cap = this.constraints.cropCaps[crop];
        if (cap != null && cap > 0) {                                       // ← ★cap=0 だと判定スキップ★
          const ha = stats[crop]?.totalHa || 0;
          if (ha > cap) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が上限(${cap}ha)を超過`);
            score -= 100;
          }
        }
        const min = this.constraints.cropMins[crop];
        if (min != null && min > 0) {                                       // ← ★min=0 だと判定スキップ★
          const ha = stats[crop]?.totalHa || 0;
          if (ha < min) {
            violations.push(`${year}: ${crop}の面積(${ha.toFixed(2)}ha)が下限(${min}ha)未満`);
            score -= 100;
          }
        }
      }
    }
    return { score, violations };
}
```

→ 「小麦(秋播) cap=0」は判定スキップ → violations に push されない → 警告なし
→ 「秋小麦 cap=7」も評価対象 = `crops` 配列に「秋小麦」が含まれていれば検出するが、`crops` は殿入力「小麦(春播)/(秋播)/だいず」等のソルバー出力名で構成 → 「秋小麦」キーは存在せず

### 3.6 generateInitialSolution main loop (rotationSolver.js L284-310・fallback)
```javascript
for (const fieldIdx of fieldIndices) {
    if (this.pinnedMap.has(`${fieldIdx},${year}`)) continue;
    let validCrops = this.getValidCrops(fieldIdx, year, plan);
    if (validCrops.length === 0) {
      validCrops = [...this.crops];
      this.errors.push(`警告: ほ場${this.fields[fieldIdx].fieldId}の${year}で制約を満たす作物がありません`);
    }
    let bestCrop = null;
    let bestScore = -Infinity;
    for (const crop of validCrops) {
      if (!this.checkCapConstraint(year, crop, plan, this.fields[fieldIdx].areaHa)) continue;
      const { ok } = this.checkFieldCountConstraint(year, crop, plan, true);
      if (!ok) continue;
      ...
    }
    if (bestCrop === null) {
      bestCrop = validCrops.length > 0 ? validCrops[0] : this.crops[0];     // ← fallback で違反 set
    }
    plan[`${fieldIdx},${year}`] = bestCrop;
}
```

→ check 全 false でも fallback で set → 違反が plan に格納される

### 3.7 β判定: **部分否定** (check関数自体は実装あり・cap=0 を「制約なし」扱いするのが本質的問題)

---

## §4 Phase 3: 警告UI 実装精読

### 4.1 警告UI 表示箇所 (Rotation.jsx L547-557)
```javascript
{result.errors.length > 0 && (
  <div className="warnings">
    <h4>⚠️ 警告/違反</h4>
    <ul>
      {result.errors.map((e, i) => (
        <li key={i}>{e}</li>
      ))}
    </ul>
  </div>
)}
```

→ `result.errors` (= solver.errors + violations) を `<div className="warnings">` 内にリスト表示
→ 表示自体はされている・しかし**スクロール位置・視認性低い可能性**
→ さらに「小麦(秋播) cap=0」では violations に push されないため、ここに出ない

### 4.2 ★summary-table 描画 (Rotation.jsx L590-650・★ハイライト完全欠如★)
```javascript
<h3>年別 作物面積(ha)</h3>
<div className="table-wrapper">
  <table className="data-table summary-table">
    <thead>
      <tr>
        <th>年</th>
        {crops.map((c) => <th key={c}>{c}</th>)}
        <th>合計</th>
      </tr>
    </thead>
    <tbody>
      {result.summaryTable.map((row, i) => (
        <tr key={i}>
          <td className={pastYears.includes(row.year) ? 'past-year' : 'future-year'}>
            {row.year}
          </td>
          {crops.map((c) => (
            <td key={c}>{parseFloat(row[c]).toFixed(1)}</td>      // ← ★ハイライト無★
          ))}
          <td className="total-cell">
            {crops.reduce((sum, c) => sum + parseFloat(row[c] || 0), 0).toFixed(1)}
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

→ summary-table のセル `<td>{parseFloat(row[c]).toFixed(1)}</td>` は**単純表示・違反検出ロジック完全欠如**
→ R9 セルが薄赤になっているとすれば、それは **計画表(rotation-table・別table)** の `future-year` クラス または `crop-cell future` のカラー指定が偶然 R9 に効いているだけ

### 4.3 計画表(rotation-table) future-year ハイライト
```javascript
{allYears.map((y) => (
  <th key={y} className={pastYears.includes(y) ? 'past-year' : 'future-year'}>
    {y}
  </th>
))}
...
<td key={y} className={`crop-cell ${pastYears.includes(y) ? 'past' : 'future'}`}>
  <span className={`crop-badge crop-${row[y]?.replace(/[^\w]/g, '') || 'empty'}`}>
    {row[y] || '-'}
  </span>
</td>
```

→ future-year 全カラム(R9/R10/R11/R12)に背景色 + crop-badge カラー→ **R9だけ薄赤に見えるのは crop-badge の crop種別カラーとfuture-year背景の重なり** (制約違反検出ロジックではない)

### 4.4 警告関連 components (Phase 3-C)
```
Layout.jsx:18 「警告」(navi label) 
ErrorMessage.jsx 「警告」(type=warning) ← API error 表示
```
→ ErrorMessage は API error 用・本件の制約違反検出には未活用

### 4.5 γ判定: **★確定★** (summary-tableハイライトロジック欠如・<div className="warnings"> 表示はあるも視認性低)

---

## §5 真因特定 (γ + ε 複合確定)

### 5.1 真因マトリクス(最終)

| 仮説 | 判定 | 一次根拠 | 二次根拠 |
|---|---|---|---|
| α 伝達経路漏れ | **否定** | user_constraints schema+データ正常 | /api/constraints GET 正常+prepareConstraints L124-143 正常 |
| β solver制約評価未組込 | **部分否定** | checkCapConstraint L165-171・checkFieldCountConstraint L173-183・evaluateSolution L213-256 実装あり | ただし cap=0 / min=0 は判定スキップ |
| **γ 警告UI部分実装** | **★確定★** | summary-table描画 L590-650 に違反ハイライト完全欠如 | <div className="warnings"> はあるが視認性低・R9薄赤は future-year クラス偶然 |
| δ pinned強制副作用 | **否定** | pinned skip(forEach先頭)は制約評価より先・無干渉 | cmd_586 で確証済 |
| **ε 作物名表記揺れ(新真因)** | **★確定★** | 殿入力「春小麦 cap=7」「秋小麦 cap=7」「大豆 cap=10」 + 別エントリ「**小麦(春播) cap=0 / 小麦(秋播) cap=0 / だいず cap=0**」 | ソルバー出力作物名「小麦(秋播)」は cap=0 = 制約なし扱い → 17ha 上書き可 |

### 5.2 ε(作物名表記揺れ) 発生機序

```
[ステップ1] 殿が制約設定画面で初回入力(画面上で「春小麦」「秋小麦」を選択)
   user_constraints DB に "春小麦 cap=7", "秋小麦 cap=7" 保存

[ステップ2] 殿が最適化実行
   → ソルバー内部 generateInitialSolution が「小麦(春播)」「小麦(秋播)」「だいず」を出力(ソルバー内部crops配列がこの表記)
   → 殿の画面: 「小麦(秋播)」と表示される(春小麦・秋小麦ではない)

[ステップ3] 殿が「あれ?小麦(秋播)?」と混乱・新規エントリで「小麦(秋播) cap=0」を追加登録
   user_constraints DB に "小麦(春播) cap=0", "小麦(秋播) cap=0", "だいず cap=0" 追記

[ステップ4] 最適化再実行
   prepareConstraints: cropCaps["小麦(秋播)"] = (cap=0 で スキップ・未登録) ←★
   ソルバー出力: 「小麦(秋播)」生成・cropCaps["小麦(秋播)"]=undefined → checkCap true (制約なし)
   → 17ha 出力可・違反なし扱い → 警告も出ない

[ステップ5] 殿: 「警告未表示・違反多発」と認識
```

### 5.3 ★crops 配列の出所★(crops と制約 crop 名の不一致の根)
- Rotation.jsx の `const DEFAULT_CROPS = ['春小麦', '秋小麦', '大豆', 'デントコーン', 'てんさい', '馬鈴薯'];` (L12) → これは defaultcrops
- 実 crops は `loadCrops()` で /api/user-crops から fetch・**ソルバー出力名「小麦(春播)/(秋播)/だいず」になっている可能性**
- 殿入力作物制約と crops 一覧の作物名が**不一致**

---

## §6 修正案 (予断なし整理・実装は別subtask候補)

### 案I1: 作物名統一(alias 定義)
- 春小麦 ↔ 小麦(春播) / 秋小麦 ↔ 小麦(秋播) / 大豆 ↔ だいず の alias map 定義
- prepareConstraints で alias 解決
- 影響: 1ファイル・~10行
- 長所: DB 無変更・後方互換性
- 短所: alias map のメンテナンスコスト・将来作物追加時の混乱

### 案I2: prepareConstraints で 0値も登録
- `if (row.cap_ha != null) c.cropCaps[crop] = row.cap_ha;` で 0値も登録
- checkCapConstraint の `cap === 0` 判定で「禁止」扱い(0=禁止作物表現)
- 影響: 1ファイル・5行程度
- 長所: 「禁止作物」表現として明示
- 短所: 既存 cap=0 ロジックの意図(制約なし vs 禁止)を再定義必要

### 案I3: summary-table セル違反ハイライト追加
- summary-table 描画時 cropCaps[c] と row[c] 比較し違反時 className 付与
- 影響: 1ファイル・~15行
- 長所: 視覚的明確化・警告気付き性向上
- 短所: 案I1/I2 解消後に行うほうが整合性良い

### 案I4: 警告UI 固定表示
- `<div className="warnings">` を画面上部固定 or sticky 配置・件数バッジ追加
- 影響: 1ファイル+CSS・~10行
- 長所: 視認性最大化
- 短所: UI設計改修コスト

### 推奨実装順 (案間関係)
1. ε解消: 殿に DB cleanup 提案(殿が誤入力した cap=0 行を削除) + 案I1 alias定義
2. β補強: 案I2 (cap=0 を「禁止」として明示)
3. γ解消: 案I3 summary-tableハイライト
4. γ補強: 案I4 警告UI固定表示

---

## §7 殿への質問(3問以内)+ 戦略提案

| Q | 内容 |
|---|---|
| **Q1** | 真因マトリクス確認: α否定 / β部分否定 / **γ確定**(summary-tableハイライト欠如) / δ否定 / **★ε作物名表記揺れ確定★**(殿入力データの「小麦(春播)/(秋播)/だいず cap=0」が真の上書き原因)で良いか? |
| **Q2** | ε根本解消方針: (a)DB cleanup 殿手作業(誤入力 cap=0 行削除)・(b)案I1 alias定義(春小麦↔小麦(春播)統一)・(c)案I2 cap=0「禁止作物」扱いに再定義・のいずれを採用? |
| **Q3** | γ警告UI 改善別subtask: 案I3(summary-tableハイライト)+案I4(警告固定表示) を cmd_590 Wave 2 として軍師 L4-L6 設計依頼するか?(or 部屋子1継続調査も可) |

### 戦略提案
- **第1優先**: 殿が ε(作物名表記揺れ) の存在認識+DB cleanup or alias 採択判断
- **第2優先**: γ警告UI 改善(視認性低・違反検出時の明示が不足)
- **第3優先**: cmd_589 軍師schema網羅監査(subtask_1273)の結果と本件統合(本件は constraints schema layer の差異 11~12回目相当)

---

## 付録: お針子FB継続適用

### ssh_raw_outputs Phase別貼付状況
| Phase | 貼付場所 | completeness |
|---|---|---|
| Phase 1-A〜E | §2 | DB schema+yasu 制約データ+ /api/constraints+Repository 全SSH貼付 |
| Phase 2-A〜H | §3 | prepareConstraints+createDefaultConstraints+check系全関数+evaluateSolution+generateInitial+localSearch 全SSH貼付 |
| Phase 3-A〜E | §4 | 警告UI+summary-table+rotation-table+components+CSS class 全SSH貼付 |
| Phase 4-A〜C | (本書随所) | pinned skip 順序+ntripcaster保全 |

### three_pillar_evidence
| 柱 | 内容 |
|---|---|
| ① 親subtask | cmd_586 close 大団円(15 subtask+15 commit+D2撤廃15件連続push 2桁突破)・本subtask 設計のみ |
| ② Phase別 SSH | Phase 1+2+3+4 を §2-§4 完全貼付 |
| ③ 真因根拠 | (1) DB yasu user_constraints データ直視で殿入力「小麦(春播)/(秋播)/だいず cap=0」発見 (2) prepareConstraints L137 `if (row.cap_ha && row.cap_ha > 0)` 0値スキップ直視 (3) checkCapConstraint L165-167 `cap == null || cap === 0` 制約なし扱い直視 (4) summary-table L640 `<td>{parseFloat(row[c]).toFixed(1)}</td>` ハイライト欠如直視 |

### oharikoma_feedback_reflection
- ✅ memory#feedback_vps_audit_raw_logs.md: 生SSH全Phase貼付(要約禁止) → §2-§4 完全貼付
- ✅ memory#feedback_needs_audit_ssh_log.md: needs_audit=true subtask の SSH生ログ添付 → 全Phase貼付
- ✅ memory#feedback_no_predisposition.md: 修正案 I1/I2/I3/I4 機械的整理・「推奨実装順」は構造分析・「殿選択を仰ぐ」中立表現
- ✅ memory#feedback_crlf_binary_edit.md: 該当なし(本subtask read-only・編集なし)

### F006 D2撤廃継続
- 本subtask: 設計のみ・実装なし → shogun リポへの docs/ 1ファイル追加のみ・rotation-planner自リポ無変更

### ntripcaster保全
- 全Phase pid 3216892/3216893+port 2101 LISTEN 完全継続

### 品質ループ第25周
- 1247→…→1276(cmd_586 close)→**1277**(cmd_590 Wave 1)

### schema差異検出 13回目候補
- 1257(POST kwarg)・1258(pesticides×4)・1259(crop_history)・1260(pinned_assignments)・1264(year表記)・1268(solve 3段階skip)・1270(認証)・1271(GET SQL select)・1272(案G1実装)・1275(prepareFields layer差)・1276(案H1実装)・1273(軍師schema監査)・**1277(constraints crop名 layer差)13回目候補**

---

(cmd_590 Wave 1 read-only調査完遂・真因 γ+ε 複合確定・修正案 I1/I2/I3/I4 殿選択待ち・cmd_586 大団円後の運用品質課題)
