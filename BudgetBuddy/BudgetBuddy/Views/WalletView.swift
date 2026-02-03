//
//  WalletView.swift
//  BudgetBuddy
//
//  The "Wallet" Dashboard - Shows financial overview and quick metrics
//

import SwiftUI

struct WalletView: View {
    @State private var viewModel = WalletViewModel()
    @State private var showingStatementUpload = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Quick Overview Header
                    Text("Financial Overview")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    // Top Row: Net Worth + Safe to Spend
                    HStack(spacing: 16) {
                        NetWorthCard(amount: viewModel.netWorth, hasStatement: viewModel.hasStatement)
                        SafeToSpendCard(amount: viewModel.safeToSpend, hasStatement: viewModel.hasStatement)
                    }

                    // Statement Info Card (if statement exists) or Upload Prompt
                    if viewModel.hasStatement {
                        LinkedStatementCard(
                            statementInfo: viewModel.statementInfo,
                            spendingBreakdown: viewModel.spendingBreakdown,
                            onUploadNew: { showingStatementUpload = true }
                        )
                    } else {
                        UploadStatementPromptCard(onUpload: { showingStatementUpload = true })
                    }

                    // Bottom Row: Small cards
                    HStack(spacing: 16) {
                        AnomaliesCard()
                        GoalProgressCard()
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
            .task {
                await viewModel.fetchFinancialSummary()
            }
            .refreshable {
                await viewModel.refresh()
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

    private func handleFileSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            guard let fileURL = urls.first else { return }
            Task {
                await uploadStatement(fileURL: fileURL)
            }
        case .failure(let error):
            print("File selection error: \(error)")
        }
    }

    private func uploadStatement(fileURL: URL) async {
        guard let userId = AuthManager.shared.authToken else { return }

        // Access security-scoped resource
        guard fileURL.startAccessingSecurityScopedResource() else {
            print("Failed to access security-scoped resource")
            return
        }
        defer { fileURL.stopAccessingSecurityScopedResource() }

        do {
            _ = try await APIService.shared.uploadStatement(fileURL: fileURL, userId: userId)
            // Refresh wallet data after successful upload
            await viewModel.refresh()
        } catch {
            print("Upload error: \(error)")
        }
    }
}

// MARK: - Net Worth Card

struct NetWorthCard: View {
    let amount: Double
    let hasStatement: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(Color.accent)
                Text("Net Worth")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            Spacer()

            if hasStatement {
                Text(formatCurrency(amount))
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)
            } else {
                Text("--")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.textSecondary)

                Text("Upload statement")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$0"
    }
}

// MARK: - Safe to Spend Card

struct SafeToSpendCard: View {
    let amount: Double
    let hasStatement: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "creditcard.fill")
                    .foregroundStyle(Color.accent)
                Text("Safe to Spend")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            Spacer()

            if hasStatement {
                Text(formatCurrency(amount))
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(amount > 0 ? Color.accent : Color.danger)
            } else {
                Text("--")
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.textSecondary)

                Text("Upload statement")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$0"
    }
}

// MARK: - Linked Statement Card

struct LinkedStatementCard: View {
    let statementInfo: StatementInfo?
    let spendingBreakdown: [SpendingCategory]
    let onUploadNew: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Image(systemName: "doc.text.fill")
                    .foregroundStyle(Color.accent)
                Text("Linked Statement")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
                Button(action: onUploadNew) {
                    Text("Update")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.accent)
                }
            }

            // Statement info
            if let info = statementInfo {
                VStack(alignment: .leading, spacing: 4) {
                    Text(info.filename)
                        .font(.system(.subheadline, design: .rounded, weight: .medium))
                        .foregroundStyle(Color.textPrimary)
                        .lineLimit(1)

                    if let period = info.statementPeriod {
                        Text(period)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }

            // Spending breakdown (top 3 categories)
            if !spendingBreakdown.isEmpty {
                Divider()
                    .background(Color.textSecondary.opacity(0.3))

                VStack(spacing: 8) {
                    ForEach(spendingBreakdown.prefix(3)) { category in
                        HStack {
                            Text(category.category)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                            Spacer()
                            Text(formatCurrency(category.amount))
                                .font(.system(.caption, design: .rounded, weight: .medium))
                                .monospacedDigit()
                                .foregroundStyle(Color.textPrimary)
                        }
                    }
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private func formatCurrency(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "$0"
    }
}

// MARK: - Upload Statement Prompt Card

struct UploadStatementPromptCard: View {
    let onUpload: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 32))
                .foregroundStyle(Color.accent)

            Text("Link Your Bank Statement")
                .font(.system(.headline, design: .rounded))
                .foregroundStyle(Color.textPrimary)

            Text("Upload a PDF or CSV statement to see your Net Worth and Safe to Spend")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)

            Button(action: onUpload) {
                Text("Upload Statement")
                    .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    .foregroundStyle(Color.background)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color.accent)
                    .clipShape(Capsule())
            }
            .padding(.top, 4)
        }
        .padding(.vertical, 24)
        .padding(.horizontal)
        .frame(maxWidth: .infinity)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct AnomaliesCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(Color.danger)
                Spacer()
                Text("2")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.danger)
            }

            Spacer()

            Text("Anomalies")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            Text("Unusual spending detected")
                .font(.system(.caption2, design: .rounded))
                .foregroundStyle(Color.textSecondary)
                .lineLimit(2)
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct GoalProgressCard: View {
    private let progress: Double = 0.65

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "target")
                    .foregroundStyle(Color.accent)
                Spacer()
                Text("65%")
                    .font(.roundedHeadline)
                    .monospacedDigit()
                    .foregroundStyle(Color.accent)
            }

            Spacer()

            Text("Vacation Fund")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

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
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Preview

#Preview {
    WalletView()
}
