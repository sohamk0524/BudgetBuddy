import SwiftUI

// MARK: - Color Palette Extension
extension Color {
    /// Deep Midnight Blue - Primary background
    static let appBackground = Color(hex: "#0F172A")

    /// Lighter Slate Blue - Cards and surfaces
    static let surface = Color(hex: "#1E293B")

    /// Electric Teal - Positive actions and accents
    static let accent = Color(hex: "#2DD4BF")

    /// Soft Coral - Alerts and warnings
    static let danger = Color(hex: "#F43F5E")

    /// Primary text color
    static let textPrimary = Color.white

    /// Secondary text color
    static let textSecondary = Color.white.opacity(0.6)

    // MARK: - Hex Color Initializer
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Card Style Modifier
struct CardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(Color.surface)
            .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

extension View {
    /// Applies the standard card styling: padding, surface background, and 16pt corner radius
    func cardStyle() -> some View {
        modifier(CardStyle())
    }
}

// MARK: - Typography Helpers
extension Font {
    /// Rounded design system font
    static func rounded(_ style: Font.TextStyle, weight: Font.Weight = .regular) -> Font {
        Font.system(style, design: .rounded, weight: weight)
    }

    /// Large title with rounded design
    static var roundedLargeTitle: Font {
        .system(.largeTitle, design: .rounded, weight: .bold)
    }

    /// Title with rounded design
    static var roundedTitle: Font {
        .system(.title, design: .rounded, weight: .semibold)
    }

    /// Headline with rounded design
    static var roundedHeadline: Font {
        .system(.headline, design: .rounded, weight: .semibold)
    }

    /// Body with rounded design
    static var roundedBody: Font {
        .system(.body, design: .rounded)
    }

    /// Caption with rounded design
    static var roundedCaption: Font {
        .system(.caption, design: .rounded)
    }
}

// MARK: - Preview
#Preview {
    VStack(spacing: 20) {
        Text("BudgetBuddy Theme")
            .font(.roundedLargeTitle)
            .foregroundStyle(Color.textPrimary)

        Text("$1,234.56")
            .font(.rounded(.title, weight: .bold))
            .monospacedDigit()
            .foregroundStyle(Color.accent)

        Text("Secondary text example")
            .font(.roundedBody)
            .foregroundStyle(Color.textSecondary)

        VStack {
            Text("Card Example")
                .font(.roundedHeadline)
                .foregroundStyle(Color.textPrimary)
            Text("This is inside a card")
                .font(.roundedCaption)
                .foregroundStyle(Color.textSecondary)
        }
        .cardStyle()

        HStack {
            Circle()
                .fill(Color.accent)
                .frame(width: 20, height: 20)
            Text("Accent")

            Circle()
                .fill(Color.danger)
                .frame(width: 20, height: 20)
            Text("Danger")
        }
        .font(.roundedCaption)
        .foregroundStyle(Color.textPrimary)
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .background(Color.appBackground)
}
