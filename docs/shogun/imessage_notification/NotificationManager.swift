// NotificationManager.swift
// rotation-planner-ios — iMessage通知基盤（スタブ）
//
// 通知タイミング（トリガー発火条件）は未定のため、
// enum定義とsendNotification()スタブのみ実装。
// 実際の呼び出し元は各Feature側で実装すること。

import Foundation

#if canImport(AppKit)
import AppKit
#endif

// MARK: - 通知タイミング種別

/// 通知のトリガー種別。タイミングの詳細は各ケースのコメント参照。
enum NotificationTrigger {
    /// 圃場作業リマインダー（例: 翌日の作業前日通知）
    /// - parameter fieldId: 圃場ID
    /// - parameter taskDate: 作業予定日
    case fieldReminder(fieldId: String, taskDate: Date)

    /// 収穫アラート（例: 収穫適期に達した圃場の通知）
    /// - parameter fieldId: 圃場ID
    /// - parameter cropName: 作物名
    case harvestAlert(fieldId: String, cropName: String)

    /// カスタム通知（任意のメッセージ）
    /// - parameter label: 通知ラベル（ログ・識別用）
    case custom(label: String)
}

// MARK: - 通知設定

/// notification_config.yaml から読み込む通知設定
struct NotificationConfig {
    let recipient: String        // 宛先（電話番号 or Apple ID）
    let enabled: Bool            // 通知全体のon/off
    let fieldReminderEnabled: Bool
    let harvestAlertEnabled: Bool
    let customEnabled: Bool

    /// notification_config.yaml のデフォルト値
    static let `default` = NotificationConfig(
        recipient: "",
        enabled: false,
        fieldReminderEnabled: true,
        harvestAlertEnabled: true,
        customEnabled: true
    )
}

// MARK: - NotificationManager

/// iMessage通知の送信管理クラス（osascript経由）
final class NotificationManager {
    private let config: NotificationConfig
    private let scriptPath: String

    /// - Parameters:
    ///   - config: 通知設定
    ///   - scriptPath: imessage_sender.applescript の絶対パス
    init(config: NotificationConfig, scriptPath: String) {
        self.config = config
        self.scriptPath = scriptPath
    }

    // MARK: Public API

    /// 通知を送信する（スタブ）
    ///
    /// - Parameters:
    ///   - trigger: 通知トリガー種別
    ///   - message: 送信するメッセージ本文
    /// - Returns: 送信成功なら true
    @discardableResult
    func sendNotification(trigger: NotificationTrigger, message: String) -> Bool {
        guard config.enabled else { return false }
        guard isEnabled(for: trigger) else { return false }
        guard !config.recipient.isEmpty else { return false }

        return runAppleScript(recipient: config.recipient, message: message)
    }

    // MARK: Private

    private func isEnabled(for trigger: NotificationTrigger) -> Bool {
        switch trigger {
        case .fieldReminder:  return config.fieldReminderEnabled
        case .harvestAlert:   return config.harvestAlertEnabled
        case .custom:         return config.customEnabled
        }
    }

    /// osascript でAppleScriptを実行する
    private func runAppleScript(recipient: String, message: String) -> Bool {
#if os(macOS)
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        process.arguments = [scriptPath, recipient, message]

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus == 0
        } catch {
            // TODO: エラーログ連携（rotation-planner の Logger に統合予定）
            return false
        }
#else
        // iOS実機ではosascript不可。将来的にはPush通知等に置き換え
        return false
#endif
    }
}
