"""Tests for MELODYX public pages and sheet music studio."""


def test_home_page_returns_marketing_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.content_type
    assert b"MELODYX" in response.data
    assert b"Le son devient" in response.data
    assert b"10 transcriptions offertes" in response.data
    assert b"melodyx-logo.jpeg" in response.data
    assert "melodyx_sid" in response.headers.get("Set-Cookie", "")


def test_public_pages_are_available(client):
    for path in ("/studio", "/library", "/pricing", "/checkout/essentiel"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"MELODYX" in response.data


def test_studio_has_upload_and_final_score_editor(client):
    response = client.get("/studio")
    assert response.status_code == 200
    assert b"dropZone" in response.data
    assert b"handleFileUpload" in response.data
    assert b"scoreEditor" in response.data
    assert b"OpenSheetMusicDisplay" in response.data
    assert b"policyConsentCard" in response.data
    assert b"disabled" in response.data
    assert b"Lire la politique de confidentialit" in response.data


def test_policy_documents_are_readable(client):
    for path, text in (
        ("/policies/privacy", "Politique de confidentialité"),
        ("/policies/copyright", "Politique de respect du droit d’auteur"),
        ("/policies/plagiarism", "Politique de non-plagiat"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert text.encode("utf-8") in response.data


def test_no_demo_references(client):
    response = client.get("/studio")
    assert response.status_code == 200
    assert b"/api/demo/" not in response.data


def test_demo_routes_removed(client):
    for path in ["/api/demo/analysis", "/api/demo/score", "/api/demo/pdf",
                 "/api/demo/midi", "/api/demo/audio"]:
        response = client.get(path)
        assert response.status_code == 404, f"{path} should return 404 but got {response.status_code}"
