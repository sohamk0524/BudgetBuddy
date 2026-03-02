"""
BudgetBuddy Backend — Google App Engine entry point.

Gunicorn targets this file: gunicorn -b :$PORT main:app
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

if os.environ.get("USE_LOCAL_DB", "").lower() in ("1", "true", "yes"):
    print("[DB] Using LOCAL Datastore emulator (localhost:8081)")
else:
    print("[DB] Using CLOUD Datastore")

from api.auth import auth_bp
from api.onboarding import onboarding_bp
from api.budget import budget_bp
from api.chat import chat_bp
from api.user import user_bp
from api.plaid import plaid_bp
from api.expenses import expenses_bp
from api.recommendations import recommendations_bp
from api.school import school_bp
from api.receipt import receipt_bp

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})

app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(user_bp)
app.register_blueprint(plaid_bp)
app.register_blueprint(expenses_bp)
app.register_blueprint(recommendations_bp)
app.register_blueprint(school_bp)
app.register_blueprint(receipt_bp)


@app.route("/")
def index():
    return jsonify({"message": "Welcome to BudgetBuddy API"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
