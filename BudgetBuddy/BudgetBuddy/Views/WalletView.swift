//
//  WalletView.swift
//  BudgetBuddy
//
//  The "Wallet" Dashboard - Shows spending plan or prompts to create one
//

import SwiftUI

struct WalletView: View {
    @State private var viewModel = SpendingPlanViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if viewModel.isLoading {
                        loadingView
                    } else if viewModel.hasPlan, let plan = viewModel.currentPlan {
                        planDashboard(plan: plan)
                    } else {
                        noPlanView
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
                    if viewModel.hasPlan {
                        Button {
                            viewModel.startQuestionFlow()
                        } label: {
                            Image(systemName: "arrow.clockwise")
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        AuthManager.shared.signOut()
                    } label: {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
            .sheet(isPresented: $viewModel.showQuestionFlow) {
                PlanQuestionFlowView(viewModel: viewModel)
            }
            .task {
                await viewModel.loadExistingPlan()
            }
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .tint(Color.accent)
            Text("Loading your plan...")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    // MARK: - No Plan View

    private var noPlanView: some View {
        VStack(spacing: 24) {
            GeneratePlanCard {
                viewModel.startQuestionFlow()
            }

            // Show legacy cards below the CTA
            Text("Quick Overview")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            // Top Row: Large + Medium cards
            HStack(spacing: 16) {
                NetWorthCard()
                UpcomingBillsCard()
            }

            // Bottom Row: Small cards
            HStack(spacing: 16) {
                AnomaliesCard()
                GoalProgressCard()
            }
        }
    }

    // MARK: - Plan Dashboard

    @ViewBuilder
    private func planDashboard(plan: SpendingPlan) -> some View {
        VStack(spacing: 16) {
            // Hero: Safe to Spend
            SafeToSpendCard(
                amount: plan.safeToSpend,
                daysRemaining: plan.daysRemaining,
                budgetUsedPercent: plan.budgetUsedPercent
            )

            // Summary text
            if !plan.summary.isEmpty {
                Text(plan.summary)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            // Budget Breakdown
            BudgetBreakdownCard(
                categories: plan.categoryAllocations,
                totalIncome: plan.totalIncome
            )

            // Savings Progress
            SavingsProgressCard(plan: plan)

            // Recommendations
            if !plan.recommendations.isEmpty {
                RecommendationsCard(recommendations: plan.recommendations)
            }

            // Warnings
            if !plan.warnings.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(Color.danger)
                        Text("Warnings")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.danger)
                    }

                    ForEach(plan.warnings, id: \.self) { warning in
                        Text(warning)
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.danger.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            // Edit button
            Button {
                viewModel.startQuestionFlow()
            } label: {
                HStack {
                    Image(systemName: "pencil")
                    Text("Update Your Plan")
                }
                .font(.roundedBody)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
            }
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

// MARK: - Legacy Cards (kept for no-plan state)

struct NetWorthCard: View {
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

            Text("$24,850")
                .font(.system(size: 28, weight: .bold, design: .rounded))
                .monospacedDigit()
                .foregroundStyle(Color.textPrimary)

            HStack(spacing: 4) {
                Image(systemName: "arrow.up.right")
                    .font(.caption)
                Text("+$1,240")
                    .font(.roundedCaption)
                    .monospacedDigit()
                Text("this month")
                    .font(.roundedCaption)
            }
            .foregroundStyle(Color.accent)
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

struct UpcomingBillsCard: View {
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

            VStack(alignment: .leading, spacing: 4) {
                Text("$1,200")
                    .font(.system(size: 24, weight: .bold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)

                Text("Rent due in 5 days")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.appBackground)
                        .frame(height: 4)

                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.danger)
                        .frame(width: geometry.size.width * 0.8, height: 4)
                }
            }
            .frame(height: 4)
        }
        .padding()
        .frame(maxWidth: .infinity, minHeight: 160, alignment: .leading)
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
