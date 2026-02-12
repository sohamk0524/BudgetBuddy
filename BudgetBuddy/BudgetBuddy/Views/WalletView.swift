//
//  WalletView.swift
//  BudgetBuddy
//
//  Unified Wallet Dashboard
//  - Statement drives numbers
//  - Plan drives goals, warnings, upcoming events
//

import SwiftUI
import UniformTypeIdentifiers

// MARK: - Wallet View

struct WalletView: View {
    @Bindable var walletViewModel: WalletViewModel
    @Bindable var planViewModel: SpendingPlanViewModel
    @State private var showingStatementUpload = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {

                    // Header
                    Text("Financial Overview")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    // MARK: - Top Row (Statement-driven)
                    HStack(spacing: 16) {
                        NetWorthCard(
                            amount: walletViewModel.netWorth,
                            hasStatement: walletViewModel.hasStatement
                        )

                        WalletSafeToSpendCard(
                            amount: walletViewModel.safeToSpend,
                            hasStatement: walletViewModel.hasStatement
                        )
                    }

                    // MARK: - Statement Section
                    if walletViewModel.hasStatement {
                        LinkedStatementCard(
                            statementInfo: walletViewModel.statementInfo,
                            spendingBreakdown: walletViewModel.spendingBreakdown,
                            onUploadNew: { showingStatementUpload = true }
                        )
                    } else {
                        UploadStatementPromptCard {
                            showingStatementUpload = true
                        }
                    }

                    // MARK: - Plan-driven Cards
                    HStack(spacing: 16) {
                        AnomaliesCard(
                            warnings: planViewModel.currentPlan?.warnings ?? []
                        )

                        GoalProgressCard(
                            goals: planViewModel.planInput.savingsGoals
                        )
                    }

                    // MARK: - Upcoming Bills
                    UpcomingBillsCard(
                        events: planViewModel.planInput.upcomingEvents
                    )

                    // MARK: - Hint
                    if planViewModel.currentPlan == nil {
                        HintCard(
                            text: "Create a plan to unlock forecasts, goals, and budget warnings"
                        )
                    }
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
            .task {
                await walletViewModel.fetchFinancialSummary()
            }
            .refreshable {
                await walletViewModel.refresh()
            }
            .fileImporter(
                isPresented: $showingStatementUpload,
                allowedContentTypes: [.pdf, .commaSeparatedText],
                allowsMultipleSelection: false
            ) { result in
                handleFileSelection(result)
            }
        }
    }

    // MARK: - File Handling

    private func handleFileSelection(_ result: Result<[URL], Error>) {
        guard case .success(let urls) = result,
              let fileURL = urls.first else { return }

        Task {
            await uploadStatement(fileURL: fileURL)
        }
    }

    private func uploadStatement(fileURL: URL) async {
        guard let userId = AuthManager.shared.authToken else { return }

        guard fileURL.startAccessingSecurityScopedResource() else { return }
        defer { fileURL.stopAccessingSecurityScopedResource() }

        do {
            _ = try await APIService.shared.uploadStatement(
                fileURL: fileURL,
                userId: userId
            )
            await walletViewModel.refresh()
        } catch {
            print("Statement upload failed: \(error)")
        }
    }
}

//
// MARK: - Cards
//

struct NetWorthCard: View {
    let amount: Double
    let hasStatement: Bool

    var body: some View {
        card(
            title: "Net Worth",
            icon: "chart.line.uptrend.xyaxis",
            value: hasStatement ? format(amount) : "--",
            subtitle: hasStatement ? nil : "Upload statement"
        )
    }
}

struct WalletSafeToSpendCard: View {
    let amount: Double
    let hasStatement: Bool

    var body: some View {
        card(
            title: "Safe to Spend",
            icon: "creditcard.fill",
            value: hasStatement ? format(amount) : "--",
            valueColor: amount >= 0 ? Color.accent : Color.danger,
            subtitle: hasStatement ? nil : "Upload statement"
        )
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

    private var daysUntil: Int {
        guard let event = nextEvent else { return 0 }
        return Calendar.current.dateComponents([.day], from: Date(), to: event.date).day ?? 0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Upcoming", systemImage: "calendar.badge.clock")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            Spacer()

            if let event = nextEvent {
                Text(event.cost.formatted(.currency(code: "USD")))
                    .font(.system(size: 24, weight: .bold, design: .rounded))

                Text("\(event.name) in \(daysUntil) days")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            } else {
                Text("--")
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                Text("No upcoming bills")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .walletCard(minHeight: 140)
    }
}

struct AnomaliesCard: View {
    let warnings: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: warnings.isEmpty ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .foregroundStyle(warnings.isEmpty ? Color.accent : Color.danger)
                Spacer()
                Text("\(warnings.count)")
                    .font(.roundedHeadline)
                    .foregroundStyle(warnings.isEmpty ? Color.accent : Color.danger)
            }

            Spacer()

            Text(warnings.isEmpty ? "All Good" : "Warnings")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            Text(warnings.first ?? "No budget warnings")
                .font(.system(.caption2, design: .rounded))
                .foregroundStyle(Color.textSecondary)
                .lineLimit(2)
        }
        .walletCard(minHeight: 120)
    }
}

struct GoalProgressCard: View {
    let goals: [SavingsGoal]

    private var primary: SavingsGoal? {
        goals.sorted { $0.priority < $1.priority }.first
    }

    private var progress: Double {
        guard let goal = primary, goal.target > 0 else { return 0 }
        return min(1, goal.current / goal.target)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "target")
                    .foregroundStyle(Color.accent)
                Spacer()
                Text("\(Int(progress * 100))%")
                    .font(.roundedHeadline)
            }

            Spacer()

            if let goal = primary {
                Text(goal.name)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                ProgressBar(progress: progress)
            } else {
                Text("No goals set")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .walletCard(minHeight: 120)
    }
}

//
// MARK: - Statement Cards
//

struct LinkedStatementCard: View {
    let statementInfo: StatementInfo?
    let spendingBreakdown: [SpendingCategory]
    let onUploadNew: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("Linked Statement", systemImage: "doc.text.fill")
                Spacer()
                Button("Update", action: onUploadNew)
            }
            .font(.roundedCaption)
            .foregroundStyle(Color.textSecondary)

            if let info = statementInfo {
                Text(info.filename)
                    .font(.system(.subheadline, design: .rounded, weight: .medium))
            }

            ForEach(spendingBreakdown.prefix(3)) { category in
                HStack {
                    Text(category.category)
                    Spacer()
                    Text(category.amount.formatted(.currency(code: "USD")))
                }
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
            }
        }
        .walletCard()
    }
}

struct UploadStatementPromptCard: View {
    let onUpload: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 32))
                .foregroundStyle(Color.accent)

            Text("Link Your Bank Statement")
                .font(.headline)

            Text("Upload a PDF or CSV to unlock your financial insights")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)

            Button("Upload Statement", action: onUpload)
                .padding(.horizontal, 20)
                .padding(.vertical, 10)
                .background(Color.accent)
                .clipShape(Capsule())
        }
        .walletCard()
    }
}

//
// MARK: - Helpers
//

struct HintCard: View {
    let text: String

    var body: some View {
        HStack {
            Image(systemName: "lightbulb.fill")
                .foregroundStyle(Color.accent)
            Text(text)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct ProgressBar: View {
    let progress: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.appBackground)
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.accent)
                    .frame(width: geo.size.width * progress)
            }
        }
        .frame(height: 4)
    }
}

private func format(_ value: Double) -> String {
    value.formatted(.currency(code: "USD"))
}

private func card(
    title: String,
    icon: String,
    value: String,
    valueColor: Color = .textPrimary,
    subtitle: String?
) -> some View {
    VStack(alignment: .leading, spacing: 12) {
        Label(title, systemImage: icon)
            .font(.roundedCaption)
            .foregroundStyle(Color.textSecondary)

        Spacer()

        Text(value)
            .font(.system(size: 28, weight: .bold, design: .rounded))
            .foregroundStyle(valueColor)

        if let subtitle {
            Text(subtitle)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
    }
    .walletCard(minHeight: 140)
}

extension View {
    func walletCard(minHeight: CGFloat? = nil) -> some View {
        self
            .padding()
            .frame(maxWidth: .infinity, minHeight: minHeight, alignment: .leading)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

//
// MARK: - Preview
//

#Preview {
    WalletView(
        walletViewModel: WalletViewModel(),
        planViewModel: SpendingPlanViewModel()
    )
}
