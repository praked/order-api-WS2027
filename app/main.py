"""FastAPI application factory."""

from fastapi import FastAPI

from app.errors import install_error_handlers
from app.routes import health, orders


def create_app() -> FastAPI:
    app = FastAPI(title="orders-api", version="0.1.0")
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(orders.router)
    return app


app = create_app()
