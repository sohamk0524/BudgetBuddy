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

    // Custom coding for complex associated values
    enum CodingKeys: String, CodingKey {
        case type
        case data
        case nodes
        case category
        case current
        case max
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
    let id: UUID
    let name: String
    let value: Double
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
