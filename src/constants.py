"""
Central constants for the Lore Management System (LMS)
All string literals shared across modules.
"""

# === HANDLERS ===
HANDLER_RULES = "rules"
HANDLER_SECURITY = "security"
HANDLER_STATIC = "static"
HANDLER_AI = "ai"

# === ACTIONS ===
ACTION_LIST_ENTITIES = "list_entities"
ACTION_GET_ENTITY = "get_entity"
ACTION_SEARCH_ENTITIES = "search_entities"
ACTION_LIST_CONTRADICTIONS = "list_contradictions"
ACTION_BLOCK = "block"
ACTION_HELP = "help"
ACTION_STATUS = "status"

# === ENTITY TYPES ===
ENTITY_CHARACTER = "character"
ENTITY_LOCATION = "location"
ENTITY_ITEM = "item"
ENTITY_FACTION = "faction"
ENTITY_EVENT = "event"

# === CONTRADICTION STATUSES ===
STATUS_PENDING = "pending"
STATUS_IN_REVIEW = "in_review"
STATUS_RESOLVED = "resolved"
STATUS_DISMISSED = "dismissed"

# === CONTRADICTION SEVERITIES ===
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
