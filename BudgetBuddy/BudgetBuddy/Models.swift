//
//  Models.swift
//  BudgetBuddy
//
//  Data models for the BudgetBuddy app
//

import Foundation

// MARK: - Message Types

enum MessageType {
    case user
    case assistant
}

// MARK: - Visual Components

enum VisualComponent: Codable, Equatable {
    case budgetBurndown(data: [BurndownDataPoint])
    case sankeyFlow(nodes: [SankeyNode])
    case interactiveSlider(category: String, current: Double, max: Double)
    case burndownChart(spent: Double, budget: Double, idealPace: Double)
    case budgetSlider(category: String, current: Double, max: Double)
    case spendingPlan(safeToSpend: Double, categories: [BudgetCategory])
    // Phase 2: New visual payload types
    case comparisonChart(data: ComparisonChartData)
    case goalProgress(data: GoalProgressData)
    case transactionList(data: TransactionListData)
    case actionCard(data: ActionCardData)
    case categoryBreakdown(data: CategoryBreakdownData)
    case insightCard(data: InsightCardData)

    // Custom coding for complex associated values
    enum CodingKeys: String, CodingKey {
        case type
        case data
        case nodes
        case category
        case current
        case max
        case spent
        case budget
        case idealPace
        case safeToSpend
        case categories
        // Phase 2 keys
        case currentPeriod
        case previousPeriod
        case changePercent
        case goals
        case totalCurrent
        case totalTarget
        case overallProgress
        case transactions
        case filters
        case summary
        case title
        case message
        case actions
        case icon
        case severity
        case total
        case insight
        case dataPoints
        case trend
        case recommendation
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)

        switch type {
        case "budgetBurndown":
            let data = try container.decode([BurndownDataPoint].self, forKey: .data)
            self = .budgetBurndown(data: data)
        case "sankeyFlow":
            let nodes = try container.decode([SankeyNode].self, forKey: .nodes)
            self = .sankeyFlow(nodes: nodes)
        case "interactiveSlider":
            let category = try container.decode(String.self, forKey: .category)
            let current = try container.decode(Double.self, forKey: .current)
            let max = try container.decode(Double.self, forKey: .max)
            self = .interactiveSlider(category: category, current: current, max: max)
        case "burndownChart":
            let spent = try container.decode(Double.self, forKey: .spent)
            let budget = try container.decode(Double.self, forKey: .budget)
            let idealPace = try container.decode(Double.self, forKey: .idealPace)
            self = .burndownChart(spent: spent, budget: budget, idealPace: idealPace)
        case "budgetSlider":
            let category = try container.decode(String.self, forKey: .category)
            let current = try container.decode(Double.self, forKey: .current)
            let max = try container.decode(Double.self, forKey: .max)
            self = .budgetSlider(category: category, current: current, max: max)
        case "spendingPlan":
            let safeToSpend = try container.decode(Double.self, forKey: .safeToSpend)
            let categories = try container.decode([BudgetCategory].self, forKey: .categories)
            self = .spendingPlan(safeToSpend: safeToSpend, categories: categories)
        // Phase 2: New visual types
        case "comparisonChart":
            let data = try ComparisonChartData(from: decoder)
            self = .comparisonChart(data: data)
        case "goalProgress":
            let data = try GoalProgressData(from: decoder)
            self = .goalProgress(data: data)
        case "transactionList":
            let data = try TransactionListData(from: decoder)
            self = .transactionList(data: data)
        case "actionCard":
            let data = try ActionCardData(from: decoder)
            self = .actionCard(data: data)
        case "categoryBreakdown":
            let data = try CategoryBreakdownData(from: decoder)
            self = .categoryBreakdown(data: data)
        case "insightCard":
            let data = try InsightCardData(from: decoder)
            self = .insightCard(data: data)
        default:
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Unknown type: \(type)")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)

        switch self {
        case .budgetBurndown(let data):
            try container.encode("budgetBurndown", forKey: .type)
            try container.encode(data, forKey: .data)
        case .sankeyFlow(let nodes):
            try container.encode("sankeyFlow", forKey: .type)
            try container.encode(nodes, forKey: .nodes)
        case .interactiveSlider(let category, let current, let max):
            try container.encode("interactiveSlider", forKey: .type)
            try container.encode(category, forKey: .category)
            try container.encode(current, forKey: .current)
            try container.encode(max, forKey: .max)
        case .burndownChart(let spent, let budget, let idealPace):
            try container.encode("burndownChart", forKey: .type)
            try container.encode(spent, forKey: .spent)
            try container.encode(budget, forKey: .budget)
            try container.encode(idealPace, forKey: .idealPace)
        case .budgetSlider(let category, let current, let max):
            try container.encode("budgetSlider", forKey: .type)
            try container.encode(category, forKey: .category)
            try container.encode(current, forKey: .current)
            try container.encode(max, forKey: .max)
        case .spendingPlan(let safeToSpend, let categories):
            try container.encode("spendingPlan", forKey: .type)
            try container.encode(safeToSpend, forKey: .safeToSpend)
            try container.encode(categories, forKey: .categories)
        // Phase 2: Encode new visual types
        case .comparisonChart(let data):
            try container.encode("comparisonChart", forKey: .type)
            try data.encode(to: encoder)
        case .goalProgress(let data):
            try container.encode("goalProgress", forKey: .type)
            try data.encode(to: encoder)
        case .transactionList(let data):
            try container.encode("transactionList", forKey: .type)
            try data.encode(to: encoder)
        case .actionCard(let data):
            try container.encode("actionCard", forKey: .type)
            try data.encode(to: encoder)
        case .categoryBreakdown(let data):
            try container.encode("categoryBreakdown", forKey: .type)
            try data.encode(to: encoder)
        case .insightCard(let data):
            try container.encode("insightCard", forKey: .type)
            try data.encode(to: encoder)
        }
    }
}

// MARK: - Supporting Data Structures

struct BurndownDataPoint: Codable, Equatable, Identifiable {
    var id: Date { date }
    let date: Date
    let amount: Double
}

struct SankeyNode: Codable, Equatable, Identifiable {
    let id: String
    let name: String
    let value: Double
}

// MARK: - Phase 2 Visual Data Structures

struct ComparisonChartData: Codable, Equatable {
    let currentPeriod: PeriodData
    let previousPeriod: PeriodData
    let categories: [CategoryComparison]?
    let changePercent: Double

    enum CodingKeys: String, CodingKey {
        case currentPeriod
        case previousPeriod
        case categories
        case changePercent
    }
}

struct PeriodData: Codable, Equatable {
    let label: String
    let total: Double
    let startDate: String?
    let endDate: String?
}

struct CategoryComparison: Codable, Equatable, Identifiable {
    var id: String { name }
    let name: String
    let current: Double
    let previous: Double
}

struct GoalProgressData: Codable, Equatable {
    let goals: [GoalProgressItem]
    let totalCurrent: Double
    let totalTarget: Double
    let overallProgress: Double
}

struct GoalProgressItem: Codable, Equatable, Identifiable {
    var id: String { name }
    let name: String
    let current: Double
    let target: Double
    let progressPercent: Double
    let remaining: Double
    let icon: String?
    let color: String?
}

struct TransactionListData: Codable, Equatable {
    let transactions: [TransactionItem]
    let filters: TransactionFilters?
    let summary: TransactionSummary
}

struct TransactionItem: Codable, Equatable, Identifiable {
    let id: String
    let description: String
    let amount: Double
    let isExpense: Bool
    let category: String
    let date: String?
    let merchant: String?
    let icon: String?
}

struct TransactionFilters: Codable, Equatable {
    let category: String?
    let dateRange: DateRange?
    let amountRange: AmountRange?
}

struct DateRange: Codable, Equatable {
    let start: String?
    let end: String?
}

struct AmountRange: Codable, Equatable {
    let min: Double?
    let max: Double?
}

struct TransactionSummary: Codable, Equatable {
    let totalIncome: Double
    let totalExpenses: Double
    let count: Int
}

struct ActionCardData: Codable, Equatable {
    let title: String
    let message: String
    let actions: [ActionButton]
    let icon: String?
    let severity: String
}

struct ActionButton: Codable, Equatable, Identifiable {
    var id: String { label + action }
    let label: String
    let action: String
    let style: String
    let data: [String: String]?

    enum CodingKeys: String, CodingKey {
        case label, action, style, data
    }

    // Memberwise initializer for creating instances in code
    init(label: String, action: String, style: String = "primary", data: [String: String]? = nil) {
        self.label = label
        self.action = action
        self.style = style
        self.data = data
    }

    // Decoder initializer for JSON parsing
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        label = try container.decode(String.self, forKey: .label)
        action = try container.decode(String.self, forKey: .action)
        style = try container.decodeIfPresent(String.self, forKey: .style) ?? "primary"
        data = try container.decodeIfPresent([String: String].self, forKey: .data)
    }
}

struct CategoryBreakdownData: Codable, Equatable {
    let categories: [CategoryBreakdownItem]
    let total: Double
}

struct CategoryBreakdownItem: Codable, Equatable, Identifiable {
    var id: String { name }
    let name: String
    let amount: Double
    let percent: Double
    let color: String?
}

struct InsightCardData: Codable, Equatable {
    let title: String
    let insight: String
    let dataPoints: [InsightDataPoint]?
    let trend: String?
    let recommendation: String?
}

struct InsightDataPoint: Codable, Equatable, Identifiable {
    var id: String { label }
    let label: String
    let value: String
}

// MARK: - Spending Plan Models

struct SpendingPlanInput: Codable {
    var housingSituation: String  // "rent", "own", "family"
    var debtTypes: [String]  // ["student_loans", "credit_cards", "car", "none"]
    var fixedExpenses: FixedExpenses
    var variableSpending: VariableSpending
    var upcomingEvents: [UpcomingEvent]
    var savingsGoals: [SavingsGoal]
    var spendingPreferences: SpendingPreferences

    init() {
        self.housingSituation = "rent"
        self.debtTypes = []
        self.fixedExpenses = FixedExpenses()
        self.variableSpending = VariableSpending()
        self.upcomingEvents = []
        self.savingsGoals = []
        self.spendingPreferences = SpendingPreferences()
    }
}

struct FixedExpenses: Codable {
    var rent: Double = 0
    var utilities: Double = 0
    var subscriptions: [Subscription] = []
}

struct Subscription: Codable, Identifiable {
    let id: UUID
    var name: String
    var amount: Double

    init(id: UUID = UUID(), name: String = "", amount: Double = 0) {
        self.id = id
        self.name = name
        self.amount = amount
    }
}

struct VariableSpending: Codable {
    var groceries: Double = 0
    var transportation: TransportationExpense = TransportationExpense()
    var diningEntertainment: Double = 0
}

struct TransportationExpense: Codable {
    var type: String = "car"  // "car", "transit", "mix"
    var gas: Double = 0
    var insurance: Double = 0
    var transitPass: Double = 0
}

struct UpcomingEvent: Codable, Identifiable {
    let id: UUID
    var name: String
    var date: Date
    var cost: Double
    var saveGradually: Bool

    init(id: UUID = UUID(), name: String = "", date: Date = Date(), cost: Double = 0, saveGradually: Bool = true) {
        self.id = id
        self.name = name
        self.date = date
        self.cost = cost
        self.saveGradually = saveGradually
    }
}

struct SavingsGoal: Codable, Identifiable {
    let id: UUID
    var name: String
    var target: Double
    var current: Double
    var priority: Int

    init(id: UUID = UUID(), name: String = "", target: Double = 0, current: Double = 0, priority: Int = 1) {
        self.id = id
        self.name = name
        self.target = target
        self.current = current
        self.priority = priority
    }
}

struct SpendingPreferences: Codable {
    var spendingStyle: Double = 0.5  // 0.0 = frugal, 1.0 = liberal
    var priorities: [String] = []  // ["savings", "experiences", "security", "flexibility"]
    var strictness: String = "moderate"  // "flexible", "moderate", "strict"
}

// MARK: - Spending Plan Response

struct SpendingPlanResponse: Codable {
    let textMessage: String
    let plan: SpendingPlan?
    let visualPayload: VisualComponent?

    enum CodingKeys: String, CodingKey {
        case textMessage
        case plan
        case visualPayload
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        textMessage = try container.decode(String.self, forKey: .textMessage)
        plan = try container.decodeIfPresent(SpendingPlan.self, forKey: .plan)
        visualPayload = try container.decodeIfPresent(VisualComponent.self, forKey: .visualPayload)
    }
}

struct SpendingPlan: Codable {
    let summary: String
    let safeToSpend: Double
    let totalIncome: Double
    let totalExpenses: Double
    let totalSavings: Double
    let daysRemaining: Int
    let budgetUsedPercent: Double
    let categoryAllocations: [BudgetCategory]
    let recommendations: [Recommendation]
    let warnings: [String]
    let createdAt: String?
}

struct BudgetCategory: Codable, Identifiable, Equatable {
    let id: String
    let name: String
    let amount: Double
    let color: String
    let items: [BudgetItem]?

    static func == (lhs: BudgetCategory, rhs: BudgetCategory) -> Bool {
        lhs.id == rhs.id && lhs.amount == rhs.amount
    }
}

struct BudgetItem: Codable, Equatable {
    let name: String
    let amount: Double
}

struct Recommendation: Codable, Identifiable {
    var id: String { category + title }
    let category: String
    let title: String
    let description: String
    let potentialSavings: Double?
}

// MARK: - Get Plan Response

struct GetPlanResponse: Codable {
    let hasPlan: Bool
    let plan: SpendingPlan?
    let createdAt: String?
    let monthYear: String?
}

// MARK: - Assistant Response

struct AssistantResponse: Codable {
    let textMessage: String
    let visualPayload: VisualComponent?
}

// MARK: - Chat Message

struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let type: MessageType
    let text: String
    let visualPayload: VisualComponent?
    let timestamp: Date

    init(id: UUID = UUID(), type: MessageType, text: String, visualPayload: VisualComponent? = nil, timestamp: Date = Date()) {
        self.id = id
        self.type = type
        self.text = text
        self.visualPayload = visualPayload
        self.timestamp = timestamp
    }
}

// MARK: - Financial Summary (from saved statement)

struct FinancialSummary: Codable {
    let hasStatement: Bool
    let netWorth: Double?
    let safeToSpend: Double?
    let statementInfo: StatementInfo?
    let spendingBreakdown: [SpendingCategory]?
}

struct StatementInfo: Codable {
    let filename: String
    let statementPeriod: String?
    let uploadedAt: String?
}

struct SpendingCategory: Codable, Identifiable {
    var id: String { category }
    let category: String
    let amount: Double
}
