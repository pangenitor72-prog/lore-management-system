# src/query_agent.py (COMPLETE, FINAL VERSION)
from __future__ import annotations
from typing import Dict, List, Any, Callable
import google.generativeai as genai
import logging
import sqlite3 # Import for type hinting Callable
from fastapi import WebSocket, WebSocketDisconnect # <-- ESSENTIAL IMPORT
from fastapi.concurrency import run_in_threadpool # For offloading blocking calls
import asyncio # For async operations
from .broadcaster import broadcaster # Import the global broadcaster instance
from datetime import datetime

logger = logging.getLogger("lms_query")

class QueryAgent:
    def __init__(self, get_db_connection_func: Callable[[], sqlite3.Connection], gemini_api_key: str): # Updated db parameter
        self.get_db_connection = get_db_connection_func # Store the connection function
        # Configure Gemini (safe to call again, as it's idempotent)
        genai.configure(api_key=gemini_api_key)

        # Use Pro for complex Q&A
        self.pro_model = genai.GenerativeModel("gemini-2.5-flash") # <-- FINAL MODEL FIX
        
        # Define the system prompt for the chat
        self.system_prompt = """
You are the "LMS Query Agent," an AI assistant for a 30-year-old tabletop Dungeon Master's (DM). 
Your sole purpose is to answer DM questions about the canonical campaign lore managed by this system.
You must adhere to the "Gospel Principle": You only report on existing lore.
If the answer is not in the lore, you must state "That information is not in the lore."

When answering, be:
1. **Sincere:** Direct and honest about the data.
2. **Intelligent:** Synthesize information, don't just list facts.
3. **Unvarnished:** Do not use flowery or evasive language. Get to the point.
"""
        # Start a new chat session with the system prompt
        self.chat = self.pro_model.start_chat(
            history=[
                {'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. I am the LMS Query Agent."]}
            ]
        )
        logger.info("QueryAgent: AI model and chat session initialized.")

    def ask(self, query: str) -> str:
        """
        Sends a user's query to the Gemini chat session and returns the text response.
        This is a BLOCKING call to the LLM.
        """
        logger.info(f"QueryAgent received: '{query}'")
        try:
            # We don't need to re-send the system prompt; the chat session is persistent
            response = self.chat.send_message(query)
            return response.text
        except Exception as e:
            logger.error(f"QueryAgent failed to get response: {e}", exc_info=True)
            return "An error occurred while processing your query. Please check the API logs."
            
    # --- HANDLER REQUIRED BY API.PY ---
    async def handle_websocket(self, websocket: WebSocket, client_id: str):
        """
        Handles the WebSocket connection for a single client (REQUIRED FOR PHASE IX DASHBOARD).
        """
        await websocket.accept()
        logger.info(f"Client {client_id} connected.")
        
        try:
            while True:
                # Wait for a message from the client
                query = await websocket.receive_text()
                
                # Use run_in_threadpool to offload the blocking 'ask' method (C1)
                response = await run_in_threadpool(self.ask, query)
                
                # Publish event for query completion
                event_data = {
                    "type": "query_completed",
                    "query": query,
                    "response_snippet": response[:200] + "..." if len(response) > 200 else response, # Snippet for brevity
                    "timestamp": datetime.now().isoformat()
                }
                asyncio.create_task(broadcaster.publish("query_events", event_data))

                # Send the response back to the client
                await websocket.send_text(response)
                
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected.")
        except Exception as e:
            logger.error(f"Error for client {client_id}: {e}", exc_info=True)
            await websocket.close(code=1011, reason="Internal error")
