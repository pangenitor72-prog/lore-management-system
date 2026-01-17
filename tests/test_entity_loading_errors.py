"""
Tests for entity loading error handling improvements.

Tests for Issue #1: HTTP 500 Error When Loading Entities
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
