"""Published policies and explicit user choices for optional AI processing."""

from flask import Blueprint, jsonify, request

from app.models.analysis import get_or_create_session
from app.models.policies import (
    POLICY_VERSION,
    has_policy_acceptance,
    record_policy_acceptance,
    update_gemini_opt_in,
)

policies_api_bp = Blueprint("policies_api", __name__, url_prefix="/api/policies")


def _with_session_cookie(response, session_id: str):
    response.set_cookie(
        "melodyx_sid",
        session_id,
        httponly=False,
        samesite="Lax",
        max_age=86400 * 30,
    )
    return response


@policies_api_bp.route("/consent", methods=["POST"])
def accept_policies():
    """Record the three required acknowledgements for the current policy version."""
    session_id = get_or_create_session()
    body = request.get_json(silent=True) or {}

    if body.get("policy_version") != POLICY_VERSION:
        return _with_session_cookie(jsonify({
            "error": {
                "code": "policy_version_mismatch",
                "message": "Les documents ont changé. Relis les versions actuelles avant de continuer.",
                "policy_version": POLICY_VERSION,
            },
        }), session_id), 409

    required = ("privacy_accepted", "copyright_accepted", "plagiarism_accepted")
    if not all(body.get(field) is True for field in required):
        return _with_session_cookie(jsonify({
            "error": {
                "code": "policy_acceptance_required",
                "message": "Lis et accepte chacun des trois documents pour importer un morceau.",
            },
        }), session_id), 400

    receipt = record_policy_acceptance(
        session_id,
        privacy_accepted=True,
        copyright_accepted=True,
        plagiarism_accepted=True,
        gemini_opt_in=body.get("gemini_opt_in") is True,
    )
    return _with_session_cookie(jsonify({"accepted": True, **receipt}), session_id), 200


@policies_api_bp.route("/ai-consent", methods=["POST"])
def update_ai_consent():
    """Enable or disable optional sharing of extracted music data with Gemini."""
    session_id = get_or_create_session()
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        return _with_session_cookie(jsonify({
            "error": {
                "code": "invalid_request",
                "message": "Le choix Gemini doit être activé ou désactivé explicitement.",
            },
        }), session_id), 400

    if not update_gemini_opt_in(session_id, enabled):
        return _with_session_cookie(jsonify({
            "error": {
                "code": "policy_consent_required",
                "message": "Accepte d’abord les trois documents avant de modifier le choix Gemini.",
                "policies_url": "/policies/privacy",
            },
        }), session_id), 428

    return _with_session_cookie(jsonify({"gemini_opt_in": enabled}), session_id), 200

