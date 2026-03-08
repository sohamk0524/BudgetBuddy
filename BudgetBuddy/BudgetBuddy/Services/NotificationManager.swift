//
//  NotificationManager.swift
//  BudgetBuddy
//
//  Manages daily local push notifications to remind users to log transactions
//

import Foundation
import UserNotifications

@MainActor
class NotificationManager {

    static let shared = NotificationManager()

    // MARK: - Constants

    private let dailyReminderID = "dailyExpenseReminder"
    private let defaults = UserDefaults.standard

    private let reminderMessages = [
        "Don't forget to log your spending today!",
        "Quick check-in: any purchases to track today?",
        "Stay on top of your budget — log today's expenses!",
        "A minute now saves later. Log your transactions!",
        "Keep your streak going — have you logged today?",
        "Your budget works best when it's up to date!"
    ]

    // MARK: - Persisted Settings (UserDefaults keys)

    var notificationsEnabled: Bool {
        get { defaults.object(forKey: "notificationsEnabled") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "notificationsEnabled") }
    }

    var reminderHour: Int {
        get { defaults.object(forKey: "reminderHour") as? Int ?? 20 }
        set { defaults.set(newValue, forKey: "reminderHour") }
    }

    var reminderMinute: Int {
        get { defaults.object(forKey: "reminderMinute") as? Int ?? 30 }
        set { defaults.set(newValue, forKey: "reminderMinute") }
    }

    private var lastReminderIndex: Int {
        get { defaults.object(forKey: "lastReminderIndex") as? Int ?? -1 }
        set { defaults.set(newValue, forKey: "lastReminderIndex") }
    }

    // MARK: - Init

    private init() {}

    // MARK: - Permission

    @discardableResult
    func requestPermission() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .badge, .sound])
            return granted
        } catch {
            print("Notification permission error: \(error)")
            return false
        }
    }

    // MARK: - Scheduling

    func scheduleDailyReminder(hasLoggedToday: Bool) {
        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: [dailyReminderID])

        guard notificationsEnabled, !hasLoggedToday else { return }

        let content = UNMutableNotificationContent()
        content.title = "BudgetBuddy"
        content.body = generateReminderMessage()
        content.sound = .default

        var dateComponents = DateComponents()
        dateComponents.hour = reminderHour
        dateComponents.minute = reminderMinute

        let trigger = UNCalendarNotificationTrigger(dateMatching: dateComponents, repeats: true)
        let request = UNNotificationRequest(identifier: dailyReminderID, content: content, trigger: trigger)

        center.add(request) { error in
            if let error {
                print("Failed to schedule daily reminder: \(error)")
            }
        }
    }

    func cancelTodayNotification() {
        UNUserNotificationCenter.current()
            .removePendingNotificationRequests(withIdentifiers: [dailyReminderID])
    }

    func updateReminderTime(hour: Int, minute: Int, hasLoggedToday: Bool) {
        reminderHour = hour
        reminderMinute = minute
        scheduleDailyReminder(hasLoggedToday: hasLoggedToday)
    }

    // MARK: - Message Rotation

    private func generateReminderMessage() -> String {
        var nextIndex = lastReminderIndex + 1
        if nextIndex >= reminderMessages.count {
            nextIndex = 0
        }
        lastReminderIndex = nextIndex
        return reminderMessages[nextIndex]
    }
}
