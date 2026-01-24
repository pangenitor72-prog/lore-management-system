# src/lms/api/game_routes.py
"""
Game Session API Routes

Endpoints for:
- Creating and managing game sessions
- Processing player actions through the DM
- Generating worlds from seed prompts
"""

from __future__ import annotations

import os
import re
import uuid
import json
import logging
import asyncio
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, status, Depends, File, UploadFile, Query
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.api.dependencies import get_neo4j_db
from src.mantle.agents.query_agent import QueryAgent
from src.mantle.agents.auditor_agent import AuditorAgent
from src.mantle.agents.lore_parsing_agent import LoreParsingAgent
from src.mantle.guardrails.token_budget import TokenTracker, TokenBudget, BudgetExceeded, RateLimitExceeded, estimate_tokens
from src.mantle.guardrails.circuit_breaker import get_circuit_breaker, CircuitOpen

# D&D Rules Integration
from src.mantle.api.dnd_routes import _characters, CharacterSheet
from src.mantle.dnd5e.engine.checks import CheckEngine, SKILL_TO_ABILITY
from src.mantle.dnd5e.engine.combat_resolver import CombatResolver
from src.mantle.dnd5e.presentation.visibility import VisibilityFilter
from src.mantle.dnd5e.creation.modes import RulesVisibility
from src.mantle.dnd5e.genre.config import get_genre, GENRES
from src.mantle.dnd5e.models.origins import get_origins_for_genre
from src.mantle.dnd5e.models.archetypes import get_archetypes_for_genre

# World Integrity Check
from src.mantle.engine.world_integrity import (
    WorldNotReadyError,
    require_valid_world,
    validate_world_before_session,
)

# Game State - Single source of truth for session state
from src.mantle.engine.game_state import GameState, CombatantState, Item
from src.mantle.engine.game_events import get_starting_inventory

# Character schema for Neo4j persistence
from src.mantle.db.character_schema import CharacterSchemaDB, OriginSchema, ArchetypeSchema

# Arc Engine for narrative pacing
try:
    from src.mantle.arc.arc_engine import ArcEngine
    ARC_ENGINE_AVAILABLE = True
except ImportError:
    ARC_ENGINE_AVAILABLE = False
    ArcEngine = None

# Context-aware action suggestions
from src.mantle.suggestions.action_engine import generate_action_suggestions, PlayerMode

logger = logging.getLogger(__name__)

from src.mantle.services.broadcaster import broadcaster
from src.mantle.services.audit_log import AuditLogger

# Shared lore parsing agent for extracting entities from gameplay
_lore_parser: Optional[LoreParsingAgent] = None


def get_lore_parser() -> LoreParsingAgent:
    """Get or create the shared lore parsing agent."""
    global _lore_parser
    if _lore_parser is None:
        _lore_parser = LoreParsingAgent()
    return _lore_parser


def get_app_version() -> str:
    """Get the current app version from deployed_version.txt."""
    try:
        version_file = Path(__file__).parent.parent.parent.parent / "data" / "deployed_version.txt"
        if version_file.exists():
            return version_file.read_text().strip().split('\n')[0]
    except Exception:
        pass
    return "unknown"


async def extract_and_store_gameplay_lore(
    narrative: str,
    session_id: str,
    db: Optional[Neo4jDatabase],
    world_id: Optional[str] = None,
    curated_world_id: Optional[str] = None,
    genre: Optional[str] = None,
    character_name: Optional[str] = None,
) -> None:
    """
    Extract entities from gameplay narrative and store them in Neo4j.

    This runs asynchronously after the narrative is returned to the player,
    so it doesn't slow down the gameplay experience.

    Args:
        narrative: The narrative text to extract entities from
        session_id: The session ID for source tracking
        db: Neo4j database instance
        world_id: The session-scoped world ID (for entity isolation)
        curated_world_id: The original curated world ID (e.g., "eldoria") for filtering
        genre: The genre(s) to tag entities with
        character_name: The player's character name for session tracking
    """
    if not db:
        logger.debug("No database available for lore extraction")
        return

    if len(narrative) < 100:
        # Too short to contain meaningful entities
        return

    try:
        parser = get_lore_parser()

        # Parse the narrative for entities, associating with the session's world
        result = await parser.parse_and_store(
            text=narrative,
            db=db,
            source_name=f"session:{session_id}",
            world_id=world_id,
            curated_world_id=curated_world_id,
            genre=genre,
            session_id=session_id,
        )

        if result.entities_stored > 0:
            logger.info(
                f"[LORE] Extracted {result.entities_stored} entities from session {session_id} "
                f"(world: {world_id or 'none'}, {result.characters_with_ocean} with OCEAN profiles)"
            )
    except Exception as e:
        # Don't let extraction failures affect gameplay
        logger.warning(f"[LORE] Entity extraction failed for session {session_id}: {e}")

# Gemini configuration - same model as LoreParsingAgent
GEMINI_MODEL = "gemini-2.0-flash-exp"  # This works for lore parsing


def get_gemini_model():
    """Get a fresh Gemini model instance for each request."""
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    logger.info(f"Gemini model created: {GEMINI_MODEL}")
    return model


# ============================================================
# AI CHARACTER OPTIONS GENERATION
# ============================================================
# Generate setting-appropriate origins and archetypes from lore

# Base D&D types that custom options can map to
BASE_ORIGINS = ["human", "elf", "dwarf", "halfling", "gnome", "half-orc", "tiefling", "dragonborn"]
BASE_ARCHETYPES = ["fighter", "rogue", "wizard", "cleric", "ranger", "barbarian", "paladin", "bard", "monk", "warlock", "sorcerer", "druid"]


async def generate_character_options_from_lore(
    lore_content: str,
    world_name: str,
    genre: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Use AI to generate setting-appropriate character origins and archetypes
    based on the world's lore content.

    Each generated option maps to a base D&D type for mechanics.

    Args:
        lore_content: The full lore text for the world
        world_name: Name of the world
        genre: Primary genre (fantasy, scifi, modern, horror, etc.)
        description: Brief description of the world

    Returns:
        Dict with 'origins' and 'archetypes' lists, each containing:
        - id: unique identifier
        - name: display name
        - description: short description
        - base_type: base D&D type for mechanics
    """
    model = get_gemini_model()
    if not model:
        logger.warning("No Gemini API key - returning empty character options")
        return {"origins": [], "archetypes": [], "ai_generated": False}

    # Truncate lore for prompt if too long
    lore_excerpt = lore_content[:8000] if len(lore_content) > 8000 else lore_content

    prompt = f'''You are designing character creation options for a tabletop RPG set in "{world_name}".

WORLD GENRE: {genre}
WORLD DESCRIPTION: {description}

LORE EXCERPT:
{lore_excerpt}

Based on this world's lore, generate COMPREHENSIVE character options with full details for character creation.

BASE ORIGINS (D&D races for mechanics - player sees setting-specific name):
{", ".join(BASE_ORIGINS)}

BASE ARCHETYPES (D&D classes for mechanics - player sees setting-specific name):
{", ".join(BASE_ARCHETYPES)}

D&D SKILLS (for proficiency choices):
Athletics, Acrobatics, Sleight of Hand, Stealth, Arcana, History, Investigation, Nature, Religion, Animal Handling, Insight, Medicine, Perception, Survival, Deception, Intimidation, Performance, Persuasion

IMPORTANT RULES:
1. Origins represent RACES or PEOPLES in fantasy; BACKGROUNDS in modern settings
2. Archetypes represent CLASSES or PROFESSIONS that fit this setting
3. Do NOT include elves/dwarves in non-fantasy settings - use human backgrounds instead
4. For modern/scifi/cyberpunk/horror: ALL origins should map to base_type "human"
5. Generate 4-6 origins and 4-6 archetypes with FULL mechanical details
6. Skills should be setting-flavored names but map to D&D skills (e.g., "Streetwise" -> Insight)
7. Equipment should fit the setting (no swords in cyberpunk unless appropriate)
8. Abilities/Features should be unique to each archetype

Output valid JSON only, no markdown:
{{
  "origins": [
    {{
      "id": "origin_id",
      "name": "Display Name",
      "description": "One sentence flavor description",
      "base_type": "human",
      "ability_bonuses": {{"strength": 1, "dexterity": 2}},
      "skill_proficiencies": ["Stealth", "Perception"],
      "traits": ["Trait name: Brief mechanical benefit"],
      "languages": ["Common", "Setting-specific language"]
    }}
  ],
  "archetypes": [
    {{
      "id": "archetype_id",
      "name": "Display Name",
      "description": "One sentence flavor description",
      "base_type": "fighter",
      "hit_die": "d10",
      "primary_ability": "Strength",
      "saving_throws": ["Strength", "Constitution"],
      "skill_choices": ["Athletics", "Intimidation", "Perception", "Survival"],
      "num_skill_choices": 2,
      "armor_proficiencies": ["Light armor", "Medium armor", "Shields"],
      "weapon_proficiencies": ["Simple weapons", "Martial weapons"],
      "starting_equipment": ["Leather armor", "Two daggers", "Thieves tools"],
      "features": [
        {{"name": "Feature Name", "description": "What it does mechanically"}}
      ]
    }}
  ],
  "setting_skills": [
    {{"id": "streetwise", "name": "Streetwise", "base_skill": "Insight", "description": "Knowledge of the urban underground"}}
  ]
}}'''

    try:
        response = await run_in_threadpool(
            lambda: model.generate_content(prompt)
        )

        # Extract JSON from response
        text = response.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            elif "```" in text:
                text = text.split("```")[0]

        result = json.loads(text)

        # Validate the structure
        origins = result.get("origins", [])
        archetypes = result.get("archetypes", [])
        setting_skills = result.get("setting_skills", [])

        # Ensure base_types are valid and add defaults for missing fields
        for origin in origins:
            if origin.get("base_type") not in BASE_ORIGINS:
                origin["base_type"] = "human"
            # Ensure required fields have defaults
            origin.setdefault("ability_bonuses", {})
            origin.setdefault("skill_proficiencies", [])
            origin.setdefault("traits", [])
            origin.setdefault("languages", ["Common"])

        for archetype in archetypes:
            if archetype.get("base_type") not in BASE_ARCHETYPES:
                archetype["base_type"] = "fighter"
            # Ensure required fields have defaults
            archetype.setdefault("hit_die", "d8")
            archetype.setdefault("primary_ability", "Strength")
            archetype.setdefault("saving_throws", [])
            archetype.setdefault("skill_choices", [])
            archetype.setdefault("num_skill_choices", 2)
            archetype.setdefault("armor_proficiencies", [])
            archetype.setdefault("weapon_proficiencies", [])
            archetype.setdefault("starting_equipment", [])
            archetype.setdefault("features", [])

        logger.info(
            f"Generated character options for {world_name}: "
            f"{len(origins)} origins, {len(archetypes)} archetypes, {len(setting_skills)} skills"
        )

        return {
            "origins": origins,
            "archetypes": archetypes,
            "setting_skills": setting_skills,
            "ai_generated": True,
            "admin_reviewed": False
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return {"origins": [], "archetypes": [], "ai_generated": False}
    except Exception as e:
        logger.error(f"AI character options generation failed: {e}")
        return {"origins": [], "archetypes": [], "ai_generated": False}


# NOTE: generate_pending_mappings_from_lore was removed - use generate_character_options_from_lore instead
# Character options are now directly editable without a separate approval workflow.


async def _removed_generate_pending_mappings_from_lore(
    world_id: str,
    lore_content: str,
    world_name: str,
    genre: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    MANTLE Ingestion: Generate PENDING mappings that require admin approval.

    Unlike generate_character_options_from_lore, this creates PendingMapping
    entries with confidence scores and source snippets. These go through
    the approval workflow before becoming active character options.

    Args:
        world_id: Unique identifier for the world
        lore_content: The full lore text for the world
        world_name: Name of the world
        genre: Primary genre
        description: Brief description

    Returns:
        Dict with 'pending_count', 'mappings' list
    """
    model = get_gemini_model()
    if not model:
        logger.warning("No Gemini API key - cannot generate pending mappings")
        return {"pending_count": 0, "mappings": []}

    # Truncate lore for prompt if too long
    lore_excerpt = lore_content[:8000] if len(lore_content) > 8000 else lore_content

    prompt = f'''You are the MANTLE Mapping Agent. Your goal is to map lore prose to D&D 5e mechanical bases for character creation.

WORLD: "{world_name}"
GENRE: {genre}
DESCRIPTION: {description}

LORE TEXT TO ANALYZE:
{lore_excerpt}

For each character type you identify, follow this structured process:

1. EXTRACT: Identify the core archetype or origin from the text. Look for:
   - Character roles/professions (archetypes) - e.g., "Void-Knight", "Netrunner", "Gunslinger"
   - Character backgrounds/peoples (origins) - e.g., "Mutant", "Corporate Exile", "Frontier Settler"

2. SOURCE: Quote the specific text passage where this appears (max 100 words).

3. PROPOSE: Suggest the best D&D 5e mechanical fit from these options:
   - For ORIGINS (backgrounds/peoples): {", ".join(BASE_ORIGINS)}
   - For ARCHETYPES (roles/classes): {", ".join(BASE_ARCHETYPES)}

4. JUSTIFY: Provide a 1-sentence explanation focusing on MECHANICAL SYNERGY.
   Example: "I chose Paladin because the text emphasizes heavy armor and divine oaths."
   Example: "I chose Rogue because the role focuses on stealth, hacking, and precision skills."

5. CONFIDENCE: Rate your confidence from 0.1 to 1.0:
   - 0.8-1.0 = Clear match (text explicitly describes mechanics that align)
   - 0.5-0.7 = Reasonable inference (role/style suggests this mapping)
   - 0.1-0.4 = Speculation (minimal textual evidence)

CRITICAL RULES:
- For modern/scifi/cyberpunk/horror/western genres: ALL origins must map to "human" (they are backgrounds, not races)
- Extract what ACTUALLY appears in the lore, not generic fantasy options
- Be conservative - only extract clearly defined character types

Output valid JSON only:
{{
  "extractions": [
    {{
      "mapping_type": "origin|archetype",
      "lore_name": "Name from the lore",
      "source_snippet": "Quote from lore...",
      "mechanical_base": "human|fighter|etc",
      "confidence": 0.85,
      "justification": "Mechanical synergy explanation"
    }}
  ]
}}'''

    try:
        response = await run_in_threadpool(
            lambda: model.generate_content(prompt)
        )

        # Extract JSON from response
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            elif "```" in text:
                text = text.split("```")[0]

        result = json.loads(text)
        extractions = result.get("extractions", [])

        # Convert extractions to pending mappings
        created_mappings = []
        timestamp = datetime.now(timezone.utc).isoformat()

        for ext in extractions:
            mapping_id = f"{world_id}_{ext.get('mapping_type', 'unknown')}_{ext.get('lore_name', '').lower().replace(' ', '_')}"

            # Validate and fix base type
            mapping_type = ext.get("mapping_type", "archetype")
            mechanical_base = ext.get("mechanical_base", "human" if mapping_type == "origin" else "fighter")

            if mapping_type == "origin" and mechanical_base not in BASE_ORIGINS:
                mechanical_base = "human"
            elif mapping_type == "archetype" and mechanical_base not in BASE_ARCHETYPES:
                mechanical_base = "fighter"

            mapping = {
                "id": mapping_id,
                "world_id": world_id,
                "mapping_type": mapping_type,
                "lore_name": ext.get("lore_name", "Unknown"),
                "lore_description": "",
                "source_snippet": ext.get("source_snippet", "")[:500],  # Limit snippet length
                "mechanical_base": mechanical_base,
                "ai_justification": ext.get("justification", ""),
                "confidence_score": min(1.0, max(0.0, float(ext.get("confidence", 0.5)))),
                "status": "pending",
                "admin_notes": "",
                "created_at": timestamp,
                "reviewed_at": None
            }

            # Store in global pending mappings
            PENDING_MAPPINGS[mapping_id] = mapping
            created_mappings.append(mapping)

        logger.info(f"Generated {len(created_mappings)} pending mappings for {world_name}")

        return {
            "pending_count": len(created_mappings),
            "mappings": created_mappings
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI extraction response as JSON: {e}")
        return {"pending_count": 0, "mappings": []}
    except Exception as e:
        logger.error(f"AI pending mappings generation failed: {e}")
        return {"pending_count": 0, "mappings": []}


# ============================================================
# WORLD CHARACTERISTICS SCHEMA
# ============================================================
# Robust taxonomy for defining curated worlds
# These are CANONICAL - set by admins, immutable during play

class WorldCharacteristics(BaseModel):
    """
    Comprehensive world characteristics for curated settings.
    These define what IS true about the world - the canonical rules.
    """
    # CORE GENRE
    primary_genre: Optional[str] = Field(
        None,
        description="Primary genre: Fantasy, Sci-Fi, Horror, Modern, Historical, Post-Apocalyptic, Superhero, Mythic"
    )
    sub_genres: List[str] = Field(
        default_factory=list,
        description="Sub-genres: Grimdark, High Fantasy, Space Opera, Cyberpunk, Noir, etc."
    )

    # WORLD RULES
    magic_level: Optional[str] = Field(
        None,
        description="Magic presence: None, Rare & Mythic, Low & Costly, Common, Pervasive"
    )
    technology_level: Optional[str] = Field(
        None,
        description="Tech level: Primitive, Ancient, Medieval, Renaissance, Industrial, Modern, Near-Future, Far-Future, Magitech"
    )
    supernatural_presence: Optional[str] = Field(
        None,
        description="Supernatural: None, Hidden/Secretive, Known but Rare, Common, Dominant"
    )

    # TONE & MOOD
    tone: Optional[str] = Field(
        None,
        description="Overall tone: Hopeful, Optimistic, Neutral, Serious, Melancholic, Dark, Grimdark, Whimsical, Campy, Satirical"
    )
    narrative_style: List[str] = Field(
        default_factory=list,
        description="Storytelling approach: Epic/Sweeping, Intimate/Character-driven, Action-packed, Slow-burn, Pulpy/Fun, Literary/Poetic, Cinematic, etc."
    )
    moral_complexity: Optional[str] = Field(
        None,
        description="Morality: Clear Good vs Evil, Mostly Clear, Gray Areas, Morally Ambiguous, No Clear Morality"
    )
    lethality: Optional[str] = Field(
        None,
        description="Danger level: Plot Armor, Forgiving, Balanced, Dangerous, Brutal"
    )

    # THEMES (multi-select)
    themes: List[str] = Field(
        default_factory=list,
        description="Major themes: Political Intrigue, War, Survival, Exploration, Mystery, Romance, Redemption, etc."
    )

    # SOCIAL STRUCTURE
    social_structures: List[str] = Field(
        default_factory=list,
        description="Social systems: Tribal, Feudal, Theocratic, Monarchic, Democratic, Corporate, Anarchic, etc."
    )

    # SCALE
    power_scale: Optional[str] = Field(
        None,
        description="Power level: Street-level, Local/Regional, Kingdom/National, Continental, World-shaping, Cosmic"
    )
    scope: Optional[str] = Field(
        None,
        description="Story scope: Intimate/Personal, Local Community, Regional, Continental, Global, Interplanetary, Cosmic"
    )

    # WORLD CONSTANTS (immutable rules the AI must respect)
    world_constants: List[str] = Field(
        default_factory=list,
        description="Hard rules: 'Magic always has a cost', 'The gods are silent', 'No one returns from the Wastes'"
    )

    # SENSORY PALETTE
    sensory_palette: List[str] = Field(
        default_factory=list,
        description="What does this world feel like? 'Ash and smoke', 'Salt and sea', 'Pine and cold stone'"
    )

    # TABOOS & CUSTOMS
    taboos: List[str] = Field(
        default_factory=list,
        description="Forbidden things: 'Speaking the dead king's name', 'Magic use in cities'"
    )
    customs: List[str] = Field(
        default_factory=list,
        description="Expected behaviors: 'Guests receive salt before business', 'Bow to nobility'"
    )

    # HISTORY ANCHORS
    history_anchors: List[str] = Field(
        default_factory=list,
        description="Key events everyone references: 'The Sundering', 'When the Empire fell', 'Before the Plague'"
    )


# Valid options for world characteristics (for UI dropdowns)
WORLD_CHARACTERISTICS_OPTIONS = {
    "primary_genre": [
        # Core genres
        "Fantasy", "Sci-Fi", "Horror", "Mystery", "Thriller", "Romance",
        "Historical", "Modern", "Western", "Noir",
        # Hybrid/Specialty
        "Post-Apocalyptic", "Superhero", "Mythic", "Comedy", "Drama",
        "Adventure", "Slice of Life", "Supernatural"
    ],
    "sub_genres": [
        # Fantasy variants
        "High Fantasy", "Low Fantasy", "Urban Fantasy", "Dark Fantasy", "Grimdark",
        "Sword & Sorcery", "Cozy Fantasy", "Portal Fantasy", "Progression Fantasy",
        "Mythological", "Fairy Tale", "Arthurian",
        # Sci-Fi variants
        "Space Opera", "Hard Sci-Fi", "Cyberpunk", "Steampunk", "Dieselpunk",
        "Solarpunk", "Biopunk", "Military Sci-Fi", "First Contact",
        # Horror variants
        "Cosmic Horror", "Gothic Horror", "Survival Horror", "Folk Horror",
        "Body Horror", "Psychological Horror", "Southern Gothic",
        # Other
        "Noir", "Neo-Noir", "Western", "Weird Western", "Wuxia", "Xianxia",
        "Heist", "Pirate/Nautical", "Alternate History", "Dark Academia",
        "Cozy Mystery", "Romantic Fantasy", "LitRPG"
    ],
    "magic_level": [
        "None", "Rare & Mythic", "Low & Costly", "Common", "Pervasive"
    ],
    "technology_level": [
        "Primitive", "Ancient", "Medieval", "Renaissance", "Industrial",
        "Modern", "Near-Future", "Far-Future", "Magitech"
    ],
    "supernatural_presence": [
        "None", "Hidden/Secretive", "Known but Rare", "Common", "Dominant"
    ],
    "tone": [
        "Hopeful", "Optimistic", "Neutral", "Serious", "Melancholic",
        "Dark", "Grimdark", "Whimsical", "Campy", "Satirical"
    ],
    "narrative_style": [
        # Pacing & Structure
        "Epic/Sweeping", "Intimate/Character-driven", "Action-packed", "Slow-burn",
        # Voice & Feel
        "Pulpy/Fun", "Literary/Poetic", "Cinematic", "Mythic/Legendary",
        "Sardonic/Ironic", "Whimsical/Playful", "Gritty/Realistic",
        # Focus
        "Atmospheric/Moody", "Dialogue-heavy", "Procedural/Methodical",
        "Ensemble-focused", "Unreliable Narrator"
    ],
    "moral_complexity": [
        "Clear Good vs Evil", "Mostly Clear", "Gray Areas", "Morally Ambiguous", "No Clear Morality"
    ],
    "lethality": [
        "Plot Armor", "Forgiving", "Balanced", "Dangerous", "Brutal"
    ],
    "themes": [
        # Power & Conflict
        "Political Intrigue", "War & Conflict", "Revolution", "Power & Its Cost", "Class Struggle",
        # Personal
        "Survival", "Identity", "Coming of Age", "Redemption", "Revenge", "Grief & Loss",
        # Relationships
        "Romance", "Found Family", "Betrayal", "Loyalty", "Forbidden Love",
        # Exploration
        "Exploration", "Mystery", "Discovery", "The Unknown",
        # Philosophy
        "Fate vs Free Will", "Nature vs Civilization", "Faith & Religion", "Legacy",
        "Corruption", "Hope vs Despair", "Humanity/What Makes Us Human",
        # Other
        "Colonialism/Empire", "Environmental", "Technology's Cost"
    ],
    "social_structures": [
        "Tribal", "Feudal", "Theocratic", "Monarchic", "Democratic",
        "Corporate", "Anarchic", "Caste System", "Meritocratic", "Oligarchic",
        "Colonial", "Guild-based", "Matriarchal", "Patriarchal"
    ],
    "power_scale": [
        "Street-level", "Local/Regional", "Kingdom/National", "Continental", "World-shaping", "Cosmic"
    ],
    "scope": [
        "Intimate/Personal", "Local Community", "Regional", "Continental", "Global", "Interplanetary", "Cosmic"
    ],
}


router = APIRouter(prefix="/game", tags=["Game"])


# ============================================================
# INVITE CODE SYSTEM (for controlled alpha testing)
# ============================================================
# Force server reload to clear invite code cache

# Path to invite codes configuration
INVITE_CODES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "invite_codes.json"

# In-memory cache of invite codes (loaded from file)
_invite_codes_cache: Optional[Dict[str, Any]] = None


def _load_invite_codes_sync() -> Dict[str, Any]:
    """Load invite codes from file (synchronous). Always reload to ensure updates are picked up."""
    global _invite_codes_cache
    # Always reload from file to catch manual updates
    try:
        if INVITE_CODES_FILE.exists():
            with open(INVITE_CODES_FILE, "r", encoding="utf-8") as f:
                _invite_codes_cache = json.load(f)
        else:
            _invite_codes_cache = {"max_testers": 20, "codes": []}
    except Exception as e:
        logger.error(f"Failed to load invite codes: {e}")
        # Fallback to existing cache if file read fails, or empty if no cache
        if _invite_codes_cache is None:
            _invite_codes_cache = {"max_testers": 20, "codes": []}
            
    return _invite_codes_cache


async def _load_invite_codes() -> Dict[str, Any]:
    """Load invite codes from file (async wrapper)."""
    return await run_in_threadpool(_load_invite_codes_sync)


def _save_invite_codes_sync() -> None:
    """Save invite codes to file (synchronous)."""
    if _invite_codes_cache:
        try:
            INVITE_CODES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(INVITE_CODES_FILE, "w", encoding="utf-8") as f:
                json.dump(_invite_codes_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save invite codes: {e}")


async def _save_invite_codes() -> None:
    """Save invite codes to file (async wrapper)."""
    await run_in_threadpool(_save_invite_codes_sync)


class InviteCodeRequest(BaseModel):
    """Request to validate an invite code."""
    code: str = Field(..., min_length=5, max_length=50, description="The invite code to validate")


class InviteCodeResponse(BaseModel):
    """Response from invite code validation."""
    valid: bool
    message: str
    tester_name: Optional[str] = None
    testers_remaining: Optional[int] = None
    is_admin: bool = False
    app_version: Optional[str] = None


@router.post("/invite/validate", response_model=InviteCodeResponse)
async def validate_invite_code(request: InviteCodeRequest):
    """
    Validate an invite code for alpha testing access.

    Returns success if the code is valid and not yet at max capacity.
    Codes are single-use per tester slot.
    """
    codes_data = await _load_invite_codes()
    max_testers = codes_data.get("max_testers", 20)
    codes = codes_data.get("codes", [])

    # Count active testers
    active_count = sum(1 for c in codes if c.get("activated", False))
    
    # DEBUG LOGGING
    code_upper = request.code.strip().upper()
    AuditLogger.log_sync(f"[INVITE DEBUG] Validating code: '{request.code}' -> Normalized: '{code_upper}'")
    AuditLogger.log_sync(f"[INVITE DEBUG] Active testers: {active_count}/{max_testers}")

    # Check if at capacity
    if active_count >= max_testers:
        # Check if the user is ALREADY activated with this code (allow re-entry)
        is_existing_user = False
        for c in codes:
            if c.get("code", "").upper() == code_upper and c.get("activated", False):
                is_existing_user = True
                break
        
        if not is_existing_user:
            AuditLogger.log_sync(f"[INVITE DEBUG] Capacity reached ({active_count}/{max_testers}). Rejecting new user.")
            return InviteCodeResponse(
                valid=False,
                message="Sorry, we've reached capacity for alpha testers. Please check back later!",
                testers_remaining=0
            )

    # Find the code
    for code_entry in codes:
        stored_code = code_entry.get("code", "").upper()
        
        if stored_code == code_upper:
            if code_entry.get("activated", False):
                # Already activated - still valid (same tester returning)
                is_admin_user = code_entry.get("is_admin", False)
                AuditLogger.log_sync(f"[INVITE DEBUG] Welcome back existing user: {code_entry.get('name')} (admin={is_admin_user})")
                return InviteCodeResponse(
                    valid=True,
                    message=f"Welcome back, {code_entry.get('name', 'Tester')}!",
                    tester_name=code_entry.get('name'),
                    testers_remaining=max_testers - active_count,
                    is_admin=is_admin_user,
                    app_version=get_app_version()
                )
            else:
                # Activate the code
                code_entry["activated"] = True
                code_entry["activated_at"] = datetime.now(timezone.utc).isoformat()
                await _save_invite_codes()

                is_admin_user = code_entry.get("is_admin", False)
                AuditLogger.log_sync(f"[INVITE DEBUG] Activating NEW user: {code_entry.get('name')} (admin={is_admin_user})")

                return InviteCodeResponse(
                    valid=True,
                    message=f"Welcome to the alpha test, {code_entry.get('name', 'Tester')}!",
                    tester_name=code_entry.get('name'),
                    testers_remaining=max_testers - active_count - 1,
                    is_admin=is_admin_user,
                    app_version=get_app_version()
                )

    # Code not found
    AuditLogger.log_sync(f"[INVITE DEBUG] Code not found in list: '{code_upper}'")
    return InviteCodeResponse(
        valid=False,
        message="Invalid invite code. Please check your code and try again.",
        testers_remaining=max_testers - active_count
    )


@router.get("/invite/status")
async def get_invite_status():
    """
    Get current alpha testing status.

    Returns capacity information for display.
    """
    codes_data = await _load_invite_codes()
    max_testers = codes_data.get("max_testers", 20)
    codes = codes_data.get("codes", [])

    active_count = sum(1 for c in codes if c.get("activated", False))

    return {
        "accepting_testers": active_count < max_testers,
        "testers_active": active_count,
        "testers_max": max_testers,
        "testers_remaining": max_testers - active_count
    }


# ============================================================
# ANALYTICS DASHBOARD (reads from Neo4j GameSession nodes)
# ============================================================

@router.get("/analytics")
async def get_analytics(http_request: Request):
    """
    Get comprehensive analytics from Neo4j.
    Shows tester engagement, session activity, and usage patterns.
    """
    from collections import defaultdict

    # Load invite codes (still from file - these are static config)
    codes_data = await _load_invite_codes()
    codes = codes_data.get("codes", [])
    activated_testers = [c for c in codes if c.get("activated", False)]

    db = getattr(http_request.app.state, "neo4j_db", None)

    sessions_list = []
    total_actions = 0
    activity_by_date = defaultdict(int)
    unique_testers = set()

    if db:
        try:
            # Get all GameSession nodes
            result = await db.execute("""
                MATCH (s:GameSession)
                RETURN s.session_id AS session_id,
                       s.character_name AS character_name,
                       s.tester AS tester,
                       s.curated_world_name AS world_name,
                       s.genre AS genre,
                       s.turn_count AS turn_count,
                       s.status AS status,
                       s.created_at AS created_at,
                       s.last_activity AS last_activity
                ORDER BY s.created_at DESC
                LIMIT 100
            """, {})

            for record in result:
                session_id = record.get("session_id", "")
                created_at = str(record.get("created_at", ""))
                turn_count = record.get("turn_count") or 0
                total_actions += turn_count
                tester_name = record.get("tester") or ""

                if tester_name:
                    unique_testers.add(tester_name)

                sessions_list.append({
                    "session_id": session_id[:8] + "..." if session_id else "unknown",
                    "character": record.get("character_name") or "Anonymous",
                    "tester": tester_name,
                    "world": record.get("world_name") or "Custom",
                    "genre": record.get("genre") or "fantasy",
                    "turn_count": turn_count,
                    "status": record.get("status") or "unknown",
                    "started_at": created_at,
                    "last_activity": str(record.get("last_activity", "")),
                })

                # Track activity by date
                if created_at and len(created_at) >= 10:
                    date = created_at[:10]
                    activity_by_date[date] += 1

        except Exception as e:
            logger.error(f"Failed to load sessions from Neo4j: {e}")

    # Build tester list from unique testers found in sessions
    testers = []
    for tester_name in unique_testers:
        # Get all sessions for this tester
        tester_sessions = [s for s in sessions_list if s.get("tester") == tester_name]

        # Find matching invite code
        matching_code = next((c for c in codes if c.get("name") == tester_name), None)

        testers.append({
            "name": tester_name,
            "code": matching_code.get("code", "") if matching_code else "",
            "activated_at": matching_code.get("activated_at") if matching_code else None,
            "last_activity": tester_sessions[0].get("last_activity") if tester_sessions else None,
            "total_sessions": len(tester_sessions),
            "total_actions": sum(s.get("turn_count", 0) for s in tester_sessions),
        })

    testers.sort(key=lambda x: x.get("last_activity") or "", reverse=True)

    return {
        "summary": {
            "testers_activated": len(unique_testers),  # Unique testers from actual sessions
            "codes_activated": len(activated_testers),  # Invite codes marked as activated
            "testers_max": codes_data.get("max_testers", 30),
            "total_sessions": len(sessions_list),
            "total_events": len(sessions_list),
            "total_actions": total_actions,
        },
        "testers": testers[:20],
        "recent_sessions": sessions_list[:15],
        "event_breakdown": {"sessions": len(sessions_list), "actions": total_actions},
        "activity_by_date": dict(sorted(activity_by_date.items())[-7:]),
    }


@router.delete("/admin/sessions/cleanup")
async def cleanup_old_sessions(
    http_request: Request,
    before_date: Optional[str] = None,
    empty_only: bool = True
):
    """
    Delete old sessions with no useful data.

    - empty_only=True (default): Delete sessions with no tester, no character, and 0 turns
    - before_date: Delete all sessions before this ISO date (e.g., "2026-01-01")
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        if empty_only:
            # Delete sessions with no tester and no character_name and 0 turns
            result = await db.execute("""
                MATCH (s:GameSession)
                WHERE (s.tester IS NULL OR s.tester = '')
                  AND (s.character_name IS NULL OR s.character_name = '')
                  AND (s.turn_count IS NULL OR s.turn_count = 0)
                DELETE s
                RETURN count(s) as deleted
            """, {})
        elif before_date:
            # Delete sessions before date
            result = await db.execute("""
                MATCH (s:GameSession)
                WHERE s.created_at < datetime($before_date)
                DELETE s
                RETURN count(s) as deleted
            """, {"before_date": before_date})
        else:
            return {"deleted": 0, "message": "Specify empty_only=true or provide before_date"}

        deleted = result[0].get("deleted", 0) if result else 0
        logger.info(f"Cleaned up {deleted} old sessions")
        return {"deleted": deleted, "message": f"Cleaned up {deleted} sessions"}
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/lore-bases/details")
async def get_all_lore_bases_details(
    http_request: Request,
):
    """
    Get detailed info about all curated worlds including:
    - Basic info (id, name, description, genres, tones)
    - Lore content (the actual seed text)
    - Entity counts from database
    - Ingestion status
    """
    db = getattr(http_request.app.state, "neo4j_db", None)

    # Get entity counts per world from database
    entity_counts = {}
    if db:
        try:
            result = await db.execute("""
                MATCH (n:Entity)
                WHERE n.curated_world_id IS NOT NULL OR n.world_id IS NOT NULL
                WITH COALESCE(n.curated_world_id, n.world_id) AS world_id
                RETURN world_id, count(*) AS count
            """, {})
            for row in result:
                wid = row.get("world_id", "")
                # Include known curated worlds OR short IDs (non-session-scoped)
                # Session-scoped IDs look like: worldname_YYMMDD_HHMMSS (timestamp suffix)
                # Curated world IDs are in LORE_BASES
                if wid and (wid in LORE_BASES or not re.match(r'.+_\d{6}_\d{6}$', wid)):
                    entity_counts[wid] = row.get("count", 0)
        except Exception as e:
            logger.warning(f"Failed to get entity counts: {e}")

    worlds = []
    for lore_id, base in LORE_BASES.items():
        lore_content = base.get("lore_content") or ""
        worlds.append({
            "id": base["id"],
            "name": base["name"],
            "description": base.get("description") or "",
            "genre": base.get("genre"),  # Legacy field for backward compatibility
            "mechanics_genre": base.get("mechanics_genre"),  # NEW: Authoritative mechanics genre
            "genre_hints": base.get("genre_hints") or [],
            "genre_confidence": base.get("genre_confidence"),  # NEW: Confidence score
            "tone_hints": base.get("tone_hints") or [],
            "lore_content": lore_content,
            "seed_prompt": base.get("seed_prompt") or "",
            "is_seed": base.get("is_seed", False),
            "entity_count": entity_counts.get(lore_id, 0),
            "has_lore_content": bool(lore_content.strip()),
            "lore_char_count": len(lore_content),
        })

    return {
        "worlds": worlds,
        "total_worlds": len(worlds),
        "total_entities": sum(entity_counts.values()),
    }


@router.put("/admin/lore-bases/{lore_id}/lore")
async def update_lore_base_content(
    lore_id: str,
    http_request: Request,
):
    """
    Update the lore_content for a curated world.
    This updates the JSON file on disk and reloads the lore base.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    try:
        body = await http_request.json()
        new_lore = body.get("lore_content", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Helper for synchronous file operations
    def _update_lore_file_sync(lid: str, content: str) -> Optional[Path]:
        # Find the JSON file for this lore base
        found_file = None
        for json_file in LORE_BASES_DIR.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("id") == lid:
                        found_file = json_file
                        break
            except Exception:
                continue

        if not found_file:
            # Check seeds directory
            for json_file in SEEDS_DIR.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("id") == lid:
                            found_file = json_file
                            break
                except Exception:
                    continue

        # Update the file or create one for Neo4j-sourced worlds
        if found_file:
            # Update existing JSON file
            with open(found_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data["lore_content"] = content

            with open(found_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return found_file
        else:
            # No JSON file - create one for this Neo4j-sourced world
            base_data = LORE_BASES.get(lid, {})
            data = {
                "id": lid,
                "name": base_data.get("name", lid),
                "description": base_data.get("description", ""),
                "genre": base_data.get("genre", "fantasy"),
                "genre_hints": base_data.get("genre_hints", []),
                "tone_hints": base_data.get("tone_hints", []),
                "seed_prompt": base_data.get("seed_prompt", ""),
                "lore_content": content,
            }

            # Create new JSON file in lore_bases directory
            new_file = LORE_BASES_DIR / f"{lid}.json"
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return new_file

    try:
        # Run file operations in thread pool
        lore_file = await run_in_threadpool(_update_lore_file_sync, lore_id, new_lore)
        if not lore_file and not LORE_BASES.get(lore_id):
             # Should be handled by _update_lore_file_sync creating new file if needed, 
             # but check logic again
             pass 

        if lore_file:
             logger.info(f"Updated JSON file: {lore_file}")
        else:
             logger.info(f"Created new JSON file for Neo4j-sourced world")

        # Update in-memory cache
        LORE_BASES[lore_id]["lore_content"] = new_lore

        # Also update Neo4j if database is available
        db = getattr(http_request.app.state, "neo4j_db", None)
        if db:
            try:
                await db.execute("""
                    MATCH (lb:LoreBase {lore_id: $lore_id})
                    SET lb.lore_content = $lore_content
                """, {"lore_id": lore_id, "lore_content": new_lore})
            except Exception as e:
                logger.warning(f"Failed to update Neo4j LoreBase: {e}")

        logger.info(f"Updated lore_content for '{lore_id}': {len(new_lore)} chars")
        return {
            "success": True,
            "lore_id": lore_id,
            "lore_char_count": len(new_lore),
            "message": f"Updated lore for '{lore_id}'"
        }
    except Exception as e:
        logger.error(f"Failed to update lore for '{lore_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/lore-bases/{lore_id}/genre")
async def get_lore_base_genre(
    lore_id: str,
    http_request: Request,
):
    """
    Get genre information for a lore base (mechanics_genre and genre_hints).
    
    Works for both curated worlds (LORE_BASES) and user-created worlds (Neo4j).
    """
    # Check curated worlds first
    if lore_id in LORE_BASES:
        world_data = LORE_BASES[lore_id]
        mechanics_genre = world_data.get("mechanics_genre") or world_data.get("genre")
        
        return {
            "lore_id": lore_id,
            "mechanics_genre": mechanics_genre,
            "genre_hints": world_data.get("genre_hints", []),
            "genre_confidence": world_data.get("genre_confidence"),
            "source": "curated",
        }
    
    # Check Neo4j for user-created worlds
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            result = await db.execute("""
                MATCH (lb:LoreBase {lore_id: $lore_id})
                RETURN lb.mechanics_genre AS mechanics_genre,
                       lb.genre AS genre,
                       lb.genre_hints AS genre_hints,
                       lb.genre_confidence AS genre_confidence
            """, {"lore_id": lore_id})
            
            if result:
                row = result[0]
                mechanics_genre = row.get("mechanics_genre") or row.get("genre")
                
                return {
                    "lore_id": lore_id,
                    "mechanics_genre": mechanics_genre,
                    "genre_hints": row.get("genre_hints", []),
                    "genre_confidence": row.get("genre_confidence"),
                    "source": "user_created",
                }
        except Exception as e:
            logger.error(f"Failed to get genre for '{lore_id}' from Neo4j: {e}")
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Lore base '{lore_id}' not found"
    )


@router.put("/admin/lore-bases/{lore_id}/genre")
async def update_lore_base_genre(
    lore_id: str,
    http_request: Request,
):
    """
    Update the mechanics_genre and genre_hints for a lore base.
    
    Request body:
    {
        "mechanics_genre": "scifi",
        "genre_hints": ["scifi", "mystery", "thriller"],
        "genre_confidence": 0.9
    }
    
    Works for both curated worlds (updates JSON file + memory) and user-created worlds (updates Neo4j).
    """
    try:
        body = await http_request.json()
        mechanics_genre = body.get("mechanics_genre")
        genre_hints = body.get("genre_hints", [])
        genre_confidence = body.get("genre_confidence")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    if not mechanics_genre:
        raise HTTPException(status_code=400, detail="mechanics_genre is required")
    
    # Validate mechanics_genre against valid genres
    from src.mantle.agents.genre_assessment import VALID_MECHANICS_GENRES
    if mechanics_genre.lower() not in VALID_MECHANICS_GENRES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mechanics_genre. Must be one of: {', '.join(sorted(VALID_MECHANICS_GENRES))}"
        )
    
    # Update curated world (LORE_BASES + JSON file)
    if lore_id in LORE_BASES:
        # Update in-memory LORE_BASES
        LORE_BASES[lore_id]["mechanics_genre"] = mechanics_genre
        LORE_BASES[lore_id]["genre_hints"] = genre_hints
        if genre_confidence is not None:
            LORE_BASES[lore_id]["genre_confidence"] = genre_confidence
        
        # Update JSON file on disk
        def _update_genre_in_file_sync(lid: str, m_genre: str, hints: list, confidence: float = None) -> Optional[Path]:
            # Find the JSON file for this lore base
            found_file = None
            for json_file in LORE_BASES_DIR.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get("id") == lid:
                            found_file = json_file
                            break
                except Exception:
                    continue
            
            if not found_file:
                # Check seeds directory
                for json_file in SEEDS_DIR.glob("*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if data.get("id") == lid:
                                found_file = json_file
                                break
                    except Exception:
                        continue
            
            if found_file:
                # Update existing file
                with open(found_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                data["mechanics_genre"] = m_genre
                data["genre_hints"] = hints
                if confidence is not None:
                    data["genre_confidence"] = confidence
                
                with open(found_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return found_file
            
            return None
        
        try:
            lore_file = await run_in_threadpool(
                _update_genre_in_file_sync, lore_id, mechanics_genre, genre_hints, genre_confidence
            )
            if lore_file:
                logger.info(f"Updated genre in JSON file: {lore_file}")
        except Exception as e:
            logger.warning(f"Failed to update JSON file for {lore_id}: {e}")
        
        logger.info(f"Updated genre for curated world '{lore_id}': {mechanics_genre}")
        return {
            "success": True,
            "lore_id": lore_id,
            "mechanics_genre": mechanics_genre,
            "genre_hints": genre_hints,
            "source": "curated",
            "message": f"Updated genre for '{lore_id}'"
        }
    
    # Update user-created world in Neo4j
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            # Check if LoreBase exists
            check_result = await db.execute("""
                MATCH (lb:LoreBase {lore_id: $lore_id})
                RETURN lb.name AS name
            """, {"lore_id": lore_id})
            
            if not check_result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lore base '{lore_id}' not found"
                )
            
            # Update genre fields
            update_query = """
                MATCH (lb:LoreBase {lore_id: $lore_id})
                SET lb.mechanics_genre = $mechanics_genre,
                    lb.genre_hints = $genre_hints
            """
            params = {
                "lore_id": lore_id,
                "mechanics_genre": mechanics_genre,
                "genre_hints": genre_hints,
            }
            
            if genre_confidence is not None:
                update_query += ", lb.genre_confidence = $genre_confidence"
                params["genre_confidence"] = genre_confidence
            
            await db.execute(update_query, params)
            
            logger.info(f"Updated genre for user-created world '{lore_id}': {mechanics_genre}")
            return {
                "success": True,
                "lore_id": lore_id,
                "mechanics_genre": mechanics_genre,
                "genre_hints": genre_hints,
                "source": "user_created",
                "message": f"Updated genre for '{lore_id}'"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update genre in Neo4j for '{lore_id}': {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Lore base '{lore_id}' not found"
    )


# ============================================================
# CHARACTER OPTIONS ENDPOINTS
# ============================================================

@router.get("/admin/lore-bases/{lore_id}/character-options")
async def get_character_options(
    lore_id: str,
    http_request: Request,
):
    """
    Get character creation options for a lore base.

    Returns the custom origins and archetypes configured for this world.
    Checks Neo4j first for persisted options, falls back to in-memory.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    base = LORE_BASES[lore_id]
    char_opts = base.get("character_options", {})
    source = "memory"

    # Try to load from Neo4j if available (structured storage)
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db and not char_opts.get("origins"):
        try:
            schema_db = CharacterSchemaDB(db)
            neo4j_opts = await schema_db.get_character_options(lore_id)
            if neo4j_opts.get("origins") or neo4j_opts.get("archetypes"):
                char_opts = neo4j_opts
                source = "neo4j"
                # Update in-memory cache
                LORE_BASES[lore_id]["character_options"] = char_opts
                logger.info(f"Loaded character options from Neo4j for {lore_id}")
        except Exception as e:
            logger.debug(f"No Neo4j character options for {lore_id}: {e}")

    return {
        "lore_id": lore_id,
        "world_name": base.get("name", lore_id),
        "character_options": char_opts,
        "has_options": bool(char_opts.get("origins") or char_opts.get("archetypes")),
        "source": source,
    }


@router.post("/admin/lore-bases/{lore_id}/character-options/generate")
async def generate_character_options(
    lore_id: str,
    http_request: Request,
):
    """
    Use AI to generate character creation options from the world's lore.

    This analyzes the lore content and generates setting-appropriate
    origins and archetypes that map to base D&D types for mechanics.

    The generated options are stored but marked as ai_generated=True
    and admin_reviewed=False until an admin reviews them.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    base = LORE_BASES[lore_id]
    lore_content = base.get("lore_content", "")
    description = base.get("description", "")
    genre = base.get("genre") or (base.get("genre_hints", ["fantasy"])[0] if base.get("genre_hints") else "fantasy")

    if not lore_content and not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lore base '{lore_id}' has no lore content to analyze"
        )

    # Use description as fallback if no lore content
    content_to_analyze = lore_content or description

    # Generate options using AI
    options = await generate_character_options_from_lore(
        lore_content=content_to_analyze,
        world_name=base.get("name", lore_id),
        genre=genre,
        description=description
    )

    # Store the options
    LORE_BASES[lore_id]["character_options"] = options

    # Try to persist to Neo4j
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $lore_id})
                SET lb.character_options = $options
            """, {
                "lore_id": lore_id,
                "options": json.dumps(options)
            })
        except Exception as e:
            logger.warning(f"Failed to persist character options to Neo4j: {e}")

    return {
        "success": True,
        "lore_id": lore_id,
        "world_name": base.get("name", lore_id),
        "character_options": options,
        "message": f"Generated {len(options.get('origins', []))} origins and {len(options.get('archetypes', []))} archetypes"
    }


@router.put("/admin/lore-bases/{lore_id}/character-options")
async def update_character_options(
    lore_id: str,
    http_request: Request,
):
    """
    Update character creation options for a lore base.

    Admins can modify the AI-generated options or provide custom ones.
    This marks the options as admin_reviewed=True.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    body = await http_request.json()
    origins = body.get("origins", [])
    archetypes = body.get("archetypes", [])

    # Validate structure
    for origin in origins:
        if not all(k in origin for k in ["id", "name", "base_type"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Origin missing required fields (id, name, base_type): {origin}"
            )
        if origin["base_type"] not in BASE_ORIGINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base_type '{origin['base_type']}' for origin. Valid: {BASE_ORIGINS}"
            )

    for archetype in archetypes:
        if not all(k in archetype for k in ["id", "name", "base_type"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Archetype missing required fields (id, name, base_type): {archetype}"
            )
        if archetype["base_type"] not in BASE_ARCHETYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base_type '{archetype['base_type']}' for archetype. Valid: {BASE_ARCHETYPES}"
            )

    options = {
        "origins": origins,
        "archetypes": archetypes,
        "ai_generated": body.get("ai_generated", False),
        "admin_reviewed": True  # Always mark as reviewed when manually updated
    }

    # Store the options in memory (for immediate use)
    LORE_BASES[lore_id]["character_options"] = options

    # Persist to Neo4j using structured schema
    db = getattr(http_request.app.state, "neo4j_db", None)
    neo4j_result = None
    if db:
        try:
            schema_db = CharacterSchemaDB(db)
            neo4j_result = await schema_db.save_character_options(
                world_id=lore_id,
                origins=origins,
                archetypes=archetypes,
            )
            logger.info(f"Persisted character options to Neo4j: {neo4j_result}")
        except Exception as e:
            logger.warning(f"Failed to persist character options to Neo4j: {e}")

    return {
        "success": True,
        "lore_id": lore_id,
        "character_options": options,
        "neo4j_result": neo4j_result,
        "message": f"Updated character options: {len(origins)} origins, {len(archetypes)} archetypes"
    }


# =============================================================================
# CHARACTER OPTIONS ENDPOINTS
# =============================================================================
# Character options (origins/archetypes) are directly editable without a staging workflow.
# - GET /admin/lore-bases/{lore_id}/character-options - view current options
# - PUT /admin/lore-bases/{lore_id}/character-options - edit options
# - POST /admin/lore-bases/{lore_id}/character-options/generate - AI generate from lore
# - POST /admin/lore-bases/{lore_id}/extract-mappings - alias for generate (legacy)


# Legacy endpoints - return character options instead of pending mappings
@router.get("/admin/pending-mappings")
async def list_pending_mappings_legacy(http_request: Request, status_filter: Optional[str] = None):
    """DEPRECATED: Pending mappings removed. Use character options endpoints instead."""
    return {"worlds": [], "total_pending": 0, "total_active": 0, "message": "Pending mappings deprecated - use character options"}


@router.get("/admin/lore-bases/{lore_id}/pending-mappings")
async def get_pending_mappings_for_world_legacy(lore_id: str, http_request: Request, status_filter: Optional[str] = None):
    """DEPRECATED: Returns character options for the world instead."""
    if lore_id not in LORE_BASES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lore base '{lore_id}' not found")

    # Return character options as "mappings" for backward compatibility
    options = LORE_BASES[lore_id].get("character_options", {})
    world_name = LORE_BASES.get(lore_id, {}).get("name", lore_id)

    return {
        "world_id": lore_id,
        "world_name": world_name,
        "mappings": [],  # No pending mappings in new system
        "pending_count": 0,
        "active_count": len(options.get("origins", [])) + len(options.get("archetypes", [])),
        "needs_approval": False,
        "character_options": options,
        "message": "Pending mappings deprecated - character options returned instead"
    }


# Legacy approve/reject/edit endpoints - return deprecation notice
@router.post("/admin/pending-mappings/{mapping_id}/approve")
async def approve_mapping_legacy(mapping_id: str, http_request: Request):
    """DEPRECATED: Use PUT /admin/lore-bases/{lore_id}/character-options instead."""
    return {"success": False, "message": "Pending mappings deprecated. Edit character options directly via PUT /admin/lore-bases/{lore_id}/character-options", "deprecated": True}


@router.post("/admin/pending-mappings/{mapping_id}/reject")
async def reject_mapping_legacy(mapping_id: str, http_request: Request):
    """DEPRECATED: Use PUT /admin/lore-bases/{lore_id}/character-options instead."""
    return {"success": False, "message": "Pending mappings deprecated. Edit character options directly.", "deprecated": True}


@router.post("/admin/pending-mappings/{mapping_id}/edit")
async def edit_mapping_legacy(mapping_id: str, http_request: Request):
    """DEPRECATED: Use PUT /admin/lore-bases/{lore_id}/character-options instead."""
    return {"success": False, "message": "Pending mappings deprecated. Edit character options directly.", "deprecated": True}


@router.post("/admin/lore-bases/{lore_id}/extract-mappings")
async def extract_character_options(
    lore_id: str,
    http_request: Request,
):
    """
    Extract character options from a world's lore using AI.

    This analyzes the lore and directly generates character creation options
    (origins and archetypes) that are immediately available for editing.

    This is an alias for /character-options/generate for backward compatibility.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    base = LORE_BASES[lore_id]

    # Try multiple fields for lore content - seed_prompt often has rich content
    lore_content = (
        base.get("lore_content", "") or
        base.get("description", "") or
        base.get("seed_prompt", "")
    )

    # Debug logging to diagnose lore content issues
    logger.info(f"Extract options for '{lore_id}': lore_content={len(base.get('lore_content') or '')}, "
                f"description={len(base.get('description') or '')}, seed_prompt={len(base.get('seed_prompt') or '')}")

    if not lore_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"World has no lore content to analyze. Fields checked: lore_content, description, seed_prompt"
        )

    # Determine genre
    genre = base.get("mechanics_genre") or base.get("genre") or "fantasy"

    # Generate character options directly (no approval workflow)
    options = await generate_character_options_from_lore(
        lore_content=lore_content,
        world_name=base.get("name", lore_id),
        genre=genre,
        description=base.get("description", "")
    )

    # Store in LORE_BASES immediately
    LORE_BASES[lore_id]["character_options"] = options

    # Persist to Neo4j if available
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $lore_id})
                SET lb.character_options = $options
            """, {"lore_id": lore_id, "options": json.dumps(options)})
        except Exception as e:
            logger.warning(f"Failed to persist character options to Neo4j: {e}")

    origins_count = len(options.get("origins", []))
    archetypes_count = len(options.get("archetypes", []))

    return {
        "success": True,
        "lore_id": lore_id,
        "world_name": base.get("name", lore_id),
        "origins_count": origins_count,
        "archetypes_count": archetypes_count,
        "character_options": options,
        "message": f"Generated {origins_count} origins and {archetypes_count} archetypes - ready to edit"
    }


@router.post("/admin/pending-mappings/bulk-approve")
async def bulk_approve_legacy(http_request: Request):
    """DEPRECATED: Use POST /admin/lore-bases/{lore_id}/extract-mappings to generate options directly."""
    return {"success": False, "message": "Pending mappings deprecated. Options are now generated directly.", "deprecated": True, "approved_count": 0}


# =============================================================================
# WORLD TUNER - Moved to world_tuner_routes.py
# =============================================================================


@router.get("/admin/entities/orphans")
async def get_orphan_entities(
    http_request: Request,
):
    """
    Find entities that are not associated with any valid curated world.
    These may be from deleted worlds or failed ingestions.
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    valid_world_ids = set(LORE_BASES.keys())

    try:
        # Find entities with no world_id or with an invalid world_id
        result = await db.execute("""
            MATCH (n:Entity)
            RETURN n.canon_id AS canon_id,
                   n.name AS name,
                   n.entity_type AS entity_type,
                   n.world_id AS world_id,
                   n.curated_world_id AS curated_world_id,
                   n.source_name AS source_name
            ORDER BY n.world_id, n.name
        """, {})

        orphans = []
        valid = []
        for row in result:
            world_id = row.get("world_id", "")
            curated_id = row.get("curated_world_id", "")

            # Check if it belongs to a valid curated world
            is_valid = False
            if curated_id and curated_id in valid_world_ids:
                is_valid = True
            elif world_id and world_id in valid_world_ids:
                is_valid = True
            # Session-scoped entities are valid if base world exists
            elif world_id and "_" in world_id:
                base_world = world_id.rsplit("_", 1)[0]
                if base_world in valid_world_ids or base_world == "custom":
                    is_valid = True

            if is_valid:
                valid.append(row)
            else:
                orphans.append({
                    "canon_id": row.get("canon_id"),
                    "name": row.get("name"),
                    "entity_type": row.get("entity_type"),
                    "world_id": world_id,
                    "curated_world_id": curated_id,
                    "source_name": row.get("source_name"),
                })

        return {
            "orphan_count": len(orphans),
            "valid_count": len(valid),
            "orphans": orphans[:100],  # Limit to 100 for display
            "valid_worlds": list(valid_world_ids),
        }
    except Exception as e:
        logger.error(f"Failed to find orphan entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/entities/orphans")
async def delete_orphan_entities(
    http_request: Request,
):
    """
    Delete all orphan entities that are not associated with valid curated worlds.
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database unavailable")

    valid_world_ids = list(LORE_BASES.keys())

    try:
        # Delete entities with no valid world association
        # This is conservative - only deletes entities with world_ids that don't match any known world
        result = await db.execute("""
            MATCH (n:Entity)
            WHERE n.world_id IS NOT NULL
              AND NOT n.world_id IN $valid_worlds
              AND NOT n.curated_world_id IN $valid_worlds
              AND NOT any(w IN $valid_worlds WHERE n.world_id STARTS WITH w + '_')
            DETACH DELETE n
            RETURN count(n) AS deleted
        """, {"valid_worlds": valid_world_ids})

        deleted = result[0].get("deleted", 0) if result else 0
        logger.info(f"Deleted {deleted} orphan entities")
        return {
            "deleted": deleted,
            "message": f"Deleted {deleted} orphan entities",
        }
    except Exception as e:
        logger.error(f"Failed to delete orphan entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API USAGE TRACKING (for cost monitoring)
# ============================================================

@router.get("/usage")
async def get_usage_stats():
    """
    Get current API usage statistics for cost monitoring.
    Shows token usage, estimated costs, and budget status.
    """
    usage = _token_tracker.get_usage_summary()
    budget = _beta_budget

    # Calculate percentages
    daily_token_pct = (usage["daily"]["tokens"] / budget.max_tokens_per_day) * 100 if budget.max_tokens_per_day else 0
    daily_cost_pct = (usage["daily"]["cost"] / budget.max_cost_per_day) * 100 if budget.max_cost_per_day else 0
    hourly_token_pct = (usage["hourly"]["tokens"] / budget.max_tokens_per_hour) * 100 if budget.max_tokens_per_hour else 0

    return {
        "daily": {
            "tokens_used": usage["daily"]["tokens"],
            "tokens_limit": budget.max_tokens_per_day,
            "tokens_remaining": usage["daily"]["tokens_remaining"],
            "tokens_percent": round(daily_token_pct, 1),
            "requests": usage["daily"]["requests"],
            "requests_limit": budget.max_requests_per_day,
            "estimated_cost": round(usage["daily"]["cost"], 4),
            "cost_limit": budget.max_cost_per_day,
            "cost_percent": round(daily_cost_pct, 1),
        },
        "hourly": {
            "tokens_used": usage["hourly"]["tokens"],
            "tokens_limit": budget.max_tokens_per_hour,
            "tokens_percent": round(hourly_token_pct, 1),
            "requests": usage["hourly"]["requests"],
            "requests_limit": budget.max_requests_per_hour,
        },
        "active_sessions": usage["active_sessions"],
        "limits": {
            "tokens_per_session": budget.max_tokens_per_session,
            "requests_per_session": budget.max_requests_per_session,
            "cost_per_session": budget.max_cost_per_session,
            "cost_per_day": budget.max_cost_per_day,
        },
        "status": "warning" if daily_cost_pct > 80 else "ok",
        "message": f"Daily usage: ${usage['daily']['cost']:.4f} of ${budget.max_cost_per_day:.2f} limit"
    }


# ============================================================
# FEEDBACK SYSTEM (stored in Neo4j for persistence)
# ============================================================

class FeedbackRequest(BaseModel):
    """Feedback submission from playtesters."""
    category: Optional[str] = Field(None, description="Feedback category: confused, frustrated, delighted, bug, idea, other")
    text: Optional[str] = Field(None, max_length=5000, description="Detailed feedback text")
    context: Optional[Dict[str, Any]] = Field(None, description="Context about what was happening")


class FeedbackResponse(BaseModel):
    """Response from feedback submission."""
    success: bool
    message: str
    feedback_id: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    http_request: Request,
    request: FeedbackRequest
):
    """
    Submit feedback from a playtester.

    Stores feedback in Neo4j for persistence across deploys.
    """
    if not request.category and not request.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a category or feedback text"
        )

    feedback_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()
    tester = request.context.get("tester", "anonymous") if request.context else "anonymous"
    session_id = request.context.get("session_id", "") if request.context else ""

    # Store in Neo4j
    db = getattr(http_request.app.state, "neo4j_db", None)
    if db:
        try:
            await db.execute("""
                CREATE (f:Feedback {
                    feedback_id: $feedback_id,
                    timestamp: $timestamp,
                    category: $category,
                    text: $text,
                    tester: $tester,
                    session_id: $session_id,
                    screen: $screen,
                    world_id: $world_id
                })
            """, {
                "feedback_id": feedback_id,
                "timestamp": timestamp,
                "category": request.category or "",
                "text": request.text or "",
                "tester": tester,
                "session_id": session_id,
                "screen": request.context.get("screen", "") if request.context else "",
                "world_id": request.context.get("world_id", "") if request.context else "",
            })
            logger.info(f"Feedback stored in Neo4j from {tester}: [{request.category}]")
        except Exception as e:
            logger.error(f"Failed to store feedback in Neo4j: {e}")
    else:
        logger.warning("No Neo4j connection - feedback not persisted")

    return FeedbackResponse(
        success=True,
        message="Thank you for your feedback!",
        feedback_id=feedback_id
    )


@router.get("/feedback")
async def get_all_feedback(http_request: Request):
    """
    Get all submitted feedback from Neo4j (for admin review).
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        return {"count": 0, "feedback": []}

    try:
        result = await db.execute("""
            MATCH (f:Feedback)
            RETURN f.feedback_id AS id,
                   f.timestamp AS timestamp,
                   f.category AS category,
                   f.text AS text,
                   f.tester AS tester,
                   f.session_id AS session_id,
                   f.screen AS screen,
                   f.world_id AS world_id
            ORDER BY f.timestamp DESC
            LIMIT 100
        """, {})

        feedback_list = []
        for record in result:
            feedback_list.append({
                "id": record.get("id"),
                "timestamp": record.get("timestamp"),
                "category": record.get("category"),
                "text": record.get("text"),
                "context": {
                    "tester": record.get("tester"),
                    "session_id": record.get("session_id"),
                    "screen": record.get("screen"),
                    "world_id": record.get("world_id"),
                }
            })

        return {"count": len(feedback_list), "feedback": feedback_list}
    except Exception as e:
        logger.error(f"Failed to load feedback from Neo4j: {e}")
        return {"count": 0, "feedback": []}


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class WorldSeedRequest(BaseModel):
    """Request to generate a world from a seed prompt."""
    seed_prompt: str = Field(
        ...,
        min_length=10,
        description="A brief description of the world to generate",
        examples=["A dark fantasy realm where magic corrupts its users"]
    )
    tone: Optional[str] = Field(
        default="dark fantasy",
        description="The narrative tone"
    )
    generate_entities: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of initial entities to generate"
    )


class WorldSeedResponse(BaseModel):
    """Response from world generation."""
    world_id: str
    name: str
    description: str
    entities_created: List[Dict[str, Any]]
    message: str


class SessionCreateRequest(BaseModel):
    """Request to create a new game session."""
    world_id: Optional[str] = None
    character_concept: Optional[str] = Field(
        default=None,
        description="Brief character concept for Session 0"
    )
    character_name: Optional[str] = Field(
        default=None,
        description="Character name for analytics tracking"
    )
    tester: Optional[str] = Field(
        default=None,
        description="Tester name from invite code for analytics"
    )
    setting_preference: Optional[str] = None
    tone_preference: Optional[str] = None
    genre: Optional[str] = Field(
        default="fantasy",
        description="Story genre (fantasy, romance, mystery, horror, adventure, drama)"
    )
    genres: Optional[List[str]] = Field(
        default=None,
        description="Multiple genres for blending (e.g., ['romance', 'mystery'])"
    )
    storytelling_style: Optional[str] = Field(
        default="guided",
        description="How structured: guided, freeform, or collaborative"
    )
    # D&D Rules Integration
    character_id: Optional[str] = Field(
        default=None,
        description="D&D character ID for rules-based play"
    )
    rules_mode: Optional[str] = Field(
        default="narrative",
        description="'narrative' for story-only, 'dnd' for d20 rules"
    )
    rules_visibility: Optional[str] = Field(
        default="guided",
        description="How much mechanical info to show: storyteller, guided, classic, tactician"
    )
    # Story Length / Pacing
    session_scope: Optional[str] = Field(
        default="one_shot",
        description="Story length: one_shot (~100 turns), short (~150), medium (~250), long (~400), campaign (unlimited)"
    )
    max_turns: Optional[int] = Field(
        default=100,
        description="Expected maximum turns for this story scope"
    )


class SessionResponse(BaseModel):
    """Game session information."""
    session_id: str
    status: str
    phase: str  # "session_0" or "active_play"
    created_at: datetime
    arc_status: Optional[Dict[str, Any]] = None
    # Extended fields for session context
    world_id: Optional[str] = None
    world_name: Optional[str] = None
    genre: Optional[str] = None
    genres: Optional[List[str]] = None
    rules_mode: Optional[str] = None
    rules_visibility: Optional[str] = None
    character_concept: Optional[str] = None
    character_id: Optional[str] = None
    tone_preference: Optional[str] = None


class PlayerActionRequest(BaseModel):
    """Player action input."""
    action: str = Field(..., min_length=1, max_length=2000, description="What the player does or says")
    needs_guidance: bool = Field(default=False, description="Whether player needs subtle story direction hints")
    adaptive_context: Optional[str] = Field(default=None, description="AI adaptation hints based on learned player preferences")


class GameEventData(BaseModel):
    """Structured game event for frontend notifications."""
    type: str  # ITEM_ADDED, DAMAGE_TAKEN, SKILL_CHECK, etc.
    data: Dict[str, Any] = {}
    turn: int = 0


class DMResponse(BaseModel):
    """DM response to player action."""
    narrative: str
    session_id: str
    phase: str
    arc_context: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None
    episode_status: Optional[Dict[str, Any]] = None
    # D&D Rules Integration
    mechanical_result: Optional[Dict[str, Any]] = None  # Roll results, damage, etc.
    character_update: Optional[Dict[str, Any]] = None  # HP changes, conditions, etc.
    # Structured Events for frontend notifications
    events: Optional[List[GameEventData]] = None  # ITEM_ADDED, GOLD_CHANGED, etc.
    # Session state flags
    session_ended: bool = False  # True when ONE_SHOT reaches THE END


# ============================================================
# SESSION STORE (in-memory + Neo4j persistence for continuity)
# ============================================================

_active_sessions: Dict[str, Dict[str, Any]] = {}

# GameState instances - authoritative source for character HP, inventory, combat
_game_states: Dict[str, GameState] = {}


def get_world_context_for_dm(world_id: str) -> str:
    """
    Get admin-configured world details for DM context.

    This pulls from LORE_BASES (populated by World Tuner and seed files)
    so the DM knows about the world the admin created.
    """
    if not world_id or world_id not in LORE_BASES:
        return ""

    world = LORE_BASES[world_id]
    lines = []

    lines.append("=== WORLD CONFIGURATION (Admin-Defined) ===")
    lines.append(f"World: {world.get('name', world_id)}")
    if world.get('genre'):
        lines.append(f"Genre: {world.get('genre')}")

    # Character options the admin configured (from World Tuner or generation)
    options = world.get("character_options", {})

    if options.get("origins"):
        lines.append("\nPlayable Origins (races) in this world:")
        for origin in options["origins"][:6]:
            desc = origin.get('description', '')[:80]
            lines.append(f"  - {origin['name']}: {desc}")

    if options.get("archetypes"):
        lines.append("\nPlayable Archetypes (classes) in this world:")
        for arch in options["archetypes"][:6]:
            desc = arch.get('description', '')[:80]
            lines.append(f"  - {arch['name']}: {desc}")

    if options.get("setting_skills"):
        lines.append("\nSetting-Specific Skills:")
        for skill in options["setting_skills"][:4]:
            lines.append(f"  - {skill['name']}: {skill.get('description', '')[:60]}")

    # Add instruction to use this context
    if options.get("origins") or options.get("archetypes"):
        lines.append("\nIMPORTANT: Reference these setting-specific elements naturally in your narrative.")
        lines.append("NPCs, factions, and lore should align with the world the admin designed.")

    return "\n".join(lines)


def _make_json_serializable(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    else:
        return obj


async def _persist_session_to_db(session_id: str, session: Dict[str, Any], db) -> bool:
    """
    Persist active session to Neo4j for continuity across server restarts.

    Stores the full session state as JSON so it can be recovered.
    """
    if not db:
        logger.debug(f"Session persistence skipped for {session_id}: No database connection")
        return False

    try:
        # Create serializable copy, handling non-JSON objects
        session_copy = dict(session)

        # Serialize Arc Engine state if present
        arc_engine = session.get("arc_engine")
        if arc_engine and hasattr(arc_engine, 'to_dict'):
            session_copy["arc_engine_state"] = arc_engine.to_dict()
            del session_copy["arc_engine"]  # Remove non-serializable object
        elif "arc_engine" in session_copy:
            del session_copy["arc_engine"]  # Remove if not serializable

        # Serialize character data if present
        character_id = session.get("character_id")
        if character_id and character_id in _characters:
            try:
                character = _characters[character_id]
                session_copy["character_data"] = character.model_dump()
                logger.debug(f"Persisted character data for {character_id} with session {session_id}")
            except Exception as char_err:
                logger.warning(f"Failed to serialize character {character_id}: {char_err}")

        # Recursively convert all datetime objects to ISO strings
        session_copy = _make_json_serializable(session_copy)

        await db.execute("""
            MERGE (s:ActiveSession {session_id: $session_id})
            SET s.session_data = $session_json,
                s.updated_at = datetime(),
                s.phase = $phase,
                s.character_concept = $character_concept,
                s.turn_count = $turn_count
        """, {
            "session_id": session_id,
            "session_json": json.dumps(session_copy),
            "phase": session.get("phase", "active_play"),
            "character_concept": session.get("character_concept", ""),
            "turn_count": len(session.get("history", [])) // 2,
        })
        logger.debug(f"Persisted session {session_id} to Neo4j (turn {len(session.get('history', [])) // 2})")
        return True
    except Exception as e:
        logger.error(f"Failed to persist session {session_id} to Neo4j: {e}", exc_info=True)
        return False


async def _recover_session_from_db(session_id: str, db) -> Optional[Dict[str, Any]]:
    """
    Recover a session from Neo4j if it's not in memory.

    Returns the session dict if found, None otherwise.
    """
    if not db:
        logger.debug(f"Session recovery skipped for {session_id}: No database connection")
        return None

    try:
        results = await db.execute("""
            MATCH (s:ActiveSession {session_id: $session_id})
            RETURN s.session_data as session_json
        """, {"session_id": session_id})

        if not results:
            logger.info(f"Session {session_id} not found in database (ActiveSession node)")
            return None

        session_data = json.loads(results[0]["session_json"])

        # Convert ISO string back to datetime
        if session_data.get("created_at"):
            try:
                session_data["created_at"] = datetime.fromisoformat(session_data["created_at"])
            except (ValueError, TypeError):
                session_data["created_at"] = datetime.now(timezone.utc)

        # Restore Arc Engine from saved state if available
        arc_engine_state = session_data.pop("arc_engine_state", None)
        if arc_engine_state and ARC_ENGINE_AVAILABLE:
            try:
                session_data["arc_engine"] = ArcEngine.from_dict(arc_engine_state)
                logger.debug(f"Restored Arc Engine state for session {session_id}")
            except Exception as arc_err:
                logger.warning(f"Failed to restore Arc Engine for {session_id}: {arc_err}")
                # Create fresh Arc Engine if restoration fails
                session_data["arc_engine"] = ArcEngine(session_id=session_id)
        elif ARC_ENGINE_AVAILABLE:
            # No saved state - create fresh Arc Engine
            session_data["arc_engine"] = ArcEngine(session_id=session_id)

        # Restore character from saved character_data if present
        character_data = session_data.get("character_data")
        character_id = session_data.get("character_id")
        if character_data and character_id:
            try:
                character = CharacterSheet.model_validate(character_data)
                _characters[character_id] = character
                logger.info(f"Restored character '{character.name}' (ID: {character_id}) for session {session_id}")
            except Exception as char_err:
                logger.warning(f"Failed to restore character {character_id} for session {session_id}: {char_err}")
        elif character_id and character_id not in _characters:
            logger.warning(f"Session {session_id} has character_id {character_id} but no character_data - character may not be available")

        logger.info(f"Successfully recovered session {session_id} from Neo4j database (turn {len(session_data.get('history', [])) // 2})")
        return session_data

    except Exception as e:
        logger.error(f"Failed to recover session {session_id} from Neo4j: {e}", exc_info=True)
        return None


# Global guardrails - Beta testing configuration
# Conservative daily limit ($2) to stay well within $20/month budget
_beta_budget = TokenBudget(
    max_tokens_per_session=150000,      # 150k tokens/session (~50-70 turns)
    max_requests_per_session=200,        # 200 AI calls per session
    max_requests_per_hour=300,           # 5 requests/min across all users
    max_tokens_per_hour=500000,          # 500k tokens/hour
    max_tokens_per_day=2000000,          # 2M tokens/day
    max_requests_per_day=2000,           # 2000 requests/day
    max_cost_per_session=0.50,           # $0.50 per session max
    max_cost_per_day=2.00,               # $2/day max - alerts if approaching $20/month budget
)
_token_tracker = TokenTracker(budget=_beta_budget)
_gemini_breaker = get_circuit_breaker("gemini")
_executor = ThreadPoolExecutor(max_workers=4)


async def protected_ai_call(
    model,
    prompt: str,
    session_id: str,
    temperature: float = 0.85,
    max_output_tokens: int = 500,
) -> str:
    """
    Make an AI call with token budget and circuit breaker protection.

    Raises:
        HTTPException: If budget exceeded, rate limited, or circuit open
    """
    logger.info(f"[PROTECTED] Entering protected_ai_call for session {session_id}")

    # Estimate tokens
    input_tokens = estimate_tokens(prompt)
    output_tokens = max_output_tokens  # Conservative estimate
    logger.info(f"[PROTECTED] Estimated tokens: input={input_tokens}, output={output_tokens}")

    # Check budget
    logger.info(f"[PROTECTED] Checking token budget...")
    try:
        _token_tracker.check_budget(session_id, input_tokens, output_tokens)
        logger.info(f"[PROTECTED] Budget check passed")
    except BudgetExceeded as e:
        logger.warning(f"Budget exceeded for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Usage limit reached: {str(e)}. Please try again later."
        )
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please slow down. Try again in {e.wait_seconds:.1f} seconds."
        )

    # Check circuit breaker
    logger.info(f"[PROTECTED] Checking circuit breaker...")
    try:
        _gemini_breaker.allow_request()
        logger.info(f"[PROTECTED] Circuit breaker check passed")
    except CircuitOpen as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service temporarily unavailable. Try again in {e.retry_after:.0f} seconds."
        )

    # Make the call in a thread pool to avoid blocking the event loop
    def _sync_generate():
        try:
            logger.info(f"[GEMINI] Starting generate_content for session {session_id}")
            logger.info(f"[GEMINI] Prompt length: {len(prompt)} chars")
            result = model.generate_content(
                prompt,
                generation_config={"temperature": temperature, "max_output_tokens": max_output_tokens}
            )
            logger.info(f"[GEMINI] Call completed for session {session_id}")
            return result
        except Exception as e:
            logger.error(f"[GEMINI] Sync call failed: {e}")
            raise

    try:
        logger.info(f"[GEMINI] Submitting to executor for session {session_id}")
        loop = asyncio.get_event_loop()
        # Add 45-second timeout to prevent infinite hangs
        response = await asyncio.wait_for(
            loop.run_in_executor(_executor, _sync_generate),
            timeout=45.0
        )
        logger.info(f"[GEMINI] Executor returned for session {session_id}")

        # Record success
        _gemini_breaker.record_success()

        # Record actual usage (estimate output tokens from response)
        actual_output = estimate_tokens(response.text)
        _token_tracker.record_usage(session_id, input_tokens, actual_output)

        return response.text

    except asyncio.TimeoutError:
        _gemini_breaker.record_failure()
        logger.error(f"AI call timed out for session {session_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Story generation timed out. Please try again."
        )
    except Exception as e:
        _gemini_breaker.record_failure()
        logger.error(f"AI call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}"
        )


def get_dm_agent(request: Request):
    """Get or create DM agent from app state."""
    if not hasattr(request.app.state, "dm_agent") or request.app.state.dm_agent is None:
        return None
    return request.app.state.dm_agent


# ============================================================
# D&D RULES INTEGRATION
# ============================================================

# Action keywords for detecting mechanical intent
ATTACK_KEYWORDS = ["attack", "strike", "hit", "slash", "stab", "shoot", "punch", "kick", "swing at", "fire at"]
SKILL_KEYWORDS = {
    "stealth": ["sneak", "hide", "stealth", "creep", "silently", "quietly"],
    "perception": ["look", "search", "notice", "spot", "see", "watch", "observe", "listen"],
    "athletics": ["climb", "jump", "swim", "push", "pull", "lift", "run", "sprint"],
    "acrobatics": ["flip", "tumble", "balance", "dodge", "roll"],
    "persuasion": ["convince", "persuade", "charm", "negotiate", "talk", "reason with"],
    "deception": ["lie", "bluff", "deceive", "trick", "mislead"],
    "intimidation": ["threaten", "intimidate", "scare", "frighten", "menace"],
    "insight": ["read", "sense motive", "tell if", "detect lie", "understand intention"],
    "investigation": ["investigate", "examine", "analyze", "deduce", "figure out", "search for clues"],
    "arcana": ["identify magic", "recall arcane", "recognize spell"],
    "history": ["remember", "recall history", "know about"],
    "nature": ["identify plant", "track", "forage", "identify animal"],
    "medicine": ["heal", "stabilize", "diagnose", "treat wound"],
    "survival": ["track", "hunt", "find food", "navigate", "make camp"],
}


def detect_mechanical_action(action: str) -> Optional[Dict[str, Any]]:
    """
    Detect if player action requires mechanical resolution.

    Returns:
        Dict with action_type and details, or None if purely narrative
    """
    action_lower = action.lower()

    # Check for attack intent
    for keyword in ATTACK_KEYWORDS:
        if keyword in action_lower:
            return {
                "action_type": "attack",
                "keyword": keyword,
                "raw_action": action,
            }

    # Check for skill check intent
    for skill, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            if keyword in action_lower:
                return {
                    "action_type": "skill_check",
                    "skill": skill,
                    "keyword": keyword,
                    "raw_action": action,
                }

    return None


def resolve_mechanical_action(
    action_info: Dict[str, Any],
    character,
    visibility: RulesVisibility,
) -> Dict[str, Any]:
    """
    Resolve a mechanical action using the D&D 5e engine.

    Returns:
        Dict with roll result, narrative description, and any state changes
    """
    result = {
        "action_type": action_info["action_type"],
        "rolls": [],
        "narrative_hint": "",
        "character_update": None,
    }

    if action_info["action_type"] == "attack":
        # Resolve attack against default AC (will be refined with actual targets)
        target_ac = 13  # Default moderate difficulty
        attack = CombatResolver.resolve_attack(character, target_ac)
        filtered = VisibilityFilter.filter_attack_result(attack, visibility)

        result["rolls"].append({
            "type": "attack",
            "roll": attack.attack_roll,
            "modifier": attack.attack_modifier,
            "total": attack.attack_total,
            "is_hit": attack.is_hit,
            "is_critical": attack.is_critical,
            "display": filtered.get("display", ""),
        })

        if attack.is_hit and attack.damage_roll:
            result["rolls"].append({
                "type": "damage",
                "damage": attack.damage_total,
                "damage_type": attack.damage_type,
            })

        result["narrative_hint"] = filtered.get("description", attack.narrative_outcome)

    elif action_info["action_type"] == "skill_check":
        skill = action_info["skill"]
        dc = 15  # Default moderate difficulty

        check = CheckEngine.skill_check(character, skill, dc)
        filtered = VisibilityFilter.filter_check_result(check, visibility)

        result["rolls"].append({
            "type": "skill",
            "skill": skill,
            "roll": check.roll,
            "modifier": check.modifier,
            "total": check.total,
            "dc": dc,
            "success": check.success,
            "display": filtered.get("display", ""),
        })

        result["narrative_hint"] = filtered.get("description", check.narrative_outcome)

    return result


# ============================================================
# WORLD GENERATION
# ============================================================

@router.post("/world/seed", response_model=WorldSeedResponse)
async def seed_world(
    request: Request,
    seed: WorldSeedRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Generate a new world from a seed prompt.

    Creates initial entities, locations, and lore based on the seed description.
    """
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured"
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    world_id = str(uuid.uuid4())[:8]

    # Generate world details with rich character descriptions for OCEAN extraction
    world_prompt = f"""You are a world-builder for a tabletop RPG.

Given this seed concept: "{seed.seed_prompt}"
Tone: {seed.tone}

Generate a world with:
1. An evocative name (2-4 words)
2. A rich description (2-3 paragraphs)
3. {seed.generate_entities} initial entities (mix of locations, characters, factions)

IMPORTANT: For each CHARACTER entity, include personality traits in the description using words like:
brave, cunning, loyal, vengeful, kind, cold, ambitious, cautious, impulsive, patient, calculating,
warm, charismatic, fearful, aggressive, studious, curious, forgiving, strict, creative, methodical.

Example: "Lord Aldric is calculating and ambitious, known for his cold demeanor yet kind to scholars."

Return ONLY valid JSON in this exact format:
{{
    "name": "World Name",
    "description": "Full world description...",
    "entities": [
        {{
            "name": "Entity Name",
            "type": "Location|Character|Faction|Item|Concept",
            "description": "Entity description with personality traits for characters..."
        }}
    ]
}}
"""

    try:
        # Use protected AI call with guardrails
        text = await protected_ai_call(
            model,
            world_prompt,
            session_id=f"world_{world_id}",
            temperature=0.9,
            max_output_tokens=2000,
        )

        # Parse JSON from response
        import json
        import re
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1)

        world_data = json.loads(text)

        # Build narrative text from all entity descriptions for LoreParsingAgent
        narrative_parts = [world_data.get("description", "")]
        for entity in world_data.get("entities", []):
            narrative_parts.append(f"{entity['name']} - {entity.get('description', '')}")

        full_narrative = "\n\n".join(narrative_parts)

        # Route through LoreParsingAgent for AI-powered OCEAN profile generation
        entities_created = []
        try:
            from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

            agent = LoreParsingAgent()
            logger.info(f"Processing world entities through LoreParsingAgent for OCEAN profiles")

            parse_result = await agent.parse_and_store(
                text=full_narrative,
                db=db,
                source_name=f"world:{world_id}",
                world_id=world_id,
            )

            # Map parsed entities back to response
            for entity in parse_result.entities:
                entities_created.append({
                    "canon_id": f"{world_id}_{entity.name.lower().replace(' ', '_')}",
                    "name": entity.name,
                    "type": entity.entity_type,
                })

            logger.info(
                f"LoreParsingAgent created {parse_result.entities_stored} entities, "
                f"{parse_result.characters_with_ocean} with OCEAN profiles"
            )

        except Exception as ingest_err:
            logger.warning(f"LoreParsingAgent failed, falling back to direct creation: {ingest_err}")

            # Fallback: Direct entity creation (without OCEAN profiles)
            for entity in world_data.get("entities", []):
                canon_id = f"{world_id}_{entity['name'].lower().replace(' ', '_')}"

                await db.execute("""
                    MERGE (e:Entity {canon_id: $canon_id})
                    SET e.name = $name,
                        e.entity_type = $type,
                        e.description = $description,
                        e.world_id = $world_id,
                        e.approval_status = 'PENDING',
                        e.confidence_level = 'AI_GENERATED',
                        e.created_at = datetime()
                    WITH e
                    CALL apoc.create.addLabels(e, [$type]) YIELD node
                    RETURN node
                """, {
                    "canon_id": canon_id,
                    "name": entity["name"],
                    "type": entity["type"],
                    "description": entity["description"],
                    "world_id": world_id,
                })

                entities_created.append({
                    "canon_id": canon_id,
                    "name": entity["name"],
                    "type": entity["type"],
                })

        # Store world metadata
        await db.execute("""
            MERGE (w:World {world_id: $world_id})
            SET w.name = $name,
                w.description = $description,
                w.seed_prompt = $seed_prompt,
                w.tone = $tone,
                w.created_at = datetime()
        """, {
            "world_id": world_id,
            "name": world_data["name"],
            "description": world_data["description"],
            "seed_prompt": seed.seed_prompt,
            "tone": seed.tone,
        })

        logger.info(f"Created world '{world_data['name']}' with {len(entities_created)} entities")

        return WorldSeedResponse(
            world_id=world_id,
            name=world_data["name"],
            description=world_data["description"],
            entities_created=entities_created,
            message=f"World '{world_data['name']}' created with {len(entities_created)} entities"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse world generation response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse generated world data"
        )
    except Exception as e:
        logger.error(f"World generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"World generation failed: {str(e)}"
        )


# ============================================================
# SESSION MANAGEMENT
# ============================================================

def get_optional_neo4j_db(request: Request):
    """Get Neo4j database if available, otherwise None."""
    return getattr(request.app.state, "neo4j_db", None)


@router.post("/session", response_model=SessionResponse)
async def create_session(
    request: Request,
    session_req: SessionCreateRequest,
):
    """
    Create a new game session.

    If no world_id is provided, starts in Session 0 mode to establish
    the setting collaboratively with the player.

    Validates world integrity before starting active_play sessions.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Determine initial phase
    phase = "session_0" if not session_req.world_id else "active_play"

    # World Integrity Check: Validate world before active_play
    # For Session 0 (no world_id), we allow empty world since we're building it
    # NOTE: Seed worlds (in LORE_BASES) are pre-validated JSON files - skip Neo4j check
    db = get_optional_neo4j_db(request)
    is_seed_world = session_req.world_id and session_req.world_id in LORE_BASES
    if session_req.world_id and db and not is_seed_world:
        try:
            # Validate that user-created worlds have required elements
            await require_valid_world(
                db,
                world_id=session_req.world_id,
                allow_empty=False,  # User-created worlds must be complete
            )
        except WorldNotReadyError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=e.to_dict(),
            )

    # Fetch lore_content from selected world (if any)
    # IMPORTANT: World determines genre - it's the source of truth
    world_lore_content = ""
    world_name = ""
    world_genre = None
    world_genre_hints = []
    if session_req.world_id:
        # Use the global LORE_BASES dict (loaded at startup from seed files)
        if session_req.world_id in LORE_BASES:
            world_data = LORE_BASES[session_req.world_id]
            world_lore_content = world_data.get("lore_content", "")
            world_name = world_data.get("name", "")
            # World's genre is authoritative
            world_genre = world_data.get("genre")
            world_genre_hints = world_data.get("genre_hints", [])
            if not world_genre and world_genre_hints:
                world_genre = world_genre_hints[0]
            logger.info(f"Loaded world '{session_req.world_id}': genre={world_genre}, hints={world_genre_hints}, lore={len(world_lore_content)} chars")
        else:
            # World ID provided but not found - return error instead of silently continuing
            logger.warning(f"World '{session_req.world_id}' not found in LORE_BASES")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"World '{session_req.world_id}' not found. Available worlds: {list(LORE_BASES.keys())[:10]}..."
            )

    # Validate character_id if provided (for D&D mode)
    if session_req.character_id:
        if session_req.character_id not in _characters:
            logger.warning(f"Character '{session_req.character_id}' not found in _characters")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character '{session_req.character_id}' not found. Please create a character first."
            )

    # Create a unique session-scoped world ID for entity isolation
    # This ensures each game has its own lore space, even if using the same base world
    base_world_id = session_req.world_id or "custom"
    session_world_id = f"{base_world_id}_{session_id[:8]}"

    # GENRE RESOLUTION: World is the source of truth
    # 1. If world selected → world's genre is primary
    # 2. User's genre selection can add flavor but doesn't override world
    # 3. No world → user's selection is used
    if world_genre:
        # World determines primary genre
        primary_genre = world_genre
        # Build genre list: world's hints + any user additions that aren't already included
        all_genres = list(world_genre_hints) if world_genre_hints else [world_genre]
        if session_req.genres:
            for g in session_req.genres:
                if g.lower() not in [x.lower() for x in all_genres]:
                    all_genres.append(g)
        elif session_req.genre and session_req.genre.lower() not in [x.lower() for x in all_genres]:
            all_genres.append(session_req.genre)
    else:
        # No world selected - use user's choice
        primary_genre = session_req.genre or "fantasy"
        all_genres = session_req.genres or [primary_genre]

    # Build genre blend string for storytelling
    genre_blend = primary_genre
    if len(all_genres) > 1:
        genre_blend = " + ".join(all_genres)

    session_data = {
        "session_id": session_id,
        "world_id": session_req.world_id,  # Original lore base ID (for loading seed lore)
        "session_world_id": session_world_id,  # Unique ID for this session's entities
        "world_name": world_name,
        "world_lore_content": world_lore_content,  # Store the full lore content!
        "character_concept": session_req.character_concept,
        "setting_preference": session_req.setting_preference,
        "tone_preference": session_req.tone_preference,
        "genre": primary_genre,
        "genres": all_genres,
        "genre_blend": genre_blend,
        "storytelling_style": session_req.storytelling_style or "guided",
        "phase": phase,
        "status": "active",
        "created_at": now,
        "history": [],
        "session_0_answers": {},
        # D&D Rules Integration
        "character_id": session_req.character_id,
        "rules_mode": session_req.rules_mode or "narrative",
        "rules_visibility": session_req.rules_visibility or "guided",
        # Story Length / Pacing
        "session_scope": session_req.session_scope or "one_shot",
        "max_turns": session_req.max_turns or 100,
        # Arc Engine for narrative pacing (per-session instance)
        "arc_engine": ArcEngine(session_id=session_id) if ARC_ENGINE_AVAILABLE else None,
    }

    _active_sessions[session_id] = session_data

    # Create GameState - the authoritative source for HP, inventory, combat
    character = _characters.get(session_req.character_id) if session_req.character_id else None
    game_state = GameState.create_new(
        session_id=session_id,
        world_id=session_req.world_id or "custom",
        character=character,
        starting_gold=10,
    )
    game_state.location = world_name or "Unknown"
    _game_states[session_id] = game_state
    game_state.save()  # Persist to JSON file
    logger.info(f"Created GameState for session {session_id} with character={character.name if character else 'None'}")

    # Store in Neo4j for persistence (if available)
    # This ensures story continuity even if server restarts
    db = get_optional_neo4j_db(request)
    if db:
        # Persist full session data for recovery
        await _persist_session_to_db(session_id, session_data, db)

        # Create GameSession node with full metadata for admin tracking
        try:
            await db.execute("""
                CREATE (s:GameSession {
                    session_id: $session_id,
                    world_id: $world_id,
                    session_world_id: $session_world_id,
                    phase: $phase,
                    status: 'active',
                    genre: $genre,
                    character_name: $character_name,
                    tester: $tester,
                    storytelling_style: $style,
                    is_curated_world: $is_curated,
                    curated_world_name: $curated_name,
                    turn_count: 0,
                    created_at: datetime()
                })
            """, {
                "session_id": session_id,
                "world_id": session_req.world_id or "",
                "session_world_id": session_world_id,
                "phase": phase,
                "genre": primary_genre,
                "character_name": session_req.character_name or session_req.character_concept or "",
                "tester": session_req.tester or "",
                "style": session_req.storytelling_style or "guided",
                "is_curated": bool(session_req.world_id and not session_req.world_id.startswith("custom")),
                "curated_name": session_req.world_id if session_req.world_id and not session_req.world_id.startswith("custom") else "",
            })
        except Exception as e:
            logger.warning(f"Failed to create GameSession node: {e}")

    logger.info(f"Created session {session_id} in phase {phase}")

    return SessionResponse(
        session_id=session_id,
        status="active",
        phase=phase,
        created_at=now,
        # Include full session context for frontend
        world_id=session_req.world_id,
        world_name=world_name,
        genre=primary_genre,
        genres=all_genres,
        rules_mode=session_req.rules_mode or "narrative",
        rules_visibility=session_req.rules_visibility or "guided",
        character_concept=session_req.character_concept,
        character_id=session_req.character_id,
        tone_preference=session_req.tone_preference,
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(request: Request, session_id: str):
    """Get session status and information. Recovers from database if needed."""
    session = _active_sessions.get(session_id)

    if not session:
        # Try to recover from database
        db = get_optional_neo4j_db(request)
        session = await _recover_session_from_db(session_id, db)

        if session:
            _active_sessions[session_id] = session
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )

    return SessionResponse(
        session_id=session_id,
        status=session.get("status", "active"),
        phase=session["phase"],
        created_at=session["created_at"],
        # Include full session context for frontend
        world_id=session.get("world_id"),
        world_name=session.get("world_name"),
        genre=session.get("genre"),
        genres=session.get("genres"),
        rules_mode=session.get("rules_mode"),
        rules_visibility=session.get("rules_visibility"),
        character_concept=session.get("character_concept"),
        character_id=session.get("character_id"),
        tone_preference=session.get("tone_preference"),
    )


@router.get("/session/{session_id}/inventory")
async def get_session_inventory(session_id: str):
    """Get the current inventory for a session from GameState."""
    # Try to get game state from memory
    game_state = _game_states.get(session_id)

    # Try to load from disk if not in memory
    if not game_state:
        game_state = GameState.load(session_id)
        if game_state:
            _game_states[session_id] = game_state

    if not game_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or has no game state"
        )

    # Build inventory response
    inventory_data = game_state.inventory.to_dict()

    return {
        "session_id": session_id,
        "items": inventory_data.get("items", []),
        "gold": inventory_data.get("gold", 0),
        "silver": inventory_data.get("silver", 0),
        "copper": inventory_data.get("copper", 0),
        "equipped": inventory_data.get("equipped", {}),
        "item_count": len(inventory_data.get("items", [])),
    }


@router.get("/session/{session_id}/character")
async def get_session_character(session_id: str):
    """Get the current character state for a session from GameState."""
    game_state = _game_states.get(session_id)

    if not game_state:
        game_state = GameState.load(session_id)
        if game_state:
            _game_states[session_id] = game_state

    if not game_state or not game_state.character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or has no character"
        )

    char = game_state.character
    return {
        "session_id": session_id,
        "name": char.name,
        "origin": char.race,
        "archetype": char.archetype,
        "level": char.level,
        "hp": char.current_hit_points,
        "max_hp": char.max_hit_points,
        "temp_hp": char.temporary_hit_points,
        "armor_class": char.armor_class,
        "conditions": char.conditions,
        "power_slots_max": char.power_slots_max,
        "power_slots_used": char.power_slots_used,
    }


@router.post("/session/{session_id}/action", response_model=DMResponse)
async def process_action(
    request: Request,
    session_id: str,
    action: PlayerActionRequest,
):
    """
    Process a player action and return the DM's response.

    Handles both Session 0 (world-building) and active play.
    Integrates D&D 5e rules when a character is present.

    Session Recovery: If session is not in memory (e.g., after server restart),
    attempts to recover from Neo4j database to maintain story continuity.
    """
    logger.info(f"Action request received for session {session_id}")

    # Get database connection first (needed for session recovery)
    db = get_optional_neo4j_db(request)

    # Try to get session from memory, or recover from database
    session = _active_sessions.get(session_id)

    if not session:
        # Session not in memory - try to recover from Neo4j
        logger.info(f"Session {session_id} not in memory, attempting recovery from database...")
        session = await _recover_session_from_db(session_id, db)

        if session:
            # Successfully recovered - restore to memory
            _active_sessions[session_id] = session
            logger.info(f"Session {session_id} recovered successfully - story continuity maintained")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found. Please start a new story or load a saved game."
            )

    # Get or recover GameState (the authoritative source for HP, inventory, combat)
    game_state = _game_states.get(session_id)
    if not game_state:
        # Try to load from disk
        game_state = GameState.load(session_id)
        if game_state:
            _game_states[session_id] = game_state
            logger.info(f"GameState recovered from disk for session {session_id}")
        else:
            # Create new if doesn't exist (legacy sessions)
            character = _characters.get(session.get("character_id")) if session.get("character_id") else None
            game_state = GameState.create_new(
                session_id=session_id,
                world_id=session.get("world_id", "custom"),
                character=character,
            )
            _game_states[session_id] = game_state
            logger.info(f"Created new GameState for legacy session {session_id}")

    model = get_gemini_model()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured"
        )

    logger.info(f"Processing action for session {session_id}: {action.action[:50]}...")

    # D&D Rules Integration - detect and resolve mechanical actions
    mechanical_result = None
    character_update = None
    mechanical_context = ""

    if session.get("rules_mode") == "dnd" and session.get("character_id"):
        character = _characters.get(session["character_id"])
        if character:
            # Detect mechanical action
            action_info = detect_mechanical_action(action.action)
            if action_info:
                try:
                    visibility = RulesVisibility(session.get("rules_visibility", "guided"))
                    mechanical_result = resolve_mechanical_action(action_info, character, visibility)

                    # Build context for AI narrative
                    if mechanical_result.get("rolls"):
                        roll = mechanical_result["rolls"][0]
                        if roll.get("type") == "attack":
                            if roll.get("is_hit"):
                                dmg = mechanical_result["rolls"][1]["damage"] if len(mechanical_result["rolls"]) > 1 else 0
                                mechanical_context = f"[MECHANICAL: Attack HIT for {dmg} damage. Incorporate this success into your narrative.]"
                            else:
                                mechanical_context = "[MECHANICAL: Attack MISSED. Describe the miss narratively.]"
                        elif roll.get("type") == "skill":
                            if roll.get("success"):
                                mechanical_context = f"[MECHANICAL: {roll['skill'].title()} check SUCCEEDED. The character accomplishes their goal.]"
                            else:
                                mechanical_context = f"[MECHANICAL: {roll['skill'].title()} check FAILED. Describe a complication or setback.]"

                    logger.info(f"Mechanical action resolved: {mechanical_result['action_type']}")

                    # APPLY MECHANICAL RESULTS TO GAME STATE
                    # This is where damage actually affects HP!
                    if mechanical_result.get("rolls") and game_state:
                        for roll in mechanical_result["rolls"]:
                            if roll.get("type") == "attack" and roll.get("is_hit"):
                                # Find the damage roll
                                dmg_roll = next(
                                    (r for r in mechanical_result["rolls"] if r.get("type") == "damage"),
                                    None
                                )
                                if dmg_roll:
                                    damage = dmg_roll.get("total") or dmg_roll.get("damage", 0)
                                    target = roll.get("target", "enemy")
                                    # Apply damage to target (NPC/enemy)
                                    # For now we track this in the mechanical_context for the DM
                                    logger.info(f"[COMBAT] Player dealt {damage} damage to {target}")
                                    # If we have a tracked enemy, apply it
                                    try:
                                        if target in game_state.active_npcs or target in game_state.combat.combatants:
                                            game_state.apply_damage_to_npc(target, damage, source="player")
                                    except ValueError:
                                        pass  # Target not tracked yet

                except Exception as e:
                    logger.warning(f"Failed to resolve mechanical action: {e}")

    # Add action to history
    session["history"].append({"role": "user", "content": action.action})

    # Handle Session 0 (collaborative world-building)
    arc_context = None  # Arc Engine context for narrative pacing
    if session["phase"] == "session_0":
        response_text, new_phase = await _handle_session_0(
            session, action.action, model, db
        )
        session["phase"] = new_phase
    else:
        # Active play - generate DM response (with mechanical context if applicable)
        response_text, arc_context = await _handle_active_play(
            session, action.action, model, db, mechanical_context,
            needs_guidance=action.needs_guidance,
            adaptive_context=action.adaptive_context,
            game_state=game_state,  # Pass game state for context injection
        )

    # Add response to history
    session["history"].append({"role": "assistant", "content": response_text})

    # Extract and store lore entities from the narrative (fire-and-forget)
    # Store both session_world_id (for isolation) and original world_id (for curated world filtering)
    asyncio.create_task(
        extract_and_store_gameplay_lore(
            response_text,
            session_id,
            db,
            world_id=session.get("session_world_id"),  # Session-scoped, for isolation
            curated_world_id=session.get("world_id"),  # Original curated world ID, for filtering
            genre=session.get("genre", "fantasy"),
            character_name=session.get("character_name"),
        )
    )

    # Generate context-aware action suggestions
    # Only for guided storytelling style
    suggested_actions = None
    if session.get("storytelling_style") == "guided":
        # Determine player mode from rules visibility
        rules_vis = session.get("rules_visibility", "storyteller")
        player_mode = "ttrpg" if rules_vis == "tactician" else "quick_start"

        # Get character class if available
        character_class = None
        if session.get("character_id"):
            character = _characters.get(session["character_id"])
            if character:
                character_class = character.archetype

        # Get arc phase and tension from arc context
        arc_phase = arc_context.get("current_phase") if arc_context else None
        tension = 0.5  # Default medium tension
        if arc_context:
            tension_level = arc_context.get("tension_level", "medium")
            tension = {"low": 0.3, "medium": 0.5, "high": 0.8, "climax": 1.0}.get(tension_level, 0.5)

        suggested_actions = generate_action_suggestions(
            narrative=response_text,
            mode=player_mode,
            character_class=character_class,
            arc_phase=arc_phase,
            tension=tension,
            max_suggestions=5,
        )

    # Extract structured events from narrative for frontend
    turn_count = len(session.get("history", [])) // 2
    events = _extract_events_from_narrative(response_text, mechanical_result, turn_count)

    # EXTRACT STATE CHANGES FROM NARRATIVE AND APPLY TO GAME STATE
    # This catches items picked up, gold found, damage mentioned in narrative
    if game_state:
        state_changes = _extract_state_changes_from_narrative(response_text, game_state)
        if state_changes:
            logger.info(f"[STATE] Applied {len(state_changes)} state changes from narrative: {state_changes}")

        # Add to history and advance turn
        game_state.add_to_history("user", action.action)
        game_state.add_to_history("assistant", response_text)
        game_state.advance_turn()

        # Save game state to disk (authoritative state)
        game_state.save()

        # Build character_update from actual game state
        if game_state.character:
            character_update = {
                "hp": game_state.character.current_hit_points,
                "max_hp": game_state.character.max_hit_points,
                "temp_hp": game_state.character.temporary_hit_points,
                "conditions": game_state.character.conditions,
                "gold": game_state.inventory.gold,
                "item_count": len(game_state.inventory.items),
            }

        # Get events from game state (merged with narrative events)
        state_events = game_state.flush_events()
        if state_events:
            # Convert to dicts and merge with narrative events
            state_event_dicts = [e.to_dict() for e in state_events]
            events = (events or []) + state_event_dicts

    # Detect session ending (THE END marker for ONE_SHOT mode)
    session_ended = "**THE END**" in response_text or "THE END" in response_text.upper()
    if session_ended:
        session["status"] = "ended"

    # Persist session to database for continuity across server restarts
    # This ensures the story is never lost
    asyncio.create_task(_persist_session_to_db(session_id, session, db))

    # Update GameSession node with turn count and last activity
    # IMPORTANT: Await this to ensure turn_count is actually saved
    if db:
        try:
            await db.execute("""
                MATCH (s:GameSession {session_id: $session_id})
                SET s.turn_count = $turn_count,
                    s.last_activity = datetime(),
                    s.status = $status
            """, {
                "session_id": session_id,
                "turn_count": turn_count,
                "status": "ended" if session_ended else "active",
            })
        except Exception as e:
            logger.error(f"Failed to update session turn_count: {e}")

    return DMResponse(
        narrative=response_text,
        session_id=session_id,
        phase=session["phase"],
        arc_context=arc_context,
        mechanical_result=mechanical_result,
        character_update=character_update,
        suggested_actions=suggested_actions,
        events=events if events else None,
        session_ended=session_ended,
    )


async def _handle_session_0(
    session: Dict[str, Any],
    player_input: str,
    model,
    db: Neo4jDatabase,
) -> tuple[str, str]:
    """Handle Session 0 collaborative world-building."""
    answers = session.get("session_0_answers", {})

    # Check if UI already provided the answers via session creation
    # If so, skip the questions and generate the opening directly
    has_setting = session.get("setting_preference") or answers.get("setting")
    has_character = session.get("character_concept") or answers.get("character")
    has_tone = session.get("tone_preference") or answers.get("tone")

    # If we have all the info from the UI, generate opening immediately
    if has_setting or has_character or has_tone:
        # Populate answers from session data for the opening generator
        if not answers.get("setting") and session.get("setting_preference"):
            answers["setting"] = session["setting_preference"]
        if not answers.get("character") and session.get("character_concept"):
            answers["character"] = session["character_concept"]
        if not answers.get("tone") and session.get("tone_preference"):
            answers["tone"] = session["tone_preference"]
        session["session_0_answers"] = answers

        # Generate opening scene directly
        opening = await _generate_opening(session, model)
        return opening, "active_play"

    # Fallback: If no UI data, ask questions conversationally
    if "setting" not in answers:
        answers["setting"] = player_input
        session["session_0_answers"] = answers
        return (
            f"*The mists part to reveal {player_input}...*\n\n"
            "**Who are you in this world?**\n\n"
            "*A weathered soldier? A curious scholar? A desperate thief?*",
            "session_0"
        )

    elif "character" not in answers:
        answers["character"] = player_input
        session["session_0_answers"] = answers
        return (
            f"*{player_input}... the world takes shape around you.*\n\n"
            "**What kind of story shall we tell?**\n\n"
            "*A grim tale of survival? A mystery to unravel? An epic quest?*",
            "session_0"
        )

    elif "tone" not in answers:
        answers["tone"] = player_input
        session["session_0_answers"] = answers

        # Generate opening scene
        opening = await _generate_opening(session, model)

        return opening, "active_play"

    return "Session 0 complete. Begin your adventure.", "active_play"


def _extract_events_from_narrative(
    narrative: str,
    mechanical_result: Optional[Dict[str, Any]],
    turn: int,
) -> List[GameEventData]:
    """
    Extract structured game events from narrative text and mechanical results.

    Detects:
    - Item acquisitions (finds, picks up, receives)
    - Gold changes (coins, gold, money)
    - Skill checks (from mechanical_result)
    - Damage (from mechanical_result)

    Returns:
        List of GameEventData for frontend rendering
    """
    import re
    events = []

    # Patterns for item acquisition
    item_patterns = [
        r"(?:find|pick up|receive|acquire|discover|obtain|grab|take)s?\s+(?:a|an|the|some)?\s*([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
        r"(?:a|an|the)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)\s+(?:is now yours|added to your inventory)",
    ]

    for pattern in item_patterns:
        matches = re.findall(pattern, narrative, re.IGNORECASE)
        for item_name in matches:
            # Filter out common false positives
            if item_name.lower() not in ["the", "a", "an", "you", "your", "they", "their"]:
                events.append(GameEventData(
                    type="ITEM_ADDED",
                    data={"item": item_name.strip(), "quantity": 1},
                    turn=turn,
                ))

    # Extract gold/coins from narrative
    gold_pattern = r"(\d+)\s*(?:gold|coins?|gp|gold pieces)"
    gold_matches = re.findall(gold_pattern, narrative, re.IGNORECASE)
    for amount_str in gold_matches:
        try:
            amount = int(amount_str)
            events.append(GameEventData(
                type="GOLD_CHANGED",
                data={"amount": amount},
                turn=turn,
            ))
        except ValueError:
            pass

    # Extract events from mechanical results
    if mechanical_result and mechanical_result.get("rolls"):
        for roll in mechanical_result["rolls"]:
            if roll.get("type") == "skill":
                events.append(GameEventData(
                    type="SKILL_CHECK",
                    data={
                        "skill": roll.get("skill", "unknown"),
                        "roll": roll.get("roll", 0),
                        "modifier": roll.get("modifier", 0),
                        "total": roll.get("total", 0),
                        "dc": roll.get("dc", 0),
                        "success": roll.get("success", False),
                    },
                    turn=turn,
                ))
            elif roll.get("type") == "attack":
                events.append(GameEventData(
                    type="ATTACK_ROLL",
                    data={
                        "roll": roll.get("roll", 0),
                        "modifier": roll.get("modifier", 0),
                        "total": roll.get("total", 0),
                        "is_hit": roll.get("is_hit", False),
                    },
                    turn=turn,
                ))
            elif roll.get("type") == "damage":
                events.append(GameEventData(
                    type="DAMAGE_DEALT",
                    data={
                        "damage": roll.get("damage", 0),
                        "damage_type": roll.get("damage_type", "unknown"),
                    },
                    turn=turn,
                ))

    return events


def _extract_state_changes_from_narrative(narrative: str, game_state: GameState) -> List[Dict[str, Any]]:
    """
    Parse narrative for state-changing events and APPLY them to game state.

    Supports two modes:
    1. STRUCTURED TAGS (preferred) - [ACQUIRED: ...], [GOLD: ...], [DAMAGE: ...], [HEAL: ...]
    2. REGEX FALLBACK - Natural language parsing for narratives without tags

    Tag Formats:
        [ACQUIRED: Item Name]
        [ACQUIRED: Item Name, rarity]
        [ACQUIRED: Item Name, rarity, type]
        [ACQUIRED: Item Name, rarity, type, slot]
        [GOLD: 50]
        [CURRENCY: silver, 25]
        [DAMAGE: 8]
        [DAMAGE: 8, fire]
        [HEAL: 10]

    Args:
        narrative: The DM's narrative response
        game_state: The GameState to mutate

    Returns:
        List of changes that were applied
    """
    import re
    changes = []

    # =================================================================
    # PHASE 1: Parse structured tags (preferred, explicit)
    # =================================================================

    # [ACQUIRED: Item Name] or [ACQUIRED: Item Name, rarity, type, slot]
    acquired_pattern = r'\[ACQUIRED:\s*([^\]]+)\]'
    acquired_matches = re.findall(acquired_pattern, narrative, re.IGNORECASE)
    for match in acquired_matches:
        parts = [p.strip() for p in match.split(',')]
        item_name = parts[0] if parts else ""
        rarity = parts[1] if len(parts) > 1 else "common"
        item_type = parts[2] if len(parts) > 2 else "misc"
        slot = parts[3] if len(parts) > 3 else "none"

        if item_name and len(item_name) >= 2:
            try:
                item = Item(
                    name=item_name,
                    quantity=1,
                    item_type=item_type,
                    rarity=rarity,
                    equipment_slot=slot,
                )
                game_state.add_item(item)
                changes.append({
                    "type": "item_added",
                    "item": item_name,
                    "rarity": rarity,
                    "item_type": item_type,
                    "source": "structured_tag",
                })
                logger.info(f"[ACQUIRED] Added item via tag: {item_name} ({rarity} {item_type})")
            except Exception as e:
                logger.warning(f"Failed to add item from tag '{match}': {e}")

    # [GOLD: amount] or [CURRENCY: type, amount]
    gold_tag_pattern = r'\[GOLD:\s*(\d+)\]'
    gold_tag_matches = re.findall(gold_tag_pattern, narrative, re.IGNORECASE)
    for match in gold_tag_matches:
        try:
            amount = int(match)
            if 0 < amount < 100000:
                game_state.add_gold(amount)
                changes.append({"type": "gold_added", "amount": amount, "source": "structured_tag"})
                logger.info(f"[GOLD] Added {amount} gold via tag")
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to add gold from tag: {e}")

    currency_tag_pattern = r'\[CURRENCY:\s*(\w+)\s*,\s*(\d+)\]'
    currency_tag_matches = re.findall(currency_tag_pattern, narrative, re.IGNORECASE)
    for currency_type, amount_str in currency_tag_matches:
        try:
            amount = int(amount_str)
            if 0 < amount < 100000:
                game_state.inventory.add_currency(currency_type.lower(), amount, game_state.turn_count)
                changes.append({
                    "type": "currency_added",
                    "currency": currency_type.lower(),
                    "amount": amount,
                    "source": "structured_tag",
                })
                logger.info(f"[CURRENCY] Added {amount} {currency_type} via tag")
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to add currency from tag: {e}")

    # [DAMAGE: amount] or [DAMAGE: amount, type]
    damage_tag_pattern = r'\[DAMAGE:\s*(\d+)(?:\s*,\s*(\w+))?\]'
    damage_tag_matches = re.findall(damage_tag_pattern, narrative, re.IGNORECASE)
    for amount_str, damage_type in damage_tag_matches:
        try:
            amount = int(amount_str)
            if 0 < amount < 1000:
                game_state.apply_damage_to_player(amount, source=damage_type or "narrative")
                changes.append({
                    "type": "damage_taken",
                    "amount": amount,
                    "damage_type": damage_type or "untyped",
                    "source": "structured_tag",
                })
                logger.info(f"[DAMAGE] Applied {amount} {damage_type or 'untyped'} damage via tag")
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to apply damage from tag: {e}")

    # [HEAL: amount]
    heal_tag_pattern = r'\[HEAL:\s*(\d+)\]'
    heal_tag_matches = re.findall(heal_tag_pattern, narrative, re.IGNORECASE)
    for match in heal_tag_matches:
        try:
            amount = int(match)
            if 0 < amount < 1000:
                game_state.heal_player(amount, source="narrative")
                changes.append({"type": "healed", "amount": amount, "source": "structured_tag"})
                logger.info(f"[HEAL] Applied {amount} healing via tag")
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to apply healing from tag: {e}")

    # =================================================================
    # PHASE 2: Fallback to regex parsing (for backwards compatibility)
    # Only if no structured tags were found
    # =================================================================

    if not changes:
        # Item pickup patterns - look for things the player received
        item_patterns = [
            r"(?:you\s+)?(?:find|pick up|receive|acquire|take|grab|obtain|discover)s?\s+(?:a|an|the|some)?\s*([A-Z][a-z]+(?:\s+[a-z]+)*)",
            r"(?:hands? you|gives? you|rewards? you with|presents? you with)\s+(?:a|an|the|some)?\s*([A-Z][a-z]+(?:\s+[a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[a-z]+)*)\s+(?:is now yours|added to your inventory|goes into your pack)",
        ]

        for pattern in item_patterns:
            matches = re.findall(pattern, narrative, re.IGNORECASE)
            for match in matches:
                item_name = match.strip()
                # Filter out false positives
                if len(item_name) < 3 or len(item_name) > 50:
                    continue
                if item_name.lower() in ["the", "a", "an", "you", "your", "they", "their", "it", "them", "this"]:
                    continue
                # Add to inventory
                try:
                    game_state.add_item_by_name(item_name)
                    changes.append({"type": "item_added", "item": item_name, "source": "regex_fallback"})
                except Exception as e:
                    logger.warning(f"Failed to add item '{item_name}': {e}")

        # Gold patterns
        gold_pattern = r"(?:you\s+)?(?:find|receive|earn|collect|take|obtain)\s+(\d+)\s*(?:gold|gp|coins?|gold pieces)"
        gold_matches = re.findall(gold_pattern, narrative, re.IGNORECASE)
        for match in gold_matches:
            try:
                amount = int(match)
                if amount > 0 and amount < 10000:  # Sanity check
                    game_state.add_gold(amount)
                    changes.append({"type": "gold_added", "amount": amount, "source": "regex_fallback"})
            except (ValueError, Exception) as e:
                logger.warning(f"Failed to add gold: {e}")

        # Damage taken patterns (enemy attacks hitting player)
        damage_patterns = [
            r"(?:you\s+)?(?:take|suffer|receive)s?\s+(\d+)\s*(?:points? of)?\s*(?:damage|hit points?)",
            r"(?:deals?|inflicts?|causes?)\s+(\d+)\s*(?:points? of)?\s*damage\s+(?:to you|against you)",
            r"strikes? you for\s+(\d+)\s*damage",
        ]

        for pattern in damage_patterns:
            matches = re.findall(pattern, narrative, re.IGNORECASE)
            for match in matches:
                try:
                    amount = int(match)
                    if amount > 0 and amount < 500:  # Sanity check
                        game_state.apply_damage_to_player(amount, source="narrative")
                        changes.append({"type": "damage_taken", "amount": amount, "source": "regex_fallback"})
                except (ValueError, Exception) as e:
                    logger.warning(f"Failed to apply damage: {e}")

        # Healing patterns
        heal_patterns = [
            r"(?:you\s+)?(?:heal|recover|regain)s?\s+(\d+)\s*(?:hit points?|hp|health)",
            r"restores?\s+(\d+)\s*(?:hit points?|hp|health)",
        ]

        for pattern in heal_patterns:
            matches = re.findall(pattern, narrative, re.IGNORECASE)
            for match in matches:
                try:
                    amount = int(match)
                    if amount > 0 and amount < 500:  # Sanity check
                        game_state.heal_player(amount, source="narrative")
                        changes.append({"type": "healed", "amount": amount, "source": "regex_fallback"})
                except (ValueError, Exception) as e:
                    logger.warning(f"Failed to apply healing: {e}")

    return changes


def _get_story_scope_guidance(scope: str, turn_count: int, max_turns: int) -> str:
    """
    Get pacing guidance based on story scope and current progress.

    IMPORTANT: Different scopes use DIFFERENT narrative structures:
    - One-shots: Compressed 5-act (Hook → Complication → Rising → Climax → Resolution)
    - Campaigns: Full Hero's Journey (12 stages across many sessions)
    """
    if max_turns <= 0:
        max_turns = 1000  # Campaign mode - no real limit

    progress = turn_count / max_turns if max_turns > 0 else 0

    # CAMPAIGNS: Subtle, principle-based guidance (not prescriptive)
    if scope == "campaign":
        # Early campaign: focus on foundation, not structure
        if turn_count < 20:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
Let them LIVE in this world first. No rush.
- Who are they? What do they care about? Who do they know?
- Small moments reveal character better than grand events
- Plant seeds casually - a name mentioned, a detail noticed
- Trust that significance will emerge from play"""
        elif turn_count < 50:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
The world is taking shape through their choices.
- Consequences ripple from earlier decisions
- Recurring faces, familiar places, building history
- Threads can dangle - not everything resolves quickly
- Let their interests guide what becomes important"""
        else:
            return f"""
=== CAMPAIGN (Turn {turn_count}) ===
A story is emerging from the accumulated choices.
- Honor what came before - callbacks reward attention
- Subplots can simmer, main threads can breathe
- Not every session needs crisis - quiet moments matter
- The shape of their journey reveals itself through play"""

    # ONE-SHOTS: Compressed structure, immediate engagement
    if scope == "one_shot":
        if progress < 0.10:
            phase = "HOOK"
            guidance = "Drop them into the moment. Character through action, not backstory. Something immediately interesting."
        elif progress < 0.25:
            phase = "COMPLICATION"
            guidance = "The situation demands response. A choice, a problem, a discovery. Personal stakes, clear and present."
        elif progress < 0.60:
            phase = "RISING TENSION"
            guidance = "Consequences compound. Choices matter. Tension builds through what they DO, not destiny."
        elif progress < 0.85:
            phase = "CLIMAX"
            guidance = "The confrontation. Everything comes to a head. This is what it's all been building toward."
        else:
            phase = "RESOLUTION"
            guidance = "Aftermath and change. Show who they've become. END with '**THE END**' when the story is complete."

        return f"""
=== STORY: ONE-SHOT ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}
REMEMBER: One-shots are COMPLETE stories. No sequel-baiting. Satisfying endings."""

    # SHORT/MEDIUM: Slightly expanded structure
    if scope in ("short", "medium"):
        if progress < 0.12:
            phase = "OPENING"
            guidance = "Establish character and world through lived experience. Who they are before anything changes."
        elif progress < 0.25:
            phase = "INCITING"
            guidance = "Something disrupts the ordinary. A choice to engage."
        elif progress < 0.50:
            phase = "RISING"
            guidance = "Complications. Allies and enemies. Stakes rise through consequence."
        elif progress < 0.75:
            phase = "CRISIS"
            guidance = "A major turning point. Something changes that can't be undone."
        elif progress < 0.90:
            phase = "CLIMAX"
            guidance = "The confrontation approaches and peaks."
        else:
            phase = "RESOLUTION"
            guidance = "Aftermath. Change. Consider ending with '**THE END**'."

        label = "SHORT STORY" if scope == "short" else "MEDIUM ADVENTURE"
        return f"""
=== STORY: {label} ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}"""

    # LONG: More room for development, closer to campaign pacing
    if scope == "long":
        if progress < 0.10:
            phase = "ORDINARY WORLD"
            guidance = "Establish who they are, what they want, what's missing."
        elif progress < 0.20:
            phase = "CALL"
            guidance = "Something beckons. A problem, opportunity, or discovery."
        elif progress < 0.35:
            phase = "THRESHOLD"
            guidance = "They commit. Cross into the unknown. No going back."
        elif progress < 0.50:
            phase = "TESTS & ALLIES"
            guidance = "Challenges, new relationships, learning the rules of this new world."
        elif progress < 0.65:
            phase = "ORDEAL"
            guidance = "The major crisis. Face what they fear. Transformation."
        elif progress < 0.80:
            phase = "REWARD & ROAD BACK"
            guidance = "They've changed. Now they must return with what they've gained."
        elif progress < 0.90:
            phase = "RESURRECTION"
            guidance = "Final test. Everything on the line. Who have they become?"
        else:
            phase = "RETURN"
            guidance = "Resolution. The world changed, or they have. Consider '**THE END**'."

        return f"""
=== STORY: EXTENDED ({turn_count}/{max_turns} turns, {progress:.0%}) ===
Phase: {phase}
{guidance}"""

    # Fallback
    return f"Turn: {turn_count}/{max_turns}"


def _get_genre_guidance(genre: str) -> Dict[str, str]:
    """Get narrative guidance specific to each genre.

    IMPORTANT: 'magic' field explicitly defines whether supernatural elements exist.
    - "yes": Magic/supernatural is core to the genre
    - "no": Grounded in reality - NO magic, NO supernatural (enforce strictly)
    - "optional": Can include supernatural horror OR psychological horror
    """
    guidance = {
        "fantasy": {
            "elements": "magic, mystical creatures, wonder, the impossible made real",
            "hooks": "something unexpected that demands attention - a person, an event, a discovery, or a problem",
            "voice": "evocative and wondrous, grounded in character rather than destiny",
            "magic": "yes",
        },
        "romance": {
            "elements": "emotional tension, meaningful glances, past connections, unspoken feelings",
            "hooks": "a moment of connection or tension with another person",
            "voice": "warm and intimate, focused on feelings and connections between people",
            "magic": "no",
        },
        "mystery": {
            "elements": "clues, secrets, suspicious characters, hidden motives, puzzles",
            "hooks": "something that feels wrong or out of place",
            "voice": "atmospheric and intriguing, building tension through details",
            "magic": "no",
        },
        "horror": {
            "elements": "dread, the unknown, isolation, things not quite right, building unease",
            "hooks": "a subtle wrongness that grows more unsettling",
            "voice": "unsettling and atmospheric, letting imagination fill the shadows",
            "magic": "optional",
        },
        "adventure": {
            "elements": "exploration, discovery, challenges, exotic locations, bold action",
            "hooks": "an opportunity or challenge that beckons",
            "voice": "exciting and propulsive, full of momentum and possibility",
            "magic": "no",
        },
        "drama": {
            "elements": "complex relationships, moral dilemmas, personal stakes, family secrets",
            "hooks": "a moment of emotional weight or decision",
            "voice": "emotionally resonant, focused on human complexity and growth",
            "magic": "no",
        },
        "urban_fantasy": {
            "elements": "hidden magic in modern cities, secret societies, mundane meets magical, parallel supernatural world, magical creatures disguised among humans",
            "hooks": "the veil between worlds thinning, a magical intrusion into normal life, or discovering the truth behind the mundane",
            "voice": "grounded in familiar reality but threaded with wonder and danger, where the magical world exists alongside our own",
            "magic": "yes",
        },
        "gothic": {
            "elements": "vampires, werewolves, mages, supernatural politics, personal horror, the beast within, ancient conspiracies, tragic immortality",
            "hooks": "a threat to one's humanity, a breach in the supernatural order, or the eternal struggle between monster and man",
            "voice": "dark and atmospheric, where monsters are the protagonists wrestling with their nature, and power comes at a terrible cost",
            "magic": "yes",
        },
    }
    return guidance.get(genre, guidance["fantasy"])


def _get_style_instructions(style: str) -> str:
    """Get storytelling instructions based on user's preferred style."""
    styles = {
        "guided": """
Provide clear narrative direction with vivid description. Help the reader feel
oriented in the world. End scenes at natural pause points, letting the reader
decide what to do next. NEVER suggest specific choices or ask questions.""",
        "freeform": """
Create a rich sandbox. Describe the environment with enough detail to spark
curiosity. Let the reader discover what catches their interest. End naturally
without prompting. NEVER suggest specific choices or ask questions.""",
        "collaborative": """
Build the story together through natural narrative flow. Describe the world
vividly and let moments breathe. End at natural pause points, trusting the
reader to respond. NEVER suggest specific choices or ask direct questions.""",
    }
    return styles.get(style, styles["guided"])


def _get_guidance_instruction(needs_guidance: bool) -> str:
    """Get optional story guidance instruction when player seems stuck."""
    if needs_guidance:
        return """
GUIDANCE MODE: The player seems uncertain about what to do next. Without railroading:
- Weave a subtle hint into the narrative about possible directions
- Have an NPC mention something relevant, or describe an environmental detail that suggests action
- Keep it natural - the player should feel they discovered the option, not that it was handed to them
Example: Instead of "You should go to the tavern", use "The distant sound of laughter drifts from the tavern's open windows"
"""
    return ""


async def _generate_opening(session: Dict[str, Any], model) -> str:
    """Generate an opening that matches the user's genre, tone, and style."""
    logger.info(f"[OPENING] Starting _generate_opening for session {session.get('session_id', 'unknown')}")

    answers = session.get("session_0_answers", {})
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))
    world_lore = session.get("world_lore_content", "")
    world_name = session.get("world_name", "")

    # Get story scope for pacing guidance
    session_scope = session.get("session_scope", "one_shot")
    max_turns = session.get("max_turns", 100)
    turn_count = len(session.get("history", [])) // 2  # Rough turn count

    logger.info(f"[OPENING] genre={genre}, tone={tone}, style={style}, scope={session_scope}, world_lore_len={len(world_lore)}")

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)
    scope_guidance = _get_story_scope_guidance(session_scope, turn_count, max_turns)

    # Get world rules from session (user's explicit choice) or fall back to genre defaults
    world_rules = session.get("world_rules", {})
    has_magic = world_rules.get("magic", genre_info.get("magic") == "yes")
    has_supernatural = world_rules.get("supernatural", genre_info.get("magic") in ["yes", "optional"])
    is_grounded = world_rules.get("grounded", genre_info.get("magic") == "no")

    # Build magic/realism guidance based on user's world rules
    if has_magic and has_supernatural:
        magic_guidance = """
WORLD RULES - MAGIC & SUPERNATURAL:
- Magic exists in this world as a real force
- Supernatural beings and phenomena are possible
- The impossible can become reality through magical means"""
    elif has_magic:
        magic_guidance = """
WORLD RULES - MAGIC EXISTS:
- Magic exists in this world as a real force
- Focus on magic systems rather than ghosts/monsters
- The impossible can become reality through magical means"""
    elif has_supernatural:
        magic_guidance = """
WORLD RULES - SUPERNATURAL:
- Supernatural forces exist (ghosts, spirits, monsters, curses)
- Magic as a learnable system does NOT exist
- Horror and the uncanny are valid, but not wizard spells"""
    elif is_grounded:
        magic_guidance = """
REALISM CONSTRAINT - THIS IS A GROUNDED WORLD:
- NO magic, NO supernatural elements, NO fantasy creatures
- Everything must have a real-world explanation
- No prophetic dreams, mystical abilities, or unexplained phenomena
- Keep it grounded in reality"""
    else:
        magic_guidance = ""  # No specific constraints

    # Build world context from lore_content if available
    world_context = ""
    if world_lore:
        # Truncate if too long, but include substantial context
        lore_excerpt = world_lore[:3000] if len(world_lore) > 3000 else world_lore
        world_context = f"""
WORLD: {world_name}
The following is the established lore for this world. Use these characters, locations, and details:

{lore_excerpt}

IMPORTANT: Stay true to these characters and this setting. The player is entering THIS world with THESE people."""

    prompt = f"""You are a master storyteller, beginning someone's story.

YOUR JOB: Understand what experience they're seeking - not just what they say, but what they actually want to feel. Read their character concept for the fantasy underneath. A "humble farmer" wants the underdog journey. A "legendary warrior" wants to feel powerful. An "orphan with mysterious past" wants to discover they're special. Give them the story they came for.
{scope_guidance}

GENRE: {genre.upper()}
Genre elements: {genre_info['elements']}
Voice: {genre_info['voice']}
{magic_guidance}

TONE: {tone}
{style_instructions}
{world_context}

SETTING: {setting if setting else f"Use the world lore above, or create an evocative {genre} setting"}
CHARACTER: {character if character else "Introduce the player gently - let them discover who they are through the scene"}

Write an opening that:
1. Begins IN THE MOMENT - drop them into a lived moment, not exposition
2. Uses characters and locations from the world lore (if provided)
3. Engages the senses - what do they see, hear, feel?
4. Creates intrigue through {genre_info['hooks']}
5. Honors the fantasy their character concept implies
6. Ends at a natural pause - DO NOT suggest choices or ask questions

Length: 2-3 paragraphs. Write ONLY the narrative.
Complete your thoughts - never end mid-sentence."""

    logger.info(f"[OPENING] Calling protected_ai_call with prompt of {len(prompt)} chars")

    # Use protected AI call with guardrails
    # 1400 tokens for opening to allow rich scene-setting without truncation
    return await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=1400,
    )


async def _handle_active_play(
    session: Dict[str, Any],
    player_input: str,
    model,
    db: Optional[Neo4jDatabase],
    mechanical_context: str = "",
    needs_guidance: bool = False,
    adaptive_context: Optional[str] = None,
    game_state: Optional[GameState] = None,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Handle active gameplay with genre-aware storytelling.

    Returns:
        Tuple of (narrative_text, arc_context_dict)
    """
    answers = session.get("session_0_answers", {})

    # Get Arc Engine for narrative pacing
    arc_engine = session.get("arc_engine")
    genre = session.get("genre", "fantasy")
    tone = session.get("tone_preference", answers.get("tone", "dramatic"))
    style = session.get("storytelling_style", "guided")
    setting = session.get("setting_preference", answers.get("setting", ""))
    character = session.get("character_concept", answers.get("character", ""))
    world_lore = session.get("world_lore_content", "")
    world_name = session.get("world_name", "")

    history = session.get("history", [])[-20:]  # Last 20 messages for better continuity

    # Get story scope for pacing guidance
    session_scope = session.get("session_scope", "one_shot")
    max_turns = session.get("max_turns", 100)
    turn_count = len(session.get("history", [])) // 2  # Rough turn count (user+assistant pairs)

    genre_info = _get_genre_guidance(genre)
    style_instructions = _get_style_instructions(style)
    scope_guidance = _get_story_scope_guidance(session_scope, turn_count, max_turns)

    # Get world rules from session (user's explicit choice) or fall back to genre defaults
    world_rules = session.get("world_rules", {})
    has_magic = world_rules.get("magic", genre_info.get("magic") == "yes")
    has_supernatural = world_rules.get("supernatural", genre_info.get("magic") in ["yes", "optional"])
    is_grounded = world_rules.get("grounded", genre_info.get("magic") == "no")

    # Build magic/realism guidance based on user's world rules
    if has_magic and has_supernatural:
        magic_guidance = ""  # Full magic world - no restrictions needed
    elif has_magic:
        magic_guidance = "\nWORLD RULE: Magic exists, but focus on magic systems rather than supernatural horror."
    elif has_supernatural:
        magic_guidance = "\nWORLD RULE: Supernatural forces exist, but learnable magic does NOT."
    elif is_grounded:
        magic_guidance = "\nREALISM: NO magic or supernatural - keep everything grounded in reality."
    else:
        magic_guidance = ""

    # Format history for context with tiered detail:
    # - Most recent exchanges get full context (crucial for continuity)
    # - Middle exchanges get moderate detail
    # - Older exchanges get abbreviated summaries
    history_lines = []
    recent_history = history[:-1] if history else []  # Exclude current action
    history_len = len(recent_history)

    for i, h in enumerate(recent_history):
        role_label = "Player" if h["role"] == "user" else "Narrator"
        content = h.get("content", "")

        # Tiered context: more recent = more detail
        if i >= history_len - 4:
            # Last 4 messages: full context (up to 1000 chars) for tight continuity
            excerpt = content[:1000] if len(content) > 1000 else content
        elif i >= history_len - 10:
            # Middle 6 messages: moderate detail (600 chars)
            excerpt = content[:600] if len(content) > 600 else content
        else:
            # Older messages: abbreviated (300 chars)
            excerpt = content[:300] if len(content) > 300 else content

        history_lines.append(f"{role_label}: {excerpt}")

    history_text = "\n\n".join(history_lines)

    # Get the MOST RECENT DM response (untruncated) for immediate context
    # This ensures the AI always knows exactly what scene the player is responding to
    last_dm_response = ""
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_dm_response = entry.get("content", "")
            break

    # Build world lore context (primary source of truth)
    world_context = ""
    if world_lore:
        # Include substantial lore for consistency
        lore_excerpt = world_lore[:2500] if len(world_lore) > 2500 else world_lore
        world_context = f"""
WORLD: {world_name}
ESTABLISHED LORE (stay true to these characters and details):
{lore_excerpt}
"""

    # Query for additional entities from database (supplementary)
    # Use session_world_id for isolation - only get entities from THIS game
    db_context = ""
    if db:
        try:
            results = await db.execute("""
                MATCH (e:Entity)
                WHERE e.world_id = $session_world_id
                RETURN e.name as name, e.description as description, e.entity_type as type
                LIMIT 5
            """, {"session_world_id": session.get("session_world_id", "")})

            if results:
                db_context = "\nAdditional discovered lore:\n" + "\n".join([
                    f"- {r['name']} ({r['type']}): {r['description'][:100]}"
                    for r in results if r.get('description')
                ])
        except Exception:
            pass

    # Build character context - prefer game_state (authoritative) over _characters
    char_context = ""
    if game_state and game_state.character:
        # Use game_state for accurate, current state (HP, inventory, conditions)
        char_context = game_state.get_dm_context()
    elif session.get("character_id"):
        # Fallback to _characters dict (may be stale)
        dnd_char = _characters.get(session["character_id"])
        if dnd_char:
            char_context = f"""
CHARACTER: {dnd_char.name}, a {dnd_char.race} {dnd_char.character_class}
- Level {dnd_char.level}, {dnd_char.current_hit_points}/{dnd_char.max_hit_points} HP
- Skills: {', '.join(dnd_char.skill_proficiencies[:4])}"""

    # Get admin-configured world context (from World Tuner / LORE_BASES)
    admin_world_context = ""
    world_id = session.get("world_id")
    if world_id:
        admin_world_context = get_world_context_for_dm(world_id)

    # Build arc context for narrative pacing (Hero's Journey phases, tension)
    # Campaigns use subtle mode - structure should emerge naturally, not be announced
    arc_context_str = ""
    if arc_engine:
        try:
            use_subtle = session_scope == "campaign"
            arc_context_str = arc_engine.get_dm_context_injection(subtle=use_subtle)
            logger.debug(f"[ARC] Injecting context (subtle={use_subtle}): phase={arc_engine.current_phase.value}, tension={arc_engine.tension_level.value}")
        except Exception as e:
            logger.warning(f"[ARC] Failed to get context injection: {e}")

    # Handle genre blending
    genre_display = session.get("genre_blend", genre)

    prompt = f"""You are a master storyteller continuing someone's story.

YOUR JOB: Read between the lines. When they act, ask yourself what experience they're seeking. "I attack the dragon" might mean they want to feel brave, or test if you'll let them be bold. "I look around carefully" means they want to be rewarded for caution. "I try to talk to them" means they want diplomacy to matter. Give them what they're actually asking for, not just the literal response.
{scope_guidance}
{arc_context_str}
GENRE: {genre_display.upper()}
Voice: {genre_info['voice']}
{magic_guidance}

TONE: {tone}
{world_context}
{db_context}
{admin_world_context}

PROTAGONIST: {character if character else 'the protagonist'}
{char_context}

STORY SO FAR:
{history_text if history_text else 'The story is just beginning.'}

CURRENT SCENE:
{last_dm_response if last_dm_response else 'The story is just beginning.'}

PLAYER'S ACTION: {player_input}
{mechanical_context}
{_get_guidance_instruction(needs_guidance)}
{f'''STORYTELLING ADJUSTMENT: {adaptive_context}
''' if adaptive_context else ''}
Continue:
- Pick up EXACTLY where the scene left off
- Honor what they're trying to do - match their energy
- Show consequences that feel meaningful
- 2-3 paragraphs, natural pause
- NO suggestions or questions

STATE CHANGE TAGS (use when player gains items, gold, or takes damage):
- When player acquires an item: include [ACQUIRED: Item Name] or [ACQUIRED: Item Name, rarity, type]
  Example: "You pocket the ancient key. [ACQUIRED: Ancient Key, rare, quest]"
- When player gains gold/currency: include [GOLD: amount] or [CURRENCY: silver, amount]
  Example: "The merchant pays you well. [GOLD: 50]"
- When player takes damage: include [DAMAGE: amount] or [DAMAGE: amount, type]
  Example: "The blade bites deep. [DAMAGE: 8, slashing]"
- When player heals: include [HEAL: amount]
  Example: "The potion takes effect. [HEAL: 10]"

Write ONLY the narrative (with state tags naturally embedded):"""

    # Use protected AI call with guardrails
    # 1200 tokens allows for complete responses without truncation
    narrative = await protected_ai_call(
        model,
        prompt,
        session_id=session.get("session_id", "unknown"),
        temperature=0.85,
        max_output_tokens=1200,
    )

    # Process narrative through Arc Engine for state updates
    arc_context = None
    if arc_engine and narrative:
        try:
            # Process the narrative to update arc state (phase transitions, tension)
            arc_engine.process_narrative(narrative, player_input)

            # Build arc context for API response
            arc_context = {
                "current_phase": arc_engine.current_phase.value,
                "phase_display": arc_engine.current_phase.value.replace("_", " ").title(),
                "act": arc_engine.current_act.value,
                "tension_level": arc_engine.tension_level.value,
                "tension_value": arc_engine.current_tension,
                "journey_progress": arc_engine.journey_progress,
                "episode_number": arc_engine.episode_number,
            }
            logger.info(f"[ARC] Post-narrative: phase={arc_context['current_phase']}, tension={arc_context['tension_level']}, progress={arc_context['journey_progress']:.0%}")
        except Exception as e:
            logger.warning(f"[ARC] Failed to process narrative: {e}")

    return narrative, arc_context


# ============================================================
# LORE BASES (Pre-made worlds)
# ============================================================

# Directory for lore base JSON files
LORE_BASES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "lore_bases"
SEEDS_DIR = LORE_BASES_DIR / "seeds"


def _get_default_character_options_for_genre(mechanics_genre: str) -> Dict[str, Any]:
    """
    Generate default character options from genre configuration.

    Uses the genre's full origin/archetype data to provide:
    - id: lowercase snake_case identifier
    - name: display name
    - description: brief description
    - base_type: D&D 5e mechanical base (for MANTLE translation, defaults to id)
    """
    # Get full origin/archetype data for this genre
    origins_data = get_origins_for_genre(mechanics_genre)
    archetypes_data = get_archetypes_for_genre(mechanics_genre)

    origins = []
    for origin in origins_data:
        origins.append({
            "id": origin.id,
            "name": origin.display_name,
            "description": origin.description or f"A {origin.display_name.lower()} background",
            "base_type": origin.id,  # For non-MANTLE worlds, id == base_type (1:1 mapping)
        })

    archetypes = []
    for archetype in archetypes_data:
        archetypes.append({
            "id": archetype.id,
            "name": archetype.display_name,
            "description": archetype.description or f"A skilled {archetype.display_name.lower()}",
            "base_type": archetype.id,  # For non-MANTLE worlds, id == base_type (1:1 mapping)
        })

    return {
        "origins": origins,
        "archetypes": archetypes,
    }


def _load_lore_bases_from_files() -> Dict[str, Dict[str, Any]]:
    """
    Load all lore bases from JSON files in data/lore_bases/ and data/lore_bases/seeds/.

    Each JSON file should contain:
    - id: unique identifier
    - name: display name
    - description: brief description for UI
    - genre_hints: list of genres (or 'genre' for single genre)
    - tone_hints: list of tone descriptors
    - seed_prompt: prompt used for AI generation
    - lore_content: full text to ingest for entities/NPCs (optional)
    """
    bases = {}

    # Load from main directory
    if LORE_BASES_DIR.exists():
        for json_file in LORE_BASES_DIR.glob("*.json"):
            _load_single_lore_file(json_file, bases)

    # Load from seeds directory (curated genre-specific lore)
    if SEEDS_DIR.exists():
        for json_file in SEEDS_DIR.glob("*.json"):
            _load_single_lore_file(json_file, bases, is_seed=True)

    return bases


def _load_single_lore_file(json_file: Path, bases: Dict, is_seed: bool = False) -> None:
    """Load a single lore base JSON file."""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        lore_id = data.get("id", json_file.stem)

        # Handle both 'genre' (single) and 'genre_hints' (list)
        genre_hints = data.get("genre_hints", [])
        if not genre_hints and data.get("genre"):
            genre_hints = [data.get("genre")]
        
        # Handle mechanics_genre: prefer explicit mechanics_genre, fallback to genre, then first genre_hint
        mechanics_genre = data.get("mechanics_genre")
        if not mechanics_genre:
            mechanics_genre = data.get("genre")
        if not mechanics_genre and genre_hints:
            mechanics_genre = genre_hints[0]
        if not mechanics_genre:
            mechanics_genre = "fantasy"  # Ultimate fallback

        # Generate default character options from genre for seed worlds
        # These can be customized later by admins via the Character Options UI
        character_options = data.get("character_options")
        if not character_options and is_seed:
            character_options = _get_default_character_options_for_genre(mechanics_genre)

        bases[lore_id] = {
            "id": lore_id,
            "name": data.get("name", lore_id.replace("_", " ").title()),
            "description": data.get("description", ""),
            "genre": data.get("genre", genre_hints[0] if genre_hints else "fantasy"),  # Keep for backward compatibility
            "mechanics_genre": mechanics_genre,  # NEW: Authoritative mechanics genre
            "genre_hints": genre_hints,
            "genre_confidence": data.get("genre_confidence"),  # Optional confidence score
            "tone_hints": data.get("tone_hints", []),
            "entities_count": 0,
            "seed_prompt": data.get("seed_prompt", ""),
            "lore_content": data.get("lore_content", ""),
            "ingested": False,
            "is_seed": is_seed,  # Mark as curated seed lore
            "character_options": character_options,  # Auto-populated from genre for seeds
        }
        num_origins = len(character_options.get("origins", [])) if character_options else 0
        num_archetypes = len(character_options.get("archetypes", [])) if character_options else 0
        logger.info(f"Loaded {'seed' if is_seed else 'lore base'} from file: {lore_id} (mechanics_genre={mechanics_genre}, {num_origins} origins, {num_archetypes} archetypes)")
    except Exception as e:
        logger.error(f"Failed to load lore file {json_file}: {e}")


# Load from files, then add built-in defaults
_file_lore_bases = _load_lore_bases_from_files()

# Built-in lore bases (can be overridden by files)
LORE_BASES = {
    "shattered_kingdoms": {
        "id": "shattered_kingdoms",
        "name": "The Shattered Kingdoms",
        "description": "A realm fractured by an ancient war between divine forces. Noble houses vie for power while darker forces stir in the shadows.",
        "genre_hints": ["fantasy", "drama", "mystery"],
        "tone_hints": ["epic", "dark", "dramatic"],
        "entities_count": 0,
        "seed_prompt": "The Shattered Kingdoms - a fractured realm where noble houses compete for power amid ancient ruins and forgotten magic",
        "lore_content": "",
        "ingested": False,
    },
    "thornwood": {
        "id": "thornwood",
        "name": "Thornwood Chronicles",
        "description": "A mystical forest where fey courts hold sway. Ancient pacts, forbidden love, and the boundaries between worlds grow thin.",
        "genre_hints": ["fantasy", "romance", "horror"],
        "tone_hints": ["intimate", "whimsical", "dark"],
        "entities_count": 0,
        "seed_prompt": "Thornwood - a mystical forest where fey courts hold ancient pacts and the veil between worlds is thin",
        "lore_content": "",
        "ingested": False,
    },
    "empty": {
        "id": "empty",
        "name": "Fresh Canvas",
        "description": "Begin with nothing. Let the world emerge from your story.",
        "genre_hints": [],
        "tone_hints": [],
        "entities_count": 0,
        "seed_prompt": "",
        "lore_content": "",
        "ingested": True,  # Empty is always "ingested"
    },
}

# Merge file-loaded lore bases (they take precedence over built-ins)
LORE_BASES.update(_file_lore_bases)

# Log all loaded lore bases at startup for debugging
logger.info(f"Loaded {len(LORE_BASES)} total lore bases from files at startup:")
for base_id, base_data in LORE_BASES.items():
    is_seed = base_data.get("is_seed", False)
    logger.info(f"  - {base_id}: {base_data.get('name', 'unnamed')} (seed={is_seed})")


async def load_lore_bases_from_neo4j(db) -> int:
    """
    Load LoreBase nodes from Neo4j database (admin-created worlds).

    This is called during app startup to restore worlds created via the API
    that were stored in Neo4j but not written to JSON files.

    Returns the count of worlds loaded from Neo4j.
    """
    if not db:
        return 0

    try:
        results = await db.execute("""
            MATCH (lb:LoreBase)
            RETURN lb.lore_id as id,
                   lb.name as name,
                   lb.description as description,
                   lb.genre as genre,
                   lb.genre_hints as genre_hints,
                   lb.tone_hints as tone_hints,
                   lb.seed_prompt as seed_prompt,
                   lb.lore_content as lore_content,
                   lb.is_curated as is_curated,
                   lb.ingested as ingested,
                   lb.entities_count as entities_count,
                   lb.world_characteristics_json as wc_json
        """, {})

        loaded_count = 0
        for record in results:
            lore_id = record.get("id")
            if not lore_id:
                continue

            # Skip if already loaded from file (file takes precedence)
            if lore_id in LORE_BASES:
                logger.debug(f"Skipping Neo4j lore base {lore_id} - already loaded from file")
                continue

            # Parse world_characteristics from JSON if present
            wc_data = {}
            wc_json = record.get("wc_json")
            if wc_json:
                try:
                    wc_data = json.loads(wc_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Load from Neo4j
            genre_hints = record.get("genre_hints") or []
            LORE_BASES[lore_id] = {
                "id": lore_id,
                "name": record.get("name", lore_id),
                "description": record.get("description", ""),
                "genre": record.get("genre", genre_hints[0] if genre_hints else "fantasy"),
                "genre_hints": genre_hints,
                "tone_hints": record.get("tone_hints") or [],
                "entities_count": record.get("entities_count") or 0,
                "seed_prompt": record.get("seed_prompt", ""),
                "lore_content": record.get("lore_content", ""),
                "ingested": record.get("ingested", False),
                "is_curated": record.get("is_curated", True),
                "world_characteristics": wc_data,
                "source": "neo4j",  # Mark as loaded from DB
            }
            loaded_count += 1
            logger.info(f"Loaded lore base from Neo4j: {lore_id}")

        return loaded_count

    except Exception as e:
        logger.error(f"Failed to load LoreBase nodes from Neo4j: {e}")
        return 0


async def migrate_seed_worlds_to_neo4j(db) -> int:
    """
    Migrate seed world character options to Neo4j.

    This ensures that worlds loaded from JSON files have their character options
    (origins, archetypes) persisted to Neo4j for the World Tuner to edit.

    Returns the count of worlds migrated.
    """
    if not db:
        logger.warning("[MIGRATION] No database connection, skipping migration")
        return 0

    from .character_schema import CharacterSchemaDB

    migrated = 0
    total_worlds = len(LORE_BASES)
    logger.info(f"[MIGRATION] Starting seed world migration, {total_worlds} worlds in LORE_BASES")

    try:
        schema_db = CharacterSchemaDB(db)

        for world_id, world_data in LORE_BASES.items():
            # Skip empty canvas
            if world_id == "empty":
                continue

            char_opts = world_data.get("character_options", {})
            origins = char_opts.get("origins", [])
            archetypes = char_opts.get("archetypes", [])

            # Skip if no character options in memory
            if not origins and not archetypes:
                continue

            logger.info(f"[MIGRATION] {world_id}: Found {len(origins)} origins, {len(archetypes)} archetypes in memory")

            # Check if already migrated by looking for existing data
            try:
                existing = await schema_db.get_character_options(world_id)
                existing_origins = existing.get("origins", [])
                existing_archetypes = existing.get("archetypes", [])

                # If Neo4j already has data for this world, skip
                if existing_origins or existing_archetypes:
                    logger.info(f"[MIGRATION] {world_id}: Already in Neo4j ({len(existing_origins)} origins, {len(existing_archetypes)} archetypes), skipping")
                    continue
                else:
                    logger.info(f"[MIGRATION] {world_id}: No existing Neo4j data, proceeding with migration")
            except Exception as e:
                logger.info(f"[MIGRATION] {world_id}: Neo4j check exception ({e}), proceeding with migration")

            # Migrate to Neo4j
            try:
                result = await schema_db.save_character_options(world_id, origins, archetypes)
                migrated += 1
                logger.info(f"[MIGRATION] {world_id}: Successfully migrated - {result}")
            except Exception as e:
                logger.error(f"[MIGRATION] {world_id}: Failed to migrate - {e}")

        logger.info(f"[MIGRATION] Complete: {migrated} worlds migrated")
        return migrated

    except Exception as e:
        logger.error(f"[MIGRATION] Fatal error: {e}")
        return 0


class CustomOrigin(BaseModel):
    """
    A setting-specific character origin that maps to a base D&D type.

    Example: "Netrunner" in cyberpunk maps to "rogue" for mechanics.
    """
    id: str = Field(..., description="Unique identifier (e.g., 'netrunner', 'mutant_survivor')")
    name: str = Field(..., description="Display name (e.g., 'Netrunner', 'Mutant Survivor')")
    description: str = Field(..., description="Short description of this origin")
    base_type: str = Field(..., description="Base D&D origin for mechanics (e.g., 'human', 'elf', 'dwarf')")
    abilities: List[str] = Field(default_factory=list, description="Flavor abilities (mapped to base)")


class CustomArchetype(BaseModel):
    """
    A setting-specific character archetype that maps to a base D&D class.

    Example: "Street Samurai" in cyberpunk maps to "fighter" for mechanics.
    """
    id: str = Field(..., description="Unique identifier (e.g., 'street_samurai', 'corporate_fixer')")
    name: str = Field(..., description="Display name (e.g., 'Street Samurai', 'Corporate Fixer')")
    description: str = Field(..., description="Short description of this archetype")
    base_type: str = Field(..., description="Base D&D class for mechanics (e.g., 'fighter', 'rogue', 'wizard')")
    key_abilities: List[str] = Field(default_factory=list, description="Flavor abilities (mapped to base)")


class WorldCharacterOptions(BaseModel):
    """Character creation options specific to a world."""
    origins: List[CustomOrigin] = Field(default_factory=list)
    archetypes: List[CustomArchetype] = Field(default_factory=list)
    ai_generated: bool = Field(default=False, description="True if options were AI-generated")
    admin_reviewed: bool = Field(default=False, description="True if admin has reviewed/approved")


# NOTE: MappingStatus, PendingMapping, PendingMappingsResponse, MappingApprovalRequest
# models were removed. Character options are now directly editable without a staging workflow.


class LoreBaseResponse(BaseModel):
    """Response for lore base information."""
    id: str
    name: str
    description: str
    genre: Optional[str] = None
    genre_hints: List[str]
    tone_hints: List[str]
    entities_count: int
    seed_prompt: str
    is_seed: bool = False
    # Additional fields for frontend visibility
    has_lore_content: bool = False  # True if lore_content exists and is non-empty
    ingested: bool = False  # True if lore has been processed into entities
    entities_created: int = 0  # Number of entities created in this request
    # World characteristics - canonical world definition
    world_characteristics: Optional[WorldCharacteristics] = None
    # Character creation options specific to this world
    character_options: Optional[WorldCharacterOptions] = None


@router.get("/lore-bases", response_model=List[LoreBaseResponse])
async def list_lore_bases(genre: Optional[str] = None):
    """
    List all available pre-made lore bases.

    Args:
        genre: Optional filter to show only lore bases matching this genre
    """
    bases = []
    for base in LORE_BASES.values():
        # Filter by genre if specified
        if genre:
            base_genre = base.get("genre", "")
            base_genres = base.get("genre_hints", [])
            if genre.lower() != base_genre.lower() and genre.lower() not in [g.lower() for g in base_genres]:
                continue

        # Build world characteristics from stored data
        wc_data = base.get("world_characteristics", {})
        world_chars = WorldCharacteristics(**wc_data) if wc_data else None

        # Build character options from stored data
        co_data = base.get("character_options")
        char_opts = None
        if co_data:
            if isinstance(co_data, dict):
                char_opts = WorldCharacterOptions(**co_data)
            elif isinstance(co_data, WorldCharacterOptions):
                char_opts = co_data

        bases.append(LoreBaseResponse(
            id=base["id"],
            name=base["name"],
            description=base.get("description") or "",
            genre=base.get("genre"),
            genre_hints=base.get("genre_hints") or [],
            tone_hints=base.get("tone_hints") or [],
            entities_count=base.get("entities_count") or 0,
            seed_prompt=base.get("seed_prompt") or "",
            is_seed=bool(base.get("is_seed")),
            has_lore_content=bool((base.get("lore_content") or "").strip()),
            ingested=bool(base.get("ingested")),
            world_characteristics=world_chars,
            character_options=char_opts,
        ))

    return bases


@router.get("/lore-bases/by-genre/{genre}", response_model=List[LoreBaseResponse])
async def get_lore_bases_for_genre(genre: str):
    """Get curated lore bases for a specific genre."""
    return await list_lore_bases(genre=genre)


@router.get("/lore-bases/{lore_id}", response_model=LoreBaseResponse)
async def get_lore_base(lore_id: str):
    """Get details of a specific lore base."""
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )
    base = LORE_BASES[lore_id]

    # Build world characteristics from stored data
    wc_data = base.get("world_characteristics", {})
    world_chars = WorldCharacteristics(**wc_data) if wc_data else None

    # Build character options from stored data
    co_data = base.get("character_options")
    char_opts = None
    if co_data:
        if isinstance(co_data, dict):
            char_opts = WorldCharacterOptions(**co_data)
        elif isinstance(co_data, WorldCharacterOptions):
            char_opts = co_data

    return LoreBaseResponse(
        id=base["id"],
        name=base["name"],
        description=base["description"],
        genre=base.get("genre"),
        genre_hints=base.get("genre_hints", []),
        tone_hints=base.get("tone_hints", []),
        entities_count=base.get("entities_count", 0),
        seed_prompt=base.get("seed_prompt", ""),
        is_seed=base.get("is_seed", False),
        has_lore_content=bool((base.get("lore_content") or "").strip()),
        ingested=base.get("ingested", False),
        world_characteristics=world_chars,
        character_options=char_opts,
    )


@router.get("/world-characteristics/options")
async def get_world_characteristics_options():
    """
    Get all valid options for world characteristics.
    Used by the frontend to populate dropdowns and multi-selects.
    """
    return WORLD_CHARACTERISTICS_OPTIONS


class UncertaintyFlagResponse(BaseModel):
    """An uncertainty flagged by the AI for admin review."""
    category: str  # entity, relationship, world, timeline
    question: str
    context: str
    suggestions: List[str] = []


class PendingDuplicateResponse(BaseModel):
    """A potential duplicate entity that needs admin review."""
    new_entity_name: str
    new_entity_type: str
    new_entity_description: str = ""
    new_entity_aliases: List[str] = []
    existing_entity_id: str
    existing_entity_name: str
    existing_entity_type: str
    existing_description: str = ""
    existing_aliases: List[str] = []
    similarity_score: float
    match_reason: str  # "exact_name", "similar_name", "alias_match"


class LoreBaseIngestResponse(BaseModel):
    """Response after ingesting a lore base."""
    lore_id: str
    entities_created: int
    entities_auto_merged: int = 0
    relationships_created: int
    npcs_with_ocean: int
    uncertainties_count: int = 0
    uncertainties: List[UncertaintyFlagResponse] = []
    pending_duplicates_count: int = 0
    pending_duplicates: List[PendingDuplicateResponse] = []
    message: str


@router.post("/lore-bases/{lore_id}/ingest", response_model=LoreBaseIngestResponse)
async def ingest_lore_base(
    lore_id: str,
    request: Request,
    force: bool = False,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Ingest a lore base's content into the database.

    This processes the lore_content field through the smart ingestor pipeline:
    - Extracts entities (Characters, Locations, Factions, Items, etc.)
    - Generates OCEAN personality profiles for NPCs
    - Extracts goals, secrets, and fears for characters
    - Infers world characteristics from narrative
    - Creates relationships between entities
    - Stores everything in Neo4j for the DM to use

    Use force=true to re-ingest and apply any updates to parsing logic.
    Re-ingesting will update existing entities with the latest extracted data.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    lore_base = LORE_BASES[lore_id]

    # Check if already ingested (skip if force=True)
    if lore_base.get("ingested", False) and not force:
        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=lore_base.get("entities_count", 0),
            relationships_created=0,
            npcs_with_ocean=0,
            uncertainties_count=0,
            uncertainties=[],
            message=f"Lore base '{lore_id}' was already ingested. Use force=true to re-ingest."
        )

    lore_content = lore_base.get("lore_content", "")
    if not lore_content or len(lore_content.strip()) < 50:
        # No substantial lore content to process
        LORE_BASES[lore_id]["ingested"] = True
        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=0,
            relationships_created=0,
            npcs_with_ocean=0,
            uncertainties_count=0,
            uncertainties=[],
            message=f"Lore base '{lore_id}' has no lore content to ingest (use seed_prompt for generation instead)"
        )

    # Use the LoreParsingAgent for AI-powered extraction with OCEAN profiles
    try:
        from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

        agent = LoreParsingAgent()
        logger.info(f"Starting AI lore parsing for lore base: {lore_id}")

        # Get genre from lore base metadata
        base_genre = lore_base.get("genre")
        if not base_genre and lore_base.get("genre_hints"):
            base_genre = lore_base.get("genre_hints")[0]

        result = await agent.parse_and_store(
            text=lore_content,
            db=db,
            source_name=f"lore_base:{lore_id}",
            world_id=lore_id,  # Use lore base ID as the world_id (this IS the curated world)
            curated_world_id=lore_id,  # Also mark as curated world
            genre=base_genre,  # Tag with the lore base's genre
        )

        # Update lore base status
        LORE_BASES[lore_id]["ingested"] = True
        LORE_BASES[lore_id]["entities_count"] = result.entities_stored

        logger.info(
            f"Ingested lore base {lore_id}: {result.entities_stored} entities, "
            f"{result.relationships_stored} relationships, "
            f"{result.characters_with_ocean} with OCEAN profiles, "
            f"{len(result.uncertainties)} uncertainties flagged"
        )

        # Convert uncertainties to response format
        uncertainty_responses = [
            UncertaintyFlagResponse(
                category=u.category,
                question=u.question,
                context=u.context,
                suggestions=u.suggestions,
            )
            for u in result.uncertainties
        ]

        # Convert pending duplicates to response format
        pending_duplicate_responses = [
            PendingDuplicateResponse(
                new_entity_name=pd.new_entity.name,
                new_entity_type=pd.new_entity.entity_type,
                new_entity_description=pd.new_entity.description or "",
                new_entity_aliases=pd.new_entity.aliases or [],
                existing_entity_id=pd.existing_entity_id,
                existing_entity_name=pd.existing_entity_name,
                existing_entity_type=pd.existing_entity_type,
                existing_description=pd.existing_description,
                existing_aliases=pd.existing_aliases,
                similarity_score=pd.similarity_score,
                match_reason=pd.match_reason,
            )
            for pd in result.pending_duplicates
        ]

        # Auto-generate character options if not already set
        if not LORE_BASES[lore_id].get("character_options"):
            try:
                options = await generate_character_options_from_lore(
                    lore_content=lore_content,
                    world_name=lore_base.get("name", lore_id),
                    genre=base_genre or "fantasy",
                    description=lore_base.get("description", "")
                )
                LORE_BASES[lore_id]["character_options"] = options

                # Persist to Neo4j
                try:
                    await db.execute("""
                        MATCH (lb:LoreBase {lore_id: $id})
                        SET lb.character_options = $options
                    """, {"id": lore_id, "options": json.dumps(options)})
                except Exception as neo4j_err:
                    logger.warning(f"Failed to persist character options to Neo4j: {neo4j_err}")

                logger.info(
                    f"Generated character options for {lore_id}: "
                    f"{len(options.get('origins', []))} origins, {len(options.get('archetypes', []))} archetypes"
                )
            except Exception as opt_err:
                logger.warning(f"Failed to generate character options for {lore_id}: {opt_err}")

        return LoreBaseIngestResponse(
            lore_id=lore_id,
            entities_created=result.entities_stored,
            entities_auto_merged=result.entities_auto_merged,
            relationships_created=result.relationships_stored,
            npcs_with_ocean=result.characters_with_ocean,
            uncertainties_count=len(result.uncertainties),
            uncertainties=uncertainty_responses,
            pending_duplicates_count=len(result.pending_duplicates),
            pending_duplicates=pending_duplicate_responses,
            message=f"Successfully ingested lore base '{lore_base['name']}' with AI parsing"
        )

    except Exception as e:
        logger.error(f"Failed to ingest lore base {lore_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest lore base: {str(e)}"
        )


class ApprovedEntity(BaseModel):
    """An entity that has been reviewed and approved by the user."""
    name: str
    type: str
    description: Optional[str] = None
    traits: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    secrets: Optional[List[str]] = None
    fears: Optional[List[str]] = None
    temporal_cues: Optional[List[str]] = None
    verbatim_text: Optional[str] = None
    # OCEAN profile fields (for characters)
    openness: Optional[float] = None
    conscientiousness: Optional[float] = None
    extraversion: Optional[float] = None
    agreeableness: Optional[float] = None
    neuroticism: Optional[float] = None


class LoreBaseUploadRequest(BaseModel):
    """Request to create a new lore base."""
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    genre_hints: List[str] = Field(default_factory=list)
    tone_hints: List[str] = Field(default_factory=list)
    seed_prompt: str = Field(default="")
    lore_content: str = Field(default="", description="Full lore text for entity extraction")
    approved_entities: Optional[List[ApprovedEntity]] = Field(
        default=None,
        description="Pre-approved entities from review step - bypasses AI extraction"
    )
    character_options: Optional[WorldCharacterOptions] = Field(
        default=None,
        description="Custom character origins/archetypes for this world. If not provided, AI will generate them."
    )


@router.post("/lore-bases", response_model=LoreBaseResponse)
async def create_lore_base(
    http_request: Request,
    lore_base: LoreBaseUploadRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Create a new lore base and automatically ingest the lore content.

    This endpoint:
    1. Creates the world definition in Neo4j (persistent!)
    2. Parses the lore_content using AI to extract entities
    3. Creates Characters, Locations, Factions with OCEAN profiles
    4. Makes the world immediately playable

    Just upload your lore and the world is ready to play.
    """
    if lore_base.id in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lore base '{lore_base.id}' already exists"
        )

    # Get primary genre
    primary_genre = lore_base.genre_hints[0] if lore_base.genre_hints else "fantasy"

    new_base = {
        "id": lore_base.id,
        "name": lore_base.name,
        "description": lore_base.description,
        "genre": primary_genre,
        "genre_hints": lore_base.genre_hints,
        "tone_hints": lore_base.tone_hints,
        "entities_count": 0,
        "seed_prompt": lore_base.seed_prompt,
        "lore_content": lore_base.lore_content,
        "ingested": False,
        "is_curated": True,
    }

    # Store lore base definition in Neo4j (persistent across deploys!)
    try:
        await db.execute("""
            CREATE (lb:LoreBase {
                lore_id: $id,
                name: $name,
                description: $description,
                genre: $genre,
                genre_hints: $genre_hints,
                tone_hints: $tone_hints,
                seed_prompt: $seed_prompt,
                lore_content: $lore_content,
                is_curated: true,
                ingested: false,
                created_at: datetime()
            })
        """, {
            "id": lore_base.id,
            "name": lore_base.name,
            "description": lore_base.description,
            "genre": primary_genre,
            "genre_hints": lore_base.genre_hints,
            "tone_hints": lore_base.tone_hints,
            "seed_prompt": lore_base.seed_prompt,
            "lore_content": lore_base.lore_content,
        })
        logger.info(f"Created LoreBase node in Neo4j: {lore_base.id}")
    except Exception as e:
        logger.error(f"Failed to create LoreBase in Neo4j: {e}")

    # Add to in-memory dict
    LORE_BASES[lore_base.id] = new_base

    entities_created = 0

    # HUMAN-REVIEWED ENTITIES: If approved_entities provided, create those directly
    if lore_base.approved_entities and len(lore_base.approved_entities) > 0:
        logger.info(f"Creating {len(lore_base.approved_entities)} pre-approved entities for {lore_base.id}")
        try:
            for entity in lore_base.approved_entities:
                entity_type = entity.type.capitalize()
                canon_id = f"{lore_base.id}:{entity.name.lower().replace(' ', '_')}"

                # Build properties dict with all available fields
                props = {
                    "canon_id": canon_id,
                    "name": entity.name,
                    "description": entity.description or "",
                    "world_id": lore_base.id,
                    "curated_world_id": lore_base.id,
                    "source": f"lore_base:{lore_base.id}:reviewed",
                    "genre": primary_genre,
                    "entity_type": entity_type,
                    "approval_status": "APPROVED",
                    "confidence_level": "HUMAN_REVIEWED",
                }

                # Add optional fields if present
                if entity.traits:
                    props["personality_traits"] = entity.traits
                if entity.aliases:
                    props["aliases"] = entity.aliases
                if entity.tags:
                    props["tags"] = entity.tags
                if entity.goals:
                    props["goals"] = entity.goals
                if entity.secrets:
                    props["secrets"] = entity.secrets
                if entity.fears:
                    props["fears"] = entity.fears
                if entity.temporal_cues:
                    props["temporal_cues"] = entity.temporal_cues
                if entity.verbatim_text:
                    props["content"] = entity.verbatim_text

                # Add OCEAN profile for characters
                if entity_type == "Character":
                    if entity.openness is not None:
                        props["openness"] = entity.openness
                    if entity.conscientiousness is not None:
                        props["conscientiousness"] = entity.conscientiousness
                    if entity.extraversion is not None:
                        props["extraversion"] = entity.extraversion
                    if entity.agreeableness is not None:
                        props["agreeableness"] = entity.agreeableness
                    if entity.neuroticism is not None:
                        props["neuroticism"] = entity.neuroticism

                # Create the entity node in Neo4j with all properties
                await db.execute(f"""
                    MERGE (e:{entity_type} {{canon_id: $canon_id}})
                    SET e += $props
                    SET e.created_at = datetime()
                    SET e:Entity
                """, {
                    "canon_id": canon_id,
                    "props": props,
                })
                entities_created += 1

            # Update counts
            new_base["ingested"] = True
            new_base["entities_count"] = entities_created
            LORE_BASES[lore_base.id] = new_base

            # Update Neo4j node
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $id})
                SET lb.ingested = true,
                    lb.entities_count = $count
            """, {"id": lore_base.id, "count": entities_created})

            logger.info(f"Created {entities_created} reviewed entities for {lore_base.id}")

        except Exception as e:
            logger.error(f"Failed to create reviewed entities for {lore_base.id}: {e}")

    # FALLBACK: If no approved_entities but has lore_content, do AI extraction
    elif lore_base.lore_content and len(lore_base.lore_content.strip()) >= 50:
        try:
            from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

            agent = LoreParsingAgent()
            logger.info(f"Auto-ingesting lore for new world: {lore_base.id}")

            result = await agent.parse_and_store(
                text=lore_base.lore_content,
                db=db,
                source_name=f"lore_base:{lore_base.id}",
                world_id=lore_base.id,
                curated_world_id=lore_base.id,
                genre=primary_genre,
            )

            # Update counts
            new_base["ingested"] = True
            new_base["entities_count"] = result.entities_stored
            entities_created = result.entities_stored
            LORE_BASES[lore_base.id] = new_base

            # Update Neo4j node
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $id})
                SET lb.ingested = true,
                    lb.entities_count = $count
            """, {"id": lore_base.id, "count": result.entities_stored})

            logger.info(
                f"Auto-ingested {lore_base.id}: {result.entities_stored} entities, "
                f"{result.characters_with_ocean} with OCEAN profiles"
            )

        except Exception as e:
            logger.error(f"Auto-ingest failed for {lore_base.id}: {e}")
            # World is still created, just not ingested

    # ============================================================
    # AUTO-GENERATE CHARACTER OPTIONS
    # ============================================================
    # If character_options not provided, generate them from lore
    if lore_base.character_options:
        # Use provided options
        new_base["character_options"] = lore_base.character_options.model_dump()
        logger.info(f"Using provided character options for {lore_base.id}")
    elif lore_base.lore_content or lore_base.description:
        # Generate options from lore using AI
        try:
            content_to_analyze = lore_base.lore_content or lore_base.description
            options = await generate_character_options_from_lore(
                lore_content=content_to_analyze,
                world_name=lore_base.name,
                genre=primary_genre,
                description=lore_base.description
            )
            new_base["character_options"] = options
            LORE_BASES[lore_base.id]["character_options"] = options

            # Persist to Neo4j
            try:
                await db.execute("""
                    MATCH (lb:LoreBase {lore_id: $id})
                    SET lb.character_options = $options
                """, {"id": lore_base.id, "options": json.dumps(options)})
            except Exception as e:
                logger.warning(f"Failed to persist character options to Neo4j: {e}")

            logger.info(
                f"Generated character options for {lore_base.id}: "
                f"{len(options.get('origins', []))} origins, {len(options.get('archetypes', []))} archetypes"
            )
        except Exception as e:
            logger.error(f"Failed to generate character options for {lore_base.id}: {e}")
            # World is still created, just without character options

    new_base["entities_created"] = entities_created
    return LoreBaseResponse(**new_base)


@router.post("/lore-bases/upload")
async def upload_lore_base_file(file: UploadFile = File(...)):
    """
    Upload a lore base JSON file.

    The file should be a JSON file with the structure:
    {
        "id": "my_world",
        "name": "My World Name",
        "description": "A brief description",
        "genre_hints": ["fantasy"],
        "tone_hints": ["epic"],
        "seed_prompt": "Seed prompt for AI",
        "lore_content": "Full narrative text with NPCs, locations, etc..."
    }
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .json file"
        )

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )

    lore_id = data.get("id", file.filename.replace(".json", ""))

    if lore_id in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lore base '{lore_id}' already exists"
        )

    new_base = {
        "id": lore_id,
        "name": data.get("name", lore_id.replace("_", " ").title()),
        "description": data.get("description", ""),
        "genre_hints": data.get("genre_hints", []),
        "tone_hints": data.get("tone_hints", []),
        "entities_count": 0,
        "seed_prompt": data.get("seed_prompt", ""),
        "lore_content": data.get("lore_content", ""),
        "ingested": False,
    }

    # Save to file
    LORE_BASES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = LORE_BASES_DIR / f"{lore_id}.json"

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_base, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save uploaded lore base: {e}")

    LORE_BASES[lore_id] = new_base

    return {
        "message": f"Lore base '{lore_id}' uploaded successfully",
        "lore_id": lore_id,
        "name": new_base["name"],
        "has_lore_content": bool(new_base["lore_content"]),
        "next_step": f"Call POST /api/game/lore-bases/{lore_id}/ingest to process entities"
    }


class LoreBaseUpdateRequest(BaseModel):
    """Request to update a lore base."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=10, max_length=500)
    genre: Optional[str] = None
    genre_hints: Optional[List[str]] = None
    tone_hints: Optional[List[str]] = None
    seed_prompt: Optional[str] = None
    lore_content: Optional[str] = None
    approved_entities: Optional[List[ApprovedEntity]] = Field(
        default=None,
        description="Pre-approved entities from review step - creates new entities"
    )
    world_characteristics: Optional[WorldCharacteristics] = Field(
        default=None,
        description="Canonical world characteristics (genre, tone, magic level, etc.)"
    )


@router.put("/lore-bases/{lore_id}", response_model=LoreBaseResponse)
async def update_lore_base(
    lore_id: str,
    update: LoreBaseUpdateRequest,
    request: Request,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Update an existing lore base's properties.

    Only provided fields will be updated. To add new lore content
    and re-ingest entities, call the /ingest endpoint after updating.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    base = LORE_BASES[lore_id]

    # Update only provided fields
    if update.name is not None:
        base["name"] = update.name
    if update.description is not None:
        base["description"] = update.description
    if update.genre is not None:
        base["genre"] = update.genre
    if update.genre_hints is not None:
        base["genre_hints"] = update.genre_hints
    if update.tone_hints is not None:
        base["tone_hints"] = update.tone_hints
    if update.seed_prompt is not None:
        base["seed_prompt"] = update.seed_prompt
    if update.lore_content is not None:
        base["lore_content"] = update.lore_content
        base["ingested"] = False  # Mark for re-ingestion
    if update.world_characteristics is not None:
        base["world_characteristics"] = update.world_characteristics.model_dump()

    LORE_BASES[lore_id] = base

    # Update Neo4j if exists
    try:
        # Store world_characteristics as JSON string in Neo4j
        wc_json = json.dumps(base.get("world_characteristics", {})) if base.get("world_characteristics") else None

        await db.execute("""
            MATCH (lb:LoreBase {lore_id: $id})
            SET lb.name = $name,
                lb.description = $description,
                lb.genre = $genre,
                lb.genre_hints = $genre_hints,
                lb.tone_hints = $tone_hints,
                lb.seed_prompt = $seed_prompt,
                lb.lore_content = $lore_content,
                lb.ingested = $ingested,
                lb.world_characteristics_json = $wc_json,
                lb.updated_at = datetime()
        """, {
            "id": lore_id,
            "name": base.get("name", ""),
            "description": base.get("description", ""),
            "genre": base.get("genre", ""),
            "genre_hints": base.get("genre_hints", []),
            "tone_hints": base.get("tone_hints", []),
            "seed_prompt": base.get("seed_prompt", ""),
            "lore_content": base.get("lore_content", ""),
            "ingested": base.get("ingested", False),
            "wc_json": wc_json,
        })
    except Exception as e:
        logger.warning(f"Failed to update LoreBase in Neo4j: {e}")

    # Also update JSON file if it exists
    try:
        file_path = LORE_BASES_DIR / f"{lore_id}.json"
        if file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(base, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to update lore base file: {e}")

    # Create approved entities if provided
    entities_created = 0
    if update.approved_entities and len(update.approved_entities) > 0:
        logger.info(f"Creating {len(update.approved_entities)} pre-approved entities for {lore_id}")
        primary_genre = base.get("genre", "fantasy")
        try:
            for entity in update.approved_entities:
                entity_type = entity.type.capitalize()
                canon_id = f"{lore_id}:{entity.name.lower().replace(' ', '_')}"

                # Create the entity node in Neo4j
                await db.execute(f"""
                    MERGE (e:{entity_type} {{canon_id: $canon_id}})
                    SET e.name = $name,
                        e.description = $description,
                        e.world_id = $world_id,
                        e.curated_world_id = $curated_world_id,
                        e.source = $source,
                        e.genre = $genre,
                        e.created_at = datetime()
                """, {
                    "canon_id": canon_id,
                    "name": entity.name,
                    "description": entity.description or "",
                    "world_id": lore_id,
                    "curated_world_id": lore_id,
                    "source": f"lore_base:{lore_id}:reviewed",
                    "genre": primary_genre,
                })
                entities_created += 1

            # Update entity count
            current_count = base.get("entities_count", 0)
            base["entities_count"] = current_count + entities_created
            base["ingested"] = True
            LORE_BASES[lore_id] = base

            # Update Neo4j node
            await db.execute("""
                MATCH (lb:LoreBase {lore_id: $id})
                SET lb.ingested = true,
                    lb.entities_count = $count
            """, {"id": lore_id, "count": base["entities_count"]})

            logger.info(f"Created {entities_created} reviewed entities for {lore_id}")

        except Exception as e:
            logger.error(f"Failed to create reviewed entities for {lore_id}: {e}")

    return LoreBaseResponse(
        id=base["id"],
        name=base["name"],
        description=base.get("description", ""),
        genre=base.get("genre"),
        genre_hints=base.get("genre_hints", []),
        tone_hints=base.get("tone_hints", []),
        entities_count=base.get("entities_count", 0),
        seed_prompt=base.get("seed_prompt", ""),
        is_seed=base.get("is_seed", False),
        has_lore_content=bool((base.get("lore_content") or "").strip()),
        ingested=base.get("ingested", False),
        entities_created=entities_created,
    )


class LoreBaseDeleteResponse(BaseModel):
    """Response after deleting a lore base."""
    lore_id: str
    message: str
    entities_deleted: int
    relationships_deleted: int


@router.delete("/lore-bases/{lore_id}", response_model=LoreBaseDeleteResponse)
async def delete_lore_base(
    lore_id: str,
    request: Request,
    db: Neo4jDatabase = Depends(get_neo4j_db),
    delete_entities: bool = Query(True, description="Also delete all entities belonging to this world")
):
    """
    Delete a lore base and optionally all its entities.

    Args:
        lore_id: ID of the lore base to delete
        delete_entities: If True (default), also deletes all entities with this world_id

    Note: Will proceed with deletion even if world not in LORE_BASES (handles
    dynamically created worlds or server restarts).
    """
    in_memory = lore_id in LORE_BASES
    logger.info(f"Delete request for world '{lore_id}' (in_memory={in_memory}, delete_entities={delete_entities})")

    entities_deleted = 0
    relationships_deleted = 0

    # Delete entities if requested
    if delete_entities:
        try:
            # Count entities first (check both world_id and curated_world_id)
            count_result = await db.execute("""
                MATCH (e:Entity)
                WHERE e.world_id = $world_id OR e.curated_world_id = $world_id
                RETURN count(e) as count
            """, {"world_id": lore_id})

            if count_result:
                entities_deleted = count_result[0].get("count", 0)

            logger.info(f"Found {entities_deleted} entities to delete for world {lore_id}")

            # Delete all entities matching either world_id or curated_world_id
            if entities_deleted > 0:
                delete_result = await db.execute("""
                    MATCH (e:Entity)
                    WHERE e.world_id = $world_id OR e.curated_world_id = $world_id
                    DETACH DELETE e
                    RETURN count(*) as deleted
                """, {"world_id": lore_id})

                actual_deleted = delete_result[0].get("deleted", 0) if delete_result else 0
                logger.info(f"Actually deleted {actual_deleted} entities for world {lore_id}")

        except Exception as e:
            logger.error(f"Failed to delete entities for {lore_id}: {e}", exc_info=True)

    # Delete the LoreBase node from Neo4j
    try:
        await db.execute("""
            MATCH (lb:LoreBase {lore_id: $id})
            DETACH DELETE lb
        """, {"id": lore_id})
    except Exception as e:
        logger.warning(f"Failed to delete LoreBase node: {e}")

    # Delete JSON file if exists
    try:
        file_path = LORE_BASES_DIR / f"{lore_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted lore base file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to delete lore base file: {e}")

    # Also check seeds directory
    try:
        seed_path = SEEDS_DIR / f"{lore_id}.json"
        if seed_path.exists():
            seed_path.unlink()
            logger.info(f"Deleted seed file: {seed_path}")
    except Exception as e:
        logger.warning(f"Failed to delete seed file: {e}")

    # Remove from in-memory dict (if present)
    was_in_memory = lore_id in LORE_BASES
    removed = LORE_BASES.pop(lore_id, None)
    logger.info(f"Removed '{lore_id}' from LORE_BASES: was_present={was_in_memory}, removed={removed is not None}")
    logger.info(f"LORE_BASES now has {len(LORE_BASES)} worlds")

    logger.info(f"Delete complete for lore base: {lore_id}")

    message = f"Successfully deleted world '{lore_id}'"
    if entities_deleted > 0:
        message += f" and {entities_deleted} entities"

    return LoreBaseDeleteResponse(
        lore_id=lore_id,
        message=message,
        entities_deleted=entities_deleted,
        relationships_deleted=relationships_deleted,
    )


class LorePreviewRequest(BaseModel):
    """Request to preview lore extraction."""
    lore_content: str = Field(..., min_length=10, description="Lore text to preview")


class LorePreviewResponse(BaseModel):
    """Response with previewed entities and relationships."""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]] = []
    summary: Dict[str, int]


@router.post("/lore-bases/{lore_id}/preview", response_model=LorePreviewResponse)
async def preview_lore_extraction(
    lore_id: str,
    preview_req: LorePreviewRequest,
    request: Request,
):
    """
    Preview what entities would be extracted from lore content.

    This does NOT save anything - it just shows what the AI would extract.
    Use this to verify extraction before committing.

    Note: lore_id can be a placeholder (e.g., "preview") for new worlds
    that don't exist yet. Preview only needs the lore content.
    """
    # Note: We don't require lore_id to exist - preview works for new worlds too
    # The lore_id is just for context/routing, the actual extraction only needs text

    try:
        from src.mantle.agents.lore_parsing_agent import LoreParsingAgent

        agent = LoreParsingAgent()

        # Parse WITHOUT storing
        result = await agent.parse_lore(preview_req.lore_content)

        # Format entities for preview
        entities = []
        summary = {
            "characters": 0,
            "locations": 0,
            "factions": 0,
            "items": 0,
            "events": 0,
            "concepts": 0,
        }

        for entity in result.entities:
            entity_type = entity.entity_type.lower()
            # Map singular to plural for summary
            type_key = entity_type + "s" if entity_type != "concept" else "concepts"
            if type_key in summary:
                summary[type_key] += 1

            entity_dict = {
                "name": entity.name,
                "type": entity.entity_type,
                "description": entity.description,
                "traits": entity.traits if entity.traits else [],
                "aliases": entity.aliases if entity.aliases else [],
                "tags": entity.tags if entity.tags else [],
                "temporal_cues": entity.temporal_cues if entity.temporal_cues else [],
                "verbatim_text": entity.verbatim_text if entity.verbatim_text else "",
                "goals": entity.goals if entity.goals else [],
                "secrets": entity.secrets if entity.secrets else [],
                "fears": entity.fears if entity.fears else [],
            }

            # Add OCEAN profile for characters
            if entity.entity_type == "Character" and entity.traits:
                ocean = agent._generate_ocean_from_traits(entity.traits)
                entity_dict["openness"] = ocean.openness
                entity_dict["conscientiousness"] = ocean.conscientiousness
                entity_dict["extraversion"] = ocean.extraversion
                entity_dict["agreeableness"] = ocean.agreeableness
                entity_dict["neuroticism"] = ocean.neuroticism

            entities.append(entity_dict)

        # Format relationships for preview
        relationships = []
        for rel in result.relationships:
            relationships.append({
                "source": rel.source,
                "target": rel.target,
                "relationship_type": rel.relationship_type,
                "description": rel.description if rel.description else "",
            })

        summary["relationships"] = len(relationships)

        return LorePreviewResponse(
            entities=entities,
            relationships=relationships,
            summary=summary,
        )

    except Exception as e:
        logger.error(f"Preview extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview failed: {str(e)}"
        )


@router.post("/lore-bases/{lore_id}/entities")
async def import_entities_to_world(
    lore_id: str,
    entities_req: dict,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Import pre-reviewed entities to an existing world.
    
    This endpoint is for human-in-the-loop entity import where entities
    have already been extracted and reviewed by the user.
    
    Body should contain:
    - entities: List of entity dicts (from preview response)
    - source_name: Optional source identifier for tracking
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )
    
    entities = entities_req.get("entities", [])
    source_name = entities_req.get("source_name", f"import_{uuid.uuid4().hex[:8]}")
    
    if not entities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No entities provided"
        )
    
    # Validate database connection
    if db is None:
        logger.error("Database connection is None when importing entities")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    logger.info(f"Importing {len(entities)} entities to world {lore_id}, source: {source_name}")
    
    entities_created = 0
    lore_base = LORE_BASES[lore_id]
    primary_genre = lore_base.get("genre", "fantasy")
    
    try:
        for entity in entities:
            entity_type = entity.get("type", "").capitalize()
            entity_name = entity.get("name", "Unknown")
            
            # Generate canon_id
            name_slug = entity_name.lower().replace(' ', '_').replace("'", "")
            canon_id = f"{lore_id}:{name_slug}"
            
            # Build properties dict with all available fields
            props = {
                "canon_id": canon_id,
                "name": entity_name,
                "canonical_name": entity_name,
                "description": entity.get("description", ""),
                "world_id": lore_id,
                "curated_world_id": lore_id,
                "source": f"lore_base:{lore_id}:{source_name}",
                "source_name": source_name,
                "genre": primary_genre,
                "entity_type": entity_type,
                "approval_status": "APPROVED",
                "confidence_level": "HUMAN_REVIEWED",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Add optional fields if present
            if entity.get("traits"):
                props["personality_traits"] = entity["traits"]
            if entity.get("aliases"):
                props["aliases"] = entity["aliases"]
            if entity.get("tags"):
                props["tags"] = entity["tags"]
            if entity.get("goals"):
                props["goals"] = entity["goals"]
            if entity.get("secrets"):
                props["secrets"] = entity["secrets"]
            if entity.get("fears"):
                props["fears"] = entity["fears"]
            if entity.get("temporal_cues"):
                props["temporal_cues"] = entity["temporal_cues"]
            if entity.get("verbatim_text"):
                props["verbatim_text"] = entity["verbatim_text"]
            
            # Add OCEAN profile for characters
            if entity_type == "Character":
                if entity.get("openness") is not None:
                    props["openness"] = float(entity["openness"])
                if entity.get("conscientiousness") is not None:
                    props["conscientiousness"] = float(entity["conscientiousness"])
                if entity.get("extraversion") is not None:
                    props["extraversion"] = float(entity["extraversion"])
                if entity.get("agreeableness") is not None:
                    props["agreeableness"] = float(entity["agreeableness"])
                if entity.get("neuroticism") is not None:
                    props["neuroticism"] = float(entity["neuroticism"])
            
            # Create or merge entity node
            safe_label = "".join([c for c in entity_type if c.isalnum()])
            
            query = f"""
            MERGE (n:`{safe_label}` {{canon_id: $canon_id}})
            ON CREATE SET n = $props
            ON MATCH SET n += $props
            SET n:Entity
            SET n.updated_at = $updated_at
            RETURN n.canon_id as id
            """
            
            await db.execute(query, {
                "canon_id": canon_id,
                "props": props,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            
            entities_created += 1
        
        # Update entity count in LORE_BASES
        LORE_BASES[lore_id]["entities_count"] = LORE_BASES[lore_id].get("entities_count", 0) + entities_created
        
        logger.info(f"Successfully imported {entities_created} entities to {lore_id}")
        
        return {
            "lore_id": lore_id,
            "entities_imported": entities_created,
            "source_name": source_name,
            "message": f"Successfully imported {entities_created} entities to world '{lore_base['name']}'"
        }
        
    except Exception as e:
        logger.error(f"Failed to import entities to {lore_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import entities: {str(e)}"
        )


@router.get("/lore-bases/{lore_id}/entities")
async def get_world_entities(
    lore_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db),
    entity_type: Optional[str] = None,
    source_name: Optional[str] = None,
    limit: int = Query(1000, le=5000),
):
    """
    Get all entities belonging to a specific world.

    Returns entities filtered by world_id or curated_world_id.
    Includes source_name for grouping by import source.
    """
    if lore_id not in LORE_BASES:
        logger.warning(f"Lore base not found in LORE_BASES: {lore_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    # Validate database connection
    if db is None:
        logger.error("Database connection is None when fetching entities")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    try:
        logger.info(f"Fetching entities for world: {lore_id}, type: {entity_type}, source: {source_name}, limit: {limit}")
        
        query = """
            MATCH (e:Entity)
            WHERE e.world_id = $world_id OR e.curated_world_id = $world_id
        """
        params = {"world_id": lore_id}

        if entity_type:
            query += " AND e.entity_type = $entity_type"
            params["entity_type"] = entity_type

        if source_name:
            query += " AND e.source_name = $source_name"
            params["source_name"] = source_name

        query += """
            RETURN e.canon_id as canon_id,
                   e.name as name,
                   e.entity_type as entity_type,
                   e.description as description,
                   e.aliases as aliases,
                   e.goals as goals,
                   e.secrets as secrets,
                   e.fears as fears,
                   e.openness as openness,
                   e.conscientiousness as conscientiousness,
                   e.extraversion as extraversion,
                   e.agreeableness as agreeableness,
                   e.neuroticism as neuroticism,
                   e.confidence_level as confidence,
                   coalesce(e.source_name, e.source) as source_name,
                   e.created_at as created_at,
                   e.director_notes as director_notes
            ORDER BY e.source, e.entity_type, e.name
            LIMIT $limit
        """
        params["limit"] = limit

        logger.debug(f"Executing query with params: {params}")
        result = await db.execute(query, params)
        logger.debug(f"Query returned {len(result) if result else 0} records")

        entities = []
        for record in result:
            try:
                entity_data = {
                    "canon_id": record.get("canon_id"),
                    "name": record.get("name"),
                    "entity_type": record.get("entity_type"),
                    "description": record.get("description") or "",
                    "aliases": record.get("aliases") or [],
                    "confidence": record.get("confidence"),
                    "source_name": record.get("source_name", "unknown"),
                    "created_at": record.get("created_at"),
                }

                # Include character-specific fields if present
                if record.get("goals") is not None:
                    entity_data["goals"] = record.get("goals") or []
                if record.get("secrets") is not None:
                    entity_data["secrets"] = record.get("secrets") or []
                if record.get("fears") is not None:
                    entity_data["fears"] = record.get("fears") or []
                if record.get("openness") is not None:
                    entity_data["openness"] = record.get("openness")
                if record.get("conscientiousness") is not None:
                    entity_data["conscientiousness"] = record.get("conscientiousness")
                if record.get("extraversion") is not None:
                    entity_data["extraversion"] = record.get("extraversion")
                if record.get("agreeableness") is not None:
                    entity_data["agreeableness"] = record.get("agreeableness")
                if record.get("neuroticism") is not None:
                    entity_data["neuroticism"] = record.get("neuroticism")

                # Include director notes if present
                director_notes = record.get("director_notes")
                if director_notes:
                    entity_data["director_notes"] = director_notes

                entities.append(entity_data)
            except Exception as parse_error:
                logger.warning(f"Failed to parse entity record: {parse_error}")
                continue

        logger.info(f"Successfully fetched {len(entities)} entities for world {lore_id}")
        
        return {
            "world_id": lore_id,
            "count": len(entities),
            "entities": entities,
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except AttributeError as e:
        logger.error(f"Database method not available for {lore_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service error - please try again"
        )
    except Exception as e:
        logger.error(f"Failed to get entities for {lore_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve entities: {type(e).__name__}"
        )


@router.get("/lore-bases/{lore_id}/sources")
async def get_world_sources(
    lore_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Get all unique source names for entities in a world.

    Useful for grouping entities by import source file.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    try:
        query = """
            MATCH (e:Entity)
            WHERE e.world_id = $world_id OR e.curated_world_id = $world_id
            WITH e.source_name as source, count(e) as count
            RETURN source, count
            ORDER BY count DESC
        """

        result = await db.execute(query, {"world_id": lore_id})

        sources = []
        for record in result:
            sources.append({
                "source_name": record.get("source") or "unknown",
                "entity_count": record.get("count", 0),
            })

        return {
            "world_id": lore_id,
            "sources": sources,
            "total_sources": len(sources),
        }

    except Exception as e:
        logger.error(f"Failed to get sources for {lore_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sources: {str(e)}"
        )


@router.delete("/lore-bases/{lore_id}/entities/{entity_id}")
async def delete_world_entity(
    lore_id: str,
    entity_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db),
):
    """
    Delete a single entity from a world.

    Also deletes any relationships connected to this entity.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    try:
        # First verify entity exists and belongs to this world
        check_query = """
            MATCH (e:Entity {canon_id: $entity_id})
            WHERE e.world_id = $world_id OR e.curated_world_id = $world_id
            RETURN e.name as name
        """
        check_result = await db.execute(check_query, {
            "entity_id": entity_id,
            "world_id": lore_id,
        })

        records = list(check_result)
        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity '{entity_id}' not found in world '{lore_id}'"
            )

        entity_name = records[0].get("name", entity_id)

        # Delete entity and its relationships
        delete_query = """
            MATCH (e:Entity {canon_id: $entity_id})
            DETACH DELETE e
            RETURN count(e) as deleted
        """
        delete_result = await db.execute(delete_query, {"entity_id": entity_id})

        logger.info(f"Deleted entity {entity_id} ({entity_name}) from world {lore_id}")

        return {
            "success": True,
            "message": f"Deleted entity '{entity_name}'",
            "entity_id": entity_id,
            "world_id": lore_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete entity: {str(e)}"
        )


@router.delete("/lore-bases/{lore_id}/entities")
async def delete_world_entities_bulk(
    lore_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db),
    source_name: Optional[str] = Query(None, description="Delete only entities from this source"),
    entity_type: Optional[str] = Query(None, description="Delete only entities of this type"),
):
    """
    Bulk delete entities from a world.

    Can filter by source_name (import file) and/or entity_type.
    If no filters provided, deletes ALL entities in the world.
    """
    if lore_id not in LORE_BASES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lore base '{lore_id}' not found"
        )

    try:
        # Build the filter description for logging/response
        filters = []
        if source_name:
            filters.append(f"source='{source_name}'")
        if entity_type:
            filters.append(f"type='{entity_type}'")
        filter_desc = ", ".join(filters) if filters else "all entities"

        # First count how many will be deleted
        count_query = """
            MATCH (e:Entity)
            WHERE (e.world_id = $world_id OR e.curated_world_id = $world_id)
        """
        params = {"world_id": lore_id}

        if source_name:
            count_query += " AND e.source_name = $source_name"
            params["source_name"] = source_name

        if entity_type:
            count_query += " AND e.entity_type = $entity_type"
            params["entity_type"] = entity_type

        count_query += " RETURN count(e) as count"
        count_result = await db.execute(count_query, params)
        count_records = list(count_result)
        entity_count = count_records[0].get("count", 0) if count_records else 0

        if entity_count == 0:
            return {
                "success": True,
                "message": f"No entities found matching criteria ({filter_desc})",
                "deleted_count": 0,
                "world_id": lore_id,
            }

        # Delete entities and their relationships
        delete_query = """
            MATCH (e:Entity)
            WHERE (e.world_id = $world_id OR e.curated_world_id = $world_id)
        """

        if source_name:
            delete_query += " AND e.source_name = $source_name"

        if entity_type:
            delete_query += " AND e.entity_type = $entity_type"

        delete_query += " DETACH DELETE e RETURN count(e) as deleted"

        await db.execute(delete_query, params)

        logger.info(f"Bulk deleted {entity_count} entities from world {lore_id} ({filter_desc})")

        return {
            "success": True,
            "message": f"Deleted {entity_count} entities ({filter_desc})",
            "deleted_count": entity_count,
            "world_id": lore_id,
            "filters": {
                "source_name": source_name,
                "entity_type": entity_type,
            }
        }

    except Exception as e:
        logger.error(f"Failed to bulk delete entities from {lore_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete entities: {str(e)}"
        )


# ============================================================
# SESSION LISTING
# ============================================================

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all active sessions."""
    return [
        SessionResponse(
            session_id=sid,
            status=data["status"],
            phase=data["phase"],
            created_at=data["created_at"],
        )
        for sid, data in _active_sessions.items()
    ]


# ============================================================
# SAVE/LOAD SYSTEM (Neo4j persistent, browser-isolated)
# ============================================================

# Max saves per browser (generous limit)
MAX_SAVES_PER_BROWSER = 50


async def _generate_session_summary(
    history: List[Dict[str, str]],
    save_data: Dict[str, Any],
    db: Optional[Neo4jDatabase],
) -> str:
    """
    Generate a narrative summary of the previous session for New Chapter mode.

    Creates a "Last time, on your adventure..." style summary that:
    - Highlights key events and decisions
    - Mentions important NPCs and locations
    - Sets up context for the new chapter
    """
    if not history:
        return "A new chapter begins..."

    # Extract key information for summary context
    character_name = save_data.get("character_name", "the hero")
    world_name = save_data.get("world_name", "the realm")
    genre = save_data.get("genre", "fantasy")

    # Get the last few exchanges for recent context
    recent_history = history[-20:] if len(history) > 20 else history

    # Build conversation text for summarization
    conversation_text = ""
    for entry in recent_history:
        role = "Player" if entry.get("role") == "user" else "Narrator"
        content = entry.get("content", "")[:500]  # Limit per entry
        conversation_text += f"{role}: {content}\n\n"

    # Try to use Gemini for intelligent summarization
    model = get_gemini_model()
    if model:
        try:
            summary_prompt = f"""You are summarizing a {genre} roleplaying story for a player returning after a break.

CHARACTER: {character_name}
WORLD: {world_name}

RECENT STORY EVENTS:
{conversation_text}

Write a brief "Previously, in your adventure..." summary (2-3 short paragraphs) that:
1. Reminds the player what happened
2. Mentions any key characters, locations, or items
3. Sets up anticipation for what comes next
4. Uses second person ("You...")
5. Matches the {genre} tone

Keep it under 200 words. Be evocative but concise."""

            response = model.generate_content(summary_prompt)
            if response and response.text:
                summary = response.text.strip()
                logger.info(f"Generated session summary ({len(summary)} chars)")
                return summary
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")

    # Fallback: Extract key details manually
    # Find mentions of notable elements in recent history
    last_narrator_text = ""
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            last_narrator_text = entry.get("content", "")
            break

    # Simple fallback summary
    if last_narrator_text:
        # Take first 2-3 sentences as context
        sentences = last_narrator_text.split(". ")[:3]
        context = ". ".join(sentences)
        if not context.endswith("."):
            context += "."
        return f"*Previously, in {world_name}...*\n\n{context}\n\nA new chapter begins for {character_name}."

    return f"*A new chapter begins in {world_name}...*\n\nYour adventure continues, {character_name}. The path ahead is yours to forge."


class SaveSlotInfo(BaseModel):
    """Information about a save slot."""
    slot: int
    is_empty: bool
    session_name: Optional[str] = None
    character_concept: Optional[str] = None
    genre: Optional[str] = None
    phase: Optional[str] = None
    turn_count: Optional[int] = None
    saved_at: Optional[datetime] = None
    world_name: Optional[str] = None
    # Character preview data
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    rules_mode: Optional[str] = None
    # Session continuation info
    session_status: Optional[str] = None  # "active", "ended", "mid_scene"
    suggested_mode: Optional[str] = None  # "continue" or "new_chapter"


class InventoryItem(BaseModel):
    """An item in the player's inventory."""
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = "📦"
    quantity: int = 1


class SaveGameRequest(BaseModel):
    """Request to save a game to a slot."""
    slot: int = Field(..., ge=1, le=MAX_SAVES_PER_BROWSER)
    session_name: Optional[str] = Field(default=None, max_length=50)
    inventory: Optional[List[dict]] = Field(default_factory=list)
    browser_id: str = Field(..., min_length=1, max_length=100)
    user_id: Optional[str] = Field(default=None, max_length=100, description="Optional user/account ID for account-based saves")


class SaveGameResponse(BaseModel):
    """Response after saving a game."""
    success: bool
    slot: int
    session_id: str
    message: str


class LoadGameResponse(BaseModel):
    """Response after loading a game."""
    success: bool
    session_id: str
    phase: str
    narrative: str
    message: str
    inventory: List[dict] = Field(default_factory=list)
    character: Optional[dict] = None  # Full character data for restoration
    # Continuation mode fields
    continuation_mode: str = "continue"  # "continue" or "new_chapter"
    session_summary: Optional[str] = None  # Summary for new_chapter mode
    arc_context: Optional[Dict[str, Any]] = None  # Current arc state
    turn_count: int = 0  # Number of turns in this session


@router.get("/saves", response_model=List[SaveSlotInfo])
async def list_save_slots(
    request: Request,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
    user_id: Optional[str] = Query(None, description="Optional user/account ID for account-based saves"),
):
    """
    List all save slots for a specific browser or user.

    Each browser has its own isolated save slots - saves from one browser
    are completely invisible to other browsers. If user_id is provided,
    saves are scoped by user_id instead of browser_id.
    """
    db = get_optional_neo4j_db(request)
    slots = []

    if db:
        try:
            # Query Neo4j for this browser's or user's saves
            # If user_id is provided, scope by user_id; otherwise scope by browser_id
            if user_id:
                query = """
                    MATCH (s:GameSave {user_id: $user_id})
                    RETURN s.slot as slot, s.session_name as session_name,
                           s.character_concept as character_concept, s.genre as genre,
                           s.phase as phase, s.turn_count as turn_count,
                           s.saved_at as saved_at, s.world_name as world_name,
                           s.character_id as character_id, s.character_name as character_name,
                           s.rules_mode as rules_mode, s.session_status as session_status
                    ORDER BY s.slot
                """
                params = {"user_id": user_id}
                logger.debug(f"Listing saves for user_id: {user_id}")
            else:
                query = """
                    MATCH (s:GameSave {browser_id: $browser_id})
                    WHERE s.user_id IS NULL
                    RETURN s.slot as slot, s.session_name as session_name,
                           s.character_concept as character_concept, s.genre as genre,
                           s.phase as phase, s.turn_count as turn_count,
                           s.saved_at as saved_at, s.world_name as world_name,
                           s.character_id as character_id, s.character_name as character_name,
                           s.rules_mode as rules_mode, s.session_status as session_status
                    ORDER BY s.slot
                """
                params = {"browser_id": browser_id}
                logger.debug(f"Listing saves for browser_id: {browser_id[:8]}...")

            results = await db.execute(query, params)

            # Build a map of existing saves
            existing_saves = {}
            for record in results:
                existing_saves[record["slot"]] = record

            # Return slots 1-10 (show first 10, more created on demand)
            for slot_num in range(1, 11):
                if slot_num in existing_saves:
                    save = existing_saves[slot_num]
                    turn_count = save["turn_count"] or 0
                    session_status = save.get("session_status", "active")

                    # Determine suggested continuation mode based on session state
                    # - First session (turn_count == 0): Only "continue" makes sense
                    # - Session ended cleanly: Suggest "new_chapter"
                    # - Session interrupted mid-scene: Suggest "continue"
                    if turn_count == 0:
                        suggested_mode = "continue"  # Just started
                    elif session_status == "ended":
                        suggested_mode = "new_chapter"  # Story concluded
                    else:
                        suggested_mode = "continue"  # Mid-story, resume

                    slots.append(SaveSlotInfo(
                        slot=slot_num,
                        is_empty=False,
                        session_name=save["session_name"],
                        character_concept=save["character_concept"],
                        genre=save["genre"],
                        phase=save["phase"],
                        turn_count=turn_count,
                        saved_at=save["saved_at"],
                        world_name=save["world_name"],
                        character_id=save.get("character_id"),
                        character_name=save.get("character_name"),
                        rules_mode=save.get("rules_mode"),
                        session_status=session_status,
                        suggested_mode=suggested_mode,
                    ))
                else:
                    slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

        except Exception as e:
            logger.error(f"Failed to list saves from Neo4j: {e}")
            # Return empty slots on error
            for slot_num in range(1, 11):
                slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))
    else:
        # No database - return empty slots
        for slot_num in range(1, 11):
            slots.append(SaveSlotInfo(slot=slot_num, is_empty=True))

    return slots


@router.post("/saves/{slot}", response_model=SaveGameResponse)
async def save_game(
    request: Request,
    slot: int,
    session_id: str,
    save_req: SaveGameRequest,
):
    """
    Save a game session to a slot.

    Saves are isolated by browser_id - each browser has its own save slots.
    All session state including history, preferences, and phase is persisted to Neo4j.
    """
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    if session_id not in _active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    session = _active_sessions[session_id]
    browser_id = save_req.browser_id
    user_id = save_req.user_id
    now = datetime.now(timezone.utc)

    # Create save data - include everything needed for full session isolation
    save_data = {
        "session_id": session_id,
        "session_name": save_req.session_name or f"Save {slot}",
        "character_concept": session.get("character_concept"),
        "genre": session.get("genre"),
        "genres": session.get("genres"),
        "genre_blend": session.get("genre_blend"),
        "tone_preference": session.get("tone_preference"),
        "setting_preference": session.get("setting_preference"),
        "storytelling_style": session.get("storytelling_style"),
        "phase": session.get("phase"),
        "history": session.get("history", []),
        "session_0_answers": session.get("session_0_answers", {}),
        "world_id": session.get("world_id"),
        "session_world_id": session.get("session_world_id"),
        "world_name": session.get("world_name"),
        "world_lore_content": session.get("world_lore_content"),
        "inventory": save_req.inventory or [],
        "saved_at": now.isoformat(),
        "created_at": session.get("created_at").isoformat() if session.get("created_at") else now.isoformat(),
        # D&D state
        "character_id": session.get("character_id"),
        "rules_mode": session.get("rules_mode"),
        "rules_visibility": session.get("rules_visibility"),
        "character_data": None,  # Will be populated below
    }

    # Include full character data in save (not just ID) for persistence across server restarts
    char_id = session.get("character_id")
    if char_id:
        char = _characters.get(char_id)
        if char:
            save_data["character_data"] = char.model_dump()
            save_data["character_name"] = char.name  # Populate character_name for save slot display

    db = get_optional_neo4j_db(request)
    if db:
        try:
            # Store the full save data as JSON in Neo4j
            # MERGE to update existing or create new
            # Scope by user_id if provided, otherwise by browser_id
            # Determine session status from session state
            session_status = session.get("status", "active")
            
            if user_id:
                # User-scoped save
                query = """
                    MERGE (s:GameSave {user_id: $user_id, slot: $slot})
                    SET s.session_id = $session_id,
                        s.browser_id = $browser_id,
                        s.session_name = $session_name,
                        s.character_concept = $character_concept,
                        s.genre = $genre,
                        s.phase = $phase,
                        s.turn_count = $turn_count,
                        s.saved_at = datetime(),
                        s.world_name = $world_name,
                        s.character_id = $character_id,
                        s.character_name = $character_name,
                        s.rules_mode = $rules_mode,
                        s.session_status = $session_status,
                        s.save_data = $save_data_json
                """
                params = {"user_id": user_id, "browser_id": browser_id}
                logger.info(f"Saved session {session_id} to Neo4j slot {slot} for user {user_id}")
            else:
                # Browser-scoped save (existing behavior)
                query = """
                    MERGE (s:GameSave {browser_id: $browser_id, slot: $slot})
                    SET s.session_id = $session_id,
                        s.session_name = $session_name,
                        s.character_concept = $character_concept,
                        s.genre = $genre,
                        s.phase = $phase,
                        s.turn_count = $turn_count,
                        s.saved_at = datetime(),
                        s.world_name = $world_name,
                        s.character_id = $character_id,
                        s.character_name = $character_name,
                        s.rules_mode = $rules_mode,
                        s.session_status = $session_status,
                        s.save_data = $save_data_json
                """
                params = {"browser_id": browser_id}
                logger.info(f"Saved session {session_id} to Neo4j slot {slot} for browser {browser_id[:8]}...")
            
            params.update({
                "slot": slot,
                "session_id": session_id,
                "session_name": save_data["session_name"],
                "character_concept": save_data.get("character_concept", ""),
                "genre": save_data.get("genre", "fantasy"),
                "phase": save_data.get("phase", "active_play"),
                "turn_count": len(save_data.get("history", [])) // 2,
                "world_name": save_data.get("world_name", ""),
                "character_id": save_data.get("character_id"),
                "character_name": save_data.get("character_name") or save_data.get("character", {}).get("name"),
                "rules_mode": save_data.get("rules_mode", "narrative"),
                "session_status": session_status,
                "save_data_json": json.dumps(save_data),
            })
            
            await db.execute(query, params)
        except Exception as e:
            logger.error(f"Failed to save to Neo4j: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save game to database"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available for saving"
        )

    return SaveGameResponse(
        success=True,
        slot=slot,
        session_id=session_id,
        message=f"Game saved to slot {slot}"
    )


@router.get("/saves/{slot}/load", response_model=LoadGameResponse)
async def load_game(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
    mode: str = Query("continue", description="Continuation mode: 'continue' or 'new_chapter'"),
    user_id: Optional[str] = Query(None, description="Optional user/account ID for account-based saves"),
):
    """
    Load a game from a save slot with optional continuation mode.

    Args:
        mode: "continue" - Resume exactly where left off with full context
              "new_chapter" - Start fresh arc with summarized history

    Restores the session and returns the last narrative or summary.
    Only loads saves belonging to the specified browser_id or user_id.
    """
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    db = get_optional_neo4j_db(request)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    try:
        # Load save from Neo4j
        # Scope by user_id if provided, otherwise by browser_id
        if user_id:
            query = """
                MATCH (s:GameSave {user_id: $user_id, slot: $slot})
                RETURN s.save_data as save_data_json
            """
            params = {"user_id": user_id, "slot": slot}
            logger.info(f"Loading save from slot {slot} for user {user_id}")
        else:
            query = """
                MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
                WHERE s.user_id IS NULL
                RETURN s.save_data as save_data_json
            """
            params = {"browser_id": browser_id, "slot": slot}
            logger.info(f"Loading save from slot {slot} for browser {browser_id[:8]}...")
        
        results = await db.execute(query, params)

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No save found in slot {slot}"
            )

        save_data = json.loads(results[0]["save_data_json"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load from Neo4j: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load game from database"
        )

    # Create a new session ID for the loaded game
    new_session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Restore session data with all isolation and context fields
    session_data = {
        "session_id": new_session_id,
        "world_id": save_data.get("world_id"),
        "session_world_id": save_data.get("session_world_id"),
        "world_name": save_data.get("world_name"),
        "world_lore_content": save_data.get("world_lore_content"),
        "character_concept": save_data.get("character_concept"),
        "setting_preference": save_data.get("setting_preference"),
        "tone_preference": save_data.get("tone_preference"),
        "genre": save_data.get("genre", "fantasy"),
        "genres": save_data.get("genres"),
        "genre_blend": save_data.get("genre_blend"),
        "storytelling_style": save_data.get("storytelling_style", "guided"),
        "phase": save_data.get("phase", "active_play"),
        "status": "active",
        "created_at": now,
        "history": save_data.get("history", []),
        "session_0_answers": save_data.get("session_0_answers", {}),
        # D&D 5e state
        "character_id": save_data.get("character_id"),
        "rules_mode": save_data.get("rules_mode"),
        "rules_visibility": save_data.get("rules_visibility"),
    }

    _active_sessions[new_session_id] = session_data

    # Restore character from save data (not just ID reference)
    char_data = save_data.get("character_data")
    char_id = save_data.get("character_id")
    if char_data:
        # Full character data available in save
        try:
            character = CharacterSheet.model_validate(char_data)
            _characters[character.character_id] = character
            logger.info(f"Restored character '{character.name}' from save data")
        except Exception as e:
            logger.error(f"Failed to restore character from save: {e}")
    elif char_id and char_id not in _characters:
        # Legacy save without character_data - log warning
        logger.warning(f"Save has character_id {char_id} but no character_data - character may not be available")

    # Get the last narrative to show the player where they left off
    history = save_data.get("history", [])
    turn_count = len(history) // 2

    # Build arc context if available
    arc_context = None
    if ARC_ENGINE_AVAILABLE:
        arc_state = save_data.get("arc_engine_state")
        if arc_state:
            try:
                arc_engine = ArcEngine.from_dict(arc_state)
                session_data["arc_engine"] = arc_engine
                arc_context = {
                    "current_phase": arc_engine.current_phase.value,
                    "phase_display": arc_engine.current_phase.value.replace("_", " ").title(),
                    "tension_level": arc_engine.tension_level.value,
                    "journey_progress": arc_engine.journey_progress,
                }
            except Exception as e:
                logger.warning(f"Failed to restore Arc Engine: {e}")

    if mode == "new_chapter":
        # NEW CHAPTER MODE: Generate summary, reset arc, preserve world
        session_summary = await _generate_session_summary(history, save_data, db)

        # Reset history to just the summary context
        session_data["history"] = [
            {"role": "system", "content": f"PREVIOUS CHAPTER SUMMARY:\n{session_summary}"}
        ]

        # Reset Arc Engine to Call to Adventure (new story arc)
        if ARC_ENGINE_AVAILABLE:
            new_arc = ArcEngine()
            session_data["arc_engine"] = new_arc
            arc_context = {
                "current_phase": "CALL_TO_ADVENTURE",
                "phase_display": "Call To Adventure",
                "tension_level": "low",
                "journey_progress": 0.0,
            }

        narrative = session_summary
        message = f"Starting new chapter in {save_data.get('world_name', 'your world')}"
        logger.info(f"Loaded save from slot {slot} as NEW CHAPTER for browser {browser_id[:8]}...")

    else:
        # CONTINUE MODE: Resume exactly where left off
        last_narrative = "Your adventure continues..."
        for entry in reversed(history):
            if entry.get("role") == "assistant":
                last_narrative = entry.get("content", last_narrative)
                break

        narrative = last_narrative
        message = f"Game loaded from slot {slot}"
        logger.info(f"Loaded save from slot {slot} for browser {browser_id[:8]}... as session {new_session_id}")

    return LoadGameResponse(
        success=True,
        session_id=new_session_id,
        phase=session_data["phase"],
        narrative=narrative,
        message=message,
        inventory=save_data.get("inventory", []),
        character=save_data.get("character_data"),
        continuation_mode=mode,
        session_summary=narrative if mode == "new_chapter" else None,
        arc_context=arc_context,
        turn_count=turn_count,
    )


@router.delete("/saves/{slot}")
async def delete_save(
    request: Request,
    slot: int,
    browser_id: str = Query(..., min_length=1, description="Unique browser identifier"),
    user_id: Optional[str] = Query(None, description="Optional user/account ID for account-based saves"),
):
    """Delete a save from a slot. Only deletes saves belonging to the specified browser_id or user_id."""
    if slot < 1 or slot > MAX_SAVES_PER_BROWSER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot must be between 1 and {MAX_SAVES_PER_BROWSER}"
        )

    db = get_optional_neo4j_db(request)
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    try:
        # Delete from Neo4j - scope by user_id if provided, otherwise by browser_id
        if user_id:
            query = """
                MATCH (s:GameSave {user_id: $user_id, slot: $slot})
                DELETE s
                RETURN count(*) as deleted
            """
            params = {"user_id": user_id, "slot": slot}
            logger.info(f"Deleting save from slot {slot} for user {user_id}")
        else:
            query = """
                MATCH (s:GameSave {browser_id: $browser_id, slot: $slot})
                WHERE s.user_id IS NULL
                DELETE s
                RETURN count(*) as deleted
            """
            params = {"browser_id": browser_id, "slot": slot}
            logger.info(f"Deleting save from slot {slot} for browser {browser_id[:8]}...")
        
        result = await db.execute(query, params)

        if not result or result[0]["deleted"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No save found in slot {slot}"
            )

        logger.info(f"Deleted save from slot {slot} for browser {browser_id[:8]}...")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete from Neo4j: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete save from database"
        )

    return {"success": True, "message": f"Save slot {slot} cleared"}


# ============================================================
# GRAPH VISUALIZATION
# ============================================================

@router.get("/graph")
async def get_graph_data(
    request: Request,
    world_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    session_id: Optional[str] = None,
    genre: Optional[str] = None,
    curated_world: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
):
    """
    Get graph data for visualization with robust filtering.

    Returns nodes and edges in a format suitable for vis.js or similar libraries.

    Args:
        world_id: Filter by session-scoped world ID
        entity_type: Filter by entity type (Character, Location, Faction, Item, Event, Concept)
        session_id: Filter to show only entities from a specific game session
        genre: Filter by genre tag
        curated_world: Filter by curated world ID (e.g., "eldoria", "veiled_city")
        search: Text search within entity names
        limit: Maximum number of nodes to return
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"nodes": [], "edges": [], "filters_applied": {}}

    try:
        # Build filter clauses dynamically
        filters = []
        params = {"limit": limit}

        if world_id:
            filters.append("n.world_id = $world_id")
            params["world_id"] = world_id

        if curated_world:
            # Match either curated_world_id or world_id (for directly ingested lore bases)
            filters.append("(n.curated_world_id = $curated_world OR n.world_id = $curated_world)")
            params["curated_world"] = curated_world

        if entity_type:
            filters.append("(n.entity_type = $entity_type OR labels(n)[0] = $entity_type)")
            params["entity_type"] = entity_type

        if session_id:
            filters.append("n.session_id = $session_id")
            params["session_id"] = session_id

        if genre:
            filters.append("(n.genre = $genre OR $genre IN n.genres)")
            params["genre"] = genre

        if search:
            filters.append("(toLower(n.name) CONTAINS toLower($search) OR toLower(n.description) CONTAINS toLower($search))")
            params["search"] = search

        # Combine filters with AND
        filter_clause = ""
        if filters:
            filter_clause = "AND " + " AND ".join(filters)

        # Get all entities (nodes)
        node_query = f"""
        MATCH (n)
        WHERE (n.canon_id IS NOT NULL OR n.name IS NOT NULL)
        {filter_clause}
        RETURN
            COALESCE(n.canon_id, id(n)) AS id,
            COALESCE(n.name, n.canonical_name, 'Unknown') AS label,
            labels(n)[0] AS type,
            n.entity_type AS entity_type,
            n.openness AS openness,
            n.description AS description,
            n.world_id AS world_id,
            n.session_id AS session_id,
            n.genre AS genre
        LIMIT $limit
        """
        nodes_result = await db.execute(node_query, params)

        # Build edge filter to match node filters
        edge_filters = []
        edge_params = {"limit": limit * 2}
        if world_id:
            edge_filters.append("(a.world_id = $world_id OR b.world_id = $world_id)")
            edge_params["world_id"] = world_id
        if entity_type:
            edge_filters.append("(a.entity_type = $entity_type OR b.entity_type = $entity_type OR labels(a)[0] = $entity_type OR labels(b)[0] = $entity_type)")
            edge_params["entity_type"] = entity_type
        if session_id:
            edge_filters.append("(a.session_id = $session_id OR b.session_id = $session_id)")
            edge_params["session_id"] = session_id

        edge_filter_clause = ""
        if edge_filters:
            edge_filter_clause = "AND " + " AND ".join(edge_filters)

        # Get all relationships (edges)
        edge_query = f"""
        MATCH (a)-[r]->(b)
        WHERE (a.canon_id IS NOT NULL OR a.name IS NOT NULL)
          AND (b.canon_id IS NOT NULL OR b.name IS NOT NULL)
        {edge_filter_clause}
        RETURN
            COALESCE(a.canon_id, id(a)) AS from,
            COALESCE(b.canon_id, id(b)) AS to,
            type(r) AS label
        LIMIT $limit
        """
        edges_result = await db.execute(edge_query, edge_params)

        # Format for vis.js
        nodes = []
        for row in nodes_result:
            node_type = row.get("entity_type") or row.get("type") or "Entity"

            # Color by type
            colors = {
                "Character": "#c98b8b",
                "Location": "#8ba88b",
                "Faction": "#a08bc9",
                "Item": "#e8c47c",
                "Event": "#8b9fc9",
                "Concept": "#d4a574",
            }
            color = colors.get(node_type, "#b8a99a")

            nodes.append({
                "id": row["id"],
                "label": row["label"],
                "group": node_type,
                "color": color,
                "title": row.get("description", "")[:200] if row.get("description") else node_type,
            })

        edges = []
        for row in edges_result:
            edges.append({
                "from": row["from"],
                "to": row["to"],
                "label": row["label"],
                "arrows": "to",
            })

        # Track which filters were applied
        filters_applied = {}
        if world_id:
            filters_applied["world_id"] = world_id
        if curated_world:
            filters_applied["curated_world"] = curated_world
        if entity_type:
            filters_applied["entity_type"] = entity_type
        if session_id:
            filters_applied["session_id"] = session_id
        if genre:
            filters_applied["genre"] = genre
        if search:
            filters_applied["search"] = search

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
            "filters_applied": filters_applied
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


@router.get("/graph/filters")
async def get_graph_filter_options(request: Request):
    """
    Get available filter options for the graph visualization.

    Returns lists of unique values for: entity types, sessions, genres, worlds.
    This populates the filter dropdowns in the UI.
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"entity_types": [], "sessions": [], "genres": [], "worlds": []}

    try:
        # Get distinct entity types
        types_query = """
        MATCH (n)
        WHERE n.entity_type IS NOT NULL
        RETURN DISTINCT n.entity_type AS entity_type
        ORDER BY entity_type
        """
        types_result = await db.execute(types_query, {})
        entity_types = [row["entity_type"] for row in types_result if row.get("entity_type")]

        # Get sessions from GameSession nodes for rich metadata
        sessions_query = """
        MATCH (s:GameSession)
        RETURN s.session_id AS session_id,
               s.world_id AS world_id,
               s.character_name AS character_name,
               s.genre AS genre,
               s.turn_count AS turn_count,
               s.status AS status,
               s.is_curated_world AS is_curated,
               s.curated_world_name AS curated_name,
               s.created_at AS created_at
        ORDER BY s.created_at DESC
        LIMIT 100
        """
        sessions_result = await db.execute(sessions_query, {})
        sessions = []
        for row in sessions_result:
            if row.get("session_id"):
                sessions.append({
                    "id": row["session_id"],
                    "world": row.get("world_id", ""),
                    "character_name": row.get("character_name", ""),
                    "genre": row.get("genre", "fantasy"),
                    "turn_count": row.get("turn_count", 0),
                    "status": row.get("status", "unknown"),
                    "is_curated": row.get("is_curated", False),
                    "curated_name": row.get("curated_name", ""),
                })

        # Get distinct genres
        genres_query = """
        MATCH (n)
        WHERE n.genre IS NOT NULL
        RETURN DISTINCT n.genre AS genre
        ORDER BY genre
        """
        genres_result = await db.execute(genres_query, {})
        genres = [row["genre"] for row in genres_result if row.get("genre")]

        # Get distinct worlds (both session-scoped and curated)
        worlds_query = """
        MATCH (n)
        WHERE n.world_id IS NOT NULL OR n.curated_world_id IS NOT NULL
        RETURN DISTINCT
            n.world_id AS world_id,
            n.curated_world_id AS curated_world_id
        LIMIT 200
        """
        worlds_result = await db.execute(worlds_query, {})

        # Separate curated worlds from session-scoped worlds
        curated_worlds = set()
        session_worlds = set()
        for row in worlds_result:
            if row.get("curated_world_id"):
                curated_worlds.add(row["curated_world_id"])
            if row.get("world_id"):
                wid = row["world_id"]
                # Check if it's a session-scoped world (has underscore + 8 char suffix)
                if "_" in wid and len(wid.split("_")[-1]) == 8:
                    session_worlds.add(wid)
                else:
                    # It's a curated world used directly
                    curated_worlds.add(wid)

        # Also add curated worlds from LORE_BASES
        for lore_id in LORE_BASES.keys():
            curated_worlds.add(lore_id)

        return {
            "entity_types": entity_types or ["Character", "Location", "Faction", "Item", "Event", "Concept"],
            "sessions": sessions,
            "genres": genres,
            "worlds": sorted(list(session_worlds))[:100],  # Session-scoped worlds
            "curated_worlds": sorted(list(curated_worlds)),  # Curated worlds from lore bases
        }

    except Exception as e:
        logger.error(f"Failed to get graph filter options: {e}")
        return {
            "entity_types": ["Character", "Location", "Faction", "Item", "Event", "Concept"],
            "sessions": [],
            "genres": [],
            "worlds": []
        }


@router.get("/graph/node/{node_id}")
async def get_node_details(
    request: Request,
    node_id: str,
):
    """
    Get full details for a specific node in the graph.

    Returns all properties stored on the node, including OCEAN personality
    traits for characters, goals, fears, secrets, etc.
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"error": "Database not available", "node_id": node_id}

    try:
        # Fetch all properties for the node
        query = """
        MATCH (n)
        WHERE n.canon_id = $node_id OR n.name = $node_id OR id(n) = toInteger($node_id)
        RETURN
            COALESCE(n.canon_id, toString(id(n))) AS id,
            labels(n) AS labels,
            properties(n) AS props
        LIMIT 1
        """
        result = await db.execute(query, {"node_id": node_id})

        if not result:
            return {"error": "Node not found", "node_id": node_id}

        row = result[0]
        node_labels = row.get("labels", [])
        props = row.get("props", {})

        # Determine entity type from labels or props
        entity_type = props.get("entity_type") or (node_labels[0] if node_labels else "Unknown")

        # Extract OCEAN personality traits
        ocean = {}
        ocean_keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
        for key in ocean_keys:
            if key in props:
                ocean[key] = props[key]

        # Extract relationships
        rel_query = """
        MATCH (n)-[r]-(other)
        WHERE n.canon_id = $node_id OR n.name = $node_id OR id(n) = toInteger($node_id)
        RETURN
            type(r) AS rel_type,
            CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction,
            COALESCE(other.name, other.canonical_name, 'Unknown') AS other_name,
            labels(other)[0] AS other_type
        LIMIT 20
        """
        rel_result = await db.execute(rel_query, {"node_id": node_id})

        relationships = []
        for rel_row in rel_result:
            relationships.append({
                "type": rel_row["rel_type"],
                "direction": rel_row["direction"],
                "target_name": rel_row["other_name"],
                "target_type": rel_row["other_type"],
            })

        return {
            "id": row["id"],
            "labels": node_labels,
            "entity_type": entity_type,
            "name": props.get("name") or props.get("canonical_name") or "Unknown",
            "description": props.get("description", ""),
            "properties": props,
            "ocean": ocean if ocean else None,
            "relationships": relationships,
        }

    except Exception as e:
        logger.error(f"Node detail query failed: {e}")
        return {"error": str(e), "node_id": node_id}


# ============================================================
# DUPLICATE DETECTION & MERGE
# ============================================================

def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0.0 to 1.0)."""
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    if n1 == n2:
        return 1.0

    # Check if one is substring of another
    if n1 in n2 or n2 in n1:
        return 0.85

    # Levenshtein-based similarity
    max_len = max(len(n1), len(n2))
    if max_len == 0:
        return 1.0

    distance = _levenshtein_distance(n1, n2)
    return 1.0 - (distance / max_len)


def _check_alias_overlap(entity1: dict, entity2: dict) -> bool:
    """Check if either entity's name appears in the other's aliases."""
    name1 = (entity1.get("name") or "").lower().strip()
    name2 = (entity2.get("name") or "").lower().strip()
    aliases1 = [a.lower().strip() for a in (entity1.get("aliases") or [])]
    aliases2 = [a.lower().strip() for a in (entity2.get("aliases") or [])]

    # Check if name1 is in aliases2 or vice versa
    if name1 and name1 in aliases2:
        return True
    if name2 and name2 in aliases1:
        return True

    # Check for alias overlap
    for a1 in aliases1:
        if a1 in aliases2:
            return True

    return False


class DuplicatePair(BaseModel):
    """A potential duplicate pair."""
    entity1_id: str
    entity1_name: str
    entity1_type: str
    entity1_description: str = ""
    entity1_aliases: List[str] = []
    entity2_id: str
    entity2_name: str
    entity2_type: str
    entity2_description: str = ""
    entity2_aliases: List[str] = []
    similarity_score: float
    match_reasons: List[str] = []


class DuplicateDetectionResponse(BaseModel):
    """Response from duplicate detection."""
    world_id: str
    total_entities: int
    duplicates_found: int
    pairs: List[DuplicatePair]


@router.get("/lore-bases/{lore_id}/duplicates", response_model=DuplicateDetectionResponse)
async def detect_duplicates(
    lore_id: str,
    threshold: float = Query(default=0.7, ge=0.5, le=1.0, description="Minimum similarity threshold"),
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Detect potential duplicate entities within a lore base.

    Uses multiple signals to find duplicates:
    - Name similarity (Levenshtein distance)
    - Alias overlap (one entity's name in another's aliases)
    - Same entity type constraint

    Returns pairs sorted by similarity score (highest first).
    """
    # Get all entities for this world
    result = await db.execute("""
        MATCH (e:Entity)
        WHERE e.curated_world_id = $world_id OR e.world_id = $world_id
        RETURN e.canon_id AS canon_id,
               e.name AS name,
               e.entity_type AS entity_type,
               e.description AS description,
               e.aliases AS aliases
        ORDER BY e.name
    """, {"world_id": lore_id})

    entities = [dict(r) for r in result]
    total_entities = len(entities)

    if total_entities < 2:
        return DuplicateDetectionResponse(
            world_id=lore_id,
            total_entities=total_entities,
            duplicates_found=0,
            pairs=[]
        )

    # Compare all pairs (same type only)
    duplicate_pairs = []
    seen_pairs = set()

    for i, e1 in enumerate(entities):
        for j, e2 in enumerate(entities):
            if i >= j:
                continue  # Skip self and already-compared pairs

            # Only compare same entity types
            if e1.get("entity_type") != e2.get("entity_type"):
                continue

            # Create pair key to avoid duplicates
            pair_key = tuple(sorted([e1["canon_id"], e2["canon_id"]]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Calculate similarity
            name_sim = _name_similarity(e1.get("name", ""), e2.get("name", ""))
            alias_overlap = _check_alias_overlap(e1, e2)

            # Determine final score and reasons
            match_reasons = []
            final_score = name_sim

            if alias_overlap:
                final_score = max(final_score, 0.9)  # Alias overlap is strong signal
                match_reasons.append("Alias overlap")

            if name_sim >= 0.8:
                match_reasons.append(f"Name similarity: {name_sim:.0%}")
            elif name_sim >= threshold:
                match_reasons.append(f"Name similar: {name_sim:.0%}")

            # Check if above threshold
            if final_score >= threshold:
                duplicate_pairs.append(DuplicatePair(
                    entity1_id=e1["canon_id"],
                    entity1_name=e1.get("name", "Unknown"),
                    entity1_type=e1.get("entity_type", "Unknown"),
                    entity1_description=(e1.get("description") or "")[:200],
                    entity1_aliases=e1.get("aliases") or [],
                    entity2_id=e2["canon_id"],
                    entity2_name=e2.get("name", "Unknown"),
                    entity2_type=e2.get("entity_type", "Unknown"),
                    entity2_description=(e2.get("description") or "")[:200],
                    entity2_aliases=e2.get("aliases") or [],
                    similarity_score=round(final_score, 2),
                    match_reasons=match_reasons,
                ))

    # Sort by similarity (highest first)
    duplicate_pairs.sort(key=lambda p: p.similarity_score, reverse=True)

    logger.info(f"Duplicate detection for {lore_id}: {len(duplicate_pairs)} pairs found from {total_entities} entities")

    return DuplicateDetectionResponse(
        world_id=lore_id,
        total_entities=total_entities,
        duplicates_found=len(duplicate_pairs),
        pairs=duplicate_pairs
    )


class MergeEntitiesRequest(BaseModel):
    """Request to merge two entities."""
    primary_id: str = Field(..., description="The entity to keep (canon_id)")
    secondary_id: str = Field(..., description="The entity to merge into primary and delete (canon_id)")
    merge_descriptions: bool = Field(default=True, description="Combine descriptions")
    merge_aliases: bool = Field(default=True, description="Combine aliases")
    merge_traits: bool = Field(default=True, description="Combine personality traits")


class MergeEntitiesResponse(BaseModel):
    """Response after merging entities."""
    success: bool
    primary_id: str
    deleted_id: str
    aliases_added: int
    relationships_transferred: int
    message: str


@router.post("/entities/merge", response_model=MergeEntitiesResponse)
async def merge_entities(
    merge_req: MergeEntitiesRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Merge two entities into one.

    The primary entity is kept, and the secondary entity's data is merged in:
    - Secondary's name is added to primary's aliases
    - Secondary's aliases are added to primary's aliases
    - All relationships pointing to secondary are redirected to primary
    - Optionally merges descriptions, traits, goals, secrets, fears
    - Secondary entity is deleted

    This follows the Gospel Principle: humans decide which entities to merge.
    """
    primary_id = merge_req.primary_id
    secondary_id = merge_req.secondary_id

    if primary_id == secondary_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot merge an entity with itself"
        )

    # Verify both entities exist
    check_result = await db.execute("""
        MATCH (p:Entity {canon_id: $primary_id})
        MATCH (s:Entity {canon_id: $secondary_id})
        RETURN p.name AS primary_name, p.aliases AS primary_aliases,
               p.description AS primary_desc, p.goals AS primary_goals,
               p.secrets AS primary_secrets, p.fears AS primary_fears,
               p.personality_traits AS primary_traits,
               s.name AS secondary_name, s.aliases AS secondary_aliases,
               s.description AS secondary_desc, s.goals AS secondary_goals,
               s.secrets AS secondary_secrets, s.fears AS secondary_fears,
               s.personality_traits AS secondary_traits
    """, {"primary_id": primary_id, "secondary_id": secondary_id})

    if not check_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both entities not found"
        )

    row = check_result[0]

    # Build merged aliases
    new_aliases = list(row.get("primary_aliases") or [])
    secondary_name = row.get("secondary_name")
    if secondary_name and secondary_name not in new_aliases:
        new_aliases.append(secondary_name)
    if merge_req.merge_aliases:
        for alias in (row.get("secondary_aliases") or []):
            if alias not in new_aliases:
                new_aliases.append(alias)

    aliases_added = len(new_aliases) - len(row.get("primary_aliases") or [])

    # Build update properties
    update_props = {"aliases": new_aliases}

    if merge_req.merge_descriptions:
        primary_desc = row.get("primary_desc") or ""
        secondary_desc = row.get("secondary_desc") or ""
        if secondary_desc and secondary_desc not in primary_desc:
            # Append secondary description if different
            if primary_desc:
                update_props["description"] = f"{primary_desc}\n\n[Merged from {secondary_name}]: {secondary_desc}"
            else:
                update_props["description"] = secondary_desc

    if merge_req.merge_traits:
        # Merge goals, secrets, fears, traits
        for field in ["goals", "secrets", "fears", "personality_traits"]:
            primary_vals = list(row.get(f"primary_{field.replace('personality_', '')}") or [])
            secondary_vals = row.get(f"secondary_{field.replace('personality_', '')}") or []
            for val in secondary_vals:
                if val not in primary_vals:
                    primary_vals.append(val)
            if primary_vals:
                update_props[field] = primary_vals

    # Update primary entity with merged data
    await db.execute("""
        MATCH (p:Entity {canon_id: $primary_id})
        SET p += $props
    """, {"primary_id": primary_id, "props": update_props})

    # Transfer relationships from secondary to primary
    # First, get all relationship types on the secondary entity
    rel_types_result = await db.execute("""
        MATCH (s:Entity {canon_id: $secondary_id})-[r]-()
        RETURN DISTINCT type(r) AS rel_type
    """, {"secondary_id": secondary_id})

    relationships_transferred = 0

    # For each relationship type, transfer relationships
    for rel_row in rel_types_result:
        rel_type = rel_row["rel_type"]
        if not rel_type:
            continue

        # Outgoing: secondary -> target becomes primary -> target
        await db.execute(f"""
            MATCH (s:Entity {{canon_id: $secondary_id}})-[r:`{rel_type}`]->(target)
            MATCH (p:Entity {{canon_id: $primary_id}})
            WHERE NOT (p)-[:`{rel_type}`]->(target)
            CREATE (p)-[nr:`{rel_type}`]->(target)
            SET nr = properties(r)
            DELETE r
        """, {"primary_id": primary_id, "secondary_id": secondary_id})

        # Incoming: source -> secondary becomes source -> primary
        await db.execute(f"""
            MATCH (source)-[r:`{rel_type}`]->(s:Entity {{canon_id: $secondary_id}})
            MATCH (p:Entity {{canon_id: $primary_id}})
            WHERE NOT (source)-[:`{rel_type}`]->(p) AND source <> p
            CREATE (source)-[nr:`{rel_type}`]->(p)
            SET nr = properties(r)
            DELETE r
        """, {"primary_id": primary_id, "secondary_id": secondary_id})

        relationships_transferred += 1

    # Clean up any remaining relationships on secondary
    await db.execute("""
        MATCH (s:Entity {canon_id: $secondary_id})-[r]-()
        DELETE r
    """, {"secondary_id": secondary_id})

    # Delete secondary entity
    await db.execute("""
        MATCH (s:Entity {canon_id: $secondary_id})
        DETACH DELETE s
    """, {"secondary_id": secondary_id})

    logger.info(f"Merged entity {secondary_id} into {primary_id}: +{aliases_added} aliases")

    return MergeEntitiesResponse(
        success=True,
        primary_id=primary_id,
        deleted_id=secondary_id,
        aliases_added=aliases_added,
        relationships_transferred=relationships_transferred,
        message=f"Successfully merged '{secondary_name}' into primary entity. Added {aliases_added} aliases."
    )


class EntityUpdateRequest(BaseModel):
    """Request to update an entity."""
    name: Optional[str] = None
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    secrets: Optional[List[str]] = None
    fears: Optional[List[str]] = None
    openness: Optional[float] = None
    conscientiousness: Optional[float] = None
    extraversion: Optional[float] = None
    agreeableness: Optional[float] = None
    neuroticism: Optional[float] = None


class EntityUpdateResponse(BaseModel):
    """Response after updating an entity."""
    success: bool
    canon_id: str
    message: str


@router.put("/entities/{canon_id}", response_model=EntityUpdateResponse)
async def update_entity(
    canon_id: str,
    update_req: EntityUpdateRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Update an existing entity's properties.

    Allows updating name, description, aliases, and for characters:
    goals, secrets, fears, and OCEAN personality scores.
    """
    # Check entity exists
    check_result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name, e.entity_type AS entity_type
    """, {"canon_id": canon_id})

    if not check_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    # Build update properties
    update_props = {}

    if update_req.name is not None:
        update_props["name"] = update_req.name
    if update_req.description is not None:
        update_props["description"] = update_req.description
    if update_req.aliases is not None:
        update_props["aliases"] = update_req.aliases
    if update_req.goals is not None:
        update_props["goals"] = update_req.goals
    if update_req.secrets is not None:
        update_props["secrets"] = update_req.secrets
    if update_req.fears is not None:
        update_props["fears"] = update_req.fears
    if update_req.openness is not None:
        update_props["openness"] = update_req.openness
    if update_req.conscientiousness is not None:
        update_props["conscientiousness"] = update_req.conscientiousness
    if update_req.extraversion is not None:
        update_props["extraversion"] = update_req.extraversion
    if update_req.agreeableness is not None:
        update_props["agreeableness"] = update_req.agreeableness
    if update_req.neuroticism is not None:
        update_props["neuroticism"] = update_req.neuroticism

    if not update_props:
        return EntityUpdateResponse(
            success=True,
            canon_id=canon_id,
            message="No changes provided"
        )

    await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        SET e += $props
    """, {"canon_id": canon_id, "props": update_props})

    logger.info(f"Updated entity {canon_id}: {list(update_props.keys())}")

    return EntityUpdateResponse(
        success=True,
        canon_id=canon_id,
        message=f"Updated {len(update_props)} properties"
    )


class ApplyPendingRequest(BaseModel):
    """Request to apply pending entity data to existing entity."""
    name: Optional[str] = None
    description: Optional[str] = None
    aliases: Optional[List[str]] = None


class ApplyPendingResponse(BaseModel):
    """Response after applying pending data."""
    success: bool
    canon_id: str
    message: str


@router.post("/entities/{canon_id}/apply-pending", response_model=ApplyPendingResponse)
async def apply_pending_to_entity(
    canon_id: str,
    pending_req: ApplyPendingRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Apply pending entity data to an existing entity (merge operation from pending duplicates).

    This is used when a user confirms a pending duplicate should be merged into
    an existing entity during ingestion review.
    """
    # Check entity exists
    check_result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name, e.aliases AS aliases, e.description AS description
    """, {"canon_id": canon_id})

    if not check_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    row = check_result[0]
    update_props = {}

    # Merge aliases
    if pending_req.aliases:
        existing_aliases = list(row.get("aliases") or [])
        for alias in pending_req.aliases:
            if alias not in existing_aliases:
                existing_aliases.append(alias)
        # Also add the pending entity's name as an alias if different
        if pending_req.name and pending_req.name != row.get("name") and pending_req.name not in existing_aliases:
            existing_aliases.append(pending_req.name)
        update_props["aliases"] = existing_aliases

    # Update description if pending has a longer/more detailed one
    if pending_req.description:
        existing_desc = row.get("description") or ""
        if len(pending_req.description) > len(existing_desc):
            update_props["description"] = pending_req.description

    if update_props:
        await db.execute("""
            MATCH (e:Entity {canon_id: $canon_id})
            SET e += $props
        """, {"canon_id": canon_id, "props": update_props})

    logger.info(f"Applied pending data to entity {canon_id}")

    return ApplyPendingResponse(
        success=True,
        canon_id=canon_id,
        message=f"Merged pending entity data into '{row.get('name')}'"
    )


class CreatePendingRequest(BaseModel):
    """Request to create a pending entity (user confirmed it's different)."""
    world_id: str
    name: str
    entity_type: str
    description: Optional[str] = None
    aliases: Optional[List[str]] = None


class CreatePendingResponse(BaseModel):
    """Response after creating a pending entity."""
    success: bool
    canon_id: str
    message: str


@router.post("/entities/create-pending", response_model=CreatePendingResponse)
async def create_pending_entity(
    create_req: CreatePendingRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Create an entity that was flagged as a pending duplicate.

    This is used when a user confirms a pending duplicate is actually a
    different entity and should be created separately.
    """
    from src.mantle.agents.lore_parsing_agent import _generate_human_readable_id
    from datetime import datetime, timezone

    # Generate a unique canon_id
    canon_id = _generate_human_readable_id(
        name=create_req.name,
        entity_type=create_req.entity_type,
        world_id=create_req.world_id
    )

    timestamp = datetime.now(timezone.utc).isoformat()

    props = {
        "canon_id": canon_id,
        "name": create_req.name,
        "entity_type": create_req.entity_type,
        "description": create_req.description or "",
        "aliases": create_req.aliases or [],
        "curated_world_id": create_req.world_id,
        "world_id": create_req.world_id,
        "confidence_level": "ADMIN_APPROVED",
        "approval_status": "APPROVED",
        "created_at": timestamp,
        "source": "pending_duplicate_review",
    }

    # Determine label
    label = create_req.entity_type.replace(" ", "_")
    if label not in ["Character", "Location", "Faction", "Item", "Event", "Concept"]:
        label = "Entity"

    try:
        await db.execute(f"""
            CREATE (e:`{label}` $props)
            SET e:Entity
        """, {"props": props})

        # Link to LoreBase
        await db.execute("""
            MATCH (e:Entity {canon_id: $canon_id})
            MATCH (lb:LoreBase {lore_id: $world_id})
            MERGE (e)-[:EXISTS_IN]->(lb)
        """, {"canon_id": canon_id, "world_id": create_req.world_id})

        logger.info(f"Created pending entity {canon_id} in world {create_req.world_id}")

        return CreatePendingResponse(
            success=True,
            canon_id=canon_id,
            message=f"Created '{create_req.name}' as a new entity"
        )

    except Exception as e:
        logger.error(f"Failed to create pending entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create entity: {str(e)}"
        )


@router.delete("/entities/{canon_id}")
async def delete_entity(
    canon_id: str,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Delete an entity by its canon_id.

    This permanently removes the entity and all its relationships.
    """
    # Check entity exists
    check_result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name
    """, {"canon_id": canon_id})

    if not check_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    entity_name = check_result[0].get("name", canon_id)

    # Delete entity and all its relationships
    await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        DETACH DELETE e
    """, {"canon_id": canon_id})

    logger.info(f"Deleted entity {canon_id} ({entity_name})")

    return {"success": True, "message": f"Deleted entity '{entity_name}'"}


# ============================================================
# DIRECTOR NOTES - Admin guidance for AI behavior
# ============================================================

@router.post("/entities/{canon_id}/director-note")
async def add_director_note(
    canon_id: str,
    http_request: Request,
):
    """
    Add a director note to an entity.

    Director notes are guidance for the AI on how to portray this entity.
    They get injected into the AI's context when this entity is referenced.

    Examples:
    - "This character is paranoid and never trusts strangers"
    - "This location is more rundown than the description suggests"
    - "This faction would never ally with the Crown"
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")

    try:
        body = await http_request.json()
        note = body.get("note", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not note:
        raise HTTPException(status_code=400, detail="Note cannot be empty")

    # Check entity exists
    check_result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name, e.director_notes AS existing_notes
    """, {"canon_id": canon_id})

    if not check_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    entity_name = check_result[0].get("name", canon_id)
    existing_notes = check_result[0].get("existing_notes") or []

    # Add the new note
    new_notes = existing_notes + [note]

    await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        SET e.director_notes = $notes
    """, {"canon_id": canon_id, "notes": new_notes})

    logger.info(f"Added director note to {canon_id} ({entity_name}): {note[:50]}...")

    return {
        "success": True,
        "message": f"Added director note to '{entity_name}'",
        "notes": new_notes,
        "note_count": len(new_notes)
    }


@router.delete("/entities/{canon_id}/director-note/{note_index}")
async def remove_director_note(
    canon_id: str,
    note_index: int,
    http_request: Request,
):
    """
    Remove a director note from an entity by index.
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")

    # Get current notes
    result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name, e.director_notes AS notes
    """, {"canon_id": canon_id})

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    entity_name = result[0].get("name", canon_id)
    notes = result[0].get("notes") or []

    if note_index < 0 or note_index >= len(notes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Note index {note_index} out of range (0-{len(notes)-1})"
        )

    removed_note = notes.pop(note_index)

    await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        SET e.director_notes = $notes
    """, {"canon_id": canon_id, "notes": notes})

    logger.info(f"Removed director note {note_index} from {canon_id}: {removed_note[:50]}...")

    return {
        "success": True,
        "message": f"Removed director note from '{entity_name}'",
        "removed_note": removed_note,
        "notes": notes,
        "note_count": len(notes)
    }


@router.get("/entities/{canon_id}/director-notes")
async def get_director_notes(
    canon_id: str,
    http_request: Request,
):
    """
    Get all director notes for an entity.
    """
    db = getattr(http_request.app.state, "neo4j_db", None)
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")

    result = await db.execute("""
        MATCH (e:Entity {canon_id: $canon_id})
        RETURN e.name AS name, e.director_notes AS notes
    """, {"canon_id": canon_id})

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity '{canon_id}' not found"
        )

    return {
        "entity_name": result[0].get("name"),
        "canon_id": canon_id,
        "notes": result[0].get("notes") or [],
        "note_count": len(result[0].get("notes") or [])
    }


# ============================================================
# ENTITY PROMOTION - Promote session entities to canon
# ============================================================

class PromoteEntityRequest(BaseModel):
    """Request to promote session entity(ies) to canon."""
    entity_ids: List[str] = Field(..., min_length=1, description="List of canon_ids to promote")
    target_world_id: str = Field(..., description="Target curated world ID to promote to")
    promote_relationships: bool = Field(
        default=False,
        description="If true, also promote relationships between promoted entities"
    )
    keep_session_entity: bool = Field(
        default=False,
        description="If true, keep the session entity and link it to canon; if false, delete session entity"
    )


class PromoteEntityResponse(BaseModel):
    """Response from entity promotion."""
    success: bool
    promoted_count: int
    promoted_entities: List[Dict[str, Any]]
    relationships_promoted: int
    message: str


@router.post("/admin/entities/promote", response_model=PromoteEntityResponse)
async def promote_entities_to_canon(
    promote_req: PromoteEntityRequest,
    db: Neo4jDatabase = Depends(get_neo4j_db)
):
    """
    Promote session-created entities to canon.
    
    This creates new canon entities in the specified curated world with properties
    copied from session entities. Optionally promotes relationships and links
    session entities to their canon counterparts.
    
    Use cases:
    - DM creates NPCs during a session and wants to promote them to canon
    - Session events that should become part of world history
    - Locations discovered/created during play that become canonical
    
    Metadata tracking:
    - Canon entities get `promoted_from_canon_id` field pointing to session entity
    - Session entities get `promoted_to_canon_id` field pointing to canon entity
    - Canon entities get `origin_session_id` for traceability
    """
    from src.mantle.agents.lore_parsing_agent import _generate_human_readable_id
    from datetime import datetime, timezone
    
    target_world = promote_req.target_world_id
    entity_ids = promote_req.entity_ids
    
    # Verify target world exists
    world_check = await db.execute("""
        MATCH (lb:LoreBase {lore_id: $world_id})
        RETURN lb.name AS name
    """, {"world_id": target_world})
    
    if not world_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target world '{target_world}' not found"
        )
    
    # Fetch all session entities to promote
    entities_result = await db.execute("""
        MATCH (e:Entity)
        WHERE e.canon_id IN $entity_ids
        RETURN e {.*} AS entity
    """, {"entity_ids": entity_ids})
    
    if not entities_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entities found with provided canon_ids"
        )
    
    timestamp = datetime.now(timezone.utc).isoformat()
    promoted_entities = []
    canon_id_mapping = {}  # session_canon_id -> new_canon_id
    
    # Promote each entity
    for row in entities_result:
        session_entity = row["entity"]
        session_canon_id = session_entity["canon_id"]
        session_id = session_entity.get("session_id")
        
        # Generate new canon_id for the promoted entity
        new_canon_id = _generate_human_readable_id(
            name=session_entity["name"],
            entity_type=session_entity["entity_type"],
            world_id=target_world
        )
        
        # Store mapping
        canon_id_mapping[session_canon_id] = new_canon_id
        
        # Copy properties from session entity
        canon_props = {
            "canon_id": new_canon_id,
            "name": session_entity["name"],
            "entity_type": session_entity["entity_type"],
            "description": session_entity.get("description", ""),
            "aliases": session_entity.get("aliases") or [],
            "curated_world_id": target_world,
            "world_id": target_world,
            "tags": session_entity.get("tags") or [],
            "created_at": timestamp,
            "promoted_from_canon_id": session_canon_id,
            "origin_session_id": session_id,
            "confidence_level": "ADMIN_PROMOTED",
            "approval_status": "APPROVED",
        }
        
        # Copy OCEAN personality if present (for characters)
        for ocean_trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            if ocean_trait in session_entity:
                canon_props[ocean_trait] = session_entity[ocean_trait]
        
        # Copy character-specific fields
        for char_field in ["goals", "secrets", "fears", "personality_traits"]:
            if char_field in session_entity:
                canon_props[char_field] = session_entity[char_field]
        
        # Copy faction-specific fields
        if session_entity["entity_type"] == "Faction":
            for faction_field in ["goals", "secrets", "fears"]:
                if faction_field in session_entity:
                    canon_props[faction_field] = session_entity[faction_field]
        
        # Determine label (whitelisted to prevent injection)
        label = session_entity["entity_type"].replace(" ", "_")
        # Security: Whitelist of valid labels (safe for Cypher)
        valid_labels = ["Character", "Location", "Faction", "Item", "Event", "Concept"]
        if label not in valid_labels:
            label = "Entity"
        
        # Create canon entity (label is whitelisted, safe for f-string)
        await db.execute(f"""
            CREATE (e:`{label}` $props)
            SET e:Entity
        """, {"props": canon_props})
        
        # Link to LoreBase
        await db.execute("""
            MATCH (e:Entity {canon_id: $canon_id})
            MATCH (lb:LoreBase {lore_id: $world_id})
            MERGE (e)-[:EXISTS_IN]->(lb)
        """, {"canon_id": new_canon_id, "world_id": target_world})
        
        # Update session entity with promotion metadata
        if promote_req.keep_session_entity:
            await db.execute("""
                MATCH (e:Entity {canon_id: $session_id})
                SET e.promoted_to_canon_id = $canon_id,
                    e.promoted_at = $timestamp
            """, {
                "session_id": session_canon_id,
                "canon_id": new_canon_id,
                "timestamp": timestamp
            })
        
        promoted_entities.append({
            "session_canon_id": session_canon_id,
            "new_canon_id": new_canon_id,
            "name": session_entity["name"],
            "entity_type": session_entity["entity_type"],
        })
    
    # Promote relationships if requested
    relationships_promoted = 0
    if promote_req.promote_relationships:
        # Get all relationships between promoted entities
        for session_id, canon_id in canon_id_mapping.items():
            # Get outgoing relationships from this session entity to other promoted entities
            rels_result = await db.execute("""
                MATCH (a:Entity {canon_id: $session_id})-[r]->(b:Entity)
                WHERE b.canon_id IN $promoted_ids
                RETURN type(r) AS rel_type, b.canon_id AS target_session_id, properties(r) AS rel_props
            """, {"session_id": session_id, "promoted_ids": list(canon_id_mapping.keys())})
            
            for rel_row in rels_result:
                rel_type = rel_row["rel_type"]
                target_session_id = rel_row["target_session_id"]
                rel_props = rel_row["rel_props"] or {}
                
                # Security: Validate rel_type from database (should already be safe, but double-check)
                # Relationship types from Neo4j should be alphanumeric+underscore
                if not re.match(r"^[A-Z_a-z0-9]+$", rel_type):
                    logger.warning(f"Skipping relationship with invalid type: {rel_type}")
                    continue
                
                # Get canon ids for both entities
                source_canon = canon_id_mapping.get(session_id)
                target_canon = canon_id_mapping.get(target_session_id)
                
                if source_canon and target_canon:
                    # Create relationship between canon entities (rel_type validated, safe for f-string)
                    await db.execute(f"""
                        MATCH (a:Entity {{canon_id: $source}})
                        MATCH (b:Entity {{canon_id: $target}})
                        MERGE (a)-[r:`{rel_type}`]->(b)
                        SET r = $props,
                            r.promoted_from_session = true,
                            r.promoted_at = $timestamp
                    """, {
                        "source": source_canon,
                        "target": target_canon,
                        "props": rel_props,
                        "timestamp": timestamp
                    })
                    relationships_promoted += 1
    
    # Delete session entities if not keeping them
    if not promote_req.keep_session_entity:
        await db.execute("""
            MATCH (e:Entity)
            WHERE e.canon_id IN $session_ids
            DETACH DELETE e
        """, {"session_ids": entity_ids})
    
    logger.info(
        f"Promoted {len(promoted_entities)} entities from session to canon world '{target_world}'"
        f" ({relationships_promoted} relationships promoted)"
    )
    
    return PromoteEntityResponse(
        success=True,
        promoted_count=len(promoted_entities),
        promoted_entities=promoted_entities,
        relationships_promoted=relationships_promoted,
        message=f"Successfully promoted {len(promoted_entities)} entities to '{target_world}'"
    )


# ============================================================
# CROSS-WORLD RELATIONSHIP CLEANUP
# ============================================================

class CrossWorldRelationship(BaseModel):
    """A relationship that spans across worlds."""
    rel_id: Optional[int] = None
    rel_type: str
    source_canon_id: str
    source_name: str
    source_world_id: Optional[str] = None
    target_canon_id: str
    target_name: str
    target_world_id: Optional[str] = None


class CrossWorldRelationshipsResponse(BaseModel):
    """Response from cross-world relationship detection."""
    total_relationships: int
    cross_world_relationships: int
    relationships: List[CrossWorldRelationship]


@router.get("/admin/relationships/cross-world", response_model=CrossWorldRelationshipsResponse)
async def detect_cross_world_relationships(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    limit: int = Query(default=100, le=1000, description="Maximum number of relationships to return")
):
    """
    Detect relationships that link entities across different worlds.
    
    These are problematic because they can leak lore between sessions or
    between unrelated curated worlds.
    
    A relationship is cross-world if:
    - Start and end entities have different `curated_world_id` values
    - Start and end entities have different `world_id` values (session-scoped)
    - One entity has a world_id/curated_world_id and the other doesn't
    
    This endpoint helps identify the bug's damage for cleanup.
    """
    # Find relationships where start and end nodes are in different worlds
    result = await db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE (
            (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NOT NULL AND a.curated_world_id <> b.curated_world_id)
            OR (a.world_id IS NOT NULL AND b.world_id IS NOT NULL AND a.world_id <> b.world_id)
            OR (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NULL AND a.world_id IS NULL)
            OR (b.curated_world_id IS NOT NULL AND a.curated_world_id IS NULL AND b.world_id IS NULL)
        )
        RETURN id(r) AS rel_id,
               type(r) AS rel_type,
               a.canon_id AS source_canon_id,
               a.name AS source_name,
               COALESCE(a.curated_world_id, a.world_id) AS source_world_id,
               b.canon_id AS target_canon_id,
               b.name AS target_name,
               COALESCE(b.curated_world_id, b.world_id) AS target_world_id
        LIMIT $limit
    """, {"limit": limit})
    
    cross_world_rels = []
    for row in result:
        cross_world_rels.append(CrossWorldRelationship(
            rel_id=row.get("rel_id"),
            rel_type=row.get("rel_type", "UNKNOWN"),
            source_canon_id=row.get("source_canon_id", ""),
            source_name=row.get("source_name", ""),
            source_world_id=row.get("source_world_id"),
            target_canon_id=row.get("target_canon_id", ""),
            target_name=row.get("target_name", ""),
            target_world_id=row.get("target_world_id"),
        ))
    
    # Get total relationship count for context
    total_result = await db.execute("""
        MATCH ()-[r]->()
        RETURN count(r) AS total
    """, {})
    total_rels = total_result[0]["total"] if total_result else 0
    
    logger.info(f"Found {len(cross_world_rels)} cross-world relationships out of {total_rels} total")
    
    return CrossWorldRelationshipsResponse(
        total_relationships=total_rels,
        cross_world_relationships=len(cross_world_rels),
        relationships=cross_world_rels
    )


@router.delete("/admin/relationships/cross-world")
async def delete_cross_world_relationships(
    db: Neo4jDatabase = Depends(get_neo4j_db),
    dry_run: bool = Query(default=True, description="If true, only count without deleting")
):
    """
    Delete relationships that link entities across different worlds.
    
    WARNING: This is destructive. Use dry_run=true first to preview what will be deleted.
    
    This cleans up the damage from the cross-world linking bug by removing
    relationships where start and end entities belong to different worlds.
    
    Safe to run repeatedly - only affects cross-world relationships.
    """
    # Count cross-world relationships first
    count_result = await db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE (
            (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NOT NULL AND a.curated_world_id <> b.curated_world_id)
            OR (a.world_id IS NOT NULL AND b.world_id IS NOT NULL AND a.world_id <> b.world_id)
            OR (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NULL AND a.world_id IS NULL)
            OR (b.curated_world_id IS NOT NULL AND a.curated_world_id IS NULL AND b.world_id IS NULL)
        )
        RETURN count(r) AS count
    """, {})
    
    count = count_result[0]["count"] if count_result else 0
    
    if dry_run:
        logger.info(f"[DRY RUN] Would delete {count} cross-world relationships")
        return {
            "dry_run": True,
            "would_delete": count,
            "message": f"Dry run complete. {count} cross-world relationships found. Set dry_run=false to delete."
        }
    
    # Actually delete cross-world relationships
    delete_result = await db.execute("""
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE (
            (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NOT NULL AND a.curated_world_id <> b.curated_world_id)
            OR (a.world_id IS NOT NULL AND b.world_id IS NOT NULL AND a.world_id <> b.world_id)
            OR (a.curated_world_id IS NOT NULL AND b.curated_world_id IS NULL AND a.world_id IS NULL)
            OR (b.curated_world_id IS NOT NULL AND a.curated_world_id IS NULL AND b.world_id IS NULL)
        )
        DELETE r
        RETURN count(*) AS deleted
    """, {})
    
    deleted = delete_result[0]["deleted"] if delete_result else 0
    
    logger.warning(f"Deleted {deleted} cross-world relationships")
    
    return {
        "dry_run": False,
        "deleted": deleted,
        "message": f"Successfully deleted {deleted} cross-world relationships"
    }
