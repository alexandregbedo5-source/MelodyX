"""MELODYX — Unit tests for Sheet Music Web Frontend."""

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


def test_index_no_demo_references(client):
    """The index page must not reference any /api/demo/ endpoints."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"/api/demo/" not in res.data


def test_index_sets_session_cookie(client):
    """First visit sets melodyx_sid cookie that persists across requests."""
    res = client.get("/")
    cookie_header = res.headers.get("Set-Cookie", "")
    assert "melodyx_sid=" in cookie_header


def test_demo_routes_removed(client):
    """All /api/demo/* routes must return 404 after demo removal."""
    for path in ["/api/demo/analysis", "/api/demo/score", "/api/demo/pdf",
                 "/api/demo/midi", "/api/demo/audio"]:
        res = client.get(path)
        assert res.status_code == 404, f"{path} should return 404 but got {res.status_code}"


def test_upload_zone_present(client):
    """The upload drop zone is present in the page."""
    res = client.get("/")
    assert b"dropZone" in res.data
    assert b"handleFileUpload" in res.data
