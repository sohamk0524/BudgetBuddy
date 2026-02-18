//
//  ExpensesView.swift
//  BudgetBuddy
//
//  Expenses tab with smart sub-categorization and classification
//

import SwiftUI

struct ExpensesView: View {
    @Bindable var viewModel: ExpensesViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    ExpensesSummaryCard(summary: viewModel.summary)

                    // Filter picker
                    Picker("Filter", selection: $viewModel.selectedFilter) {
                        ForEach(ExpenseFilter.allCases, id: \.self) { filter in
                            Text(filter.rawValue).tag(filter)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)
                    .onChange(of: viewModel.selectedFilter) {
                        Task { await viewModel.fetchExpenses() }
                    }

                    // Classification prompt for top unclassified merchant
                    if let merchant = viewModel.unclassifiedMerchants.first {
                        ClassificationPromptCard(merchant: merchant) { classification in
                            Task {
                                await viewModel.classifyMerchant(
                                    merchantName: merchant.merchantName,
                                    classification: classification
                                )
                            }
                        }

                        // AI auto-classify button when multiple unclassified merchants
                        if viewModel.unclassifiedMerchants.count > 1 {
                            Button {
                                Task { await viewModel.autoClassifyWithAI() }
                            } label: {
                                HStack(spacing: 8) {
                                    if viewModel.isAutoClassifying {
                                        ProgressView()
                                            .tint(.white)
                                    } else {
                                        Image(systemName: "sparkles")
                                    }
                                    Text(viewModel.isAutoClassifying ? "Classifying..." : "Auto-Classify All with AI")
                                        .font(.roundedBody)
                                        .fontWeight(.medium)
                                }
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(Color.accent.opacity(viewModel.isAutoClassifying ? 0.5 : 1.0))
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .disabled(viewModel.isAutoClassifying)
                            .padding(.horizontal)
                        }
                    }

                    // Transaction list
                    LazyVStack(spacing: 8) {
                        ForEach(viewModel.transactions) { transaction in
                            ExpenseTransactionRow(transaction: transaction)
                                .onTapGesture {
                                    viewModel.selectedTransaction = transaction
                                    viewModel.showClassificationSheet = true
                                }
                        }

                        if viewModel.hasMore {
                            Button {
                                Task { await viewModel.loadMore() }
                            } label: {
                                Text("Load More")
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.accent)
                                    .frame(maxWidth: .infinity)
                                    .padding()
                            }
                        }
                    }
                    .padding(.horizontal)

                    if viewModel.transactions.isEmpty && !viewModel.isLoading {
                        VStack(spacing: 12) {
                            Image(systemName: "tray")
                                .font(.system(size: 40))
                                .foregroundStyle(Color.textSecondary)
                            Text("No expenses found")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.textSecondary)
                            Text("Link a bank account to see your transactions")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                        }
                        .padding(.top, 40)
                    }
                }
                .padding(.vertical)
            }
            .background(Color.appBackground)
            .navigationTitle("Expenses")
            .toolbarColorScheme(.dark, for: .navigationBar)
            .refreshable {
                await viewModel.refresh()
            }
            .task {
                if viewModel.transactions.isEmpty {
                    await viewModel.refresh()
                }
            }
            .sheet(isPresented: $viewModel.showClassificationSheet) {
                if let transaction = viewModel.selectedTransaction {
                    TransactionClassificationSheet(
                        transaction: transaction,
                        viewModel: viewModel
                    )
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
                }
            }
        }
    }
}

// MARK: - Summary Card

struct ExpensesSummaryCard: View {
    let summary: ExpensesSummary

    private var total: Double {
        summary.totalEssential + summary.totalDiscretionary + summary.totalMixed + summary.totalUnclassified
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Spending Breakdown")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            // Colored segment bar
            if total > 0 {
                GeometryReader { geometry in
                    HStack(spacing: 2) {
                        let width = geometry.size.width - 6 // account for spacing
                        segmentRect(color: .green, fraction: summary.totalEssential / total, width: width)
                        segmentRect(color: Color.danger, fraction: summary.totalDiscretionary / total, width: width)
                        segmentRect(color: .yellow, fraction: summary.totalMixed / total, width: width)
                        segmentRect(color: .gray, fraction: summary.totalUnclassified / total, width: width)
                    }
                }
                .frame(height: 12)
                .clipShape(Capsule())
            }

            // Legend
            HStack(spacing: 16) {
                legendItem(color: .green, label: "Essential", amount: summary.totalEssential)
                legendItem(color: Color.danger, label: "Fun Money", amount: summary.totalDiscretionary)
            }
            HStack(spacing: 16) {
                legendItem(color: .yellow, label: "Mixed", amount: summary.totalMixed)
                legendItem(color: .gray, label: "Unclassified", amount: summary.totalUnclassified)
            }
        }
        .walletCard()
        .padding(.horizontal)
    }

    private func segmentRect(color: Color, fraction: Double, width: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(color)
            .frame(width: max(fraction * width, fraction > 0 ? 4 : 0))
    }

    private func legendItem(color: Color, label: String, amount: Double) -> some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
            Spacer()
            Text("$\(amount, specifier: "%.0f")")
                .font(.roundedCaption)
                .foregroundStyle(Color.textPrimary)
                .monospacedDigit()
        }
    }
}

// MARK: - Classification Prompt Card

struct ClassificationPromptCard: View {
    let merchant: UnclassifiedMerchant
    let onClassify: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "questionmark.circle.fill")
                    .foregroundStyle(Color.accent)
                Text("Classify Merchant")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)
            }

            Text("How would you classify **\(merchant.merchantName)**?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            Text("\(merchant.transactionCount) transactions totaling $\(merchant.totalSpent, specifier: "%.2f")")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)

            HStack(spacing: 10) {
                classifyButton("Essential", color: .green, classification: "essential")
                classifyButton("Fun Money", color: Color.danger, classification: "discretionary")
                classifyButton("Mixed", color: .yellow, classification: "mixed")
            }
        }
        .walletCard()
        .padding(.horizontal)
    }

    private func classifyButton(_ label: String, color: Color, classification: String) -> some View {
        Button {
            onClassify(classification)
        } label: {
            Text(label)
                .font(.roundedCaption)
                .fontWeight(.semibold)
                .foregroundStyle(color == .yellow ? .black : .white)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity)
                .background(color.opacity(0.8))
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }
}

// MARK: - Transaction Row

struct ExpenseTransactionRow: View {
    let transaction: ExpenseTransaction

    private var badgeColor: Color {
        switch transaction.subCategory {
        case "essential": return .green
        case "discretionary": return Color.danger
        case "mixed": return .yellow
        default: return .gray
        }
    }

    private var badgeLabel: String {
        switch transaction.subCategory {
        case "discretionary": return "Fun Money"
        default: return transaction.subCategory.capitalized
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(transaction.merchantName ?? transaction.name)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .lineLimit(1)

                if let dateStr = transaction.date {
                    Text(formatDate(dateStr))
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text("$\(transaction.amount, specifier: "%.2f")")
                    .font(.roundedBody)
                    .fontWeight(.medium)
                    .foregroundStyle(Color.textPrimary)
                    .monospacedDigit()

                Text(badgeLabel)
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(badgeColor == .yellow ? .black : .white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(badgeColor.opacity(0.8))
                    .clipShape(Capsule())
            }
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func formatDate(_ dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: dateStr) else { return dateStr }
        formatter.dateFormat = "MMM d, yyyy"
        return formatter.string(from: date)
    }
}

// MARK: - Transaction Classification Sheet

struct TransactionClassificationSheet: View {
    let transaction: ExpenseTransaction
    @Bindable var viewModel: ExpensesViewModel

    @State private var selectedCategory: String
    @State private var essentialRatio: Double
    @Environment(\.dismiss) private var dismiss

    init(transaction: ExpenseTransaction, viewModel: ExpensesViewModel) {
        self.transaction = transaction
        self.viewModel = viewModel
        _selectedCategory = State(initialValue: transaction.subCategory == "unclassified" ? "mixed" : transaction.subCategory)
        let currentRatio: Double = if let ea = transaction.essentialAmount, transaction.amount > 0 {
            ea / abs(transaction.amount)
        } else {
            0.5
        }
        _essentialRatio = State(initialValue: currentRatio)
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Transaction details
                VStack(spacing: 6) {
                    Text(transaction.merchantName ?? transaction.name)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text("$\(transaction.amount, specifier: "%.2f")")
                        .font(.rounded(.title, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()

                    if let dateStr = transaction.date {
                        Text(dateStr)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                .padding(.top)

                // Category picker
                Picker("Classification", selection: $selectedCategory) {
                    Text("Essential").tag("essential")
                    Text("Fun Money").tag("discretionary")
                    Text("Mixed").tag("mixed")
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .onChange(of: selectedCategory) {
                    switch selectedCategory {
                    case "essential": essentialRatio = 1.0
                    case "discretionary": essentialRatio = 0.0
                    default: break
                    }
                }

                // Slider for mixed
                if selectedCategory == "mixed" {
                    VStack(spacing: 8) {
                        HStack {
                            Text("Essential")
                                .font(.roundedCaption)
                                .foregroundStyle(.green)
                            Spacer()
                            Text("\(Int(essentialRatio * 100))%")
                                .font(.roundedBody)
                                .fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary)
                                .monospacedDigit()
                            Spacer()
                            Text("Fun Money")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.danger)
                        }

                        Slider(value: $essentialRatio, in: 0...1, step: 0.05)
                            .tint(Color.accent)

                        HStack {
                            Text("$\(transaction.amount * essentialRatio, specifier: "%.2f") essential")
                                .font(.roundedCaption)
                                .foregroundStyle(.green)
                            Spacer()
                            Text("$\(transaction.amount * (1 - essentialRatio), specifier: "%.2f") fun money")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.danger)
                        }
                    }
                    .padding(.horizontal)
                }

                Spacer()
            }
            .background(Color.appBackground)
            .navigationTitle("Classify Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(Color.accent)
                }
            }
            .onDisappear {
                let ratio: Double? = selectedCategory == "mixed" ? essentialRatio : nil
                Task {
                    await viewModel.classifyTransaction(
                        transactionId: transaction.id,
                        subCategory: selectedCategory,
                        essentialRatio: ratio
                    )
                }
            }
        }
    }
}

#Preview {
    ExpensesView(viewModel: ExpensesViewModel())
}
