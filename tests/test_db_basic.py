import sqlite3
import pytest
from src.database import Database, get_db_connection, db_session # Assuming Database is for schema init, get_db_connection/db_session for operations
from src.models import EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge # For creating valid test data
from datetime import datetime, timezone

@pytest.fixture
def in_memory_db():
    """Provides an in-memory SQLite database for testing."""
    # Use a unique temporary path for each test instance to prevent conflicts
    # For in-memory, a simple :memory: is fine as it's isolated per connection
    conn = get_db_connection(":memory:")
    
    # Initialize schema using the Database utility, passing the in-memory connection path
    db_utility = Database(":memory:") # Initialize Database with the in-memory path to initialize schema
    # The _initialize_schema method in Database class expects to create a connection
    # internally from the db_path, so we need to ensure it's pointing to the :memory: db.
    # However, our refactored Database._initialize_schema uses db_session, which uses DB_PATH
    # or the passed db_path to create a new connection.
    # We should ensure schema is applied to the fixture's connection.

    # Manually apply schema to the fixture's connection
    schema_path = Path(__file__).parent.parent / "data/schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()

    yield conn
    conn.close()

def test_db_connection_and_schema_init(in_memory_db: sqlite3.Connection):
    """Test that the database can connect and schema is initialized."""
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    table_names = [table['name'] for table in tables]
    
    assert "entities" in table_names
    assert "relationships" in table_names
    assert "contradictions" in table_names
    assert "aliases" in table_names
    assert "approved_fields" in table_names
    assert "triage_analysis" in table_names
    assert "agent_chat_log" in table_names

def test_insert_and_fetch_entity(in_memory_db: sqlite3.Connection):
    """Test inserting and fetching an entity."""
    test_canon_id = "char-test1"
    test_entity_type = EntityType.CHARACTER
    test_canonical_name = "Test Character"
    created_at = datetime.now(timezone.utc).isoformat()

    with db_session(db_path=":memory:") as conn: # Ensure operations use the in-memory db
        Database.execute(conn, """
            INSERT INTO entities (
                canon_id, entity_type, canonical_name, approval_status,
                confidence_level, party_knowledge, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_canon_id, test_entity_type.value, test_canonical_name,
            ApprovalStatus.APPROVED.value, ConfidenceLevel.CONFIRMED.value,
            PartyKnowledge.KNOWN.value, created_at, created_at
        ), commit=True)
    
    fetched_entity = Database.fetch_one(in_memory_db, "SELECT * FROM entities WHERE canon_id = ?", (test_canon_id,))
    
    assert fetched_entity is not None
    assert fetched_entity['canon_id'] == test_canon_id
    assert fetched_entity['entity_type'] == test_entity_type.value
    assert fetched_entity['canonical_name'] == test_canonical_name

def test_entity_with_aliases_and_approved_fields(in_memory_db: sqlite3.Connection):
    """Test inserting an entity with aliases and approved fields."""
    test_canon_id = "loc-test1"
    test_entity_type = EntityType.LOCATION
    test_canonical_name = "Test Location"
    created_at = datetime.now(timezone.utc).isoformat()
    test_aliases = ["TL1", "TL_one"]
    test_approved_fields = {"climate": "temperate", "population": "1000"}

    with db_session(db_path=":memory:") as conn:
        Database.execute(conn, """
            INSERT INTO entities (
                canon_id, entity_type, canonical_name, approval_status,
                confidence_level, party_knowledge, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_canon_id, test_entity_type.value, test_canonical_name,
            ApprovalStatus.PENDING.value, ConfidenceLevel.PROBABLE.value,
            PartyKnowledge.RUMORED.value, created_at, created_at
        ), commit=True)

        for alias in test_aliases:
            Database.execute(conn, "INSERT INTO aliases (canon_id, alias) VALUES (?, ?)", (test_canon_id, alias), commit=True)
        
        for key, value in test_approved_fields.items():
            Database.execute(conn, "INSERT INTO approved_fields (canon_id, field_key, field_value) VALUES (?, ?, ?)", (test_canon_id, key, json.dumps(value)), commit=True)

    fetched_entity = Database.fetch_one(in_memory_db, "SELECT * FROM entities WHERE canon_id = ?", (test_canon_id,))
    assert fetched_entity is not None

    fetched_aliases = Database.fetch_all(in_memory_db, "SELECT alias FROM aliases WHERE canon_id = ?", (test_canon_id,))
    assert sorted([a['alias'] for a in fetched_aliases]) == sorted(test_aliases)

    fetched_fields = Database.fetch_all(in_memory_db, "SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?", (test_canon_id,))
    assert len(fetched_fields) == len(test_approved_fields)
    for f in fetched_fields:
        assert json.loads(f['field_value']) == test_approved_fields[f['field_key']]

