"""MELODYX — Analysis retrieval, listing, deletion, and AI teacher (B7 / P1)."""

import json
from typing import Any, Optional

from flask import Blueprint, current_app, jsonify, request

from app.extensions import get_db
from app.models.analysis import (
    get_analysis,
    get_analyses_for_session,
    delete_analysis as model_delete_analysis,
    get_or_create_session,
    save_ai_interaction,
    get_cached_ai_response,
    increment_ai_calls,
)
from app.services.gemini_service import _build_cache_key

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_id() -> Optional[str]:
    """Return the session id from the request cookie or query param, or *None*."""
    return request.cookies.get("melodyx_sid") or request.args.get("session_id")


def _build_full_response(analysis: dict) -> dict:
    """Build the full analysis response payload.

    Merges database metadata with the pipeline result when available.
    """
    cfg = current_app.config
    status: str = analysis["status"]
    result: Optional[dict] = analysis.get("result")

    payload: dict[str, Any] = {
        "analysis_id": analysis["id"],
        "original_filename": analysis.get("original_filename"),
        "status": status,
        "stage": analysis.get("stage"),
        "progress": analysis.get("progress", 0.0),
        "warnings": analysis.get("warnings", []),
        "schema_version": cfg.get("SCHEMA_VERSION", "1.0"),
        "created_at": analysis.get("created_at"),
        "expires_at": analysis.get("expires_at"),
        "limits": {
            "max_file_mb": cfg.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024) // (1024 * 1024),
            "max_duration_s": float(cfg.get("MAX_DURATION_SECONDS", 240)),
        },
    }

    # Audio metadata — always include when known
    if analysis.get("duration_seconds") is not None:
        payload["audio"] = {
            "duration_seconds": analysis["duration_seconds"],
            "sample_rate": analysis.get("sample_rate"),
            "channels": analysis.get("channels"),
        }

    # Completed — attach full music and AI sections from result
    if status == "completed" and result is not None:
        payload["music"] = result.get("music", {})
        payload["ai"] = result.get("ai", {
            "available": bool(cfg.get("GEMINI_API_KEY")),
            "model": cfg.get("GEMINI_MODEL"),
            "summary": None,
        })
    else:
        payload["ai"] = {
            "available": bool(cfg.get("GEMINI_API_KEY")),
            "model": cfg.get("GEMINI_MODEL") if cfg.get("GEMINI_API_KEY") else None,
        }

    # Failed — attach error object
    if status == "failed":
        payload["error"] = {
            "code": analysis.get("error_code", "pipeline_error"),
            "message": analysis.get("error_message", "An unknown error occurred."),
        }

    return payload


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@analysis_bp.route("/analysis/<analysis_id>", methods=["GET"])
def get_analysis_route(analysis_id: str):
    """Return the current state of a single analysis.

    Pipeline failure is *not* an HTTP error — the response is 200 with
    ``status=failed`` and an ``error`` object.
    """
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    analysis = get_analysis(analysis_id, sid)
    if analysis is None:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    payload = _build_full_response(analysis)
    return jsonify(payload), 200


@analysis_bp.route("/analysis/<analysis_id>/instruments", methods=["GET"])
def get_analysis_instruments(analysis_id: str):
    """Return available instrument scores and metadata for an analysis."""
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    analysis = get_analysis(analysis_id, sid)
    if analysis is None:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    from app.services.stem_separator import AVAILABLE_INSTRUMENTS
    return jsonify({
        "analysis_id": analysis_id,
        "default": "conductor",
        "instruments": AVAILABLE_INSTRUMENTS,
    }), 200


@analysis_bp.route("/analysis/start", methods=["POST"])
def restart_analysis_route():
    """Rerun an analysis with optional parameters (e.g. quantization grid).

    Accepts JSON body:
        {
            "analysis_id": "an_...",
            "options": {
                "quantization_grid": "16th",
                "confidence_threshold": 0.5
            }
        }
    Returns 202 on success.
    """
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    body = request.get_json(silent=True) or {}
    analysis_id = body.get("analysis_id")
    if not analysis_id:
        return jsonify({"error": {"code": "invalid_request", "message": "analysis_id is required."}}), 400

    analysis = get_analysis(analysis_id, sid)
    if analysis is None:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    # Update status to queued
    from app.models.analysis import update_analysis_status
    update_analysis_status(analysis_id, "queued", stage=None, progress=0.0)

    try:
        from app.services.pipeline import submit_pipeline
        submit_pipeline(current_app._get_current_object(), analysis_id)
    except Exception:
        current_app.logger.exception("Failed to restart pipeline for %s", analysis_id)

    return jsonify({
        "analysis_id": analysis_id,
        "status": "queued",
        "message": "Analysis restarted.",
    }), 202


@analysis_bp.route("/analyses", methods=["GET"])
def list_analyses():
    """Return a lightweight list of all analyses for the current session."""
    sid = _session_id()
    if not sid:
        return jsonify([]), 200

    analyses = get_analyses_for_session(sid)
    items = [
        {
            "analysis_id": a["id"],
            "status": a["status"],
            "stage": a.get("stage"),
            "original_filename": a.get("original_filename"),
            "created_at": a.get("created_at"),
        }
        for a in analyses
    ]

    return jsonify(items), 200


@analysis_bp.route("/analysis/<analysis_id>", methods=["DELETE"])
def delete_analysis_route(analysis_id: str):
    """Delete an analysis and all associated files.

    Returns 204 on success, 404 if the analysis does not exist or
    does not belong to the current session.
    """
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    deleted = model_delete_analysis(analysis_id, sid)
    if not deleted:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    return "", 204


@analysis_bp.route("/analysis/<analysis_id>/teacher", methods=["POST"])
def ask_teacher_route(analysis_id: str):
    """Submit a question to the AI teacher for a completed analysis (P1).

    Request body:
        {
            "level": "beginner|intermediate",
            "language": "fr|en",
            "selection": {"measure_start": 5, "measure_end": 6},
            "question": "Why is this note sharp?"
        }
    """
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    # --- Validate request body -------------------------------------------
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": {"code": "invalid_request", "message": "JSON body required."}}), 400

    level: str = body.get("level", "beginner")
    if level not in ("beginner", "intermediate"):
        return jsonify({"error": {"code": "invalid_request", "message": "Level must be 'beginner' or 'intermediate'."}}), 400

    language: str = body.get("language", "en")
    if language not in ("fr", "en"):
        return jsonify({"error": {"code": "invalid_request", "message": "Language must be 'fr' or 'en'."}}), 400

    selection: Optional[dict] = body.get("selection")
    question: str = body.get("question", "").strip()
    if not question:
        return jsonify({"error": {"code": "invalid_request", "message": "A question is required."}}), 400

    if len(question) > 500:
        return jsonify({"error": {"code": "invalid_request", "message": "Question too long (max 500 characters)."}}), 400

    # --- Check analysis --------------------------------------------------
    analysis = get_analysis(analysis_id, sid)
    if analysis is None:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    if analysis["status"] != "completed":
        return jsonify({
            "error": {
                "code": "invalid_request",
                "message": "Analysis is not yet completed.",
            },
        }), 400

    from app.models.policies import has_gemini_opt_in
    if not has_gemini_opt_in(sid):
        return jsonify({
            "error": {
                "code": "gemini_consent_required",
                "message": "Active l’autorisation facultative Gemini avant de partager des données musicales avec le service IA.",
                "policies_url": "/policies/privacy",
            },
        }), 403

    # --- AI call quota ---------------------------------------------------
    max_calls: int = int(current_app.config.get("MAX_AI_CALLS_PER_SESSION", 20))
    db = get_db()
    session_row = db.execute(
        "SELECT ai_calls_count FROM sessions WHERE id = ?", (sid,)
    ).fetchone()
    if session_row and session_row["ai_calls_count"] >= max_calls:
        return jsonify({
            "error": {
                "code": "rate_limited",
                "message": f"AI call limit ({max_calls}) reached for this session.",
            },
        }), 429

    # --- Cache check -----------------------------------------------------
    cache_key = _build_cache_key(analysis_id, selection, question, level)
    cached = get_cached_ai_response(cache_key)
    if cached:
        cached["cached"] = True
        return jsonify(cached), 200

    # --- Call Gemini service ---------------------------------------------
    result = analysis.get("result")
    if not result:
        return jsonify({"error": {"code": "ai_unavailable", "message": "No analysis data available for AI."}}), 502

    import time
    start_ms = time.monotonic()

    try:
        from app.services.gemini_service import ask_teacher

        ai_response = ask_teacher(
            analysis_data=result,
            question=question,
            selection=selection,
            level=level,
            language=language,
            config=dict(current_app.config),
        )
    except Exception as exc:
        current_app.logger.exception("AI teacher call failed for %s", analysis_id)
        latency = int((time.monotonic() - start_ms) * 1000)
        save_ai_interaction(
            analysis_id=analysis_id,
            selection=selection,
            level=level,
            question=question,
            answer=None,
            model=current_app.config.get("GEMINI_MODEL", ""),
            cache_key=cache_key,
            status="error",
            latency_ms=latency,
        )
        return jsonify({
            "error": {"code": "ai_unavailable", "message": str(exc)},
        }), 502

    latency = int((time.monotonic() - start_ms) * 1000)

    # Check if AI returned an error
    if not ai_response.get("answer") and ai_response.get("available") is False:
        save_ai_interaction(
            analysis_id=analysis_id,
            selection=selection,
            level=level,
            question=question,
            answer=ai_response,
            model=current_app.config.get("GEMINI_MODEL", ""),
            cache_key=cache_key,
            status="error",
            latency_ms=latency,
        )
        return jsonify({
            "error": {"code": "ai_unavailable", "message": ai_response.get("error", "AI unavailable.")},
        }), 503

    # --- Save interaction & increment quota ------------------------------
    save_ai_interaction(
        analysis_id=analysis_id,
        selection=selection,
        level=level,
        question=question,
        answer=ai_response,
        model=ai_response.get("model", ""),
        cache_key=cache_key,
        status="ok",
        latency_ms=latency,
    )
    increment_ai_calls(sid)

    return jsonify(ai_response), 200
