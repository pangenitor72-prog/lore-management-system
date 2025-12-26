# src/lms/orchestrator/sub_agents/development/convention_checker.py
"""
Convention Checker Sub-Agent.

Rule-based agent for checking code against project conventions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ...models import Task, TaskResult, SubAgentContext, TaskStatus
from ...protocols import AgentBackend, SubAgentCapability
from ..rule_agent import RuleBasedSubAgent, Rule


class ConventionCheckerAgent(RuleBasedSubAgent):
    """
    Specialized agent for checking code conventions.

    Uses deterministic rules to validate code against project standards.
    """

    def __init__(self, agent_id: Optional[str] = None):
        """
        Initialize the convention checker agent.

        Args:
            agent_id: Optional custom agent ID
        """
        rules = [
            self._import_order_rule(),
            self._enum_value_rule(),
            self._async_convention_rule(),
            self._logging_convention_rule(),
            self._type_hint_rule(),
            self._docstring_rule(),
        ]

        super().__init__(
            capabilities=[
                SubAgentCapability.CONVENTION_CHECKING,
                SubAgentCapability.FILE_ANALYSIS,
            ],
            rules=rules,
            agent_id=agent_id,
        )

    @property
    def backend_type(self) -> AgentBackend:
        """This is a rule-based agent."""
        return AgentBackend.RULE_BASED

    def _import_order_rule(self) -> Rule:
        """Check import ordering: stdlib -> third-party -> local."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(f.endswith(".py") for f in context.file_contents.keys())

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                lines = content.split("\n")
                seen_local = False
                seen_third_party = False

                for i, line in enumerate(lines, 1):
                    stripped = line.strip()

                    # Skip non-import lines
                    if not stripped.startswith(("import ", "from ")):
                        continue

                    # Detect import type
                    is_local = stripped.startswith(("from src.", "from .", "from .."))
                    is_stdlib = self._is_stdlib_import(stripped)

                    if is_local:
                        seen_local = True
                    elif not is_stdlib:
                        seen_third_party = True

                    # Check order violations
                    if seen_local and is_stdlib:
                        violations.append({
                            "file": path,
                            "line": i,
                            "message": "Standard library import after local import",
                            "severity": "medium",
                        })
                    if seen_local and not is_local and not is_stdlib:
                        violations.append({
                            "file": path,
                            "line": i,
                            "message": "Third-party import after local import",
                            "severity": "medium",
                        })

            return {"import_order_violations": violations}

        return Rule(
            name="import_order",
            condition=condition,
            action=action,
            priority=10,
            description="Check import ordering (stdlib -> third-party -> local)",
        )

    def _is_stdlib_import(self, line: str) -> bool:
        """Check if an import is from the standard library."""
        stdlib_modules = {
            "os", "sys", "re", "json", "typing", "pathlib", "datetime",
            "asyncio", "logging", "collections", "functools", "itertools",
            "uuid", "enum", "abc", "dataclasses", "contextlib", "traceback",
            "time", "io", "unittest", "copy", "hashlib", "base64",
        }

        # Extract module name
        if line.startswith("import "):
            module = line.split()[1].split(".")[0]
        elif line.startswith("from "):
            module = line.split()[1].split(".")[0]
        else:
            return False

        return module in stdlib_modules

    def _enum_value_rule(self) -> Rule:
        """Check that enums use .value when writing to database."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(f.endswith(".py") for f in context.file_contents.keys())

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            # Pattern to find enum usage without .value in db context
            enum_types = r"(EntityType|ApprovalStatus|ContradictionStatus|TaskStatus|TaskType)"
            pattern = rf"{enum_types}\.(\w+)(?!\.value)"

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                # Only check files that interact with database
                if "db." not in content and "execute(" not in content:
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    if re.search(pattern, line) and ".value" not in line:
                        violations.append({
                            "file": path,
                            "line": i,
                            "message": "Enum used without .value in database context",
                            "severity": "high",
                        })

            return {"enum_value_violations": violations}

        return Rule(
            name="enum_value",
            condition=condition,
            action=action,
            priority=8,
            description="Check enum .value usage in database operations",
        )

    def _async_convention_rule(self) -> Rule:
        """Check async/await usage conventions."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(f.endswith(".py") for f in context.file_contents.keys())

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                # Check for sync database calls in async functions
                in_async = False
                for i, line in enumerate(content.split("\n"), 1):
                    if "async def" in line:
                        in_async = True
                    elif line.strip().startswith("def ") and "async" not in line:
                        in_async = False

                    if in_async:
                        # Check for db operations without await
                        if "db.execute(" in line and "await" not in line:
                            violations.append({
                                "file": path,
                                "line": i,
                                "message": "Missing await on db.execute in async function",
                                "severity": "high",
                            })

            return {"async_violations": violations}

        return Rule(
            name="async_convention",
            condition=condition,
            action=action,
            priority=9,
            description="Check async/await usage",
        )

    def _logging_convention_rule(self) -> Rule:
        """Check logging conventions (use AuditLogger, not print)."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(
                "agent" in f.lower() or "service" in f.lower()
                for f in context.file_contents.keys()
            )

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    if "print(" in line and "# DEBUG" not in line and "#noqa" not in line:
                        violations.append({
                            "file": path,
                            "line": i,
                            "message": "Use AuditLogger instead of print()",
                            "severity": "low",
                        })

            return {"logging_violations": violations}

        return Rule(
            name="logging_convention",
            condition=condition,
            action=action,
            priority=5,
            description="Check logging convention (use AuditLogger)",
        )

    def _type_hint_rule(self) -> Rule:
        """Check for missing type hints on public functions."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(f.endswith(".py") for f in context.file_contents.keys())

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            # Pattern for function without return type hint
            func_pattern = r"^\s*(?:async\s+)?def\s+([a-z_][a-z0-9_]*)\s*\([^)]*\)\s*:"

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                for i, line in enumerate(content.split("\n"), 1):
                    match = re.match(func_pattern, line)
                    if match:
                        func_name = match.group(1)
                        # Skip private/dunder methods
                        if func_name.startswith("_"):
                            continue
                        # Check for return type
                        if "->" not in line:
                            violations.append({
                                "file": path,
                                "line": i,
                                "message": f"Function '{func_name}' missing return type hint",
                                "severity": "low",
                            })

            return {"type_hint_violations": violations}

        return Rule(
            name="type_hints",
            condition=condition,
            action=action,
            priority=3,
            description="Check for type hints on public functions",
        )

    def _docstring_rule(self) -> Rule:
        """Check for docstrings on public functions and classes."""

        def condition(task: Task, context: SubAgentContext) -> bool:
            return any(f.endswith(".py") for f in context.file_contents.keys())

        def action(task: Task, context: SubAgentContext) -> Dict[str, Any]:
            violations = []

            for path, content in context.file_contents.items():
                if not path.endswith(".py"):
                    continue

                lines = content.split("\n")
                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Check class definitions
                    if stripped.startswith("class ") and not stripped.startswith("class _"):
                        # Check if next non-empty line is a docstring
                        if not self._has_docstring(lines, i + 1):
                            violations.append({
                                "file": path,
                                "line": i + 1,
                                "message": f"Class missing docstring",
                                "severity": "medium",
                            })

                    # Check public function definitions
                    if re.match(r"^\s*(?:async\s+)?def\s+[a-z]", stripped):
                        func_match = re.match(r"^\s*(?:async\s+)?def\s+([a-z_][a-z0-9_]*)", stripped)
                        if func_match and not func_match.group(1).startswith("_"):
                            if not self._has_docstring(lines, i + 1):
                                violations.append({
                                    "file": path,
                                    "line": i + 1,
                                    "message": f"Function '{func_match.group(1)}' missing docstring",
                                    "severity": "low",
                                })

            return {"docstring_violations": violations}

        return Rule(
            name="docstrings",
            condition=condition,
            action=action,
            priority=2,
            description="Check for docstrings on public functions and classes",
        )

    def _has_docstring(self, lines: List[str], start_idx: int) -> bool:
        """Check if there's a docstring starting at the given line index."""
        for i in range(start_idx, min(start_idx + 3, len(lines))):
            line = lines[i].strip()
            if not line:
                continue
            if line.startswith('"""') or line.startswith("'''"):
                return True
            if line.startswith("#"):
                continue
            return False
        return False
