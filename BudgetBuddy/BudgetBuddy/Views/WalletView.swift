//
//  WalletView.swift
//  BudgetBuddy
//
//  The "Wallet" Dashboard - A Bento Box style grid for quick status checks
//

import SwiftUI

struct WalletView: View {
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Top Row: Large + Medium cards
                    HStack(spacing: 16) {
                        // Large Card: Net Worth
                        NetWorthCard()

                        // Medium Card: Upcoming Bills
                        UpcomingBillsCard()
                    }

                    // Bottom Row: Small cards
                    HStack(spacing: 16) {
                        // Small Card: Anomalies
                        AnomaliesCard()

                        // Small Card: Goal Progress
                        GoalProgressCard()
                    }
                }
                .padding()
            }
            .background(Color.background)
            .navigationTitle("Wallet")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(Color.background, for: .navigationBar)
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
        }
    }
}

// MARK: - Net Worth Card (Large)

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

// MARK: - Upcoming Bills Card (Medium)

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

            // Progress indicator
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.background)
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

// MARK: - Anomalies Card (Small)

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

// MARK: - Goal Progress Card (Small)

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

            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.background)
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
