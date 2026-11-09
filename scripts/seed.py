"""Create orders.db with a few sample orders so the MCP server has something to show."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402

SAMPLES = [
    ("ada", "keyboard", 1, 4999),
    ("grace", "monitor", 2, 38900),
    ("alan", "usb-c cable", 3, 1497),
    ("barbara", "laptop stand", 1, 2999),
    ("edsger", "mouse", 1, 2499),
]


def main() -> None:
    path = os.environ.get("ORDERS_DB", "orders.db")
    conn = db.connect(path)
    for customer, item, quantity, amount_cents in SAMPLES:
        db.create_order(conn, customer, item, quantity, amount_cents)
    conn.execute("UPDATE orders SET status = 'shipped' WHERE customer IN ('ada', 'alan')")
    conn.commit()
    print(f"Seeded {len(SAMPLES)} orders into {path}")


if __name__ == "__main__":
    main()
