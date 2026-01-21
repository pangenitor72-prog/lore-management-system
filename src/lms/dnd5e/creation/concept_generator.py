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

    MANTLE Translation Layer:
    When world_character_options are provided, the generator uses ONLY the
    world-specific vocabulary (e.g., "Netrunner" not "rogue", "Mutant" not "elf").
    The base_type field maps world terms to D&D mechanics internally.
    """

    def __init__(self, gemini_client=None, genre: str = "fantasy", world_character_options: Dict[str, Any] = None):
        """
        Initialize the concept generator.

        Args:
            gemini_client: Optional Gemini client for AI parsing
            genre: Genre for character generation (fantasy, scifi, modern, horror)
            world_character_options: Optional dict with 'origins' and 'archetypes' lists
                                    from the world's custom character options (MANTLE layer)
        """
        self.gemini_client = gemini_client
        self.genre = genre
        self.genre_config = get_genre(genre)
        self.world_options = world_character_options or {}

        # Build MANTLE keyword mappings if world options provided
        self._custom_origin_keywords = {}
        self._custom_archetype_keywords = {}
        if self.world_options:
            self._build_mantle_keywords()

    def _build_mantle_keywords(self):
        """
        Build keyword mappings from world-specific character options.

        Extracts keywords from option names and descriptions to enable
        natural language matching against MANTLE vocabulary.
        """
        stop_words = {
            'the', 'and', 'for', 'with', 'who', 'that', 'this', 'from', 'have', 'has',
            'are', 'was', 'were', 'been', 'being', 'their', 'them', 'they', 'your',
            'can', 'will', 'would', 'could', 'should', 'may', 'might', 'must'
        }

        def extract_keywords(option: Dict[str, Any]) -> List[str]:
            """Extract searchable keywords from an option's name and description."""
            words = []

            # Add name words
            name = option.get('name', option.get('display_name', ''))
            if name:
                words.extend(name.lower().split())

            # Add description words (filtered)
            desc = option.get('description', '')
            if desc:
                desc_words = re.sub(r'[^a-z\s]', '', desc.lower()).split()
                words.extend(w for w in desc_words if len(w) >= 3 and w not in stop_words)

            # Add base_type for fallback matching
            base_type = option.get('base_type', '')
            if base_type:
                words.append(base_type.lower())

            # Add id as keyword
            option_id = option.get('id', '')
            if option_id:
                words.extend(option_id.lower().replace('_', ' ').split())

            return list(set(words))

        # Build origin keywords
        for origin in self.world_options.get('origins', []):
            origin_id = origin.get('id', '')
            if origin_id:
                self._custom_origin_keywords[origin_id] = extract_keywords(origin)

        # Build archetype keywords
        for archetype in self.world_options.get('archetypes', []):
            archetype_id = archetype.get('id', '')
            if archetype_id:
                self._custom_archetype_keywords[archetype_id] = extract_keywords(archetype)

        logger.debug(f"MANTLE keywords built: {len(self._custom_origin_keywords)} origins, "
                    f"{len(self._custom_archetype_keywords)} archetypes")

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
        """Parse concept using AI (Gemini) with MANTLE vocabulary when available."""

        # Build prompt based on whether we have world-specific options
        if self._custom_origin_keywords and self._custom_archetype_keywords:
            # MANTLE Mode: Use world-specific vocabulary ONLY
            prompt = self._build_mantle_ai_prompt(concept)
        else:
            # Fallback to genre-based D&D terms
            prompt = self._build_generic_ai_prompt(concept)

        # Call Gemini
        response = await self.gemini_client.generate_content(prompt)

        # Parse JSON from response
        import json
        text = response.text
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("Could not parse AI response as JSON")

    def _build_mantle_ai_prompt(self, concept: str) -> str:
        """
        Build AI prompt using MANTLE vocabulary - world-specific options ONLY.

        The AI is STRICTLY FORBIDDEN from using generic D&D terms.
        """
        # Build origin list from world options
        origins = self.world_options.get('origins', [])
        origin_list = "\n".join([
            f"  - {o.get('id')}: {o.get('name')} - {o.get('description', '')}"
            for o in origins
        ])

        # Build archetype list from world options
        archetypes = self.world_options.get('archetypes', [])
        archetype_list = "\n".join([
            f"  - {a.get('id')}: {a.get('name')} - {a.get('description', '')}"
            for a in archetypes
        ])

        return f"""Parse this character concept using ONLY the world-specific options below.

STRICT RULES:
- You MUST use ONLY the origin and archetype IDs listed below
- DO NOT use generic D&D terms like "human", "elf", "dwarf", "fighter", "rogue", "cleric", "wizard"
- Match the player's description to the CLOSEST world-specific option
- If uncertain, pick the option that best matches the character's described role/style

CHARACTER CONCEPT: "{concept}"

AVAILABLE ORIGINS (use the ID value):
{origin_list}

AVAILABLE ARCHETYPES (use the ID value):
{archetype_list}

Extract and return as JSON:
{{
    "name": "Character Name (if mentioned, or suggest appropriate one)",
    "origin": "origin_id_from_list_above",
    "archetype": "archetype_id_from_list_above",
    "primary_ability": "strength|dexterity|constitution|intelligence|wisdom|charisma",
    "secondary_ability": "ability_name",
    "skills": ["skill1", "skill2"],
    "personality_note": "brief personality description"
}}

Return ONLY valid JSON. Use ONLY the IDs from the lists above."""

    def _build_generic_ai_prompt(self, concept: str) -> str:
        """Build AI prompt using standard genre-based terms (fallback)."""
        origin_keywords = ORIGIN_KEYWORDS_BY_GENRE.get(self.genre, FANTASY_ORIGIN_KEYWORDS)
        archetype_keywords = ARCHETYPE_KEYWORDS_BY_GENRE.get(self.genre, FANTASY_ARCHETYPE_KEYWORDS)

        origins_str = ", ".join(origin_keywords.keys())
        archetypes_str = ", ".join(archetype_keywords.keys())

        return f"""Parse this character concept into structured data for a {self.genre} setting.

Character Concept: "{concept}"

Extract:
1. Name (if mentioned, otherwise suggest one)
2. Origin ({origins_str})
3. Archetype ({archetypes_str})
4. Primary ability (strength, dexterity, constitution, intelligence, wisdom, or charisma)
5. Secondary ability
6. Two suggested skills appropriate for this character

Return as JSON:
{{
    "name": "Character Name",
    "origin": "origin_name",
    "archetype": "archetype_name",
    "primary_ability": "ability_name",
    "secondary_ability": "ability_name",
    "skills": ["skill1", "skill2"],
    "personality_note": "brief personality description"
}}

Only use the origins and archetypes listed. Return valid JSON only."""

    def _keyword_parse_concept(self, concept: str) -> Dict[str, Any]:
        """Parse concept using keyword matching (fallback), with MANTLE support."""
        concept_lower = concept.lower()

        # Use MANTLE vocabulary if world options are available
        if self._custom_origin_keywords and self._custom_archetype_keywords:
            return self._mantle_keyword_parse(concept_lower, concept)

        # Otherwise fall back to genre-specific keywords
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

    def _mantle_keyword_parse(self, concept_lower: str, original_concept: str) -> Dict[str, Any]:
        """
        MANTLE keyword parsing - match concept to world-specific options.

        Uses keyword scoring to find the best match for origin and archetype
        from the world's custom character options.
        """
        # Score each origin by keyword matches
        origin_scores = {}
        for origin_id, keywords in self._custom_origin_keywords.items():
            score = sum(1 for kw in keywords if kw in concept_lower)
            if score > 0:
                origin_scores[origin_id] = score

        # Score each archetype by keyword matches
        archetype_scores = {}
        for archetype_id, keywords in self._custom_archetype_keywords.items():
            score = sum(1 for kw in keywords if kw in concept_lower)
            if score > 0:
                archetype_scores[archetype_id] = score

        # Get best matches or defaults
        origins = self.world_options.get('origins', [])
        archetypes = self.world_options.get('archetypes', [])

        if origin_scores:
            detected_origin = max(origin_scores.keys(), key=lambda k: origin_scores[k])
        else:
            # Fallback: if player used a D&D term, map via base_type
            detected_origin = self._fallback_origin_from_dnd_term(concept_lower, origins)

        if archetype_scores:
            detected_archetype = max(archetype_scores.keys(), key=lambda k: archetype_scores[k])
        else:
            # Fallback: if player used a D&D term, map via base_type
            detected_archetype = self._fallback_archetype_from_dnd_term(concept_lower, archetypes)

        # Get base_type for mechanics lookup
        origin_base_type = "human"
        archetype_base_type = "fighter"
        for o in origins:
            if o.get('id') == detected_origin:
                origin_base_type = o.get('base_type', 'human')
                break
        for a in archetypes:
            if a.get('id') == detected_archetype:
                archetype_base_type = a.get('base_type', 'fighter')
                break

        # Get archetype data using base_type for mechanics
        archetype_data = get_archetype(archetype_base_type, self.genre)
        primary_ability = archetype_data.primary_ability if archetype_data else "strength"
        secondary_ability = "constitution"

        # Detect ability emphasis from concept
        for ability, keywords in ABILITY_KEYWORDS.items():
            if any(kw in concept_lower for kw in keywords):
                if ability != primary_ability:
                    secondary_ability = ability
                    break

        # Extract name from concept
        words = original_concept.split()
        common_words = {"a", "an", "the", "who", "is", "was", "with", "and", "or", "but", "from"}
        name = None
        for word in words:
            if len(word) > 1 and word[0].isupper() and word.lower() not in common_words:
                # Exclude keywords from all options
                all_keywords = set()
                for kws in self._custom_origin_keywords.values():
                    all_keywords.update(kws)
                for kws in self._custom_archetype_keywords.values():
                    all_keywords.update(kws)
                if word.lower() not in all_keywords:
                    name = word
                    break

        if not name:
            name = "Alex"  # Default name for MANTLE worlds

        # Get skills from archetype (using base_type for mechanics)
        skills = archetype_data.skill_choices[:archetype_data.num_skill_choices] if archetype_data else []

        logger.debug(f"MANTLE parse: '{original_concept}' -> origin={detected_origin}, archetype={detected_archetype}")

        return {
            "name": name,
            "origin": detected_origin,
            "archetype": detected_archetype,
            "origin_base_type": origin_base_type,
            "archetype_base_type": archetype_base_type,
            "primary_ability": primary_ability,
            "secondary_ability": secondary_ability,
            "skills": skills,
            "personality_note": original_concept,
        }

    def _fallback_origin_from_dnd_term(self, concept_lower: str, origins: List[Dict]) -> str:
        """Map D&D origin terms to world-specific origins via base_type."""
        dnd_origins = ["human", "elf", "dwarf", "halfling", "gnome", "half-elf", "half-orc", "tiefling"]

        for dnd_term in dnd_origins:
            if dnd_term in concept_lower:
                # Find a world origin with matching base_type
                for o in origins:
                    if o.get('base_type', '').lower() == dnd_term:
                        return o.get('id')
                break

        # Default to first origin
        return origins[0].get('id') if origins else "human"

    def _fallback_archetype_from_dnd_term(self, concept_lower: str, archetypes: List[Dict]) -> str:
        """Map D&D archetype terms to world-specific archetypes via base_type."""
        dnd_classes = ["fighter", "rogue", "cleric", "wizard", "barbarian", "bard", "druid",
                       "monk", "paladin", "ranger", "sorcerer", "warlock"]

        for dnd_term in dnd_classes:
            if dnd_term in concept_lower:
                # Find a world archetype with matching base_type
                for a in archetypes:
                    if a.get('base_type', '').lower() == dnd_term:
                        return a.get('id')
                break

        # Default to first archetype
        return archetypes[0].get('id') if archetypes else "fighter"

    def _build_character(self, parsed: Dict[str, Any], player_id: str) -> CharacterSheet:
        """Build a CharacterSheet from parsed concept data."""
        # Get origin and archetype IDs (MANTLE IDs if using world options)
        origin_id = parsed.get("origin") or parsed.get("race", "human")
        archetype_id = parsed.get("archetype") or parsed.get("class", "fighter")

        # For MANTLE: use base_type for mechanics lookup, but keep MANTLE ID in character sheet
        # This lets us show "Netrunner" to the player while using "rogue" mechanics
        origin_lookup_id = parsed.get("origin_base_type", origin_id)
        archetype_lookup_id = parsed.get("archetype_base_type", archetype_id)

        origin_data = get_origin(origin_lookup_id, self.genre)
        archetype_data = get_archetype(archetype_lookup_id, self.genre)

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
        hp = get_starting_hp(archetype_lookup_id, con_mod, self.genre)

        # Determine AC and equipment based on archetype and genre (use base_type for mechanics)
        base_ac, equipment = self._get_starting_equipment(archetype_lookup_id, dex_mod)

        # Power/spell setup for casters
        power_slots = {}
        cantrips = []
        abilities_known = []
        if archetype_data and archetype_data.has_powers:
            power_slots = {1: 2}

            # For fantasy genre, use SRD spells for proper class-based spells
            # Use archetype_lookup_id (base_type) for spell list lookup
            if self.genre == "fantasy":
                from ..data.loader import get_srd_loader
                loader = get_srd_loader()

                # Get cantrips and level 1 spells for this class (use base_type for lookup)
                available_cantrips = loader.get_cantrips_for_class(archetype_lookup_id)
                available_spells = [s for s in loader.get_spells_for_class(archetype_lookup_id) if s.get("level") == 1]

                # Calculate number of prepared spells
                num_cantrips = archetype_data.cantrips_known
                num_prepared = self._get_prepared_spell_count(archetype_data, abilities)

                # Select first N cantrips and spells (auto-selection for concept mode)
                cantrips = [s.get("id", s.get("name", "").lower().replace(" ", "_"))
                           for s in available_cantrips[:num_cantrips]]
                abilities_known = [s.get("id", s.get("name", "").lower().replace(" ", "_"))
                                  for s in available_spells[:num_prepared]]
            else:
                # For non-fantasy genres, use the abilities module (use base_type for lookup)
                from ..models.abilities import get_cantrips_for_archetype, get_abilities_for_archetype, AbilityType
                archetype_cantrips = get_cantrips_for_archetype(archetype_lookup_id, self.genre)
                archetype_abilities = [
                    a for a in get_abilities_for_archetype(archetype_lookup_id, self.genre)
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
            rules_visibility="guided",  # Concept mode defaults to guided for progressive reveal
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

    def _get_prepared_spell_count(self, archetype_data, abilities: AbilityScores) -> int:
        """Calculate number of prepared spells based on archetype and ability modifier."""
        if not archetype_data:
            return 2  # Default

        archetype_id = archetype_data.id.lower()

        # Cleric and Druid prepare WIS mod + level spells
        if archetype_id in ["cleric", "druid"]:
            wis_mod = abilities.get_modifier(AbilityName.WIS)
            return max(1, wis_mod + 1)  # +1 for level 1

        # Wizard prepares INT mod + level spells
        if archetype_id == "wizard":
            int_mod = abilities.get_modifier(AbilityName.INT)
            return max(1, int_mod + 1)

        # Paladin prepares CHA mod + half level spells (starts at level 2)
        if archetype_id == "paladin":
            return 1  # Minimal at level 1

        # Bard, Sorcerer, Warlock - spells known (not prepared)
        if archetype_id in ["bard", "sorcerer", "warlock"]:
            return 2  # Default known spells at level 1

        # Ranger - starts at level 2, but give 1 for concept
        if archetype_id == "ranger":
            return 1

        return 2  # Default
