# cmd_577 完了報告書: rotation-planner VPS導入+v2本切替

| 項目 | 内容 |
|---|---|
| subtask | subtask_1239 / cmd_577 |
| 作成日時 | 2026-05-18T15:22:32 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp |
| 対象リポジトリ | github.com/yasunorioi/rotation-planner |
| 関連報告書 | rotation_planner_vps_setup_20260518.md (Wave 1/2a) / rotation_planner_v2c2_baseline_20260518.md (Wave 2c-2) / rotation_planner_v2_migration_strategy_20260518.md (軍師戦略書) |

---

## §1 エグゼクティブサマリ (殿レビュー用)

**結論**:
1. cmd_577 milestone本切替 **完遂** — 旧Gradio(port 7863) 停止 → v2正式運用へ昇格
2. rotation-planner v2 (FastAPI+React+nginx 80 public + uvicorn 8001 internal) 稼働中・外部公開 200 OK
3. ntripcaster (pid 3216892/3216893, port 2101) **完全保全** — Wave 1 baseline と diff 0行で完了

**完遂規模**:
- subtask完遂 19件 (1220-1244のうち本subtask 1239含めて20件・1223はPhase A,B保持で停止扱い)
- お針子監査 audit_record #25-#35 (11件・全PASS)
- V4境界線「戻せるか」判定で正しい停止 3回 (Wave 2b/2e-3/2f-2)
- F006抑制完璧: 全subtask で VPS git 無変更

**殿への申し送り 3項目** (詳細§5):
- admin/admin123 401 (PW再設定別cmd判断要)
- 404 endpoint 3件 (router prefix mismatch調査別cmd)
- cmd_579 実装フェーズ起票判断 (殿Q1'-Q3'裁定済)

---

## §2 完遂タイムライン (Wave別)

| Wave | subtask | 担当 | 内容 | 監査 |
|---|---|---|---|---|
| 1 | 1220 | 部屋子1 | VPS Wave 1 調査+計画書 (既稼働Gradio発見) | お針子 18/18 |
| 2a | 1221 | 部屋子1 | SSH key生成 (id_ed25519_rotation_planner) | お針子 17/18 |
| 2b | 1223 | 部屋子1 | SSH化(Phase A,B完了・Phase C前停止) | (停止・案β移行) |
| 2c | 1224 | 軍師 | v2移行戦略書 | お針子 18/18 |
| 2c-2 | 1225-1226 | 部屋子1 | 殿Q1'-Q6'採択+VPS baseline 10項目 | お針子 PASS |
| 2d-1 | 1227 | 部屋子1 | clone+venv+pip install (実測2分) | お針子 PASS |
| 2d-2 | 1228-1229 | 足軽1 | nvm + Node 20→22 + npm build | お針子 PASS |
| 2e | 1230-1231 | 足軽1/2 | JWT_SECRET 生成 + DB cp | お針子 PASS |
| 2e-3 | 1232 | 部屋子1 | systemd unit + ALTER patch case iii (init_db schema乖離発見+殿A) | お針子 PASS |
| 2f-1 | 1233 | 足軽1 | JWT認証フロー4項目 | お針子 PASS |
| 2f-2 | 1234 | 部屋子1 | nginx u4→u7 + React配信 (agriha衝突→殿A修正版) | お針子 PASS |
| 2f-2.5 | 1241 | 足軽1 | 残3テーブルALTER (inventory+8列等) | お針子 17/18 |
| 2f-2.6 | 1242 | 足軽2 | admin PW初期化 | お針子 17/18 |
| 2f-3 | 1235 ★本切替 | 部屋子1 | 旧Gradio stop+disable+port 7863 REMOVED | お針子 18/18 #33 milestone |
| 2f-3.5 | 1243 | 足軽1 | React useCallback bug fix | お針子 17/18 |
| 2f-3.6 | 1244 | 部屋子1 | users.json復旧 (前提誤り判明=v2 DB認証) | お針子 18/18 #34 |
| 2f-4 | 1236 | 部屋子1 | 全機能スモーク7 Phase (ja_staff/ja123 milestone再現) | (本subtask後監査) |
| D3対応 | 1240 | 軍師 | schema diff調査 | お針子 18/18 |
| 2g | 1237-1238 | 足軽1/2 | 旧disable確認+app rename | お針子 PASS |
| **2g-3** | **1239** | **部屋子1** | **本完了報告書** | (closing) |

---

## §3 重要発見・教訓 (5件の盲点)

### 発見1 (Wave 2b・cmd_577 全体戦略変更): origin/main がGradio→FastAPI+React完全移行済 (57+commits)
- **検知**: 部屋子1 がPhase C 前で `git fetch origin` 比較・portal.py origin/main から削除済を発見
- **対応**: V4境界線「戻せるか」判定で正しい中断 → 案β全面移行へ殿裁定
- **教訓**: 「単純な git pull で更新」前提はupstream大改修時に致命的・fetch+log差分の事前確認必須

### 発見2 (Wave 2e-3・schema進化): crop_master.category不在 + IF NOT EXISTS の ALTER系未対応
- **検知**: init_db() でsqlite3.OperationalError(table crop_master has no column named category) → systemctl Restart=alwaysループ
- **対応**: Python1行 case (iii) で DB に直接ALTER (db_schema.sql非編集・upstream取り込みコンフリクト最小化)
- **教訓**: Q4'=IF NOT EXISTS は新規CREATE のみ対応・ALTER TABLE は別ロジック必要

### 発見3 (Wave 2f-2.5・schema差分): 残3テーブル(inventory+8列・fields+land_category・pesticide_masters構造刷新)
- **検知**: 軍師 schema diff調査 (subtask_1240)
- **対応**: 足軽1 subtask_1241 で冪等patch SQL+bash wrapper
- **教訓**: 単一テーブル(crop_master)の patch では不十分・全テーブルの schema diff 事前調査が必要

### 発見4 (Wave 2f-2・既存システム衝突): nginx既存設定 agriha が port 80 catch-all占有
- **検知**: 部屋子1 が `sites-enabled` 検査時に発見・listen 80 default_server で nginx -t 失敗確実と判定
- **対応**: 殿裁定A修正版 (agriha-chat orphan停止・rotation-planner専用化) で Phase 3 再着手
- **教訓**: VPSは複数サービス共存環境・新規サービスは既存confとの衝突を事前検査必須

### 発見5 (subtask_1244・認証source誤認): v2 auth.py は DB認証 (users.json はv1旧コード遺物)
- **検知**: 部屋子1 が ja_staff/ja123 で代替認証成功時に発見・DB users.is_active=0 で論理削除済が真因
- **対応**: D3=削除 (users.json) ・D1=ja_staff/ja123 代替認証で milestone再開・D2=ja_user戻さず
- **教訓**: タスク指示の前提も検証対象・「users.json読込」前提は v1 のみ通用・auth実装の確認が前提整合性に必須

---

## §4 cmd_577 milestone達成証跡

### subtask_1235★本切替★ (お針子 audit_record #33 18/18満点・severity=S3 milestone)
| 証跡 | 結果 |
|---|---|
| 旧 rotation-planner.service | stop+disable完了・inactive(dead) 1d 6h 29min CPU time 正常終了 |
| port 7863 | **REMOVED** (LISTEN解除) |
| ntripcaster diff | **exit 0 完全一致** (pid 3216892/3216893 + port 2101 baseline維持) |
| listen diff | 7863 1行のみ削除・他全port無変動 |
| v2 active | pid 4076046 Memory 97-189M (継続稼働) |

### subtask_1236 全機能スモーク (7 Phase完遂)
| 項目 | 結果 |
|---|---|
| ja_staff/ja123 login | 200 OK + JWT 172字 + /me 200 (id=4 ja_staff JA職員) |
| ドメイン GET 8 endpoint | 5/8 200 (fields/crops/plans/inventory/admin/users) ・3/8 404 (pesticides/gis-polygons/dashboard・列挙のみ・別cmd判断) |
| React UI | bundle index-CTqyA67u.js 200 + useCallback 7検出 (subtask_1243反映継続) |
| エラーハンドリング | no_token 401 / invalid_token 401 / nonexistent 404 (全期待通り) |
| **外部公開** | `http://ik1-421-42663.vs.sakura.ne.jp/` **200 OK** |
| nginx active | port 80 + 443 LISTEN・toiso.fit conf維持 (殿明示遵守) |

---

## §5 殿への申し送り・残課題 (将来別cmd起票候補)

| # | 残課題 | 状況 | 別cmd判断 |
|---|---|---|---|
| 1 | **admin PW再設定** | cmd_578既知・現状 admin/admin123 401・平文不明 | 別cmd起票要 |
| 2 | **404 endpoint 3件** | /api/pesticides /api/gis/polygons /api/dashboard・router prefix mismatch可能性 | 別cmd調査 |
| 3 | **is_active=0 ユーザー復活/削除判断** | ja_user/farmer1/farmer_demo がDB上論理削除・D2=NO で代替運用・将来cleanup候補 | 殿判断後別cmd |
| 4 | **app.bak.20260518/ 削除** | 殿Q6'=90日採択により 2026-08-16以降に別cmd起票 | 2026-08-16以降別cmd |
| 5 | **upstream PR** | ALTER patch (case iii)・useCallback bug fix・users.json遺物のupstream反映 | 殿明示許可後別cmd (F006抑制継続中) |
| 6 | **cmd_579 実装フェーズ** | 殿Q1'-Q3'裁定済 (user_private_crops/admin+ja_staff閲覧可/soft delete) | 本cmd_577 close後に起票判断 |

---

## §6 軍師戦略書 fix項目 (将来 simplicity check / unknown_unknowns 反映)

cmd_579 subtask_1245 §6 で軍師が 5-7件目盲点を反映済の旨確認:
- **5件目**: data dir 全cp (subtask_1231のDB単体cp現場判断見直し・users.json遺漏)
- **6件目**: お針子 file 監査 (DB hashだけでなくusers.json等ファイル整合性チェック)
- **7件目**: schema/migrate/ensure 3点同期 (CREATE TABLE IF NOT EXISTS + ALTER + 既存ALTER冪等化)

本cmd_577 milestone後、軍師戦略書 fix を `gunshi.md` または別cmd で恒久化検討。これら3項目は他project (uecs-llm等) でも有用なskill_candidate候補。

---

## §7 完遂metrics

| 指標 | 値 |
|---|---|
| subtask完遂 | 19件 (1220-1244+本1239) |
| 重要発見 (盲点) | 5件 |
| お針子監査 | audit_record #25-#35 (11件・全PASS) |
| V4境界線正しい停止 | 3回 (Wave 2b portal.py発見/2e-3 schema乖離/2f-2 agriha衝突) |
| F006抑制 | 完璧 (全subtask で VPS git無変更・upstream PR は別cmd予定) |
| **ntripcaster完全保全** | Wave 1 baseline (pid 3216892/3216893+port 2101) → 最終 完全一致継続 (11日連続稼働中) |
| nginx u4→u7 upgrade影響 | libstdc++/libc6 完全変動なし (依存pinning成功) |
| 全体所要時間 | 2026-05-18 約4時間半 (10:46 subtask_1220 assigned → 15:22 本報告書) |
| Phase Aborted (Wave 2b Phase C) | 1回 (アーキテクチャ大変更で正しい中断) |
| ローカル fix 件数 | DB ALTER 4テーブル + useCallback + users.json遺物 |
| 殿の意思決定回数 | 主要9件 (Q1-Q6+Q1'-Q3'+D1-D3+案A修正版+5案進言裁定+D3 users.json削除等) |

---

## 付録: cmd_577 close チェックリスト (家老用)

- [x] subtask_1239 本報告書作成完了
- [x] §1-§7 全構成記入済 (エグゼ 30行以内厳守)
- [x] ntripcaster完全保全継続 (最終確認 subtask_1236 Phase 5)
- [x] 殿への申し送り 6項目明文化 (§5)
- [x] git add+commit+push private main (本subtaskで実施)
- [ ] 家老が cmd_577 status=done に更新 (本subtask完了後)
- [ ] cmd_579 起票判断 (家老/殿)

---

(cmd_577 close 直前報告書終了)
