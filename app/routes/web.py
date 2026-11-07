"""MELODYX — Web Frontend & Sheet Music Studio Routes."""

from flask import (
    Blueprint,
    make_response,
    render_template,
    request,
)

from app.models.analysis import get_or_create_session

web_bp = Blueprint("web", __name__)


@web_bp.route("/", methods=["GET"])
def index():
    """Render the MELODYX Sheet Music Studio web application.

    Clean empty state by default — no hardcoded song or auto-loaded demo.
    """
    param_sid = request.args.get("session_id")
    sid = param_sid or get_or_create_session()

    # Only load an analysis if explicitly requested via query parameter
    req_aid = request.args.get("analysis_id", "")

    inst = request.args.get("instrument", "conductor").lower()
    if inst not in ("conductor", "piano", "lead", "bass"):
        inst = "conductor"

    resp = make_response(render_template(
        "index.html",
        session_id=sid,
        default_analysis_id=req_aid,
        default_instrument=inst,
    ))

    resp.set_cookie(
        "melodyx_sid",
        sid,
        max_age=86400 * 30,
        httponly=False,
        samesite="Lax",
    )

    return resp
