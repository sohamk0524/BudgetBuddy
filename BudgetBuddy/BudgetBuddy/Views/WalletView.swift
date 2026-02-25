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
    @Bindable var walletViewModel: WalletViewModel
    @Bindable var planViewModel: SpendingPlanViewModel
    @State private var showingStatementUpload = false
    @State private var showCategoryEditor = false
    @State private var showVoiceRecording = false
    @State private var voiceViewModel = VoiceTransactionViewModel()

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

    /// Top expenses filtered by user's custom category preferences.
    /// Shows 3 by default; shows however many the user picked when customized.
    private var filteredTopExpenses: [TopExpense] {
        let prefs = walletViewModel.customCategories
        if prefs.isEmpty {
            return Array(walletViewModel.topExpenses.prefix(3))
        }
        return walletViewModel.topExpenses.filter { prefs.contains($0.category) }
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

                    // MARK: - Voice Transaction
                    VoiceTransactionTile { showVoiceRecording = true }

                    // MARK: - Top Expenses
                    TopExpensesCard(
                        topExpenses: filteredTopExpenses,
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
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("Wallet")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.textPrimary)
                }
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
                            await walletViewModel.fetchTopExpenses()
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
            .sheet(isPresented: $showVoiceRecording) {
                VoiceTransactionFlowView(viewModel: voiceViewModel) {
                    showVoiceRecording = false
                    Task { await walletViewModel.refresh() }
                }
            }
            .onChange(of: voiceViewModel.state) { _, newState in
                if newState == .success {
                    Task { await walletViewModel.refresh() }
                }
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
    let abs = abs(value)
    let sign = value < 0 ? "-" : ""
    if abs >= 1_000_000 {
        return "\(sign)$\(String(format: "%.1fM", abs / 1_000_000))"
    } else if abs >= 10_000 {
        return "\(sign)$\(String(format: "%.1fk", abs / 1_000))"
    }
    return value.formatted(.currency(code: "USD"))
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
    .walletCard()
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
