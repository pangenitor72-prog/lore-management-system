"""
Genre Resolution Utility

Centralized function for resolving mechanics genre across all character creation flows.

Rule: If world_id is provided and resolvable, world's mechanics_genre is authoritative.
      User-selected genre becomes optional narrative flavor.
"""

import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


async def resolve_mechanics_genre(
    world_id: Optional[str],
    user_genre: Optional[str],
    lore_bases: dict = None,
    db = None,
) -> Tuple[str, List[str]]:
    """
    Resolve the authoritative mechanics genre and narrative flavor tags.
    
    Args:
        world_id: World ID (curated world ID or session-scoped world ID)
        user_genre: User's genre selection (becomes flavor if world exists)
        lore_bases: LORE_BASES dict for looking up curated worlds
        db: Neo4j database for looking up user-created worlds
        
    Returns:
        Tuple of (mechanics_genre, flavor_genres)
        - mechanics_genre: Single authoritative genre for mechanics
        - flavor_genres: List of narrative flavor tags
    """
    flavor_genres = []
    
    # If world_id provided, world genre dominates
    if world_id and lore_bases:
        # Check curated worlds first
        if world_id in lore_bases:
            world_data = lore_bases[world_id]
            
            # Try mechanics_genre first (new field)
            mechanics_genre = world_data.get("mechanics_genre")
            if not mechanics_genre:
                # Fallback to genre field
                mechanics_genre = world_data.get("genre")
            
            if not mechanics_genre:
                # Fallback to first genre_hint
                hints = world_data.get("genre_hints", [])
                mechanics_genre = hints[0] if hints else None
            
            if mechanics_genre:
                # World has a genre - use it for mechanics
                # User's genre becomes flavor if different
                genre_hints = world_data.get("genre_hints", [])
                flavor_genres = list(genre_hints)  # Start with world's hints
                
                if user_genre and user_genre.lower() != mechanics_genre.lower():
                    # User genre is different - add as narrative flavor
                    if user_genre not in flavor_genres:
                        flavor_genres.append(user_genre)
                
                logger.info(
                    f"[GENRE] Resolved from curated world '{world_id}': "
                    f"mechanics={mechanics_genre}, flavor={flavor_genres}"
                )
                return mechanics_genre, flavor_genres
        
        # Check database for user-created worlds
        if db:
            try:
                result = await db.execute("""
                    MATCH (lb:LoreBase {lore_id: $world_id})
                    RETURN lb.mechanics_genre AS mechanics_genre,
                           lb.genre AS genre,
                           lb.genre_hints AS genre_hints
                """, {"world_id": world_id})
                
                if result:
                    row = result[0]
                    mechanics_genre = row.get("mechanics_genre") or row.get("genre")
                    genre_hints = row.get("genre_hints") or []
                    
                    if mechanics_genre:
                        flavor_genres = list(genre_hints)
                        if user_genre and user_genre.lower() != mechanics_genre.lower():
                            if user_genre not in flavor_genres:
                                flavor_genres.append(user_genre)
                        
                        logger.info(
                            f"[GENRE] Resolved from DB world '{world_id}': "
                            f"mechanics={mechanics_genre}, flavor={flavor_genres}"
                        )
                        return mechanics_genre, flavor_genres
            except Exception as e:
                logger.warning(f"[GENRE] Failed to query DB for world {world_id}: {e}")
    
    # No world or world has no genre - use user's genre
    if user_genre:
        logger.info(f"[GENRE] Using user-selected genre: {user_genre}")
        return user_genre, [user_genre]
    
    # Ultimate fallback
    logger.info("[GENRE] No genre information available, defaulting to fantasy")
    return "fantasy", ["fantasy"]


def resolve_mechanics_genre_sync(
    world_id: Optional[str],
    user_genre: Optional[str],
    lore_bases: dict = None,
) -> Tuple[str, List[str]]:
    """
    Synchronous version of resolve_mechanics_genre (for non-async contexts).
    
    Only checks LORE_BASES (no DB lookup).
    
    Args:
        world_id: World ID (curated world ID only)
        user_genre: User's genre selection
        lore_bases: LORE_BASES dict for looking up curated worlds
        
    Returns:
        Tuple of (mechanics_genre, flavor_genres)
    """
    flavor_genres = []
    
    # If world_id provided, world genre dominates
    if world_id and lore_bases and world_id in lore_bases:
        world_data = lore_bases[world_id]
        
        # Try mechanics_genre first (new field)
        mechanics_genre = world_data.get("mechanics_genre")
        if not mechanics_genre:
            # Fallback to genre field
            mechanics_genre = world_data.get("genre")
        
        if not mechanics_genre:
            # Fallback to first genre_hint
            hints = world_data.get("genre_hints", [])
            mechanics_genre = hints[0] if hints else None
        
        if mechanics_genre:
            # World has a genre - use it for mechanics
            genre_hints = world_data.get("genre_hints", [])
            flavor_genres = list(genre_hints)
            
            if user_genre and user_genre.lower() != mechanics_genre.lower():
                if user_genre not in flavor_genres:
                    flavor_genres.append(user_genre)
            
            logger.info(
                f"[GENRE] Resolved (sync) from world '{world_id}': "
                f"mechanics={mechanics_genre}, flavor={flavor_genres}"
            )
            return mechanics_genre, flavor_genres
    
    # No world or world has no genre - use user's genre
    if user_genre:
        logger.info(f"[GENRE] Using user-selected genre (sync): {user_genre}")
        return user_genre, [user_genre]
    
    # Ultimate fallback
    logger.info("[GENRE] No genre information (sync), defaulting to fantasy")
    return "fantasy", ["fantasy"]
