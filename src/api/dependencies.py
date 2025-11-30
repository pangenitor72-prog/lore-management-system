from fastapi import Request
from src.db.neo4j_adapter import Neo4jDatabase

async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    """Dependency to get the Neo4j database adapter from app state."""
    return request.app.state.neo4j_db
