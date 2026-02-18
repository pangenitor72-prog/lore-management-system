# src/mantle/api/helpers/narrative_extraction.py
"""
Narrative Extraction Helpers

Functions that extract information from DM narrative text:
- Entity names from prose
- NPC IDs by matching against the knowledge graph
- Scene NPC tracking for memory context

Extracted from game_routes.py for better organization.
"""

import re
import logging
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.mantle.db.neo4j_adapter import Neo4jDatabase
    from src.mantle.engine.game_state import GameState

logger = logging.getLogger(__name__)


def extract_entity_names_from_text(text: str) -> List[str]:
    """
    Extract potential entity names from narrative text.

    Uses simple heuristics to find named entities:
    - Capitalized multi-word names (e.g., "Lord Blackwood", "The Iron Guard")
    - Single capitalized words that aren't sentence starters
    - Named locations and places

    This is imperfect but sufficient for decoherence tracking.
    """
    if not text:
        return []

    entities = set()

    # Pattern 1: Titles + Names (Lord/Lady/Captain/etc. + Name)
    title_pattern = re.compile(
        r'\b(Lord|Lady|King|Queen|Prince|Princess|Captain|General|Master|Mistress|'
        r'Father|Mother|Brother|Sister|Elder|Chief|Mayor|Governor|Baron|Baroness|'
        r'Count|Countess|Duke|Duchess|Sir|Dame|Doctor|Professor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        re.IGNORECASE
    )
    for match in title_pattern.finditer(text):
        entities.add(match.group(0).strip())

    # Pattern 2: "The X" patterns (The Iron Guard, The Crimson Tower)
    the_pattern = re.compile(r'\bThe\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})')
    for match in the_pattern.finditer(text):
        full_match = match.group(0).strip()
        # Filter out common non-entities
        if full_match.lower() not in ("the story", "the player", "the air", "the room",
                                       "the door", "the ground", "the sky", "the sun",
                                       "the moon", "the night", "the day", "the darkness"):
            entities.add(full_match)

    # Pattern 3: Standalone capitalized names (not at sentence start)
    # Look for patterns like "spoke to Marcus" or "from Elena"
    name_pattern = re.compile(r'(?<=[a-z]\s)([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)?)')
    for match in name_pattern.finditer(text):
        name = match.group(1).strip()
        # Filter out common words that might be capitalized
        if name.lower() not in ("the", "a", "an", "he", "she", "it", "they", "you", "i",
                                 "but", "and", "or", "so", "yet", "for", "nor"):
            entities.add(name)

    return list(entities)[:20]  # Limit to prevent excessive tracking


async def extract_scene_npcs_from_narrative(
    narrative: str,
    world_id: str,
    db: Optional["Neo4jDatabase"],
) -> List[str]:
    """
    Extract NPC canon_ids mentioned in narrative by matching against known world NPCs.

    Args:
        narrative: The DM's narrative response text
        world_id: The world ID to search NPCs in
        db: Neo4j database connection

    Returns:
        List of NPC canon_ids that were mentioned in the narrative
    """
    if not narrative or not db or not world_id:
        return []

    try:
        # Get all Character entities for this world that aren't player characters
        query = """
        MATCH (e:Entity {world_id: $world_id})
        WHERE e.entity_type = 'Character'
          AND (e.is_player_character IS NULL OR e.is_player_character = false)
        RETURN e.canon_id as id, e.name as name
        """
        results = await db.execute_query(query, {"world_id": world_id})

        if not results:
            return []

        # Match NPC names against the narrative text (case-insensitive)
        # Use a set to prevent duplicates when both full name and first name match
        narrative_lower = narrative.lower()
        mentioned_npcs = set()

        for record in results:
            npc_name = record.get("name", "")
            npc_id = record.get("id", "")
            if npc_name and npc_id:
                # Check if NPC name appears in narrative
                if npc_name.lower() in narrative_lower:
                    mentioned_npcs.add(npc_id)
                    continue
                # Also check first name only for common references
                first_name = npc_name.split()[0] if " " in npc_name else ""
                if first_name and len(first_name) > 2 and first_name.lower() in narrative_lower:
                    mentioned_npcs.add(npc_id)

        return list(mentioned_npcs)[:10]  # Limit to prevent excessive tracking

    except Exception as e:
        logger.warning(f"[MEMORY] Failed to extract scene NPCs: {e}")
        return []


def get_npc_ids_for_memory_context(
    session_data: Dict,
    game_state: Optional["GameState"],
) -> List[str]:
    """
    Get NPC IDs to use for memory context injection.

    Prioritizes:
    1. scene_npcs from GameState (NPCs detected in recent narrative)
    2. Fallback to empty list (memory context will still include legends/threads)

    Args:
        session_data: The session data dictionary
        game_state: The current GameState instance

    Returns:
        List of NPC canon_ids present in the current scene
    """
    if game_state and game_state.scene_npcs:
        return list(game_state.scene_npcs)
    return []


def apply_legend_reputation_to_new_npcs(
    new_npc_ids: List[str],
    memory_manager,
) -> int:
    """
    Apply player's legendary reputation to NPCs meeting the player for the first time.

    When an NPC has never interacted with the player but the player has public legends,
    create an initial impression based on those legends. This makes NPCs react to
    the player's fame/infamy from the first meeting.

    Args:
        new_npc_ids: List of NPC canon_ids who are new to this scene
        memory_manager: The session's MemoryManager instance

    Returns:
        Number of NPCs who received reputation-based impressions
    """
    if not memory_manager or not new_npc_ids:
        return 0

    try:
        from src.mantle.memory.models import Impression, ImpressionValence

        # Get player's public legends
        legends = memory_manager.get_public_legends()
        if not legends:
            return 0  # No reputation to apply

        # Calculate aggregate reputation from legends
        total_respect = sum(l.respect_modifier for l in legends)
        total_fear = sum(l.fear_modifier for l in legends)
        avg_respect = total_respect / len(legends) if legends else 0
        avg_fear = total_fear / len(legends) if legends else 0

        # Determine valence based on reputation balance
        if avg_respect > 0.3 and avg_fear < 0.2:
            valence = ImpressionValence.FRIENDLY
            summary_prefix = "Has heard good things about you"
        elif avg_fear > 0.3:
            valence = ImpressionValence.WARY
            summary_prefix = "Has heard fearsome tales about you"
        elif avg_respect > 0.1:
            valence = ImpressionValence.NEUTRAL
            summary_prefix = "Has heard of your deeds"
        else:
            return 0  # Reputation too weak to matter

        # Get the most notable legend for the summary
        best_legend = max(legends, key=lambda l: abs(l.respect_modifier) + abs(l.fear_modifier))

        applied_count = 0
        for npc_id in new_npc_ids:
            # Check if we already have an impression for this NPC
            existing = memory_manager.get_npc_impression(npc_id)
            if existing:
                continue  # Already met this NPC, don't overwrite

            # Create initial impression based on reputation
            initial_impression = Impression(
                agent_id=npc_id,
                valence=valence,
                intensity=min(0.7, 0.3 + abs(avg_respect) + abs(avg_fear)),
                summary=f"{summary_prefix}: \"{best_legend.epithet}\"",
                respect=min(1.0, 0.5 + avg_respect),
                trust=0.4,  # Slightly cautious with strangers
                fear=min(1.0, max(0.0, avg_fear)),
                affection=0.3,  # Neutral starting affection
                will_help=avg_respect > 0,
                will_trade=True,
                will_share_secrets=False,
                will_betray=False,
                forms_of_address=best_legend.common_phrases[:2] if best_legend.common_phrases else ["stranger"],
            )

            memory_manager.experiential.record_impression(initial_impression)
            applied_count += 1
            logger.debug(f"[MEMORY] Applied legend reputation to new NPC: {npc_id} ({valence.value})")

        if applied_count > 0:
            logger.info(f"[MEMORY] Applied legend reputation to {applied_count} new NPCs")

        return applied_count

    except Exception as e:
        logger.warning(f"[MEMORY] Failed to apply legend reputation: {e}")
        return 0
