import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sqlite3
from src.api import app
from src.database import get_db, get_db_connection

TABLES_TO_CLEAR = [
    "entities", "aliases", "approved_fields", "relationships",
    "revisions", "contradictions", "contradiction_entities",
    "triage_analysis", "agent_chat_log"
]

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """
    Runs once per test session. Deletes the old DB and creates a new one
    with the correct schema. This solves the file lock PermissionError.
    """
    db_path = Path(__file__).parent / ".." / "data/lore.db"
    if db_path.exists():
        db_path.unlink()
    
    # Bootstrap schema by instantiating Database class
    from src.database import Database
    _ = Database()
    
    yield # Let the tests run

@pytest.fixture(scope="function")
def api_client():
    """
    Provides a FastAPI TestClient where the database is wiped clean for each test.
    """
    # This connection is used to wipe the tables
    conn = get_db_connection()
    cursor = conn.cursor()
    for table in TABLES_TO_CLEAR:
        cursor.execute(f"DELETE FROM {table};")
    conn.commit()
    conn.close()

    # This override will provide a NEW connection for each 'request' from the test client.
    def override_get_db():
        connection = get_db_connection()
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()