# 2F合議トリガー設計メモ

> **作成**: subtask_1092 / cmd_497 Wave2  
> **参照**: agent-swarm/server/botsu/notify.py, docs/shogun/v4_three_story_architecture.md §3.4  
> **実装候補**: Option C（notify.py kenshu板ルーティング追加）

---

## 1. 現状の手動トリガーフロー vs 自動トリガーフロー図

### 現状（手動トリガー）

```
足軽が kenshu板にPOST
    │
    ▼
notify_post(board="kenshu", ...) 呼び出し
    │
    ▼ ← ここが未定義（elif分岐なし）
    ※ 何も起きない（通知ゼロ）
    │
    ▼
足軽が手動で tmux send-keys → 老中ペイン
    │
    ▼
老中が手動で 2Fメンバーに確認依頼
    │
    ▼
2F各員が手動でkenshu板を確認してレス
```

**問題点**: 足軽がsend-keysを忘れると合議が始まらない。
老中の手動転送が介在するため遅延・見落とし発生リスクあり。

### 自動トリガー（Option C 実装後）

```
足軽が kenshu板にPOST
    │
    ▼
notify_post(board="kenshu", author_id="ashigaru1", ...)
    │
    ├─[1F判定]──→ 2F全員(ohariko/gunshi/kanjou_ginmiyaku) + 老中 に自動通知
    │               └ tmux send-keys × 3ペイン（kanjou_ginmiyakuはNOTIFY_EXEC）
    │
2Fメンバーが kenshu板を確認してレス
    │
    ▼
notify_post(board="kenshu", author_id="ohariko", ...)
    │
    ├─[2F判定]──→ 老中のみ通知（循環防止）
    │
老中が kenshu_gate に検収判定POST
    │
    ▼
notify_post(board="kenshu_gate", author_id="roju", ...)
    │
    ├─[老中判定]──→ 足軽（結果通知）+ 2F（情報共有）
```

---

## 2. notify.py変更箇所の概要

### 変更ファイル

`agent-swarm/server/botsu/notify.py`

### 変更内容（差分概要）

`notify_post()` 関数に以下の2分岐を追加（約40行）:

```python
# notify_post() 内に追加
elif board == "kenshu":
    _notify_kenshu(thread_id, author_id, message)
elif board == "kenshu_gate":
    _notify_kenshu_gate(thread_id, author_id, message)
```

### 追加関数: `_notify_kenshu()`

```
通知先マッピング:
  author_id ∈ 1F(ashigaru1, ashigaru2, ...) → 2F全員 + 老中
  author_id ∈ 2F(ohariko, gunshi, kanjou_ginmiyaku) → 老中のみ
  author_id == "roju" → 2F全員（老中自身の投稿は2Fに共有）
```

### 追加関数: `_notify_kenshu_gate()`

```
通知先マッピング:
  author_id == "roju" → 足軽全員(PASS/FAIL結果通知) + 2F(情報共有)
  author_id ∈ 2F → 老中のみ（合議結果集約）
```

### 1F判定ロジック

```python
# 2Fメンバー集合（設計書 §3.1準拠）
F2_AGENTS = {"ohariko", "gunshi", "kanjou_ginmiyaku", "roju", "karo-roju"}

def _is_1f_agent(author_id: str) -> bool:
    """足軽/部屋子判定: 2F/3Fでなければ1F扱い。"""
    return author_id not in F2_AGENTS
```

---

## 3. 循環通知防止ルール

### 循環通知のリスク

kenshu板は全員書き込み可（`writers: null`）。
2Fがレスする→全員通知→再度2Fが通知を受け取る→無限ループ発生リスク。

### 防止ルール（author_id別ルーティング）

| 投稿者(author_id) | 板 | 通知先 | 除外理由 |
|------------------|----|-------|---------|
| 1F足軽 | kenshu | 2F全員 + 老中 | - |
| 2F(お針子/軍師/勘定) | kenshu | 老中のみ | 2F→2F通知で循環防止 |
| 老中 | kenshu | 2F全員 | 老中投稿は合議共有 |
| 老中 | kenshu_gate | 足軽全員 + 2F | 検収結果の全体共有 |
| 2F | kenshu_gate | 老中のみ | 2Fのkenshu_gate投稿は集約 |

### 実装上の注意

- `author_id` は `do_reply_add()` から渡される投稿者IDを使用（偽装不可）
- 自分自身への通知は除外: `if aid != author_id`（既存ロジックと同様）
- `kanjou_ginmiyaku` はペイン=nullのため `exec_notify()` 経由で通知

---

## 4. Phase 3への布石

### Phase 3の定義（v4設計書 §6より）

BBS納品成功率 ≥ 90% 達成時に移行。
Phase 3では **PDCA自動回転**を目指す: 

```
足軽が実装完了
    → kenshu板POST（自動）
    → 2F合議トリガー（notify.py Opt-C）
    → 合議結果 kenshu_gate POST（2F）
    → 老中が audit_records に記録 + YAML inbox更新
    → 次タスク自動割当（PDCA回転）
```

### 本実装（Option C）がPhase 3前提条件を満たす理由

1. **合議の自動発火**: kenshu POSTと同時に2Fが通知を受ける → 老中不要
2. **結果の自動伝達**: kenshu_gate POSTで足軽に自動フィードバック
3. **audit_records連携**: kenshu_gate POST後に `botsunichiroku.py audit add` を呼ぶことで
   DB記録も自動化可能（Phase 3拡張ポイント）

### Phase 3実装の残課題

- `_notify_kenshu_gate()` → `audit add` の自動呼び出し統合
- 差し戻し時の YAML inbox `status: blocked` 自動更新
- 2Fエージェントの非同期応答タイムアウト設計

---

## 5. ポーリング禁止(F004)への適合確認

### F004 ルール

> ポーリング禁止: `while True: sleep(X)` による状態確認は禁止。  
> イベント駆動（send-keys通知 + 受信側が起動時のみ確認）に徹せよ。

### Option C の F004 適合性

| 観点 | 評価 | 根拠 |
|-----|------|------|
| notify_post() の呼び出しタイミング | ✅ | 投稿イベント発火時のみ（`do_reply_add()` 内で同期呼び出し） |
| tmux send-keys 通知方式 | ✅ | push型通知。受信側はsend-keysで起動されるまで待機 |
| kanjou_ginmiyaku の exec_notify | ✅ | Popenで非同期起動。受信時のみ処理 |
| 2Fによる合議結果確認 | ✅ | send-keys通知で発火。ポーリング不要 |
| audit_records 更新タイミング | ✅ | kenshu_gate POST時に1回のみ実行 |

**結論**: Option C はすべてイベント駆動で設計可能。F004 違反なし。

### 注意点

`_notify_kenshu()` および `_notify_kenshu_gate()` は `notify_post()` から
同期的に呼ばれるため、実行時間が長くなると投稿レスポンスが遅延する可能性がある。
`send_keys()` は `timeout=3` で制御されており、tmux不応答時も3秒でタイムアウトする。
実用上の問題はない。

---

## 実装優先度

| タスク | 優先度 | 担当 |
|--------|:------:|------|
| `_notify_kenshu()` 追加 | **高** | 足軽（subtask_1092後継） |
| `_notify_kenshu_gate()` 追加 | **高** | 足軽 |
| `F2_AGENTS` 定数化 | **中** | 上記と同時 |
| audit add 自動呼び出し統合 | **低** | Phase 3で検討 |
