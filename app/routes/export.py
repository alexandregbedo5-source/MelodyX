"""MELODYX — Export endpoints for analysis artifacts (B8)."""

import json as _json
import os
from pathlib import Path
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, send_file

from app.extensions import get_db
from app.models.analysis import get_analysis, get_artifacts

export_bp = Blueprint("export", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_id() -> Optional[str]:
    """Return the session id from the request cookie, or *None*."""
    return request.cookies.get("melodyx_sid")


def _get_completed_analysis(analysis_id: str, session_id: str):
    """Return the analysis dict if it exists, belongs to the session, and is completed.

    Returns a tuple ``(analysis_dict | None, error_response | None)``.
    """
    analysis = get_analysis(analysis_id, session_id)

    if analysis is None:
        return None, (jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404)

    if analysis["status"] != "completed":
        return None, (
            jsonify({
                "error": {
                    "code": "invalid_request",
                    "message": "Analysis is not yet completed.",
                },
            }),
            400,
        )

    return analysis, None


def _find_artifact_path(analysis_id: str, session_id: str, artifact_type: str) -> Optional[str]:
    """Find the path to a specific artifact type from the artifacts table."""
    artifacts = get_artifacts(analysis_id, session_id)
    for art in artifacts:
        if art.get("artifact_type") == artifact_type:
            path = art.get("file_path", "")
            if path and os.path.isfile(path):
                return path
    return None


def _artifact_path_by_dir(analysis: dict, filename: str) -> Optional[str]:
    """Resolve the full path to an artifact file inside the analysis directory."""
    stored_path = analysis.get("stored_path", "")
    if not stored_path:
        return None
    analysis_dir = str(Path(stored_path).parent)
    artifact = os.path.join(analysis_dir, filename)
    if os.path.isfile(artifact):
        return artifact
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@export_bp.route("/analysis/<analysis_id>/score", methods=["GET"])
def export_score(analysis_id: str):
    """Serve the MusicXML score file for a completed analysis."""
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    analysis, err = _get_completed_analysis(analysis_id, sid)
    if err:
        return err

    # Try artifacts table first, then directory
    artifact = _find_artifact_path(analysis_id, sid, "musicxml")
    if artifact is None:
        artifact = _artifact_path_by_dir(analysis, f"{analysis_id}.musicxml")
    if artifact is None:
        return jsonify({"error": {"code": "not_found", "message": "Score file not found."}}), 404

    return send_file(
        artifact,
        mimetype="application/vnd.recordare.musicxml+xml",
        as_attachment=True,
        download_name=f"{analysis_id}_score.musicxml",
    )


@export_bp.route("/analysis/<analysis_id>/midi", methods=["GET"])
def export_midi(analysis_id: str):
    """Serve the MIDI file for a completed analysis."""
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    analysis, err = _get_completed_analysis(analysis_id, sid)
    if err:
        return err

    artifact = _find_artifact_path(analysis_id, sid, "midi")
    if artifact is None:
        artifact = _artifact_path_by_dir(analysis, f"{analysis_id}.mid")
    if artifact is None:
        return jsonify({"error": {"code": "not_found", "message": "MIDI file not found."}}), 404

    return send_file(
        artifact,
        mimetype="audio/midi",
        as_attachment=True,
        download_name=f"{analysis_id}.mid",
    )


@export_bp.route("/analysis/<analysis_id>/json", methods=["GET"])
def export_json(analysis_id: str):
    """Return the full analysis result as JSON."""
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    analysis, err = _get_completed_analysis(analysis_id, sid)
    if err:
        return err

    # Get result from the analysis object (already loaded by get_analysis)
    result = analysis.get("result")
    if result:
        return jsonify(result), 200

    # Fallback: fetch from analysis_results table
    db = get_db()
    row = db.execute(
        """
        SELECT result_json FROM analysis_results
        WHERE analysis_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (analysis_id,),
    ).fetchone()

    if row is None or row["result_json"] is None:
        return jsonify({"error": {"code": "not_found", "message": "Result JSON not found."}}), 404

    try:
        result = _json.loads(row["result_json"])
    except (_json.JSONDecodeError, TypeError):
        return jsonify({"error": {"code": "internal_error", "message": "Corrupt result data."}}), 500

    return jsonify(result), 200


@export_bp.route("/analysis/<analysis_id>/pdf", methods=["GET"])
def export_pdf(analysis_id: str):
    """PDF export — not yet implemented (stub)."""
    return jsonify({
        "error": {
            "code": "not_implemented",
            "message": "PDF export is not yet available. Use browser print.",
        },
    }), 501
