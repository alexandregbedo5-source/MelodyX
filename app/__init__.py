"""MELODYX — Flask application factory."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from flask import Flask, jsonify, request

from app.config import Config
from app.extensions import init_extensions, close_db
from app.models.analysis import init_db, purge_expired_analyses

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background purge scheduler
# ---------------------------------------------------------------------------

def _start_purge_scheduler(app: Flask, interval_seconds: int = 3600) -> None:
    """Launch a daemon thread that purges expired analyses every *interval_seconds*."""

    def _purge_loop() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                with app.app_context():
                    count = purge_expired_analyses()
                    if count:
                        logger.info("Purged %d expired analyses.", count)
            except Exception:
                logger.exception("Error during purge cycle.")

    t = threading.Thread(target=_purge_loop, daemon=True, name="melodyx-purge")
    t.start()


# ---------------------------------------------------------------------------
# Error response builder
# ---------------------------------------------------------------------------

def _error_response(http_status: int, code: str, message: str) -> tuple[Any, int]:
    """Return a canonical JSON error envelope."""
    request_id = getattr(request, "_melodyx_request_id", str(uuid.uuid4()))
    body = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    return jsonify(body), http_status


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure the MELODYX Flask application.

    Parameters
    ----------
    test_config:
        Optional dict merged into the config for testing.

    Returns
    -------
    Flask
        The fully configured application instance.
    """
    app = Flask(__name__, instance_relative_config=False)

    # --- Configuration -------------------------------------------------------
    cfg = Config()
    app.config.from_object(cfg)
    if test_config:
        app.config.update(test_config)

    # --- Extensions ----------------------------------------------------------
    init_extensions(app)

    # --- Database ------------------------------------------------------------
    init_db(app)

    # --- Blueprints ----------------------------------------------------------
    from app.routes.health import health_bp
    from app.routes.upload import upload_bp
    from app.routes.analysis import analysis_bp
    from app.routes.export import export_bp
    from app.routes.playback import playback_bp
    from app.routes.web import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(playback_bp)

    # --- After-request hooks -------------------------------------------------

    @app.after_request
    def _add_request_id(response):  # type: ignore[no-untyped-def]
        """Attach a unique X-Request-Id header to every response."""
        rid = str(uuid.uuid4())
        request._melodyx_request_id = rid  # type: ignore[attr-defined]
        response.headers["X-Request-Id"] = rid
        return response

    @app.after_request
    def _add_security_headers(response):  # type: ignore[no-untyped-def]
        """Add common security headers."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Cache-Control"] = "no-store"
        
        # Allow frontend assets, scripts, audio streaming and fonts
        ctype = response.headers.get("Content-Type", "")
        if "text/html" in ctype or "javascript" in ctype or "text/css" in ctype:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "media-src 'self' blob: http: https:; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' https://cdn.jsdelivr.net;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

    # --- Error handlers ------------------------------------------------------

    @app.errorhandler(400)
    def _bad_request(exc):  # type: ignore[no-untyped-def]
        msg = str(exc.description) if hasattr(exc, "description") else "Bad request."
        return _error_response(400, "invalid_request", msg)

    @app.errorhandler(404)
    def _not_found(exc):  # type: ignore[no-untyped-def]
        return _error_response(404, "not_found", "Resource not found.")

    @app.errorhandler(413)
    def _payload_too_large(exc):  # type: ignore[no-untyped-def]
        return _error_response(413, "file_too_large", "File exceeds maximum allowed size.")

    @app.errorhandler(415)
    def _unsupported_media(exc):  # type: ignore[no-untyped-def]
        return _error_response(415, "unsupported_format", "Unsupported media type.")

    @app.errorhandler(422)
    def _unprocessable(exc):  # type: ignore[no-untyped-def]
        msg = str(exc.description) if hasattr(exc, "description") else "Unprocessable entity."
        return _error_response(422, "unprocessable_entity", msg)

    @app.errorhandler(429)
    def _rate_limited(exc):  # type: ignore[no-untyped-def]
        return _error_response(429, "rate_limited", "Rate limit exceeded. Try again later.")

    @app.errorhandler(500)
    def _internal(exc):  # type: ignore[no-untyped-def]
        logger.exception("Internal server error")
        return _error_response(500, "internal_error", "Internal server error.")

    # --- Background scheduler ------------------------------------------------
    if not app.config.get("TESTING"):
        _start_purge_scheduler(app, interval_seconds=3600)

    return app
