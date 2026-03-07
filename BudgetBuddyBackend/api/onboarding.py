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
    weekly_spending_limit = data.get("weeklySpendingLimit", 0)
    try:
        weekly_spending_limit = float(weekly_spending_limit)
    except (TypeError, ValueError):
        weekly_spending_limit = 0
    strictness_level = data.get("strictnessLevel", "moderate")
    school = data.get("school", "").strip() or None

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if name:
        update_user(user_id, name=name)

    profile_kwargs = dict(
        is_student=is_student,
        weekly_spending_limit=weekly_spending_limit,
        strictness_level=strictness_level,
    )
    if school:
        profile_kwargs["school"] = school

    upsert_profile(user_id, **profile_kwargs)

    return jsonify({"status": "success"})
