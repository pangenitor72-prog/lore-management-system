import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from src.lms.db.neo4j_adapter import Neo4jDatabase

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_driver():
    """Fixture to create a mock sync Neo4j driver."""
    driver = MagicMock()
    driver.verify_connectivity = MagicMock()

    # Mock session context manager
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute_write = MagicMock(return_value=[])
    driver.session = MagicMock(return_value=mock_session)

    return driver


@pytest.fixture
def db_adapter():
    """Fixture to create a Neo4jDatabase instance."""
    return Neo4jDatabase(uri="bolt://mock", auth=("user", "pass"))


async def test_connect(db_adapter, mock_driver):
    """Test that connect establishes a driver and verifies connectivity."""

    # Helper to run sync functions as if they were async
    async def mock_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs) if callable(func) else func

    with patch.object(db_adapter, '_build_driver', return_value=mock_driver):
        with patch('asyncio.to_thread', side_effect=mock_to_thread):
            await db_adapter.connect()

    assert db_adapter._driver is not None


async def test_connect_retry_on_failure(db_adapter):
    """Test that connect retries on failure."""
    call_count = 0

    def failing_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("Connection failed")
        mock_driver = MagicMock()
        mock_driver.verify_connectivity = MagicMock()
        return mock_driver

    with patch.object(db_adapter, '_build_driver', side_effect=failing_then_succeed):
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await db_adapter.connect(retries=3, base_delay=0.01)

    assert call_count == 2
    assert db_adapter._driver is not None


async def test_execute_creates_session(db_adapter, mock_driver):
    """Test that execute uses session with proper context management."""
    db_adapter._driver = mock_driver

    # Mock the session's execute_write to return expected data
    mock_result = [{"name": "test"}]
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=None)
    mock_session.execute_write = MagicMock(return_value=mock_result)
    mock_driver.session = MagicMock(return_value=mock_session)

    result = await db_adapter.execute("MATCH (n) RETURN n", {})

    mock_driver.session.assert_called_once_with(database="neo4j")
    assert result == mock_result


async def test_close_driver(db_adapter, mock_driver):
    """Test that close properly shuts down the driver."""
    db_adapter._driver = mock_driver

    await db_adapter.close()

    mock_driver.close.assert_called_once()
    assert db_adapter._driver is None


def test_scheme_detection(db_adapter):
    """Test URI scheme detection."""
    adapter_bolt = Neo4jDatabase(uri="bolt://localhost:7687", auth=("u", "p"))
    adapter_ssl = Neo4jDatabase(uri="neo4j+s://aura.neo4j.io", auth=("u", "p"))
    adapter_ssc = Neo4jDatabase(uri="neo4j+ssc://private.neo4j.io", auth=("u", "p"))

    assert adapter_bolt._scheme() == "bolt"
    assert adapter_ssl._scheme() == "neo4j+s"
    assert adapter_ssc._scheme() == "neo4j+ssc"


def test_ssl_scheme_detection(db_adapter):
    """Test SSL scheme detection."""
    adapter_bolt = Neo4jDatabase(uri="bolt://localhost:7687", auth=("u", "p"))
    adapter_ssl = Neo4jDatabase(uri="neo4j+s://aura.neo4j.io", auth=("u", "p"))

    assert adapter_bolt._is_ssl_scheme() is False
    assert adapter_ssl._is_ssl_scheme() is True


def test_auth_tuple_handling():
    """Test that auth can be passed as tuple or separate args."""
    # Auth as tuple
    adapter1 = Neo4jDatabase(uri="bolt://mock", auth=("user", "pass"))
    assert adapter1.auth == ("user", "pass")

    # Auth as separate args
    adapter2 = Neo4jDatabase(uri="bolt://mock", user="user", password="pass")
    assert adapter2.auth == ("user", "pass")

    # User as tuple (legacy support)
    adapter3 = Neo4jDatabase(uri="bolt://mock", user=("user", "pass"))
    assert adapter3.auth == ("user", "pass")


def test_connection_test_method(db_adapter, mock_driver):
    """Test the synchronous test_connection method."""
    with patch.object(db_adapter, '_build_driver', return_value=mock_driver):
        result = db_adapter.test_connection()
        assert result is True


def test_connection_test_method_failure(db_adapter):
    """Test test_connection returns False on failure."""
    def fail_build():
        raise Exception("Connection failed")

    with patch.object(db_adapter, '_build_driver', side_effect=fail_build):
        result = db_adapter.test_connection()
        assert result is False


# ============================================================================
# SKIPPED TESTS - Methods moved to other modules
# ============================================================================

@pytest.mark.skip(reason="create_vector_index moved to src/lms/db/schema_init.py")
async def test_create_vector_index():
    pass


@pytest.mark.skip(reason="store_embedding moved to src/lms/services/vector_service.py")
async def test_store_embedding():
    pass


@pytest.mark.skip(reason="store_embeddings_batch moved to src/lms/services/vector_service.py")
async def test_store_embeddings_batch():
    pass


@pytest.mark.skip(reason="vector_search moved to src/lms/services/vector_service.py")
async def test_vector_search():
    pass


@pytest.mark.skip(reason="validate_identifier not on Neo4jDatabase - use parameterized queries instead")
async def test_validate_identifier():
    pass
