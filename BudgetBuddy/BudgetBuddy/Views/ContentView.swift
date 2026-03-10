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
    @State private var insightsViewModel = InsightsViewModel()
    var body: some View {
        Group {
            if !authManager.isAuthenticated {
                // Show login/registration
                LoginView()
            } else if authManager.needsOnboarding {
                // Show onboarding wizard
                OnboardingWizardView()
            } else {
                // Show main app
                mainTabView
            }
        }
        .task {
            // Skip session restore when biometric prompt is showing —
            // authenticateWithBiometrics() calls restoreSession() after a successful unlock.
            guard authManager.authState != .biometricPrompt else { return }
            await authManager.restoreSession()
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

            // Tab 3: Insights
            InsightsView(viewModel: insightsViewModel, selectedTab: $selectedTab)
                .tabItem {
                    Label("Insights", systemImage: "chart.pie.fill")
                }
                .tag(2)

            // Tab 4: Profile
            NavigationStack {
                ProfileView()
            }
                .tabItem {
                    Label("Profile", systemImage: "person.circle")
                }
                .tag(3)
        }
        .tint(Color.accent)
        .onChange(of: selectedTab) { _, newTab in
            let tabs: [AnalyticsManager.Tab] = [.tips, .expenses, .insights, .profile]
            if newTab < tabs.count {
                AnalyticsManager.logTabViewed(tabs[newTab])
            }
        }
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
