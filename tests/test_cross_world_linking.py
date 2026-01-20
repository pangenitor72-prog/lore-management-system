"""
Test cross-world entity linking prevention and entity promotion.

Tests the fixes for the bug where relationships were created across worlds
when entities share the same name, and tests the admin workflow for promoting
session entities to canon.
"""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from fastapi import status
from src.lms.agents.lore_parsing_agent import LoreParsingAgent


@pytest.mark.asyncio
async def test_relationship_creation_doesnt_link_across_worlds(mock_neo4j_db):
    """
    Test that relationship creation uses canon_id mapping and doesn't create
    cross-world links when entities share names.
    """
    agent = LoreParsingAgent(api_key=None)  # No API key needed for this test
    
    # Setup: Create two worlds with entities that share the same name
    # World 1: "world_a" with entity "Captain Varn"
    await mock_neo4j_db.execute("""
        CREATE (e:Entity:Character {
            canon_id: 'world_a-chr-captain-varn-0001',
            name: 'Captain Varn',
            entity_type: 'Character',
            description: 'A brave ship captain from World A',
            world_id: 'world_a',
            curated_world_id: 'world_a'
        })
    """, {})
    
    # World 2: "world_b" with entity "Captain Varn" (different person)
    await mock_neo4j_db.execute("""
        CREATE (e:Entity:Character {
            canon_id: 'world_b-chr-captain-varn-0002',
            name: 'Captain Varn',
            entity_type: 'Character',
            description: 'A different captain from World B',
            world_id: 'world_b',
            curated_world_id: 'world_b'
        })
    """, {})
    
    # Now ingest lore into world_a that creates a relationship to "Captain Varn"
    # This should ONLY link to the world_a Captain Varn, NOT the world_b one
    from src.lms.agents.lore_parsing_agent import (
        ParsedLoreResult, ExtractedEntity, ExtractedRelationship
    )
    
    # Create a mock result with entities and relationships
    result = ParsedLoreResult(
        entities=[
            ExtractedEntity(
                name="The Silver Star",
                entity_type="Item",
                description="Captain Varn's prized ship",
                traits=[],
                tags=["ship"],
                verbatim_text="The Silver Star is Captain Varn's ship"
            )
        ],
        relationships=[
            ExtractedRelationship(
                source="Captain Varn",
                target="The Silver Star",
                relationship_type="OWNS",
                description="Captain Varn owns The Silver Star"
            )
        ]
    )
    
    # Patch the parse_lore method to return our mock result
    async def mock_parse_lore(text):
        return result
    
    agent.parse_lore = mock_parse_lore
    
    # Run parse_and_store for world_a
    await agent.parse_and_store(
        text="Captain Varn owns The Silver Star",
        db=mock_neo4j_db,
        source_name="test_ingestion",
        world_id="world_a",
        curated_world_id="world_a"
    )
    
    # Verify: The relationship should only exist within world_a
    # Check that a relationship was created to the world_a Captain Varn
    world_a_rels = await mock_neo4j_db.execute("""
        MATCH (a:Entity {world_id: 'world_a'})-[r:OWNS]->(b:Entity {world_id: 'world_a'})
        WHERE a.name = 'Captain Varn'
        RETURN a.canon_id AS source_id, b.canon_id AS target_id, type(r) AS rel_type
    """, {})
    
    assert len(world_a_rels) == 1, "Should have exactly one relationship in world_a"
    assert world_a_rels[0]["source_id"] == "world_a-chr-captain-varn-0001"
    
    # Verify: NO relationship should exist from world_b Captain Varn
    world_b_rels = await mock_neo4j_db.execute("""
        MATCH (a:Entity {world_id: 'world_b'})-[r:OWNS]->(b:Entity)
        WHERE a.name = 'Captain Varn'
        RETURN count(r) AS count
    """, {})
    
    assert world_b_rels[0]["count"] == 0, "Should have NO relationships from world_b Captain Varn"
    
    # Verify: NO cross-world relationships exist
    cross_world_rels = await mock_neo4j_db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE a.world_id <> b.world_id
        RETURN count(r) AS count
    """, {})
    
    assert cross_world_rels[0]["count"] == 0, "Should have NO cross-world relationships"


@pytest.mark.asyncio
async def test_canon_id_mapping_within_scope(mock_neo4j_db):
    """
    Test that entities created in the same ingestion scope are properly
    mapped by canon_id for relationship resolution.
    """
    agent = LoreParsingAgent(api_key=None)
    
    from src.lms.agents.lore_parsing_agent import (
        ParsedLoreResult, ExtractedEntity, ExtractedRelationship
    )
    
    # Create a result with multiple new entities and relationships between them
    result = ParsedLoreResult(
        entities=[
            ExtractedEntity(
                name="Lord Ashford",
                entity_type="Character",
                description="A noble lord",
                traits=["noble", "ambitious"],
                tags=["nobility"],
                verbatim_text="Lord Ashford is a noble"
            ),
            ExtractedEntity(
                name="Castle Ashford",
                entity_type="Location",
                description="The lord's castle",
                traits=[],
                tags=["castle"],
                verbatim_text="Castle Ashford"
            ),
            ExtractedEntity(
                name="Lady Elena",
                entity_type="Character",
                description="Lord Ashford's wife",
                traits=["kind", "diplomatic"],
                tags=["nobility"],
                verbatim_text="Lady Elena is Lord Ashford's wife"
            )
        ],
        relationships=[
            ExtractedRelationship(
                source="Lord Ashford",
                target="Castle Ashford",
                relationship_type="RESIDES_IN",
                description="Lord Ashford lives in Castle Ashford"
            ),
            ExtractedRelationship(
                source="Lord Ashford",
                target="Lady Elena",
                relationship_type="MARRIED_TO",
                description="Lord Ashford is married to Lady Elena"
            ),
            ExtractedRelationship(
                source="Lady Elena",
                target="Castle Ashford",
                relationship_type="RESIDES_IN",
                description="Lady Elena lives in Castle Ashford"
            )
        ]
    )
    
    async def mock_parse_lore(text):
        return result
    
    agent.parse_lore = mock_parse_lore
    
    # Ingest into world_test
    ingest_result = await agent.parse_and_store(
        text="Lord Ashford and Lady Elena live in Castle Ashford",
        db=mock_neo4j_db,
        source_name="test_ingestion",
        world_id="world_test",
        curated_world_id="world_test"
    )
    
    # Verify all 3 entities were created
    assert ingest_result.entities_stored == 3, f"Expected 3 entities stored, got {ingest_result.entities_stored}"
    
    # Verify all 3 relationships were created
    assert ingest_result.relationships_stored == 3, f"Expected 3 relationships stored, got {ingest_result.relationships_stored}"
    
    # Verify the relationships are all within world_test
    rels = await mock_neo4j_db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE a.world_id = 'world_test' AND b.world_id = 'world_test'
        RETURN count(r) AS count
    """, {})
    
    assert rels[0]["count"] == 3, "All 3 relationships should be within world_test"
    
    # Verify NO relationships cross world boundaries
    cross_world = await mock_neo4j_db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE a.world_id <> b.world_id
        RETURN count(r) AS count
    """, {})
    
    assert cross_world[0]["count"] == 0, "No cross-world relationships should exist"


def test_detect_cross_world_relationships(client: TestClient, mock_neo4j_db):
    """
    Test the admin endpoint that detects cross-world relationships.
    """
    # Setup: Create entities in two different worlds with a cross-world relationship
    # This simulates the bug's damage that needs to be detected
    import asyncio
    
    async def setup():
        # World 1 entity
        await mock_neo4j_db.execute("""
            CREATE (a:Entity:Character {
                canon_id: 'world1-chr-john-0001',
                name: 'John',
                entity_type: 'Character',
                world_id: 'world1',
                curated_world_id: 'world1'
            })
        """, {})
        
        # World 2 entity
        await mock_neo4j_db.execute("""
            CREATE (b:Entity:Character {
                canon_id: 'world2-chr-jane-0002',
                name: 'Jane',
                entity_type: 'Character',
                world_id: 'world2',
                curated_world_id: 'world2'
            })
        """, {})
        
        # Create a cross-world relationship (the bug)
        await mock_neo4j_db.execute("""
            MATCH (a:Entity {canon_id: 'world1-chr-john-0001'})
            MATCH (b:Entity {canon_id: 'world2-chr-jane-0002'})
            CREATE (a)-[:KNOWS]->(b)
        """, {})
    
    asyncio.run(setup())
    
    # Call the detection endpoint
    response = client.get("/game/admin/relationships/cross-world")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["cross_world_relationships"] == 1, "Should detect 1 cross-world relationship"
    assert len(data["relationships"]) == 1
    
    rel = data["relationships"][0]
    assert rel["source_world_id"] == "world1"
    assert rel["target_world_id"] == "world2"
    assert rel["rel_type"] == "KNOWS"


def test_delete_cross_world_relationships_dry_run(client: TestClient, mock_neo4j_db):
    """
    Test the cleanup endpoint in dry_run mode (doesn't actually delete).
    """
    # Setup: Create a cross-world relationship
    import asyncio
    
    async def setup():
        await mock_neo4j_db.execute("""
            CREATE (a:Entity:Character {
                canon_id: 'world1-chr-alice-0001',
                name: 'Alice',
                world_id: 'world1',
                curated_world_id: 'world1'
            })
        """, {})
        
        await mock_neo4j_db.execute("""
            CREATE (b:Entity:Character {
                canon_id: 'world2-chr-bob-0002',
                name: 'Bob',
                world_id: 'world2',
                curated_world_id: 'world2'
            })
        """, {})
        
        await mock_neo4j_db.execute("""
            MATCH (a:Entity {canon_id: 'world1-chr-alice-0001'})
            MATCH (b:Entity {canon_id: 'world2-chr-bob-0002'})
            CREATE (a)-[:FRIENDS_WITH]->(b)
        """, {})
    
    asyncio.run(setup())
    
    # Call delete with dry_run=true
    response = client.delete("/game/admin/relationships/cross-world?dry_run=true")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["dry_run"] is True
    assert data["would_delete"] == 1, "Should report 1 relationship would be deleted"
    
    # Verify the relationship still exists (wasn't actually deleted)
    async def verify():
        result = await mock_neo4j_db.execute("""
            MATCH ()-[r:FRIENDS_WITH]->()
            RETURN count(r) AS count
        """, {})
        return result[0]["count"]
    
    count = asyncio.run(verify())
    assert count == 1, "Relationship should still exist in dry_run mode"


def test_delete_cross_world_relationships_actual(client: TestClient, mock_neo4j_db):
    """
    Test the cleanup endpoint actually deletes cross-world relationships.
    """
    import asyncio
    
    async def setup():
        # Create entities in two worlds
        await mock_neo4j_db.execute("""
            CREATE (a:Entity:Character {
                canon_id: 'worldA-chr-charlie-0001',
                name: 'Charlie',
                world_id: 'worldA',
                curated_world_id: 'worldA'
            })
        """, {})
        
        await mock_neo4j_db.execute("""
            CREATE (b:Entity:Character {
                canon_id: 'worldB-chr-diana-0002',
                name: 'Diana',
                world_id: 'worldB',
                curated_world_id: 'worldB'
            })
        """, {})
        
        # Create a cross-world relationship
        await mock_neo4j_db.execute("""
            MATCH (a:Entity {canon_id: 'worldA-chr-charlie-0001'})
            MATCH (b:Entity {canon_id: 'worldB-chr-diana-0002'})
            CREATE (a)-[:RIVALS]->(b)
        """, {})
        
        # Also create a valid within-world relationship
        await mock_neo4j_db.execute("""
            CREATE (c:Entity:Location {
                canon_id: 'worldA-loc-tavern-0003',
                name: 'The Tavern',
                world_id: 'worldA',
                curated_world_id: 'worldA'
            })
        """, {})
        
        await mock_neo4j_db.execute("""
            MATCH (a:Entity {canon_id: 'worldA-chr-charlie-0001'})
            MATCH (c:Entity {canon_id: 'worldA-loc-tavern-0003'})
            CREATE (a)-[:FREQUENTS]->(c)
        """, {})
    
    asyncio.run(setup())
    
    # Call delete with dry_run=false
    response = client.delete("/game/admin/relationships/cross-world?dry_run=false")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["dry_run"] is False
    assert data["deleted"] == 1, "Should delete exactly 1 cross-world relationship"
    
    # Verify the cross-world relationship is gone
    async def verify_deleted():
        cross_world = await mock_neo4j_db.execute("""
            MATCH (a:Entity)-[r]->(b:Entity)
            WHERE a.world_id <> b.world_id
            RETURN count(r) AS count
        """, {})
        return cross_world[0]["count"]
    
    count = asyncio.run(verify_deleted())
    assert count == 0, "Cross-world relationship should be deleted"
    
    # Verify the within-world relationship still exists
    async def verify_kept():
        within_world = await mock_neo4j_db.execute("""
            MATCH (a:Entity {world_id: 'worldA'})-[r]->(b:Entity {world_id: 'worldA'})
            RETURN count(r) AS count
        """, {})
        return within_world[0]["count"]
    
    count = asyncio.run(verify_kept())
    assert count == 1, "Within-world relationship should be preserved"


def test_promote_entities_to_canon(client: TestClient, mock_neo4j_db):
    """
    Test promoting session entities to canon.
    """
    import asyncio
    
    async def setup():
        # Create a curated world
        await mock_neo4j_db.execute("""
            CREATE (lb:LoreBase {
                lore_id: 'my_world',
                name: 'My World'
            })
        """, {})
        
        # Create session entities
        await mock_neo4j_db.execute("""
            CREATE (e:Entity:Character {
                canon_id: 'session123-chr-npc-0001',
                name: 'NPC the First',
                entity_type: 'Character',
                description: 'An NPC created during gameplay',
                world_id: 'my_world_session123',
                session_id: 'session123',
                openness: 0.7,
                conscientiousness: 0.6,
                extraversion: 0.8,
                agreeableness: 0.5,
                neuroticism: 0.4
            })
        """, {})
        
        await mock_neo4j_db.execute("""
            CREATE (e:Entity:Location {
                canon_id: 'session123-loc-tavern-0002',
                name: 'The New Tavern',
                entity_type: 'Location',
                description: 'A tavern discovered during the session',
                world_id: 'my_world_session123',
                session_id: 'session123'
            })
        """, {})
        
        # Create a relationship between them
        await mock_neo4j_db.execute("""
            MATCH (a:Entity {canon_id: 'session123-chr-npc-0001'})
            MATCH (b:Entity {canon_id: 'session123-loc-tavern-0002'})
            CREATE (a)-[:FREQUENTS {description: 'NPC frequents this tavern'}]->(b)
        """, {})
    
    asyncio.run(setup())
    
    # Promote both entities to canon
    response = client.post("/game/admin/entities/promote", json={
        "entity_ids": ["session123-chr-npc-0001", "session123-loc-tavern-0002"],
        "target_world_id": "my_world",
        "promote_relationships": True,
        "keep_session_entity": False
    })
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["success"] is True
    assert data["promoted_count"] == 2
    assert data["relationships_promoted"] == 1
    
    # Verify canon entities were created
    async def verify_canon():
        canon_entities = await mock_neo4j_db.execute("""
            MATCH (e:Entity)
            WHERE e.curated_world_id = 'my_world'
            RETURN e.canon_id AS canon_id, e.name AS name, e.promoted_from_canon_id AS promoted_from
        """, {})
        return canon_entities
    
    canon = asyncio.run(verify_canon())
    assert len(canon) == 2, "Should have 2 canon entities"
    
    # Verify OCEAN personality was copied
    async def verify_ocean():
        char = await mock_neo4j_db.execute("""
            MATCH (e:Entity:Character)
            WHERE e.curated_world_id = 'my_world' AND e.name = 'NPC the First'
            RETURN e.openness AS o, e.conscientiousness AS c, e.extraversion AS e_val
        """, {})
        return char[0] if char else None
    
    char_data = asyncio.run(verify_ocean())
    assert char_data is not None
    assert char_data["o"] == 0.7
    assert char_data["c"] == 0.6
    assert char_data["e_val"] == 0.8
    
    # Verify relationship was promoted
    async def verify_relationship():
        rels = await mock_neo4j_db.execute("""
            MATCH (a:Entity)-[r:FREQUENTS]->(b:Entity)
            WHERE a.curated_world_id = 'my_world' AND b.curated_world_id = 'my_world'
            RETURN count(r) AS count
        """, {})
        return rels[0]["count"]
    
    rel_count = asyncio.run(verify_relationship())
    assert rel_count == 1, "Should have 1 promoted relationship in canon"
    
    # Verify session entities were deleted (since keep_session_entity=False)
    async def verify_deleted():
        session_entities = await mock_neo4j_db.execute("""
            MATCH (e:Entity)
            WHERE e.session_id = 'session123'
            RETURN count(e) AS count
        """, {})
        return session_entities[0]["count"]
    
    session_count = asyncio.run(verify_deleted())
    assert session_count == 0, "Session entities should be deleted when keep_session_entity=False"
