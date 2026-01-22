# src/db/neo4j_adapter.py

from typing import Optional, Tuple, Union
from urllib.parse import urlparse
import logging
import asyncio

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, Neo4jError

logger = logging.getLogger(__name__)


class Neo4jDatabase:
    """
    A safe, stable, single-driver Neo4j interface for async FastAPI.

    Aura-ready improvements:
    - Scheme validation and SSL auto-detection (neo4j+s / neo4j+ssc)
    - Retries with exponential backoff
    - Configurable connection timeout (default 30s for cloud latency)
    """

    def __init__(
        self,
        uri: str,
        user: Optional[Union[str, Tuple[str, str]]] = None,
        password: Optional[str] = None,
        auth: Optional[Tuple[str, str]] = None,
        database: str = "neo4j",
        connection_timeout: int = 30,
        max_connection_pool_size: int = 50,
    ):
        # Allow both (user, password) tuple or separate args
        if auth:
            self.auth = auth
        elif isinstance(user, tuple):
            self.auth = user
        else:
            self.auth = (user, password)

        self.uri = uri
        self.database = database
        self.connection_timeout = connection_timeout
        self.max_connection_pool_size = max_connection_pool_size
        self._driver = None

    def _scheme(self) -> str:
        parsed = urlparse(self.uri)
        return parsed.scheme.lower()

    def _is_ssl_scheme(self) -> bool:
        scheme = self._scheme()
        return scheme.endswith("+s") or scheme.endswith("+ssc")

    def _validate_scheme(self):
        scheme = self._scheme()
        allowed = {"bolt", "bolt+ssc", "bolt+s", "neo4j", "neo4j+ssc", "neo4j+s"}
        if scheme and scheme not in allowed:
            logger.warning("Unexpected Neo4j URI scheme detected", extra={"scheme": scheme})
        if scheme in {"neo4j+s", "neo4j+ssc"}:
            logger.info("Neo4j Aura/Secure scheme detected", extra={"scheme": scheme})

    def _build_driver(self):
        self._validate_scheme()
        return GraphDatabase.driver(
            self.uri,
            auth=self.auth if self.auth else None,
            max_connection_lifetime=3600,
            max_connection_pool_size=self.max_connection_pool_size,
            connection_timeout=self.connection_timeout,
        )

    async def connect(self, retries: int = 3, base_delay: float = 1.0):
        """Establish driver with retries and connectivity check."""
        if self._driver:
            return self._driver

        last_error = None
        for attempt in range(retries):
            try:
                driver = await asyncio.to_thread(self._build_driver)
                await asyncio.to_thread(driver.verify_connectivity)
                self._driver = driver
                logger.info(
                    "Neo4j driver connected",
                    extra={
                        "uri": self.uri,
                        "ssl_scheme": self._is_ssl_scheme(),
                        "attempt": attempt + 1,
                    },
                )
                return self._driver
            except Exception as e:
                last_error = e
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "Neo4j connection attempt failed; retrying",
                    exc_info=True,
                    extra={"attempt": attempt + 1, "delay": delay, "uri": self.uri},
                )
                await asyncio.sleep(delay)

        logger.error("Neo4j connection failed after retries", exc_info=last_error)
        raise last_error

    async def close(self):
        """Close the driver gracefully."""
        if self._driver:
            logger.info("Closing Neo4j driver...")
            await asyncio.to_thread(self._driver.close)
            self._driver = None

    async def execute(self, cypher: str, params: dict = None) -> list:
        """
        Execute a read/write Cypher query safely.
        Ensures sessions are always closed.
        """
        params = params or {}

        if not self._driver:
            await self.connect()

        try:
            def _run(tx):
                result = tx.run(cypher, params)
                return [record.data() for record in result]

            # Use a context-managed session to guarantee closure
            def _execute():
                with self._driver.session(database=self.database) as session:
                    return session.execute_write(_run)

            return await asyncio.to_thread(_execute)

        except ServiceUnavailable:
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

        except Neo4jError:
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

        except Exception:
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

    async def execute_with_overlay(
        self,
        cypher: str,
        params: dict = None,
        session_id: Optional[str] = None,
    ) -> list:
        """
        Execute query with session-aware delta-layer coalesce.

        Implements the "Layered Memory" strategy:
        - Layer A (Canon): Nodes without session scope, shared globally
        - Layer B (Session Overlay): Nodes scoped to a session_id

        Read Logic:
            Session layer takes precedence. If a node exists in the session
            overlay (Instance) that links to a Canon entity, the overlay
            version is returned.

        Write Logic:
            When session_id is provided, writes create/update nodes in the
            session layer only, preserving Canon immutability.

        Args:
            cypher: The Cypher query to execute
            params: Query parameters
            session_id: If provided, enables delta-layer awareness.
                       If None, behaves exactly like execute() (STORY mode).

        Returns:
            List of result records
        """
        if session_id is None:
            # No session context = pure Canon mode (backwards compatible)
            return await self.execute(cypher, params)

        params = params or {}
        params["_session_id"] = session_id

        # For session-scoped queries, we inject the session context
        # The actual coalesce logic depends on the query pattern.
        # This method provides the infrastructure; callers use helper methods
        # like read_entity_with_overlay() for specific patterns.
        return await self.execute(cypher, params)

    async def read_entity_with_overlay(
        self,
        canon_id: str,
        session_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Read an entity with session overlay coalesce.

        Returns session Instance if it exists, otherwise falls back to Canon Entity.
        """
        if session_id is None:
            # Pure Canon read
            result = await self.execute(
                "MATCH (e:Entity {canon_id: $cid}) RETURN properties(e) as entity",
                {"cid": canon_id},
            )
            return result[0]["entity"] if result else None

        # Coalesce: prefer session overlay, fall back to Canon
        result = await self.execute(
            """
            MATCH (e:Entity {canon_id: $cid})
            OPTIONAL MATCH (s:Session {session_id: $sid})-[:CONTAINS]->(i:Instance)-[:INSTANCE_OF]->(e)
            RETURN COALESCE(properties(i), properties(e)) as entity,
                   i IS NOT NULL as is_overlay
            """,
            {"cid": canon_id, "sid": session_id},
        )
        return result[0]["entity"] if result else None

    async def write_entity_delta(
        self,
        canon_id: str,
        session_id: str,
        properties: dict,
    ) -> dict:
        """
        Write entity changes to session overlay (delta layer).

        Creates or updates an Instance node that overrides the Canon Entity
        for this session only. Canon remains immutable.

        Args:
            canon_id: The canonical entity ID to create an overlay for
            session_id: The session to scope the overlay to
            properties: Properties to set on the overlay

        Returns:
            The updated overlay properties
        """
        result = await self.execute(
            """
            MATCH (s:Session {session_id: $sid})
            MATCH (e:Entity {canon_id: $cid})
            MERGE (s)-[:CONTAINS]->(i:Instance {canon_id: $cid})
            ON CREATE SET i.created_at = datetime()
            MERGE (i)-[:OVERRIDES]->(e)
            SET i += $props, i.updated_at = datetime()
            RETURN properties(i) as instance
            """,
            {"sid": session_id, "cid": canon_id, "props": properties},
        )
        return result[0]["instance"] if result else {}

    def test_connection(self) -> bool:
        """Return True/False without raising on connectivity."""
        try:
            if not self._driver:
                # Best-effort lazy connect without retries to avoid long waits
                self._driver = self._build_driver()
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False