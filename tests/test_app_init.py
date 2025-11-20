import pytest
from pathlib import Path
import sqlite3
from src.database import Database, get_db_connection

def test_db_bootstrap_on_init():
    """
    Tests that the database file is created and the schema is applied
    when the Database class is instantiated.
    """
    db_path = Path(__file__).parent.parent / "data/lore.db"
    
    # 1. Delete the database file to ensure a clean slate
    if db_path.exists():
        db_path.unlink()
    
    # 2. Trigger database initialization
    _ = Database() 

    # 3. Verify the database file now exists
    assert db_path.exists(), "Database file was not created on app initialization."

    # 4. Verify the schema was loaded correctly by connecting to the new file
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row['name'] for row in cursor.fetchall()}
        
    required_tables = {
        "entities", "approved_fields", "aliases", "relationships",
        "revisions", "contradictions", "contradiction_entities",
        "triage_analysis", "agent_chat_log"
    }
    assert required_tables.issubset(tables), f"Missing tables: {required_tables - tables}"