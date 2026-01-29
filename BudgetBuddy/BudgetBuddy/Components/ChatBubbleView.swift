//
//  ChatBubbleView.swift
//  BudgetBuddy
//
//  View component for rendering chat message bubbles
//

import SwiftUI

struct ChatBubbleView: View {
    let message: ChatMessage

    private var isUser: Bool {
        message.type == .user
    }

    var body: some View {
        HStack {
            if isUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                Text(message.text)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(bubbleBackground)
                    .foregroundColor(isUser ? .white : .primary)
                    .clipShape(RoundedRectangle(cornerRadius: 18))

                Text(formattedTime)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 8)
            }

            if !isUser {
                Spacer(minLength: 60)
            }
        }
    }

    private var bubbleBackground: Color {
        isUser ? .blue : Color(.systemGray5)
    }

    private var formattedTime: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: message.timestamp)
    }
}

#Preview {
    VStack(spacing: 16) {
        ChatBubbleView(message: ChatMessage(
            type: .user,
            text: "Can I afford dinner tonight?"
        ))

        ChatBubbleView(message: ChatMessage(
            type: .assistant,
            text: "Based on your spending, you have $127.50 safe to spend today!"
        ))
    }
    .padding()
}
