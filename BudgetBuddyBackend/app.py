import json
import os
from datetime import datetime, date
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from db_models import db, User, FinancialProfile, BudgetPlan, SavedStatement, PlaidItem, PlaidAccount, Transaction
from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement
from services.plan_generator import generate_plan, save_plan_to_db
from services import plaid_service

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
# Plaid Integration Endpoints
# =============================================================================

@app.route("/plaid/link-token", methods=["POST"])
def create_plaid_link_token():
    """
    Create a Plaid Link token to initialize the Link flow.

    Expected request body:
    {
        "userId": 1
    }

    Returns:
    {
        "linkToken": "link-sandbox-...",
        "expiration": "2026-02-10T00:00:00Z"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        result = plaid_service.create_link_token(user_id)
        return jsonify({
            "linkToken": result["link_token"],
            "expiration": result["expiration"],
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Plaid link token error: {e}")
        return jsonify({"error": "Failed to create link token"}), 500


@app.route("/plaid/exchange-token", methods=["POST"])
def exchange_plaid_token():
    """
    Exchange a public token for an access token and fetch initial data.

    Expected request body:
    {
        "userId": 1,
        "publicToken": "public-sandbox-...",
        "institutionId": "ins_109508",
        "institutionName": "First Platypus Bank"
    }

    Returns:
    {
        "success": true,
        "itemId": "...",
        "accounts": [...],
        "transactionCount": 150
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    public_token = data.get("publicToken")
    institution_id = data.get("institutionId")
    institution_name = data.get("institutionName")

    if not user_id or not public_token:
        return jsonify({"error": "userId and publicToken are required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Exchange public token for access token
        encrypted_token, item_id = plaid_service.exchange_public_token(public_token)

        # Create PlaidItem record
        plaid_item = PlaidItem(
            user_id=user_id,
            item_id=item_id,
            access_token_encrypted=encrypted_token,
            institution_id=institution_id,
            institution_name=institution_name or plaid_service.get_institution_name(institution_id),
            status="active"
        )
        db.session.add(plaid_item)
        db.session.flush()

        # Fetch accounts
        accounts_response = plaid_service.get_accounts(encrypted_token)
        account_records = []

        for account_data in accounts_response["accounts"]:
            account = PlaidAccount(
                plaid_item_id=plaid_item.id,
                account_id=account_data["account_id"],
                name=account_data["name"],
                official_name=account_data["official_name"],
                account_type=account_data["type"],
                account_subtype=account_data["subtype"],
                balance_available=account_data["balances"]["available"],
                balance_current=account_data["balances"]["current"],
                balance_limit=account_data["balances"]["limit"],
                mask=account_data["mask"]
            )
            db.session.add(account)
            account_records.append(account)

        db.session.flush()

        # Fetch historical transactions (6 months)
        transactions = plaid_service.fetch_historical_transactions(encrypted_token, months=6)

        # Create a mapping of account_id to PlaidAccount record
        account_map = {acc.account_id: acc for acc in account_records}

        transaction_count = 0
        for txn_data in transactions:
            account = account_map.get(txn_data["account_id"])
            if account:
                transaction = Transaction(
                    plaid_account_id=account.id,
                    transaction_id=txn_data["transaction_id"],
                    amount=txn_data["amount"],
                    date=datetime.strptime(txn_data["date"], "%Y-%m-%d").date() if txn_data["date"] else None,
                    authorized_date=datetime.strptime(txn_data["authorized_date"], "%Y-%m-%d").date() if txn_data["authorized_date"] else None,
                    name=txn_data["name"],
                    merchant_name=txn_data["merchant_name"],
                    category_primary=txn_data["category"],
                    category_detailed=txn_data["category_detailed"],
                    category_confidence=txn_data["category_confidence"],
                    pending=txn_data["pending"],
                    payment_channel=txn_data["payment_channel"]
                )
                db.session.add(transaction)
                transaction_count += 1

        db.session.commit()

        return jsonify({
            "success": True,
            "itemId": item_id,
            "accounts": [
                {
                    "accountId": acc.account_id,
                    "name": acc.name,
                    "type": acc.account_type,
                    "subtype": acc.account_subtype,
                    "mask": acc.mask,
                    "balanceCurrent": acc.balance_current,
                    "balanceAvailable": acc.balance_available
                }
                for acc in account_records
            ],
            "transactionCount": transaction_count
        })

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        print(f"Plaid exchange token error: {e}")
        return jsonify({"error": "Failed to exchange token and fetch data"}), 500


@app.route("/plaid/accounts/<int:user_id>", methods=["GET"])
def get_plaid_accounts(user_id):
    """
    Get all linked accounts for a user.

    Returns:
    {
        "items": [
            {
                "itemId": "...",
                "institutionName": "First Platypus Bank",
                "status": "active",
                "accounts": [...]
            }
        ]
    }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()

    items = []
    for item in plaid_items:
        accounts = []
        for account in item.accounts:
            accounts.append({
                "accountId": account.account_id,
                "name": account.name,
                "officialName": account.official_name,
                "type": account.account_type,
                "subtype": account.account_subtype,
                "mask": account.mask,
                "balanceAvailable": account.balance_available,
                "balanceCurrent": account.balance_current,
                "balanceLimit": account.balance_limit
            })

        items.append({
            "itemId": item.item_id,
            "institutionId": item.institution_id,
            "institutionName": item.institution_name,
            "status": item.status,
            "createdAt": item.created_at.isoformat() if item.created_at else None,
            "accounts": accounts
        })

    return jsonify({"items": items})


@app.route("/plaid/transactions/<int:user_id>", methods=["GET"])
def get_plaid_transactions(user_id):
    """
    Get transactions for a user with optional date filtering.

    Query params:
        startDate: YYYY-MM-DD (optional)
        endDate: YYYY-MM-DD (optional)
        limit: int (optional, default 100)
        offset: int (optional, default 0)

    Returns:
    {
        "transactions": [...],
        "total": 500,
        "hasMore": true
    }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Get all account IDs for this user
    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if not account_ids:
        return jsonify({"transactions": [], "total": 0, "hasMore": False})

    # Build query
    query = Transaction.query.filter(Transaction.plaid_account_id.in_(account_ids))

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.date <= end)
        except ValueError:
            pass

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    transactions = query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

    result = []
    for txn in transactions:
        result.append({
            "transactionId": txn.transaction_id,
            "accountId": txn.plaid_account.account_id,
            "amount": txn.amount,
            "date": txn.date.isoformat() if txn.date else None,
            "authorizedDate": txn.authorized_date.isoformat() if txn.authorized_date else None,
            "name": txn.name,
            "merchantName": txn.merchant_name,
            "categoryPrimary": txn.category_primary,
            "categoryDetailed": txn.category_detailed,
            "pending": txn.pending,
            "paymentChannel": txn.payment_channel
        })

    return jsonify({
        "transactions": result,
        "total": total,
        "hasMore": offset + limit < total
    })


@app.route("/plaid/sync/<int:user_id>", methods=["POST"])
def sync_plaid_transactions(user_id):
    """
    Sync new transactions for all of a user's linked accounts.

    Returns:
    {
        "added": 5,
        "modified": 2,
        "removed": 0
    }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_items = PlaidItem.query.filter_by(user_id=user_id, status="active").all()

    if not plaid_items:
        return jsonify({"error": "No linked accounts found"}), 404

    total_added = 0
    total_modified = 0
    total_removed = 0

    for item in plaid_items:
        try:
            # Build account map for this item
            account_map = {acc.account_id: acc for acc in item.accounts}

            has_more = True
            cursor = item.transactions_cursor

            while has_more:
                result = plaid_service.sync_transactions(
                    item.access_token_encrypted,
                    cursor
                )

                # Process added transactions
                for txn_data in result["added"]:
                    account = account_map.get(txn_data["account_id"])
                    if account:
                        # Check if transaction already exists
                        existing = Transaction.query.filter_by(
                            transaction_id=txn_data["transaction_id"]
                        ).first()

                        if not existing:
                            transaction = Transaction(
                                plaid_account_id=account.id,
                                transaction_id=txn_data["transaction_id"],
                                amount=txn_data["amount"],
                                date=datetime.strptime(txn_data["date"], "%Y-%m-%d").date() if txn_data["date"] else None,
                                authorized_date=datetime.strptime(txn_data["authorized_date"], "%Y-%m-%d").date() if txn_data["authorized_date"] else None,
                                name=txn_data["name"],
                                merchant_name=txn_data["merchant_name"],
                                category_primary=txn_data["category"],
                                category_detailed=txn_data["category_detailed"],
                                category_confidence=txn_data["category_confidence"],
                                pending=txn_data["pending"],
                                payment_channel=txn_data["payment_channel"]
                            )
                            db.session.add(transaction)
                            total_added += 1

                # Process modified transactions
                for txn_data in result["modified"]:
                    existing = Transaction.query.filter_by(
                        transaction_id=txn_data["transaction_id"]
                    ).first()

                    if existing:
                        existing.amount = txn_data["amount"]
                        existing.date = datetime.strptime(txn_data["date"], "%Y-%m-%d").date() if txn_data["date"] else None
                        existing.name = txn_data["name"]
                        existing.merchant_name = txn_data["merchant_name"]
                        existing.category_primary = txn_data["category"]
                        existing.category_detailed = txn_data["category_detailed"]
                        existing.pending = txn_data["pending"]
                        total_modified += 1

                # Process removed transactions
                for removed in result["removed"]:
                    existing = Transaction.query.filter_by(
                        transaction_id=removed["transaction_id"]
                    ).first()
                    if existing:
                        db.session.delete(existing)
                        total_removed += 1

                cursor = result["next_cursor"]
                has_more = result["has_more"]

            # Update the cursor for next sync
            item.transactions_cursor = cursor

        except Exception as e:
            print(f"Error syncing item {item.item_id}: {e}")
            continue

    db.session.commit()

    return jsonify({
        "added": total_added,
        "modified": total_modified,
        "removed": total_removed
    })


@app.route("/plaid/unlink/<int:user_id>/<item_id>", methods=["DELETE"])
def unlink_plaid_item(user_id, item_id):
    """
    Unlink a bank account (remove PlaidItem and associated data).

    Returns:
    {
        "success": true
    }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_item = PlaidItem.query.filter_by(
        user_id=user_id,
        item_id=item_id
    ).first()

    if not plaid_item:
        return jsonify({"error": "Plaid item not found"}), 404

    try:
        # Remove from Plaid
        plaid_service.remove_item(plaid_item.access_token_encrypted)
    except Exception as e:
        print(f"Warning: Failed to remove item from Plaid: {e}")
        # Continue with local cleanup even if Plaid removal fails

    # Delete from database (cascade will remove accounts and transactions)
    db.session.delete(plaid_item)
    db.session.commit()

    return jsonify({"success": True})


if __name__ == "__main__":
    # host='0.0.0.0' allows connections from physical devices on the same network
    app.run(debug=True, host='0.0.0.0', port=5000)
