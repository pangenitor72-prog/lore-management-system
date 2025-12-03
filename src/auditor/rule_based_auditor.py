from typing import List, Dict, Any
import logging
from src.db.neo4j_adapter import Neo4jDatabase
from src.services.audit_log import AuditLogger
from src.core.models import Contradiction # Now imported from models

logger = logging.getLogger(__name__)


class RuleBasedAuditor:
    """
    Performs rule-based contradiction detection using Cypher queries against the Neo4j graph.
    """

    def __init__(self, db: Neo4jDatabase):
        self.db = db

    async def run_full_audit(self) -> Dict[str, List[Dict]]:
        """Runs all RULE-BASED audit checks using Cypher queries."""
        await AuditLogger.log("Starting Neo4j rule-based audit...")
        
        results = {
            "conflicting_birthplaces": [],
            "impossible_timelines": [],
            "conflicting_memberships": [],
            "orphaned_relationships": [],
            "confidence_mismatches": [],
            "missing_required_fields": [],
            "self_referential_relationships": [],
            "circular_relationships": [],
            "unparseable_dates": []
        }
        
        results["conflicting_birthplaces"] = [c.to_dict() for c in await self.check_conflicting_birthplaces()]
        results["impossible_timelines"] = [c.to_dict() for c in await self.check_impossible_timelines()]
        results["conflicting_memberships"] = [c.to_dict() for c in await self.check_conflicting_memberships()]
        results["orphaned_relationships"] = [c.to_dict() for c in await self.check_orphaned_relationships()]
        results["confidence_mismatches"] = [c.to_dict() for c in await self.check_confidence_mismatches()]
        results["missing_required_fields"] = [c.to_dict() for c in await self.check_missing_required_fields()]
        results["self_referential_relationships"] = [c.to_dict() for c in await self.check_self_referential()]
        results["circular_relationships"] = [c.to_dict() for c in await self.check_circular_relationships()]
        results["unparseable_dates"] = [c.to_dict() for c in await self.check_unparseable_dates()]
        
        await AuditLogger.log("Neo4j rule-based audit complete.")
        
        summary = self.get_summary(results)
        # Assuming broadcaster is available for publishing events if needed
        # await broadcaster.publish("auditor_events", {
        #     "type": "audit_progress",
        #     "message": "Rule-based audit complete.",
        #     "summary": summary
        # })
        return results
    
    async def check_conflicting_birthplaces(self) -> List[Contradiction]:
        """Check for entities with multiple conflicting birthplace values stored as properties."""
        contradictions = []
        cypher = """
        MATCH (e)-[:BORN_IN]->(loc1:Location)
        MATCH (e)-[:BORN_IN]->(loc2:Location)
        WHERE loc1 <> loc2
        RETURN e.canon_id AS canon_id, 
               e.name AS canonical_name,
               loc1.name AS birthplace1, 
               loc2.name AS birthplace2
        """
        records = await self.db.execute(cypher)
        
        if records:
            for conflict in records:
                contradictions.append(Contradiction(
                    contradiction_type="CONFLICTING_BIRTHPLACES", severity="HIGH",
                    description=f"Entity '{conflict['canonical_name']}' has conflicting birthplace entries",
                    entity_ids=[conflict['canon_id']],
                    evidence={"birthplace1": conflict['birthplace1'], "birthplace2": conflict['birthplace2']}
                ))
        return contradictions
    
    async def check_impossible_timelines(self) -> List[Contradiction]:
        """Check for entities with birth_date after death_date."""
        contradictions = []
        cypher = """
        MATCH (e)
        WHERE e.birth_date IS NOT NULL AND e.death_date IS NOT NULL
        AND e.birth_date > e.death_date
        RETURN e.canon_id AS canon_id, 
               e.name AS canonical_name,
               e.birth_date AS birth_date, 
               e.death_date AS death_date
        """
        records = await self.db.execute(cypher)
        
        if records:
            for impossible in records:
                contradictions.append(Contradiction(
                    contradiction_type="IMPOSSIBLE_TIMELINE", severity="HIGH",
                    description=f"Entity '{impossible['canonical_name']}' has death before birth",
                    entity_ids=[impossible['canon_id']],
                    evidence={"birth_date": impossible['birth_date'], "death_date": impossible['death_date']}
                ))
        return contradictions
    
    async def check_conflicting_memberships(self) -> List[Contradiction]:
        """Check for entities with multiple PRIMARY_MEMBER_OF relationships."""
        contradictions = []
        cypher = """
        MATCH (e)-[:PRIMARY_MEMBER_OF]->(f1)
        MATCH (e)-[:PRIMARY_MEMBER_OF]->(f2)
        WHERE f1 <> f2 AND id(f1) < id(f2)
        RETURN e.canon_id AS entity_id, 
               e.name AS canonical_name,
               f1.canon_id AS faction1_id, 
               f1.name AS faction1_name,
               f2.canon_id AS faction2_id, 
               f2.name AS faction2_name
        """
        records = await self.db.execute(cypher)
        
        if records:
            for conflict in records:
                contradictions.append(Contradiction(
                    contradiction_type="CONFLICTING_MEMBERSHIP", severity="MEDIUM",
                    description=f"Entity '{conflict['canonical_name']}' has primary membership in multiple factions",
                    entity_ids=[conflict['entity_id'], conflict['faction1_id'], conflict['faction2_id']],
                    evidence={"faction1": conflict['faction1_name'], "faction2": conflict['faction2_name']}
                ))
        return contradictions
    
    async def check_orphaned_relationships(self) -> List[Contradiction]:
        """Check for relationships pointing to non-existent entities."""
        contradictions = []
        cypher = """
        MATCH (n)
        WHERE n.references IS NOT NULL
        UNWIND n.references AS ref_id
        OPTIONAL MATCH (target {canon_id: ref_id})
        WITH n, ref_id, target
        WHERE target IS NULL
        RETURN n.canon_id AS from_canon_id, 
               ref_id AS missing_entity_id,
               'REFERENCES' AS relationship_type
        """
        records = await self.db.execute(cypher)
        
        if records:
            for orphan in records:
                contradictions.append(Contradiction(
                    contradiction_type="ORPHANED_RELATIONSHIP", severity="HIGH",
                    description="Node references non-existent entity",
                    entity_ids=[orphan['from_canon_id']] if orphan['from_canon_id'] else [],
                    evidence= {
                        "missing_entity_id": orphan['missing_entity_id'],
                        "relationship_type": orphan['relationship_type']
                    }
                ))
        return contradictions
    
    async def check_confidence_mismatches(self) -> List[Contradiction]:
        """Check for UNCERTAIN/SPECULATIVE entities with CONFIRMED relationships."""
        contradictions = []
        cypher = """
        MATCH (e)-[r]->(e2)
        WHERE e.confidence_level IN ['UNCERTAIN', 'SPECULATIVE']
        AND r.confidence_level = 'CONFIRMED'
        RETURN e.canon_id AS canon_id, 
               e.name AS canonical_name,
               e.confidence_level AS entity_confidence,
               type(r) AS relationship_type, 
               r.confidence_level AS relationship_confidence,
               e2.name AS related_entity
        """
        records = await self.db.execute(cypher)
        
        if records:
            for mismatch in records:
                contradictions.append(Contradiction(
                    contradiction_type="CONFIDENCE_MISMATCH", severity="MEDIUM",
                    description=f"Entity '{mismatch['canonical_name']}' has low confidence but confirmed relationship",
                    entity_ids=[mismatch['canon_id']],
                    evidence= {
                        "entity_confidence": mismatch['entity_confidence'],
                        "relationship_type": mismatch['relationship_type'],
                        "relationship_confidence": mismatch['relationship_confidence'],
                        "related_entity": mismatch['related_entity']
                    }
                ))
        return contradictions
    
    async def check_missing_required_fields(self) -> List[Contradiction]:
        """Check for Character entities missing required fields like 'race'."""
        contradictions = []
        cypher = """
        MATCH (e:Character)
        WHERE e.race IS NULL
        RETURN e.canon_id AS canon_id, 
               e.name AS canonical_name
        """
        records = await self.db.execute(cypher)
        
        if records:
            for entity in records:
                contradictions.append(Contradiction(
                    contradiction_type="MISSING_REQUIRED_FIELD", severity="LOW",
                    description=f"Character '{entity['canonical_name']}' missing required field: race",
                    entity_ids=[entity['canon_id']],
                    evidence={"missing_field": "race"}
                ))
        return contradictions
    
    async def check_self_referential(self) -> List[Contradiction]:
        """Check for relationships where FROM and TO are the same entity."""
        contradictions = []
        cypher = """
        MATCH (e)-[r]->(e)
        RETURN e.canon_id AS from_canon_id, 
               e.name AS canonical_name,
               type(r) AS relationship_type,
               id(r) AS relationship_id
        """
        records = await self.db.execute(cypher)
        
        if records:
            for ref in records:
                contradictions.append(Contradiction(
                    contradiction_type="SELF_REFERENTIAL", severity="HIGH",
                    description=f"Entity '{ref['canonical_name']}' has relationship to itself",
                    entity_ids=[ref['from_canon_id']],
                    evidence={"relationship_id": ref['relationship_id'], "relationship_type": ref['relationship_type']}
                ))
        return contradictions
    
    async def check_circular_relationships(self) -> List[Contradiction]:
        """Check for 2-hop and 3-hop circular relationships."""
        await AuditLogger.log("Running circular relationship checks...")
        contradictions = []
        
        # 2-hop cycles
        cypher_2hop = """
        MATCH (a)-[r1]->(b)-[r2]->(a)
        WHERE id(a) < id(b)
        RETURN DISTINCT 
            a.canon_id AS entity_a, 
            b.canon_id AS entity_b,
            a.name AS name_a, 
            b.name AS name_b,
            type(r1) AS rel1_type, 
            type(r2) AS rel2_type
        """
        cycles_2 = await self.db.execute(cypher_2hop)
        
        if cycles_2:
            for cycle in cycles_2:
                contradictions.append(Contradiction(
                    contradiction_type="CIRCULAR_RELATIONSHIP", severity="MEDIUM",
                    description=f"2-hop cycle detected: {cycle['name_a']} <-> {cycle['name_b']}",
                    entity_ids=[cycle['entity_a'], cycle['entity_b']],
                    evidence= {
                        "cycle_type": "2-hop", "entity_a": cycle['name_a'], "entity_b": cycle['name_b'],
                        "relationship_1": cycle['rel1_type'], "relationship_2": cycle['rel2_type']
                    }
                ))

        # 3-hop cycles
        cypher_3hop = """
        MATCH (a)-[r1]->(b)-[r2]->(c)-[r3]->(a)
        WHERE a <> b AND b <> c AND a <> c
        AND id(a) < id(b) AND id(a) < id(c)
        RETURN DISTINCT
            a.canon_id AS entity_a, 
            b.canon_id AS entity_b, 
            c.canon_id AS entity_c,
            a.name AS name_a, 
            b.name AS name_b, 
            c.name AS name_c,
            type(r1) AS rel1_type, 
            type(r2) AS rel2_type, 
            type(r3) AS rel3_type
        """
        cycles_3 = await self.db.execute(cypher_3hop)
        
        if cycles_3:
            for cycle in cycles_3:
                contradictions.append(Contradiction(
                    contradiction_type="CIRCULAR_RELATIONSHIP", severity="HIGH",
                    description=f"3-hop cycle detected: {cycle['name_a']} -> {cycle['name_b']} -> {cycle['name_c']} -> {cycle['name_a']}",
                    entity_ids=[cycle['entity_a'], cycle['entity_b'], cycle['entity_c']],
                    evidence= {
                        "cycle_type": "3-hop", 
                        "entity_a": cycle['name_a'], 
                        "entity_b": cycle['name_b'], 
                        "entity_c": cycle['name_c'],
                        "relationships": [cycle['rel1_type'], cycle['rel2_type'], cycle['rel3_type']]
                    }
                ))
        
        await AuditLogger.log(f"Circular checks complete. Found {len(contradictions)} cycles.")
        return contradictions
    
    async def check_unparseable_dates(self) -> List[Contradiction]:
        """Check for date fields that don't match expected format."""
        contradictions = []
        date_fields = ['birth_date', 'death_date', 'founded_date', 'occurred_date']
        
        for field in date_fields:
            cypher = f"""
            MATCH (e)
            WHERE e.{field} IS NOT NULL
            AND NOT e.{field} =~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$'
            AND NOT e.{field} =~ '^\\d{{4}}$'
            AND size(toString(e.{field})) > 0
            RETURN e.canon_id AS canon_id, 
                   e.name AS canonical_name,
                   e.{field} AS date_value
            """
            records = await self.db.execute(cypher)
            
            if records:
                for bad in records:
                    contradictions.append(Contradiction(
                        contradiction_type="UNPARSEABLE_DATE", severity="LOW",
                        description=f"Entity '{bad['canonical_name']}' has unparseable date in {field}",
                        entity_ids=[bad['canon_id']],
                        evidence={"field": field, "invalid_value": bad['date_value']}
                    ))
        return contradictions
    
    def get_summary(self, results: Dict[str, List[Dict]]) -> Dict:
        """Generate summary statistics from rule-based audit results."""
        total = sum(len(contradictions) for contradictions in results.values())
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for contradictions in results.values():
            for c in contradictions:
                severity_counts[c["severity"]] += 1
        return {
            "total_contradictions": total,
            "by_severity": severity_counts,
            "by_type": {k: len(v) for k, v in results.items() if len(v) > 0}
        }
