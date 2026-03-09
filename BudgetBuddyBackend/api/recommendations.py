"""
Recommendations Blueprint — cached AI-generated financial recommendations.
"""

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import get_user
from services.recommendations_generator import get_cached_or_generate, generate_recommendations

recommendations_bp = Blueprint('recommendations', __name__)


@recommendations_bp.route("/recommendations/<user_id>", methods=["GET"])
@require_auth
def get_recommendations(user_id):
    """Return cached recommendations if fresh, otherwise generate new ones."""
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    result = get_cached_or_generate(user_id)
    return jsonify(result)


@recommendations_bp.route("/recommendations/generate", methods=["POST"])
@require_auth
def generate_fresh_recommendations():
    """Force-generate fresh recommendations."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    action = data.get("action", "general")
    valid_actions = (
        "general", "budget_balance", "spending_habits",
        "food", "drink", "groceries", "transportation", "entertainment", "other",
    )
    if action not in valid_actions:
        action = "general"

    result = generate_recommendations(user_id, action=action)
    return jsonify(result)
