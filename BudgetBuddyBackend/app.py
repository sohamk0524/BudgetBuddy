from flask import Flask, jsonify, request
from flask_cors import CORS

from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement

app = Flask(__name__)

# Enable CORS for iOS simulator to communicate with localhost
# Allow all origins and methods for development
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"]}})


@app.route("/")
def index():
    return jsonify({"message": "Welcome to BudgetBuddy API"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


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
    response = process_message(user_message)

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
