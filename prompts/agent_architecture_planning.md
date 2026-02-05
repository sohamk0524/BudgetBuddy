# Instructions for Claude CLI: Intelligent Agent & Tool Architecture Plan

**Context:**
We have a functional MVP of "BudgetBuddy" (iOS + Flask/SQLite).
* **Current State:** The backend logic is brittle, relying on simple keyword matching (e.g., if "plan" in text -> show Sankey).
* **Goal:** Upgrade to a **Sophisticated, Interwoven AI Agent** capable of complex reasoning, state awareness, and dynamic tool usage.

**The Core Objective:**
We need a comprehensive architectural plan to transform the backend into a central intelligence that "knows" everything about the user and the app features. It must proactively guide the user (e.g., noticing a missing plan) and reactively execute complex tasks via tools.

**IMPORTANT SCOPE NOTE:**
The prompt below uses specific examples like "Creating a Plan" or "Uploading a Bank Statement." **These are illustrative examples only.**
Your plan must design a **General Purpose Agent Architecture** that can handle these examples *plus* a wide range of future capabilities 

---

## Required Output: `agent_architecture_plan.md`

Please analyze the codebase and generate a strategy document (`agent_architecture_plan.md`) that addresses the following:

### 1. The "Interwoven" State Machine
* **Concept:** The Agent should not just answer questions; it should track the "Health" of the user's profile.
* **Requirement:** Define how the agent will detect specific states and trigger proactive dialogue.
    * *Example Scenario:* User logs in -> Agent checks DB -> Sees `has_plan = False` -> Agent bypasses standard greeting and asks: "I see you don't have a budget plan yet. Shall we build one?"
    * *Beyond the Example:* How does this scale to other states like "Spending Velocity High" or "Subscription Price Hiked"?

### 2. The Scalable Tool Registry
* **Concept:** A formalized system where the LLM selects a tool from a registry, and the backend executes it.
* **Requirement:** Design a tool definition pattern (using function calling or JSON schemas).
    * **Illustrative Tools:** `ParseBankStatement`, `CreateBudgetPlan`.
    * **Required Extensibility:** The architecture must allow us to easily plug in new tools later without changing the orchestrator logic.
    * **Additional Features:** Tools defined should result in a very immersive experience that makes the agent feel like the app instead of an isolated feature

### 3. Multi-Modal & Contextual Input
* **Concept:** The agent needs "eyes" to read documents and "memory" to recall previous context.
* **Requirement:**
    * How to handle file uploads (PDF/CSV) in the chat stream and merge that data into the `FinancialProfile`.
    * How to maintain conversation history so the agent knows what "Manage *that* subscription" refers to.

### 4. Implementation Roadmap
* Break the execution down into phases:
    * **Phase 1: The Brain.** Implementing the LLM Router and Tool Interface.
    * **Phase 2: The Core Tools.** Implementing the logic for the specific examples (Plan Creation, Document Parsing).
    * **Phase 3: The Expansion.** Implementing the "Proactive" logic and broader toolset.

**Output Format:**
A single, well-structured Markdown file named `agent_architecture_plan.md`.