"""Guided character creation flow with explanations."""

import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ..models.ability_scores import AbilityScores, AbilityName
from ..models.races import RaceName, RACES
from ..models.classes import ClassName, CLASSES, get_starting_hp
from ..models.character_sheet import CharacterSheet


class GuidedCreationState(BaseModel):
    """Tracks state through guided creation flow."""
    step: int = 0
    name: Optional[str] = None
    race: Optional[RaceName] = None
    character_class: Optional[ClassName] = None
    playstyle: Optional[str] = None  # "warrior", "skilled", "caster"
    ability_priority: Optional[str] = None  # Primary stat preference
    skill_proficiencies: List[str] = []
    selected_cantrips: List[str] = []  # Selected cantrip IDs
    selected_spells: List[str] = []  # Selected spell IDs
    selected_equipment: Dict[str, str] = {}  # choice_1: "option_id", etc.
    completed: bool = False


class GuidedCreationFlow:
    """
    Step-by-step character creation with plain language explanations.

    Steps:
    0. Choose name
    1. "What ancestry calls to you?" (race with narrative framing)
    2. "What is your calling?" (class with playstyle focus)
    3. "What is your greatest strength?" (simplified ability priority)
    4. "What are you good at?" (skills with context)
    5. "Choose your spells" (casters only, non-casters skip)
    6. "Choose your equipment" (class-based choices)
    7. Review with narrative summary
    """

    PLAYSTYLE_TO_ABILITIES = {
        "fighting": ["strength", "constitution"],
        "stealth": ["dexterity", "intelligence"],
        "magic": ["intelligence", "wisdom"],
        "leadership": ["charisma", "wisdom"],
    }

    def __init__(self, genre: str = "fantasy"):
        self.state = GuidedCreationState()
        self.genre = genre  # Store for future genre-specific content

    def get_current_step(self) -> int:
        return self.state.step

    def get_step_content(self) -> Dict[str, Any]:
        """Get content for current step with explanations."""
        step = self.state.step

        if step == 0:
            return {
                "step": "name",
                "question": "What is your character called?",
                "hint": "This is how others will address you in the world.",
                "input_type": "text",
            }

        elif step == 1:
            return {
                "step": "ancestry",
                "question": "What ancestry calls to you?",
                "hint": "Your ancestry shapes your natural abilities and heritage.",
                "options": [
                    {
                        "id": "human",
                        "name": "Human",
                        "tagline": "Versatile and ambitious",
                        "description": "Humans are adaptable and driven. They excel at anything they put their mind to.",
                        "mechanical_hint": "Bonus to all abilities - good at everything",
                    },
                    {
                        "id": "elf",
                        "name": "Elf",
                        "tagline": "Graceful and perceptive",
                        "description": "Elves have keen senses and natural agility. They see in darkness and resist enchantments.",
                        "mechanical_hint": "Bonus to Dexterity - nimble and precise",
                    },
                    {
                        "id": "dwarf",
                        "name": "Dwarf",
                        "tagline": "Tough and resilient",
                        "description": "Dwarves are hardy folk with poison resistance and darkvision. They endure what breaks others.",
                        "mechanical_hint": "Bonus to Constitution - hard to take down",
                    },
                    {
                        "id": "halfling",
                        "name": "Halfling",
                        "tagline": "Lucky and brave",
                        "description": "Halflings have uncanny luck and surprising courage. Misfortune tends to miss them.",
                        "mechanical_hint": "Bonus to Dexterity + reroll 1s - fortune favors you",
                    },
                ],
            }

        elif step == 2:
            return {
                "step": "calling",
                "question": "What is your calling?",
                "hint": "How do you face the challenges ahead?",
                "options": [
                    {
                        "id": "fighter",
                        "name": "Fighter",
                        "tagline": "Master of martial combat",
                        "description": "You solve problems with steel and determination. Tough, versatile, and deadly in combat.",
                        "playstyle": "Direct confrontation, protecting allies",
                    },
                    {
                        "id": "rogue",
                        "name": "Rogue",
                        "tagline": "Cunning and precise",
                        "description": "You prefer guile over brute force. Strike from shadows, pick locks, and talk your way out of trouble.",
                        "playstyle": "Stealth, skills, and opportunistic strikes",
                    },
                    {
                        "id": "cleric",
                        "name": "Cleric",
                        "tagline": "Divine power and healing",
                        "description": "You channel divine magic to heal allies and smite foes. A beacon of hope in dark places.",
                        "playstyle": "Support, healing, and divine wrath",
                    },
                    {
                        "id": "wizard",
                        "name": "Wizard",
                        "tagline": "Arcane knowledge and power",
                        "description": "You've studied the arcane arts. Versatile magic lets you control the battlefield.",
                        "playstyle": "Powerful spells, utility, and knowledge",
                    },
                ],
            }

        elif step == 3:
            return {
                "step": "strengths",
                "question": "What is your greatest strength?",
                "hint": "This determines how we distribute your natural abilities.",
                "options": [
                    {
                        "id": "physical",
                        "name": "Physical Power",
                        "description": "You're naturally strong and tough. You can lift heavy things and take a hit.",
                        "abilities": ["strength", "constitution"],
                    },
                    {
                        "id": "agility",
                        "name": "Quick Reflexes",
                        "description": "You're fast and precise. You dodge danger and strike with accuracy.",
                        "abilities": ["dexterity", "constitution"],
                    },
                    {
                        "id": "intellect",
                        "name": "Sharp Mind",
                        "description": "You're clever and perceptive. You notice what others miss and learn quickly.",
                        "abilities": ["intelligence", "wisdom"],
                    },
                    {
                        "id": "presence",
                        "name": "Force of Personality",
                        "description": "You're charismatic and insightful. People listen when you speak.",
                        "abilities": ["charisma", "wisdom"],
                    },
                ],
            }

        elif step == 4:
            class_data = CLASSES[self.state.character_class]
            return {
                "step": "skills",
                "question": "What are you especially good at?",
                "hint": f"Choose {class_data.num_skill_choices} skills that fit your character.",
                "num_choices": class_data.num_skill_choices,
                "options": [
                    self._skill_to_option(skill) for skill in class_data.skill_choices
                ],
            }

        elif step == 5:
            # Spell selection step (casters only)
            class_data = CLASSES[self.state.character_class]
            if not class_data.spellcasting:
                # Non-casters skip spell selection, go to equipment
                self.state.step = 6
                return self.get_step_content()

            from ..data.loader import get_srd_loader
            loader = get_srd_loader()

            # Get cantrips and level 1 spells for this class
            class_id = self.state.character_class.value
            cantrips = loader.get_cantrips_for_class(class_id)
            level_1_spells = [s for s in loader.get_spells_for_class(class_id) if s.get("level") == 1]

            # Calculate how many spells to prepare (ability mod + level, min 1)
            num_cantrips = class_data.cantrips_known
            num_prepared = self._get_prepared_spell_count()

            return {
                "step": "spells",
                "question": "Choose your spells",
                "hint": f"Select {num_cantrips} cantrips and {num_prepared} prepared spells.",
                "cantrips": {
                    "options": [self._spell_to_option(s) for s in cantrips],
                    "num_choices": num_cantrips,
                    "selected": self.state.selected_cantrips,
                },
                "spells": {
                    "options": [self._spell_to_option(s) for s in level_1_spells],
                    "num_choices": num_prepared,
                    "selected": self.state.selected_spells,
                },
            }

        elif step == 6:
            # Equipment selection step
            from ..data.loader import get_srd_loader
            loader = get_srd_loader()
            class_id = self.state.character_class.value
            equipment_choices = loader.get_equipment_choices_for_class(class_id)

            if not equipment_choices:
                # No choices for this class, skip to review
                self.state.step = 7
                return self.get_step_content()

            choices = []
            for key, choice in equipment_choices.items():
                if key.startswith("choice_"):
                    choices.append({
                        "choice_id": key,
                        "prompt": choice.get("prompt", "Choose equipment"),
                        "options": choice.get("options", []),
                        "selected": self.state.selected_equipment.get(key),
                    })

            return {
                "step": "equipment",
                "question": "Choose your starting equipment",
                "hint": "Select your gear from the options below.",
                "choices": choices,
                "fixed": equipment_choices.get("fixed", []),
            }

        elif step == 7:
            return {
                "step": "review",
                "question": "Does this look right?",
                "character": self._build_narrative_summary(),
            }

        return {}

    def _spell_to_option(self, spell: Dict[str, Any]) -> Dict[str, Any]:
        """Convert spell data to user-friendly option."""
        return {
            "id": spell.get("id", spell.get("name", "").lower().replace(" ", "_")),
            "name": spell.get("name", "Unknown"),
            "school": spell.get("school", "").title(),
            "description": spell.get("description", "")[:150] + "..." if len(spell.get("description", "")) > 150 else spell.get("description", ""),
            "casting_time": spell.get("casting_time", "1 action"),
            "range": spell.get("range", "Self"),
            "concentration": spell.get("concentration", False),
            "duration": spell.get("duration", "Instantaneous"),
        }

    def _get_prepared_spell_count(self) -> int:
        """Calculate number of prepared spells based on class and ability modifier."""
        if not self.state.character_class:
            return 2  # Default

        # Generate abilities to get the modifier
        abilities = self._generate_abilities()

        if self.state.character_class == ClassName.CLERIC:
            # Cleric prepares WIS mod + level spells (min 1)
            wis_mod = abilities.get_modifier(AbilityName.WIS)
            return max(1, wis_mod + 1)  # +1 for level 1
        elif self.state.character_class == ClassName.WIZARD:
            # Wizard prepares INT mod + level spells (min 1)
            int_mod = abilities.get_modifier(AbilityName.INT)
            return max(1, int_mod + 1)  # +1 for level 1

        return 2  # Default for other casters

    def _skill_to_option(self, skill: str) -> Dict[str, str]:
        """Convert skill name to user-friendly option."""
        skill_descriptions = {
            "athletics": ("Athletics", "Climbing, jumping, swimming, feats of strength"),
            "acrobatics": ("Acrobatics", "Balance, tumbling, escaping grapples"),
            "stealth": ("Stealth", "Moving silently and hiding"),
            "sleight_of_hand": ("Sleight of Hand", "Pickpocketing, lockpicking, tricks"),
            "arcana": ("Arcana", "Knowledge of magic and the planes"),
            "history": ("History", "Knowledge of past events and civilizations"),
            "investigation": ("Investigation", "Finding clues and deducing facts"),
            "nature": ("Nature", "Knowledge of plants, animals, weather"),
            "religion": ("Religion", "Knowledge of gods, rituals, prayers"),
            "animal_handling": ("Animal Handling", "Calming and controlling animals"),
            "insight": ("Insight", "Reading people's true intentions"),
            "medicine": ("Medicine", "Stabilizing the wounded, diagnosing illness"),
            "perception": ("Perception", "Noticing hidden things and danger"),
            "survival": ("Survival", "Tracking, foraging, navigating wilderness"),
            "deception": ("Deception", "Lying and misdirection"),
            "intimidation": ("Intimidation", "Threatening and coercing"),
            "performance": ("Performance", "Entertaining and captivating audiences"),
            "persuasion": ("Persuasion", "Convincing others with charm and logic"),
        }
        name, desc = skill_descriptions.get(skill, (skill.title(), ""))
        return {"id": skill, "name": name, "description": desc}

    def set_name(self, name: str) -> bool:
        if len(name.strip()) < 1:
            return False
        self.state.name = name.strip()
        self.state.step = 1
        return True

    def set_race(self, race: str) -> bool:
        try:
            self.state.race = RaceName(race.lower())
            self.state.step = 2
            return True
        except ValueError:
            return False

    def set_class(self, character_class: str) -> bool:
        try:
            self.state.character_class = ClassName(character_class.lower())
            self.state.step = 3
            return True
        except ValueError:
            return False

    def set_strength_priority(self, priority: str) -> bool:
        valid = ["physical", "agility", "intellect", "presence"]
        if priority.lower() not in valid:
            return False
        self.state.ability_priority = priority.lower()
        self.state.step = 4
        return True

    def set_skills(self, skills: List[str]) -> bool:
        class_data = CLASSES[self.state.character_class]
        if len(skills) != class_data.num_skill_choices:
            return False
        available = [s.lower() for s in class_data.skill_choices]
        for skill in skills:
            if skill.lower() not in available:
                return False
        self.state.skill_proficiencies = [s.lower() for s in skills]
        self.state.step = 5  # Go to spell selection (non-casters will auto-skip)
        return True

    def set_spells(self, cantrips: List[str], spells: List[str]) -> bool:
        """Set selected cantrips and spells."""
        class_data = CLASSES[self.state.character_class]

        # Non-casters don't select spells
        if not class_data.spellcasting:
            self.state.step = 6  # Go to equipment
            return True

        # Validate cantrip count
        if len(cantrips) != class_data.cantrips_known:
            return False

        # Validate spell count
        num_prepared = self._get_prepared_spell_count()
        if len(spells) != num_prepared:
            return False

        # Validate selections are available to this class
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        class_id = self.state.character_class.value

        available_cantrips = {s.get("id", s.get("name", "").lower().replace(" ", "_"))
                             for s in loader.get_cantrips_for_class(class_id)}
        available_spells = {s.get("id", s.get("name", "").lower().replace(" ", "_"))
                           for s in loader.get_spells_for_class(class_id) if s.get("level") == 1}

        for c in cantrips:
            if c not in available_cantrips:
                return False
        for s in spells:
            if s not in available_spells:
                return False

        self.state.selected_cantrips = cantrips
        self.state.selected_spells = spells
        self.state.step = 6  # Advance to equipment selection
        return True

    def set_equipment(self, choices: Dict[str, str]) -> bool:
        """Set selected equipment choices."""
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        class_id = self.state.character_class.value
        equipment_data = loader.get_equipment_choices_for_class(class_id)

        if not equipment_data:
            # No choices for this class, advance to review
            self.state.step = 7
            return True

        # Validate all required choices are provided
        required_choices = [k for k in equipment_data.keys() if k.startswith("choice_")]
        for choice_key in required_choices:
            if choice_key not in choices:
                return False
            # Validate the option is valid
            choice_data = equipment_data[choice_key]
            valid_options = [opt.get("id") for opt in choice_data.get("options", [])]
            if choices[choice_key] not in valid_options:
                return False

        self.state.selected_equipment = choices
        self.state.step = 7  # Advance to review
        return True

    def _generate_abilities(self) -> AbilityScores:
        """Generate ability scores based on class and priority."""
        # Base array adjusted by priority
        priority_map = {
            "physical": {"strength": 15, "constitution": 14, "dexterity": 13,
                         "wisdom": 12, "intelligence": 10, "charisma": 8},
            "agility": {"dexterity": 15, "constitution": 14, "wisdom": 13,
                        "strength": 12, "intelligence": 10, "charisma": 8},
            "intellect": {"intelligence": 15, "wisdom": 14, "constitution": 13,
                          "dexterity": 12, "strength": 10, "charisma": 8},
            "presence": {"charisma": 15, "wisdom": 14, "constitution": 13,
                         "dexterity": 12, "intelligence": 10, "strength": 8},
        }

        base_scores = priority_map.get(self.state.ability_priority, priority_map["physical"])

        # Adjust for class primary ability
        class_data = CLASSES[self.state.character_class]
        primary = class_data.primary_ability

        # Ensure primary ability is at least 14
        if base_scores[primary] < 14:
            # Swap with the 14
            for ability, score in base_scores.items():
                if score == 14:
                    base_scores[ability] = base_scores[primary]
                    base_scores[primary] = 14
                    break

        # Apply racial bonuses
        race_data = RACES[self.state.race]
        for ability, bonus in race_data.ability_bonuses.items():
            base_scores[ability] = min(20, base_scores[ability] + bonus)

        return AbilityScores(**base_scores)

    def finalize(self, player_id: str = "") -> CharacterSheet:
        """Create the final character sheet."""
        if self.state.step != 7:
            raise ValueError("Character creation not complete")

        race_data = RACES[self.state.race]
        class_data = CLASSES[self.state.character_class]
        abilities = self._generate_abilities()

        con_mod = abilities.get_modifier(AbilityName.CON)
        dex_mod = abilities.get_modifier(AbilityName.DEX)
        starting_hp = get_starting_hp(self.state.character_class, con_mod)

        # Build equipment from selections
        equipment = self._build_equipment_list(dex_mod)

        # Calculate AC based on selected armor
        base_ac = self._calculate_ac_from_equipment(equipment, dex_mod)

        # Spell slots for casters - use player-selected spells
        spell_slots = {}
        cantrips = []
        spells_known = []
        if class_data.spellcasting:
            spell_slots = {1: 2}
            cantrips = self.state.selected_cantrips
            spells_known = self.state.selected_spells

        return CharacterSheet(
            character_id=str(uuid.uuid4()),
            name=self.state.name,
            player_id=player_id,
            race=self.state.race,
            character_class=self.state.character_class,
            level=1,
            ability_scores=abilities,
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
            rules_visibility="guided",
        )

    def _build_equipment_list(self, dex_mod: int) -> List[str]:
        """Build equipment list from selected choices and fixed items."""
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        class_id = self.state.character_class.value
        equipment_data = loader.get_equipment_choices_for_class(class_id)

        equipment = []

        if equipment_data:
            # Add fixed items
            equipment.extend(equipment_data.get("fixed", []))

            # Add items from selected choices
            for choice_key, selected_id in self.state.selected_equipment.items():
                choice_data = equipment_data.get(choice_key, {})
                for option in choice_data.get("options", []):
                    if option.get("id") == selected_id:
                        equipment.extend(option.get("items", []))
                        break
        else:
            # Fallback for classes without equipment data
            if self.state.character_class == ClassName.FIGHTER:
                equipment = ["chain mail", "longsword", "shield"]
            elif self.state.character_class == ClassName.ROGUE:
                equipment = ["leather armor", "rapier", "shortbow"]
            elif self.state.character_class == ClassName.CLERIC:
                equipment = ["scale mail", "mace", "shield", "holy symbol"]
            else:  # Wizard
                equipment = ["quarterstaff", "spellbook", "arcane focus"]

        return equipment

    def _calculate_ac_from_equipment(self, equipment: List[str], dex_mod: int) -> int:
        """Calculate AC based on equipped armor."""
        # Check for armor in equipment
        if "chain_mail" in equipment or "chain mail" in equipment:
            return 16  # Heavy armor, no DEX
        elif "scale_mail" in equipment or "scale mail" in equipment:
            base_ac = 14 + min(dex_mod, 2)  # Medium armor
        elif "leather" in equipment or "leather armor" in equipment:
            base_ac = 11 + dex_mod  # Light armor
        else:
            base_ac = 10 + dex_mod  # No armor

        # Add shield if present
        if "shield" in equipment:
            base_ac += 2

        return base_ac

    def _build_narrative_summary(self) -> Dict[str, Any]:
        """Build a narrative summary for review."""
        abilities = self._generate_abilities()
        race_data = RACES[self.state.race]
        class_data = CLASSES[self.state.character_class]

        con_mod = abilities.get_modifier(AbilityName.CON)
        hp = get_starting_hp(self.state.character_class, con_mod)

        narrative = f"{self.state.name} is a {race_data.display_name} {class_data.display_name}. "

        if self.state.ability_priority == "physical":
            narrative += "Strong and tough, they face challenges head-on. "
        elif self.state.ability_priority == "agility":
            narrative += "Quick and nimble, they strike with precision. "
        elif self.state.ability_priority == "intellect":
            narrative += "Sharp-minded and observant, knowledge is their weapon. "
        else:
            narrative += "Charismatic and insightful, they lead through presence. "

        narrative += f"With {hp} hit points, they're ready for adventure."

        return {
            "name": self.state.name,
            "race": race_data.display_name,
            "class": class_data.display_name,
            "narrative": narrative,
            "hit_points": hp,
            "skills": self.state.skill_proficiencies,
        }
