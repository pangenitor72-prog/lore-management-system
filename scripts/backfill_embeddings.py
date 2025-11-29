#!/usr/bin/env python3
"""
Backfill Embeddings Script

Generates and stores vector embeddings for all entities in the Neo4j database
that don't already have embeddings. This enables semantic similarity search.

Usage:
    python scripts/backfill_embeddings.py [--batch-size 50] [--limit 1000]

Prerequisites:
    - Neo4j running with entities loaded
    - GEMINI_API_KEY in .env
    - Vector index created (script will create if missing)
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from neo4j_adapter import Neo4jDatabase
from embedding_service import EmbeddingService

# Load environment
load_dotenv()

# Configuration
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")


async def create_vector_index(db: Neo4jDatabase) -> bool:
    """Ensure the vector index exists."""
    print("\n📐 Checking vector index...")
    
    # Check if index exists
    indexes = await db.list_indexes()
    for idx in indexes:
        if idx.get("name") == "entity_embeddings":
            print("   ✅ Vector index 'entity_embeddings' already exists")
            return True
    
    # Create index
    print("   Creating vector index 'entity_embeddings'...")
    success = await db.create_vector_index(
        index_name="entity_embeddings",
        label="Entity",  # Will need to adjust based on your labels
        property_name="embedding",
        dimensions=768,
        similarity_function="cosine"
    )
    
    if not success:
        # Try without label constraint (for mixed labels)
        print("   Trying index on all nodes...")
        query = """
        CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
        FOR (n) ON (n.embedding)
        OPTIONS {
            indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }
        }
        """
        try:
            await db.execute(query)
            print("   ✅ Vector index created")
            return True
        except Exception as e:
            print(f"   ❌ Failed to create index: {e}")
            print("   Note: Vector indexes may require specific node labels.")
            print("   The script will continue - embeddings will still be stored.")
            return False
    
    return success


async def backfill_embeddings(
    db: Neo4jDatabase,
    embedding_service: EmbeddingService,
    batch_size: int = 50,
    limit: int = None
) -> dict:
    """
    Generate and store embeddings for entities missing them.
    
    Returns:
        Dict with statistics about the operation
    """
    stats = {
        "total_processed": 0,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "start_time": datetime.now().isoformat()
    }
    
    # Get current counts
    counts = await db.count_embeddings()
    print(f"\n📊 Current state:")
    print(f"   With embeddings:    {counts['with_embedding']}")
    print(f"   Without embeddings: {counts['without_embedding']}")
    
    if counts['without_embedding'] == 0:
        print("\n✅ All entities already have embeddings!")
        return stats
    
    target = min(counts['without_embedding'], limit) if limit else counts['without_embedding']
    print(f"\n🚀 Starting backfill for {target} entities (batch size: {batch_size})...")
    
    processed = 0
    batch_num = 0
    
    while processed < target:
        batch_num += 1
        current_batch_size = min(batch_size, target - processed)
        
        # Fetch nodes without embeddings
        nodes = await db.get_nodes_without_embeddings(limit=current_batch_size)
        
        if not nodes:
            print("\n   No more nodes to process.")
            break
        
        print(f"\n   Batch {batch_num}: Processing {len(nodes)} entities...")
        
        embeddings_to_store = []
        
        for node in nodes:
            stats["total_processed"] += 1
            
            name = node.get("name", "Unknown")
            canon_id = node.get("canon_id")
            
            if not canon_id:
                print(f"      ⚠️ Skipping {name}: No canon_id")
                stats["skipped"] += 1
                continue
            
            # Generate embedding
            embedding = embedding_service.embed_entity(node)
            
            if embedding:
                embeddings_to_store.append({
                    "node_id": canon_id,
                    "embedding": embedding
                })
                stats["successful"] += 1
                print(f"      ✅ {name}")
            else:
                stats["failed"] += 1
                print(f"      ❌ {name}: Failed to generate embedding")
        
        # Batch store embeddings
        if embeddings_to_store:
            stored = await db.store_embeddings_batch(embeddings_to_store)
            print(f"      💾 Stored {stored} embeddings")
        
        processed += len(nodes)
        
        # Progress
        progress = (processed / target) * 100
        print(f"      Progress: {processed}/{target} ({progress:.1f}%)")
    
    stats["end_time"] = datetime.now().isoformat()
    
    # Final counts
    final_counts = await db.count_embeddings()
    print(f"\n📊 Final state:")
    print(f"   With embeddings:    {final_counts['with_embedding']}")
    print(f"   Without embeddings: {final_counts['without_embedding']}")
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Backfill vector embeddings for Neo4j entities")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of entities per batch")
    parser.add_argument("--limit", type=int, default=None, help="Maximum entities to process")
    parser.add_argument("--skip-index", action="store_true", help="Skip vector index creation")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  VECTOR EMBEDDING BACKFILL")
    print("=" * 60)
    
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY not found in environment")
        sys.exit(1)
    
    # Initialize services
    print("\n🔌 Connecting to Neo4j...")
    db = Neo4jDatabase(uri=DB_URI, auth=(DB_USER, DB_PASSWORD))
    await db.connect()
    
    print("🤖 Initializing embedding service...")
    embedding_service = EmbeddingService(GEMINI_KEY)
    
    try:
        # Create vector index if needed
        if not args.skip_index:
            await create_vector_index(db)
        
        # Run backfill
        stats = await backfill_embeddings(
            db=db,
            embedding_service=embedding_service,
            batch_size=args.batch_size,
            limit=args.limit
        )
        
        # Summary
        print("\n" + "=" * 60)
        print("  BACKFILL COMPLETE")
        print("=" * 60)
        print(f"  Total processed: {stats['total_processed']}")
        print(f"  Successful:      {stats['successful']}")
        print(f"  Failed:          {stats['failed']}")
        print(f"  Skipped:         {stats['skipped']}")
        print("=" * 60)
        
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

