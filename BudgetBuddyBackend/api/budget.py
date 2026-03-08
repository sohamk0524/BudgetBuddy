"""
Budget Blueprint — generate and retrieve spending plans.
"""

import json

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import get_user, get_latest_plan
from services.plan_generator import generate_plan, save_plan_to_db

budget_bp = Blueprint('budget', __name__)


@budget_bp.route("/generate-plan", methods=["POST"])
@require_auth
def generate_spending_plan():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    deep_dive_data = data.get("deepDiveData", {})

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    result = generate_plan(user_id, deep_dive_data)

    if result.get("plan"):
        save_plan_to_db(user_id, result["plan"])

    return jsonify(result)


@budget_bp.route("/get-plan/<user_id>", methods=["GET"])
@require_auth
def get_user_plan(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    plan_record = get_latest_plan(user_id)
    if not plan_record:
        return jsonify({"hasPlan": False, "plan": None})

    plan_data = json.loads(plan_record['plan_json'])
    created_at = plan_record.get('created_at')

    return jsonify({
        "hasPlan": True,
        "plan": plan_data,
        "createdAt": created_at.isoformat() if created_at else None,
        "monthYear": plan_record.get('month_year'),
    })
