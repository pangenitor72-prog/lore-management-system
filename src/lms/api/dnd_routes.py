"""d20 Rules Engine API Routes (genre-agnostic with D&D 5e compatibility)."""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

# Genre system
from ..dnd5e.genre import GenreConfig, get_genre, get_available_genres

# Models (generic with backward-compatible aliases)
from ..dnd5e.models import (
    get_origin, get_origins_for_genre,
    get_archetype, get_archetypes_for_genre,
    get_ability, get_abilities_for_genre,
    CharacterSheet,
    # Backward compatible
    RACES, CLASSES, get_all_races, get_all_classes,
)
from ..dnd5e.creation.modes import (
    CreationMode, RulesVisibility, DEFAULT_VISIBILITY,
    get_mode_description, get_visibility_description
)
from ..dnd5e.creation.concept_generator import ConceptGenerator
from ..dnd5e.creation.guided_flow import GuidedCreationFlow
from ..dnd5e.creation.classic_flow import ClassicCreationFlow
from ..dnd5e.engine.checks import CheckEngine, SKILL_TO_ABILITY, DIFFICULTY_CLASS
from ..dnd5e.engine.combat_resolver import CombatResolver
from ..dnd5e.presentation.visibility import VisibilityFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dnd", tags=["d20 Rules Engine"])


# Request/Response Models

class CharacterCreateRequest(BaseModel):
    """Request to create a character."""
    mode: CreationMode = CreationMode.GUIDED
    genre: str = "fantasy"  # fantasy, scifi, modern, horror
    concept: Optional[str] = None  # For CONCEPT mode
    name: Optional[str] = None
    origin: Optional[str] = None  # Generic term (race in fantasy)
    archetype: Optional[str] = None  # Generic term (class in fantasy)
    # Backward compatible aliases
    race: Optional[str] = None
    character_class: Optional[str] = None
    ability_assignments: Optional[Dict[str, int]] = None  # For CLASSIC mode
    skill_proficiencies: Optional[List[str]] = None
    player_id: str = ""

    def get_origin(self) -> Optional[str]:
        """Get origin, preferring new field over legacy."""
        return self.origin or self.race

    def get_archetype(self) -> Optional[str]:
        """Get archetype, preferring new field over legacy."""
        return self.archetype or self.character_class


class CharacterResponse(BaseModel):
    """Summary response for a character."""
    character_id: str
    name: str
    genre: str = "fantasy"
    origin: str  # Generic term
    archetype: str  # Generic term
    # Backward compatible aliases
    race: str = ""
    character_class: str = ""
    level: int
    hit_points: int
    max_hit_points: int
    armor_class: int


class CharacterDetailResponse(BaseModel):
    """Full character sheet response."""
    character: Dict[str, Any]
    display: Dict[str, Any]  # Visibility-filtered display data


class RaceResponse(BaseModel):
    """Race information response."""
    id: str
    name: str
    description: str
    ability_bonuses: Dict[str, int]
    traits: List[str]
    speed: int


class ClassResponse(BaseModel):
    """Class information response."""
    id: str
    name: str
    description: str
    hit_die: str
    primary_ability: str
    features: List[str]
    spellcasting: bool


class RollRequest(BaseModel):
    """Request to perform a roll."""
    roll_type: str = "skill"  # skill, ability, save, attack
    skill: Optional[str] = None
    ability: Optional[str] = None
    dc: int = 15
    advantage: bool = False
    disadvantage: bool = False
    target_ac: Optional[int] = None  # For attack rolls


class RollResponse(BaseModel):
    """Response from a roll."""
    success: bool
    roll: int
    total: int
    display: str  # Visibility-appropriate display
    narrative: str


class VisibilityRequest(BaseModel):
    """Request to update visibility settings."""
    rules_visibility: RulesVisibility


class GuidedStepRequest(BaseModel):
    """Request for guided creation step."""
    choice: str


# In-memory storage for creation flows (would be session-based in production)
_creation_flows: Dict[str, Any] = {}
_characters: Dict[str, CharacterSheet] = {}
_visibility_settings: Dict[str, RulesVisibility] = {}


# Endpoints

# =============================================================================
# GENRE ENDPOINTS
# =============================================================================

@router.get("/genres")
async def list_genres():
    """Get all available genres with their descriptions."""
    return get_available_genres()


@router.get("/genres/{genre_id}")
async def get_genre_details(genre_id: str):
    """Get detailed information about a specific genre."""
    genre = get_genre(genre_id)
    return {
        "id": genre.id.value,
        "name": genre.name,
        "description": genre.description,
        "terminology": genre.terminology.model_dump(),
        "example_origins": genre.example_origins,
        "example_archetypes": genre.example_archetypes,
        "has_magic": genre.has_magic,
        "gritty_mode": genre.gritty_mode,
        "sanity_system": genre.sanity_system,
    }


@router.get("/genres/{genre_id}/origins")
async def list_origins_for_genre(genre_id: str):
    """Get all available origins for a genre."""
    origins = get_origins_for_genre(genre_id)
    genre = get_genre(genre_id)
    return {
        "genre": genre_id,
        "term": genre.terminology.origin,
        "term_plural": genre.terminology.origin_plural,
        "origins": [
            {
                "id": origin.id,
                "name": origin.display_name,
                "description": origin.description,
                "ability_bonuses": origin.ability_bonuses,
                "traits": origin.traits,
                "speed": origin.speed,
            }
            for origin in origins
        ]
    }


@router.get("/genres/{genre_id}/archetypes")
async def list_archetypes_for_genre(genre_id: str):
    """Get all available archetypes for a genre."""
    archetypes = get_archetypes_for_genre(genre_id)
    genre = get_genre(genre_id)
    return {
        "genre": genre_id,
        "term": genre.terminology.archetype,
        "term_plural": genre.terminology.archetype_plural,
        "archetypes": [
            {
                "id": arch.id,
                "name": arch.display_name,
                "description": arch.description,
                "hit_die": arch.hit_die.value,
                "primary_ability": arch.primary_ability,
                "features": arch.features_by_level.get(1, []),
                "has_powers": arch.has_powers,
            }
            for arch in archetypes
        ]
    }


# =============================================================================
# BACKWARD COMPATIBLE REFERENCE ENDPOINTS (Fantasy/D&D 5e)
# =============================================================================

@router.get("/reference/races", response_model=List[RaceResponse])
async def list_races():
    """Get all available races (fantasy origins). Backward compatible."""
    return [
        RaceResponse(
            id=origin.id,
            name=origin.display_name,
            description=origin.description,
            ability_bonuses=origin.ability_bonuses,
            traits=origin.traits,
            speed=origin.speed,
        )
        for origin in get_origins_for_genre("fantasy")
    ]


@router.get("/reference/classes", response_model=List[ClassResponse])
async def list_classes():
    """Get all available classes (fantasy archetypes). Backward compatible."""
    return [
        ClassResponse(
            id=arch.id,
            name=arch.display_name,
            description=arch.description,
            hit_die=arch.hit_die.value,
            primary_ability=arch.primary_ability,
            features=arch.features_by_level.get(1, []),
            spellcasting=arch.has_powers,
        )
        for arch in get_archetypes_for_genre("fantasy")
    ]


@router.get("/reference/skills")
async def list_skills():
    """Get all skills and their associated abilities."""
    return {
        skill: ability.value
        for skill, ability in SKILL_TO_ABILITY.items()
    }


@router.get("/reference/difficulty")
async def get_difficulty_classes():
    """Get standard difficulty class reference."""
    return DIFFICULTY_CLASS


@router.get("/creation/modes")
async def get_creation_modes():
    """Get available character creation modes with descriptions."""
    return [
        {
            "id": mode.value,
            **get_mode_description(mode),
            "default_visibility": DEFAULT_VISIBILITY[mode].value,
        }
        for mode in CreationMode
    ]


@router.get("/visibility/modes")
async def get_visibility_modes():
    """Get available visibility modes with descriptions."""
    return [
        {
            "id": visibility.value,
            **get_visibility_description(visibility),
        }
        for visibility in RulesVisibility
    ]


@router.post("/characters/concept", response_model=CharacterResponse)
async def create_character_from_concept(request: CharacterCreateRequest):
    """
    Create a character from a natural language concept.

    Example: "A gruff dwarf blacksmith who became an adventurer"
    Supports all genres - concept will be interpreted in genre context.
    """
    if not request.concept:
        raise HTTPException(status_code=400, detail="Concept is required for concept mode")

    genre = request.genre or "fantasy"
    generator = ConceptGenerator(genre=genre)
    character = generator.generate_from_concept_sync(
        request.concept,
        player_id=request.player_id,
    )

    _characters[character.character_id] = character
    logger.info(f"Created {genre} character from concept: {character.name}")

    # Get display names using genre-aware lookups
    origin_data = get_origin(character.origin, genre)
    archetype_data = get_archetype(character.archetype, genre)

    return CharacterResponse(
        character_id=character.character_id,
        name=character.name,
        genre=genre,
        origin=origin_data.display_name if origin_data else character.origin,
        archetype=archetype_data.display_name if archetype_data else character.archetype,
        # Backward compatible
        race=origin_data.display_name if origin_data else character.origin,
        character_class=archetype_data.display_name if archetype_data else character.archetype,
        level=character.level,
        hit_points=character.current_hit_points,
        max_hit_points=character.max_hit_points,
        armor_class=character.armor_class,
    )


@router.post("/characters/guided/start")
async def start_guided_creation(player_id: str = ""):
    """Start a guided character creation flow."""
    flow = GuidedCreationFlow()
    flow_id = f"guided_{player_id or 'anon'}_{len(_creation_flows)}"
    _creation_flows[flow_id] = flow

    return {
        "flow_id": flow_id,
        "step": flow.get_current_step(),
        "content": flow.get_step_content(),
    }


@router.post("/characters/guided/{flow_id}/step")
async def guided_creation_step(flow_id: str, request: GuidedStepRequest):
    """Submit a choice for the current guided creation step."""
    flow = _creation_flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Creation flow not found")

    step = flow.get_current_step()

    if step == 0:
        success = flow.set_name(request.choice)
    elif step == 1:
        success = flow.set_race(request.choice)
    elif step == 2:
        success = flow.set_class(request.choice)
    elif step == 3:
        success = flow.set_strength_priority(request.choice)
    elif step == 4:
        # Skills are passed as comma-separated
        skills = [s.strip() for s in request.choice.split(",")]
        success = flow.set_skills(skills)
    else:
        success = False

    if not success:
        raise HTTPException(status_code=400, detail="Invalid choice for this step")

    # Check if complete
    if flow.get_current_step() == 5:
        return {
            "flow_id": flow_id,
            "step": flow.get_current_step(),
            "content": flow.get_step_content(),
            "ready_to_finalize": True,
        }

    return {
        "flow_id": flow_id,
        "step": flow.get_current_step(),
        "content": flow.get_step_content(),
    }


@router.post("/characters/guided/{flow_id}/finalize", response_model=CharacterResponse)
async def finalize_guided_creation(flow_id: str, player_id: str = ""):
    """Finalize the guided creation and create the character."""
    flow = _creation_flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Creation flow not found")

    try:
        character = flow.finalize(player_id)
        _characters[character.character_id] = character

        # Clean up flow
        del _creation_flows[flow_id]

        logger.info(f"Finalized guided character: {character.name}")

        return CharacterResponse(
            character_id=character.character_id,
            name=character.name,
            race=RACES[character.race].display_name,
            character_class=CLASSES[character.character_class].display_name,
            level=character.level,
            hit_points=character.current_hit_points,
            max_hit_points=character.max_hit_points,
            armor_class=character.armor_class,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/characters/classic/start")
async def start_classic_creation(player_id: str = ""):
    """Start a classic character creation flow."""
    flow = ClassicCreationFlow()
    flow_id = f"classic_{player_id or 'anon'}_{len(_creation_flows)}"
    _creation_flows[flow_id] = flow

    return {
        "flow_id": flow_id,
        "step": flow.get_current_step(),
        "options": flow.get_step_options(),
    }


@router.get("/characters/{character_id}", response_model=CharacterDetailResponse)
async def get_character(character_id: str, visibility: Optional[str] = None):
    """Get a character's full sheet."""
    character = _characters.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    vis_mode = RulesVisibility(visibility) if visibility else RulesVisibility(character.rules_visibility)

    # Filter display based on visibility
    display = character.to_summary_dict()
    if vis_mode == RulesVisibility.STORYTELLER:
        # Minimal mechanical info
        display = {
            "name": character.name,
            "race": RACES[character.race].display_name,
            "class": CLASSES[character.character_class].display_name,
            "health_status": "healthy" if character.current_hit_points > character.max_hit_points // 2 else "wounded",
        }
    elif vis_mode == RulesVisibility.GUIDED:
        # Some mechanical hints
        display["health_status"] = f"{character.current_hit_points}/{character.max_hit_points} HP"
    # CLASSIC and TACTICIAN get full display

    return CharacterDetailResponse(
        character=character.model_dump(),
        display=display,
    )


@router.post("/characters/{character_id}/roll", response_model=RollResponse)
async def perform_roll(character_id: str, request: RollRequest):
    """Perform a dice roll for a character."""
    character = _characters.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    vis_mode = RulesVisibility(character.rules_visibility)

    if request.roll_type == "skill" and request.skill:
        from ..dnd5e.models.ability_scores import AbilityName
        result = CheckEngine.skill_check(
            character,
            request.skill,
            request.dc,
            advantage=request.advantage,
            disadvantage=request.disadvantage,
        )
        filtered = VisibilityFilter.filter_check_result(result, vis_mode)

        return RollResponse(
            success=result.success,
            roll=result.roll,
            total=result.total,
            display=filtered.get("display", f"{result.total} vs DC {request.dc}"),
            narrative=filtered.get("description", result.narrative_outcome),
        )

    elif request.roll_type == "attack" and request.target_ac:
        attack_result = CombatResolver.resolve_attack(
            character,
            request.target_ac,
            advantage=request.advantage,
            disadvantage=request.disadvantage,
        )
        filtered = VisibilityFilter.filter_attack_result(attack_result, vis_mode)

        return RollResponse(
            success=attack_result.is_hit,
            roll=attack_result.attack_roll,
            total=attack_result.attack_total,
            display=filtered.get("display", f"{attack_result.attack_total} vs AC {request.target_ac}"),
            narrative=filtered.get("description", attack_result.narrative_outcome),
        )

    elif request.roll_type == "ability" and request.ability:
        from ..dnd5e.models.ability_scores import AbilityName
        ability = AbilityName(request.ability)
        result = CheckEngine.ability_check(
            character,
            ability,
            request.dc,
            advantage=request.advantage,
            disadvantage=request.disadvantage,
        )
        filtered = VisibilityFilter.filter_check_result(result, vis_mode)

        return RollResponse(
            success=result.success,
            roll=result.roll,
            total=result.total,
            display=filtered.get("display", f"{result.total} vs DC {request.dc}"),
            narrative=filtered.get("description", result.narrative_outcome),
        )

    elif request.roll_type == "save" and request.ability:
        from ..dnd5e.models.ability_scores import AbilityName
        ability = AbilityName(request.ability)
        result = CheckEngine.saving_throw(
            character,
            ability,
            request.dc,
            advantage=request.advantage,
            disadvantage=request.disadvantage,
        )
        filtered = VisibilityFilter.filter_check_result(result, vis_mode)

        return RollResponse(
            success=result.success,
            roll=result.roll,
            total=result.total,
            display=filtered.get("display", f"{result.total} vs DC {request.dc}"),
            narrative=filtered.get("description", result.narrative_outcome),
        )

    raise HTTPException(status_code=400, detail="Invalid roll request")


@router.post("/characters/{character_id}/damage")
async def apply_damage(character_id: str, damage: int):
    """Apply damage to a character."""
    character = _characters.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    updated = character.take_damage(damage)
    _characters[character_id] = updated

    return {
        "character_id": character_id,
        "damage_taken": damage,
        "current_hp": updated.current_hit_points,
        "max_hp": updated.max_hit_points,
        "is_conscious": updated.is_conscious,
    }


@router.post("/characters/{character_id}/heal")
async def apply_healing(character_id: str, healing: int):
    """Apply healing to a character."""
    character = _characters.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    updated = character.heal(healing)
    _characters[character_id] = updated

    return {
        "character_id": character_id,
        "healing": healing,
        "current_hp": updated.current_hit_points,
        "max_hp": updated.max_hit_points,
    }


@router.post("/characters/{character_id}/rest")
async def long_rest(character_id: str):
    """Perform a long rest, restoring HP and spell slots."""
    character = _characters.get(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    updated = character.long_rest()
    _characters[character_id] = updated

    return {
        "character_id": character_id,
        "current_hp": updated.current_hit_points,
        "spell_slots_restored": True,
        "conditions_cleared": True,
    }


@router.post("/settings/visibility")
async def update_visibility(request: VisibilityRequest, session_id: str = "default"):
    """Update the rules visibility setting for a session."""
    _visibility_settings[session_id] = request.rules_visibility
    return {
        "session_id": session_id,
        "visibility": request.rules_visibility.value,
    }


@router.get("/settings/visibility")
async def get_visibility(session_id: str = "default"):
    """Get the current visibility setting for a session."""
    visibility = _visibility_settings.get(session_id, RulesVisibility.GUIDED)
    return {
        "session_id": session_id,
        "visibility": visibility.value,
        "description": get_visibility_description(visibility),
    }
