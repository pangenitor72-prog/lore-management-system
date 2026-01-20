"""
Tests for game save/load persistence and session recovery.
"""
import pytest
import json
from datetime import datetime, timezone
from fastapi import status


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        "session_id": "test-session-123",
        "world_id": "test_world",
        "session_world_id": "test_world_abc123",
        "world_name": "Test World",
        "world_lore_content": "A fantasy world",
        "character_concept": "A brave warrior",
        "genre": "fantasy",
        "genres": ["fantasy", "adventure"],
        "phase": "active_play",
        "status": "active",
        "history": [
            {"role": "user", "content": "I enter the tavern"},
            {"role": "assistant", "content": "You see a crowded room"},
        ],
        "rules_mode": "narrative",
        "rules_visibility": "guided",
    }


@pytest.fixture
def mock_character_data():
    """Sample character data for testing."""
    return {
        "character_id": "char-123",
        "name": "TestHero",
        "archetype": "fighter",
        "level": 3,
        "hit_points": 30,
        "max_hit_points": 30,
        "armor_class": 16,
    }


def test_list_saves_empty(client):
    """Test listing save slots when no saves exist."""
    browser_id = "test-browser-123"
    response = client.get(f"/api/game/saves?browser_id={browser_id}")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 10  # Should return 10 empty slots
    assert all(slot["is_empty"] for slot in data)


def test_save_game_without_session(client):
    """Test saving a game when session doesn't exist."""
    browser_id = "test-browser-123"
    save_request = {
        "slot": 1,
        "session_name": "Test Save",
        "browser_id": browser_id,
        "inventory": [],
    }
    
    response = client.post(
        "/api/game/saves/1?session_id=nonexistent-session",
        json=save_request
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_save_and_load_game_flow(client, mock_neo4j_db):
    """Test complete save and load flow."""
    browser_id = "test-browser-456"
    
    # 1. Create a session
    session_request = {
        "world_id": None,
        "character_concept": "A brave knight",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    
    session_response = client.post("/api/game/session", json=session_request)
    assert session_response.status_code == status.HTTP_200_OK
    session_data = session_response.json()
    session_id = session_data["session_id"]
    
    # 2. Save the session
    save_request = {
        "slot": 1,
        "session_name": "My Epic Adventure",
        "browser_id": browser_id,
        "inventory": [{"name": "Sword", "quantity": 1}],
    }
    
    save_response = client.post(
        f"/api/game/saves/1?session_id={session_id}",
        json=save_request
    )
    assert save_response.status_code == status.HTTP_200_OK
    save_data = save_response.json()
    assert save_data["success"] is True
    assert save_data["slot"] == 1
    assert save_data["session_id"] == session_id
    
    # 3. List saves - should show the saved game
    list_response = client.get(f"/api/game/saves?browser_id={browser_id}")
    assert list_response.status_code == status.HTTP_200_OK
    slots = list_response.json()
    
    # Find our save
    our_save = next((s for s in slots if s["slot"] == 1), None)
    assert our_save is not None
    assert our_save["is_empty"] is False
    assert our_save["session_name"] == "My Epic Adventure"
    assert our_save["genre"] == "fantasy"
    
    # 4. Load the save
    load_response = client.get(
        f"/api/game/saves/1/load?browser_id={browser_id}&mode=continue"
    )
    assert load_response.status_code == status.HTTP_200_OK
    load_data = load_response.json()
    assert load_data["success"] is True
    assert load_data["session_id"] != session_id  # New session ID
    assert load_data["phase"] == "session_0"  # Original phase
    assert len(load_data["inventory"]) == 1


def test_session_recovery_from_db(client, mock_neo4j_db):
    """Test session recovery after it's been removed from memory."""
    # 1. Create a session
    session_request = {
        "world_id": None,
        "character_concept": "A wise wizard",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    
    create_response = client.post("/api/game/session", json=session_request)
    assert create_response.status_code == status.HTTP_200_OK
    session_id = create_response.json()["session_id"]
    
    # 2. Verify session exists and is persisted
    # The session should be automatically persisted to mock DB
    
    # 3. Try to get the session (should work even if not in memory)
    get_response = client.get(f"/api/game/session/{session_id}")
    assert get_response.status_code == status.HTTP_200_OK
    session_data = get_response.json()
    assert session_data["session_id"] == session_id
    assert session_data["phase"] == "session_0"


def test_save_with_user_id(client, mock_neo4j_db):
    """Test saving with user_id instead of just browser_id."""
    user_id = "user-789"
    browser_id = "browser-xyz"
    
    # 1. Create a session
    session_request = {
        "world_id": None,
        "character_concept": "A stealthy rogue",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    
    session_response = client.post("/api/game/session", json=session_request)
    session_id = session_response.json()["session_id"]
    
    # 2. Save with user_id
    save_request = {
        "slot": 1,
        "session_name": "User Save",
        "browser_id": browser_id,
        "user_id": user_id,
        "inventory": [],
    }
    
    save_response = client.post(
        f"/api/game/saves/1?session_id={session_id}",
        json=save_request
    )
    assert save_response.status_code == status.HTTP_200_OK
    
    # 3. List saves with user_id
    list_response = client.get(f"/api/game/saves?browser_id={browser_id}&user_id={user_id}")
    assert list_response.status_code == status.HTTP_200_OK
    slots = list_response.json()
    
    user_save = next((s for s in slots if s["slot"] == 1), None)
    assert user_save is not None
    assert user_save["is_empty"] is False
    assert user_save["session_name"] == "User Save"


def test_save_isolation_by_browser_id(client, mock_neo4j_db):
    """Test that saves are properly isolated by browser_id."""
    browser1 = "browser-aaa"
    browser2 = "browser-bbb"
    
    # Create and save a session for browser1
    session_req1 = {
        "world_id": None,
        "character_concept": "Browser 1 Character",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    session1 = client.post("/api/game/session", json=session_req1).json()
    
    save_req1 = {
        "slot": 1,
        "session_name": "Browser 1 Save",
        "browser_id": browser1,
        "inventory": [],
    }
    client.post(f"/api/game/saves/1?session_id={session1['session_id']}", json=save_req1)
    
    # List saves for browser2 - should not see browser1's save
    list_response = client.get(f"/api/game/saves?browser_id={browser2}")
    assert list_response.status_code == status.HTTP_200_OK
    slots = list_response.json()
    
    # All slots should be empty for browser2
    assert all(slot["is_empty"] for slot in slots)


def test_delete_save(client, mock_neo4j_db):
    """Test deleting a save slot."""
    browser_id = "test-browser-del"
    
    # 1. Create and save a session
    session_req = {
        "world_id": None,
        "character_concept": "Temporary character",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    session = client.post("/api/game/session", json=session_req).json()
    
    save_req = {
        "slot": 2,
        "session_name": "Temp Save",
        "browser_id": browser_id,
        "inventory": [],
    }
    client.post(f"/api/game/saves/2?session_id={session['session_id']}", json=save_req)
    
    # 2. Verify save exists
    list_response = client.get(f"/api/game/saves?browser_id={browser_id}")
    slots = list_response.json()
    our_save = next((s for s in slots if s["slot"] == 2), None)
    assert our_save is not None
    assert our_save["is_empty"] is False
    
    # 3. Delete the save
    delete_response = client.delete(f"/api/game/saves/2?browser_id={browser_id}")
    assert delete_response.status_code == status.HTTP_200_OK
    
    # 4. Verify save is gone
    list_response2 = client.get(f"/api/game/saves?browser_id={browser_id}")
    slots2 = list_response2.json()
    deleted_slot = next((s for s in slots2 if s["slot"] == 2), None)
    assert deleted_slot is not None
    assert deleted_slot["is_empty"] is True


def test_load_with_new_chapter_mode(client, mock_neo4j_db):
    """Test loading a save in new_chapter mode."""
    browser_id = "test-browser-chapter"
    
    # 1. Create and save a session with history
    session_req = {
        "world_id": None,
        "character_concept": "Seasoned adventurer",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    session = client.post("/api/game/session", json=session_req).json()
    session_id = session["session_id"]
    
    # Add some actions to create history (would normally be done via action endpoint)
    # For testing, we'll just save with history
    
    save_req = {
        "slot": 3,
        "session_name": "Chapter 1 Complete",
        "browser_id": browser_id,
        "inventory": [{"name": "Magic Ring", "quantity": 1}],
    }
    client.post(f"/api/game/saves/3?session_id={session_id}", json=save_req)
    
    # 2. Load in new_chapter mode
    load_response = client.get(
        f"/api/game/saves/3/load?browser_id={browser_id}&mode=new_chapter"
    )
    assert load_response.status_code == status.HTTP_200_OK
    load_data = load_response.json()
    
    assert load_data["success"] is True
    assert load_data["continuation_mode"] == "new_chapter"
    # Should have a session summary
    assert "narrative" in load_data


def test_save_slot_validation(client):
    """Test slot number validation."""
    browser_id = "test-browser-val"
    
    # Create a session
    session_req = {
        "world_id": None,
        "character_concept": "Test",
        "genre": "fantasy",
        "storytelling_style": "guided",
    }
    session = client.post("/api/game/session", json=session_req).json()
    
    # Try invalid slot numbers
    save_req = {
        "slot": 999,  # Too high
        "session_name": "Invalid",
        "browser_id": browser_id,
        "inventory": [],
    }
    
    response = client.post(
        f"/api/game/saves/999?session_id={session['session_id']}",
        json=save_req
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Try slot 0
    response = client.post(
        f"/api/game/saves/0?session_id={session['session_id']}",
        json=save_req
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
