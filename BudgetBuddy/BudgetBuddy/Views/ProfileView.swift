//
//  ProfileView.swift
//  BudgetBuddy
//
//  User profile page for managing settings, financial profile, and Plaid connections
//

import SwiftUI

@MainActor
struct ProfileView: View {
    @State private var viewModel = ProfileViewModel()
    @State private var showDeleteConfirmation = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {

                // MARK: - Profile Header
                profileHeader

                // MARK: - Financial Profile
                financialProfileSection

                // MARK: - Notification Settings
                notificationSettingsSection

                // MARK: - Categories
                categorySettingsSection

                // MARK: - Face ID
                biometricSection

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

                // MARK: - Delete Account
                Button {
                    showDeleteConfirmation = true
                } label: {
                    HStack {
                        Image(systemName: "trash")
                        Text("Delete Account")
                    }
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.danger)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.danger.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .alert("Delete Account", isPresented: $showDeleteConfirmation) {
                    Button("Cancel", role: .cancel) { }
                    Button("Delete", role: .destructive) {
                        Task { await AuthManager.shared.deleteAccount() }
                    }
                } message: {
                    Text("This will permanently delete your account, all linked bank connections, and all transaction data. This action cannot be undone.")
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

                if viewModel.isStudent {
                    profileRow(label: "University", value: AppConfig.universityDisplayName(for: viewModel.school)) {
                        Picker("University", selection: $viewModel.school) {
                            Text("Select...").tag("")
                            ForEach(AppConfig.universities, id: \.key) { university in
                                Text(university.name).tag(university.key)
                            }
                        }
                        .pickerStyle(.menu)
                        .tint(Color.accent)
                    }
                }

                profileRow(label: "Weekly Limit", value: String(format: "$%.0f", viewModel.weeklySpendingLimit)) {
                    TextField("Amount", value: $viewModel.weeklySpendingLimit, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                        .font(.roundedBody)
                        .foregroundStyle(Color.accent)
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

    // MARK: - Biometric Section

    private var biometricSection: some View {
        HStack {
            let type = AuthManager.shared.biometricType
            let icon = type == "Face ID" ? "faceid" : "touchid"
            Label(type, systemImage: icon)
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Spacer()

            Toggle("", isOn: Binding(
                get: { AuthManager.shared.biometricEnabled },
                set: { newValue in
                    if newValue {
                        Task { await AuthManager.shared.enableBiometrics() }
                    } else {
                        AuthManager.shared.disableBiometrics()
                    }
                }
            ))
            .tint(Color.accent)
            .labelsHidden()
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Notification Settings Section

    private var notificationSettingsSection: some View {
        NavigationLink {
            NotificationSettingsView()
        } label: {
            HStack {
                Label("Notifications", systemImage: "bell")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
            .padding()
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Category Settings Section

    private var categorySettingsSection: some View {
        NavigationLink {
            CategorySettingsView()
        } label: {
            HStack {
                Label("Categories", systemImage: "tag")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
            .padding()
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: - Linked Accounts Section

    private var linkedAccountsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("Linked Accounts", systemImage: "building.columns")
                    .font(.roundedHeadline)
                    .foregroundStyle(Color.textPrimary)

                Spacer()

                Text("Coming Soon")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.accent)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Color.accent.opacity(0.15))
                    .clipShape(Capsule())
            }

            Text("Bank account linking will be available in a future update. Stay tuned!")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

}

#Preview {
    NavigationStack {
        ProfileView()
    }
}
