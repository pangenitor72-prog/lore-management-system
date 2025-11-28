"""
Auditor Agent - Contradiction Detection System
Detects 9 types of logical and temporal contradictions in lore database (Rule-Based)
AND complex semantic contradictions (AI-Based).

Refactored to use Neo4j graph database instead of SQLite.
"""

from __future__ import annotations

from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import json
import re
import uuid
from audit_log import AuditLogger
import logging
import asyncio
from .neo4j_adapter import Neo4jDatabase
import google.generativeai as genai
from .broadcaster import broadcaster



class Contradiction:
    """Represents a detected contradiction."""

    def __init__(
        self,
        contradiction_type: str,
        severity: str,
        description: str,
        entity_ids: List[str],
        evidence: Dict
    ):
        self.type = contradiction_type
        self.severity = severity
        self.description = description
        self.entity_ids = entity_ids
        self.evidence = evidence

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "entity_ids": self.entity_ids,
            "evidence": self.evidence
        }


class AuditorAgent:
    """Runs systematic audits for contradictions in Neo4j graph database."""

    def __init__(self, neo4j_db: Neo4jDatabase, gemini_api_key: str):
        self.db = neo4j_db
        genai.configure(api_key=gemini_api_key)
        self.flash = genai.GenerativeModel("gemini-2.5-flash")
        self.pro = genai.GenerativeModel("gemini-2.5-pro")
        AuditLogger.log_sync("AuditorAgent: Neo4j + AI hybrid mode initialized.")
    def detect_contradictions(self, entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Finds, Scores, and suggests Resolutions for AI-detected contradictions."""
        a_name, b_name = entity_a.get("name","?"), entity_b.get("name","?")
        AuditLogger.log_sync(f"AI-DETECT: Comparing {a_name} vs {b_name}")
        prompt = self._build_prompt(entity_a, entity_b)
        
        try:
            resp = self.flash.generate_content(
                prompt,
                generation_config={"temperature":0.1,"top_p":0.95,"max_output_tokens":4096}
            )
            contradictions = self._parse_json_array(resp.text)
            
            final_contradictions = []
            for con in contradictions:
                scored_con = self._score_contradiction_confidence(con, entity_a, entity_b)
                resolved_con = self._suggest_resolutions(scored_con, entity_a, entity_b)
                final_contradictions.append(resolved_con)

            return final_contradictions
            
        except Exception as e:
            AuditLogger.log_sync(f"AI detection failed: {e}", level=logging.ERROR)
            return []

    async def _fetch_entities(self, limit: int | None = None) -> List[Dict[str, Any]]:
        """Fetches all entity nodes from the Neo4j graph."""
        await AuditLogger.log("Fetching entities from Neo4j...")
        
        cypher = """
        MATCH (n)
        WHERE n.canon_id IS NOT NULL
        RETURN n.canon_id AS canon_id, 
               n.name AS name,
               n.canonical_name AS canonical_name,
               labels(n)[0] AS entity_type,
               properties(n) AS properties
        """
        if limit:
            cypher += f" LIMIT {limit}"
        
        records = await self.db.execute(cypher)
        
        entities = []
        if records:
            for record in records:
                entity = {
                    "canon_id": record["canon_id"],
                    "name": record["name"] or record["canonical_name"],
                    "canonical_name": record["canonical_name"],
                    "type": record["entity_type"],
                    **record["properties"]
                }
                entities.append(entity)
        
        await AuditLogger.log(f"Fetch complete. {len(entities)} entities loaded.")
        return entities

    async def analyze_all_entities(self, limit: int | None = None) -> int:
        """Runs detect_contradictions across all entity pairs and persists findings."""
        await AuditLogger.log("Batch AI scan start")
        
        entities = await self._fetch_entities(limit)
        
        count = 0
        for i, a in enumerate(entities):
            for b in entities[i+1:]:
                if not await self._should_compare(a, b): 
                    continue
                
                cons = self.detect_contradictions(a, b)
                
                for c in cons:
                    await self.persist_contradiction(c, a, b)
                    count += 1
                
        await AuditLogger.log(f"Complete: {count} contradictions found and persisted.")
        await broadcaster.publish("auditor_events", {
            "type": "audit_progress",
            "message": f"AI audit complete. {count} contradictions found and persisted.",
            "total_contradictions_found": count
        })
        return count

    async def _should_compare(self, a: Dict, b: Dict) -> bool:
        """Logic to decide if two entities are worth an AI comparison."""
        try:
            # Same name = always compare
            if a.get("name", "").lower() == b.get("name", "").lower():
                return True
            # Same type = always compare
            if a.get("type") == b.get("type"):
                return True
            
            # Check if there's a relationship between them in the graph
            cypher = """
            MATCH (a {canon_id: $from_id})-[r]-(b {canon_id: $to_id})
            RETURN count(r) AS cnt
            """
            params = {"from_id": a["canon_id"], "to_id": b["canon_id"]}
            
            records = await self.db.execute(cypher, params)
            if records and len(records) > 0:
                cnt = records[0]["cnt"]
                return cnt > 0
            return False
        except Exception as e:
            AuditLogger.log_sync(f"_should_compare error: {e}")
            return False

    def _build_prompt(self,a,b)->str:
        """Builds the initial detection prompt for Gemini-Flash."""
        return f"""
You are a lore consistency analyzer. Compare:

ENTITY_A:
{json.dumps(a,indent=2)}

ENTITY_B:
{json.dumps(b,indent=2)}

Identify contradictions (attribute, relationship, temporal, geographic, narrative).
Return ONLY a JSON array like:
[{{"type":"temporal","severity":"HIGH","description":"...",
"evidence_a":"...","evidence_b":"...","confidence":0.9,
"reasoning":"...","possible_resolutions":["..."]}}]
If none, return [].
""".strip()

    def _parse_json_array(self,text:str)->List[Dict[str,Any]]:
        """Parses the JSON array from the AI's response."""
        if not text: return []
        m=re.search(r"\[.*\]",text,re.DOTALL)
        if not m:
            m=re.search(r"\{.*\}",text,re.DOTALL)
            if m:
                try:
                    d=json.loads(m.group())
                    if isinstance(d,dict) and "contradictions" in d:
                        arr=d["contradictions"]
                        return arr if isinstance(arr,list) else []
                except json.JSONDecodeError:
                    AuditLogger.log_sync("Failed to parse dict from LLM response for contradictions.")
                    return []
            return []
        try:
            arr=json.loads(m.group())
            return arr if isinstance(arr,list) else []
        except json.JSONDecodeError:
            AuditLogger.log_sync("Failed to parse list from LLM response for contradictions.")
            return []

    def _score_contradiction_confidence(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """Uses gemini-1.5-pro to assign a confidence score."""
        AuditLogger.log_sync(f"AI-SCORE: Scoring contradiction: {contradiction.get('description', 'N/A')[:50]}...")
        
        prompt = f"""
You are a confidence score analyst.
A "flash" model has detected the following contradiction:
ENTITY_A: {json.dumps(entity_a, indent=2)}
ENTITY_B: {json.dumps(entity_b, indent=2)}
DETECTED CONTRADICTION: {json.dumps(contradiction, indent=2)}
Your task is to analyze this contradiction and the evidence.
Return ONLY a JSON object with your analysis, like this:
{{"confidence": 0.85, "reasoning": "The flash model's reasoning is sound..."}}
Assign a confidence score from 0.0 (unlikely) to 1.0 (certain).
"""
        
        try:
            resp = self.pro.generate_content(
                prompt,
                generation_config={"temperature": 0.0}
            )
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                score_data = json.loads(match.group())
                contradiction["confidence"] = score_data.get("confidence", 0.0)
                contradiction["scoring_reasoning"] = score_data.get("reasoning", "No reasoning provided.")
            else:
                contradiction["confidence"] = 0.0
                contradiction["scoring_reasoning"] = "Failed to parse pro-model scoring response."
        except Exception as e:
            AuditLogger.log_sync(f"AI scoring failed: {e}", level=logging.ERROR)
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = f"Error during scoring: {e}"
        return contradiction

    def _suggest_resolutions(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """Uses gemini-1.5-pro to suggest resolutions."""
        if contradiction.get("confidence", 0.0) < 0.7:
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = "Confidence score too low to suggest resolution."
            return contradiction

        AuditLogger.log_sync(f"AI-RESOLVE: Suggesting resolutions for: {contradiction.get('description', 'N/A')[:50]}...")
        
        prompt = f"""
You are a "Lore Arbiter's Assistant."
A highly confident contradiction has been detected:
ENTITY_A: {json.dumps(entity_a, indent=2)}
ENTITY_B: {json.dumps(entity_b, indent=2)}
DETECTED CONTRADICTION (Confidence: {contradiction.get('confidence')}):
{json.dumps(contradiction, indent=2)}

Your task is to suggest 1-3 possible resolutions for the human arbiter (the DM).
NEVER decide the "truth." Only present options. Adhere to the Gospel Principle.
Example: "Verify the 'death_date' of Entity A from Source X."

Return ONLY a JSON object like this:
{{"reasoning": "The core conflict is a temporal paradox.",
  "possible_resolutions": ["SUGGESTION 1: ..."]
}}
"""
        
        try:
            resp = self.pro.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                res_data = json.loads(match.group())
                contradiction["possible_resolutions"] = res_data.get("possible_resolutions", [])
                contradiction["resolution_reasoning"] = res_data.get("reasoning", "No reasoning provided.")
            else:
                contradiction["possible_resolutions"] = []
                contradiction["resolution_reasoning"] = "Failed to parse pro-model resolution response."
        except Exception as e:
            AuditLogger.log_sync(f"AI resolution suggestion failed: {e}", level=logging.ERROR)
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = f"Error during resolution suggestion: {e}"
        return contradiction

    async def persist_contradiction(self, con: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]):
        """Inserts a single AI-detected contradiction as a node in Neo4j."""
        try:
            con_id = str(uuid.uuid4())
            con['id'] = con_id
            
            cypher = """
            CREATE (c:Contradiction {
                contradiction_id: $contradiction_id,
                detected_at: $detected_at,
                entity_a_id: $entity_a_id,
                entity_b_id: $entity_b_id,
                contradiction_type: $contradiction_type,
                severity: $severity,
                description: $description,
                evidence: $evidence,
                confidence: $confidence,
                scoring_reasoning: $scoring_reasoning,
                possible_resolutions: $possible_resolutions
            })
            RETURN c.contradiction_id AS id
            """
            
            params = {
                "contradiction_id": con_id,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "entity_a_id": entity_a.get("canon_id"),
                "entity_b_id": entity_b.get("canon_id"),
                "contradiction_type": con.get("type", "UNKNOWN"),
                "severity": con.get("severity", "LOW"),
                "description": con.get("description", "No description provided."),
                "evidence": json.dumps(con.get("evidence", {})),
                "confidence": con.get("confidence", 0.0),
                "scoring_reasoning": con.get("scoring_reasoning", ""),
                "possible_resolutions": json.dumps(con.get("possible_resolutions", []))
            }
            
            await self.db.execute(cypher, params)
            await AuditLogger.log(f"PERSIST: Stored contradiction {con_id} ({con.get('type')})")

            # Publish event for new contradiction
            event_data = {
                "type": "new_contradiction",
                "contradiction": {
                    "id": con_id,
                    "type": con.get("type", "UNKNOWN"),
                    "severity": con.get("severity", "LOW"),
                    "description": con.get("description", "No description provided."),
                    "entity_a_id": entity_a.get("canon_id"),
                    "entity_b_id": entity_b.get("canon_id"),
                    "detected_at": datetime.now(timezone.utc).isoformat()
                }
            }
            await broadcaster.publish("auditor_events", event_data)

        except Exception as e:
            await AuditLogger.log(f"Failed to persist contradiction: {e}", level=logging.ERROR)

    # --- 3. RULE-BASED METHODS (CYPHER CHECKS) ---

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
        await broadcaster.publish("auditor_events", {
            "type": "audit_progress",
            "message": "Rule-based audit complete.",
            "summary": summary
        })
        return results
    
    async def check_conflicting_birthplaces(self) -> List[Contradiction]:
        """Check for entities with multiple conflicting birthplace values stored as properties."""
        contradictions = []
        # In Neo4j, we look for nodes with a birthplace property that might have conflicts
        # This assumes birthplace is stored as a list or we check related Location nodes
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
        """Check for relationships pointing to non-existent entities.
        
        Note: In Neo4j, relationships cannot exist without both endpoints,
        so this check looks for dangling references in properties instead.
        """
        contradictions = []
        # In Neo4j, edges always connect existing nodes, so orphans aren't possible
        # in the traditional sense. However, we can check for nodes with reference
        # properties pointing to non-existent canon_ids.
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
                    evidence={
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
                    evidence={
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
        """Check for 2-hop and 3-hop circular relationships (A->B->A or A->B->C->A)."""
        await AuditLogger.log("Running circular relationship checks...")
        contradictions = []
        
        # 2-hop cycles: A -> B -> A
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
                    evidence={
                        "cycle_type": "2-hop", "entity_a": cycle['name_a'], "entity_b": cycle['name_b'],
                        "relationship_1": cycle['rel1_type'], "relationship_2": cycle['rel2_type']
                    }
                ))

        # 3-hop cycles: A -> B -> C -> A
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
                    evidence={
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
        """Check for date fields that don't match expected format (YYYY-MM-DD or YYYY)."""
        contradictions = []
        date_fields = ['birth_date', 'death_date', 'founded_date', 'occurred_date']
        
        for field in date_fields:
            cypher = f"""
            MATCH (e)
            WHERE e.{field} IS NOT NULL
            AND NOT e.{field} =~ '^\\\\d{{4}}-\\\\d{{2}}-\\\\d{{2}}$'
            AND NOT e.{field} =~ '^\\\\d{{4}}$'
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
    
    # ==========================================
    # SEMANTIC SUBMISSION AUDIT (NEW)
    # ==========================================
    
    # Entity extraction prompt (adapted from ingestor.py)
    ENTITY_EXTRACTION_PROMPT = """You are a Named Entity Extractor for a D&D Campaign lore system.
Analyze the following text and extract ONLY the names of entities mentioned.

**Entity Types to Look For:**
- Characters (NPCs, PCs, villains, heroes)
- Factions (Organizations, groups, clans, cults)
- Locations (Places, regions, buildings)
- Items (Weapons, artifacts, objects)
- Events (Battles, ceremonies, historical moments)
- Concepts (Magic types, curses, prophecies)

**Output Format:**
Return ONLY a JSON object with a single key "entities" containing a list of entity names.
Do NOT include markdown code fences.

Example:
{"entities": ["Vulture Clan", "Lead Corps", "Gyrocopter", "Smoker Legion"]}

TEXT:
"""

    CONTRADICTION_CHECK_PROMPT = """You are a Lore Consistency Checker for a D&D Campaign.

Your task is to determine if NEW SUBMISSION contradicts the ESTABLISHED TRUTH from the canonical knowledge graph.

**ESTABLISHED TRUTH (from Knowledge Graph):**
{graph_truth}

**NEW SUBMISSION (to be checked):**
{new_text}

**Instructions:**
1. Compare the claims in the NEW SUBMISSION against the ESTABLISHED TRUTH.
2. A contradiction exists if the new text makes claims that DIRECTLY CONFLICT with established facts.
3. New information that ADDS to existing lore without conflicting is NOT a contradiction.
4. Be specific about what conflicts.

**Output Format:**
Return ONLY a valid JSON object:
- If contradictions found: {{"status": "CONTRADICTION", "contradictions": [{{"claim": "what the new text says", "truth": "what the graph says", "severity": "HIGH/MEDIUM/LOW", "explanation": "why this conflicts"}}]}}
- If no contradictions: {{"status": "SAFE", "notes": "Brief explanation of why the submission is compatible"}}

CRITICAL: Return ONLY valid JSON. No markdown, no explanations outside the JSON."""

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from AI response with error recovery."""
        cleaned = text.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in response
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Return empty structure if all else fails
        return {"status": "ERROR", "message": "Failed to parse AI response"}

    async def _extract_entities_from_text(self, text: str) -> List[str]:
        """Extract entity names from text using Gemini."""
        await AuditLogger.log(f"Extracting entities from submission ({len(text)} chars)...")
        
        try:
            response = self.flash.generate_content(
                self.ENTITY_EXTRACTION_PROMPT + text,
                generation_config={"temperature": 0.1}
            )
            data = self._parse_json_response(response.text)
            entities = data.get("entities", [])
            await AuditLogger.log(f"Extracted {len(entities)} entities: {entities}")
            return entities
        except Exception as e:
            await AuditLogger.log(f"Entity extraction failed: {e}", level=logging.ERROR)
            return []

    async def _retrieve_graph_truth(self, entity_names: List[str]) -> Dict[str, Any]:
        """Query Neo4j for existing facts about the given entities."""
        if not entity_names:
            return {"entities": [], "relationships": []}
        
        await AuditLogger.log(f"Retrieving graph truth for: {entity_names}")
        
        # Query for entities and their relationships
        cypher = """
        MATCH (n)
        WHERE n.name IN $names
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n.name AS entity_name,
               labels(n)[0] AS entity_type,
               properties(n) AS entity_properties,
               collect(DISTINCT {
                   relationship: type(r),
                   target: m.name,
                   target_type: labels(m)[0],
                   direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
               }) AS relationships
        """
        
        records = await self.db.execute(cypher, {"names": entity_names})
        
        truth = {"entities": [], "relationships": []}
        
        if records:
            for record in records:
                entity_info = {
                    "name": record["entity_name"],
                    "type": record["entity_type"],
                    "properties": record["entity_properties"]
                }
                truth["entities"].append(entity_info)
                
                # Add relationships
                for rel in record["relationships"]:
                    if rel.get("target"):  # Filter out null relationships
                        truth["relationships"].append({
                            "from": record["entity_name"] if rel["direction"] == "outgoing" else rel["target"],
                            "to": rel["target"] if rel["direction"] == "outgoing" else record["entity_name"],
                            "type": rel["relationship"]
                        })
        
        await AuditLogger.log(f"Retrieved {len(truth['entities'])} entities, {len(truth['relationships'])} relationships")
        return truth

    def _format_graph_truth(self, truth: Dict[str, Any]) -> str:
        """Format graph truth into readable text for the AI prompt."""
        if not truth["entities"] and not truth["relationships"]:
            return "No existing information found in the knowledge graph for the mentioned entities."
        
        lines = []
        
        # Format entities
        for entity in truth["entities"]:
            props = entity.get("properties", {})
            desc = props.get("description", "")
            line = f"- {entity['name']} ({entity['type']})"
            if desc:
                line += f": {desc}"
            lines.append(line)
            
            # Add key properties
            for key, value in props.items():
                if key not in ["name", "description"] and value:
                    lines.append(f"    • {key}: {value}")
        
        # Format relationships
        if truth["relationships"]:
            lines.append("\nEstablished Relationships:")
            seen = set()
            for rel in truth["relationships"]:
                rel_str = f"  - {rel['from']} --[{rel['type']}]--> {rel['to']}"
                if rel_str not in seen:
                    lines.append(rel_str)
                    seen.add(rel_str)
        
        return "\n".join(lines)

    async def audit_submission(self, text: str) -> Dict[str, Any]:
        """
        Audit a new lore submission against the existing knowledge graph.
        
        Returns:
            {
                "status": "SAFE" | "CONTRADICTION" | "ERROR",
                "entities_checked": [...],
                "contradictions": [...] (if any),
                "notes": "..." (explanation)
            }
        """
        await AuditLogger.log("=" * 50)
        await AuditLogger.log("SEMANTIC AUDIT: Starting submission check")
        await AuditLogger.log("=" * 50)
        
        result = {
            "status": "SAFE",
            "entities_checked": [],
            "contradictions": [],
            "notes": ""
        }
        
        # Step 1: Extract entities from the submission
        entities = await self._extract_entities_from_text(text)
        result["entities_checked"] = entities
        
        if not entities:
            result["notes"] = "No recognizable entities found in submission. Cannot verify against graph."
            await AuditLogger.log("No entities found - skipping verification")
            return result
        
        # Step 2: Retrieve existing facts from the graph
        graph_truth = await self._retrieve_graph_truth(entities)
        
        if not graph_truth["entities"]:
            result["notes"] = f"Entities {entities} not found in knowledge graph. This appears to be new lore."
            await AuditLogger.log("Entities not in graph - treating as new lore")
            return result
        
        # Step 3: Format the graph truth for the prompt
        formatted_truth = self._format_graph_truth(graph_truth)
        
        # Step 4: Ask Gemini to compare
        await AuditLogger.log("Sending to Gemini for semantic comparison...")
        
        comparison_prompt = self.CONTRADICTION_CHECK_PROMPT.format(
            graph_truth=formatted_truth,
            new_text=text
        )
        
        try:
            response = self.pro.generate_content(
                comparison_prompt,
                generation_config={"temperature": 0.1}
            )
            
            comparison_result = self._parse_json_response(response.text)
            
            result["status"] = comparison_result.get("status", "ERROR")
            result["contradictions"] = comparison_result.get("contradictions", [])
            result["notes"] = comparison_result.get("notes", comparison_result.get("message", ""))
            
            if result["status"] == "CONTRADICTION":
                await AuditLogger.log(f"🚨 CONTRADICTIONS FOUND: {len(result['contradictions'])}")
                for c in result["contradictions"]:
                    await AuditLogger.log(f"  - {c.get('explanation', 'No explanation')}")
            else:
                await AuditLogger.log(f"✅ Submission is SAFE: {result['notes']}")
                
        except Exception as e:
            await AuditLogger.log(f"Semantic comparison failed: {e}", level=logging.ERROR)
            result["status"] = "ERROR"
            result["notes"] = f"AI comparison failed: {str(e)}"
        
        return result

    def review(self, record: dict) -> dict:
        """
        Placeholder review method for AuditorAgent.
        Simulates contradiction analysis and returns a status recommendation.
        """
        AuditLogger.log_sync(f"AuditorAgent reviewing contradiction: {record.get('contradiction_id')}")
        try:
            description = record.get("description", "").lower()
            resolved = "test" in description or "example" in description
            AuditLogger.log_sync(f"Review decision -> resolved={resolved}")
            return {"resolved": resolved}
        except Exception as e:
            
            AuditLogger.log_sync(f"AuditorAgent.review failed: {e}", level=logging.ERROR)
            return {"resolved": False, "error": str(e)}
