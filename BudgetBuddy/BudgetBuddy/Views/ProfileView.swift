//
//  ProfileView.swift
//  BudgetBuddy
//
//  User profile page for managing settings, financial profile, and Plaid connections
//

import SwiftUI

struct ProfileView: View {
    @State private var viewModel = ProfileViewModel()
    @State private var showPlaidLink = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {

                // MARK: - Profile Header
                profileHeader

                // MARK: - Financial Profile
                financialProfileSection

                // MARK: - Linked Accounts
                linkedAccountsSection

                // MARK: - Sign Out
                Button {
                    AuthManager.shared.signOut()
                } label: {
                    HStack {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                        Text("Sign Out")
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.danger)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
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
                Text("Profile")
                    .font(.system(size: 22, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.textPrimary)
            }
            if viewModel.isEditing {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") {
                        Task { await viewModel.saveProfile() }
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.accent)
                    .disabled(viewModel.isSaving)
                }
            } else {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Edit") {
                        viewModel.isEditing = true
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.accent)
                }
            }
        }
        .task {
            await viewModel.loadProfile()
        }
        .sheet(isPresented: $showPlaidLink) {
            PlaidLinkView(
                showPlaidLink: $showPlaidLink,
                userId: AuthManager.shared.authToken ?? 0,
                onComplete: {
                    showPlaidLink = false
                    Task { await viewModel.loadProfile() }
                },
                onSkip: {
                    showPlaidLink = false
                }
            )
        }
    }

    // MARK: - Profile Header

    private var profileHeader: some View {
        VStack(spacing: 16) {
            // Avatar circle with initials
            ZStack {
                Circle()
                    .fill(Color.accent.opacity(0.2))
                    .frame(width: 80, height: 80)

                Text(initials)
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(Color.accent)
            }

            if viewModel.isEditing {
                TextField("Your Name", text: $viewModel.name)
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textPrimary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 48)
                    .padding(.vertical, 6)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color.accent.opacity(0.4), lineWidth: 1)
                    )
                    .padding(.horizontal, 32)
            } else {
                Text(viewModel.name.isEmpty ? "BudgetBuddy User" : viewModel.name)
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textPrimary)
            }

            Text(viewModel.phoneNumber)
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .padding(.vertical, 8)
    }

    private var initials: String {
        let parts = viewModel.name.split(separator: " ")
        if parts.isEmpty { return "BB" }
        let first = parts.first.map { String($0.prefix(1)).uppercased() } ?? ""
        let last = parts.count > 1 ? String(parts.last!.prefix(1)).uppercased() : ""
        return first + last
    }

    // MARK: - Financial Profile Section

    private var financialProfileSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Financial Profile", systemImage: "person.text.rectangle")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            VStack(spacing: 12) {
                profileRow(label: "Student", value: viewModel.isStudent ? "Yes" : "No") {
                    Toggle("Student", isOn: $viewModel.isStudent)
                        .tint(Color.accent)
                        .labelsHidden()
                }

                profileRow(label: "Weekly Limit", value: String(format: "$%.0f", viewModel.weeklySpendingLimit)) {
                    TextField("Amount", value: $viewModel.weeklySpendingLimit, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .font(.roundedBody)
                        .foregroundStyle(Color.accent)
                }

                profileRow(label: "Strictness", value: formatStrictness(viewModel.strictnessLevel)) {
                    Picker("Strictness", selection: $viewModel.strictnessLevel) {
                        Text("Relaxed").tag("relaxed")
                        Text("Moderate").tag("moderate")
                        Text("Strict").tag("strict")
                    }
                    .pickerStyle(.menu)
                    .tint(Color.accent)
                }
            }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    @ViewBuilder
    private func profileRow<EditContent: View>(
        label: String,
        value: String,
        @ViewBuilder editView: () -> EditContent
    ) -> some View {
        HStack {
            Text(label)
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .layoutPriority(1)

            Spacer(minLength: 8)

            Group {
                if viewModel.isEditing {
                    editView()
                        .font(.roundedBody)
                        .foregroundStyle(Color.accent)
                } else {
                    Text(value)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                }
            }
            .frame(width: 160, alignment: .trailing)
        }
        .padding(.vertical, 4)
    }

    // MARK: - Linked Accounts Section

    private var linkedAccountsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Linked Accounts", systemImage: "building.columns")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            if viewModel.plaidItems.isEmpty {
                VStack(spacing: 8) {
                    Text("No bank accounts linked")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)

                    Text("Connect your bank to see real-time transactions and spending insights")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.vertical, 8)
            } else {
                ForEach(viewModel.plaidItems) { item in
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.institutionName ?? "Unknown Bank")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.textPrimary)

                            Text("\(item.accounts.count) account\(item.accounts.count == 1 ? "" : "s")")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)
                        }

                        Spacer()

                        HStack(spacing: 8) {
                            Text(item.status.capitalized)
                                .font(.roundedCaption)
                                .foregroundStyle(item.status == "active" ? Color.accent : Color.danger)

                            Button {
                                Task { await viewModel.unlinkPlaidItem(itemId: item.itemId) }
                            } label: {
                                Text("Unlink")
                                    .font(.roundedCaption)
                                    .foregroundStyle(Color.danger)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }

            Button {
                showPlaidLink = true
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Link New Account")
                }
                .font(.roundedHeadline)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.accent.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Formatters

    private func formatStrictness(_ value: String) -> String {
        switch value {
        case "relaxed": return "Relaxed"
        case "moderate": return "Moderate"
        case "strict": return "Strict"
        default: return "--"
        }
    }
}

#Preview {
    NavigationStack {
        ProfileView()
    }
}
