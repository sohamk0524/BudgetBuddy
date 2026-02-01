from flask import Flask, jsonify, request
from flask_cors import CORS

from services.orchestrator import process_message

app = Flask(__name__)

# Enable CORS for iOS simulator to communicate with localhost
CORS(app)


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
