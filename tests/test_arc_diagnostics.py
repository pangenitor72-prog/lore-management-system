import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status


def test_arc_status_disabled(client: TestClient):
    """
    Test /arc/status endpoint when Arc Engine is disabled via config.
    """
    with patch.dict(os.environ, {"ENABLE_ARC_ENGINE": "false"}):
        # Re-import to pick up env var
        import importlib
        import src.lms.agents.dm_agent as dm_agent_module
        importlib.reload(dm_agent_module)
        
        response = client.get("/arc/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["enabled"] is False
        assert data["available"] is False
        assert data["reason"] == "Disabled via config (ENABLE_ARC_ENGINE=false)"
        assert "dependencies_checked" in data


def test_arc_status_enabled_but_import_failed(client: TestClient):
    """
    Test /arc/status endpoint when Arc Engine is enabled but import fails.
    """
    with patch.dict(os.environ, {"ENABLE_ARC_ENGINE": "true"}):
        # Mock the import to fail
        with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
             patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", False), \
             patch("src.lms.agents.dm_agent.ARC_ENGINE_IMPORT_ERROR", "ModuleNotFoundError: No module named 'src.lms.arc'"):
            
            response = client.get("/arc/status")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["enabled"] is True
            assert data["available"] is False
            assert "Import failed" in data["reason"]
            assert data["import_error"] is not None


def test_arc_status_enabled_and_available(client: TestClient):
    """
    Test /arc/status endpoint when Arc Engine is enabled and successfully imported.
    """
    with patch.dict(os.environ, {"ENABLE_ARC_ENGINE": "true"}):
        # Mock successful import
        with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
             patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", True), \
             patch("src.lms.agents.dm_agent.ARC_ENGINE_IMPORT_ERROR", None):
            
            response = client.get("/arc/status")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["enabled"] is True
            assert data["available"] is True
            assert data["reason"] == "Import successful"
            assert data["import_error"] is None
            assert "dependencies_checked" in data
            # Should have checked pydantic
            assert "pydantic" in data["dependencies_checked"]


def test_arc_session_when_disabled(client: TestClient):
    """
    Test /arc/session/{session_id} endpoint when Arc Engine is disabled.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", False):
        response = client.get("/arc/session/test-session-123")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "disabled via configuration" in data["detail"].lower()


def test_arc_session_when_unavailable(client: TestClient):
    """
    Test /arc/session/{session_id} endpoint when Arc Engine failed to import.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", False):
        
        response = client.get("/arc/session/test-session-123")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "not available" in data["detail"].lower()


def test_arc_session_not_found(client: TestClient):
    """
    Test /arc/session/{session_id} endpoint when session doesn't exist.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", True):
        
        # Mock _active_sessions to be empty
        with patch("src.lms.api.game_routes._active_sessions", {}):
            response = client.get("/arc/session/nonexistent-session")
            
            # Should get 404 or appropriate error
            assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_503_SERVICE_UNAVAILABLE]


def test_arc_session_without_arc_engine(client: TestClient):
    """
    Test /arc/session/{session_id} endpoint when session exists but arc_engine not initialized.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", True):
        
        # Mock a session without arc_engine
        mock_session = {
            "session_id": "test-session-123",
            "player_id": "player1"
        }
        
        with patch("src.lms.api.game_routes._active_sessions", {"test-session-123": mock_session}):
            response = client.get("/arc/session/test-session-123")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == "test-session-123"
            assert data["arc_engine_state"] == "not_initialized"


def test_arc_session_with_arc_engine(client: TestClient):
    """
    Test /arc/session/{session_id} endpoint when session has arc_engine initialized.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", True):
        
        # Mock an arc_engine instance
        mock_arc_engine = MagicMock()
        mock_arc_engine.current_phase = MagicMock(value="CALL_TO_ADVENTURE")
        mock_arc_engine.current_act = MagicMock(value="DEPARTURE")
        mock_arc_engine.tension_level = MagicMock(value="BUILDING")
        mock_arc_engine.current_tension = 0.45
        mock_arc_engine.journey_progress = 0.15
        mock_arc_engine.episode_number = 1
        
        mock_session = {
            "session_id": "test-session-123",
            "arc_engine": mock_arc_engine
        }
        
        with patch("src.lms.api.game_routes._active_sessions", {"test-session-123": mock_session}):
            response = client.get("/arc/session/test-session-123")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            assert data["session_id"] == "test-session-123"
            assert data["current_phase"] == "CALL_TO_ADVENTURE"
            assert data["current_act"] == "DEPARTURE"
            assert data["tension_level"] == "BUILDING"
            assert data["tension_value"] == 0.45
            assert data["journey_progress"] == 0.15
            assert data["episode_number"] == 1
            assert "phase_guidance" in data
            assert "tension_guidance" in data


def test_health_check_includes_arc_engine(client: TestClient):
    """
    Test that /health endpoint includes arc_engine status.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_AVAILABLE", True), \
         patch("src.lms.agents.dm_agent.ARC_ENGINE_IMPORT_ERROR", None):
        
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "checks" in data
        assert "arc_engine" in data["checks"]
        assert data["checks"]["arc_engine"] == "available"
        
        assert "features" in data
        assert "arc_engine_enabled" in data["features"]
        assert data["features"]["arc_engine_enabled"] is True


def test_health_check_arc_engine_disabled(client: TestClient):
    """
    Test that /health endpoint shows arc_engine as disabled when not enabled.
    """
    with patch("src.lms.agents.dm_agent.ARC_ENGINE_ENABLED", False):
        
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "checks" in data
        assert "arc_engine" in data["checks"]
        assert data["checks"]["arc_engine"] == "disabled"
        
        assert "features" in data
        assert "arc_engine_enabled" in data["features"]
        assert data["features"]["arc_engine_enabled"] is False
