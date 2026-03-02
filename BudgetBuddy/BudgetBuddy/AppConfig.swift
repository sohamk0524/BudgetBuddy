import Foundation

enum AppConfig {
    #if DEBUG
    static let baseURL = URL(string: "http://localhost:5000")!
    #else
    static let baseURL = URL(string: "https://budgetbuddy-488223.wl.r.appspot.com")!
    #endif

    // Update these once GitHub Pages is live
    static let termsURL   = URL(string: "https://sohamk0524.github.io/BudgetBuddy/terms.html")!
    static let privacyURL = URL(string: "https://sohamk0524.github.io/BudgetBuddy/privacy.html")!
}
