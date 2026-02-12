//
//  PlanView.swift
//  BudgetBuddy
//
//  Dedicated view for displaying and managing the spending plan
//

import SwiftUI

struct PlanView: View {
    @Bindable var viewModel: SpendingPlanViewModel
    @Bindable var walletViewModel: WalletViewModel

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
            .navigationTitle("My Plan")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if viewModel.hasPlan {
                        Button {
                            viewModel.startQuestionFlow()
                        } label: {
                            Image(systemName: "pencil")
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
            }
            .sheet(isPresented: $viewModel.showQuestionFlow) {
                PlanQuestionFlowView(viewModel: viewModel)
            }
            .sheet(isPresented: $viewModel.showAddGoalSheet) {
                AddSavingsGoalSheet { name, target in
                    viewModel.addUserSavingsGoal(name: name, target: target)
                }
            }
            .sheet(item: $viewModel.selectedGoal) { goal in
                UpdateSavedAmountSheet(
                    goal: goal,
                    onSave: { id, amount in
                        viewModel.updateSavedAmount(id: id, additionalAmount: amount)
                    },
                    onDelete: { id in
                        viewModel.deleteUserSavingsGoal(id: id)
                    }
                )
            }
            .task {
                viewModel.loadSavingsGoals()
                await viewModel.loadExistingPlan()
                await walletViewModel.fetchFinancialSummary()
            }
            .onChange(of: viewModel.showQuestionFlow) { oldValue, newValue in
                // Refresh plan when question flow is dismissed (after generating)
                if oldValue == true && newValue == false && viewModel.currentPlan != nil {
                    // Plan was just generated, view will auto-update via @Observable
                }
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
            Spacer()

            Image(systemName: "doc.text.fill")
                .font(.system(size: 64))
                .foregroundStyle(Color.accent.opacity(0.6))

            VStack(spacing: 8) {
                Text("No Spending Plan Yet")
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textPrimary)

                Text("Create a personalized budget plan based on your income, expenses, and goals.")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }

            Button {
                viewModel.startQuestionFlow()
            } label: {
                HStack {
                    Image(systemName: "sparkles")
                    Text("Generate My Plan")
                }
                .font(.roundedHeadline)
                .foregroundStyle(Color.appBackground)
                .frame(maxWidth: .infinity)
                .padding()
            }
            .background(Color.accent)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .padding(.horizontal, 32)

            Spacer()
        }
        .frame(minHeight: 400)
    }

    // MARK: - Plan Dashboard

    @ViewBuilder
    private func planDashboard(plan: SpendingPlan) -> some View {
        // Calculate disposable income (income minus fixed expenses)
        let fixedExpenses = plan.categoryAllocations.first(where: { $0.id == "fixed" })?.amount ?? 0
        let savingsAmount = plan.categoryAllocations.first(where: { $0.id == "savings" })?.amount ?? 0
        let eventsAmount = plan.categoryAllocations.first(where: { $0.id == "events" })?.amount ?? 0
        let disposableIncome = plan.totalIncome - fixedExpenses - savingsAmount - eventsAmount

        // Calculate amount spent based on budget used percent
        let amountSpent = (plan.budgetUsedPercent / 100) * disposableIncome

        VStack(spacing: 16) {

            // ── SECTION 1: Spending Summary ──

            // Weekly Spending Heatmap
            WeeklySpendingHeatmap(data: viewModel.weeklySpendingData)

            // Income/Expense Waterfall
            IncomeExpenseWaterfall(
                totalIncome: plan.totalIncome,
                categories: plan.categoryAllocations
            )

            // Month-to-Month Spending Delta
            MonthSpendingDeltaView(
                thisMonthData: thisMonthSpendingData(plan: plan),
                lastMonthData: viewModel.lastMonthSpending
            )

            // Semester Overview
            SemesterOverviewChart(data: viewModel.semesterMonthlyTotals)

            // Semester Cost Breakdown
            SemesterCostBreakdownCard(data: viewModel.semesterCostBreakdown)

            // ── SECTION 2: Budget Performance ──

            // Spending Progress Bar (Hero)
            SpendingProgressCard(
                disposableIncome: disposableIncome,
                amountSpent: amountSpent,
                daysRemaining: plan.daysRemaining
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

            // Actual vs Planned
            ActualVsPlannedChart(
                plannedCategories: plan.categoryAllocations,
                actualSpending: walletViewModel.spendingBreakdown
            )

            // User Savings Goals
            UserSavingsGoalsCard(goals: viewModel.userSavingsGoals) { goal in
                viewModel.selectedGoal = goal
            }

            // Add Savings Goal button
            Button {
                viewModel.showAddGoalSheet = true
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Savings Goal")
                }
                .font(.roundedHeadline)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
            }
            .background(Color.accent.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))

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
        }
    }

    // MARK: - This Month Spending Data

    /// Uses wallet spending breakdown if available, otherwise falls back to plan allocations
    private func thisMonthSpendingData(plan: SpendingPlan) -> [(category: String, amount: Double)] {
        if !walletViewModel.spendingBreakdown.isEmpty {
            return walletViewModel.spendingBreakdown.map { ($0.category, $0.amount) }
        }
        // Fallback: use plan category allocations
        return plan.categoryAllocations
            .filter { $0.amount > 0 }
            .flatMap { category -> [(category: String, amount: Double)] in
                if let items = category.items, !items.isEmpty {
                    return items.filter { $0.amount > 0 }.map { ($0.name, $0.amount) }
                }
                return [(category.name, category.amount)]
            }
    }
}

// MARK: - Preview

#Preview {
    PlanView(viewModel: SpendingPlanViewModel(), walletViewModel: WalletViewModel())
}
