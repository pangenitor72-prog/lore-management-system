# MANTLE Translation Layer

The MANTLE (Mechanical ANnotation and Translation Layer for Entities) system bridges narrative lore and D&D 5e mechanics. It ensures players see setting-appropriate terminology (like "Void-Knight" or "Netrunner") while the game engine uses standard D&D mechanics underneath.

## Overview

```
Player sees:     "Netrunner"  →  AI/System uses:  "Rogue" mechanics
Player sees:     "Mutant"     →  AI/System uses:  "Human" base stats
```

## Core Concepts

### Translation Bible
The mapping between world-specific terminology and D&D 5e base types. Each world has its own Translation Bible stored in `character_options`.

### Pending Mappings
AI-proposed translations that require admin approval before becoming active. This implements a "human-in-the-loop" workflow where AI suggests but admins decide.

### Confidence Scores
Each AI proposal includes a confidence score (0.0-1.0):
- **0.8-1.0**: Clear match (text explicitly describes mechanics that align)
- **0.5-0.7**: Reasonable inference (role/style suggests this mapping)
- **0.1-0.4**: Speculation (minimal textual evidence)

## Workflow

### 1. Lore Ingestion
When new lore is added to a world, the MANTLE Mapping Agent analyzes it:
1. **Extract**: Identifies character archetypes and origins from prose
2. **Source**: Quotes the specific text passage
3. **Propose**: Suggests best D&D 5e mechanical fit
4. **Justify**: Provides mechanical synergy explanation
5. **Score**: Rates confidence in the mapping

### 2. Admin Approval
Admins review AI proposals in the World Manager:
- **Approve**: Mapping becomes active in Translation Bible
- **Edit**: Modify the mechanical base before approval
- **Reject**: Discard the mapping

### 3. Character Creation
When players create characters:
- They see world-specific options (e.g., "Vigilante", "Psychic")
- System maps to D&D base types for mechanics
- Player never sees "rogue" or "cleric" - only setting terms

## API Endpoints

### List All Pending Mappings
```
GET /game/admin/pending-mappings
```
Returns all pending mappings grouped by world.

### Get World Mappings
```
GET /game/admin/lore-bases/{lore_id}/pending-mappings
```
Returns pending and active mappings for a specific world.

### Extract Mappings from Lore
```
POST /game/admin/lore-bases/{lore_id}/extract-mappings
```
Triggers AI analysis of world lore to generate pending mappings.

### Approve Mapping
```
POST /game/admin/pending-mappings/{mapping_id}/approve
```
Converts pending mapping to active, adds to Translation Bible.

### Reject Mapping
```
POST /game/admin/pending-mappings/{mapping_id}/reject
```
Marks mapping as rejected (retained for audit).

### Edit Mapping
```
POST /game/admin/pending-mappings/{mapping_id}/edit
```
Modify mechanical base or notes before approval.

### Bulk Approve
```
POST /game/admin/pending-mappings/bulk-approve
Body: { "world_id": "titan_city" }
```
Approves all pending mappings for a world at once.

## Data Model

### PendingMapping
```json
{
  "id": "titan_city_archetype_vigilante",
  "world_id": "titan_city",
  "mapping_type": "archetype",
  "lore_name": "Vigilante",
  "lore_description": "Street-level hero using martial arts and gadgets",
  "source_snippet": "In the Hollows, Vigilance protects those the Champions overlook...",
  "mechanical_base": "rogue",
  "ai_justification": "I chose Rogue because the text emphasizes stealth, gadgets, and street-level skills.",
  "confidence_score": 0.85,
  "status": "pending",
  "admin_notes": "",
  "created_at": "2026-01-21T...",
  "reviewed_at": null
}
```

### Mapping Status
- `pending`: AI proposed, awaiting admin review
- `active`: Admin approved, available for character creation
- `rejected`: Admin rejected (retained for audit)

## Frontend UI

The MANTLE Mappings modal is accessible from the World Manager via the "🔮 MANTLE Mappings" button.

Features:
- Pending/Active counters
- Per-mapping approve/reject/edit buttons
- Confidence score color coding (green ≥80%, yellow ≥50%, red <50%)
- Expandable source snippets
- Bulk approve action

## Backend Integration

### ConceptGenerator
The `ConceptGenerator` class accepts `world_character_options` to enable MANTLE mode:
- Builds dynamic keyword patterns from world options
- Scores user concept against world vocabulary
- Falls back to D&D term mapping if user uses standard terms
- Returns world-specific IDs with `base_type` for mechanics

### Character Sheet
When MANTLE is active:
- `origin` field contains world-specific ID (e.g., "mutant")
- `origin_base_type` contains D&D base (e.g., "human")
- Mechanics use base_type, display uses origin

## Example: Titan City (Superhero)

### Origins
| World Term | Base Type | Description |
|------------|-----------|-------------|
| Empowered Human | human | Transformed by cosmic event |
| Alien Visitor | elf | Being from another world |
| Mutant | human | Born with genetic mutations |
| Android | dwarf | Artificial being |

### Archetypes
| World Term | Base Type | Description |
|------------|-----------|-------------|
| Vigilante | rogue | Street-level hero with gadgets |
| Energy Controller | wizard | Wields cosmic/elemental forces |
| Super Soldier | fighter | Peak physical condition |
| Psychic | cleric | Mental powers like telepathy |

## Best Practices

1. **Review Low Confidence**: Pay extra attention to mappings <50% confidence
2. **Check Source Snippets**: Verify the AI found relevant text
3. **Consider Mechanics**: Does the base type's skills/features fit the role?
4. **Maintain Consistency**: Similar roles should map to similar base types
5. **Document Decisions**: Use admin_notes to explain unusual mappings
