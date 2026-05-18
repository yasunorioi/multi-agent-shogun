# rotation-planner VPS導入 セットアップ計画書 (Wave 1)

| 項目 | 内容 |
|---|---|
| subtask | subtask_1220 / cmd_577 |
| 作成日 | 2026-05-18 |
| 作成者 | 部屋子1 (ashigaru6) |
| 対象VPS | ik1-421-42663.vs.sakura.ne.jp (debianユーザー) |
| 対象リポジトリ | https://github.com/yasunorioi/rotation-planner |
| Wave | 1 (調査+計画書のみ・実装禁止) |
| ntripcaster | 稼働中・ノータッチ厳守 |

---

## 🔴 エグゼクティブサマリ (最重要)

**`rotation-planner` は既にVPSで稼働中である。**

- systemd unit `rotation-planner.service` (active running)
- 配置 `/var/www/rotation-planner/app/` (webappユーザー所有)
- Port 7863 (Gradioアプリ) でlisten中
- 起動コマンド `/var/www/rotation-planner/app/venv/bin/python portal.py`

ゆえに本タスクの「VPS導入」は **新規セットアップではなく、(a)既存版の更新/再構築 (b)別インスタンス追設 (c)現状確認のみ — のいずれか** である可能性が高い。Wave 2着手前に殿に意図確認が必要(§6 Q1)。

---

## §1 リポジトリ調査結果

### 言語/フレームワーク
- **メイン**: Python 3.x + Gradio (Webポータル `portal.py`)
- **代替起動**: FastAPI (`api/main.py`) + React (`frontend/app/`, npm) — `start-dev.sh` で起動するdev構成
- **デモ版**: Hugging Face Spaces (`deploy_demo.sh`) — VPS無関係

### 起動方式 (3パターン併存)
| 起動方式 | コマンド | 用途 | ポート |
|---|---|---|---|
| VPS本番 | `python portal.py` (Gradioポータル) | VPS常駐 | 7863 |
| 開発 | `bash start-dev.sh` | ローカル開発 | 8000 (API) + 5173 (React) |
| デモ | `bash deploy_demo.sh` | HF Spaces配信 | (HF側) |

### 依存
**origin/main `requirements.txt`** (8件):
```
pandas>=2.0.0, numpy>=1.24.0, ortools>=9.0,
shapely>=2.0.0, pyproj>=3.0.0, requests>=2.28.0,
reportlab>=4.0.0, python-multipart>=0.0.6
```

**VPS実体 `/var/www/rotation-planner/app/requirements.txt`** (8件・差分あり):
```
gradio>=4.0.0    ← origin/mainに無い
pandas>=2.0.0, numpy>=1.24.0, ortools>=9.0,
shapely>=2.0.0, pyproj>=3.0.0, requests>=2.28.0,
reportlab>=4.0.0
                ← python-multipart 無し
```

⚠️ **差分**: VPS版はgradio追加・python-multipart削除。push漏れ or 別管理(§6 Q2)。

### Python版数要件
- 明示なし。VPS既稼働実績から Python 3.11 系で動作OK
- VPS既設 venv は Python 3.11.2 (Debian 12 system Python)

### 主要ファイル
- `portal.py` (37KB) — Gradioポータル本体 (VPS稼働分)
- `admin_ui.py` (25KB)、`pesticide_master_ui.py` (14KB)
- `api/main.py` — FastAPIエントリ
- `frontend/app/` — React SPA
- `db_schema.sql` (24KB) — SQLite schema
- `rotation_planner/` — ドメインロジック(CP-SAT optimizer等)

### ブランチ
- `main` (HEAD VPS = `3c72c7a`)
- `feature/multi-farmer` (remote only、未使用)

---

## §2 VPS現状 (read-only baseline)

### OS / Runtime
| 項目 | 値 |
|---|---|
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | 6.1.0-42-amd64 |
| Python | 3.11.2 (system) |
| Node | **未インストール** |
| npm | **未インストール** |
| Docker | active running (containerd含む) |
| 空き容量 | `/` = 25G中 8.8G使用、15G空き (38%) |

### 既存稼働サービス (systemctl --type=service --state=running)
| サービス | 説明 | 関連ポート |
|---|---|---|
| **rotation-planner.service** | Rotation Planner Gradio App (User=webapp) | **7863** ← 既に稼働中 |
| agriha-linebot.service | LINE Bot (FastAPI/uvicorn, User=www-data) | 8443 (127.0.0.1) |
| docker.service / containerd.service | コンテナ基盤 | — |
| ssh.service | SSH | 22 |
| cron / dbus / snapd / systemd-* | OS標準 | — |

### TCP listen baseline (sudo ss -tlnp、★Wave 2比較用に保存)
```
LISTEN 0.0.0.0:22         sshd(pid=586)
LISTEN 0.0.0.0:2101       ntripcaster(pid=3216893)    ★保護対象
LISTEN 127.0.0.1:8443     uvicorn(pid=671)            agriha-linebot
LISTEN 0.0.0.0:7863       python(pid=555)             rotation-planner (稼働中!)
LISTEN [::]:22            sshd(pid=586)
```

### UDP listen baseline
```
UNCONN 0.0.0.0:41751
UNCONN [::]:41751
```

### Python版数
`Python 3.11.2`

---

## §3 セットアップ手順案 (Wave 2で実行する内容)

**前提**: §6 Q1 を殿が回答してから Wave 2 起票。シナリオ別に分岐:

### Scenario A: 「既存版をorigin/main最新へ更新」(最有力候補)
```bash
# 1. ntripcaster影響なし確認 (Wave 2冒頭)
ssh debian@ik1-421-42663.vs.sakura.ne.jp \
  'ps -ef | grep -E "ntrip|caster" | grep -v grep'   # baselineと一致確認

# 2. 既存サービス停止 (殿承認後のみ)
sudo systemctl stop rotation-planner.service

# 3. backup
sudo -u webapp cp -r /var/www/rotation-planner/app \
  /var/www/rotation-planner/app.bak.$(date +%Y%m%d)

# 4. git pull (作業ディレクトリ未コミット data/settings.json は要退避)
cd /var/www/rotation-planner/app
sudo -u webapp git stash         # settings.json退避
sudo -u webapp git pull origin main
sudo -u webapp git stash pop

# 5. 依存更新 (venv内)
sudo -u webapp venv/bin/pip install -r requirements.txt

# 6. 起動再開
sudo systemctl start rotation-planner.service
sudo systemctl status rotation-planner.service

# 7. ポート確認
sudo ss -tlnp | grep 7863

# 8. ntripcaster影響再確認
sudo ss -tlnp | grep 2101    # ntripcaster 健在確認
ps -ef | grep -E "ntrip|caster" | grep -v grep  # baselineと一致確認
```

### Scenario B: 「別ポートで別インスタンス追設」
- 空きポート例: 7864, 7865, 8080 (8443=linebot占有、2101=ntrip占有、22=ssh占有 を回避)
- /var/www/rotation-planner-v2/ など別ディレクトリへclone
- systemd unit `rotation-planner-v2.service` を新規作成
- 既存rotation-plannerは停止不要

### Scenario C: 「現状確認のみで終わり」
- Wave 2 不要。本Wave 1報告書をもって完了。

### 共通: Node不要
- VPS本番(`portal.py` Gradio)はPythonのみで起動可能。Node/npm導入不要。
- `start-dev.sh` 等の開発フローを使う場合のみNode導入必要(殿確認事項・§6 Q4)。

---

## §4 起動確認結果 (Wave 2で記入)

(空欄。Wave 2 実行後に追記)

---

## §5 ntripcaster影響評価 (Wave 2比較用baseline)

### 現状ベースライン (2026-05-18T10:51 取得)
```
=== NTRIP プロセス ===
root  3216892   1  May07 ?     00:00:00 SCREEN -AmdS ntrip ./ntripcaster
root  3216893 3216892  May07 pts/0 00:10:49 ./ntripcaster

=== ポート 2101 (NTRIP) ===
LISTEN 0.0.0.0:2101   ntripcaster(pid=3216893)
```

### 重要事実
- **ntripcasterはsystemd管理外**。`screen -AmdS ntrip ./ntripcaster` で root セッション内起動。
- 連続稼働中 (`May07` 起動、約11日間)。
- pid 3216892 (screen wrapper) と 3216893 (実プロセス) のいずれも触ってはならない。
- `screen -ls` でセッション `ntrip` を確認可能 (root所有)。**screen kill/quitも禁止**。
- `apt upgrade` 等で libstdc++ 等の共有LIBがダウングレードされた場合に影響リスクあり → Wave 1範囲外だがWave 2も apt upgrade 禁止。

### 衝突有無評価
| 評価項目 | 結果 |
|---|---|
| port 2101 (NTRIP) | 衝突なし (rotation-plannerは7863使用) |
| 共有ライブラリ依存 | リスクなし(個別 apt install のみで対応可、Wave 1は調査なので不要) |
| プロセスシグナル | リスクなし(rotation-planner restartはntrip pidに影響しない) |
| systemd操作 | リスクなし(ntripcasterはsystemd管理外。systemctl restart rotation-planner は無影響) |
| screen セッション | 触る予定なし(Wave 2も対象外) |

→ **Wave 2作業はntripcasterに影響しない見込み**。但しWave 2冒頭・末尾で `ps -ef | grep ntrip` と `sudo ss -tlnp | grep 2101` を再確認すること。

---

## §6 殿への質問・確定要事項

### Q1 (最優先・必須). 本タスクの真意確認
**事実**: `rotation-planner.service` は既にVPSで稼働中 (port 7863, pid 555, May07起動の長期稼働実績)。

**選択肢**:
- **(A) 既存版をorigin/main最新へ更新** ← §3 Scenario A
- **(B) 別ポートで別インスタンス追設**(マルチインスタンス) ← §3 Scenario B
- **(C) 現状確認のみで終わり** ← Wave 2不要
- **(D) その他**(殿の意図記述)

### Q2. requirements.txt 差分の扱い
**事実**: VPS実体は `gradio>=4.0.0` 追加・`python-multipart` 削除 (origin/main差分あり)。
**質問**: (a)VPS側の修正をoriginにpushして揃える / (b)VPSのrequirements.txt を origin準拠に戻す / (c)現状放置 (どれ?)

### Q3. systemd化方針 (Scenario B採用時のみ)
**質問**: 新規追設の場合、systemd unit `rotation-planner-v2.service` を作る? それともtmux/screen常駐で十分?

### Q4. Node/npm導入要否
**事実**: VPS本番は portal.py (Gradio) のみで動作。Node不要。
**質問**: `start-dev.sh` (React frontend) をVPSで使う計画はある? なければNode導入不要。

### Q5. (セキュリティ警告) GitHub PAT埋込
**事実**: VPS `/var/www/rotation-planner/app/.git/config` の origin URL に `ghp_xxxxxxxxx` (GitHub PAT) が平文埋込されている。
**質問**: SSH key認証 or `git credential` ストアへ移行するか? 露出スコープ調査要否?
*(注: PAT実値は本報告書には記載しない。Wave 1範囲外だが発見につき報告)*

### Q6. systemd unit と実プロセスの不整合
**事実**: rotation-planner.service unit は `GRADIO_SERVER_NAME=127.0.0.1` 指定だが、実プロセス(pid=555)は `0.0.0.0:7863` で全インターフェースlisten。
**仮説**: unit変更後に restart していない or 別プロセスが先行起動。
**質問**: 127.0.0.1 限定にしてリバースプロキシ(nginx等)経由にする? それとも 0.0.0.0 のままで放置?

### Q7. feature/multi-farmer ブランチ
**事実**: origin に `feature/multi-farmer` ブランチが残存(remote-only)。
**質問**: マージ予定 or 削除予定? Wave 2方針に影響あり?

---

## 付録: Wave 1で実行した read-only コマンド一覧 (監査用)

```bash
# ローカル
git clone --depth=1 https://github.com/yasunorioi/rotation-planner.git /tmp/rotation-planner-probe
ls -la /tmp/rotation-planner-probe/
cat /tmp/rotation-planner-probe/{requirements.txt, start-dev.sh, deploy_demo.sh}

# VPS (SSH read-only)
ssh debian@ik1-421-42663.vs.sakura.ne.jp '...'
  cat /etc/os-release
  uname -a
  df -h /
  python3 --version
  systemctl list-units --type=service --state=running
  ss -tlnp / ss -ulnp
  sudo -n ss -tlnp
  systemctl cat rotation-planner.service
  systemctl cat agriha-linebot.service
  ls -la /var/www/rotation-planner/app/
  cd /var/www/rotation-planner/app && sudo -u webapp git status / branch -a / log
  cat /var/www/rotation-planner/app/requirements.txt
  ps -ef | grep -E 'ntrip|caster'
```

実行コマンドはすべて read-only。書き込み・サービス操作・ファイル変更は一切行っていない。

---

(Wave 1終了。Wave 2着手は §6 Q1-Q2 への殿回答後)

---

## §7 Wave 2a SSH key準備完了 (2026-05-18T11:19)

### 殿回答(2026-05-18)を踏まえた本Waveの位置付け
- Q1=A: 既存版更新 → Wave 2b で実施
- Q2=a: VPS差分(gradio追加・python-multipart削除) を origin/main へ push → Wave 2b で実施
- Q5=SSH key移行 → **本Wave 2a で SSH key 準備のみ完了**
- Q3/Q4/Q6/Q7=放置

### 既存SSH key検出 → 新規鍵を別ファイル名で追設(既存鍵温存)
webapp ユーザーには既に既存鍵が1つあった:

| 項目 | 既存鍵 (温存) | 新規鍵 (本Wave 2a生成) |
|---|---|---|
| ファイル | `/home/webapp/.ssh/id_ed25519` | `/home/webapp/.ssh/id_ed25519_rotation_planner` |
| 公開鍵 | `/home/webapp/.ssh/id_ed25519.pub` | `/home/webapp/.ssh/id_ed25519_rotation_planner.pub` |
| 作成日 | 2026-01-31 | 2026-05-18 |
| コメント | `debian@ik1-421-42663` (用途不明) | `vps-rotation-planner-deploy-20260518` |
| 指紋 | `SHA256:ByyTcXiJd+X/r/NPZ6vgEO31m7q+PlCLKPs/sxykl6E` | `SHA256:DzSqCMSXC3DgQGK4a7Si9iMeFVTkg9IR/HT6OSs0Lqg` |

**理由**: 既存鍵のコメントが用途明示でなく、別所(別サーバ/別サービス)で利用されている可能性があるため、上書き生成は破壊リスク。別ファイル名で生成し既存鍵を温存。Wave 2b で `.git/config` の `core.sshCommand` または `~/.ssh/config` で新規鍵を明示指定する。

### 🔴 殿への提示: 新規鍵 公開鍵全文 (GitHubに登録するもの)

下記をそのままコピーしてGitHub UIに貼り付け:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN1IAKaVg5p6l21yay/SLxsq6dIQEVjGXiChLyZruDm8 vps-rotation-planner-deploy-20260518
```

指紋(登録後の照合用): `SHA256:DzSqCMSXC3DgQGK4a7Si9iMeFVTkg9IR/HT6OSs0Lqg`

### 🔴 殿への登録依頼 (2択)

#### 推奨: (b) Deploy Key (rotation-planner専用)
GitHub UI: **`yasunorioi/rotation-planner` → Settings → Deploy keys → Add deploy key**

| 項目 | 値 |
|---|---|
| Title | `vps-rotation-planner-deploy-20260518` |
| Key | (上記公開鍵全文) |
| ☑ Allow write access | **必須チェック** (Wave 2b で git push するため) |

**長所**: rotation-planner リポジトリ専用。yasunorioi アカウント全体・他リポジトリへの影響なし。露出最小。
**短所**: なし(本Wave 2bの用途には完全に合致)。

#### 代替: (a) アカウントレベルSSH key
GitHub UI: **yasunorioi アカウント → Settings → SSH and GPG keys → New SSH key**

| 項目 | 値 |
|---|---|
| Title | `vps-rotation-planner-deploy-20260518` |
| Key type | Authentication Key |
| Key | (上記公開鍵全文) |

**長所**: 殿の他リポジトリにも同じ鍵で push 可能。
**短所**: 万一VPS侵害時に yasunorioi 配下の全リポジトリが書き込み可能になる露出。

→ **(b) Deploy Key 推奨**。rotation-planner 1リポジトリだけ書き込み可能にする最小権限。

### 🚫 秘密鍵について (絶対不出)

秘密鍵 `/home/webapp/.ssh/id_ed25519_rotation_planner` は **本報告書に一切記載しない**。
鍵生成時に webapp ユーザー領域(600 権限)へ保存済み・GitHub登録は公開鍵 (.pub) のみで完結する。

### ntripcaster 影響評価 (Wave 2a)

| 項目 | 結果 |
|---|---|
| プロセス | 変動なし (pid 3216892/3216893 健在・確認は §5 baseline と同じコマンドで Wave 2b 冒頭に実施) |
| ポート 2101 | 変動なし(ssh-keygen はネットワーク無関与) |
| systemd / apt | 操作なし |
| screen セッション | 操作なし |
| 共有ライブラリ | 変動なし(パッケージインストールなし) |

Wave 2a はwebappユーザー領域のファイル生成のみ。ntripcaster 完全保全。

### Wave 2b 着手条件 (殿の手動操作完了後)

殿が GitHub UI で公開鍵を **Deploy Key (Allow write access)** または **Account SSH key** として登録 → 完了通知を受領後、家老が **subtask_1222 (Wave 2b)** を起票:
- SSH接続テスト `ssh -T -i ~/.ssh/id_ed25519_rotation_planner git@github.com`
- `.git/config` origin URL を `git@github.com:yasunorioi/rotation-planner.git` へ変更 (旧PAT URL置換)
- `~/.ssh/config` または `core.sshCommand` で新規鍵を明示指定
- VPS差分 (gradio追加・python-multipart削除) を origin/main へ push (Q2=a)
- 既存版更新 (Q1=A): stop → backup → git pull → pip install → start
- 起動確認 (curl 7863) + ntripcaster無影響確認 (ss/ps before-after)
- 旧PAT (`ghp_xxx`) は GitHub Settings → Personal access tokens で殿が手動 Revoke
- 報告書 §4 と §8 を追記


