import pytest
import os
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from src.api.routes import app
from src.db.neo4j_adapter import Neo4jDatabase
from src.db.mock_adapter import InMemoryMockDatabase
from src.api.dependencies import get_neo4j_db


# Set test environment variables before importing app
@pytest.fixture(scope="session", autouse=True)
def set_test_env_vars():
    """Set test environment variables for all tests."""
    test_env = {
        "NEO4J_URI": "bolt://test-localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "test_password",
        "GEMINI_API_KEY": "",  # Optional, not set for tests
    }
    
    # Store original values
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original values
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


# Mock Neo4j Database
@pytest.fixture
def mock_neo4j_db():
    return InMemoryMockDatabase()


# Override dependency and lifespan for testing
@pytest.fixture
def client(mock_neo4j_db):
    # Patch the get_neo4j_db dependency to return our mock
    app.dependency_overrides[get_neo4j_db] = lambda: mock_neo4j_db

    # Patch the connect_neo4j_with_timeout within src.api.routes to avoid real connection attempts
    # Also patch Neo4jDatabase to prevent any real database instantiation
    with patch("src.api.routes.connect_neo4j_with_timeout", AsyncMock(return_value=True)), \
         patch("src.api.routes.Neo4jDatabase", return_value=mock_neo4j_db):
        # Pre-set all app.state attributes that the lifespan would normally set
        # This ensures health checks pass even if lifespan partially runs
        app.state.neo4j_db = mock_neo4j_db
        app.state.query_agent = AsyncMock()
        app.state.auditor = AsyncMock()
        app.state.ai_enabled = False  # Disable AI features for faster tests
        app.state.vector_search_enabled = True  # Pretend vector index exists

        with TestClient(app) as c:
            yield c
    
    # Clean up overrides after test
    app.dependency_overrides = {}
