//
//  BurndownWidgetView.swift
//  BudgetBuddy
//
//  A minimalist line chart showing budget burndown with actual vs ideal spending
//

import SwiftUI
import Charts

struct BurndownWidgetView: View {
    let spent: Double
    let budget: Double
    let idealPace: Double

    // Generate chart data points
    private var chartData: [ChartDataPoint] {
        let calendar = Calendar.current
        let today = Date()
        let components = calendar.dateComponents([.year, .month], from: today)

        guard let startOfMonth = calendar.date(from: components),
              let range = calendar.range(of: .day, in: .month, for: today) else {
            return []
        }

        let daysInMonth = range.count
        let currentDay = calendar.component(.day, from: today)
        let dailyIdealSpend = budget / Double(daysInMonth)
        let actualDailySpend = spent / Double(currentDay)

        var dataPoints: [ChartDataPoint] = []

        // Generate data for all days
        for day in 1...daysInMonth {
            guard let date = calendar.date(byAdding: .day, value: day - 1, to: startOfMonth) else {
                continue
            }

            // Ideal line (linear burndown)
            let idealRemaining = budget - (dailyIdealSpend * Double(day))

            // Actual line (only up to current day, then projected)
            let actualRemaining: Double
            if day <= currentDay {
                // Past/current days - use actual rate
                actualRemaining = budget - (actualDailySpend * Double(day))
            } else {
                // Future days - project based on current rate
                actualRemaining = budget - (actualDailySpend * Double(day))
            }

            dataPoints.append(ChartDataPoint(
                date: date,
                idealRemaining: max(0, idealRemaining),
                actualRemaining: max(0, actualRemaining),
                isProjected: day > currentDay
            ))
        }

        return dataPoints
    }

    private var currentDay: Int {
        Calendar.current.component(.day, from: Date())
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Budget Burndown")
                        .font(.roundedHeadline)
                        .foregroundStyle(Color.textPrimary)

                    Text("Remaining: $\(Int(budget - spent))")
                        .font(.roundedCaption)
                        .monospacedDigit()
                        .foregroundStyle(Color.textSecondary)
                }

                Spacer()

                // Status indicator
                if spent > idealPace {
                    Label("Over Pace", systemImage: "exclamationmark.triangle.fill")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.danger)
                } else {
                    Label("On Track", systemImage: "checkmark.circle.fill")
                        .font(.roundedCaption)
                        .foregroundStyle(Color.accent)
                }
            }

            // Chart
            Chart(chartData) { point in
                // Ideal Pace Line (dashed)
                LineMark(
                    x: .value("Date", point.date),
                    y: .value("Ideal", point.idealRemaining),
                    series: .value("Type", "Ideal")
                )
                .foregroundStyle(Color.textSecondary.opacity(0.5))
                .lineStyle(StrokeStyle(lineWidth: 2, dash: [5, 5]))

                // Actual Spending Line
                LineMark(
                    x: .value("Date", point.date),
                    y: .value("Actual", point.actualRemaining),
                    series: .value("Type", "Actual")
                )
                .foregroundStyle(
                    point.isProjected ? Color.accent.opacity(0.5) : Color.accent
                )
                .lineStyle(StrokeStyle(
                    lineWidth: 3,
                    dash: point.isProjected ? [4, 4] : []
                ))

                // Gradient area under actual spending (only for past days)
                if !point.isProjected {
                    AreaMark(
                        x: .value("Date", point.date),
                        y: .value("Actual", point.actualRemaining)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color.accent.opacity(0.3), Color.accent.opacity(0.05)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                }
            }
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                    AxisValueLabel(format: .dateTime.day())
                        .foregroundStyle(Color.textSecondary)
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading) { value in
                    AxisValueLabel {
                        if let amount = value.as(Double.self) {
                            Text("$\(Int(amount))")
                                .font(.roundedCaption)
                                .monospacedDigit()
                                .foregroundStyle(Color.textSecondary)
                        }
                    }
                }
            }
            .chartYScale(domain: 0...budget)
            .chartLegend(.hidden)
            .frame(height: 160)

            // Legend
            HStack(spacing: 16) {
                LegendItem(color: Color.accent, label: "Actual", dashed: false)
                LegendItem(color: Color.textSecondary.opacity(0.5), label: "Ideal Pace", dashed: true)
            }
            .font(.roundedCaption)
        }
        .padding()
    }
}

// MARK: - Supporting Types

struct ChartDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let idealRemaining: Double
    let actualRemaining: Double
    let isProjected: Bool
}

struct LegendItem: View {
    let color: Color
    let label: String
    let dashed: Bool

    var body: some View {
        HStack(spacing: 6) {
            if dashed {
                Rectangle()
                    .fill(color)
                    .frame(width: 16, height: 2)
                    .mask(
                        HStack(spacing: 2) {
                            ForEach(0..<4, id: \.self) { _ in
                                Rectangle().frame(width: 3)
                            }
                        }
                    )
            } else {
                Rectangle()
                    .fill(color)
                    .frame(width: 16, height: 3)
                    .clipShape(Capsule())
            }

            Text(label)
                .foregroundStyle(Color.textSecondary)
        }
    }
}

// MARK: - Preview

#Preview {
    VStack {
        BurndownWidgetView(spent: 1876, budget: 2500, idealPace: 1450)
            .cardStyle()

        BurndownWidgetView(spent: 800, budget: 2500, idealPace: 1450)
            .cardStyle()
    }
    .padding()
    .background(Color.appBackground)
}
