"""MELODYX quota and simulated checkout API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.models.analysis import get_or_create_session
from app.models.billing import activate_simulated_subscription
from app.services.billing import (
    PAYMENT_PROVIDERS,
    PLAN_CATALOG,
    get_billing_status,
)

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")


def _session_id() -> str:
    return request.cookies.get("melodyx_sid") or request.args.get("session_id") or get_or_create_session()


@billing_bp.route("/status", methods=["GET"])
def billing_status_route():
    return jsonify(get_billing_status(_session_id())), 200


@billing_bp.route("/simulate", methods=["POST"])
def simulate_payment_route():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": {"code": "invalid_request", "message": "Un objet JSON est requis."}}), 400

    plan_id = body.get("plan_id")
    provider = body.get("provider")
    plan = PLAN_CATALOG.get(plan_id) if isinstance(plan_id, str) else None
    if not plan or plan.get("free"):
        return jsonify({"error": {"code": "invalid_plan", "message": "Choisis une offre payante valide."}}), 400
    if not isinstance(provider, str) or provider not in PAYMENT_PROVIDERS:
        return jsonify({"error": {"code": "invalid_provider", "message": "Choisis un moyen de paiement proposé."}}), 400

    session_id = _session_id()
    subscription = activate_simulated_subscription(
        session_id, plan_id, int(plan["price_fcfa"]), provider
    )
    status = get_billing_status(session_id)
    return jsonify({
        "simulated": True,
        "message": "Paiement simulé confirmé. Aucun débit réel n’a été effectué.",
        "subscription": subscription,
        "billing": status,
    }), 201
