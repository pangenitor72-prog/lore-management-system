import sqlite3
from pathlib import Path
from typing import Generator
import contextlib
from fastapi import Depends
import logging

logger = logging.getLogger("lms_db")

DB_FILE_PATH = Path("data/lore.db") # Renamed for clarity to avoid conflict with DB_PATH in Database class
DB_PATH = Path(__file__).parent.parent / DB_FILE_PATH # This is now the absolute path

def get_db_connection(db_path: str = str(DB_PATH)) -> sqlite3.Connection:
    """Establishes and returns a new database connection."""
    conn = sqlite3.connect(
    str(db_path),
    timeout=10.0,
    check_same_thread=False
)

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

@contextlib.contextmanager
def db_session(db_path: str = str(DB_PATH)) -> Generator[sqlite3.Connection, None, None]:
    """Provides a transactional database session as a context manager."""
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        logger.error(f"Database transaction failed: {e}. Rolling back.", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()

# Dependency for FastAPI to provide a DB connection per request
async def get_db() -> Generator[sqlite3.Connection, None, None]:
    # This will use the default file path
    with db_session() as conn:
        yield conn

class Database:
    """Utility class for database operations, especially schema initialization."""
    def __init__(self, db_file_path_str: str = str(DB_FILE_PATH)):
        self.db_path_str = db_file_path_str
        
        if self.db_path_str != ":memory:":
            db_path = Path(__file__).parent.parent / db_file_path_str
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = db_path
        else:
            self.db_path = ":memory:"

        self.schema_path = Path(__file__).parent.parent / "data/schema.sql"
        self._initialize_schema()

    def _initialize_schema(self):
        """Loads and executes the schema.sql file to create tables if they don't exist."""
        try:
            # Use db_session to ensure the schema is applied correctly.
            db_to_init = str(self.db_path) if self.db_path != ":memory:" else ":memory:"
            with db_session(db_path=db_to_init) as conn:
                with open(self.schema_path, 'r') as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
            logger.info(f"Schema initialized successfully for database: {db_to_init}")
        except Exception as e:
            logger.critical(f"Failed to initialize schema for {self.db_path}: {e}", exc_info=True)
            raise

    @staticmethod
    def create_tables(conn: sqlite3.Connection):
        """Creates tables in the given database connection."""
        schema_path = Path(__file__).parent.parent / "data/schema.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)

    # Static methods for core DB operations, taking a connection
    @staticmethod
    def execute(conn: sqlite3.Connection, query: str, params=(), commit: bool = False):
        """Executes a query. Can optionally commit immediately."""
        cur = conn.cursor()
        cur.execute(query, params)
        if commit:
            conn.commit()
        return cur

    @staticmethod
    def fetch_all(conn: sqlite3.Connection, query: str, params=()):
        logger.debug(f"Executing query: {query} with params: {params}")
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        logger.debug(f"Fetched rows: {rows}")
        try:
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error converting rows to dict: {e}", exc_info=True)
            raise

    @staticmethod
    def fetch_one(conn: sqlite3.Connection, query: str, params=()):
        cur = conn.cursor()
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None



    # The close and transaction methods are no longer needed for the refactored class
    # as db_session context manager handles connection lifecycle.