# src/lms/orchestrator/models.py
"""
Data models for the Orchestrator Agent System.

All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task in the queue."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(str, Enum):
    """High-level task categories."""
    DEVELOPMENT = "development"
    LORE_MANAGEMENT = "lore_management"
    ANALYSIS = "analysis"
    MAINTENANCE = "maintenance"


def _generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class Task(BaseModel):
    """
    Represents a task to be executed by a sub-agent.

    Tasks can be hierarchical (parent/child) and have dependencies
    on other tasks.
    """
    task_id: str = Field(default_factory=_generate_uuid)
    task_type: TaskType
    title: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING

    # Task hierarchy
    parent_task_id: Optional[str] = None
    subtask_ids: List[str] = Field(default_factory=list)

    # Dependencies
    depends_on: List[str] = Field(default_factory=list)  # Task IDs that must complete first
    blocks: List[str] = Field(default_factory=list)  # Task IDs that depend on this task

    # Assignment
    assigned_agent_id: Optional[str] = None
    required_capabilities: List[str] = Field(default_factory=list)

    # Input/Output
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None

    # Metadata
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    # Context hints for the sub-agent
    relevant_files: List[str] = Field(default_factory=list)
    lore_entities: List[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class TaskResult(BaseModel):
    """
    Result of a task execution by a sub-agent.

    Contains the output, any artifacts created, and execution metadata.
    """
    task_id: str
    agent_id: str
    status: TaskStatus

    # Output
    output: Dict[str, Any] = Field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)  # Files, entities created

    # Execution details
    execution_time_ms: int = 0
    tokens_used: int = 0

    # Error handling
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    # Follow-up
    suggested_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class SubAgentContext(BaseModel):
    """
    Context injected into sub-agents for task execution.

    Provides project information, relevant files, and lore context.
    """
    # Project context
    project_root: str
    claude_md_content: Optional[str] = None
    architecture_docs: Dict[str, str] = Field(default_factory=dict)

    # Relevant files for the task
    file_contents: Dict[str, str] = Field(default_factory=dict)
    file_summaries: Dict[str, str] = Field(default_factory=dict)

    # Lore context (for lore management tasks)
    lore_entities: List[Dict[str, Any]] = Field(default_factory=list)
    campaign_context: Optional[Dict[str, Any]] = None

    # Execution context
    session_id: str = Field(default_factory=_generate_uuid)
    parent_task_results: Dict[str, TaskResult] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class OrchestratorState(BaseModel):
    """
    State of the orchestrator session.

    Tracks active agents, task queue, and statistics.
    """
    session_id: str = Field(default_factory=_generate_uuid)
    active_agents: Dict[str, str] = Field(default_factory=dict)  # agent_id -> status
    task_queue: List[str] = Field(default_factory=list)  # Task IDs in priority order
    completed_tasks: List[str] = Field(default_factory=list)
    failed_tasks: List[str] = Field(default_factory=list)

    # Statistics
    total_tasks_processed: int = 0
    total_tokens_used: int = 0
    session_started_at: datetime = Field(default_factory=_utcnow)

    model_config = {"extra": "forbid"}


class AgentRegistration(BaseModel):
    """
    Registration information for a sub-agent.

    Used when registering agents with the orchestrator.
    """
    agent_id: str
    agent_type: str
    capabilities: List[str]
    backend_type: str
    max_concurrent_tasks: int = 1
    registered_at: datetime = Field(default_factory=_utcnow)

    model_config = {"extra": "forbid"}
