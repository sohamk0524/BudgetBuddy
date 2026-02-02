# Instructions for CLI: BudgetBuddy Full Stack Auth & Onboarding

**Context:**
We are upgrading "BudgetBuddy" from a mock prototype to a functional MVP.
* **Current State:** A Flask backend with mock data and an iOS frontend with a mock service.
* **Goal:** Implement real User Authentication, a SQLite Database, and a personalized Onboarding flow.

---

## Part 1: Backend Implementation (Python/Flask)

**Action:** Generate or Overwrite the following files in the `./backend/` directory.

### 1. `backend/requirements.txt`
* **Content:**
    ```text
    flask
    flask-cors
    flask-sqlalchemy
    werkzeug
    ```

### 2. `backend/models.py`
* **Content:** Define the database schema.
    ```python
    from flask_sqlalchemy import SQLAlchemy
    
    db = SQLAlchemy()
    
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        password_hash = db.Column(db.String(256))
        profile = db.relationship('FinancialProfile', backref='user', uselist=False)
    
    class FinancialProfile(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        monthly_income = db.Column(db.Float, default=0.0)
        fixed_expenses = db.Column(db.Float, default=0.0)
        savings_goal_name = db.Column(db.String(100))
        savings_goal_target = db.Column(db.Float, default=0.0)
    ```

### 3. `backend/app.py`
* **Content:** The main application logic.
    * Initialize `Flask`, `CORS`, and `SQLAlchemy`.
    * Config: `SQLALCHEMY_DATABASE_URI = 'sqlite:///budgetbuddy.db'`.
    * **Route `POST /register`**:
        * Expect `{"email": "...", "password": "..."}`.
        * Check if email exists.
        * Hash password using `werkzeug.security.generate_password_hash`.
        * Create `User`. Return `{"token": user.id, "status": "success"}`.
    * **Route `POST /login`**:
        * Expect `{"email": "...", "password": "..."}`.
        * Verify hash using `check_password_hash`.
        * Return `{"token": user.id, "hasProfile": (user.profile is not None)}`.
    * **Route `POST /onboarding`**:
        * Expect `{"userId": 1, "income": 5000, "expenses": 2000, "goalName": "Car", "goalTarget": 10000}`.
        * Create `FinancialProfile` linked to the user.
    * **Route `POST /chat`**:
        * Expect `{"userId": 1, "message": "..."}`.
        * Call `orchestrator.process_message(user_id, message)`.

### 4. `backend/services/orchestrator.py`
* **Content:** The logic engine.
    * Import `models` (User, FinancialProfile).
    * Function `process_message(user_id, text)`:
        * Fetch `FinancialProfile` by `user_id`.
        * **Logic:**
            * Calculate `discretionary = profile.monthly_income - profile.fixed_expenses`.
            * If text contains "afford" or "can I buy":
                * Check if the parsed amount (assume $100 for prototype or try to extract) < `discretionary`.
                * Return `AssistantResponse` (JSON) with a `.burndownChart` visual payload using the user's real `discretionary` as the budget limit.
            * If text contains "plan":
                * Return `AssistantResponse` with a `.sankeyFlow` visual payload using real `income` and `expenses`.

---

## Part 2: Frontend Implementation (Swift/iOS)

**Action:** Generate or Overwrite the following files in the `./BudgetBuddy/` directory.

### 1. `./BudgetBuddy/Services/AuthManager.swift`
* **Content:**
    ```swift
    import SwiftUI
    import Observation
    
    @Observable
    class AuthManager {
        static let shared = AuthManager()
        
        var isAuthenticated: Bool = false
        var needsOnboarding: Bool = false
        var authToken: Int? {
            didSet { UserDefaults.standard.setValue(authToken, forKey: "authToken") }
        }
        
        init() {
            if let token = UserDefaults.standard.value(forKey: "authToken") as? Int {
                self.authToken = token
                self.isAuthenticated = true
                // In a real app, we would verify the token valid here
            }
        }
        
        func login(email: String, password: String) async {
            // Call API POST /login
            // On success: self.authToken = response.token; self.isAuthenticated = true; self.needsOnboarding = !response.hasProfile
        }
        
        func register(email: String, password: String) async {
             // Call API POST /register
             // On success: self.authToken = response.token; self.isAuthenticated = true; self.needsOnboarding = true
        }
        
        func completeOnboarding(income: Double, expenses: Double, goalName: String, goalTarget: Double) async {
            // Call API POST /onboarding
            // On success: self.needsOnboarding = false
        }
        
        func signOut() {
            self.isAuthenticated = false
            self.authToken = nil
            UserDefaults.standard.removeObject(forKey: "authToken")
        }
    }
    ```

### 2. `./BudgetBuddy/Services/APIService.swift`
* **Content:**
    * Replace the mock service.
    * Function `sendMessage(text: String) async throws -> AssistantResponse`.
    * **Crucial:** It must read `AuthManager.shared.authToken` and include it in the JSON body: `{"userId": token, "message": text}`.
    * Perform `URLRequest` to `http://127.0.0.1:5000/chat`.

### 3. `./BudgetBuddy/Views/Auth/LoginView.swift`
* **Content:**
    * A ZStack with `Color.theme.background`.
    * Two `TextField`s (Email, Password) styled with `.cardStyle()`.
    * A "Sign In" Button that calls `AuthManager.shared.login`.
    * A "Register" Button that calls `AuthManager.shared.register`.

### 4. `./BudgetBuddy/Views/Onboarding/OnboardingWizardView.swift`
* **Content:**
    * A `TabView` with `PageTabViewStyle`.
    * **Page 1:** "Monthly Income" (TextField).
    * **Page 2:** "Fixed Expenses" (TextField).
    * **Page 3:** "Savings Goal" (TextField name, TextField amount).
    * **Button:** "Finish" -> Calls `AuthManager.shared.completeOnboarding`.

### 5. `./BudgetBuddy/Views/ContentView.swift`
* **Content:**
    * State: `@State var authManager = AuthManager.shared`.
    * Body:
        ```swift
        if !authManager.isAuthenticated {
            LoginView()
        } else if authManager.needsOnboarding {
            OnboardingWizardView()
        } else {
            TabView {
                ChatView()
                    .tabItem { Label("Chat", systemImage: "message.fill") }
                WalletView()
                    .tabItem { Label("Wallet", systemImage: "wallet.pass.fill") }
            }
            .onAppear {
                // Set tab bar appearance to dark
                let appearance = UITabBarAppearance()
                appearance.configureWithOpaqueBackground()
                appearance.backgroundColor = UIColor(Color.theme.background)
                UITabBar.appearance().standardAppearance = appearance
                UITabBar.appearance().scrollEdgeAppearance = appearance
            }
        }
        ```

**Output:**
Provide the full code for all files listed above. Ensure Python code uses `snake_case` and Swift code uses `camelCase` and proper `import` statements.