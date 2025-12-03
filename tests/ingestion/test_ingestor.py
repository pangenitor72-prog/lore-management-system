import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion.ingestor import LoreIngestor
from src.services.extraction_service import ExtractionService
from src.services.embedding_service import EmbeddingService

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_extraction_service():
    """Fixture for a mock ExtractionService."""
    service = AsyncMock(spec=ExtractionService)
    service.extract_graph_from_chunk.return_value = {
        "nodes": [{"id": "mock_node", "label": "Character", "properties": {"description": "A test node"}}],
        "relationships": [{"source": "mock_node", "target": "another_node", "type": "KNOWS"}]
    }
    return service


@pytest.fixture
def mock_embedding_service():
    """Fixture for a mock EmbeddingService."""
    service = MagicMock(spec=EmbeddingService)
    service.embed_entity.return_value = [0.1, 0.2, 0.3]
    return service


@pytest.fixture
def mock_neo4j_driver():
    """Fixture for a mock Neo4j driver."""
    driver = MagicMock()
    # Mock the session context manager
    session = AsyncMock()
    driver.session.return_value.__aenter__.return_value = session
    driver.session.return_value.__aexit__.return_value = None
    session.run.return_value = AsyncMock() # Mock the run method
    return driver


@pytest.fixture
def ingestor(mock_extraction_service, mock_embedding_service, mock_neo4j_driver):
    """Fixture to create a LoreIngestor instance with mock dependencies."""
    ingestor = LoreIngestor(
        neo4j_driver=mock_neo4j_driver,
        extraction_service=mock_extraction_service,
        embedding_service=mock_embedding_service
    )
    return ingestor


async def test_process_file_content(ingestor, mock_extraction_service):
    """Test that file content is chunked and sent to the extraction service."""
    test_content = "This is a test content string that will be processed."
    
    # We expect one chunk, so one call
    result = await ingestor.process_file_content("test.txt", test_content)
    
    mock_extraction_service.extract_graph_from_chunk.assert_called_once()
    
    # Check that the result contains the merged data from the mock service
    assert result["data"]["nodes"][0]["id"] == "mock_node"
    assert len(result["data"]["nodes"]) == 1
    assert result["chunks_count"] == 1


async def test_process_file_content_multiple_chunks(ingestor, mock_extraction_service):
    """Test that long content is split into multiple chunks."""
    # Create content longer than the chunk size
    long_content = "A" * (LoreIngestor.MAX_CHUNK_SIZE + 1)
    
    await ingestor.process_file_content("long_test.txt", long_content)
    
    # Expect more than one call to the extraction service
    assert mock_extraction_service.extract_graph_from_chunk.call_count > 1


async def test_save_to_neo4j_with_embeddings(ingestor, mock_neo4j_driver, mock_embedding_service):
    """Test saving data to Neo4j, including embedding generation."""
    data_to_save = {
        "nodes": [{"id": "Node1", "label": "Character", "properties": {}}],
        "relationships": [{"source": "Node1", "target": "Node2", "type": "RELATED_TO"}]
    }
    
    # Don't mock the loop/executor. Let the default loop run the mock function in a thread.
    result = await ingestor.save_to_neo4j(data_to_save, "test_file.txt")

    assert result["nodes_saved"] == 1
    assert result["rels_saved"] == 1
    
    # Check that the embedding service was called
    mock_embedding_service.embed_entity.assert_called_once()
    
    # Check that the driver's session was used
    mock_neo4j_driver.session.assert_called()
    
    # Get the session mock to check the run calls
    session_mock = mock_neo4j_driver.session.return_value.__aenter__.return_value
    
    # There should be calls for nodes, relationships, and the file source
    assert session_mock.run.call_count >= 2


async def test_save_to_neo4j_no_embeddings(ingestor, mock_neo4j_driver, mock_embedding_service):
    """Test saving data when embeddings are disabled."""
    ingestor.enable_embeddings = False
    
    data_to_save = {
        "nodes": [{"id": "Node1", "label": "Character", "properties": {}}],
        "relationships": []
    }
    
    result = await ingestor.save_to_neo4j(data_to_save, "test_file.txt")
    
    assert result["nodes_saved"] == 1
    
    # Embedding service should NOT be called
    mock_embedding_service.embed_entity.assert_not_called()
    
    session_mock = mock_neo4j_driver.session.return_value.__aenter__.return_value
    # Check that properties in the node query do not contain 'embedding'
    
    # Find the call for saving nodes
    node_params = None
    for call in session_mock.run.call_args_list:
        args, kwargs = call
        if "UNWIND $items AS item" in args[0] and "MERGE (n:" in args[0]:
            # Parameters are usually the second positional argument
            if len(args) > 1:
                node_params = args[1]
            else:
                node_params = kwargs
            break
    
    assert node_params is not None
    # Depending on how it was called, it might be directly the dict or wrapped
    items = node_params.get('items')
    assert items is not None
    assert "embedding" not in items[0]['props']


def test_chunk_text_short(ingestor):
    """Test chunking for text shorter than MAX_CHUNK_SIZE."""
    text = "This is a short text."
    chunks = ingestor.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_chunk_text_long(ingestor):
    """Test chunking for text longer than MAX_CHUNK_SIZE."""
    long_text = "word " * LoreIngestor.MAX_CHUNK_SIZE
    chunks = ingestor.chunk_text(long_text)
    assert len(chunks) > 1
    # Check for overlap - verifying that the start of the second chunk 
    # (which is the overlap region) is present at the end of the first chunk.
    # We check a subset to avoid issues with stripping/boundary spaces.
    overlap_sample = chunks[1][:LoreIngestor.CHUNK_OVERLAP // 2]
    assert overlap_sample in chunks[0]
