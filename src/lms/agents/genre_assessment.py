"""
Genre Assessment Agent

AI-powered agent that analyzes world lore and determines:
1. mechanics_genre: Single authoritative genre for mechanical options (origins, archetypes, equipment, powers)
2. genre_hints: List of narrative flavor tags for storytelling
3. confidence: Assessment confidence score
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GenreAssessment(BaseModel):
    """Result of genre assessment for a world."""
    mechanics_genre: str = Field(
        description="Single authoritative genre for mechanical options. "
                    "One of: fantasy, scifi, modern, horror, western, cyberpunk, steampunk, "
                    "postapoc, superhero, mythology, noir, wuxia, pirate, dark_fantasy, space_opera"
    )
    genre_hints: List[str] = Field(
        default_factory=list,
        description="List of narrative flavor tags/genres (fantasy, mystery, romance, drama, etc.)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the assessment (0.0-1.0)"
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of why this genre was chosen"
    )


# Valid mechanics genres (must match GenreConfig IDs)
VALID_MECHANICS_GENRES = {
    "fantasy", "scifi", "modern", "horror", "western", "cyberpunk", "steampunk",
    "postapoc", "superhero", "mythology", "noir", "wuxia", "pirate", 
    "dark_fantasy", "space_opera", "generic"
}


def assess_genre_from_text(lore_text: str, gemini_client=None) -> GenreAssessment:
    """
    Assess the mechanics genre and narrative flavor from lore text.
    
    Args:
        lore_text: World lore content to analyze
        gemini_client: Optional Gemini client for AI assessment (falls back to keyword matching)
        
    Returns:
        GenreAssessment with mechanics_genre, genre_hints, and confidence
    """
    if not lore_text or len(lore_text.strip()) < 50:
        # Too short to assess meaningfully, default to fantasy
        return GenreAssessment(
            mechanics_genre="fantasy",
            genre_hints=["fantasy"],
            confidence=0.3,
            reasoning="Insufficient lore content for assessment"
        )
    
    # Try AI assessment first if client available
    if gemini_client:
        try:
            return _ai_assess_genre(lore_text, gemini_client)
        except Exception as e:
            logger.warning(f"AI genre assessment failed, falling back to keyword matching: {e}")
    
    # Fallback to keyword-based assessment
    return _keyword_assess_genre(lore_text)


def _ai_assess_genre(lore_text: str, gemini_client) -> GenreAssessment:
    """Use AI (Gemini) to assess genre from lore text."""
    prompt = f"""Analyze this world lore and determine its genre for RPG character creation.

World Lore:
{lore_text[:3000]}

Determine:
1. **mechanics_genre**: The single PRIMARY genre that should determine available character options (races/origins, classes/archetypes, equipment, powers). This affects game mechanics.

Valid mechanics_genre options:
- fantasy: Magic, medieval, swords & sorcery, elves, wizards, dragons
- scifi: Future tech, space, aliens, robots, lasers, starships
- modern: Contemporary real world, guns, cars, no magic or sci-fi
- horror: Modern with supernatural/horror elements, monsters, survival
- western: Wild West, cowboys, outlaws, frontier
- cyberpunk: Near-future dystopia, hackers, corporations, augmentation
- steampunk: Victorian tech, steam power, airships, gadgets
- postapoc: Post-apocalyptic wasteland, survival, scavenging
- superhero: Modern with superpowers, heroes, vigilantes
- mythology: Ancient mythological setting (Greek, Norse, etc.)
- noir: 1940s detective noir, crime, mystery
- wuxia: Chinese martial arts fantasy, cultivation, qi
- pirate: Age of sail, pirates, naval adventures
- dark_fantasy: Grimdark fantasy, bleak, brutal
- space_opera: Epic space fantasy, galactic empires

2. **genre_hints**: Additional narrative flavor tags (can include fantasy, mystery, romance, drama, thriller, comedy, etc.)

3. **confidence**: How confident are you in this assessment? (0.0-1.0)

4. **reasoning**: Brief explanation (1 sentence)

Return JSON only:
{{
    "mechanics_genre": "primary_genre_here",
    "genre_hints": ["tag1", "tag2", "tag3"],
    "confidence": 0.9,
    "reasoning": "One sentence explanation"
}}"""

    response = gemini_client.generate_content(prompt)
    text = response.text
    
    # Extract JSON from response
    json_match = re.search(r'\{[^{}]*"mechanics_genre"[^{}]*\}', text, re.DOTALL)
    if not json_match:
        raise ValueError("Could not parse AI response as JSON")
    
    data = json.loads(json_match.group())
    
    # Validate mechanics_genre
    mechanics_genre = data.get("mechanics_genre", "fantasy").lower()
    if mechanics_genre not in VALID_MECHANICS_GENRES:
        # Try to map to closest valid genre
        mechanics_genre = _map_to_valid_genre(mechanics_genre)
    
    return GenreAssessment(
        mechanics_genre=mechanics_genre,
        genre_hints=data.get("genre_hints", [mechanics_genre]),
        confidence=min(1.0, max(0.0, float(data.get("confidence", 0.7)))),
        reasoning=data.get("reasoning", "AI assessment")
    )


def _keyword_assess_genre(lore_text: str) -> GenreAssessment:
    """Fallback keyword-based genre assessment."""
    text_lower = lore_text.lower()
    
    # Genre keyword patterns with weights
    genre_patterns = {
        "scifi": [
            ("space", 3), ("starship", 4), ("alien", 3), ("robot", 3), ("android", 4),
            ("laser", 3), ("plasma", 3), ("cybernetic", 3), ("colony", 2), ("galaxy", 3),
            ("warp", 4), ("hyperspace", 4), ("federation", 2), ("empire", 1)
        ],
        "cyberpunk": [
            ("hacker", 4), ("netrunner", 5), ("corpo", 4), ("augment", 3), ("chrome", 3),
            ("cyberdeck", 5), ("neural", 3), ("megacorp", 4), ("neon", 2), ("street", 1)
        ],
        "horror": [
            ("monster", 3), ("vampire", 4), ("werewolf", 4), ("zombie", 4), ("demon", 3),
            ("curse", 3), ("haunted", 3), ("terror", 2), ("nightmare", 2), ("eldritch", 4),
            ("cult", 3), ("ritual", 2)
        ],
        "modern": [
            ("detective", 3), ("police", 3), ("city", 1), ("car", 2), ("phone", 2),
            ("apartment", 2), ("office", 1), ("gun", 2), ("street", 1), ("realistic", 3)
        ],
        "western": [
            ("cowboy", 5), ("outlaw", 4), ("sheriff", 4), ("saloon", 4), ("frontier", 4),
            ("revolver", 4), ("ranch", 3), ("cattle", 3), ("dusty", 2), ("frontier", 4)
        ],
        "steampunk": [
            ("steam", 3), ("clockwork", 4), ("airship", 4), ("brass", 3), ("gear", 2),
            ("victorian", 4), ("goggles", 3), ("contraption", 3), ("automaton", 4)
        ],
        "postapoc": [
            ("wasteland", 5), ("radiation", 4), ("survivor", 3), ("scavenger", 4),
            ("mutant", 4), ("ruins", 2), ("vault", 4), ("apocalypse", 4), ("fallout", 4)
        ],
        "superhero": [
            ("hero", 2), ("superpower", 5), ("villain", 3), ("cape", 3), ("vigilante", 4),
            ("powers", 2), ("meta", 3), ("secret identity", 4), ("origin story", 4)
        ],
        "mythology": [
            ("god", 2), ("goddess", 3), ("olympus", 5), ("valhalla", 5), ("titan", 4),
            ("hero", 1), ("epic", 1), ("pantheon", 4), ("divine", 2), ("immortal", 2)
        ],
        "noir": [
            ("detective", 3), ("dame", 4), ("gumshoe", 5), ("fedora", 4), ("cigarette", 2),
            ("rain", 1), ("shadow", 1), ("corrupt", 2), ("private eye", 5)
        ],
        "wuxia": [
            ("martial", 3), ("cultivat", 4), ("sect", 3), ("elder", 2), ("technique", 2),
            ("qi", 5), ("dao", 4), ("immortal", 2), ("jade", 2)
        ],
        "pirate": [
            ("pirate", 5), ("ship", 2), ("sea", 1), ("captain", 2), ("treasure", 3),
            ("sailor", 3), ("plunder", 4), ("cutlass", 4), ("crew", 2)
        ],
        "dark_fantasy": [
            ("grimdark", 5), ("bleak", 3), ("brutal", 3), ("despair", 3), ("cursed", 2),
            ("dark", 1), ("blood", 1), ("grim", 3)
        ],
        "fantasy": [
            ("magic", 3), ("wizard", 4), ("elf", 4), ("dwarf", 4), ("dragon", 4),
            ("spell", 3), ("sword", 2), ("kingdom", 2), ("castle", 2), ("quest", 2),
            ("enchant", 3), ("sorcerer", 4), ("arcane", 3), ("mage", 4)
        ],
    }
    
    # Calculate scores for each genre
    scores = {}
    for genre, patterns in genre_patterns.items():
        score = 0
        for keyword, weight in patterns:
            count = text_lower.count(keyword)
            score += count * weight
        scores[genre] = score
    
    # Get top genre
    if not scores or all(s == 0 for s in scores.values()):
        # No clear signals, default to fantasy
        return GenreAssessment(
            mechanics_genre="fantasy",
            genre_hints=["fantasy"],
            confidence=0.4,
            reasoning="No clear genre signals found, defaulting to fantasy"
        )
    
    # Sort by score
    sorted_genres = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_genre, top_score = sorted_genres[0]
    
    # Calculate confidence based on score separation
    second_score = sorted_genres[1][1] if len(sorted_genres) > 1 else 0
    score_gap = top_score - second_score
    confidence = min(0.95, 0.5 + (score_gap / max(top_score, 1)) * 0.4)
    
    # Collect genre hints (include top 3 genres with non-zero scores)
    genre_hints = [g for g, s in sorted_genres[:3] if s > 0]
    
    return GenreAssessment(
        mechanics_genre=top_genre,
        genre_hints=genre_hints,
        confidence=confidence,
        reasoning=f"Keyword-based assessment (score: {top_score})"
    )


def _map_to_valid_genre(genre: str) -> str:
    """Map an invalid genre to a valid mechanics genre."""
    genre_lower = genre.lower()
    
    # Common mappings
    mappings = {
        "sci-fi": "scifi",
        "science fiction": "scifi",
        "space": "space_opera",
        "gothic": "dark_fantasy",
        "high fantasy": "fantasy",
        "urban fantasy": "modern",  # Urban fantasy uses modern mechanics
        "mystery": "modern",
        "thriller": "modern",
        "romance": "fantasy",  # Default to fantasy for pure romance
        "adventure": "fantasy",
        "historical": "modern",  # Historical uses modern-ish mechanics
        "post-apocalyptic": "postapoc",
        "post apocalyptic": "postapoc",
    }
    
    return mappings.get(genre_lower, "fantasy")  # Default to fantasy if unknown


def assess_genre_from_world_data(world_data: Dict[str, Any], gemini_client=None) -> GenreAssessment:
    """
    Assess genre from world data dictionary (from LORE_BASES or Neo4j).
    
    Args:
        world_data: World data with 'genre', 'genre_hints', 'lore_content', etc.
        gemini_client: Optional Gemini client for AI assessment
        
    Returns:
        GenreAssessment with mechanics_genre resolved
    """
    # Check if already has mechanics_genre stored
    if "mechanics_genre" in world_data and world_data["mechanics_genre"]:
        return GenreAssessment(
            mechanics_genre=world_data["mechanics_genre"],
            genre_hints=world_data.get("genre_hints", [world_data["mechanics_genre"]]),
            confidence=world_data.get("genre_confidence", 1.0),
            reasoning="Stored assessment"
        )
    
    # Try to assess from lore_content
    lore_content = world_data.get("lore_content", "")
    if lore_content and len(lore_content.strip()) > 50:
        assessment = assess_genre_from_text(lore_content, gemini_client)
        
        # Merge with existing genre_hints if present
        existing_hints = world_data.get("genre_hints", [])
        if existing_hints:
            # Combine and deduplicate
            all_hints = [assessment.mechanics_genre] + assessment.genre_hints + existing_hints
            assessment.genre_hints = list(dict.fromkeys(all_hints))  # Preserve order, remove dupes
        
        return assessment
    
    # Fallback to existing genre field
    existing_genre = world_data.get("genre")
    if existing_genre:
        mechanics_genre = _map_to_valid_genre(existing_genre)
        return GenreAssessment(
            mechanics_genre=mechanics_genre,
            genre_hints=world_data.get("genre_hints", [mechanics_genre]),
            confidence=0.7,
            reasoning="Using existing genre field"
        )
    
    # Last resort: use genre_hints[0] or default to fantasy
    genre_hints = world_data.get("genre_hints", [])
    if genre_hints:
        mechanics_genre = _map_to_valid_genre(genre_hints[0])
        return GenreAssessment(
            mechanics_genre=mechanics_genre,
            genre_hints=genre_hints,
            confidence=0.6,
            reasoning="Using first genre hint"
        )
    
    # Ultimate fallback
    return GenreAssessment(
        mechanics_genre="fantasy",
        genre_hints=["fantasy"],
        confidence=0.3,
        reasoning="No genre information available, defaulting to fantasy"
    )
