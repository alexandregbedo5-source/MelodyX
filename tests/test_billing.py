"""Tests for the ten-transcription allowance and demo payment flow."""

import io

from app.extensions import get_db
from app.models.analysis import create_analysis


def _session_id(client):
    client.get("/")
    return client.get_cookie("melodyx_sid").value


def test_ten_transcriptions_then_simulated_payment_unlocks(app, client):
    session_id = _session_id(client)
    expires_at = "2099-01-01T00:00:00Z"

    with app.app_context():
        for number in range(10):
            created = create_analysis(
                session_id, f"song-{number}.wav", f"uploads/song-{number}.wav",
                f"hash-{number}", expires_at, analysis_id=f"quota_{number}",
                enforce_quota=True,
            )
            assert created == f"quota_{number}"

        assert create_analysis(
            session_id, "blocked.wav", "uploads/blocked.wav", "blocked-hash",
            expires_at, analysis_id="quota_blocked", enforce_quota=True,
        ) is None

    status = client.get("/api/billing/status").get_json()
    assert status["transcriptions_used"] == 10
    assert status["remaining_free"] == 0
    assert status["requires_payment"] is True

    pricing = client.get("/pricing?reason=quota")
    assert pricing.status_code == 200
    assert "1 500".encode() in pricing.data

    payment = client.post("/api/billing/simulate", json={
        "plan_id": "essentiel",
        "provider": "wave",
    })
    assert payment.status_code == 201
    assert payment.get_json()["simulated"] is True
    assert payment.get_json()["subscription"]["amount_fcfa"] == 1500

    status = client.get("/api/billing/status").get_json()
    assert status["is_paid"] is True
    assert status["requires_payment"] is False
    with app.app_context():
        assert create_analysis(
            session_id, "song-after-payment.wav", "uploads/song-after-payment.wav",
            "post-payment-hash", expires_at, analysis_id="quota_unlocked",
            enforce_quota=True,
        ) == "quota_unlocked"


def test_upload_redirects_to_pricing_when_free_quota_is_used(app, client, monkeypatch):
    session_id = _session_id(client)
    from app.models.policies import POLICY_VERSION
    consent = client.post("/api/policies/consent", json={
        "policy_version": POLICY_VERSION,
        "privacy_accepted": True,
        "copyright_accepted": True,
        "plagiarism_accepted": True,
    })
    assert consent.status_code == 200
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO transcription_usage (session_id, transcriptions_used) VALUES (?, 10)",
            (session_id,),
        )
        db.commit()

    monkeypatch.setattr("app.routes.upload._ffprobe_info", lambda _path: (1.0, 22050, 1))
    response = client.post(
        "/api/audio/upload",
        data={"audio": (io.BytesIO(b"valid-enough-for-the-probe"), "quota.wav", "audio/wav")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 402
    payload = response.get_json()
    assert payload["error"]["code"] == "quota_exceeded"
    assert payload["error"]["pricing_url"] == "/pricing?reason=quota"


def test_simulated_payment_rejects_invalid_provider(client):
    response = client.post("/api/billing/simulate", json={
        "plan_id": "essentiel",
        "provider": [],
    })
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_provider"
