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

    Each uploaded song has its own analysis — no hardcoded demo.
    """
    # Re-use the model-level get_or_create_session which properly inserts
    # into the sessions table, so the upload route will recognise the same sid.
    sid = get_or_create_session()
    is_new = request.cookies.get("melodyx_sid") is None

    # Optionally load a specific analysis if passed as query param
    req_aid = request.args.get("analysis_id", "")

    resp = make_response(render_template(
        "index.html",
        session_id=sid,
        default_analysis_id=req_aid,
    ))

    if is_new:
        resp.set_cookie(
            "melodyx_sid",
            sid,
            max_age=86400 * 30,
            httponly=False,
            samesite="Lax",
        )

    return resp
