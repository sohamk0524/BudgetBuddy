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

    // MARK: - UserDefaults Cache Keys

    private enum CacheKey {
        static let name = "profile_name"
        static let phone = "profile_phone"
        static let isStudent = "profile_isStudent"
        static let weeklyLimit = "profile_weeklyLimit"
        static let strictness = "profile_strictness"
        static let school = "profile_school"
    }

    // MARK: - State

    var name: String = ""
    var phoneNumber: String = ""
    var isStudent: Bool = true
    var weeklySpendingLimit: Double = 0
    var strictnessLevel: String = ""
    var school: String = ""

    var plaidItems: [PlaidItemInfo] = []

    var isLoading = false
    var isSaving = false
    var isEditing = false
    var errorMessage: String?

    // MARK: - Dependencies

    private let apiService = APIService.shared
    private let defaults = UserDefaults.standard

    // MARK: - Init

    init() {
        loadFromCache()
    }

    // MARK: - Cache

    private func loadFromCache() {
        name = defaults.string(forKey: CacheKey.name) ?? ""
        phoneNumber = defaults.string(forKey: CacheKey.phone) ?? ""
        isStudent = defaults.bool(forKey: CacheKey.isStudent)
        weeklySpendingLimit = defaults.double(forKey: CacheKey.weeklyLimit)
        strictnessLevel = defaults.string(forKey: CacheKey.strictness) ?? ""
        school = defaults.string(forKey: CacheKey.school) ?? ""
    }

    private func saveToCache() {
        defaults.set(name, forKey: CacheKey.name)
        defaults.set(phoneNumber, forKey: CacheKey.phone)
        defaults.set(isStudent, forKey: CacheKey.isStudent)
        defaults.set(weeklySpendingLimit, forKey: CacheKey.weeklyLimit)
        defaults.set(strictnessLevel, forKey: CacheKey.strictness)
        defaults.set(school, forKey: CacheKey.school)
    }

    // MARK: - Public Methods

    func loadProfile() async {
        guard let userId = AuthManager.shared.authToken else { return }

        isLoading = true
        errorMessage = nil

        do {
            let profile = try await apiService.getUserProfile(userId: userId)
            name = profile.name ?? ""
            phoneNumber = profile.phoneNumber ?? ""
            isStudent = profile.profile?.isStudent ?? false
            weeklySpendingLimit = profile.profile?.weeklySpendingLimit ?? 0
            strictnessLevel = profile.profile?.strictnessLevel ?? ""
            school = profile.profile?.school ?? ""
            plaidItems = profile.plaidItems
            saveToCache()
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
                weeklySpendingLimit: weeklySpendingLimit,
                strictnessLevel: strictnessLevel.isEmpty ? nil : strictnessLevel,
                school: school.isEmpty ? nil : school
            )
            try await apiService.updateUserProfile(userId: userId, update: update)

            // Update AuthManager name
            AuthManager.shared.userName = name.isEmpty ? nil : name

            saveToCache()
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
            let url = AppConfig.baseURL.appendingPathComponent("plaid/unlink/\(userId)/\(itemId)")
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
