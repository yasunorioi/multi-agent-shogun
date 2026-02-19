# ArSprout SSH + WireGuard 設定手順書

> **作成日**: 2026-02-19
> **対象**: ArSprout 新SDカード（公式イメージ）+ WireGuard VPN追加
> **作業者**: 殿（物理操作が必要）
> **背景**: ArSprout公式イメージはSSHパスワード未設定・WireGuard未導入。
>          現場設置前にSSH鍵認証とVPN接続を設定する。

---

## 現行VPN構成（確認済み）

```
[VPS] 153.127.46.167 → 10.10.0.1
  ├── ArSprout     → 10.10.0.10  ← 今回設定対象（既存IP再利用）
  ├── Dev PC       → 10.10.0.100
  ├── Ubuntu PC    → 10.10.0.101
  └── iPhone       → 10.10.0.102
```

**ArSproutに割り当てるVPN IP: `10.10.0.10`**（既存設定を継承。VPS側Peerは更新が必要）

---

## 目次

1. [SDカードのSSH設定（PCマウント方式）](#1-sdカードのssh設定pcマウント方式)
2. [ArSprout初回起動 + ローカルSSH接続確認](#2-arsprout初回起動--ローカルssh接続確認)
3. [WireGuard設定（ArSprout上）](#3-wireguard設定arsprout上)
4. [VPS側 wg0.conf 更新](#4-vps側-wg0conf-更新必須)
5. [動作確認](#5-動作確認)
6. [トラブルシューティング](#6-トラブルシューティング)

---

## 1. SDカードのSSH設定（PCマウント方式）

ArSproutを起動する前に、SDカードをPCにマウントしてSSHと公開鍵を設定する。

### 1.1 SDカードのデバイス確認

```bash
# SDカードを差し込み後、デバイス名を確認
lsblk
# 例: /dev/sde (SDカード全体), /dev/sde1 (boot), /dev/sde2 (rootfs)

# または dmesg で確認
dmesg | tail -20 | grep -E 'sd[a-z]|mmcblk'
```

### 1.2 マウント

```bash
# マウントポイント作成
sudo mkdir -p /mnt/arsprout_boot /mnt/arsprout_root

# パーティション確認 (FAT32=bootパーティション, ext4=rootパーティション)
sudo fdisk -l /dev/sde   # デバイス名は適宜変更

# 1番パーティション(boot/FAT32) をマウント
sudo mount /dev/sde1 /mnt/arsprout_boot

# 2番パーティション(rootfs/ext4) をマウント
sudo mount /dev/sde2 /mnt/arsprout_root
```

### 1.3 SSH有効化

```bash
# SSH有効化ファイルを作成（Raspberry Pi OS方式）
sudo touch /mnt/arsprout_boot/ssh
echo "SSH有効化ファイル作成完了"
```

### 1.4 公開鍵の登録

```bash
# arpiユーザーの.sshディレクトリ作成
sudo mkdir -p /mnt/arsprout_root/home/arpi/.ssh
sudo chmod 700 /mnt/arsprout_root/home/arpi/.ssh

# 殿の公開鍵を authorized_keys に追加
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICv7mL88G66oJKyuTAbHMRmfO+JkzuIBU7zkBzaxL8aR' \
  | sudo tee /mnt/arsprout_root/home/arpi/.ssh/authorized_keys

# パーミッション設定
sudo chmod 600 /mnt/arsprout_root/home/arpi/.ssh/authorized_keys

# 所有者をarpiユーザーに設定
# arpiのUID/GIDを確認してから設定
grep arpi /mnt/arsprout_root/etc/passwd
# 出力例: arpi:x:1000:1000:...
sudo chown -R 1000:1000 /mnt/arsprout_root/home/arpi/.ssh
```

### 1.5 sshd_config 確認（任意）

```bash
# パスワード認証が有効かどうか確認（鍵認証のみにする場合）
grep -E 'PasswordAuth|PubkeyAuth' /mnt/arsprout_root/etc/ssh/sshd_config
# または
sudo grep -n 'PasswordAuthentication' /mnt/arsprout_root/etc/ssh/sshd_config
```

公開鍵登録後はパスワード認証は不要。変更は任意。

### 1.6 アンマウント

```bash
sudo umount /mnt/arsprout_boot
sudo umount /mnt/arsprout_root
echo "アンマウント完了。SDカードを取り出してArSproutに挿入してOK"
```

---

## 2. ArSprout初回起動 + ローカルSSH接続確認

### 2.1 起動とIP確認

1. SDカードをArSproutに挿入して電源ON
2. ルーターの管理画面またはネットワークスキャンでIPを確認:
   ```bash
   # 自宅LANが 192.168.1.0/24 の場合
   nmap -sn 192.168.1.0/24 | grep -B1 -A1 -i "raspberry\|arsprout"

   # または arp スキャン
   sudo arp-scan --localnet | grep -i "raspberry"
   ```
3. ArSproutのIPを確認する（例: `192.168.1.74`）

### 2.2 SSH接続テスト

```bash
# ローカルネットワーク経由でSSH接続
ssh arpi@192.168.1.74   # ← 実際のIPに変更

# 初回接続時: fingerprint確認メッセージが出る → "yes" と入力
# The authenticity of host '192.168.1.74' can't be established.
# → yes

# 接続成功確認
arpi@arsprout:~$ whoami
# → arpi
arpi@arsprout:~$ hostname
# → arsprout (またはArSproutのホスト名)
```

### 2.3 sudo権限確認

```bash
arpi@arsprout:~$ sudo -l
# パスワードなしでsudoが使える想定 (nopasswd設定)
# または
arpi@arsprout:~$ sudo whoami
# → root
```

---

## 3. WireGuard設定（ArSprout上）

ArSproutにSSH接続した状態で実行する。

### 3.1 WireGuardインストール

```bash
sudo apt update && sudo apt install -y wireguard wireguard-tools
```

### 3.2 鍵ペア生成

```bash
# 鍵ファイル保存ディレクトリ作成
sudo mkdir -p /etc/wireguard

# 秘密鍵 + 公開鍵を生成
wg genkey | sudo tee /etc/wireguard/private.key | wg pubkey | sudo tee /etc/wireguard/public.key

# 公開鍵を表示（VPS設定に必要。コピーして控えておく）
sudo cat /etc/wireguard/public.key
# 出力例: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=

# パーミッション設定（秘密鍵は600必須）
sudo chmod 600 /etc/wireguard/private.key
sudo chmod 644 /etc/wireguard/public.key
```

**⚠️ 公開鍵をコピーしておく。Step 4で VPS 設定に使用する。**

### 3.3 wg0.conf 作成

```bash
# 秘密鍵の値を確認
PRIVKEY=$(sudo cat /etc/wireguard/private.key)
echo "PrivateKey = $PRIVKEY"

# wg0.conf を作成
sudo tee /etc/wireguard/wg0.conf << 'EOF'
[Interface]
Address = 10.10.0.10/24
PrivateKey = <PRIVATE_KEY>        # ← sudo cat /etc/wireguard/private.key の値に置換
DNS = 1.1.1.1

[Peer]
# VPS WireGuard Server
PublicKey = exVHb4SxYi99jNOGjOpVpcBvMB7lsTSWGRg1bZGc/SQ=
PresharedKey = <PRESHARED_KEY>   # ← VPS wg0.confの既存PSKをそのまま使用可（後述）
Endpoint = 153.127.46.167:31820
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
EOF
```

**`<PRIVATE_KEY>` と `<PRESHARED_KEY>` の設定方法:**

```bash
# 方法A: ワンライナーで直接書き込み（推奨）
PRIVKEY=$(sudo cat /etc/wireguard/private.key)
# VPSからPSKを取得:
# ssh debian@153.127.46.167 'sudo grep PresharedKey /etc/wireguard/wg0.conf'
PSK="<PSK_FROM_VPS>"

sudo tee /etc/wireguard/wg0.conf > /dev/null << EOF
[Interface]
Address = 10.10.0.10/24
PrivateKey = ${PRIVKEY}
DNS = 1.1.1.1

[Peer]
# VPS WireGuard Server
PublicKey = exVHb4SxYi99jNOGjOpVpcBvMB7lsTSWGRg1bZGc/SQ=
PresharedKey = ${PSK}
Endpoint = 153.127.46.167:31820
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
EOF

# 確認
sudo cat /etc/wireguard/wg0.conf
sudo chmod 600 /etc/wireguard/wg0.conf
```

> **PSKについて**: `<PSK_FROM_VPS>` はVPS wg0.confの既存ArSprout Peerに設定済みの値。
> 取得方法: `ssh debian@153.127.46.167 'sudo grep PresharedKey /etc/wireguard/wg0.conf'`
> 新規PSKを生成する場合は `wg genpsk` コマンドを使用し、VPS側も同時に更新すること。

### 3.4 WireGuard 起動 + 自動起動設定

```bash
# wg0インターフェース起動
sudo systemctl enable --now wg-quick@wg0

# 起動確認
sudo systemctl status wg-quick@wg0

# WireGuard状態確認
sudo wg show
# 出力例:
# interface: wg0
#   public key: <ArSproutの公開鍵>
#   listening port: xxxxx
# peer: exVHb4Sxxx...
#   endpoint: 153.127.46.167:31820
#   latest handshake: X seconds ago
#   transfer: xxx received, xxx sent
```

---

## 4. VPS側 wg0.conf 更新（必須）

> **⚠️ この手順は殿がVPSにSSHしてrootまたはsudo権限で実行する**

新SDカードで生成した ArSprout の公開鍵が変わるため、VPS側の設定を更新する。

### 4.1 現在の設定バックアップ

```bash
ssh debian@153.127.46.167
sudo cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.bak_$(date +%Y%m%d)
```

### 4.2 ArSprout Peer の公開鍵を更新

```bash
# wg0.conf を編集（nanoまたはvi）
sudo nano /etc/wireguard/wg0.conf

# 以下の行を見つけて <新しい公開鍵> に書き換える:
# [Peer]
# # Arsprout - Production IoT Device
# PublicKey = Qq+Fe6KYQs7QPF92M0EupEBx0biGMKl5AY4eAjdeYiU=  ← ここを新公開鍵に変更
# PresharedKey = <PSK_FROM_VPS>  ← 変更不要（再利用）
# # VPSからPSKを取得: ssh debian@153.127.46.167 'sudo grep PresharedKey /etc/wireguard/wg0.conf'
# AllowedIPs = 10.10.0.10/32  ← 変更不要
```

**書き換えイメージ:**
```ini
[Peer]
# Arsprout - Production IoT Device (updated SDcard 2026-02-19)
PublicKey = <Step 3.2 で取得した新しい公開鍵>
PresharedKey = <PSK_FROM_VPS>
AllowedIPs = 10.10.0.10/32
```

### 4.3 VPS側 WireGuard を再読み込み

```bash
# wg0を再起動（接続中のPeerも再接続される）
sudo systemctl restart wg-quick@wg0

# または ホットリロード（接続を切らずにPeer設定のみ更新）
sudo wg syncconf wg0 <(sudo wg-quick strip wg0)

# 設定確認
sudo wg show
```

---

## 5. 動作確認

### 5.1 ArSprout側でWG接続確認

```bash
# ArSproutに(ローカルネットワーク経由で)SSH接続してから実行
sudo wg show
# 期待: VPSとのhandshakeが "X seconds ago" と表示される

# VPSにping
ping -c 3 10.10.0.1
# 期待: 3/3 packets received
```

### 5.2 VPS側での確認

```bash
ssh debian@153.127.46.167
sudo wg show
# 期待: 10.10.0.10 のPeerに latest handshake が表示される
```

### 5.3 VPN経由SSH接続テスト（最終確認）

```bash
# 自宅PCから VPN経由でArSproutにSSH
ssh arpi@10.10.0.10
# 接続成功 → セットアップ完了！
```

### 5.4 接続確認チェックリスト

- [ ] `ssh arpi@192.168.1.xx` (ローカル) 接続成功
- [ ] ArSprout上で `sudo wg show` → VPSとhandshake確認
- [ ] `ping 10.10.0.1` → VPSへの疎通確認
- [ ] `ssh arpi@10.10.0.10` (VPN経由) 接続成功
- [ ] `sudo systemctl status wg-quick@wg0` → active (running)

---

## 6. トラブルシューティング

### SSH接続できない

```bash
# authorized_keysのパーミッションを確認
ls -la ~/.ssh/
# .ssh: 700, authorized_keys: 600 が必須

# sshdログを確認
sudo journalctl -u ssh -n 50
```

### WireGuard handshakeが確立しない

```bash
# VPS側ファイアウォール確認 (UDP 31820が開いているか)
ssh debian@153.127.46.167 'sudo ufw status'
# または: sudo iptables -L -n | grep 31820

# wg0.confの公開鍵・PSKが一致しているか確認
# ArSprout側: sudo wg show → public key
# VPS側: sudo cat /etc/wireguard/wg0.conf → ArSprout PeerのPublicKey

# WireGuardログ確認
sudo journalctl -u wg-quick@wg0 -n 50
```

### ArSproutのローカルIPが分からない

```bash
# nmap でRaspberry Piを探す
nmap -sn 192.168.1.0/24

# Avahi/mDNSが有効ならhostname.localで接続可能な場合も
ssh arpi@arsprout.local
# または
ssh arpi@raspberrypi.local
```

### wg-quick@wg0 が起動しない

```bash
# 詳細ログ
sudo journalctl -u wg-quick@wg0 -n 50

# 設定ファイルの構文チェック
sudo wg-quick strip wg0
```

---

## 付録: VPN IPアドレス割当表（2026-02-19現在）

| IP | デバイス | 状態 |
|----|---------|------|
| 10.10.0.1 | VPS (WGサーバー) | 稼働中 |
| 10.10.0.10 | **ArSprout (新SDカード)** | **今回設定** |
| 10.10.0.11〜99 | 未割当 | 空き |
| 10.10.0.100 | Dev PC (Windows) | 稼働中 |
| 10.10.0.101 | Ubuntu Dev PC | 稼働中 |
| 10.10.0.102 | iPhone | 稼働中 |

---

## 付録: 作業サマリ（ワンライン版）

```
1. SDカード(PC) → ssh有効化 + 公開鍵登録 → ArSproutに挿入・起動
2. ssh arpi@192.168.1.xx → apt install wireguard → wg genkey → wg0.conf作成 → systemctl enable wg-quick@wg0
3. VPS: wg0.conf の ArSprout PublicKey を新しい公開鍵に書き換え → wg syncconf
4. ssh arpi@10.10.0.10 で確認
```
