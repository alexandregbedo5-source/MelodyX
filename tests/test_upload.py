"""Tests for /api/audio/upload endpoint."""
import io
import json


def test_upload_no_file_returns_400(client):
    """POST without file should return 400."""
    response = client.post('/api/audio/upload')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error']['code'] == 'invalid_request'


def test_upload_wrong_extension_returns_415(client):
    """POST with unsupported extension should return 415."""
    data = {'audio': (io.BytesIO(b'fake content'), 'test.exe')}
    response = client.post('/api/audio/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 415
    resp_data = json.loads(response.data)
    assert resp_data['error']['code'] == 'unsupported_format'


def test_upload_returns_request_id(client):
    """Upload response should include X-Request-Id."""
    data = {'audio': (io.BytesIO(b'fake wav content'), 'test.wav')}
    response = client.post('/api/audio/upload', data=data, content_type='multipart/form-data')
    assert 'X-Request-Id' in response.headers


def test_record_no_data_returns_400(client):
    """POST /api/audio/record with no audio returns 400."""
    response = client.post('/api/audio/record')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error']['code'] == 'invalid_request'


def test_upload_valid_audio_success(client):
    """POST /api/audio/upload with valid WAV queues analysis with 202."""
    import numpy as np
    import soundfile as sf

    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, y, sr, format='WAV')
    buf.seek(0)

    data = {'audio': (buf, 'piano_note.wav', 'audio/wav')}
    response = client.post('/api/audio/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 202
    resp_data = json.loads(response.data)
    assert resp_data['status'] == 'queued'
    assert resp_data['analysis_id'].startswith('an_')
    assert 'melodyx_sid' in response.headers.get('Set-Cookie', '')
