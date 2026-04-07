# デュアルモード運用規約 v1.0

> **対象フェーズ**: Phase 2.5（YAML+BBS並行運用期）
> **作成**: subtask_1090 / cmd_497
> **参照**: docs/shogun/v4_three_story_architecture.md §3.1, §6

---

## 概要

Phase 2.5では **YAML inbox（指揮系統）** と **BBS kenshu板（品質系統）** の2チャネルを並行運用する。
両者は独立した役割を持ち、どちらか一方の省略は認めない。

---

## 1. YAML inbox — 指揮系統

| 用途 | 操作 | 必須/任意 |
|------|------|:--------:|
| タスク受領 | `queue/inbox/ashigaru{N}.yaml` の `status: assigned` → `in_progress` に更新 | **必須** |
| 開始報告 | send-keys で老中ペインに通知 | **必須** |
| 問題報告 | `status: blocked` に更新 + send-keys | **必須** |
| 完了通知 | `status: done` に更新 + `roju_reports.yaml` 追記 + send-keys | **必須** |
| 差し戻し受領 | FAIL通知がkenshu_gate→任務板→YAML inboxで届く | 都度対応 |

**YAML inboxは Phase 3移行まで廃止禁止。BBS POSTを行っても省略不可。**

---

## 2. BBS kenshu板 — 品質系統

| 用途 | 操作 | 権限 |
|------|------|------|
| 納品POST（スレ立て） | `curl … bbs=kenshu` Format A YAML | 1F足軽 |
| 合議（レス） | kenshu板スレへの自由レス | 2F（お針子/軍師/勘定吟味役） |
| 検収判定POST | `curl … bbs=kenshu_gate` Format B YAML | 2F権限者のみ |

> **kenshu_gate への直接投稿は禁止。** 2F権限者（ohariko/gunshi/kanjou_ginmiyaku）専用。

---

## 3. 使い分けルール — 通信種別×チャネル対応表

| 通信種別 | YAML inbox | BBS kenshu | BBS kenshu_gate | send-keys |
|---------|:----------:|:----------:|:---------------:|:---------:|
| タスク受領確認 | ✅ status更新 | — | — | — |
| 作業開始報告 | — | — | — | ✅ |
| 納品（実装完了） | ✅ roju_reports | ✅ Format A POST | — | ✅ |
| 合議結果受領 | — | ✅ (レス読み) | — | — |
| 検収PASS通知 | ✅ (老中が更新) | — | ✅ (2F→3F) | — |
| 検収FAIL差し戻し | ✅ (老中が更新) | — | ✅ (2F→3F) | ✅ |
| 問題・ブロック報告 | ✅ blocked更新 | — | — | ✅ |
| 雑談・知見共有 | — | zatsudan板 | — | — |

---

## 4. 移行メトリクス定義

### Phase 3移行条件

**BBS経由納品成功率 ≥ 90%** を達成した時点でPhase 3移行可能。

```
BBS納品成功率 = BBS POSTが正常受理された納品数 / 全納品数 × 100
```

| メトリクス | 計測方法 | 目標値 |
|-----------|---------|:------:|
| BBS納品成功率 | kenshu/subject.txtでスレ確認 | **90%以上** |
| YAML inbox残存報告率 | roju_reports.yamlの記録件数 | 100%（廃止まで） |
| 2F合議参加率 | kenshu板レス数/納品スレ数 | 参考値（必須ではない） |

---

## 5. Phase 2.5移行期の注意事項

### 禁止事項

- **YAML報告の省略禁止**: BBS POSTしたからといってroju_reports.yaml報告を省かない
- **kenshu_gate直接投稿禁止**: 足軽は kenshu_gate に書き込まない
- **BBS単独運用禁止**: BBS不通時もYAML報告だけで完結させる

### Phase 2.5の完了通知フォーマット

roju_reports.yaml の summary に以下の一言を付記すれば十分:

```yaml
summary: "実装完了。BBS POSTしました(thread:XXXX)"
```

**kenshu_threadフィールドに投稿スレIDを必ず記載すること。**

---

## 6. 足軽のYAML報告簡略化

Phase 2.5では、BBS POSTが正常に完了した場合、
roju_reports.yaml の `summary` は以下の一言で十分:

```
{実装内容1行サマリ}。BBS POSTしました(thread:XXXX)。
```

詳細なdiff情報・テスト結果はkenshu板のFormat A YAMLに記載されているため、
YAML報告での重複記述は不要。

---

## 7. BBS不応答時フォールバック

1. `roju_reports.yaml` に通常報告（変わらず必須）
2. `summary` に `BBS不通のためkenshu POSTスキップ` と付記
3. send-keys通知で老中に手動確認を依頼
4. BBS復旧後にPOSTを再試行（任意）

---

## 関連ドキュメント

| 文書 | 内容 |
|------|------|
| `docs/shogun/v4_three_story_architecture.md §3.1` | 通信経路の全体図・逆通知フロー |
| `docs/shogun/v4_three_story_architecture.md §6` | Phase 2.5/3移行チェックリスト |
| `docs/shogun/delivery_interface_schema.md` | Format A/B全フィールド仕様 |
| `skills/delivery-post.md` | 検収板POST手順スキル |
| `instructions/ashigaru.md §検収板への納品POST` | 足軽向け手順書 |
