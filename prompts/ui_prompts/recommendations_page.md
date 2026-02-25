# UI Implementation Specification: Recommendations Page

## Objective
Replace the existing chat-based interface with a new "Recommendations" tab. The UI is a dark-themed, dashboard-style mobile screen that provides users with a quick overview of their daily spending limit, actionable financial recommendations based on past transactions, and quick action buttons for deeper financial analysis.

## Global Styling & Theme
* **Theme:** Dark mode.
* **Background Color:** Deep navy/dark blue (e.g., `#0F172A` or similar slate-900).
* **Accent Color:** Bright Teal/Mint (e.g., `#2DD4BF` or `#14B8A6`). Used for primary buttons, active icons, and status indicators.
* **Card Background Color:** Semi-transparent dark gray/blue (e.g., `#1E293B` or `rgba(255, 255, 255, 0.05)`).
* **Text Colors:** * Primary text: Pure White (`#FFFFFF`).
    * Secondary text: Light Gray (`#94A3B8`).
* **Border Radius:** Use heavily rounded corners (`border-radius: 16px` to `24px`) for all cards and buttons.

## Layout Structure (Top to Bottom)

### 1. Hero Section (Budget Overview)
* **Layout:** Centered vertically and horizontally at the top of the screen.
* **Amount Display:** A large pill-shaped container (dark teal background) displaying the amount `$` (small) and `124` (large, bold).
* **Status Indicator:** * A small teal circle icon followed by the text "Status: On Track".
    * Secondary text below it: "Safe to Spend Today".
* **Pagination Dots:** 4 dots below the status text, with the first dot fully opaque and the rest slightly transparent.

### 2. Recommendations List (Scrollable Area)
* **Layout:** A vertical stack (`flex-col` with `gap-4`) of recommendation cards.
* **Card Design:**
    * Background: Dark gray/blue.
    * Padding: ~16px inside the card.
    * Layout: Flex row. Left side contains an icon; right side contains a Title and Subtitle.
* **Card Items:**
    1.  **Grocery Savings:** Shopping cart icon. Text: "Switch to [Store X] for weekly shop - estimated $30 savings."
    2.  **Utility Audit:** Up/Down arrows icon. Text: "Review energy provider for better rates - potential $20/month."
    3.  **Transport Card:** Credit card icon. Text: "Consider annual pass for commute - saves $X yearly."

### 3. Action Buttons (Sticky/Fixed to Bottom above Nav)
* **Layout:** A vertical stack containing one large primary button and a row of two secondary buttons.
* **Primary CTA (Generate Recommendations):**
    * Width: 100% (full width of the container).
    * Background: Teal gradient or solid bright Teal.
    * Icon: Lightbulb.
    * Text: "Generate Recommendations" (White text, semi-bold).
    * Style: Pill-shaped (`rounded-full`).
* **Secondary Actions (Row):**
    * Layout: Flex row, `justify-between` or grid with 2 columns, gap of ~12px.
    * Button 1: "Check if Budget is Balanced".
    * Button 2: "Analyze Spending Habits".
    * Style: Transparent background with a subtle gray border (`border-gray-700`), white text, pill-shaped.

### 4. Bottom Navigation Bar
* **Layout:** Floating or standard bottom nav bar, pill-shaped background with a subtle border.
* **Tabs:**
    * **Recommendations (Active):** Lightbulb icon. Icon and text are colored Teal.
    * **Wallet (Inactive):** Wallet/Document icon. Icon and text are colored Light Gray.

## Interactivity & State Management Notes for the AI
1.  **Dynamic Data:** The `$124` safe-to-spend amount, the recommendation cards, and the status text should be passed in as props or fetched from a state management store.
2.  **Generate Button:** The "Generate Recommendations" button should trigger an async function (e.g., an LLM call or backend fetch) to refresh the recommendation cards above it. Include a loading state (spinner) for this button.
3.  **Scroll Behavior:** The Hero Section and Bottom Nav/Action Buttons should ideally remain fixed, while the "Recommendations List" is a scrollable view (`ScrollView` or `ListView`).

---
**AI Prompt Instruction:** "Using the specifications above, generate the complete UI code for this screen using [Insert your preferred framework: e.g., React Native with Tailwind / Flutter / SwiftUI]. Ensure the component is responsive and accurately matches the dark-theme aesthetic described."