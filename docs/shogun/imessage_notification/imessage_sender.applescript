-- imessage_sender.applescript
-- iMessageでメッセージを送信するAppleScript
--
-- 使い方:
--   osascript imessage_sender.applescript "+81901234xxxx" "本文テキスト"
--   osascript imessage_sender.applescript "user@example.com" "本文テキスト"
--
-- 引数:
--   argv[1] : 宛先（電話番号 or Apple ID メールアドレス）
--   argv[2] : メッセージ本文

on run argv
    if (count of argv) < 2 then
        error "Usage: osascript imessage_sender.applescript <recipient> <message>"
    end if

    set recipientAddress to item 1 of argv
    set messageBody to item 2 of argv

    tell application "Messages"
        -- iMessageサービスを取得（SMS/MMS にフォールバックしない）
        set targetService to first service whose service type = iMessage

        -- 宛先バディを解決（未登録でも電話番号/Apple IDで送信可能）
        set targetBuddy to buddy recipientAddress of targetService

        -- 送信
        send messageBody to targetBuddy
    end tell

    return "sent: " & messageBody & " -> " & recipientAddress
end run
