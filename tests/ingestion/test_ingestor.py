import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion.ingestor import LoreIngestor
from src.services.extraction_service import ExtractionService
from src.services.embedding_service import EmbeddingService
from src.db.neo4j_adapter import Neo4jDatabase

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_extraction_service():
    """Fixture for a mock ExtractionService."""
    service = AsyncMock(spec=ExtractionService)
    service.extract_graph_from_chunk.return_value = {
        "nodes": [{"id": "mock_node", "label": "Character", "properties": {"description": "A test node", "content": "Narrative text"}}],
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
def mock_neo4j_db():
    """Fixture for a mock Neo4jDatabase."""
    db = AsyncMock(spec=Neo4jDatabase)
    db.execute = AsyncMock()
    return db


@pytest.fixture
def ingestor(mock_extraction_service, mock_embedding_service, mock_neo4j_db):
    """Fixture to create a LoreIngestor instance with mock dependencies."""
    ingestor = LoreIngestor(
        db=mock_neo4j_db,
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


async def test_save_to_neo4j_with_embeddings(ingestor, mock_neo4j_db, mock_embedding_service):
    """Test saving data to Neo4j, including embedding generation."""
    data_to_save = {
        "nodes": [{"id": "Node1", "label": "Character", "properties": {"content": "Some lore text"}}],
        "relationships": [{"source": "Node1", "target": "Node2", "type": "RELATED_TO"}]
    }
    
    # Don't mock the loop/executor. Let the default loop run the mock function in a thread.
    result = await ingestor.save_to_neo4j(data_to_save, "test_file.txt")

    assert result["nodes_saved"] == 1
    # rels_saved depends on if valid nodes exist. Node2 is target but not defined in nodes list.
    # The code handles rels separately.
    assert result["relationships_saved"] == 1
    
    # Check that the embedding service was called
    mock_embedding_service.embed_entity.assert_called_once()
    
    # Check that db.execute was called
    # Calls: 1 for nodes, 1 for rels, 1 for file node
    assert mock_neo4j_db.execute.call_count >= 3


async def test_save_to_neo4j_no_embeddings(ingestor, mock_neo4j_db, mock_embedding_service):
    """Test saving data when embeddings are disabled."""
    ingestor.enable_embeddings = False
    
    data_to_save = {
        "nodes": [{"id": "Node1", "label": "Character", "properties": {"content": "Some lore text"}}],
        "relationships": []
    }
    
    result = await ingestor.save_to_neo4j(data_to_save, "test_file.txt")
    
    assert result["nodes_saved"] == 1
    
    # Embedding service should NOT be called
    mock_embedding_service.embed_entity.assert_not_called()
    
    # Check calls to execute
    calls = mock_neo4j_db.execute.call_args_list
    
    # Check that properties in the node query do not contain 'embedding'
    found_node_call = False
    for call in calls:
        query, params = call.args
        if "items" in params:
            items = params["items"]
            if len(items) > 0 and items[0]["name"] == "Node1":
                found_node_call = True
                assert "embedding" not in items[0]["props"]
                break
    
    assert found_node_call


async def test_save_to_neo4j_missing_content(ingestor, mock_neo4j_db):
    """Test that entities without content are skipped."""
    data_to_save = {
        "nodes": [
            {"id": "Node1", "label": "Character", "properties": {"content": "Some lore text."}},
            {"id": "Node2", "label": "Character", "properties": {}} # Missing content
        ],
        "relationships": []
    }

    result = await ingestor.save_to_neo4j(data_to_save, "test_file.txt")

    # Node2 should be skipped
    assert result["nodes_saved"] == 1
    
    # Check that only Node1 was saved
    call_args = mock_neo4j_db.execute.call_args_list
    found = False
    for call in call_args:
        query, params = call.args
        if "items" in params:
            items = params["items"]
            if len(items) == 1 and items[0]["name"] == "Node1":
                found = True
                break
    assert found


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
    # Check for overlap
    overlap_sample = chunks[1][:LoreIngestor.CHUNK_OVERLAP // 2]
    assert overlap_sample in chunks[0]
