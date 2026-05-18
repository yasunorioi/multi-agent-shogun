# rotation-planner v2: ほ場→輪作画面 反映バグ調査 (cmd_580 Wave 1)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1246 / cmd_580 |
| 作成日時 | 2026-05-18T15:30 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp |
| 対象ファイル | /var/www/rotation-planner-v2/app/frontend/app/src/pages/Rotation.jsx:81-99 |
| 報告書範囲 | read-only調査+設計のみ (実装は別subtask) |

---

## §1 エグゼクティブサマリ

**症状**: yasu(殿新規ユーザー)で ほ場20件登録・crop_history 29件記録済(R8/R9両方)・しかし輪作画面に R8現行作物が見えず

**真因**: **新仮説ζ (令和↔西暦 変換欠落) 確定** — `Rotation.jsx:86` の `histories[field.id][`R${h.year}`] = h.crop` が DB値 `2026` から `"R2026"` キーを生成・UI期待値 `"R8"` (令和8年) と不一致

**殿仮説検証**:
- α (異テーブル参照): **部分的YES** — rotation_plans 0件・しかし crop_history 29件あり (R8/R9両方)
- β (user_id整合性): **NO** — yasu user_id=6 で全データ整合
- ε (年度フィルタ過剰): **NO** — フィルタではなくキー不一致

**推奨修正案 (最小変更)**:
`Rotation.jsx:86` の R接頭辞付与時に 令和変換 `reiwaYear = Number(h.year) - 2018` を介在
- 2019→R1, 2020→R2, ..., 2026→R8
- 実装は別subtask起票 (本subtaskは設計のみ)

**殿質問**: (1) コード修正承認 (2) upstream PR要否 (3) UI側 vs データ層 どちらで変換する設計か

---

## §2 DB実体スナップショット (Phase 1 出力)

### users.yasu
```
id=6 username=yasu role=farmer is_active=1
```

### fields (yasu所有) — **20件登録完了**
- 全件 id 2-21・user_id=6
- 地区: 中央(8件)・上山口(2件)・戸磯(10件)
- 例: id=2 IMP_6_001 中央 hase-2 3.8033ha / id=21 IMP_6_020 戸磯 kawashima 0.1505ha

### rotation_plans (yasu) — **0件** (空)
- yasu は新規ユーザーで輪作計画未作成・**plans 空が空配列を返す原因の1つ**

### plan_details (yasu経由) — **0件** (rotation_plans 0件のため)

### crop_history (yasu経由) — **29件** ★存在する
- field_id 2-21 × year=2026(R8/20件) + year=2027(R9/9件)
- 例:
  - field_id=2 year=2026 てんさい
  - field_id=3 year=2026 てんさい
  - field_id=4 year=2026 飼料作物
  - field_id=4 year=2027 飼料作物
  - field_id=18 year=2026 長なす
  - field_id=18 year=2027 長なす
- **DB year カラムは西暦TEXT (例: "2026")**

### schema 確認 (年度フィルタ実装の手がかり)
```sql
CREATE TABLE crop_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
    year TEXT NOT NULL,  -- ★ TEXT・西暦保存
    crop TEXT NOT NULL,
    is_inferred INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(field_id, year)
);
```

→ 仮説α一部肯定: 「現行作物」格納先は **crop_history** (rotation_plans/plan_details ではない)

---

## §3 API+SQL精読結果 (Phase 2 出力)

### 輪作画面 (Rotation.jsx) のデータ読込フロー

```javascript
// /var/www/rotation-planner-v2/app/frontend/app/src/pages/Rotation.jsx:7
import { fieldApi, constraintApi, planApi, cropApi, rotationApi } from '../lib/api';

// L48,55 useEffect でloadHistories呼び出し

// L81-99 loadHistories() 関数
const loadHistories = async () => {
    const histories = {};
    for (const field of fields) {
      try {
        const history = await fieldApi.getHistory(field.id);  // → GET /api/fields/{field_id}/history
        histories[field.id] = {};
        for (const h of history) {
          histories[field.id][`R${h.year}`] = h.crop;  // ★L86 問題箇所
        }
      } catch {
        histories[field.id] = {};
      }
    }
    setFieldHistories(histories);
};
```

### `/api/fields/{field_id}/history` 動作確認 (ja_staff token・read-only)
```bash
curl /api/fields/2/history → 200 OK
[{"id":1,"field_id":2,"year":2026,"crop":"てんさい"}]
```
→ APIは正しく **西暦 `2026`** を返す

### `/api/plans` (yasu) → `[]` 空配列 (rotation_plans 0件のため)

### `/api/fields/{field_id}/current-crop` (fields.py L518)
```python
# 1. 輪作計画から作物を取得
plans = PlanRepository.get_plans(current_user["id"])
for plan in plans: ...  # yasu 0件 = skip
# 2. 作付履歴から取得
history = CropHistoryRepository.get_history(field_id)
for h in history:
    if h["year"] == year:
        return {"crop": h["crop"], "source": "history"}
```
- このendpointは「西暦 year」で問合せ可能・**Rotation.jsxは使っていない** (上記grep結果)
- Rotation.jsx は `fieldApi.getHistory(field.id)` のみ使用

### API routes実態 (router prefix)
- /api/fields (✓)
- /api/plans (✓)
- /api/crops (✓)
- /api/admin/* (✓)
- /api/inventory (✓)
- /api/pesticides → **404** (router未登録の可能性・subtask_1236で記録済・本subtask対象外)
- /api/gis/* → **404** (同上)
- /api/dashboard → **404** (同上)

---

## §4 真因特定

### 確定: **新仮説ζ (令和↔西暦 変換欠落)**

**ロジック追跡**:
1. ユーザーがほ場ID 2 を登録時、`crop_year` を「令和8年」のドロップダウンで選択
2. fields.py POST `/api/fields/{field_id}/history` 経由で DB に保存 → DB値: `year="2026"` (西暦TEXT)
3. Rotation.jsx が `fieldApi.getHistory(2)` → `[{year: 2026, crop: "てんさい"}]` を取得
4. **L86**: `histories[2]["R2026"] = "てんさい"` というキー生成
5. UI レンダリング側が `histories[2]["R8"]` (令和8年表記) を期待・**キー不一致で undefined**
6. 結果: 「R8列に現行作物が見えない」

### 殿仮説検証 (根拠付き)
| 仮説 | 判定 | 根拠 |
|---|---|---|
| α 異テーブル参照 | **部分肯定** | rotation_plans=0/crop_history=29 (現行作物は crop_history・rotation_plans は別目的の計画格納) |
| β user_id整合性ズレ | **否定** | yasu user_id=6 で fields/crop_history(via field_id JOIN)/plans 全整合 |
| ε 年度フィルタ過剰 | **否定** | フィルタ実装なし・「キー命名規則」の問題 |
| **ζ 令和↔西暦変換欠落** | **確定** | Rotation.jsx:86 で R + 西暦 → "R2026" 生成・UI期待 "R8" と不一致 |

### 補足: 「数分待つ」要素=非同期/キャッシュは関係なし
- API 即時応答 (subtask_1236 で平均レスポンス確認)
- バッチcronなし (本subtaskでgrep未検出)

---

## §5 修正案 (最小変更+rollback)

### 案A: フロントエンドで令和変換 (推奨・最小変更)

`Rotation.jsx:81-99` の `loadHistories()` を以下に変更:
```javascript
const loadHistories = async () => {
    const histories = {};
    for (const field of fields) {
      try {
        const history = await fieldApi.getHistory(field.id);
        histories[field.id] = {};
        for (const h of history) {
          // 西暦 → 令和変換 (2019=R1)
          const reiwaYear = Number(h.year) - 2018;
          histories[field.id][`R${reiwaYear}`] = h.crop;
        }
      } catch {
        histories[field.id] = {};
      }
    }
    setFieldHistories(histories);
};
```

**長所**: 単一行変更・ロジック明示・rollback容易 (1行 revert)
**短所**: 平成・大正の年号には対応せず (現状要件外)

### 案B: バックエンドで令和変換 (API応答変更)

`fields.py` の crop_history API endpoint で `year` を `R8` 形式に変換して返す。
**短所**: 既存 frontend の `R${year}` 直書きと衝突・他frontend(管理画面等)への波及大

### 案C: UI側を西暦キーに合わせる (推奨せず)

Rotation.jsx の UI テーブル columns を `R2026, R2027` 等の西暦キーに変える。
**短所**: 殿の業務用語(令和)から離れる・ユーザビリティ悪化

### 推奨: **案A** (フロントエンド1行変更)

### Rollback手順
```bash
ssh debian@... 'sudo -u webapp git -C /var/www/rotation-planner-v2/app diff HEAD~1 frontend/app/src/pages/Rotation.jsx'
# 修正前後の差分確認後・必要時は git checkout HEAD~1 -- pages/Rotation.jsx で revert
```

---

## §6 殿への質問

| # | 質問 |
|---|---|
| Q1 | **修正案A承認可否** (Rotation.jsx L86 を令和変換に1行変更・別subtaskで実装) |
| Q2 | **upstream PR要否** (本修正をfork-origin に push して upstream反映するか・F006抑制継続中) |
| Q3 | UI側 vs データ層 どちらで変換するべき設計か (案A vs 案B のアーキテクチャ判断) |
| Q4 | 他の画面 (Dashboard.jsx, DataManagement.jsx) でも同じパターンの不具合があるか別subtaskで調査要? |
| Q5 | `2019=R1` の前提でよいか? (改元年=2019/平成31年=2018年4月までは平成・5/1から令和) — 業務的に「2018年=H30」のcrop_history が登録される可能性は? |

### 補足: cmd_577 申し送りとの整合
本バグは cmd_577 milestone 後の発見・rotation-planner v2 では認証フロー (subtask_1235/1236) + DB schema (subtask_1241) は完遂・**フロントエンドの令和/西暦変換**のみ残課題として cmd_580 で対応。

---

## 付録: 実行コマンド一覧 (read-only・F006抑制継続)

```bash
# 全て ssh debian@ik1-421-42663.vs.sakura.ne.jp '...' 経由・read-only

# Phase 1 DB SELECT (sqlite3 read-only)
sudo -u webapp sqlite3 -header -column $DB "SELECT * FROM users/fields/rotation_plans/plan_details/crop_history WHERE..."
sudo -u webapp sqlite3 $DB ".schema fields/rotation_plans/plan_details/crop_history"

# Phase 2 grep + head
sudo -u webapp ls -la /var/www/rotation-planner-v2/app/api/routers/
sudo -u webapp grep -rnE "rotation_plans|plan_details|crop_history" .../api/routers/
sudo -u webapp head -200 .../plans.py / .../fields.py
sudo -u webapp grep -rnE "fieldApi|planApi|R\${" .../frontend/app/src/

# Phase 2 live API (ja_staff token・read-only GET)
curl /api/plans /api/fields /api/crops /api/fields/2/history
```

書き込み・サービス操作・ファイル変更は一切なし。

---

(cmd_580 Wave 1 真因特定+修正案提示完了・実装は別subtaskで起票判断)
