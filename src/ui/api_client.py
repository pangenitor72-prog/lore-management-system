# src/ui/api_client.py

"""
Production-Safe API Client for LMS / MANTLE / AIRPG

This module provides a typed, controlled interface for
UI code (e.g., Streamlit or TUI) to interact with the FastAPI backend.

Goals:
- Replace direct agent/database imports inside app.py
- Prevent accidental creation of duplicate drivers or agents
- Provide clean, stable HTTP wrappers with timeouts + error handling
- Keep logic OUT of app.py (Hardening Phase Requirement)

This file is intentionally conservative and does NOT introduce
business logic — it is merely an HTTP boundary wrapper.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from requests import Response

logger = logging.getLogger(__name__)

# Adjustable when deployed
BASE_URL: str = "http://localhost:8000"

# Default timeout for all API calls (seconds)
DEFAULT_TIMEOUT: int = 10


class APIClientError(Exception):
    """Generic wrapper for API-related exceptions."""
    pass


def _handle_response(resp: Response) -> Dict[str, Any]:
    """
    Centralized response handling:
    - Raises clear exceptions on non-200 responses
    - Parses JSON safely
    """
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error(
            "API returned an error",
            extra={"status": resp.status_code, "body": resp.text},
        )
        raise APIClientError(f"API request failed: {resp.status_code}") from e

    try:
        return resp.json()
    except ValueError as e:
        logger.error("Failed to parse JSON response", exc_info=True)
        raise APIClientError("Invalid JSON response from API") from e


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe POST wrapper with timeout and unified error handling.
    """
    url = f"{BASE_URL}{path}"

    try:
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.Timeout as e:
        logger.error(f"API timeout contacting {url}")
        raise APIClientError(f"Request to {url} timed out") from e
    except requests.RequestException as e:
        logger.error(f"Connection error contacting {url}", exc_info=True)
        raise APIClientError(f"Could not reach API endpoint: {url}") from e

    return _handle_response(resp)


def _get(path: str) -> Dict[str, Any]:
    """
    Safe GET wrapper with timeout and unified error handling.
    """
    url = f"{BASE_URL}{path}"

    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
    except requests.Timeout as e:
        logger.error(f"API timeout contacting {url}")
        raise APIClientError(f"Request to {url} timed out") from e
    except requests.RequestException as e:
        logger.error(f"Connection error contacting {url}", exc_info=True)
        raise APIClientError(f"Could not reach API endpoint: {url}") from e

    return _handle_response(resp)


# ----------------------------------------------------------------------
# PUBLIC CLIENT FUNCTIONS
# These wrappers should replace all direct agent/database usage in app.py
# ----------------------------------------------------------------------

def query_lore(query: str) -> Dict[str, Any]:
    """Send a free-form query to the QueryAgent endpoint."""
    payload = {"query": query}
    return _post("/query", payload)


def create_entity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Request creation of an entity via the API."""
    return _post("/entities", data)


def get_entity(entity_id: str) -> Dict[str, Any]:
    """Retrieve a single entity by ID."""
    return _get(f"/entities/{entity_id}")


def ingest_file(file_text: str, filename: str) -> Dict[str, Any]:
    """
    Ingest raw text content into the system.
    (For future: convert this to multipart/form-data when ready.)
    """
    payload = {
        "filename": filename,
        "content": file_text,
    }
    return _post("/upload/text", payload)


def audit_world() -> Dict[str, Any]:
    """Trigger a world-wide audit scan via the backend."""
    return _post("/audit/run", {})


# End of api_client.py