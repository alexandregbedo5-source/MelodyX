"""MELODYX — Health-check endpoint."""

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Return service health, configuration limits, and AI availability.

    Returns 200 with status information including allowed formats,
    file-size / duration limits, AI readiness, and retention policy.
    """
    cfg = current_app.config

    gemini_key: str = cfg.get("GEMINI_API_KEY", "")
    ai_available: bool = bool(gemini_key)
    ai_model = cfg.get("GEMINI_MODEL") if ai_available else None

    max_file_mb: int = cfg.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024) // (1024 * 1024)
    max_duration_s: float = float(cfg.get("MAX_DURATION_SECONDS", 240))
    retention_hours: int = int(cfg.get("FILE_RETENTION_HOURS", 24))

    payload = {
        "status": "ok",
        "version": "1.0",
        "schema_version": cfg.get("SCHEMA_VERSION", "1.0"),
        "limits": {
            "max_file_mb": max_file_mb,
            "max_duration_s": max_duration_s,
            "allowed_formats": ["wav", "mp3", "flac", "ogg", "webm", "mp4", "m4a"],
        },
        "ai": {
            "available": ai_available,
            "model": ai_model,
        },
        "retention_hours": retention_hours,
    }

    return jsonify(payload), 200
