"""Shared fixtures. Tests never touch the network: Redis is fakeredis, SQLite is a temp file."""

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.cache import get_cache
from app.main import create_app
from app.settings import Settings, get_settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(db_path=str(tmp_path / "test.db"), redis_url="redis://unused")


@pytest.fixture
def cache() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(settings, cache) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_cache] = lambda: cache
    return TestClient(app)


@pytest.fixture
def order_payload() -> dict:
    return {"customer": "ada", "item": "keyboard", "quantity": 1, "amount_cents": 4999}
