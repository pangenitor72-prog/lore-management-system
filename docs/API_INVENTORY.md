# API Inventory

## Server Configuration
- Host: 127.0.0.1
- Port: 8000

## MANTLE Translation Layer Endpoints

### Pending Mappings Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/game/admin/pending-mappings` | List all pending mappings across all worlds |
| GET | `/game/admin/lore-bases/{lore_id}/pending-mappings` | Get mappings for a specific world |
| POST | `/game/admin/lore-bases/{lore_id}/extract-mappings` | Extract mappings from world lore via AI |
| POST | `/game/admin/pending-mappings/{mapping_id}/approve` | Approve a pending mapping |
| POST | `/game/admin/pending-mappings/{mapping_id}/reject` | Reject a pending mapping |
| POST | `/game/admin/pending-mappings/{mapping_id}/edit` | Edit mapping before approval |
| POST | `/game/admin/pending-mappings/bulk-approve` | Bulk approve all pending for a world |

### Character Options Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/game/admin/lore-bases/{lore_id}/character-options` | Get world's character creation options |
| POST | `/game/admin/lore-bases/{lore_id}/character-options/generate` | AI-generate options from lore |
| PUT | `/game/admin/lore-bases/{lore_id}/character-options` | Update character options |

See [MANTLE Translation Layer](mantle/TRANSLATION_LAYER.md) for full documentation
