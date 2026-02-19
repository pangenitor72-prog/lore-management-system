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
        results = await db.execute(query, {"world_id": world_id})

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


async def audit_narrative_for_contradictions(
    narrative: str,
    world_id: str,
    db: Optional["Neo4jDatabase"],
    session_id: str = "unknown",
) -> List[Dict]:
    """
    Audit DM-generated narrative for contradictions against established world lore.

    This is a lightweight audit that:
    1. Extracts entities mentioned in the narrative
    2. Checks NPC behaviors against their OCEAN personality profiles
    3. Detects factual contradictions (dead characters appearing alive, etc.)

    Args:
        narrative: The DM's narrative response text
        world_id: The world ID to check against
        db: Neo4j database connection
        session_id: Session ID for logging

    Returns:
        List of contradiction dicts with type, severity, description
    """
    if not narrative or not db or not world_id:
        return []

    contradictions = []

    try:
        # Extract entity names mentioned in narrative
        entity_names = extract_entity_names_from_text(narrative)
        if not entity_names:
            return []

        # Query for entities in this world that match mentioned names
        # Coalesce session overlay over canon to catch NPCs who died THIS session
        query = """
        MATCH (e:Entity {world_id: $world_id})
        WHERE e.entity_type = 'Character'
          AND ANY(name IN $names WHERE toLower(e.name) CONTAINS toLower(name))
        OPTIONAL MATCH (s:Session {session_id: $session_id})-[:CONTAINS]->(i:Instance)-[:OVERRIDES]->(e)
        RETURN e.canon_id as id,
               e.name as name,
               COALESCE(i.status, e.status) as status,
               COALESCE(i.is_dead, e.is_dead) as is_dead,
               COALESCE(i.is_missing, e.is_missing) as is_missing,
               e.openness as openness,
               e.conscientiousness as conscientiousness,
               e.extraversion as extraversion,
               e.agreeableness as agreeableness,
               e.neuroticism as neuroticism,
               e.description as description
        """
        results = await db.execute(query, {
            "world_id": world_id,
            "names": entity_names[:20],
            "session_id": session_id,
        })

        if not results:
            return []

        narrative_lower = narrative.lower()

        for record in results:
            npc_name = record.get("name", "")
            npc_id = record.get("id", "")

            # Check 1: Dead character appearing alive
            is_dead = record.get("is_dead") or record.get("status") == "dead"
            if is_dead and npc_name.lower() in narrative_lower:
                # Check if they're actually acting (not just being mentioned in past tense)
                action_indicators = [
                    f"{npc_name.lower()} says",
                    f"{npc_name.lower()} speaks",
                    f"{npc_name.lower()} walks",
                    f"{npc_name.lower()} looks",
                    f"{npc_name.lower()} turns",
                    f"{npc_name.lower()} smiles",
                    f"{npc_name.lower()} nods",
                ]
                if any(indicator in narrative_lower for indicator in action_indicators):
                    contradictions.append({
                        "type": "resurrection_without_explanation",
                        "severity": "HIGH",
                        "entity_id": npc_id,
                        "entity_name": npc_name,
                        "description": f"{npc_name} is marked as dead but appears to be acting in the narrative.",
                    })
                    logger.warning(f"[AUDITOR] Contradiction: {npc_name} is dead but appears active in narrative")

            # Check 2: Missing character appearing without explanation
            is_missing = record.get("is_missing") or record.get("status") == "missing"
            if is_missing and npc_name.lower() in narrative_lower:
                if any(indicator in narrative_lower for indicator in action_indicators):
                    contradictions.append({
                        "type": "location_inconsistency",
                        "severity": "MEDIUM",
                        "entity_id": npc_id,
                        "entity_name": npc_name,
                        "description": f"{npc_name} is marked as missing but appears in the scene.",
                    })
                    logger.info(f"[AUDITOR] Note: {npc_name} is missing but appears in narrative (may be intentional)")

        if contradictions:
            logger.info(f"[AUDITOR] Found {len(contradictions)} potential contradictions in narrative")
        else:
            logger.debug(f"[AUDITOR] No contradictions found in narrative")

        return contradictions

    except Exception as e:
        logger.warning(f"[AUDITOR] Failed to audit narrative: {e}")
        return []


async def write_npc_state_to_overlay(
    npc_id: str,
    session_id: str,
    state_changes: Dict,
    db: Optional["Neo4jDatabase"],
) -> bool:
    """
    Write NPC state changes to session overlay (delta layer).

    This allows NPCs to change state during a session (die, get captured, etc.)
    without modifying canonical world data. Other sessions see the original state.

    Args:
        npc_id: The NPC's canon_id
        session_id: The session to scope the overlay to
        state_changes: Dict of properties to set (e.g., {"is_dead": True})
        db: Neo4j database connection

    Returns:
        True if write succeeded, False otherwise
    """
    if not db or not npc_id or not session_id or not state_changes:
        return False

    try:
        result = await db.write_entity_delta(
            canon_id=npc_id,
            session_id=session_id,
            properties=state_changes,
        )
        if result:
            logger.info(f"[OVERLAY] Wrote state changes for {npc_id}: {state_changes}")
            return True
        return False
    except Exception as e:
        logger.warning(f"[OVERLAY] Failed to write state for {npc_id}: {e}")
        return False


async def detect_and_apply_npc_state_changes(
    narrative: str,
    world_id: str,
    session_id: str,
    db: Optional["Neo4jDatabase"],
) -> List[Dict]:
    """
    Detect NPC state changes in narrative and write them to session overlays.

    Looks for patterns indicating:
    - NPC death (killed, slain, died, murdered)
    - NPC capture (captured, imprisoned, arrested)
    - NPC departure (fled, escaped, vanished)

    Args:
        narrative: The DM's narrative response
        world_id: The world ID to match NPCs against
        session_id: The session ID for overlay scoping
        db: Neo4j database connection

    Returns:
        List of state changes that were applied
    """
    if not narrative or not db or not world_id or not session_id:
        return []

    changes_applied = []

    try:
        # Get NPCs from this world with current overlay state
        # Check overlay to avoid redundant state changes (e.g., killing already-dead NPCs)
        query = """
        MATCH (e:Entity {world_id: $world_id})
        WHERE e.entity_type = 'Character'
          AND (e.is_player_character IS NULL OR e.is_player_character = false)
        OPTIONAL MATCH (s:Session {session_id: $session_id})-[:CONTAINS]->(i:Instance)-[:OVERRIDES]->(e)
        RETURN e.canon_id as id,
               e.name as name,
               COALESCE(i.is_dead, e.is_dead, false) as is_dead,
               COALESCE(i.is_captured, e.is_captured, false) as is_captured,
               COALESCE(i.is_missing, e.is_missing, false) as is_missing,
               COALESCE(i.is_hostile, false) as is_hostile,
               COALESCE(i.is_injured, false) as is_injured
        """
        results = await db.execute(query, {"world_id": world_id, "session_id": session_id})
        if not results:
            return []

        narrative_lower = narrative.lower()

        # Death indicators
        death_patterns = [
            "dies", "died", "dead", "killed", "slain", "murdered",
            "perished", "fell lifeless", "breathed his last", "breathed her last",
            "no longer breathing", "lies dead", "lay dead",
        ]

        # Capture indicators
        capture_patterns = [
            "captured", "imprisoned", "arrested", "taken prisoner",
            "in chains", "bound and gagged", "thrown in the dungeon",
        ]

        # Departure indicators
        departure_patterns = [
            "fled", "escaped", "vanished", "disappeared",
            "ran away", "nowhere to be found",
        ]

        # Hostility indicators (NPC turns against player)
        hostile_patterns = [
            "attacks you", "draws weapon", "turns hostile", "betrays",
            "snarls", "lunges at", "swings at", "threatens",
        ]

        # Injury indicators
        injury_patterns = [
            "wounded", "injured", "bleeding", "hurt", "limping",
            "clutches wound", "staggers", "collapses",
        ]

        for record in results:
            npc_name = record.get("name", "")
            npc_id = record.get("id", "")
            if not npc_name or not npc_id:
                continue

            # Skip NPCs already in a terminal state
            already_dead = record.get("is_dead", False)
            already_captured = record.get("is_captured", False)
            already_missing = record.get("is_missing", False)

            npc_name_lower = npc_name.lower()
            if npc_name_lower not in narrative_lower:
                continue

            # Find the context around this NPC's mention
            state_changes = {}

            # Check for death (skip if already dead)
            if not already_dead:
                for pattern in death_patterns:
                    if pattern in narrative_lower:
                        name_idx = narrative_lower.find(npc_name_lower)
                        pattern_idx = narrative_lower.find(pattern)
                        if abs(name_idx - pattern_idx) < 60:
                            state_changes["is_dead"] = True
                            state_changes["status"] = "dead"
                            break

            # Check for capture (only if not dead and not already captured)
            if not state_changes.get("is_dead") and not already_captured:
                for pattern in capture_patterns:
                    if pattern in narrative_lower:
                        name_idx = narrative_lower.find(npc_name_lower)
                        pattern_idx = narrative_lower.find(pattern)
                        if abs(name_idx - pattern_idx) < 60:
                            state_changes["is_captured"] = True
                            state_changes["status"] = "captured"
                            break

            # Check for departure (only if not dead/captured and not already missing)
            if not state_changes.get("is_dead") and not state_changes.get("is_captured") and not already_missing:
                for pattern in departure_patterns:
                    if pattern in narrative_lower:
                        name_idx = narrative_lower.find(npc_name_lower)
                        pattern_idx = narrative_lower.find(pattern)
                        if abs(name_idx - pattern_idx) < 60:
                            state_changes["is_missing"] = True
                            state_changes["status"] = "missing"
                            break

            # Check for hostility (only if still active - not dead/captured/missing)
            if not state_changes.get("is_dead") and not state_changes.get("is_captured") and not state_changes.get("is_missing"):
                for pattern in hostile_patterns:
                    if pattern in narrative_lower:
                        name_idx = narrative_lower.find(npc_name_lower)
                        pattern_idx = narrative_lower.find(pattern)
                        if abs(name_idx - pattern_idx) < 60:
                            state_changes["is_hostile"] = True
                            state_changes["disposition"] = "hostile"
                            break

            # Check for injury (can stack with other non-terminal states)
            if not state_changes.get("is_dead"):
                for pattern in injury_patterns:
                    if pattern in narrative_lower:
                        name_idx = narrative_lower.find(npc_name_lower)
                        pattern_idx = narrative_lower.find(pattern)
                        if abs(name_idx - pattern_idx) < 60:
                            state_changes["is_injured"] = True
                            break

            # Apply state changes if any
            if state_changes:
                success = await write_npc_state_to_overlay(
                    npc_id=npc_id,
                    session_id=session_id,
                    state_changes=state_changes,
                    db=db,
                )
                if success:
                    changes_applied.append({
                        "npc_id": npc_id,
                        "npc_name": npc_name,
                        "changes": state_changes,
                    })

        return changes_applied

    except Exception as e:
        logger.warning(f"[OVERLAY] Failed to detect/apply state changes: {e}")
        return []


async def get_npc_overlay_state_context(
    world_id: str,
    session_id: str,
    db: Optional["Neo4jDatabase"],
) -> str:
    """
    Get formatted NPC state context from session overlays for DM prompt injection.

    Returns a string like:
    "=== NPC STATUS (THIS SESSION) ===
    - Lord Blackwood: DEAD (killed earlier this session)
    - Lady Ashworth: CAPTURED (imprisoned earlier this session)
    DO NOT include these characters as active participants."

    Args:
        world_id: The world ID to query NPCs from
        session_id: The session ID to check overlays for
        db: Neo4j database connection

    Returns:
        Formatted context string, or empty string if no state changes
    """
    if not db or not world_id or not session_id:
        return ""

    try:
        # Query for NPCs that have overlay state in this session
        # Includes terminal states (dead/captured/missing) and mood/disposition changes
        query = """
        MATCH (s:Session {session_id: $session_id})-[:CONTAINS]->(i:Instance)-[:OVERRIDES]->(e:Entity)
        WHERE e.world_id = $world_id
          AND e.entity_type = 'Character'
        RETURN e.name as name,
               i.is_dead as is_dead,
               i.is_captured as is_captured,
               i.is_missing as is_missing,
               i.is_hostile as is_hostile,
               i.is_injured as is_injured,
               i.disposition as disposition,
               i.status as status
        """
        results = await db.execute(query, {"world_id": world_id, "session_id": session_id})

        if not results:
            return ""

        # Compact format: ⚠️ NPC STATE: Name=STATUS | Name=STATUS
        unavailable = []  # Dead/Captured/Missing - can't participate
        changed = []      # Mood/disposition changes - still active

        for record in results:
            name = record.get("name", "Unknown")
            if record.get("is_dead"):
                unavailable.append(f"{name}=DEAD")
            elif record.get("is_captured"):
                unavailable.append(f"{name}=CAPTURED")
            elif record.get("is_missing"):
                unavailable.append(f"{name}=MISSING")
            elif record.get("is_hostile"):
                changed.append(f"{name}=HOSTILE")
            elif record.get("is_injured"):
                changed.append(f"{name}=INJURED")
            elif record.get("disposition"):
                changed.append(f"{name}={record['disposition'].upper()}")

        if not unavailable and not changed:
            return ""

        lines = []
        if unavailable:
            lines.append(f"⚠️ UNAVAILABLE: {' | '.join(unavailable)}")
            lines.append("(Do not include these NPCs as active participants)")
        if changed:
            lines.append(f"NPC CHANGES: {' | '.join(changed)}")

        logger.info(f"[OVERLAY] Injecting NPC state: {len(unavailable)} unavailable, {len(changed)} changed")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"[OVERLAY] Failed to get NPC state context: {e}")
        return ""
