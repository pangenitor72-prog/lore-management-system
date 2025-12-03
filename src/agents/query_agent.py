# src/agents/query_agent.py - Refactored for Neo4j with Vector Search
"""
Query Agent - RAG-powered Q&A over the Neo4j knowledge graph.
Uses 4-tier retrieval strategy:
  1. Agentic Entity Extraction (Gemini)
  2. Vector Similarity Search (semantic)
  3. Reverse Match (node names in query)
  4. Keyword Search (fallback)
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import json
import google.generativeai as genai
from src.services.audit_log import AuditLogger
import logging
from fastapi import WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
import asyncio
from src.services.broadcaster import broadcaster
from datetime import datetime
from src.db.neo4j_adapter import Neo4jDatabase
from src.services.embedding_service import EmbeddingService
from src.prompts import QueryPrompts


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
    
    def __init__(self, neo4j_db: Neo4jDatabase, gemini_api_key: str, enable_vector_search: bool = True):
        self.db = neo4j_db
        self.gemini_api_key = gemini_api_key
        genai.configure(api_key=gemini_api_key)
        
        # Vector search configuration
        self.vector_search_enabled = enable_vector_search
        self.embedding_service: Optional[EmbeddingService] = None
        
        if enable_vector_search:
            try:
                self.embedding_service = EmbeddingService(gemini_api_key)
                AuditLogger.log_sync("QueryAgent: Vector search ENABLED")
            except Exception as e:
                AuditLogger.log_sync(f"QueryAgent: Vector search disabled - {e}", level=logging.WARNING)
                self.vector_search_enabled = False
        
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
        records = await self.db.execute(cypher, params)
        
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
        records = await self.db.execute(cypher, params)
        
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
        records = await self.db.execute(cypher, params)
        
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
        if not self.vector_search_enabled or not self.embedding_service:
            return []
        
        try:
            # Generate query embedding (use RETRIEVAL_QUERY for optimal matching)
            query_embedding = await run_in_threadpool(
                self.embedding_service.embed_query, 
                query
            )
            
            if not query_embedding:
                await AuditLogger.log("Vector search: Failed to embed query", level=logging.WARNING)
                return []
            
            # Search Neo4j vector index
            if campaign_id:
                cypher_parts = []
                cypher_parts.append("""
                CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
                YIELD node, score
                MATCH (node)-[:BELONGS_TO]->(:Campaign {campaign_id: $campaign_id})
                WHERE score >= $min_score
                RETURN node.canon_id AS canon_id,
                       node.name AS name,
                       labels(node)[0] AS type,
                       node.description AS description,
                       properties(node) AS properties,
                       score
                ORDER BY score DESC
                """ ) 
                cypher = "".join(cypher_parts)
                params = {
                    "index_name": "entity_embeddings",
                    "limit": limit,
                    "embedding": query_embedding,
                    "min_score": min_score,
                    "campaign_id": campaign_id
                }
                records = await self.db.execute(cypher, params)
                results = [dict(r) for r in records] if records else []
            else:
                results = await self.db.vector_search(
                    query_embedding=query_embedding,
                    limit=limit,
                    min_score=min_score
                )
            
            if results:
                await AuditLogger.log(f"Vector search found {len(results)} entities (min_score={min_score})")
            
            return results
            
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
        await AuditLogger.log(f"Retrieving context for: '{query}'")
        
        context_parts = []
        seen_entities = set()
        strategies_used = []
        
        # Helper to fetch and format entity context
        async def fetch_entity_context(entity_name: str, source: str = "unknown"):
            if entity_name and entity_name.lower() not in seen_entities:
                seen_entities.add(entity_name.lower())
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
        if isinstance(vector_results, Exception):
            await AuditLogger.log(f"Vector search failed: {vector_results}", level=logging.WARNING)
            vector_results = []
        
        # === PROCESS STRATEGY 1 RESULTS: Agentic Entity Extraction ===
        if extracted_entities:
            await AuditLogger.log(f"Strategy 1 (Agentic): Searching for {extracted_entities}")
            strategies_used.append("agentic")
            for entity in extracted_entities:
                # Search for the extracted entity (handles typos, variations)
                matches = await self.search_nodes(entity, limit=3, campaign_id=campaign_id)
                for match in matches:
                    await fetch_entity_context(match["name"], "agentic")
        
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
        
        # === STRATEGY 3: Reverse Match (if still need more context) ===
        # Find nodes whose names appear within the raw query string
        if not context_parts:
            await AuditLogger.log("Strategy 3 (Reverse Match): Checking for node names in query...")
            strategies_used.append("reverse")
            matches = await self.reverse_match_entities(query, limit=10, campaign_id=campaign_id)
            await AuditLogger.log(f"Reverse match found {len(matches)} entities")
            
            for match in matches:
                await fetch_entity_context(match["name"], "reverse")
        
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
        
        if context_parts:
            context = "=== LORE CONTEXT FROM KNOWLEDGE GRAPH ===\n\n" + "\n\n".join(context_parts)
        else:
            context = "=== NO MATCHING LORE FOUND IN KNOWLEDGE GRAPH ==="
        
        await AuditLogger.log(
            f"Retrieved {len(context_parts)} context entries for {len(seen_entities)} unique entities. "
            f"Strategies: {', '.join(strategies_used) or 'none'}"
        )
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
            await AuditLogger.log(f"QueryAgent failed: {e}", level=logging.ERROR)
            return "An error occurred while processing your query. Please check the API logs."

    # --- HANDLER REQUIRED BY API.PY --- 
    async def handle_websocket(self, websocket: WebSocket, client_id: str):
        """
        Handles the WebSocket connection for a single client.
        Now uses async RAG-powered ask method.
        """
        await websocket.accept()
        await AuditLogger.log(f"Client {client_id} connected.")
        
        try:
            while True:
                # Wait for a message from the client
                query = await websocket.receive_text()
                
                # Use the async ask method (now with RAG)
                response = await self.ask(query)
                
                # Publish event for query completion
                event_data = {
                    "type": "query_completed",
                    "query": query,
                    "response_snippet": response[:200] + "..." if len(response) > 200 else response,
                    "timestamp": datetime.now().isoformat()
                }
                asyncio.create_task(broadcaster.publish("query_events", event_data))

                # Send the response back to the client
                await websocket.send_text(response)
                
        except WebSocketDisconnect:
            await AuditLogger.log(f"Client {client_id} disconnected.")
        except Exception as e:
            await AuditLogger.log(f"Error for client {client_id}: {e}", level=logging.ERROR)
            await websocket.close(code=1011, reason="Internal error")