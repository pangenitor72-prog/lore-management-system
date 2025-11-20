import pytest
from fastapi.testclient import TestClient
from fastapi import status
from src.models import EntityType, ApprovalStatus

# The 'api_client' fixture is now provided by 'tests/conftest.py'

def test_create_full_entity(api_client: TestClient):
    """
    Verify full entity creation including enums, aliases, approved_fields,
    and correct canon_id prefixing.
    """
    entity_data = {
        "entity_type": EntityType.CHARACTER.value,
        "canonical_name": "Sir Reginald the Bold",
        "aliases": ["Reggie", "The Bold"],
        "approved_fields": {"title": "Knight of the Realm", "age": 42},
        "approval_status": ApprovalStatus.APPROVED.value,
        "confidence_level": "CONFIRMED",
        "party_knowledge": "KNOWN"
    }
    response = api_client.post("/entities", json=entity_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    created_entity = response.json()

    # Verify canon_id prefixing
    assert created_entity['canon_id'].startswith("character-")
    
    # Verify core fields
    assert created_entity['canonical_name'] == "Sir Reginald the Bold"
    assert created_entity['approval_status'] == ApprovalStatus.APPROVED.value

    # Verify aliases and approved_fields persistence
    assert sorted(created_entity['aliases']) == sorted(["Reggie", "The Bold"])
    assert created_entity['approved_fields']['title'] == "Knight of the Realm"
    
    # Verify timestamp creation
    assert "created_at" in created_entity
    assert "updated_at" in created_entity

def test_get_entity_and_json_roundtrip(api_client: TestClient):
    """
    Verify that an entity can be retrieved and that JSON data in
    approved_fields is correctly loaded.
    """
    # First, create a complex entity
    entity_data = {
        "entity_type": "Item",
        "canonical_name": "Amulet of JSON",
        "aliases": [],
        "approved_fields": {
            "properties": {"material": "gold", "enchantment": "data_integrity"},
            "charges": 5
        },
        "approval_status": "APPROVED",
        "confidence_level": "CONFIRMED",
        "party_knowledge": "SECRET"
    }
    create_response = api_client.post("/entities", json=entity_data)
    assert create_response.status_code == status.HTTP_201_CREATED
    canon_id = create_response.json()['canon_id']

    # Now, retrieve it
    get_response = api_client.get(f"/entities/{canon_id}")
    assert get_response.status_code == status.HTTP_200_OK
    fetched_entity = get_response.json()

    # Verify JSON round-trip integrity
    assert fetched_entity['approved_fields']['charges'] == 5
    assert isinstance(fetched_entity['approved_fields']['properties'], dict)
    assert fetched_entity['approved_fields']['properties']['enchantment'] == "data_integrity"

def test_list_entities_returns_real_entities(api_client: TestClient):
    """
    Verify that the list endpoint returns a list of fully-formed entities.
    This also implicitly tests the M4 (N+1) fix.
    """
    # Create an entity to ensure the list is not empty
    api_client.post("/entities", json={
        "entity_type": "Event", "canonical_name": "The Grand Testival",
        "approval_status": "APPROVED", "confidence_level": "CONFIRMED", "party_knowledge": "KNOWN"
    })
    
    response = api_client.get("/entities")
    assert response.status_code == status.HTTP_200_OK
    
    entities = response.json()
    assert isinstance(entities, list)
    assert len(entities) > 0

    # Check that a sample entity has the full structure
    sample_entity = entities[0]
    assert "canon_id" in sample_entity
    assert "canonical_name" in sample_entity
    assert "aliases" in sample_entity
    assert isinstance(sample_entity['aliases'], list)
    assert "approved_fields" in sample_entity
    assert isinstance(sample_entity['approved_fields'], dict)
