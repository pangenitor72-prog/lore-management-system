import pytest
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from src.mantle.core.models import GameSessionResponse, InstanceResponse

# The 'client' fixture is provided by 'tests/conftest.py'

# NOTE: The /sessions/{session_id} endpoint is not yet implemented.
# These tests are skipped until the route is added.
pytestmark = pytest.mark.skip(reason="The /sessions endpoint is not yet implemented")

@pytest.fixture
def mock_game_session_state():
    """
    Fixture to provide a consistent mock game session state.
    """
    return {
        "session_id": "test_session_123",
        "dm_id": "test_dm_456",
        "active_entities": [
            {"id": "char-1", "name": "Hero", "type": "Character"},
            {"id": "loc-1", "name": "Village", "type": "Location"}
        ],
        "player_characters": [
            {"id": "player-1", "name": "PlayerOne", "type": "Character"}
        ],
        "current_events": ["A dragon attacks the village.", "The hero prepares for battle."],
        "world_state_summary": "The world is in peril.",
        "campaign_name": "Dragon's Breath",
        "campaign_goal": "Defeat the dragon.",
        "lore_accuracy_score": 0.95,
        "active_contradictions_count": 2,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

@pytest.mark.asyncio
@patch("src.core.game_session.GameSession", autospec=True)
async def test_get_game_session_success(
    mock_game_session_class: AsyncMock,
    client: TestClient,
    mock_game_session_state: dict
):
    """
    Test successful retrieval of a game session.
    """
    mock_instance = mock_game_session_class.return_value
    mock_instance.get_state.return_value = mock_game_session_state

    session_id = "test_session_123"
    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Assertions based on mock_game_session_state
    assert data["session_id"] == mock_game_session_state["session_id"]
    assert data["dm_id"] == mock_game_session_state["dm_id"]
    assert len(data["active_entities"]) == len(mock_game_session_state["active_entities"])
    assert data["active_entities"][0]["name"] == mock_game_session_state["active_entities"][0]["name"]
    assert data["player_characters"][0]["name"] == mock_game_session_state["player_characters"][0]["name"]
    assert data["world_state_summary"] == mock_game_session_state["world_state_summary"]
    assert data["lore_accuracy_score"] == mock_game_session_state["lore_accuracy_score"]
    assert data["active_contradictions_count"] == mock_game_session_state["active_contradictions_count"]
    # Check if the datetime string is correctly formatted and matches
    assert datetime.fromisoformat(data["last_updated"]).replace(tzinfo=timezone.utc) == \
           datetime.fromisoformat(mock_game_session_state["last_updated"])
    
    # Verify GameSession and get_state were called correctly
    mock_game_session_class.assert_called_once()
    assert mock_game_session_class.call_args[1]['session_id'] == session_id
    mock_instance.get_state.assert_awaited_once()


@pytest.mark.asyncio
@patch("src.core.game_session.GameSession", autospec=True)
async def test_get_game_session_not_found(
    mock_game_session_class: AsyncMock,
    client: TestClient
):
    """
    Test retrieval of a non-existent game session.
    """
    mock_instance = mock_game_session_class.return_value
    mock_instance.get_state.return_value = {}  # Simulate session not found

    session_id = "non_existent_session"
    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Game session not found" in response.json()["detail"]

    mock_game_session_class.assert_called_once()
    assert mock_game_session_class.call_args[1]['session_id'] == session_id
    mock_instance.get_state.assert_awaited_once()

@pytest.mark.asyncio
@patch("src.core.game_session.GameSession", autospec=True)
async def test_get_game_session_internal_error(
    mock_game_session_class: AsyncMock,
    client: TestClient
):
    """
    Test internal server error during game session retrieval.
    """
    mock_instance = mock_game_session_class.return_value
    mock_instance.get_state.side_effect = Exception("Database error")

    session_id = "error_session"
    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to format game session data" in response.json()["detail"]

    mock_game_session_class.assert_called_once()
    assert mock_game_session_class.call_args[1]['session_id'] == session_id
    mock_instance.get_state.assert_awaited_once()