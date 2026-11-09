"""Application settings. All configuration is read here, never via os.environ elsewhere."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("ORDERS_DB", "orders.db"))
    redis_url: str = field(
        default_factory=lambda: os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    )


_settings = Settings()


def get_settings() -> Settings:
    """FastAPI dependency. Tests override it with a temporary database."""
    return _settings
