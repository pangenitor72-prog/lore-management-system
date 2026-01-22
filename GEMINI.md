# GEMINI.md

Context file for Google Gemini AI assistants working on this codebase.

## Project Overview

**Mantle** is an AI-powered narrative RPG platform combining:
- Knowledge management for narrative coherence
- AI Dungeon Master (you power this!)
- D&D 5e mechanics with visibility scaling

**Live Site:** https://lore-management-system.fly.dev/

## Tech Stack

- **Backend:** Python 3.11+ / FastAPI / Neo4j
- **AI:** Google Gemini API (gemini-2.0-flash)
- **Frontend:** Static HTML/CSS/JS (~22k lines in `frontend/dist/index.html`)
- **Deployment:** Fly.io

## Where Gemini Is Used

### 1. DM Agent (`src/lms/agents/dm_agent.py`)
The AI Dungeon Master that generates narrative responses.
- Uses conversation history for context
- Integrates with Arc Engine for pacing
- Follows "Gospel Principle": AI suggests, humans decide

### 2. World Tuner Agent (`src/lms/agents/world_tuner_agent.py`)
Conversational assistant for world configuration.
- Helps admins add races/classes through natural dialogue
- Outputs structured proposals for approval
- Uses MANTLE system (maps to D&D 5e base types)

### 3. Query Agent (`src/lms/agents/query_agent.py`)
Knowledge retrieval from the lore database.

### 4. Auditor Agent (`src/lms/agents/auditor_agent.py`)
Contradiction detection when new lore is added.

### 5. Lore Parsing Agent (`src/lms/agents/lore_parsing_agent.py`)
Entity extraction from raw text.

### 6. Character Options Generator (`src/lms/api/game_routes.py`)
`generate_character_options_from_lore()` - Extracts origins/archetypes from world lore.

## API Key Configuration

```python
# All agents use this pattern:
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")
```

## Common Patterns

### Async Generation
```python
response = await asyncio.get_event_loop().run_in_executor(
    None,
    lambda: self.model.generate_content(
        prompt,
        generation_config={"temperature": 0.7, "max_output_tokens": 2000}
    )
)
```

### JSON Extraction from Response
```python
# Look for ```json blocks
json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)
if json_match:
    data = json.loads(json_match.group(1))
```

## Key Concepts

### MANTLE Translation System
Maps setting-specific concepts to D&D 5e mechanics:
- **Origins** (races) → base_type: human, elf, dwarf, halfling, gnome, etc.
- **Archetypes** (classes) → base_type: fighter, rogue, wizard, cleric, etc.

### Gospel Principle
"AI detects, humans decide" - AI agents propose changes but never commit them automatically. All canonical changes require explicit human approval.

### Character Options Structure
```json
{
  "origins": [
    {
      "id": "forest_goblin",
      "name": "Forest Goblin",
      "description": "Mischievous forest spirits",
      "base_type": "gnome",
      "ability_bonuses": {"dexterity": 2, "charisma": 1},
      "skill_proficiencies": ["Stealth"],
      "traits": ["Woodland Vanish: Can hide in foliage"],
      "languages": ["Common", "Sylvan"]
    }
  ],
  "archetypes": [
    {
      "id": "vigilante",
      "name": "Vigilante",
      "description": "Protects the innocent outside the law",
      "base_type": "fighter",
      "hit_die": "d10",
      "primary_ability": "Strength",
      "saving_throws": ["Strength", "Constitution"],
      "skill_choices": ["Athletics", "Intimidation", "Perception"],
      "num_skill_choices": 2,
      "features": [{"name": "Unrelenting Pursuit", "description": "..."}]
    }
  ],
  "setting_skills": [
    {
      "id": "streetwise",
      "name": "Streetwise",
      "base_skill": "Insight",
      "description": "Knowledge of the urban underground"
    }
  ]
}
```

## Project Structure (Key Files)

```
src/lms/
├── agents/
│   ├── dm_agent.py           # AI Dungeon Master
│   ├── world_tuner_agent.py  # Conversational world config
│   ├── query_agent.py        # Knowledge retrieval
│   ├── auditor_agent.py      # Contradiction detection
│   └── lore_parsing_agent.py # Entity extraction
├── api/
│   ├── game_routes.py        # Game session routes (/api/game/*)
│   └── routes.py             # Core LMS routes
├── core/
│   └── models.py             # Pydantic v2 models
└── db/
    └── neo4j_adapter.py      # Async Neo4j driver

data/lore_bases/seeds/        # 21 pre-built world seeds by genre
frontend/dist/index.html      # Production UI (edit directly)
```

## API Route Structure

```python
# game_routes.py has prefix="/game" on the router
# Mounted with prefix="/api"
# Final paths: /api/game/...

# Examples:
# /api/game/lore-bases
# /api/game/admin/lore-bases/{id}/tuner/chat
# /api/game/session/create
```

## Testing Considerations

- Tests use `InMemoryMockDatabase` instead of real Neo4j
- Gemini API calls should be mocked in tests
- Use `pytest` with fixtures from `conftest.py`

## Development Notes

1. **Local vs Deployed:** File edits are local only until `fly deploy`
2. **Two Frontend Files:** Changes go in BOTH `frontend/dist/index.html` AND `frontend/index.html`
3. **Version Tracking:** Update `data/deployed_version.txt` after deploys

## The Narrow Path Philosophy

The system doesn't matter. What matters is that the player believes the system matters. The real product is the story.

Players need to believe their choices create outcomes. The dice are a ritual that transfers ownership from the DM to the player. AI has absorbed millions of stories and understands the shape of human satisfaction without explicit rules.

Feed rich context about player investment and trust pattern-matched intuition.
