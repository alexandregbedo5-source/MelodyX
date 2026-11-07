"""Plan catalog and quota helpers for MELODYX's simulated billing flow."""

from __future__ import annotations

from typing import Any

from app.models.billing import get_active_subscription, get_transcription_usage


FREE_TRANSCRIPTION_LIMIT = 10

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "decouverte": {
        "id": "decouverte",
        "name": "Découverte",
        "price_fcfa": 0,
        "period": "pour 10 transcriptions",
        "description": "Le temps de découvrir l’atelier et ses outils.",
        "features": [
            "10 transcriptions offertes",
            "Édition de chaque partition",
            "Aperçu et lecture audio",
        ],
        "free": True,
    },
    "essentiel": {
        "id": "essentiel",
        "name": "Essentiel",
        "price_fcfa": 1500,
        "period": "pour 30 jours",
        "description": "Pour travailler régulièrement ses morceaux.",
        "features": [
            "Transcriptions sans quota",
            "Édition des pupitres",
            "Exports PDF, MIDI et MusicXML",
        ],
        "free": False,
    },
    "atelier": {
        "id": "atelier",
        "name": "Atelier",
        "price_fcfa": 3500,
        "period": "pour 30 jours",
        "description": "Pour arranger et préparer ses morceaux en détail.",
        "features": [
            "Transcriptions sans quota",
            "Toutes les partitions et tous les exports",
            "Édition, sauvegarde et historique des pupitres",
        ],
        "free": False,
        "featured": True,
    },
}

PAYMENT_PROVIDERS = {
    "orange_money": "Orange Money",
    "mtn_momo": "MTN MoMo",
    "moov_money": "Moov Money",
    "wave": "Wave",
    "carte_test": "Carte de démonstration",
}


def get_billing_status(session_id: str) -> dict[str, Any]:
    used = get_transcription_usage(session_id)
    subscription = get_active_subscription(session_id)
    plan_id = subscription["plan_id"] if subscription else "decouverte"
    plan = PLAN_CATALOG.get(plan_id, PLAN_CATALOG["decouverte"])
    paid = bool(subscription and not plan.get("free"))
    return {
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "plan_status": subscription["status"] if subscription else "free",
        "price_fcfa": plan["price_fcfa"],
        "expires_at": subscription.get("expires_at") if subscription else None,
        "payment_reference": subscription.get("reference") if subscription else None,
        "provider": subscription.get("provider") if subscription else None,
        "transcriptions_used": used,
        "free_limit": FREE_TRANSCRIPTION_LIMIT,
        "remaining_free": max(0, FREE_TRANSCRIPTION_LIMIT - used),
        "is_paid": paid,
        "requires_payment": not paid and used >= FREE_TRANSCRIPTION_LIMIT,
    }
