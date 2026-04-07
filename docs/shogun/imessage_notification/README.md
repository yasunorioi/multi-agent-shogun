# rotation-planner-ios iMessage通知基盤

iMessageでの農場通知機能（フック基盤）。通知タイミングは未定のためスタブのみ。

---

## MBPでの適用手順

**Step 1**: ファイルをリポにコピー

```bash
cd /Users/yasu/Project/rotation-planner-ios/
cp ~/Downloads/imessage_notification/imessage_sender.applescript ./scripts/
cp ~/Downloads/imessage_notification/NotificationManager.swift ./RotationPlanner/Notifications/
cp ~/Downloads/imessage_notification/notification_config.yaml ./config/
```

**Step 2**: notification_config.yaml を編集して宛先を設定

```yaml
enabled: true
recipient: "+819012345678"  # 自分のiPhone番号
```

**Step 3**: AppleScript の動作確認

```bash
osascript scripts/imessage_sender.applescript "+819012345678" "テスト送信"
```

Messages.app で自分宛にメッセージが届けば完了。

---

## ファイル構成

| ファイル | 役割 |
|--------|------|
| `imessage_sender.applescript` | Messages.app を叩く送信スクリプト（osascript経由） |
| `NotificationManager.swift` | Swift側フック（sendNotification + NotificationTrigger enum） |
| `notification_config.yaml` | 宛先・有効/無効・種別ごとon/off設定 |

## 通知種別（NotificationTrigger）

| enum | 用途 | 発火タイミング |
|------|------|:----------:|
| `.fieldReminder(fieldId:taskDate:)` | 圃場作業リマインダー | 未定 |
| `.harvestAlert(fieldId:cropName:)` | 収穫適期アラート | 未定 |
| `.custom(label:)` | 任意メッセージ | 任意 |

## 制約・注意

- **macOSのみ動作**: `runAppleScript()` は `#if os(macOS)` ガード済み。iOS実機では空振り
- **Messages.appが開いている必要あり**: osascript実行時にMessages.appが起動していること
- **iMessageアカウント**: Macで同じApple IDにサインインしていること
