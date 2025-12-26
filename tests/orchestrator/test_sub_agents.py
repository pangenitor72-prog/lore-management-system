# tests/orchestrator/test_sub_agents.py
"""
Tests for sub-agents.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.lms.orchestrator.models import (
    Task,
    TaskResult,
    TaskStatus,
    TaskType,
    SubAgentContext,
)
from src.lms.orchestrator.protocols import AgentBackend, SubAgentCapability
from src.lms.orchestrator.sub_agents.rule_agent import (
    RuleBasedSubAgent,
    Rule,
    create_keyword_rule,
)
from src.lms.orchestrator.sub_agents.development.convention_checker import (
    ConventionCheckerAgent,
)


class TestRuleBasedSubAgent:
    """Tests for the RuleBasedSubAgent class."""

    @pytest.fixture
    def simple_rule(self):
        """Create a simple test rule."""
        return Rule(
            name="test_rule",
            condition=lambda t, c: "test" in t.title.lower(),
            action=lambda t, c: {"matched": True},
            priority=10,
        )

    @pytest.mark.asyncio
    async def test_agent_creation(self, simple_rule):
        """Test creating a rule-based agent."""
        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            rules=[simple_rule],
        )

        assert agent.backend_type == AgentBackend.RULE_BASED
        assert SubAgentCapability.FILE_ANALYSIS in agent.capabilities
        assert len(agent.rules) == 1

    @pytest.mark.asyncio
    async def test_execute_matching_rule(self, simple_rule, sample_context):
        """Test executing a matching rule."""
        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            rules=[simple_rule],
        )

        task = Task(
            task_type=TaskType.ANALYSIS,
            title="Test Task",
            description="A test",
        )

        result = await agent.execute(task, sample_context)

        assert result.status == TaskStatus.COMPLETED
        assert result.output["matched_rules"] == ["test_rule"]

    @pytest.mark.asyncio
    async def test_execute_no_matching_rule(self, simple_rule, sample_context):
        """Test executing when no rule matches."""
        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            rules=[simple_rule],
        )

        task = Task(
            task_type=TaskType.ANALYSIS,
            title="Other Task",
            description="Not a test",
        )

        result = await agent.execute(task, sample_context)

        assert result.status == TaskStatus.COMPLETED
        assert result.output["message"] == "No matching rules found"

    @pytest.mark.asyncio
    async def test_add_rule(self, simple_rule):
        """Test adding a rule to an agent."""
        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            rules=[],
        )

        assert len(agent.rules) == 0

        agent.add_rule(simple_rule)

        assert len(agent.rules) == 1

    @pytest.mark.asyncio
    async def test_rule_priority_order(self, sample_context):
        """Test that rules execute in priority order."""
        execution_order = []

        rule1 = Rule(
            name="low_priority",
            condition=lambda t, c: True,
            action=lambda t, c: {"order": execution_order.append(1) or 1},
            priority=1,
        )
        rule2 = Rule(
            name="high_priority",
            condition=lambda t, c: True,
            action=lambda t, c: {"order": execution_order.append(2) or 2},
            priority=10,
        )

        agent = RuleBasedSubAgent(
            capabilities=[SubAgentCapability.FILE_ANALYSIS],
            rules=[rule1, rule2],
        )

        task = Task(
            task_type=TaskType.ANALYSIS,
            title="Test",
            description="Test",
        )

        await agent.execute(task, sample_context)

        # High priority should execute first
        assert execution_order == [2, 1]


class TestConventionCheckerAgent:
    """Tests for the ConventionCheckerAgent class."""

    @pytest.fixture
    def checker_agent(self):
        """Create a convention checker agent."""
        return ConventionCheckerAgent()

    @pytest.mark.asyncio
    async def test_agent_backend_type(self, checker_agent):
        """Test that agent has correct backend type."""
        assert checker_agent.backend_type == AgentBackend.RULE_BASED

    @pytest.mark.asyncio
    async def test_check_import_order(self, checker_agent):
        """Test import order checking."""
        context = SubAgentContext(
            project_root="/test",
            file_contents={
                "test.py": """from src.local import thing
import os  # stdlib after local - violation!
"""
            },
        )

        task = Task(
            task_type=TaskType.ANALYSIS,
            title="Check conventions",
            description="Check code",
        )

        result = await checker_agent.execute(task, context)

        assert result.status == TaskStatus.COMPLETED
        # Should find the import order violation
        violations = result.output.get("results", {}).get(
            "import_order_violations", []
        )
        assert len(violations) > 0

    @pytest.mark.asyncio
    async def test_check_print_statements(self, checker_agent):
        """Test logging convention checking."""
        context = SubAgentContext(
            project_root="/test",
            file_contents={
                "agent.py": """def some_function():
    print("debugging")  # Should use AuditLogger
"""
            },
        )

        task = Task(
            task_type=TaskType.ANALYSIS,
            title="Check conventions",
            description="Check agent code",
        )

        result = await checker_agent.execute(task, context)

        assert result.status == TaskStatus.COMPLETED


class TestCreateKeywordRule:
    """Tests for the create_keyword_rule helper."""

    @pytest.mark.asyncio
    async def test_keyword_match(self, sample_context):
        """Test keyword matching."""
        rule = create_keyword_rule(
            name="test_keyword",
            keywords=["refactor", "cleanup"],
            action=lambda t, c: {"matched": True},
        )

        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Refactor Code",
            description="Clean up the module",
        )

        assert rule.matches(task, sample_context) is True

    @pytest.mark.asyncio
    async def test_keyword_no_match(self, sample_context):
        """Test when keywords don't match."""
        rule = create_keyword_rule(
            name="test_keyword",
            keywords=["refactor", "cleanup"],
            action=lambda t, c: {"matched": True},
        )

        task = Task(
            task_type=TaskType.DEVELOPMENT,
            title="Add Feature",
            description="Implement new feature",
        )

        assert rule.matches(task, sample_context) is False
