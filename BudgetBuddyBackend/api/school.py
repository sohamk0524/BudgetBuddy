"""
School Blueprint — School-specific RAG advice endpoint.
"""

from flask import Blueprint, jsonify, request

from middleware.auth import require_auth
from db_models import get_profile
from services.school_rag import get_school_advice

school_bp = Blueprint('school', __name__)


@school_bp.route("/api/school-advice", methods=["POST"])
@require_auth
def school_advice():
    """
    Get AI-synthesized, school-specific financial advice via web search (RAG).

    Expected request body:
    {
        "query": "cheap coffee near campus",
        "user_id": 1,
        "school_name": "uc_davis"  (optional — falls back to user's profile)
    }

    Returns:
    {
        "answer": "markdown string...",
        "sources": [{"title": "...", "url": "..."}]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    query = data.get("query")
    user_id = data.get("user_id")

    if not query:
        return jsonify({"error": "query is required"}), 400
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id must be an integer"}), 400

    school_name = data.get("school_name")

    # If no school_name provided, look it up from the user's profile
    if not school_name:
        profile = get_profile(user_id_int)
        if profile and profile.get("school"):
            school_name = profile["school"]
        else:
            return jsonify({"error": "No school found. Provide school_name or complete onboarding."}), 400

    result = get_school_advice(query, school_name)

    if "error" in result:
        return jsonify(result), 500

    return jsonify(result)
