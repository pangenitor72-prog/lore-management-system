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
        # Validate URI
        if not uri or not uri.strip():
            raise ValueError("Neo4j URI cannot be empty")
        
        # Allow both (user, password) tuple or separate args
        if auth:
            self.auth = auth
        elif isinstance(user, tuple):
            self.auth = user
        elif user is not None:
            self.auth = (user, password)
        else:
            self.auth = None
        
        # Validate auth credentials
        if not self.auth:
            raise ValueError("Neo4j auth must be a tuple of (username, password)")
        
        if not isinstance(self.auth, tuple) or len(self.auth) != 2:
            raise ValueError("Neo4j auth must be a tuple of (username, password)")
        
        if not self.auth[0] or not self.auth[0].strip():
            raise ValueError("Neo4j username cannot be empty")
        
        if not self.auth[1] or not self.auth[1].strip():
            raise ValueError("Neo4j password cannot be empty")

        self.uri = uri.strip()
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