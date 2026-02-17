# Project Overview: BudgetBuddy

## 1. The Problem
Managing personal finances is currently defined by **friction and anxiety**.
* **Friction:** Users must manually categorize transactions, link accounts, and update spreadsheets.
* **Anxiety:** Static numbers in banking apps (e.g., "$1,200 balance") do not answer the real emotional questions: "Can I afford dinner?" or "Will I make rent?"
* **Result:** High abandonment rates. Most users start budgeting but quit within 3 months because the administrative burden outweighs the perceived value.

## 2. Current Solutions & Their Failings
* **Mint (Legacy)/Rocket Money:** Excellent at *tracking* (backward-looking) but poor at *planning* (forward-looking). They show you where you lost money, rather than preventing the loss.
* **YNAB (You Need A Budget):** effective methodology, but has a steep learning curve and requires high manual maintenance ("giving every dollar a job").
* **Generic AI Wrappers:** Simple chatbots that can answer basic questions but lack visual context and persistence. They are text-only and fail to provide "at-a-glance" status updates.

## 3. The BudgetBuddy Solution
BudgetBuddy is a **Hybrid AI Financial Copilot** that combines a conversational interface with a generative graphical UI.
* **Generative UI:** The app does not have a static dashboard. If the user asks about travel, the UI morphs to show a travel savings burndown chart. If they ask about debt, it renders a payoff simulator.
* **Contextual Intelligence:** Instead of raw data, we provide **Synthesis**. We ingest banking data and output a single "Safe-to-Spend" number that accounts for upcoming bills and goals.
* **Proactive "Nudging":** The system alerts users to potential overspending *before* it happens based on spending velocity, not just hard limits.

## 4. Measures of Success
1.  **Retention:** 40% of users active after 30 days (beating the fintech average of ~15%).
2.  **"Safe-to-Spend" Adherence:** Do users who check their daily "Safe-to-Spend" number end the month with a positive balance?
3.  **Interaction Depth:** Users engaging with *both* the chat and the visual plan (indicating the hybrid model is working).
4.  **Time-to-Plan:** A new user should be able to go from "Sign up" to "Actionable Budget Plan" in under 2 minutes.