//
//  AnalyticsManager.swift
//  BudgetBuddy
//
//  Centralised Firebase Analytics wrapper.
//  All event names and parameter keys are defined here so they stay consistent.
//
//  Each log* call fires an individual event visible in Firebase Analytics → Events.
//  Each setFeatureUsed* call sets a persistent user property visible in
//  Firebase Analytics → User Properties, letting you slice any report or
//  build custom audiences per feature (e.g. "users who have ever added an expense").
//

import FirebaseAnalytics
import Foundation

enum AnalyticsManager {

    // MARK: - Session

    static func logSessionStart() {
        Analytics.logEvent("session_start", parameters: nil)
    }

    // MARK: - Tab Navigation

    enum Tab: String {
        case tips
        case expenses
        case insights
        case profile
    }

    static func logTabViewed(_ tab: Tab) {
        Analytics.logEvent("tab_viewed", parameters: ["tab_name": tab.rawValue])
    }

    // MARK: - Expenses

    /// Fired each time the Expenses tab is opened. Also marks the user as an
    /// expense viewer so they appear in the "Expense Users" audience.
    static func logExpensesViewed() {
        Analytics.logEvent("expenses_viewed", parameters: nil)
        Analytics.setUserProperty("true", forName: "used_expenses")
    }

    static func logTransactionTapped() {
        Analytics.logEvent("transaction_tapped", parameters: nil)
    }

    enum AddMethod: String {
        case manual
        case voice
        case receipt
    }

    /// Fired when the user picks an add-transaction method from the dialog.
    static func logExpenseAdded(method: AddMethod) {
        Analytics.logEvent("expense_added", parameters: ["method": method.rawValue])
        Analytics.setUserProperty("true", forName: "used_add_expense")
        // Record the specific method they've ever used
        Analytics.setUserProperty("true", forName: "used_add_expense_\(method.rawValue)")
    }

    static func logExpenseClassified() {
        Analytics.logEvent("expense_classified", parameters: nil)
        Analytics.setUserProperty("true", forName: "used_classify_expense")
    }

    // MARK: - Recommendations

    static func logRecommendationsViewed() {
        Analytics.logEvent("recommendations_viewed", parameters: nil)
        Analytics.setUserProperty("true", forName: "used_recommendations")
    }

    static func logRecommendationExpanded(title: String) {
        Analytics.logEvent("recommendation_expanded", parameters: ["title": title])
        Analytics.setUserProperty("true", forName: "used_recommendation_expanded")
    }

    static func logRecommendationsGenerated() {
        Analytics.logEvent("recommendations_generated", parameters: nil)
        Analytics.setUserProperty("true", forName: "used_recommendations_generated")
    }

    // MARK: - Insights

    static func logInsightsViewed() {
        Analytics.logEvent("insights_viewed", parameters: nil)
        Analytics.setUserProperty("true", forName: "used_insights")
    }

    static func logInsightsDateRangeChanged(range: String) {
        Analytics.logEvent("insights_date_range_changed", parameters: ["range": range])
    }

    static func logInsightsCategoryTapped(category: String) {
        Analytics.logEvent("insights_category_tapped", parameters: ["category": category])
    }

    static func logInsightsBarGroupingChanged(grouping: String) {
        Analytics.logEvent("insights_bar_grouping_changed", parameters: ["grouping": grouping])
    }

}
