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
        default:
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Unknown type")
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

struct SavingsGoal: Codable, Identifiable, Hashable {
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
    let totalEssential: Double?
    let totalDiscretionary: Double?
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
    var items: [BudgetItem]?
    var essentialAmount: Double? = nil
    var discretionaryAmount: Double? = nil

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

// MARK: - Financial Summary (from Plaid or saved statement)

struct FinancialSummary: Codable {
    let hasData: Bool
    let source: String?
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

// MARK: - Plaid Integration Models

struct PlaidLinkTokenResponse: Codable {
    let linkToken: String
    let expiration: String
}

struct PlaidExchangeRequest: Codable {
    let userId: String
    let publicToken: String
    let institutionId: String?
    let institutionName: String?
}

struct PlaidExchangeResponse: Codable {
    let success: Bool
    let itemId: String
    let accounts: [PlaidAccountInfo]
    let transactionCount: Int
}

struct PlaidAccountInfo: Codable, Identifiable {
    var id: String { accountId }
    let accountId: String
    let name: String
    let type: String?
    let subtype: String?
    let mask: String?
    let balanceCurrent: Double?
    let balanceAvailable: Double?
}

struct PlaidAccountsResponse: Codable {
    let items: [PlaidItemInfo]
}

struct PlaidItemInfo: Codable, Identifiable {
    var id: String { itemId }
    let itemId: String
    let institutionId: String?
    let institutionName: String?
    let status: String
    let createdAt: String?
    let accounts: [PlaidAccountDetail]
}

struct PlaidAccountDetail: Codable, Identifiable {
    var id: String { accountId }
    let accountId: String
    let name: String
    let officialName: String?
    let type: String?
    let subtype: String?
    let mask: String?
    let balanceAvailable: Double?
    let balanceCurrent: Double?
    let balanceLimit: Double?
}

struct PlaidTransaction: Codable, Identifiable {
    var id: String { transactionId }
    let transactionId: String
    let accountId: String
    let amount: Double
    let date: String?
    let authorizedDate: String?
    let name: String
    let merchantName: String?
    let categoryPrimary: String?
    let categoryDetailed: String?
    let pending: Bool
    let paymentChannel: String?
}

struct PlaidTransactionsResponse: Codable {
    let transactions: [PlaidTransaction]
    let total: Int
    let hasMore: Bool
}

struct PlaidSyncResponse: Codable {
    let added: Int
    let modified: Int
    let removed: Int
}

// MARK: - Expense Classification Models

struct ExpenseTransaction: Codable, Identifiable {
    let id: Int
    let transactionId: String
    let accountId: String
    let amount: Double
    let date: String?
    let authorizedDate: String?
    let name: String
    let merchantName: String?
    let categoryPrimary: String?
    let categoryDetailed: String?
    let pending: Bool
    let paymentChannel: String?
    let subCategory: String
    let essentialAmount: Double?
    let discretionaryAmount: Double?
    let source: String?
    let notes: String?
    let receiptItems: [ReceiptLineItem]?
}

struct ExpensesSummary {
    let totalFood: Double
    let totalDrink: Double
    let totalGroceries: Double
    let totalTransportation: Double
    let totalEntertainment: Double
    let totalOther: Double
    let totalUnclassified: Double

    var total: Double { totalFood + totalDrink + totalGroceries + totalTransportation + totalEntertainment + totalOther + totalUnclassified }
}

struct ExpensesResponse: Codable {
    let transactions: [ExpenseTransaction]
    let total: Int
    let hasMore: Bool
}

struct MerchantClassificationInfo: Codable, Identifiable {
    var id: String { merchantName }
    let merchantName: String
    let classification: String
    let essentialRatio: Double
    let confidence: String
    let classificationCount: Int
}

struct MerchantClassificationsResponse: Codable {
    let classifications: [MerchantClassificationInfo]
}

struct ClassifyMerchantResponse: Codable {
    let success: Bool
    let reclassifiedCount: Int
}

struct ClassifiedTransactionInfo: Codable {
    let id: Int
    let subCategory: String
    let essentialAmount: Double?
    let discretionaryAmount: Double?
}

struct ChallengeInfo: Codable {
    let show: Bool
    let reason: String?
}

struct ClassifyTransactionResponse: Codable {
    let success: Bool
    let transaction: ClassifiedTransactionInfo
    let updatedMerchantRatio: Double
    let autoApplied: Int?
    let challenge: ChallengeInfo?
}

struct UnclassifiedMerchant: Codable, Identifiable {
    var id: String { merchantName }
    let merchantName: String
    let totalSpent: Double
    let transactionCount: Int
}

struct UnclassifiedMerchantsResponse: Codable {
    let merchants: [UnclassifiedMerchant]
}

struct MerchantContext: Codable {
    let totalUnclassified: Int
    let totalSpent: Double
    let alreadyClassified: Int
}

struct UnclassifiedTransactionItem: Codable, Identifiable {
    let id: Int
    let transactionId: String
    let merchantName: String?
    let amount: Double
    let date: String?
    let name: String
    let source: String?
    let merchantContext: MerchantContext?

    var isVoice: Bool { source == "voice" }
}

struct UnclassifiedTransactionsResponse: Codable {
    let transactions: [UnclassifiedTransactionItem]
    let totalUnclassified: Int
}

struct AutoClassifyMerchantResult: Codable {
    let merchantName: String
    let classification: String
    let essentialRatio: Double
    let transactionsUpdated: Int
}

struct AutoClassifyResponse: Codable {
    let classified: Int
    let merchants: [AutoClassifyMerchantResult]
}

// MARK: - Receipt Scanning Models

struct ReceiptLineItem: Codable, Identifiable {
    let id = UUID()
    let name: String
    let price: Double
    var category: String  // "food", "drink", "transportation", "entertainment", "other"

    enum CodingKeys: String, CodingKey {
        case name, price
        case category = "classification"  // JSON key kept for backward compat
    }
}

struct ReceiptAnalysisResult: Codable {
    let merchant: String
    let date: String?
    let total: Double
    let items: [ReceiptLineItem]
}

struct ReceiptAttachRequest: Codable {
    let userId: String
    let merchant: String
    let total: Double
    let items: [ReceiptLineItem]
    let category: String  // "food", "drink", "transportation", "entertainment", "other"
    let date: String
}

struct ReceiptAttachResponse: Codable {
    let transactionId: Int
    let source: String   // "plaid" | "manual"
    let enriched: Bool
}

struct AddReceiptItemsResponse: Codable {
    let success: Bool
    let itemCount: Int
    let subCategory: String?
}

// MARK: - User Profile Models

struct UserProfile: Codable {
    let name: String?
    let phoneNumber: String?
    let profile: FinancialProfileInfo?
    let plaidItems: [PlaidItemInfo]
}

struct FinancialProfileInfo: Codable {
    let isStudent: Bool?
    let weeklySpendingLimit: Double?
    let strictnessLevel: String?
    let school: String?
}

struct UserProfileUpdateRequest: Codable {
    var name: String?
    var isStudent: Bool?
    var weeklySpendingLimit: Double?
    var strictnessLevel: String?
    var school: String?
}

// MARK: - Top Expenses Models

struct TopExpensesResponse: Codable {
    let source: String
    let topExpenses: [TopExpense]
    let totalSpending: Double
    let period: Int
}

struct TopExpense: Codable, Identifiable {
    var id: String { category }
    let category: String
    let amount: Double
    let transactionCount: Int
}

// MARK: - Category Preference Models

struct CategoryPreferencesResponse: Codable {
    let categories: [CategoryPreference]
}

struct CategoryPreference: Codable, Identifiable {
    let id: Int
    let categoryName: String
    let displayOrder: Int
}

// MARK: - Smart Nudge Models

struct NudgesResponse: Codable {
    let nudges: [SmartNudge]
}

struct SmartNudge: Codable, Identifiable {
    var id: String { (type ?? "unknown") + (title ?? "untitled") }
    let type: String?
    let title: String?
    let message: String?
    let potentialSavings: Double?
    let category: String?
}

// MARK: - Recommendation Models

struct RecommendationItem: Codable, Identifiable {
    var id: String { category + title }
    let category: String
    let title: String
    let description: String
    let potentialSavings: Double?
    let priority: Int?
    let icon: String?
}

struct RecommendationsResponse: Codable {
    let recommendations: [RecommendationItem]
    let safeToSpend: Double?
    let status: String?
    let summary: String?
    let cached: Bool?
    let generatedAt: String?
}

// MARK: - Voice Transaction Models

struct VoiceTransaction: Codable, Identifiable {
    let id: UUID
    var amount: Double?
    var category: String?  // "Food", "Drink", "Groceries", "Transportation", "Entertainment", "Other"
    var store: String?
    var date: Date
    var notes: String?
    var items: [EditableReceiptItem]

    init(id: UUID = UUID(), amount: Double? = nil, category: String? = nil,
         store: String? = nil, date: Date = Date(), notes: String? = nil,
         items: [EditableReceiptItem] = []) {
        self.id = id; self.amount = amount; self.category = category
        self.store = store; self.date = date; self.notes = notes; self.items = items
    }
}

struct ParsedTransactionResponse: Codable {
    let amount: Double?
    let category: String?
    let store: String?
    let date: String?
    let notes: String?
}

// Multi-transaction parse response (new grouped format)
struct ParsedTransactionGroupResponse: Codable {
    let transactions: [ParsedTransactionWithItems]
}

struct ParsedTransactionWithItems: Codable {
    let amount: Double?
    let category: String?
    let store: String?
    let date: String?
    let notes: String?
    let items: [ParsedItem]?
}

struct ParsedItem: Codable {
    let name: String
    let price: Double
    let classification: String
}

struct SaveTransactionRequest: Codable {
    let userId: String
    let amount: Double
    let category: String  // "Food", "Drink", "Groceries", "Transportation", "Entertainment", "Other"
    let store: String?
    let date: String   // ISO 8601
    let notes: String?
    let source: String?  // "manual" or "voice"
    let receiptItems: [[String: String]]?  // [{name, price, category}]
}

struct SaveTransactionResponse: Codable {
    let success: Bool
    let transactionId: String?
}
