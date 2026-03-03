//
//  PlaidLinkManager.swift
//  BudgetBuddy
//
//  Manages the Plaid Link flow state and presentation
//

import SwiftUI
import LinkKit

/// Manages the Plaid Link flow for connecting bank accounts
@Observable
class PlaidLinkManager {
    static let shared = PlaidLinkManager()

    // MARK: - State

    var isLoading: Bool = false
    var isLinkActive: Bool = false
    var errorMessage: String?
    var linkSuccess: Bool = false
    var linkedAccounts: [PlaidAccountInfo] = []

    // MARK: - Private

    private var linkToken: String?
    private var handler: Handler?

    private init() {}

    // MARK: - Public Methods

    /// Start the Plaid Link flow for a user
    func startLink(userId: Int) async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
            linkSuccess = false
        }

        do {
            // Get link token from backend
            let response = try await PlaidService.shared.createLinkToken(userId: userId)
            linkToken = response.linkToken

            await MainActor.run {
                isLoading = false
                isLinkActive = true
            }
        } catch {
            await MainActor.run {
                isLoading = false
                errorMessage = error.localizedDescription
            }
        }
    }

    /// Create the Link configuration and handler
    func createLinkHandler(userId: Int, completion: @escaping (Bool) -> Void) -> Handler? {
        guard let linkToken = linkToken else {
            errorMessage = "No link token available"
            return nil
        }

        var configuration = LinkTokenConfiguration(token: linkToken) { [weak self] result in
            self?.handleLinkSuccess(result: result, userId: userId, completion: completion)
        }

        configuration.onExit = { [weak self] exit in
            self?.handleLinkExit(exit: exit, completion: completion)
        }

        configuration.onEvent = { event in
            print("Plaid Link Event: \(event.eventName)")
        }

        let result = Plaid.create(configuration)
        switch result {
        case .success(let handler):
            self.handler = handler
            return handler
        case .failure(let error):
            errorMessage = "Failed to create Plaid Link: \(error.localizedDescription)"
            completion(false)
            return nil
        }
    }

    /// Present Plaid Link
    func presentLink(from viewController: UIViewController, userId: Int, completion: @escaping (Bool) -> Void) {
        guard let handler = createLinkHandler(userId: userId, completion: completion) else {
            return
        }

        handler.open(presentUsing: .viewController(viewController))
    }

    /// Reset the manager state
    func reset() {
        isLoading = false
        isLinkActive = false
        errorMessage = nil
        linkSuccess = false
        linkedAccounts = []
        linkToken = nil
        handler = nil
    }

    // MARK: - Private Handlers

    private func handleLinkSuccess(result: LinkSuccess, userId: Int, completion: @escaping (Bool) -> Void) {
        Task {
            await MainActor.run {
                isLoading = true
            }

            do {
                // Exchange the public token
                let institution = result.metadata.institution
                let exchangeResponse = try await PlaidService.shared.exchangePublicToken(
                    userId: userId,
                    publicToken: result.publicToken,
                    institutionId: institution.id,
                    institutionName: institution.name
                )

                await MainActor.run {
                    isLoading = false
                    isLinkActive = false
                    linkSuccess = true
                    linkedAccounts = exchangeResponse.accounts
                    errorMessage = nil
                }

                // Post notification that bank was linked
                await MainActor.run {
                    NotificationCenter.default.post(name: .plaidBankLinked, object: nil)
                }

                completion(true)

            } catch {
                await MainActor.run {
                    isLoading = false
                    isLinkActive = false
                    errorMessage = error.localizedDescription
                }
                completion(false)
            }
        }
    }

    private func handleLinkExit(exit: LinkExit, completion: @escaping (Bool) -> Void) {
        isLinkActive = false

        if let error = exit.error {
            errorMessage = error.localizedDescription
        }

        completion(false)
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let plaidBankLinked = Notification.Name("plaidBankLinked")
    static let onboardingCompleted = Notification.Name("onboardingCompleted")
    static let transactionAdded = Notification.Name("transactionAdded")
}
