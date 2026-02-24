import Foundation

enum AppConfig {
    #if DEBUG
    static let baseURL = URL(string: "http://localhost:5000")!
    #else
    static let baseURL = URL(string: "https://budgetbuddy-488223.wl.r.appspot.com")!
    #endif
}
