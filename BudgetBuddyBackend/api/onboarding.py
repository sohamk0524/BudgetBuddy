"""
Onboarding Blueprint — saves user profile from the 4-Question Protocol.
"""

from flask import Blueprint, jsonify, request

from db_models import get_user, update_user, get_profile, upsert_profile

onboarding_bp = Blueprint('onboarding', __name__)


@onboarding_bp.route("/onboarding", methods=["POST"])
def onboarding():
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

    user = get_user(int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404

    if name:
        update_user(int(user_id), name=name)

    upsert_profile(
        int(user_id),
        is_student=is_student,
        budgeting_goal=budgeting_goal,
        strictness_level=strictness_level,
    )

    return jsonify({"status": "success"})
