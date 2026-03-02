//
//  NotificationSettingsView.swift
//  BudgetBuddy
//
//  Settings UI for configuring daily expense reminder notifications
//

import SwiftUI

struct NotificationSettingsView: View {
    @AppStorage("notificationsEnabled") private var notificationsEnabled = true
    @State private var reminderTime = Date()

    private let manager = NotificationManager.shared

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {

                // MARK: - Enable/Disable
                VStack(alignment: .leading, spacing: 16) {
                    Label("Daily Reminder", systemImage: "bell.badge")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    HStack {
                        Text("Enable Notifications")
                            .font(.roundedBody)
                            .foregroundStyle(Color.textSecondary)

                        Spacer()

                        Toggle("", isOn: $notificationsEnabled)
                            .tint(Color.accent)
                            .labelsHidden()
                    }
                    .padding(.vertical, 4)
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 16))

                // MARK: - Reminder Time
                if notificationsEnabled {
                    VStack(alignment: .leading, spacing: 16) {
                        Label("Reminder Time", systemImage: "clock")
                            .font(.roundedHeadline)
                            .foregroundStyle(Color.textPrimary)

                        DatePicker(
                            "Time",
                            selection: $reminderTime,
                            displayedComponents: .hourAndMinute
                        )
                        .datePickerStyle(.wheel)
                        .labelsHidden()
                        .frame(maxWidth: .infinity)
                        .environment(\.colorScheme, .dark)
                    }
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                }
            }
            .padding()
        }
        .background(Color.appBackground)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Color.appBackground, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("Notifications")
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.textPrimary)
            }
        }
        .onAppear {
            reminderTime = timeFromComponents(hour: manager.reminderHour, minute: manager.reminderMinute)
        }
        .onChange(of: notificationsEnabled) { _, enabled in
            manager.notificationsEnabled = enabled
            if enabled {
                Task { await manager.requestPermission() }
                manager.scheduleDailyReminder(hasLoggedToday: false)
            } else {
                manager.cancelTodayNotification()
            }
        }
        .onChange(of: reminderTime) { _, newTime in
            let comps = Calendar.current.dateComponents([.hour, .minute], from: newTime)
            manager.updateReminderTime(
                hour: comps.hour ?? 20,
                minute: comps.minute ?? 30,
                hasLoggedToday: false
            )
        }
    }

    // MARK: - Helpers

    private func timeFromComponents(hour: Int, minute: Int) -> Date {
        var comps = DateComponents()
        comps.hour = hour
        comps.minute = minute
        return Calendar.current.date(from: comps) ?? Date()
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
    }
}
