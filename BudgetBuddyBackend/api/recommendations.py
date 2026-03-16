"""
Recommendations Blueprint — cached AI-generated financial recommendations.
"""

import json

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import get_user, get_recommendation_prefs, upsert_recommendation_prefs
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
    search_query = data.get("searchQuery")

    # Allow builtin actions + any custom category the user has defined
    builtin_actions = {
        "general", "budget_balance", "spending_habits",
        "food", "drink", "groceries", "transportation", "entertainment", "other",
    }
    if action not in builtin_actions:
        # Check if it's a valid custom category for this user
        from services.classification_service import get_valid_categories_for_user
        user_cats = set(get_valid_categories_for_user(user_id))
        if action.lower() not in user_cats:
            action = "general"

    result = generate_recommendations(user_id, action=action, search_query=search_query)
    return jsonify(result)


@recommendations_bp.route("/recommendations/preferences/<user_id>", methods=["GET"])
@require_auth
def get_preferences(user_id):
    """Return the user's saved tips and disliked tip IDs."""
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    prefs = get_recommendation_prefs(user_id)
    if not prefs:
        return jsonify({"savedTips": [], "dislikedTipIds": [], "seenTipIds": []})

    try:
        saved_tips = json.loads(prefs.get("saved_tips_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        saved_tips = []
    try:
        disliked_tip_ids = json.loads(prefs.get("disliked_tip_ids_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        disliked_tip_ids = []
    try:
        seen_tips_raw = json.loads(prefs.get("seen_tip_ids_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        seen_tips_raw = []

    # Support both old format (string IDs) and new format (full objects)
    seen_tips = [r for r in seen_tips_raw if isinstance(r, dict)]
    seen_tip_ids = [r.get("category", "") + r.get("title", "") for r in seen_tips]
    # Include any legacy string IDs
    seen_tip_ids += [r for r in seen_tips_raw if isinstance(r, str)]

    return jsonify({
        "savedTips": saved_tips,
        "dislikedTipIds": disliked_tip_ids,
        "seenTipIds": seen_tip_ids,
        "seenTips": seen_tips,
    })


@recommendations_bp.route("/recommendations/save", methods=["POST"])
@require_auth
def save_recommendation():
    """Toggle save/unsave a recommendation."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    recommendation = data.get("recommendation")
    if not user_id or not recommendation:
        return jsonify({"error": "userId and recommendation are required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    tip_id = recommendation.get("category", "") + recommendation.get("title", "")

    prefs = get_recommendation_prefs(user_id)
    try:
        saved_tips = json.loads(prefs.get("saved_tips_json", "[]")) if prefs else []
    except (json.JSONDecodeError, TypeError):
        saved_tips = []

    existing_ids = [r.get("category", "") + r.get("title", "") for r in saved_tips]

    if tip_id in existing_ids:
        saved_tips = [r for r in saved_tips if (r.get("category", "") + r.get("title", "")) != tip_id]
        saved = False
    else:
        saved_tips.append(recommendation)
        saved = True

    upsert_recommendation_prefs(user_id, saved_tips_json=json.dumps(saved_tips))
    return jsonify({"saved": saved})


@recommendations_bp.route("/recommendations/dislike", methods=["POST"])
@require_auth
def dislike_recommendation():
    """Dislike a recommendation (removes from saved if present)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    tip_id = data.get("tipId")
    if not user_id or not tip_id:
        return jsonify({"error": "userId and tipId are required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    prefs = get_recommendation_prefs(user_id)
    try:
        disliked_ids = json.loads(prefs.get("disliked_tip_ids_json", "[]")) if prefs else []
    except (json.JSONDecodeError, TypeError):
        disliked_ids = []
    try:
        saved_tips = json.loads(prefs.get("saved_tips_json", "[]")) if prefs else []
    except (json.JSONDecodeError, TypeError):
        saved_tips = []

    if tip_id not in disliked_ids:
        disliked_ids.append(tip_id)

    # Also remove from saved and seen if present (mutual exclusivity)
    saved_tips = [r for r in saved_tips if (r.get("category", "") + r.get("title", "")) != tip_id]

    try:
        seen_tips = json.loads(prefs.get("seen_tip_ids_json", "[]")) if prefs else []
    except (json.JSONDecodeError, TypeError):
        seen_tips = []
    seen_tips = [r for r in seen_tips if isinstance(r, dict) and (r.get("category", "") + r.get("title", "")) != tip_id]

    upsert_recommendation_prefs(
        user_id,
        saved_tips_json=json.dumps(saved_tips),
        disliked_tip_ids_json=json.dumps(disliked_ids),
        seen_tip_ids_json=json.dumps(seen_tips),
    )
    return jsonify({"disliked": True})


@recommendations_bp.route("/recommendations/seen", methods=["POST"])
@require_auth
def mark_already_seen():
    """Mark a recommendation as used/already seen (hides it but doesn't negatively signal)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_id = data.get("userId")
    recommendation = data.get("recommendation")
    if not user_id or not recommendation:
        return jsonify({"error": "userId and recommendation are required"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    tip_id = recommendation.get("category", "") + recommendation.get("title", "")

    prefs = get_recommendation_prefs(user_id)
    try:
        seen_tips = json.loads(prefs.get("seen_tip_ids_json", "[]")) if prefs else []
    except (json.JSONDecodeError, TypeError):
        seen_tips = []

    # Handle migration: filter out any old-format string IDs
    seen_tips = [r for r in seen_tips if isinstance(r, dict)]

    existing_ids = [r.get("category", "") + r.get("title", "") for r in seen_tips]
    if tip_id not in existing_ids:
        seen_tips.append(recommendation)

    upsert_recommendation_prefs(user_id, seen_tip_ids_json=json.dumps(seen_tips))
    return jsonify({"seen": True})
