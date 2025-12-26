"""Classic (PHB-style) character creation flow."""

import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ..models.ability_scores import AbilityScores, STANDARD_ARRAY
from ..models.races import RaceName, RACES, get_race
from ..models.classes import ClassName, CLASSES, get_class, get_starting_hp
from ..models.character_sheet import CharacterSheet


class ClassicCreationState(BaseModel):
    """Tracks state through classic creation flow."""
    step: int = 0
    name: Optional[str] = None
    race: Optional[RaceName] = None
    character_class: Optional[ClassName] = None
    ability_scores: Optional[AbilityScores] = None
    skill_proficiencies: List[str] = []
    completed: bool = False


class ClassicCreationFlow:
    """
    Standard PHB-style character creation.

    Steps:
    1. Choose name
    2. Choose race
    3. Choose class
    4. Assign ability scores (standard array)
    5. Select skill proficiencies
    6. Review and finalize
    """

    STEPS = [
        "name",
        "race",
        "class",
        "abilities",
        "skills",
        "review",
    ]

    def __init__(self):
        self.state = ClassicCreationState()

    def get_current_step(self) -> str:
        """Get the name of the current step."""
        return self.STEPS[self.state.step]

    def get_step_options(self) -> Dict[str, Any]:
        """Get options and instructions for current step."""
        step = self.get_current_step()

        if step == "name":
            return {
                "step": "name",
                "prompt": "What is your character's name?",
                "input_type": "text",
            }

        elif step == "race":
            races = []
            for race_name in RaceName:
                race_data = RACES[race_name]
                races.append({
                    "id": race_name.value,
                    "name": race_data.display_name,
                    "description": race_data.description,
                    "ability_bonuses": race_data.ability_bonuses,
                    "traits": race_data.traits,
                    "speed": race_data.speed,
                })
            return {
                "step": "race",
                "prompt": "Choose your character's race:",
                "options": races,
            }

        elif step == "class":
            classes = []
            for class_name in ClassName:
                class_data = CLASSES[class_name]
                classes.append({
                    "id": class_name.value,
                    "name": class_data.display_name,
                    "description": class_data.description,
                    "hit_die": class_data.hit_die.value,
                    "primary_ability": class_data.primary_ability,
                    "features": class_data.features_by_level.get(1, []),
                })
            return {
                "step": "class",
                "prompt": "Choose your character's class:",
                "options": classes,
            }

        elif step == "abilities":
            return {
                "step": "abilities",
                "prompt": "Assign your ability scores using the standard array:",
                "standard_array": STANDARD_ARRAY,
                "abilities": ["strength", "dexterity", "constitution",
                              "intelligence", "wisdom", "charisma"],
                "race_bonuses": RACES[self.state.race].ability_bonuses if self.state.race else {},
            }

        elif step == "skills":
            class_data = CLASSES[self.state.character_class]
            return {
                "step": "skills",
                "prompt": f"Choose {class_data.num_skill_choices} skills:",
                "available_skills": class_data.skill_choices,
                "num_choices": class_data.num_skill_choices,
            }

        elif step == "review":
            return {
                "step": "review",
                "prompt": "Review your character:",
                "character": self._build_preview(),
            }

        return {}

    def set_name(self, name: str) -> bool:
        """Set character name and advance."""
        if len(name.strip()) < 1:
            return False
        self.state.name = name.strip()
        self.state.step = 1
        return True

    def set_race(self, race: str) -> bool:
        """Set race and advance."""
        try:
            self.state.race = RaceName(race.lower())
            self.state.step = 2
            return True
        except ValueError:
            return False

    def set_class(self, character_class: str) -> bool:
        """Set class and advance."""
        try:
            self.state.character_class = ClassName(character_class.lower())
            self.state.step = 3
            return True
        except ValueError:
            return False

    def set_abilities(self, assignments: Dict[str, int]) -> bool:
        """
        Set ability score assignments.

        Args:
            assignments: Dict mapping ability name to score from standard array

        Returns:
            True if valid assignment
        """
        # Validate all scores are from standard array (used exactly once)
        used_scores = list(assignments.values())
        if sorted(used_scores) != sorted(STANDARD_ARRAY):
            return False

        # Create ability scores and apply racial bonuses
        base_scores = AbilityScores(**assignments)
        race_data = RACES[self.state.race]
        final_scores = base_scores.apply_bonuses(race_data.ability_bonuses)

        self.state.ability_scores = final_scores
        self.state.step = 4
        return True

    def set_skills(self, skills: List[str]) -> bool:
        """
        Set skill proficiencies.

        Args:
            skills: List of skill names

        Returns:
            True if valid selection
        """
        class_data = CLASSES[self.state.character_class]

        # Validate count
        if len(skills) != class_data.num_skill_choices:
            return False

        # Validate all skills are available for this class
        available = [s.lower() for s in class_data.skill_choices]
        for skill in skills:
            if skill.lower() not in available:
                return False

        self.state.skill_proficiencies = [s.lower() for s in skills]
        self.state.step = 5
        return True

    def finalize(self, player_id: str = "") -> CharacterSheet:
        """Create the final character sheet."""
        if self.state.step != 5:
            raise ValueError("Character creation not complete")

        race_data = RACES[self.state.race]
        class_data = CLASSES[self.state.character_class]

        # Calculate starting HP
        con_mod = self.state.ability_scores.get_modifier(
            __import__('src.lms.dnd5e.models.ability_scores', fromlist=['AbilityName']).AbilityName.CON
        )
        from ..models.ability_scores import AbilityName
        con_mod = self.state.ability_scores.get_modifier(AbilityName.CON)
        starting_hp = get_starting_hp(self.state.character_class, con_mod)

        # Calculate AC (10 + DEX mod, no armor yet)
        dex_mod = self.state.ability_scores.get_modifier(AbilityName.DEX)
        base_ac = 10 + dex_mod

        # Build equipment list from starter pack
        # (Simplified for Phase 1 - just use defaults)
        equipment = ["adventurer's pack"]
        if self.state.character_class == ClassName.FIGHTER:
            equipment = ["chain mail", "longsword", "shield", "light crossbow", "20 bolts"]
            base_ac = 16  # Chain mail
        elif self.state.character_class == ClassName.ROGUE:
            equipment = ["leather armor", "rapier", "shortbow", "20 arrows", "thieves' tools"]
            base_ac = 11 + dex_mod  # Leather
        elif self.state.character_class == ClassName.CLERIC:
            equipment = ["scale mail", "mace", "shield", "holy symbol"]
            base_ac = 14 + min(dex_mod, 2) + 2  # Scale mail + shield
        elif self.state.character_class == ClassName.WIZARD:
            equipment = ["quarterstaff", "arcane focus", "spellbook"]
            base_ac = 10 + dex_mod  # No armor

        # Build spell slots if spellcaster
        spell_slots = {}
        cantrips = []
        spells_known = []
        if class_data.spellcasting:
            spell_slots = {1: class_data.spell_slots_by_level.get(1, {}).get(1, 0)}
            # Default cantrips and spells (simplified)
            if self.state.character_class == ClassName.CLERIC:
                cantrips = ["sacred_flame", "light"]
                spells_known = ["cure_wounds", "bless"]
            elif self.state.character_class == ClassName.WIZARD:
                cantrips = ["fire_bolt", "light"]
                spells_known = ["magic_missile", "shield"]

        sheet = CharacterSheet(
            character_id=str(uuid.uuid4()),
            name=self.state.name,
            player_id=player_id,
            race=self.state.race,
            character_class=self.state.character_class,
            level=1,
            ability_scores=self.state.ability_scores,
            max_hit_points=starting_hp,
            current_hit_points=starting_hp,
            armor_class=base_ac,
            speed=race_data.speed,
            skill_proficiencies=self.state.skill_proficiencies,
            saving_throw_proficiencies=class_data.saving_throw_proficiencies,
            armor_proficiencies=class_data.armor_proficiencies,
            weapon_proficiencies=class_data.weapon_proficiencies,
            equipment=equipment,
            spell_slots_max=spell_slots,
            cantrips_known=cantrips,
            spells_known=spells_known,
            features=class_data.features_by_level.get(1, []),
        )

        self.state.completed = True
        return sheet

    def _build_preview(self) -> Dict[str, Any]:
        """Build a preview of the character for review step."""
        race_data = RACES[self.state.race]
        class_data = CLASSES[self.state.character_class]

        from ..models.ability_scores import AbilityName
        con_mod = self.state.ability_scores.get_modifier(AbilityName.CON)

        return {
            "name": self.state.name,
            "race": race_data.display_name,
            "class": class_data.display_name,
            "level": 1,
            "hit_points": get_starting_hp(self.state.character_class, con_mod),
            "abilities": self.state.ability_scores.to_display_dict(),
            "skills": self.state.skill_proficiencies,
            "features": class_data.features_by_level.get(1, []),
            "traits": race_data.traits,
        }
