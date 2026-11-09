"""SQLite storage for orders. The MCP server reads the same file (read-only)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Depends

from app.settings import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer     TEXT    NOT NULL,
    item         TEXT    NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity >= 1),
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    status       TEXT    NOT NULL DEFAULT 'created',
    created_at   TEXT    NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def create_order(
    conn: sqlite3.Connection, customer: str, item: str, quantity: int, amount_cents: int
) -> dict:
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO orders (customer, item, quantity, amount_cents, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (customer, item, quantity, amount_cents, created_at),
    )
    conn.commit()
    return get_order(conn, cur.lastrowid)


def get_order(conn: sqlite3.Connection, order_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def list_orders(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
