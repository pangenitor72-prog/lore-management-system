# tests/orchestrator/test_task_manager.py
"""
Tests for the TaskManager.
"""

import pytest

from src.mantle.orchestrator.models import (
    Task,
    TaskResult,
    TaskStatus,
    TaskType,
    TaskPriority,
)
from src.mantle.orchestrator.task_manager import TaskManager


class TestTaskManager:
    """Tests for the TaskManager class."""

    @pytest.mark.asyncio
    async def test_add_task(self, task_manager, sample_task):
        """Test adding a task to the manager."""
        task_id = await task_manager.add_task(sample_task)

        assert task_id == sample_task.task_id

        retrieved = await task_manager.get_task(task_id)
        assert retrieved is not None
        assert retrieved.title == sample_task.title

    @pytest.mark.asyncio
    async def test_get_next_task(self, task_manager):
        """Test getting the next available task."""
        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Test",
            description="Test task",
        )
        await task_manager.add_task(task)

        next_task = await task_manager.get_next_task()

        assert next_task is not None
        assert next_task.task_id == task.task_id
        assert next_task.status == TaskStatus.ASSIGNED

    @pytest.mark.asyncio
    async def test_get_next_task_empty(self, task_manager):
        """Test getting next task when queue is empty."""
        next_task = await task_manager.get_next_task()
        assert next_task is None

    @pytest.mark.asyncio
    async def test_complete_task(self, task_manager, sample_task, sample_result):
        """Test completing a task."""
        await task_manager.add_task(sample_task)

        await task_manager.complete_task(sample_result)

        task = await task_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_priority_ordering(self, task_manager):
        """Test that tasks are ordered by priority."""
        low = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Low Priority",
            description="Low",
            priority=TaskPriority.LOW,
        )
        high = Task(
            task_type=TaskType.DEVELOPMENT,
            title="High Priority",
            description="High",
            priority=TaskPriority.HIGH,
        )

        # Add low first, then high
        await task_manager.add_task(low)
        await task_manager.add_task(high)

        # High priority should come first
        next_task = await task_manager.get_next_task()
        assert next_task.priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, task_manager):
        """Test that tasks with dependencies wait for them."""
        task1 = Task(
            task_type=TaskType.DEVELOPMENT,
            title="First",
            description="Must run first",
        )
        task2 = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Second",
            description="Depends on first",
            depends_on=[task1.task_id],
        )

        await task_manager.add_task(task1)
        await task_manager.add_task(task2)

        # First task should come first
        next_task = await task_manager.get_next_task()
        assert next_task.task_id == task1.task_id

        # Second task should wait
        next_task2 = await task_manager.get_next_task()
        assert next_task2 is None  # Still waiting

        # Complete first task
        result = TaskResult(
            task_id=task1.task_id,
            agent_id="test",
            status=TaskStatus.COMPLETED,
        )
        await task_manager.complete_task(result)

        # Now second task should be available
        next_task3 = await task_manager.get_next_task()
        assert next_task3.task_id == task2.task_id

    @pytest.mark.asyncio
    async def test_add_subtasks(self, task_manager):
        """Test adding subtasks to a parent task."""
        parent = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Parent",
            description="Parent task",
        )
        await task_manager.add_task(parent)

        subtasks = [
            Task(
                task_type=TaskType.DEVELOPMENT,
                title="Child 1",
                description="First child",
            ),
            Task(
                task_type=TaskType.DEVELOPMENT,
                title="Child 2",
                description="Second child",
            ),
        ]

        subtask_ids = await task_manager.add_subtasks(parent.task_id, subtasks)

        assert len(subtask_ids) == 2

        parent_task = await task_manager.get_task(parent.task_id)
        assert len(parent_task.subtask_ids) == 2

    @pytest.mark.asyncio
    async def test_fail_task_with_retry(self, task_manager):
        """Test failing a task with retry available."""
        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Retry Test",
            description="Test task",
            max_retries=3,
        )
        await task_manager.add_task(task)

        # Fail the task
        retried = await task_manager.fail_task(
            task.task_id, "Test error", can_retry=True
        )

        assert retried is True

        task = await task_manager.get_task(task.task_id)
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1

    @pytest.mark.asyncio
    async def test_fail_task_no_retry(self, task_manager):
        """Test failing a task permanently."""
        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="No Retry Test",
            description="Test task",
            max_retries=0,
        )
        await task_manager.add_task(task)

        retried = await task_manager.fail_task(
            task.task_id, "Test error", can_retry=True
        )

        assert retried is False

        task = await task_manager.get_task(task.task_id)
        assert task.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_manager, sample_task):
        """Test cancelling a task."""
        await task_manager.add_task(sample_task)

        cancelled = await task_manager.cancel_task(sample_task.task_id)

        assert cancelled is True

        task = await task_manager.get_task(sample_task.task_id)
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_queue_status(self, task_manager):
        """Test getting queue status."""
        # Add some tasks
        for i in range(3):
            task = Task(
                task_type=TaskType.DEVELOPMENT,
                title=f"Task {i}",
                description="Test",
            )
            await task_manager.add_task(task)

        status = await task_manager.get_queue_status()

        assert status["total_tasks"] == 3
        assert status["pending"] == 3
        assert status["queue_length"] == 3

    @pytest.mark.asyncio
    async def test_clear(self, task_manager, sample_task):
        """Test clearing all tasks."""
        await task_manager.add_task(sample_task)

        await task_manager.clear()

        status = await task_manager.get_queue_status()
        assert status["total_tasks"] == 0
