"""MELODYX — Database schema initialisation and model helpers."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from flask import Flask, request as flask_request

from app.extensions import get_db

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    ai_calls_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    original_filename TEXT,
    stored_path TEXT,
    file_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT DEFAULT NULL,
    progress REAL DEFAULT 0.0,
    duration_seconds REAL DEFAULT NULL,
    sample_rate INTEGER DEFAULT NULL,
    channels INTEGER DEFAULT NULL,
    warnings_json TEXT DEFAULT '[]',
    error_code TEXT DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT DEFAULT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL,
    run_number INTEGER NOT NULL DEFAULT 1,
    result_json TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    mime TEXT NOT NULL,
    size_bytes INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE TABLE IF NOT EXISTS ai_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT NOT NULL,
    selection_json TEXT,
    level TEXT DEFAULT 'beginner',
    question TEXT,
    answer_json TEXT,
    model TEXT,
    cache_key TEXT,
    status TEXT DEFAULT 'pending',
    latency_ms INTEGER DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE TABLE IF NOT EXISTS score_edits (
    analysis_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    musicxml TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (analysis_id, instrument),
    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
);

CREATE TABLE IF NOT EXISTS transcription_usage (
    session_id TEXT PRIMARY KEY,
    transcriptions_used INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    amount_fcfa INTEGER NOT NULL,
    provider TEXT NOT NULL,
    reference TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS policy_consents (
    session_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    privacy_accepted INTEGER NOT NULL DEFAULT 0,
    copyright_accepted INTEGER NOT NULL DEFAULT 0,
    plagiarism_accepted INTEGER NOT NULL DEFAULT 0,
    gemini_opt_in INTEGER NOT NULL DEFAULT 0,
    accepted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (session_id, policy_version),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_analyses_session ON analyses(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_cache ON ai_interactions(cache_key);
CREATE INDEX IF NOT EXISTS idx_billing_session ON billing_subscriptions(session_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_policy_consents_expiry ON policy_consents(expires_at);
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def init_db(app: Flask) -> None:
    """Create all tables if they do not already exist.

    Called once during application startup from the factory.
    """
    db_path: str = app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.execute(
            """INSERT OR IGNORE INTO transcription_usage (session_id, transcriptions_used)
               SELECT session_id, COUNT(*) FROM analyses GROUP BY session_id"""
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def create_session() -> str:
    """Insert a new session row and return its id."""
    session_id = uuid.uuid4().hex
    db = get_db()
    db.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
    db.commit()
    return session_id


def get_or_create_session(req: Any = None) -> str:
    """Return the session id from the *melodyx_sid* cookie, creating one if absent.

    Parameters
    ----------
    req:
        The Flask request object.  Falls back to ``flask.request`` when
        *None*.
    """
    if req is None:
        req = flask_request
    sid: Optional[str] = req.cookies.get("melodyx_sid")
    if sid:
        db = get_db()
        row = db.execute("SELECT id FROM sessions WHERE id = ?", (sid,)).fetchone()
        if row:
            db.execute(
                "UPDATE sessions SET last_seen_at = datetime('now') WHERE id = ?",
                (sid,),
            )
            db.commit()
            return sid
    # No valid session — create one
    return create_session()


# ---------------------------------------------------------------------------
# Analysis CRUD
# ---------------------------------------------------------------------------


def _new_analysis_id() -> str:
    return f"an_{uuid.uuid4().hex[:12]}"


def create_analysis(
    session_id: str,
    filename: str,
    stored_path: str,
    sha256: str,
    expires_at: str,
    *,
    analysis_id: Optional[str] = None,
    enforce_quota: bool = False,
    free_limit: int = 10,
) -> Optional[str]:
    """Create a new analysis row and return its id.

    Parameters
    ----------
    session_id:
        Owning session.
    filename:
        Original uploaded filename.
    stored_path:
        Path where the file is stored on disk.
    sha256:
        SHA-256 hex digest of the uploaded file.
    expires_at:
        ISO-8601 UTC datetime string after which the analysis may be purged.
    analysis_id:
        Optional pre-generated id, used to keep the analysis folder and row aligned.
    enforce_quota:
        If true, reject the analysis when the free transcription allowance is used.
    free_limit:
        Number of accepted transcriptions before a paid plan is required.

    Returns
    -------
    Optional[str]
        The id, or ``None`` when the free transcription allowance is exhausted.
    """
    analysis_id = analysis_id or _new_analysis_id()
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "INSERT OR IGNORE INTO transcription_usage (session_id) VALUES (?)",
            (session_id,),
        )
        usage = db.execute(
            "SELECT transcriptions_used FROM transcription_usage WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        active_plan = db.execute(
            """SELECT 1 FROM billing_subscriptions
               WHERE session_id = ? AND status = 'active' AND plan_id != 'decouverte'
                 AND expires_at > ? LIMIT 1""",
            (session_id, now),
        ).fetchone()
        if enforce_quota and int(usage["transcriptions_used"]) >= free_limit and not active_plan:
            db.rollback()
            return None

        db.execute(
            """INSERT INTO analyses
               (id, session_id, original_filename, stored_path, file_sha256, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (analysis_id, session_id, filename, stored_path, sha256, expires_at),
        )
        db.execute(
            """UPDATE transcription_usage
               SET transcriptions_used = transcriptions_used + 1, updated_at = datetime('now')
               WHERE session_id = ?""",
            (session_id,),
        )
        db.commit()
        return analysis_id
    except Exception:
        db.rollback()
        raise


def refund_transcription(session_id: str) -> None:
    """Refund one accepted transcription after a processing failure."""
    db = get_db()
    db.execute(
        """UPDATE transcription_usage
           SET transcriptions_used = MAX(0, transcriptions_used - 1), updated_at = datetime('now')
           WHERE session_id = ?""",
        (session_id,),
    )
    db.commit()


def get_analysis(analysis_id: str, session_id: str) -> Optional[dict[str, Any]]:
    """Fetch an analysis by id, but only if it belongs to *session_id*.

    Returns ``None`` when the analysis does not exist **or** belongs to a
    different session — callers must never reveal whether an id exists.
    """
    db = get_db()
    row = db.execute(
        "SELECT * FROM analyses WHERE id = ? AND session_id = ?",
        (analysis_id, session_id),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    # Attach the latest result_json if analysis is complete
    res_row = db.execute(
        """SELECT result_json, schema_version FROM analysis_results
           WHERE analysis_id = ? ORDER BY run_number DESC LIMIT 1""",
        (analysis_id,),
    ).fetchone()
    if res_row:
        result["result"] = json.loads(res_row["result_json"])
        result["schema_version"] = res_row["schema_version"]
    # Parse warnings
    result["warnings"] = json.loads(result.pop("warnings_json", "[]") or "[]")
    return result


def update_analysis_status(
    analysis_id: str,
    status: str,
    *,
    stage: Optional[str] = None,
    progress: Optional[float] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None,
) -> None:
    """Update mutable fields on an analysis row."""
    fields: list[str] = ["status = ?"]
    params: list[Any] = [status]

    _optional = {
        "stage": stage,
        "progress": progress,
        "error_code": error_code,
        "error_message": error_message,
        "completed_at": completed_at,
        "duration_seconds": duration_seconds,
        "sample_rate": sample_rate,
        "channels": channels,
    }
    for col, val in _optional.items():
        if val is not None:
            fields.append(f"{col} = ?")
            params.append(val)

    params.append(analysis_id)
    db = get_db()
    db.execute(
        f"UPDATE analyses SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    db.commit()


def add_warning(analysis_id: str, warning_dict: dict[str, Any]) -> None:
    """Append a warning object to the warnings_json array."""
    db = get_db()
    row = db.execute(
        "SELECT warnings_json FROM analyses WHERE id = ?", (analysis_id,)
    ).fetchone()
    if row is None:
        return
    warnings = json.loads(row["warnings_json"] or "[]")
    warnings.append(warning_dict)
    db.execute(
        "UPDATE analyses SET warnings_json = ? WHERE id = ?",
        (json.dumps(warnings), analysis_id),
    )
    db.commit()


def save_result(
    analysis_id: str,
    result_json: str,
    schema_version: str,
) -> None:
    """Persist an analysis result JSON blob."""
    db = get_db()
    # Determine run number
    row = db.execute(
        "SELECT COALESCE(MAX(run_number), 0) AS n FROM analysis_results WHERE analysis_id = ?",
        (analysis_id,),
    ).fetchone()
    run_number = (row["n"] if row else 0) + 1
    db.execute(
        """INSERT INTO analysis_results (analysis_id, run_number, result_json, schema_version)
           VALUES (?, ?, ?, ?)""",
        (analysis_id, run_number, result_json, schema_version),
    )
    db.commit()


def save_artifact(
    analysis_id: str,
    artifact_type: str,
    file_path: str,
    mime: str,
    size_bytes: int,
) -> None:
    """Record an exported artifact (MIDI, MusicXML, PDF, etc.)."""
    db = get_db()
    db.execute(
        """INSERT INTO artifacts (analysis_id, artifact_type, file_path, mime, size_bytes)
           VALUES (?, ?, ?, ?, ?)""",
        (analysis_id, artifact_type, file_path, mime, size_bytes),
    )
    db.commit()


def get_score_edit(analysis_id: str, instrument: str) -> Optional[dict[str, Any]]:
    """Return the user's saved final MusicXML for one instrument score."""
    db = get_db()
    row = db.execute(
        """SELECT analysis_id, instrument, musicxml, version, updated_at
           FROM score_edits WHERE analysis_id = ? AND instrument = ?""",
        (analysis_id, instrument),
    ).fetchone()
    return dict(row) if row else None


def save_score_edit(
    analysis_id: str,
    instrument: str,
    musicxml: str,
    expected_version: int,
) -> tuple[bool, int, Optional[str]]:
    """Save an edited final score with optimistic concurrency control.

    ``expected_version`` is zero for a score that has never been edited.
    Returns ``(saved, current_or_new_version, updated_at)``.
    """
    db = get_db()
    updated_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT version FROM score_edits WHERE analysis_id = ? AND instrument = ?",
            (analysis_id, instrument),
        ).fetchone()
        current_version = int(row["version"]) if row else 0
        if current_version != expected_version:
            db.rollback()
            return False, current_version, None

        new_version = current_version + 1
        if row:
            db.execute(
                """UPDATE score_edits SET musicxml = ?, version = ?, updated_at = ?
                   WHERE analysis_id = ? AND instrument = ?""",
                (musicxml, new_version, updated_at, analysis_id, instrument),
            )
        else:
            db.execute(
                """INSERT INTO score_edits
                   (analysis_id, instrument, musicxml, version, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (analysis_id, instrument, musicxml, new_version, updated_at),
            )
        db.commit()
        return True, new_version, updated_at
    except Exception:
        db.rollback()
        raise


def delete_score_edits(analysis_id: str) -> None:
    """Remove saved final-score edits for an analysis."""
    db = get_db()
    db.execute("DELETE FROM score_edits WHERE analysis_id = ?", (analysis_id,))
    db.commit()


def get_artifacts(analysis_id: str, session_id: str) -> list[dict[str, Any]]:
    """Return all artifacts for an analysis if the session owns it."""
    db = get_db()
    rows = db.execute(
        """SELECT a.* FROM artifacts a
           JOIN analyses an ON an.id = a.analysis_id
           WHERE a.analysis_id = ? AND an.session_id = ?""",
        (analysis_id, session_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_analyses_for_session(session_id: str) -> list[dict[str, Any]]:
    """Return all analyses belonging to a session, newest first."""
    db = get_db()
    rows = db.execute(
        """SELECT id, original_filename, status, stage, progress,
                  duration_seconds, created_at, completed_at, expires_at
           FROM analyses WHERE session_id = ? ORDER BY created_at DESC""",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_analysis(analysis_id: str, session_id: str) -> bool:
    """Delete an analysis and its associated files if the session owns it.

    Returns ``True`` when a row was actually deleted.
    """
    db = get_db()
    row = db.execute(
        "SELECT stored_path FROM analyses WHERE id = ? AND session_id = ?",
        (analysis_id, session_id),
    ).fetchone()
    if row is None:
        return False

    # Remove stored audio file
    stored = row["stored_path"]
    if stored and os.path.isfile(stored):
        os.remove(stored)

    # Remove artifact files
    artifacts = db.execute(
        "SELECT file_path FROM artifacts WHERE analysis_id = ?", (analysis_id,)
    ).fetchall()
    for art in artifacts:
        if art["file_path"] and os.path.isfile(art["file_path"]):
            os.remove(art["file_path"])

    # Cascade delete related rows
    db.execute("DELETE FROM score_edits WHERE analysis_id = ?", (analysis_id,))
    db.execute("DELETE FROM artifacts WHERE analysis_id = ?", (analysis_id,))
    db.execute("DELETE FROM analysis_results WHERE analysis_id = ?", (analysis_id,))
    db.execute("DELETE FROM ai_interactions WHERE analysis_id = ?", (analysis_id,))
    db.execute(
        "DELETE FROM analyses WHERE id = ? AND session_id = ?",
        (analysis_id, session_id),
    )
    db.commit()
    return True


def purge_expired_analyses() -> int:
    """Delete all analyses whose ``expires_at`` is in the past.

    Returns the number of purged analyses.
    """
    import sqlite3 as _sqlite3
    from flask import current_app

    db_path: str = current_app.config["DATABASE_PATH"]
    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        expired = conn.execute(
            "SELECT id, stored_path FROM analyses WHERE expires_at < ?", (now,)
        ).fetchall()

        count = 0
        for row in expired:
            aid = row["id"]
            # Remove stored audio
            if row["stored_path"] and os.path.isfile(row["stored_path"]):
                os.remove(row["stored_path"])
            # Remove artifacts
            arts = conn.execute(
                "SELECT file_path FROM artifacts WHERE analysis_id = ?", (aid,)
            ).fetchall()
            for art in arts:
                if art["file_path"] and os.path.isfile(art["file_path"]):
                    os.remove(art["file_path"])
            conn.execute("DELETE FROM artifacts WHERE analysis_id = ?", (aid,))
            conn.execute("DELETE FROM score_edits WHERE analysis_id = ?", (aid,))
            conn.execute("DELETE FROM analysis_results WHERE analysis_id = ?", (aid,))
            conn.execute("DELETE FROM ai_interactions WHERE analysis_id = ?", (aid,))
            conn.execute("DELETE FROM analyses WHERE id = ?", (aid,))
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AI interaction helpers
# ---------------------------------------------------------------------------


def save_ai_interaction(
    analysis_id: str,
    selection: Optional[dict[str, Any]],
    level: str,
    question: str,
    answer: Optional[dict[str, Any]],
    model: str,
    cache_key: Optional[str],
    status: str,
    latency_ms: Optional[int],
) -> None:
    """Persist an AI question / answer interaction."""
    db = get_db()
    db.execute(
        """INSERT INTO ai_interactions
           (analysis_id, selection_json, level, question, answer_json,
            model, cache_key, status, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            analysis_id,
            json.dumps(selection) if selection else None,
            level,
            question,
            json.dumps(answer) if answer else None,
            model,
            cache_key,
            status,
            latency_ms,
        ),
    )
    db.commit()


def get_cached_ai_response(cache_key: str) -> Optional[dict[str, Any]]:
    """Return a cached AI answer dict if one exists for the given key."""
    db = get_db()
    row = db.execute(
        """SELECT answer_json FROM ai_interactions
           WHERE cache_key = ? AND status = 'ok'
           ORDER BY created_at DESC LIMIT 1""",
        (cache_key,),
    ).fetchone()
    if row and row["answer_json"]:
        return json.loads(row["answer_json"])
    return None


def increment_ai_calls(session_id: str) -> int:
    """Increment the session's AI call counter and return the new count."""
    db = get_db()
    db.execute(
        "UPDATE sessions SET ai_calls_count = ai_calls_count + 1 WHERE id = ?",
        (session_id,),
    )
    db.commit()
    row = db.execute(
        "SELECT ai_calls_count FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return row["ai_calls_count"] if row else 1
