"""MELODYX — Audio file upload endpoint (B1)."""

import hashlib
import json
import os
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

from flask import Blueprint, current_app, jsonify, request

from app.extensions import get_db
from app.models.analysis import (
    create_analysis,
    create_session,
    get_or_create_session,
    update_analysis_status,
)

upload_bp = Blueprint("upload", __name__, url_prefix="/api/audio")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIME_MAP: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "webm": "audio/webm",
    "mp4": "audio/mp4",
    "m4a": "audio/x-m4a",
}


def _allowed_extension(filename: str) -> bool:
    """Return *True* if *filename* has an allowed audio extension."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    allowed: set[str] = current_app.config.get(
        "ALLOWED_EXTENSIONS",
        {"wav", "mp3", "flac", "ogg", "webm", "mp4", "m4a"},
    )
    return ext in allowed


def _allowed_mime(mime_type: str) -> bool:
    """Return *True* if *mime_type* is in the allowed set."""
    allowed: set[str] = current_app.config.get(
        "ALLOWED_MIME_TYPES",
        {
            "audio/wav", "audio/mpeg", "audio/flac", "audio/ogg",
            "audio/webm", "audio/mp4", "audio/x-m4a", "audio/x-wav",
            "audio/wave",
        },
    )
    return mime_type in allowed


def _sha256(filepath: str) -> str:
    """Compute the SHA-256 hex digest of the file at *filepath*."""
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_info(filepath: str) -> Tuple[float, Optional[int], Optional[int]]:
    """Run *ffprobe* on *filepath* and return ``(duration, sample_rate, channels)``.

    Falls back to PyAV if ffprobe is not available on PATH.
    Raises ``ValueError`` if the audio stream cannot be read.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            probe = json.loads(result.stdout)
            audio_stream = None
            for stream in probe.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break

            if audio_stream is not None:
                duration_str = (
                    audio_stream.get("duration")
                    or probe.get("format", {}).get("duration")
                )
                if duration_str is not None:
                    duration = float(duration_str)
                    sample_rate = int(audio_stream["sample_rate"]) if "sample_rate" in audio_stream else None
                    channels = int(audio_stream["channels"]) if "channels" in audio_stream else None
                    return duration, sample_rate, channels
    except Exception:
        pass

    # Fallback: PyAV
    try:
        import av
        with av.open(filepath) as container:
            audio_stream = next((s for s in container.streams if s.type == "audio"), None)
            if audio_stream is None:
                raise ValueError("No audio stream found in file")
            duration = float(container.duration / av.time_base) if container.duration else 0.0
            if duration <= 0 and audio_stream.duration:
                duration = float(audio_stream.duration * audio_stream.time_base)
            if duration <= 0:
                raise ValueError("Cannot determine audio duration")
            sample_rate = audio_stream.sample_rate
            channels = audio_stream.channels
            return duration, sample_rate, channels
    except Exception as exc:
        raise ValueError(f"Could not read audio file: {exc}")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@upload_bp.route("/upload", methods=["POST"])
def upload_audio():
    """Accept an audio file upload and queue it for analysis.

    Returns 202 on success with the new ``analysis_id`` and status.
    """
    # 1. Session ----------------------------------------------------------
    session_id = get_or_create_session()
    is_new_session = request.cookies.get("melodyx_sid") is None

    # 2. File presence ----------------------------------------------------
    if "audio" not in request.files:
        return jsonify({"error": {"code": "invalid_request", "message": "No audio file provided."}}), 400

    audio_file = request.files["audio"]
    if audio_file.filename is None or audio_file.filename.strip() == "":
        return jsonify({"error": {"code": "invalid_request", "message": "No audio file selected."}}), 400

    original_filename: str = audio_file.filename

    # 3. (MAX_CONTENT_LENGTH handled by Flask — returns 413 automatically)

    # 4. Extension --------------------------------------------------------
    if not _allowed_extension(original_filename):
        return jsonify({
            "error": {
                "code": "unsupported_format",
                "message": "File extension is not supported.",
            },
        }), 415

    # 5. MIME type --------------------------------------------------------
    mime_type: str = audio_file.content_type or ""
    if not _allowed_mime(mime_type):
        return jsonify({
            "error": {
                "code": "unsupported_format",
                "message": f"MIME type '{mime_type}' is not supported.",
            },
        }), 415

    # 6. Generate analysis_id & storage dir --------------------------------
    analysis_id: str = f"an_{secrets.token_hex(6)}"
    upload_folder: str = current_app.config["UPLOAD_FOLDER"]
    analysis_dir = os.path.join(upload_folder, analysis_id)
    os.makedirs(analysis_dir, exist_ok=True)

    # 7. Save file -------------------------------------------------------
    ext = original_filename.rsplit(".", 1)[1].lower()
    internal_name = f"{secrets.token_hex(8)}.{ext}"
    stored_path = os.path.join(analysis_dir, internal_name)
    audio_file.save(stored_path)

    # 8. SHA-256 hash -----------------------------------------------------
    file_hash: str = _sha256(stored_path)

    # 9. ffprobe verification --------------------------------------------
    try:
        duration, sample_rate, channels = _ffprobe_info(stored_path)
    except ValueError as exc:
        _cleanup_dir(analysis_dir)
        return jsonify({
            "error": {
                "code": "unreadable_audio",
                "message": str(exc),
            },
        }), 422

    max_duration: float = float(current_app.config.get("MAX_DURATION_SECONDS", 240))
    if duration > max_duration:
        _cleanup_dir(analysis_dir)
        return jsonify({
            "error": {
                "code": "audio_too_long",
                "message": (
                    f"Audio duration ({duration:.1f}s) exceeds the "
                    f"maximum allowed ({max_duration:.0f}s)."
                ),
            },
        }), 422

    # 10. Database insert -------------------------------------------------
    retention_hours: int = int(current_app.config.get("FILE_RETENTION_HOURS", 24))
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=retention_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    analysis_id = create_analysis(
        session_id=session_id,
        filename=original_filename,
        stored_path=stored_path,
        sha256=file_hash,
        expires_at=expires_at,
    )

    # Update with audio metadata
    update_analysis_status(
        analysis_id, "queued",
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
    )

    # 11. Submit pipeline task --------------------------------------------
    try:
        from app.services.pipeline import submit_pipeline

        submit_pipeline(current_app._get_current_object(), analysis_id)
    except Exception:
        current_app.logger.exception(
            "Failed to submit pipeline task for %s", analysis_id
        )

    # 12. Response --------------------------------------------------------
    resp = jsonify({
        "analysis_id": analysis_id,
        "status": "queued",
        "message": "Analysis started.",
    })
    resp.status_code = 202

    if is_new_session:
        resp.set_cookie(
            "melodyx_sid",
            session_id,
            httponly=True,
            samesite="Lax",
            max_age=retention_hours * 3600,
        )

    return resp


@upload_bp.route("/record", methods=["POST"])
def record_audio():
    """Accept an audio recording from the browser (WebM/Opus, MP4/AAC, WAV) and queue it for analysis.

    Returns 202 on success with the new ``analysis_id`` and status.
    """
    session_id = get_or_create_session()
    is_new_session = request.cookies.get("melodyx_sid") is None

    # Audio can be passed via form-data 'audio', 'blob', or raw data
    audio_file = None
    if "audio" in request.files:
        audio_file = request.files["audio"]
    elif "blob" in request.files:
        audio_file = request.files["blob"]

    if audio_file is None or not audio_file.filename:
        # Check raw body
        if not request.data:
            return jsonify({"error": {"code": "invalid_request", "message": "No recording data provided."}}), 400

    analysis_id: str = f"an_{secrets.token_hex(6)}"
    upload_folder: str = current_app.config["UPLOAD_FOLDER"]
    analysis_dir = os.path.join(upload_folder, analysis_id)
    os.makedirs(analysis_dir, exist_ok=True)

    # Determine extension
    content_type = request.content_type or ""
    if "webm" in content_type:
        ext = "webm"
    elif "mp4" in content_type or "m4a" in content_type:
        ext = "mp4"
    elif "wav" in content_type:
        ext = "wav"
    elif audio_file and "." in audio_file.filename:
        ext = audio_file.filename.rsplit(".", 1)[1].lower()
    else:
        ext = "webm"

    internal_name = f"recording_{secrets.token_hex(8)}.{ext}"
    stored_path = os.path.join(analysis_dir, internal_name)

    if audio_file:
        audio_file.save(stored_path)
    else:
        with open(stored_path, "wb") as f:
            f.write(request.data)

    file_hash: str = _sha256(stored_path)

    try:
        duration, sample_rate, channels = _ffprobe_info(stored_path)
    except ValueError as exc:
        _cleanup_dir(analysis_dir)
        return jsonify({
            "error": {
                "code": "unreadable_audio",
                "message": str(exc),
            },
        }), 422

    max_duration: float = float(current_app.config.get("MAX_DURATION_SECONDS", 240))
    if duration > max_duration:
        _cleanup_dir(analysis_dir)
        return jsonify({
            "error": {
                "code": "audio_too_long",
                "message": f"Audio duration ({duration:.1f}s) exceeds maximum allowed ({max_duration:.0f}s).",
            },
        }), 422

    retention_hours: int = int(current_app.config.get("FILE_RETENTION_HOURS", 24))
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=retention_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    analysis_id = create_analysis(
        session_id=session_id,
        filename=f"recording.{ext}",
        stored_path=stored_path,
        sha256=file_hash,
        expires_at=expires_at,
    )

    update_analysis_status(
        analysis_id, "queued",
        duration_seconds=duration,
        sample_rate=sample_rate,
        channels=channels,
    )

    try:
        from app.services.pipeline import submit_pipeline
        submit_pipeline(current_app._get_current_object(), analysis_id)
    except Exception:
        current_app.logger.exception("Failed to submit pipeline task for %s", analysis_id)

    resp = jsonify({
        "analysis_id": analysis_id,
        "status": "queued",
        "message": "Recording queued for analysis.",
    })
    resp.status_code = 202

    if is_new_session:
        resp.set_cookie(
            "melodyx_sid",
            session_id,
            httponly=True,
            samesite="Lax",
            max_age=retention_hours * 3600,
        )

    return resp


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------

def _cleanup_dir(directory: str) -> None:
    """Remove all files in *directory* then the directory itself."""
    import shutil

    try:
        shutil.rmtree(directory, ignore_errors=True)
    except Exception:
        pass
