//
//  PlanQuestionFlowView.swift
//  BudgetBuddy
//
//  Conversational question flow for gathering spending plan data
//

import SwiftUI

struct PlanQuestionFlowView: View {
    @Bindable var viewModel: SpendingPlanViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            Color.appBackground
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                headerView

                // Progress
                progressView
                    .padding(.horizontal, 24)
                    .padding(.top, 16)

                // Question Content
                if let question = viewModel.currentQuestion {
                    questionContent(for: question)
                        .transition(.asymmetric(
                            insertion: .move(edge: .trailing).combined(with: .opacity),
                            removal: .move(edge: .leading).combined(with: .opacity)
                        ))
                        .id(question.id)
                }

                Spacer()

                // Navigation
                navigationButtons
                    .padding(.horizontal, 24)
                    .padding(.bottom, 32)
            }
        }
        .animation(.spring(response: 0.3), value: viewModel.currentQuestionIndex)
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.title3)
                    .foregroundStyle(Color.textSecondary)
            }

            Spacer()

            Text("Generate Your Plan")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)

            Spacer()

            // Spacer to balance the X button
            Color.clear
                .frame(width: 24, height: 24)
        }
        .padding(.horizontal, 24)
        .padding(.top, 16)
    }

    // MARK: - Progress

    private var progressView: some View {
        VStack(spacing: 8) {
            HStack {
                Text(viewModel.currentQuestion?.category ?? "")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.accent)

                Spacer()

                Text("\(viewModel.currentQuestionIndex + 1) of \(viewModel.totalQuestions)")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.surface)
                        .frame(height: 8)

                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.accent)
                        .frame(width: geometry.size.width * viewModel.progress, height: 8)
                        .animation(.spring(response: 0.3), value: viewModel.progress)
                }
            }
            .frame(height: 8)
        }
    }

    // MARK: - Question Content

    @ViewBuilder
    private func questionContent(for question: SpendingPlanViewModel.Question) -> some View {
        ScrollView {
            VStack(spacing: 24) {
                // Question Title
                VStack(spacing: 8) {
                    Text(question.title)
                        .font(.roundedTitle)
                        .foregroundStyle(Color.textPrimary)
                        .multilineTextAlignment(.center)

                    Text(question.subtitle)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 32)

                // Question Input
                questionInput(for: question)
                    .padding(.horizontal, 24)
            }
        }
    }

    @ViewBuilder
    private func questionInput(for question: SpendingPlanViewModel.Question) -> some View {
        switch question.type {
        case .currency(let keyPath):
            CurrencyInputView(value: Binding(
                get: { viewModel.planInput[keyPath: keyPath] },
                set: { viewModel.planInput[keyPath: keyPath] = $0 }
            ))

        case .picker(let options, let keyPath):
            PickerInputView(
                options: options,
                selection: Binding(
                    get: { viewModel.planInput[keyPath: keyPath] },
                    set: { viewModel.planInput[keyPath: keyPath] = $0 }
                )
            )

        case .slider(let range, let keyPath):
            SliderInputView(
                value: Binding(
                    get: { viewModel.planInput[keyPath: keyPath] },
                    set: { viewModel.planInput[keyPath: keyPath] = $0 }
                ),
                range: range
            )

        case .subscriptions:
            SubscriptionsInputView(viewModel: viewModel)

        case .upcomingEvents:
            UpcomingEventsInputView(viewModel: viewModel)

        case .savingsGoals:
            SavingsGoalsInputView(viewModel: viewModel)

        case .transportationType:
            TransportationInputView(viewModel: viewModel)

        case .multiSelect:
            EmptyView() // Placeholder

        case .housingSituation:
            HousingSituationInputView(
                selection: $viewModel.planInput.housingSituation
            )

        case .debtTypes:
            DebtTypesInputView(
                selectedTypes: $viewModel.planInput.debtTypes
            )
        }
    }

    // MARK: - Navigation

    private var navigationButtons: some View {
        HStack(spacing: 16) {
            if viewModel.canGoBack {
                Button {
                    viewModel.previousQuestion()
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

            Button {
                if viewModel.isLastQuestion {
                    Task {
                        await viewModel.generatePlan()
                    }
                } else {
                    viewModel.nextQuestion()
                }
            } label: {
                if viewModel.isGenerating {
                    ProgressView()
                        .tint(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                } else {
                    Text(viewModel.isLastQuestion ? "Generate Plan" : "Next")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.appBackground)
                        .frame(maxWidth: .infinity)
                        .padding()
                }
            }
            .background(Color.accent)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .disabled(viewModel.isGenerating)
        }
    }
}

// MARK: - Currency Input

struct CurrencyInputView: View {
    @Binding var value: Double
    @State private var textValue: String = ""

    var body: some View {
        HStack {
            Text("$")
                .font(.roundedTitle)
                .foregroundStyle(Color.textSecondary)

            TextField("0", text: $textValue)
                .font(.roundedTitle)
                .foregroundStyle(Color.textPrimary)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.center)
                .onChange(of: textValue) { _, newValue in
                    value = Double(newValue) ?? 0
                }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .onAppear {
            if value > 0 {
                textValue = String(format: "%.0f", value)
            }
        }
    }
}

// MARK: - Picker Input

struct PickerInputView: View {
    let options: [(String, String)]
    @Binding var selection: String

    var body: some View {
        VStack(spacing: 12) {
            ForEach(options, id: \.0) { value, label in
                Button {
                    selection = value
                } label: {
                    HStack {
                        Text(label)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)

                        Spacer()

                        Image(systemName: selection == value ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(selection == value ? Color.accent : Color.textSecondary)
                    }
                    .padding()
                    .background(selection == value ? Color.accent.opacity(0.15) : Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(selection == value ? Color.accent : Color.clear, lineWidth: 2)
                    )
                }
            }
        }
    }
}

// MARK: - Slider Input

struct SliderInputView: View {
    @Binding var value: Double
    let range: ClosedRange<Double>

    private var label: String {
        if value < 0.33 {
            return "Frugal"
        } else if value < 0.66 {
            return "Balanced"
        } else {
            return "Liberal"
        }
    }

    var body: some View {
        VStack(spacing: 16) {
            Text(label)
                .font(.roundedHeadline)
                .foregroundStyle(Color.accent)

            Slider(value: $value, in: range)
                .tint(Color.accent)

            HStack {
                Text("Frugal")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)

                Spacer()

                Text("Liberal")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

// MARK: - Subscriptions Input

struct SubscriptionsInputView: View {
    @Bindable var viewModel: SpendingPlanViewModel

    private func binding(for id: UUID) -> Binding<Subscription> {
        Binding(
            get: { viewModel.planInput.fixedExpenses.subscriptions.first { $0.id == id } ?? Subscription() },
            set: { newValue in
                if let i = viewModel.planInput.fixedExpenses.subscriptions.firstIndex(where: { $0.id == id }) {
                    viewModel.planInput.fixedExpenses.subscriptions[i] = newValue
                }
            }
        )
    }

    var body: some View {
        VStack(spacing: 12) {
            ForEach(viewModel.planInput.fixedExpenses.subscriptions) { sub in
                let b = binding(for: sub.id)
                HStack {
                    TextField("Name", text: b.name)
                        .font(.roundedBody)
                        .foregroundStyle(Color.textPrimary)

                    Spacer()

                    HStack {
                        Text("$")
                            .foregroundStyle(Color.textSecondary)

                        TextField("0", value: b.amount, format: .number)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)
                            .keyboardType(.decimalPad)
                            .frame(width: 60)
                    }

                    Button {
                        viewModel.planInput.fixedExpenses.subscriptions.removeAll { $0.id == sub.id }
                    } label: {
                        Image(systemName: "minus.circle.fill")
                            .foregroundStyle(Color.danger)
                    }
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Button {
                viewModel.addSubscription()
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Subscription")
                }
                .font(.roundedBody)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
}

// MARK: - Transportation Input

struct TransportationInputView: View {
    @Bindable var viewModel: SpendingPlanViewModel

    var body: some View {
        VStack(spacing: 16) {
            // Type selection
            HStack(spacing: 12) {
                TransportTypeButton(
                    icon: "car.fill",
                    label: "Car",
                    isSelected: viewModel.planInput.variableSpending.transportation.type == "car"
                ) {
                    viewModel.planInput.variableSpending.transportation.type = "car"
                }

                TransportTypeButton(
                    icon: "bus.fill",
                    label: "Transit",
                    isSelected: viewModel.planInput.variableSpending.transportation.type == "transit"
                ) {
                    viewModel.planInput.variableSpending.transportation.type = "transit"
                }

                TransportTypeButton(
                    icon: "figure.walk",
                    label: "Mix",
                    isSelected: viewModel.planInput.variableSpending.transportation.type == "mix"
                ) {
                    viewModel.planInput.variableSpending.transportation.type = "mix"
                }
            }

            // Conditional inputs based on type
            if viewModel.planInput.variableSpending.transportation.type == "car" ||
               viewModel.planInput.variableSpending.transportation.type == "mix" {
                VStack(spacing: 12) {
                    ExpenseRow(label: "Gas", value: $viewModel.planInput.variableSpending.transportation.gas)
                    ExpenseRow(label: "Insurance", value: $viewModel.planInput.variableSpending.transportation.insurance)
                }
            }

            if viewModel.planInput.variableSpending.transportation.type == "transit" ||
               viewModel.planInput.variableSpending.transportation.type == "mix" {
                ExpenseRow(label: "Transit Pass", value: $viewModel.planInput.variableSpending.transportation.transitPass)
            }
        }
    }
}

struct TransportTypeButton: View {
    let icon: String
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(label)
                    .font(.roundedCaption)
            }
            .foregroundStyle(isSelected ? Color.accent : Color.textSecondary)
            .frame(maxWidth: .infinity)
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

struct ExpenseRow: View {
    let label: String
    @Binding var value: Double
    @State private var textValue: String = ""

    var body: some View {
        HStack {
            Text(label)
                .font(.roundedBody)
                .foregroundStyle(Color.textPrimary)

            Spacer()

            HStack {
                Text("$")
                    .foregroundStyle(Color.textSecondary)

                TextField("0", text: $textValue)
                    .font(.roundedBody)
                    .foregroundStyle(Color.textPrimary)
                    .keyboardType(.decimalPad)
                    .frame(width: 80)
                    .multilineTextAlignment(.trailing)
                    .onChange(of: textValue) { _, newValue in
                        value = Double(newValue) ?? 0
                    }
            }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .onAppear {
            if value > 0 {
                textValue = String(format: "%.0f", value)
            }
        }
    }
}

// MARK: - Upcoming Events Input

struct UpcomingEventsInputView: View {
    @Bindable var viewModel: SpendingPlanViewModel

    private func binding(for id: UUID) -> Binding<UpcomingEvent> {
        Binding(
            get: { viewModel.planInput.upcomingEvents.first { $0.id == id } ?? UpcomingEvent() },
            set: { newValue in
                if let i = viewModel.planInput.upcomingEvents.firstIndex(where: { $0.id == id }) {
                    viewModel.planInput.upcomingEvents[i] = newValue
                }
            }
        )
    }

    var body: some View {
        VStack(spacing: 12) {
            ForEach(viewModel.planInput.upcomingEvents) { event in
                let b = binding(for: event.id)
                VStack(spacing: 8) {
                    HStack {
                        TextField("Event name", text: b.name)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)

                        Button {
                            viewModel.planInput.upcomingEvents.removeAll { $0.id == event.id }
                        } label: {
                            Image(systemName: "minus.circle.fill")
                                .foregroundStyle(Color.danger)
                        }
                    }

                    HStack {
                        DatePicker("", selection: b.date, displayedComponents: .date)
                            .labelsHidden()

                        Spacer()

                        HStack {
                            Text("$")
                                .foregroundStyle(Color.textSecondary)

                            TextField("Cost", value: b.cost, format: .number)
                                .font(.roundedBody)
                                .foregroundStyle(Color.textPrimary)
                                .keyboardType(.decimalPad)
                                .frame(width: 80)
                        }
                    }

                    Toggle("Save gradually", isOn: b.saveGradually)
                        .font(.roundedCaption)
                        .tint(Color.accent)
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Button {
                viewModel.addUpcomingEvent()
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Event")
                }
                .font(.roundedBody)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            if viewModel.planInput.upcomingEvents.isEmpty {
                Text("No big expenses? Tap 'Next' to continue")
                    .font(.roundedCaption)
                    .foregroundStyle(Color.textSecondary)
            }
        }
    }
}

// MARK: - Savings Goals Input

struct SavingsGoalsInputView: View {
    @Bindable var viewModel: SpendingPlanViewModel

    private func binding(for id: UUID) -> Binding<SavingsGoal> {
        Binding(
            get: { viewModel.planInput.savingsGoals.first { $0.id == id } ?? SavingsGoal() },
            set: { newValue in
                if let i = viewModel.planInput.savingsGoals.firstIndex(where: { $0.id == id }) {
                    viewModel.planInput.savingsGoals[i] = newValue
                }
            }
        )
    }

    var body: some View {
        VStack(spacing: 12) {
            ForEach(viewModel.planInput.savingsGoals) { goal in
                let b = binding(for: goal.id)
                VStack(spacing: 8) {
                    HStack {
                        TextField("Goal name", text: b.name)
                            .font(.roundedBody)
                            .foregroundStyle(Color.textPrimary)

                        Button {
                            viewModel.planInput.savingsGoals.removeAll { $0.id == goal.id }
                        } label: {
                            Image(systemName: "minus.circle.fill")
                                .foregroundStyle(Color.danger)
                        }
                    }

                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Target")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)

                            HStack {
                                Text("$")
                                    .foregroundStyle(Color.textSecondary)

                                TextField("0", value: b.target, format: .number)
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)
                                    .keyboardType(.decimalPad)
                            }
                        }

                        Spacer()

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Current")
                                .font(.roundedCaption)
                                .foregroundStyle(Color.textSecondary)

                            HStack {
                                Text("$")
                                    .foregroundStyle(Color.textSecondary)

                                TextField("0", value: b.current, format: .number)
                                    .font(.roundedBody)
                                    .foregroundStyle(Color.textPrimary)
                                    .keyboardType(.decimalPad)
                            }
                        }
                    }
                }
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Button {
                viewModel.addSavingsGoal()
            } label: {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Savings Goal")
                }
                .font(.roundedBody)
                .foregroundStyle(Color.accent)
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
}

// MARK: - Housing Situation Input

struct HousingSituationInputView: View {
    @Binding var selection: String

    private let options = [
        ("rent", "Renting", "I pay rent monthly"),
        ("own", "Own Home", "I have a mortgage or own outright"),
        ("family", "Living with Family", "No housing payment")
    ]

    var body: some View {
        VStack(spacing: 12) {
            ForEach(options, id: \.0) { value, title, subtitle in
                Button {
                    selection = value
                } label: {
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

                        Image(systemName: selection == value ? "checkmark.circle.fill" : "circle")
                            .font(.title2)
                            .foregroundStyle(selection == value ? Color.accent : Color.textSecondary)
                    }
                    .padding()
                    .background(selection == value ? Color.accent.opacity(0.15) : Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(selection == value ? Color.accent : Color.clear, lineWidth: 2)
                    )
                }
            }
        }
    }
}

// MARK: - Debt Types Input

struct DebtTypesInputView: View {
    @Binding var selectedTypes: [String]

    private let options = [
        ("student_loans", "Student Loans", "Education debt"),
        ("credit_cards", "Credit Cards", "Revolving credit"),
        ("car", "Car Payment", "Auto loan"),
        ("none", "No Debt", "Debt-free")
    ]

    var body: some View {
        VStack(spacing: 12) {
            ForEach(options, id: \.0) { value, title, subtitle in
                Button {
                    toggleSelection(value)
                } label: {
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

                        Image(systemName: selectedTypes.contains(value) ? "checkmark.square.fill" : "square")
                            .font(.title2)
                            .foregroundStyle(selectedTypes.contains(value) ? Color.accent : Color.textSecondary)
                    }
                    .padding()
                    .background(selectedTypes.contains(value) ? Color.accent.opacity(0.15) : Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(selectedTypes.contains(value) ? Color.accent : Color.clear, lineWidth: 2)
                    )
                }
            }
        }
    }

    private func toggleSelection(_ value: String) {
        if value == "none" {
            // If "No Debt" is selected, clear all others
            if selectedTypes.contains(value) {
                selectedTypes.removeAll { $0 == value }
            } else {
                selectedTypes = [value]
            }
        } else {
            // Remove "none" if selecting a debt type
            selectedTypes.removeAll { $0 == "none" }
            if selectedTypes.contains(value) {
                selectedTypes.removeAll { $0 == value }
            } else {
                selectedTypes.append(value)
            }
        }
    }
}

#Preview {
    PlanQuestionFlowView(viewModel: SpendingPlanViewModel())
}
