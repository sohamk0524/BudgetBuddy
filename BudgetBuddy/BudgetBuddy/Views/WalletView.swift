//
//  WalletView.swift
//  BudgetBuddy
//
//  The "Wallet" Dashboard - Shows financial overview and quick metrics
//

import SwiftUI

struct WalletView: View {
    @Bindable var viewModel: SpendingPlanViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Quick Overview Header
                    Text("Financial Overview")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    // Top Row: Large + Medium cards
                    HStack(spacing: 16) {
                        NetWorthCard(plan: viewModel.currentPlan)
                        UpcomingBillsCard(events: viewModel.planInput.upcomingEvents)
                    }

                    // Bottom Row: Small cards
                    HStack(spacing: 16) {
                        AnomaliesCard(warnings: viewModel.currentPlan?.warnings ?? [])
                        GoalProgressCard(goals: viewModel.planInput.savingsGoals)
                    }

                    // Hint to check Plan tab
                    HStack {
                        Image(systemName: "lightbulb.fill")
                            .foregroundStyle(Color.accent)
                        Text("Check the Plan tab to view or create your personalized spending plan")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .padding()
            }
            .background(Color.appBackground)
            .navigationTitle("Wallet")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        AuthManager.shared.signOut()
                    } label: {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
        }
    }
}

// MARK: - Legacy Cards (kept for no-plan state)

struct NetWorthCard: View {
    let plan: SpendingPlan?

    private var netPosition: Double {
        guard let plan = plan else { return 0 }
        return plan.totalIncome - plan.totalExpenses
    }

    private var savingsAmount: Double {
        plan?.totalSavings ?? 0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(Color.accent)
                Text("Monthly Net")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            Spacer()

            if let plan = plan {
                Text(netPosition.formatted(.currency(code: "USD")))
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)

                HStack(spacing: 4) {
                    Image(systemName: savingsAmount >= 0 ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption)
                    Text(savingsAmount.formatted(.currency(code: "USD")))
                        .font(.roundedCaption)
                        .monospacedDigit()
                    Text("to savings")
                        .font(.roundedCaption)
                }
                .foregroundStyle(savingsAmount >= 0 ? Color.accent : Color.danger)
            } else {
                Text("--")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.textSecondary)

                Text("Create a plan to see data")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct UpcomingBillsCard: View {
    let events: [UpcomingEvent]

    private var nextEvent: UpcomingEvent? {
        events
            .filter { $0.date >= Date() }
            .sorted { $0.date < $1.date }
            .first
    }

    private var daysUntilEvent: Int {
        guard let event = nextEvent else { return 0 }
        return Calendar.current.dateComponents([.day], from: Date(), to: event.date).day ?? 0
    }

    private var urgencyProgress: Double {
        guard nextEvent != nil else { return 0 }
        let maxDays = 30.0
        return min(1.0, max(0, 1.0 - Double(daysUntilEvent) / maxDays))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "calendar.badge.clock")
                    .foregroundStyle(Color.danger)
                Text("Upcoming")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            Spacer()

            if let event = nextEvent {
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.cost.formatted(.currency(code: "USD")))
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(Color.textPrimary)

                    Text("\(event.name) in \(daysUntilEvent) days")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                        .lineLimit(1)
                }

                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.appBackground)
                            .frame(height: 4)

                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.danger)
                            .frame(width: geometry.size.width * urgencyProgress, height: 4)
                    }
                }
                .frame(height: 4)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    Text("--")
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.textSecondary)

                    Text("No upcoming events")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct AnomaliesCard: View {
    let warnings: [String]

    private var warningCount: Int {
        warnings.count
    }

    private var firstWarning: String? {
        warnings.first
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: warningCount > 0 ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                    .foregroundStyle(warningCount > 0 ? Color.danger : Color.accent)
                Spacer()
                Text("\(warningCount)")
                    .font(.roundedHeadline)
                    .foregroundStyle(warningCount > 0 ? Color.danger : Color.accent)
            }

            Spacer()

            Text(warningCount > 0 ? "Warnings" : "All Good")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            if let warning = firstWarning {
                Text(warning)
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .lineLimit(2)
            } else {
                Text("No budget warnings")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .lineLimit(2)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct GoalProgressCard: View {
    let goals: [SavingsGoal]

    private var primaryGoal: SavingsGoal? {
        goals.sorted { $0.priority < $1.priority }.first
    }

    private var progress: Double {
        guard let goal = primaryGoal, goal.target > 0 else { return 0 }
        return min(1.0, goal.current / goal.target)
    }

    private var progressPercent: Int {
        Int(progress * 100)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "target")
                    .foregroundStyle(Color.accent)
                Spacer()
                Text("\(progressPercent)%")
                    .font(.roundedHeadline)
                    .monospacedDigit()
                    .foregroundStyle(Color.accent)
            }

            Spacer()

            if let goal = primaryGoal {
                Text(goal.name.isEmpty ? "Savings Goal" : goal.name)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .lineLimit(1)

                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.appBackground)
                            .frame(height: 4)

                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.accent)
                            .frame(width: geometry.size.width * progress, height: 4)
                    }
                }
                .frame(height: 4)
            } else {
                Text("No goals set")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                Text("Add goals in your plan")
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Preview

#Preview {
    WalletView(viewModel: SpendingPlanViewModel())
}
