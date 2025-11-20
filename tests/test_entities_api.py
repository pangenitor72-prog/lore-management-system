import pytest
from httpx import AsyncClient
from fastapi import status
from src.api import app
from src.database import get_db, get_db_connection, Database # Import Database static methods
from src.models import EntityCreate, EntityType, ApprovalStatus, ConfidenceLevel, PartyKnowledge
from datetime import datetime, timezone
import json
from pathlib import Path

# Fixture for an in-memory database for API tests
@pytest.fixture
async def client():
    # Use an in-memory SQLite database for tests
    test_db_conn = get_db_connection(":memory:")
    
    # Initialize schema
    schema_path = Path(__file__).parent.parent / "data/schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    test_db_conn.executescript(schema_sql)
    test_db_conn.commit()

    def override_get_db():
        try:
            yield test_db_conn
        finally:
            test_db_conn.close()

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_entity(client: AsyncClient):
    entity_data = EntityCreate(
        entity_type=EntityType.CHARACTER,
        canonical_name="Test Character",
        aliases=["TC"],
        approved_fields={"origin": "fantasy", "age": 30},
        approval_status=ApprovalStatus.PENDING,
        confidence_level=ConfidenceLevel.PROBABLE,
        party_knowledge=PartyKnowledge.KNOWN
    )
    response = await client.post("/entities", json=entity_data.model_dump(mode='json'))
    assert response.status_code == status.HTTP_201_CREATED
    created_entity = response.json()
    assert created_entity['canonical_name'] == "Test Character"
    assert "char-" in created_entity['canon_id']
    assert created_entity['approved_fields']['age'] == 30 # Check JSON parsing on retrieval

@pytest.mark.asyncio
async def test_get_entity(client: AsyncClient):
    # First create an entity
    entity_data = EntityCreate(
        entity_type=EntityType.LOCATION,
        canonical_name="Test Location",
        aliases=["TL"],
        approved_fields={"biome": "forest"},
        approval_status=ApprovalStatus.APPROVED,
        confidence_level=ConfidenceLevel.CONFIRMED,
        party_knowledge=PartyKnowledge.RUMORED
    )
    create_response = await client.post("/entities", json=entity_data.model_dump(mode='json'))
    canon_id = create_response.json()['canon_id']

    response = await client.get(f"/entities/{canon_id}")
    assert response.status_code == status.HTTP_200_OK
    fetched_entity = response.json()
    assert fetched_entity['canon_id'] == canon_id
    assert fetched_entity['canonical_name'] == "Test Location"
    assert fetched_entity['approved_fields']['biome'] == "forest" # Check JSON parsing on retrieval

@pytest.mark.asyncio
async def test_list_entities(client: AsyncClient):
    # Create a few entities
    entity_data_1 = EntityCreate(
        entity_type=EntityType.ITEM,
        canonical_name="Sword of Testing 1",
        aliases=[],
        approved_fields={},
        approval_status=ApprovalStatus.PENDING,
        confidence_level=ConfidenceLevel.UNCERTAIN,
        party_knowledge=PartyKnowledge.FORGOTTEN
    )
    await client.post("/entities", json=entity_data_1.model_dump(mode='json'))

    entity_data_2 = EntityCreate(
        entity_type=EntityType.ITEM,
        canonical_name="Sword of Testing 2",
        aliases=[],
        approved_fields={},
        approval_status=ApprovalStatus.APPROVED,
        confidence_level=ConfidenceLevel.CONFIRMED,
        party_knowledge=PartyKnowledge.KNOWN
    )
    await client.post("/entities", json=entity_data_2.model_dump(mode='json'))

    # List all entities
    response = await client.get("/entities")
    assert response.status_code == status.HTTP_200_OK
    entities = response.json()
    assert len(entities) >= 2 # May have other entities from other tests if not careful with DB cleanup

    # List with filter
    response_filtered = await client.get("/entities", params={"approval_status": ApprovalStatus.APPROVED.value})
    assert response_filtered.status_code == status.HTTP_200_OK
    filtered_entities = response_filtered.json()
    for entity in filtered_entities:
        assert entity['approval_status'] == ApprovalStatus.APPROVED.value