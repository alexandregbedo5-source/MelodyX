"""Tests for consent gating, policy pages, and the optional Gemini choice."""

import io

from app.models.policies import POLICY_VERSION, has_gemini_opt_in, has_policy_acceptance


def _session_id(client):
    client.get("/")
    return client.get_cookie("melodyx_sid").value


def _accepted_payload(**extra):
    payload = {
        "policy_version": POLICY_VERSION,
        "privacy_accepted": True,
        "copyright_accepted": True,
        "plagiarism_accepted": True,
    }
    payload.update(extra)
    return payload


def test_policy_consent_requires_all_documents(client):
    session_id = _session_id(client)
    response = client.post("/api/policies/consent", json={
        "policy_version": POLICY_VERSION,
        "privacy_accepted": True,
        "copyright_accepted": True,
    })
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "policy_acceptance_required"
    with client.application.app_context():
        assert not has_policy_acceptance(session_id)


def test_upload_and_microphone_endpoints_are_blocked_until_consent(client, monkeypatch):
    def unexpected_probe(_path):
        raise AssertionError("The audio file must not be processed before consent.")

    monkeypatch.setattr("app.routes.upload._ffprobe_info", unexpected_probe)
    upload = client.post(
        "/api/audio/upload",
        data={"audio": (io.BytesIO(b"audio bytes"), "song.wav", "audio/wav")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 428
    assert upload.get_json()["error"]["code"] == "policy_consent_required"

    recording = client.post("/api/audio/record", data=b"audio bytes", content_type="audio/webm")
    assert recording.status_code == 428
    assert recording.get_json()["error"]["code"] == "policy_consent_required"


def test_acceptance_unlocks_upload_and_keeps_gemini_off_by_default(client, monkeypatch):
    session_id = _session_id(client)
    response = client.post("/api/policies/consent", json=_accepted_payload())
    assert response.status_code == 200
    assert response.get_json()["accepted"] is True
    assert response.get_json()["gemini_opt_in"] is False

    with client.application.app_context():
        assert has_policy_acceptance(session_id)
        assert not has_gemini_opt_in(session_id)

    monkeypatch.setattr("app.routes.upload._ffprobe_info", lambda _path: (1.0, 22050, 1))
    monkeypatch.setattr("app.services.pipeline.submit_pipeline", lambda *_args: None)
    upload = client.post(
        "/api/audio/upload",
        data={"audio": (io.BytesIO(b"audio bytes"), "song.wav", "audio/wav")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 202
    assert upload.get_json()["analysis_id"].startswith("an_")


def test_gemini_consent_can_be_toggled_separately(client):
    session_id = _session_id(client)
    client.post("/api/policies/consent", json=_accepted_payload())

    enabled = client.post("/api/policies/ai-consent", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.get_json()["gemini_opt_in"] is True
    with client.application.app_context():
        assert has_gemini_opt_in(session_id)

    disabled = client.post("/api/policies/ai-consent", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.get_json()["gemini_opt_in"] is False
    with client.application.app_context():
        assert not has_gemini_opt_in(session_id)
