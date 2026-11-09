"""A small, read-only MCP server over the orders database.

Run it through an MCP client (Claude Code, Codex, Cursor) or the Inspector:
    make seed && make mcp-inspect

Rules this server follows:
- Read-only: it opens SQLite with mode=ro, and every tool is annotated read_only_hint.
- Small outputs: tools return a few fields, not whole tables. Every token costs context.
- Errors the model can act on: raise ToolError with a hint. Any other exception reaches
  the model only as "Error executing tool <name>".
- stdout belongs to the protocol. Never print(); log to stderr if you must.
"""

import os
import sqlite3
from pathlib import Path
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

# The repo-root orders.db, wherever the client starts us from. ORDERS_DB overrides it.
DB_PATH = os.environ.get("ORDERS_DB") or str(Path(__file__).resolve().parents[1] / "orders.db")
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

mcp = MCPServer("orders")


def _query(sql: str, params: tuple = ()) -> list[dict]:
    if not Path(DB_PATH).exists():
        raise ToolError(f"No database at {DB_PATH}. Ask the user to run `make seed`.")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def get_order(order_id: int) -> dict:
    """Look up one order by its numeric id. Returns the order, or an error if it doesn't exist."""
    rows = _query("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not rows:
        raise ToolError(f"Order {order_id} not found. Use recent_orders to see valid ids.")
    return rows[0]


@mcp.tool(annotations=READ_ONLY)
def recent_orders(limit: Annotated[int, Field(ge=1, le=50)] = 10) -> list[dict]:
    """List the most recent orders, newest first (id, customer, item, status only)."""
    return _query(
        "SELECT id, customer, item, status FROM orders ORDER BY id DESC LIMIT ?", (limit,)
    )


@mcp.tool(annotations=READ_ONLY)
def order_stats() -> dict:
    """Count orders and sum their value, overall and per status."""
    total = _query("SELECT COUNT(*) AS orders, COALESCE(SUM(amount_cents), 0) AS cents FROM orders")
    by_status = _query("SELECT status, COUNT(*) AS orders FROM orders GROUP BY status")
    return {"total": total[0], "by_status": by_status}


@mcp.resource("orders://{order_id}")
def order_resource(order_id: int) -> dict:
    """One order as a resource the client application can attach to the context."""
    rows = _query("SELECT * FROM orders WHERE id = ?", (order_id,))
    return rows[0] if rows else {}


if __name__ == "__main__":
    mcp.run()  # stdio by default
