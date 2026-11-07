"""Billing records for the local MELODYX payment simulation."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.extensions import get_db


def get_transcription_usage(session_id: str) -> int:
    db = get_db()
    row = db.execute(
        "SELECT transcriptions_used FROM transcription_usage WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return int(row["transcriptions_used"]) if row else 0


def get_active_subscription(session_id: str) -> Optional[dict[str, Any]]:
    db = get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = db.execute(
        """SELECT plan_id, status, amount_fcfa, provider, reference, started_at, expires_at
           FROM billing_subscriptions
           WHERE session_id = ? AND status = 'active' AND expires_at > ?
           ORDER BY id DESC LIMIT 1""",
        (session_id, now),
    ).fetchone()
    return dict(row) if row else None


def activate_simulated_subscription(
    session_id: str,
    plan_id: str,
    amount_fcfa: int,
    provider: str,
) -> dict[str, Any]:
    """Record a 30-day demo subscription without charging or storing payment details."""
    now = datetime.now(timezone.utc)
    started_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reference = f"MX-DEMO-{secrets.token_hex(4).upper()}"

    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "UPDATE billing_subscriptions SET status = 'superseded' WHERE session_id = ? AND status = 'active'",
            (session_id,),
        )
        db.execute(
            """INSERT INTO billing_subscriptions
               (session_id, plan_id, status, amount_fcfa, provider, reference, started_at, expires_at)
               VALUES (?, ?, 'active', ?, ?, ?, ?, ?)""",
            (session_id, plan_id, amount_fcfa, provider, reference, started_at, expires_at),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "plan_id": plan_id,
        "status": "active",
        "amount_fcfa": amount_fcfa,
        "provider": provider,
        "reference": reference,
        "started_at": started_at,
        "expires_at": expires_at,
    }
