//
//  ReceiptLineItemsView.swift
//  BudgetBuddy
//
//  Shows Claude Vision receipt analysis: merchant, total, and tappable line items.
//  Users can tap any item to toggle it between Essential and Fun Money.
//

import SwiftUI

struct ReceiptLineItemsView: View {
    let result: ReceiptAnalysisResult
    /// Called on confirm with the user-edited essential and discretionary totals.
    let onConfirm: (_ essentialTotal: Double, _ discretionaryTotal: Double) -> Void

    /// Per-item classification overrides (index → "essential" | "discretionary")
    @State private var classifications: [String]

    init(result: ReceiptAnalysisResult, onConfirm: @escaping (_ essentialTotal: Double, _ discretionaryTotal: Double) -> Void) {
        self.result = result
        self.onConfirm = onConfirm
        _classifications = State(initialValue: result.items.map(\.classification))
    }

    // MARK: - Derived totals

    private var currentEssentialTotal: Double {
        zip(result.items, classifications).reduce(0) { sum, pair in
            sum + (pair.1 == "essential" ? pair.0.price : 0)
        }
    }

    private var currentDiscretionaryTotal: Double {
        zip(result.items, classifications).reduce(0) { sum, pair in
            sum + (pair.1 == "discretionary" ? pair.0.price : 0)
        }
    }

    private var essentialFraction: Double {
        guard result.total > 0 else { return 0.5 }
        return currentEssentialTotal / result.total
    }

    // MARK: - Body

    var body: some View {
        VStack(spacing: 0) {
            // Header card
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(result.merchant)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)
                    Spacer()
                    Text("$\(result.total, specifier: "%.2f")")
                        .font(.rounded(.title2, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }

                // Split bar — updates live as user toggles items
                if result.total > 0 {
                    GeometryReader { geo in
                        HStack(spacing: 2) {
                            Color.accent
                                .frame(width: max(essentialFraction * geo.size.width, essentialFraction > 0 ? 4 : 0))
                            Color.danger
                                .frame(width: max((1 - essentialFraction) * geo.size.width, (1 - essentialFraction) > 0 ? 4 : 0))
                        }
                    }
                    .frame(height: 10)
                    .clipShape(Capsule())
                    .animation(.easeInOut(duration: 0.25), value: essentialFraction)
                }

                HStack {
                    HStack(spacing: 6) {
                        Circle().fill(Color.accent).frame(width: 8, height: 8)
                        Text("Essential $\(currentEssentialTotal, specifier: "%.2f")")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                            .monospacedDigit()
                    }
                    Spacer()
                    HStack(spacing: 6) {
                        Circle().fill(Color.danger).frame(width: 8, height: 8)
                        Text("Fun Money $\(currentDiscretionaryTotal, specifier: "%.2f")")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                            .monospacedDigit()
                    }
                }
            }
            .padding(16)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .padding(.horizontal)
            .padding(.top, 12)

            // Hint pill — outside the card, consistent 12pt spacing above and below
            HStack(spacing: 5) {
                Image(systemName: "hand.tap")
                    .font(.system(size: 12))
                Text("Tap items to change their category")
                    .font(.roundedCaption)
            }
            .foregroundStyle(Color.textSecondary)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(Color.appBackground)
            .clipShape(Capsule())
            .overlay(Capsule().stroke(Color.textSecondary.opacity(0.18), lineWidth: 1))
            .padding(.vertical, 12)

            // Line items — tappable
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(Array(result.items.enumerated()), id: \.offset) { index, item in
                        let cls = index < classifications.count ? classifications[index] : item.classification
                        let isEssential = cls == "essential"

                        Button {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                classifications[index] = isEssential ? "discretionary" : "essential"
                            }
                        } label: {
                            HStack(spacing: 12) {
                                // Color bar
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(isEssential ? Color.accent : Color.danger)
                                    .frame(width: 4)
                                    .padding(.vertical, 2)

                                Text(item.name)
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)
                                    .lineLimit(2)
                                    .multilineTextAlignment(.leading)
                                    .frame(maxWidth: .infinity, alignment: .leading)

                                VStack(alignment: .trailing, spacing: 2) {
                                    Text("$\(item.price, specifier: "%.2f")")
                                        .font(.roundedBody)
                                        .fontWeight(.medium)
                                        .foregroundStyle(Color.textPrimary)
                                        .monospacedDigit()

                                    Text(isEssential ? "Essential" : "Fun Money")
                                        .font(.system(size: 10, weight: .semibold, design: .rounded))
                                        .foregroundStyle(isEssential ? Color.accent : Color.danger)
                                }
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.surface)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .buttonStyle(.plain)
                        .padding(.horizontal)
                    }
                }
                .padding(.bottom, 12)
            }

            // Confirm button
            Button {
                onConfirm(currentEssentialTotal, currentDiscretionaryTotal)
            } label: {
                Text("Confirm & Save")
                    .font(.roundedHeadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
            .padding(.horizontal)
            .padding(.vertical, 12)
            .background(Color.surface)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.appBackground)
    }
}
