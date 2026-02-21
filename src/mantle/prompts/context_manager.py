"""
Prompt Context Manager - Token-aware context injection for DM prompts.

Manages the assembly of DM prompts with priority-based token budgeting.
Lower-priority sections are skipped when budget is tight, ensuring
critical context always fits within limits.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import IntEnum
import logging

logger = logging.getLogger(__name__)


class ContextPriority(IntEnum):
    """Priority tiers for context sections. Lower = more important."""
    CRITICAL = 1   # Must always include (base system, current scene, player input)
    HIGH = 2       # Include unless severely constrained (history, world lore)
    MEDIUM = 3     # Include if budget allows (graph, arc, memory)
    LOW = 4        # Nice to have, skip first (storytelling prefs, semantic search)


@dataclass
class ContextSection:
    """A section of context to potentially include in the prompt."""
    name: str
    content: str
    priority: ContextPriority
    max_tokens: int
    actual_tokens: int = 0
    included: bool = False
    truncated: bool = False


@dataclass
class PromptBudget:
    """Token budget configuration."""
    total_budget: int = 16000  # Doubled from 8000
    reserve_tokens: int = 900  # Buffer for model response overhead (doubled)

    # Per-section token limits (all doubled)
    section_limits: Dict[str, int] = field(default_factory=lambda: {
        # CRITICAL - always included
        "base_system": 5000,
        "current_scene": 1500,
        "player_input": 500,
        "character_context": 600,
        # HIGH - include unless severely constrained
        "history": 1200,
        "world_lore": 800,
        "npc_state_overlay": 300,
        # MEDIUM - include if budget allows
        "knowledge_graph": 1000,
        "arc_context": 400,
        "npc_personality": 400,
        "memory_context": 600,
        # LOW - skip if budget tight
        "storytelling_prefs": 300,
        "auditor_warnings": 200,
        "semantic_search": 300,
        "decoherence_context": 300,
        "investment_context": 200,
        "catalyst_directive": 150,
        "guidance_instruction": 200,
    })


class PromptContextManager:
    """
    Manages context injection with token budget awareness.

    Assembles DM prompts by:
    1. Accepting context sections with assigned priorities
    2. Sorting by priority (CRITICAL first)
    3. Including sections until budget is exhausted
    4. Truncating oversized sections to their max_tokens limit
    5. Reporting what was included/excluded

    Usage:
        manager = PromptContextManager()
        manager.add("character_context", char_str, ContextPriority.CRITICAL)
        manager.add("memory_context", memory_str, ContextPriority.MEDIUM)
        prompt_parts, report = manager.build()
        final_prompt = "\\n\\n".join(prompt_parts)
    """

    def __init__(self, budget: Optional[PromptBudget] = None):
        self.budget = budget or PromptBudget()
        self.sections: List[ContextSection] = []
        self.tokens_used = 0

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.

        Uses ~3.5 chars per token for English text (conservative estimate).
        This matches the existing estimation in game_routes.py.
        """
        if not text:
            return 0
        return max(1, len(text) // 3)

    def add(
        self,
        name: str,
        content: str,
        priority: ContextPriority,
        max_tokens: Optional[int] = None,
    ) -> None:
        """
        Add a context section to be considered for inclusion.

        Args:
            name: Section identifier (e.g., "memory_context")
            content: The actual text content
            priority: How important this section is
            max_tokens: Override default limit for this section
        """
        # Skip empty content
        if not content or not content.strip():
            return

        # Get limit from budget or use provided override
        limit = max_tokens or self.budget.section_limits.get(name, 200)
        tokens = self.estimate_tokens(content)

        section = ContextSection(
            name=name,
            content=content,
            priority=priority,
            max_tokens=limit,
            actual_tokens=tokens,
        )
        self.sections.append(section)

    def build(self) -> Tuple[List[str], Dict[str, Any]]:
        """
        Build the final prompt parts, respecting token budget.

        Sections are sorted by priority (lower = more important).
        Sections are included until the budget is exhausted.
        Oversized sections are truncated to their max_tokens limit.

        Returns:
            Tuple of:
              - List of content strings to include in prompt
              - Report dict with budget usage details
        """
        available = self.budget.total_budget - self.budget.reserve_tokens

        # Sort by priority (CRITICAL=1 first, LOW=4 last)
        sorted_sections = sorted(self.sections, key=lambda s: (s.priority, s.name))

        included_parts = []
        included_names = []
        excluded_names = []

        for section in sorted_sections:
            # Calculate tokens needed (respect section limit)
            tokens_needed = min(section.actual_tokens, section.max_tokens)

            if self.tokens_used + tokens_needed <= available:
                # Section fits - include it
                content = section.content

                # Truncate if over section limit
                if section.actual_tokens > section.max_tokens:
                    char_limit = section.max_tokens * 3  # Reverse token estimate
                    content = content[:char_limit].rstrip() + "..."
                    section.truncated = True
                    logger.debug(
                        f"[PROMPT BUDGET] Truncated '{section.name}' "
                        f"from {section.actual_tokens} to {section.max_tokens} tokens"
                    )

                included_parts.append(content)
                section.included = True
                self.tokens_used += tokens_needed
                included_names.append(section.name)
            else:
                # Section doesn't fit - exclude it
                excluded_names.append(section.name)

                # Log warning if CRITICAL section excluded
                if section.priority == ContextPriority.CRITICAL:
                    logger.warning(
                        f"[PROMPT BUDGET] CRITICAL section '{section.name}' "
                        f"excluded due to budget ({self.tokens_used}/{available} used)"
                    )
                else:
                    logger.debug(
                        f"[PROMPT BUDGET] Excluded '{section.name}' "
                        f"({section.actual_tokens} tokens, priority {section.priority.name})"
                    )

        # Build report
        report = {
            "total_budget": self.budget.total_budget,
            "reserve_tokens": self.budget.reserve_tokens,
            "available_tokens": available,
            "tokens_used": self.tokens_used,
            "tokens_remaining": available - self.tokens_used,
            "sections_included": included_names,
            "sections_excluded": excluded_names,
            "sections_truncated": [s.name for s in sorted_sections if s.truncated],
            "utilization_pct": round(100 * self.tokens_used / available, 1),
        }

        logger.debug(
            f"[PROMPT BUDGET] Built prompt: {self.tokens_used}/{available} tokens "
            f"({report['utilization_pct']}%), "
            f"{len(included_names)} included, {len(excluded_names)} excluded"
        )

        return included_parts, report

    def get_remaining_budget(self) -> int:
        """Get remaining token budget after current sections."""
        available = self.budget.total_budget - self.budget.reserve_tokens
        return available - self.tokens_used
