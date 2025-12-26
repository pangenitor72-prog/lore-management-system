import pytest
from unittest.mock import AsyncMock, patch

from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.services.embedding_orchestrator import EmbeddingOrchestrator

# Use the standard embedding dimension
EMBEDDING_DIMENSION = EmbeddingOrchestrator.EMBEDDING_DIMENSION

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_driver():
    """Fixture to create a mock Neo4j driver."""
    driver = AsyncMock()
    # The driver.execute_query is the key method to mock
    driver.execute_query.return_value = ([], {}, [])
    return driver


@pytest.fixture
async def db_adapter(mock_driver):
    """Fixture to create a Neo4jDatabase instance with a mocked driver."""
    with patch('src.lms.db.neo4j_adapter.AsyncGraphDatabase.driver') as mock_async_driver:
        # Prevent the actual driver from being created
        mock_async_driver.return_value = mock_driver
        
        adapter = Neo4jDatabase(uri="bolt://mock", auth=("user", "pass"))
        # Since we are mocking the driver creation, we need to manually set it
        adapter.driver = mock_driver
        
        yield adapter
        
        # Teardown logic if needed
        await adapter.close()


async def test_connect(db_adapter, mock_driver):
    """Test that connect establishes a driver and verifies connectivity."""
    # Reset to simulate initial state
    db_adapter.driver = None 
    
    with patch('src.lms.db.neo4j_adapter.AsyncGraphDatabase.driver') as mock_async_driver:
        mock_async_driver.return_value = mock_driver
        
        await db_adapter.connect()

        # Assert that a new driver was created
        mock_async_driver.assert_called_once_with("bolt://mock", auth=("user", "pass"))
        # Assert that we verified connectivity
        mock_driver.verify_connectivity.assert_called_once()
        assert db_adapter.driver is not None


async def test_create_vector_index(db_adapter, mock_driver):
    """Test the create_vector_index method constructs the correct query."""
    await db_adapter.create_vector_index()

    # Get the call arguments
    call_args, call_kwargs = mock_driver.execute_query.call_args
    query = call_args[0]
    params = call_kwargs['parameters_']

    # Assert that the correct query and params were used
    assert "CREATE VECTOR INDEX entity_embeddings" in query
    assert f"`vector.dimensions`: $dimensions" in query
    assert params["dimensions"] == EMBEDDING_DIMENSION
    assert params["similarity_function"] == "cosine"


async def test_store_embedding(db_adapter, mock_driver):
    """Test the store_embedding method for a single embedding."""
    node_id = "test-node-123"
    embedding = [0.1] * EMBEDDING_DIMENSION
    
    # Mock the return value to simulate a successful update
    mock_driver.execute_query.return_value = ([{"name": "test-node-123"}], {}, [])

    success = await db_adapter.store_embedding(node_id, embedding)

    call_args, call_kwargs = mock_driver.execute_query.call_args
    query = call_args[0]
    params = call_kwargs['parameters_']

    assert success is True
    assert "MATCH (n {canon_id: $node_id})" in query
    assert "SET n.embedding = $embedding" in query
    assert params["node_id"] == node_id
    assert params["embedding"] == embedding


async def test_store_embeddings_batch(db_adapter, mock_driver):
    """Test the store_embeddings_batch method."""
    batch = [{"node_id": "node1", "embedding": [0.1] * EMBEDDING_DIMENSION}]
    
    # Mock return to simulate one node updated
    mock_driver.execute_query.return_value = ([{"updated": 1}], {}, [])

    count = await db_adapter.store_embeddings_batch(batch)

    call_args, call_kwargs = mock_driver.execute_query.call_args
    query = call_args[0]
    params = call_kwargs['parameters_']

    assert count == 1
    assert "UNWIND $items AS item" in query
    assert "MATCH (n {canon_id: item.node_id})" in query
    assert "SET n.embedding = item.embedding" in query
    assert params["items"] == batch


async def test_vector_search(db_adapter, mock_driver):
    """Test the vector_search method."""
    query_embedding = [0.2] * EMBEDDING_DIMENSION
    
    await db_adapter.vector_search(query_embedding, limit=5, min_score=0.8)

    call_args, call_kwargs = mock_driver.execute_query.call_args
    query = call_args[0]
    params = call_kwargs['parameters_']

    assert "CALL db.index.vector.queryNodes($index_name, $limit, $embedding)" in query
    assert "WHERE score >= $min_score" in query
    assert params["index_name"] == "entity_embeddings"
    assert params["limit"] == 5
    assert params["embedding"] == query_embedding
    assert params["min_score"] == 0.8


async def test_validate_identifier_valid(db_adapter):
    """Test that valid identifiers pass."""
    assert db_adapter.validate_identifier("ValidLabel") == "ValidLabel"
    assert db_adapter.validate_identifier("Valid_Label_123") == "Valid_Label_123"
    assert db_adapter.validate_identifier("_Valid") == "_Valid"

async def test_validate_identifier_invalid(db_adapter):
    """Test that invalid identifiers raise ValueError."""
    with pytest.raises(ValueError):
        db_adapter.validate_identifier("Invalid-Label")
    with pytest.raises(ValueError):
        db_adapter.validate_identifier("1Invalid")
    with pytest.raises(ValueError):
        db_adapter.validate_identifier("Invalid Label")
    with pytest.raises(ValueError):
        db_adapter.validate_identifier("`Invalid`")

