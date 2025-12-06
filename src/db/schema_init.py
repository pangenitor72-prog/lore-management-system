"""
Neo4j Schema Initialization Module
Creates all necessary constraints, indexes, and vector indexes for the LMS database.

Usage:
    python -m src.db.schema_init
    
Or import and call:
    from src.db.schema_init import initialize_schema
    await initialize_schema()
"""

import asyncio
import os
import logging
from typing import List, Tuple, Optional
from dotenv import load_dotenv

from src.db.neo4j_adapter import Neo4jDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# ============================================
# SCHEMA DEFINITIONS
# ============================================

# Uniqueness constraints (prevent duplicate IDs)
UNIQUENESS_CONSTRAINTS = [
    # Entity constraints
    ("entity_canon_id_unique", "Entity", "canon_id"),
    
    # Character constraints  
    ("character_canon_id_unique", "Character", "canon_id"),
    
    # Location constraints
    ("location_canon_id_unique", "Location", "canon_id"),
    
    # Faction constraints
    ("faction_canon_id_unique", "Faction", "canon_id"),
    
    # Event constraints
    ("event_canon_id_unique", "Event", "canon_id"),
    
    # Item constraints
    ("item_canon_id_unique", "Item", "canon_id"),
    
    # Concept constraints
    ("concept_canon_id_unique", "Concept", "canon_id"),
    
    # Contradiction constraints
    ("contradiction_id_unique", "Contradiction", "contradiction_id"),
    
    # ReviewQueue constraints
    ("review_id_unique", "ReviewQueue", "review_id"),
    
    # File source tracking
    ("file_name_unique", "File", "name"),
    
    # Session constraints (for AIRPG)
    ("session_id_unique", "Session", "session_id"),
    
    # Instance constraints (for AIRPG)
    ("instance_id_unique", "Instance", "instance_id"),
]

# Performance indexes (for fast lookups)
PERFORMANCE_INDEXES = [
    # Entity indexes
    ("idx_entity_name", "Entity", "name"),
    ("idx_entity_type", "Entity", "entity_type"),
    ("idx_entity_confidence", "Entity", "confidence_level"),
    ("idx_entity_party_knowledge", "Entity", "party_knowledge"),
    
    # Character indexes
    ("idx_character_name", "Character", "name"),
    ("idx_character_race", "Character", "race"),
    
    # Location indexes
    ("idx_location_name", "Location", "name"),
    
    # Faction indexes
    ("idx_faction_name", "Faction", "name"),
    
    # Contradiction indexes
    ("idx_contradiction_status", "Contradiction", "status"),
    ("idx_contradiction_severity", "Contradiction", "severity"),
    ("idx_contradiction_type", "Contradiction", "contradiction_type"),
    
    # ReviewQueue indexes
    ("idx_review_status", "ReviewQueue", "status"),
    ("idx_review_session", "ReviewQueue", "session_id"),
    
    # Session indexes (for AIRPG)
    ("idx_session_id", "Session", "session_id"),
    
    # Instance indexes (for AIRPG)
    ("idx_instance_session", "Instance", "session_id"),
]

# Composite indexes (for complex queries)
COMPOSITE_INDEXES = [
    # Entity lookup by name and type
    ("idx_entity_name_type", "Entity", ["name", "entity_type"]),
    
    # Contradiction lookup by status and severity
    ("idx_contradiction_status_severity", "Contradiction", ["status", "severity"]),
]

# Full-text indexes (for search)
FULLTEXT_INDEXES = [
    # Entity full-text search
    ("entity_fulltext", ["Entity", "Character", "Location", "Faction", "Event", "Item", "Concept"], 
     ["name", "description", "content"]),
]

# Vector index configuration
VECTOR_INDEX_CONFIG = {
    "index_name": "entity_embeddings",
    "label": "Entity",
    "property_name": "embedding",
    "dimensions": 768,   # Gemini text-embedding-004 uses 768-dim vectors
    "similarity_function": "cosine"
}


# ============================================
# SCHEMA INITIALIZATION FUNCTIONS
# ============================================

async def create_uniqueness_constraints(db: Neo4jDatabase) -> Tuple[int, int]:
    """
    Create uniqueness constraints for all entity types.
    
    Returns:
        Tuple of (created_count, skipped_count)
    """
    created = 0
    skipped = 0
    
    logger.info("Creating uniqueness constraints...")
    
    for constraint_name, label, property_name in UNIQUENESS_CONSTRAINTS:
        query = f"""
        CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
        FOR (n:{label})
        REQUIRE n.{property_name} IS UNIQUE
        """
        try:
            await db.execute(query)
            logger.info(f"  ✓ Constraint: {constraint_name}")
            created += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"  - Skipped (exists): {constraint_name}")
                skipped += 1
            else:
                logger.error(f"  ✗ Failed: {constraint_name} - {e}")
    
    return created, skipped


async def create_performance_indexes(db: Neo4jDatabase) -> Tuple[int, int]:
    """
    Create performance indexes for common query patterns.
    
    Returns:
        Tuple of (created_count, skipped_count)
    """
    created = 0
    skipped = 0
    
    logger.info("Creating performance indexes...")
    
    for index_name, label, property_name in PERFORMANCE_INDEXES:
        query = f"""
        CREATE INDEX {index_name} IF NOT EXISTS
        FOR (n:{label})
        ON (n.{property_name})
        """
        try:
            await db.execute(query)
            logger.info(f"  ✓ Index: {index_name}")
            created += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"  - Skipped (exists): {index_name}")
                skipped += 1
            else:
                logger.error(f"  ✗ Failed: {index_name} - {e}")
    
    return created, skipped


async def create_composite_indexes(db: Neo4jDatabase) -> Tuple[int, int]:
    """
    Create composite indexes for complex queries.
    
    Returns:
        Tuple of (created_count, skipped_count)
    """
    created = 0
    skipped = 0
    
    logger.info("Creating composite indexes...")
    
    for index_name, label, properties in COMPOSITE_INDEXES:
        props_str = ", ".join([f"n.{p}" for p in properties])
        query = f"""
        CREATE INDEX {index_name} IF NOT EXISTS
        FOR (n:{label})
        ON ({props_str})
        """
        try:
            await db.execute(query)
            logger.info(f"  ✓ Composite Index: {index_name}")
            created += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"  - Skipped (exists): {index_name}")
                skipped += 1
            else:
                logger.error(f"  ✗ Failed: {index_name} - {e}")
    
    return created, skipped


async def create_fulltext_indexes(db: Neo4jDatabase) -> Tuple[int, int]:
    """
    Create full-text indexes for search functionality.
    
    Returns:
        Tuple of (created_count, skipped_count)
    """
    created = 0
    skipped = 0
    
    logger.info("Creating full-text indexes...")
    
    for index_name, labels, properties in FULLTEXT_INDEXES:
        labels_str = "|".join(labels)
        props_str = ", ".join([f"n.{p}" for p in properties])
        
        query = f"""
        CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
        FOR (n:{labels_str})
        ON EACH [{props_str}]
        """
        try:
            await db.execute(query)
            logger.info(f"  ✓ Fulltext Index: {index_name}")
            created += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"  - Skipped (exists): {index_name}")
                skipped += 1
            else:
                logger.error(f"  ✗ Failed: {index_name} - {e}")
    
    return created, skipped


async def create_vector_index(db: Neo4jDatabase) -> bool:
    """
    Create the vector index for semantic similarity search.
    
    Returns:
        True if created or already exists, False on error
    """
    logger.info("Creating vector index for embeddings...")
    
    config = VECTOR_INDEX_CONFIG
    
    success = await db.create_vector_index(
        index_name=config["index_name"],
        label=config["label"],
        property_name=config["property_name"],
        dimensions=config["dimensions"],
        similarity_function=config["similarity_function"]
    )
    
    if success:
        logger.info(f"  ✓ Vector Index: {config['index_name']} ({config['dimensions']} dims, {config['similarity_function']})")
    else:
        logger.error(f"  ✗ Failed to create vector index: {config['index_name']}")
    
    return success


async def verify_schema(db: Neo4jDatabase) -> dict:
    """
    Verify that all schema elements are in place.
    
    Returns:
        Dict with verification results
    """
    logger.info("Verifying schema...")
    
    results = {
        "constraints": [],
        "indexes": [],
        "vector_indexes": [],
        "all_present": True
    }
    
    # Get all indexes
    indexes = await db.list_indexes()
    
    for idx in indexes:
        idx_name = idx.get("name", "unknown")
        idx_type = idx.get("type", "unknown")
        
        if idx_type == "VECTOR":
            results["vector_indexes"].append(idx_name)
        elif "CONSTRAINT" in str(idx.get("uniqueness", "")):
            results["constraints"].append(idx_name)
        else:
            results["indexes"].append(idx_name)
    
    # Check expected vs actual
    expected_constraints = len(UNIQUENESS_CONSTRAINTS)
    expected_indexes = len(PERFORMANCE_INDEXES) + len(COMPOSITE_INDEXES) + len(FULLTEXT_INDEXES)
    
    actual_constraints = len(results["constraints"])
    actual_indexes = len(results["indexes"])
    actual_vector = len(results["vector_indexes"])
    
    logger.info(f"  Constraints: {actual_constraints}/{expected_constraints}")
    logger.info(f"  Indexes: {actual_indexes}/{expected_indexes}")
    logger.info(f"  Vector Indexes: {actual_vector}/1")
    
    if actual_vector < 1:
        results["all_present"] = False
        logger.warning("  ⚠ Vector index missing!")
    
    return results


async def initialize_schema(
    uri: Optional[str] = None,
    user: Optional[str] = None, 
    password: Optional[str] = None,
    db_name: str = "neo4j"
) -> dict:
    """
    Initialize the complete Neo4j schema for LMS.
    
    Args:
        uri: Neo4j connection URI (default: from NEO4J_URI env var)
        user: Neo4j username (default: from NEO4J_USER env var)
        password: Neo4j password (default: from NEO4J_PASSWORD env var)
        db_name: Database name (default: "neo4j")
        
    Returns:
        Dict with initialization results
    """
    # Get connection details from environment if not provided
    uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = user or os.getenv("NEO4J_USER", "neo4j")
    password = password or os.getenv("NEO4J_PASSWORD", "password")
    
    logger.info("=" * 60)
    logger.info("LMS Neo4j Schema Initialization")
    logger.info("=" * 60)
    logger.info(f"URI: {uri}")
    logger.info(f"Database: {db_name}")
    logger.info("")
    
    results = {
        "success": False,
        "constraints": {"created": 0, "skipped": 0},
        "indexes": {"created": 0, "skipped": 0},
        "composite_indexes": {"created": 0, "skipped": 0},
        "fulltext_indexes": {"created": 0, "skipped": 0},
        "vector_index": False,
        "verification": {}
    }
    
    db = Neo4jDatabase(uri, (user, password), db_name)
    
    try:
        await db.connect()
        
        # 1. Create uniqueness constraints
        c, s = await create_uniqueness_constraints(db)
        results["constraints"] = {"created": c, "skipped": s}
        
        # 2. Create performance indexes
        c, s = await create_performance_indexes(db)
        results["indexes"] = {"created": c, "skipped": s}
        
        # 3. Create composite indexes
        c, s = await create_composite_indexes(db)
        results["composite_indexes"] = {"created": c, "skipped": s}
        
        # 4. Create full-text indexes
        c, s = await create_fulltext_indexes(db)
        results["fulltext_indexes"] = {"created": c, "skipped": s}
        
        # 5. Create vector index
        results["vector_index"] = await create_vector_index(db)
        
        # 6. Verify schema
        results["verification"] = await verify_schema(db)
        
        results["success"] = True
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("Schema Initialization Complete!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Schema initialization failed: {e}")
        results["error"] = str(e)
        
    finally:
        await db.close()
    
    return results


# ============================================
# CLI ENTRY POINT
# ============================================

async def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize Neo4j schema for LMS")
    parser.add_argument("--uri", help="Neo4j URI (default: from NEO4J_URI env)")
    parser.add_argument("--user", help="Neo4j username (default: from NEO4J_USER env)")
    parser.add_argument("--password", help="Neo4j password (default: from NEO4J_PASSWORD env)")
    parser.add_argument("--database", default="neo4j", help="Database name (default: neo4j)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    results = await initialize_schema(
        uri=args.uri,
        user=args.user,
        password=args.password,
        db_name=args.database
    )
    
    if results["success"]:
        print("\n✅ Schema initialization successful!")
    else:
        print(f"\n❌ Schema initialization failed: {results.get('error', 'Unknown error')}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
