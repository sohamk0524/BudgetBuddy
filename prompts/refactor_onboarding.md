# Task: Refactor Onboarding Interview Logic

## Context
You are an expert software engineer working on an agentic budgeting tool. Your task is to refactor the current onboarding interview module. The current flow asks incorrect or superfluous questions. We need to streamline this into a strict, 4-step interview process.

## Objective
Update the onboarding logic to strictly adhere to the **4-Question Protocol** defined below. You must analyze the existing code, retain only the logic that overlaps with these requirements, and delete any questions or logic that falls outside this scope.

## The 4-Question Protocol
The agent must ask **only** the following four questions, in this order:

1.  **Name**
    * *Type:* String input.
    * *Context:* The user's first name.
    
2.  **Student Status**
    * *Type:* Boolean (Yes/No).
    * *Context:* "Are you currently a student?"

3.  **Primary Motivation ("Why")**
    * *Type:* Selection from a list (Enum/Array).
    * *Context:* Why are they using this tool?

4.  **Strictness Level**
    * *Type:* Selection from a list (Enum/Array).
    * *Context:* How aggressive should the agent be about budget adherence?
    * *Required Options:*
        * "Relaxed (Guide me gently)"
        * "Moderate (Keep me on track)"
        * "Strict (Don't let me overspend)"

## Execution Instructions

### 1. Audit and Prune
Analyze the existing onboarding code. identifying all currently asked questions.
* **IF** a question is not one of the 4 listed above (e.g., Age, Income, Rent, Location), **DELETE IT** entirely from the flow.
* **IF** a question matches one of the 4 (e.g., "Name" exists), **KEEP IT** but ensure it matches the new specifications.

### 2. Implement Missing Logic
* **IF** any of the 4 questions are missing, implement them now.
* Ensure the "Why" and "Strictness" questions utilize a selection mechanism (buttons, dropdown, or numbered list) rather than open-ended text to ensure data consistency.

### 3. Output
Generate the updated code block for the onboarding component/function. Ensure variable names are semantic (e.g., `userBudgetingGoal`, `strictnessLevel`).