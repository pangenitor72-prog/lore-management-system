from typing import List, Dict, Any
import logging

from src.lms.db.neo4j_adapter import Neo4jDatabase
from src.lms.services.audit_log import AuditLogger
from src.lms.core.models import Contradiction  # Pydantic model with .to_dict()

logger = logging.getLogger(__name__)


class RuleBasedAuditor:
    """
    Performs rule-based contradiction detection using Cypher queries
    against the Neo4j graph.

    This version is aligned with the current LMS/MANTLE data model:

    - Assumes entities are stored as :Entity nodes with:
        - canon_id (string, unique per entity)
        - name (string)
        - optional canonical_name
        - optional entity_type (e.g. Character, Location, Faction)
        - optional domain fields (race, birth_date, death_date, etc.)
    - Is defensive: every query is wrapped with try/except so audit
      failures do NOT crash the system.
    - Returns lists of Contradiction objects, then converted to dicts
      in run_full_audit() for API/JSON use.
    """

    def __init__(self, db: Neo4jDatabase):
        self.db = db

    # ============================================================
    # PUBLIC ENTRYPOINT
    # ============================================================

    async def run_full_audit(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run all rule-based audit checks.

        Returns:
            A dict keyed by check name, each value a list of
            contradiction dicts (via Contradiction.to_dict()).
        """
        await AuditLogger.log("Starting Neo4j rule-based audit...")

        results: Dict[str, List[Dict[str, Any]]] = {
            "conflicting_birthplaces": [],
            "impossible_timelines": [],
            "conflicting_memberships": [],
            "orphaned_relationships": [],
            "confidence_mismatches": [],
            "missing_required_fields": [],
            "self_referential_relationships": [],
            "circular_relationships": [],
            "unparseable_dates": [],
            "canonical_collisions": [],
        }

        # NOTE: Each check is isolated and defensive.
        checks = [
            ("conflicting_birthplaces", self.check_conflicting_birthplaces),
            ("impossible_timelines", self.check_impossible_timelines),
            ("conflicting_memberships", self.check_conflicting_memberships),
            ("orphaned_relationships", self.check_orphaned_relationships),
            ("confidence_mismatches", self.check_confidence_mismatches),
            ("missing_required_fields", self.check_missing_required_fields),
            ("self_referential_relationships", self.check_self_referential),
            ("circular_relationships", self.check_circular_relationships),
            ("unparseable_dates", self.check_unparseable_dates),
            ("canonical_collisions", self.check_canonical_collisions),
        ]

        for key, check_fn in checks:
            try:
                contradictions = await check_fn()
                results[key] = [c.to_dict() for c in contradictions]
            except Exception as e:
                # Audit failures should not take down the system
                await AuditLogger.log(
                    f"Rule-based audit check '{key}' failed: {e}",
                    level=logging.ERROR,
                )
                results[key] = []

        await AuditLogger.log("Neo4j rule-based audit complete.")

        # Optional: you can compute and log a summary here if desired
        summary = self.get_summary(results)
        await AuditLogger.log(
            f"Rule-based audit summary: {summary}",
            level=logging.INFO,
        )

        return results

    # ============================================================
    # INDIVIDUAL CHECKS
    # ============================================================

    async def check_conflicting_birthplaces(self) -> List[Contradiction]:
        """
        Check for entities with multiple conflicting birthplace relationships.

        This assumes (optionally) a pattern like:
            (e:Entity)-[:BORN_IN]->(loc:Entity {entity_type: 'Location'})

        If you never create BORN_IN edges, this will simply return [].
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)-[:BORN_IN]->(loc1:Entity)
        MATCH (e:Entity)-[:BORN_IN]->(loc2:Entity)
        WHERE loc1 <> loc2
        RETURN
            e.canon_id AS canon_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
            coalesce(loc1.name, loc1.canon_id) AS birthplace1,
            coalesce(loc2.name, loc2.canon_id) AS birthplace2
        """

        records = await self.db.execute(cypher)

        for conflict in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="CONFLICTING_BIRTHPLACES",
                    severity="HIGH",
                    description=(
                        f"Entity '{conflict['canonical_name']}' has conflicting birthplace "
                        f"entries: '{conflict['birthplace1']}' vs '{conflict['birthplace2']}'."
                    ),
                    entity_ids=[conflict["canon_id"]],
                    evidence={
                        "birthplace1": conflict["birthplace1"],
                        "birthplace2": conflict["birthplace2"],
                    },
                )
            )

        return contradictions

    async def check_impossible_timelines(self) -> List[Contradiction]:
        """
        Check for entities with birth_date after death_date.

        This assumes dates are stored as comparable values (e.g. strings
        in ISO-8601 or numeric years). If you don't store these fields,
        this will simply return [].
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)
        WHERE e.birth_date IS NOT NULL
          AND e.death_date IS NOT NULL
          AND e.birth_date > e.death_date
        RETURN
            e.canon_id AS canon_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
            e.birth_date AS birth_date,
            e.death_date AS death_date
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="IMPOSSIBLE_TIMELINE",
                    severity="HIGH",
                    description=(
                        f"Entity '{row['canonical_name']}' has death before birth "
                        f"({row['birth_date']} > {row['death_date']})."
                    ),
                    entity_ids=[row["canon_id"]],
                    evidence={
                        "birth_date": row["birth_date"],
                        "death_date": row["death_date"],
                    },
                )
            )

        return contradictions

    async def check_conflicting_memberships(self) -> List[Contradiction]:
        """
        Check for entities with multiple PRIMARY_MEMBER_OF relationships
        to different factions.

        Pattern:
            (e:Entity)-[:PRIMARY_MEMBER_OF]->(f:Entity)

        If you don't use PRIMARY_MEMBER_OF, this is a no-op.
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)-[:PRIMARY_MEMBER_OF]->(f1:Entity)
        MATCH (e:Entity)-[:PRIMARY_MEMBER_OF]->(f2:Entity)
        WHERE f1 <> f2 AND id(f1) < id(f2)
        RETURN
            e.canon_id AS entity_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
            f1.canon_id AS faction1_id,
            coalesce(f1.name, f1.canon_id) AS faction1_name,
            f2.canon_id AS faction2_id,
            coalesce(f2.name, f2.canon_id) AS faction2_name
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="CONFLICTING_MEMBERSHIP",
                    severity="MEDIUM",
                    description=(
                        f"Entity '{row['canonical_name']}' has PRIMARY membership in "
                        f"multiple factions: '{row['faction1_name']}' and '{row['faction2_name']}'."
                    ),
                    entity_ids=[
                        row["entity_id"],
                        row["faction1_id"],
                        row["faction2_id"],
                    ],
                    evidence={
                        "faction1": row["faction1_name"],
                        "faction2": row["faction2_name"],
                    },
                )
            )

        return contradictions

    async def check_orphaned_relationships(self) -> List[Contradiction]:
        """
        Check for nodes that reference non-existent entities via a
        "references" property containing canon_ids.

        Pattern:
            MATCH (n:Entity)
            WHERE n.references IS NOT NULL
            UNWIND n.references AS ref_id
            OPTIONAL MATCH (target:Entity {canon_id: ref_id})
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (n:Entity)
        WHERE n.references IS NOT NULL
        UNWIND n.references AS ref_id
        OPTIONAL MATCH (target:Entity {canon_id: ref_id})
        WITH n, ref_id, target
        WHERE target IS NULL
        RETURN
            n.canon_id AS from_canon_id,
            coalesce(n.canonical_name, n.name, n.canon_id) AS from_name,
            ref_id AS missing_entity_id
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="ORPHANED_RELATIONSHIP",
                    severity="HIGH",
                    description=(
                        f"Node '{row['from_name']}' references missing entity "
                        f"canon_id='{row['missing_entity_id']}'."
                    ),
                    entity_ids=[row["from_canon_id"]] if row["from_canon_id"] else [],
                    evidence={
                        "missing_entity_id": row["missing_entity_id"],
                        "relationship_type": "REFERENCES",
                    },
                )
            )

        return contradictions

    async def check_confidence_mismatches(self) -> List[Contradiction]:
        """
        Check for UNCERTAIN/SPECULATIVE entities that have CONFIRMED relationships.

        Pattern:
            (e:Entity {confidence_level IN ['UNCERTAIN','SPECULATIVE']})-[r]->(e2)
            WHERE r.confidence_level = 'CONFIRMED'

        If you don't store confidence_level on relationships, this
        will simply return [].
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)-[r]->(e2:Entity)
        WHERE e.confidence_level IN ['UNCERTAIN', 'SPECULATIVE']
          AND r.confidence_level = 'CONFIRMED'
        RETURN
            e.canon_id AS canon_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
            e.confidence_level AS entity_confidence,
            type(r) AS relationship_type,
            r.confidence_level AS relationship_confidence,
            coalesce(e2.canonical_name, e2.name, e2.canon_id) AS related_entity
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="CONFIDENCE_MISMATCH",
                    severity="MEDIUM",
                    description=(
                        f"Entity '{row['canonical_name']}' has low confidence "
                        f"('{row['entity_confidence']}') but a CONFIRMED "
                        f"relationship '{row['relationship_type']}' "
                        f"to '{row['related_entity']}'."
                    ),
                    entity_ids=[row["canon_id"]],
                    evidence={
                        "entity_confidence": row["entity_confidence"],
                        "relationship_type": row["relationship_type"],
                        "relationship_confidence": row["relationship_confidence"],
                        "related_entity": row["related_entity"],
                    },
                )
            )

        return contradictions

    async def check_missing_required_fields(self) -> List[Contradiction]:
        """
        Check for Character entities missing required fields like 'race'.

        We assume:
            - Characters are :Entity with entity_type = 'Character'
              OR labeled :Character.
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)
        WHERE
            (e.entity_type = 'Character' OR 'Character' IN labels(e))
            AND (e.race IS NULL OR trim(toString(e.race)) = '')
        RETURN
            e.canon_id AS canon_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="MISSING_REQUIRED_FIELD",
                    severity="LOW",
                    description=(
                        f"Character '{row['canonical_name']}' is missing required field: race."
                    ),
                    entity_ids=[row["canon_id"]],
                    evidence={"missing_field": "race"},
                )
            )

        return contradictions

    async def check_self_referential(self) -> List[Contradiction]:
        """
        Check for relationships where FROM and TO are the same entity.

        This flags potentially accidental self-links, which are usually
        modeling errors unless explicitly intended.
        """
        contradictions: List[Contradiction] = []

        cypher = """
        MATCH (e:Entity)-[r]->(e)
        RETURN
            e.canon_id AS canon_id,
            coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
            type(r) AS relationship_type,
            id(r) AS relationship_id
        """

        records = await self.db.execute(cypher)

        for row in records or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="SELF_REFERENTIAL",
                    severity="HIGH",
                    description=(
                        f"Entity '{row['canonical_name']}' has a self-referential "
                        f"relationship of type '{row['relationship_type']}'."
                    ),
                    entity_ids=[row["canon_id"]],
                    evidence={
                        "relationship_id": row["relationship_id"],
                        "relationship_type": row["relationship_type"],
                    },
                )
            )

        return contradictions

    async def check_circular_relationships(self) -> List[Contradiction]:
        """
        Check for 2-hop and 3-hop circular relationships among :Entity nodes.

        These can indicate muddled modeling or accidentally cyclical
        graph structure where hierarchy or directionality was expected.
        """
        contradictions: List[Contradiction] = []
        await AuditLogger.log("Running circular relationship checks...")

        # 2-hop cycles: a -> b -> a
        cypher_2hop = """
        MATCH (a:Entity)-[r1]->(b:Entity)-[r2]->(a)
        WHERE id(a) < id(b)
        RETURN DISTINCT
            a.canon_id AS entity_a,
            b.canon_id AS entity_b,
            coalesce(a.canonical_name, a.name, a.canon_id) AS name_a,
            coalesce(b.canonical_name, b.name, b.canon_id) AS name_b,
            type(r1) AS rel1_type,
            type(r2) AS rel2_type
        """

        cycles_2 = await self.db.execute(cypher_2hop)

        for row in cycles_2 or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="CIRCULAR_RELATIONSHIP",
                    severity="MEDIUM",
                    description=(
                        f"2-hop cycle detected between '{row['name_a']}' "
                        f"and '{row['name_b']}'."
                    ),
                    entity_ids=[row["entity_a"], row["entity_b"]],
                    evidence={
                        "cycle_type": "2-hop",
                        "entity_a": row["name_a"],
                        "entity_b": row["name_b"],
                        "relationship_1": row["rel1_type"],
                        "relationship_2": row["rel2_type"],
                    },
                )
            )

        # 3-hop cycles: a -> b -> c -> a
        cypher_3hop = """
        MATCH (a:Entity)-[r1]->(b:Entity)-[r2]->(c:Entity)-[r3]->(a)
        WHERE a <> b AND b <> c AND a <> c
          AND id(a) < id(b) AND id(a) < id(c)
        RETURN DISTINCT
            a.canon_id AS entity_a,
            b.canon_id AS entity_b,
            c.canon_id AS entity_c,
            coalesce(a.canonical_name, a.name, a.canon_id) AS name_a,
            coalesce(b.canonical_name, b.name, b.canon_id) AS name_b,
            coalesce(c.canonical_name, c.name, c.canon_id) AS name_c,
            type(r1) AS rel1_type,
            type(r2) AS rel2_type,
            type(r3) AS rel3_type
        """

        cycles_3 = await self.db.execute(cypher_3hop)

        for row in cycles_3 or []:
            contradictions.append(
                Contradiction(
                    contradiction_type="CIRCULAR_RELATIONSHIP",
                    severity="HIGH",
                    description=(
                        "3-hop cycle detected: "
                        f"{row['name_a']} -> {row['name_b']} -> "
                        f"{row['name_c']} -> {row['name_a']}."
                    ),
                    entity_ids=[row["entity_a"], row["entity_b"], row["entity_c"]],
                    evidence={
                        "cycle_type": "3-hop",
                        "entity_a": row["name_a"],
                        "entity_b": row["name_b"],
                        "entity_c": row["name_c"],
                        "relationships": [
                            row["rel1_type"],
                            row["rel2_type"],
                            row["rel3_type"],
                        ],
                    },
                )
            )

        await AuditLogger.log(
            f"Circular checks complete. Found {len(contradictions)} cycles."
        )
        return contradictions

    async def check_unparseable_dates(self) -> List[Contradiction]:
        """
        Check for date fields that don't match a simple expected format.

        We allow:
            - 'YYYY-MM-DD'
            - 'YYYY'

        Anything else (non-empty) is flagged as 'UNPARSEABLE_DATE'.
        """
        contradictions: List[Contradiction] = []
        date_fields = ["birth_date", "death_date", "founded_date", "occurred_date"]

        for field in date_fields:
            cypher = f"""
            MATCH (e:Entity)
            WHERE e.{field} IS NOT NULL
              AND size(toString(e.{field})) > 0
              AND NOT e.{field} =~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
              AND NOT e.{field} =~ '^\\d{{4}}$'
            RETURN
                e.canon_id AS canon_id,
                coalesce(e.canonical_name, e.name, e.canon_id) AS canonical_name,
                e.{field} AS date_value
            """

            records = await self.db.execute(cypher)

            for row in records or []:
                contradictions.append(
                    Contradiction(
                        contradiction_type="UNPARSEABLE_DATE",
                        severity="LOW",
                        description=(
                            f"Entity '{row['canonical_name']}' has unparseable "
                            f"date in field '{field}': {row['date_value']!r}."
                        ),
                        entity_ids=[row["canon_id"]],
                        evidence={
                            "field": field,
                            "invalid_value": row["date_value"],
                        },
                    )
                )

        return contradictions

    async def check_canonical_collisions(self) -> List[Contradiction]:
        """
        Check for entities that have duplicate normalized names (violation of Canonical Identity Policy).
        
        This detects when multiple entities of the same type share the same normalized name,
        indicating a failure of the ingestion canonicalization logic or legacy data issues.
        """
        contradictions: List[Contradiction] = []
        
        # Check for multiple entities with same (entity_type, normalized_name)
        # We rely on normalized_name being populated.
        
        cypher = """
        MATCH (e:Entity)
        WHERE e.normalized_name IS NOT NULL
        WITH e.entity_type as etype, e.normalized_name as norm, collect(e) as nodes
        WHERE size(nodes) > 1
        RETURN 
            etype, 
            norm, 
            nodes
        """
        
        records = await self.db.execute(cypher)
        
        for row in records or []:
             nodes = row['nodes']
             # Extract IDs and names
             ids = [n.get('canon_id') for n in nodes]
             names = [n.get('name') for n in nodes]
             
             contradictions.append(
                Contradiction(
                    contradiction_type="CANONICAL_COLLISION",
                    severity="HIGH",
                    description=(
                        f"Canonical Identity Violation: Multiple {row['etype']} entities "
                        f"share normalized name '{row['norm']}': {names}. "
                        f"IDs: {ids}"
                    ),
                    entity_ids=ids,
                    evidence={
                        "normalized_name": row['norm'],
                        "entity_type": row['etype'],
                        "conflicting_names": names
                    }
                )
             )
             
        return contradictions

    # ============================================================
    # SUMMARY
    # ============================================================

    def get_summary(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Generate summary statistics from rule-based audit results.

        Args:
            results: Dict from run_full_audit (values are lists of dicts)

        Returns:
            {
                "total_contradictions": int,
                "by_severity": {"HIGH": int, "MEDIUM": int, "LOW": int},
                "by_type": {check_name: count, ...}
            }
        """
        total = 0
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

        for contradictions in results.values():
            total += len(contradictions)
            for c in contradictions:
                sev = c.get("severity")
                if sev in severity_counts:
                    severity_counts[sev] += 1

        by_type = {k: len(v) for k, v in results.items() if v}

        return {
            "total_contradictions": total,
            "by_severity": severity_counts,
            "by_type": by_type,
        }