# Lore Bases

Place your lore base files here as JSON files. These files define pre-made worlds that players can choose when starting a new game session.

## How Lore Processing Works

When you upload a lore base with `lore_content`, the system processes it through a **smart ingestion pipeline**:

1. **Text Segmentation** - Splits long content into manageable chunks
2. **Entity Detection** - Identifies characters, locations, factions, items, and events
3. **Property Extraction** - Extracts names, descriptions, and personality traits
4. **OCEAN Profile Generation** - Converts personality traits into psychological profiles for NPCs
5. **Relationship Inference** - Detects relationships between entities
6. **Neo4j Storage** - Persists everything to the graph database

### OCEAN Profiles

NPCs automatically receive OCEAN personality profiles based on trait words in their descriptions:

- **Openness** - curious, creative, studious, open-minded
- **Conscientiousness** - methodical, loyal, strict, disciplined
- **Extraversion** - charismatic, warm, commanding, bold
- **Agreeableness** - kind, forgiving, cold, vengeful
- **Neuroticism** - fearful, anxious, calm, brave

Example description that generates good OCEAN profiles:
> "Lord Aldric is calculating and ambitious, known for his cold demeanor and strategic mind. Despite his ruthless reputation, he shows kindness to scholars."

## JSON Format

Each lore base file should be named `{id}.json` and contain:

```json
{
  "id": "your_world_id",
  "name": "Display Name",
  "description": "A brief description shown to users in the world selection screen",
  "genre_hints": ["fantasy", "romance", "mystery", "horror", "drama"],
  "tone_hints": ["epic", "intimate", "dark", "whimsical", "gritty"],
  "seed_prompt": "A shorter prompt used when the AI needs to generate additional content",
  "lore_content": "Full lore text describing your world, characters, locations, and factions..."
}
```

## Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (lowercase, underscores only) |
| `name` | Yes | Display name for the UI |
| `description` | Yes | Brief description for world selection |
| `genre_hints` | No | List of genres to guide AI tone |
| `tone_hints` | No | List of tones/moods |
| `seed_prompt` | No | Short prompt for AI content generation |
| `lore_content` | No | **Full narrative text** for entity extraction |

## Writing Effective lore_content

For best results with NPC personality extraction, write character descriptions that include:

1. **Personality trait words** - Use descriptive adjectives like "cunning", "loyal", "vengeful", "kind"
2. **Behavioral descriptions** - "He commands absolute loyalty" or "She avoids confrontation"
3. **Contrasting traits** - "Despite his cold exterior, he shows kindness to the poor"
4. **Relationships** - Mention connections between characters

### Example lore_content

```
The Gilded Court of Valdris stands as a beacon of culture and treachery.

Lord Aldric Ravencrest is calculating and ambitious. Cold and methodical, he prefers
manipulation over direct confrontation. Despite his ruthless reputation, he shows
genuine kindness to artists and scholars.

Lady Seraphina Ashford leads House Ashford with charm and grace. Warm and charismatic,
she draws people to her like moths to flame. Yet beneath her warm exterior lurks a
vengeful heart - those who betray her trust discover her kindness has limits.

Captain Thorne is a man of few words. His loyalty is absolute and his fear of failure
drives him to obsessive preparation. Veterans speak of his bravery in battle.

The Golden Serpent Tavern serves as neutral ground. Its proprietor, Old Marco, has
dirt on everyone yet maintains absolute discretion - his word is his bond.
```

## API Endpoints

### List all lore bases
```
GET /api/game/lore-bases
```

### Get specific lore base
```
GET /api/game/lore-bases/{id}
```

### Create lore base via JSON
```
POST /api/game/lore-bases
Content-Type: application/json

{
  "id": "my_world",
  "name": "My World",
  ...
}
```

### Upload lore base file
```
POST /api/game/lore-bases/upload
Content-Type: multipart/form-data

file: my_world.json
```

### Process lore base (extract entities & OCEAN profiles)
```
POST /api/game/lore-bases/{id}/ingest

Response:
{
  "lore_id": "my_world",
  "entities_created": 15,
  "relationships_created": 8,
  "npcs_with_ocean": 6,
  "message": "Successfully ingested lore base 'My World'"
}
```

## Example Files

See `example_world.json` for a complete example with rich character descriptions.
