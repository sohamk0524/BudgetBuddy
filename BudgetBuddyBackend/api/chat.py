"""
Chat Blueprint — AI chat and bank statement upload.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import get_user, get_statement, upsert_statement, delete_statement_for_user
from services.orchestrator import process_message
from services.statement_analyzer import analyze_statement
from services.gcs_service import upload_statement as gcs_upload, delete_statement as gcs_delete

chat_bp = Blueprint('chat', __name__)


@chat_bp.route("/chat", methods=["POST"])
@require_auth
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_message = data.get("message", "")
    user_id = data.get("userId", "anonymous")

    if not user_message:
        return jsonify({"error": "Message field is required"}), 400

    response = process_message(user_message, user_id)
    return jsonify(response.to_dict())


@chat_bp.route("/upload-statement", methods=["POST", "OPTIONS"])
@require_auth
def upload_statement():
    if request.method == "OPTIONS":
        return "", 200

    print(f"Upload request received. Files: {list(request.files.keys())}")
    print(f"Content-Type: {request.content_type}")

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    print(f"Received file: {file.filename}")

    user_id = request.form.get("userId") or None

    file_content = file.read()
    filename = file.filename
    file_type = "pdf" if filename.lower().endswith(".pdf") else "csv"

    response, llm_analysis = analyze_statement(file_content, filename, return_analysis=True)

    if user_id:
        user = get_user(user_id)
        if user:
            _save_statement(user_id, filename, file_type, file_content, llm_analysis)
            print(f"Statement saved for user {user_id}")

    return jsonify(response.to_dict())


def _save_statement(user_id: str, filename: str, file_type: str,
                    file_content: bytes, analysis: dict):
    """Upload file to GCS and upsert the SavedStatement entity in Datastore."""
    # Delete old GCS file if one exists
    existing = get_statement(user_id)
    if existing and existing.get('gcs_path'):
        try:
            gcs_delete(existing['gcs_path'])
        except Exception as e:
            print(f"Warning: failed to delete old GCS file: {e}")

    # Upload new file to GCS
    try:
        gcs_path = gcs_upload(user_id, filename, file_content)
    except Exception as e:
        print(f"Warning: GCS upload failed, storing path placeholder: {e}")
        gcs_path = f"statements/{user_id}/{filename}"

    # Extract metrics from analysis
    ending_balance = 0.0
    total_income = 0.0
    total_expenses = 0.0
    statement_start_date = None
    statement_end_date = None

    if analysis:
        total_income = float(analysis.get("total_income", 0) or 0)
        total_expenses = float(analysis.get("total_expenses", 0) or 0)
        ending_balance = float(analysis.get("ending_balance", 0) or 0)
        if ending_balance == 0:
            metadata = analysis.get("metadata", {})
            if isinstance(metadata, dict):
                ending_balance = float(metadata.get("ending_balance", 0) or 0)
        if ending_balance == 0 and (total_income > 0 or total_expenses > 0):
            ending_balance = total_income - total_expenses

        start_date_str = analysis.get("statement_start_date")
        end_date_str = analysis.get("statement_end_date")

        if start_date_str:
            try:
                statement_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date().isoformat()
            except (ValueError, TypeError):
                pass

        if end_date_str:
            try:
                statement_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date().isoformat()
            except (ValueError, TypeError):
                pass

        if not statement_start_date or not statement_end_date:
            transactions = analysis.get("transactions", [])
            if transactions and isinstance(transactions, list):
                dates = []
                for tx in transactions:
                    if isinstance(tx, dict) and tx.get("date"):
                        try:
                            dates.append(tx["date"])
                        except (ValueError, TypeError):
                            pass
                if dates:
                    dates.sort()
                    if not statement_start_date:
                        statement_start_date = dates[0]
                    if not statement_end_date:
                        statement_end_date = dates[-1]

    print(f"Saving statement: balance={ending_balance}, income={total_income}, expenses={total_expenses}")

    transactions = analysis.get("transactions", []) if analysis else []
    upsert_statement(
        user_id,
        filename=filename,
        file_type=file_type,
        gcs_path=gcs_path,
        parsed_data=json.dumps({"transactions": transactions}),
        llm_analysis=json.dumps(analysis) if analysis else "{}",
        ending_balance=ending_balance,
        total_income=total_income,
        total_expenses=total_expenses,
        statement_start_date=statement_start_date,
        statement_end_date=statement_end_date,
    )
