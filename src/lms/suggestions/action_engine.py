# src/lms/suggestions/action_engine.py
"""
Context-Aware Action Suggestion Engine for Mantle (AIRPG)

Generates mode-appropriate action suggestions for two distinct audiences:
1. QUICK START (narrative-first, mechanics invisible)
2. TTRPG (mechanics-visible, tactical clarity)

Integrates with:
- Arc Engine (story phases and tension)
- Character abilities (class-specific actions)
- Scene context (entities, objects, NPCs)
- Active story hooks
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PlayerMode(str, Enum):
    """Player experience mode - determines action presentation style."""
    QUICK_START = "quick_start"  # Narrative-first, CYOA style
    TTRPG = "ttrpg"  # Mechanics-visible, tactical


class ActionCategory(str, Enum):
    """Categories of actions for balanced suggestion diversity."""
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"
    ABILITY = "ability"  # Class-specific
    ENVIRONMENTAL = "environmental"
    RETREAT = "retreat"


@dataclass
class ActionSuggestion:
    """A single action suggestion with both presentation modes."""
    quick_start_text: str  # Narrative presentation
    ttrpg_text: str  # Mechanical presentation
    category: ActionCategory
    priority: float  # 0.0-1.0, higher = more relevant
    requires_class: Optional[str] = None  # Class restriction if any
    skill_check: Optional[str] = None  # Associated skill/ability


class ActionSuggestionEngine:
    """
    Generates contextually relevant action suggestions.

    Considers:
    - Player mode (quick_start vs ttrpg)
    - Scene content (narrative analysis)
    - Character class/abilities
    - Arc Engine phase (story beat)
    - Nearby entities (NPCs, objects, locations)
    - Active story hooks
    """

    # Keywords for scene analysis
    COMBAT_KEYWORDS = [
        "attack", "fight", "battle", "sword", "weapon", "guard", "enemy",
        "threat", "danger", "hostile", "approach", "charge", "aggressive",
        "defend", "block", "parry", "strike", "blood", "wound", "armor"
    ]

    SOCIAL_KEYWORDS = [
        "person", "people", "crowd", "stranger", "merchant", "guard",
        "noble", "peasant", "innkeeper", "traveler", "conversation",
        "speak", "talk", "ask", "tell", "negotiate", "persuade",
        "bribe", "threaten", "charm", "flirt", "greeting"
    ]

    EXPLORATION_KEYWORDS = [
        "door", "passage", "corridor", "room", "chamber", "cave",
        "forest", "path", "road", "mountain", "river", "building",
        "ruins", "dungeon", "tower", "entrance", "exit", "stairs",
        "dark", "hidden", "secret", "mysterious", "ancient"
    ]

    OBJECT_KEYWORDS = [
        "chest", "box", "container", "book", "scroll", "letter",
        "key", "potion", "gold", "treasure", "artifact", "item",
        "weapon", "armor", "tool", "bag", "sack", "crate",
        "lever", "switch", "button", "mechanism", "lock"
    ]

    MAGIC_KEYWORDS = [
        "magic", "spell", "enchant", "glow", "shimmer", "arcane",
        "rune", "symbol", "ward", "barrier", "aura", "energy",
        "curse", "blessing", "divine", "unholy", "supernatural"
    ]

    STEALTH_KEYWORDS = [
        "shadow", "dark", "quiet", "sneak", "hide", "observe",
        "watch", "listen", "unnoticed", "unseen", "patrol", "guard"
    ]

    # Class-specific action templates
    CLASS_ACTIONS = {
        "fighter": [
            ActionSuggestion(
                quick_start_text="Use your combat training to assess the threat",
                ttrpg_text="Second Wind (bonus action, regain HP)",
                category=ActionCategory.ABILITY,
                priority=0.8,
                requires_class="fighter",
            ),
            ActionSuggestion(
                quick_start_text="Take a defensive stance",
                ttrpg_text="Defense fighting style - focus on AC",
                category=ActionCategory.COMBAT,
                priority=0.7,
                requires_class="fighter",
            ),
            ActionSuggestion(
                quick_start_text="Charge into the fray",
                ttrpg_text="Action Surge for extra attack if needed",
                category=ActionCategory.COMBAT,
                priority=0.85,
                requires_class="fighter",
            ),
        ],
        "rogue": [
            ActionSuggestion(
                quick_start_text="Slip into the shadows",
                ttrpg_text="Hide (Cunning Action - bonus action Stealth)",
                category=ActionCategory.ABILITY,
                priority=0.9,
                requires_class="rogue",
                skill_check="stealth",
            ),
            ActionSuggestion(
                quick_start_text="Look for a vulnerable opening",
                ttrpg_text="Position for Sneak Attack (need advantage or ally)",
                category=ActionCategory.COMBAT,
                priority=0.85,
                requires_class="rogue",
            ),
            ActionSuggestion(
                quick_start_text="Check for traps or hidden dangers",
                ttrpg_text="Investigation check for traps (expertise applies)",
                category=ActionCategory.EXPLORATION,
                priority=0.75,
                requires_class="rogue",
                skill_check="investigation",
            ),
            ActionSuggestion(
                quick_start_text="Pick the lock",
                ttrpg_text="Thieves' Tools check (DEX + proficiency)",
                category=ActionCategory.ABILITY,
                priority=0.8,
                requires_class="rogue",
            ),
        ],
        "cleric": [
            ActionSuggestion(
                quick_start_text="Call upon your deity for guidance",
                ttrpg_text="Cast Guidance (cantrip, +1d4 to ability check)",
                category=ActionCategory.ABILITY,
                priority=0.7,
                requires_class="cleric",
            ),
            ActionSuggestion(
                quick_start_text="Heal your wounds with divine power",
                ttrpg_text="Cast Cure Wounds (1st level, 1d8+WIS HP)",
                category=ActionCategory.ABILITY,
                priority=0.85,
                requires_class="cleric",
            ),
            ActionSuggestion(
                quick_start_text="Invoke sacred flame against evil",
                ttrpg_text="Sacred Flame (cantrip, DEX save, 1d8 radiant)",
                category=ActionCategory.COMBAT,
                priority=0.8,
                requires_class="cleric",
            ),
            ActionSuggestion(
                quick_start_text="Bless your allies for the coming battle",
                ttrpg_text="Cast Bless (1st level, 3 creatures +1d4 attacks/saves)",
                category=ActionCategory.ABILITY,
                priority=0.75,
                requires_class="cleric",
            ),
        ],
        "wizard": [
            ActionSuggestion(
                quick_start_text="Unleash a bolt of arcane fire",
                ttrpg_text="Fire Bolt (cantrip, ranged spell attack, 1d10 fire)",
                category=ActionCategory.COMBAT,
                priority=0.8,
                requires_class="wizard",
            ),
            ActionSuggestion(
                quick_start_text="Create a magical barrier",
                ttrpg_text="Cast Shield (reaction, +5 AC until next turn)",
                category=ActionCategory.ABILITY,
                priority=0.85,
                requires_class="wizard",
            ),
            ActionSuggestion(
                quick_start_text="Study the magical energies",
                ttrpg_text="Cast Detect Magic (ritual, 10 min, sense magic)",
                category=ActionCategory.ABILITY,
                priority=0.7,
                requires_class="wizard",
                skill_check="arcana",
            ),
            ActionSuggestion(
                quick_start_text="Blast the area with magical missiles",
                ttrpg_text="Magic Missile (1st level, 3 darts, 1d4+1 each, auto-hit)",
                category=ActionCategory.COMBAT,
                priority=0.9,
                requires_class="wizard",
            ),
        ],
    }

    # Phase-appropriate action templates (Arc Engine integration)
    PHASE_ACTIONS = {
        "ORDINARY_WORLD": [
            ActionSuggestion(
                quick_start_text="Go about your daily routine",
                ttrpg_text="Downtime activity (describe what you do)",
                category=ActionCategory.SOCIAL,
                priority=0.6,
            ),
            ActionSuggestion(
                quick_start_text="Speak with someone you know",
                ttrpg_text="Social interaction (no check needed for allies)",
                category=ActionCategory.SOCIAL,
                priority=0.7,
            ),
        ],
        "CALL_TO_ADVENTURE": [
            ActionSuggestion(
                quick_start_text="Investigate what's happening",
                ttrpg_text="Investigation or Perception check",
                category=ActionCategory.EXPLORATION,
                priority=0.85,
                skill_check="investigation",
            ),
            ActionSuggestion(
                quick_start_text="Ask questions about the situation",
                ttrpg_text="Insight check to read the messenger",
                category=ActionCategory.SOCIAL,
                priority=0.8,
                skill_check="insight",
            ),
        ],
        "TESTS_ALLIES_ENEMIES": [
            ActionSuggestion(
                quick_start_text="Prove yourself in combat",
                ttrpg_text="Engage enemy (roll initiative if not in combat)",
                category=ActionCategory.COMBAT,
                priority=0.8,
            ),
            ActionSuggestion(
                quick_start_text="Try to win them over",
                ttrpg_text="Persuasion or Intimidation check",
                category=ActionCategory.SOCIAL,
                priority=0.75,
                skill_check="persuasion",
            ),
        ],
        "ORDEAL": [
            ActionSuggestion(
                quick_start_text="Face the challenge head-on",
                ttrpg_text="Direct confrontation (combat or contest)",
                category=ActionCategory.COMBAT,
                priority=0.9,
            ),
            ActionSuggestion(
                quick_start_text="Look for a weakness",
                ttrpg_text="Perception or Investigation for vulnerabilities",
                category=ActionCategory.EXPLORATION,
                priority=0.8,
                skill_check="perception",
            ),
        ],
        "CLIMAX": [
            ActionSuggestion(
                quick_start_text="Make your final stand",
                ttrpg_text="Full attack action, use all resources",
                category=ActionCategory.COMBAT,
                priority=0.95,
            ),
            ActionSuggestion(
                quick_start_text="Attempt a desperate gambit",
                ttrpg_text="High-risk action with DM's ruling",
                category=ActionCategory.ABILITY,
                priority=0.85,
            ),
        ],
    }

    # Generic contextual actions
    GENERIC_ACTIONS = {
        "combat_detected": [
            ActionSuggestion(
                quick_start_text="Attack the enemy",
                ttrpg_text="Melee/Ranged Attack (STR/DEX + proficiency)",
                category=ActionCategory.COMBAT,
                priority=0.8,
            ),
            ActionSuggestion(
                quick_start_text="Defend yourself",
                ttrpg_text="Dodge action (disadvantage on attacks against you)",
                category=ActionCategory.COMBAT,
                priority=0.6,
            ),
            ActionSuggestion(
                quick_start_text="Fall back to safety",
                ttrpg_text="Disengage and move (no opportunity attacks)",
                category=ActionCategory.RETREAT,
                priority=0.5,
            ),
        ],
        "social_detected": [
            ActionSuggestion(
                quick_start_text="Start a conversation",
                ttrpg_text="Social interaction (Persuasion/Deception/Intimidation)",
                category=ActionCategory.SOCIAL,
                priority=0.75,
            ),
            ActionSuggestion(
                quick_start_text="Read their intentions",
                ttrpg_text="Insight check vs their Deception",
                category=ActionCategory.SOCIAL,
                priority=0.7,
                skill_check="insight",
            ),
            ActionSuggestion(
                quick_start_text="Offer them something",
                ttrpg_text="Persuasion check (advantage with appropriate offer)",
                category=ActionCategory.SOCIAL,
                priority=0.65,
                skill_check="persuasion",
            ),
        ],
        "exploration_detected": [
            ActionSuggestion(
                quick_start_text="Look around carefully",
                ttrpg_text="Perception check (WIS + proficiency)",
                category=ActionCategory.EXPLORATION,
                priority=0.7,
                skill_check="perception",
            ),
            ActionSuggestion(
                quick_start_text="Search the area",
                ttrpg_text="Investigation check (INT + proficiency)",
                category=ActionCategory.EXPLORATION,
                priority=0.7,
                skill_check="investigation",
            ),
            ActionSuggestion(
                quick_start_text="Move forward cautiously",
                ttrpg_text="Stealth check while moving (half speed)",
                category=ActionCategory.EXPLORATION,
                priority=0.6,
                skill_check="stealth",
            ),
        ],
        "object_detected": [
            ActionSuggestion(
                quick_start_text="Examine it closely",
                ttrpg_text="Investigation check for details/traps",
                category=ActionCategory.EXPLORATION,
                priority=0.8,
                skill_check="investigation",
            ),
            ActionSuggestion(
                quick_start_text="Try to open/use it",
                ttrpg_text="Interact with object (may require check)",
                category=ActionCategory.ENVIRONMENTAL,
                priority=0.75,
            ),
            ActionSuggestion(
                quick_start_text="Take it with you",
                ttrpg_text="Pick up item (free object interaction)",
                category=ActionCategory.ENVIRONMENTAL,
                priority=0.6,
            ),
        ],
        "magic_detected": [
            ActionSuggestion(
                quick_start_text="Sense the magical energy",
                ttrpg_text="Arcana check to identify magic type",
                category=ActionCategory.ABILITY,
                priority=0.75,
                skill_check="arcana",
            ),
            ActionSuggestion(
                quick_start_text="Approach carefully",
                ttrpg_text="Cautious movement (check for magical traps)",
                category=ActionCategory.EXPLORATION,
                priority=0.7,
            ),
        ],
        "stealth_opportunity": [
            ActionSuggestion(
                quick_start_text="Stay hidden",
                ttrpg_text="Stealth check (DEX + proficiency)",
                category=ActionCategory.EXPLORATION,
                priority=0.8,
                skill_check="stealth",
            ),
            ActionSuggestion(
                quick_start_text="Watch and wait",
                ttrpg_text="Perception check while hidden",
                category=ActionCategory.EXPLORATION,
                priority=0.7,
                skill_check="perception",
            ),
        ],
        "default": [
            ActionSuggestion(
                quick_start_text="Look around",
                ttrpg_text="Perception check (passive or active)",
                category=ActionCategory.EXPLORATION,
                priority=0.5,
                skill_check="perception",
            ),
            ActionSuggestion(
                quick_start_text="Wait and observe",
                ttrpg_text="Ready action (choose trigger and response)",
                category=ActionCategory.EXPLORATION,
                priority=0.4,
            ),
            ActionSuggestion(
                quick_start_text="Consider your options",
                ttrpg_text="Take a moment (no action, think about strategy)",
                category=ActionCategory.EXPLORATION,
                priority=0.3,
            ),
        ],
    }

    def __init__(self):
        """Initialize the action suggestion engine."""
        pass

    def generate_suggestions(
        self,
        mode: PlayerMode,
        narrative: str,
        character_class: Optional[str] = None,
        arc_phase: Optional[str] = None,
        nearby_entities: Optional[List[Dict[str, Any]]] = None,
        story_hooks: Optional[List[str]] = None,
        tension: float = 0.5,
        max_suggestions: int = 5,
    ) -> List[str]:
        """
        Generate contextually relevant action suggestions.

        Args:
            mode: Player mode (quick_start or ttrpg)
            narrative: Current scene description
            character_class: Player's character class (fighter, rogue, etc.)
            arc_phase: Current Arc Engine phase (ORDINARY_WORLD, ORDEAL, etc.)
            nearby_entities: List of nearby NPCs/objects from Neo4j
            story_hooks: Active unresolved story threads
            tension: Current tension level (0.0-1.0)
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of action suggestion strings formatted for the mode
        """
        candidates: List[Tuple[float, ActionSuggestion]] = []

        # 1. Analyze scene context
        scene_context = self._analyze_scene(narrative)

        # 2. Add context-based actions
        for context_type in scene_context:
            actions = self.GENERIC_ACTIONS.get(context_type, [])
            for action in actions:
                # Boost priority based on tension for combat
                priority = action.priority
                if context_type == "combat_detected" and tension > 0.7:
                    priority *= 1.2
                candidates.append((priority, action))

        # 3. Add class-specific actions if character class provided
        if character_class:
            class_key = character_class.lower()
            class_actions = self.CLASS_ACTIONS.get(class_key, [])
            for action in class_actions:
                # Class actions get priority boost
                priority = action.priority * 1.1
                # Combat class actions boosted in high tension
                if action.category == ActionCategory.COMBAT and tension > 0.6:
                    priority *= 1.15
                candidates.append((priority, action))

        # 4. Add phase-appropriate actions from Arc Engine
        if arc_phase:
            phase_key = arc_phase.upper().replace(" ", "_")
            phase_actions = self.PHASE_ACTIONS.get(phase_key, [])
            for action in phase_actions:
                candidates.append((action.priority, action))

        # 5. Add entity-based actions
        if nearby_entities:
            entity_actions = self._generate_entity_actions(nearby_entities, mode)
            for action in entity_actions:
                candidates.append((action.priority, action))

        # 6. Add story hook actions
        if story_hooks:
            hook_actions = self._generate_hook_actions(story_hooks, mode)
            for action in hook_actions:
                candidates.append((action.priority, action))

        # 7. Ensure minimum suggestions with defaults
        if len(candidates) < max_suggestions:
            for action in self.GENERIC_ACTIONS["default"]:
                candidates.append((action.priority * 0.5, action))

        # 8. Sort by priority and ensure category diversity
        candidates.sort(key=lambda x: x[0], reverse=True)

        # 9. Select with diversity (avoid all same category)
        selected = self._select_diverse(candidates, max_suggestions)

        # 10. Format for mode
        return [self._format_action(action, mode) for action in selected]

    def _analyze_scene(self, narrative: str) -> List[str]:
        """Analyze narrative text to determine scene context types."""
        contexts = []
        narrative_lower = narrative.lower()

        # Check for combat indicators
        combat_score = sum(1 for kw in self.COMBAT_KEYWORDS if kw in narrative_lower)
        if combat_score >= 2:
            contexts.append("combat_detected")

        # Check for social indicators
        social_score = sum(1 for kw in self.SOCIAL_KEYWORDS if kw in narrative_lower)
        if social_score >= 2:
            contexts.append("social_detected")

        # Check for exploration indicators
        exploration_score = sum(1 for kw in self.EXPLORATION_KEYWORDS if kw in narrative_lower)
        if exploration_score >= 2:
            contexts.append("exploration_detected")

        # Check for objects
        object_score = sum(1 for kw in self.OBJECT_KEYWORDS if kw in narrative_lower)
        if object_score >= 1:
            contexts.append("object_detected")

        # Check for magic
        magic_score = sum(1 for kw in self.MAGIC_KEYWORDS if kw in narrative_lower)
        if magic_score >= 1:
            contexts.append("magic_detected")

        # Check for stealth opportunities
        stealth_score = sum(1 for kw in self.STEALTH_KEYWORDS if kw in narrative_lower)
        if stealth_score >= 2:
            contexts.append("stealth_opportunity")

        # Default if nothing detected
        if not contexts:
            contexts.append("default")

        return contexts

    def _generate_entity_actions(
        self,
        entities: List[Dict[str, Any]],
        mode: PlayerMode,
    ) -> List[ActionSuggestion]:
        """Generate actions based on nearby entities."""
        actions = []

        for entity in entities[:5]:  # Limit to top 5 entities
            entity_type = entity.get("type", "").lower()
            entity_name = entity.get("name", "someone")

            if entity_type in ["character", "npc", "person"]:
                actions.append(ActionSuggestion(
                    quick_start_text=f"Approach {entity_name}",
                    ttrpg_text=f"Interact with {entity_name} (social check if needed)",
                    category=ActionCategory.SOCIAL,
                    priority=0.7,
                ))
            elif entity_type in ["item", "object", "treasure"]:
                actions.append(ActionSuggestion(
                    quick_start_text=f"Examine the {entity_name}",
                    ttrpg_text=f"Investigation check on {entity_name}",
                    category=ActionCategory.EXPLORATION,
                    priority=0.65,
                    skill_check="investigation",
                ))
            elif entity_type in ["location", "place", "building"]:
                actions.append(ActionSuggestion(
                    quick_start_text=f"Head toward {entity_name}",
                    ttrpg_text=f"Move to {entity_name} (may trigger encounters)",
                    category=ActionCategory.EXPLORATION,
                    priority=0.6,
                ))
            elif entity_type in ["creature", "monster", "enemy"]:
                actions.append(ActionSuggestion(
                    quick_start_text=f"Prepare for {entity_name}",
                    ttrpg_text=f"Ready action against {entity_name}",
                    category=ActionCategory.COMBAT,
                    priority=0.8,
                ))

        return actions

    def _generate_hook_actions(
        self,
        hooks: List[str],
        mode: PlayerMode,
    ) -> List[ActionSuggestion]:
        """Generate actions based on active story hooks."""
        actions = []

        for hook in hooks[:3]:  # Limit to top 3 hooks
            hook_lower = hook.lower()

            # Determine hook type and create appropriate action
            if any(word in hook_lower for word in ["find", "search", "locate", "where"]):
                actions.append(ActionSuggestion(
                    quick_start_text=f"Investigate: {hook[:50]}...",
                    ttrpg_text=f"Investigation/Perception for lead on: {hook[:40]}",
                    category=ActionCategory.EXPLORATION,
                    priority=0.7,
                    skill_check="investigation",
                ))
            elif any(word in hook_lower for word in ["speak", "talk", "ask", "meet"]):
                actions.append(ActionSuggestion(
                    quick_start_text=f"Follow up on: {hook[:50]}...",
                    ttrpg_text=f"Social check to pursue: {hook[:40]}",
                    category=ActionCategory.SOCIAL,
                    priority=0.65,
                ))
            else:
                actions.append(ActionSuggestion(
                    quick_start_text=f"Pursue: {hook[:50]}...",
                    ttrpg_text=f"Action toward goal: {hook[:40]}",
                    category=ActionCategory.EXPLORATION,
                    priority=0.6,
                ))

        return actions

    def _select_diverse(
        self,
        candidates: List[Tuple[float, ActionSuggestion]],
        max_count: int,
    ) -> List[ActionSuggestion]:
        """Select diverse actions avoiding too many of same category."""
        selected = []
        category_counts: Dict[ActionCategory, int] = {}
        max_per_category = 2

        for priority, action in candidates:
            if len(selected) >= max_count:
                break

            # Check category limit
            cat_count = category_counts.get(action.category, 0)
            if cat_count >= max_per_category:
                continue

            # Check for duplicate text
            action_text = action.quick_start_text.lower()
            if any(action_text == s.quick_start_text.lower() for s in selected):
                continue

            selected.append(action)
            category_counts[action.category] = cat_count + 1

        return selected

    def _format_action(self, action: ActionSuggestion, mode: PlayerMode) -> str:
        """Format action text for the specified mode."""
        if mode == PlayerMode.QUICK_START:
            return action.quick_start_text
        else:  # TTRPG mode
            return action.ttrpg_text


# Singleton instance for easy access
_engine_instance: Optional[ActionSuggestionEngine] = None


def get_action_engine() -> ActionSuggestionEngine:
    """Get or create the action suggestion engine singleton."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ActionSuggestionEngine()
    return _engine_instance


def generate_action_suggestions(
    narrative: str,
    mode: str = "quick_start",
    character_class: Optional[str] = None,
    arc_phase: Optional[str] = None,
    nearby_entities: Optional[List[Dict[str, Any]]] = None,
    story_hooks: Optional[List[str]] = None,
    tension: float = 0.5,
    max_suggestions: int = 5,
) -> List[str]:
    """
    Convenience function to generate action suggestions.

    This is the main entry point for generating suggestions.

    Args:
        narrative: Current scene description
        mode: "quick_start" or "ttrpg"
        character_class: Player's class (fighter, rogue, cleric, wizard)
        arc_phase: Current Arc Engine phase
        nearby_entities: List of nearby entities from Neo4j
        story_hooks: Active story threads
        tension: Tension level 0.0-1.0
        max_suggestions: Max number of suggestions

    Returns:
        List of formatted action suggestion strings
    """
    engine = get_action_engine()
    player_mode = PlayerMode(mode) if mode in PlayerMode.__members__.values() else PlayerMode.QUICK_START

    return engine.generate_suggestions(
        mode=player_mode,
        narrative=narrative,
        character_class=character_class,
        arc_phase=arc_phase,
        nearby_entities=nearby_entities,
        story_hooks=story_hooks,
        tension=tension,
        max_suggestions=max_suggestions,
    )
