# Feature Specification: Hybrid "Quick-Action" Chat Interface
**Target Audience:** UC Davis Students
**Goal:** Reduce typing friction by replacing the empty chat state with a 6-option "Quick-Action" modal.

## 1. UI/UX Flow
**Current State:** User opens chat -> sees empty text bar -> has to think of a prompt.
**New State:** 1. User opens chat (or clicks the text input bar).
2. A **"Quick-Action Modal"** instantly appears (overlay or bottom sheet).
3. The Modal contains a 2x3 grid of the most common student financial needs.
4. Selecting an option prefills the prompt or opens a specific mini-form.
5. The AI responds with UC Davis-specific context.

## 2. The 6 Quick-Action Modules

### Option A: "I'm craving..." (Food Focus)
- **UI Interaction:** Opens a dropdown or quick-text field.
- **Pre-set variables:** Coffee (CoHo/Peet's), Boba (Lazi Cow/Sharetea), Late Night (In-N-Out/Ali Baba).
- **AI Logic:** 1. Check "Dining/Food" budget category.
    2. If budget is low: Suggest cheaper alternatives (e.g., "You only have $15 left for dining. Maybe grab a bagel at the CoHo instead of a sit-down meal?").
    3. If budget is healthy: "Treat yourself! You're under budget."

### Option B: "I want to go..." (Activity/Transport Focus)
- **UI Interaction:** Fill in the blank: "I want to go to [Location]."
- **Common Inputs:** Downtown, Sacramento, Tahoe, SF, The ARC.
- **AI Logic:**
    1. Estimate cost (Gas, Uber, Bus fare, Ticket).
    2. Check "Transport" or "Entertainment" budget.
    3. **Davis Context:** Suggest Unitrans if the user is trying to save money on local travel.

### Option C: "Am I on track?" (Pulse Check)
- **UI Interaction:** Single tap execution.
- **AI Logic:**
    1. Call `get_budget_plan` and `get_transaction_summary`.
    2. Response: "It's week 3 of the quarter. You've spent 40% of your monthly budget. You are [On Track / At Risk]."

### Option D: "I just spent..." (Quick Logging)
- **UI Interaction:** Number pad + Category selector.
- **AI Logic:** Immediately calls `log_transaction(amount, category)`.
- **Response:** "Got it. Logged $15 for 'Groceries' at Trader Joe's. Remaining Grocery Budget: $85."

### Option E: "Can I afford...?" (Purchase Decision)
- **UI Interaction:** Input Item Name + Price.
- **AI Logic:**
    1. Check "Free Cash Flow" (Income - Fixed Expenses - Current Spend).
    2. Response: "Yes, but you'll have to skip [Category] next week," or "No, wait until financial aid drops."

### Option F: "Let me type..." (Fallback)
- **UI Interaction:** Closes the modal and focuses the standard keyboard.
- **Behavior:** Reverts to the standard "Chat with Tools" logic defined previously.

## 3. Technical Implementation Requirements
- **Frontend:** React/Next.js (assuming current stack).
- **Component:** `QuickActionGrid` (the modal) and `ActionInput` (the fill-in-the-blank forms).
- **State Management:** When an option is clicked, it should programmatically construct the user prompt strings (e.g., "User clicked Option A -> send prompt: 'Check dining budget for craving'") so the existing AI backend handles it without modification.