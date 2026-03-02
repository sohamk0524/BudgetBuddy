## Overview
I am building an iOS app called BudgetBuddy using SwiftUI (iOS 17+).

I want to integrate daily local push notifications that remind users to log transactions, triggering/cancelling reminders based on transaction activity inside ExpensesViewModel.

The reminder should:
- Trigger once daily at a configurable time (default: 8:30 PM)
- Only send if the user has NOT logged a transaction that day
- Automatically cancel that day's reminder if a transaction is logged
- Rotate between multiple reminder messages
- Be structured in a scalable way so I can add streak logic later

## Implementation Requirements
### Create a NotificationManager

Create a NotificationManager class that:
- Uses UNUserNotificationCenter
- Requests notification permission
- Schedules a daily reminder
- Cancels today’s reminder
- Reschedules when reminder time changes
- Rotates reminder messages randomly (avoid repeating the same one consecutively)
- Use modern Swift (async/await if appropriate).

### Transaction Detection Logic

Since I already have transactions: [ExpenseTransaction] in my ViewModel, implement a helper:

func hasLoggedTransactionToday() -> Bool

Assume ExpenseTransaction.date is an ISO string or Date — handle appropriately.

This function should:
- Compare transaction date to today’s date (Calendar.current.isDateInToday)
- Return true if at least one transaction exists for today

### Integration with ExpensesViewModel

Modify my ViewModel to:

Call NotificationManager.cancelTodayNotification() whenever:
- A transaction is classified
- A new transaction appears after refresh
- After refresh(), re-check if a notification should be scheduled
- Specifically integrate inside:
    - classifyTransaction
    - classifyViaSwipe
    - refresh()
    - fetchExpenses()

Make sure logic does NOT create duplicate scheduled notifications.

### ReminderSettings

Create a lightweight settings mode using:

@AppStorage for:
- reminderTime
- notificationsEnabled

Include:
- Default time of 8:30 PM
- Function to update and reschedule when time changes

### SwiftUI App Integration

Show:
- How to initialize NotificationManager in the main App struct
- Where to request permission (on first launch)
- Example SettingsView with:
    - Toggle for notifications
    - TimePicker for reminder time
    - Changing the time should automatically reschedule notifications.

### Scheduling Logic Details

Notification should:
- Schedule once per day using UNCalendarNotificationTrigger
- Before scheduling, check hasLoggedTransactionToday()
    - If true → do not schedule
    - If false → schedule

Also:
- Prevent duplicate pending notifications
- Use a consistent identifier like "dailyExpenseReminder"

### Future-Proofing

Structure NotificationManager so that later I can:
- Change message content dynamically
- Add streak-based conditions
- Add challenge-based notifications

Keep message generation in a separate function like:

private func generateReminderMessage() -> String

## Output Format

Please provide:

- Full NotificationManager implementation
- Modifications to ExpensesViewModel
- ReminderSettings model
- SwiftUI App entry point example
- SettingsView example
- Explanation of scheduling flow

Use modern Swift and iOS 17 best practices.
Do NOT use deprecated APIs.
Keep code clean and production-ready.
