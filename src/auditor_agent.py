"""
Auditor Agent - Contradiction Detection System
Detects 9 types of logical and temporal contradictions in lore database (Rule-Based)
AND complex semantic contradictions (AI-Based).
"""

from __future__ import annotations
from starlette.concurrency import run_in_threadpool
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timezone
import json
import re
import uuid
import logging
import sqlite3
import asyncio # For async operations
from .database import Database, db_session, get_db_connection # Import necessary db components
import google.generativeai as genai
from .broadcaster import broadcaster # Import the global broadcaster instance

logger = logging.getLogger("lms_auditor")

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
    """Runs systematic audits for contradictions in lore database."""

    def __init__(self, get_db_connection_func: Callable[[], sqlite3.Connection], gemini_api_key: str):
        self.get_db_connection = get_db_connection_func
        genai.configure(api_key=gemini_api_key) # Safe to call multiple times
        self.flash = genai.GenerativeModel("gemini-2.5-flash") # Standard model for fast detection
        self.pro = genai.GenerativeModel("gemini-2.5-pro")     # Standard model for complex reasoning (scoring/resolving)
        logger.info("AuditorAgent: Hybrid mode. DB and AI models initialized.")
    def detect_contradictions(self, entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Finds, Scores, and suggests Resolutions for AI-detected contradictions."""
        a_name, b_name = entity_a.get("name","?"), entity_b.get("name","?")
        logger.info(f"AI-DETECT: Comparing {a_name} vs {b_name}")
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
            logger.error(f"AI detection failed: {e}", exc_info=True)
            return []

    def _fetch_entities_sync(self, limit: int | None = None) -> List[Dict[str, Any]]:
        """Synchronously fetches all entities from the database."""
        logger.debug(f"Sync fetch starting.")
        conn = self.get_db_connection()
        try:
            entities = Database.fetch_all(conn, "SELECT * FROM entities")
        finally:
            conn.close()
        logger.debug(f"Sync fetch complete. {len(entities)} entities loaded.")
        return entities

    async def analyze_all_entities(self, limit:int|None=None) -> int:
        """Runs detect_contradictions across all entity pairs and persists findings."""
        logger.info("Batch AI scan start")
        
        entities = await run_in_threadpool(self._fetch_entities_sync, limit)

        if limit: entities = entities[:int(limit)]
        
        count = 0
        for i,a in enumerate(entities):
            for b in entities[i+1:]:
                if not self._should_compare(a,b): 
                    continue
                
                cons = self.detect_contradictions(a,b)
                
                for c in cons:
                    await self.persist_contradiction(c, a, b)
                    count += 1
                
        logger.info(f"Complete: {count} contradictions found and persisted.")
        await broadcaster.publish("auditor_events", {
            "type": "audit_progress",
            "message": f"AI audit complete. {count} contradictions found and persisted.",
            "total_contradictions_found": count
        })
        return count

    def _should_compare(self,a,b)->bool:
        """Logic to decide if two entities are worth an AI comparison."""
        try:
            if a.get("name","").lower()==b.get("name","").lower(): return True
            if a.get("type")==b.get("type"): return True
            q="""SELECT COUNT(*) as cnt FROM relationships
                 WHERE (from_canon_id=? AND to_canon_id=?) OR (from_canon_id=? AND to_canon_id=?)""" # Corrected column names
            
            conn = self.get_db_connection()
            try:
                r = Database.fetch_one(conn, q,(a["canon_id"],b["canon_id"],b["canon_id"],a["canon_id"]))
            finally:
                conn.close()
            return (r and (r.get("cnt") or r.get("count") or 0)>0)
        except Exception as e:
            logger.warning(f"_should_compare error: {e}", exc_info=True)
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
                    logger.debug("Failed to parse dict from LLM response for contradictions.")
                    return []
            return []
        try:
            arr=json.loads(m.group())
            return arr if isinstance(arr,list) else []
        except json.JSONDecodeError:
            logger.debug("Failed to parse list from LLM response for contradictions.")
            return []

    def _score_contradiction_confidence(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """Uses gemini-1.5-pro to assign a confidence score."""
        logger.info(f"AI-SCORE: Scoring contradiction: {contradiction.get('description', 'N/A')[:50]}...")
        
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
            logger.error(f"AI scoring failed: {e}", exc_info=True)
            contradiction["confidence"] = 0.0
            contradiction["scoring_reasoning"] = f"Error during scoring: {e}"
        return contradiction

    def _suggest_resolutions(self, contradiction: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]) -> Dict[str, Any]:
        """Uses gemini-1.5-pro to suggest resolutions."""
        if contradiction.get("confidence", 0.0) < 0.7:
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = "Confidence score too low to suggest resolution."
            return contradiction

        logger.info(f"AI-RESOLVE: Suggesting resolutions for: {contradiction.get('description', 'N/A')[:50]}...")
        
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
            logger.error(f"AI resolution suggestion failed: {e}", exc_info=True)
            contradiction["possible_resolutions"] = []
            contradiction["resolution_reasoning"] = f"Error during resolution suggestion: {e}"
        return contradiction

    def _persist_contradiction_sync(self, contradiction: Dict, entity_a: Dict, entity_b: Dict):
        logger.debug(f"Sync persist starting for {contradiction.get('id')}")
        conn = self.get_db_connection() # New connection for this thread
        try:
            con_id = str(uuid.uuid4())
            contradiction['id'] = con_id # Add id for return
            resolutions_json = json.dumps(contradiction.get("possible_resolutions", []))

            data = (
                con_id,
                datetime.now(timezone.utc).isoformat(),
                entity_a.get("canon_id"),
                entity_b.get("canon_id"),
                contradiction.get("type", "UNKNOWN"),
                contradiction.get("severity", "LOW"),
                contradiction.get("description", "No description provided."),
                json.dumps(contradiction.get("evidence", {})),
                contradiction.get("confidence", 0.0),
                contradiction.get("scoring_reasoning", ""),
                resolutions_json
            )

            sql = """
            INSERT INTO contradictions (
                contradiction_id, detected_at, entity_a_id, entity_b_id,
                contradiction_type, severity, description, evidence,
                confidence, scoring_reasoning, possible_resolutions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            Database.execute(conn, sql, data)
            conn.commit()
            logger.info(f"PERSIST: Stored contradiction {con_id} ({contradiction.get('type')})")

        except Exception as e:
            logger.error(f"Sync persist failed: {e}", exc_info=True)
            conn.rollback()
            raise
        finally:
            conn.close()
        return contradiction

    async def persist_contradiction(self, con: Dict[str, Any], entity_a: Dict[str, Any], entity_b: Dict[str, Any]):
        """Inserts a single AI-detected contradiction into the database."""
        try:
            persisted_con = await run_in_threadpool(self._persist_contradiction_sync, con, entity_a, entity_b)

            # Publish event for new contradiction
            event_data = {
                "type": "new_contradiction",
                "contradiction": {
                    "id": persisted_con.get("id"),
                    "type": persisted_con.get("type", "UNKNOWN"),
                    "severity": persisted_con.get("severity", "LOW"),
                    "description": persisted_con.get("description", "No description provided."),
                    "entity_a_id": entity_a.get("canon_id"),
                    "entity_b_id": entity_b.get("canon_id"),
                    "detected_at": datetime.now(timezone.utc).isoformat()
                }
            }
            await broadcaster.publish("auditor_events", event_data)

        except Exception as e:
            logger.error(f"Failed to persist contradiction: {e}", exc_info=True)

    # --- 3. RULE-BASED METHODS (SQL CHECKS) ---

    def _run_full_audit_sync(self) -> Dict[str, List[Dict]]:
        """Synchronously runs all RULE-BASED audit checks."""
        logger.info("Starting synchronous rule-based audit.")
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
        
        results["conflicting_birthplaces"] = [c.to_dict() for c in self.check_conflicting_birthplaces()]
        results["impossible_timelines"] = [c.to_dict() for c in self.check_impossible_timelines()]
        results["conflicting_memberships"] = [c.to_dict() for c in self.check_conflicting_memberships()]
        results["orphaned_relationships"] = [c.to_dict() for c in self.check_orphaned_relationships()]
        results["confidence_mismatches"] = [c.to_dict() for c in self.check_confidence_mismatches()]
        results["missing_required_fields"] = [c.to_dict() for c in self.check_missing_required_fields()]
        results["self_referential_relationships"] = [c.to_dict() for c in self.check_self_referential()]
        results["circular_relationships"] = [c.to_dict() for c in self.check_circular_relationships()]
        results["unparseable_dates"] = [c.to_dict() for c in self.check_unparseable_dates()]
        
        logger.info("Synchronous rule-based audit complete.")
        return results

    async def run_full_audit(self) -> Dict[str, List[Dict]]:
        """Asynchronously runs all RULE-BASED audit checks and publishes completion event."""
        
        results = await run_in_threadpool(self._run_full_audit_sync)
        
        summary = self.get_summary(results)
        await broadcaster.publish("auditor_events", {
            "type": "audit_progress",
            "message": "Rule-based audit complete.",
            "summary": summary
        })
        return results
    
    def check_conflicting_birthplaces(self) -> List[Contradiction]:
        """Check for entities with multiple conflicting birthplace values."""
        contradictions = []
        query = """
        SELECT 
            af1.canon_id, af1.field_value as birthplace1,
            af2.field_value as birthplace2, e.canonical_name
        FROM approved_fields af1
        JOIN approved_fields af2 ON af1.canon_id = af2.canon_id
        JOIN entities e ON af1.canon_id = e.canon_id
        WHERE af1.field_key = 'birthplace' AND af2.field_key = 'birthplace'
        AND af1.id < af2.id AND af1.field_value != af2.field_value
        """
        conn = self.get_db_connection()
        try:
            conflicts = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for conflict in conflicts:
            contradictions.append(Contradiction(
                contradiction_type="CONFLICTING_BIRTHPLACES", severity="HIGH",
                description=f"Entity '{conflict['canonical_name']}' has conflicting birthplace entries",
                entity_ids=[conflict['canon_id']],
                evidence={"birthplace1": conflict['birthplace1'], "birthplace2": conflict['birthplace2']}
            ))
        return contradictions
    
    def check_impossible_timelines(self) -> List[Contradiction]:
        """Check for entities with birth_date after death_date."""
        contradictions = []
        query = """
        SELECT 
            e.canon_id, e.canonical_name,
            birth.field_value as birth_date, death.field_value as death_date
        FROM entities e
        JOIN approved_fields birth ON e.canon_id = birth.canon_id AND birth.field_key = 'birth_date'
        JOIN approved_fields death ON e.canon_id = death.canon_id AND death.field_key = 'death_date'
        WHERE birth.field_value > death.field_value
        """
        conn = self.get_db_connection()
        try:
            impossibles = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for impossible in impossibles:
            contradictions.append(Contradiction(
                contradiction_type="IMPOSSIBLE_TIMELINE", severity="HIGH",
                description=f"Entity '{impossible['canonical_name']}' has death before birth",
                entity_ids=[impossible['canon_id']],
                evidence={"birth_date": impossible['birth_date'], "death_date": impossible['death_date']}
            ))
        return contradictions
    
    def check_conflicting_memberships(self) -> List[Contradiction]:
        """Check for entities with multiple PRIMARY_MEMBER_OF relationships."""
        contradictions = []
        query = """
        SELECT 
            r1.from_canon_id as entity_id, e.canonical_name,
            r1.to_canon_id as faction1_id, f1.canonical_name as faction1_name,
            r2.to_canon_id as faction2_id, f2.canonical_name as faction2_name
        FROM relationships r1
        JOIN relationships r2 ON r1.from_canon_id = r2.from_canon_id
        JOIN entities e ON r1.from_canon_id = e.canon_id
        JOIN entities f1 ON r1.to_canon_id = f1.canon_id
        JOIN entities f2 ON r2.to_canon_id = f2.canon_id
        WHERE r1.relationship_type = 'PRIMARY_MEMBER_OF'
        AND r2.relationship_type = 'PRIMARY_MEMBER_OF'
        AND r1.id < r2.id AND r1.to_canon_id != r2.to_canon_id
        """
        conn = self.get_db_connection()
        try:
            conflicts = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for conflict in conflicts:
            contradictions.append(Contradiction(
                contradiction_type="CONFLICTING_MEMBERSHIP", severity="MEDIUM",
                description=f"Entity '{conflict['canonical_name']}' has primary membership in multiple factions",
                entity_ids=[conflict['entity_id'], conflict['faction1_id'], conflict['faction2_id']],
                evidence={"faction1": conflict['faction1_name'], "faction2": conflict['faction2_name']}
            ))
        return contradictions
    
    def check_orphaned_relationships(self) -> List[Contradiction]:
        """Check for relationships pointing to non-existent entities."""
        contradictions = []
        query_from = """
        SELECT r.id, r.from_canon_id, r.relationship_type, r.to_canon_id
        FROM relationships r LEFT JOIN entities e ON r.from_canon_id = e.canon_id
        WHERE e.canon_id IS NULL
        """
        conn = self.get_db_connection()
        try:
            orphans_from = Database.fetch_all(conn, query_from)
        finally:
            conn.close()
        for orphan in orphans_from:
            contradictions.append(Contradiction(
                contradiction_type="ORPHANED_RELATIONSHIP", severity="HIGH",
                description="Relationship references non-existent entity (FROM side)",
                entity_ids=[],
                evidence={
                    "relationship_id": orphan['id'], "missing_entity_id": orphan['from_canon_id'],
                    "relationship_type": orphan['relationship_type']
                }
            ))
        
        query_to = """
        SELECT r.id, r.from_canon_id, r.relationship_type, r.to_canon_id
        FROM relationships r LEFT JOIN entities e ON r.to_canon_id = e.canon_id
        WHERE e.canon_id IS NULL
        """
        conn = self.get_db_connection()
        try:
            orphans_to = Database.fetch_all(conn, query_to)
        finally:
            conn.close()
        for orphan in orphans_to:
            contradictions.append(Contradiction(
                contradiction_type="ORPHANED_RELATIONSHIP", severity="HIGH",
                description="Relationship references non-existent entity (TO side)",
                entity_ids=[orphan['from_canon_id']],
                evidence={
                    "relationship_id": orphan['id'], "missing_entity_id": orphan['to_canon_id'],
                    "relationship_type": orphan['relationship_type']
                }
            ))
        return contradictions
    
    def check_confidence_mismatches(self) -> List[Contradiction]:
        """Check for UNCERTAIN/SPECULATIVE entities with CONFIRMED relationships."""
        contradictions = []
        query = """
        SELECT 
            e.canon_id, e.canonical_name, e.confidence_level as entity_confidence,
            r.id as relationship_id, r.relationship_type, r.confidence_level as relationship_confidence,
            e2.canonical_name as related_entity
        FROM entities e
        JOIN relationships r ON e.canon_id = r.from_canon_id
        JOIN entities e2 ON r.to_canon_id = e2.canon_id
        WHERE e.confidence_level IN ('UNCERTAIN', 'SPECULATIVE')
        AND r.confidence_level = 'CONFIRMED'
        """
        conn = self.get_db_connection()
        try:
            mismatches = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for mismatch in mismatches:
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
    
    def check_missing_required_fields(self) -> List[Contradiction]:
        """Check for Character entities missing required fields like 'race'."""
        contradictions = []
        query = """
        SELECT e.canon_id, e.canonical_name
        FROM entities e
        WHERE e.entity_type = 'Character'
        AND e.canon_id NOT IN (
            SELECT canon_id FROM approved_fields WHERE field_key = 'race'
        )
        """
        conn = self.get_db_connection()
        try:
            missing_race = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for entity in missing_race:
            contradictions.append(Contradiction(
                contradiction_type="MISSING_REQUIRED_FIELD", severity="LOW",
                description=f"Character '{entity['canonical_name']}' missing required field: race",
                entity_ids=[entity['canon_id']],
                evidence={"missing_field": "race"}
            ))
        return contradictions
    
    def check_self_referential(self) -> List[Contradiction]:
        """Check for relationships where FROM and TO are the same entity."""
        contradictions = []
        query = """
        SELECT r.id, r.from_canon_id, r.relationship_type, e.canonical_name
        FROM relationships r
        JOIN entities e ON r.from_canon_id = e.canon_id
        WHERE r.from_canon_id = r.to_canon_id
        """
        conn = self.get_db_connection()
        try:
            self_refs = Database.fetch_all(conn, query)
        finally:
            conn.close()
        for ref in self_refs:
            contradictions.append(Contradiction(
                contradiction_type="SELF_REFERENTIAL", severity="HIGH",
                description=f"Entity '{ref['canonical_name']}' has relationship to itself",
                entity_ids=[ref['from_canon_id']],
                evidence={"relationship_id": ref['id'], "relationship_type": ref['relationship_type']}
            ))
        return contradictions
    
    def check_circular_relationships(self) -> List[Contradiction]:
        """Check for 2-hop and 3-hop circular relationships (A->B->A or A->B->C->A)."""
        logger.info("Running circular relationship checks...")
        contradictions = []
        
        query_2hop = """
        SELECT DISTINCT
            r1.from_canon_id as entity_a, r1.to_canon_id as entity_b,
            e1.canonical_name as name_a, e2.canonical_name as name_b,
            r1.relationship_type as rel1_type, r2.relationship_type as rel2_type
        FROM relationships r1
        JOIN relationships r2 ON r1.to_canon_id = r2.from_canon_id
        JOIN entities e1 ON r1.from_canon_id = e1.canon_id
        JOIN entities e2 ON r1.to_canon_id = e2.canon_id
        WHERE r1.from_canon_id = r2.to_canon_id AND r1.from_canon_id < r1.to_canon_id
        """
        conn = self.get_db_connection()
        try:
            cycles_2 = Database.fetch_all(conn, query_2hop)
        finally:
            conn.close()
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

        query_3hop = """
        SELECT DISTINCT
            r1.from_canon_id as entity_a, r2.from_canon_id as entity_b, r3.from_canon_id as entity_c,
            e1.canonical_name as name_a, e2.canonical_name as name_b, e3.canonical_name as name_c,
            r1.relationship_type as rel1_type, r2.relationship_type as rel2_type, r3.relationship_type as rel3_type
        FROM relationships r1
        JOIN relationships r2 ON r1.to_canon_id = r2.from_canon_id
        JOIN relationships r3 ON r2.to_canon_id = r3.from_canon_id
        JOIN entities e1 ON r1.from_canon_id = e1.canon_id
        JOIN entities e2 ON r2.from_canon_id = e2.canon_id
        JOIN entities e3 ON r3.from_canon_id = e3.canon_id
        WHERE r1.from_canon_id = r3.to_canon_id 
        AND r1.from_canon_id != r2.from_canon_id
        AND r1.from_canon_id < r2.from_canon_id
        """
        conn = self.get_db_connection()
        try:
            cycles_3 = Database.fetch_all(conn, query_3hop)
        finally:
            conn.close()
        for cycle in cycles_3:
            is_valid_cycle = (cycle['entity_a'] < cycle['entity_b'] and cycle['entity_a'] < cycle['entity_c'])
            if is_valid_cycle:
                contradictions.append(Contradiction(
                    contradiction_type="CIRCULAR_RELATIONSHIP", severity="HIGH",
                    description=f"3-hop cycle detected: {cycle['name_a']} -> {cycle['name_b']} -> {cycle['name_c']} -> {cycle['name_a']}",
                    entity_ids=[cycle['entity_a'], cycle['entity_b'], cycle['entity_c']],
                    evidence={
                        "cycle_type": "3-hop", "entity_a": cycle['name_a'], "entity_b": cycle['name_b'], "entity_c": cycle['name_c'],
                        "relationships": [cycle['rel1_type'], cycle['rel2_type'], cycle['rel3_type']]
                    }
                ))
        logger.info(f"Circular checks complete. Found {len(contradictions)} cycles.")
        return contradictions
    
    def check_unparseable_dates(self) -> List[Contradiction]:
        """Check for date fields that don't match expected format (YYYY-MM-DD or YYYY)."""
        contradictions = []
        date_fields = ['birth_date', 'death_date', 'founded_date', 'occurred_date']
        for field in date_fields:
            query = f"""
            SELECT 
                af.canon_id, e.canonical_name, af.field_value as date_value
            FROM approved_fields af
            JOIN entities e ON af.canon_id = e.canon_id
            WHERE af.field_key = '{field}'
            AND af.field_value NOT LIKE '____-__-__'
            AND af.field_value NOT LIKE '____'
            AND LENGTH(af.field_value) > 0
            """
            conn = self.get_db_connection()
            try:
                bad_dates = Database.fetch_all(conn, query)
            finally:
                conn.close()
            for bad in bad_dates:
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
    
    def review(self, record: dict) -> dict:
        """
        Placeholder review method for AuditorAgent.
        Simulates contradiction analysis and returns a status recommendation.
        """
        logger.debug(f"AuditorAgent reviewing contradiction: {record.get('contradiction_id')}")
        try:
            description = record.get("description", "").lower()
            resolved = "test" in description or "example" in description
            logger.debug(f"Review decision -> resolved={resolved}")
            return {"resolved": resolved}
        except Exception as e:
            
            logger.error(f"AuditorAgent.review failed: {e}", exc_info=True)
            return {"resolved": False, "error": str(e)}
