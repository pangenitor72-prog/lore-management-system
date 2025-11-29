import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from src.api import app
from src.neo4j_adapter import Neo4jDatabase

# Mock Neo4j Database
@pytest.fixture
def mock_neo4j_db():
    mock_db = AsyncMock(spec=Neo4jDatabase)
    # Default behavior for common methods
    mock_db.execute.return_value = []
    mock_db.list_indexes.return_value = [{"name": "entity_embeddings"}]
    return mock_db

# Override dependency
@pytest.fixture
def client(mock_neo4j_db):
    # Patch the state
    app.state.neo4j_db = mock_neo4j_db
    # Also patch agents if needed, or let them be mocks
    app.state.query_agent = AsyncMock()
    app.state.auditor = AsyncMock()
    
    with TestClient(app) as c:
        yield c
