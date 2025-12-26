# tests/orchestrator/test_models.py
"""
Tests for orchestrator data models.
"""

import pytest
from datetime import datetime, timezone

from src.lms.orchestrator.models import (
    Task,
    TaskResult,
    TaskStatus,
    TaskType,
    TaskPriority,
    SubAgentContext,
    OrchestratorState,
)


class TestTask:
    """Tests for the Task model."""

    def test_task_creation_defaults(self):
        """Test task creation with default values."""
        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Test Task",
            description="A test task",
        )

        assert task.task_id is not None
        assert task.task_type == TaskType.DEVELOPMENT
        assert task.title == "Test Task"
        assert task.priority == TaskPriority.MEDIUM
        assert task.status == TaskStatus.PENDING
        assert task.parent_task_id is None
        assert task.subtask_ids == []
        assert task.depends_on == []

    def test_task_creation_with_values(self):
        """Test task creation with explicit values."""
        task = Task(
            task_type=TaskType.LORE_MANAGEMENT,
            title="Create Entity",
            description="Create a new character",
            priority=TaskPriority.HIGH,
            relevant_files=["src/test.py"],
            lore_entities=["Character1"],
        )

        assert task.task_type == TaskType.LORE_MANAGEMENT
        assert task.priority == TaskPriority.HIGH
        assert task.relevant_files == ["src/test.py"]
        assert task.lore_entities == ["Character1"]

    def test_task_id_uniqueness(self):
        """Test that task IDs are unique."""
        task1 = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Task 1",
            description="First task",
        )
        task2 = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Task 2",
            description="Second task",
        )

        assert task1.task_id != task2.task_id


class TestTaskResult:
    """Tests for the TaskResult model."""

    def test_result_creation(self):
        """Test result creation."""
        result = TaskResult(
            task_id="test-id",
            agent_id="test-agent",
            status=TaskStatus.COMPLETED,
            output={"data": "value"},
        )

        assert result.task_id == "test-id"
        assert result.agent_id == "test-agent"
        assert result.status == TaskStatus.COMPLETED
        assert result.output == {"data": "value"}
        assert result.error_message is None

    def test_result_with_error(self):
        """Test result creation with error."""
        result = TaskResult(
            task_id="test-id",
            agent_id="test-agent",
            status=TaskStatus.FAILED,
            error_message="Something went wrong",
        )

        assert result.status == TaskStatus.FAILED
        assert result.error_message == "Something went wrong"


class TestSubAgentContext:
    """Tests for the SubAgentContext model."""

    def test_context_creation(self):
        """Test context creation."""
        context = SubAgentContext(
            project_root="/test/path",
            claude_md_content="# Test",
        )

        assert context.project_root == "/test/path"
        assert context.claude_md_content == "# Test"
        assert context.file_contents == {}
        assert context.lore_entities == []

    def test_context_with_files(self):
        """Test context with file contents."""
        context = SubAgentContext(
            project_root="/test/path",
            file_contents={
                "test.py": "def hello(): pass",
                "main.py": "print('hello')",
            },
        )

        assert len(context.file_contents) == 2
        assert "test.py" in context.file_contents


class TestOrchestratorState:
    """Tests for the OrchestratorState model."""

    def test_state_creation(self):
        """Test state creation with defaults."""
        state = OrchestratorState()

        assert state.session_id is not None
        assert state.active_agents == {}
        assert state.task_queue == []
        assert state.total_tasks_processed == 0

    def test_state_timestamps(self):
        """Test that state has valid timestamps."""
        state = OrchestratorState()

        assert state.session_started_at is not None
        assert state.session_started_at <= datetime.now(timezone.utc)
