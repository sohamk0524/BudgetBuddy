//
//  ContentView.swift
//  BudgetBuddy
//
//  Root view with auth routing and TabView for Tips, Expenses, and Profile
//

import SwiftUI

@MainActor
struct ContentView: View {
    @State private var authManager = AuthManager.shared
    @State private var selectedTab = 0
    @State private var expensesViewModel = ExpensesViewModel()
    @State private var showPlaidLink = false
    @State private var hasCompletedPlaidFlow = false

    var body: some View {
        Group {
            if !authManager.isAuthenticated {
                // Show login/registration
                LoginView()
            } else if authManager.needsOnboarding {
                // Show onboarding wizard
                OnboardingWizardView()
            } else if showPlaidLink && !hasCompletedPlaidFlow {
                // Show Plaid Link after onboarding
                PlaidLinkView(
                    showPlaidLink: $showPlaidLink,
                    userId: authManager.authToken ?? "",
                    onComplete: {
                        hasCompletedPlaidFlow = true
                        showPlaidLink = false
                    },
                    onSkip: {
                        hasCompletedPlaidFlow = true
                        showPlaidLink = false
                    }
                )
            } else {
                // Show main app
                mainTabView
            }
        }
        .task {
            // Validate persisted session with the backend on launch
            await authManager.restoreSession()
        }
        .onReceive(NotificationCenter.default.publisher(for: .onboardingCompleted)) { _ in
            // Show Plaid Link after onboarding completes
            showPlaidLink = true
        }
    }

    private var mainTabView: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Recommendations (Tips Dashboard)
            RecommendationsView()
                .tabItem {
                    Label("Tips", systemImage: "lightbulb.fill")
                }
                .tag(0)

            // Tab 2: Expenses (Classification)
            ExpensesView(viewModel: expensesViewModel)
                .tabItem {
                    Label("Expenses", systemImage: "list.bullet.rectangle.fill")
                }
                .tag(1)

            // Tab 3: Profile
            NavigationStack {
                ProfileView()
            }
                .tabItem {
                    Label("Profile", systemImage: "person.circle")
                }
                .tag(2)

            // Tab 4: Plan (Spending Plan) — hidden for now
            // PlanView(viewModel: planViewModel, walletViewModel: walletViewModel)
            //     .tabItem {
            //         Label("Plan", systemImage: "doc.text.fill")
            //     }
            //     .tag(3)
        }
        .tint(Color.accent)
        .onAppear {
            // Configure TabBar appearance for dark theme
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = UIColor(Color.surface)

            // Normal state
            appearance.stackedLayoutAppearance.normal.iconColor = UIColor(Color.textSecondary)
            appearance.stackedLayoutAppearance.normal.titleTextAttributes = [
                .foregroundColor: UIColor(Color.textSecondary)
            ]

            // Selected state
            appearance.stackedLayoutAppearance.selected.iconColor = UIColor(Color.accent)
            appearance.stackedLayoutAppearance.selected.titleTextAttributes = [
                .foregroundColor: UIColor(Color.accent)
            ]

            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
}
