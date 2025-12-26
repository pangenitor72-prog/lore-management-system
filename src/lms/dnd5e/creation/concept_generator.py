"""AI-driven character generation from natural language concepts."""

import uuid
import re
import logging
from typing import Optional, Dict, Any

from ..models.ability_scores import AbilityScores, AbilityName
from ..models.races import RaceName, RACES
from ..models.classes import ClassName, CLASSES, get_starting_hp
from ..models.character_sheet import CharacterSheet

logger = logging.getLogger(__name__)


# Keyword mappings for concept parsing (fallback when no AI available)
RACE_KEYWORDS = {
    RaceName.HUMAN: ["human", "man", "woman", "person", "versatile", "adaptable"],
    RaceName.ELF: ["elf", "elven", "elvish", "graceful", "ancient", "fey", "slender"],
    RaceName.DWARF: ["dwarf", "dwarven", "stout", "stocky", "bearded", "mountain", "forge"],
    RaceName.HALFLING: ["halfling", "hobbit", "small", "nimble", "cheerful", "lucky"],
}

CLASS_KEYWORDS = {
    ClassName.FIGHTER: ["fighter", "warrior", "soldier", "knight", "martial", "sword", "battle", "combat", "veteran"],
    ClassName.ROGUE: ["rogue", "thief", "assassin", "sneaky", "stealthy", "spy", "criminal", "pickpocket", "shadow"],
    ClassName.CLERIC: ["cleric", "priest", "healer", "divine", "holy", "temple", "religious", "faith"],
    ClassName.WIZARD: ["wizard", "mage", "sorcerer", "scholar", "arcane", "magic", "spell", "learned"],
}

ABILITY_KEYWORDS = {
    "strength": ["strong", "muscular", "powerful", "brute", "mighty", "brawny"],
    "dexterity": ["agile", "quick", "nimble", "graceful", "fast", "acrobatic", "stealthy"],
    "constitution": ["tough", "resilient", "hardy", "enduring", "sturdy", "rugged"],
    "intelligence": ["smart", "clever", "intelligent", "learned", "scholarly", "wise"],
    "wisdom": ["perceptive", "insightful", "observant", "spiritual", "intuitive"],
    "charisma": ["charismatic", "charming", "persuasive", "leader", "inspiring", "silver-tongued"],
}


class ConceptGenerator:
    """
    Generates complete characters from natural language descriptions.

    Can use AI (Gemini) for parsing, or falls back to keyword matching.
    """

    def __init__(self, gemini_client=None):
        """
        Initialize the concept generator.

        Args:
            gemini_client: Optional Gemini client for AI parsing
        """
        self.gemini_client = gemini_client

    async def generate_from_concept(
        self,
        concept: str,
        player_id: str = "",
    ) -> CharacterSheet:
        """
        Generate a complete character from a concept description.

        Args:
            concept: Natural language character description
            player_id: Player ID to associate with character

        Returns:
            Complete CharacterSheet
        """
        # Try AI parsing first if available
        if self.gemini_client:
            try:
                parsed = await self._ai_parse_concept(concept)
            except Exception as e:
                logger.warning(f"AI parsing failed, using fallback: {e}")
                parsed = self._keyword_parse_concept(concept)
        else:
            parsed = self._keyword_parse_concept(concept)

        return self._build_character(parsed, player_id)

    def generate_from_concept_sync(
        self,
        concept: str,
        player_id: str = "",
    ) -> CharacterSheet:
        """Synchronous version using keyword parsing only."""
        parsed = self._keyword_parse_concept(concept)
        return self._build_character(parsed, player_id)

    async def _ai_parse_concept(self, concept: str) -> Dict[str, Any]:
        """Parse concept using AI (Gemini)."""
        prompt = f"""Parse this D&D character concept into structured data.

Character Concept: "{concept}"

Extract:
1. Name (if mentioned, otherwise suggest one)
2. Race (human, elf, dwarf, or halfling)
3. Class (fighter, rogue, cleric, or wizard)
4. Primary ability (strength, dexterity, constitution, intelligence, wisdom, or charisma)
5. Secondary ability
6. Two suggested skills appropriate for this character

Return as JSON:
{{
    "name": "Character Name",
    "race": "race_name",
    "class": "class_name",
    "primary_ability": "ability_name",
    "secondary_ability": "ability_name",
    "skills": ["skill1", "skill2"],
    "personality_note": "brief personality description"
}}

Only use the races and classes listed. Return valid JSON only."""

        # Call Gemini (implementation depends on your client)
        response = await self.gemini_client.generate_content(prompt)
        # Parse JSON from response
        import json
        # Extract JSON from response text
        text = response.text
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("Could not parse AI response as JSON")

    def _keyword_parse_concept(self, concept: str) -> Dict[str, Any]:
        """Parse concept using keyword matching (fallback)."""
        concept_lower = concept.lower()

        # Detect race
        detected_race = RaceName.HUMAN  # Default
        for race, keywords in RACE_KEYWORDS.items():
            if any(kw in concept_lower for kw in keywords):
                detected_race = race
                break

        # Detect class
        detected_class = ClassName.FIGHTER  # Default
        for cls, keywords in CLASS_KEYWORDS.items():
            if any(kw in concept_lower for kw in keywords):
                detected_class = cls
                break

        # Detect ability emphasis
        primary_ability = CLASSES[detected_class].primary_ability
        secondary_ability = "constitution"  # Safe default

        for ability, keywords in ABILITY_KEYWORDS.items():
            if any(kw in concept_lower for kw in keywords):
                if ability != primary_ability:
                    secondary_ability = ability
                    break

        # Extract name (look for capitalized words that aren't common words)
        words = concept.split()
        common_words = {"a", "an", "the", "who", "is", "was", "with", "and", "or", "but", "from"}
        name = None
        for word in words:
            if word[0].isupper() and word.lower() not in common_words:
                if word.lower() not in concept_lower.split():
                    continue
                # Check it's not a race/class keyword
                all_keywords = []
                for kws in RACE_KEYWORDS.values():
                    all_keywords.extend(kws)
                for kws in CLASS_KEYWORDS.values():
                    all_keywords.extend(kws)
                if word.lower() not in all_keywords:
                    name = word
                    break

        if not name:
            # Generate a default name based on race
            default_names = {
                RaceName.HUMAN: "Roland",
                RaceName.ELF: "Aelindra",
                RaceName.DWARF: "Thorin",
                RaceName.HALFLING: "Pippin",
            }
            name = default_names[detected_race]

        # Suggest skills based on class
        class_data = CLASSES[detected_class]
        skills = class_data.skill_choices[:class_data.num_skill_choices]

        return {
            "name": name,
            "race": detected_race.value,
            "class": detected_class.value,
            "primary_ability": primary_ability,
            "secondary_ability": secondary_ability,
            "skills": skills,
            "personality_note": concept,
        }

    def _build_character(self, parsed: Dict[str, Any], player_id: str) -> CharacterSheet:
        """Build a CharacterSheet from parsed concept data."""
        race = RaceName(parsed["race"])
        char_class = ClassName(parsed["class"])
        race_data = RACES[race]
        class_data = CLASSES[char_class]

        # Generate ability scores optimized for class
        primary = parsed["primary_ability"]
        secondary = parsed.get("secondary_ability", "constitution")

        # Start with balanced scores, boost primary and secondary
        base_scores = {
            "strength": 10,
            "dexterity": 10,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        # Set primary to 15, secondary to 14
        base_scores[primary] = 15
        if secondary != primary:
            base_scores[secondary] = 14

        # Ensure CON is reasonable for survivability
        if base_scores["constitution"] < 12:
            base_scores["constitution"] = 12

        # Apply racial bonuses
        for ability, bonus in race_data.ability_bonuses.items():
            base_scores[ability] = min(20, base_scores[ability] + bonus)

        abilities = AbilityScores(**base_scores)

        # Calculate derived stats
        con_mod = abilities.get_modifier(AbilityName.CON)
        dex_mod = abilities.get_modifier(AbilityName.DEX)
        starting_hp = get_starting_hp(char_class, con_mod)

        # Determine AC and equipment based on class
        if char_class == ClassName.FIGHTER:
            base_ac = 16  # Chain mail
            equipment = ["chain mail", "longsword", "shield"]
        elif char_class == ClassName.ROGUE:
            base_ac = 11 + dex_mod  # Leather
            equipment = ["leather armor", "rapier", "shortbow"]
        elif char_class == ClassName.CLERIC:
            base_ac = 14 + min(dex_mod, 2) + 2  # Scale mail + shield
            equipment = ["scale mail", "mace", "shield", "holy symbol"]
        else:  # Wizard
            base_ac = 10 + dex_mod  # No armor
            equipment = ["quarterstaff", "spellbook", "arcane focus"]

        # Spell setup for casters
        spell_slots = {}
        cantrips = []
        spells_known = []
        if class_data.spellcasting:
            spell_slots = {1: 2}
            if char_class == ClassName.CLERIC:
                cantrips = ["sacred_flame", "light"]
                spells_known = ["cure_wounds", "bless"]
            else:
                cantrips = ["fire_bolt", "light"]
                spells_known = ["magic_missile", "shield"]

        # Get skills (limit to class available)
        skills = parsed.get("skills", [])
        available = [s.lower() for s in class_data.skill_choices]
        skills = [s for s in skills if s.lower() in available]
        # Fill remaining slots if needed
        while len(skills) < class_data.num_skill_choices:
            for s in available:
                if s not in skills:
                    skills.append(s)
                    break
            if len(skills) >= class_data.num_skill_choices:
                break

        return CharacterSheet(
            character_id=str(uuid.uuid4()),
            name=parsed["name"],
            player_id=player_id,
            race=race,
            character_class=char_class,
            level=1,
            ability_scores=abilities,
            max_hit_points=starting_hp,
            current_hit_points=starting_hp,
            armor_class=base_ac,
            speed=race_data.speed,
            skill_proficiencies=skills[:class_data.num_skill_choices],
            saving_throw_proficiencies=class_data.saving_throw_proficiencies,
            armor_proficiencies=class_data.armor_proficiencies,
            weapon_proficiencies=class_data.weapon_proficiencies,
            equipment=equipment,
            spell_slots_max=spell_slots,
            cantrips_known=cantrips,
            spells_known=spells_known,
            features=class_data.features_by_level.get(1, []),
            rules_visibility="storyteller",  # Concept mode defaults to storyteller
        )
