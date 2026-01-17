"""
Tests for entity loading error handling improvements.

Tests for Issue #1: HTTP 500 Error When Loading Entities
Tests for Issue #2: Per-world entity import feature
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import AsyncMock, patch


def test_get_entities_for_management_success(client: TestClient):
    """Test successful entity loading for management view."""
    response = client.get("/entities/manage")
    assert response.status_code == status.HTTP_200_OK
    entities = response.json()
    assert isinstance(entities, list)


def test_get_entities_for_management_with_world_filter(client: TestClient):
    """Test entity loading with world_id filter."""
    response = client.get("/entities/manage?world_id=test_world")
    assert response.status_code == status.HTTP_200_OK
    entities = response.json()
    assert isinstance(entities, list)


def test_get_world_entities_not_found(client: TestClient):
    """Test getting entities for non-existent world returns 404."""
    response = client.get("/api/game/lore-bases/nonexistent_world/entities")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_get_world_entities_with_filters(client: TestClient):
    """Test getting world entities with type and source filters."""
    # This should succeed even with empty result
    response = client.get(
        "/api/game/lore-bases/shattered_kingdoms/entities",
        params={
            "entity_type": "Character",
            "source_name": "test_source",
            "limit": 100
        }
    )
    # Should return 200 with empty list if world exists but has no entities
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


def test_get_world_entities_database_error_handling(client: TestClient, mock_neo4j_db):
    """Test that database errors are properly handled and logged."""
    # Mock database to raise an exception
    original_execute = mock_neo4j_db.execute
    
    async def failing_execute(*args, **kwargs):
        raise Exception("Database connection failed")
    
    mock_neo4j_db.execute = failing_execute
    
    try:
        response = client.get("/api/game/lore-bases/shattered_kingdoms/entities")
        # Should return 500 with proper error message
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to get entities" in response.json()["detail"]
    finally:
        # Restore original execute
        mock_neo4j_db.execute = original_execute


def test_entities_manage_database_error_handling(client: TestClient, mock_neo4j_db):
    """Test that database errors in management endpoint are properly handled."""
    # Mock database to raise an exception
    original_execute = mock_neo4j_db.execute
    
    async def failing_execute(*args, **kwargs):
        raise Exception("Query execution failed")
    
    mock_neo4j_db.execute = failing_execute
    
    try:
        response = client.get("/entities/manage")
        # Should return 500 with proper error message
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to get entities" in response.json()["detail"]
    finally:
        # Restore original execute
        mock_neo4j_db.execute = original_execute


def test_get_world_entities_empty_result(client: TestClient):
    """Test that empty entity lists are handled properly."""
    response = client.get("/api/game/lore-bases/shattered_kingdoms/entities")
    
    if response.status_code == status.HTTP_200_OK:
        data = response.json()
        assert "world_id" in data
        assert "count" in data
        assert "entities" in data
        assert isinstance(data["entities"], list)
        assert data["count"] == len(data["entities"])
    else:
        # If world doesn't exist, should be 404
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_import_entities_to_world_success(client: TestClient):
    """Test successfully importing entities to a world."""
    # Sample entities from preview
    entities = [
        {
            "name": "Test Character",
            "type": "Character",
            "description": "A test character",
            "traits": ["brave", "intelligent"],
            "openness": 0.7,
            "conscientiousness": 0.8,
            "extraversion": 0.6,
            "agreeableness": 0.5,
            "neuroticism": 0.4
        },
        {
            "name": "Test Location",
            "type": "Location",
            "description": "A test location",
            "tags": ["city", "coastal"]
        }
    ]
    
    response = client.post(
        "/api/game/lore-bases/shattered_kingdoms/entities",
        json={
            "entities": entities,
            "source_name": "test_import"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["entities_imported"] == 2
    assert data["lore_id"] == "shattered_kingdoms"
    assert data["source_name"] == "test_import"


def test_import_entities_to_nonexistent_world(client: TestClient):
    """Test importing entities to non-existent world returns 404."""
    entities = [{"name": "Test", "type": "Character", "description": "Test"}]
    
    response = client.post(
        "/api/game/lore-bases/nonexistent_world/entities",
        json={"entities": entities}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_import_entities_no_entities_provided(client: TestClient):
    """Test importing with no entities returns 400."""
    response = client.post(
        "/api/game/lore-bases/shattered_kingdoms/entities",
        json={"entities": []}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No entities provided" in response.json()["detail"]


def test_import_entities_database_error(client: TestClient, mock_neo4j_db):
    """Test that database errors during import are properly handled."""
    original_execute = mock_neo4j_db.execute
    
    async def failing_execute(*args, **kwargs):
        raise Exception("Database write failed")
    
    mock_neo4j_db.execute = failing_execute
    
    entities = [{"name": "Test", "type": "Character", "description": "Test"}]
    
    try:
        response = client.post(
            "/api/game/lore-bases/shattered_kingdoms/entities",
            json={"entities": entities}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to import entities" in response.json()["detail"]
    finally:
        mock_neo4j_db.execute = original_execute
