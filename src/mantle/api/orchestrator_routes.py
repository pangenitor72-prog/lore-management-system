# src/lms/api/orchestrator_routes.py
"""
API routes for the Orchestrator Agent System.

Provides endpoints for submitting tasks, checking status,
and managing the orchestrator.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field

from src.mantle.orchestrator import (
    Orchestrator,
    TaskType,
    TaskPriority,
)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ============================================================================
# Request/Response Models
# ============================================================================


class TaskSubmission(BaseModel):
    """Request model for submitting a task."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    task_type: str = Field(default="development")
    priority: str = Field(default="medium")
    relevant_files: List[str] = Field(default_factory=list)
    lore_entities: List[str] = Field(default_factory=list)
    auto_decompose: bool = Field(default=True)


class TaskResponse(BaseModel):
    """Response model for task submission."""

    task_id: str
    message: str


class StatusResponse(BaseModel):
    """Response model for orchestrator status."""

    session_id: str
    is_running: bool
    queue_status: dict
    agents_active: int
    agents_total: int
    duration_seconds: float
    total_tokens_used: int


class TaskStatusResponse(BaseModel):
    """Response model for individual task status."""

    task_id: str
    title: str
    status: str
    result: Optional[dict] = None


# ============================================================================
# Helper Functions
# ============================================================================


def get_orchestrator(request: Request) -> Orchestrator:
    """Get the orchestrator from app state."""
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not initialized. Check GEMINI_API_KEY.",
        )
    return orchestrator


def parse_task_type(value: str) -> TaskType:
    """Parse task type string to enum."""
    mapping = {
        "development": TaskType.DEVELOPMENT,
        "lore_management": TaskType.LORE_MANAGEMENT,
        "lore": TaskType.LORE_MANAGEMENT,
        "analysis": TaskType.ANALYSIS,
        "maintenance": TaskType.MAINTENANCE,
    }
    return mapping.get(value.lower(), TaskType.DEVELOPMENT)


def parse_priority(value: str) -> TaskPriority:
    """Parse priority string to enum."""
    mapping = {
        "critical": TaskPriority.CRITICAL,
        "high": TaskPriority.HIGH,
        "medium": TaskPriority.MEDIUM,
        "low": TaskPriority.LOW,
    }
    return mapping.get(value.lower(), TaskPriority.MEDIUM)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/tasks", response_model=TaskResponse)
async def submit_task(
    submission: TaskSubmission,
    request: Request,
) -> TaskResponse:
    """
    Submit a new task to the orchestrator.

    The orchestrator will decompose complex tasks into subtasks
    and coordinate their execution.
    """
    orchestrator = get_orchestrator(request)

    task_id = await orchestrator.submit_task(
        title=submission.title,
        description=submission.description,
        task_type=parse_task_type(submission.task_type),
        priority=parse_priority(submission.priority),
        relevant_files=submission.relevant_files,
        lore_entities=submission.lore_entities,
        auto_decompose=submission.auto_decompose,
    )

    return TaskResponse(
        task_id=task_id,
        message=f"Task '{submission.title}' submitted successfully",
    )


@router.post("/tasks/{task_id}/run", response_model=dict)
async def run_single_task(
    task_id: str,
    request: Request,
) -> dict:
    """
    Run a single task by ID.

    Returns the task result when complete.
    """
    orchestrator = get_orchestrator(request)

    try:
        result = await orchestrator.run_single_task(task_id)
        return {
            "task_id": task_id,
            "status": result.status.value,
            "output": result.output,
            "warnings": result.warnings,
            "execution_time_ms": result.execution_time_ms,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=dict)
async def run_orchestrator(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Start the orchestrator to run all pending tasks.

    Runs in the background and returns immediately.
    """
    orchestrator = get_orchestrator(request)

    if orchestrator.is_running:
        raise HTTPException(
            status_code=409,
            detail="Orchestrator is already running",
        )

    # Run in background
    background_tasks.add_task(orchestrator.run)

    return {
        "message": "Orchestrator started",
        "session_id": orchestrator.state.session_id,
    }


@router.post("/stop")
async def stop_orchestrator(request: Request) -> dict:
    """Stop the orchestrator gracefully."""
    orchestrator = get_orchestrator(request)
    await orchestrator.stop()
    return {"message": "Orchestrator stopped"}


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    """Get the current orchestrator status."""
    orchestrator = get_orchestrator(request)
    status = await orchestrator.get_status()
    return StatusResponse(**status)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    request: Request,
) -> TaskStatusResponse:
    """Get the status of a specific task."""
    orchestrator = get_orchestrator(request)

    task = await orchestrator._task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await orchestrator._task_manager.get_result(task_id)

    return TaskStatusResponse(
        task_id=task.task_id,
        title=task.title,
        status=task.status.value,
        result=result.output if result else None,
    )


@router.get("/tasks/{task_id}/tree")
async def get_task_tree(
    task_id: str,
    request: Request,
) -> dict:
    """Get a task and all its subtasks as a tree."""
    orchestrator = get_orchestrator(request)

    tree = await orchestrator._task_manager.get_task_tree(task_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Task not found")

    return tree
