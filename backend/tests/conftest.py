"""Shared test fixtures."""

import pytest
from fastapi import FastAPI

from cinescout.api.routes import cinemas, health, showings


@pytest.fixture
def test_app() -> FastAPI:
    """Minimal FastAPI app without the APScheduler lifespan, for API tests."""
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(cinemas.router, prefix="/api")
    app.include_router(showings.router, prefix="/api")
    return app
