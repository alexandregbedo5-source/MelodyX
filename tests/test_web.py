"""MELODYX — Unit tests for Sheet Music Web Frontend & Demo Endpoints."""

import pytest


def test_index_page_returns_200(client):
    """GET / serves the interactive sheet music studio interface."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert b"MELODYX" in res.data
    assert b"OpenSheetMusicDisplay" in res.data
    # Check that session cookie was initialized
    assert "melodyx_sid" in res.headers.get("Set-Cookie", "")


def test_demo_analysis_endpoint(client):
    """GET /api/demo/analysis returns the sample piece analysis data."""
    res = client.get("/api/demo/analysis")
    assert res.status_code == 200
    data = res.get_json()
    assert "id" in data
    assert "result" in data
    assert "music" in data["result"]
    assert data["result"]["music"]["tempo_bpm"]["value"] > 0


def test_demo_score_endpoint(client):
    """GET /api/demo/score serves the MusicXML score."""
    res = client.get("/api/demo/score")
    assert res.status_code == 200
    assert b"score-partwise" in res.data or b"part" in res.data


def test_demo_pdf_endpoint(client):
    """GET /api/demo/pdf serves the vector PDF score sheet."""
    res = client.get("/api/demo/pdf")
    assert res.status_code == 200
    assert res.content_type == "application/pdf"
    assert res.data[:5] == b"%PDF-"


def test_demo_audio_endpoint(client):
    """GET /api/demo/audio serves the demo song audio stream."""
    res = client.get("/api/demo/audio")
    assert res.status_code in (200, 206)
    assert "audio/" in res.content_type
