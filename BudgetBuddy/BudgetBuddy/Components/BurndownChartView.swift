//
//  BurndownChartView.swift
//  BudgetBuddy
//
//  View component for rendering budget burndown charts
//

import SwiftUI
import Charts

struct BurndownChartView: View {
    let data: [BurndownDataPoint]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "chart.line.downtrend.xyaxis")
                    .foregroundColor(.blue)
                Text("Budget Burndown")
                    .font(.headline)
            }

            // Chart
            Chart(data) { point in
                LineMark(
                    x: .value("Date", point.date),
                    y: .value("Amount", point.amount)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [.blue, .cyan],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .lineStyle(StrokeStyle(lineWidth: 2))

                AreaMark(
                    x: .value("Date", point.date),
                    y: .value("Amount", point.amount)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [.blue.opacity(0.3), .cyan.opacity(0.1)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
            }
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.day().month(.abbreviated))
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading) { value in
                    AxisGridLine()
                    AxisValueLabel {
                        if let amount = value.as(Double.self) {
                            Text("$\(Int(amount))")
                        }
                    }
                }
            }
            .frame(height: 200)

            // Summary stats
            HStack {
                StatView(title: "Starting", value: startingAmount)
                Spacer()
                StatView(title: "Current", value: currentAmount)
                Spacer()
                StatView(title: "Projected End", value: projectedEnd)
            }
            .padding(.top, 8)
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 2)
    }

    // MARK: - Computed Properties

    private var startingAmount: String {
        guard let first = data.first else { return "$0" }
        return "$\(Int(first.amount))"
    }

    private var currentAmount: String {
        let today = Date()
        let current = data.last(where: { $0.date <= today })?.amount ?? 0
        return "$\(Int(current))"
    }

    private var projectedEnd: String {
        guard let last = data.last else { return "$0" }
        return "$\(Int(last.amount))"
    }
}

// MARK: - Supporting Views

private struct StatView: View {
    let title: String
    let value: String

    var body: some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
        }
    }
}

#Preview {
    let sampleData = (0..<30).map { day in
        BurndownDataPoint(
            date: Calendar.current.date(byAdding: .day, value: day, to: Date())!,
            amount: max(0, 2500.0 - Double(day) * 80.0)
        )
    }

    return BurndownChartView(data: sampleData)
        .padding()
}
