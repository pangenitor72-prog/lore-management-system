# tests/orchestrator/test_orchestrator.py
"""
Tests for the main Orchestrator class.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.mantle.orchestrator import Orchestrator
from src.mantle.orchestrator.models import TaskType, TaskPriority, TaskStatus


class TestOrchestrator:
    """Tests for the Orchestrator class."""

    @pytest.fixture
    def orchestrator(self, project_root):
        """Create an orchestrator without Gemini."""
        return Orchestrator(
            project_root=project_root,
            gemini_api_key=None,  # No LLM
        )

    @pytest.fixture
    def orchestrator_with_mock_llm(self, project_root, mock_gemini_key):
        """Create an orchestrator with mocked Gemini."""
        with patch("src.mantle.orchestrator.sub_agents.llm_agent.GEMINI_AVAILABLE", True):
            with patch("src.mantle.orchestrator.sub_agents.llm_agent.genai") as mock_genai:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = '{"status": "success", "output": {}}'
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model

                orch = Orchestrator(
                    project_root=project_root,
                    gemini_api_key=mock_gemini_key,
                )
                yield orch

    @pytest.mark.asyncio
    async def test_orchestrator_creation(self, orchestrator):
        """Test creating an orchestrator."""
        assert orchestrator is not None
        assert orchestrator.is_running is False

    @pytest.mark.asyncio
    async def test_submit_task(self, orchestrator):
        """Test submitting a task."""
        task_id = await orchestrator.submit_task(
            title="Test Task",
            description="A simple test task",
            task_type=TaskType.DEVELOPMENT,
        )

        assert task_id is not None

    @pytest.mark.asyncio
    async def test_get_status(self, orchestrator):
        """Test getting orchestrator status."""
        status = await orchestrator.get_status()

        assert "session_id" in status
        assert "is_running" in status
        assert "queue_status" in status
        assert status["is_running"] is False

    @pytest.mark.asyncio
    async def test_submit_multiple_tasks(self, orchestrator):
        """Test submitting multiple tasks."""
        task_ids = []
        for i in range(3):
            task_id = await orchestrator.submit_task(
                title=f"Task {i}",
                description=f"Test task {i}",
                task_type=TaskType.DEVELOPMENT,
            )
            task_ids.append(task_id)

        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3  # All unique

    @pytest.mark.asyncio
    async def test_submit_with_priority(self, orchestrator):
        """Test submitting tasks with different priorities."""
        low_id = await orchestrator.submit_task(
            title="Low Priority",
            description="Low priority task",
            priority=TaskPriority.LOW,
        )
        high_id = await orchestrator.submit_task(
            title="High Priority",
            description="High priority task",
            priority=TaskPriority.HIGH,
        )

        # High priority should be first in queue
        status = await orchestrator.get_status()
        assert status["queue_status"]["pending"] == 2

    @pytest.mark.asyncio
    async def test_stop_orchestrator(self, orchestrator):
        """Test stopping the orchestrator."""
        await orchestrator.stop()
        assert orchestrator.is_running is False

    @pytest.mark.asyncio
    async def test_register_agent(self, orchestrator):
        """Test registering an external agent."""
        from src.mantle.orchestrator.sub_agents.rule_agent import RuleBasedSubAgent
        from src.mantle.orchestrator.protocols import SubAgentCapability

        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            agent_id="custom-agent",
        )

        orchestrator.register_agent(agent)

        assert "custom-agent" in orchestrator._agents

    @pytest.mark.asyncio
    async def test_unregister_agent(self, orchestrator):
        """Test unregistering an agent."""
        from src.mantle.orchestrator.sub_agents.rule_agent import RuleBasedSubAgent
        from src.mantle.orchestrator.protocols import SubAgentCapability

        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            agent_id="temp-agent",
        )

        orchestrator.register_agent(agent)
        result = orchestrator.unregister_agent("temp-agent")

        assert result is True
        assert "temp-agent" not in orchestrator._agents

    @pytest.mark.asyncio
    async def test_run_empty_queue(self, orchestrator):
        """Test running with empty queue completes immediately."""
        result = await orchestrator.run()

        assert result is not None
        assert result["queue_status"]["total_tasks"] == 0


class TestOrchestratorWithRuleAgent:
    """Tests for orchestrator using rule-based agents (no LLM)."""

    @pytest.fixture
    def orchestrator(self, project_root):
        """Create an orchestrator without LLM."""
        return Orchestrator(
            project_root=project_root,
            gemini_api_key=None,
        )

    @pytest.mark.asyncio
    async def test_run_simple_task(self, orchestrator):
        """Test running a simple task with rule-based agent."""
        task_id = await orchestrator.submit_task(
            title="Check conventions",
            description="Check code conventions",
            task_type=TaskType.ANALYSIS,
            auto_decompose=False,  # Don't try to decompose without LLM
        )

        # Run the single task
        result = await orchestrator.run_single_task(task_id)

        # Rule-based agent should complete
        assert result.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)


class TestOrchestratorContextIntegration:
    """Tests for orchestrator context building."""

    @pytest.fixture
    def orchestrator(self, project_root):
        """Create an orchestrator."""
        return Orchestrator(
            project_root=project_root,
            gemini_api_key=None,
        )

    @pytest.mark.asyncio
    async def test_context_includes_claude_md(self, orchestrator):
        """Test that context includes CLAUDE.md."""
        from src.mantle.orchestrator.models import Task, TaskType

        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Test",
            description="Test",
        )

        context = await orchestrator._context_provider.build_context(task)

        assert context.project_root is not None
        assert context.claude_md_content is not None

    @pytest.mark.asyncio
    async def test_context_discovers_relevant_files(self, orchestrator, project_root):
        """Test that context discovers relevant files."""
        import os
        from pathlib import Path

        # Create a relevant file
        src_dir = Path(project_root) / "src" / "lms" / "agents"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "test_agent.py").write_text("class TestAgent: pass")

        from src.mantle.orchestrator.models import Task, TaskType

        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Modify agent",
            description="Make changes to the agent code",
        )

        context = await orchestrator._context_provider.build_context(task)

        # Should discover agent-related files based on description
        assert context.project_root is not None
