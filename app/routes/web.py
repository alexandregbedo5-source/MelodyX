"""MELODYX public pages and interactive sheet music studio."""

from flask import Blueprint, abort, current_app, make_response, render_template, request

from app.models.analysis import get_analyses_for_session, get_or_create_session
from app.services.billing import PLAN_CATALOG, get_billing_status
from app.models.policies import POLICY_VERSION, get_policy_acceptance, has_policy_acceptance
from app.services.policies import POLICY_DOCUMENTS

web_bp = Blueprint("web", __name__)


def _page_response(template: str, session_id: str, **context):
    response = make_response(render_template(
        template,
        session_id=session_id,
        billing=get_billing_status(session_id),
        active_page=context.pop("active_page", "home"),
        **context,
    ))
    response.set_cookie(
        "melodyx_sid",
        session_id,
        max_age=86400 * 30,
        httponly=False,
        samesite="Lax",
    )
    return response


def _page_session() -> str:
    return request.args.get("session_id") or get_or_create_session()


@web_bp.route("/", methods=["GET"])
def index():
    return _page_response("home.html", _page_session(), active_page="home")


@web_bp.route("/studio", methods=["GET"])
def studio():
    session_id = _page_session()
    policy_acceptance = get_policy_acceptance(session_id)
    instrument = request.args.get("instrument", "conductor").lower()
    if instrument not in ("conductor", "piano", "lead", "bass"):
        instrument = "conductor"
    return _page_response(
        "index.html",
        session_id,
        active_page="studio",
        default_analysis_id=request.args.get("analysis_id", ""),
        default_instrument=instrument,
        policy_version=POLICY_VERSION,
        policy_acceptance=policy_acceptance,
        policies_accepted=has_policy_acceptance(session_id),
    )


@web_bp.route("/library", methods=["GET"])
def library():
    session_id = _page_session()
    return _page_response(
        "library.html",
        session_id,
        active_page="library",
        analyses=get_analyses_for_session(session_id),
    )


@web_bp.route("/pricing", methods=["GET"])
def pricing():
    return _page_response(
        "pricing.html",
        _page_session(),
        active_page="pricing",
        plans=list(PLAN_CATALOG.values()),
        reason=request.args.get("reason", ""),
        payment_success=request.args.get("payment") == "success",
    )


@web_bp.route("/checkout/<plan_id>", methods=["GET"])
def checkout(plan_id: str):
    plan = PLAN_CATALOG.get(plan_id)
    if not plan or plan.get("free"):
        abort(404)
    return _page_response(
        "checkout.html",
        _page_session(),
        active_page="pricing",
        plan=plan,
    )


@web_bp.route("/policies/<policy_id>", methods=["GET"])
def policy(policy_id: str):
    document = POLICY_DOCUMENTS.get(policy_id)
    if not document:
        abort(404)
    document = dict(document)
    document["id"] = policy_id
    document["version"] = POLICY_VERSION
    document["contact_email"] = current_app.config.get("PRIVACY_CONTACT_EMAIL", "").strip()
    return _page_response(
        "policy.html",
        _page_session(),
        active_page="",
        policy=document,
    )
