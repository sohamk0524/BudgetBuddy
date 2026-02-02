//
//  OnboardingWizardView.swift
//  BudgetBuddy
//
//  Onboarding wizard for collecting user financial profile
//

import SwiftUI

struct OnboardingWizardView: View {
    @State private var currentPage = 0
    @State private var monthlyIncome: String = ""
    @State private var fixedExpenses: String = ""
    @State private var savingsGoalName: String = ""
    @State private var savingsGoalTarget: String = ""

    var authManager = AuthManager.shared

    private var canFinish: Bool {
        !monthlyIncome.isEmpty && !fixedExpenses.isEmpty
    }

    var body: some View {
        ZStack {
            Color.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                VStack(spacing: 8) {
                    Text("Let's Set Up Your Budget")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("Step \(currentPage + 1) of 3")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                .padding(.top, 40)
                .padding(.bottom, 24)

                // Page Indicator
                HStack(spacing: 8) {
                    ForEach(0..<3, id: \.self) { index in
                        Capsule()
                            .fill(index == currentPage ? Color.accent : Color.surface)
                            .frame(width: index == currentPage ? 24 : 8, height: 8)
                            .animation(.spring(response: 0.3), value: currentPage)
                    }
                }
                .padding(.bottom, 32)

                // Pages
                TabView(selection: $currentPage) {
                    // Page 1: Monthly Income
                    OnboardingPage(
                        icon: "dollarsign.circle.fill",
                        title: "Monthly Income",
                        subtitle: "How much do you earn each month after taxes?",
                        placeholder: "e.g., 5000",
                        text: $monthlyIncome,
                        keyboardType: .decimalPad
                    )
                    .tag(0)

                    // Page 2: Fixed Expenses
                    OnboardingPage(
                        icon: "house.fill",
                        title: "Fixed Expenses",
                        subtitle: "Rent, utilities, subscriptions, and other recurring bills",
                        placeholder: "e.g., 2000",
                        text: $fixedExpenses,
                        keyboardType: .decimalPad
                    )
                    .tag(1)

                    // Page 3: Savings Goal
                    SavingsGoalPage(
                        goalName: $savingsGoalName,
                        goalTarget: $savingsGoalTarget
                    )
                    .tag(2)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))

                Spacer()

                // Navigation Buttons
                HStack(spacing: 16) {
                    // Back Button
                    if currentPage > 0 {
                        Button {
                            withAnimation {
                                currentPage -= 1
                            }
                        } label: {
                            Text("Back")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.accent)
                                .frame(maxWidth: .infinity)
                                .padding()
                        }
                        .background(Color.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }

                    // Next / Finish Button
                    Button {
                        if currentPage < 2 {
                            withAnimation {
                                currentPage += 1
                            }
                        } else {
                            finishOnboarding()
                        }
                    } label: {
                        if authManager.isLoading {
                            ProgressView()
                                .tint(Color.background)
                                .frame(maxWidth: .infinity)
                                .padding()
                        } else {
                            Text(currentPage < 2 ? "Next" : "Finish")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.background)
                                .frame(maxWidth: .infinity)
                                .padding()
                        }
                    }
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .disabled(currentPage == 2 && !canFinish)
                    .opacity(currentPage == 2 && !canFinish ? 0.6 : 1.0)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 32)

                // Error Message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                        .padding(.bottom, 16)
                }
            }
        }
    }

    private func finishOnboarding() {
        let income = Double(monthlyIncome) ?? 0.0
        let expenses = Double(fixedExpenses) ?? 0.0
        let goalTarget = Double(savingsGoalTarget) ?? 0.0

        Task {
            await authManager.completeOnboarding(
                income: income,
                expenses: expenses,
                goalName: savingsGoalName,
                goalTarget: goalTarget
            )
        }
    }
}

// MARK: - Onboarding Page Component

struct OnboardingPage: View {
    let icon: String
    let title: String
    let subtitle: String
    let placeholder: String
    @Binding var text: String
    var keyboardType: UIKeyboardType = .default

    var body: some View {
        VStack(spacing: 24) {
            // Icon
            Image(systemName: icon)
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            // Title
            Text(title)
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            // Subtitle
            Text(subtitle)
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            // Input Field
            HStack {
                Text("$")
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textSecondary)

                TextField(placeholder, text: $text)
                    .font(.roundedTitle)
                    .foregroundStyle(Color.textPrimary)
                    .keyboardType(keyboardType)
                    .multilineTextAlignment(.center)
            }
            .padding()
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .padding(.horizontal, 48)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Savings Goal Page

struct SavingsGoalPage: View {
    @Binding var goalName: String
    @Binding var goalTarget: String

    var body: some View {
        VStack(spacing: 24) {
            // Icon
            Image(systemName: "target")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            // Title
            Text("Savings Goal")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            // Subtitle
            Text("What are you saving for? (Optional)")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            // Goal Name
            VStack(alignment: .leading, spacing: 8) {
                Text("Goal Name")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                TextField("e.g., Vacation, Car, Emergency Fund", text: $goalName)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .padding()
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .padding(.horizontal, 32)

            // Goal Amount
            VStack(alignment: .leading, spacing: 8) {
                Text("Target Amount")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                HStack {
                    Text("$")
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)

                    TextField("e.g., 10000", text: $goalTarget)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)
                        .keyboardType(.decimalPad)
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .padding(.horizontal, 32)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Preview

#Preview {
    OnboardingWizardView()
}
