import json
import random
import string
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

from db_models import db, User, FinancialProfile, BudgetPlan, SavedStatement, OTPCode
from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement
from services.plan_generator import generate_plan, save_plan_to_db

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
        "hasProfile": user.profile is not None
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


if __name__ == "__main__":
    # host='0.0.0.0' allows connections from physical devices on the same network
    app.run(debug=True, host='0.0.0.0', port=5000)
