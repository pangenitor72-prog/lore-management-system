# src/mantle/api/graph_routes.py
"""
Graph Visualization API Routes

Endpoints for knowledge graph visualization:
- Get graph data for vis.js rendering
- Get available filter options
- Get detailed node information
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["Graph"])


def get_optional_neo4j_db(request: Request):
    """Get Neo4j database if available, otherwise None."""
    return getattr(request.app.state, "neo4j_db", None)


def get_lore_bases(request: Request) -> dict:
    """Get LORE_BASES from app state or return empty dict."""
    return getattr(request.app.state, "lore_bases", {})


@router.get("")
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
            n.genre AS genre,
            n.image_url AS image_url
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

            node_data = {
                "id": row["id"],
                "label": row["label"],
                "group": node_type,
                "color": color,
                "title": row.get("description", "")[:200] if row.get("description") else node_type,
            }
            if row.get("image_url"):
                node_data["image_url"] = row["image_url"]
            nodes.append(node_data)

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


@router.get("/filters")
async def get_graph_filter_options(request: Request):
    """
    Get available filter options for the graph visualization.

    Returns lists of unique values for: entity types, sessions, genres, worlds.
    This populates the filter dropdowns in the UI.
    """
    db = get_optional_neo4j_db(request)
    if not db:
        return {"entity_types": [], "sessions": [], "genres": [], "worlds": []}

    lore_bases = get_lore_bases(request)

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
        for lore_id in lore_bases.keys():
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


@router.get("/node/{node_id}")
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
