# nouveau→nvidia-driver 切替 + フリーズログ救出レポート

- **作成日**: 2026-05-02T09:32:46 JST
- **作成者**: ashigaru6（部屋子1）
- **cmd**: cmd_576 / subtask_1219
- **モード**: V4自動運転可カテゴリ（HW破壊リスクなし・apt revert可）
- **完遂状況**: **PARTIAL（停止条件2件発動・殿帰宅後手動完遂用に手順移管）**

---

## §1. 今朝のフリーズログ救出結果（Phase 0・最重要）

### 救出ファイル

| ファイル | 行数 | 内容 |
|---|---|---|
| `/tmp/freeze_log_b-1.txt` | 19 | 前回boot(-1)中の nouveau/Xid/fault/drm/gpu warning↑ |
| `/tmp/freeze_kernel_b-1.txt` | 200 | 前回boot kernel末尾200行 |
| `/tmp/current_boot_log.txt` | 36 | 現boot(0)の DRM/GPU 警告 |
| `/tmp/reboot_history.txt` | 8 | journalctl --list-boots（過去7boot） |

### nouveau Xid:13 タイムスタンプ抽出（全件）

```
[1] 4/29 22:44:24  gsp: mmu fault queued  fault_addr: 0x3ff5650000  fault_type: 0x00000002 (write)
                   fifo: chrome[54051] errored - disabling channel(18)

[2] 4/29 22:44:24  Xid:13 Graphics Exception on GPC 0/1/2
                   ESR(GPC0)=0x80000010 / ESR(GPC1)=0x80000010 / ESR(GPC2)=0x80000010
                   全コア "WIDTH CT Violation" (テクスチャ寸法違反)
                   chrome[54350]: channel 18 killed! / error fencing pushbuf: -19

[3] 4/29 22:44:55  gsp: mmu fault queued  fault_addr: 0x3ffd154000  fault_type: 0x00000002
                   chrome[54801]: channel 18 killed!

(過去5/01 21:21, 22:40, 5/02 01:13, 01:19 はsubtask_1217で別途記録済)
```

### 解釈

- 全件 chrome プロセスが引き金（Wayland描画アクセラレーション）
- WIDTH CT Violation = 5K2K@60Hz テクスチャ寸法に nouveau が対応しきれない
- **errornum 共通**: ESR=0x80000010 / 0x500434=0x48-0x4c / 0x500438=0x2001800
- mmu fault: type 0x00000002 = write fault（書き込み権限違反）

### 過去bootギャップ分析

| Boot | 終了 → 次開始 gap | 評価 |
|---|---|---|
| -6→-5 | 17秒 | 通常reboot |
| -5→-4 | 39秒 | 通常reboot |
| -4→-3 | 26秒 | 通常reboot |
| -3→-2 | 32秒 | 通常reboot |
| -2→-1 | 39秒 | 通常reboot |
| **-1→0** | **3分33秒** | **異常gap = リセット強要痕跡** |

→ 殿の追加証言（Q2回答: マウス・キーボード操作で復帰せず=GPU出力のみ死亡）と完全整合。

---

## §2. 切替前環境（Phase 1・read-only）

| 項目 | 値 |
|------|-----|
| GPU 1 | NVIDIA AD107 [GeForce RTX 4060] (Lovelace) — driver=**nouveau** |
| GPU 2 | AMD Raphael — driver=amdgpu（未接続） |
| Kernel | 6.17.0-22-generic |
| linux-headers | linux-headers-6.17.0-22-generic ✅ 導入済 / build symlink有効 |
| dkms | インストール済 / 現在エントリなし |
| nvidia系pkg | **一切未インストール** |
| **secure boot** | **disabled** (Setup Mode) ✅ MOK登録不要 |
| ubuntu-drivers recommended | **nvidia-driver-595-open** （distro non-free） |
| nvidia-driver-550 状態 | **transitional package**（Ubuntu 25.10で実体なし・依存解決で他に置換） |

### ubuntu-drivers devices 出力抜粋

```
== /sys/devices/.../0000:01:00.0 ==
modalias : pci:v000010DEd00002882sv00001458sd00004109bc03sc00i00
vendor   : NVIDIA Corporation
model    : AD107 [GeForce RTX 4060]
driver   : nvidia-driver-580 / 580-open / 580-server / 580-server-open
driver   : nvidia-driver-595 / 595-open(★recommended) / 595-server / 595-server-open
driver   : xserver-xorg-video-nouveau - distro free builtin
```

→ **550 系は ubuntu-drivers の対応リストから除外**（Lovelace世代の継続サポート無し）

---

## §3. インストール手順（Phase 2・🚨停止条件発動で殿手動実行用に移管）

### 🚨 停止条件発動内訳

| # | 条件 | 状況 | 影響 |
|---|---|---|---|
| 1 | sudo passwordless 不可 | `sudo -n true` → PASSWORD_REQUIRED | apt install / sudo tee / sudo update-initramfs 全て実行不能 |
| 2 | nvidia-driver-550 が殿のGPU未対応 | Ubuntu 25.10 で 550=transitional package・ubuntu-drivers 推奨は 595-open | 別バージョン選定要 = 指示書「殿確認必須で中断」該当 |

→ **指示書の停止条件通り、Phase 2/3 を中断し、殿確認必須として手順移管**。

### 殿帰宅後の実行手順（コピペ可・bak保存付revert可）

```bash
# 0. sudo 認証準備
sudo -v

# 1. ubuntu-drivers 自動選択(recommended=595-open)
sudo ubuntu-drivers install 2>&1 | tee /tmp/nvidia_install.log

# もしくは明示指定:
# sudo apt install -y nvidia-driver-595-open

# 2. dkms 状態確認
dkms status | grep nvidia
```

### 想定パッケージ群（apt の依存解決による）

- nvidia-driver-595-open (metapackage)
- nvidia-dkms-595-open
- nvidia-utils-595
- libnvidia-* 一式

### Installed-Size 事前確認

`nvidia-driver-595-open`: 37 KiB（metapackage 単体・依存込みで実サイズ約 700-900 MB 想定）

---

## §4. nouveau ブラックリスト+initramfs-u（Phase 3・殿手動実行用）

### 既存状態

```
/etc/modprobe.d/blacklist-nouveau.conf  → 未存在
lsmod | grep nouveau → ロード中(refcount=48・amdgpu経由でi2c_algo_bit/video等共有)
```

### 殿帰宅後の手順

```bash
# nvidia-driver install で自動作成される場合あり、未作成なら手動:
ls /etc/modprobe.d/blacklist-nouveau.conf 2>/dev/null || \
  echo -e "blacklist nouveau\noptions nouveau modeset=0" | sudo tee /etc/modprobe.d/blacklist-nouveau.conf

sudo update-initramfs -u
```

revert: `sudo rm /etc/modprobe.d/blacklist-nouveau.conf && sudo update-initramfs -u`

---

## §5. secure boot 状態 + MOK登録要否（Phase 1判定済）

```
$ mokutil --sb-state
SecureBoot disabled
Platform is in Setup Mode
```

→ **secure boot 無効** ✅ → **MOK 登録不要・停止条件1回避**

将来 secure boot 有効化時:
- `nvidia-driver-595-open` は dkms ビルドで kernel module を自動生成
- secure boot 有効なら MOK 登録必要（`sudo mokutil --import /var/lib/shim-signed/mok/MOK.der`）→ 再起動時 MokManager で承認
- 現状は無効のため不要

---

## §6. 殿帰宅後の再起動手順 + 確認手順

### 再起動前

```bash
# §3/§4 の install + blacklist + initramfs-u 完了確認
ls /etc/modprobe.d/blacklist-nouveau.conf
dkms status | grep nvidia
```

### 再起動

```bash
sudo systemctl reboot
```

### 再起動後の確認

```bash
# nouveau が消えている事
lsmod | grep nouveau    # 空であること

# nvidia がロードされている事
lsmod | grep nvidia     # nvidia / nvidia_modeset / nvidia_drm / nvidia_uvm 確認

# ドライバ稼働確認
nvidia-smi
# 期待: GeForce RTX 4060 / Driver Version: 595.xx.xx / CUDA Version 12.x

# DRM 接続確認
cat /sys/class/drm/card*-DP-4/status   # connected であること
xrandr 2>&1 | head -3                   # 5120x2880@60Hz 認識
```

### 再発監視（再起動後 1 時間程度）

```bash
journalctl -b 0 -p warning | grep -iE 'nvidia|drm|gpu|fault' | tail -20
# nvidia 由来の Xid エラーがないことを確認
# ある場合は Chrome のハードウェア加速 OFF を検討
```

---

## §7. ロールバック手順（nvidia → nouveau 復帰）

nvidia導入後に問題発生（画面真っ暗継続・boot失敗等）時:

```bash
# 1. nvidia 関連 purge
sudo apt remove --purge 'nvidia-*' 'libnvidia-*'
sudo apt autoremove --purge

# 2. nouveau blacklist 解除
sudo rm /etc/modprobe.d/blacklist-nouveau.conf
sudo update-initramfs -u

# 3. 再起動
sudo systemctl reboot

# 4. 再起動後確認
lspci -k | grep -A 3 -i vga    # Kernel driver in use: nouveau に戻ったこと
```

### 緊急時（boot失敗→GUI起動不能）

- GRUB で `Advanced options` → `recovery mode` → root shell
- もしくは別端末から `ssh yasu@192.168.15.14` （SSH既稼働 → cmd_575 setup後はboot自動起動）
- ロールバック手順実行 → reboot

---

## §8. エグゼクティブサマリ（30行以内厳守）

### 結論（3行）

1. **Phase 0 完遂**: 今朝のフリーズログ救出済（4/29 22:44 nouveau Xid:13+mmu fault・全件chrome原因）+過去boot gap 3分33秒の異常リセット痕跡確認
2. **Phase 1 完遂**: secure boot=disabled（MOK不要）/ recommended=**nvidia-driver-595-open**（550非対応・transitional pkg）/ kernel-headers+dkms完備
3. **Phase 2/3 中断**: 停止条件2件発動 — (a) sudo passwordless不可 (b) 指示書 550 が Ubuntu 25.10 で transitional → 殿確認必須中断・手順は §3/§4/§6 にコピペ可形式で移管

### 選択肢

- **A**: 595-open採用（Ubuntu公式recommended・Lovelace正式サポート・最新535+系列）→ 推奨
- **B**: 595-server採用（サーバー版・headless志向・GUI環境では不要）→ 非推奨
- **C**: 580-open採用（一世代古い・Lovelace対応はあるが推奨度低）→ 緊急回避用

### 推奨

**A（nvidia-driver-595-open）即実行**。 dashboard.md「殿帰宅時の作業手順」Step 3に全コピペ手順記載。所要約3-5分（apt install本体は5-10分・dkms build時間別）+再起動1回。再起動は殿判断のため本cmd範囲外。

### 殿への質問（3問）

1. **Q1**: 595-open採用OKか？（550指示だったがUbuntu 25.10は550=transitional package・595-openがpublic recommended）
2. **Q2**: dashboard.md Step 1-3 を帰宅直後実行可能か？（cmd_575残作業も同時完遂・所要5分程度）
3. **Q3**: 再起動タイミングはいつか？（apt install後即時 or その日の作業終了後・夜間放置の前）

---

## 付録: 自動運転境界判定

| 観点 | 評価 |
|---|---|
| HW物理破壊リスク | **なし**（ソフトドライバ切替のみ） |
| 既存セッション保護 | ✅ 再起動なし(本cmd範囲外) |
| revert可能性 | ✅ apt remove + rm blacklist で完全復帰 |
| F006抵触 | **なし** |
| 殿の判断点 | 再起動タイミング のみ |
| 自動運転で完遂可能か | 🟡 sudo passwordless なら可 / 現環境では PARTIAL（停止条件発動）|

read-only逸脱: 0件（実行は journalctl/ls/cat/lspci/lsmod 等の情報取得のみ）
F006厳守: GitHub Issue/PR/コメント投稿 0件
revert可能形式: 全手順 bak保存 or apt remove で復帰可能

既存暫定回避(cmd_575 gsettings idle系)は **そのまま維持**（二重化で再発リスク低減）。
