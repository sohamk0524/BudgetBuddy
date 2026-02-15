//
//  OnboardingWizardView.swift
//  BudgetBuddy
//
//  Onboarding wizard – 4-Question Protocol:
//  1. Name  2. Student Status  3. Primary Motivation  4. Strictness Level
//

import SwiftUI

struct OnboardingWizardView: View {
    @State private var currentPage = 0

    // 4-Question Protocol fields
    @State private var name: String = ""
    @State private var isStudent: Bool = false
    @State private var userBudgetingGoal: String = "stability"
    @State private var strictnessLevel: String = "moderate"

    var authManager = AuthManager.shared

    private let totalPages = 4

    private var canFinish: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var body: some View {
        ZStack {
            Color.appBackground
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                VStack(spacing: 8) {
                    Text("Let's Set Up Your Budget")
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)

                    Text("Step \(currentPage + 1) of \(totalPages)")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }
                .padding(.top, 40)
                .padding(.bottom, 24)

                // Page Indicator
                HStack(spacing: 6) {
                    ForEach(0..<totalPages, id: \.self) { index in
                        Capsule()
                            .fill(index == currentPage ? Color.accent : Color.surface)
                            .frame(width: index == currentPage ? 20 : 6, height: 6)
                            .animation(.spring(response: 0.3), value: currentPage)
                    }
                }
                .padding(.bottom, 32)

                // Pages
                TabView(selection: $currentPage) {
                    // Page 0: Name
                    NamePage(name: $name)
                        .tag(0)

                    // Page 1: Student Status
                    StudentStatusPage(isStudent: $isStudent)
                        .tag(1)

                    // Page 2: Primary Motivation ("Why")
                    PrimaryMotivationPage(selectedGoal: $userBudgetingGoal)
                        .tag(2)

                    // Page 3: Strictness Level
                    StrictnessLevelPage(selectedStrictness: $strictnessLevel)
                        .tag(3)
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
                        if currentPage < totalPages - 1 {
                            withAnimation {
                                currentPage += 1
                            }
                        } else {
                            finishOnboarding()
                        }
                    } label: {
                        if authManager.isLoading {
                            ProgressView()
                                .tint(Color.appBackground)
                                .frame(maxWidth: .infinity)
                                .padding()
                        } else {
                            Text(currentPage < totalPages - 1 ? "Next" : "Finish")
                                .font(.roundedHeadline)
                                .foregroundStyle(Color.appBackground)
                                .frame(maxWidth: .infinity)
                                .padding()
                        }
                    }
                    .background(Color.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .disabled(currentPage == totalPages - 1 && !canFinish)
                    .opacity(currentPage == totalPages - 1 && !canFinish ? 0.6 : 1.0)
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
        let trimmedName = name.trimmingCharacters(in: .whitespaces)

        Task {
            await authManager.completeOnboarding(
                name: trimmedName,
                isStudent: isStudent,
                userBudgetingGoal: userBudgetingGoal,
                strictnessLevel: strictnessLevel
            )
        }
    }
}

// MARK: - Name Page

struct NamePage: View {
    @Binding var name: String

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "hand.wave.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("What's Your Name?")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("We'll use this to personalize your experience")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            TextField("e.g., Alex", text: $name)
                .font(.roundedTitle)
                .foregroundStyle(Color.textPrimary)
                .multilineTextAlignment(.center)
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .padding(.horizontal, 48)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Student Status Page

struct StudentStatusPage: View {
    @Binding var isStudent: Bool

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "graduationcap.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Are You a Student?")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("This helps us tailor advice for your situation")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            VStack(spacing: 12) {
                SelectableOptionCard(
                    title: "Yes",
                    subtitle: "I'm currently enrolled in school",
                    isSelected: isStudent
                ) {
                    isStudent = true
                }

                SelectableOptionCard(
                    title: "No",
                    subtitle: "I'm not currently a student",
                    isSelected: !isStudent
                ) {
                    isStudent = false
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Primary Motivation Page

struct PrimaryMotivationPage: View {
    @Binding var selectedGoal: String

    private let options = [
        ("emergency_fund", "Build Emergency Fund", "Save 3-6 months of expenses"),
        ("pay_debt", "Pay Off Debt", "Become debt-free"),
        ("save_purchase", "Save for a Purchase", "Big item like car, vacation, etc."),
        ("stability", "General Stability", "Maintain financial health")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "flag.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Why Are You Here?")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("What's your main reason for using BudgetBuddy?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedGoal == value
                    ) {
                        selectedGoal = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Strictness Level Page

struct StrictnessLevelPage: View {
    @Binding var selectedStrictness: String

    private let options = [
        ("relaxed", "Relaxed", "Guide me gently"),
        ("moderate", "Moderate", "Keep me on track"),
        ("strict", "Strict", "Don't let me overspend")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "slider.horizontal.3")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("How Strict Should We Be?")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Choose how aggressively we should enforce your budget")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedStrictness == value
                    ) {
                        selectedStrictness = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Selectable Option Card (Single Select)

struct SelectableOptionCard: View {
    let title: String
    let subtitle: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text(subtitle)
                        .font(.roundedCaption)
                        .foregroundStyle(Color.textSecondary)
                }

                Spacer()

                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundStyle(isSelected ? Color.accent : Color.textSecondary)
            }
            .padding()
            .background(isSelected ? Color.accent.opacity(0.15) : Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.accent : Color.clear, lineWidth: 2)
            )
        }
    }
}

// MARK: - Preview

#Preview {
    OnboardingWizardView()
}
