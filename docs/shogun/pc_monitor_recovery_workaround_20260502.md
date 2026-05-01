# PCモニター復帰不能 — 暫定回避実装レポート

- **作成日**: 2026-05-02T02:27:17 JST
- **作成者**: ashigaru6（部屋子1）
- **cmd**: cmd_575 / subtask_1218
- **モード**: V4自動運転可カテゴリ（内部設定変更のみ・全revert可）

---

## §1. GPU/OS/カーネル情報

| 項目 | 値 |
|------|-----|
| OS | Ubuntu 25.10 (questing) |
| Kernel | Linux 6.17.0-22-generic x86_64 |
| ディスプレイサーバ | Wayland |
| GPU 1 (使用中) | **NVIDIA RTX 4060 (AD107)** — driver=**nouveau** |
| GPU 2 (未接続) | AMD Raphael — driver=amdgpu |
| 接続モニタ | DP-4 (NVIDIA card1) 5120x2880@60Hz |
| LAN IP | 192.168.15.14 (enp4s0) |

### 過去boot履歴（journalctl --list-boots 抜粋）

```
-1: 04-29 20:39 → 05-01 21:10:25
 0: 05-01 21:13:58 → 現在
```

→ -1から0の **gap 3分33秒**（通常reboot gapは17〜39秒）。**強制リセット痕跡**を確認。

---

## §2. 既存設定（変更前）

### gsettings (GNOME)

| キー | 変更前 |
|------|--------|
| `org.gnome.settings-daemon.plugins.power idle-dim` | **true** |
| `org.gnome.desktop.screensaver idle-activation-enabled` | **true** |
| `org.gnome.settings-daemon.plugins.power ambient-enabled` | **true** |
| `org.gnome.desktop.session idle-delay` | 0（既無効） |
| `org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type` | 'nothing'（既対策済） |

### systemd-logind

```
/etc/systemd/logind.conf:
[Login]
（IdleAction指定なし＝デフォルト動作）
```

### SSH（既存）

- `openssh-server` インストール済み（10.0p1-5ubuntu5.4）
- `systemctl is-active ssh` = **active** ✅
- `systemctl is-enabled ssh` = **disabled** 🟡（要対応・§3後段）
- `ss -tlnp` = `0.0.0.0:22 / [::]:22 LISTEN` ✅
- `~/.ssh/authorized_keys` 存在
- `sshd_config`: `#PasswordAuthentication yes`（コメント=デフォルト=yes）

---

## §3. 実施した変更

### Phase 2: SSH（既稼働確認のみ・新規変更なし）

殿の追加判明事項では「SSH未設定」となっていたが、確認の結果 **既に稼働中**であった:

- ssh 22ポート listen 中 → **外部から既にアクセス可能**
- LAN IP `192.168.15.14`、認証は `~/.ssh/authorized_keys` 鍵存在
- 朝以降、殿のスマホ/別PC等から `ssh yasu@192.168.15.14` で接続可能

### Phase 3 (実行済): GNOME idle対策（user権限・revert可）

```bash
# 実行コマンド (2026-05-02T02:27:17 JST)
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false
gsettings set org.gnome.settings-daemon.plugins.power ambient-enabled false
```

| キー | 変更前 → 変更後 | revert |
|------|---|---|
| `idle-dim` | true → **false** | `gsettings reset org.gnome.settings-daemon.plugins.power idle-dim` |
| `idle-activation-enabled` | true → **false** | `gsettings reset org.gnome.desktop.screensaver idle-activation-enabled` |
| `ambient-enabled` | true → **false** | `gsettings reset org.gnome.settings-daemon.plugins.power ambient-enabled` |

これにより無操作時のモニター減光・スクリーンセーバー起動・周辺光自動調整が **全て停止**。GNOMEレイヤー由来のモニターOFF経路を遮断。

### Phase 3 (殿手動実行用): logind IdleAction=ignore + SSH強化

ash6は **sudo passwordless 不可**のため自動実行できず。**殿の朝の作業として §5 に手順記載**。実行内容:

#### 3-A. logind IdleAction=ignore （revert可能形式）

```bash
sudo cp /etc/systemd/logind.conf /etc/systemd/logind.conf.bak.20260502
sudo tee -a /etc/systemd/logind.conf <<'EOF'

# ===== cmd_575 subtask_1218 暫定回避 (2026-05-02) =====
# original: IdleAction=suspend (default), IdleActionSec=30min
IdleAction=ignore
IdleActionSec=0
# ===== /cmd_575 =====
EOF
sudo systemctl restart systemd-logind
systemctl status systemd-logind --no-pager | head -5
```

revert: `sudo cp /etc/systemd/logind.conf.bak.20260502 /etc/systemd/logind.conf && sudo systemctl restart systemd-logind`

#### 3-B. SSH 自動起動有効化 + パスワード認証無効化（authorized_keys 存在時のみ）

```bash
sudo systemctl enable ssh
# authorized_keys 存在確認済（~/.ssh/authorized_keys）→ PasswordAuth無効化可能
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.20260502
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
ss -tlnp | grep :22  # 動作確認
```

revert: `sudo cp /etc/ssh/sshd_config.bak.20260502 /etc/ssh/sshd_config && sudo systemctl restart ssh`

#### 3-C. ufw許可（ufw有効時のみ）

```bash
sudo ufw status >/dev/null 2>&1 && sudo ufw allow ssh   # LAN内のみ運用前提
```

### スコープ外（実施せず・殿許可待ち別cmd）

- nvidia-driver-550 系プロプライエタリ切替（cmd_574 §8 推奨A）
- 完全サスペンド無効化（指示書厳禁）
- BIOS設定変更
- nouveauブラックリスト化

---

## §4. 残リスク（次回フリーズ時の挙動予測）

| リスク | 発生条件 | 影響 | 対応 |
|---|---|---|---|
| **nouveau Xid:13再発** | Chromeで5K2K描画 | GPCチャネルkill→画面真っ暗。GNOME idle対策ではこの根本原因は防げない | **SSH経由で `sudo systemctl reboot` 可能**（モニター死亡時の救出経路） |
| **logind IdleAction未対策での自動suspend** | 殿が§5の3-A未実行のまま放置 | 30分でsystemd-logindがsuspend発火→モニター戻らない可能性 | 殿の朝の作業 §5 で対処 |
| **SSH disabled状態で再起動** | フリーズ→電源強制再投入後、SSHが立ち上がらない | 次回フリーズ時に外部救出経路が消失 | §5 3-B `sudo systemctl enable ssh` |
| **PasswordAuth有効のまま外部公開** | 万一WAN到達時 | brute force リスク | §5 3-B PasswordAuth=no |

---

## §5. 朝の確認手順（殿起床時即把握用）

### A. 朝起きて画面真っ暗だった場合

1. **別端末（スマホ/ノートPC）から SSH 接続を試みる**:
   ```
   ssh yasu@192.168.15.14
   ```
2. SSH 接続成功 → ログイン後 `journalctl -k --since "1 hour ago" | grep -iE 'nouveau|xid|fault' | tail -30` でフリーズ時刻のGPU例外を確認
3. その後 `sudo systemctl reboot` で **リセットボタンに頼らず**再起動可能
4. SSH 接続失敗時のみリセットボタン

### B. 朝起きて画面正常だった場合（=対策成功 or 偶発的に発症せず）

1. 念のため `journalctl -b 0 -p warning | grep -iE 'nouveau|drm' | tail -20` でGPU例外発生有無確認
2. **§3 手動実行手順 3-A / 3-B を順次実行**（コピペ実行用に手順記載）
3. 再起動して `systemctl is-enabled ssh` = enabled、`grep IdleAction /etc/systemd/logind.conf` 反映確認

### C. 全変更のrevert方法（一括）

```bash
# GNOME idle 全revert
gsettings reset org.gnome.settings-daemon.plugins.power idle-dim
gsettings reset org.gnome.desktop.screensaver idle-activation-enabled
gsettings reset org.gnome.settings-daemon.plugins.power ambient-enabled
# logind revert (3-A実行済の場合)
sudo cp /etc/systemd/logind.conf.bak.20260502 /etc/systemd/logind.conf
sudo systemctl restart systemd-logind
# sshd revert (3-B実行済の場合)
sudo cp /etc/ssh/sshd_config.bak.20260502 /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## §6. エグゼクティブサマリ（30行以内厳守）

### 結論（3行）

1. **SSH既に稼働中**（LAN IP `192.168.15.14`・鍵認証可）— 朝以降もし画面真っ暗ならスマホ等から `ssh yasu@192.168.15.14` で救出可能
2. ash6が user権限で実行可能な GNOME idle 対策（idle-dim/idle-activation/ambient = false）を **既に適用済**。idle由来のモニターOFF経路は遮断
3. logind IdleAction=ignore と SSH enable + PasswordAuth=no は **sudo必要のため殿朝の手動実行**（§3 にコピペ手順記載・全revert可）

### 選択肢

- **A**: §5 朝の手順 B 全実行（logind+SSH強化・所要1分）→ 暫定回避完了
- **B**: §5 のうち SSH enable のみ実行（最低限の救出経路確保）→ logindは様子見
- **C**: 何もせず即 cmd_576 へ（nvidia-driver切替=根本対策へ進む）

### 推奨

**B（SSH enable のみ）即実行→ 短期間で C（nvidia-driver切替）へ移行**。logind対策は nouveau問題に対しては効果限定的（GNOME idleではなくGPU drm例外が主因）。根本対策＝nvidia-driver切替を急ぐべき。

### 殿への質問（3問）

1. **Q1**: §5 3-A/3-B のコピペ手順、起床直後に実行可能か？（推奨B最低限なら3-Bだけで可）
2. **Q2**: 直近 -1→0 boot gap 3分33秒の異常gap、就寝中ではなく操作中の発生だった可能性。フリーズ発生は **就寝中限定**か、**操作中も**起こるか？
3. **Q3**: cmd_576 起票（nvidia-driver-550 切替）を本日着手して良いか、もう数日 nouveau継続でログ蓄積するか？

---

read-only逸脱ゼロ／HW設定変更ゼロ／F006厳守／全変更 revert可能形式厳守
