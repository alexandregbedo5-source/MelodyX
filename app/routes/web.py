"""MELODYX — Web Frontend & Sheet Music Studio Routes."""

import json
import os
import uuid
from pathlib import Path
from typing import Optional

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    send_file,
)

from app.extensions import get_db
from app.models.analysis import get_analysis

web_bp = Blueprint("web", __name__)

DEMO_ANALYSIS_ID = "an_9b2673209489"


def _ensure_session_id():
    """Get or generate a session ID."""
    sid = request.cookies.get("melodyx_sid")
    is_new = False
    if not sid:
        sid = uuid.uuid4().hex
        is_new = True
    return sid, is_new


@web_bp.route("/", methods=["GET"])
def index():
    """Render the MELODYX Sheet Music Studio web application."""
    sid, is_new = _ensure_session_id()
    
    # Check if there is a requested analysis_id
    req_aid = request.args.get("analysis_id", "")
    if not req_aid and request.args.get("demo") == "1":
        req_aid = DEMO_ANALYSIS_ID

    resp = make_response(render_template(
        "index.html",
        session_id=sid,
        default_analysis_id=req_aid or DEMO_ANALYSIS_ID,
        demo_analysis_id=DEMO_ANALYSIS_ID,
    ))

    if is_new:
        resp.set_cookie("melodyx_sid", sid, max_age=86400 * 30, httponly=False, samesite="Lax")

    return resp


@web_bp.route("/demo", methods=["GET"])
def demo_redirect():
    """Redirect to the demo sheet music view."""
    sid, is_new = _ensure_session_id()
    resp = make_response(render_template(
        "index.html",
        session_id=sid,
        default_analysis_id=DEMO_ANALYSIS_ID,
        demo_analysis_id=DEMO_ANALYSIS_ID,
    ))
    if is_new:
        resp.set_cookie("melodyx_sid", sid, max_age=86400 * 30, httponly=False, samesite="Lax")
    return resp


@web_bp.route("/api/demo/analysis", methods=["GET"])
def demo_analysis():
    """Return the demo song analysis JSON regardless of session."""
    db = get_db()
    row = db.execute(
        """
        SELECT a.*, ar.result_json
        FROM analyses a
        LEFT JOIN analysis_results ar ON a.id = ar.analysis_id
        WHERE a.id = ?
        """,
        (DEMO_ANALYSIS_ID,),
    ).fetchone()

    if not row:
        return jsonify({"error": {"code": "not_found", "message": "Demo analysis not found."}}), 404

    data = dict(row)
    if data.get("result_json"):
        try:
            data["result"] = json.loads(data["result_json"])
        except Exception:
            data["result"] = None

    return jsonify(data), 200


def _get_demo_dir() -> Path:
    """Return the absolute path to the demo files directory."""
    return Path(current_app.root_path).parent / "uploads" / "an_f30ad38e60cd"


@web_bp.route("/api/demo/score", methods=["GET"])
def demo_score():
    """Serve the MusicXML file for the demo song."""
    xml_path = _get_demo_dir() / "an_9b2673209489.musicxml"
    if not xml_path.is_file():
        return jsonify({"error": {"code": "not_found", "message": "Demo score file not found."}}), 404

    return send_file(
        str(xml_path),
        mimetype="application/vnd.recordare.musicxml+xml",
        as_attachment=False,
    )


@web_bp.route("/api/demo/pdf", methods=["GET"])
def demo_pdf():
    """Serve the PDF partition for the demo song."""
    pdf_path = _get_demo_dir() / "an_9b2673209489_partition.pdf"
    if not pdf_path.is_file():
        db = get_db()
        row = db.execute(
            "SELECT result_json FROM analysis_results WHERE analysis_id = ?",
            (DEMO_ANALYSIS_ID,),
        ).fetchone()
        if row and row["result_json"]:
            try:
                from app.services.pdf_generator import generate_sheet_music_pdf
                res = json.loads(row["result_json"])
                generate_sheet_music_pdf(res, str(pdf_path), title="Chanson d'Opéra & Ensemble")
            except Exception as e:
                current_app.logger.exception("Failed to generate demo PDF: %s", e)

    if not pdf_path.is_file():
        return jsonify({"error": {"code": "not_found", "message": "Demo PDF file not found."}}), 404

    is_inline = request.args.get("inline") == "1"
    return send_file(
        str(pdf_path),
        mimetype="application/pdf",
        as_attachment=not is_inline,
        download_name="chanson_opera_partition.pdf",
    )


@web_bp.route("/api/demo/midi", methods=["GET"])
def demo_midi():
    """Serve the MIDI file for the demo song."""
    mid_path = _get_demo_dir() / "an_9b2673209489.mid"
    if not mid_path.is_file():
        return jsonify({"error": {"code": "not_found", "message": "Demo MIDI file not found."}}), 404

    return send_file(
        str(mid_path),
        mimetype="audio/midi",
        as_attachment=True,
        download_name="chanson_opera.mid",
    )


@web_bp.route("/api/demo/audio", methods=["GET"])
def demo_audio():
    """Serve the audio file for the demo song supporting HTTP Range requests."""
    demo_dir = _get_demo_dir()
    audio_path = demo_dir / "ec474a97350a84cd_converted.wav"
    if not audio_path.is_file():
        audio_path = demo_dir / "ec474a97350a84cd.m4a"
    if not audio_path.is_file():
        return jsonify({"error": {"code": "not_found", "message": "Demo audio file not found."}}), 404

    mimetype = "audio/wav" if str(audio_path).endswith(".wav") else "audio/mp4"
    return send_file(
        str(audio_path),
        mimetype=mimetype,
        conditional=True,
        as_attachment=False,
    )
