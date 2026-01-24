"""Guided character creation flow with explanations."""

import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from ..models.ability_scores import AbilityScores, AbilityName
from ..models.races import RaceName, RACES
from ..models.archetypes import ClassName, CLASSES, get_starting_hp, get_archetypes_for_genre, get_archetype
from ..models.origins import get_origins_for_genre, get_origin
from ..models.character_sheet import CharacterSheet
from ..genre.config import get_genre


# Cache for genre powers data
_genre_powers_cache: Optional[Dict[str, Any]] = None


def get_genre_powers() -> Dict[str, Any]:
    """Load genre-specific abilities from genre_powers.json."""
    global _genre_powers_cache
    if _genre_powers_cache is None:
        data_path = Path(__file__).parent.parent / "data" / "genre_powers.json"
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                _genre_powers_cache = json.load(f)
        else:
            _genre_powers_cache = {}
    return _genre_powers_cache


def get_powers_for_genre(genre: str) -> Optional[Dict[str, Any]]:
    """Get the powers/abilities data for a specific genre."""
    powers = get_genre_powers()
    return powers.get(genre)


# Genre-specific default equipment based on proficiencies
GENRE_EQUIPMENT_DEFAULTS = {
    "modern": {
        "firearms": ["pistol", "ammunition (box)"],
        "pistols": ["pistol", "ammunition (box)"],
        "simple": ["utility knife"],
        "light": ["leather jacket"],
        "medium": ["tactical vest"],
        "default": ["smartphone", "wallet", "keys", "casual clothing"],
    },
    "scifi": {
        "firearms": ["laser pistol", "power cell"],
        "pistols": ["laser pistol", "power cell"],
        "rifles": ["plasma rifle", "power cell (2)"],
        "simple": ["utility tool"],
        "light": ["flight suit"],
        "medium": ["combat armor"],
        "heavy": ["power armor"],
        "default": ["communicator", "datapad", "credit chip"],
    },
    "western": {
        "firearms": ["revolver", "ammunition (20)"],
        "pistols": ["revolver", "ammunition (20)"],
        "rifles": ["rifle", "ammunition (20)"],
        "simple": ["hunting knife"],
        "light": ["leather duster"],
        "default": ["bedroll", "canteen", "rope (50 ft)"],
    },
    "cyberpunk": {
        "firearms": ["smartgun", "ammunition (box)"],
        "pistols": ["heavy pistol", "ammunition (box)"],
        "simple": ["monoblade"],
        "light": ["armored jacket"],
        "medium": ["corporate security armor"],
        "default": ["agent (phone)", "credstick", "interface plugs"],
    },
    "noir": {
        "firearms": ["snub-nose revolver", "ammunition (12)"],
        "pistols": ["snub-nose revolver", "ammunition (12)"],
        "simple": ["switchblade"],
        "light": ["trench coat"],
        "default": ["cigarettes", "lighter", "notepad", "business cards"],
    },
    "horror": {
        "firearms": ["shotgun", "shells (12)"],
        "pistols": ["revolver", "ammunition (12)"],
        "simple": ["crowbar"],
        "light": ["heavy coat"],
        "default": ["flashlight", "first aid kit", "rope"],
    },
    "fantasy": {
        "martial": ["longsword"],
        "simple": ["quarterstaff", "dagger"],
        "light": ["leather armor"],
        "medium": ["scale mail"],
        "heavy": ["chain mail"],
        "shields": ["shield"],
        "default": ["backpack", "bedroll", "waterskin", "rations (3 days)"],
    },
    "steampunk": {
        "firearms": ["pepperbox pistol", "ammunition (20)"],
        "martial": ["cavalry saber"],
        "simple": ["walking cane"],
        "light": ["leather coat"],
        "medium": ["reinforced vest"],
        "default": ["pocket watch", "goggles", "tool kit", "10 shillings"],
    },
    "postapoc": {
        "firearms": ["pipe rifle", "scrap ammunition (20)"],
        "martial": ["machete"],
        "simple": ["makeshift club"],
        "light": ["scrap leather"],
        "medium": ["salvaged armor"],
        "default": ["water canteen", "rad counter", "rope", "fire starter"],
    },
    "superhero": {
        "simple": ["collapsible baton"],
        "default": ["costume", "communicator", "secret identity gear"],
    },
    "mythology": {
        "martial": ["bronze spear", "xiphos (short sword)"],
        "simple": ["staff"],
        "light": ["chiton (robes)"],
        "medium": ["bronze cuirass"],
        "heavy": ["bronze armor"],
        "shields": ["aspis (round shield)"],
        "default": ["travel cloak", "waterskin", "sacred token", "10 drachmas"],
    },
    "wuxia": {
        "martial": ["jian (straight sword)", "dao (saber)"],
        "monk": ["iron palm gloves"],
        "simple": ["bo staff"],
        "light": ["traveling robes"],
        "default": ["waterskin", "rice", "bedroll", "5 taels silver"],
    },
    "pirate": {
        "firearms": ["flintlock pistol", "powder and shot (20)"],
        "martial": ["cutlass"],
        "simple": ["belaying pin"],
        "light": ["sailor's garb"],
        "medium": ["leather jerkin"],
        "default": ["compass", "rope (50 ft)", "grappling hook", "10 pieces of eight"],
    },
    "dark_fantasy": {
        "firearms": ["crossbow", "bolts (20)"],
        "martial": ["longsword"],
        "simple": ["torch", "dagger"],
        "light": ["leather armor"],
        "medium": ["chain shirt"],
        "heavy": ["plate armor"],
        "shields": ["shield"],
        "default": ["bedroll", "flint and steel", "holy symbol", "5 crowns"],
    },
    "space_opera": {
        "blasters": ["blaster pistol", "power cell"],
        "heavy": ["blaster rifle", "power cell (2)"],
        "simple": ["vibroblade"],
        "light": ["flight suit"],
        "medium": ["combat armor"],
        "powered": ["power armor"],
        "default": ["communicator", "datapad", "ration packs (3)", "500 credits"],
    },
}


class GuidedCreationState(BaseModel):
    """Tracks state through guided creation flow."""
    step: int = 0
    name: Optional[str] = None
    race: Optional[str] = None  # Now stores origin ID (genre-agnostic)
    character_class: Optional[str] = None  # Now stores archetype ID (genre-agnostic)
    playstyle: Optional[str] = None  # "warrior", "skilled", "caster"
    ability_priority: Optional[str] = None  # Primary stat preference
    skill_proficiencies: List[str] = []
    selected_cantrips: List[str] = []  # Selected cantrip IDs
    selected_spells: List[str] = []  # Selected spell IDs
    selected_equipment: Dict[str, str] = {}  # choice_1: "option_id", etc.
    selected_background: Optional[str] = None  # e.g., "acolyte"
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
    7. "What is your background?" (background selection)
    8. Review with narrative summary
    """

    PLAYSTYLE_TO_ABILITIES = {
        "fighting": ["strength", "constitution"],
        "stealth": ["dexterity", "intelligence"],
        "magic": ["intelligence", "wisdom"],
        "leadership": ["charisma", "wisdom"],
    }

    def __init__(self, genre: str = "fantasy", world_character_options: Dict[str, Any] = None):
        self.state = GuidedCreationState()
        self.genre = genre  # Store for future genre-specific content
        self.world_options = world_character_options  # MANTLE world-specific options

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
            # Get genre-specific origins instead of hardcoded D&D races
            genre_config = get_genre(self.genre)

            # Use world-specific MANTLE options if available
            options = []
            if self.world_options and self.world_options.get("origins"):
                # World has MANTLE-approved origins - use these exclusively
                for origin_data in self.world_options["origins"]:
                    # Look up base type mechanics from genre data
                    base_type = origin_data.get("base_type", "human")
                    base_origin = get_origin(base_type, self.genre)

                    # Format ability bonuses from base type
                    if base_origin and base_origin.ability_bonuses:
                        bonus_parts = [f"+{v} {k.title()}" for k, v in base_origin.ability_bonuses.items() if v > 0]
                        mechanical_hint = ", ".join(bonus_parts[:3])
                        if len(bonus_parts) > 3:
                            mechanical_hint += " and more"
                    else:
                        mechanical_hint = "Balanced abilities"

                    options.append({
                        "id": origin_data.get("id", origin_data.get("name", "").lower().replace(" ", "_")),
                        "name": origin_data.get("name", "Unknown"),
                        "tagline": origin_data.get("description", "")[:50],
                        "description": origin_data.get("description", "A unique origin"),
                        "mechanical_hint": mechanical_hint,
                        "base_type": base_type,  # Include base type for mechanics
                    })
            else:
                # Fall back to genre default origins
                origins = get_origins_for_genre(self.genre)
                for origin in origins:
                    # Format ability bonuses as hint
                    if origin.ability_bonuses:
                        bonus_parts = [f"+{v} {k.title()}" for k, v in origin.ability_bonuses.items() if v > 0]
                        mechanical_hint = ", ".join(bonus_parts[:3])  # Limit to 3 for readability
                        if len(bonus_parts) > 3:
                            mechanical_hint += " and more"
                    else:
                        mechanical_hint = "Balanced abilities"

                    options.append({
                        "id": origin.id,
                        "name": origin.display_name,
                        "tagline": origin.personality_hint.split(",")[0] if origin.personality_hint else origin.description[:50],
                        "description": origin.description,
                        "mechanical_hint": mechanical_hint,
                    })

            # Use genre-appropriate terminology
            origin_term = genre_config.terminology.origin

            return {
                "step": "ancestry",
                "question": f"What {origin_term.lower()} calls to you?",
                "hint": f"Your {origin_term.lower()} shapes your natural abilities and heritage.",
                "options": options,
            }

        elif step == 2:
            # Get genre-specific archetypes instead of hardcoded D&D classes
            # NOTE: has_powers can mean magic, tech, psionics, ki, etc. depending on genre
            # The genre-specific archetypes already have appropriate powers for their setting
            genre_config = get_genre(self.genre)

            # Use world-specific MANTLE options if available
            options = []
            if self.world_options and self.world_options.get("archetypes"):
                # World has MANTLE-approved archetypes - use these exclusively
                for arch_data in self.world_options["archetypes"]:
                    # Look up base type mechanics from genre data
                    base_type = arch_data.get("base_type", "fighter")
                    base_arch = get_archetype(base_type, self.genre)

                    playstyle = arch_data.get("description", "")[:60]
                    if base_arch and base_arch.playstyle_hint:
                        playstyle = base_arch.playstyle_hint

                    options.append({
                        "id": arch_data.get("id", arch_data.get("name", "").lower().replace(" ", "_")),
                        "name": arch_data.get("name", "Unknown"),
                        "tagline": arch_data.get("description", "")[:50],
                        "description": arch_data.get("description", "A unique calling"),
                        "playstyle": playstyle,
                        "base_type": base_type,  # Include base type for mechanics
                    })
            else:
                # Fall back to genre default archetypes
                archetypes = get_archetypes_for_genre(self.genre)
                for arch in archetypes:
                    options.append({
                        "id": arch.id,
                        "name": arch.display_name,
                        "tagline": arch.playstyle_hint.split(",")[0] if arch.playstyle_hint else arch.description[:50],
                        "description": arch.description,
                        "playstyle": arch.playstyle_hint or "Versatile adventurer",
                    })

            # Use genre-appropriate terminology
            archetype_term = genre_config.terminology.archetype

            return {
                "step": "calling",
                "question": f"What is your {archetype_term.lower()}?",
                "hint": "How do you face the challenges ahead?",
                "options": options,
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
            # Skills - prioritize world-specific archetype data, then genre archetypes
            skill_choices = []
            num_choices = 2

            # First try world-specific archetype from MANTLE world options
            world_archetype = None
            if self.world_options:
                archetypes = self.world_options.get("archetypes", [])
                for arch in archetypes:
                    if arch.get("id") == self.state.character_class:
                        world_archetype = arch
                        break

            if world_archetype:
                # Use world-specific skill choices
                skill_choices = list(world_archetype.get("skill_choices", []))
                num_choices = world_archetype.get("num_skill_choices", 2)
            else:
                # Fall back to genre archetypes
                archetype = get_archetype(self.state.character_class, self.genre)
                if archetype:
                    skill_choices = list(archetype.skill_choices)
                    num_choices = archetype.num_skill_choices
                else:
                    # Last resort: fantasy classes
                    class_data = CLASSES.get(self.state.character_class)
                    skill_choices = list(class_data.skill_choices) if class_data else []
                    num_choices = class_data.num_skill_choices if class_data else 2

            # Add setting-specific skills from world options
            if self.world_options:
                setting_skills = self.world_options.get("setting_skills", [])
                for skill in setting_skills:
                    skill_id = skill.get("id") or skill.get("name", "").lower().replace(" ", "_")
                    # Add if not already in list
                    if skill_id and skill_id not in [s.lower() for s in skill_choices]:
                        skill_choices.append(skill_id)

            # Ensure at least 3 choices available (more interesting for players)
            num_choices = max(num_choices, 3) if len(skill_choices) >= 3 else len(skill_choices)

            return {
                "step": "skills",
                "question": "What are you especially good at?",
                "hint": f"Choose {num_choices} skills that fit your character.",
                "num_choices": num_choices,
                "options": [
                    self._skill_to_option(skill) for skill in skill_choices
                ],
            }

        elif step == 5:
            # Spell/power/ability selection step - genre and archetype aware
            # Every character should get meaningful ability choices appropriate to their genre
            genre_config = get_genre(self.genre)
            archetype = get_archetype(self.state.character_class, self.genre)

            # Check for genre-specific powers (wuxia techniques, noir methods, etc.)
            genre_powers = get_powers_for_genre(self.genre)

            # For fantasy genre with casters, use SRD spells
            if self.genre == "fantasy":
                # Non-casters in fantasy don't select spells
                if archetype and not archetype.has_powers:
                    self.state.step = 6
                    return self.get_step_content()

                # Fallback check for fantasy classes
                if not archetype:
                    class_data = CLASSES.get(self.state.character_class)
                    if not class_data or not class_data.spellcasting:
                        self.state.step = 6
                        return self.get_step_content()

                from ..data.loader import get_srd_loader
                loader = get_srd_loader()

                # Get cantrips and level 1 spells for this class
                class_id = self.state.character_class
                cantrips = loader.get_cantrips_for_class(class_id)
                level_1_spells = [s for s in loader.get_spells_for_class(class_id) if s.get("level") == 1]

                # Calculate how many spells to prepare
                if archetype:
                    num_cantrips = archetype.cantrips_known
                else:
                    class_data = CLASSES.get(self.state.character_class)
                    num_cantrips = class_data.cantrips_known if class_data else 2
                num_prepared = self._get_prepared_spell_count()

                # Skip if no spells available
                if num_cantrips == 0 and not level_1_spells:
                    self.state.step = 6
                    return self.get_step_content()

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

            # For non-fantasy genres, use genre-specific abilities
            # This ensures even "grounded" genres feel powerful through specialties/tricks/methods
            if genre_powers:
                power_term = genre_powers.get("power_term", "Abilities")
                cantrip_term = genre_powers.get("cantrip_term", "Basic Abilities")
                basic_forms = genre_powers.get("basic_forms", [])
                techniques = genre_powers.get("techniques", [])
                num_basic = genre_powers.get("default_basic", 2)
                num_techniques = genre_powers.get("default_techniques", 2)

                return {
                    "step": "abilities",
                    "question": f"Choose your {power_term.lower()}",
                    "hint": f"Select {num_basic} {cantrip_term.lower()} and {num_techniques} {power_term.lower()}. These define what makes your character special.",
                    "power_term": power_term,
                    "cantrip_term": cantrip_term,
                    "cantrips": {
                        "options": [self._power_to_option(p) for p in basic_forms],
                        "num_choices": num_basic,
                        "selected": self.state.selected_cantrips,
                    },
                    "spells": {
                        "options": [self._power_to_option(p) for p in techniques],
                        "num_choices": num_techniques,
                        "selected": self.state.selected_spells,
                    },
                }

            # Fallback: skip if no abilities defined for this genre
            self.state.step = 6
            return self.get_step_content()

        elif step == 6:
            # Equipment selection step - genre-aware
            genre_config = get_genre(self.genre)

            if self.genre == "fantasy":
                # Fantasy uses SRD equipment data
                from ..data.loader import get_srd_loader
                loader = get_srd_loader()
                class_id = self.state.character_class
                equipment_choices = loader.get_equipment_choices_for_class(class_id)

                if not equipment_choices:
                    # No choices for this class, skip to background
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
            else:
                # Non-fantasy: prioritize world-specific archetype equipment
                fixed_equipment = []
                archetype_name = self.state.character_class.title()

                # First check for world-specific archetype with starting_equipment
                world_archetype = None
                if self.world_options:
                    archetypes = self.world_options.get("archetypes", [])
                    for arch in archetypes:
                        if arch.get("id") == self.state.character_class:
                            world_archetype = arch
                            break

                if world_archetype and world_archetype.get("starting_equipment"):
                    # Use world-specific starting equipment directly
                    fixed_equipment = list(world_archetype.get("starting_equipment", []))
                    archetype_name = world_archetype.get("name", archetype_name)
                else:
                    # Fall back to genre equipment defaults
                    archetype = get_archetype(self.state.character_class, self.genre)
                    genre_equipment = GENRE_EQUIPMENT_DEFAULTS.get(self.genre, {})

                    # Add default items for this genre
                    fixed_equipment.extend(genre_equipment.get("default", []))

                    # Add weapon based on proficiencies
                    if archetype:
                        archetype_name = archetype.display_name
                        for prof in archetype.weapon_proficiencies:
                            if prof in genre_equipment:
                                fixed_equipment.extend(genre_equipment[prof])
                                break  # Only add one weapon type

                        # Add armor based on proficiencies
                        for armor_type in ["heavy", "medium", "light"]:
                            if armor_type in archetype.armor_proficiencies and armor_type in genre_equipment:
                                fixed_equipment.extend(genre_equipment[armor_type])
                                break  # Only add one armor type

                # Remove duplicates while preserving order
                seen = set()
                unique_equipment = []
                for item in fixed_equipment:
                    if item not in seen:
                        seen.add(item)
                        unique_equipment.append(item)

                return {
                    "step": "equipment",
                    "question": f"Your starting {genre_config.terminology.ability_power.lower() if hasattr(genre_config.terminology, 'ability_power') else 'gear'}",
                    "hint": f"Standard equipment for a {archetype_name} in this setting.",
                    "choices": [],  # No choices for non-fantasy - streamlined
                    "fixed": unique_equipment,
                }

        elif step == 7:
            # Background selection step
            from ..models.backgrounds import get_all_backgrounds
            backgrounds = get_all_backgrounds()

            return {
                "step": "background",
                "question": "What is your background?",
                "hint": "Your background describes where you came from and grants additional skills.",
                "options": [
                    {
                        "id": bg.id,
                        "name": bg.display_name,
                        "description": bg.description,
                        "skills": bg.skill_proficiencies,
                        "feature": bg.feature_name,
                    }
                    for bg in backgrounds
                ],
            }

        elif step == 8:
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

    def _power_to_option(self, power: Dict[str, Any]) -> Dict[str, Any]:
        """Convert genre power data to user-friendly option."""
        return {
            "id": power.get("id", power.get("name", "").lower().replace(" ", "_")),
            "name": power.get("name", "Unknown"),
            "description": power.get("description", ""),
        }

    def _get_prepared_spell_count(self) -> int:
        """Calculate number of prepared spells based on class and ability modifier."""
        if not self.state.character_class:
            return 2  # Default

        # Generate abilities to get the modifier
        abilities = self._generate_abilities()

        # character_class is now a string ID
        if self.state.character_class == "cleric":
            # Cleric prepares WIS mod + level spells (min 1)
            wis_mod = abilities.get_modifier(AbilityName.WIS)
            return max(1, wis_mod + 1)  # +1 for level 1
        elif self.state.character_class == "wizard":
            # Wizard prepares INT mod + level spells (min 1)
            int_mod = abilities.get_modifier(AbilityName.INT)
            return max(1, int_mod + 1)  # +1 for level 1

        # For other archetypes with powers, use archetype's power_ability
        archetype = get_archetype(self.state.character_class, self.genre)
        if archetype and archetype.power_ability:
            # Map full ability name to AbilityName enum (lowercase 3-letter code)
            ability_map = {
                "strength": AbilityName.STR,
                "dexterity": AbilityName.DEX,
                "constitution": AbilityName.CON,
                "intelligence": AbilityName.INT,
                "wisdom": AbilityName.WIS,
                "charisma": AbilityName.CHA,
            }
            ability_name = ability_map.get(archetype.power_ability.lower(), AbilityName.INT)
            mod = abilities.get_modifier(ability_name)
            return max(1, mod + 1)

        return 2  # Default for other casters

    def _skill_to_option(self, skill: str) -> Dict[str, str]:
        """Convert skill name to user-friendly option."""
        skill_descriptions = {
            # Standard 5e Skills
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
            # Tech/Sci-Fi Skills
            "hacking": ("Hacking", "Breaking into computer systems and networks"),
            "computers": ("Computers", "Using and programming digital systems"),
            "electronics": ("Electronics", "Working with circuits and electrical devices"),
            "science": ("Science", "Applied physics, chemistry, and biology"),
            "demolitions": ("Demolitions", "Setting and disarming explosives"),
            "engineering": ("Engineering", "Designing and building structures/machines"),
            # Vehicle/Mechanical Skills
            "mechanics": ("Mechanics", "Repairing and maintaining machinery"),
            "piloting": ("Piloting", "Flying aircraft, spacecraft, or other vehicles"),
            "vehicles": ("Vehicles", "Operating cars, bikes, boats, and other transports"),
            "driving": ("Driving", "Maneuvering ground vehicles at speed"),
            "navigation": ("Navigation", "Finding your way using maps, stars, or tech"),
            # Street/Urban Skills
            "streetwise": ("Streetwise", "Knowing the streets, gangs, and underworld"),
            "contacts": ("Contacts", "Knowing people who can get things done"),
            # Medical Skills
            "first_aid": ("First Aid", "Emergency medical treatment in the field"),
            "surgery": ("Surgery", "Performing medical operations"),
            # Combat Skills
            "firearms": ("Firearms", "Using guns and ranged weapons effectively"),
            "martial_arts": ("Martial Arts", "Unarmed combat techniques and styles"),
            "brawling": ("Brawling", "Dirty fighting and bar room tactics"),
            # Craft/Artisan Skills
            "calligraphy": ("Calligraphy", "Beautiful writing and document creation"),
            "forgery": ("Forgery", "Creating fake documents and signatures"),
            "tinker": ("Tinker", "Building and modifying small gadgets"),
            # Social/Subterfuge Skills
            "disguise": ("Disguise", "Changing appearance to pass as another"),
            "etiquette": ("Etiquette", "Proper conduct in formal social settings"),
            "gambling": ("Gambling", "Games of chance and reading opponents"),
            "interrogation": ("Interrogation", "Extracting information through questioning"),
            # Wilderness Skills
            "tracking": ("Tracking", "Following trails and hunting prey"),
            "riding": ("Riding", "Controlling mounts and mounted combat"),
        }
        # First check world options for setting-specific skill descriptions
        if self.world_options:
            setting_skills = self.world_options.get("setting_skills", [])
            for setting_skill in setting_skills:
                skill_id = setting_skill.get("id") or setting_skill.get("name", "").lower().replace(" ", "_")
                if skill_id and skill_id.lower() == skill.lower():
                    return {
                        "id": skill,
                        "name": setting_skill.get("name", skill.replace("_", " ").title()),
                        "description": setting_skill.get("description", ""),
                    }

        # Fall back to hardcoded descriptions
        name, desc = skill_descriptions.get(skill.lower(), (skill.replace("_", " ").title(), ""))
        return {"id": skill, "name": name, "description": desc}

    def set_name(self, name: str) -> bool:
        if len(name.strip()) < 1:
            return False
        self.state.name = name.strip()
        self.state.step = 1
        return True

    def set_race(self, race: str) -> bool:
        # Store origin ID directly (genre-agnostic)
        self.state.race = race.lower()
        self.state.step = 2
        return True

    def set_class(self, character_class: str) -> bool:
        # Store archetype ID directly (genre-agnostic)
        self.state.character_class = character_class.lower()
        self.state.step = 3
        return True

    def set_strength_priority(self, priority: str) -> bool:
        valid = ["physical", "agility", "intellect", "presence"]
        if priority.lower() not in valid:
            return False
        self.state.ability_priority = priority.lower()
        self.state.step = 4
        return True

    def set_skills(self, skills: List[str]) -> bool:
        # Get archetype data for skill validation - same logic as get_step_content
        available = []
        num_choices = 2

        # First try world-specific archetype from MANTLE world options
        world_archetype = None
        if self.world_options:
            archetypes = self.world_options.get("archetypes", [])
            for arch in archetypes:
                if arch.get("id") == self.state.character_class:
                    world_archetype = arch
                    break

        if world_archetype:
            # Use world-specific skill choices
            available = [s.lower() for s in world_archetype.get("skill_choices", [])]
            num_choices = world_archetype.get("num_skill_choices", 2)
        else:
            # Fall back to genre archetypes
            archetype = get_archetype(self.state.character_class, self.genre)
            if archetype:
                available = [s.lower() for s in archetype.skill_choices]
                num_choices = archetype.num_skill_choices
            else:
                # Last resort: fantasy classes
                class_data = CLASSES.get(ClassName(self.state.character_class)) if self.state.character_class in [c.value for c in ClassName] else None
                if class_data:
                    num_choices = class_data.num_skill_choices
                    available = [s.lower() for s in class_data.skill_choices]
                else:
                    num_choices = 2
                    available = [s.lower() for s in skills]  # Accept whatever was provided

        # Include setting-specific skills in available list
        if self.world_options:
            setting_skills = self.world_options.get("setting_skills", [])
            for skill in setting_skills:
                skill_id = skill.get("id") or skill.get("name", "").lower().replace(" ", "_")
                if skill_id and skill_id.lower() not in available:
                    available.append(skill_id.lower())

        # Ensure at least 3 choices allowed (matches get_step_content)
        num_choices = max(num_choices, 3) if len(available) >= 3 else len(available)

        if len(skills) != num_choices:
            return False
        for skill in skills:
            if skill.lower() not in available:
                return False
        self.state.skill_proficiencies = [s.lower() for s in skills]
        self.state.step = 5  # Go to spell selection (non-casters will auto-skip)
        return True

    def set_spells(self, cantrips: List[str], spells: List[str]) -> bool:
        """Set selected cantrips/basic forms and spells/techniques."""
        # Get archetype data
        archetype = get_archetype(self.state.character_class, self.genre)

        # For fantasy, check if non-caster
        if self.genre == "fantasy":
            if archetype and not archetype.has_powers:
                self.state.step = 6  # Go to equipment
                return True

            # Get expected cantrip count
            if archetype:
                expected_cantrips = archetype.cantrips_known
            else:
                # Fallback for fantasy classes
                class_data = CLASSES.get(ClassName(self.state.character_class)) if self.state.character_class in [c.value for c in ClassName] else None
                expected_cantrips = class_data.cantrips_known if class_data else 0

            # Validate cantrip count
            if len(cantrips) != expected_cantrips:
                return False

            # Validate spell count
            num_prepared = self._get_prepared_spell_count()
            if len(spells) != num_prepared:
                return False

            # Validate selections are available to this class
            from ..data.loader import get_srd_loader
            loader = get_srd_loader()
            class_id = self.state.character_class

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
            self.state.step = 6
            return True

        # For non-fantasy genres, validate against genre powers
        genre_powers = get_powers_for_genre(self.genre)
        if not genre_powers:
            # No powers for this genre, skip
            self.state.step = 6
            return True

        # Validate counts
        expected_basic = genre_powers.get("default_basic", 2)
        expected_techniques = genre_powers.get("default_techniques", 2)

        if len(cantrips) != expected_basic:
            return False
        if len(spells) != expected_techniques:
            return False

        # Validate selections exist in genre powers
        available_basic = {p.get("id") for p in genre_powers.get("basic_forms", [])}
        available_techniques = {p.get("id") for p in genre_powers.get("techniques", [])}

        for c in cantrips:
            if c not in available_basic:
                return False
        for s in spells:
            if s not in available_techniques:
                return False

        self.state.selected_cantrips = cantrips
        self.state.selected_spells = spells
        self.state.step = 6  # Advance to equipment selection
        return True

    def set_equipment(self, choices: Dict[str, str]) -> bool:
        """Set selected equipment choices."""
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        class_id = self.state.character_class
        equipment_data = loader.get_equipment_choices_for_class(class_id)

        if not equipment_data:
            # No choices for this class, advance to background
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
        self.state.step = 7  # Advance to background selection
        return True

    def set_background(self, background: str) -> bool:
        """Set selected background."""
        from ..models.backgrounds import get_background
        bg = get_background(background)
        if not bg:
            return False

        self.state.selected_background = background
        self.state.step = 8  # Advance to review
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

        # Adjust for class primary ability - use genre-aware archetype lookup
        archetype = get_archetype(self.state.character_class, self.genre)
        if archetype:
            primary = archetype.primary_ability
        else:
            class_data = CLASSES.get(self.state.character_class)
            primary = class_data.primary_ability if class_data else "strength"

        # Ensure primary ability is at least 14
        if base_scores.get(primary, 10) < 14:
            # Swap with the 14
            for ability, score in base_scores.items():
                if score == 14:
                    base_scores[ability] = base_scores.get(primary, 10)
                    base_scores[primary] = 14
                    break

        # Apply origin bonuses - use genre-aware origin lookup
        origin_data = get_origin(self.state.race, self.genre)
        if origin_data and origin_data.ability_bonuses:
            for ability, bonus in origin_data.ability_bonuses.items():
                if ability in base_scores:
                    base_scores[ability] = min(20, base_scores[ability] + bonus)
        elif self.state.race in RACES:
            # Fallback to fantasy RACES if origin not found
            race_data = RACES[self.state.race]
            for ability, bonus in race_data.ability_bonuses.items():
                base_scores[ability] = min(20, base_scores[ability] + bonus)

        return AbilityScores(**base_scores)

    def finalize(self, player_id: str = "") -> CharacterSheet:
        """Create the final character sheet."""
        if self.state.step != 8:
            raise ValueError("Character creation not complete")

        # Use genre-aware origin lookup with fallback to fantasy RACES
        origin_data = get_origin(self.state.race, self.genre)
        if not origin_data and self.state.race in RACES:
            origin_data = RACES[self.state.race]

        # Use genre-aware archetype lookup with fallback to CLASSES
        archetype = get_archetype(self.state.character_class, self.genre)
        if archetype:
            class_data = archetype
            is_caster = archetype.has_powers
        else:
            class_data = CLASSES.get(self.state.character_class)
            is_caster = getattr(class_data, 'spellcasting', False) or getattr(class_data, 'has_powers', False) if class_data else False

        abilities = self._generate_abilities()

        con_mod = abilities.get_modifier(AbilityName.CON)
        dex_mod = abilities.get_modifier(AbilityName.DEX)
        starting_hp = get_starting_hp(self.state.character_class, con_mod, self.genre)

        # Build equipment from selections
        equipment = self._build_equipment_list(dex_mod)

        # Calculate AC based on selected armor
        base_ac = self._calculate_ac_from_equipment(equipment, dex_mod)

        # Spell slots for casters - use player-selected spells
        spell_slots = {}
        cantrips = []
        spells_known = []
        if is_caster:
            spell_slots = {1: 2}
            cantrips = self.state.selected_cantrips
            spells_known = self.state.selected_spells

        # Build skill list combining class and background
        all_skills = list(self.state.skill_proficiencies)
        background_data = None
        if self.state.selected_background:
            from ..models.backgrounds import get_background
            background_data = get_background(self.state.selected_background)
            if background_data:
                for skill in background_data.skill_proficiencies:
                    if skill not in all_skills:
                        all_skills.append(skill)

        # Get speed from origin (default 30 if not found)
        speed = origin_data.speed if origin_data and hasattr(origin_data, 'speed') else 30

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
            speed=speed,
            skill_proficiencies=all_skills,
            saving_throw_proficiencies=class_data.saving_throw_proficiencies if class_data else [],
            armor_proficiencies=class_data.armor_proficiencies if class_data else [],
            weapon_proficiencies=class_data.weapon_proficiencies if class_data else [],
            equipment=equipment,
            spell_slots_max=spell_slots,
            cantrips_known=cantrips,
            spells_known=spells_known,
            features=class_data.features_by_level.get(1, []) if class_data else [],
            background=self.state.selected_background or "",
            rules_visibility="guided",
            genre=self.genre,
        )

    def _build_equipment_list(self, dex_mod: int) -> List[str]:
        """Build equipment list from selected choices and fixed items."""
        from ..data.loader import get_srd_loader
        loader = get_srd_loader()
        class_id = self.state.character_class
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
            class_id = self.state.character_class

            # First check for world-specific archetype with starting_equipment
            world_archetype = None
            if self.world_options:
                archetypes = self.world_options.get("archetypes", [])
                for arch in archetypes:
                    if arch.get("id") == class_id:
                        world_archetype = arch
                        break

            if world_archetype and world_archetype.get("starting_equipment"):
                # Use world-specific starting equipment directly
                equipment = list(world_archetype.get("starting_equipment", []))
            elif class_id == "fighter":
                equipment = ["chain mail", "longsword", "shield"]
            elif class_id == "rogue":
                equipment = ["leather armor", "rapier", "shortbow"]
            elif class_id == "cleric":
                equipment = ["scale mail", "mace", "shield", "holy symbol"]
            elif class_id == "wizard":
                equipment = ["quarterstaff", "spellbook", "arcane focus"]
            elif class_id == "barbarian":
                equipment = ["greataxe", "handaxe", "explorer's pack"]
            elif class_id == "bard":
                equipment = ["rapier", "lute", "leather armor", "dagger"]
            elif class_id == "druid":
                equipment = ["wooden shield", "scimitar", "leather armor", "druidic focus"]
            elif class_id == "monk":
                equipment = ["shortsword", "dungeoneer's pack", "10 darts"]
            elif class_id == "paladin":
                equipment = ["chain mail", "longsword", "shield", "holy symbol"]
            elif class_id == "ranger":
                equipment = ["scale mail", "shortsword", "shortsword", "longbow", "20 arrows"]
            elif class_id == "sorcerer":
                equipment = ["light crossbow", "20 bolts", "arcane focus", "daggers"]
            elif class_id == "warlock":
                equipment = ["leather armor", "light crossbow", "20 bolts", "arcane focus", "daggers"]
            else:
                # For non-fantasy archetypes, use genre equipment defaults
                genre_equipment = GENRE_EQUIPMENT_DEFAULTS.get(self.genre, {})
                archetype = get_archetype(class_id, self.genre)

                if genre_equipment:
                    equipment = list(genre_equipment.get("default", []))
                    # Add weapon based on archetype proficiencies
                    if archetype:
                        for prof in archetype.weapon_proficiencies:
                            if prof in genre_equipment:
                                equipment.extend(genre_equipment[prof])
                                break
                        for armor_type in ["heavy", "medium", "light"]:
                            if armor_type in archetype.armor_proficiencies and armor_type in genre_equipment:
                                equipment.extend(genre_equipment[armor_type])
                                break
                else:
                    # Generic fallback
                    equipment = ["dagger", "explorer's pack"]

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

        # Use genre-aware lookups
        origin_data = get_origin(self.state.race, self.genre)
        archetype = get_archetype(self.state.character_class, self.genre)

        # Get display names with fallbacks
        origin_name = origin_data.display_name if origin_data else self.state.race.title()
        archetype_name = archetype.display_name if archetype else self.state.character_class.title()

        con_mod = abilities.get_modifier(AbilityName.CON)
        hp = get_starting_hp(self.state.character_class, con_mod, self.genre)

        narrative = f"{self.state.name} is a {origin_name} {archetype_name}. "

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
            "race": origin_name,
            "class": archetype_name,
            "narrative": narrative,
            "hit_points": hp,
            "skills": self.state.skill_proficiencies,
            "cantrips": self.state.selected_cantrips,
            "spells": self.state.selected_spells,
        }
