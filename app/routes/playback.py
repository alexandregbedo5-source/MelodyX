"""MELODYX — Audio playback with Range request support (B8)."""

import mimetypes
import os
import re
from typing import Optional, Tuple

from flask import Blueprint, Response, current_app, jsonify, request

from app.extensions import get_db

playback_bp = Blueprint("playback", __name__, url_prefix="/api")

# ---------------------------------------------------------------------------
# MIME helpers
# ---------------------------------------------------------------------------

_EXTENSION_MIME: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".mp4": "audio/mp4",
    ".m4a": "audio/x-m4a",
}


def _mime_for_path(path: str) -> str:
    """Return the MIME type for *path* based on its extension."""
    ext = os.path.splitext(path)[1].lower()
    return _EXTENSION_MIME.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_id() -> Optional[str]:
    """Return the session id from the request cookie, or *None*."""
    return request.cookies.get("melodyx_sid")


def _parse_range(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """Parse an HTTP ``Range`` header and return ``(start, end)`` inclusive.

    Only supports a single byte range (e.g. ``bytes=0-1023``).
    Returns *None* if the header cannot be parsed or is out of bounds.
    """
    match = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not match:
        return None

    start_str, end_str = match.group(1), match.group(2)

    if start_str == "" and end_str == "":
        return None

    if start_str == "":
        # Suffix range: last N bytes
        suffix_length = int(end_str)
        if suffix_length == 0:
            return None
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    elif end_str == "":
        # Open-ended range
        start = int(start_str)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str)

    if start > end or start >= file_size:
        return None

    # Clamp end to file boundary
    end = min(end, file_size - 1)

    return start, end


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@playback_bp.route("/analysis/<analysis_id>/audio", methods=["GET"])
def stream_audio(analysis_id: str):
    """Serve the original uploaded audio file with HTTP Range support.

    Returns 200 for full content or 206 for partial content.
    """
    sid = _session_id()
    if not sid:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404

    from app.models.analysis import get_analysis
    analysis = get_analysis(analysis_id, sid)

    if analysis is None:
        return jsonify({"error": {"code": "not_found", "message": "Analysis not found."}}), 404
    stored_path: str = analysis.get("stored_path", "")

    if not stored_path or not os.path.isfile(stored_path):
        return jsonify({"error": {"code": "not_found", "message": "Audio file not found on disk."}}), 404

    file_size: int = os.path.getsize(stored_path)
    content_type: str = _mime_for_path(stored_path)

    range_header: Optional[str] = request.headers.get("Range")

    if range_header:
        # --- Partial Content (206) ----------------------------------------
        byte_range = _parse_range(range_header, file_size)
        if byte_range is None:
            return Response(
                "Range Not Satisfiable",
                status=416,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        start, end = byte_range
        length = end - start + 1

        with open(stored_path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Disposition": "inline",
        }
        return Response(data, status=206, headers=headers)

    # --- Full Content (200) -----------------------------------------------
    def _generate():
        """Stream file in 64 KiB chunks to avoid loading into memory."""
        with open(stored_path, "rb") as f:
            while True:
                chunk = f.read(65_536)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
        "Content-Disposition": "inline",
    }
    return Response(_generate(), status=200, headers=headers)
