"""
Central constants for the Lore Management System (LMS)
All string literals shared across modules.
"""

# === VALID ENTITY TYPES ===
VALID_ENTITY_TYPES = [
    "Character",
    "Location",
    "Faction",
    "Event",
    "Item",
    "Concept",
]

# === VALID RELATIONSHIP TYPES ===
VALID_RELATIONSHIP_TYPES = [
    "LOCATED_IN",
    "MEMBER_OF",
    "PRIMARY_MEMBER_OF",
    "OWNS",
    "CREATED",
    "DEFEATED",
    "ALLIED_WITH",
    "ENEMY_OF",
    "KNOWS",
    "WIELDS",
    "RELATED_TO",
    "REFERENCES",
    "VULNERABLE_TO",
    "PARTICIPATED_IN",
    "PARENT_OF",
    "CHILD_OF",
]

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
