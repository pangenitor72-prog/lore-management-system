"""
Test script for Lore Management System API
Tests basic entity creation and retrieval
"""

import sys
sys.path.insert(0, '/home/claude/lore-system/src')

from database import Database
from models import EntityCreate, EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge

# Initialize database
db = Database("data/lore.db")
print("=" * 60)
print("LORE MANAGEMENT SYSTEM - API FOUNDATION TEST")
print("=" * 60)

# Test 1: Create an entity directly in database
print("\n[TEST 1] Creating test entity...")
canon_id = "character-test001"

try:
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
        
        # Add alias
        conn.execute("""
            INSERT INTO aliases (canon_id, alias) VALUES (?, ?)
        """, (canon_id, "TC"))
        
        # Add field
        conn.execute("""
            INSERT INTO approved_fields (canon_id, field_key, field_value)
            VALUES (?, ?, ?)
        """, (canon_id, "age", "30"))
    
    print("✓ Entity created successfully")
    
except Exception as e:
    print(f"✗ Failed to create entity: {e}")
    sys.exit(1)

# Test 2: Retrieve entity
print("\n[TEST 2] Retrieving entity...")
try:
    entity = db.fetch_one("SELECT * FROM entities WHERE canon_id = ?", (canon_id,))
    if entity:
        print(f"✓ Entity retrieved: {entity['canonical_name']}")
        print(f"  - Type: {entity['entity_type']}")
        print(f"  - Status: {entity['approval_status']}")
        print(f"  - Confidence: {entity['confidence_level']}")
    else:
        print("✗ Entity not found")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Failed to retrieve entity: {e}")
    sys.exit(1)

# Test 3: Query aliases
print("\n[TEST 3] Retrieving aliases...")
try:
    aliases = db.fetch_all("SELECT alias FROM aliases WHERE canon_id = ?", (canon_id,))
    print(f"✓ Found {len(aliases)} alias(es): {[a['alias'] for a in aliases]}")
    
except Exception as e:
    print(f"✗ Failed to retrieve aliases: {e}")
    sys.exit(1)

# Test 4: Query fields
print("\n[TEST 4] Retrieving approved fields...")
try:
    fields = db.fetch_all("""
        SELECT field_key, field_value FROM approved_fields WHERE canon_id = ?
    """, (canon_id,))
    print(f"✓ Found {len(fields)} field(s):")
    for f in fields:
        print(f"  - {f['field_key']}: {f['field_value']}")
    
except Exception as e:
    print(f"✗ Failed to retrieve fields: {e}")
    sys.exit(1)

# Test 5: List all entities
print("\n[TEST 5] Listing all entities...")
try:
    entities = db.fetch_all("SELECT canon_id, canonical_name FROM entities")
    print(f"✓ Found {len(entities)} entity/entities in database:")
    for e in entities:
        print(f"  - {e['canon_id']}: {e['canonical_name']}")
    
except Exception as e:
    print(f"✗ Failed to list entities: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL TESTS PASSED ✓")
print("=" * 60)
print("\nDatabase foundation is working correctly.")
print("Next step: Start API server and test HTTP endpoints.")
