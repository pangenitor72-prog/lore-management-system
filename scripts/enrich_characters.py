#!/usr/bin/env python3
"""
Character Enrichment Script

Retroactively populates existing Character nodes with OCEAN personality traits,
goals, fears, secrets, and other character data using AI analysis.

Usage:
    python scripts/enrich_characters.py [--dry-run] [--limit 50]

Prerequisites:
    - Neo4j running with Character nodes
    - GEMINI_API_KEY in .env
"""
import asyncio
import argparse
import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Lazy imports for Neo4j
neo4j_driver = None


def get_neo4j_driver():
    """Get or create Neo4j driver."""
    global neo4j_driver
    if neo4j_driver is None:
        from neo4j import AsyncGraphDatabase
        neo4j_driver = AsyncGraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASSWORD))
    return neo4j_driver


async def find_characters_missing_ocean(limit: int = 100) -> list:
    """Find Character nodes that don't have OCEAN personality traits."""
    driver = get_neo4j_driver()

    query = """
    MATCH (c:Character)
    WHERE c.openness IS NULL
      AND c.name IS NOT NULL
      AND c.description IS NOT NULL
    RETURN
        c.name AS name,
        c.description AS description,
        c.role AS role,
        c.occupation AS occupation,
        c.goals AS goals,
        c.fears AS fears,
        c.secrets AS secrets,
        c.background AS background,
        id(c) AS node_id
    LIMIT $limit
    """

    async with driver.session() as session:
        result = await session.run(query, {"limit": limit})
        records = await result.data()
        return records


async def update_character_with_enrichment(node_id: int, enrichment: dict) -> bool:
    """Update a Character node with enriched data."""
    driver = get_neo4j_driver()

    # Build SET clauses for non-null values
    set_clauses = []
    params = {"node_id": node_id}

    # OCEAN traits
    for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
        if trait in enrichment and enrichment[trait] is not None:
            set_clauses.append(f"c.{trait} = ${trait}")
            params[trait] = float(enrichment[trait])

    # Text fields (only if not already set)
    for field in ["goals", "fears", "secrets", "background"]:
        if field in enrichment and enrichment[field]:
            set_clauses.append(f"c.{field} = COALESCE(c.{field}, ${field})")
            params[field] = enrichment[field]

    if not set_clauses:
        return False

    query = f"""
    MATCH (c:Character)
    WHERE id(c) = $node_id
    SET {', '.join(set_clauses)},
        c.enriched_at = datetime()
    RETURN c.name AS name
    """

    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()
        return record is not None


async def generate_character_enrichment(character: dict) -> dict:
    """Use Gemini to generate personality traits and character details."""
    import google.generativeai as genai

    if not GEMINI_KEY:
        print("ERROR: GEMINI_API_KEY not set")
        return {}

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Build context from existing character data
    context_parts = [f"Name: {character['name']}"]
    if character.get('description'):
        context_parts.append(f"Description: {character['description']}")
    if character.get('role'):
        context_parts.append(f"Role: {character['role']}")
    if character.get('occupation'):
        context_parts.append(f"Occupation: {character['occupation']}")

    context = "\n".join(context_parts)

    prompt = f"""Analyze this character and generate psychological profile data.

CHARACTER:
{context}

Generate a JSON response with these fields:
1. OCEAN personality traits (each 0.0-1.0):
   - openness: Creative/curious (high) vs conventional/traditional (low)
   - conscientiousness: Organized/disciplined (high) vs spontaneous/careless (low)
   - extraversion: Outgoing/energetic (high) vs reserved/withdrawn (low)
   - agreeableness: Cooperative/compassionate (high) vs competitive/skeptical (low)
   - neuroticism: Anxious/sensitive (high) vs confident/stable (low)

2. Character motivations (only if not obvious from description):
   - goals: What does this character want to achieve? (1-2 sentences)
   - fears: What is this character afraid of? (1-2 sentences)
   - secrets: What does this character hide? (1-2 sentences, can be "None known")

Base the personality on their role, description, and typical behavior for such a character.
Be specific and grounded in the character details provided.

Respond with ONLY valid JSON, no markdown:
{{"openness": 0.X, "conscientiousness": 0.X, "extraversion": 0.X, "agreeableness": 0.X, "neuroticism": 0.X, "goals": "...", "fears": "...", "secrets": "..."}}
"""

    try:
        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        # Clean up response if needed
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)

        # Validate OCEAN values are in range
        for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            if trait in data:
                data[trait] = max(0.0, min(1.0, float(data[trait])))

        return data

    except Exception as e:
        print(f"   ERROR generating enrichment: {e}")
        return {}


async def main():
    parser = argparse.ArgumentParser(description="Enrich Character nodes with OCEAN traits")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--limit", type=int, default=50, help="Max characters to process (default: 50)")
    args = parser.parse_args()

    print("=" * 60)
    print("CHARACTER ENRICHMENT SCRIPT")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Limit: {args.limit} characters")
    print(f"Database: {DB_URI}")
    print()

    # Find characters needing enrichment
    print("Searching for characters missing OCEAN traits...")
    characters = await find_characters_missing_ocean(args.limit)

    if not characters:
        print("No characters found needing enrichment!")
        return

    print(f"Found {len(characters)} characters to enrich\n")

    # Process each character
    success_count = 0
    error_count = 0

    for i, char in enumerate(characters, 1):
        name = char['name']
        print(f"[{i}/{len(characters)}] Processing: {name}")

        # Generate enrichment
        enrichment = await generate_character_enrichment(char)

        if not enrichment:
            print(f"   SKIP: No enrichment generated")
            error_count += 1
            continue

        # Show what was generated
        ocean_str = ", ".join([
            f"O:{enrichment.get('openness', '?'):.1f}" if isinstance(enrichment.get('openness'), (int, float)) else "O:?",
            f"C:{enrichment.get('conscientiousness', '?'):.1f}" if isinstance(enrichment.get('conscientiousness'), (int, float)) else "C:?",
            f"E:{enrichment.get('extraversion', '?'):.1f}" if isinstance(enrichment.get('extraversion'), (int, float)) else "E:?",
            f"A:{enrichment.get('agreeableness', '?'):.1f}" if isinstance(enrichment.get('agreeableness'), (int, float)) else "A:?",
            f"N:{enrichment.get('neuroticism', '?'):.1f}" if isinstance(enrichment.get('neuroticism'), (int, float)) else "N:?",
        ])
        print(f"   OCEAN: [{ocean_str}]")

        if enrichment.get('goals'):
            print(f"   Goals: {enrichment['goals'][:60]}...")
        if enrichment.get('fears'):
            print(f"   Fears: {enrichment['fears'][:60]}...")

        # Update database (unless dry run)
        if args.dry_run:
            print(f"   DRY RUN: Would update node {char['node_id']}")
            success_count += 1
        else:
            updated = await update_character_with_enrichment(char['node_id'], enrichment)
            if updated:
                print(f"   UPDATED")
                success_count += 1
            else:
                print(f"   ERROR: Update failed")
                error_count += 1

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(characters)}")
    print(f"Successful: {success_count}")
    print(f"Errors: {error_count}")

    if args.dry_run:
        print("\nThis was a DRY RUN. Run without --dry-run to apply changes.")

    # Cleanup
    if neo4j_driver:
        await neo4j_driver.close()


if __name__ == "__main__":
    asyncio.run(main())
