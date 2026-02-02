from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from db_models import db, User, FinancialProfile
from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement

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
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"]}})


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
    Save user's financial profile from onboarding.

    Expected request body:
    {
        "userId": 1,
        "income": 5000.0,
        "expenses": 2000.0,
        "goalName": "Car",
        "goalTarget": 10000.0
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
    income = data.get("income", 0.0)
    expenses = data.get("expenses", 0.0)
    goal_name = data.get("goalName", "")
    goal_target = data.get("goalTarget", 0.0)

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check if profile already exists
    if user.profile:
        # Update existing profile
        user.profile.monthly_income = income
        user.profile.fixed_expenses = expenses
        user.profile.savings_goal_name = goal_name
        user.profile.savings_goal_target = goal_target
    else:
        # Create new profile
        profile = FinancialProfile(
            user_id=user_id,
            monthly_income=income,
            fixed_expenses=expenses,
            savings_goal_name=goal_name,
            savings_goal_target=goal_target
        )
        db.session.add(profile)

    db.session.commit()

    return jsonify({"status": "success"})


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

    Expected: multipart/form-data with 'file' field

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

    # Read file content
    file_content = file.read()
    filename = file.filename

    # Analyze the statement
    response = analyze_statement(file_content, filename)

    return jsonify(response.to_dict())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
