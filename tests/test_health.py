"""Tests for /api/health endpoint."""
import json


def test_health_returns_200(client):
    """GET /api/health should return 200 with status info."""
    response = client.get('/api/health')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data['status'] == 'ok'
    assert data['version'] == '1.0'
    assert data['schema_version'] == '1.0'
    assert 'limits' in data
    assert 'max_file_mb' in data['limits']
    assert 'max_duration_s' in data['limits']
    assert 'allowed_formats' in data['limits']
    assert 'ai' in data
    assert 'retention_hours' in data


def test_health_has_request_id(client):
    """Every response should have X-Request-Id header."""
    response = client.get('/api/health')
    assert 'X-Request-Id' in response.headers


def test_health_limits_match_config(client):
    """Health endpoint limits should match configuration."""
    response = client.get('/api/health')
    data = json.loads(response.data)
    assert data['limits']['max_file_mb'] == 50
    assert data['limits']['max_duration_s'] == 240
    assert 'wav' in data['limits']['allowed_formats']
    assert 'mp3' in data['limits']['allowed_formats']
