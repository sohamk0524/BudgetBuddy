import json
from datetime import datetime, date
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from db_models import (
    db, User, FinancialProfile, BudgetPlan, SavedStatement,
    Transaction, SavingsGoal, SavingsContribution, BudgetCategory
)
from services.orchestrator import (
    process_message, get_orchestrator, process_message_with_session,
    check_proactive_message
)
from services.statement_analyzer import analyze_statement
from services.plan_generator import generate_plan, save_plan_to_db
from services.analytics import get_analytics

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budgetbuddy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Create tables on first request
with app.app_context():
    db.create_all()

# Enable CORS for iOS simulator to communicate with localhost
# Allow all origins and methods for development
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "DELETE", "OPTIONS"]}})


@app.route("/")
def index():
    return jsonify({"message": "Welcome to BudgetBuddy API"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/register", methods=["POST"])
def register():
    """
    Register a new user account.

    Expected request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }

    Returns:
    {
        "token": user_id,
        "status": "success"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 409

    # Create new user with hashed password
    password_hash = generate_password_hash(password)
    new_user = User(email=email, password_hash=password_hash)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "token": new_user.id,
        "status": "success"
    })


@app.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user.

    Expected request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }

    Returns:
    {
        "token": user_id,
        "hasProfile": true/false
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Find user by email
    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({
        "token": user.id,
        "hasProfile": user.profile is not None
    })


@app.route("/onboarding", methods=["POST"])
def onboarding():
    """
    Save user's general profile from onboarding.

    Expected request body:
    {
        "userId": 1,
        "age": 25,
        "occupation": "employed",
        "income": 5000.0,
        "incomeFrequency": "monthly",
        "financialPersonality": "balanced",
        "primaryGoal": "emergency_fund"
    }

    Returns:
    {
        "status": "success"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    age = data.get("age", 0)
    occupation = data.get("occupation", "")
    income = data.get("income", 0.0)
    income_frequency = data.get("incomeFrequency", "monthly")
    financial_personality = data.get("financialPersonality", "balanced")
    primary_goal = data.get("primaryGoal", "stability")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check if profile already exists
    if user.profile:
        # Update existing profile
        user.profile.age = age
        user.profile.occupation = occupation
        user.profile.monthly_income = income
        user.profile.income_frequency = income_frequency
        user.profile.financial_personality = financial_personality
        user.profile.primary_goal = primary_goal
    else:
        # Create new profile
        profile = FinancialProfile(
            user_id=user_id,
            age=age,
            occupation=occupation,
            monthly_income=income,
            income_frequency=income_frequency,
            financial_personality=financial_personality,
            primary_goal=primary_goal
        )
        db.session.add(profile)

    db.session.commit()

    return jsonify({"status": "success"})


@app.route("/generate-plan", methods=["POST"])
def generate_spending_plan():
    """
    Generate a personalized spending plan.

    Expected request body:
    {
        "userId": 1,
        "deepDiveData": {
            "fixedExpenses": {
                "rent": 1200,
                "utilities": 150,
                "subscriptions": [{"name": "Netflix", "amount": 15}]
            },
            "variableSpending": {
                "groceries": 400,
                "transportation": {"type": "car", "gas": 150, "insurance": 100},
                "diningEntertainment": 200
            },
            "upcomingEvents": [
                {"name": "Wedding", "date": "2026-06-15", "cost": 800, "saveGradually": true}
            ],
            "savingsGoals": [
                {"name": "Emergency fund", "target": 1000, "current": 150, "priority": 1}
            ],
            "spendingPreferences": {
                "spendingStyle": 0.3,
                "priorities": ["savings", "security"],
                "strictness": "moderate"
            }
        }
    }

    Returns:
    {
        "textMessage": "Your personalized plan is ready!",
        "plan": { ... },
        "visualPayload": { ... }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    deep_dive_data = data.get("deepDiveData", {})

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Generate the plan
    result = generate_plan(user_id, deep_dive_data)

    # Save the plan if generated successfully
    if result.get("plan"):
        save_plan_to_db(user_id, result["plan"])

    return jsonify(result)


@app.route("/get-plan/<int:user_id>", methods=["GET"])
def get_user_plan(user_id):
    """
    Get the user's most recent spending plan.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get the most recent plan
    plan_record = BudgetPlan.query.filter_by(user_id=user_id).order_by(BudgetPlan.created_at.desc()).first()

    if not plan_record:
        return jsonify({"hasPlan": False, "plan": None})

    import json
    plan_data = json.loads(plan_record.plan_json)

    return jsonify({
        "hasPlan": True,
        "plan": plan_data,
        "createdAt": plan_record.created_at.isoformat() if plan_record.created_at else None,
        "monthYear": plan_record.month_year
    })


@app.route("/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint for the BudgetBuddy AI assistant.

    Expected request body:
    {
        "message": "user text",
        "userId": "123"
    }

    Returns:
    {
        "textMessage": "response text",
        "visualPayload": { ... } or null
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_message = data.get("message", "")
    user_id = data.get("userId", "anonymous")

    if not user_message:
        return jsonify({"error": "Message field is required"}), 400

    # Process the message through the orchestrator
    response = process_message(user_message, user_id)

    return jsonify(response.to_dict())


@app.route("/upload-statement", methods=["POST", "OPTIONS"])
def upload_statement():
    """
    Upload and analyze a bank statement (PDF or CSV).
    If userId is provided, saves the statement to the database (replacing any existing).

    Expected: multipart/form-data with 'file' field and optional 'userId' field

    Returns:
    {
        "textMessage": "analysis summary",
        "visualPayload": { ... } or null
    }
    """
    # Handle preflight request
    if request.method == "OPTIONS":
        return "", 200

    print(f"Upload request received. Files: {list(request.files.keys())}")
    print(f"Content-Type: {request.content_type}")

    if "file" not in request.files:
        print("No 'file' field in request.files")
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    print(f"Received file: {file.filename}")

    # Get optional userId from form data
    user_id = request.form.get("userId")
    if user_id:
        try:
            user_id = int(user_id)
        except ValueError:
            user_id = None

    # Read file content
    file_content = file.read()
    filename = file.filename

    # Determine file type
    file_type = "pdf" if filename.lower().endswith(".pdf") else "csv"

    # Analyze the statement (returns response and parsed analysis)
    response, llm_analysis = analyze_statement(file_content, filename, return_analysis=True)

    # If user is authenticated, save the statement
    if user_id:
        user = User.query.get(user_id)
        if user:
            _save_statement(user_id, filename, file_type, file_content, llm_analysis)
            print(f"Statement saved for user {user_id}")

    return jsonify(response.to_dict())


def _save_statement(user_id: int, filename: str, file_type: str,
                    file_content: bytes, analysis: dict):
    """
    Save or replace a user's statement in the database.

    The analysis dict comes from the statement_analyzer and contains:
    - ending_balance: float (from custom parsing)
    - total_income: float (from custom parsing)
    - total_expenses: float (from custom parsing)
    - transactions: list
    - statement_start_date: str (YYYY-MM-DD)
    - statement_end_date: str (YYYY-MM-DD)
    - top_categories: list (from LLM or basic categorization)
    - friendly_summary: str
    - metadata: dict (duplicate of key metrics)
    """
    # Delete existing statement if any
    existing = SavedStatement.query.filter_by(user_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    # Extract metrics from analysis (prefer top-level, fall back to metadata)
    ending_balance = 0.0
    total_income = 0.0
    total_expenses = 0.0
    statement_start_date = None
    statement_end_date = None

    if analysis:
        # Get totals directly from analysis (set by custom parser)
        total_income = float(analysis.get("total_income", 0) or 0)
        total_expenses = float(analysis.get("total_expenses", 0) or 0)

        # Get ending balance - check top level first, then metadata
        ending_balance = float(analysis.get("ending_balance", 0) or 0)
        if ending_balance == 0:
            metadata = analysis.get("metadata", {})
            if isinstance(metadata, dict):
                ending_balance = float(metadata.get("ending_balance", 0) or 0)

        # If still no ending balance, estimate from income - expenses
        if ending_balance == 0 and (total_income > 0 or total_expenses > 0):
            ending_balance = total_income - total_expenses

        # Get dates - check top level first (set by custom parser)
        start_date_str = analysis.get("statement_start_date")
        end_date_str = analysis.get("statement_end_date")

        if start_date_str:
            try:
                statement_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        if end_date_str:
            try:
                statement_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        # Fall back to parsing dates from transactions if not found
        if not statement_start_date or not statement_end_date:
            transactions = analysis.get("transactions", [])
            if transactions and isinstance(transactions, list):
                dates = []
                for tx in transactions:
                    if isinstance(tx, dict) and tx.get("date"):
                        try:
                            parsed_date = datetime.strptime(tx["date"], "%Y-%m-%d").date()
                            dates.append(parsed_date)
                        except (ValueError, TypeError):
                            pass
                if dates:
                    if not statement_start_date:
                        statement_start_date = min(dates)
                    if not statement_end_date:
                        statement_end_date = max(dates)

    print(f"Saving statement: balance={ending_balance}, income={total_income}, expenses={total_expenses}")

    # Create new statement record
    transactions = analysis.get("transactions", []) if analysis else []
    statement = SavedStatement(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        raw_file=file_content,
        parsed_data=json.dumps({"transactions": transactions}),
        llm_analysis=json.dumps(analysis) if analysis else "{}",
        ending_balance=ending_balance,
        total_income=total_income,
        total_expenses=total_expenses,
        statement_start_date=statement_start_date,
        statement_end_date=statement_end_date
    )

    db.session.add(statement)
    db.session.commit()


@app.route("/user/financial-summary", methods=["GET"])
def get_financial_summary():
    """
    Get financial summary derived from user's saved statement.

    Query params:
        userId: int - the authenticated user's ID

    Returns:
    {
        "hasStatement": true/false,
        "netWorth": float or null,
        "safeToSpend": float or null,
        "statementInfo": { filename, statementPeriod, uploadedAt } or null,
        "spendingBreakdown": [{ category, amount }] or null
    }
    """
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    # Get user and their profile
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get user's saved statement
    statement = SavedStatement.query.filter_by(user_id=user_id).first()

    # Get user's financial profile (from onboarding)
    profile = user.profile
    essential_expenses = profile.fixed_expenses if profile else 0.0
    savings_target = profile.savings_goal_target if profile else 0.0

    if not statement:
        return jsonify({
            "hasStatement": False,
            "netWorth": None,
            "safeToSpend": None,
            "statementInfo": None,
            "spendingBreakdown": None
        })

    # Calculate derived metrics
    net_worth = statement.ending_balance
    net_income = statement.total_income

    # Safe to Spend = Net Worth + Net Income - Essential Expenses - Savings Target
    safe_to_spend = .08 * net_worth 
    safe_to_spend = max(0, safe_to_spend)  # Don't go negative

    # Build statement info
    statement_period = None
    if statement.statement_start_date and statement.statement_end_date:
        statement_period = f"{statement.statement_start_date.isoformat()} to {statement.statement_end_date.isoformat()}"

    statement_info = {
        "filename": statement.filename,
        "statementPeriod": statement_period,
        "uploadedAt": statement.created_at.isoformat() if statement.created_at else None
    }

    # Get spending breakdown from LLM analysis
    spending_breakdown = None
    if statement.llm_analysis:
        try:
            analysis = json.loads(statement.llm_analysis)
            top_categories = analysis.get("top_categories", [])
            if top_categories:
                spending_breakdown = [
                    {"category": cat.get("category", "Other"), "amount": float(cat.get("amount", 0))}
                    for cat in top_categories
                ]
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({
        "hasStatement": True,
        "netWorth": round(net_worth, 2) if net_worth else 0.0,
        "safeToSpend": round(safe_to_spend, 2) if safe_to_spend else 0.0,
        "statementInfo": statement_info,
        "spendingBreakdown": spending_breakdown
    })


@app.route("/user/statement", methods=["DELETE"])
def delete_statement():
    """
    Delete user's saved statement.

    Query params:
        userId: int - the authenticated user's ID

    Returns: 204 No Content on success
    """
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    statement = SavedStatement.query.filter_by(user_id=user_id).first()

    if statement:
        db.session.delete(statement)
        db.session.commit()

    return "", 204


# =============================================================================
# PHASE 3: NEW TOOL API ENDPOINTS
# =============================================================================

@app.route("/transaction", methods=["POST"])
def create_transaction():
    """
    Manually log a financial transaction.

    Expected request body:
    {
        "userId": 1,
        "amount": 50.00,
        "category": "groceries",
        "transactionType": "expense",  // "expense" or "income"
        "merchant": "Whole Foods",     // optional
        "date": "2026-02-04",          // optional, defaults to today
        "notes": "Weekly groceries"    // optional
    }

    Returns:
    {
        "status": "success",
        "transaction": { ... }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    amount = data.get("amount")
    category = data.get("category")

    if not user_id or amount is None or not category:
        return jsonify({"error": "userId, amount, and category are required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Parse transaction type
    tx_type = data.get("transactionType", "expense")
    if tx_type not in ["expense", "income"]:
        tx_type = "expense"

    # Parse date
    date_str = data.get("date")
    if date_str:
        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            tx_date = date.today()
    else:
        tx_date = date.today()

    # Create transaction
    transaction = Transaction(
        user_id=user_id,
        amount=abs(float(amount)),
        transaction_type=tx_type,
        category=category.lower(),
        merchant=data.get("merchant"),
        description=data.get("notes"),
        transaction_date=tx_date,
        source="manual"
    )

    db.session.add(transaction)

    # Update budget category if exists
    current_month = datetime.now().strftime("%Y-%m")
    if tx_type == "expense":
        budget_cat = BudgetCategory.query.filter_by(
            user_id=user_id,
            name=category.lower(),
            month_year=current_month
        ).first()
        if budget_cat:
            budget_cat.spent_amount = (budget_cat.spent_amount or 0) + abs(float(amount))

    db.session.commit()

    return jsonify({
        "status": "success",
        "transaction": {
            "id": transaction.id,
            "amount": transaction.amount,
            "category": transaction.category,
            "transactionType": transaction.transaction_type,
            "merchant": transaction.merchant,
            "date": transaction.transaction_date.isoformat(),
        }
    })


@app.route("/transactions", methods=["GET"])
def get_transactions():
    """
    Get user's transactions with optional filtering.

    Query params:
        userId: int (required)
        category: string (optional)
        startDate: YYYY-MM-DD (optional)
        endDate: YYYY-MM-DD (optional)
        limit: int (optional, default 50)

    Returns:
    {
        "transactions": [...],
        "summary": { "totalIncome": x, "totalExpenses": y, "count": z }
    }
    """
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    # Build query
    query = Transaction.query.filter_by(user_id=user_id)

    # Apply filters
    category = request.args.get("category")
    if category:
        query = query.filter_by(category=category.lower())

    start_date = request.args.get("startDate")
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.transaction_date >= start)
        except ValueError:
            pass

    end_date = request.args.get("endDate")
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.transaction_date <= end)
        except ValueError:
            pass

    # Limit results
    limit = min(int(request.args.get("limit", 50)), 200)
    transactions = query.order_by(Transaction.transaction_date.desc()).limit(limit).all()

    # Build response
    tx_list = []
    total_income = 0
    total_expenses = 0

    for tx in transactions:
        tx_list.append({
            "id": tx.id,
            "amount": tx.amount,
            "category": tx.category,
            "transactionType": tx.transaction_type,
            "merchant": tx.merchant,
            "description": tx.description,
            "date": tx.transaction_date.isoformat() if tx.transaction_date else None,
            "source": tx.source,
        })
        if tx.transaction_type == "income":
            total_income += tx.amount
        else:
            total_expenses += tx.amount

    return jsonify({
        "transactions": tx_list,
        "summary": {
            "totalIncome": round(total_income, 2),
            "totalExpenses": round(total_expenses, 2),
            "count": len(tx_list)
        }
    })


@app.route("/savings-goal", methods=["POST"])
def create_savings_goal():
    """
    Create or update a savings goal.

    Expected request body:
    {
        "userId": 1,
        "name": "Emergency Fund",
        "targetAmount": 10000,
        "targetDate": "2026-12-31",     // optional
        "monthlyContribution": 500,     // optional
        "priority": 1,                  // optional (1=high, 2=medium, 3=low)
        "description": "6 months expenses"  // optional
    }

    Returns:
    {
        "status": "success",
        "goal": { ... }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    name = data.get("name")
    target_amount = data.get("targetAmount")

    if not user_id or not name or target_amount is None:
        return jsonify({"error": "userId, name, and targetAmount are required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check for existing goal with same name
    existing = SavingsGoal.query.filter_by(
        user_id=user_id,
        name=name,
        is_active=True
    ).first()

    # Parse target date
    target_date = None
    if data.get("targetDate"):
        try:
            target_date = datetime.strptime(data["targetDate"], "%Y-%m-%d").date()
        except ValueError:
            pass

    if existing:
        # Update existing goal
        existing.target_amount = float(target_amount)
        if target_date:
            existing.target_date = target_date
        if data.get("monthlyContribution") is not None:
            existing.monthly_contribution = float(data["monthlyContribution"])
        if data.get("priority"):
            existing.priority = int(data["priority"])
        if data.get("description"):
            existing.description = data["description"]
        goal = existing
    else:
        # Create new goal
        goal = SavingsGoal(
            user_id=user_id,
            name=name,
            target_amount=float(target_amount),
            current_amount=0,
            target_date=target_date,
            monthly_contribution=float(data.get("monthlyContribution", 0)),
            priority=int(data.get("priority", 2)),
            description=data.get("description"),
            is_active=True
        )
        db.session.add(goal)

    db.session.commit()

    progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0

    return jsonify({
        "status": "success",
        "goal": {
            "id": goal.id,
            "name": goal.name,
            "targetAmount": goal.target_amount,
            "currentAmount": goal.current_amount,
            "progressPercent": round(progress, 1),
            "targetDate": goal.target_date.isoformat() if goal.target_date else None,
            "monthlyContribution": goal.monthly_contribution,
            "priority": goal.priority,
        }
    })


@app.route("/savings-goals", methods=["GET"])
def get_savings_goals():
    """
    Get user's savings goals.

    Query params:
        userId: int (required)
        activeOnly: bool (optional, default true)

    Returns:
    {
        "goals": [...],
        "summary": { "totalSaved": x, "totalTarget": y, "overallProgress": z }
    }
    """
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    active_only = request.args.get("activeOnly", "true").lower() == "true"

    query = SavingsGoal.query.filter_by(user_id=user_id)
    if active_only:
        query = query.filter_by(is_active=True)

    goals = query.order_by(SavingsGoal.priority, SavingsGoal.created_at).all()

    goal_list = []
    total_saved = 0
    total_target = 0

    for goal in goals:
        progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
        total_saved += goal.current_amount
        total_target += goal.target_amount

        goal_list.append({
            "id": goal.id,
            "name": goal.name,
            "targetAmount": goal.target_amount,
            "currentAmount": goal.current_amount,
            "progressPercent": round(progress, 1),
            "remaining": max(0, goal.target_amount - goal.current_amount),
            "targetDate": goal.target_date.isoformat() if goal.target_date else None,
            "monthlyContribution": goal.monthly_contribution,
            "priority": goal.priority,
            "isCompleted": goal.is_completed,
        })

    overall_progress = (total_saved / total_target * 100) if total_target > 0 else 0

    return jsonify({
        "goals": goal_list,
        "summary": {
            "totalSaved": round(total_saved, 2),
            "totalTarget": round(total_target, 2),
            "overallProgress": round(overall_progress, 1),
            "goalCount": len(goal_list)
        }
    })


@app.route("/savings-contribution", methods=["POST"])
def add_savings_contribution():
    """
    Add a contribution to a savings goal.

    Expected request body:
    {
        "userId": 1,
        "goalId": 1,        // or "goalName": "Emergency Fund"
        "amount": 100,
        "notes": "Monthly contribution"  // optional
    }

    Returns:
    {
        "status": "success",
        "contribution": { ... },
        "goal": { ... }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    amount = data.get("amount")

    if not user_id or amount is None:
        return jsonify({"error": "userId and amount are required"}), 400

    # Find the goal
    goal = None
    if data.get("goalId"):
        goal = SavingsGoal.query.filter_by(
            id=int(data["goalId"]),
            user_id=user_id,
            is_active=True
        ).first()
    elif data.get("goalName"):
        goal = SavingsGoal.query.filter_by(
            user_id=user_id,
            is_active=True
        ).filter(SavingsGoal.name.ilike(f"%{data['goalName']}%")).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    # Create contribution
    contribution = SavingsContribution(
        goal_id=goal.id,
        user_id=user_id,
        amount=float(amount),
        contribution_date=date.today(),
        source="manual",
        notes=data.get("notes")
    )
    db.session.add(contribution)

    # Update goal progress
    goal.current_amount = (goal.current_amount or 0) + float(amount)

    # Check if goal is completed
    if goal.current_amount >= goal.target_amount and not goal.is_completed:
        goal.is_completed = True
        goal.completed_at = datetime.utcnow()

    db.session.commit()

    progress = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0

    return jsonify({
        "status": "success",
        "contribution": {
            "id": contribution.id,
            "amount": contribution.amount,
            "date": contribution.contribution_date.isoformat(),
        },
        "goal": {
            "id": goal.id,
            "name": goal.name,
            "currentAmount": goal.current_amount,
            "targetAmount": goal.target_amount,
            "progressPercent": round(progress, 1),
            "remaining": max(0, goal.target_amount - goal.current_amount),
            "isCompleted": goal.is_completed,
        }
    })


@app.route("/budget-category", methods=["PUT"])
def update_budget_category():
    """
    Update or create a budget category allocation.

    Expected request body:
    {
        "userId": 1,
        "category": "groceries",
        "budgetedAmount": 500,      // new budget amount
        "isEssential": true         // optional
    }

    Returns:
    {
        "status": "success",
        "category": { ... }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    category = data.get("category")
    budgeted_amount = data.get("budgetedAmount")

    if not user_id or not category or budgeted_amount is None:
        return jsonify({"error": "userId, category, and budgetedAmount are required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    current_month = datetime.now().strftime("%Y-%m")

    # Find or create category
    budget_cat = BudgetCategory.query.filter_by(
        user_id=user_id,
        name=category.lower(),
        month_year=current_month
    ).first()

    if budget_cat:
        old_amount = budget_cat.budgeted_amount
        budget_cat.budgeted_amount = float(budgeted_amount)
        if data.get("isEssential") is not None:
            budget_cat.is_essential = bool(data["isEssential"])
    else:
        old_amount = 0
        budget_cat = BudgetCategory(
            user_id=user_id,
            name=category.lower(),
            budgeted_amount=float(budgeted_amount),
            spent_amount=0,
            month_year=current_month,
            is_essential=bool(data.get("isEssential", False))
        )
        db.session.add(budget_cat)

    db.session.commit()

    remaining = budget_cat.budgeted_amount - (budget_cat.spent_amount or 0)
    percent_used = ((budget_cat.spent_amount or 0) / budget_cat.budgeted_amount * 100) if budget_cat.budgeted_amount > 0 else 0

    return jsonify({
        "status": "success",
        "category": {
            "name": budget_cat.name,
            "budgetedAmount": budget_cat.budgeted_amount,
            "spentAmount": budget_cat.spent_amount or 0,
            "remaining": round(remaining, 2),
            "percentUsed": round(percent_used, 1),
            "isEssential": budget_cat.is_essential,
            "monthYear": budget_cat.month_year,
            "previousBudget": old_amount,
        }
    })


# =============================================================================
# SESSION & PROACTIVE MESSAGE ENDPOINTS
# =============================================================================

@app.route("/session/start", methods=["POST"])
def start_session():
    """
    Start a new conversation session with proactive message check.

    Expected request body:
    {
        "userId": 1
    }

    Returns:
    {
        "sessionId": "uuid",
        "proactiveMessage": {          // null if no proactive message
            "message": "...",
            "suggestedAction": "tool_name",
            "severity": "warning"
        }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    # Start session via orchestrator
    orchestrator = get_orchestrator()
    session_id = orchestrator.start_session(user_id)

    # Check for proactive messages
    proactive = check_proactive_message(user_id)

    return jsonify({
        "sessionId": session_id,
        "proactiveMessage": proactive
    })


@app.route("/session/end", methods=["POST"])
def end_session():
    """
    End a conversation session.

    Expected request body:
    {
        "sessionId": "uuid"
    }

    Returns:
    {
        "status": "success"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    session_id = data.get("sessionId")
    if not session_id:
        return jsonify({"error": "sessionId is required"}), 400

    orchestrator = get_orchestrator()
    orchestrator.end_session(session_id)

    return jsonify({"status": "success"})


@app.route("/proactive/check", methods=["GET"])
def check_proactive():
    """
    Check if there are any proactive messages for the user.

    Query params:
        userId: int (required)

    Returns:
    {
        "hasMessage": true/false,
        "message": {
            "message": "...",
            "suggestedAction": "tool_name",
            "severity": "warning"
        } or null
    }
    """
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    proactive = check_proactive_message(user_id)

    return jsonify({
        "hasMessage": proactive is not None,
        "message": proactive
    })


@app.route("/chat/session", methods=["POST"])
def chat_with_session():
    """
    Chat endpoint with full session support.
    Maintains conversation context across messages.

    Expected request body:
    {
        "message": "user text",
        "userId": 1,
        "sessionId": "uuid",          // optional, created if not provided
        "isSessionStart": false       // optional, triggers proactive check
    }

    Returns:
    {
        "textMessage": "response text",
        "visualPayload": { ... } or null,
        "sessionId": "uuid",
        "suggestions": ["...", "..."],
        "uiEvents": [...]
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_message = data.get("message", "")
    user_id = data.get("userId")
    session_id = data.get("sessionId")
    is_session_start = data.get("isSessionStart", False)

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    # Generate session ID if not provided
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        is_session_start = True

    # Process with session support
    response = process_message_with_session(
        text=user_message,
        user_id=user_id,
        session_id=session_id,
        is_session_start=is_session_start
    )

    return jsonify(response)


@app.route("/budget-categories", methods=["GET"])
def get_budget_categories():
    """
    Get user's budget categories for the current month.

    Query params:
        userId: int (required)
        monthYear: YYYY-MM (optional, defaults to current month)

    Returns:
    {
        "categories": [...],
        "summary": { "totalBudgeted": x, "totalSpent": y, "remaining": z }
    }
    """
    user_id = request.args.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    month_year = request.args.get("monthYear", datetime.now().strftime("%Y-%m"))

    categories = BudgetCategory.query.filter_by(
        user_id=user_id,
        month_year=month_year
    ).order_by(BudgetCategory.display_order, BudgetCategory.name).all()

    cat_list = []
    total_budgeted = 0
    total_spent = 0

    for cat in categories:
        spent = cat.spent_amount or 0
        remaining = cat.budgeted_amount - spent
        percent_used = (spent / cat.budgeted_amount * 100) if cat.budgeted_amount > 0 else 0

        total_budgeted += cat.budgeted_amount
        total_spent += spent

        cat_list.append({
            "name": cat.name,
            "budgetedAmount": cat.budgeted_amount,
            "spentAmount": spent,
            "remaining": round(remaining, 2),
            "percentUsed": round(percent_used, 1),
            "isEssential": cat.is_essential,
            "icon": cat.icon,
            "color": cat.color,
        })

    return jsonify({
        "categories": cat_list,
        "summary": {
            "totalBudgeted": round(total_budgeted, 2),
            "totalSpent": round(total_spent, 2),
            "remaining": round(total_budgeted - total_spent, 2),
            "monthYear": month_year
        }
    })


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@app.route("/analytics/overview", methods=["GET"])
def analytics_overview():
    """
    Get analytics overview for agent performance.

    Query params:
        days: int (optional, default 7) - number of days to include

    Returns:
    {
        "period": "Last 7 days",
        "totalEvents": int,
        "eventsByType": { "chat": n, "tool_call": n, ... },
        "successRate": float,
        "avgLatencyMs": float,
        "activeUsers": int,
        "totalUsers": int,
        "dailyActivity": [...],
        "topTools": [...]
    }
    """
    days = request.args.get("days", 7, type=int)
    days = min(max(days, 1), 30)  # Clamp between 1 and 30

    analytics = get_analytics()
    overview = analytics.get_overview(days=days)

    return jsonify(overview)


@app.route("/analytics/tools", methods=["GET"])
def analytics_tools():
    """
    Get detailed tool usage statistics.

    Returns:
    {
        "tools": {
            "tool_name": {
                "toolName": str,
                "totalCalls": int,
                "successfulCalls": int,
                "failedCalls": int,
                "successRate": float,
                "avgLatencyMs": float,
                "lastCalled": str (ISO datetime)
            },
            ...
        },
        "successRates": { "tool_name": float, ... }
    }
    """
    analytics = get_analytics()

    return jsonify({
        "tools": analytics.get_tool_stats(),
        "successRates": analytics.get_tool_success_rates()
    })


@app.route("/analytics/user/<int:user_id>", methods=["GET"])
def analytics_user(user_id: int):
    """
    Get analytics for a specific user.

    Returns:
    {
        "userId": int,
        "totalInteractions": int,
        "totalToolCalls": int,
        "sessionsCount": int,
        "lastActive": str (ISO datetime),
        "favoriteTools": [...],
        "proactiveEngagement": float (%)
    }
    """
    analytics = get_analytics()
    user_stats = analytics.get_user_stats(user_id)

    if not user_stats:
        return jsonify({
            "userId": user_id,
            "totalInteractions": 0,
            "totalToolCalls": 0,
            "sessionsCount": 0,
            "lastActive": None,
            "favoriteTools": [],
            "proactiveEngagement": 0
        })

    return jsonify(user_stats)


@app.route("/analytics/failures", methods=["GET"])
def analytics_failures():
    """
    Get common failure patterns for improvement analysis.

    Returns:
    {
        "patterns": [
            {
                "tool": str,
                "error": str,
                "count": int,
                "suggestion": str
            },
            ...
        ]
    }
    """
    analytics = get_analytics()

    return jsonify({
        "patterns": analytics.get_common_failure_patterns()
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
