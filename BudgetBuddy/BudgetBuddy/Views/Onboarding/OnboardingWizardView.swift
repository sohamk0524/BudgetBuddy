//
//  OnboardingWizardView.swift
//  BudgetBuddy
//
//  Onboarding wizard for collecting user financial profile
//

import SwiftUI

struct OnboardingWizardView: View {
    @State private var currentPage = 0

    // General profile fields
    @State private var age: String = ""
    @State private var occupation: String = ""
    @State private var monthlyIncome: String = ""
    @State private var incomeFrequency: String = "monthly"
    @State private var financialPersonality: String = "balanced"
    @State private var primaryGoal: String = "stability"

    var authManager = AuthManager.shared

    private let totalPages = 6

    private var canFinish: Bool {
        !monthlyIncome.isEmpty
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
                    // Page 1: Age
                    AgePage(age: $age)
                        .tag(0)

                    // Page 2: Occupation
                    OccupationPage(occupation: $occupation)
                        .tag(1)

                    // Page 3: Monthly Income
                    OnboardingPage(
                        icon: "dollarsign.circle.fill",
                        title: "Monthly Income",
                        subtitle: "How much do you earn each month after taxes?",
                        placeholder: "e.g., 5000",
                        text: $monthlyIncome,
                        keyboardType: .decimalPad
                    )
                    .tag(2)

                    // Page 4: Income Frequency
                    IncomeFrequencyPage(selectedFrequency: $incomeFrequency)
                        .tag(3)

                    // Page 5: Financial Personality
                    FinancialPersonalityPage(selectedPersonality: $financialPersonality)
                        .tag(4)

                    // Page 6: Primary Goal
                    PrimaryGoalPage(selectedGoal: $primaryGoal)
                        .tag(5)
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
        let income = Double(monthlyIncome) ?? 0.0
        let ageInt = Int(age) ?? 0

        Task {
            await authManager.completeOnboarding(
                age: ageInt,
                occupation: occupation,
                income: income,
                incomeFrequency: incomeFrequency,
                financialPersonality: financialPersonality,
                primaryGoal: primaryGoal
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

// MARK: - Age Page

struct AgePage: View {
    @Binding var age: String

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "person.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Your Age")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("This helps us tailor advice for your life stage")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            TextField("e.g., 25", text: $age)
                .font(.roundedTitle)
                .foregroundStyle(Color.textPrimary)
                .keyboardType(.numberPad)
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

// MARK: - Occupation Page

struct OccupationPage: View {
    @Binding var occupation: String

    private let options = [
        ("student", "Student", "Currently in school or university"),
        ("employed", "Employed", "Working full-time or part-time"),
        ("self_employed", "Self-Employed", "Freelancer or business owner"),
        ("retired", "Retired", "No longer working")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "briefcase.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Your Occupation")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("What best describes your work situation?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: occupation == value
                    ) {
                        occupation = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Income Frequency Page

struct IncomeFrequencyPage: View {
    @Binding var selectedFrequency: String

    private let options = [
        ("biweekly", "Biweekly", "Every two weeks"),
        ("monthly", "Monthly", "Once a month"),
        ("irregular", "Irregular", "Varies each month")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "calendar.badge.clock")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Income Frequency")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("How often do you get paid?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedFrequency == value
                    ) {
                        selectedFrequency = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Housing Situation Page

struct HousingSituationPage: View {
    @Binding var selectedSituation: String

    private let options = [
        ("rent", "Renting", "I pay rent monthly"),
        ("own", "Own Home", "I have a mortgage or own outright"),
        ("family", "Living with Family", "No housing payment")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "house.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Housing Situation")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("What's your current living arrangement?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedSituation == value
                    ) {
                        selectedSituation = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Debt Types Page

struct DebtTypesPage: View {
    @Binding var selectedDebtTypes: Set<String>

    private let options = [
        ("student_loans", "Student Loans", "Education debt"),
        ("credit_cards", "Credit Cards", "Revolving credit"),
        ("car", "Car Payment", "Auto loan"),
        ("none", "No Debt", "Debt-free")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "creditcard.fill")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Debt Obligations")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("Select all that apply")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    MultiSelectOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedDebtTypes.contains(value)
                    ) {
                        if value == "none" {
                            // If "No Debt" is selected, clear all others
                            if selectedDebtTypes.contains(value) {
                                selectedDebtTypes.remove(value)
                            } else {
                                selectedDebtTypes = [value]
                            }
                        } else {
                            // Remove "none" if selecting a debt type
                            selectedDebtTypes.remove("none")
                            if selectedDebtTypes.contains(value) {
                                selectedDebtTypes.remove(value)
                            } else {
                                selectedDebtTypes.insert(value)
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Financial Personality Page

struct FinancialPersonalityPage: View {
    @Binding var selectedPersonality: String

    private let options = [
        ("aggressive_saver", "Aggressive Saver", "I prioritize saving over spending"),
        ("balanced", "Balanced", "I maintain a healthy balance"),
        ("relaxed", "Relaxed", "Most of my income goes to expenses")
    ]

    var body: some View {
        VStack(spacing: 24) {
            Image(systemName: "person.fill.questionmark")
                .font(.system(size: 56))
                .foregroundStyle(Color.accent)

            Text("Financial Personality")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("How would you describe your spending style?")
                .font(.roundedBody)
                .foregroundStyle(Color.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            VStack(spacing: 12) {
                ForEach(options, id: \.0) { value, title, subtitle in
                    SelectableOptionCard(
                        title: title,
                        subtitle: subtitle,
                        isSelected: selectedPersonality == value
                    ) {
                        selectedPersonality = value
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()
        }
        .padding(.top, 24)
    }
}

// MARK: - Primary Goal Page

struct PrimaryGoalPage: View {
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

            Text("Primary Goal")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Text("What's your main financial priority right now?")
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

// MARK: - Multi-Select Option Card

struct MultiSelectOptionCard: View {
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

                Image(systemName: isSelected ? "checkmark.square.fill" : "square")
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
