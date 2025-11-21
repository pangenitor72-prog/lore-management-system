import pytest
import asyncio
from src.broadcaster import Broadcaster, broadcaster as global_broadcaster
from src.auditor_agent import AuditorAgent, Contradiction
from src.query_agent import QueryAgent
from src.database import Database, get_db, get_db_connection
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
import sqlite3
import os
import json

# Import the FastAPI app directly for testing
from src.api import app

# Ensure that the database module uses a temporary file-based DB for tests
@pytest.fixture(scope="function")
def test_db_path():
    """Creates a temporary database file for a test session and ensures schema exists."""
    # Use a fixed name for simplicity in debugging and to ensure it's in a writable directory
    db_path = "test_broadcast_db.sqlite3"
    if os.path.exists(db_path):
        os.unlink(db_path)

    # Create tables in the new DB file
    # The connection needs to be sharable across threads for the test to work
    conn = sqlite3.connect(db_path, check_same_thread=False)
    Database.create_tables(conn)
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def mock_db_connection(test_db_path):
    """Fixture that provides a connection to the temporary file-based test DB."""
    conn = sqlite3.connect(test_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

@pytest.fixture
def api_client(test_db_path):
    """
    Test client for the FastAPI app that uses a temporary file-based database.
    This allows the database to be shared between the main test thread and
    application worker threads, which is not possible with an in-memory DB.
    """
    def override_get_db_connection():
        # Each part of the app gets its own connection to the same file.
        # check_same_thread=False is critical for threaded access.
        conn = sqlite3.connect(test_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row # Ensure rows can be accessed by column name
        return conn

    app.dependency_overrides[get_db_connection] = override_get_db_connection
    
    def override_get_db():
        conn = override_get_db_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client
    
    # Clean up the overrides after the test
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def mock_gemini_models():
    """Mocks the Gemini API models to prevent actual API calls."""
    with patch("google.generativeai.GenerativeModel") as mock_gen_model:
        mock_flash = MagicMock()
        mock_pro = MagicMock()

        # Mock generate_content for flash model (contradiction detection)
        mock_flash.generate_content.return_value = AsyncMock(text=json.dumps([
            {"type": "TEST_CONTRADICTION", "severity": "LOW", "description": "Test AI contradiction", "evidence_a": {}, "evidence_b": {}}
        ]))
        
        # Mock generate_content for pro model (scoring and resolution)
        mock_pro.generate_content.return_value = AsyncMock(text=json.dumps(
            {"confidence": 0.9, "reasoning": "Mock reasoning", "possible_resolutions": ["Mock resolution"]}
        ))

        # Assign the mock instances to the return value of GenerativeModel
        mock_gen_model.side_effect = lambda model_name: {
            "gemini-2.5-flash": mock_flash,
            "gemini-2.5-pro": mock_pro,
            "gemini-1.5-flash": mock_flash, # For QueryAgent
        }.get(model_name)
        
        yield

@pytest.fixture
def auditor_agent(test_db_path):
    """Fixture for AuditorAgent that uses the file-based test database."""
    def get_test_db_connection():
        conn = sqlite3.connect(test_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    return AuditorAgent(get_test_db_connection, "mock_gemini_key")

@pytest.fixture
def query_agent(test_db_path):
    """Fixture for QueryAgent that uses the file-based test database."""
    def get_test_db_connection():
        conn = sqlite3.connect(test_db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    return QueryAgent(get_test_db_connection, "mock_gemini_key")

@pytest.mark.asyncio
async def test_broadcaster_publish_subscribe():
    """
    Tests that a message published to a channel is received by a subscriber.
    """
    local_broadcaster = Broadcaster() # Use a local instance for isolated testing
    test_channel = "test_channel"
    test_message = {"data": "hello world"}

    # Subscribe to the channel
    queue = await local_broadcaster.subscribe(test_channel)

    # Publish a message
    await local_broadcaster.publish(test_channel, test_message)

    # Wait for the message in the subscriber's queue
    received_message = await asyncio.wait_for(queue.get(), timeout=1)

    assert received_message == test_message

    # Unsubscribe
    local_broadcaster.unsubscribe(test_channel, queue)
    assert queue not in local_broadcaster._subscribers[test_channel]

@pytest.mark.asyncio
async def test_broadcaster_no_subscribers():
    """
    Tests that publishing to a channel with no subscribers doesn't raise an error.
    """
    local_broadcaster = Broadcaster()
    test_channel = "non_existent_channel"
    test_message = {"data": "should not be received"}

    await local_broadcaster.publish(test_channel, test_message)
    # No assertion needed, just ensure no exception is raised

@pytest.mark.asyncio
async def test_broadcaster_multiple_subscribers():
    """
    Tests that a message published to a channel is received by multiple subscribers.
    """
    local_broadcaster = Broadcaster()
    test_channel = "multi_sub_channel"
    test_message = {"data": "multi-cast message"}

    queue1 = await local_broadcaster.subscribe(test_channel)
    queue2 = await local_broadcaster.subscribe(test_channel)

    await local_broadcaster.publish(test_channel, test_message)

    received_message1 = await asyncio.wait_for(queue1.get(), timeout=1)
    received_message2 = await asyncio.wait_for(queue2.get(), timeout=1)

    assert received_message1 == test_message
    assert received_message2 == test_message

    local_broadcaster.unsubscribe(test_channel, queue1)
    local_broadcaster.unsubscribe(test_channel, queue2)

@pytest.mark.asyncio
async def test_global_broadcaster_instance():
    """
    Tests that the global broadcaster instance is accessible and functional.
    """
    test_channel = "global_test_channel"
    test_message = {"data": "global message"}

    queue = await global_broadcaster.subscribe(test_channel)
    await global_broadcaster.publish(test_channel, test_message)
    
    received_message = await asyncio.wait_for(queue.get(), timeout=1)
    assert received_message == test_message
    
    global_broadcaster.unsubscribe(test_channel, queue)


@pytest.mark.asyncio
async def test_auditor_agent_publishes_on_persist_contradiction(auditor_agent, mock_db_connection):
    """
    Tests that AuditorAgent publishes a 'new_contradiction' event when a contradiction is persisted.
    """
    # Setup - add dummy entity
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("entity-1", "Character", "Test Entity 1", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("entity-2", "Character", "Test Entity 2", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    mock_db_connection.commit()

    test_contradiction_data = {
        "type": "TEST_CONTRADICTION",
        "severity": "HIGH",
        "description": "This is a test contradiction.",
        "entity_ids": ["entity-1", "entity-2"],
        "evidence": {"key": "value"},
        "confidence": 0.95,
        "scoring_reasoning": "Test scoring",
        "possible_resolutions": ["Test resolution"]
    }
    entity_a = {"canon_id": "entity-1"}
    entity_b = {"canon_id": "entity-2"}

    # Subscribe to the auditor_events channel
    queue = await global_broadcaster.subscribe("auditor_events")
    await auditor_agent.persist_contradiction(test_contradiction_data, entity_a, entity_b)

    # The publish call is wrapped in asyncio.create_task, so we need to yield to event loop
    await asyncio.sleep(0.01) # Give a brief moment for the task to run

    received_event = await asyncio.wait_for(queue.get(), timeout=1)

    assert received_event["type"] == "new_contradiction"
    assert received_event["contradiction"]["type"] == "TEST_CONTRADICTION"
    assert received_event["contradiction"]["severity"] == "HIGH"
    assert received_event["contradiction"]["description"] == "This is a test contradiction."
    assert "id" in received_event["contradiction"]
    
    global_broadcaster.unsubscribe("auditor_events", queue)

@pytest.mark.asyncio
async def test_auditor_agent_publishes_on_ai_audit_completion(auditor_agent, mock_db_connection):
    """
    Tests that AuditorAgent publishes an 'audit_progress' event upon AI audit completion.
    """
    # Setup: Ensure some entities exist for analyze_all_entities to run
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("char-1", "Character", "Char 1", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("char-2", "Character", "Char 2", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    mock_db_connection.commit()

    queue = await global_broadcaster.subscribe("auditor_events")

    # Call the method that triggers the event
    await auditor_agent.analyze_all_entities(limit=2) # Limit to avoid excessive mocks

    # This can publish multiple events, we need to find the right one
    while True:
        received_event = await asyncio.wait_for(queue.get(), timeout=2)
        if received_event.get("type") == "audit_progress" and "AI audit complete" in received_event.get("message", ""):
            break

    assert received_event["type"] == "audit_progress"
    assert "AI audit complete" in received_event["message"]
    assert "total_contradictions_found" in received_event
    
    global_broadcaster.unsubscribe("auditor_events", queue)


@pytest.mark.asyncio
async def test_auditor_agent_publishes_on_rule_based_audit_completion(auditor_agent):
    """
    Tests that AuditorAgent publishes an 'audit_progress' event upon rule-based audit completion.
    """
    queue = await global_broadcaster.subscribe("auditor_events")

    # Call the method that triggers the event
    await auditor_agent.run_full_audit()

    await asyncio.sleep(0.01) # Allow task to run

    received_event = await asyncio.wait_for(queue.get(), timeout=1)

    assert received_event["type"] == "audit_progress"
    assert "Rule-based audit complete" in received_event["message"]
    assert "summary" in received_event
    
    global_broadcaster.unsubscribe("auditor_events", queue)


@pytest.mark.asyncio
async def test_query_agent_publishes_on_query_completion(query_agent):
    """
    Tests that QueryAgent publishes a 'query_completed' event after processing a query.
    """
    # Mock WebSocket for the handle_websocket method
    mock_websocket = AsyncMock()
    mock_websocket.receive_text.side_effect = ["Who is the king?", asyncio.CancelledError] # Simulate one query then disconnect
    mock_websocket.send_text.return_value = None

    # Mock the LLM response for the ask method
    with patch.object(query_agent.chat, 'send_message', return_value=MagicMock(text="The king is Arthur.")) as mock_send_message:
        queue = await global_broadcaster.subscribe("query_events")

        # Run the handle_websocket in a task, as it's an infinite loop
        task = asyncio.create_task(query_agent.handle_websocket(mock_websocket, "test_client"))

        try:
            # We need to wait for the query to be processed and event published
            await asyncio.sleep(0.1)
            
            received_event = await asyncio.wait_for(queue.get(), timeout=1)

            assert received_event["type"] == "query_completed"
            assert received_event["query"] == "Who is the king?"
            assert received_event["response_snippet"] == "The king is Arthur."
            assert "timestamp" in received_event

            mock_send_message.assert_called_once_with("Who is the king?")

        except asyncio.TimeoutError:
            pytest.fail("QueryAgent did not publish query_completed event in time.")
        except asyncio.CancelledError:
            pass # Expected from receive_text.side_effect
        finally:
            task.cancel()
            global_broadcaster.unsubscribe("query_events", queue)


@pytest.mark.asyncio
async def test_websocket_auditor_endpoint_receives_events(api_client, auditor_agent, mock_db_connection):
    """
    Tests that the /ws/auditor WebSocket endpoint correctly receives and forwards
    events published to the 'auditor_events' channel.
    """
    # Setup - add dummy entity
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("entity-A", "Character", "Entity A", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    Database.execute(mock_db_connection, "INSERT INTO entities (canon_id, entity_type, canonical_name, approval_status, confidence_level, party_knowledge, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("entity-B", "Character", "Entity B", "APPROVED", "CONFIRMED", "KNOWN", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))
    mock_db_connection.commit()

    # The 'auditor_agent' fixture is a separate instance from the one used by the FastAPI app.
    # To test the websocket, we must trigger an action that causes the app's
    # own broadcaster to publish. The most reliable way is to publish directly.
    # However, for an integration test like this, we'll assume the fixture setup
    # correctly injects a usable agent, and we'll call its methods.

    # Connect to the WebSocket endpoint
    with api_client.websocket_connect("/ws/auditor") as websocket:
        
        # 1. Test 'new_contradiction' event
        test_contradiction_data = { "type": "WS_TEST", "description": "WebSocket test contradiction." }
        entity_a = {"canon_id": "entity-A"}
        entity_b = {"canon_id": "entity-B"}

        # This call will run in a thread, persist to the file DB, and then broadcast.
        # The websocket, running in the main thread, should receive the event.
        await auditor_agent.persist_contradiction(test_contradiction_data, entity_a, entity_b)

        # Wait for the message to be received by the WebSocket client
        received_message = websocket.receive_json()
        assert received_message["type"] == "new_contradiction"
        assert received_message["contradiction"]["type"] == "WS_TEST"
        assert received_message["contradiction"]["description"] == "WebSocket test contradiction."

        # 2. Test 'audit_progress' event from rule-based audit
        await auditor_agent.run_full_audit()
        received_message_2 = websocket.receive_json()
        assert received_message_2["type"] == "audit_progress"
        assert "Rule-based audit complete" in received_message_2["message"]

