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
    param_sid = request.args.get("session_id")
    sid = param_sid or get_or_create_session()

    # Optionally load a specific analysis if passed as query param, or latest for this session
    req_aid = request.args.get("analysis_id", "")
    if not req_aid:
        try:
            from app.extensions import get_db
            db = get_db()
            row = db.execute(
                "SELECT id FROM analyses WHERE session_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
                (sid,),
            ).fetchone()
            if row:
                req_aid = row["id"]
            else:
                # If current session has no completed analyses yet, link latest completed
                latest = db.execute(
                    "SELECT id FROM analyses WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if latest:
                    req_aid = latest["id"]
                    db.execute(
                        "UPDATE analyses SET session_id = ? WHERE id = ?",
                        (sid, req_aid),
                    )
                    db.commit()
        except Exception:
            pass

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
