"""Order endpoints."""

import sqlite3

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app import db
from app.errors import APIError

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderIn(BaseModel):
    customer: str = Field(min_length=1, max_length=100)
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1, le=1000)
    amount_cents: int = Field(ge=0)


class OrderOut(OrderIn):
    id: int
    status: str
    created_at: str


@router.post("", status_code=201, response_model=OrderOut)
def create_order(order: OrderIn, conn: sqlite3.Connection = Depends(db.get_db)) -> dict:
    """Create an order."""
    return db.create_order(conn, **order.model_dump())


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, conn: sqlite3.Connection = Depends(db.get_db)) -> dict:
    """Fetch one order by id."""
    order = db.get_order(conn, order_id)
    if order is None:
        raise APIError(404, "order_not_found")
    return order


@router.get("", response_model=list[OrderOut])
def list_orders(
    limit: int = Query(default=20, ge=1, le=100),
    conn: sqlite3.Connection = Depends(db.get_db),
) -> list[dict]:
    """List the most recent orders, newest first."""
    return db.list_orders(conn, limit)
