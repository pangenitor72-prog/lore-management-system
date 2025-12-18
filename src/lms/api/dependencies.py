
from fastapi import Request, HTTPException
from src.db.neo4j_adapter import Neo4jDatabase
from src.agents.auditor_agent import AuditorAgent
from src.agents.query_agent import QueryAgent
from src.agents.dm_agent import DMAgent


async def get_neo4j_db(request: Request) -> Neo4jDatabase:
    """Dependency to get the Neo4j database adapter from app state."""
    db = getattr(request.app.state, "neo4j_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db


async def get_auditor(request: Request) -> AuditorAgent:
    auditor = getattr(request.app.state, "auditor", None)
    if auditor is None:
        raise HTTPException(status_code=503, detail="Auditor agent not available")
    return auditor


async def get_query_agent(request: Request) -> QueryAgent:
    query_agent = getattr(request.app.state, "query_agent", None)
    if query_agent is None:
        raise HTTPException(status_code=503, detail="Query agent not available")
    return query_agent


async def get_dm_agent(request: Request) -> DMAgent:
    dm_agent = getattr(request.app.state, "dm_agent", None)
    if dm_agent is None:
        raise HTTPException(status_code=503, detail="DM agent not available")
    return dm_agent