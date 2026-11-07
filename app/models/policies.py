"""Persist versioned policy acknowledgements for anonymous MELODYX sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.extensions import get_db


# Bump this value whenever the published policy text changes materially.
POLICY_VERSION = "2026-11-07.1"
POLICY_ACKNOWLEDGEMENT_DAYS = 30


def get_policy_acceptance(
    session_id: str,
    policy_version: str = POLICY_VERSION,
) -> Optional[dict[str, Any]]:
    """Return an active consent receipt for the session, if one exists."""
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = db.execute(
        """SELECT * FROM policy_consents
           WHERE session_id = ? AND policy_version = ? AND expires_at > ?""",
        (session_id, policy_version, now),
    ).fetchone()
    if row is None:
        db.execute(
            "DELETE FROM policy_consents WHERE session_id = ? AND policy_version = ? AND expires_at <= ?",
            (session_id, policy_version, now),
        )
        db.commit()
        return None
    return dict(row)


def has_policy_acceptance(
    session_id: str,
    policy_version: str = POLICY_VERSION,
) -> bool:
    """Whether all three required policy acknowledgements are current."""
    receipt = get_policy_acceptance(session_id, policy_version)
    return bool(receipt and all(
        receipt.get(field) == 1
        for field in ("privacy_accepted", "copyright_accepted", "plagiarism_accepted")
    ))


def has_gemini_opt_in(
    session_id: str,
    policy_version: str = POLICY_VERSION,
) -> bool:
    """Whether the session has separately opted in to Gemini data transfer."""
    receipt = get_policy_acceptance(session_id, policy_version)
    return bool(
        receipt
        and receipt.get("gemini_opt_in") == 1
        and all(
            receipt.get(field) == 1
            for field in ("privacy_accepted", "copyright_accepted", "plagiarism_accepted")
        )
    )


def record_policy_acceptance(
    session_id: str,
    *,
    privacy_accepted: bool,
    copyright_accepted: bool,
    plagiarism_accepted: bool,
    gemini_opt_in: bool = False,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    """Save the policy version, required acknowledgements and optional AI choice."""
    accepted_at = datetime.now(timezone.utc)
    expires_at = accepted_at + timedelta(days=POLICY_ACKNOWLEDGEMENT_DAYS)
    accepted_text = accepted_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_text = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    db = get_db()
    db.execute(
        """INSERT INTO policy_consents (
               session_id, policy_version, privacy_accepted, copyright_accepted,
               plagiarism_accepted, gemini_opt_in, accepted_at, expires_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, policy_version) DO UPDATE SET
               privacy_accepted = excluded.privacy_accepted,
               copyright_accepted = excluded.copyright_accepted,
               plagiarism_accepted = excluded.plagiarism_accepted,
               gemini_opt_in = excluded.gemini_opt_in,
               accepted_at = excluded.accepted_at,
               expires_at = excluded.expires_at""",
        (
            session_id,
            policy_version,
            int(privacy_accepted),
            int(copyright_accepted),
            int(plagiarism_accepted),
            int(gemini_opt_in),
            accepted_text,
            expires_text,
        ),
    )
    db.commit()
    return {
        "policy_version": policy_version,
        "privacy_accepted": bool(privacy_accepted),
        "copyright_accepted": bool(copyright_accepted),
        "plagiarism_accepted": bool(plagiarism_accepted),
        "gemini_opt_in": bool(gemini_opt_in),
        "accepted_at": accepted_text,
        "expires_at": expires_text,
    }


def update_gemini_opt_in(
    session_id: str,
    enabled: bool,
    policy_version: str = POLICY_VERSION,
) -> bool:
    """Change the optional Gemini choice only while the required receipt is valid."""
    if not has_policy_acceptance(session_id, policy_version):
        return False
    db = get_db()
    db.execute(
        """UPDATE policy_consents SET gemini_opt_in = ?
           WHERE session_id = ? AND policy_version = ?""",
        (int(enabled), session_id, policy_version),
    )
    db.commit()
    return True


def purge_expired_policy_consents() -> int:
    """Remove expired acknowledgement receipts."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = get_db()
    cursor = db.execute("DELETE FROM policy_consents WHERE expires_at <= ?", (now,))
    db.commit()
    return max(0, cursor.rowcount)
