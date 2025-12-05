# src/db/neo4j_adapter.py

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable, Neo4jError
import logging
import asyncio

logger = logging.getLogger(__name__)


class Neo4jDatabase:
    """
    A safe, stable, single-driver Neo4j interface for async FastAPI.

    Fixes:
    - Connection pooling issues
    - Async misuse
    - Driver re-instantiation
    - Unclosed sessions
    """

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        self._driver = GraphDatabase.driver(
            uri,
            auth=basic_auth(user, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_timeout=30,
        )
        self.database = database
        logger.info(f"Neo4j driver initialized for {uri}")

    async def close(self):
        """Close the driver gracefully."""
        if self._driver:
            logger.info("Closing Neo4j driver...")
            await asyncio.to_thread(self._driver.close)

    async def execute(self, cypher: str, params: dict = None) -> list:
        """
        Execute a read/write Cypher query safely.
        Ensures sessions are always closed.
        
        HARDENING PHASE FIX:
        - No silent failures.
        - Structured error logs.
        - Exceptions are re-raised with context.
        """
        params = params or {}

        try:
            def _run(tx):
                result = tx.run(cypher, params)
                return [record.data() for record in result]

            # Use a context-managed session to guarantee closure
            def _execute():
                with self._driver.session(database=self.database) as session:
                    return session.execute_write(_run)

            return await asyncio.to_thread(_execute)

        except ServiceUnavailable as e:
            logger.error(
                "Neo4j ServiceUnavailable",
                exc_info=True,
                extra={
                    "cypher": cypher,
                    "params": params,
                    "database": self.database,
                },
            )
            raise

        except Neo4jError as e:
            logger.error(
                "Neo4jError occurred",
                exc_info=True,
                extra={
                    "cypher": cypher,
                    "params": params,
                    "database": self.database,
                },
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected Neo4j exception",
                exc_info=True,
                extra={
                    "cypher": cypher,
                    "params": params,
                    "database": self.database,
                },
            )
            raise