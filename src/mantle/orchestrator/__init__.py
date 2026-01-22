# src/lms/orchestrator/__init__.py
"""
Orchestrator Agent System

A multi-agent orchestration system for the Lore Management System that coordinates
sub-agents to complete development and lore management tasks.

Usage:
    from src.mantle.orchestrator import Orchestrator
    from src.mantle.orchestrator.models import TaskType, TaskPriority

    orchestrator = Orchestrator(
        project_root=".",
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
    )

    task_id = await orchestrator.submit_task(
        title="Add pagination to entities API",
        description="Implement cursor-based pagination",
        task_type=TaskType.DEVELOPMENT,
    )

    summary = await orchestrator.run()
"""

from .orchestrator import Orchestrator
from .models import (
    Task,
    TaskResult,
    TaskStatus,
    TaskPriority,
    TaskType,
    SubAgentContext,
    OrchestratorState,
)
from .protocols import (
    AgentBackend,
    SubAgentCapability,
    SubAgentProtocol,
)
from .task_manager import TaskManager
from .context_provider import ContextProvider

__all__ = [
    # Main orchestrator
    "Orchestrator",
    # Models
    "Task",
    "TaskResult",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    "SubAgentContext",
    "OrchestratorState",
    # Protocols
    "AgentBackend",
    "SubAgentCapability",
    "SubAgentProtocol",
    # Components
    "TaskManager",
    "ContextProvider",
]
