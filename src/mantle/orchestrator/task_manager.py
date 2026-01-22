# src/lms/orchestrator/task_manager.py
"""
Task Manager for the Orchestrator Agent System.

Manages task lifecycle, dependencies, and queue ordering.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import Task, TaskResult, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Manages task lifecycle, dependencies, and queue.

    Responsibilities:
    - Task creation and decomposition
    - Priority queue management
    - Dependency resolution
    - Result aggregation
    """

    def __init__(self):
        """Initialize the task manager."""
        self._tasks: Dict[str, Task] = {}
        self._results: Dict[str, TaskResult] = {}
        self._queue: List[str] = []  # Task IDs in priority order
        self._lock = asyncio.Lock()

    async def add_task(self, task: Task) -> str:
        """
        Add a task to the queue.

        Args:
            task: The task to add

        Returns:
            The task ID
        """
        async with self._lock:
            self._tasks[task.task_id] = task
            self._reorder_queue()
            logger.info(f"Added task {task.task_id}: {task.title}")
            return task.task_id

    async def add_subtasks(
        self, parent_id: str, subtasks: List[Task]
    ) -> List[str]:
        """
        Add subtasks to a parent task.

        Args:
            parent_id: The parent task ID
            subtasks: List of subtasks to add

        Returns:
            List of subtask IDs
        """
        async with self._lock:
            parent = self._tasks.get(parent_id)
            if not parent:
                raise ValueError(f"Parent task {parent_id} not found")

            subtask_ids = []
            for subtask in subtasks:
                subtask.parent_task_id = parent_id
                self._tasks[subtask.task_id] = subtask
                subtask_ids.append(subtask.task_id)

            parent.subtask_ids.extend(subtask_ids)
            self._reorder_queue()

            logger.info(
                f"Added {len(subtasks)} subtasks to parent {parent_id}"
            )
            return subtask_ids

    async def get_next_task(self) -> Optional[Task]:
        """
        Get the next ready task from the queue.

        A task is ready when:
        - Its status is PENDING
        - All its dependencies are COMPLETED

        Returns:
            The next ready task, or None if no tasks are ready
        """
        async with self._lock:
            for task_id in self._queue:
                task = self._tasks[task_id]
                if (
                    task.status == TaskStatus.PENDING
                    and self._dependencies_met(task)
                ):
                    task.status = TaskStatus.ASSIGNED
                    task.started_at = datetime.now(timezone.utc)
                    return task
            return None

    async def mark_running(self, task_id: str) -> None:
        """
        Mark a task as running.

        Args:
            task_id: The task ID
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.RUNNING

    async def complete_task(self, result: TaskResult) -> None:
        """
        Mark a task as completed with its result.

        Args:
            result: The task result
        """
        async with self._lock:
            task = self._tasks.get(result.task_id)
            if not task:
                logger.warning(
                    f"Task {result.task_id} not found for completion"
                )
                return

            task.status = result.status
            task.completed_at = datetime.now(timezone.utc)
            task.output_data = result.output
            self._results[result.task_id] = result

            # Update dependent tasks - remove this task from their depends_on
            for blocked_id in task.blocks:
                blocked = self._tasks.get(blocked_id)
                if blocked:
                    blocked.depends_on = [
                        d for d in blocked.depends_on if d != result.task_id
                    ]

            # Remove from queue
            if task.task_id in self._queue:
                self._queue.remove(task.task_id)

            self._reorder_queue()

            logger.info(
                f"Task {result.task_id} completed with status {result.status.value}"
            )

    async def fail_task(
        self, task_id: str, error_message: str, can_retry: bool = True
    ) -> bool:
        """
        Mark a task as failed.

        Args:
            task_id: The task ID
            error_message: Error description
            can_retry: Whether to allow retry

        Returns:
            True if the task was retried, False if it failed permanently
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if can_retry and task.retry_count < task.max_retries:
                # Retry the task
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                task.started_at = None
                self._reorder_queue()
                logger.info(
                    f"Task {task_id} will retry "
                    f"({task.retry_count}/{task.max_retries})"
                )
                return True
            else:
                # Fail permanently
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc)

                # Create a failure result
                self._results[task_id] = TaskResult(
                    task_id=task_id,
                    agent_id="task_manager",
                    status=TaskStatus.FAILED,
                    error_message=error_message,
                )

                # Remove from queue
                if task_id in self._queue:
                    self._queue.remove(task_id)

                # Block dependent tasks
                for blocked_id in task.blocks:
                    blocked = self._tasks.get(blocked_id)
                    if blocked:
                        blocked.status = TaskStatus.BLOCKED

                logger.error(f"Task {task_id} failed permanently: {error_message}")
                return False

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Args:
            task_id: The task ID

        Returns:
            True if cancelled, False if task not found or not cancellable
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            if task.status not in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
                return False

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)

            if task_id in self._queue:
                self._queue.remove(task_id)

            logger.info(f"Task {task_id} cancelled")
            return True

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: The task ID

        Returns:
            The task, or None if not found
        """
        return self._tasks.get(task_id)

    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get a task result by ID.

        Args:
            task_id: The task ID

        Returns:
            The result, or None if not found
        """
        return self._results.get(task_id)

    async def get_all_results(
        self, task_ids: List[str]
    ) -> Dict[str, TaskResult]:
        """
        Get multiple results at once.

        Args:
            task_ids: List of task IDs

        Returns:
            Dict mapping task IDs to results
        """
        return {
            tid: self._results[tid]
            for tid in task_ids
            if tid in self._results
        }

    async def get_pending_count(self) -> int:
        """Get the number of pending tasks."""
        return sum(
            1 for t in self._tasks.values() if t.status == TaskStatus.PENDING
        )

    async def get_running_count(self) -> int:
        """Get the number of running tasks."""
        return sum(
            1
            for t in self._tasks.values()
            if t.status in (TaskStatus.ASSIGNED, TaskStatus.RUNNING)
        )

    async def has_pending_work(self) -> bool:
        """Check if there is any pending or running work."""
        return any(
            t.status
            in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING)
            for t in self._tasks.values()
        )

    def _dependencies_met(self, task: Task) -> bool:
        """
        Check if all dependencies are completed.

        Args:
            task: The task to check

        Returns:
            True if all dependencies are completed
        """
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if not dep or dep.status != TaskStatus.COMPLETED:
                return False
        return True

    def _reorder_queue(self) -> None:
        """
        Reorder queue by priority and dependencies.

        Priority order: CRITICAL > HIGH > MEDIUM > LOW
        Within same priority: fewer dependencies first
        Within same dependencies: older tasks first
        """
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }

        # Get all pending/assigned tasks
        pending_tasks = [
            tid
            for tid, t in self._tasks.items()
            if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED)
        ]

        self._queue = sorted(
            pending_tasks,
            key=lambda tid: (
                priority_order.get(self._tasks[tid].priority, 2),
                len(self._tasks[tid].depends_on),
                self._tasks[tid].created_at,
            ),
        )

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status.

        Returns:
            Dict with task counts by status
        """
        status_counts = {status: 0 for status in TaskStatus}
        for task in self._tasks.values():
            status_counts[task.status] += 1

        return {
            "total_tasks": len(self._tasks),
            "pending": status_counts[TaskStatus.PENDING],
            "assigned": status_counts[TaskStatus.ASSIGNED],
            "running": status_counts[TaskStatus.RUNNING],
            "completed": status_counts[TaskStatus.COMPLETED],
            "failed": status_counts[TaskStatus.FAILED],
            "blocked": status_counts[TaskStatus.BLOCKED],
            "cancelled": status_counts[TaskStatus.CANCELLED],
            "queue_length": len(self._queue),
        }

    async def get_task_tree(self, task_id: str) -> Dict[str, Any]:
        """
        Get a task and all its subtasks as a tree.

        Args:
            task_id: The root task ID

        Returns:
            Dict representing the task tree
        """
        task = self._tasks.get(task_id)
        if not task:
            return {}

        def build_tree(t: Task) -> Dict[str, Any]:
            return {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status.value,
                "subtasks": [
                    build_tree(self._tasks[sid])
                    for sid in t.subtask_ids
                    if sid in self._tasks
                ],
            }

        return build_tree(task)

    async def clear(self) -> None:
        """Clear all tasks and results."""
        async with self._lock:
            self._tasks.clear()
            self._results.clear()
            self._queue.clear()
            logger.info("Task manager cleared")
