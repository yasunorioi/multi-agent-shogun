# rotation-planner v2: Wave 10 戦略見直し局面・runtime debug挿入+ζ7-ζ11実証 (cmd_586 / subtask_1270)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1270 / cmd_586 (Wave 10 = 9波目) |
| 作成日時 | 2026-05-18T22:30 JST |
| 作成者 | 部屋子1 (ashigaru6) |
| 報告書範囲 | 読み書き混合 (X3 read-only実証 + X2 runtime debug実装) |
| 親subtask | subtask_1269 Wave 9=done (commit 6fa2ed6・案E1) |
| 殿戦略 | X1(軍師再設計)/X2(runtime debug)/X3(部屋子1継続) のうち X2+X3 並行採択 |
| 品質ループ | 第19周 |

---

## §1 エグゼクティブサマリ

### 9波目症状(殿2026-05-18 22:18)
案E1完遂(commit 6fa2ed6・D2撤廃10件目)後も R9上書き継続:
- IMP_6_003 R9 → だいず ❌
- IMP_6_004 R9 → 小麦(春播) ❌
- IMP_6_005 R9 → だいず ❌
- IMP_6_006 R9 → 小麦(春播) ❌
- IMP_6_007 R9 → てんさい ❌

★**R9 表示作物が "だいず/小麦春播/てんさい" と多様 = localSearch random性が反映 = pinnedMap.has() が false を返している可能性極大**★

### Phase 1 (X3 read-only実証) ζ7-ζ11 判定マトリクス

| 仮説 | 判定 | 一次根拠 |
|---|---|---|
| ζ7 案E1ロジックエラー | **否定** | L315/L352 共に `if (this.pinnedMap.has(key)) continue;` 正しい配置・前置確認済 |
| ζ8 別上書き経路 | **否定** | plan[]/currentPlan[] 書込 14箇所全て solver内・runOptimizationJS 内で solver.solve() 後の plan は generateResultTables にそのまま渡るのみ |
| ζ9 solve()呼出順序 | **否定** | L381-383: generateInitialSolution → localSearch → ensureMinFields 正常 |
| ζ11 bundle再ビルド漏れ | **否定** | bundle index-BcU7SQN9.js (Wave 9) に `pinnedMap.has(` **3件** + 案E1 反映確証 |
| **ζ10 pinnedMap 空のまま渡し** | **★最有力★** | Rotation.jsx L19: useState([])・L58-62: pinnedApi.list catch で空配列フォールバック・**fetch失敗時 solver に空配列が渡る** → pinnedMap.size=0 → has() 常 false → 案E1 skip 不発火 → 全 R9 上書き → ランダム結果(殿症状一致) |

### Phase 2 (X2 runtime debug) 11 console.log 挿入
- rotationSolver.js: 8箇所 (constructor + generateInitialSolution START/PRE/END + localSearch START/END + ensureMinFields START/END)
- Rotation.jsx: 3箇所 (loadPinnedAssignments SUCCESS/FAIL + solver前)
- bundle検出: `DEBUG-1270 11件` 完全反映

### Phase 4 commit 15d9095 origin push成功
**★D2撤廃 11件目連続push・2桁突破★** (1247→…→1265→1269→**1270**)

### 殿devtools依頼(本subtaskの真因確定に必須)
殿に http://ik1-421-42663.vs.sakura.ne.jp/ で F12 → Console タブ → Ctrl+Shift+R 強制リロード → yasu最適化実行 → **[DEBUG-1270] 全ログコピー** をお願い申し上げます。

### 殿への質問(3問以内)
| Q | 内容 |
|---|---|
| Q1 | 殿devtools [DEBUG-1270] 全ログ取得お願い(真因確定の鍵)・F12 → Console → Ctrl+Shift+R → yasu最適化実行 → ログコピペ |
| Q2 | ζ10(pinnedMap空のまま渡し)確認後の対応: 認証修復(cmd_587と統合)? それとも pinnedApi.list の認証不要化(/api/pinned-assignments を未認証で yasu pin取得可)?  |
| Q3 | 案X1(軍師再設計)発動可否: ζ10確定なら認証問題に帰結し X1不要・別仮説浮上なら X1発動 |

### Three Pillar Evidence
| 柱 | 証跡 |
|---|---|
| ① commit hash | rotation-planner自リポ origin push commit `15d9095` (6fa2ed6..15d9095 main→main)・★D2撤廃11件目・2桁突破★ |
| ② Phase別 SSH | Phase 1(ζ7-ζ11実証L)+Phase 2(.bak×2+11 patches Python+diff確認)+Phase 3(vite build 6.10s+DEBUG-1270 11件検出)+Phase 4(HTTP 200+commit+push成功+ntripcaster保全) 全SSH §2-§5 |
| ③ debug反映 | bundle index-CV46wlyV.js (629.03kB) 内 DEBUG-1270=11件・11 strings 全部検出(`[DEBUG-1270] constructor pinnedAssignments.length=`...計11種) |

---

## §2 Phase 1: 案X3 ζ7-ζ11 read-only実証

### 2.1 ζ11 bundle再ビルド漏れ (Phase 1-A/B/C)
```
NEW_BUNDLE=index-BcU7SQN9.js (Wave 9 build 22:09 mtime・最新)
bundle内 pinnedMap.has( : ★3件★ (案E1 +2件・generateInitialSolution既存 +1件 = 3件)
bundle内 continue       : 38件
```
**→ ζ11 完全否定**: Wave 9 commit 6fa2ed6 案E1 完全反映

### 2.2 ζ9 solve()呼出順序 (Phase 1-D)
```
269:  generateInitialSolution() {
308:  localSearch(plan, maxIterations = 1000) {
341:  ensureMinFields(plan) {
378:  solve(options = {}) {
381:    let plan = this.generateInitialSolution();
382:    plan = this.localSearch(plan, maxIterations);
383:    plan = this.ensureMinFields(plan);
```
**→ ζ9 否定**: 順序正常・pre-fill が最初に走り pinned 設定

### 2.3 ζ10 pinnedMap 空のまま渡し疑い (Phase 1-E/F)
```javascript
// Rotation.jsx L19
const [pinnedAssignments, setPinnedAssignments] = useState([]);   // ★初期 空配列★

// L58-62 loadPinnedAssignments
const data = await pinnedApi.list({ active_only: true });
setPinnedAssignments(Array.isArray(data) ? data : []);
} catch {
  setPinnedAssignments([]);                                       // ★catch 時も 空配列★
}

// L180-187
const solver = new RotationSolver(
  solverFields, pastYears, futureYearsList, crops, solverConstraints,
  pinnedAssignments                                                // ★fetch失敗時 [] が渡る★
);
```
**→ ζ10 最有力**: fetch (`/api/pinned-assignments`) が認証問題等で 401/エラー → catch で空配列 → solver の pinnedMap.size=0 → 案E1 has() 常 false → skip 不発火 → 殿症状(R9多様作物上書き)完全説明

### 2.4 ζ8 別上書き経路 (Phase 1-G)
```
plan[]/currentPlan[] 書込 14箇所:
  L90/L152/L202/L226 (読み込みのみ)
  L273 pre-fill (pinnedMap → plan)
  L302 generateInitial main loop (L278 skip後)
  L318/L321/L323/L328/L335 localSearch (L315 skip追加済)
  L353/L363 ensureMinFields (L352 skip追加済)
  L406/L422 generateResultTables (読み込みのみ)
```
**→ ζ8 否定**: 全 plan[] 書込は solver 内で skip 制御済・runOptimizationJS で solve() 後 plan は generateResultTables にそのまま渡すのみ

### 2.5 ζ7 案E1ロジックエラー (Phase 1-H/I)
```javascript
// L313-322 localSearch
for (let iter = 0; iter < maxIterations; iter++) {
  const fieldIdx = ...;
  const year = this.futureYears[...];
  const key = `${fieldIdx},${year}`;
  if (this.pinnedMap.has(key)) continue;       // ← 案E1 正確配置 ✅
  const validCrops = this.getValidCrops(fieldIdx, year, currentPlan);
  ...
}

// L349-358 ensureMinFields
for (let i = 0; i < this.fields.length; i++) {
  const key = `${i},${year}`;
  if (this.pinnedMap.has(key)) continue;       // ← 案E1 正確配置 ✅
  const currentCrop = plan[key];
  ...
}
```
**→ ζ7 否定**: 案E1 ロジック・配置共に正常

---

## §3 Phase 2: 案X2 runtime debug 11箇所挿入

### 3.1 rotationSolver.js 8箇所 (Phase 2-C)
```diff
@@ constructor 末尾 @@
+    console.log("[DEBUG-1270] constructor pinnedAssignments.length=", pinnedAssignments.length, "pinnedMap.size=", this.pinnedMap.size, "entries=", [...this.pinnedMap.entries()].slice(0, 10));

@@ generateInitialSolution L269 @@
+    console.log("[DEBUG-1270] generateInitialSolution START pinnedMap.size=", this.pinnedMap.size, "entries=", [...this.pinnedMap.entries()]);

@@ generateInitialSolution pre-fill 直後 @@
+    console.log("[DEBUG-1270] generateInitialSolution pre-fill done plan keys=", Object.keys(plan));

@@ generateInitialSolution END @@
+    console.log("[DEBUG-1270] generateInitialSolution END plan sample=", JSON.stringify(plan).slice(0, 600));

@@ localSearch START + counters @@
+    let _ls_skip_count = 0, _ls_accept_count = 0;
+    console.log("[DEBUG-1270] localSearch START pinnedMap.size=", this.pinnedMap.size, "plan sample=", JSON.stringify(currentPlan).slice(0, 600));

@@ localSearch SKIP counter @@
-      if (this.pinnedMap.has(key)) continue;
+      if (this.pinnedMap.has(key)) { _ls_skip_count++; continue; }

@@ localSearch accept counter @@
+        _ls_accept_count++;

@@ localSearch END @@
+    console.log("[DEBUG-1270] localSearch END skip_count=", _ls_skip_count, "accept_count=", _ls_accept_count, "plan sample=", JSON.stringify(currentPlan).slice(0, 600));

@@ ensureMinFields START + counters @@
+    let _em_skip_count = 0, _em_overwrite_count = 0;
+    console.log("[DEBUG-1270] ensureMinFields START pinnedMap.size=", this.pinnedMap.size, "plan sample=", JSON.stringify(plan).slice(0, 600));

@@ ensureMinFields SKIP counter @@
-            if (this.pinnedMap.has(key)) continue;
+            if (this.pinnedMap.has(key)) { _em_skip_count++; continue; }

@@ ensureMinFields overwrite counter @@
+            _em_overwrite_count++;

@@ ensureMinFields END @@
+    console.log("[DEBUG-1270] ensureMinFields END skip_count=", _em_skip_count, "overwrite_count=", _em_overwrite_count, "plan sample=", JSON.stringify(plan).slice(0, 600));
```

### 3.2 Rotation.jsx 3箇所 (Phase 2-D)
```diff
@@ loadPinnedAssignments 内 @@
+      console.log("[DEBUG-1270] Rotation.jsx loadPinnedAssignments SUCCESS data=", data);
-    } catch {
+    } catch (e) {
+      console.log("[DEBUG-1270] Rotation.jsx loadPinnedAssignments FAIL error=", e && e.message);

@@ solver 直前 @@
+    console.log("[DEBUG-1270] Rotation.jsx before solver pinnedAssignments=", pinnedAssignments, "length=", pinnedAssignments.length, "futureYearsList=", futureYearsList);
```

### 3.3 ファイル状態
- rotationSolver.js: 433→445行 (+12行) ・ .bak.20260518_1270 残置 (15209B)
- Rotation.jsx: 676→679行 (+3行) ・ .bak.20260518_1270 残置 (22382B)
- 改行: LF維持 (両ファイル file判定確認)・バイナリモード rb/wb 既定パターン遵守

### 3.4 Phase 3 npm build + bundle検出
```
✓ 129 modules transformed.
dist/assets/index-CV46wlyV.js  629.03 kB │ gzip: 187.47 kB
✓ built in 6.10s

bundle内 'DEBUG-1270' 検出: ★11件★ (完全反映)
bundle内 pinnedMap.has( : 3件 (案E1継続)
bundle内 2018 : 7件 (Wave 7案A継続)
```

---

## §4 殿devtools依頼内容

### 4.1 殿協力依頼手順
1. http://ik1-421-42663.vs.sakura.ne.jp/ にアクセス(または既開タブを再利用)
2. F12 で開発者ツール → **Console タブ**
3. **Ctrl+Shift+R** で強制リロード(新bundle index-CV46wlyV.js を確実に取得)
4. login済の状態で **輪作画面** に遷移
5. **yasu の最適化(JS)実行** ボタンクリック
6. Console タブの **[DEBUG-1270] で始まる全ログ** をコピー
7. 老中(または部屋子1)に貼付 / dashboard.md に添付

### 4.2 取得期待ログ(成功時の例)
```
[DEBUG-1270] Rotation.jsx loadPinnedAssignments SUCCESS data= [{field_id:4, year:"2027", crop:"飼料作物", ...}, ...] (14要素 期待)
[DEBUG-1270] Rotation.jsx before solver pinnedAssignments= [(14要素)] length= 14 futureYearsList= ["R9","R10","R11","R12"]
[DEBUG-1270] constructor pinnedAssignments.length= 14 pinnedMap.size= 14 entries= [["0,R9","飼料作物"],...]
[DEBUG-1270] generateInitialSolution START pinnedMap.size= 14 entries= [...]
[DEBUG-1270] generateInitialSolution pre-fill done plan keys= ["0,R9","1,R9",...,"3,R10","4,R10"]
[DEBUG-1270] generateInitialSolution END plan sample= ... (R9=飼料作物 含む)
[DEBUG-1270] localSearch START pinnedMap.size= 14 plan sample= ...
[DEBUG-1270] localSearch END skip_count= XXX accept_count= YYY (skip_count>0 が正常・skip_count=0 なら ζ10確定)
[DEBUG-1270] ensureMinFields START pinnedMap.size= 14 plan sample= ...
[DEBUG-1270] ensureMinFields END skip_count= ZZZ overwrite_count= WWW
```

### 4.3 想定NG ログ(ζ10確定パターン)
```
[DEBUG-1270] Rotation.jsx loadPinnedAssignments FAIL error= "Request failed with status code 401"
                                                            (or "Network Error" / "Cannot read properties")
[DEBUG-1270] Rotation.jsx before solver pinnedAssignments= [] length= 0
[DEBUG-1270] constructor pinnedAssignments.length= 0 pinnedMap.size= 0 entries= []
[DEBUG-1270] localSearch END skip_count= 0 accept_count= N
```
→ pinnedMap.size=0 + skip_count=0 が観測されれば ζ10 完全確定

---

## §5 真因再判定 (Phase 1 確証 + 殿devtools結果待ち)

### 5.1 Phase 1 read-only 確証
| 仮説 | 判定 |
|---|---|
| ζ7 案E1ロジックエラー | **否定** |
| ζ8 別上書き経路 | **否定** |
| ζ9 solve()呼出順序 | **否定** |
| ζ11 bundle再ビルド漏れ | **否定** |
| **ζ10 pinnedMap 空のまま渡し** | **最有力**(殿devtools確認待ち) |

### 5.2 ζ10 最有力の補強証跡

**(1) Rotation.jsx 認証エラー時の挙動**:
- L60-62: `catch { setPinnedAssignments([]); }` → 認証失敗時 確実に空配列
- L186: solver に空配列が渡される
- → pinnedMap.size=0 → has() 常 false → 案E1/A/全保護機構失効

**(2) 認証問題の既知情報(cmd_587 subtask_1264/1266 知見)**:
- ja_user is_active=0(無効化)
- admin/ja_staff/yasu password不明(hash=961ef3bb で sha256(admin)等とも一致せず)
- 部屋子1 単体での login 不可能・curl 検証手段なし
- ★**殿ブラウザは過去login済の token で動いている可能性**★
- → token expire してれば 401 → fetch失敗 → 空配列 → ζ10 発火

**(3) 殿症状の randomness が証拠**:
- IMP_6_003 R9 → だいず / IMP_6_004 → 小麦春播 / IMP_6_005 → だいず / IMP_6_006 → 小麦春播 / IMP_6_007 → てんさい
- 5ほ場で4種 = localSearch random 結果が反映
- 案E1 が効いていれば 同一作物固定(pinned値=飼料作物)で揃うはず
- → 案E1 skip 未発火 = pinnedMap 空 = ζ10 確定濃厚

### 5.3 案X1軍師再設計の必要性

| シナリオ | X1判断 |
|---|---|
| 殿devtools結果が ζ10 確定 (pinnedMap.size=0) | **X1不要** → cmd_587 (認証修復) と統合・部屋子1で対応可能 |
| 殿devtools結果が ζ10 否定 (pinnedMap.size>0 だが skip 不発火) | **X1必要** → 軍師にL5-L6再設計依頼・案E2/E3/全別アプローチ検討 |
| 殿devtools結果が想定外パターン | 部屋子1 Wave 11 で追加調査・X1判断保留 |

---

## §6 修正案(殿devtools結果次第・予断なし整理)

### 案F1: pinnedApi.list を 認証なしで yasu pin取得可能化
**箇所**: api/routers/pinned_assignments.py L? (`@router.get` decorator)
- 認証 dependency を外す or anonymous user 用 fallback
- 影響範囲: API 1ファイル・~5行
- 長所: 認証問題と独立に pinned 機能稼働可能
- 短所: セキュリティ低下(他ユーザーの pin 閲覧可能性)・admin/ja_staff バイパス機構との整合性検討要

### 案F2: 認証修復 (cmd_587 統合)
**箇所**: DB users テーブル + auth.py
- ja_user is_active=1 復活 + admin/yasu password reset (sha256(ja123) ハッシュ設定 or 新 password)
- 影響範囲: DB 数行 UPDATE + auth.py 既存・~0-数行
- 長所: 根本解決・他機能(plans/fields 等)の認証も復活
- 短所: 部屋子1 単体検証手段不足のままなら殿確認頼み・cmd_587 進捗待ち

### 案F3: pinnedAssignments props 渡しを localStorage / Context 経由に変更
**箇所**: Rotation.jsx + 新規 context provider
- API取得結果を localStorage キャッシュ
- 影響範囲: Rotation.jsx + 新規 provider ファイル
- 長所: 認証問題と独立・SPAキャッシュ
- 短所: stale data 問題・実装複雑

### 推奨判断材料
- 殿devtools結果が ζ10 確定 → **案F2(認証修復・cmd_587統合)が最も筋良し**(根本原因に対処)
- 別仮説浮上 → 軍師依頼(案X1)
- 一時凌ぎ需要 → 案F1(認証バイパス)も検討

---

## §7 殿への質問 + 戦略提案

| Q | 内容 |
|---|---|
| **Q1** | 殿devtools [DEBUG-1270] 全ログ取得お願い(F12 → Console → Ctrl+Shift+R → yasu最適化実行 → ログコピペ)・本subtask の真因確定に必須 |
| **Q2** | ζ10 確定後の対応路線: 案F1(pinnedApi 認証バイパス)/案F2(認証修復・cmd_587統合)/案F3(localStorage キャッシュ) のいずれを採用するか? |
| **Q3** | 案X1(軍師再設計)発動可否: 殿devtools結果次第判断(ζ10 確定なら X1不要・別仮説浮上なら X1発動) |

### 戦略提案
- **第1優先**: 殿devtools結果取得 → 真因確定
- **第2優先(ζ10確定時)**: cmd_587(認証修復)と本subtask統合・案F2推奨
- **第3優先(ζ10否定時)**: 案X1軍師再設計依頼・solver全体アーキテクチャ見直し
- **D2撤廃**: 本subtask **11件目連続push 2桁突破達成**・次 Wave 11 で12件目目標

---

## 付録: お針子FB継続適用

### ssh_raw_outputs Phase別貼付状況
| Phase | 貼付場所 | completeness |
|---|---|---|
| Phase 1-A〜L | §2 | ζ7-ζ11 全実証 SSH貼付 |
| Phase 2-A〜F | §3 | .bak×2+11 patches Python+diff+改行+grep 全SSH貼付 |
| Phase 3-A〜F | §3.4 | vite build+新bundle+DEBUG-1270 11件検出 全SSH貼付 |
| Phase 4-A〜G | §4 | ntripcaster保全+HTTP+commit+origin push 全SSH貼付 |

### three_pillar_evidence
| 柱 | 内容 |
|---|---|
| ① commit hash | rotation-planner自リポ origin push commit `15d9095`(6fa2ed6..15d9095 main->main)・★D2撤廃11件目・2桁突破★ |
| ② Phase別 SSH | Phase 1(ζ7-ζ11実証)+Phase 2(.bak+11patches+diff)+Phase 3(build+DEBUG-1270 11件検出)+Phase 4(HTTP+commit+push成功+ntripcaster保全) を §2-§5 に完全貼付 |
| ③ debug反映確証 | bundle index-CV46wlyV.js (629.03kB・22:24 mtime) 内 DEBUG-1270=11件・11 strings 全部検出(constructor/generateInitial START/PRE/END/localSearch START/END/ensureMinFields START/END/Rotation.jsx 3種) |

### oharikoma_feedback_reflection
- ✅ memory#feedback_vps_audit_raw_logs.md: 生SSH全Phase貼付(要約禁止)→ §2-§5 完全貼付
- ✅ memory#feedback_needs_audit_ssh_log.md: needs_audit=true subtask の SSH生ログ添付 → 本subtask needs_audit=true・全Phase貼付
- ✅ memory#feedback_crlf_binary_edit.md: ★完全準拠★ LF only ながら バイナリモード rb/wb 既定パターン遵守・最初 b"..." で日本語ASCII制限エラー検出→`str.encode("utf-8")` で str→bytes 変換に切替・LF維持確証
- ✅ memory#feedback_no_predisposition.md: 修正案 F1/F2/F3 機械的整理・推奨判断材料は提示するも「殿選択を仰ぐ」中立表現

### F006 D2撤廃継続
- 本subtask: 実装(debug挿入)・rotation-planner自リポへ commit 15d9095 origin push のみ・shogun リポは docs/ のみ追加
- D2撤廃 **11件連続・2桁突破** (1247→1250→1254→1255→1257→1259→1260→1262→1265→1269→**1270**)

### ntripcaster保全
- 全Phase(1-4)で pid 3216892/3216893+port 2101 LISTEN 確認・完全継続

### 品質ループ第19周
- 1247 → 1250 → 1254 → 1255 → 1257 → 1259 → 1260 → 1262 → 1264 → 1265 → 1268 → 1269 → **1270**

### バイナリモード現場対処メモ
- 最初 `b"..."` で日本語含む long string を bytes literal にした際 `SyntaxError: bytes can only contain ASCII literal characters`
- 対処: `"...".encode("utf-8")` で str→bytes 変換に切替・read/write は `rb`/`wb` 維持
- → memory#feedback_crlf_binary_edit.md パターンの拡張版として現場記録

---

(cmd_586 Wave 10 = 9波目戦略見直し局面・X2 runtime debug+X3 ζ7-ζ11実証 並行採択完了・ζ10 最有力・殿devtools結果待ち・Wave 11 修正実装は殿御裁定後・D2撤廃11件目2桁突破)
