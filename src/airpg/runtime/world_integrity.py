# src/airpg/runtime/world_integrity.py
"""
World Integrity Check - The "Golden Master" validator.

Ensures world consistency across all users by validating that:
1. A Root node exists (Theme/Tone definition)
2. At least one Location is defined
3. At least one Faction or NPC exists

Also extracts "Immutable Canon Truths" for DM prompt injection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.lms.db.neo4j_adapter import Neo4jDatabase


class WorldNotReadyError(Exception):
    """
    Raised when attempting to start a session in an incomplete world.

    A world must have:
    - A Root node (Campaign/World with theme/tone)
    - At least one Location
    - At least one Faction OR NPC

    This prevents users from spawning into a void.
    """

    def __init__(self, errors: List[str], world_id: Optional[str] = None):
        self.errors = errors
        self.world_id = world_id
        message = f"World not ready for gameplay: {'; '.join(errors)}"
        if world_id:
            message = f"[{world_id}] {message}"
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API error response."""
        return {
            "error": "world_not_ready",
            "world_id": self.world_id,
            "errors": self.errors,
            "message": str(self),
        }


@dataclass
class CanonTruths:
    """
    Immutable Canon Truths extracted from the world.

    These are injected into every DM prompt to ensure consistent
    tone and theme across all users and sessions.
    """
    world_name: str = "Unknown World"
    theme: str = "Fantasy Adventure"
    tone: str = "Balanced"
    core_conflict: str = ""
    key_factions: List[str] = field(default_factory=list)
    forbidden_elements: List[str] = field(default_factory=list)

    def to_prompt_injection(self) -> str:
        """Format canon truths for DM prompt injection."""
        factions = ", ".join(self.key_factions) if self.key_factions else "None defined"
        forbidden = ", ".join(self.forbidden_elements) if self.forbidden_elements else "None"

        return f"""
=== IMMUTABLE CANON TRUTHS (Never Contradict) ===
World: {self.world_name}
Theme: {self.theme}
Tone: {self.tone}
Core Conflict: {self.core_conflict or "To be discovered"}
Key Factions: {factions}
Forbidden Elements: {forbidden}
"""


@dataclass
class IntegrityResult:
    """Result of a world integrity check."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    canon_truths: Optional[CanonTruths] = None

    # Counts for reporting
    location_count: int = 0
    faction_count: int = 0
    npc_count: int = 0
    has_root: bool = False


class WorldIntegrityCheck:
    """
    Validates world state before a session can begin.

    Requirements for a valid world:
    1. Root node with Theme/Tone defined
    2. At least 1 Location
    3. At least 1 Faction OR 1 NPC
    """

    def __init__(self, db: "Neo4jDatabase"):
        self.db = db

    async def validate(self, campaign_id: Optional[str] = None) -> IntegrityResult:
        """
        Run full integrity check on the world.

        Args:
            campaign_id: Optional campaign to scope the check

        Returns:
            IntegrityResult with validation status and extracted truths
        """
        result = IntegrityResult(is_valid=True)
        errors = []
        warnings = []

        # 1. Check for Root/World definition
        root_data = await self._check_root(campaign_id)
        if root_data:
            result.has_root = True
            result.canon_truths = self._extract_canon_truths(root_data)
        else:
            errors.append("No world root defined. Create a Campaign or World node with theme/tone.")
            result.has_root = False

        # 2. Check for Locations
        result.location_count = await self._count_nodes("Location", campaign_id)
        if result.location_count == 0:
            errors.append("No locations defined. Create at least one Location node.")

        # 3. Check for Factions or NPCs
        result.faction_count = await self._count_nodes("Faction", campaign_id)
        result.npc_count = await self._count_nodes("Character", campaign_id)

        if result.faction_count == 0 and result.npc_count == 0:
            errors.append("No factions or NPCs defined. Create at least one Faction or Character.")

        # Warnings for sparse worlds
        if result.location_count == 1:
            warnings.append("Only one location defined. Consider adding more for variety.")
        if result.faction_count == 0:
            warnings.append("No factions defined. Factions add political depth.")

        # Set final validity
        result.errors = errors
        result.warnings = warnings
        result.is_valid = len(errors) == 0

        return result

    async def _check_root(self, campaign_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Check for and return root/world definition."""
        if campaign_id:
            query = """
            MATCH (c:Campaign {campaign_id: $cid})
            RETURN c.name AS name, c.theme AS theme, c.tone AS tone,
                   c.core_conflict AS core_conflict, c.description AS description
            """
            result = await self.db.execute(query, {"cid": campaign_id})
        else:
            # Check for any World or Campaign node
            query = """
            MATCH (w) WHERE w:Campaign OR w:World
            RETURN w.name AS name, w.theme AS theme, w.tone AS tone,
                   w.core_conflict AS core_conflict, w.description AS description
            LIMIT 1
            """
            result = await self.db.execute(query, {})

        return result[0] if result else None

    async def _count_nodes(self, label: str, campaign_id: Optional[str]) -> int:
        """Count nodes of a specific label."""
        if campaign_id:
            query = f"""
            MATCH (n:{label})-[:BELONGS_TO]->(:Campaign {{campaign_id: $cid}})
            RETURN count(n) AS count
            """
            result = await self.db.execute(query, {"cid": campaign_id})
        else:
            query = f"MATCH (n:{label}) RETURN count(n) AS count"
            result = await self.db.execute(query, {})

        return result[0]["count"] if result else 0

    def _extract_canon_truths(self, root_data: Dict[str, Any]) -> CanonTruths:
        """Extract immutable canon truths from root data."""
        return CanonTruths(
            world_name=root_data.get("name") or "Unknown World",
            theme=root_data.get("theme") or "Fantasy Adventure",
            tone=root_data.get("tone") or "Balanced",
            core_conflict=root_data.get("core_conflict") or "",
        )

    async def get_canon_truths(self, campaign_id: Optional[str] = None) -> CanonTruths:
        """
        Get canon truths without full validation.

        Useful for injecting into DM prompts without blocking on errors.
        """
        root_data = await self._check_root(campaign_id)
        if root_data:
            truths = self._extract_canon_truths(root_data)

            # Also fetch key factions
            factions = await self._get_faction_names(campaign_id)
            truths.key_factions = factions

            return truths

        return CanonTruths()

    async def _get_faction_names(self, campaign_id: Optional[str]) -> List[str]:
        """Get names of key factions."""
        if campaign_id:
            query = """
            MATCH (f:Faction)-[:BELONGS_TO]->(:Campaign {campaign_id: $cid})
            RETURN f.name AS name LIMIT 5
            """
            result = await self.db.execute(query, {"cid": campaign_id})
        else:
            query = "MATCH (f:Faction) RETURN f.name AS name LIMIT 5"
            result = await self.db.execute(query, {})

        return [r["name"] for r in result if r.get("name")]


async def validate_world_before_session(
    db: "Neo4jDatabase",
    campaign_id: Optional[str] = None,
    allow_empty: bool = False,
) -> IntegrityResult:
    """
    Convenience function to validate world before starting a session.

    Args:
        db: Neo4j database connection
        campaign_id: Optional campaign to validate
        allow_empty: If True, return valid even if world is empty (for new games)

    Returns:
        IntegrityResult
    """
    checker = WorldIntegrityCheck(db)
    result = await checker.validate(campaign_id)

    if allow_empty and not result.is_valid:
        # For new games, we allow starting with empty world
        result.is_valid = True
        result.warnings.extend(result.errors)
        result.errors = []


async def require_valid_world(
    db: "Neo4jDatabase",
    world_id: Optional[str] = None,
    allow_empty: bool = False,
) -> IntegrityResult:
    """
    Validate world and raise WorldNotReadyError if invalid.

    Use this before create_session to prevent spawning into a void.

    Args:
        db: Neo4j database connection
        world_id: World/campaign ID to validate
        allow_empty: If True, allow empty worlds (for Session 0 creation)

    Returns:
        IntegrityResult if valid

    Raises:
        WorldNotReadyError: If world is not ready for gameplay
    """
    result = await validate_world_before_session(db, world_id, allow_empty)

    if not result.is_valid:
        raise WorldNotReadyError(result.errors, world_id)

    return result
