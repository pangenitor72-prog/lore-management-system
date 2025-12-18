# src/ui/api_client.py

"""
Production-Safe API Client for LMS / MANTLE / AIRPG
"""

from __future__ import annotations
import logging
import requests
from typing import Any, Dict, List, Optional
from requests import Response

logger = logging.getLogger(__name__)

# CONFIGURATION
BASE_URL = "http://localhost:9000"
DEFAULT_TIMEOUT: int = 30  # Increased for slow LLM generation

class APIClientError(Exception):
    """Generic wrapper for API-related exceptions."""
    pass

# --- INTERNAL HELPERS ---

def _handle_response(resp: Response) -> Any:
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error(f"API Error {resp.status_code}: {resp.text}")
        raise APIClientError(f"API request failed: {resp.status_code}") from e

    try:
        return resp.json()
    except ValueError as e:
        raise APIClientError("Invalid JSON response from API") from e

def _post(path: str, payload: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        return _handle_response(resp)
    except requests.RequestException as e:
        raise APIClientError(f"Connection failed to {url}") from e

def _get(path: str) -> Any:
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        return _handle_response(resp)
    except requests.RequestException as e:
        raise APIClientError(f"Connection failed to {url}") from e

# --- PUBLIC CLIENT FUNCTIONS ---

# 1. CORE LORE & ENTITIES
def query_lore(query: str) -> Dict[str, Any]:
    return _post("/query", {"query": query})

def get_entity(entity_id: str) -> Dict[str, Any]:
    return _get(f"/entities/{entity_id}")

def ingest_file(file_text: str, filename: str) -> Dict[str, Any]:
    return _post("/upload/text", {"filename": filename, "content": file_text})

# 2. GAME LOOP (The DM Agent)
def send_dm_action(action: str, session_id: str = "default") -> Dict[str, Any]:
    """Send player input to the AI DM and get the narrative response."""
    return _post("/dm/next", {"action": action, "session_id": session_id})

# 3. VISUALIZATION
def fetch_graph_data() -> Dict[str, Any]:
    """Get the node/edge data for the visualizer."""
    return _get("/graph/basic")

# 4. AUDIT & REVIEW
def run_audit() -> Dict[str, Any]:
    """Trigger a full world scan."""
    return _post("/audit/run", {})

def get_pending_contradictions() -> List[Dict[str, Any]]:
    """Fetch contradictions waiting for human review."""
    return _get("/review/pending")

def resolve_contradiction(contradiction_id: int, resolution_notes: str) -> Dict[str, Any]:
    """Mark a contradiction as resolved."""
    return _post("/review/resolve", {"id": contradiction_id, "notes": resolution_notes})
