"""Pytest configuration and fixtures for MELODYX tests."""
import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def app():
    """Create application for testing."""
    # Create a temp directory for uploads
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ['UPLOAD_FOLDER'] = os.path.join(tmpdir, 'uploads')
        os.environ['DATABASE_URL'] = f'sqlite:///{os.path.join(tmpdir, "test.db")}'
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['GEMINI_API_KEY'] = ''  # Disabled for tests
        
        app = create_app()
        app.config['TESTING'] = True
        
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
