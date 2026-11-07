"""Pytest configuration and fixtures for MELODYX tests."""
import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def app():
    """Create application for testing."""
    # Keep test data out of the project's configured database and uploads.
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app({
            'UPLOAD_FOLDER': os.path.join(tmpdir, 'uploads'),
            'DATABASE_PATH': os.path.join(tmpdir, 'test.db'),
            'SECRET_KEY': 'test-secret-key',
            'GEMINI_API_KEY': '',  # Disabled for tests
            'TESTING': True,
        })
        
        yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def session_client(client):
    """Create test client with a session cookie."""
    # Make a first request to get a session
    client.get('/api/health')
    return client
