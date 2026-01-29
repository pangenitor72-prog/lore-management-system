
"""
Batch Image Generation Script for AIRpg/Mantle.

Scans existing worlds in Neo4j and generates images for key entities (Locations, Factions)
that are missing visual assets.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.services.image_service import image_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

async def batch_generate():
    logger.info("Connecting to Neo4j...")
    db = Neo4jDatabase(NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD)
    
    try:
        # 1. Get all LoreBases
        worlds = await db.execute("""
            MATCH (w:World) 
            RETURN w.world_id as id, w.name as name, w.tone as tone, w.description as description
            UNION
            MATCH (lb:LoreBase)
            RETURN lb.lore_id as id, lb.name as name, COALESCE(lb.tone_hints[0], 'neutral') as tone, lb.description as description
        """)
        
        logger.info(f"Found {len(worlds)} worlds to process.")
        
        for world in worlds:
            wid = world["id"]
            wname = world.get("name") or wid or "Unknown World"
            wtone = world.get("tone") or "fantasy"
            wdesc = world.get("description") or ""
            
            logger.info(f"Processing world: {wname} ({wid})")
            
            # Generate World Cover if missing
            # Check if world node has image
            world_nodes = await db.execute(
                "MATCH (n {world_id: $wid}) WHERE n:World OR n:LoreBase RETURN n.image_url as url",
                {"wid": wid}
            )
            
            has_image = False
            if world_nodes and world_nodes[0].get("url"):
                has_image = True

            if not has_image and wdesc:
                logger.info(f"Generating cover image for {wname}...")
                cover_url = await image_service.generate_image(
                    prompt=wdesc[:500],
                    entity_name=wname,
                    entity_type="World",
                    style_key=wtone
                )
                if cover_url:
                    await db.execute(
                        "MATCH (n {world_id: $wid}) WHERE n:World OR n:LoreBase SET n.image_url = $url",
                        {"wid": wid, "url": cover_url}
                    )
            
            # 2. Find key entities without images
            # Focus on Locations and Factions first
            entities = await db.execute("""
                MATCH (e:Entity)
                WHERE (e.world_id = $wid OR e.curated_world_id = $wid)
                  AND (e:Location OR e:Faction OR e:Character)
                  AND e.image_url IS NULL
                RETURN e.canon_id as id, e.name as name, labels(e) as labels, e.description as description, e.entity_type as type
                LIMIT 50
            """, {"wid": wid})
            
            logger.info(f"Found {len(entities)} entities missing images in {wname}.")
            
            for ent in entities:
                eid = ent["id"]
                ename = ent["name"]
                etype = ent["type"] or ("Location" if "Location" in ent["labels"] else "Entity")
                edesc = ent["description"]
                
                if not edesc:
                    continue
                    
                # Generate
                img_url = await image_service.generate_image(
                    prompt=edesc,
                    entity_name=ename,
                    entity_type=etype,
                    style_key=wtone
                )
                
                if img_url:
                    await db.execute(
                        "MATCH (e:Entity {canon_id: $eid}) SET e.image_url = $url",
                        {"eid": eid, "url": img_url}
                    )
                    logger.info(f"Updated {ename} with image.")
                    
                # Rate limiting / polite delay
                await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Batch generation failed: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(batch_generate())
