//
//  QuickActionModalView.swift
//  BudgetBuddy
//
//  Quick-Action types and sub-menu sheets for the chat interface
//

import SwiftUI

// MARK: - Quick Action Option (used by the inline grid in ChatView)

enum QuickActionOption: String, CaseIterable, Identifiable {
    case craving = "I'm craving..."
    case goTo = "I want to go..."
    case onTrack = "Am I on track?"
    case justSpent = "I just spent..."
    case canAfford = "Can I afford...?"
    case typeOwn = "Let me type..."

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .craving: return "fork.knife"
        case .goTo: return "figure.walk"
        case .onTrack: return "checkmark.circle"
        case .justSpent: return "dollarsign.circle"
        case .canAfford: return "questionmark.circle"
        case .typeOwn: return "keyboard"
        }
    }
}

// MARK: - Sub-Menu Types (presented as half-sheets)

enum QuickActionSubMenu: String, Identifiable {
    case craving
    case goTo
    case justSpent
    case canAfford

    var id: String { rawValue }

    var title: String {
        switch self {
        case .craving: return "I'm craving..."
        case .goTo: return "I want to go..."
        case .justSpent: return "I just spent..."
        case .canAfford: return "Can I afford...?"
        }
    }
}

// MARK: - Sub-Menu Sheet View

struct QuickActionSubMenuView: View {
    let menu: QuickActionSubMenu
    let onSendPrompt: (String) -> Void
    let onPrefillType: ((String) -> Void)?
    @Environment(\.dismiss) private var dismiss

    // "I just spent..." state
    @State private var spentAmount: String = ""
    @State private var spentCategory: String = "Food"

    // "Can I afford...?" state
    @State private var affordItem: String = ""
    @State private var affordPrice: String = ""

    private let spendCategories = ["Food", "Transport", "Entertainment", "Groceries", "Shopping", "Other"]

    var body: some View {
        NavigationStack {
            ZStack {
                Color.appBackground.ignoresSafeArea()

                switch menu {
                case .craving:
                    cravingSubMenuView
                case .goTo:
                    goToSubMenuView
                case .justSpent:
                    spentInputView
                case .canAfford:
                    affordInputView
                }
            }
            .navigationTitle(menu.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Color.textSecondary)
                    }
                }
            }
            .toolbarBackground(Color.appBackground, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
        .presentationBackground(Color.appBackground)
    }

    // MARK: - Craving Sub-Menu

    private let cravingOptions = [
        ("Coffee", "CoHo / Peet's"),
        ("Boba", "Lazi Cow / Sharetea"),
        ("Sandwiches", "Ike's / Subway"),
        ("Asian Food", "Nobu Hachi / Thai Canteen"),
        ("Halal", "Shah's / Ali Baba"),
        ("Late Night", "In-N-Out / IHOP"),
    ]

    private var cravingSubMenuView: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(cravingOptions, id: \.0) { name, detail in
                    Button {
                        send("I'm craving \(name)")
                    } label: {
                        HStack {
                            Text(name)
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.textPrimary)
                            Spacer()
                            Text(detail)
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                            Image(systemName: "chevron.right")
                                .foregroundStyle(Color.textSecondary)
                        }
                        .padding()
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }

                // Let me type fallback
                typeOwnRow(prefill: "I'm craving ")
            }
            .padding()
        }
    }

    // MARK: - Go-To Sub-Menu

    private let goToOptions = ["Downtown", "Sacramento", "Tahoe", "SF", "The ARC"]

    private var goToSubMenuView: some View {
        ScrollView {
            VStack(spacing: 12) {
                ForEach(goToOptions, id: \.self) { location in
                    Button {
                        send("I want to go to \(location)")
                    } label: {
                        HStack {
                            Text(location)
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.textPrimary)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundStyle(Color.textSecondary)
                        }
                        .padding()
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }

                // Let me type fallback
                typeOwnRow(prefill: "I want to go to ")
            }
            .padding()
        }
    }

    // MARK: - "I just spent..." Input

    private var spentInputView: some View {
        VStack(spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Amount")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                HStack {
                    Text("$")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.accent)
                    TextField("0.00", text: $spentAmount)
                        .keyboardType(.decimalPad)
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Category")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(spendCategories, id: \.self) { category in
                            Button {
                                spentCategory = category
                            } label: {
                                Text(category)
                                    .font(.roundedCaption)
                                    .foregroundStyle(spentCategory == category ? Color.appBackground : Color.textPrimary)
                                    .padding(.horizontal, 14)
                                    .padding(.vertical, 8)
                                    .background(spentCategory == category ? Color.accent : Color.surface)
                                    .clipShape(Capsule())
                            }
                        }
                    }
                }
            }

            Button {
                guard !spentAmount.isEmpty else { return }
                send("I just spent $\(spentAmount) on \(spentCategory)")
            } label: {
                Text("Log It")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.appBackground)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(spentAmount.isEmpty ? Color.textSecondary : Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(spentAmount.isEmpty)

            Spacer()
        }
        .padding()
    }

    // MARK: - "Can I afford...?" Input

    private var affordInputView: some View {
        VStack(spacing: 20) {
            VStack(alignment: .leading, spacing: 8) {
                Text("What do you want to buy?")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                TextField("e.g. New headphones", text: $affordItem)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Price")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
                HStack {
                    Text("$")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.accent)
                    TextField("0.00", text: $affordPrice)
                        .keyboardType(.decimalPad)
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Button {
                guard !affordPrice.isEmpty else { return }
                let item = affordItem.isEmpty ? "something" : affordItem
                send("Can I afford \(item) for $\(affordPrice)?")
            } label: {
                Text("Check Budget")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.appBackground)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(affordPrice.isEmpty ? Color.textSecondary : Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(affordPrice.isEmpty)

            Spacer()
        }
        .padding()
    }

    // MARK: - Helpers

    private func send(_ prompt: String) {
        dismiss()
        onSendPrompt(prompt)
    }

    private func typeOwnRow(prefill: String) -> some View {
        Button {
            dismiss()
            onPrefillType?(prefill)
        } label: {
            HStack {
                Image(systemName: "keyboard")
                    .foregroundStyle(Color.accent)
                Text("Let me type...")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textSecondary)
                Spacer()
            }
            .padding()
            .background(Color.surface.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.textSecondary.opacity(0.3), lineWidth: 1)
            )
        }
    }
}

#Preview {
    Color.appBackground
        .sheet(isPresented: .constant(true)) {
            QuickActionSubMenuView(
                menu: .craving,
                onSendPrompt: { print($0) },
                onPrefillType: { print("Prefill: \($0)") }
            )
        }
}
