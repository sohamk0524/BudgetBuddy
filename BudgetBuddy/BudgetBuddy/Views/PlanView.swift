//
//  PlanView.swift
//  BudgetBuddy
//
//  Dedicated view for displaying and managing the spending plan
//

import SwiftUI

struct PlanView: View {
    @Bindable var viewModel: SpendingPlanViewModel

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
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("My Plan")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.textPrimary)
                }
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
            }
            .sheet(isPresented: $viewModel.showQuestionFlow) {
                PlanQuestionFlowView(viewModel: viewModel)
            }
            .task {
                await viewModel.loadExistingPlan()
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

// MARK: - Preview

#Preview {
    PlanView(viewModel: SpendingPlanViewModel())
}
