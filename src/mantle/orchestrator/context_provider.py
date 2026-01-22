# src/lms/orchestrator/context_provider.py
"""
Context Provider for the Orchestrator Agent System.

Discovers and injects relevant context for sub-agents, including
project documentation, relevant files, and lore entities.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .models import Task, SubAgentContext, TaskType

if TYPE_CHECKING:
    from src.mantle.db.neo4j_adapter import Neo4jDatabase

logger = logging.getLogger(__name__)


class ContextProvider:
    """
    Discovers and injects relevant context for sub-agents.

    Responsibilities:
    - Read project documentation (CLAUDE.md, docs/)
    - Discover relevant files based on task
    - Query lore entities for lore-related tasks
    - Build SubAgentContext for execution
    """

    # Key documentation files to always include
    CORE_DOCS = [
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/CONVENTIONS.md",
        "docs/NEO4J_SCHEMA.md",
    ]

    # File patterns for different task types
    TASK_TYPE_PATTERNS = {
        TaskType.DEVELOPMENT: [
            "src/lms/**/*.py",
            "tests/**/*.py",
        ],
        TaskType.LORE_MANAGEMENT: [
            "src/lms/agents/*.py",
            "src/lms/core/models.py",
        ],
        TaskType.ANALYSIS: [
            "docs/**/*.md",
            "src/**/*.py",
        ],
    }

    def __init__(
        self,
        project_root: str,
        neo4j_db: Optional["Neo4jDatabase"] = None,
        max_file_size: int = 50000,
        max_files: int = 10,
    ):
        """
        Initialize the context provider.

        Args:
            project_root: Root directory of the project
            neo4j_db: Optional Neo4j database connection for lore queries
            max_file_size: Maximum file size to read (bytes)
            max_files: Maximum number of files to include in context
        """
        self._project_root = Path(project_root)
        self._db = neo4j_db
        self._max_file_size = max_file_size
        self._max_files = max_files
        self._doc_cache: Dict[str, str] = {}

    async def build_context(self, task: Task) -> SubAgentContext:
        """
        Build comprehensive context for a task.

        Args:
            task: The task to build context for

        Returns:
            SubAgentContext with all relevant information
        """
        context = SubAgentContext(project_root=str(self._project_root))

        # Load CLAUDE.md (always included)
        claude_md = await self._read_file("CLAUDE.md")
        if claude_md:
            context.claude_md_content = claude_md

        # Load architecture docs
        for doc_path in self.CORE_DOCS:
            content = await self._read_file(doc_path)
            if content:
                context.architecture_docs[doc_path] = content

        # Load explicitly requested files
        if task.relevant_files:
            for file_path in task.relevant_files[: self._max_files]:
                content = await self._read_file(file_path)
                if content:
                    context.file_contents[file_path] = content

        # Discover additional relevant files based on task
        additional_files = await self._discover_relevant_files(task)
        for file_path, content in additional_files.items():
            if file_path not in context.file_contents:
                if len(context.file_contents) < self._max_files:
                    context.file_contents[file_path] = content

        # Load lore entities if applicable
        if task.lore_entities and self._db:
            context.lore_entities = await self._load_lore_entities(
                task.lore_entities
            )

        # Load additional lore context for lore management tasks
        if task.task_type == TaskType.LORE_MANAGEMENT and self._db:
            extra_entities = await self._discover_related_entities(task)
            for entity in extra_entities:
                if entity not in context.lore_entities:
                    context.lore_entities.append(entity)

        return context

    async def _read_file(self, relative_path: str) -> Optional[str]:
        """
        Read a file from the project.

        Args:
            relative_path: Path relative to project root

        Returns:
            File contents, or None if not readable
        """
        # Check cache first
        if relative_path in self._doc_cache:
            return self._doc_cache[relative_path]

        full_path = self._project_root / relative_path

        try:
            # Run file read in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def read_file() -> Optional[str]:
                if not full_path.exists():
                    return None
                if not full_path.is_file():
                    return None
                if full_path.stat().st_size > self._max_file_size:
                    logger.debug(f"File too large: {relative_path}")
                    return None
                return full_path.read_text(encoding="utf-8", errors="replace")

            content = await loop.run_in_executor(None, read_file)

            if content:
                self._doc_cache[relative_path] = content

            return content

        except Exception as e:
            logger.debug(f"Could not read {relative_path}: {e}")
            return None

    async def _discover_relevant_files(
        self, task: Task
    ) -> Dict[str, str]:
        """
        Discover files relevant to the task based on description.

        Args:
            task: The task to find files for

        Returns:
            Dict mapping file paths to contents
        """
        relevant: Dict[str, str] = {}
        description_lower = task.description.lower()
        title_lower = task.title.lower()
        combined = f"{title_lower} {description_lower}"

        # Pattern matching for common task patterns
        patterns_to_check: List[str] = []

        # Development task patterns
        if "agent" in combined:
            patterns_to_check.append("src/lms/agents/*.py")
        if "model" in combined:
            patterns_to_check.append("src/lms/core/models.py")
        if "api" in combined or "route" in combined:
            patterns_to_check.append("src/lms/api/*.py")
        if "test" in combined:
            patterns_to_check.append("tests/*.py")
        if "prompt" in combined:
            patterns_to_check.append("src/lms/prompts/*.py")
        if "service" in combined:
            patterns_to_check.append("src/lms/services/*.py")
        if "database" in combined or "neo4j" in combined:
            patterns_to_check.append("src/lms/db/*.py")

        # Lore task patterns
        if "entity" in combined or "character" in combined:
            patterns_to_check.append("src/lms/core/entity_factory.py")
        if "contradiction" in combined:
            patterns_to_check.append("src/lms/services/contradiction_service.py")
        if "personality" in combined or "ocean" in combined:
            patterns_to_check.append("src/lms/personality.py")

        # AIRPG patterns
        if "airpg" in combined or "runtime" in combined:
            patterns_to_check.append("src/airpg/runtime/*.py")
        if "engine" in combined:
            patterns_to_check.append("src/airpg/engine/*.py")

        # Glob for matching files
        for pattern in patterns_to_check:
            files = await self._glob_files(pattern, limit=3)
            relevant.update(files)

            if len(relevant) >= self._max_files:
                break

        return relevant

    async def _glob_files(
        self, pattern: str, limit: int = 5
    ) -> Dict[str, str]:
        """
        Glob files and read their contents.

        Args:
            pattern: Glob pattern to match
            limit: Maximum files to return

        Returns:
            Dict mapping file paths to contents
        """
        results: Dict[str, str] = {}

        try:
            loop = asyncio.get_event_loop()

            def do_glob() -> List[Path]:
                return list(self._project_root.glob(pattern))[:limit]

            files = await loop.run_in_executor(None, do_glob)

            for file_path in files:
                relative = str(file_path.relative_to(self._project_root))
                content = await self._read_file(relative)
                if content:
                    results[relative] = content

        except Exception as e:
            logger.debug(f"Glob failed for {pattern}: {e}")

        return results

    async def _load_lore_entities(
        self, entity_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Load lore entities from Neo4j.

        Args:
            entity_names: Names of entities to load

        Returns:
            List of entity dictionaries
        """
        if not self._db:
            return []

        entities = []

        for name in entity_names[:10]:  # Limit to 10 entities
            query = """
            MATCH (e)
            WHERE toLower(e.name) = toLower($name)
               OR toLower(e.canonical_name) = toLower($name)
            RETURN e.name AS name,
                   e.entity_type AS type,
                   e.description AS description,
                   e.canon_id AS canon_id,
                   labels(e) AS labels
            LIMIT 1
            """

            try:
                results = await self._db.execute(query, {"name": name})
                if results:
                    record = results[0]
                    entities.append({
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "description": record.get("description"),
                        "canon_id": record.get("canon_id"),
                        "labels": record.get("labels", []),
                    })
            except Exception as e:
                logger.warning(f"Failed to load entity {name}: {e}")

        return entities

    async def _discover_related_entities(
        self, task: Task
    ) -> List[Dict[str, Any]]:
        """
        Discover entities related to the task description.

        Uses keyword extraction to find relevant entities.

        Args:
            task: The task to find entities for

        Returns:
            List of related entity dictionaries
        """
        if not self._db:
            return []

        # Extract potential entity names from description
        # Simple approach: look for capitalized words
        import re

        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", task.description)

        if not words:
            return []

        entities = []

        for word in words[:5]:  # Limit searches
            query = """
            MATCH (e)
            WHERE toLower(e.name) CONTAINS toLower($word)
            RETURN e.name AS name,
                   e.entity_type AS type,
                   e.description AS description
            LIMIT 2
            """

            try:
                results = await self._db.execute(query, {"word": word})
                for record in results:
                    entity = {
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "description": record.get("description"),
                    }
                    if entity not in entities:
                        entities.append(entity)
            except Exception as e:
                logger.debug(f"Entity search failed for {word}: {e}")

        return entities[:5]  # Limit total

    async def get_file_summary(self, file_path: str) -> Optional[str]:
        """
        Get a brief summary of a file.

        Args:
            file_path: Path to the file

        Returns:
            Summary string, or None if file not readable
        """
        content = await self._read_file(file_path)
        if not content:
            return None

        lines = content.split("\n")

        # Extract docstring if present
        if lines and lines[0].strip().startswith('"""'):
            docstring_lines = []
            for i, line in enumerate(lines):
                docstring_lines.append(line)
                if i > 0 and '"""' in line:
                    break
            return "\n".join(docstring_lines)

        # Return first few lines
        return "\n".join(lines[:10])

    def clear_cache(self) -> None:
        """Clear the document cache."""
        self._doc_cache.clear()
