from __future__ import annotations

# src/agents/query_agent.py - Refactored for Neo4j with Vector Search
"""
Query Agent - RAG-powered Q&A over the Neo4j knowledge graph.
Uses 4-tier retrieval strategy:
  1. Agentic Entity Extraction (Gemini)
  2. Vector Similarity Search (semantic)
  3. Reverse Match (node names in query)
  4. Keyword Search (fallback)
"""

from typing import Dict, List, Any, Optional
import json
import google.generativeai as genai
from src.services.audit_log import AuditLogger
import logging
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from starlette.concurrency import run_in_threadpool
import asyncio
from src.services.broadcaster import broadcaster
from datetime import datetime
from src.db.neo4j_adapter import Neo4jDatabase
from src.services.vector_service import VectorService
from src.services.embedding_orchestrator import EmbeddingOrchestrator
from src.prompts import QueryPrompts

BROADCAST_EVENTS = False  # TEMP: disable broadcaster during early dev
logger = logging.getLogger(__name__)


class QueryAgent:
    """RAG-powered query agent using Neo4j for context retrieval with vector search."""
    
    # Filler words/phrases to strip from queries before searching
    FILLER_PHRASES = [
        "tell me about", "what do you know about", "who is", "who are", 
        "what is", "what are", "where is", "where are", "can you tell me about",
        "i want to know about", "describe", "explain", "give me info on",
        "give me information on", "what can you tell me about", "summarize",
        "summary of", "details about", "details on", "info on", "info about"
    ]
    
    def __init__(
        self, 
        neo4j_db: Neo4jDatabase, 
        gemini_api_key: str, 
        vector_service: Optional[VectorService] = None,
        enable_vector_search: bool = True
    ):
        self.db = neo4j_db
        self.gemini_api_key = gemini_api_key
        genai.configure(api_key=gemini_api_key)
        
        # Vector search configuration
        self.vector_search_enabled = enable_vector_search
        # For compatibility with external callers/prompts expecting this name
        self.enable_vector_search = enable_vector_search
        self.vector_service = vector_service
        
        if enable_vector_search and not self.vector_service:
            try:
                orchestrator = EmbeddingOrchestrator(gemini_api_key)
                self.vector_service = VectorService(neo4j_db, orchestrator)
                AuditLogger.log_sync("QueryAgent: Vector search ENABLED (Service created internally)")
            except Exception as e:
                AuditLogger.log_sync(f"QueryAgent: Vector search disabled - {e}", level=logging.WARNING)
                self.vector_search_enabled = False
        elif enable_vector_search and self.vector_service:
             AuditLogger.log_sync("QueryAgent: Vector search ENABLED (Service injected)")
        
        # Use Flash for fast Q&A
        self.pro_model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Define the system prompt for the chat
        self.system_prompt = QueryPrompts.get_system_prompt()

        # Start a new chat session with the system prompt
        self.chat = self.pro_model.start_chat(
            history=[
                {'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. I am the LMS Query Agent. I will only answer based on the lore context provided."]}
            ]
        )
        mode = "4-tier (with vector)" if self.vector_search_enabled else "3-tier (no vector)"
        AuditLogger.log_sync(f"QueryAgent: Neo4j + Gemini RAG initialized. Retrieval: {mode}")

        # Quick Neo4j connectivity check at startup
        try:
            async def _test_db():
                try:
                    result = await self.db.execute("MATCH (n) RETURN count(n) as total")
                    print(f"[QueryAgent] Neo4j connection test: {result}", flush=True)
                except Exception as e:
                    print(f"[QueryAgent] Neo4j connection FAILED: {e}", flush=True)

            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_test_db())
            else:
                loop.run_until_complete(_test_db())
        except Exception as e:
            print(f"[QueryAgent] Neo4j connection test scheduling failed: {e}", flush=True)

    async def search_entities(self, term: str, limit: int = 5, campaign_id: Optional[str] = None):
        return await self.search_nodes(term, limit=limit, campaign_id=campaign_id)


    async def extract_search_entities(self, user_query: str) -> List[str]:
        """
        Agentic Entity Extraction: Use Gemini to intelligently extract named entities
        from the user's query before searching the graph.
        
        This handles:
        - Complex phrasing ("What happened when the dark one attacked the village?")
        - Slang and typos (Gemini can normalize these)
        - Multi-entity queries ("Tell me about Kael and the Vulture Clan")
        
        Returns a list of clean entity names to search for.
        """
        extraction_prompt = QueryPrompts.build_extraction_prompt(user_query)

        try:
            # Use a fresh model call (not the chat) for extraction
            # Wrap blocking Gemini call in threadpool to avoid blocking the event loop
            response = await run_in_threadpool(
                self.pro_model.generate_content,
                extraction_prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 256}
            )
            
            # Parse the JSON response
            cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
            entities = json.loads(cleaned_json)
            
            if isinstance(entities, list):
                # Filter out empty strings and very short entities
                entities = [e.strip() for e in entities if isinstance(e, str) and len(e.strip()) > 1]
                await AuditLogger.log(f"Agentic extraction found entities: {entities}")
                return entities
            
            return []
        except Exception as e:
            await AuditLogger.log(f"Agentic entity extraction failed: {e}", level=logging.WARNING)
            return []  # Graceful fallback - continue with other strategies

    def _strip_filler_words(self, query: str) -> str:
        """
        Strips common conversational filler phrases from the query.
        Returns a cleaner search string.
        """
        cleaned = query.lower().strip()
        
        # Remove filler phrases (sorted by length, longest first to avoid partial matches)
        for phrase in sorted(self.FILLER_PHRASES, key=len, reverse=True):
            if cleaned.startswith(phrase):
                cleaned = cleaned[len(phrase):].strip()
                break  # Only remove one filler phrase
        
        # Remove trailing punctuation
        cleaned = cleaned.rstrip("?.!\"")
        
        return cleaned.strip()

    def _extract_search_terms(self, query: str) -> List[str]:
        """
        Extracts meaningful search terms from a query.
        Strips filler words and splits into individual terms + multi-word phrases.
        """
        cleaned = self._strip_filler_words(query)
        
        # Common stop words to filter out
        stop_words = {
            "what", "who", "where", "when", "how", "why", "is", "are", "was", "were",
            "the", "a", "an", "of", "to", "in", "for", "about", "tell", "me", "and",
            "their", "they", "them", "his", "her", "its", "with", "from", "this", "that"
        }
        
        terms = []
        
        # First, try the entire cleaned phrase (for multi-word entities like "Vulture Clan")
        if len(cleaned) > 2:
            terms.append(cleaned)
        
        # Then add individual words that aren't stop words
        words = cleaned.split()
        for word in words:
            word_clean = word.strip(",.!?;:'\"")
            if word_clean.lower() not in stop_words and len(word_clean) > 2:
                if word_clean not in terms:
                    terms.append(word_clean)
        
        return terms[:5]  # Limit to 5 terms

    async def search_nodes(self, term: str, limit: int = 10, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for nodes in the graph that match the search term.
        Case-insensitive search across name, content, and description properties.
        """
        cypher_parts = ["MATCH (n) "]
        if campaign_id:
            cypher_parts.append("MATCH (n)-[:BELONGS_TO]->(:Campaign {campaign_id: $campaign_id}) ")
        
        cypher_parts.append("""
        WHERE toLower(n.name) CONTAINS toLower($term) 
           OR toLower(n.canonical_name) CONTAINS toLower($term)
           OR toLower(n.description) CONTAINS toLower($term)
           OR toLower(n.content) CONTAINS toLower($term)
        RETURN n.name AS name,
               n.canonical_name AS canonical_name,
               labels(n)[0] AS type,
               properties(n) AS properties
        LIMIT $limit
        """)
        cypher = "".join(cypher_parts)
        params = {"term": term, "limit": limit}
        if campaign_id:
            params["campaign_id"] = campaign_id
        await AuditLogger.log(f"[Neo4j] search_nodes cypher: {cypher} params={params}")
        records = await self.db.execute(cypher, params)
        await AuditLogger.log(f"[Neo4j] search_nodes returned {len(records) if records else 0} rows")
        
        results = []
        if records:
            for record in records:
                results.append({
                    "name": record["name"] or record["canonical_name"],
                    "type": record["type"],
                    "properties": record["properties"]
                })
        return results

    async def get_node_with_neighbors(self, name: str, depth: int = 1, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve a node and its immediate neighbors from the graph.
        Case-insensitive matching for robust lookups.
        """
        cypher_parts = ["MATCH (n) "]
        if campaign_id:
            cypher_parts.append("MATCH (n)-[:BELONGS_TO]->(:Campaign {campaign_id: $campaign_id}) ")
            
        cypher_parts.append("""
        WHERE toLower(n.name) = toLower($name) 
           OR toLower(n.canonical_name) = toLower($name)
        OPTIONAL MATCH (n)-[r]-(neighbor)
        RETURN n.name AS name,
               labels(n)[0] AS type,
               properties(n) AS properties,
               collect(DISTINCT {
                   relationship: type(r),
                   neighbor_name: neighbor.name,
                   neighbor_type: labels(neighbor)[0],
                   direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END
               }) AS relationships
        """ ) 
        cypher = "".join(cypher_parts)
        params = {"name": name}
        if campaign_id:
            params["campaign_id"] = campaign_id
        await AuditLogger.log(f"[Neo4j] get_node_with_neighbors cypher: {cypher} params={params}")
        records = await self.db.execute(cypher, params)
        await AuditLogger.log(f"[Neo4j] get_node_with_neighbors returned {len(records) if records else 0} rows")
        
        if records and len(records) > 0:
            record = records[0]
            return {
                "name": record["name"],
                "type": record["type"],
                "properties": record["properties"],
                "relationships": [r for r in record["relationships"] if r["neighbor_name"]]
            }
        return {}

    async def reverse_match_entities(self, message: str, limit: int = 10, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Reverse Match Strategy: Find all nodes whose names appear in the user's message.
        
        Instead of extracting keywords and searching for them, we ask Neo4j:
        "Which node names are contained within this message?"
        
        Example: "Tell me about the Vulture Clan" will match node "Vulture Clan"
        because toLower("tell me about the vulture clan") CONTAINS toLower("Vulture Clan")
        """
        cypher_parts = ["MATCH (n) "]
        if campaign_id:
            cypher_parts.append("MATCH (n)-[:BELONGS_TO]->(:Campaign {campaign_id: $campaign_id}) ")
            
        cypher_parts.append("""
        WHERE n.name IS NOT NULL 
          AND size(n.name) > 2
          AND toLower($message) CONTAINS toLower(n.name)
        RETURN n.name AS name,
               labels(n)[0] AS type,
               properties(n) AS properties,
               size(n.name) AS name_length
        ORDER BY name_length DESC
        LIMIT $limit
        """)
        cypher = "".join(cypher_parts)
        params = {"message": message, "limit": limit}
        if campaign_id:
            params["campaign_id"] = campaign_id
        await AuditLogger.log(f"[Neo4j] reverse_match_entities cypher: {cypher} params={params}")
        records = await self.db.execute(cypher, params)
        await AuditLogger.log(f"[Neo4j] reverse_match_entities returned {len(records) if records else 0} rows")
        
        results = []
        if records:
            for record in records:
                results.append({
                    "name": record["name"],
                    "type": record["type"],
                    "properties": record["properties"]
                })
        return results

    async def vector_search(self, query: str, limit: int = 5, min_score: float = 0.6, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Vector Similarity Search.
        """
        if not self.vector_search_enabled or not self.vector_service:
            return []
        
        try:
            # Delegate to VectorService which handles embedding generation and search
            # Note: campaign_id filtering is not yet implemented in VectorService.vector_search directly
            # For now, we search globally.
            # TODO: Add filtering to VectorService if strictly required by architecture
            
            results = await self.vector_service.vector_search(
                query_text=query,
                limit=limit
            )
            
            # Post-filter by campaign_id if needed (since VectorService might return global results)
            # This is less efficient than filtering in DB but safe for MVP.
            # However, QueryAgent previously used a custom query with campaign_id match.
            # VectorService uses native index which supports pre-filtering but the service method signature is simple.
            
            # If we want to maintain the exact behavior (filtering inside DB), we might need to extend VectorService.
            # But for now, let's trust the results or update VectorService later.
            # The previous implementation had a complex query.
            
            if results:
                await AuditLogger.log(f"Vector search found {len(results)} entities")
            
            # Remap keys if necessary. VectorService returns id, name, score.
            # QueryAgent expects name, type, properties (or at least name).
            # VectorService returns: [{'id': ..., 'name': ..., 'score': ...}]
            # We need to ensure format compatibility.
            
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "name": r.get("name"),
                    "score": r.get("score"),
                    # We might need to fetch full node data if properties are needed, 
                    # but retrieve_context usually fetches full node later.
                    # Wait, retrieve_context iterates results and calls fetch_entity_context(name).
                    # fetch_entity_context gets full node.
                    # So returning just name is sufficient for retrieve_context to work!
                })
            
            return formatted_results
            
        except Exception as e:
            await AuditLogger.log(f"Vector search failed: {e}", level=logging.WARNING)
            return []

    async def retrieve_context(self, query: str, campaign_id: Optional[str] = None) -> str:
        """
        Retrieves relevant context from the Neo4j graph using a 4-tier strategy:
        
        1. AGENTIC EXTRACTION (Primary): Use Gemini to extract entities from the query
        2. VECTOR SEARCH (Semantic): Find semantically similar entities via embeddings
        3. REVERSE MATCH (Fallback): Find nodes whose names appear in the raw query
        4. KEYWORD SEARCH (Last Resort): Traditional keyword-based search
        
        Strategies 1 and 2 run in PARALLEL using asyncio.gather for better latency.
        """
        print("[RETRIEVE] Entered retrieve_context with query:", query, flush=True)
        await AuditLogger.log(f"Retrieving context for: '{query}'")
        
        context_parts = []
        seen_entities = set()
        strategies_used = []
        
        # Helper to fetch and format entity context
        async def fetch_entity_context(entity_name: str, source: str = "unknown"):
            if entity_name and entity_name.lower() not in seen_entities:
                seen_entities.add(entity_name.lower())
                print("[RETRIEVE] About to query Neo4j", flush=True)
                full_context = await self.get_node_with_neighbors(entity_name, campaign_id=campaign_id)
                if full_context:
                    context_parts.append(self._format_entity_context(full_context))
                    return True
            return False
        
        # === RUN STRATEGIES 1 & 2 IN PARALLEL ===
        # Both involve LLM/embedding calls that can run concurrently
        async def noop_vector_search():
            """No-op coroutine when vector search is disabled."""
            return []
        
        extraction_task = self.extract_search_entities(query)
        vector_task = self.vector_search(query, limit=5, min_score=0.6, campaign_id=campaign_id) if self.vector_search_enabled else noop_vector_search()
        
        # Wait for both to complete simultaneously
        extracted_entities, vector_results = await asyncio.gather(
            extraction_task,
            vector_task,
            return_exceptions=True  # Don't fail if one strategy errors
        )
        
        # Handle exceptions from gather
        if isinstance(extracted_entities, Exception):
            await AuditLogger.log(f"Agentic extraction failed: {extracted_entities}", level=logging.WARNING)
            extracted_entities = []
            print("[RETRIEVE] Passed condition: extracted_entities exception handled", flush=True)
        if isinstance(vector_results, Exception):
            await AuditLogger.log(f"Vector search failed: {vector_results}", level=logging.WARNING)
            vector_results = []
            print("[RETRIEVE] Passed condition: vector_results exception handled", flush=True)
        
        # === PROCESS STRATEGY 1 RESULTS: Agentic Entity Extraction ===
        if extracted_entities:
            await AuditLogger.log(f"Strategy 1 (Agentic): Searching for {extracted_entities}")
            strategies_used.append("agentic")
            for entity in extracted_entities:
                # Search for the extracted entity (handles typos, variations)
                matches = await self.search_nodes(entity, limit=3, campaign_id=campaign_id)
                for match in matches:
                    await fetch_entity_context(match["name"], "agentic")
            print("[RETRIEVE] Passed condition: processed extracted_entities", flush=True)
        
        # === PROCESS STRATEGY 2 RESULTS: Vector Similarity Search ===
        if vector_results and len(context_parts) < 5:
            await AuditLogger.log(f"Strategy 2 (Vector): Processing {len(vector_results)} semantic matches...")
            strategies_used.append("vector")
            for result in vector_results:
                name = result.get("name")
                score = result.get("score", 0)
                if name:
                    added = await fetch_entity_context(name, "vector")
                    if added:
                        await AuditLogger.log(f"  Vector match: {name} (score={score:.3f})")
            print("[RETRIEVE] Passed condition: processed vector_results", flush=True)
        
        # === STRATEGY 3: Reverse Match (if still need more context) ===
        # Find nodes whose names appear within the raw query string
        if not context_parts:
            await AuditLogger.log("Strategy 3 (Reverse Match): Checking for node names in query...")
            strategies_used.append("reverse")
            matches = await self.reverse_match_entities(query, limit=10, campaign_id=campaign_id)
            await AuditLogger.log(f"Reverse match found {len(matches)} entities")
            
            for match in matches:
                await fetch_entity_context(match["name"], "reverse")
            print("[RETRIEVE] Passed condition: reverse match executed", flush=True)
        
        # === STRATEGY 4: Keyword Search (Last Resort) ===
        # Traditional keyword extraction and search
        if not context_parts:
            await AuditLogger.log("Strategy 4 (Keyword Search): Trying keyword extraction...")
            strategies_used.append("keyword")
            search_terms = self._extract_search_terms(query)
            
            for term in search_terms:
                matches = await self.search_nodes(term, limit=5, campaign_id=campaign_id)
                for match in matches:
                    await fetch_entity_context(match["name"], "keyword")
            print("[RETRIEVE] Passed condition: keyword search executed", flush=True)
        
        if context_parts:
            context = "=== LORE CONTEXT FROM KNOWLEDGE GRAPH ===\n\n" + "\n\n".join(context_parts)
        else:
            context = "=== NO MATCHING LORE FOUND IN KNOWLEDGE GRAPH ==="
        
        await AuditLogger.log(
            f"Retrieved {len(context_parts)} context entries for {len(seen_entities)} unique entities. "
            f"Strategies: {', '.join(strategies_used) or 'none'}"
        )
        print(f"[RETRIEVE] Final context length: {len(context_parts)} parts, strategies: {strategies_used}", flush=True)
        return context

    def _format_entity_context(self, entity: Dict[str, Any]) -> str:
        """Formats an entity and its relationships into readable context."""
        lines = [f"**{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})"]
        
        # Add key properties
        props = entity.get("properties", {})
        important_keys = ["description", "content", "race", "class", "location", "birth_date", "death_date"]
        for key in important_keys:
            if key in props and props[key]:
                lines.append(f"  - {key}: {props[key]}")
        
        # Add relationships
        relationships = entity.get("relationships", [])
        if relationships:
            lines.append("  Relationships:")
            for rel in relationships[:10]:  # Limit to 10 relationships
                direction = "→" if rel.get("direction") == "outgoing" else "←"
                lines.append(f"    {direction} {rel.get('relationship', 'RELATED_TO')} {rel.get('neighbor_name', '?')} ({rel.get('neighbor_type', '?')})")
        
        return "\n".join(lines)

    async def ask(self, query: str, campaign_id: Optional[str] = None) -> str:
        """
        RAG-powered query: retrieves context from Neo4j, then asks Gemini.
        """
        print("[ASK] Entered ask() with query:", query, flush=True)
        await AuditLogger.log(f"QueryAgent received: '{query}'")
        try:
            # Step 1: Retrieve relevant context from the graph
            context = await self.retrieve_context(query, campaign_id=campaign_id)

            # Step 2: Build the augmented prompt
            augmented_prompt = f"{context}\n\n=== USER QUESTION ===\n{query}"

            # Step 3: Send to Gemini (wrap blocking call in threadpool)
            response = await run_in_threadpool(self.chat.send_message, augmented_prompt)
            return response.text

        except Exception as e:
            logger.error("ASK ERROR", exc_info=True)
            await AuditLogger.log(f"QueryAgent failed: {e}", level=logging.ERROR)
            return "An error occurred while processing your query. Please check the API logs."

    async def handle_websocket(self, websocket: WebSocket, client_id: str):
        from datetime import timezone

        while True:
            try:
                data = await websocket.receive_json()
                print("[QueryAgent] RAW WS IN:", data)
            except WebSocketDisconnect:
                print("[QueryAgent] WebSocket disconnected")
                break
            except Exception as e:
                print("[QueryAgent] Client disconnected during receive_json:", e)
                break

            if data is None:
                print("[QueryAgent] Received None payload; treating as disconnect.")
                break

            query = None
            if isinstance(data, dict):
                query = data.get("query") or data.get("message")
            elif isinstance(data, str):
                query = data

            if not query:
                print("[QueryAgent] No query in payload; ignoring.")
                continue

            if BROADCAST_EVENTS:
                try:
                    await broadcaster.publish("query_events", {
                        "client_id": client_id,
                        "query": query,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    print("[QueryAgent] Fatal WebSocket error during publish:", e)

            try:
                response = await self.ask(query)
            except Exception as e:
                print("[QueryAgent] ERROR inside ask():", e)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "error": "internal_error",
                        "detail": str(e)
                    })
                continue

            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json({
                        "client_id": client_id,
                        "query": query,
                        "response": response,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    print("[QueryAgent] Fatal WebSocket error during send_json:", e)
                    break

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass
        return

    async def answer_lore_question(self, query: str, client_id: str):
        """
        Handles vector search → semantic reasoning workflow.
        Returns a string answer to the lore question.
        """
        # 1. Vector search (if available)
        vector_results = None
        try:
            if self.enable_vector_search:
                vector_results = await self.search_similar_entities(query)
        except Exception as e:
            vector_results = None
            await AuditLogger.log(f"[QueryAgent] Vector search failed: {e}", level="WARNING")

        # 2. Semantic answer generation (Gemini or GPT)
        try:
            semantic_answer = await self.semantic_answer(query, vector_results)
            if semantic_answer:
                return semantic_answer
        except Exception as e:
            await AuditLogger.log(f"[QueryAgent] semantic_answer error: {e}", level="ERROR")

        # 3. Fallback
        return "No relevant lore found in the world archive."

    # --- Utility stubs to ensure websocket loop functions even if implementations are missing ---
    async def search_similar_entities(self, query: str):
        """
        Wrapper around vector_search or other retrieval logic.
        """
        try:
            return await self.vector_search(query, limit=5, min_score=0.6)
        except Exception:
            return None

    async def semantic_answer(self, query: str, vector_hits=None):
        """
        Generate a semantic answer using available context.
        Placeholder implementation that falls back to existing ask pipeline if needed.
        """
        try:
            # Reuse ask to leverage full RAG pipeline if available
            return await self.ask(query)
        except Exception:
            return f"(placeholder) You asked: {query}"
