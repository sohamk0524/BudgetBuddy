//
//  ContentView.swift
//  BudgetBuddy
//
//  Root view with auth routing and TabView for Chat, Wallet, and Plan
//

import SwiftUI

struct ContentView: View {
    @State private var authManager = AuthManager.shared
    @State private var selectedTab = 0
    @State private var planViewModel = SpendingPlanViewModel()
    @State private var walletViewModel = WalletViewModel()

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
    }

    private var mainTabView: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Chat (Command Center)
            ChatView()
                .tabItem {
                    Label("Chat", systemImage: "message.fill")
                }
                .tag(0)

            // Tab 2: Wallet (Dashboard)
            WalletView(walletViewModel: walletViewModel, planViewModel: planViewModel)
                .tabItem {
                    Label("Wallet", systemImage: "wallet.pass.fill")
                }
                .tag(1)

            // Tab 3: Plan (Spending Plan)
            PlanView(viewModel: planViewModel, walletViewModel: walletViewModel)
                .tabItem {
                    Label("Plan", systemImage: "doc.text.fill")
                }
                .tag(2)
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
