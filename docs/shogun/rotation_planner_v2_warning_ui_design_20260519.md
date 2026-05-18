# rotation-planner v2 γ警告UI改善 軍師L4-L6設計レポート (cmd_590 Wave 2)

| 項目 | 内容 |
|---|---|
| cmd / subtask | cmd_590 / subtask_1278 |
| 作成日 | 2026-05-19T01:35 |
| 作成者 | 軍師 (gunshi) |
| 前段 | subtask_1277 (Wave 1 read-only調査) 真因γ+ε複合確定・殿Q3=YES γ改善軍師依頼 |
| 殿明示 | **「予断与えず」** memory#feedback_no_predisposition.md 準拠・I3/I4 を予断ではなく前提情報として独立評価・代替案ありえる前提 |
| 監査対象 | origin/main HEAD `44e9304`(本日 01:28 取得)の frontend/app/src/pages/Rotation.jsx (680行) + lib/rotationSolver.js + App.css |
| Wave | 2 = 設計レポートのみ・実装は別Wave/別cmd起票後 |
| read-only | 完全可逆(コード変更なし) |
| 並行 | cmd_591 (OR-Tools 500緊急・殿運用ブロック寄り) と並行・本cmdは品質改善寄り |

---

## §1 エグゼクティブサマリ (殿レビュー用・30行以内厳守)

**結論3行:**
1. **軍師独立評価で 4案(I3/I4 + 軍師追加 I5/I6) を 7軸×重み100 で公平採点 → 案I4(警告UI固定表示)が単独評価で 73/100 最高得点**。理由: errors が **plain string** (rotationSolver.js L288/L382 で `errors.push("警告: ほ場${fieldId}の${year}...")`) で構造化されていないため、I3/I6 は errors 構造化を**前提依存**・即実装不可。
2. **段階提案 (cmd_577/cmd_584/cmd_589 方式踏襲):** **短期=I4 sticky警告UI + I5 違反件数バッジ**(errors string のままで即実装可・工数2-3時間)/ **中期=errors 構造化 + I3 summary-table セルハイライト**(rotationSolver.js 改修必要・1日工数)/ **長期=I6 クリック連動スクロール+ハイライト**(UX最高・但しI3完了が前提)。
3. **L6 構造的予防策**: (a) errors を `{type, field_id, year, crop, severity, message}` 構造化 schema 化・(b) `<WarningBar>` design-system component 化(全画面で一貫性確保)・(c) accessibility WCAG 2.1 AA 準拠(aria-live + role=alert + コントラスト 4.5:1 以上)。

**4案 加重スコア表 (重み計100点・各案0-10点採点)**

| 評価軸 | 重み | I3 ハイライト | **I4 固定表示 ★** | I5 件数バッジ | I6 連動 |
|---|:---:|:---:|:---:|:---:|:---:|
| (i) UX改善効果(殿視認性) | **25** | 9 (225) | 7 (175) | 6 (150) | 9 (225) |
| (ii) 工数(小≧) | 15 | 4 (60) | **9 (135)** | 8 (120) | 3 (45) |
| (iii) errors構造化無依存度 | 15 | 2 (30) | **9 (135)** | 7 (105) | 2 (30) |
| (iv) cmd_582 pending UI整合 | 10 | 6 (60) | 7 (70) | 7 (70) | 6 (60) |
| (v) お針子検出容易性 | 10 | **9 (90)** | 6 (60) | 7 (70) | **9 (90)** |
| (vi) accessibility (WCAG) | 10 | 7 (70) | 8 (80) | 6 (60) | 8 (80) |
| (vii) 将来制約追加自動連動 | 15 | 8 (120) | 5 (75) | 6 (90) | 8 (120) |
| **加重合計 (100点換算)** | 100 | **66** | **73 ★** | **67** | **65** |

**推奨: 段階提案 = 短期 I4+I5 / 中期 I3 / 長期 I6** (cmd_584/cmd_589 方式踏襲)。

**殿への質問3問:**
- **Q1':** 段階提案 採用(短期I4+I5 → 中期I3 → 長期I6) or 単発採用(I4のみ or I3のみ)?(軍師推奨=段階提案)
- **Q2':** **errors 構造化(JSON object化・rotationSolver.js 改修)を本cmd の中期スコープに含めるか?** (含めれば I3/I6 が中長期で実装可・含めなければ短期I4+I5 で完結)
- **Q3':** accessibility WCAG 2.1 AA 準拠(aria-live等)は本cmd で対応 or 別cmd起票?(殿の運用環境=PC/モバイル不明・軍師推奨=本cmd I4 段階で最小対応)

---

## §2 監査範囲 (read-only実証)

### §2.1 対象ファイル

| ファイル | 行数 | 関連箇所 |
|---|---|---|
| `frontend/app/src/pages/Rotation.jsx` | 680行 | L546-555 warnings UI / L591-622 rotation-table / L628-675 summary-table |
| `frontend/app/src/lib/rotationSolver.js` | 415+行 | L288/L382 errors.push (plain string) / L399 allErrors=[...errors, ...violations] |
| `frontend/app/src/App.css` | (多数行) | `.warnings`/`.warnings h4`/`.warnings ul` 定義あり・`.future-year`/`.past-year`/`.crop-cell` 定義あり |

### §2.2 三重突合根拠(お針子FB項目)

| 観点 | 根拠 |
|---|---|
| commit hash | origin/main HEAD `44e9304`(本日 01:28 取得・15d9095→44e9304 で 2 commits先行を pull) |
| Phase別SSH | 本subtaskはローカル `/tmp/rotation-planner-probe-v2` のみ・実機SSH無し(read-only分析がVPS実機状態と分離) |
| 三重突合 | (a) Rotation.jsx L628-675 で summary-table の td が `past-year`/`future-year` クラスのみで違反ハイライト無いことを直接読取 / (b) rotationSolver.js L288/L382 で errors が plain string で push されることを grep / (c) App.css に `.violation`/`.error-cell` 等の違反系クラスが grep で 0件 → I3 実装には CSS新規追加 + errors 構造化 + JSX 連動 の 3層が必要と確証 |

### §2.3 schema差異検出 何回目候補

- 本cmd_590 は API schema 監査(cmd_589)とは別系統 = **UI design 系の 1回目候補**(UI/UX 改善の構造的監査として独立)
- 但し errors 構造化は cmd_589 のパターンB(型不一致)系の予防策と相関 → 別cmd で統合検討余地

### §2.4 V4境界線(各案ごと)

| 案 | 戻せるか | V4自動運転可否 |
|---|:---:|:---:|
| I3 ハイライト(summary-table CSS+JSX) | ○ git revert可 | ✅ 自動運転可・但しerrors構造化前提 |
| **I4 固定表示(CSS sticky 1行)** | ○ git revert可 | ✅ 自動運転可・最も単純 |
| I5 件数バッジ(warnings h4 改修) | ○ git revert可 | ✅ 自動運転可 |
| I6 連動(JSX+state追加) | ○ git revert可 | ✅ 自動運転可・但しI3完了前提 |

---

## §3 γ真因 構造分析 (L4)

### §3.1 部屋子1 Wave1 確定済の真因(前提)

- **summary-table 描画 (Rotation.jsx L628-675) に違反ハイライトロジック完全欠如**
- 各 `td` は `past-year`/`future-year` クラス + 数値表示のみ
- **R9=17.0 薄赤は `.future-year` クラスの偶然反応**(本来 future-year は他の色を当てている設計のはずだが視覚的に赤系)
- **警告UI (`<div className='warnings'>` L547) は実装あり**で 7件の警告表示確認済(JS版動作中)・但し**通常フロー描画で画面スクロールに埋もれる**

### §3.2 errors data 形態(本subtask 追加調査)

```javascript
// rotationSolver.js L288 (generateInitialSolution)
this.errors.push(`警告: ほ場${this.fields[fieldIdx].fieldId}の${year}で制約を満たす作物がありません`);

// rotationSolver.js L382 (ensureMinFields)
this.errors.push(`警告: ${year}の${crop}最小ほ場数(${minF})を満たせません`);
```

→ **errors は plain string** ・field_id/year/crop/制約種別の構造化なし・I3/I6 で「該当セル特定」するには:
- **(option A)** 文字列パース (脆い・正規表現で year/field_id を抽出・将来エラーメッセージ変更でバグ)
- **(option B)** rotationSolver.js を改修して errors を **object 化** ★軍師推奨(中期 §6.1 予防策)

### §3.3 既存 CSS 資産

| クラス | 存在 | 用途 |
|---|:---:|---|
| `.warnings`(L547で使用) | ✅ App.css 定義あり | 警告コンテナ |
| `.warnings h4` / `.warnings ul` | ✅ | 内部スタイル |
| `.future-year` / `.past-year` | ✅ | 年セル背景色 |
| `.crop-cell.past` / `.future` | ✅ | 作物セル背景色 |
| `.violation` / `.error-cell` / `.warning-cell` | ❌ 0件 | I3 実装で新規追加要 |

→ **I3 実装には CSS新規追加 + errors 構造化 + JSX 連動 の 3層改修が必要**(工数3-5時間以上)。

### §3.4 各案の実装影響度

| 案 | 改修ファイル | 改修行数 | 前提依存 |
|---|---|---|---|
| I3 | App.css(新規 .violation-cell) + rotationSolver.js(errors 構造化) + Rotation.jsx(L647 各td className 拡張) | ~50行 | errors 構造化 |
| **I4** | App.css(`.warnings` に position:sticky + top:0 + z-index 追加・3行) + Rotation.jsx微調整 | ~5行 | なし(即実装可) |
| I5 | Rotation.jsx L548 `<h4>⚠️ 警告/違反 (${errors.length}件)</h4>` + 色付きバッジ | ~3行 | なし |
| I6 | Rotation.jsx state追加 + onClick handler + scrollIntoView() + Rotation.jsx L612/L647 className連動 | ~30行 | I3 完了 |

---

## §4 軍師独立 4案 評価(予断与えず厳守)

### §4.1 評価軸と重み (合計100点)

| 軸 | 重み | 説明 |
|---|:---:|---|
| (i) UX改善効果(殿視認性) | **25** | 最重要・殿が違反を見落とさない |
| (ii) 工数(小≧) | 15 | 実装+レビュー+テスト時間 |
| (iii) errors 構造化無依存度 | 15 | errors を JSON object 化せずに動くか |
| (iv) cmd_582 pending UI 整合 | 10 | cmd_582 のUI改修案Bと衝突しないか |
| (v) お針子検出容易性 | 10 | 視認性→監査スクリーンショットで違反が見えるか |
| (vi) accessibility (WCAG 2.1) | 10 | aria-live / コントラスト / role=alert |
| (vii) 将来制約追加自動連動 | 15 | rotationSolver の制約増えても UI 自動追従 |

### §4.2 4案の中身(軍師独立提案・I3/I4は部屋子1Wave1の参照案・I5/I6は軍師独自追加)

**案I3: summary-table セルに違反ハイライト追加 (部屋子1Wave1)**
- summary-table の年×作物セルで違反該当セルに `.violation-cell` (赤背景+赤枠)
- errors 構造化が前提(文字列パースは脆い)
- 工数: 半日(errors構造化込み)
- メリット: 直接「どこが違反か」見える・お針子も検出容易
- デメリット: 工数最大・rotationSolver.js 改修必要

**案I4: 警告UI 固定表示 (部屋子1Wave1) ★単独評価最高得点**
- `.warnings` に `position: sticky; top: 0; z-index: 10` 追加
- 結果セクションをスクロールしても warnings が画面上部に固定
- 工数: 30分(CSS 3行 + Rotation.jsx 微調整)
- メリット: 即実装可・errors 構造化不要・最小工数で UX 向上
- デメリット: ハイライトはせず・「どこが違反か」は文字で読む必要

**案I5: 違反集計サマリカウンタ (軍師独自追加)**
- `<h4>⚠️ 警告/違反 ({errors.length}件)</h4>` で件数を見出しに表示
- type ごとの集計バッジ(`制約違反: 5件 / 最小ほ場違反: 2件`)も検討可
- 工数: 1-2時間(string パースで type 集計)
- メリット: 警告の規模感が一目・I4と組合せで効果倍増
- デメリット: type 集計はパース依存・errors 構造化前で簡素

**案I6: クリック連動スクロール+ハイライト (軍師独自追加)**
- 警告リストの各 `<li>` クリック → 該当 summary-table セルへスクロール+一時ハイライト(2秒)
- 工数: 1日以上(I3 完了が前提)
- メリット: UX最高・MAGI 3家老的「警告→該当→アクション」の clean flow
- デメリット: I3 完了前提・工数大・全体構造の改修

### §4.3 加重スコア表 (0-10点採点 × 重み)

| 軸 | 重み | I3 | **I4 ★** | I5 | I6 |
|---|:---:|:---:|:---:|:---:|:---:|
| (i) UX改善効果 | 25 | 9 (225) | 7 (175) | 6 (150) | 9 (225) |
| (ii) 工数(小≧) | 15 | 4 (60) | **9 (135)** | 8 (120) | 3 (45) |
| (iii) errors構造化無依存度 | 15 | 2 (30) | **9 (135)** | 7 (105) | 2 (30) |
| (iv) cmd_582 整合 | 10 | 6 (60) | 7 (70) | 7 (70) | 6 (60) |
| (v) お針子検出 | 10 | 9 (90) | 6 (60) | 7 (70) | 9 (90) |
| (vi) accessibility | 10 | 7 (70) | 8 (80) | 6 (60) | 8 (80) |
| (vii) 将来制約自動連動 | 15 | 8 (120) | 5 (75) | 6 (90) | 8 (120) |
| **加重合計** | 100 | **65.5** | **73.0 ★** | **66.5** | **65.0** |

### §4.4 推奨と段階提案

**最高得点 (単独評価):** 案I4 (73/100)。理由:
- 工数(重み15) で 9点満点・即実装可
- errors 構造化無依存度(15) で 9点満点・rotationSolver.js 改修不要
- UX改善(25) は 7点でI3/I6より低いが、即効性が勝つ

**軍師独立判断 段階提案** (cmd_584/cmd_589 方式踏襲):

| フェーズ | 採用案 | 内容 | 期間 |
|---|---|---|---|
| **短期** | **I4 + I5** | 警告UI固定表示 + 件数バッジ・errors stringのまま即実装 | 2-3時間 |
| **中期** | I3 + errors構造化 | summary-table セルハイライト・errors を `{type, field_id, year, crop, severity, message}` 化 | 1-2日 |
| **長期** | I6 | クリック連動スクロール+一時ハイライト | 1日以上(I3完了後) |

### §4.5 dissent (推奨案I4の最大リスク)

- **I4 最大リスク:** 「警告UIが画面上部に固定で常時表示される圧迫感」(殿が結果テーブルに集中したい時に邪魔)
- **緩和:** `<button>閉じる</button>` で警告UI を一時最小化可・初期状態は展開・閉じても件数バッジ(I5)で件数は見える
- **撤回条件:** 殿が短期実装後に「邪魔」と判断した場合 → I4 から I3 直行に変更可(段階提案の柔軟性)

---

## §5 cmd_582 pending UI改修との整合性確認

### §5.1 cmd_582 概要 (軍師が把握する範囲)

- cmd_584 §5.4 で「cmd_582 (UI改修案B pending) との整合性 → 別subtask再評価推奨」と既記録
- cmd_582 の詳細設計書を軍師は未読 → 本subtaskでも同様に「衝突可能性あり」を明示
- 想定衝突点: Rotation.jsx の同一画面・同一ファイルを編集 → git merge 衝突リスク

### §5.2 緩和策

- 本cmd_590 Wave 3 (実装フェーズ) 着手前に **cmd_582 設計書をレビュー+統合実装プラン**を軍師再設計する**別subtask 起票推奨**(cmd_584 §5.4 と同じパターン)
- I4 は CSS 3行+JSX 微調整なので衝突しても resolve 容易
- I3/I6 は JSX 構造大改修・cmd_582 と本cmd の優先順位を明示する必要

---

## §6 L6 構造的予防策

### §6.1 予防策(a) errors 構造化 schema 化

```javascript
// rotationSolver.js 改修案
// 旧:
this.errors.push(`警告: ほ場${fieldId}の${year}で制約を満たす作物がありません`);

// 新:
this.errors.push({
  type: "no_valid_crop",        // 制約種別
  severity: "warning",           // warning | error | info
  field_id: fieldId,
  field_code: this.fields[fieldIdx].fieldCode,
  year: year,
  crop: null,                    // 該当作物(なければnull)
  message: `警告: ほ場${fieldId}の${year}で制約を満たす作物がありません`,
});
```

**効果:**
- I3/I6 が「該当セル特定」を構造化フィールド経由で実現
- 文字列パース脆性を排除
- 将来の制約追加(min_gap_years/cap_ha違反等)で type 追加だけで UI 自動連動
- お針子監査もtype別件数を構造化集計可

**工数:** rotationSolver.js 改修 (errors push箇所 2-5箇所) + Rotation.jsx errors.message 表示への変更 (1行) = **半日**。

### §6.2 予防策(b) `<WarningBar>` design-system component 化

```jsx
// frontend/app/src/components/WarningBar.jsx (新規)
export function WarningBar({ warnings, position = "sticky", onClick }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div className="warning-bar" style={{ position }}>
      <h4>
        <span aria-live="polite" role="alert">
          ⚠️ 警告/違反 ({warnings.length}件)
        </span>
      </h4>
      <ul>
        {warnings.map((w, i) => (
          <li key={i} onClick={() => onClick?.(w)}>
            {typeof w === "string" ? w : w.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

**効果:**
- 全画面で警告UI 一貫性確保(Rotation.jsx 以外でも再利用可・例: ほ場登録時の警告・農薬発注時の警告)
- I4/I5/I6 を component prop で切替(position="sticky" でI4・onClick でI6)
- accessibility(`aria-live` + `role=alert`)を component で強制

### §6.3 予防策(c) WCAG 2.1 AA 準拠

- **コントラスト比 4.5:1 以上**: 警告バー背景色 #FFF3CD vs テキスト #856404 (現状未確認・別cmd検証)
- **aria-live="polite"**: 動的に追加される警告を screen reader が読み上げ
- **role="alert"**: 緊急性の高い警告は role=alert で割込み読み上げ
- **キーボード操作**: I6 クリック連動はキーボードナビゲーションも対応(tabindex=0 + Enter キー)

**工数:** I4 段階で **30分以内**で最小対応可能(`aria-live` + 既存色のコントラスト計測)。

### §6.4 予防策の優先順位

| 優先 | 予防策 | 工数 | 効果 |
|---|---|---|---|
| **1位** | **(b) `<WarningBar>` component化** | 1-2時間 | I4/I5/I6 を component prop で柔軟切替・将来再利用 |
| 2位 | (a) errors 構造化 | 半日 | I3/I6 の前提・文字列パース脆性排除 |
| 3位 | (c) WCAG 2.1 AA | 30分(I4段階)・1日(完全対応) | accessibility 法的要件(将来) |

---

## §7 殿への質問 (3問以内・軍師独立判断)

### Q1' 段階提案 採用 or 単発採用

| 選択肢 | 内容 | 軍師評価 |
|---|---|---|
| (a) 段階提案(短期I4+I5 → 中期I3 → 長期I6) | UX最高・予防効果も得る・期間長め | ★軍師推奨 |
| (b) 単発 I4 のみ | 工数最小・errors構造化不要・即実装可 | UX中程度・将来I3に進めるか不明 |
| (c) 単発 I3 のみ | UX高い・但しerrors構造化必要・工数大 | 短期で完成・中長期改修なし |
| (d) その他 | (軍師が想定外の組合せ・殿判断) | - |

### Q2' errors 構造化(rotationSolver.js 改修)スコープ

| 選択肢 | 内容 |
|---|---|
| **(a) 本cmd 中期スコープに含める ★推奨(段階提案採用時)** | I3/I6 実装の前提として errors object化を Wave 3-4 で実装 |
| (b) 別cmd 起票 | errors 構造化は独立 cmd・本cmdは I4+I5 で完結 |
| (c) 含めない(I3/I6 は文字列パースで実装) | 脆性高い・将来 errors メッセージ変更でバグリスク・軍師非推奨 |

### Q3' accessibility WCAG 2.1 AA 準拠

| 選択肢 | 内容 |
|---|---|
| **(a) 本cmd で最小対応(aria-live + コントラスト確認・30分) ★軍師推奨** | I4 実装と同時に最小限の accessibility 確保 |
| (b) 別cmd 起票 (完全対応・1日) | 完全準拠は別cmd・本cmd は機能優先 |
| (c) 後日判断 | accessibility 対応なし・将来法的要件で再検討 |

---

## 付録A. お針子FB項目(全項目応答)

| FB項目 | 応答 |
|---|---|
| ssh_raw_outputs Phase別 | 本subtaskはローカル `/tmp/rotation-planner-probe-v2` のみ・実機SSH無し。Phase=(1) git fetch+pull / (2) Rotation.jsx grep+read / (3) rotationSolver.js errors.push grep / (4) App.css 既存class grep / (5) 4案 weighted scoring / (6) レポート執筆。全 read-only。 |
| three_pillar_evidence | (a) commit hash `44e9304` (origin/main HEAD 01:28 取得) / (b) Phase別grep出力で Rotation.jsx L628-675 td className= `past-year`/`future-year`のみ・違反系クラス無し / (c) App.cssに `.violation`/`.error-cell`/`.warning-cell` 0件grep + rotationSolver.js errors.push が plain string であることを三重突合 |
| schema差異検出 何回目候補 | **UI design 系 1回目候補**(cmd_589 までの API schema 監査とは別系統・errors 構造化は将来 cmd_589 のパターンB と統合検討余地) |
| V4境界線「戻せるか」判定 | 本subtask=read-only完全可逆 / I3=✅自動運転可(CSS+JSX・revert可・但しerrors構造化先行必要) / I4=✅自動運転可(CSS 3行・最も単純・revert容易) / I5=✅自動運転可(JSX 3行) / I6=✅自動運転可(I3 完了前提・JSX 30行) |

## 付録B. simplicity check 3問

| # | 問い | 回答 |
|---|------|------|
| 1 | この設計は、もっと少ないステップで達成できないか? | 本subtask は 4案評価+段階提案(短中長)で**過剰でも過小でもない**。単発採用(I4のみ)で済ますなら短期解で済むが、UX改善効果が中程度に留まる・段階提案を選好。 |
| 2 | 軍師追加の I5/I6 は過剰追加ではないか? | I5(件数バッジ)はI4と組合せで効果倍増・1-2時間と軽量・**残す**。I6 はI3 完了前提で長期で別cmd判断可・**段階提案の長期で記述・本cmdスコープ外**にdowngrade。 |
| 3 | 殿質問は最小限か? | Q1'(方針)/Q2'(errors構造化)/Q3'(accessibility) の 3問のみ・各推奨明示・殿の判断ボトルネック最小化。 |

## 付録C. unknown_unknowns (8項目・10未満で可)

1. **cmd_582 pending UI改修案B の詳細未読** → 本cmd Wave 3 着手前に統合実装プラン軍師再設計が必要(cmd_584 §5.4 と同パターン)
2. **errors 文字列パターンが将来変更**された場合の I5 件数バッジ集計の脆性 → 予防策(a) errors 構造化で根本解決
3. **summary-table の violationセル**= 「年×crop の cell が複数違反に該当する」ケース(min_fields+forbidden_transition で重複)→ I3 設計時に severity 優先順位(error > warning > info)が必要
4. **Mobile UX**: I4 sticky で画面狭いモバイル端末では本体テーブルの可視領域が更に狭まる → max-height: 30vh + collapse ボタンで緩和(本書 §4.5 dissent と同種)
5. **rotation-table (L591-622) も同様の違反ハイライトが必要か?** → 本cmd は summary-table 限定だが、殿の運用次第で rotation-table へも展開要望ありえる(別cmd判断)
6. **国際化 i18n**: 警告メッセージが現状 日本語 hardcoded → 将来 英語対応時に errors 構造化の `i18n_key` フィールド追加が必要
7. **エラーログ蓄積**: フロントエンド errors を バックエンドにログ送信(audit_log)する設計が将来必要 → 本cmdスコープ外
8. **テスト戦略**: I3/I4 の e2e テスト(Playwright等)を別cmd起票するか → cmd_589 §6.2 pytest CI smoke-test と同種の構造的予防策

## 付録D. north_star_alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    rotation-planner = 「農家を雑な事務作業から解放する道具」(殿memory)。
    現状=γ警告が summary-table で視認不可(R9=17.0 薄赤は偶然反応)・warnings UIも埋もれて読まれない。
    本設計で I4 sticky + I5 件数バッジ + 中長期で I3 summary-tableハイライト → 殿が違反を一目で把握。
  risks_to_north_star:
    - "I4 単発で終わる病(段階提案を発動しない場合・UX改善が中途半端) → Q1' で段階提案 採用推奨"
    - "errors 構造化を別cmd分離で実装遅延 → Q2' 本cmdスコープ採用推奨"
    - "cmd_582 UI改修との衝突 → 別subtask統合プラン再設計推奨"
    - "rotation-tableへの展開要望 → 本cmd 完了後の殿フィードバックで別cmd判断"
    - "accessibility未対応で将来法的要件 → Q3' 最小対応推奨"
```

---

(本書 EOF)
