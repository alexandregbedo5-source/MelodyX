"""Tests for /api/analysis endpoints, exports, and teacher."""
import io
import json
import os
import tempfile
import pytest

from app.models.analysis import (
    create_session,
    create_analysis,
    update_analysis_status,
    save_result,
    save_artifact,
)


def _seed_completed_analysis(app, session_id):
    """Seed a fully completed analysis with artifacts in the database."""
    with app.app_context():
        from app.extensions import get_db
        db = get_db()
        db.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (session_id,))
        db.commit()

        tmp_dir = os.path.join(app.config["UPLOAD_FOLDER"], "an_seed_001")
        os.makedirs(tmp_dir, exist_ok=True)

        audio_path = os.path.join(tmp_dir, "piano.wav")
        with open(audio_path, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 1000)

        midi_path = os.path.join(tmp_dir, "an_seed_001.mid")
        with open(midi_path, "wb") as f:
            f.write(b"MThd" + b"\x00" * 50)

        musicxml_path = os.path.join(tmp_dir, "an_seed_001.musicxml")
        with open(musicxml_path, "w", encoding="utf-8") as f:
            f.write("<score-partwise><part id='P1'></part></score-partwise>")

        aid = create_analysis(
            session_id=session_id,
            filename="piano.wav",
            stored_path=audio_path,
            sha256="fake_sha256_hash",
            expires_at="2099-01-01T00:00:00Z",
        )
        update_analysis_status(
            aid,
            "completed",
            stage="ai_interpretation",
            progress=1.0,
            duration_seconds=12.5,
            sample_rate=22050,
            channels=1,
            completed_at="2026-11-06T12:00:00Z",
        )

        sample_music = {
            "tempo_bpm": {"value": 120.0, "confidence": 0.9, "source": "librosa"},
            "key": {"value": "C major", "confidence": 0.85, "source": "librosa"},
            "time_signature": {"value": "4/4", "confidence": 0.95, "source": "librosa"},
            "chords": [{"label": "C", "start": 0.0, "end": 2.0, "confidence": 0.9, "source": "librosa"}],
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0],
            "measures": [{"index": 1, "start": 0.0, "end": 2.0, "time_signature": "4/4"}],
            "notes": [
                {
                    "id": "n_0001",
                    "pitch": 60,
                    "name": "C4",
                    "start": 0.0,
                    "duration": 0.5,
                    "confidence": 0.95,
                    "source": "basic_pitch",
                    "estimated": True,
                    "measure": 1,
                    "hand": "right",
                }
            ],
        }
        sample_result = {
            "schema_version": "1.0",
            "analysis_id": aid,
            "music": sample_music,
            "ai": {"available": False},
        }
        save_result(aid, json.dumps(sample_result), "1.0")
        save_artifact(aid, "midi", midi_path, "audio/midi", 54)
        save_artifact(aid, "musicxml", musicxml_path, "application/vnd.recordare.musicxml+xml", 60)

        return aid


def test_analysis_not_found_returns_404(client):
    """GET non-existent analysis should return 404."""
    response = client.get('/api/analysis/an_nonexistent')
    assert response.status_code == 404


def test_analysis_wrong_session_returns_404(client, app):
    """Analysis belonging to different session returns 404 (not 403) to not leak info."""
    with app.app_context():
        aid = _seed_completed_analysis(app, "other_session")

    client.set_cookie("melodyx_sid", "my_session")
    response = client.get(f'/api/analysis/{aid}')
    assert response.status_code == 404


def test_analysis_completed_retrieval(client, app):
    """GET /api/analysis/{id} returns full data for completed analysis."""
    session_id = "test_sess_001"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get(f'/api/analysis/{aid}')
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["status"] == "completed"
    assert data["progress"] == 1.0
    assert data["schema_version"] == "1.0"
    assert "audio" in data
    assert data["audio"]["duration_seconds"] == 12.5
    assert "music" in data
    assert data["music"]["key"]["value"] == "C major"
    assert len(data["music"]["notes"]) == 1
    assert data["music"]["notes"][0]["name"] == "C4"


def test_analyses_list(client, app):
    """GET /api/analyses returns analyses belonging to session."""
    session_id = "test_sess_list"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get('/api/analyses')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) >= 1
    assert data[0]["analysis_id"] == aid
    assert data[0]["status"] == "completed"


def test_restart_analysis(client, app):
    """POST /api/analysis/start restarts analysis and returns 202."""
    session_id = "test_sess_restart"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.post(
        '/api/analysis/start',
        json={"analysis_id": aid, "options": {"quantization_grid": "16th"}},
    )
    assert response.status_code == 202
    data = json.loads(response.data)
    assert data["analysis_id"] == aid
    assert data["status"] == "queued"


def test_export_score_musicxml(client, app):
    """GET /api/analysis/{id}/score serves MusicXML score."""
    session_id = "test_sess_export"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get(f'/api/analysis/{aid}/score')
    assert response.status_code == 200
    assert "musicxml" in response.headers.get("Content-Type", "").lower()
    assert b"score-partwise" in response.data


def test_export_midi(client, app):
    """GET /api/analysis/{id}/midi serves MIDI artifact."""
    session_id = "test_sess_midi"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get(f'/api/analysis/{aid}/midi')
    assert response.status_code == 200
    assert "midi" in response.headers.get("Content-Type", "").lower()
    assert b"MThd" in response.data


def test_export_json(client, app):
    """GET /api/analysis/{id}/json returns full analysis JSON."""
    session_id = "test_sess_json"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get(f'/api/analysis/{aid}/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["analysis_id"] == aid
    assert "music" in data


def test_playback_range_request(client, app):
    """GET /api/analysis/{id}/audio supports HTTP Range requests (206 Partial Content)."""
    session_id = "test_sess_range"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    # Full content
    resp_full = client.get(f'/api/analysis/{aid}/audio')
    assert resp_full.status_code == 200

    # Range request (first 50 bytes)
    headers = {"Range": "bytes=0-49"}
    resp_partial = client.get(f'/api/analysis/{aid}/audio', headers=headers)
    assert resp_partial.status_code == 206
    assert len(resp_partial.data) == 50
    assert "bytes 0-49/" in resp_partial.headers.get("Content-Range", "")


def test_delete_analysis(client, app):
    """DELETE /api/analysis/{id} removes analysis and returns 204."""
    session_id = "test_sess_del"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.delete(f'/api/analysis/{aid}')
    assert response.status_code == 204

    # Subsequent GET returns 404
    get_resp = client.get(f'/api/analysis/{aid}')
    assert get_resp.status_code == 404


def test_pdf_export_success(client, app):
    """PDF export generates and serves a valid classical sheet music PDF."""
    session_id = "test_sess_pdf"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.get(f'/api/analysis/{aid}/pdf')
    assert response.status_code == 200
    assert response.content_type == "application/pdf"
    assert response.data[:5] == b"%PDF-"
    assert len(response.data) > 1000


def test_teacher_validation_missing_question(client, app):
    """POST /api/analysis/{id}/teacher without question returns 400."""
    session_id = "test_sess_teacher_val"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    response = client.post(
        f'/api/analysis/{aid}/teacher',
        json={"level": "beginner", "language": "fr", "question": ""},
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"]["code"] == "invalid_request"


def test_teacher_cache_returns_cached_response(client, app):
    """POST /api/analysis/{id}/teacher returns cached answer when available."""
    from app.services.gemini_service import _build_cache_key
    from app.models.analysis import save_ai_interaction

    session_id = "test_sess_teacher_cache"
    client.set_cookie("melodyx_sid", session_id)
    aid = _seed_completed_analysis(app, session_id)

    selection = {"measure_start": 1, "measure_end": 1}
    question = "Why is this C major?"
    level = "beginner"
    cache_key = _build_cache_key(aid, selection, question, level)

    cached_answer = {
        "answer": "This is a C major triad consisting of notes C, E, and G.",
        "grounding": {
            "measured": ["C4, E4, G4 in measure 1"],
            "estimated": ["C major triad (0.90 confidence)"],
            "unavailable": ["Fingerings"],
        },
        "model": "gemini-2.0-flash",
    }

    with app.app_context():
        save_ai_interaction(
            analysis_id=aid,
            selection=selection,
            level=level,
            question=question,
            answer=cached_answer,
            model="gemini-2.0-flash",
            cache_key=cache_key,
            status="ok",
            latency_ms=150,
        )

    response = client.post(
        f'/api/analysis/{aid}/teacher',
        json={
            "level": level,
            "language": "en",
            "selection": selection,
            "question": question,
        },
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["cached"] is True
    assert "C major triad" in data["answer"]
    assert "measured" in data["grounding"]
