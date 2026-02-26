//
//  ReceiptLineItemsView.swift
//  BudgetBuddy
//
//  Shows Claude Vision receipt analysis: merchant, total, line items with color-coded bars.
//

import SwiftUI

struct ReceiptLineItemsView: View {
    let result: ReceiptAnalysisResult
    let onConfirm: () -> Void

    private var essentialFraction: Double {
        guard result.total > 0 else { return 0.5 }
        return result.essentialTotal / result.total
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header card
            VStack(alignment: .leading, spacing: 12) {
                Text(result.merchant)
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                HStack {
                    Text("Total")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                    Spacer()
                    Text("$\(result.total, specifier: "%.2f")")
                        .font(.rounded(.title2, weight: .bold))
                        .foregroundStyle(Color.accent)
                        .monospacedDigit()
                }

                // Essential / Discretionary split bar
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
                }

                HStack {
                    HStack(spacing: 6) {
                        Circle().fill(Color.accent).frame(width: 8, height: 8)
                        Text("Essential $\(result.essentialTotal, specifier: "%.2f")")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                    Spacer()
                    HStack(spacing: 6) {
                        Circle().fill(Color.danger).frame(width: 8, height: 8)
                        Text("Fun Money $\(result.discretionaryTotal, specifier: "%.2f")")
                            .font(.roundedCaption)
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
            .padding(16)
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .padding(.horizontal)
            .padding(.top, 12)

            // Line items
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(result.items) { item in
                        HStack(spacing: 12) {
                            // Color bar
                            RoundedRectangle(cornerRadius: 3)
                                .fill(item.isEssential ? Color.accent : Color.danger)
                                .frame(width: 4)
                                .padding(.vertical, 2)

                            Text(item.name)
                                .font(.roundedBody)
                                .foregroundStyle(Color.textPrimary)
                                .lineLimit(1)

                            Spacer()

                            Text("$\(item.price, specifier: "%.2f")")
                                .font(.roundedBody)
                                .fontWeight(.medium)
                                .foregroundStyle(Color.textPrimary)
                                .monospacedDigit()
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .padding(.horizontal)
                    }
                }
                .padding(.vertical, 12)
            }

            Spacer(minLength: 0)

            // Confirm button
            Button(action: onConfirm) {
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
        .background(Color.appBackground)
    }
}
