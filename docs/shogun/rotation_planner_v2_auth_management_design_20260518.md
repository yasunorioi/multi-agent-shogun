# rotation-planner v2: 認証情報管理整理 調査・設計報告書

**作成**: 2026-05-18 / 足軽1 (ashigaru1) / subtask_1266  
**対象**: `/var/www/rotation-planner-v2/app/data/rotation_planner.db` + auth.py + admin.py  
**目的**: ja_user is_active=0復活 + admin/ja_staff/yasu password hashリセット方針設計 (Playwright自動テスト基盤前提条件)

---

## §1 エグゼクティブサマリー

| 項目 | 状況 |
|------|------|
| ja_user is_active | **0 (ログイン不可)** → 復活要 |
| admin パスワード | **不明** (hash `961ef3bb8f...` → 広域照合100件超で特定失敗) |
| ja_staff パスワード | **不明** (admin と同一 hash) |
| yasu パスワード | **不明** (admin と同一 hash) |
| ja_user パスワード | **ja123** (hash照合で判明) |
| farmer1/farmer_demo | is_active=0・パスワード不明 (テスト不要) |

**必要な修正**: 2種類  
1. `ja_user` を `is_active=1` に復活 (SQLite UPDATE)  
2. `admin`/`ja_staff`/`yasu` を既知パスワード `admin123` にリセット (SQLite UPDATE)

---

## §2 Phase 1-2 生SSH出力全文

### Phase 1-A: users 全件

```
id|username|role|is_active|password_hash
1|admin|admin|1|961ef3bb8fa15690c1ac276db691a9aab83c68845c5b1c8373db268c34da0ef2
2|ja_user|ja_staff|0|8f2b253bd51b844d277795e6ab953a02aaa4f8d2860eed91f4e0065c42bc07a7
3|farmer1|farmer|0|f0645a6e48d17d05e04c1993f77cc15e0b1fb399a1fd137e9876d00c239b2b2c
4|ja_staff|ja_staff|1|961ef3bb8fa15690c1ac276db691a9aab83c68845c5b1c8373db268c34da0ef2
5|farmer_demo|farmer|0|d3ad9315b7be5dd53b31a273b3b3aba5defe700808305aa16a3062b76658a791
6|yasu|farmer|1|961ef3bb8fa15690c1ac276db691a9aab83c68845c5b1c8373db268c34da0ef2
```

### Phase 1-B: auth.py is_active / authenticate 参照

```
55: "SELECT id, username, password_hash, display_name, role, org_id, is_active "
56: "FROM users WHERE is_active = 1 ORDER BY id"
108: def hash_password(password: str) -> str:
118:     return hashlib.sha256(password.encode()).hexdigest()
125: def authenticate(username: str, password: str) -> bool:
141:     "SELECT id FROM users WHERE username = ? AND password_hash = ? AND is_active = 1",
```

**hash方式**: `hashlib.sha256(password.encode()).hexdigest()` — ソルトなし SHA256・64文字 hex

### Phase 1-D: UserRepository.authenticate 定義

```python
def authenticate(username: str, password_hash: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM users
            WHERE username = ? AND password_hash = ? AND is_active = 1
        """, (username, password_hash))
        return row_to_dict(cursor.fetchone())
```

**is_active=0 ユーザーは認証不可**: authenticate / login API 両方で `AND is_active = 1` 条件あり。

### Phase 2-B: 既知パスワード SHA256照合結果

```
admin123 => 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9
ja123    => 8f2b253bd51b844d277795e6ab953a02aaa4f8d2860eed91f4e0065c42bc07a7  ← ja_user と一致
```

`961ef3bb8fa15690c1ac276db691a9aab83c68845c5b1c8373db268c34da0ef2` (admin/ja_staff/yasu) は:
- 100件超の候補照合 (admin, admin123, password, rotation, planner, yasu, debian, webapp, sakura, 他) で **一致なし → パスワード不明**

### Phase 2-K: admin.py パスワードリセット API

```python
from rotation_planner.common import update_password
# ...
if user.password:
    update_password(username, user.password)
```

→ `/api/admin/users/{username}` 経由でパスワードリセット API が存在するが、**admin JWT が必要**。現状 admin パスワード不明のため API 経由は不可 → SQLite 直接操作が必要。

---

## §3 現状ユーザー構成と Playwright テスト用要件

### 現状

| id | username | role | is_active | パスワード | Playwright 用途 |
|----|---------|------|-----------|-----------|----------------|
| 1 | admin | admin | 1 | **不明** | admin機能テスト |
| 2 | ja_user | ja_staff | **0** | ja123 | JA staff テスト (is_active=0で不可) |
| 3 | farmer1 | farmer | 0 | 不明 | 不使用 |
| 4 | ja_staff | ja_staff | 1 | **不明** | JA staff テスト(代替候補) |
| 5 | farmer_demo | farmer | 0 | 不明 | 不使用 |
| 6 | yasu | farmer | 1 | **不明** | farmer テスト |

### Playwright テスト基盤に必要なユーザー

| username | role | 要求 |
|---------|------|------|
| admin | admin | is_active=1・既知PW必須 |
| ja_user or ja_staff | ja_staff | is_active=1・既知PW必須 |
| yasu (or farmer1) | farmer | is_active=1・既知PW必須 |

---

## §4 修正設計

### 4-1. ja_user is_active 復活 (SQLite UPDATE)

```sql
-- ja_user is_active=0 → 1 復活
UPDATE users SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE username='ja_user';
```

**確認**: `ja_user` パスワードは `ja123` (判明済) → 復活後すぐにログイン可能。

### 4-2. admin/ja_staff/yasu パスワードリセット (SQLite UPDATE)

```sql
-- admin123 のSHA256 hash
-- hashlib.sha256('admin123'.encode()).hexdigest() = 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9
UPDATE users
SET password_hash='240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
    updated_at=CURRENT_TIMESTAMP
WHERE username IN ('admin','ja_staff','yasu');
```

**根拠**: subtask_1242 で確認済みのハッシュ計算方式と一致 (`hashlib.sha256(password.encode()).hexdigest()`)。

### 4-3. 実装手順 (別 Wave で実施)

```bash
# VPS SSH
DB=/var/www/rotation-planner-v2/app/data/rotation_planner.db
sudo -u webapp sqlite3 "$DB" << 'EOSQL'
-- Step 1: ja_user 復活
UPDATE users SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE username='ja_user';

-- Step 2: admin/ja_staff/yasu PW リセット (admin123)
UPDATE users
SET password_hash='240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
    updated_at=CURRENT_TIMESTAMP
WHERE username IN ('admin','ja_staff','yasu');

-- Step 3: 確認
SELECT id, username, role, is_active, substr(password_hash,1,20) FROM users ORDER BY id;
EOSQL
```

### 4-4. 変更後のテスト用ユーザー構成

| username | role | is_active | password | Playwright 用途 |
|---------|------|-----------|---------|----------------|
| admin | admin | 1 | admin123 | admin機能・ユーザー管理テスト |
| ja_user | ja_staff | **1** | ja123 | JA staff テスト (旧パスワードで可) |
| ja_staff | ja_staff | 1 | admin123 | JA staff テスト (ja_user代替) |
| yasu | farmer | 1 | admin123 | farmer テスト |
| farmer1 | farmer | 0 | (不明) | 不使用 (is_active=0維持) |
| farmer_demo | farmer | 0 | (不明) | 不使用 (is_active=0維持) |

---

## §5 別 subtask 提案

```
cmd_587 Wave 2: 認証情報 DB 実装
- Phase 1: ja_user is_active=0 → 1 (SQLite UPDATE)
- Phase 2: admin/ja_staff/yasu password → admin123 (SQLite UPDATE)
- Phase 3: curl 4件検証 (admin/ja_user/ja_staff/yasu ログイン確認)
- needs_audit: true (生SSH全Phase貼付)
- 前提条件: 殿 §6 Q1-Q3 確認後実施
```

---

## §6 殿への質問

**Q1: ja_user パスワードを `ja123` のまま維持するか `admin123` に統一するか？**  
→ `ja_user/ja123` で is_active 復活のみでもテスト可能。統一する場合は `admin123` にリセット追加。Playwright テストコードの認証情報管理が簡素化される。

**Q2: farmer1/farmer_demo は is_active=0 のまま維持か？**  
→ Playwright テスト用途としては `yasu/admin123` (farmer role) があれば十分。farmer1/farmer_demo は不使用。ただし明示的に「維持」と確定させたい。

**Q3: `961ef3bb8f...` の旧パスワード(不明)について記録・追跡は必要か？**  
→ 100件以上の照合で特定失敗。このハッシュは上書きされるため、追跡不要であれば問題ない。もし「前のパスワードを残したい」なら別途調査が必要だが、Playwright テスト基盤の観点では既知 PW への置換で十分。

**Q4: Playwright テスト認証情報の管理方針は？**  
→ テスト用 `.env` または `playwright.config.ts` 内の環境変数に `TEST_ADMIN_USER=admin`, `TEST_ADMIN_PASS=admin123` 等を定義する方針でよいか確認されたい。

---

*報告者: 足軽1 (ashigaru1) / subtask_1266 / 2026-05-18*
