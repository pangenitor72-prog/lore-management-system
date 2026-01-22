"""API layer - FastAPI routes and WebSocket handlers."""

from src.mantle.api.routes import app, router
from src.mantle.api.dependencies import get_neo4j_db

__all__ = [
    "app",
    "router",
    "get_neo4j_db",
]
