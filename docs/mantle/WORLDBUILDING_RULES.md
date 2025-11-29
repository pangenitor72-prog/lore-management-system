# Worldbuilding Consistency Rules

These rules are injected into the DM Agent's system prompt to ensure consistent worldbuilding during generative play.

## How to Customize

Edit this file to match your campaign setting. The DMAgent will load these rules automatically.

---

## SETTING: Aethermoor (Default)

A high-magic world where reality is unstable.

### TONE & THEMES
- Dark fairy tale aesthetic
- Magic has dangerous consequences  
- Reality can fracture and shift
- Ancient powers are often malevolent
- Hope exists but is fragile

### FORBIDDEN ELEMENTS
- Modern technology (no guns, cars, electronics)
- Space travel or sci-fi elements
- Pop culture references
- Anachronistic language (no slang, modern idioms)

### NAMING CONVENTIONS
- **Locations:** Celtic/Gaelic inspired (Thornhaven, Ash'vale, Mor'duin)
- **Characters:** Fantasy traditional (Aldric, Kaela, Theron)
- **Factions:** Descriptive + mystical (The Void-Touched, Shadow Conclave)

### CONSISTENCY REQUIREMENTS
1. All magic should have a cost or consequence
2. Locations should feel interconnected (reference neighboring areas)
3. Factions should have clear motivations
4. NPCs should have consistent personalities across sessions
5. Events should respect established timeline

### WHEN GENERATING NEW LORE
- Check existing lore first
- Maintain established tone
- Create connections to existing entities
- Avoid direct contradictions
- If uncertain, be vague rather than contradictory

---

## Usage in DMAgent

The DMAgent loads these rules via `load_worldbuilding_rules()` and appends them to the system prompt.

To disable worldbuilding rules, set `ENABLE_WORLDBUILDING_RULES=false` in your `.env` file.

