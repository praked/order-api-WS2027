"""Talks to the real server over stdio, the way an agent does."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_server" / "orders_mcp.py"


@pytest.fixture
def seeded_db(tmp_path) -> str:
    path = str(tmp_path / "orders.db")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed.py")],
        env={**os.environ, "ORDERS_DB": path},
        check=True,
        capture_output=True,
    )
    return path


def _payload(result) -> object:
    if result.structured_content is not None:
        data = result.structured_content
        return data.get("result", data) if isinstance(data, dict) else data
    return json.loads(result.content[0].text)


async def _session(db_path: str):
    params = StdioServerParameters(
        command=sys.executable, args=[str(SERVER)], env={**os.environ, "ORDERS_DB": db_path}
    )
    async with Client(params) as client:
        tools = await client.list_tools()
        names = sorted(t.name for t in tools.tools)
        read_only = all(t.annotations and t.annotations.read_only_hint for t in tools.tools)
        order = _payload(await client.call_tool("get_order", {"order_id": 1}))
        missing = await client.call_tool("get_order", {"order_id": 999})
        recent = _payload(await client.call_tool("recent_orders", {"limit": 2}))
        stats = _payload(await client.call_tool("order_stats", {}))
        return names, read_only, order, missing, recent, stats


def test_server_over_stdio(seeded_db):
    names, read_only, order, missing, recent, stats = asyncio.run(_session(seeded_db))
    assert names == ["get_order", "order_stats", "recent_orders"]
    assert read_only
    assert order["customer"] == "ada"
    assert missing.is_error and "not found" in missing.content[0].text
    assert [o["id"] for o in recent] == [5, 4]
    assert stats["total"]["orders"] == 5


async def _no_db_session(db_path: str):
    params = StdioServerParameters(
        command=sys.executable, args=[str(SERVER)], env={**os.environ, "ORDERS_DB": db_path}
    )
    async with Client(params) as client:
        return await client.call_tool("order_stats", {})


def test_missing_database_gives_the_model_a_hint(tmp_path):
    result = asyncio.run(_no_db_session(str(tmp_path / "nope.db")))
    assert result.is_error and "make seed" in result.content[0].text
