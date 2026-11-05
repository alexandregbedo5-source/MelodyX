"""MELODYX — Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Flask application configuration loaded from environment variables."""

    # --- Core Flask ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-to-a-random-string")

    # --- Upload limits ---
    _max_mb: int = int(os.getenv("MAX_CONTENT_LENGTH_MB", "50"))
    MAX_CONTENT_LENGTH: int = _max_mb * 1024 * 1024  # bytes

    # --- Audio constraints ---
    MAX_DURATION_SECONDS: float = float(os.getenv("MAX_DURATION_SECONDS", "240"))

    # --- Paths ---
    UPLOAD_FOLDER: str = str(
        Path(os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))).resolve()
    )
    DATABASE_PATH: str = str(
        Path(
            os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'melodyx.db'}")
            .replace("sqlite:///", "")
        ).resolve()
    )

    # --- Gemini AI ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_TIMEOUT: int = 25
    GEMINI_MAX_RETRIES: int = 2

    # --- Retention ---
    FILE_RETENTION_HOURS: int = int(os.getenv("FILE_RETENTION_HOURS", "24"))

    # --- Rate limiting ---
    MAX_AI_CALLS_PER_SESSION: int = 20

    # --- Allowed uploads ---
    ALLOWED_EXTENSIONS: set[str] = {
        "wav", "mp3", "flac", "ogg", "webm", "mp4", "m4a",
    }
    ALLOWED_MIME_TYPES: set[str] = {
        "audio/wav",
        "audio/mpeg",
        "audio/flac",
        "audio/ogg",
        "audio/webm",
        "audio/mp4",
        "audio/x-m4a",
        "audio/x-wav",
        "audio/wave",
    }

    # --- Schema ---
    SCHEMA_VERSION: str = "1.0"

    def __init__(self) -> None:
        """Ensure the upload directory exists on instantiation."""
        os.makedirs(self.UPLOAD_FOLDER, exist_ok=True)
