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
    completed: bool = False


class GuidedCreationFlow:
    """
    Step-by-step character creation with plain language explanations.

    Steps:
    1. Choose name
    2. "What draws you to adventure?" (race with narrative framing)
    3. "How do you solve problems?" (class with playstyle focus)
    4. "What are your strengths?" (simplified ability priority)
    5. "What are you good at?" (skills with context)
    6. Review with narrative summary
    """

    PLAYSTYLE_TO_ABILITIES = {
        "fighting": ["strength", "constitution"],
        "stealth": ["dexterity", "intelligence"],
        "magic": ["intelligence", "wisdom"],
        "leadership": ["charisma", "wisdom"],
    }

    def __init__(self):
        self.state = GuidedCreationState()

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
            return {
                "step": "review",
                "question": "Does this look right?",
                "character": self._build_narrative_summary(),
            }

        return {}

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
        self.state.step = 5
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
        if self.state.step != 5:
            raise ValueError("Character creation not complete")

        race_data = RACES[self.state.race]
        class_data = CLASSES[self.state.character_class]
        abilities = self._generate_abilities()

        con_mod = abilities.get_modifier(AbilityName.CON)
        dex_mod = abilities.get_modifier(AbilityName.DEX)
        starting_hp = get_starting_hp(self.state.character_class, con_mod)

        # Calculate AC based on class
        if self.state.character_class == ClassName.FIGHTER:
            base_ac = 16  # Chain mail
            equipment = ["chain mail", "longsword", "shield"]
        elif self.state.character_class == ClassName.ROGUE:
            base_ac = 11 + dex_mod
            equipment = ["leather armor", "rapier", "shortbow"]
        elif self.state.character_class == ClassName.CLERIC:
            base_ac = 14 + min(dex_mod, 2) + 2
            equipment = ["scale mail", "mace", "shield", "holy symbol"]
        else:  # Wizard
            base_ac = 10 + dex_mod
            equipment = ["quarterstaff", "spellbook", "arcane focus"]

        # Spell slots for casters
        spell_slots = {}
        cantrips = []
        spells_known = []
        if class_data.spellcasting:
            spell_slots = {1: 2}
            if self.state.character_class == ClassName.CLERIC:
                cantrips = ["sacred_flame", "light"]
                spells_known = ["cure_wounds", "bless"]
            else:
                cantrips = ["fire_bolt", "light"]
                spells_known = ["magic_missile", "shield"]

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
