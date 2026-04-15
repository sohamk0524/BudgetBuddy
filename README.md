# BudgetBuddy

An AI-powered personal finance iOS app built around a **Hybrid AI Financial Copilot** — a chat assistant whose UI morphs to match what you ask. Ask about travel, you get a travel savings chart. Ask about debt, you get a payoff simulator.

## Features

- **Generative chat UI** — responses render as dynamic widgets (charts, simulators, breakdowns) picked per-query, not walls of text.
- **Voice transactions** — log expenses hands-free.
- **Plaid integration** — link real bank accounts for live balances and transactions.
- **Statement import** — upload a PDF or CSV and the backend parses, classifies, and ingests it.
- **Spending plans** — auto-generated budgets tailored to income, goals, and history, with category-level tracking.
- **Smart nudges** — real-time alerts when a category trends over budget.
- **Recommendations** — a mix of deterministic templates and LLM-generated tips, which you can save, use, or dismiss.
- **School-aware RAG** — student users get tips grounded in their school's financial aid and resources.
- Share Extension, auth, onboarding, and push notifications.

## Tech Stack

**iOS** (`BudgetBuddy/`) — SwiftUI only, Swift Charts, MVVM with the `@Observable` macro, `@MainActor` concurrency, dark mode throughout.

**Backend** (`BudgetBuddyBackend/`) — Python + Flask with a Blueprint-per-feature layout. A central **orchestrator** runs a tool-use LLM workflow (Ollama `llama3.2:3b` locally, via the OpenAI SDK) to fetch data, generate plans, and build responses. `pdfplumber` for statements, Google Cloud Datastore for storage, deployable to App Engine. Pytest suite (~167 cases).

**Architecture**

```
SwiftUI View ──► ViewModel ──► APIService
                                    │
                                    ▼
                      Flask Blueprint ──► Orchestrator
                                              │
                            ┌─────────────────┼─────────────────┐
                            ▼                 ▼                 ▼
                      LLM + Tools       Plaid / Stmts      Datastore
                                              │
                                              ▼
                              AssistantResponse (text + VisualComponent)
                                              │
                                              ▼
                                 GenerativeWidgetView renders widget
```

The `VisualComponent` enum in `Models.swift` is the contract between backend and UI: the backend picks a component type, the iOS renderer builds the widget.

## Repository Layout

```
BudgetBuddy/                 iOS app
BudgetBuddyBackend/          Flask backend + LLM orchestrator
BudgetBuddyShareExtension/   iOS share extension
docs/                        Design docs
```
