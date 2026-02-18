import json
import os
import random
import string
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from db_models import db, User, FinancialProfile, BudgetPlan, SavedStatement, OTPCode, PlaidItem, PlaidAccount, Transaction, UserCategoryPreference, MerchantClassification, DeviceToken
from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement
from services.plan_generator import generate_plan, save_plan_to_db
from services import plaid_service
from services.classification_service import classify_transaction, retroactively_reclassify, classify_new_transactions, normalize_merchant_name, llm_classify_merchants_batch, CONFIDENCE_THRESHOLD
from services.push_service import notify_new_transactions, notify_classification_needed

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budgetbuddy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Create tables on first request
with app.app_context():
    db.create_all()

    # Migrate: add 'name' column to User table if it doesn't exist (SQLite)
    try:
        import sqlite3 as _sqlite3
        db_path = os.path.join(app.instance_path, 'budgetbuddy.db')
        if os.path.exists(db_path):
            conn = _sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(user)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns and 'name' not in columns:
                conn.execute("ALTER TABLE user ADD COLUMN name VARCHAR(100)")
                conn.commit()
                print("Migration: added 'name' column to user table")

            # Migrate: add classification columns to transaction table
            cursor = conn.execute("PRAGMA table_info('transaction')")
            tx_columns = [row[1] for row in cursor.fetchall()]
            if tx_columns and 'sub_category' not in tx_columns:
                conn.execute("ALTER TABLE 'transaction' ADD COLUMN sub_category VARCHAR(20) DEFAULT 'unclassified'")
                conn.commit()
                print("Migration: added 'sub_category' column to transaction table")
            if tx_columns and 'essential_amount' not in tx_columns:
                conn.execute("ALTER TABLE 'transaction' ADD COLUMN essential_amount FLOAT")
                conn.commit()
                print("Migration: added 'essential_amount' column to transaction table")
            if tx_columns and 'discretionary_amount' not in tx_columns:
                conn.execute("ALTER TABLE 'transaction' ADD COLUMN discretionary_amount FLOAT")
                conn.commit()
                print("Migration: added 'discretionary_amount' column to transaction table")

            conn.close()
    except Exception as e:
        print(f"Migration warning (non-fatal): {e}")

# Enable CORS for iOS simulator to communicate with localhost
# Allow all origins and methods for development
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})


@app.route("/")
def index():
    return jsonify({"message": "Welcome to BudgetBuddy API"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def send_via_twilio(phone_number: str, code: str):
    """
    Placeholder for Twilio SMS integration.
    In production, this would send the SMS via Twilio API.
    For development, we just print to console.
    """
    print(f"\n{'='*50}")
    print(f"SMS to {phone_number}: Your BudgetBuddy code is {code}")
    print(f"{'='*50}\n")


@app.route("/v1/send_sms_code", methods=["POST"])
def send_sms_code():
    """
    Send an SMS verification code to the provided phone number.

    Expected request body:
    {
        "phone_number": "+14155551234"
    }

    Returns:
    {
        "status": "success"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    phone_number = data.get("phone_number", "").strip()

    if not phone_number:
        return jsonify({"error": "Phone number is required"}), 400

    # Basic E.164 validation (starts with + and has 10-15 digits)
    if not phone_number.startswith("+") or not (10 <= len(phone_number) <= 16):
        return jsonify({"error": "Invalid phone number format. Use E.164 format (e.g., +14155551234)"}), 400

    # Generate 6-digit code
    code = ''.join(random.choices(string.digits, k=6))

    # Set expiry to 5 minutes from now
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    # Invalidate any existing unused codes for this phone
    OTPCode.query.filter_by(phone_number=phone_number, verified=False).delete()

    # Create new OTP record
    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expires_at=expires_at
    )
    db.session.add(otp)
    db.session.commit()

    # Send via Twilio (placeholder)
    send_via_twilio(phone_number, code)

    return jsonify({"status": "success"})


@app.route("/v1/verify_code", methods=["POST"])
def verify_code():
    """
    Verify the SMS code and authenticate the user.

    Expected request body:
    {
        "phone_number": "+14155551234",
        "code": "123456"
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

    phone_number = data.get("phone_number", "").strip()
    code = data.get("code", "").strip()

    if not phone_number or not code:
        return jsonify({"error": "Phone number and code are required"}), 400

    # Find the most recent unverified OTP for this phone
    otp = OTPCode.query.filter_by(
        phone_number=phone_number,
        verified=False
    ).order_by(OTPCode.created_at.desc()).first()

    if not otp:
        return jsonify({"error": "No verification code found. Please request a new one."}), 400

    # Check if code is expired
    if datetime.utcnow() > otp.expires_at:
        return jsonify({"error": "Verification code has expired. Please request a new one."}), 400

    # Check if code matches
    if otp.code != code:
        return jsonify({"error": "Invalid verification code"}), 401

    # Mark OTP as verified
    otp.verified = True
    db.session.commit()

    # Find or create user
    user = User.query.filter_by(phone_number=phone_number).first()

    if not user:
        # Auto-create new user
        user = User(phone_number=phone_number)
        db.session.add(user)
        db.session.commit()

    return jsonify({
        "token": user.id,
        "hasProfile": user.profile is not None,
        "name": user.name
    })


@app.route("/v1/user", methods=["DELETE"])
def delete_user():
    """
    Delete a user and all associated data (App Store compliance).

    Query params:
        userId: int - the user's ID

    Returns: 204 No Content on success
    """
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "Invalid userId"}), 400

    user = User.query.get(user_id)

    if user:
        # Delete associated OTP codes
        OTPCode.query.filter_by(phone_number=user.phone_number).delete()

        # Delete user (cascade will handle profile, statement, plans)
        db.session.delete(user)
        db.session.commit()

    return "", 204


@app.route("/onboarding", methods=["POST"])
def onboarding():
    """
    Save user's profile from onboarding (4-Question Protocol).

    Expected request body:
    {
        "userId": 1,
        "name": "Alex",
        "isStudent": true,
        "budgetingGoal": "emergency_fund",
        "strictnessLevel": "moderate"
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
    name = data.get("name", "").strip() or None
    is_student = data.get("isStudent", False)
    budgeting_goal = data.get("budgetingGoal", "stability")
    strictness_level = data.get("strictnessLevel", "moderate")

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Update name if provided
    if name:
        user.name = name

    # Check if profile already exists
    if user.profile:
        # Update existing profile
        user.profile.is_student = is_student
        user.profile.budgeting_goal = budgeting_goal
        user.profile.strictness_level = strictness_level
    else:
        # Create new profile
        profile = FinancialProfile(
            user_id=user_id,
            is_student=is_student,
            budgeting_goal=budgeting_goal,
            strictness_level=strictness_level
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
    Get financial summary from Plaid accounts (preferred) or saved statement (fallback).

    Query params:
        userId: int - the authenticated user's ID

    Returns:
    {
        "hasData": true/false,
        "source": "plaid" | "statement" | "none",
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

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # --- Try Plaid first ---
    plaid_accounts = (
        PlaidAccount.query
        .join(PlaidItem)
        .filter(PlaidItem.user_id == user_id, PlaidItem.status == "active")
        .all()
    )

    if plaid_accounts:
        # Net Worth = assets - liabilities
        asset_types = {"depository", "investment"}
        liability_types = {"credit", "loan"}

        asset_total = sum(
            (a.balance_current or 0) for a in plaid_accounts
            if a.account_type in asset_types
        )
        liability_total = sum(
            (a.balance_current or 0) for a in plaid_accounts
            if a.account_type in liability_types
        )
        net_worth = round(asset_total - liability_total, 2)

        # Safe to Spend: prefer BudgetPlan.safeToSpend, else sum of available balances
        safe_to_spend = None
        latest_plan = (
            BudgetPlan.query
            .filter_by(user_id=user_id)
            .order_by(BudgetPlan.created_at.desc())
            .first()
        )
        if latest_plan:
            try:
                plan_data = json.loads(latest_plan.plan_json)
                safe_to_spend = plan_data.get("safeToSpend")
            except (json.JSONDecodeError, TypeError):
                pass

        if safe_to_spend is None:
            safe_to_spend = sum(
                (a.balance_available or a.balance_current or 0)
                for a in plaid_accounts
                if a.account_type == "depository"
            )

        safe_to_spend = round(max(0, safe_to_spend), 2)

        return jsonify({
            "hasData": True,
            "source": "plaid",
            "netWorth": net_worth,
            "safeToSpend": safe_to_spend,
            "statementInfo": None,
            "spendingBreakdown": None
        })

    # --- Fall back to statement ---
    statement = SavedStatement.query.filter_by(user_id=user_id).first()

    if statement:
        net_worth = statement.ending_balance
        safe_to_spend = max(0, .08 * net_worth) if net_worth else 0.0

        statement_period = None
        if statement.statement_start_date and statement.statement_end_date:
            statement_period = f"{statement.statement_start_date.isoformat()} to {statement.statement_end_date.isoformat()}"

        statement_info = {
            "filename": statement.filename,
            "statementPeriod": statement_period,
            "uploadedAt": statement.created_at.isoformat() if statement.created_at else None
        }

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
            "hasData": True,
            "source": "statement",
            "netWorth": round(net_worth, 2) if net_worth else 0.0,
            "safeToSpend": round(safe_to_spend, 2),
            "statementInfo": statement_info,
            "spendingBreakdown": spending_breakdown
        })

    # --- Neither ---
    return jsonify({
        "hasData": False,
        "source": "none",
        "netWorth": None,
        "safeToSpend": None,
        "statementInfo": None,
        "spendingBreakdown": None
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
                classify_transaction(transaction, user_id)
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
                            classify_transaction(transaction, user_id)
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


# =============================================================================
# User Profile Endpoints
# =============================================================================

@app.route("/user/profile/<int:user_id>", methods=["GET"])
def get_user_profile(user_id):
    """
    Fetch user profile including name, email, financial profile, and linked Plaid accounts.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    profile_data = None
    if user.profile:
        profile_data = {
            "isStudent": user.profile.is_student,
            "budgetingGoal": user.profile.budgeting_goal,
            "strictnessLevel": user.profile.strictness_level
        }

    plaid_items_data = []
    for item in user.plaid_items:
        accounts = [{
            "accountId": acc.account_id,
            "name": acc.name,
            "type": acc.account_type,
            "subtype": acc.account_subtype,
            "mask": acc.mask,
            "balanceCurrent": acc.balance_current
        } for acc in item.accounts]

        plaid_items_data.append({
            "itemId": item.item_id,
            "institutionName": item.institution_name,
            "status": item.status,
            "accounts": accounts
        })

    return jsonify({
        "name": user.name,
        "phoneNumber": user.phone_number,
        "profile": profile_data,
        "plaidItems": plaid_items_data
    })


@app.route("/user/profile/<int:user_id>", methods=["PUT"])
def update_user_profile(user_id):
    """
    Update user profile fields (partial update).
    Accepts any subset of: name, isStudent, budgetingGoal, strictnessLevel.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    # Update user-level fields
    if "name" in data:
        user.name = data["name"]

    # Update profile fields
    if user.profile:
        if "isStudent" in data:
            user.profile.is_student = data["isStudent"]
        if "budgetingGoal" in data:
            user.profile.budgeting_goal = data["budgetingGoal"]
        if "strictnessLevel" in data:
            user.profile.strictness_level = data["strictnessLevel"]

    db.session.commit()

    return jsonify({"status": "success"})


# Plaid category code → human-readable display name
CATEGORY_DISPLAY_NAMES = {
    "INCOME": "Income",
    "TRANSFER_IN": "Transfers In",
    "TRANSFER_OUT": "Transfers Out",
    "LOAN_PAYMENTS": "Loan Payments",
    "BANK_FEES": "Bank Fees",
    "ENTERTAINMENT": "Entertainment",
    "FOOD_AND_DRINK": "Food & Drink",
    "GENERAL_MERCHANDISE": "Shopping",
    "HOME_IMPROVEMENT": "Home Improvement",
    "MEDICAL": "Medical",
    "PERSONAL_CARE": "Personal Care",
    "GENERAL_SERVICES": "Services",
    "GOVERNMENT_AND_NON_PROFIT": "Government & Taxes",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "RENT_AND_UTILITIES": "Rent & Utilities",
    "COFFEE": "Coffee",
    "GROCERIES": "Groceries",
    "RESTAURANTS": "Restaurants",
    "SHOPPING": "Shopping",
    "CLOTHING": "Clothing",
    "ELECTRONICS": "Electronics",
    "GAS": "Gas",
    "PARKING": "Parking",
    "PUBLIC_TRANSIT": "Public Transit",
    "RIDESHARE": "Rideshare",
    "AIRLINES": "Airlines",
    "LODGING": "Lodging",
    "SUBSCRIPTION": "Subscriptions",
    "GYM_AND_FITNESS": "Gym & Fitness",
    "UTILITIES": "Utilities",
    "INTERNET_AND_CABLE": "Internet & Cable",
    "PHONE": "Phone",
    "INSURANCE": "Insurance",
    "MORTGAGE": "Mortgage",
    "RENT": "Rent",
    "EDUCATION": "Education",
    "CHILDCARE": "Childcare",
    "PETS": "Pets",
    "CHARITY": "Charity",
    "INVESTMENTS": "Investments",
    "SAVINGS": "Savings",
    "TAXES": "Taxes",
    "GAMBLING": "Gambling",
    "ALCOHOL_AND_BARS": "Alcohol & Bars",
}


def format_category_name(raw_name):
    """Convert a Plaid category code to a human-readable display name."""
    if raw_name in CATEGORY_DISPLAY_NAMES:
        return CATEGORY_DISPLAY_NAMES[raw_name]
    # Fallback: "FOOD_AND_DRINK" → "Food & Drink"
    return raw_name.replace("_", " ").title().replace(" And ", " & ")


@app.route("/user/top-expenses/<int:user_id>", methods=["GET"])
def get_top_expenses(user_id):
    """
    Aggregate top spending categories from Plaid transactions (fallback: statement).

    Query params:
        days: int (optional, default 30)

    Returns:
    {
        "source": "plaid" | "statement",
        "topExpenses": [{ "category": str, "amount": float, "transactionCount": int }],
        "totalSpending": float,
        "period": int
    }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    days = request.args.get("days", 30, type=int)

    # Try Plaid transactions first
    plaid_items = PlaidItem.query.filter_by(user_id=user_id, status="active").all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if account_ids:
        start_date = (datetime.now() - timedelta(days=days)).date()
        transactions = Transaction.query.filter(
            Transaction.plaid_account_id.in_(account_ids),
            Transaction.date >= start_date
        ).all()

        category_data = {}
        for txn in transactions:
            if txn.amount > 0:
                cat = txn.category_primary or "Uncategorized"
                if cat not in category_data:
                    category_data[cat] = {"amount": 0, "count": 0}
                category_data[cat]["amount"] += txn.amount
                category_data[cat]["count"] += 1

        sorted_cats = sorted(category_data.items(), key=lambda x: x[1]["amount"], reverse=True)
        total = sum(v["amount"] for v in category_data.values())

        return jsonify({
            "source": "plaid",
            "topExpenses": [
                {"category": format_category_name(cat), "amount": round(data["amount"], 2), "transactionCount": data["count"]}
                for cat, data in sorted_cats[:5]
            ],
            "totalSpending": round(total, 2),
            "period": days
        })

    # Fallback to statement
    statement = SavedStatement.query.filter_by(user_id=user_id).first()
    if statement and statement.llm_analysis:
        try:
            analysis = json.loads(statement.llm_analysis)
            top_categories = analysis.get("top_categories", [])
            expenses = [
                {"category": cat.get("category", "Other"), "amount": float(cat.get("amount", 0)), "transactionCount": 0}
                for cat in top_categories[:5]
            ]
            total = sum(e["amount"] for e in expenses)
            return jsonify({
                "source": "statement",
                "topExpenses": expenses,
                "totalSpending": round(total, 2),
                "period": days
            })
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({
        "source": "none",
        "topExpenses": [],
        "totalSpending": 0,
        "period": days
    })


@app.route("/user/category-preferences/<int:user_id>", methods=["GET"])
def get_category_preferences(user_id):
    """Get user's pinned category preferences."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    prefs = UserCategoryPreference.query.filter_by(user_id=user_id).order_by(
        UserCategoryPreference.display_order
    ).all()

    return jsonify({
        "categories": [
            {"id": p.id, "categoryName": p.category_name, "displayOrder": p.display_order}
            for p in prefs
        ]
    })


@app.route("/user/category-preferences/<int:user_id>", methods=["PUT"])
def update_category_preferences(user_id):
    """
    Set pinned categories.

    Expected body:
    { "categories": ["FOOD_AND_DRINK", "TRANSPORTATION", "SHOPPING"] }
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    if not data or "categories" not in data:
        return jsonify({"error": "categories field is required"}), 400

    # Delete existing preferences
    UserCategoryPreference.query.filter_by(user_id=user_id).delete()

    # Insert new ones
    for i, cat_name in enumerate(data["categories"]):
        pref = UserCategoryPreference(
            user_id=user_id,
            category_name=cat_name,
            display_order=i
        )
        db.session.add(pref)

    db.session.commit()

    return jsonify({"status": "success"})


@app.route("/user/nudges/<int:user_id>", methods=["GET"])
def get_nudges(user_id):
    """
    Get rules-based smart nudges (actual vs. budget comparison).
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    from services.nudge_generator import generate_nudges
    nudges = generate_nudges(user_id)

    return jsonify({"nudges": nudges})


# =============================================================================
# Expense Classification Endpoints
# =============================================================================

@app.route("/expenses/<int:user_id>", methods=["GET"])
def get_expenses(user_id):
    """
    Get expenses with sub-category classification data.
    Auto-classifies any unclassified transactions on first access (lazy backfill).

    Query params:
        startDate, endDate, category, subCategory, limit, offset
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    category = request.args.get("category")
    sub_category = request.args.get("subCategory")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Get all account IDs for this user
    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if not account_ids:
        return jsonify({
            "transactions": [],
            "summary": {"totalEssential": 0, "totalDiscretionary": 0, "totalMixed": 0, "totalUnclassified": 0},
            "total": 0,
            "hasMore": False
        })

    # Lazy backfill: auto-classify unclassified expense transactions
    unclassified = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        ((Transaction.sub_category == 'unclassified') | (Transaction.sub_category.is_(None))),
        Transaction.amount > 0  # Only expenses, not income
    ).all()

    if unclassified:
        for txn in unclassified:
            classify_transaction(txn, user_id)
        db.session.commit()

    # Build query with filters
    query = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        Transaction.amount > 0  # Only expenses (positive = money out)
    )

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

    if category:
        query = query.filter(Transaction.category_primary == category)

    if sub_category:
        if sub_category == 'essential':
            # Include essential + mixed transactions with essential_amount > 0
            query = query.filter(
                (Transaction.sub_category == 'essential') |
                ((Transaction.sub_category == 'mixed') & (Transaction.essential_amount > 0))
            )
        elif sub_category == 'discretionary':
            # Include discretionary + mixed transactions with discretionary_amount > 0
            query = query.filter(
                (Transaction.sub_category == 'discretionary') |
                ((Transaction.sub_category == 'mixed') & (Transaction.discretionary_amount > 0))
            )
        else:
            query = query.filter(Transaction.sub_category == sub_category)

    # Compute summary from filtered query (before pagination)
    all_filtered = query.all()
    # Fold mixed into Essential/Fun Money totals
    total_essential = sum(t.essential_amount or 0 for t in all_filtered if t.sub_category in ('essential', 'mixed'))
    total_discretionary = sum(t.discretionary_amount or 0 for t in all_filtered if t.sub_category in ('discretionary', 'mixed'))
    total_unclassified = sum(t.amount for t in all_filtered if t.sub_category == 'unclassified' or t.sub_category is None)

    total = len(all_filtered)

    # Apply pagination and ordering
    transactions = query.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

    result = []
    for txn in transactions:
        result.append({
            "id": txn.id,
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
            "paymentChannel": txn.payment_channel,
            "subCategory": txn.sub_category or "unclassified",
            "essentialAmount": txn.essential_amount,
            "discretionaryAmount": txn.discretionary_amount
        })

    return jsonify({
        "transactions": result,
        "summary": {
            "totalEssential": round(total_essential, 2),
            "totalDiscretionary": round(total_discretionary, 2),
            "totalFunMoney": round(total_discretionary, 2),
            "totalMixed": 0,
            "totalUnclassified": round(total_unclassified, 2)
        },
        "total": total,
        "hasMore": offset + limit < total
    })


@app.route("/merchant/classify", methods=["POST"])
def classify_merchant():
    """
    User classifies a merchant. Creates/updates MerchantClassification
    and retroactively reclassifies all past transactions for that merchant.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    merchant_name = data.get("merchantName")
    classification = data.get("classification")
    essential_ratio = data.get("essentialRatio")

    if not user_id or not merchant_name or not classification:
        return jsonify({"error": "userId, merchantName, and classification are required"}), 400

    # Accept "split" as user-facing alias for "mixed"
    if classification == 'split':
        classification = 'mixed'

    if classification not in ('essential', 'discretionary', 'mixed'):
        return jsonify({"error": "classification must be essential, discretionary, mixed, or split"}), 400

    # Default essential_ratio based on classification
    if essential_ratio is None:
        if classification == 'essential':
            essential_ratio = 1.0
        elif classification == 'discretionary':
            essential_ratio = 0.0
        else:
            essential_ratio = 0.5

    normalized = normalize_merchant_name(merchant_name)

    # Create or update MerchantClassification
    mc = MerchantClassification.query.filter_by(
        user_id=user_id,
        merchant_name=normalized
    ).first()

    if mc:
        mc.classification = classification
        mc.essential_ratio = essential_ratio
        mc.confidence = 'user_set'
        mc.classification_count += 1
    else:
        mc = MerchantClassification(
            user_id=user_id,
            merchant_name=normalized,
            classification=classification,
            essential_ratio=essential_ratio,
            confidence='user_set',
            classification_count=1
        )
        db.session.add(mc)

    # Retroactively reclassify
    count = retroactively_reclassify(user_id, merchant_name, classification, essential_ratio)
    db.session.commit()

    return jsonify({
        "success": True,
        "reclassifiedCount": count
    })


@app.route("/transaction/<int:transaction_id>/classify", methods=["PUT"])
def classify_single_transaction(transaction_id):
    """
    User adjusts classification of a single transaction.
    Also updates the merchant's running average.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    sub_category = data.get("subCategory")
    essential_ratio = data.get("essentialRatio")

    # Accept "split" as user-facing alias for "mixed"
    if sub_category == 'split':
        sub_category = 'mixed'

    if not sub_category or sub_category not in ('essential', 'discretionary', 'mixed'):
        return jsonify({"error": "subCategory must be essential, discretionary, mixed, or split"}), 400

    if essential_ratio is None:
        if sub_category == 'essential':
            essential_ratio = 1.0
        elif sub_category == 'discretionary':
            essential_ratio = 0.0
        else:
            essential_ratio = 0.5

    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    # Apply classification to transaction
    amount = abs(transaction.amount) if transaction.amount else 0.0
    transaction.sub_category = sub_category
    transaction.essential_amount = round(amount * essential_ratio, 2)
    transaction.discretionary_amount = round(amount * (1.0 - essential_ratio), 2)

    # Update merchant running average
    updated_merchant_ratio = essential_ratio
    auto_applied = 0
    merchant = normalize_merchant_name(transaction.merchant_name)
    if merchant:
        # Get user_id from the transaction's account chain
        account = transaction.plaid_account
        if account:
            plaid_item = account.plaid_item
            if plaid_item:
                user_id = plaid_item.user_id

                mc = MerchantClassification.query.filter_by(
                    user_id=user_id,
                    merchant_name=merchant
                ).first()

                if mc:
                    # Running average: new_avg = ((old_avg * count) + new_ratio) / (count + 1)
                    new_count = mc.classification_count + 1
                    mc.essential_ratio = round(((mc.essential_ratio * mc.classification_count) + essential_ratio) / new_count, 4)
                    mc.classification_count = new_count
                    mc.classification = sub_category
                    mc.confidence = 'user_set'
                    updated_merchant_ratio = mc.essential_ratio
                else:
                    mc = MerchantClassification(
                        user_id=user_id,
                        merchant_name=merchant,
                        classification=sub_category,
                        essential_ratio=essential_ratio,
                        confidence='user_set',
                        classification_count=1
                    )
                    db.session.add(mc)
                    db.session.flush()

                # Auto-apply: if threshold reached, classify all remaining unclassified from this merchant
                if mc.classification_count >= CONFIDENCE_THRESHOLD and mc.confidence == 'user_set':
                    auto_applied = retroactively_reclassify(user_id, merchant, mc.classification, mc.essential_ratio)
                    # Restore this transaction's exact user-set ratio (not the running average)
                    transaction.essential_amount = round(amount * essential_ratio, 2)
                    transaction.discretionary_amount = round(amount * (1.0 - essential_ratio), 2)

    db.session.commit()

    return jsonify({
        "success": True,
        "transaction": {
            "id": transaction.id,
            "subCategory": transaction.sub_category,
            "essentialAmount": transaction.essential_amount,
            "discretionaryAmount": transaction.discretionary_amount
        },
        "updatedMerchantRatio": updated_merchant_ratio,
        "autoApplied": auto_applied
    })


@app.route("/merchant/classifications/<int:user_id>", methods=["GET"])
def get_merchant_classifications(user_id):
    """Get all merchant classifications for a user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    classifications = MerchantClassification.query.filter_by(user_id=user_id).all()

    return jsonify({
        "classifications": [
            {
                "merchantName": mc.merchant_name,
                "classification": mc.classification,
                "essentialRatio": mc.essential_ratio,
                "confidence": mc.confidence,
                "classificationCount": mc.classification_count
            }
            for mc in classifications
        ]
    })


@app.route("/expenses/unclassified/<int:user_id>", methods=["GET"])
def get_unclassified_transactions(user_id):
    """Get individual unclassified transactions sorted by merchant impact, round-robin."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    limit = request.args.get("limit", 10, type=int)

    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if not account_ids:
        return jsonify({"transactions": [], "totalUnclassified": 0})

    # Get all unclassified transactions (expenses only)
    unclassified = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        ((Transaction.sub_category == 'unclassified') | (Transaction.sub_category.is_(None))),
        Transaction.amount > 0
    ).all()

    total_unclassified = len(unclassified)

    # Skip merchants where user has classification_count >= CONFIDENCE_THRESHOLD
    high_confidence_merchants = set()
    merchant_classifications = MerchantClassification.query.filter_by(user_id=user_id).all()
    for mc in merchant_classifications:
        if mc.classification_count >= CONFIDENCE_THRESHOLD and mc.confidence == 'user_set':
            high_confidence_merchants.add(mc.merchant_name)

    # Group by merchant
    merchant_txns = {}
    for txn in unclassified:
        name = normalize_merchant_name(txn.merchant_name)
        if name in high_confidence_merchants:
            continue
        if name not in merchant_txns:
            merchant_txns[name] = []
        merchant_txns[name].append(txn)

    # Sort merchants by total unclassified spend (highest first)
    sorted_merchants = sorted(
        merchant_txns.items(),
        key=lambda x: sum(t.amount for t in x[1]),
        reverse=True
    )

    # Within each merchant, sort by date descending
    for name, txns in sorted_merchants:
        txns.sort(key=lambda t: t.date or date.min, reverse=True)

    # Build merchant context for each merchant
    # Also count already-classified transactions per merchant
    merchant_context_data = {}
    all_transactions = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        Transaction.amount > 0
    ).all()

    for txn in all_transactions:
        name = normalize_merchant_name(txn.merchant_name)
        if not name:
            continue
        if name not in merchant_context_data:
            merchant_context_data[name] = {"totalSpent": 0, "classified": 0, "unclassified": 0}
        merchant_context_data[name]["totalSpent"] += txn.amount
        if txn.sub_category and txn.sub_category != 'unclassified':
            merchant_context_data[name]["classified"] += 1
        else:
            merchant_context_data[name]["unclassified"] += 1

    # Round-robin: take one transaction per merchant in order, repeat
    result_txns = []
    pointers = {name: 0 for name, _ in sorted_merchants}

    while len(result_txns) < limit:
        added_any = False
        for name, txns in sorted_merchants:
            if pointers[name] < len(txns) and len(result_txns) < limit:
                txn = txns[pointers[name]]
                pointers[name] += 1
                added_any = True

                ctx = merchant_context_data.get(name, {})
                result_txns.append({
                    "id": txn.id,
                    "transactionId": txn.transaction_id,
                    "merchantName": txn.merchant_name,
                    "amount": txn.amount,
                    "date": txn.date.isoformat() if txn.date else None,
                    "name": txn.name,
                    "merchantContext": {
                        "totalUnclassified": ctx.get("unclassified", 0),
                        "totalSpent": round(ctx.get("totalSpent", 0), 2),
                        "alreadyClassified": ctx.get("classified", 0)
                    }
                })
        if not added_any:
            break

    return jsonify({
        "transactions": result_txns,
        "totalUnclassified": total_unclassified
    })


@app.route("/expenses/auto-classify/<int:user_id>", methods=["POST"])
def auto_classify_with_llm(user_id):
    """
    Trigger LLM-based batch classification for unclassified merchants.
    Classifies up to 20 merchants at once using AI inference.
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plaid_items = PlaidItem.query.filter_by(user_id=user_id).all()
    account_ids = []
    for item in plaid_items:
        for account in item.accounts:
            account_ids.append(account.id)

    if not account_ids:
        return jsonify({"classified": 0, "merchants": []})

    # Get unclassified transactions grouped by merchant
    unclassified = Transaction.query.filter(
        Transaction.plaid_account_id.in_(account_ids),
        ((Transaction.sub_category == 'unclassified') | (Transaction.sub_category.is_(None))),
        Transaction.merchant_name.isnot(None),
        Transaction.amount > 0
    ).all()

    merchant_info = {}
    for txn in unclassified:
        name = normalize_merchant_name(txn.merchant_name)
        if not name or name in merchant_info:
            continue
        merchant_info[name] = {
            "name": txn.merchant_name,
            "category_primary": txn.category_primary,
            "category_detailed": txn.category_detailed
        }

    if not merchant_info:
        return jsonify({"classified": 0, "merchants": []})

    # Batch classify via LLM
    merchants_to_classify = list(merchant_info.values())[:20]
    results = llm_classify_merchants_batch(merchants_to_classify, user_id)

    classified_count = 0
    classified_merchants = []

    for result in results:
        merchant_name = result.get("name", "")
        classification = result["classification"]
        essential_ratio = result["essential_ratio"]
        normalized = normalize_merchant_name(merchant_name)

        if not normalized:
            continue

        # Store the classification
        existing = MerchantClassification.query.filter_by(
            user_id=user_id, merchant_name=normalized
        ).first()

        if not existing:
            mc = MerchantClassification(
                user_id=user_id,
                merchant_name=normalized,
                classification=classification,
                essential_ratio=essential_ratio,
                confidence='inferred',
                classification_count=1
            )
            db.session.add(mc)

        # Retroactively classify transactions
        count = retroactively_reclassify(user_id, merchant_name, classification, essential_ratio)
        classified_count += count
        classified_merchants.append({
            "merchantName": merchant_name,
            "classification": classification,
            "essentialRatio": essential_ratio,
            "transactionsUpdated": count
        })

    db.session.commit()

    return jsonify({
        "classified": classified_count,
        "merchants": classified_merchants
    })


# =============================================================================
# Push Notifications & Webhooks
# =============================================================================

@app.route("/device/register", methods=["POST"])
def register_device_token():
    """
    Register a device token for push notifications.

    Expected body:
    {
        "userId": 1,
        "token": "abc123...",
        "platform": "ios"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    token = data.get("token", "").strip()
    platform = data.get("platform", "ios")

    if not user_id or not token:
        return jsonify({"error": "userId and token are required"}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Upsert device token
    existing = DeviceToken.query.filter_by(user_id=user_id, token=token).first()
    if existing:
        existing.is_active = True
        existing.platform = platform
    else:
        device = DeviceToken(
            user_id=user_id,
            token=token,
            platform=platform,
            is_active=True
        )
        db.session.add(device)

    db.session.commit()
    return jsonify({"success": True})


@app.route("/device/unregister", methods=["POST"])
def unregister_device_token():
    """Unregister a device token (e.g., on logout)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    token = data.get("token", "").strip()

    if not user_id or not token:
        return jsonify({"error": "userId and token are required"}), 400

    existing = DeviceToken.query.filter_by(user_id=user_id, token=token).first()
    if existing:
        existing.is_active = False
        db.session.commit()

    return jsonify({"success": True})


@app.route("/plaid/webhook", methods=["POST"])
def plaid_webhook():
    """
    Handle Plaid webhook events.
    Plaid sends webhooks for transaction updates, item errors, etc.

    Key webhook types:
    - TRANSACTIONS: DEFAULT_UPDATE, SYNC_UPDATES_AVAILABLE
    - ITEM: ERROR, PENDING_EXPIRATION
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    webhook_type = data.get("webhook_type")
    webhook_code = data.get("webhook_code")
    item_id = data.get("item_id")

    print(f"[WEBHOOK] type={webhook_type}, code={webhook_code}, item_id={item_id}")

    if webhook_type == "TRANSACTIONS":
        if webhook_code in ("DEFAULT_UPDATE", "SYNC_UPDATES_AVAILABLE"):
            # Find the PlaidItem by item_id
            plaid_item = PlaidItem.query.filter_by(item_id=item_id).first()
            if not plaid_item:
                print(f"[WEBHOOK] Unknown item_id: {item_id}")
                return jsonify({"received": True}), 200

            user_id = plaid_item.user_id

            try:
                # Sync new transactions
                account_map = {acc.account_id: acc for acc in plaid_item.accounts}
                has_more = True
                cursor = plaid_item.transactions_cursor
                new_transactions = []

                while has_more:
                    result = plaid_service.sync_transactions(
                        plaid_item.access_token_encrypted,
                        cursor
                    )

                    for txn_data in result["added"]:
                        account = account_map.get(txn_data["account_id"])
                        if account:
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
                                classify_transaction(transaction, user_id)
                                new_transactions.append(transaction)

                    # Handle modified transactions
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
                            classify_transaction(existing, user_id)

                    # Handle removed transactions
                    for removed in result["removed"]:
                        existing = Transaction.query.filter_by(
                            transaction_id=removed["transaction_id"]
                        ).first()
                        if existing:
                            db.session.delete(existing)

                    cursor = result["next_cursor"]
                    has_more = result["has_more"]

                plaid_item.transactions_cursor = cursor
                db.session.commit()

                # Send push notification for new transactions
                if new_transactions:
                    notify_new_transactions(user_id, new_transactions)

                    # Check if any are unclassified and prompt
                    for txn in new_transactions:
                        if txn.sub_category == 'unclassified' and txn.merchant_name:
                            notify_classification_needed(user_id, txn.merchant_name, abs(txn.amount))
                            break  # Only one prompt at a time

                print(f"[WEBHOOK] Synced {len(new_transactions)} new transactions for user {user_id}")

            except Exception as e:
                print(f"[WEBHOOK] Error processing transactions: {e}")
                db.session.rollback()

        elif webhook_code == "INITIAL_UPDATE":
            print(f"[WEBHOOK] Initial historical update for item {item_id}")

    elif webhook_type == "ITEM":
        if webhook_code == "ERROR":
            error = data.get("error", {})
            print(f"[WEBHOOK] Item error for {item_id}: {error}")
            plaid_item = PlaidItem.query.filter_by(item_id=item_id).first()
            if plaid_item:
                plaid_item.status = "error"
                db.session.commit()

        elif webhook_code == "PENDING_EXPIRATION":
            print(f"[WEBHOOK] Item pending expiration: {item_id}")
            plaid_item = PlaidItem.query.filter_by(item_id=item_id).first()
            if plaid_item:
                plaid_item.status = "pending_expiration"
                db.session.commit()

    return jsonify({"received": True}), 200


if __name__ == "__main__":
    # host='0.0.0.0' allows connections from physical devices on the same network
    app.run(debug=True, host='0.0.0.0', port=5000)
