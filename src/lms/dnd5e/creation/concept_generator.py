"""AI-driven character generation from natural language concepts."""

import uuid
import re
import logging
from typing import Optional, Dict, Any, List

from ..models.ability_scores import AbilityScores, AbilityName
from ..models.origins import get_origin, get_origins_for_genre, FANTASY_ORIGINS
from ..models.archetypes import get_archetype, get_archetypes_for_genre, get_starting_hp, FANTASY_ARCHETYPES
from ..models.character_sheet import CharacterSheet
from ..genre import get_genre

logger = logging.getLogger(__name__)


# =============================================================================
# KEYWORD MAPPINGS BY GENRE
# =============================================================================

# Fantasy (D&D 5e)
FANTASY_ORIGIN_KEYWORDS = {
    "human": ["human", "man", "woman", "person", "versatile", "adaptable"],
    "elf": ["elf", "elven", "elvish", "graceful", "ancient", "fey", "slender"],
    "dwarf": ["dwarf", "dwarven", "stout", "stocky", "bearded", "mountain", "forge"],
    "halfling": ["halfling", "hobbit", "small", "nimble", "cheerful", "lucky"],
}

FANTASY_ARCHETYPE_KEYWORDS = {
    "fighter": ["fighter", "warrior", "soldier", "knight", "martial", "sword", "battle", "combat", "veteran"],
    "rogue": ["rogue", "thief", "assassin", "sneaky", "stealthy", "spy", "criminal", "pickpocket", "shadow"],
    "cleric": ["cleric", "priest", "healer", "divine", "holy", "temple", "religious", "faith"],
    "wizard": ["wizard", "mage", "sorcerer", "scholar", "arcane", "magic", "spell", "learned"],
}

# Sci-Fi
SCIFI_ORIGIN_KEYWORDS = {
    "human": ["human", "terran", "earthling", "standard"],
    "android": ["android", "robot", "synthetic", "artificial", "machine", "droid"],
    "alien": ["alien", "xenomorph", "extraterrestrial", "otherworldly", "strange"],
    "cyborg": ["cyborg", "augmented", "enhanced", "implant", "modified", "hybrid"],
}

SCIFI_ARCHETYPE_KEYWORDS = {
    "soldier": ["soldier", "marine", "trooper", "fighter", "grunt", "military", "combat"],
    "hacker": ["hacker", "slicer", "netrunner", "tech", "coder", "digital", "cyber"],
    "pilot": ["pilot", "driver", "navigator", "ace", "hotshot", "helm"],
    "medic": ["medic", "doctor", "surgeon", "healer", "medical", "trauma"],
}

# Modern/Horror
MODERN_ORIGIN_KEYWORDS = {
    "urban": ["urban", "city", "metropolitan", "street", "downtown"],
    "rural": ["rural", "country", "farm", "small town", "rustic"],
    "military": ["military", "veteran", "service", "army", "navy", "marine", "soldier"],
    "academic": ["academic", "professor", "scholar", "university", "educated", "phd"],
}

MODERN_ARCHETYPE_KEYWORDS = {
    "detective": ["detective", "investigator", "cop", "police", "pi", "sleuth"],
    "soldier": ["soldier", "military", "veteran", "combat", "fighter"],
    "doctor": ["doctor", "physician", "surgeon", "medical", "healer", "nurse"],
    "engineer": ["engineer", "technician", "mechanic", "builder", "tech"],
}

# Genre keyword registry
ORIGIN_KEYWORDS_BY_GENRE = {
    "fantasy": FANTASY_ORIGIN_KEYWORDS,
    "scifi": SCIFI_ORIGIN_KEYWORDS,
    "modern": MODERN_ORIGIN_KEYWORDS,
    "horror": MODERN_ORIGIN_KEYWORDS,
}

ARCHETYPE_KEYWORDS_BY_GENRE = {
    "fantasy": FANTASY_ARCHETYPE_KEYWORDS,
    "scifi": SCIFI_ARCHETYPE_KEYWORDS,
    "modern": MODERN_ARCHETYPE_KEYWORDS,
    "horror": MODERN_ARCHETYPE_KEYWORDS,
}

# Default names by genre and origin
DEFAULT_NAMES = {
    "fantasy": {
        "human": "Roland", "elf": "Aelindra", "dwarf": "Thorin", "halfling": "Pippin",
    },
    "scifi": {
        "human": "Marcus", "android": "ARIA-7", "alien": "Zyx'thel", "cyborg": "Chrome",
    },
    "modern": {
        "urban": "Jake", "rural": "Emma", "military": "Cole", "academic": "Sarah",
    },
    "horror": {
        "urban": "Michael", "rural": "Beth", "military": "Frank", "academic": "Eleanor",
    },
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
    Supports all genres (fantasy, scifi, modern, horror).
    """

    def __init__(self, gemini_client=None, genre: str = "fantasy"):
        """
        Initialize the concept generator.

        Args:
            gemini_client: Optional Gemini client for AI parsing
            genre: Genre for character generation (fantasy, scifi, modern, horror)
        """
        self.gemini_client = gemini_client
        self.genre = genre
        self.genre_config = get_genre(genre)

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

        # Get genre-specific keywords
        origin_keywords = ORIGIN_KEYWORDS_BY_GENRE.get(self.genre, FANTASY_ORIGIN_KEYWORDS)
        archetype_keywords = ARCHETYPE_KEYWORDS_BY_GENRE.get(self.genre, FANTASY_ARCHETYPE_KEYWORDS)

        # Get available origins and archetypes for this genre
        origins = get_origins_for_genre(self.genre)
        archetypes = get_archetypes_for_genre(self.genre)

        # Default to first available
        detected_origin = origins[0].id if origins else "human"
        detected_archetype = archetypes[0].id if archetypes else "fighter"

        # Detect origin
        for origin_id, keywords in origin_keywords.items():
            if any(kw in concept_lower for kw in keywords):
                detected_origin = origin_id
                break

        # Detect archetype
        for archetype_id, keywords in archetype_keywords.items():
            if any(kw in concept_lower for kw in keywords):
                detected_archetype = archetype_id
                break

        # Get archetype data for primary ability
        archetype_data = get_archetype(detected_archetype, self.genre)
        primary_ability = archetype_data.primary_ability if archetype_data else "strength"
        secondary_ability = "constitution"  # Safe default

        # Detect ability emphasis
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
                # Check it's not an origin/archetype keyword
                all_keywords = []
                for kws in origin_keywords.values():
                    all_keywords.extend(kws)
                for kws in archetype_keywords.values():
                    all_keywords.extend(kws)
                if word.lower() not in all_keywords:
                    name = word
                    break

        if not name:
            # Generate a default name based on genre and origin
            genre_names = DEFAULT_NAMES.get(self.genre, DEFAULT_NAMES["fantasy"])
            name = genre_names.get(detected_origin, "Alex")

        # Suggest skills based on archetype
        skills = archetype_data.skill_choices[:archetype_data.num_skill_choices] if archetype_data else []

        return {
            "name": name,
            "origin": detected_origin,
            "archetype": detected_archetype,
            "primary_ability": primary_ability,
            "secondary_ability": secondary_ability,
            "skills": skills,
            "personality_note": concept,
        }

    def _build_character(self, parsed: Dict[str, Any], player_id: str) -> CharacterSheet:
        """Build a CharacterSheet from parsed concept data."""
        # Get origin and archetype data for this genre
        origin_id = parsed.get("origin") or parsed.get("race", "human")
        archetype_id = parsed.get("archetype") or parsed.get("class", "fighter")

        origin_data = get_origin(origin_id, self.genre)
        archetype_data = get_archetype(archetype_id, self.genre)

        if not origin_data or not archetype_data:
            # Fallback to defaults
            origins = get_origins_for_genre(self.genre)
            archetypes = get_archetypes_for_genre(self.genre)
            origin_data = origins[0] if origins else None
            archetype_data = archetypes[0] if archetypes else None

        # Generate ability scores optimized for archetype
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

        # Apply origin bonuses
        if origin_data:
            for ability, bonus in origin_data.ability_bonuses.items():
                base_scores[ability] = min(20, base_scores[ability] + bonus)

        abilities = AbilityScores(**base_scores)

        # Calculate derived stats
        con_mod = abilities.get_modifier(AbilityName.CON)
        dex_mod = abilities.get_modifier(AbilityName.DEX)
        hp = get_starting_hp(archetype_id, con_mod, self.genre)

        # Determine AC and equipment based on archetype and genre
        base_ac, equipment = self._get_starting_equipment(archetype_id, dex_mod)

        # Power/spell setup for casters
        power_slots = {}
        cantrips = []
        abilities_known = []
        if archetype_data and archetype_data.has_powers:
            power_slots = {1: 2}
            # Get starting abilities from the abilities module
            from ..models.abilities import get_cantrips_for_archetype, get_abilities_for_archetype, AbilityType
            archetype_cantrips = get_cantrips_for_archetype(archetype_id, self.genre)
            archetype_abilities = [
                a for a in get_abilities_for_archetype(archetype_id, self.genre)
                if a.ability_type.value.startswith("level_")
            ]
            cantrips = [c.id for c in archetype_cantrips[:2]]
            abilities_known = [a.id for a in archetype_abilities[:2]]

        # Get skills (limit to archetype available)
        skills = parsed.get("skills", [])
        if archetype_data:
            available = [s.lower() for s in archetype_data.skill_choices]
            skills = [s for s in skills if s.lower() in available]
            # Fill remaining slots if needed
            while len(skills) < archetype_data.num_skill_choices:
                for s in available:
                    if s not in skills:
                        skills.append(s)
                        break
                if len(skills) >= archetype_data.num_skill_choices:
                    break
            skills = skills[:archetype_data.num_skill_choices]

        return CharacterSheet(
            character_id=str(uuid.uuid4()),
            name=parsed["name"],
            player_id=player_id,
            genre=self.genre,
            origin=origin_id,
            archetype=archetype_id,
            level=1,
            ability_scores=abilities,
            max_hit_points=hp,
            current_hit_points=hp,
            armor_class=base_ac,
            speed=origin_data.speed if origin_data else 30,
            skill_proficiencies=skills,
            saving_throw_proficiencies=archetype_data.saving_throw_proficiencies if archetype_data else [],
            armor_proficiencies=archetype_data.armor_proficiencies if archetype_data else [],
            weapon_proficiencies=archetype_data.weapon_proficiencies if archetype_data else [],
            equipment=equipment,
            power_slots_max=power_slots,
            cantrips_known=cantrips,
            abilities_known=abilities_known,
            features=archetype_data.features_by_level.get(1, []) if archetype_data else [],
            rules_visibility="storyteller",  # Concept mode defaults to storyteller
        )

    def _get_starting_equipment(self, archetype_id: str, dex_mod: int) -> tuple:
        """Get starting equipment based on genre and archetype."""
        # Fantasy equipment
        fantasy_equipment = {
            "fighter": (16, ["chain mail", "longsword", "shield"]),
            "rogue": (11 + dex_mod, ["leather armor", "rapier", "shortbow"]),
            "cleric": (14 + min(dex_mod, 2) + 2, ["scale mail", "mace", "shield", "holy symbol"]),
            "wizard": (10 + dex_mod, ["quarterstaff", "spellbook", "arcane focus"]),
        }

        # Sci-fi equipment
        scifi_equipment = {
            "soldier": (16, ["combat armor", "assault rifle", "sidearm"]),
            "hacker": (11 + dex_mod, ["light vest", "pistol", "neural interface"]),
            "pilot": (12 + dex_mod, ["flight suit", "pistol", "toolkit"]),
            "medic": (12 + dex_mod, ["medic vest", "pistol", "medkit"]),
        }

        # Modern equipment
        modern_equipment = {
            "detective": (10 + dex_mod, ["concealed vest", "pistol", "badge"]),
            "soldier": (14, ["tactical vest", "rifle", "sidearm"]),
            "doctor": (10, ["lab coat", "medical bag", "phone"]),
            "engineer": (10, ["work clothes", "toolkit", "laptop"]),
        }

        genre_equipment = {
            "fantasy": fantasy_equipment,
            "scifi": scifi_equipment,
            "modern": modern_equipment,
            "horror": modern_equipment,
        }

        equipment_map = genre_equipment.get(self.genre, fantasy_equipment)
        return equipment_map.get(archetype_id, (10 + dex_mod, ["basic gear"]))
