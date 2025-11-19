import pytest
from src.database import Database
from src.models import EntityCreate, EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge

@pytest.fixture(scope="module")
def db():
    """
    Fixture to set up an in-memory SQLite database for testing.
    """
    db = Database(":memory:")
    yield db
    db.close()

def test_create_entity(db):
    """
    Tests creating an entity directly in the database.
    """
    canon_id = "character-test001"
    with db.transaction() as conn:
        conn.execute("""
            INSERT INTO entities (
                canon_id, entity_type, canonical_name,
                approval_status, confidence_level, party_knowledge
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            canon_id, "Character", "Test Character",
            "APPROVED", "CONFIRMED", "KNOWN"
        ))
        conn.execute("INSERT INTO aliases (canon_id, alias) VALUES (?, ?)", (canon_id, "TC"))
        conn.execute("INSERT INTO approved_fields (canon_id, field_key, field_value) VALUES (?, ?, ?)", (canon_id, "age", "30"))
    
    entity = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
    assert entity is not None
    assert entity['canonical_name'] == "Test Character"

def test_retrieve_entity(db):
    """
    Tests retrieving an entity from the database.
    """
    entity = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", ("character-test001",))
    assert entity is not None
    assert entity['canonical_name'] == "Test Character"
    assert entity['entity_type'] == "Character"
    assert entity['approval_status'] == "APPROVED"
    assert entity['confidence_level'] == "CONFIRMED"

def test_retrieve_aliases(db):
    """
    Tests retrieving aliases for an entity.
    """
    aliases = db.fetch_all("SELECT alias FROM aliases WHERE canon_id = ?", ("character-test001",))
    assert len(aliases) == 1
    assert aliases[0]['alias'] == "TC"

def test_retrieve_fields(db):
    """
    Tests retrieving approved fields for an entity.
    """
    fields = db.fetch_all("SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?", ("character-test001",))
    assert len(fields) == 1
    assert fields[0]['field_key'] == "age"
    assert fields[0]['field_value'] == "30"

def test_list_all_entities(db):
    """
    Tests listing all entities in the database.
    """
    entities = db.fetch_all("SELECT canon_id, canonical_name FROM entities")
    assert len(entities) >= 1
