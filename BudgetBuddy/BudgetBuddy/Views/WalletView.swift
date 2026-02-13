//
//  WalletView.swift
//  BudgetBuddy
//
//  Unified Wallet Dashboard
//  - Plaid/Statement drives numbers
//  - Plan drives goals, warnings, upcoming events
//

import SwiftUI
import UniformTypeIdentifiers

// MARK: - Wallet View

struct WalletView: View {
    @State private var walletViewModel = WalletViewModel()
    @Bindable var planViewModel: SpendingPlanViewModel
    @State private var showingStatementUpload = false
    @State private var showCategoryEditor = false

    private var greeting: String {
        if let name = AuthManager.shared.userName, !name.isEmpty {
            return "Hey, \(name)!"
        }
        return "Financial Overview"
    }

    private var dateSubtitle: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {

                    // MARK: - Header
                    VStack(alignment: .leading, spacing: 4) {
                        Text(greeting)
                            .font(.roundedTitle)
                            .foregroundStyle(Color.textPrimary)

                        Text(dateSubtitle)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                    // MARK: - Top Row
                    HStack(spacing: 16) {
                        NetWorthCard(
                            amount: walletViewModel.netWorth,
                            hasData: walletViewModel.hasData
                        )

                        WalletSafeToSpendCard(
                            amount: walletViewModel.safeToSpend,
                            hasData: walletViewModel.hasData
                        )
                    }

                    // MARK: - Top Expenses
                    TopExpensesCard(
                        topExpenses: walletViewModel.topExpenses,
                        source: walletViewModel.expenseSource,
                        onCustomize: { showCategoryEditor = true }
                    )

                    // MARK: - Goal Progress (all goals)
                    GoalProgressSection(
                        goals: planViewModel.planInput.savingsGoals
                    )

                    // MARK: - Smart Nudges
                    SmartNudgesCard(
                        nudges: walletViewModel.nudges
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
                    NavigationLink {
                        ProfileView()
                    } label: {
                        Image(systemName: "person.circle")
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
            .task {
                await walletViewModel.refresh()
            }
            .refreshable {
                await walletViewModel.refresh()
            }
            .sheet(isPresented: $showCategoryEditor) {
                CategoryEditorSheet(
                    availableCategories: walletViewModel.topExpenses.map { $0.category },
                    selectedCategories: $walletViewModel.customCategories,
                    onSave: { categories in
                        Task {
                            await walletViewModel.updateCategoryPreferences(categories)
                        }
                    }
                )
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
    let hasData: Bool

    var body: some View {
        card(
            title: "Net Worth",
            icon: "chart.line.uptrend.xyaxis",
            value: hasData ? format(amount) : "--",
            subtitle: hasData ? nil : "Link bank account"
        )
    }
}

struct WalletSafeToSpendCard: View {
    let amount: Double
    let hasData: Bool

    var body: some View {
        card(
            title: "Safe to Spend",
            icon: "creditcard.fill",
            value: hasData ? format(amount) : "--",
            valueColor: amount >= 0 ? Color.accent : Color.danger,
            subtitle: hasData ? nil : "Link bank account"
        )
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
            .lineLimit(1)
            .minimumScaleFactor(0.5)

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
        planViewModel: SpendingPlanViewModel()
    )
}
