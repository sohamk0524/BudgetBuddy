//
//  RecommendationsView.swift
//  BudgetBuddy
//
//  Dashboard tab showing safe-to-spend and AI-generated financial tips.
//

import SwiftUI

struct RecommendationsView: View {
    @State private var viewModel = RecommendationsViewModel()

    var body: some View {
        ZStack {
            Color.appBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // Hero — safe-to-spend pill
                PulseHeaderView(
                    safeToSpend: viewModel.safeToSpend,
                    isHealthy: viewModel.isHealthy,
                    status: viewModel.statusDisplayText
                )

                // Content
                if viewModel.isLoading && viewModel.recommendations.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(Color.accent)
                    Spacer()
                } else if viewModel.recommendations.isEmpty {
                    emptyState
                } else {
                    recommendationsList
                }

                // Action buttons pinned to bottom
                actionButtons
            }

            // Error banner
            if let error = viewModel.errorMessage {
                VStack {
                    errorBanner(error)
                    Spacer()
                }
                .padding(.top, 8)
            }
        }
        .task {
            await viewModel.loadRecommendations()
        }
    }

    // MARK: - Recommendations List

    private var recommendationsList: some View {
        ScrollView {
            // Summary
            if !viewModel.summary.isEmpty {
                Text(viewModel.summary)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 20)
                    .padding(.top, 12)
            }

            LazyVStack(spacing: 12) {
                ForEach(viewModel.recommendations) { item in
                    RecommendationCardView(item: item)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Spacer()

            Image(systemName: "lightbulb")
                .font(.system(size: 48))
                .foregroundStyle(Color.accent.opacity(0.6))

            Text("No recommendations yet")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Tap \"Generate Recommendations\" to get personalized financial tips based on your spending and budget.")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: 10) {
            // Primary: Generate Recommendations
            Button {
                Task { await viewModel.generateRecommendations() }
            } label: {
                HStack(spacing: 8) {
                    if viewModel.isGenerating {
                        ProgressView()
                            .tint(.white)
                            .controlSize(.small)
                    } else {
                        Image(systemName: "lightbulb.fill")
                    }
                    Text("Generate Recommendations")
                        .font(.roundedHeadline)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.accent)
                .foregroundStyle(Color.appBackground)
                .clipShape(Capsule())
            }
            .disabled(viewModel.isGenerating)

            // Secondary row
            HStack(spacing: 10) {
                Button {
                    Task { await viewModel.generateRecommendations(action: "budget_balance") }
                } label: {
                    Text("Check Budget")
                        .font(.roundedCaption)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .foregroundStyle(Color.accent)
                        .overlay(Capsule().strokeBorder(Color.accent, lineWidth: 1))
                }
                .disabled(viewModel.isGenerating)

                Button {
                    Task { await viewModel.generateRecommendations(action: "spending_habits") }
                } label: {
                    Text("Analyze Spending")
                        .font(.roundedCaption)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .foregroundStyle(Color.accent)
                        .overlay(Capsule().strokeBorder(Color.accent, lineWidth: 1))
                }
                .disabled(viewModel.isGenerating)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color.surface)
    }

    // MARK: - Error Banner

    private func errorBanner(_ message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(Color.danger)
            Text(message)
                .font(.roundedCaption)
                .foregroundStyle(Color.textPrimary)
            Spacer()
            Button {
                viewModel.errorMessage = nil
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding(12)
        .background(Color.danger.opacity(0.15))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 16)
    }
}

// MARK: - Recommendation Card

struct RecommendationCardView: View {
    let item: RecommendationItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Icon
            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: item.icon ?? "lightbulb")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Color.accent)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(item.title)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Text(item.description)
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                if let savings = item.potentialSavings, savings > 0 {
                    Text("Save ~$\(Int(savings))")
                        .font(.system(.caption2, design: .rounded, weight: .semibold))
                        .foregroundStyle(Color.accent)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.accent.opacity(0.12))
                        .clipShape(Capsule())
                        .padding(.top, 2)
                }
            }

            Spacer(minLength: 0)
        }
        .cardStyle()
    }
}

// MARK: - Preview

#Preview {
    RecommendationsView()
}
