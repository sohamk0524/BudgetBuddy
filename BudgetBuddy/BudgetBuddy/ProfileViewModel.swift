//
//  ProfileViewModel.swift
//  BudgetBuddy
//
//  ViewModel for the user profile page
//

import Foundation
import Observation

@Observable
@MainActor
class ProfileViewModel {

    // MARK: - State

    var name: String = ""
    var email: String = ""
    var isStudent: Bool = false
    var budgetingGoal: String = ""
    var strictnessLevel: String = ""

    var plaidItems: [PlaidItemInfo] = []

    var isLoading = false
    var isSaving = false
    var isEditing = false
    var errorMessage: String?

    // MARK: - Dependencies

    private let apiService = APIService.shared

    // MARK: - Public Methods

    func loadProfile() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil

        do {
            let profile = try await apiService.getUserProfile(userId: userId)
            name = profile.name ?? ""
            email = profile.email
            isStudent = profile.profile?.isStudent ?? false
            budgetingGoal = profile.profile?.budgetingGoal ?? ""
            strictnessLevel = profile.profile?.strictnessLevel ?? ""
            plaidItems = profile.plaidItems
        } catch {
            print("Failed to load profile: \(error)")
            errorMessage = "Failed to load profile"
        }

        isLoading = false
    }

    func saveProfile() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isSaving = true
        errorMessage = nil

        do {
            let update = UserProfileUpdateRequest(
                name: name.isEmpty ? nil : name,
                isStudent: isStudent,
                budgetingGoal: budgetingGoal.isEmpty ? nil : budgetingGoal,
                strictnessLevel: strictnessLevel.isEmpty ? nil : strictnessLevel
            )
            try await apiService.updateUserProfile(userId: userId, update: update)

            // Update AuthManager name
            AuthManager.shared.userName = name.isEmpty ? nil : name

            isEditing = false
        } catch {
            print("Failed to save profile: \(error)")
            errorMessage = "Failed to save profile"
        }

        isSaving = false
    }

    func unlinkPlaidItem(itemId: String) async {
        guard let userId = AuthManager.shared.authToken else { return }

        do {
            let url = URL(string: "http://localhost:5000/plaid/unlink/\(userId)/\(itemId)")!
            var request = URLRequest(url: url)
            request.httpMethod = "DELETE"

            let (_, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else { return }

            // Reload profile to refresh plaid items
            await loadProfile()
        } catch {
            print("Failed to unlink Plaid item: \(error)")
            errorMessage = "Failed to unlink account"
        }
    }
}
