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
                    status: viewModel.statusDisplayText,
                    savingsStreak: viewModel.savingsStreak
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
            await withTaskGroup(of: Void.self) { group in
                group.addTask { await viewModel.loadSpendingSummary() }
                group.addTask { await viewModel.loadGamification() }
            }
            AnalyticsManager.logRecommendationsViewed()
        }
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        HStack(spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(Color.textSecondary)

                TextField("Search for deals...", text: $viewModel.searchQuery)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .submitLabel(.search)
                    .onSubmit {
                        Task { await viewModel.searchDeals() }
                    }

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

            if viewModel.isSearchActive {
                Button("Cancel") {
                    viewModel.clearSearch()
                }
                .font(.system(.subheadline, design: .rounded, weight: .medium))
                .foregroundStyle(Color.accent)
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
                // Total saved banner (Used filter only)
                if viewModel.filterMode == .used && viewModel.totalSaved > 0 {
                    HStack(spacing: 10) {
                        Image(systemName: "leaf.fill")
                            .font(.system(size: 18))
                            .foregroundStyle(.green)
                        Text("You've saved **$\(Int(viewModel.totalSaved))** by using tips!")
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // Challenges history (Challenges filter only)
                if viewModel.filterMode == .challenges {
                    // Active challenge
                    if let challenge = viewModel.weeklyChallenge {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Active Challenge")
                                .font(.system(.caption, design: .rounded, weight: .semibold))
                                .foregroundStyle(Color.textSecondary)
                                .textCase(.uppercase)
                                .padding(.horizontal, 4)
                            WeeklyChallengeCardView(
                                challenge: challenge,
                                onAccept: { Task { await viewModel.acceptChallenge() } },
                                onDecline: { Task { await viewModel.declineChallenge() } },
                                onDismiss: { Task { await viewModel.dismissChallenge() } }
                            )
                        }
                    }

                    // History
                    if viewModel.challengeHistory.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "trophy")
                                .font(.system(size: 32))
                                .foregroundStyle(Color.textSecondary.opacity(0.4))
                            Text("No challenge history yet")
                                .font(.roundedBody)
                                .foregroundStyle(Color.textSecondary)
                            Text("Complete weekly challenges to build your history")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary.opacity(0.7))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 40)
                    } else {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Past Challenges")
                                .font(.system(.caption, design: .rounded, weight: .semibold))
                                .foregroundStyle(Color.textSecondary)
                                .textCase(.uppercase)
                                .padding(.horizontal, 4)

                            ForEach(viewModel.challengeHistory.reversed()) { entry in
                                ChallengeHistoryRowView(entry: entry)
                            }
                        }
                    }
                }

                // Weekly Challenge card (only in All mode with no category filter)
                if viewModel.filterMode == .all && viewModel.activeCategory == nil,
                   let challenge = viewModel.weeklyChallenge {
                    WeeklyChallengeCardView(
                        challenge: challenge,
                        onAccept: { Task { await viewModel.acceptChallenge() } },
                        onDecline: { Task { await viewModel.declineChallenge() } },
                        onDismiss: { Task { await viewModel.dismissChallenge() } }
                    )
                }

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
                    Text(filterLabel)
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

            // Refresh button (right-aligned)
            Button {
                Task {
                    await viewModel.generateRecommendations()
                    await viewModel.loadGamification()
                }
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
                    } else {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 12, weight: .semibold))
                        Text("Refresh")
                            .font(.system(.subheadline, design: .rounded, weight: .medium))
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Color.accent.opacity(0.15))
                .foregroundStyle(Color.accent)
                .clipShape(Capsule())
                .animation(.easeInOut(duration: 0.2), value: viewModel.isGenerating)
            }
            .disabled(viewModel.isGenerating)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.surface)
    }

    private var filterLabel: String {
        viewModel.filterMode.rawValue
    }

    private var filterIcon: String {
        switch viewModel.filterMode {
        case .all: return "line.3.horizontal.decrease"
        case .saved: return "bookmark.fill"
        case .used: return "checkmark.circle.fill"
        case .challenges: return "trophy.fill"
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

// MARK: - Weekly Challenge Card

struct WeeklyChallengeCardView: View {
    let challenge: WeeklyChallenge
    var onAccept: (() -> Void)? = nil
    var onDecline: (() -> Void)? = nil
    var onDismiss: (() -> Void)? = nil

    private var isAccepted: Bool { challenge.accepted ?? false }

    private var progress: Double {
        guard challenge.targetAmount > 0 else { return 0 }
        return challenge.currentSpent / challenge.targetAmount
    }

    private var progressColor: Color {
        progress >= 1.0 ? .danger : progress >= 0.75 ? .yellow : .green
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header — matches RecommendationCardView layout
            HStack(alignment: .top, spacing: 10) {
                ZStack {
                    Circle()
                        .fill(Color.accent.opacity(0.15))
                        .frame(width: 32, height: 32)
                    Image(systemName: "trophy.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Color.accent)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(challenge.description)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text("Weekly Challenge")
                        .font(.system(.caption, design: .rounded, weight: .semibold))
                        .foregroundStyle(Color.accent)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(Color.accent.opacity(0.12))
                        .clipShape(Capsule())
                        .padding(.top, 2)
                }

                Spacer(minLength: 0)

                HStack(spacing: 8) {
                    Menu {
                        if !isAccepted {
                            Button {
                                onAccept?()
                            } label: {
                                Label("Accept Challenge", systemImage: "checkmark.circle")
                            }
                        }
                        Button {
                            onDecline?()
                        } label: {
                            Label("New Challenge", systemImage: "arrow.triangle.2.circlepath")
                        }
                        Button(role: .destructive) {
                            onDismiss?()
                        } label: {
                            Label("Remove Challenge", systemImage: "xmark.circle")
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(Color.textSecondary)
                            .frame(width: 28, height: 28)
                            .contentShape(Rectangle())
                    }
                }
            }

            if isAccepted {
                // Progress bar
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule()
                            .fill(Color.textSecondary.opacity(0.15))
                            .frame(height: 6)
                        Capsule()
                            .fill(progressColor)
                            .frame(width: geo.size.width * min(progress, 1.0), height: 6)
                    }
                }
                .frame(height: 6)
                .padding(.top, 12)

                HStack {
                    Text("$\(Int(challenge.currentSpent)) / $\(Int(challenge.targetAmount))")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Spacer()
                    if progress >= 1.0 {
                        Text("Over target")
                            .font(.system(.caption, design: .rounded, weight: .semibold))
                            .foregroundStyle(Color.danger)
                    } else {
                        Text("$\(Int(challenge.targetAmount - challenge.currentSpent)) left")
                            .font(.system(.caption, design: .rounded, weight: .semibold))
                            .foregroundStyle(progressColor)
                    }
                }
                .padding(.top, 6)
            } else {
                // Accept (50%) / New (25%) / Skip (25%)
                GeometryReader { geo in
                    let totalWidth = geo.size.width
                    let spacing: CGFloat = 8
                    let acceptWidth = (totalWidth - spacing * 2) * 0.5
                    let smallWidth = (totalWidth - spacing * 2) * 0.25

                    HStack(spacing: spacing) {
                        Button {
                            onAccept?()
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 11, weight: .bold))
                                Text("Accept")
                                    .font(.system(.caption, design: .rounded, weight: .semibold))
                            }
                            .foregroundStyle(Color.appBackground)
                            .frame(width: acceptWidth)
                            .padding(.vertical, 9)
                            .background(Color.accent)
                            .clipShape(Capsule())
                        }

                        Button {
                            onDecline?()
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "arrow.triangle.2.circlepath")
                                    .font(.system(size: 10, weight: .semibold))
                                Text("New")
                                    .font(.system(.caption, design: .rounded, weight: .medium))
                            }
                            .foregroundStyle(Color.textSecondary)
                            .frame(width: smallWidth)
                            .padding(.vertical, 9)
                            .background(Color.textSecondary.opacity(0.1))
                            .clipShape(Capsule())
                        }

                        Button {
                            onDismiss?()
                        } label: {
                            Text("Skip")
                                .font(.system(.caption, design: .rounded, weight: .medium))
                                .foregroundStyle(Color.textSecondary)
                                .frame(width: smallWidth)
                                .padding(.vertical, 9)
                                .background(Color.textSecondary.opacity(0.1))
                                .clipShape(Capsule())
                        }
                    }
                }
                .frame(height: 34)
                .padding(.top, 10)
            }
        }
        .cardStyle()
    }
}

// MARK: - Challenge History Row

struct ChallengeHistoryRowView: View {
    let entry: ChallengeHistoryEntry

    private var isCompleted: Bool { entry.completed ?? false }
    private var wasAccepted: Bool { entry.accepted ?? false }
    private var wasDismissed: Bool { entry.dismissed ?? false }

    private var statusIcon: String {
        if !wasAccepted { return "minus.circle" }
        if wasDismissed { return "xmark.circle" }
        if isCompleted { return "checkmark.circle.fill" }
        return "exclamationmark.circle.fill"
    }

    private var statusColor: Color {
        if !wasAccepted { return .textSecondary }
        if wasDismissed { return .textSecondary }
        if isCompleted { return .green }
        return .danger
    }

    private var statusText: String {
        if !wasAccepted { return "Not Accepted" }
        if wasDismissed { return "Dismissed" }
        if isCompleted { return "Completed" }
        return "Over Target"
    }

    var body: some View {
        HStack(spacing: 12) {
            // Status icon
            Image(systemName: statusIcon)
                .font(.system(size: 20))
                .foregroundStyle(statusColor)

            VStack(alignment: .leading, spacing: 3) {
                Text(entry.description ?? "\(entry.category.capitalized) challenge")
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .lineLimit(2)

                HStack(spacing: 8) {
                    Text(formatWeekRange(start: entry.weekStart, end: entry.weekEnd))
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)

                    if wasAccepted {
                        Text("$\(Int(entry.currentSpent)) / $\(Int(entry.targetAmount))")
                            .font(.system(size: 11, weight: .medium, design: .rounded))
                            .foregroundStyle(statusColor)
                            .monospacedDigit()
                    }
                }
            }

            Spacer()

            // Status badge
            Text(statusText)
                .font(.system(size: 10, weight: .semibold, design: .rounded))
                .foregroundStyle(statusColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(statusColor.opacity(0.12))
                .clipShape(Capsule())
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func formatWeekRange(start: String, end: String) -> String {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd"
        let displayFmt = DateFormatter()
        displayFmt.dateFormat = "MMM d"

        guard let startDate = df.date(from: start),
              let endDate = df.date(from: end) else {
            return "\(start) – \(end)"
        }
        return "\(displayFmt.string(from: startDate)) – \(displayFmt.string(from: endDate))"
    }
}

// MARK: - Preview

#Preview {
    RecommendationsView()
}
