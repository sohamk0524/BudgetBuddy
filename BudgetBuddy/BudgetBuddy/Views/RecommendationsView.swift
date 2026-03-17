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
    @State private var loadingStepIndex = 0

    private var loadingStepLabels: [String] {
        if let cat = viewModel.activeCategory {
            let name = cat.prefix(1).uppercased() + cat.dropFirst()
            return [
                "Reviewing \(name.lowercased()) transactions",
                "Analyzing your \(name.lowercased()) spending",
                "Finding \(name.lowercased()) deals nearby",
                "Building \(name.lowercased()) savings tips",
            ]
        }
        return [
            "Fetching your transactions",
            "Checking spending status",
            "Searching for local deals",
            "Crafting personalized tips",
        ]
    }
    private let loadingStepIcons = ["creditcard", "chart.bar.fill", "mappin.and.ellipse", "lightbulb.fill"]
    private var loadingStepIcon: String { loadingStepIcons[min(loadingStepIndex, loadingStepIcons.count - 1)] }

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

                // Search bar
                searchBar

                // Money Moves or category indicator (hidden during search)
                if !viewModel.isSearchActive {
                    if viewModel.activeCategory != nil {
                        categoryChip
                    } else if !viewModel.moneyMovesCards.isEmpty && viewModel.filterMode == .all {
                        moneyMovesRow
                    }
                }

                // Search results take priority when active
                if viewModel.isSearchActive {
                    if viewModel.isSearching {
                        searchingPlaceholder
                    } else if viewModel.searchResults.isEmpty {
                        VStack(spacing: 12) {
                            Spacer()
                            Image(systemName: "magnifyingglass")
                                .font(.system(size: 32))
                                .foregroundStyle(Color.textSecondary.opacity(0.6))
                            Text("No deals found for \"\(viewModel.searchQuery)\"")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 32)
                            Spacer()
                        }
                    } else {
                        searchResultsList
                    }
                } else if viewModel.isLoading && viewModel.recommendations.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(Color.accent)
                    Spacer()
                } else if viewModel.isGenerating && viewModel.displayedRecommendations.isEmpty {
                    generatingPlaceholder
                } else if viewModel.filterMode == .saved && viewModel.displayedRecommendations.isEmpty {
                    savedEmptyState
                } else if viewModel.filterMode == .used && viewModel.displayedRecommendations.isEmpty {
                    usedEmptyState
                } else if viewModel.displayedRecommendations.isEmpty && viewModel.activeCategory != nil && !viewModel.isGenerating {
                    Spacer()
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 32))
                            .foregroundStyle(Color.textSecondary.opacity(0.6))
                        Text("No \(viewModel.activeCategoryDisplayName.lowercased()) tips found")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
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

            // Undo toast
            if let undo = viewModel.pendingUndo {
                VStack {
                    Spacer()
                    HStack {
                        Text(undo.action.rawValue)
                            .font(.system(.caption, design: .rounded))
                            .foregroundStyle(Color.textPrimary)
                        Spacer()
                        Button("Undo") {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.undoLastAction()
                            }
                        }
                        .font(.system(.caption, design: .rounded, weight: .semibold))
                        .foregroundStyle(Color.accent)
                    }
                    .padding(12)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal, 16)
                    .padding(.bottom, 60)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .animation(.spring(response: 0.3, dampingFraction: 0.8), value: viewModel.pendingUndo != nil)
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
        .task(id: viewModel.isGenerating) {
            guard viewModel.isGenerating else { return }
            loadingStepIndex = 0
            while !Task.isCancelled && viewModel.isGenerating {
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                guard viewModel.isGenerating else { break }
                withAnimation(.easeInOut(duration: 0.25)) {
                    loadingStepIndex = min(loadingStepIndex + 1, loadingStepLabels.count - 1)
                }
            }
        }
        .task {
            await viewModel.loadRecommendations()
            await viewModel.loadSpendingSummary()
            AnalyticsManager.logRecommendationsViewed()
        }
        .alert("Daily Limit Reached", isPresented: $viewModel.showLimitAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(viewModel.limitAlertMessage)
        }
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        VStack(spacing: 6) {
            HStack(spacing: 10) {
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(viewModel.canSearch ? Color.textSecondary : Color.textSecondary.opacity(0.4))

                    TextField(
                        viewModel.canSearch ? "Search for deals..." : "Search limit reached today",
                        text: $viewModel.searchQuery
                    )
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .submitLabel(.search)
                    .onSubmit {
                        Task { await viewModel.searchDeals() }
                    }
                    .disabled(!viewModel.canSearch)

                    if !viewModel.searchQuery.isEmpty {
                        Button {
                            viewModel.clearSearch()
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 14))
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .opacity(viewModel.canSearch ? 1 : 0.7)

                if viewModel.isSearchActive {
                    Button("Cancel") {
                        viewModel.clearSearch()
                    }
                    .font(.system(.subheadline, design: .rounded, weight: .medium))
                    .foregroundStyle(Color.accent)
                }
            }

            // Search counter
            HStack {
                Spacer()
                Text("\(viewModel.searchesRemaining) search\(viewModel.searchesRemaining == 1 ? "" : "es") left today")
                    .font(.system(.caption2, design: .rounded, weight: .medium))
                    .foregroundStyle(viewModel.searchesRemaining > 0 ? Color.textSecondary : Color.danger)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 4)
    }

    // MARK: - Search Results

    private var searchResultsList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                HStack {
                    Text("Results for \"\(viewModel.searchQuery)\"")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Spacer()
                }

                ForEach(viewModel.searchResults) { item in
                    RecommendationCardView(
                        item: item,
                        isSaved: viewModel.savedTipIds.contains(item.id),
                        isUsed: viewModel.usedTipIds.contains(item.id),
                        onToggleSave: { viewModel.toggleSave(item) },
                        onDislike: {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.dislike(item)
                            }
                        },
                        onMarkUsed: {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.markUsed(item)
                            }
                        }
                    )
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }

    private var searchingPlaceholder: some View {
        VStack(spacing: 20) {
            Spacer()
            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.12))
                    .frame(width: 72, height: 72)
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 28, weight: .medium))
                    .foregroundStyle(Color.accent)
            }
            Text("Searching for deals...")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
            ProgressView()
                .tint(Color.accent)
            Spacer()
        }
    }

    // MARK: - Recommendations List

    private var recommendationsList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(viewModel.displayedRecommendations) { item in
                    RecommendationCardView(
                        item: item,
                        isSaved: viewModel.savedTipIds.contains(item.id),
                        isUsed: viewModel.usedTipIds.contains(item.id),
                        onToggleSave: { viewModel.toggleSave(item) },
                        onDislike: {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.dislike(item)
                            }
                        },
                        onMarkUsed: {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.markUsed(item)
                            }
                        },
                        onRestore: viewModel.filterMode == .used ? {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                viewModel.restoreFromUsed(item)
                            }
                        } : nil
                    )
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

    // MARK: - Empty States

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

    private var savedEmptyState: some View {
        VStack(spacing: 16) {
            Spacer()

            Image(systemName: "bookmark")
                .font(.system(size: 48))
                .foregroundStyle(Color.textSecondary.opacity(0.4))

            Text("No saved tips yet")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Tap the \u{2022}\u{2022}\u{2022} menu on any tip and select Save.")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
    }

    private var usedEmptyState: some View {
        VStack(spacing: 16) {
            Spacer()

            Image(systemName: "checkmark.circle")
                .font(.system(size: 48))
                .foregroundStyle(Color.textSecondary.opacity(0.4))

            Text("No used tips yet")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Mark tips you've already used from the \u{2022}\u{2022}\u{2022} menu.")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            Spacer()
        }
    }

    // MARK: - Generating Placeholder (no cached content)

    private var generatingPlaceholder: some View {
        VStack(spacing: 28) {
            Spacer()

            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.12))
                    .frame(width: 72, height: 72)
                Image(systemName: loadingStepIcon)
                    .font(.system(size: 28, weight: .medium))
                    .foregroundStyle(Color.accent)
                    .id(loadingStepIndex)
                    .transition(.asymmetric(
                        insertion: .scale(scale: 0.7).combined(with: .opacity),
                        removal: .opacity
                    ))
            }

            VStack(spacing: 10) {
                ForEach(Array(loadingStepLabels.enumerated()), id: \.offset) { index, label in
                    HStack(spacing: 10) {
                        ZStack {
                            if index < loadingStepIndex {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Color.accent)
                                    .font(.system(size: 16))
                            } else if index == loadingStepIndex {
                                ProgressView()
                                    .scaleEffect(0.7)
                                    .tint(Color.accent)
                                    .frame(width: 16, height: 16)
                            } else {
                                Circle()
                                    .strokeBorder(Color.textSecondary.opacity(0.3), lineWidth: 1.5)
                                    .frame(width: 16, height: 16)
                            }
                        }
                        .frame(width: 18)

                        Text(label)
                            .font(.roundedBody)
                            .foregroundStyle(
                                index <= loadingStepIndex ? Color.textPrimary : Color.textSecondary.opacity(0.4)
                            )
                            .animation(.easeInOut(duration: 0.3), value: loadingStepIndex)

                        Spacer()
                    }
                }
            }
            .padding(.horizontal, 40)

            Spacer()
        }
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        HStack {
            // Filter picker (left-aligned)
            Menu {
                ForEach(RecommendationFilterMode.allCases, id: \.self) { mode in
                    Button {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            viewModel.filterMode = mode
                        }
                    } label: {
                        HStack {
                            Text(mode.rawValue)
                            if viewModel.filterMode == mode {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: filterIcon)
                        .font(.system(size: 12, weight: .semibold))
                    Text(viewModel.filterMode.rawValue)
                        .font(.system(.subheadline, design: .rounded, weight: .medium))
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(viewModel.filterMode == .all ? Color.surface : Color.accent.opacity(0.15))
                .foregroundStyle(viewModel.filterMode == .all ? Color.textSecondary : Color.accent)
                .clipShape(Capsule())
                .overlay(
                    Capsule()
                        .strokeBorder(Color.textSecondary.opacity(viewModel.filterMode == .all ? 0.2 : 0), lineWidth: 1)
                )
            }

            Spacer()

            // Refresh counter
            Text("\(viewModel.refreshesRemaining)/\(RecommendationsViewModel.dailyRefreshLimit)")
                .font(.system(.caption2, design: .rounded, weight: .semibold))
                .monospacedDigit()
                .foregroundStyle(viewModel.canRefresh ? Color.textSecondary : Color.danger)

            // Refresh button (right-aligned)
            Button {
                Task { await viewModel.generateRecommendations() }
                AnalyticsManager.logRecommendationsGenerated()
            } label: {
                HStack(spacing: 6) {
                    if viewModel.isGenerating {
                        ProgressView()
                            .tint(Color.accent)
                            .controlSize(.mini)
                        Text(loadingStepLabels[min(loadingStepIndex, loadingStepLabels.count - 1)])
                            .font(.system(.subheadline, design: .rounded, weight: .medium))
                            .lineLimit(1)
                            .id(loadingStepIndex)
                            .transition(.asymmetric(
                                insertion: .move(edge: .bottom).combined(with: .opacity),
                                removal:   .move(edge: .top).combined(with: .opacity)
                            ))
                    } else if !viewModel.canRefresh {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 12, weight: .semibold))
                        Text("Locked")
                            .font(.system(.subheadline, design: .rounded, weight: .medium))
                    } else {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 12, weight: .semibold))
                        Text("Refresh")
                            .font(.system(.subheadline, design: .rounded, weight: .medium))
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(viewModel.canRefresh ? Color.accent.opacity(0.15) : Color.textSecondary.opacity(0.1))
                .foregroundStyle(viewModel.canRefresh ? Color.accent : Color.textSecondary)
                .clipShape(Capsule())
                .animation(.easeInOut(duration: 0.2), value: viewModel.isGenerating)
            }
            .disabled(viewModel.isGenerating || !viewModel.canRefresh)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.surface)
    }

    private var filterIcon: String {
        switch viewModel.filterMode {
        case .all: return "line.3.horizontal.decrease"
        case .saved: return "bookmark.fill"
        case .used: return "checkmark.circle.fill"
        }
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
    let isSaved: Bool
    let isUsed: Bool
    let onToggleSave: () -> Void
    let onDislike: () -> Void
    var onMarkUsed: (() -> Void)? = nil
    var onRestore: (() -> Void)? = nil
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(Color.accent.opacity(0.15))
                        .frame(width: 32, height: 32)
                    Image(systemName: item.icon ?? "lightbulb")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Color.accent)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(item.title)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

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

                HStack(spacing: 8) {
                    // Context menu for actions
                    Menu {
                        Button {
                            onToggleSave()
                        } label: {
                            Label(isSaved ? "Unsave" : "Save", systemImage: isSaved ? "bookmark.slash" : "bookmark")
                        }

                        if isUsed, let onRestore {
                            Button {
                                onRestore()
                            } label: {
                                Label("Mark as Unused", systemImage: "arrow.uturn.backward")
                            }
                        } else {
                            Button {
                                onMarkUsed?()
                            } label: {
                                Label("Used", systemImage: "checkmark.circle")
                            }
                        }

                        Button(role: .destructive) {
                            onDislike()
                        } label: {
                            Label("Not for me", systemImage: "hand.thumbsdown")
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(Color.textSecondary)
                            .frame(width: 28, height: 28)
                            .contentShape(Rectangle())
                    }

                    if item.isExpandable {
                        Image(systemName: "chevron.right")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(Color.textSecondary)
                            .rotationEffect(.degrees(isExpanded ? 90 : 0))
                    }
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
            if !isExpanded {
                AnalyticsManager.logRecommendationExpanded(title: item.title)
            }
        }
    }

    @ViewBuilder
    private var expandedContent: some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()
                .overlay(Color.textSecondary.opacity(0.3))
                .padding(.top, 8)

            if let context = item.spendingContext {
                Text(context)
                    .font(.system(.caption2, design: .rounded))
                    .foregroundStyle(Color.textSecondary)
                    .lineLimit(1)
            }

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
