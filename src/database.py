# src/database.py
"""
Database helpers for Lore Management System
- Per-transaction sqlite3 connections (no shared long-lived connection)
- transaction() context manager that commits on success and rollbacks on exception
- execute_and_commit helper for single-statement writes
- fetch_one / fetch_all helpers that use short-lived connections
"""
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Generator, Iterable, Optional, Any

DB_FILE_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "lore.db"
SCHEMA_PATH_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "schema.sql"


def _open_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    db_path = db_path or DB_FILE_DEFAULT
    conn = sqlite3.connect(str(db_path), timeout=30.0, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    # Recommended for concurrency when using sqlite
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        # Non-fatal if PRAGMA unsupported
        pass
    return conn


@contextmanager
def transaction(db_path: Optional[Path | str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for an atomic DB transaction using a fresh sqlite3 connection.
    Commits on exit, rolls back on exception, and always closes the connection.

    Usage:
        with transaction() as conn:
            cur = conn.cursor()
            cur.execute(...)
    """
    conn = _open_connection(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            # ensure we don't mask original exception
            pass
        raise
    finally:
        conn.close()


def execute_and_commit(sql: str, params: Iterable[Any] = (), db_path: Optional[Path | str] = None) -> sqlite3.Cursor:
    """
    Execute a single statement inside a transaction and commit immediately.
    Returns the cursor so callers can inspect lastrowid or rowcount.
    """
    with transaction(db_path) as conn:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        return cur


def fetch_all(sql: str, params: Iterable[Any] = (), db_path: Optional[Path | str] = None) -> list[dict]:
    """
    Run a read query using a short-lived connection and return list of dict rows.
    """
    conn = _open_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_one(sql: str, params: Iterable[Any] = (), db_path: Optional[Path | str] = None) -> Optional[dict]:
    conn = _open_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def initialize_schema(db_path: Optional[Path | str] = None, schema_path: Optional[Path | str] = None) -> None:
    """
    Create DB file directory if needed and initialize schema from schema.sql if present.
    This uses its own short-lived connection.
    """
    db_path = db_path or DB_FILE_DEFAULT
    schema_path = schema_path or SCHEMA_PATH_DEFAULT

    db_path = Path(db_path)
    db_dir = db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)

    conn = _open_connection(db_path)
    try:
        if Path(schema_path).is_file():
            with open(schema_path, "r", encoding="utf-8") as f:
                sql = f.read()
            conn.executescript(sql)
            conn.commit()
    finally:
        conn.close()