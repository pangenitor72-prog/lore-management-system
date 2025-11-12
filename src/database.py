import sqlite3
from pathlib import Path
import contextlib
from typing import Generator

DB_PATH = Path("data/lore.db")

class Database:
    def __init__(self, db_path="data/lore.db"):
        # Use the correct relative path from the root
        self.db_path = Path(__file__).parent.parent / db_path
        self.schema_path = Path(__file__).parent.parent / "data/schema.sql"

        # Ensure the database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Set timeout to 10 seconds (10.0)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        self.conn.row_factory = sqlite3.Row

        # Enable WAL (Write-Ahead Logging) mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL;")

        print(f"[DB] Connected to database at {self.db_path} (WAL Mode)")
        self._initialize_schema()

    def _initialize_schema(self):
        """Loads and executes the schema.sql file to create tables if they don't exist."""
        try:
            with open(self.schema_path, 'r') as f:
                schema_sql = f.read()

            # Use executescript to run all SQL commands in the file
            self.conn.executescript(schema_sql)
            self.conn.commit()
            print("[DB] Schema initialized successfully.")
        except Exception as e:
            print(f"[DB] CRITICAL: Failed to initialize schema: {e}")

    def execute(self, query, params=()):
        """Executes a query *without* committing."""
        cur = self.conn.cursor()
        cur.execute(query, params)
        # DO NOT COMMIT HERE - The transaction manager will handle it.
        return cur

    def fetch_all(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

    def fetch_one(self, query, params=()):
        cur = self.conn.cursor()
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

    @contextlib.contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Correctly manages a database transaction with commit and rollback."""
        try:
            yield self.conn
            # If yield succeeds, commit the changes
            self.conn.commit()
        except Exception as e:
            print(f"Transaction failed: {e}. Rolling back.")
            # If any error occurs, roll back all changes
            self.conn.rollback()
            raise