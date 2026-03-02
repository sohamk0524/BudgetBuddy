# Task: Implement Weekly Spending Limit Feature

## Core Directive
**Strict Execution:** Only write the code and make the changes strictly necessary to accomplish the specific requirements listed below. Do not refactor unrelated code or introduce scope creep.

## Task Overview
Introduce a Weekly Spending Limit feature that allows users to set a budget during onboarding, modify it later, and track their remaining "safe to spend" amount dynamically.

## Specific Requirements

### 1. Onboarding Flow Updates
* **Remove:** Delete the current onboarding step that asks the user for their "motivation".
* **Add:** Replace it with a new input step that asks the user to set their initial "Weekly Spending Limit".
* **Data Model:** Ensure this value is properly saved to the user's account/profile state upon completing onboarding.

### 2. Profile Tab Updates
* **Read/Write Access:** Add a dedicated section within the Profile Tab for the Weekly Spending Limit.
* **Functionality:** Display the user's current limit and provide an input mechanism to modify and save a new limit.

### 3. Tips Tab & Core Logic
* **UI Update:** Update the "Safe to Spend" display within the Tips Tab.
* **Calculation:** The displayed amount must be calculated dynamically using the following formula:
  `Safe to Spend = (Weekly Spending Limit) - (Sum of all transactions for the current week)`