"""Integration hooks for the DM Agent."""

import re
import logging
from typing import Dict, Any, Optional, List

from ..models.ability_scores import AbilityName
from ..models.character_sheet import CharacterSheet
from ..engine.checks import CheckEngine, CheckResult, SKILL_TO_ABILITY, ALL_SKILLS
from ..engine.combat_resolver import CombatResolver, AttackResult, DamageResult, WEAPON_DAMAGE, DamageType
from ..creation.modes import RulesVisibility
from ..presentation.visibility import VisibilityFilter
from ..presentation.narration import NarrationHelper

logger = logging.getLogger(__name__)


# Keywords for action detection
ATTACK_KEYWORDS = [
    "attack", "strike", "hit", "swing", "slash", "stab", "shoot",
    "punch", "kick", "smash", "bash", "fire at", "cast at"
]

SKILL_KEYWORDS = {
    "sneak": "stealth",
    "hide": "stealth",
    "move quietly": "stealth",
    "move silently": "stealth",
    "climb": "athletics",
    "jump": "athletics",
    "swim": "athletics",
    "lift": "athletics",
    "push": "athletics",
    "convince": "persuasion",
    "persuade": "persuasion",
    "talk to": "persuasion",
    "negotiate": "persuasion",
    "lie": "deception",
    "deceive": "deception",
    "bluff": "deception",
    "threaten": "intimidation",
    "intimidate": "intimidation",
    "scare": "intimidation",
    "look for": "perception",
    "search": "investigation",
    "examine": "investigation",
    "inspect": "investigation",
    "listen": "perception",
    "watch": "perception",
    "notice": "perception",
    "sense motive": "insight",
    "read": "insight",
    "tumble": "acrobatics",
    "balance": "acrobatics",
    "flip": "acrobatics",
    "dodge": "acrobatics",
    "heal": "medicine",
    "treat": "medicine",
    "pick lock": "sleight_of_hand",
    "pickpocket": "sleight_of_hand",
    "perform": "performance",
    "play": "performance",
    "sing": "performance",
    "recall": "history",
    "remember": "history",
    "identify magic": "arcana",
    "understand magic": "arcana",
    "track": "survival",
    "forage": "survival",
    "calm animal": "animal_handling",
    "handle animal": "animal_handling",
}


class DnD5eHooks:
    """
    Hooks for integrating D&D 5e rules into the DM Agent.

    This class processes player actions, determines if mechanical
    resolution is needed, and provides results for narrative integration.
    """

    def __init__(
        self,
        visibility: RulesVisibility = RulesVisibility.GUIDED,
    ):
        """
        Initialize the hooks.

        Args:
            visibility: Rules visibility level for this session
        """
        self.visibility = visibility
        self.active_characters: Dict[str, CharacterSheet] = {}
        self.combat_active = False
        self.current_encounter: Optional[Dict[str, Any]] = None

    def register_character(self, character: CharacterSheet) -> None:
        """Register a character for rule resolution."""
        self.active_characters[character.character_id] = character
        logger.info(f"Registered character {character.name} ({character.character_id})")

    def get_character(self, character_id: str) -> Optional[CharacterSheet]:
        """Get a registered character by ID."""
        return self.active_characters.get(character_id)

    def set_visibility(self, visibility: RulesVisibility) -> None:
        """Update the visibility mode."""
        self.visibility = visibility

    async def process_action(
        self,
        player_input: str,
        character_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a player action and determine mechanical resolution.

        Args:
            player_input: The player's input text
            character_id: ID of the acting character
            context: Optional context (target AC, DC, etc.)

        Returns:
            Dict with:
                - action_type: "attack", "skill_check", "save", or "narrative"
                - mechanical_result: The raw result (if applicable)
                - filtered_result: Visibility-filtered result
                - narrative_context: Hints for DM narrative
        """
        character = self.active_characters.get(character_id)
        if not character:
            return {
                "action_type": "narrative",
                "error": "Character not found",
            }

        # Classify the action
        action_type = self._classify_action(player_input)

        if action_type == "attack":
            return await self._handle_attack(character, player_input, context)
        elif action_type == "skill_check":
            return await self._handle_skill_check(character, player_input, context)
        elif action_type == "save":
            return await self._handle_save(character, player_input, context)
        else:
            return {"action_type": "narrative", "rules_context": None}

    def _classify_action(self, input_text: str) -> str:
        """Classify the type of action from player input."""
        input_lower = input_text.lower()

        # Check for attack
        for keyword in ATTACK_KEYWORDS:
            if keyword in input_lower:
                return "attack"

        # Check for skill use
        for keyword, skill in SKILL_KEYWORDS.items():
            if keyword in input_lower:
                return "skill_check"

        # Check for explicit skill mention
        for skill in ALL_SKILLS:
            if skill.replace("_", " ") in input_lower:
                return "skill_check"

        return "narrative"

    def _extract_skill(self, input_text: str) -> str:
        """Extract the skill being used from input."""
        input_lower = input_text.lower()

        # Check keyword mappings first
        for keyword, skill in SKILL_KEYWORDS.items():
            if keyword in input_lower:
                return skill

        # Check for explicit skill names
        for skill in ALL_SKILLS:
            if skill.replace("_", " ") in input_lower:
                return skill

        # Default based on common actions
        return "perception"  # Safe default

    async def _handle_attack(
        self,
        character: CharacterSheet,
        input_text: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle an attack action."""
        # Get target AC from context or use default
        target_ac = context.get("target_ac", 12) if context else 12
        weapon_name = context.get("weapon") if context else None

        # Determine weapon type
        is_ranged = any(w in input_text.lower() for w in ["shoot", "bow", "crossbow", "throw"])
        weapon_type = "ranged" if is_ranged else "melee"

        # Check for finesse weapons
        is_finesse = any(w in input_text.lower() for w in ["rapier", "dagger", "shortsword"])

        # Determine advantage/disadvantage from context
        advantage = context.get("advantage", False) if context else False
        disadvantage = context.get("disadvantage", False) if context else False

        # Resolve the attack
        attack_result = CombatResolver.resolve_attack(
            character,
            target_ac,
            weapon_type=weapon_type,
            is_finesse=is_finesse,
            advantage=advantage,
            disadvantage=disadvantage,
        )

        # Roll damage if hit
        damage_result = None
        if attack_result.is_hit:
            # Determine weapon damage
            weapon_key = weapon_name or ("shortbow" if is_ranged else "longsword")
            damage_dice, damage_type = WEAPON_DAMAGE.get(
                weapon_key,
                ("1d6", DamageType.SLASHING)
            )

            # Get ability modifier for damage
            if is_ranged:
                ability_mod = character.ability_scores.get_modifier(AbilityName.DEX)
            elif is_finesse:
                str_mod = character.ability_scores.get_modifier(AbilityName.STR)
                dex_mod = character.ability_scores.get_modifier(AbilityName.DEX)
                ability_mod = max(str_mod, dex_mod)
            else:
                ability_mod = character.ability_scores.get_modifier(AbilityName.STR)

            damage_result = CombatResolver.roll_damage(
                damage_dice,
                damage_type,
                ability_modifier=ability_mod,
                is_critical=attack_result.is_critical,
            )

        # Filter for visibility
        filtered_attack = VisibilityFilter.filter_attack_result(
            attack_result, self.visibility
        )
        filtered_damage = None
        if damage_result:
            filtered_damage = VisibilityFilter.filter_damage_result(
                damage_result, self.visibility
            )

        # Generate narrative context
        narrative = NarrationHelper.narrate_attack(attack_result)
        if damage_result:
            narrative += f", dealing damage"

        return {
            "action_type": "attack",
            "mechanical_result": {
                "attack": attack_result.model_dump(),
                "damage": damage_result.model_dump() if damage_result else None,
            },
            "filtered_result": {
                "attack": filtered_attack,
                "damage": filtered_damage,
            },
            "narrative_context": narrative,
            "mechanical_text": VisibilityFilter.format_for_narrative(
                attack_result=attack_result,
                damage_result=damage_result,
                visibility=self.visibility,
            ),
        }

    async def _handle_skill_check(
        self,
        character: CharacterSheet,
        input_text: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle a skill check action."""
        skill = self._extract_skill(input_text)

        # Get DC from context or estimate
        dc = context.get("dc", 15) if context else self._estimate_dc(input_text)

        # Check for advantage/disadvantage
        advantage = context.get("advantage", False) if context else False
        disadvantage = context.get("disadvantage", False) if context else False

        # Perform the check
        result = CheckEngine.skill_check(
            character,
            skill,
            dc,
            advantage=advantage,
            disadvantage=disadvantage,
        )

        # Filter for visibility
        filtered = VisibilityFilter.filter_check_result(result, self.visibility)

        # Generate narrative context
        narrative = NarrationHelper.narrate_check(result)

        return {
            "action_type": "skill_check",
            "skill": skill,
            "mechanical_result": result.model_dump(),
            "filtered_result": filtered,
            "narrative_context": narrative,
            "mechanical_text": VisibilityFilter.format_for_narrative(
                check_result=result,
                visibility=self.visibility,
            ),
        }

    async def _handle_save(
        self,
        character: CharacterSheet,
        input_text: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Handle a saving throw."""
        # Determine ability from context
        ability_str = context.get("ability", "dexterity") if context else "dexterity"
        ability = AbilityName(ability_str)

        dc = context.get("dc", 15) if context else 15
        advantage = context.get("advantage", False) if context else False
        disadvantage = context.get("disadvantage", False) if context else False

        result = CheckEngine.saving_throw(
            character,
            ability,
            dc,
            advantage=advantage,
            disadvantage=disadvantage,
        )

        filtered = VisibilityFilter.filter_check_result(result, self.visibility)
        narrative = "resists" if result.success else "succumbs"

        return {
            "action_type": "save",
            "ability": ability.value,
            "mechanical_result": result.model_dump(),
            "filtered_result": filtered,
            "narrative_context": narrative,
            "mechanical_text": VisibilityFilter.format_for_narrative(
                check_result=result,
                visibility=self.visibility,
            ),
        }

    def _estimate_dc(self, input_text: str) -> int:
        """Estimate DC based on action description."""
        input_lower = input_text.lower()

        # Look for difficulty indicators
        if any(w in input_lower for w in ["impossible", "legendary", "epic"]):
            return 25
        elif any(w in input_lower for w in ["very hard", "extremely difficult"]):
            return 20
        elif any(w in input_lower for w in ["hard", "difficult", "challenging"]):
            return 17
        elif any(w in input_lower for w in ["easy", "simple", "basic"]):
            return 10
        elif any(w in input_lower for w in ["trivial", "automatic"]):
            return 5

        return 15  # Default medium difficulty

    def get_dm_prompt_context(self, character_id: str) -> str:
        """
        Get context to inject into DM prompts about character capabilities.

        This helps the DM agent understand what the character can do.
        """
        character = self.active_characters.get(character_id)
        if not character:
            return ""

        abilities = character.ability_scores.to_display_dict()
        skills = ", ".join(character.skill_proficiencies) or "none"

        return f"""
Character Mechanical Context:
- Name: {character.name}
- Race: {character.race.value}, Class: {character.character_class.value} Level {character.level}
- HP: {character.current_hit_points}/{character.max_hit_points}
- AC: {character.armor_class}
- Skills (proficient): {skills}
- Spells: {', '.join(character.spells_known) if character.spells_known else 'none'}
"""
