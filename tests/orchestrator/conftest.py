# tests/orchestrator/conftest.py
"""
Pytest fixtures for orchestrator tests.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.mantle.orchestrator.models import (
    Task,
    TaskResult,
    TaskStatus,
    TaskType,
    TaskPriority,
    SubAgentContext,
)
from src.mantle.orchestrator.protocols import SubAgentCapability, AgentBackend
from src.mantle.orchestrator.task_manager import TaskManager
from src.mantle.orchestrator.context_provider import ContextProvider


@pytest.fixture
def mock_gemini_key():
    """Fixture providing a mock Gemini API key."""
    return "test-api-key-12345"


@pytest.fixture
def project_root(tmp_path):
    """Fixture providing a temporary project root."""
    # Create basic project structure
    (tmp_path / "CLAUDE.md").write_text("# Test Project\nTest instructions.")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text("# Architecture\nTest.")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("# Test file\ndef hello(): pass")
    return str(tmp_path)


@pytest.fixture
def sample_task():
    """Fixture providing a sample task."""
    return Task(
        task_type=TaskType.DEVELOPMENT,
        title="Test Task",
        description="A test task for unit testing",
        priority=TaskPriority.MEDIUM,
    )


@pytest.fixture
def sample_context(project_root):
    """Fixture providing a sample context."""
    return SubAgentContext(
        project_root=project_root,
        claude_md_content="# Test Project",
        file_contents={"test.py": "def hello(): pass"},
    )


@pytest.fixture
def sample_result(sample_task):
    """Fixture providing a sample task result."""
    return TaskResult(
        task_id=sample_task.task_id,
        agent_id="test-agent",
        status=TaskStatus.COMPLETED,
        output={"message": "Task completed"},
    )


@pytest.fixture
def task_manager():
    """Fixture providing a task manager instance."""
    return TaskManager()


@pytest.fixture
def context_provider(project_root):
    """Fixture providing a context provider instance."""
    return ContextProvider(project_root=project_root)


@pytest.fixture
def mock_db():
    """Fixture providing a mock Neo4j database."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_genai():
    """Fixture providing a mock Gemini API."""
    with patch("src.mantle.orchestrator.sub_agents.llm_agent.genai") as mock:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"status": "success", "output": {"result": "test"}}'
        mock_model.generate_content.return_value = mock_response
        mock.GenerativeModel.return_value = mock_model
        yield mock
