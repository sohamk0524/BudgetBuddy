//
//  ContentView.swift
//  BudgetBuddy
//
//  Root view with TabView for Chat and Wallet
//

import SwiftUI

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Chat (Command Center)
            ChatView()
                .tabItem {
                    Label("Chat", systemImage: "message.fill")
                }
                .tag(0)

            // Tab 2: Wallet (Dashboard)
            WalletView()
                .tabItem {
                    Label("Wallet", systemImage: "wallet.pass.fill")
                }
                .tag(1)
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
