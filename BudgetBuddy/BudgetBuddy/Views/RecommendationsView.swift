//
//  RecommendationsView.swift
//  BudgetBuddy
//
//  Dashboard tab showing safe-to-spend and AI-generated financial tips.
//

import SwiftUI

@MainActor
struct RecommendationsView: View {
    @State private var viewModel = RecommendationsViewModel()

    var body: some View {
        ZStack {
            Color.appBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // Hero — safe-to-spend pill
                PulseHeaderView(
                    safeToSpend: viewModel.dailySafeToSpend,
                    isHealthy: viewModel.isHealthy,
                    status: viewModel.statusDisplayText
                )

                // Money Moves or category indicator
                if viewModel.activeCategory != nil {
                    categoryChip
                } else if !viewModel.moneyMovesCards.isEmpty {
                    moneyMovesRow
                }

                // Content
                if viewModel.isLoading && viewModel.recommendations.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(Color.accent)
                    Spacer()
                } else if viewModel.displayedRecommendations.isEmpty && viewModel.activeCategory != nil {
                    Spacer()
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 32))
                            .foregroundStyle(Color.textSecondary.opacity(0.6))
                        Text("No \(viewModel.activeCategoryDisplayName.lowercased()) tips yet")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                        Text("Tap Refresh to generate new recommendations.")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary.opacity(0.7))
                    }
                    Spacer()
                } else if viewModel.displayedRecommendations.isEmpty && viewModel.activeCategory == nil {
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
            await viewModel.loadSpendingSummary()
        }
    }

    // MARK: - Recommendations List

    private var recommendationsList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(viewModel.displayedRecommendations) { item in
                    RecommendationCardView(item: item)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    // MARK: - Money Moves

    private var moneyMovesRow: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Money Moves")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .padding(.leading, 16)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(viewModel.moneyMovesCards) { card in
                        MoneyMovesCardView(card: card) {
                            viewModel.selectCategory(card.category)
                        }
                    }
                }
                .padding(.horizontal, 16)
            }
        }
        .padding(.vertical, 10)
    }

    private var categoryChip: some View {
        HStack(spacing: 8) {
            Button {
                viewModel.clearCategoryFilter()
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: viewModel.activeCategoryIcon)
                        .font(.system(size: 12, weight: .semibold))
                    Text(viewModel.activeCategoryDisplayName)
                        .font(.system(.subheadline, design: .rounded, weight: .semibold))
                    Image(systemName: "xmark")
                        .font(.system(size: 10, weight: .bold))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Color.accent)
                .foregroundStyle(Color.appBackground)
                .clipShape(Capsule())
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
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

            Text("Tap \"Refresh\" to get personalized financial tips based on your spending and budget.")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        HStack {
            Spacer()
            Button {
                Task { await viewModel.generateRecommendations() }
            } label: {
                HStack(spacing: 6) {
                    if viewModel.isGenerating && viewModel.activeCategory == nil {
                        ProgressView()
                            .tint(Color.accent)
                            .controlSize(.mini)
                    } else {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 12, weight: .semibold))
                    }
                    Text("Refresh")
                        .font(.system(.subheadline, design: .rounded, weight: .medium))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Color.accent.opacity(0.15))
                .foregroundStyle(Color.accent)
                .clipShape(Capsule())
            }
            .disabled(viewModel.isGenerating)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
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

// MARK: - Money Moves Card

struct MoneyMovesCardView: View {
    let card: MoneyMovesCard
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 8) {
                // Icon + category
                HStack(spacing: 6) {
                    Image(systemName: card.icon)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Color.accent)
                    Text(card.category.prefix(1).uppercased() + card.category.dropFirst())
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }

                // Amount
                Text("$\(Int(card.amount))")
                    .font(.rounded(.title2, weight: .bold))
                    .monospacedDigit()
                    .foregroundStyle(Color.textPrimary)

                // Context
                Text("\(card.transactionCount) transaction\(card.transactionCount == 1 ? "" : "s")")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                // CTA
                Text("Get tips →")
                    .font(.system(.caption, design: .rounded, weight: .semibold))
                    .foregroundStyle(Color.appBackground)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Color.accent)
                    .clipShape(Capsule())
            }
            .frame(width: 150, alignment: .leading)
            .padding(14)
            .background(Color.surface)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(Color.accent.opacity(0.15), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Recommendation Card

struct RecommendationCardView: View {
    let item: RecommendationItem
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
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

                    if let context = item.spendingContext {
                        Text(context)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    if let savings = item.potentialSavings, savings > 0 {
                        Text("Save ~$\(Int(savings))")
                            .font(.system(.caption, design: .rounded, weight: .semibold))
                            .foregroundStyle(Color.accent)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(Color.accent.opacity(0.12))
                            .clipShape(Capsule())
                            .padding(.top, 2)
                    }
                }

                Spacer(minLength: 0)

                if item.isExpandable {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(Color.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                }
            }

            if isExpanded {
                expandedContent
            }
        }
        .cardStyle()
        .contentShape(Rectangle())
        .onTapGesture {
            guard item.isExpandable else { return }
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                isExpanded.toggle()
            }
        }
    }

    @ViewBuilder
    private var expandedContent: some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()
                .overlay(Color.textSecondary.opacity(0.3))
                .padding(.top, 8)

            if let steps = item.steps {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                        Text("\(index + 1). \(step)")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }

            HStack(spacing: 8) {
                if let horizon = item.timeHorizon {
                    Text(horizon)
                        .font(.system(.caption2, design: .rounded, weight: .medium))
                        .foregroundStyle(Color.textSecondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.textSecondary.opacity(0.15))
                        .clipShape(Capsule())
                }

                if let urlString = item.link, let url = URL(string: urlString) {
                    Link(item.linkTitle ?? "Learn More", destination: url)
                        .font(.system(.caption, design: .rounded, weight: .semibold))
                        .foregroundStyle(Color.accent)
                }
            }
        }
        .transition(.opacity.combined(with: .move(edge: .top)))
    }
}

// MARK: - Preview

#Preview {
    RecommendationsView()
}
