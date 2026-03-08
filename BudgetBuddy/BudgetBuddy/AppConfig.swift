import Foundation

enum AppConfig {
    #if DEBUG
    static let baseURL = URL(string: "http://localhost:5000")!
    #else
    static let baseURL = URL(string: "https://budgetbuddy-488223.wl.r.appspot.com")!
    #endif

    // Update these once GitHub Pages is live
    static let termsURL   = URL(string: "https://budgetbuddy.sandeepreehal.com/terms.html")!
    static let privacyURL = URL(string: "https://budgetbuddy.sandeepreehal.com/privacy.html")!

    /// Supported universities: (backendKey, displayName)
    static let universities: [(key: String, name: String)] = [
        ("uc_berkeley",    "UC Berkeley"),
        ("uc_davis",       "UC Davis"),
        ("uc_irvine",      "UC Irvine"),
        ("uc_los_angeles", "UC Los Angeles"),
        ("uc_merced",      "UC Merced"),
        ("uc_riverside",   "UC Riverside"),
        ("uc_san_diego",   "UC San Diego"),
        ("uc_santa_barbara", "UC Santa Barbara"),
        ("uc_santa_cruz",  "UC Santa Cruz"),
    ]

    static func universityDisplayName(for key: String) -> String {
        universities.first(where: { $0.key == key })?.name ?? "--"
    }
}
